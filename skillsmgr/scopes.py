"""Skill scopes — global store plus per-agent filesystem roots.

Each scope is an independent SKILL.md tree we can list/search and write
into. Global scope is the skills-manager Store; every other scope is a
plain filesystem dir scanned on demand (no DB). Discovery probes real
paths at runtime; missing dirs show count 0.
"""

from __future__ import annotations

import os
import shutil
import threading
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .diagnostics import diagnose as _diagnose
from .frontmatter import FrontmatterError, dump_frontmatter, parse_frontmatter
from .loader import load_skill, read_skill_text_strict, scan_dir
from . import root_discovery as _root_discovery
from .store import (
    SkillNotFound,
    Store,
    StoreError,
    _coalesced_read,
    _atomic_write_text,
    _mutation_lock,
)
from .validator import validate_skill_name

# Injectable override for the global Store (lets the web UI + tests share one
# data_dir instead of each call constructing Store() with default resolution).
#
# SCOPE-10: this is a ``ContextVar``, not a module global.  As a plain global
# the last ``set_global_store`` won for every caller in the process, so a second
# in-process ``WebAppServer`` silently redirected the first server's global
# reads *and* its snapshot writes to another data dir.  A ContextVar is
# per-thread, and the web server rebinds it from its own ``store`` at the start
# of every request thread, so two servers can no longer affect each other.
_GLOBAL_STORE: ContextVar[Store | None] = ContextVar("skillsmgr_global_store", default=None)
_SCOPE_READ_FLIGHTS: dict = {}
_SCOPE_READ_FLIGHTS_LOCK = threading.Lock()


def set_global_store(store: Store | None) -> None:
    """Override the Store used for global-scope operations (or reset with None)."""
    _GLOBAL_STORE.set(store)


def _global_store() -> Store:
    store = _GLOBAL_STORE.get()
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
    store = _GLOBAL_STORE.get()
    return store.skills_dir if store is not None else paths.skills_dir()


def _holds_document(path: Path) -> bool:
    """True when *path* is a directory holding a skill document."""
    return (path / "SKILL.md").is_file() or (path / "SKILL.md.disabled").is_file()


def _safe_scope_skill_path(scope: "Scope", name: str) -> Path:
    """Return a validated skill path contained by an agent scope root.

    Uses ``contained_entry`` rather than ``contained_path`` so the *named*
    entry is addressed (SCOPE-3): resolving the final component turned an
    in-root alias into the physical skill, so a write through the alias mutated
    a different skill than the one requested, the physical skill was listed
    twice, and remove() deleted the target while leaving a dangling link.
    """
    try:
        direct = paths.contained_entry(scope.base, name)
        # SCOPE-18: the flat short-circuit used to accept *any* directory with
        # the requested name, so `deploy/deploy/SKILL.md` resolved to the
        # grouping directory `deploy`, which holds no document -- the two views
        # then contradicted each other (scan listed the skill, get_skill
        # reported SkillNotFound).  Only short-circuit when the flat path really
        # is a skill; a non-recursive scope keeps the historical contract.
        if not scope.recursive or _holds_document(direct):
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
                return paths.contained_entry_under(resolved_base, *relative.parts)
        return direct
    except ValueError as exc:
        raise StoreError(str(exc)) from exc


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
    # Project-local scopes if present (shown last, only when they exist).
    for label, rel, recursive, consumer in _root_discovery.project_scope_specs():
        cand = cwd / rel
        # Avoid duplicate when CWD scope equals a home scope path.
        if cand.is_dir() and all(cand.resolve() != s.base.resolve() for s in scopes if s.base.exists()):
            # Use a stable id derived from label.
            sid = label.lower().replace(" ", "-").replace(".", "")
            scopes.append(Scope(sid, label, cand, "project", True, recursive, True, consumer))
    return scopes


def _scope_by_id(scope_id: str) -> Scope | None:
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
    from .tokens import aggregate as _agg

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
            else (scan_dir(s.base, recursive=s.recursive) if exists else [])
        )
        agg = _agg(entries)
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
        return str(paths_module.safe_skill_path(store.skills_dir, name))
    except ValueError:
        return None


