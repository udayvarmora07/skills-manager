"""Skill scopes — global store plus per-agent filesystem roots.

Each scope is an independent SKILL.md tree we can list/search and write
into. Global scope is the skills-manager Store; every other scope is a
plain filesystem dir scanned on demand (no DB). Discovery probes real
paths at runtime; missing dirs show count 0.
"""

from __future__ import annotations

import os
import re
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from . import paths
from . import path_safety
from .diagnostics import diagnose as _diagnose
from .frontmatter import FrontmatterError, dump_frontmatter, parse_frontmatter
from .documents import (
    ACTIVE_DOCUMENT,
    DOCUMENT_NAMES,
    document_path,
    document_text,
    has_document,
    read_skill_text,
    read_skill_text_strict,
    reject_conflicting_documents,
    toggle_document,
)
from .loader import load_skill, scan_dir
from . import root_discovery as _root_discovery
from .atomic_io import atomic_write_text, mutation_lock
from .context import active_store
from .read_flights import coalesced_read
from .store import (
    SkillNotFound,
    Store,
    StoreError,
)
from .native_state import observe_native_entries
from .search import MAX_SEARCH_LENGTH, rank_results
from .store import list_snapshots, read_snapshot, write_snapshot, write_snapshot_bytes
from .tokens import aggregate, estimate
from .validator import MAX_COMPATIBILITY, MAX_DESCRIPTION, validate_skill_name
from .clock import STAMP_FORMAT, iso, stamp

_SCOPE_READ_FLIGHTS: dict = {}
_SCOPE_READ_FLIGHTS_LOCK = threading.Lock()


def _global_store() -> Store:
    store = active_store()
    return store if store is not None else Store()


def _global_skills_dir() -> Path:
    """Return the one authoritative skills tree for the ``global`` scope.

    SCOPE-9: ``known_scopes()`` derived the global root from the *environment*
    while ``scan_scope("global")`` derived it from the *injected Store*.  With
    an injected Store on another data dir the two disagreed, so
    ``sync_skill(..., ["global"])`` reported success while creating a
    destination that ``store.list()``, ``scan_scope("global")`` and
    ``get_skill("global", ...)`` could never see.  There is now one identity:
    the injected Store's own tree whenever a Store is injected.
    """
    store = active_store()
    return store.skills_dir if store is not None else paths.skills_dir()


def safe_scope_skill_path(scope: "Scope", name: str) -> Path:
    """Return a validated skill path contained by an agent scope root.

    Uses ``contained_entry`` rather than ``contained_path`` so the *named*
    entry is addressed (SCOPE-3): resolving the final component turned an
    in-root alias into the physical skill, so a write through the alias mutated
    a different skill than the one requested, the physical skill was listed
    twice, and remove() deleted the target while leaving a dangling link.
    """
    try:
        direct = path_safety.contained_entry(scope.base, name)
        # SCOPE-18: the flat short-circuit used to accept *any* directory with
        # the requested name, so `deploy/deploy/SKILL.md` resolved to the
        # grouping directory `deploy`, which holds no document -- the two views
        # then contradicted each other (scan listed the skill, get_skill
        # reported SkillNotFound).  Only short-circuit when the flat path really
        # is a skill; a non-recursive scope keeps the historical contract.
        if not scope.recursive or has_document(direct):
            return direct
        # Recursive consumers may discover a skill below a project/category
        # directory. Preserve the existing name-based public API by resolving
        # the first deterministic observed instance when the flat path is absent.
        resolved_base = _resolved_scope_root(scope)
        for record in scan_dir(scope.base, recursive=True):
            if record.get("name") == name and record.get("path"):
                try:
                    relative = Path(record["path"]).resolve().relative_to(resolved_base)
                except (ValueError, OSError):
                    continue
                return path_safety.contained_entry_under(resolved_base, *relative.parts)
        return direct
    except ValueError as exc:
        raise _refused_path_error(scope, name, exc) from exc


def _peer_link_roots(scope: "Scope") -> tuple[Path, ...]:
    """Resolved bases of the *other* managed agent roots (SCOPE-2).

    The global store is deliberately excluded to retain its containment policy;
    its filesystem remains authoritative and SQLite is only an index. A root is
    not a peer when missing, unreadable, or the same physical directory as this
    scope.
    """
    if scope.id == "global":
        return ()
    try:
        own = scope.base.resolve()
    except OSError:
        own = scope.base
    roots: list[Path] = []
    for other in known_scopes():
        if other.id == "global" or other.id == scope.id:
            continue
        try:
            if not other.base.is_dir():
                continue
            resolved = other.base.resolve()
        except OSError:
            continue
        if resolved == own or resolved in roots:
            continue
        roots.append(resolved)
    return tuple(roots)


def _peer_link_info(scope: "Scope", name: str) -> dict | None:
    """Describe a flat scope entry that is a link into a peer root.

    Returns ``{"path", "target", "linked_to", "link_target_root"}`` or ``None``
    when the entry is not a symlink, its target is not a directory inside a
    peer root, or the target fails that root's containment guard (which also
    refuses a chain of links leaving the peer root).
    """
    try:
        validate_skill_name(name)
    except ValueError:
        return None
    link = scope.base / name
    try:
        if not link.is_symlink():
            return None
        target = Path(os.path.realpath(link))
    except OSError:
        return None
    if not target.is_dir():
        return None
    for peer_root in _peer_link_roots(scope):
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
        return {
            "path": str(link),
            "target": contained,
            "linked_to": str(target),
            "link_target_root": str(peer_root),
        }
    return None


def _refused_path_error(scope: "Scope", name: str, exc: Exception) -> StoreError:
    """The clean refusal for a path guard that rejected *name*.

    SCOPE-2: a link into a peer root is readable but never writable through
    this scope.  Name the peer directory and where to make the change, rather
    than surfacing the interpreter-level containment message; every other
    refusal keeps that message unchanged.
    """
    link = _peer_link_info(scope, name)
    if link is None:
        return StoreError(str(exc))
    return StoreError(
        f"skill '{name}' in scope '{scope.id}' is a link into "
        f"{link['link_target_root']}; change it there"
    )


def _scope_read_dir(scope: "Scope", name: str) -> tuple[Path, dict | None]:
    """Resolve one skill directory for a read, following a peer link.

    Returns ``(directory, link)`` where ``link`` is the peer-link description
    for a followed link and ``None`` for an ordinary skill.  Writers must not
    use this: :func:`safe_scope_skill_path` still refuses out-of-root links.
    """
    try:
        skill_dir = safe_scope_skill_path(scope, name)
    except StoreError:
        link = _peer_link_info(scope, name)
        if link is None:
            raise
        return Path(link["target"]), link
    if not skill_dir.is_dir():
        link = _peer_link_info(scope, name)
        if link is not None:
            return Path(link["target"]), link
    return skill_dir, None


