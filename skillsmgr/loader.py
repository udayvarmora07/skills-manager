"""Shared SKILL.md loader and directory scanner.

Single implementation used by Store (global DB) and scopes (external agent
dirs). Keeps FS parsing consistent; FS stays source of truth.
"""

from __future__ import annotations

import copy
import hashlib
import os
import threading
from collections import OrderedDict
from pathlib import Path

from .frontmatter import FrontmatterError, parse_frontmatter
from .observations import document_observations
from . import path_safety
from .documents import (
    ACTIVE_DOCUMENT,
    DISABLED_DOCUMENT,
    DOCUMENT_NAMES,
    read_skill_text,
)
from .errors import SkillNotFound, StoreError
from .tokens import estimate as _estimate_tokens
from .registry import read_provenance
from .validator import validate_skill_name
from .clock import now_iso


def _coerce_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def required_field_gaps(data: dict) -> list[str]:
    """Return the required frontmatter fields a document is missing (BUG-2).

    ``validator.validate_text`` reports a document with no ``name`` or no
    ``description`` as two ``error``-level issues, while the loader used to mark
    it perfectly loadable -- so ``doctor --explain`` called a document the
    validator rejects an effective, shadowing skill.  The same rule is applied
    here so both halves of the tool agree about the same file.
    """
    gaps: list[str] = []
    for field in ("name", "description"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            gaps.append(field)
    return gaps


def _probe_document(skill_dir: Path) -> tuple[str | None, int, str | None, bool]:
    """Pick a skill's document, reporting unreadable files and the conflict state.

    Returns ``(text, disabled, read_error, conflict)``.  One such entry used to
    abort *every* scope view with a raw ``PermissionError`` (SCOPE-4), so an
    unreadable document is reported as drift with the reason rather than being
    allowed to take the whole scan down.

    **[SPEC]** Existence is decided with :func:`os.stat`, not ``is_file()``.
    ``Path.is_file()`` *raised* ``PermissionError`` for a document inside an
    unreadable directory up to Python 3.13 and **returns False** in 3.14, so
    probing with it made the same store report drift on one version and raise
    ``SkillNotFound`` on another -- issue #13's contract, silently split by
    the interpreter.  Stat-ing directly tells "absent" apart from "cannot be
    read" on every supported version (3.10-3.14).

    ``conflict`` is the same answer :func:`conflicting_documents` gives, taken
    from the probe this function has to make anyway instead of re-stat'ing
    both names for every loaded document (docs/24 §D1): with an active
    document the only remaining question is whether the disabled one is also
    there, and with a disabled document the active one is already known absent.
    """
    for filename, disabled in ((ACTIVE_DOCUMENT, 0), (DISABLED_DOCUMENT, 1)):
        candidate = skill_dir / filename
        try:
            os.stat(candidate)
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError as exc:
            return None, disabled, f"{candidate} cannot be read ({exc.strerror or exc})", False
        try:
            text, decode_error = read_skill_text(candidate)
        except OSError as exc:
            return None, disabled, f"{candidate} cannot be read ({exc.strerror or exc})", False
        other = DISABLED_DOCUMENT if not disabled else ACTIVE_DOCUMENT
        return text, disabled, decode_error, (skill_dir / other).is_file()
    return None, 0, None, False


def name_is_addressable(name: str) -> bool:
    """True when *name* passes the canonical skill-name rule (BUG-10, SCOPE-14).

    The loader reads whatever the filesystem holds, so it can emit a directory
    name that every writer refuses: a dot-directory (``.hidden-skill``), an
    ``Upper-Case`` or ``with_underscore`` name, or an NFC/NFD pair.  Those rows
    used to be listed as ordinary skills and then raised
    ``invalid skill name`` the moment the user clicked them, with no way to
    clean them up through the tool.  They stay visible -- the filesystem is the
    source of truth -- but they are marked so no caller presents them as
    addressable.
    """
    try:
        validate_skill_name(name)
    except ValueError:
        return False
    return True


def _link_escape_record(skill_dir: Path, reason: str) -> dict:
    """Build the malformed row for a skill directory that links out of its root.

    Shaped like any other loaded entry; the empty body and the reason are what
    surface the drift (SCOPE-2).
    """
    token = _estimate_tokens("")
    record = {
        "name": skill_dir.name,
        "disabled": 0,
        "malformed": True,
        "document_missing": False,
        "decode_error": reason,
        "document_conflict": False,
        "missing_required": [],
        "addressable": name_is_addressable(skill_dir.name),
        "description": "",
        "body": "",
        "category": "uncategorized",
        "license": None,
        "version": None,
        "tokens": token["tokens"],
        "tokens_method": token["method"],
        "tokens_pct": token["pct_window"],
        "chars": token["chars"],
        "link_escape": True,
    }
    record.update(document_observations(skill_dir, "", {}))
    return record


def _peer_link_record(skill_dir: Path, link_roots: tuple[Path, ...]) -> dict | None:
    """Read a skill directory that links into another managed scope root.

    SCOPE-2 refuses a link out of its own root so a write can never land
    outside a managed root and the tool never reads an unmanaged location.
    Both properties survive here: the resolved target must lie inside one of
    ``link_roots`` -- the *already-resolved* bases of the other known scope
    roots -- and it is re-checked with the same containment guard that peer
    root's own scan uses.  Only then is the document loaded.

    The returned row keeps the link's own on-disk ``path`` so a caller can
    show the entry it found, while ``linked_to`` and ``link_target_root`` name
    the resolved target and its peer root.  ``read_only``/``link_followed``
    tell every writer and interface this copy must not be mutated through the
    link.

    ``None`` means "not followable": a link into anything that is not a peer
    root, a dangling link, a target that fails the peer guard, or a peer target
    holding no document.  The caller then builds today's escape record, byte
    for byte.
    """
    if not link_roots:
        return None
    try:
        target = Path(os.path.realpath(skill_dir))
        if not target.is_dir():
            return None
    except OSError:
        return None
    for peer_root in link_roots:
        try:
            if target != peer_root and not target.is_relative_to(peer_root):
                continue
            relative = target.relative_to(peer_root)
        except (AttributeError, ValueError):
            continue
        if not relative.parts:
            continue
        try:
            contained = path_safety.contained_entry_under(peer_root, *relative.parts)
        except ValueError:
            continue
        try:
            record = load_skill(contained)
        except (SkillNotFound, OSError):
            return None
        record["path"] = str(skill_dir)
        record["linked_to"] = str(target)
        record["link_target_root"] = str(peer_root)
        record["read_only"] = True
        record["link_followed"] = True
        return record
    return None


def _unreadable_record(skill_dir: Path, read_error: str, disabled: int) -> dict:
    """Build the malformed row for a document that could not be opened.

    Shaped like any other loaded entry so every consumer (list, get, scan,
    doctor, scope views) keeps working; the empty body and the ``decode_error``
    reason are what surface the drift (SCOPE-4).
    """
    token = _estimate_tokens("")
    record = {
        "name": skill_dir.name,
        "disabled": disabled,
        "malformed": True,
        "document_missing": False,
        "decode_error": read_error,
        "document_conflict": False,
        "missing_required": [],
        "addressable": name_is_addressable(skill_dir.name),
        "description": "",
        "body": "",
        "category": "uncategorized",
        "license": None,
        "version": None,
        "tokens": token["tokens"],
        "tokens_method": token["method"],
        "tokens_pct": token["pct_window"],
        "chars": token["chars"],
    }
    record.update(document_observations(skill_dir, "", {}))
    return record


def document_reuse_worthwhile(document_count: int) -> bool:
    """Whether reuse can pay for itself across *document_count* documents.

    **[SPEC]** A bounded LRU cannot beat a sequential scan larger than its own
    bound.  The scan visits documents in a stable order, so by the time a second
    pass reaches a document the first pass published, that entry has long since
    been evicted: the hit rate collapses to *zero* and the reader pays the
    bookkeeping for no reuse at all.  Measured at 5,000 documents through a
    1,000-entry bound, the second pass re-derived 5,001 documents.

    Above the bound the honest answer is therefore to skip reuse rather than
    thrash -- the caller keeps exactly the behaviour it had before the reuse
    existed, with none of its cost.

    **[SPEC] The bound is compared against what is *already retained*, not
    against this scan alone.**  The cache is process-global module state while
    every caller measures one batch, and the merged Library view
    (``scopes.list_all()``) walks the scopes in sequence.  Judging each scope on
    its own made eight 700-skill scopes each read "700 <= 4096, reuse is on"
    against a 5,600-document aggregate: measured 0% reuse and +9.6% over running
    with reuse off, which is the failure this function exists to prevent.
    Counting occupancy turns the aggregate case into a partial win -- the early
    scopes still hit, the later ones are skipped rather than thrashing.

    **[?] This mitigates the aggregate case; it does not solve it.** Measured
    on a merged sweep of 8 scopes x 700 documents against the 4,096 bound, warm:
    reuse off 821.4 ms, per-scan judgement 892.0 ms (+8.6%), occupancy-aware
    872.3 ms (+6.2%). Once the *working set* exceeds the bound an LRU cannot hit
    above its own size no matter how the decision is sliced, so a net loss over
    running with reuse off is structural, not a bug in the slicing. The correct
    fix is an aggregate decision made once by ``scopes.list_all()`` and threaded
    down through ``scan_scope``/``scan_dir``; it needs the merged candidate
    count, which for a recursive scope is the walk itself. Recorded rather than
    half-built: the real library measured on this machine is ~1,965 documents,
    well under the bound, where reuse wins ~30%.

    Taking the lock here is safe: every caller decides *outside*
    ``_document_cache_lookup``/``_document_cache_store``.
    """
    return document_cache_size() + document_count <= MAX_DOCUMENT_CACHE


#: Bounded, process-local reuse of a derived document record.
#:
#: **Why the key is the content hash and not ``(mtime_ns, size)``.**  The audit
#: recommended the latter; measurement rejected it on this repository's
#: supported platforms.  An ``(mtime_ns, size)`` key is blind by construction to
#: an edit that keeps the byte count identical and lands inside the filesystem's
#: mtime granularity, which is one second on HFS+ and two on FAT and is
#: routinely one on network mounts.  A content hash has no granularity at all:
#: different bytes are always a different key, so the reused record is provably
#: the record those exact bytes produce.  Reading the document is required to
#: learn the hash, so the guarantee is exact rather than statistical, and the
#: read is the cheapest part of the work.
#:
#: **What the key must also carry, because it is not a fact about the bytes.**
#: ``disabled`` and ``document_conflict`` describe which of the two document
#: names exists and whether the *other* one does too -- ``SKILL.md`` and
#: ``SKILL.md.disabled`` may hold byte-identical content, and a second document
#: dropped in beside an unchanged one is exactly the state a toggle would
#: destroy (STORE-3/SCOPE-13).  The document path is therefore part of the key,
#: which carries the name, and ``decode_error`` is carried because two different
#: undecodable byte sequences can produce the same U+FFFD replacement text.
#:
#: **Why 4,096.**  One request derives every document in every scope, so the
#: bound has to exceed a full library or :func:`document_reuse_worthwhile`
#: switches reuse off.  4,096 covers roughly twice the largest library measured
#: here (2,000 rows) and retains about 3.5 KiB per entry (measured: 3.6x its own
#: document), so the ceiling is about 14 MiB.
MAX_DOCUMENT_CACHE = 4096

#: The only record values that are containers rather than immutable scalars.
#: Everything else a loader record holds is a ``str``/``int``/``float``/``bool``/
#: ``None``, so copying the mapping and copying these is equivalent to a
#: whole-record ``copy.deepcopy`` -- pinned against ``copy.deepcopy`` on real
#: records by ``test_the_isolated_copy_equals_a_whole_record_deepcopy`` -- and it
#: is paid on *every* load, hit or miss, so its cost lands on both.
#:
#: ``missing_required`` was missing from this list and is a ``list``.  Because
#: ``dict(record)`` copies only the mapping, the cached entry, every hit and
#: every caller all shared one list object: a caller appending to it wrote
#: straight through into the cache and into every later read in the process.
#: Nothing mutated it at the time, so the promise was false rather than the
#: behaviour being wrong -- which is the harder defect to notice.
_MUTABLE_RECORD_KEYS = (
    "portable_frontmatter",
    "frontmatter_extensions",
    "missing_required",
    "provenance",
    "registry_provenance",
)

#: Beyond this nesting depth the value is handed to ``copy.deepcopy``, which is
#: both cycle-safe and exact.  Frontmatter cannot reach it; the constant exists
#: so an unexpectedly deep or self-referential value is copied *correctly*
#: rather than by a recursion this module would have to get right forever.
_COPY_MAX_DEPTH = 12
_COPY_SCALARS = (str, bytes, int, float, bool, type(None))


_document_cache: "OrderedDict[tuple, dict]" = OrderedDict()
_document_cache_lock = threading.Lock()


def _copy_value(value, depth: int = 0):
    """Return a copy of *value* sharing no mutable object with it.

    Equivalent to ``copy.deepcopy`` for the values a loader record can hold --
    JSON-shaped data from the frontmatter parser and from ``json.loads`` -- and
    measured at roughly a third of its cost, which matters because this runs on
    every load.  Anything it does not recognise, and anything deeper than
    :data:`_COPY_MAX_DEPTH`, is handed straight to ``copy.deepcopy``.
    """
    if value.__class__ in _COPY_SCALARS:
        return value
    if depth >= _COPY_MAX_DEPTH:
        # Deliberately NOT ``return value``. Returning the value itself would
        # hand the caller and the cache the same object, which is strictly
        # worse than the sharing ``deepcopy`` would have avoided -- the docstring
        # above promised a copy and this branch was not one.
        return copy.deepcopy(value)
    if isinstance(value, dict):
        return {key: _copy_value(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_value(item, depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_value(item, depth + 1) for item in value)
    return copy.deepcopy(value)


def isolated_record(record: dict) -> dict:
    """Return a copy of *record* sharing no mutable object with it.

    Callers annotate what they are handed -- ``scopes.scan_scope`` writes
    ``record["provenance"]["scope"]``, the store writes ``"global"`` -- so
    neither the cache nor one caller may ever reach another's object.
    """
    out = dict(record)
    for key in _MUTABLE_RECORD_KEYS:
        value = out.get(key)
        if isinstance(value, (dict, list, tuple)):
            out[key] = _copy_value(value)
    return out


def _document_cache_key(
    skill_dir: Path, document: str, text: str, disabled: int, conflict: bool, decode_error
) -> tuple:
    """Identity of one *derivation*, from the bytes and the filesystem facts.

    The document's own path leads the key because the derived record reports it
    verbatim as ``provenance.path``: two callers reach the same physical file
    through different spellings -- ``scan_dir`` addresses a skill below the
    *resolved* scope root, ``hygiene`` through a recursive record's ``path``
    below the unresolved base -- and each has always reported the spelling it
    was given.  ``os.path.realpath`` was the obvious identity here and was
    measured: it costs one ``lstat`` per path component and buys nothing this
    spelling does not already buy, because ``scan_dir`` hands every scope the
    same resolved root.  So does ``skill_dir / document``: building a second
    ``Path`` re-parsed every component and cost 17 microseconds per load against
    1 for the concatenation below.

    The path already carries the document's *name*, so it and ``disabled`` are
    each redundant with the other; both are kept because neither is the kind of
    thing to infer later, and each costs nothing.
    """
    return (
        str(skill_dir) + os.sep + document,
        hashlib.sha256(text.encode("utf-8")).hexdigest(),
        disabled,
        conflict,
        decode_error,
    )


def _document_cache_lookup(key: tuple) -> dict | None:
    """Return an independent copy of a cached record, or ``None``.

    The copy is re-stamped on the way out.  A hit is still a genuine
    observation: the document was re-read and re-hashed to *prove* these are
    the same bytes, so ``observed_at`` must say when this read happened rather
    than when this process first derived them -- otherwise a refresh button
    reports an observation from before the session started, and the field stops
    meaning what ``document_observations`` says it means.  It reaches the
    global Store too (``observed_at`` is in ``Store._OBSERVED_KEYS``).

    The stamp lands on the copy, never on the stored entry: an entry whose
    stamp crept forward on every hit would describe nothing at all.  One
    ``datetime.now()`` per hit is noise against the work a hit avoids.
    """
    with _document_cache_lock:
        record = _document_cache.get(key)
        if record is not None:
            _document_cache.move_to_end(key)
    if record is None:
        return None
    out = isolated_record(record)
    out["observed_at"] = now_iso()
    return out


def _document_cache_store(key: tuple, record: dict) -> None:
    """Publish a derived record, evicting the least recently used entries.

    A bounded table, because the web UI is a long-lived process and an
    unbounded one would grow for the life of the session.  Nothing is
    persisted: the table is module state and dies with the interpreter.
    """
    with _document_cache_lock:
        _document_cache[key] = record
        _document_cache.move_to_end(key)
        while len(_document_cache) > MAX_DOCUMENT_CACHE:
            _document_cache.popitem(last=False)


def document_cache_size() -> int:
    """Number of derived records currently held (read-only introspection)."""
    with _document_cache_lock:
        return len(_document_cache)


def clear_document_cache() -> None:
    """Drop every derived record.  Nothing on disk is affected."""
    with _document_cache_lock:
        _document_cache.clear()


def _registry_provenance_fields(skill_dir: Path) -> dict:
    """The registry sidecar answer for one skill, read on *every* load.

    Deliberately never reused.  A provenance sidecar is a filesystem fact
    rather than a fact about ``SKILL.md``'s bytes -- writing one changes nothing
    about the document -- and ``read_provenance`` additionally reconciles it
    against the skill directory's *other* files, which the document hash does
    not cover.  Reuse keyed on the document would therefore serve a stale
    provenance answer, so this probe is the one thing a warm read keeps doing.
    In a library that did not come from the registry it is one ``lexists``.
    """
    try:
        provenance = read_provenance(skill_dir)
    except (OSError, StoreError) as exc:
        return {"registry_provenance_error": str(exc)}
    return {"registry_provenance": provenance} if provenance is not None else {}


def _apply_registry_provenance(record: dict, fields: dict) -> dict:
    """Overlay a freshly probed sidecar answer onto *record*."""
    record.pop("registry_provenance", None)
    record.pop("registry_provenance_error", None)
    record.update(fields)
    if "registry_provenance_error" in fields:
        # A stale or malformed sidecar is drift, never silent trust.
        record["malformed"] = True
    return record


def load_skill(
    skill_dir: Path, *, include_husks: bool = False, reuse: bool = True
) -> dict:
    """Load one skill directory (SKILL.md or SKILL.md.disabled).

    An undecodable document never raises: it is reported as a ``malformed``
    row carrying ``decode_error`` so callers can surface drift instead of
    failing with a raw ``UnicodeDecodeError`` (issue #13).

    With ``include_husks`` a directory holding *no* document is reported as a
    ``malformed`` drift row instead of raising ``SkillNotFound`` (STORE-13);
    the store's own scans opt in, agent-scope scans keep the old contract.

    ``reuse=False`` skips the bounded derived-record reuse entirely, which is
    how :func:`document_reuse_worthwhile` is acted on: a caller that knows it is
    about to load more documents than the bound can hold passes ``False`` and
    keeps exactly the pre-reuse cost instead of thrashing.
    """
    text, disabled, read_error, conflict = _probe_document(skill_dir)
    if text is None:
        if read_error is None:
            if include_husks:
                # STORE-13: a directory with no document at all is drift the
                # store has to see; other consumers keep the historical
                # ``SkillNotFound`` contract.
                husk = _husk_record(skill_dir)
                husk["path"] = str(skill_dir)
                return husk
            raise SkillNotFound(
                f"skill '{skill_dir.name}' has no SKILL.md (or SKILL.md.disabled)"
            )
        # The document exists but could not be opened at all: still a skill on
        # disk, so report the row as malformed rather than letting the raw
        # PermissionError abort every scope view (SCOPE-4).
        return _unreadable_record(skill_dir, read_error, disabled)
    decode_error = read_error
    cache_key = None
    if reuse:
        # The document was read, so its bytes are known: everything below is a
        # pure function of those bytes plus the two filesystem facts the probe
        # already returned (``disabled`` and ``conflict``).  A repeat request
        # reuses the derived record instead of re-parsing, re-hashing,
        # re-estimating and re-probing the provenance sidecar (docs/24 §D1,
        # second half).  The probe still runs first, so a deleted document, a
        # rename, a conflicting second document and a decoding failure are each
        # still observed.
        cache_key = _document_cache_key(
            skill_dir,
            DISABLED_DOCUMENT if disabled else ACTIVE_DOCUMENT,
            text,
            disabled,
            conflict,
            decode_error,
        )
        cached = _document_cache_lookup(cache_key)
        if cached is not None:
            return _apply_registry_provenance(
                cached, _registry_provenance_fields(skill_dir)
            )
    # A mixed state is drift the user has to settle by hand (see
    # conflicting_documents, whose answer the probe already returned): the
    # invisible second document would be destroyed by the next toggle, so it
    # must never be reported as a healthy skill.
    malformed = decode_error is not None or conflict
    try:
        data, body = parse_frontmatter(text)
    except FrontmatterError:
        data, body = {}, text
        malformed = True
    # BUG-2: a document the *validator* rejects as an error must not be
    # reported as a loadable skill here, or doctor --explain confidently
    # announces an invalid skill as effective and shadowing a valid one.
    gaps = required_field_gaps(data)
    if gaps:
        malformed = True
    metadata = data.get("metadata")
    category = "uncategorized"
    if isinstance(metadata, dict) and isinstance(metadata.get("category"), str):
        category = metadata["category"] or "uncategorized"
    raw_text = text or ""
    tok = _estimate_tokens(raw_text)
    # BUG-10: a document that could only be read lossily must not put its
    # replacement-character text in front of the user or into stats -- the
    # decode_error is the signal, and mojibake is not a description.
    description = "" if decode_error is not None else _coerce_str(data.get("description"))
    record = {
        "name": skill_dir.name,
        "disabled": disabled,
        "malformed": malformed,
        "document_missing": False,
        "decode_error": decode_error,
        "encoding_error": decode_error is not None,
        "document_conflict": conflict,
        "missing_required": gaps,
        "addressable": name_is_addressable(skill_dir.name),
        "description": description,
        "body": body,
        "category": category,
        "license": data.get("license") if data.get("license") is not None else None,
        "version": _coerce_str(data.get("version")) if data.get("version") else None,
        "tokens": tok["tokens"],
        "tokens_method": tok["method"],
        "tokens_pct": tok["pct_window"],
        "chars": tok["chars"],
    }
    record.update(document_observations(skill_dir, raw_text, data))
    record["malformed"] = malformed
    # Publish a snapshot for the next read.  A copy, because callers annotate
    # the record they were handed; ``_document_cache_lookup`` copies again on
    # the way out, so no caller and the cache never share an object.  The
    # sidecar answer is deliberately not part of what is published.
    if cache_key is not None:
        _document_cache_store(cache_key, isolated_record(record))
    # Registry provenance is a filesystem sidecar, not an index column, and is
    # probed on every load so a stale or malformed one is visible drift rather
    # than silently being treated as trustworthy metadata.
    return _apply_registry_provenance(record, _registry_provenance_fields(skill_dir))


def _husk_record(skill_dir: Path) -> dict:
    """Build the drift row for a directory that holds no skill document.

    STORE-13: a directory whose document was destroyed (the husk an interrupted
    remove or a failed purge leaves behind) has no ``SKILL.md`` at all, so
    ``load_skill`` raises ``SkillNotFound`` and the directory was neither an
    orphan dir nor drift -- ``doctor()`` called the tree healthy and no read
    path could see it.  It is reported as drift instead of being skipped.
    """
    token = _estimate_tokens("")
    record = {
        "name": skill_dir.name,
        "disabled": 0,
        "malformed": True,
        "document_missing": True,
        "decode_error": f"{skill_dir} holds no SKILL.md (or SKILL.md.disabled)",
        "document_conflict": False,
        "missing_required": ["name", "description"],
        "description": "",
        "body": "",
        "category": "uncategorized",
        "license": None,
        "version": None,
        "tokens": token["tokens"],
        "tokens_method": token["method"],
        "tokens_pct": token["pct_window"],
        "chars": token["chars"],
    }
    record.update(document_observations(skill_dir, "", {}))
    return record


def _document_dirs(entries) -> set[Path]:
    """Parent directories of every skill document among *entries*.

    One walk collects both document names.  ``rglob("SKILL.md")`` and
    ``rglob("SKILL.md.disabled")`` each traverse the whole tree, so every
    recursive scope root was walked twice per request; ``rglob("*")`` visits
    exactly the same entries and the name test below selects the same set.
    """
    return {path.parent for path in entries if path.name in DOCUMENT_NAMES}


def scan_dir(
    root: Path,
    *,
    recursive: bool = False,
    include_husks: bool = False,
    annotate_paths: bool = False,
    link_roots: tuple[Path, ...] = (),
) -> list[dict]:
    """Scan a skill root, optionally walking nested skill directories.

    Recursive discovery is opt-in because consumers differ: some treat a root
    as a flat directory while Cursor/OpenCode-style project roots can organize
    skills below category or nested project directories.

    A directory whose document is unreadable is *kept* and marked ``malformed``
    (issue #13): the filesystem is the source of truth, so a skill that exists
    on disk must stay visible to ``doctor``/``resync`` as drift rather than
    silently vanish from the scan.

    ``include_husks`` additionally reports direct subdirectories that hold no
    document at all (STORE-13); it is off by default so agent-scope scans keep
    listing only real skills.

    ``annotate_paths`` records the validated document directory as ``path`` on
    every entry, including the flat ones that used to carry none.  The value is
    the *contained named entry* under the resolved root, which is exactly the
    path :func:`skillsmgr.scopes.scan_scope` otherwise re-derived per row --
    re-deriving it re-resolved the scope base and re-ran the containment check
    the scan had already performed, for every skill on every request (docs/24
    §D1).  It is opt-in because a flat record without ``path`` is what the
    other callers (``effective``, ``cli_handlers``, the web route) consume, and
    the records they see are unchanged.

    ``link_roots`` are the already-resolved bases of the *other* known managed
    scope roots.  A directory that is a symlink out of ``root`` is normally
    reported as drift (SCOPE-2); when its resolved target lies inside one of
    these peer roots it is read read-only instead
    (:func:`_peer_link_record`).  The default is empty, so every existing
    caller -- the global store above all -- keeps refusing those links.

    The scan also decides whether the derived-record reuse is worth running at
    all: a scan holding more documents than the bounded cache can hold would
    evict every entry before the next request reached it, so this one is
    measured up front and turned off (:func:`document_reuse_worthwhile`).
    """
    entries: list[dict] = []
    try:
        is_dir = root.is_dir()
    except OSError:
        return entries
    if not is_dir:
        return entries
    # SEC-10: resolve the root once for the whole scan.  Doing it per candidate
    # re-resolved the same path for every skill on every request.
    resolved_root = Path(root).expanduser().resolve()
    if recursive:
        try:
            candidates = sorted(_document_dirs(root.rglob("*")))
        except OSError:
            # One unsearchable directory in the tree must not abort the scan.
            candidates = sorted(_document_dirs(root.glob("*")))
    else:
        try:
            candidates = sorted(path for path in root.iterdir() if path.is_dir())
        except OSError:
            return entries
    reuse = document_reuse_worthwhile(len(candidates))
    for child in candidates:
        # A candidate enumerated from ``root`` itself is a direct child, and
        # its relative parts are its own name; only a deeper candidate (a
        # recursive root) needs the general form.  pathlib's ``relative_to``
        # reparses both operands and cost about as much as the containment
        # check below (docs/24 §D1).
        if child.parent == root:
            relative_parts: tuple[str, ...] = (child.name,)
        else:
            try:
                relative_parts = child.relative_to(root).parts
            except (ValueError, OSError):
                continue
        try:
            named = path_safety.contained_entry_under(resolved_root, *relative_parts)
        except ValueError as exc:
            # SCOPE-2: a skill directory that is a symlink out of the root is
            # invisible to every read view, yet every name-addressed operation
            # refuses it -- so the tool cannot list, view or repair skills its
            # own documented install workflow creates (``skills-mgr install``
            # symlinks unless ``--copy`` is given).  Report it as drift rather
            # than dropping it silently: the filesystem is the source of truth.
            #
            # A link into another managed scope root is the one exception: the
            # target is already in a managed root, so it is read read-only
            # here instead of being shown empty (SCOPE-2).
            followed = _peer_link_record(child, link_roots)
            if followed is not None:
                entries.append(followed)
                continue
            entry = _link_escape_record(child, str(exc))
            # Always carry the on-disk path: the record has no contained path
            # to derive, and the caller still has to show the user where the
            # offending entry lives.
            entry["path"] = str(child)
            entries.append(entry)
            continue
        try:
            entry = load_skill(
                named, include_husks=include_husks, reuse=reuse
            )
            if recursive:
                entry["path"] = str(child)
            elif annotate_paths:
                entry["path"] = str(named)
            entries.append(entry)
        except (SkillNotFound, OSError):
            continue
    return sorted(entries, key=lambda item: (item["name"].lower(), item.get("path", "")))