def scan_scope(scope_id: str) -> list[dict]:
    """List skills in one scope, annotated with scope fields."""
    if scope_id == "global":
        store = _global_store()
        rows = store.list()
        physical_root = str(store.skills_dir.resolve())
        for r in rows:
            r["scope"] = "global"
            r["scope_label"] = "Global"
            if not r.get("path"):
                r["path"] = _global_row_path(store, r["name"], paths)
            r["physical_root"] = physical_root
            if r.get("path"):
                try:
                    r["physical_path"] = str(Path(r["path"]).resolve())
                except OSError:
                    r["physical_path"] = str(r["path"])
            # Enrich global rows with tokens if missing (DB rows don't have them).
            if "tokens" not in r or not r.get("tokens"):
                try:
                    from .tokens import estimate as _est

                    p = paths.safe_skill_path(store.skills_dir, r["name"])
                    raw = ""
                    for cand in (p / "SKILL.md", p / "SKILL.md.disabled"):
                        if cand.is_file():
                            raw = cand.read_text(encoding="utf-8")
                            break
                    tok = _est(raw)
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
        return _annotate_instance_states(rows)
    scope = _scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    entries = scan_dir(scope.base, recursive=scope.recursive)
    physical_root = str(_resolved_scope_root(scope))
    for e in entries:
        e["scope"] = scope.id
        e["scope_label"] = scope.label
        try:
            # ``contained_entry`` keeps the *named* entry so a read and a write
            # of the same skill address the same path (SCOPE-3).
            e["path"] = e.get("path") or str(paths.contained_entry(scope.base, e["name"]))
        except (ValueError, OSError):
            continue
        e["physical_root"] = physical_root
        try:
            e["physical_path"] = str(Path(e["path"]).resolve())
        except OSError:
            e["physical_path"] = str(e["path"])
        e["status"] = "disabled" if e.get("disabled") else "active"
        e.setdefault("tokens_pct", 0)
        e.setdefault("chars", 0)
        e["root_availability"] = _availability(scope)
        e["discovery_recursive"] = scope.recursive
        e["consumer"] = scope.consumer
        if isinstance(e.get("provenance"), dict):
            e["provenance"]["scope"] = scope.id
            e["provenance"]["consumer"] = scope.consumer
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
    return _coalesced_read(
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


def find_duplicates() -> list[dict]:
    """Same-name skills present in more than one scope.

    Read-only grouping over list_all(): each entry is
    {"name", "scopes", "count", "descriptions_differ", "records"} where
    records carry scope/scope_label/description/disabled/tokens. Converge
    with the existing sync_skill() — no new mutation paths.
    """
    groups: dict[str, list[dict]] = {}
    for rec in list_all():
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
        rec["scope"] = "global"
        rec["scope_label"] = "Global"
        # Token enrichment for detail view.
        try:
            from .tokens import estimate as _est

            p = (
                Path(rec["path"])
                if rec.get("path")
                else paths.safe_skill_path(paths.skills_dir(), name)
            )
            raw = ""
            for cand in (p / "SKILL.md", p / "SKILL.md.disabled"):
                if cand.is_file():
                    raw = cand.read_text(encoding="utf-8")
                    break
            tok = _est(raw)
            rec["tokens"] = tok["tokens"]
            rec["tokens_method"] = tok["method"]
            rec["tokens_pct"] = tok["pct_window"]
            rec["chars"] = tok["chars"]
            rec["lines"] = tok["lines"]
            rec["body_tokens"] = _est(rec.get("body") or "")["tokens"]
            rec["frontmatter_tokens"] = max(0, tok["tokens"] - rec["body_tokens"])
        except Exception as exc:
            _diagnose("global scope detail enrichment failed", exc)
        return rec
    scope = _scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    skill_dir = _safe_scope_skill_path(scope, name)
    if not skill_dir.is_dir():
        raise SkillNotFound(f"skill '{name}' is not installed in scope '{scope_id}'")
    entry = load_skill(skill_dir)
    entry["scope"] = scope.id
    entry["scope_label"] = scope.label
    entry["path"] = str(skill_dir)
    entry["status"] = "disabled" if entry.get("disabled") else "active"
    if isinstance(entry.get("provenance"), dict):
        entry["provenance"]["scope"] = scope.id
        entry["provenance"]["consumer"] = scope.consumer
    # Try to enrich from raw frontmatter (compatibility, allowed-tools).
    try:
        raw = (skill_dir / "SKILL.md").read_text(encoding="utf-8") if (skill_dir / "SKILL.md").is_file() else (skill_dir / "SKILL.md.disabled").read_text(encoding="utf-8")
        data, _ = parse_frontmatter(raw)
        if isinstance(data.get("compatibility"), str):
            entry["compatibility"] = data["compatibility"]
        if isinstance(data.get("allowed-tools"), str):
            entry["allowed_tools"] = data["allowed-tools"]
        from .tokens import estimate as _est2

        entry["body_tokens"] = _est2(entry.get("body") or "")["tokens"]
        entry["frontmatter_tokens"] = max(0, (entry.get("tokens", 0) or 0) - entry["body_tokens"])
        entry["lines"] = raw.count("\n") + 1 if raw else 0
    except Exception as exc:
        _diagnose(f"scope detail enrichment failed for {scope_id!r}", exc)
    return entry


def get_raw(scope_id: str, name: str) -> str:
    """Raw SKILL.md text for one skill in one scope."""
    if scope_id == "global":
        store = _global_store()
        rec = store.get(name)
        p = (
            Path(rec["path"])
            if rec.get("path")
            else paths.safe_skill_path(paths.skills_dir(), name)
        )
    else:
        scope = _scope_by_id(scope_id)
        if scope is None:
            raise StoreError(f"unknown scope {scope_id!r}")
        p = _safe_scope_skill_path(scope, name)
    for cand in (p / "SKILL.md", p / "SKILL.md.disabled"):
        if cand.is_file():
            return read_skill_text_strict(cand, subject=f"skill '{name}'")
    raise SkillNotFound(f"skill '{name}' has no SKILL.md in scope '{scope_id}'")


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
    scope = _scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    # Reuse Store.create logic but write to scope base.
    from .validator import MAX_COMPATIBILITY, MAX_DESCRIPTION, MAX_NAME, NAME_RE

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
        skill_dir = paths.contained_entry(scope.base, name)
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    # Do not let the sidecar lock's preparation create the candidate directory;
    # an absent flat path is precisely the successful create case.
    scope.base.mkdir(parents=True, exist_ok=True)
    with _mutation_lock(skill_dir / "SKILL.md"):
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
            _atomic_write_text(skill_dir / "SKILL.md", content)
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
    scope = _scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    skill_dir = _safe_scope_skill_path(scope, name)
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
        from .store import write_snapshot as _write_snapshot

        with _mutation_lock(md):
            _write_snapshot(_global_store().data_dir, scope_id, name, text)
            order = orig_keys + [k for k in data if k not in orig_keys]
            try:
                _atomic_write_text(md, dump_frontmatter(data, key_order=order) + orig_body)
            except OSError as exc:
                raise StoreError(f"could not edit skill '{name}' safely: {exc}") from exc
    return {"name": name, "changed": changed, "scope": scope_id}


def remove_skill(scope_id: str, name: str, *, purge: bool = False) -> dict:
    if scope_id == "global":
        return _global_store().remove(name, purge=purge)
    scope = _scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    skill_dir = _safe_scope_skill_path(scope, name)
    if not skill_dir.is_dir():
        raise SkillNotFound(f"skill '{name}' is not installed in scope '{scope_id}'")
    if purge:
        shutil.rmtree(skill_dir)
        return {"name": name, "action": "purged", "scope": scope_id}
    # Soft delete: move to sibling trash dir.
    trash = scope.base.parent / "trash"
    trash.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%SZ")
    target = paths.contained_path(trash, f"{scope_id}__{name}-{ts}")
    counter = 1
    while target.exists():
        target = paths.contained_path(trash, f"{scope_id}__{name}-{ts}-{counter}")
        counter += 1
    shutil.move(str(skill_dir), str(target))
    return {"name": name, "action": "trashed", "scope": scope_id, "trash_path": str(target)}


def toggle_skill(scope_id: str, name: str, *, enable: bool) -> dict:
    if scope_id == "global":
        store = _global_store()
        return store.enable(name) if enable else store.disable(name)
    scope = _scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    skill_dir = _safe_scope_skill_path(scope, name)
    src = skill_dir / ("SKILL.md.disabled" if enable else "SKILL.md")
    dst = skill_dir / ("SKILL.md" if enable else "SKILL.md.disabled")
    if not src.is_file():
        if dst.is_file():
            raise StoreError(f"skill '{name}' is already {'enabled' if enable else 'disabled'} in scope '{scope_id}'")
        raise SkillNotFound(f"skill '{name}' is not installed in scope '{scope_id}'")
    # SCOPE-13: with both documents present the rename below would land on top
    # of the other one and destroy it, with no snapshot.  Refuse instead of
    # guessing which document the user meant.
    if dst.is_file():
        raise StoreError(
            f"skill '{name}' has both SKILL.md and SKILL.md.disabled in scope "
            f"'{scope_id}'; remove one of the two documents first"
        )
    try:
        src.rename(dst)
    except FileNotFoundError:
        # STORE-11: the lock is process-local, so a second process (CLI + Web UI
        # on one data dir) can move the document between the checks above and
        # this rename.  Report that as a clean, actionable conflict instead of
        # letting a raw FileNotFoundError reach the caller as a traceback/500.
        raise StoreError(
            f"skill '{name}' changed concurrently in scope '{scope_id}' "
            "(another process moved its document); retry the toggle"
        ) from None
    return {"name": name, "disabled": not enable, "scope": scope_id}


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
    from .store import write_snapshot as _write_snapshot

    snapshot_data_dir = _global_store().data_dir
    target_roots: set[Path] = set()
    for sid in to_scopes:
        if sid == from_scope:
            skipped.append({"scope": sid, "reason": "same as source"})
            continue
        scope = _scope_by_id(sid)
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
        previous_content = None
        dest = _safe_scope_skill_path(scope, name)
        if force and dest.exists():
            old_md = dest / "SKILL.md"
            if not old_md.is_file():
                old_md = dest / "SKILL.md.disabled"
            if old_md.is_file():
                previous_content = read_skill_text_strict(
                    old_md, subject=f"skill '{name}' in scope '{sid}'"
                )
        if dest.exists() and not force:
            skipped.append({"scope": sid, "reason": "already exists (use force)"})
            continue
        if dest.exists():
            _write_snapshot(snapshot_data_dir, sid, name, previous_content or "")
        stage = scope.base / f".{name}.skillsmgr-stage"
        backup = scope.base / f".{name}.skillsmgr-backup"
        try:
            if stage.exists():
                shutil.rmtree(stage)
            if backup.exists():
                shutil.rmtree(backup)
            _copy_skill_tree(src_dir, stage)
            if dest.exists():
                shutil.move(str(dest), str(backup))
            shutil.move(str(stage), str(dest))
            if backup.exists():
                shutil.rmtree(backup)
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
    from .store import list_snapshots as _list_snapshots

    if scope_id == "global":
        return _list_snapshots(_global_store().data_dir, "global", name)
    if _scope_by_id(scope_id) is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    return _list_snapshots(_global_store().data_dir, scope_id, name)


def restore_snapshot(scope_id: str, name: str, snapshot: str) -> dict:
    from .store import read_snapshot as _read_snapshot
    from .store import write_snapshot as _write_snapshot

    if scope_id == "global":
        return _global_store().restore(name, snapshot=snapshot)
    scope = _scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    content = _read_snapshot(_global_store().data_dir, scope_id, name, snapshot)
    skill_dir = _safe_scope_skill_path(scope, name)
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        if (skill_dir / "SKILL.md.disabled").is_file():
            raise StoreError(f"skill '{name}' is disabled in scope '{scope_id}'; enable it first")
        raise SkillNotFound(f"skill '{name}' has no SKILL.md in scope '{scope_id}'")
    with _mutation_lock(md):
        current = read_skill_text_strict(md, subject=f"skill '{name}' in scope '{scope_id}'")
        _write_snapshot(_global_store().data_dir, scope_id, name, current)
        try:
            _atomic_write_text(md, content)
        except OSError as exc:
            raise StoreError(f"could not restore skill '{name}' safely: {exc}") from exc
    return {"name": name, "snapshot": snapshot, "scope": scope_id}


def _global_search_records(store: Store | None = None) -> list[dict]:
    """Return global list rows with bodies loaded through Store's public API."""
    store = store or _global_store()
    records: list[dict] = []
    for row in store.list():
        record = dict(row, scope="global", scope_label="Global")
        full = store.get(row["name"])
        record["body"] = full.get("body", "")
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
    return _coalesced_read(
        _SCOPE_READ_FLIGHTS,
        _SCOPE_READ_FLIGHTS_LOCK,
        key,
        lambda: _search_all_uncached(term, scope_id, store=selected_store),
    )


def _search_all_uncached(
    term: str, scope_id: str | None = None, *, store: Store | None = None
) -> list[dict]:
    """Case-insensitive search over name/description/body.

    scope_id == None or 'all' -> all scopes; otherwise one scope.  The
    optional store selects the global records for callers serving a requested
    data directory; agent scopes continue using their filesystem adapters.
    """
    if len(term) > 200:
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
    from .search import rank_results

    try:
        ranked = rank_results(pool, term) if term else [(r, 0) for r in pool]
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    ranked.sort(key=lambda p: (-p[1], p[0]["name"].lower()))
    results = [r for r, _ in ranked]
    # Store.search historically omits body from global result rows.  Keep that
    # output shape while retaining the body in the private ranking pool.
    for record in results:
        if record.get("scope") == "global":
            record.pop("body", None)
    return results