def _apply_link_read(entry: dict, skill_dir: Path, link: dict | None) -> dict:
    """Stamp the observed path of a read, marking a followed link read-only."""
    if link is None:
        entry["path"] = str(skill_dir)
        return entry
    entry["path"] = link["path"]
    entry["linked_to"] = link["linked_to"]
    entry["link_target_root"] = link["link_target_root"]
    entry["read_only"] = True
    entry["link_followed"] = True
    return entry


@dataclass(frozen=True)
class Scope:
    id: str
    label: str
    base: Path
    kind: str
    writable: bool
    recursive: bool = False
    supported: bool = True
    consumer: str | None = None


def _resolved_scope_root(scope: Scope) -> Path:
    return _root_discovery.resolved_root(scope)


def _escaping_links(root: Path) -> list[str]:
    """Return links inside *root* whose target leaves *root* (SCOPE-1).

    ``shutil.copytree`` follows symlinks by default, so one link to a file
    outside the scope made a sync read that file's bytes and materialize them
    into another agent scope -- an 88-byte skill produced 65 KB of files that
    lived outside the skill directory, in a place the agent then loads.
    """
    resolved_root = root.resolve()
    escaping: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_symlink():
            continue
        try:
            target = Path(os.path.realpath(path))
            inside = target == resolved_root or target.is_relative_to(resolved_root)
        except (OSError, AttributeError):
            inside = False
        if not inside:
            escaping.append(str(path.relative_to(root)))
    return escaping


def _copy_skill_tree(src_dir: Path, dest: Path) -> None:
    """Copy a skill directory without following symlinks out of it (SCOPE-1).

    Symlinks are copied *as links* (``symlinks=True``), so no bytes from
    outside the skill directory can be materialized into the destination; a
    link that escapes the source is refused outright, because copying it as a
    link would install a dangling or out-of-scope reference in the target
    scope.
    """
    escaping = _escaping_links(src_dir)
    if escaping:
        raise StoreError(
            "cannot sync a skill containing symlinks that point outside it: "
            + ", ".join(escaping[:3])
            + (" ..." if len(escaping) > 3 else "")
        )
    shutil.copytree(src_dir, dest, symlinks=True)


def _unique_physical_scopes(scopes: list[Scope]) -> list[Scope]:
    return _root_discovery.unique_physical_scopes(scopes)


def _availability(scope: Scope) -> str:
    return _root_discovery.availability(scope)


def _annotate_instance_states(records: list[dict]) -> list[dict]:
    return _root_discovery.annotate_instance_states(records)


def _cwd() -> Path:
    try:
        return Path.cwd()
    except OSError:
        return paths.home_dir()


def known_scopes() -> list[Scope]:
    """All scopes we know about, in stable UI order.

    The home directory comes from ``paths.home_dir()`` so an empty ``$HOME``
    cannot relocate every agent scope to ``/`` (SCOPE-17).
    """
    home = paths.home_dir()
    cwd = _cwd()
    scopes: list[Scope] = [
        Scope("global", "Global", _global_skills_dir(), "global", True, consumer="skills-manager"),
        Scope("claude-code", "Claude Code", home / ".claude/skills", "agent", True, consumer="claude-code"),
        Scope("codex", "Codex", home / ".codex/skills", "agent", True, consumer="codex"),
        Scope("cursor", "Cursor", home / ".cursor/skills", "agent", True, recursive=True, consumer="cursor"),
        Scope("opencode", "Opencode", home / ".config/opencode/skills", "agent", True, recursive=True, consumer="opencode"),
        Scope("gemini", "Gemini", home / ".gemini/skills", "agent", True, consumer="gemini"),
        Scope("commandcode", "Command Code", home / ".commandcode/skills", "agent", True, consumer="commandcode"),
        Scope("agents", "Agents", home / ".agents/skills", "agent", True, recursive=True, consumer="shared-agent-skills"),
    ]
    for label, rel, recursive, consumer in _root_discovery.project_scope_specs():
        cand = cwd / rel
        if cand.is_dir() and all(cand.resolve() != s.base.resolve() for s in scopes if s.base.exists()):
            sid = label.lower().replace(" ", "-").replace(".", "")
            scopes.append(Scope(sid, label, cand, "project", True, recursive, True, consumer))
    return scopes


def scope_by_id(scope_id: str) -> Scope | None:
    for s in known_scopes():
        if s.id == scope_id:
            return s
    return None


def list_scopes(
    *, include_missing: bool = False, records: list[dict] | None = None
) -> list[dict]:
    """Return scope descriptors with live counts and token totals.

    ``records`` is an internal request-level seam: when a caller already has a
    merged filesystem snapshot (the Web UI stats route), summarize it instead
    of rescanning every root.  The default remains the filesystem-source-of-
    truth scan for existing callers.
    """
    # A broken layout is one condition with one answer, whatever the route.
    # Reporting the global root as ``missing`` -- and ``writable`` -- while four
    # other routes answer 404 was how the UI ended up half-broken and
    # half-looking-healthy (docs/24 §D3-4).
    _global_store()._check_store_layout()
    by_scope: dict[str, list[dict]] | None = None
    if records is not None:
        by_scope = {}
        for record in records:
            by_scope.setdefault(str(record.get("scope", "")), []).append(record)
    out: list[dict] = []
    for s in _unique_physical_scopes(known_scopes()):
        exists = s.base.is_dir()
        availability = _availability(s)
        if not exists and not include_missing and s.id != "global":
            continue
        entries = (
            by_scope.get(s.id, [])
            if by_scope is not None
            else (
                scan_dir(s.base, recursive=s.recursive, link_roots=_peer_link_roots(s))
                if exists
                else []
            )
        )
        agg = aggregate(entries)
        out.append(
            {
                "id": s.id,
                "label": s.label,
                "path": str(s.base),
                "kind": s.kind,
                "writable": s.writable,
                "availability": availability,
                "recursive": s.recursive,
                "supported": s.supported,
                "consumer": s.consumer,
                "exists": exists,
                "count": len(entries),
                "tokens": agg["total_tokens"],
                "avg_tokens": agg["avg_tokens"],
                "max_tokens": agg["max_tokens"],
            }
        )
    return out


def _global_row_path(store: Store, name: str, paths_module):
    """Return the on-disk path of a global row, or ``None`` when unaddressable.

    SCOPE-15: resolving a row name through the name guard raised a raw
    ``ValueError`` for any row whose name fails the canonical rule, and one such
    row aborted ``scan_scope("global")``, ``list_all()`` and ``search_all()``
    together.  A row the tool cannot address simply has no path.
    """
    try:
        return str(path_safety.safe_skill_path(store.skills_dir, name))
    except ValueError:
        return None


