"""Shared SKILL.md loader and directory scanner.

Single implementation used by Store (global DB) and scopes (external agent
dirs). Keeps FS parsing consistent; FS stays source of truth.
"""

from __future__ import annotations

from pathlib import Path

from .frontmatter import FrontmatterError, parse_frontmatter
from .observations import document_observations
from . import paths
from .store import SkillNotFound, StoreError
from .tokens import estimate as _estimate_tokens


def read_skill_text(path: Path) -> tuple[str, str | None]:
    """Read a skill document, tolerating invalid UTF-8 (issue #13).

    Returns ``(text, decode_error)``.  ``decode_error`` is ``None`` for a clean
    UTF-8 document; otherwise ``text`` keeps the document readable with U+FFFD
    replacement characters and the message names the file, the offending byte,
    and the fix.  Read/report paths mark the row ``malformed`` with that
    message; write paths must call :func:`read_skill_text_strict` instead, so
    lossy replacement characters can never be written back to disk.
    """
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return raw.decode("utf-8", errors="replace"), (
            f"{path} is not valid UTF-8 (byte 0x{raw[exc.start]:02x} at offset "
            f"{exc.start}); re-save it as UTF-8"
        )


def read_skill_text_strict(path: Path, *, subject: str) -> str:
    """Read a skill document that is about to be rewritten.

    Undecodable input fails closed as a clean :class:`StoreError` naming
    ``subject``; a caller must never rewrite a document it could only read
    lossily.
    """
    text, decode_error = read_skill_text(path)
    if decode_error is not None:
        raise StoreError(f"cannot safely rewrite {subject}: {decode_error}")
    return text


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


def conflicting_documents(skill_dir: Path) -> bool:
    """True when a skill directory holds *both* SKILL.md and SKILL.md.disabled.

    The store's one-document invariant: a skill is described by exactly one of
    the two names.  With both present, exactly one is visible to reads while a
    toggle (disable/enable) resolves the other as its source and renames it
    over the first, silently destroying one of the two documents -- with no
    snapshot taken.  Every entry point that toggles or installs a skill has to
    refuse this state instead of guessing.
    """
    return (skill_dir / "SKILL.md").is_file() and (skill_dir / "SKILL.md.disabled").is_file()


def read_skill_or_report(skill_dir: Path) -> tuple[str | None, int, str | None]:
    """Pick a skill's document and read it, reporting unreadable files.

    Returns ``(text, disabled, read_error)``.  ``is_file()`` and
    ``read_bytes()`` both raise ``OSError`` for an unreadable file or an
    unsearchable directory, and one such entry used to abort *every* scope
    view with a raw ``PermissionError`` (SCOPE-4).  The filesystem is the
    source of truth, so an unreadable document is reported as drift with the
    reason rather than being allowed to take the whole scan down.
    """
    for filename, disabled in (("SKILL.md", 0), ("SKILL.md.disabled", 1)):
        candidate = skill_dir / filename
        try:
            is_file = candidate.is_file()
        except OSError as exc:
            return None, disabled, f"{candidate} cannot be read ({exc.strerror or exc})"
        if not is_file:
            continue
        try:
            text, decode_error = read_skill_text(candidate)
        except OSError as exc:
            return None, disabled, f"{candidate} cannot be read ({exc.strerror or exc})"
        return text, disabled, decode_error
    return None, 0, None


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
    from .validator import validate_skill_name

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


def load_skill(skill_dir: Path, *, include_husks: bool = False) -> dict:
    """Load one skill directory (SKILL.md or SKILL.md.disabled).

    An undecodable document never raises: it is reported as a ``malformed``
    row carrying ``decode_error`` so callers can surface drift instead of
    failing with a raw ``UnicodeDecodeError`` (issue #13).

    With ``include_husks`` a directory holding *no* document is reported as a
    ``malformed`` drift row instead of raising ``SkillNotFound`` (STORE-13);
    the store's own scans opt in, agent-scope scans keep the old contract.
    """
    text, disabled, read_error = read_skill_or_report(skill_dir)
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
    # A mixed state is drift the user has to settle by hand (see
    # conflicting_documents): the invisible second document would be destroyed
    # by the next toggle, so it must never be reported as a healthy skill.
    conflict = conflicting_documents(skill_dir)
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
    return record


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


def scan_dir(root: Path, *, recursive: bool = False, include_husks: bool = False) -> list[dict]:
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
            candidates = sorted(
                {path.parent for path in root.rglob("SKILL.md")}
                | {path.parent for path in root.rglob("SKILL.md.disabled")}
            )
        except OSError:
            # One unsearchable directory in the tree must not abort the scan.
            candidates = sorted(
                {path.parent for path in root.glob("SKILL.md")}
                | {path.parent for path in root.glob("SKILL.md.disabled")}
            )
    else:
        try:
            candidates = sorted(path for path in root.iterdir() if path.is_dir())
        except OSError:
            return entries
    for child in candidates:
        try:
            relative = child.relative_to(root)
        except (ValueError, OSError):
            continue
        try:
            named = paths.contained_entry_under(resolved_root, *relative.parts)
        except ValueError as exc:
            # SCOPE-2: a skill directory that is a symlink out of the root is
            # invisible to every read view, yet every name-addressed operation
            # refuses it -- so the tool cannot list, view or repair skills its
            # own documented install workflow creates (``skills-mgr install``
            # symlinks unless ``--copy`` is given).  Report it as drift rather
            # than dropping it silently: the filesystem is the source of truth.
            entry = _link_escape_record(child, str(exc))
            # Always carry the on-disk path: the record has no contained path
            # to derive, and the caller still has to show the user where the
            # offending entry lives.
            entry["path"] = str(child)
            entries.append(entry)
            continue
        try:
            entry = load_skill(named, include_husks=include_husks)
            if recursive:
                entry["path"] = str(child)
            entries.append(entry)
        except (SkillNotFound, OSError):
            continue
    return sorted(entries, key=lambda item: (item["name"].lower(), item.get("path", "")))