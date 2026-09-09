"""Skill scopes — global store plus per-agent filesystem roots.

Each scope is an independent SKILL.md tree we can list/search and write
into. Global scope is the skills-manager Store; every other scope is a
plain filesystem dir scanned on demand (no DB). Discovery probes real
paths at runtime; missing dirs show count 0.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .frontmatter import dump_frontmatter, parse_frontmatter
from .loader import load_skill, scan_dir
from . import root_discovery as _root_discovery
from .store import (
    SkillNotFound,
    Store,
    StoreError,
    _atomic_write_text,
    _mutation_lock,
)
from .validator import validate_skill_name

# Injectable override for the global Store (lets the web UI + tests share one
# data_dir instead of each call constructing Store() with default resolution).
_GLOBAL_STORE: Store | None = None


def set_global_store(store: Store | None) -> None:
    """Override the Store used for global-scope operations (or reset with None)."""
    global _GLOBAL_STORE
    _GLOBAL_STORE = store


def _global_store() -> Store:
    return _GLOBAL_STORE if _GLOBAL_STORE is not None else Store()


def _safe_scope_skill_path(scope: "Scope", name: str) -> Path:
    """Return a validated skill path contained by an agent scope root."""
    try:
        direct = paths.safe_skill_path(scope.base, name)
        if not scope.recursive or direct.is_dir():
            return direct
        # Recursive consumers may discover a skill below a project/category
        # directory. Preserve the existing name-based public API by resolving
        # the first deterministic observed instance when the flat path is absent.
        for record in scan_dir(scope.base, recursive=True):
            if record.get("name") == name and record.get("path"):
                return paths.contained_path(scope.base, Path(record["path"]).relative_to(scope.base))
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
        return Path.home()


def known_scopes() -> list[Scope]:
    """All scopes we know about, in stable UI order."""
    home = Path.home()
    cwd = _cwd()
    scopes: list[Scope] = [
        Scope("global", "Global", paths.skills_dir(), "global", True, consumer="skills-manager"),
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


def list_scopes(*, include_missing: bool = False) -> list[dict]:
    """Return scope descriptors with live counts and token totals."""
    from .tokens import aggregate as _agg

    out: list[dict] = []
    for s in _unique_physical_scopes(known_scopes()):
        exists = s.base.is_dir()
        availability = _availability(s)
        if not exists and not include_missing and s.id != "global":
            continue
        entries = scan_dir(s.base, recursive=s.recursive) if exists else []
        count = len(entries)
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
                "count": count,
                "tokens": agg["total_tokens"],
                "avg_tokens": agg["avg_tokens"],
                "max_tokens": agg["max_tokens"],
            }
        )
    return out


def scan_scope(scope_id: str) -> list[dict]:
    """List skills in one scope, annotated with scope fields."""
    if scope_id == "global":
        store = _global_store()
        rows = store.list()
        for r in rows:
            r["scope"] = "global"
            r["scope_label"] = "Global"
            if not r.get("path"):
                r["path"] = str(paths.safe_skill_path(paths.skills_dir(), r["name"]))
            # Enrich global rows with tokens if missing (DB rows don't have them).
            if "tokens" not in r or not r.get("tokens"):
                try:
                    from .tokens import estimate as _est

                    p = paths.safe_skill_path(paths.skills_dir(), r["name"])
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
                except Exception:
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
    for e in entries:
        e["scope"] = scope.id
        e["scope_label"] = scope.label
        try:
            e["path"] = e.get("path") or str(paths.contained_path(scope.base, e["name"]))
        except ValueError:
            continue
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


def list_all(*, include_missing: bool = False) -> list[dict]:
    """Merged list across global + every existing agent scope."""
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for desc in list_scopes(include_missing=include_missing):
        sid = desc["id"]
        for rec in scan_scope(sid):
            key = (sid, rec["name"])
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
        except Exception:
            pass
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
    except Exception:
        pass
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
            return cand.read_text(encoding="utf-8")
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
    skill_dir = _safe_scope_skill_path(scope, name)
    with _mutation_lock(skill_dir / "SKILL.md"):
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
    text = md.read_text(encoding="utf-8")
    try:
        data, orig_body = parse_frontmatter(text)
    except Exception:
        data, orig_body = {}, text
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
    src.rename(dst)
    return {"name": name, "disabled": not enable, "scope": scope_id}


def sync_skill(
    name: str,
    from_scope: str,
    to_scopes: list[str] | None = None,
    *,
    force: bool = False,
) -> dict:
    """Copy skill `name` from `from_scope` to each scope in `to_scopes`.

    Default: when from_scope is global, copy to every other writable
    existing scope. Returns {synced:[scope_id], skipped:[{scope,reason}]}.
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
            to_scopes = [d["id"] for d in list_scopes() if d["id"] != "global" and d["writable"] and d["exists"]]
        else:
            raise StoreError("to_scopes is required when from_scope is not global")

    synced: list[str] = []
    skipped: list[dict] = []
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
        previous_content = None
        dest = _safe_scope_skill_path(scope, name)
        if force and dest.exists():
            old_md = dest / "SKILL.md"
            if not old_md.is_file():
                old_md = dest / "SKILL.md.disabled"
            if old_md.is_file():
                previous_content = old_md.read_text(encoding="utf-8")
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
            shutil.copytree(src_dir, stage)
            if dest.exists():
                shutil.move(str(dest), str(backup))
            shutil.move(str(stage), str(dest))
            if backup.exists():
                shutil.rmtree(backup)
        except OSError:
            if dest.exists() and backup.exists():
                shutil.rmtree(dest, ignore_errors=True)
            if backup.exists() and not dest.exists():
                shutil.move(str(backup), str(dest))
            shutil.rmtree(stage, ignore_errors=True)
            raise
        synced.append(sid)
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
        current = md.read_text(encoding="utf-8")
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