def _physical_path(path: str) -> str:
    """The resolved physical spelling of *path*.

    ``Path(path).resolve()`` and ``os.path.realpath(path)`` answer the same
    question, but only the second is ``os.path.realpath`` itself; wrapping it in
    ``Path`` reparsed every component of every row, which was the largest
    single cost left in the per-row annotation loop (docs/24 §D1).  The
    best-effort fallback the old expression had is kept: a row whose path
    cannot be resolved is still a row the user has to see.
    """
    try:
        return os.path.realpath(path)
    except OSError:
        return str(path)


def _annotate_scope_entries(entries: list[dict], scope: Scope, physical_root: str) -> list[dict]:
    """Stamp the per-scope fields on every entry a scan of *scope* produced.

    Split out of :func:`scan_scope` because two of the answers are functions of
    the scope, not of the row: ``_availability`` costs an ``is_dir`` and an
    ``os.access`` per call and used to be asked once per skill, and the
    physical root is resolved once for the whole scan.
    """
    availability = _availability(scope)
    for e in entries:
        e["scope"] = scope.id
        e["scope_label"] = scope.label
        try:
            # ``contained_entry`` keeps the *named* entry so a read and a write
            # of the same skill address the same path (SCOPE-3).
            e["path"] = e.get("path") or str(path_safety.contained_entry(scope.base, e["name"]))
        except (ValueError, OSError):
            continue
        e["physical_root"] = physical_root
        e["physical_path"] = _physical_path(e["path"])
        e["status"] = "disabled" if e.get("disabled") else "active"
        e.setdefault("tokens_pct", 0)
        e.setdefault("chars", 0)
        e["root_availability"] = availability
        e["discovery_recursive"] = scope.recursive
        e["consumer"] = scope.consumer
        if isinstance(e.get("provenance"), dict):
            e["provenance"]["scope"] = scope.id
            e["provenance"]["consumer"] = scope.consumer
    return _annotate_native_entries(entries, scope)


def _skill_document(entry: dict) -> Path | None:
    return Path(entry["path"]) / "SKILL.md" if entry.get("path") else None


def _annotate_native_entries(entries: list[dict], scope: Scope) -> list[dict]:
    documents = [(entry["name"], _skill_document(entry)) for entry in entries]
    states = observe_native_entries(scope.consumer, documents,
                                    home=paths.home_dir(), project=_cwd())
    for entry, state in zip(entries, states):
        entry["native_state"] = state
    return entries


def _enrich_global_row(r: dict, store: Store, physical_root: str) -> None:
    """Stamp the global-scope fields on one row from ``Store.list()``."""
    r["scope"] = "global"
    r["scope_label"] = "Global"
    if not r.get("path"):
        r["path"] = _global_row_path(store, r["name"], paths)
    r["physical_root"] = physical_root
    if r.get("path"):
        r["physical_path"] = _physical_path(r["path"])
    # Enrich global rows with tokens if missing.  ``Store.list()`` already
    # estimated them from the same bytes while observing the row, so this
    # fallback only runs for a row whose loader pass did not produce them --
    # it used to re-read and re-parse every SKILL.md on every merged request
    # (docs/24 §D1).
    if "tokens" not in r or not r.get("tokens"):
        try:
            p = path_safety.safe_skill_path(store.skills_dir, r["name"])
            raw = document_text(p)
            tok = estimate(raw)
            r["tokens"] = tok["tokens"]
            r["tokens_method"] = tok["method"]
            r["tokens_pct"] = tok["pct_window"]
            r["chars"] = tok["chars"]
        except Exception as exc:
            _diagnose("global scope token enrichment failed", exc)
            r.setdefault("tokens", 0)
            r.setdefault("tokens_method", "heuristic")
    r.setdefault("tokens_pct", 0)
    r.setdefault("chars", 0)
    r["root_availability"] = "writable"
    r["discovery_recursive"] = False
    r["consumer"] = "skills-manager"


def scan_scope(scope_id: str, *, include_husks: bool = False) -> list[dict]:
    """List skills in one scope, annotated with scope fields."""
    if scope_id == "global":
        store = _global_store()
        rows = store.list()
        physical_root = str(store.skills_dir.resolve())
        for r in rows:
            _enrich_global_row(r, store, physical_root)
        return _annotate_instance_states(rows)
    scope = scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    # SEC-10/§D1: a flat record used to carry no path, so the loop below
    # re-derived it for every row -- re-resolving the scope base and re-running
    # the name/containment check the scan had already performed.  The scan can
    # hand over the exact entry it validated instead.
    entries = scan_dir(
        scope.base,
        recursive=scope.recursive,
        include_husks=include_husks,
        annotate_paths=True,
        link_roots=_peer_link_roots(scope),
    )
    _annotate_scope_entries(entries, scope, str(_resolved_scope_root(scope)))
    return _annotate_instance_states(sorted(entries, key=lambda r: (r["name"].lower(), r.get("path", ""))))


def _merged_scope_ids(*, include_missing: bool = False) -> list[str]:
    """Scope ids a merged view must visit, without scanning any root.

    SEC-10: ``list_all`` used ``list_scopes()`` only for the ids, but
    ``list_scopes`` scans every root to compute its counts and token totals — so
    one merged request scanned each scope twice, roughly halving its cost.  This
    applies the same selection rules (deduplicated physical roots, missing roots
    skipped, ``global`` always present) with no scan at all.
    """
    ids: list[str] = []
    for scope in _unique_physical_scopes(known_scopes()):
        if not scope.base.is_dir() and not include_missing and scope.id != "global":
            continue
        ids.append(scope.id)
    return ids


def list_all(*, include_missing: bool = False) -> list[dict]:
    """Merged list across global + every existing agent scope."""
    store = _global_store()
    key = ("list-all", str(Path(store.data_dir).resolve()), include_missing)
    return coalesced_read(
        _SCOPE_READ_FLIGHTS,
        _SCOPE_READ_FLIGHTS_LOCK,
        key,
        lambda: _list_all_uncached(include_missing=include_missing),
    )


def _list_all_uncached(*, include_missing: bool = False) -> list[dict]:
    """Merged list across global + every existing agent scope.

    SCOPE-11: the dedupe key includes the on-disk path.  One *recursive* scope
    can hold two genuinely different skills with the same name -- the documented
    monorepo ``apps/*/<root>/`` shape.  Keying on ``(scope, name)`` dropped the
    second copy, re-annotated the survivor as ``['active']`` (erasing the
    duplicate/divergent signal that ``scan_scope`` and ``find_duplicates``
    report), and made this list disagree with both the per-scope scan and
    ``/api/stats``' summed counts.
    """
    merged: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for sid in _merged_scope_ids(include_missing=include_missing):
        for rec in scan_scope(sid):
            key = (sid, str(rec["name"]), str(rec.get("path") or ""))
            if key in seen:
                continue
            seen.add(key)
            merged.append(rec)
    merged.sort(key=lambda r: (r["name"].lower(), r["scope"]))
    return _annotate_instance_states(merged)


def _merged_records(records: list[dict] | None) -> list[dict]:
    """Return *records* when a caller already holds a merged filesystem snapshot.

    The request-level seam shared by :func:`list_scopes` and
    :func:`find_duplicates`: a caller that has already merged every scope must
    not force a second full pass over every root. ``None`` keeps the
    filesystem-authoritative scan for every existing caller.
    """
    return list_all() if records is None else records


def find_duplicates(records: list[dict] | None = None) -> list[dict]:
    """Same-name skills present in more than one scope.

    Read-only grouping over list_all(): each entry is
    {"name", "scopes", "count", "descriptions_differ", "records"} where
    records carry scope/scope_label/description/disabled/tokens. Converge
    with the existing sync_skill() — no new mutation paths.

    ``records`` is the same request-level seam :func:`list_scopes` accepts: a
    caller that already holds a merged filesystem snapshot passes it instead of
    forcing a second full pass over every root.  The default remains the
    filesystem-authoritative scan.
    """
    groups: dict[str, list[dict]] = {}
    for rec in _merged_records(records):
        groups.setdefault(rec["name"], []).append(rec)
    dupes: list[dict] = []
    for name in sorted(groups):
        recs = groups[name]
        scopes_seen = sorted({r["scope"] for r in recs})
        if len(scopes_seen) < 2:
            continue
        descs = {(r.get("description") or "").strip() for r in recs}
        dupes.append(
            {
                "name": name,
                "scopes": scopes_seen,
                "count": len(scopes_seen),
                "descriptions_differ": len(descs) > 1,
                "records": [
                    {
                        "scope": r["scope"],
                        "scope_label": r.get("scope_label", r["scope"]),
                        "description": r.get("description", ""),
                        "disabled": bool(r.get("disabled")),
                        "tokens": r.get("tokens", 0),
                        "instance_state": r.get("instance_state", "unresolved"),
                        "instance_states": r.get("instance_states", ["unresolved"]),
                        "effective_state": r.get("effective_state", "unresolved"),
                    }
                    for r in sorted(recs, key=lambda x: x["scope"])
                ],
            }
        )
    return dupes


def get_skill(scope_id: str, name: str) -> dict:
    """Full record for one skill in one scope (includes body, path)."""
    if scope_id == "global":
        rec = _global_store().get(name)
        if not rec.get("installed"):
            # STORE-10 keeps a stale index row visible to doctor(); its stored
            # body must not be served as if the document still existed.
            raise SkillNotFound(
                f"skill '{name}' is not installed; run doctor to see why the index "
                "still has a row for it"
            )
        rec["scope"] = "global"
        rec["scope_label"] = "Global"
        tok = estimate(document_text(Path(rec["path"])))
        rec.update(tokens=tok["tokens"], tokens_method=tok["method"], tokens_pct=tok["pct_window"],
                   chars=tok["chars"], lines=tok["lines"])
        rec["body_tokens"] = estimate(rec.get("body") or "")["tokens"]
        rec["frontmatter_tokens"] = max(0, tok["tokens"] - rec["body_tokens"])
        return rec
    scope = scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    skill_dir, link = _scope_read_dir(scope, name)
    if not skill_dir.is_dir():
        raise SkillNotFound(f"skill '{name}' is not installed in scope '{scope_id}'")
    entry = load_skill(skill_dir)
    entry["scope"] = scope.id
    entry["scope_label"] = scope.label
    _apply_link_read(entry, skill_dir, link)
    entry["status"] = "disabled" if entry.get("disabled") else "active"
    if isinstance(entry.get("provenance"), dict):
        entry["provenance"]["scope"] = scope.id
        entry["provenance"]["consumer"] = scope.consumer
    try:
        raw = document_text(skill_dir)
        data, _ = parse_frontmatter(raw)
        if isinstance(data.get("compatibility"), str):
            entry["compatibility"] = data["compatibility"]
        if isinstance(data.get("allowed-tools"), str):
            entry["allowed_tools"] = data["allowed-tools"]
        entry["body_tokens"] = estimate(entry.get("body") or "")["tokens"]
        entry["frontmatter_tokens"] = max(0, (entry.get("tokens", 0) or 0) - entry["body_tokens"])
        entry["lines"] = raw.count("\n") + 1 if raw else 0
    except Exception as exc:
        _diagnose(f"scope detail enrichment failed for {scope_id!r}", exc)
    return _annotate_native_entries([entry], scope)[0]


def get_raw(scope_id: str, name: str) -> str:
    """Raw SKILL.md text for one skill in one scope."""
    if scope_id == "global":
        store = _global_store()
        rec = store.get(name)
        p = (
            Path(rec["path"])
            if rec.get("path")
            else path_safety.safe_skill_path(paths.skills_dir(), name)
        )
    else:
        scope = scope_by_id(scope_id)
        if scope is None:
            raise StoreError(f"unknown scope {scope_id!r}")
        p, _link = _scope_read_dir(scope, name)
    document = document_path(p)
    if document is not None:
        return read_skill_text(document)[0]
    raise SkillNotFound(f"skill '{name}' has no SKILL.md in scope '{scope_id}'")


def find_skill(name: str, scope_id: str = "all") -> dict:
    """One skill's full record: from ``scope_id``, or the first scope holding it."""
    if scope_id not in ("all", ""):
        return get_skill(scope_id, name)
    row = next((r for r in list_all() if r["name"] == name), None)
    if row is None:
        raise SkillNotFound(f"skill '{name}' not found")
    return get_skill(row.get("scope", "global"), name)


def record_text(record: dict) -> str:
    """The text a token estimate covers: the document, else the stored body."""
    raw = document_text(Path(record["path"])) if record.get("path") else ""
    return raw or record.get("body") or ""


def _check_mutation_documents(skill_dir: Path) -> None:
    for filename in DOCUMENT_NAMES:
        if (skill_dir / filename).is_symlink():
            raise StoreError("cannot mutate a symlinked skill document; replace the link with a regular file first")


def _scope_mutation_lock(skill_dir: Path):
    # A document symlink changes the lock's resolved key across a rename.
    # Refuse it before calculating the same key used by Store, then recheck
    # inside the lock before touching either document.
    _check_mutation_documents(skill_dir)
    return mutation_lock(skill_dir.resolve() / ACTIVE_DOCUMENT)


def create_skill(
    scope_id: str,
    name: str,
    description: str,
    *,
    license: str | None = None,
    category: str | None = None,
    compatibility: str | None = None,
    version: str | None = None,
    allowed_tools: str | None = None,
    body: str | None = None,
) -> dict:
    """Create a skill in the given scope (scope-aware create)."""
    if scope_id == "global":
        return _global_store().create(
            name,
            description,
            license=license,
            category=category,
            compatibility=compatibility,
            version=version,
            allowed_tools=allowed_tools,
            body=body,
        )
    scope = scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    try:
        name = validate_skill_name(name.strip())
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    if not description or not description.strip():
        raise StoreError("description is required")
    description = description.strip()
    if len(description) > MAX_DESCRIPTION:
        raise StoreError(f"description exceeds {MAX_DESCRIPTION} characters")
    if compatibility and len(compatibility) > MAX_COMPATIBILITY:
        raise StoreError(f"compatibility exceeds {MAX_COMPATIBILITY} characters")
    # Create always targets the flat public install address.  A recursive
    # resolver may return an existing nested instance for reads, but that must
    # not make an unrelated category prevent creating the flat skill.
    try:
        skill_dir = path_safety.contained_entry(scope.base, name)
    except ValueError as exc:
        raise _refused_path_error(scope, name, exc) from exc
    # Do not let the sidecar lock's preparation create the candidate directory;
    # an absent flat path is precisely the successful create case.
    scope.base.mkdir(parents=True, exist_ok=True)
    with _scope_mutation_lock(skill_dir):
        _check_mutation_documents(skill_dir)
        # A recursive scope may already contain an observed nested instance with
        # this name.  The flat destination is the public create address, so it
        # is still valid to create it only when the flat path itself is absent;
        # the previous resolver returned the nested instance here and made a
        # fresh create look like a duplicate of an unrelated category.
        if skill_dir.exists():
            raise StoreError(f"skill '{name}' already exists in scope '{scope_id}'")
        data: dict = {"name": name, "description": description}
        if license:
            data["license"] = license
        if compatibility:
            data["compatibility"] = compatibility
        if version:
            data["version"] = version
        if allowed_tools:
            data["allowed-tools"] = allowed_tools.strip() if isinstance(allowed_tools, str) else allowed_tools
        if category:
            data["metadata"] = {"category": category}
        if body is None:
            body = f"# {name}\n"
        if not body.endswith("\n"):
            body += "\n"
        content = dump_frontmatter(data, key_order=list(data.keys())) + body
        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_text(skill_dir / "SKILL.md", content)
        except OSError as exc:
            shutil.rmtree(skill_dir, ignore_errors=True)
            raise StoreError(f"could not create skill '{name}' safely: {exc}") from exc
    return {"name": name, "path": str(skill_dir), "scope": scope_id}


def edit_skill(
    scope_id: str,
    name: str,
    *,
    description: str | None = None,
    license: str | None = None,
    category: str | None = None,
    compatibility: str | None = None,
    version: str | None = None,
    allowed_tools: str | None = None,
    body: str | None = None,
) -> dict:
    if scope_id == "global":
        return _global_store().edit(
            name,
            description=description,
            license=license,
            category=category,
            compatibility=compatibility,
            version=version,
            allowed_tools=allowed_tools,
            body=body,
        )
    scope = scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    skill_dir = safe_scope_skill_path(scope, name)
    with _scope_mutation_lock(skill_dir):
        _check_mutation_documents(skill_dir)
        if not skill_dir.is_dir():
            raise SkillNotFound(f"skill '{name}' is not installed in scope '{scope_id}'")
        md = skill_dir / "SKILL.md"
        if not md.is_file():
            if (skill_dir / "SKILL.md.disabled").is_file():
                raise StoreError(f"skill '{name}' is disabled in scope '{scope_id}'; enable it first")
            raise SkillNotFound(f"skill '{name}' has no SKILL.md in scope '{scope_id}'")
        text = read_skill_text_strict(md, subject=f"skill '{name}'")
        try:
            data, orig_body = parse_frontmatter(text)
        except FrontmatterError as exc:
            # SCOPE-12: treating an unparseable document as "no frontmatter" made
            # the rewrite re-emit the corrupt document as the *body* and dump a
            # fresh block above it -- four '---' fences, no 'name', and no error.
            # Fail closed, mirroring the undecodable-document policy above.
            raise StoreError(
                f"cannot safely edit skill '{name}' in scope '{scope_id}': its "
                f"frontmatter is malformed ({exc}); repair it by hand first"
            ) from exc
        orig_keys = list(data.keys())
        changed = False
        if description is not None:
            description = description.strip()
            if not description:
                raise StoreError("description cannot be empty")
            if data.get("description") != description:
                data["description"] = description
                changed = True
        if license is not None and data.get("license") != license:
            data["license"] = license
            changed = True
        if compatibility is not None and data.get("compatibility") != compatibility:
            data["compatibility"] = compatibility
            changed = True
        if version is not None and data.get("version") != version:
            data["version"] = version
            changed = True
        if allowed_tools is not None and data.get("allowed-tools") != allowed_tools.strip():
            data["allowed-tools"] = allowed_tools.strip()
            changed = True
        if category is not None:
            if not isinstance(data.get("metadata"), dict):
                data["metadata"] = {}
            if data["metadata"].get("category") != category:
                data["metadata"]["category"] = category
                changed = True
        if body is not None:
            if not body.endswith("\n"):
                body += "\n"
            if body != orig_body:
                orig_body = body
                changed = True
        if changed:
            write_snapshot(_global_store().data_dir, scope_id, name, text)
            order = orig_keys + [k for k in data if k not in orig_keys]
            try:
                atomic_write_text(md, dump_frontmatter(data, key_order=order) + orig_body)
            except OSError as exc:
                raise StoreError(f"could not edit skill '{name}' safely: {exc}") from exc
        return {"name": name, "changed": changed, "scope": scope_id}


def remove_skill(scope_id: str, name: str, *, purge: bool = False) -> dict:
    if scope_id == "global":
        return _global_store().remove(name, purge=purge)
    scope = scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    skill_dir = safe_scope_skill_path(scope, name)
    if not skill_dir.is_dir():
        raise SkillNotFound(f"skill '{name}' is not installed in scope '{scope_id}'")
    if purge:
        shutil.rmtree(skill_dir)
        return {"name": name, "action": "purged", "scope": scope_id}
    trash = _scope_trash_dir(scope)
    trash.mkdir(parents=True, exist_ok=True)
    target = path_safety.unique_child(trash, f"{scope_id}__{name}-{stamp()}")
    shutil.move(str(skill_dir), str(target))
    return {"name": name, "action": "trashed", "scope": scope_id, "trash_path": str(target)}


# ---------------------------------------------------------------------------
# Agent-scope trash (the sibling ``trash`` folder ``remove_skill`` writes to)
# ---------------------------------------------------------------------------

MAX_SCOPE_TRASH_ROWS = 500
# ``remove_skill`` writes ``<scope>__<name>-<timestamp>`` and appends ``-<n>``
# on a collision.  The name is greedy so a canonical name containing hyphens
# still parses; the fixed-width timestamp anchors the match at the end.
_TRASH_TAIL_RE = re.compile(
    r"^(?P<name>.+)-(?P<stamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}Z)(?:-(?P<copy>\d+))?$"
)


def _agent_scope(scope_id: str) -> Scope:
    """Resolve a non-global scope for trash work.

    ``global`` is refused on purpose: its trash lives in the manager's own data
    root and is served by ``Store.trash_list`` / ``Store.restore``.  Only agent
    scopes have the sibling ``trash`` folder :func:`remove_skill` uses.
    """
    if scope_id == "global":
        raise StoreError("the global library trash is not an agent trash folder")
    scope = scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    return scope


def _scope_trash_dir(scope: Scope) -> Path:
    return _checked_scope_trash_dir(scope)


def _checked_scope_trash_dir(scope: Scope) -> Path:
    # The scope root may itself be reached through a symlinked home or agent
    # directory. Anchor trash below its resolved parent, then refuse a linked
    # trash root so listing/restoring cannot cross into an unrelated tree.
    try:
        parent = scope.base.parent.resolve()
        trash = parent / "trash"
        if trash.is_symlink():
            raise StoreError(
                f"the trash folder for scope '{scope.id}' must not be a symlink"
            )
        if trash.exists() and not trash.is_dir():
            raise StoreError(
                f"the trash path for scope '{scope.id}' is not a directory"
            )
        return trash
    except OSError as exc:
        raise StoreError(
            f"could not safely resolve the trash folder for scope '{scope.id}': {exc}"
        ) from exc


def _scope_trash_size(entry: Path) -> int:
    total = 0
    try:
        for path in entry.rglob("*"):
            try:
                if path.is_file() and not path.is_symlink():
                    total += path.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


def _parse_scope_trash_entry(scope_id: str, entry: Path) -> dict | None:
    """Return the listing row for one trash directory, or ``None``.

    A symlink is never a trashed skill: this tool will not follow one out of the
    trash folder, and ``remove_skill`` never creates one.  The returned row
    carries its collision counter as ``_copy`` for ordering only.
    """
    prefix = f"{scope_id}__"
    if not entry.name.startswith(prefix):
        return None
    try:
        if entry.is_symlink() or not entry.is_dir():
            return None
    except OSError:
        return None
    match = _TRASH_TAIL_RE.match(entry.name[len(prefix):])
    if match is None:
        return None
    try:
        name = validate_skill_name(match.group("name"))
    except ValueError:
        return None
    from datetime import datetime, timezone

    try:
        trashed = datetime.strptime(
            match.group("stamp"), STAMP_FORMAT
        ).replace(tzinfo=timezone.utc)
        modified = iso(entry.stat().st_mtime)
    except (ValueError, OSError):
        return None
    return {
        "name": name,
        "scope": scope_id,
        "trash_path": str(entry),
        "trashed_at": iso(trashed),
        "modified": modified,
        "size_bytes": _scope_trash_size(entry),
        "_copy": int(match.group("copy") or 0),
    }


def scope_trash_list(scope_id: str) -> list[dict]:
    """List soft-deleted skills for one agent scope, newest first.

    Only plain directories matching ``<scope>__<name>-<timestamp>[-<n>]``
    whose name still passes the canonical rule are returned. The filename is
    an address for recovery, not authentication of the folder's origin.
    Reads create nothing, a missing trash folder is an empty list, and the
    result is bounded to ``MAX_SCOPE_TRASH_ROWS``.
    """
    scope = _agent_scope(scope_id)
    trash = _scope_trash_dir(scope)
    if not trash.is_dir():
        return []
    try:
        candidates = list(trash.iterdir())
    except OSError as exc:
        raise StoreError(
            f"could not read the trash folder for scope '{scope_id}': {exc}"
        ) from exc
    rows = [
        row
        for row in (_parse_scope_trash_entry(scope_id, entry) for entry in candidates)
        if row is not None
    ]
    rows.sort(key=lambda row: (row["trashed_at"], row["_copy"]), reverse=True)
    bounded = rows[:MAX_SCOPE_TRASH_ROWS]
    for row in bounded:
        row.pop("_copy", None)
    return bounded


def _select_trash_entry(
    candidates: list[dict], trash_path: str | None, scope_id: str, name: str
) -> dict:
    """Pick the entry to restore: the exact requested path, else the newest."""
    if trash_path is not None:
        if not isinstance(trash_path, str) or not trash_path.strip():
            raise StoreError("trash_path must be a non-empty string")
        wanted = os.path.realpath(trash_path)
        for entry in candidates:
            if os.path.realpath(entry["trash_path"]) == wanted:
                return entry
        raise StoreError(
            f"the requested trash_path is not a restorable entry for '{name}' in "
            f"scope '{scope_id}'; refresh the trash list and retry"
        )
    if not candidates:
        raise SkillNotFound(f"no trashed copy of '{name}' exists in scope '{scope_id}'")
    return candidates[0]


def _validated_scope_trash_entry(
    scope: Scope, scope_id: str, name: str, entry: dict
) -> Path:
    """Recheck the chosen trash child and its root immediately before restore."""
    trash = _scope_trash_dir(scope)
    source = Path(entry["trash_path"])
    if source.parent != trash:
        raise StoreError(
            f"the trashed copy of '{name}' is outside the trash folder for "
            f"scope '{scope_id}'"
        )
    try:
        if trash.is_symlink() or not trash.is_dir():
            raise StoreError(
                f"the trash folder for scope '{scope_id}' changed; refresh and retry"
            )
        if source.is_symlink() or not source.is_dir():
            raise StoreError(
                f"the trashed copy of '{name}' changed; refresh and retry"
            )
        if source.resolve(strict=True) != source:
            raise StoreError(
                f"the trashed copy of '{name}' is no longer contained in the "
                f"trash folder for scope '{scope_id}'"
            )
        current = _parse_scope_trash_entry(scope_id, source)
        if current is None or current["name"] != name:
            raise StoreError(
                f"the trashed copy of '{name}' changed; refresh and retry"
            )
    except OSError as exc:
        raise StoreError(
            f"could not safely verify the trashed copy of '{name}' in "
            f"scope '{scope_id}': {exc}"
        ) from exc
    return source


def restore_trashed(scope_id: str, name: str, trash_path: str | None = None) -> dict:
    """Move one trashed agent-scope skill back where the agent reads it.

    The destination must be free (a symlink counts as occupied), and the move
    is a rename on the same filesystem under the per-skill mutation lock the
    other scoped writes use — never a copy.
    """
    try:
        name = validate_skill_name(name)
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    scope = _agent_scope(scope_id)
    candidates = [row for row in scope_trash_list(scope_id) if row["name"] == name]
    entry = _select_trash_entry(candidates, trash_path, scope_id, name)
    skill_dir = safe_scope_skill_path(scope, name)
    with _scope_mutation_lock(skill_dir):
        _check_mutation_documents(skill_dir)
        if skill_dir.exists() or skill_dir.is_symlink():
            raise StoreError(
                f"skill '{name}' already exists in scope '{scope_id}'; remove it "
                "before restoring the trashed copy"
            )
        # Listing and selection happen before the mutation lock. Revalidate
        # both the root and the exact child while holding it so a replaced root
        # or entry cannot redirect this rename to a symlinked external tree.
        source = _validated_scope_trash_entry(scope, scope_id, name, entry)
        try:
            os.rename(source, skill_dir)
        except FileNotFoundError:
            # The advisory lock excludes cooperating writers, but this trash
            # folder is a plain directory another tool may edit.
            raise StoreError(
                f"the trashed copy of '{name}' changed concurrently in scope "
                f"'{scope_id}'; retry the restore"
            ) from None
        except OSError as exc:
            raise StoreError(
                f"could not restore '{name}' in scope '{scope_id}': {exc}"
            ) from exc
    return {"name": name, "scope": scope_id, "action": "restored", "path": str(skill_dir)}


def toggle_skill(scope_id: str, name: str, *, enable: bool) -> dict:
    if scope_id == "global":
        store = _global_store()
        return store.enable(name) if enable else store.disable(name)
    scope = scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    skill_dir = safe_scope_skill_path(scope, name)
    # STORE-11: the checks and the rename are one step under the same lock key
    # the sibling scope writers use.
    with _scope_mutation_lock(skill_dir):
        _check_mutation_documents(skill_dir)
        toggle_document(skill_dir, name, enable=enable, scope_id=scope_id)
    return {"name": name, "disabled": not enable, "scope": scope_id}


def _snapshot_sync_target(dest: Path, data_dir: Path, scope_id: str, name: str, force: bool) -> bool:
    """Snapshot existing destination bytes; return False if force is required."""
    if not dest.exists():
        return True
    if not force:
        return False
    try:
        active = dest / "SKILL.md"
        disabled = dest / "SKILL.md.disabled"
        document = active if active.is_file() else disabled
        content = document.read_bytes() if document.is_file() else b""
        write_snapshot_bytes(data_dir, scope_id, name, content)
    except OSError as exc:
        raise StoreError(f"could not snapshot skill '{name}' in scope '{scope_id}' safely") from exc
    return True


def sync_skill(
    name: str,
    from_scope: str,
    to_scopes: list[str] | None = None,
    *,
    force: bool = False,
) -> dict:
    """Copy skill `name` from `from_scope` to each scope in `to_scopes`.

    Default: when from_scope is global, copy to every other **writable**
    existing scope (a read-only root is not a target at all). Returns
    {synced:[scope_id], skipped:[{scope,reason}]}.

    SCOPE-8: each target is independent.  A target that cannot be written is
    reported in ``skipped`` with its reason, and the other targets still run —
    the caller sees what actually landed instead of losing the whole run to the
    first failure.  Only when *no* target succeeded does this raise, and then as
    a clean ``StoreError`` (previously a raw ``OSError`` reached the CLI and the
    REST layer as a 500).
    """
    try:
        name = validate_skill_name(name)
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    src = get_skill(from_scope, name)
    src_dir = Path(src["path"])
    if not src_dir.is_dir():
        raise SkillNotFound(f"source skill '{name}' has no directory in scope '{from_scope}'")
    # SCOPE-14: the copy below is a whole-tree ``copytree``, so a source holding
    # both documents *created* the mixed state in every target -- the one thing
    # ``Store.add`` (STORE-3) and both archive importers refuse to install, and
    # the one thing every toggle then refuses forever with no route back
    # through sync while the source stayed mixed.  Refuse the source up front,
    # before any target is touched, so a refused sync is a no-op rather than a
    # partial install.
    reject_conflicting_documents(src_dir, name, scope_id=from_scope)

    if to_scopes is None:
        if from_scope == "global":
            to_scopes = [
                d["id"]
                for d in list_scopes()
                if d["id"] != "global" and d["availability"] == "writable"
            ]
        else:
            raise StoreError("to_scopes is required when from_scope is not global")

    synced: list[str] = []
    skipped: list[dict] = []
    failures: list[tuple[str, str]] = []
    snapshot_data_dir = _global_store().data_dir
    target_roots: set[Path] = set()
    for sid in to_scopes:
        if sid == from_scope:
            skipped.append({"scope": sid, "reason": "same as source"})
            continue
        scope = scope_by_id(sid)
        if scope is None:
            skipped.append({"scope": sid, "reason": "unknown scope"})
            continue
        root_key = _resolved_scope_root(scope)
        if root_key in target_roots:
            skipped.append({"scope": sid, "reason": "same physical root as another target"})
            continue
        target_roots.add(root_key)
        if _availability(scope) == "read-only":
            # The declared ``writable`` flag is always True; the computed
            # availability is what the filesystem actually allows (SCOPE-8).
            skipped.append({"scope": sid, "reason": "read-only root (cannot be written)"})
            continue
        dest = safe_scope_skill_path(scope, name)
        if dest.resolve() == src_dir.resolve():
            skipped.append({"scope": sid, "reason": "same physical skill as source"})
            continue
        with _scope_mutation_lock(dest):
            _check_mutation_documents(dest)
            reject_conflicting_documents(dest, name, scope_id=sid)
            if not _snapshot_sync_target(dest, snapshot_data_dir, sid, name, force):
                skipped.append({"scope": sid, "reason": "already exists (use force)"})
                continue
            stage = scope.base / f".{name}.skillsmgr-stage"
            backup = scope.base / f".{name}.skillsmgr-backup"
            try:
                if stage.exists():
                    shutil.rmtree(stage)
                if backup.exists() or backup.is_symlink():
                    raise StoreError(f"a previous sync backup for '{name}' in scope '{sid}' needs manual review")
                _copy_skill_tree(src_dir, stage)
                if dest.exists():
                    shutil.move(str(dest), str(backup))
                shutil.move(str(stage), str(dest))
            except StoreError as exc:
                # Policy refusals happen before replacement (retained backup
                # or unsafe source). Keep recovery evidence and other targets.
                reason = str(exc)
                failures.append((sid, reason))
                skipped.append({"scope": sid, "reason": f"failed: {reason}"})
                continue
            except OSError as exc:
                if dest.exists() and backup.exists():
                    shutil.rmtree(dest, ignore_errors=True)
                if backup.exists() and not dest.exists():
                    shutil.move(str(backup), str(dest))
                shutil.rmtree(stage, ignore_errors=True)
                reason = getattr(exc, "strerror", None) or str(exc) or "copy failed"
                failures.append((sid, reason))
                skipped.append({"scope": sid, "reason": f"failed: {reason}"})
                continue
            if backup.exists() or backup.is_symlink():
                try:
                    if backup.is_symlink():
                        backup.unlink()
                    else:
                        shutil.rmtree(backup)
                except OSError:
                    _diagnose("sync completed but backup cleanup failed", OSError("backup retained for manual review"))
            synced.append(sid)
    if failures and not synced:
        failed_scope, reason = failures[0]
        raise StoreError(f"sync to '{failed_scope}' failed: {reason}")
    if "global" in synced:
        # The global scope is Store-backed: raw staged writes above bypass the
        # index, so reconcile the row (reactivating it when a stale 'trashed'
        # row predated the sync) through the public resync seam.
        _global_store().resync()
    return {"name": name, "from_scope": from_scope, "synced": synced, "skipped": skipped}


def list_snapshots_for(scope_id: str, name: str) -> list[str]:
    if scope_id == "global":
        return list_snapshots(_global_store().data_dir, "global", name)
    if scope_by_id(scope_id) is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    return list_snapshots(_global_store().data_dir, scope_id, name)


def restore_snapshot(scope_id: str, name: str, snapshot: str) -> dict:
    if scope_id == "global":
        return _global_store().restore(name, snapshot=snapshot)
    scope = scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    content = read_snapshot(_global_store().data_dir, scope_id, name, snapshot)
    skill_dir = safe_scope_skill_path(scope, name)
    md = skill_dir / "SKILL.md"
    with _scope_mutation_lock(skill_dir):
        _check_mutation_documents(skill_dir)
        if not md.is_file():
            if (skill_dir / "SKILL.md.disabled").is_file():
                raise StoreError(f"skill '{name}' is disabled in scope '{scope_id}'; enable it first")
            raise SkillNotFound(f"skill '{name}' has no SKILL.md in scope '{scope_id}'")
        current = read_skill_text_strict(md, subject=f"skill '{name}' in scope '{scope_id}'")
        write_snapshot(_global_store().data_dir, scope_id, name, current)
        try:
            atomic_write_text(md, content)
        except OSError as exc:
            raise StoreError(f"could not restore skill '{name}' safely: {exc}") from exc
    return {"name": name, "snapshot": snapshot, "scope": scope_id}


def _indexed_bodies(store: Store) -> dict[str, str]:
    """Map every indexed skill name to its stored body, in one read."""
    return {
        row["name"]: row["body"]
        for row in store._index_rows("SELECT name, body FROM skills")
    }


def _global_search_records(store: Store | None = None) -> list[dict]:
    """Return global list rows with their indexed bodies attached.

    Bodies come from one ``SELECT name, body`` rather than a ``Store.get()`` per
    row.  ``Store.get()`` returns ``body`` *from the index* and spends its
    document read filling ``Store._OBSERVED_KEYS`` -- and this caller discards
    every one of those keys, so the old form re-read and re-hashed every
    document in the library to derive metadata nobody looked at.  It was the
    whole cost of the call: the reuse cache cannot help, because proving the
    bytes unchanged *is* the file read.

    The body **source is deliberately unchanged** -- still the index, exactly as
    ``Store.search()`` has always used it -- so the CLI and the web route keep
    agreeing on what a body match means.  Making this route filesystem-
    authoritative instead would leave ``skills-mgr search`` disagreeing with it,
    which is a worse defect than the staleness it removes.

    One ``_index_rows`` call rather than a new public ``Store`` method: the read
    seam already exists, it is what every other read uses, and a new public
    method is locked-constraint 5.  ``scopes`` already reaches a private ``Store``
    method (``_check_store_layout``), so this crosses the same line that already
    exists rather than drawing a new one.
    """
    store = store or _global_store()
    bodies = _indexed_bodies(store)
    records: list[dict] = []
    for row in store.list():
        record = dict(row, scope="global", scope_label="Global")
        record["body"] = bodies.get(row["name"], "")
        records.append(record)
    return records


def search_all(
    term: str, scope_id: str | None = None, *, store: Store | None = None
) -> list[dict]:
    """Case-insensitive search over name, description and body."""
    selected_store = store or _global_store()
    key = (
        "search-all",
        str(Path(selected_store.data_dir).resolve()),
        term,
        scope_id or "all",
    )
    return coalesced_read(
        _SCOPE_READ_FLIGHTS,
        _SCOPE_READ_FLIGHTS_LOCK,
        key,
        lambda: [row for row, _score in search_ranked(term, scope_id, store=selected_store)],
    )


def search_ranked(
    term: str, scope_id: str | None = None, *, store: Store | None = None
) -> list[tuple[dict, int]]:
    """``(row, score)`` pairs, best first: name/description/body search.

    scope_id == None or 'all' -> all scopes; otherwise one scope.  The
    optional store selects the global records for callers serving a requested
    data directory; agent scopes continue using their filesystem adapters.
    """
    if len(term) > MAX_SEARCH_LENGTH:
        raise StoreError("search query too long")
    if scope_id in (None, "all"):
        pool: list[dict] = []
        for descriptor in list_scopes():
            if descriptor["id"] == "global":
                pool.extend(_global_search_records(store))
            else:
                pool.extend(scan_scope(descriptor["id"]))
    elif scope_id == "global":
        pool = _global_search_records(store)
    else:
        pool = scan_scope(scope_id)

    # Rank via search.py scoring for consistent ordering.  The matcher raises
    # ValueError for bounded wildcard violations; scope callers expose the
    # established StoreError contract instead of leaking that implementation
    # exception through CLI or REST adapters.
    try:
        ranked = rank_results(pool, term) if term else [(r, 0) for r in pool]
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    ranked.sort(key=lambda p: (-p[1], p[0]["name"].lower()))
    # Store.search historically omits body from global result rows.  Keep that
    # output shape while retaining the body in the private ranking pool.
    for record, _score in ranked:
        if record.get("scope") == "global":
            record.pop("body", None)
    return ranked
