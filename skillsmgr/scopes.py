"""Skill scopes — global store plus per-agent filesystem roots.

Each scope is an independent SKILL.md tree we can list/search and write
into. Global scope is the skills-manager Store; every other scope is a
plain filesystem dir scanned on demand (no DB). Discovery probes real
paths at runtime; missing dirs show count 0.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .frontmatter import dump_frontmatter, parse_frontmatter
from .loader import load_skill, scan_dir
from .store import SkillNotFound, Store, StoreError

# Injectable override for the global Store (lets the web UI + tests share one
# data_dir instead of each call constructing Store() with default resolution).
_GLOBAL_STORE: Store | None = None


def set_global_store(store: Store | None) -> None:
    """Override the Store used for global-scope operations (or reset with None)."""
    global _GLOBAL_STORE
    _GLOBAL_STORE = store


def _global_store() -> Store:
    return _GLOBAL_STORE if _GLOBAL_STORE is not None else Store()


@dataclass(frozen=True)
class Scope:
    id: str
    label: str
    base: Path
    kind: str
    writable: bool


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
        Scope("global", "Global", paths.skills_dir(), "global", True),
        Scope("claude-code", "Claude Code", home / ".claude/skills", "agent", True),
        Scope("codex", "Codex", home / ".codex/skills", "agent", True),
        Scope("cursor", "Cursor", home / ".cursor/skills-cursor", "agent", True),
        Scope("opencode", "Opencode", home / ".config/opencode/skills", "agent", True),
        Scope("gemini", "Gemini", home / ".gemini/skills", "agent", True),
        Scope("commandcode", "Command Code", home / ".commandcode/skills", "agent", True),
        Scope("agents", "Agents", home / ".agents/skills", "agent", True),
    ]
    # Project-local scopes if present (shown last, only when they exist).
    for label, rel in (
        ("Project .agents", ".agents/skills"),
        ("Project .claude", ".claude/skills"),
        ("Project skills", "skills"),
    ):
        cand = cwd / rel
        # Avoid duplicate when CWD scope equals a home scope path.
        if cand.is_dir() and all(cand.resolve() != s.base.resolve() for s in scopes if s.base.exists()):
            # Use a stable id derived from label.
            sid = label.lower().replace(" ", "-").replace(".", "")
            scopes.append(Scope(sid, label, cand, "project", True))
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
    for s in known_scopes():
        exists = s.base.is_dir()
        if not exists and not include_missing and s.id != "global":
            continue
        entries = scan_dir(s.base) if exists else []
        count = len(entries)
        agg = _agg(entries)
        out.append(
            {
                "id": s.id,
                "label": s.label,
                "path": str(s.base),
                "kind": s.kind,
                "writable": s.writable,
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
                r["path"] = str(paths.skills_dir() / r["name"])
            # Enrich global rows with tokens if missing (DB rows don't have them).
            if "tokens" not in r or not r.get("tokens"):
                try:
                    from .tokens import estimate as _est

                    p = Path(r["path"]) if r.get("path") else paths.skills_dir() / r["name"]
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
        return rows
    scope = _scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    entries = scan_dir(scope.base)
    for e in entries:
        e["scope"] = scope.id
        e["scope_label"] = scope.label
        e["path"] = str(scope.base / e["name"])
        e["status"] = "disabled" if e.get("disabled") else "active"
        e.setdefault("tokens_pct", 0)
        e.setdefault("chars", 0)
    return sorted(entries, key=lambda r: r["name"])


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
    return merged


def get_skill(scope_id: str, name: str) -> dict:
    """Full record for one skill in one scope (includes body, path)."""
    if scope_id == "global":
        rec = _global_store().get(name)
        rec["scope"] = "global"
        rec["scope_label"] = "Global"
        # Token enrichment for detail view.
        try:
            from .tokens import estimate as _est

            p = Path(rec["path"]) if rec.get("path") else paths.skills_dir() / name
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
    skill_dir = scope.base / name
    if not skill_dir.is_dir():
        raise SkillNotFound(f"skill '{name}' is not installed in scope '{scope_id}'")
    entry = load_skill(skill_dir)
    entry["scope"] = scope.id
    entry["scope_label"] = scope.label
    entry["path"] = str(skill_dir)
    entry["status"] = "disabled" if entry.get("disabled") else "active"
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
        p = Path(rec["path"]) if rec.get("path") else paths.skills_dir() / name
    else:
        scope = _scope_by_id(scope_id)
        if scope is None:
            raise StoreError(f"unknown scope {scope_id!r}")
        p = scope.base / name
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

    name = name.strip()
    if not NAME_RE.fullmatch(name) or len(name) > MAX_NAME:
        raise StoreError(f"invalid skill name {name!r}")
    if not description or not description.strip():
        raise StoreError("description is required")
    description = description.strip()
    if len(description) > MAX_DESCRIPTION:
        raise StoreError(f"description exceeds {MAX_DESCRIPTION} characters")
    if compatibility and len(compatibility) > MAX_COMPATIBILITY:
        raise StoreError(f"compatibility exceeds {MAX_COMPATIBILITY} characters")
    skill_dir = scope.base / name
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
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
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
    skill_dir = scope.base / name
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
        order = orig_keys + [k for k in data if k not in orig_keys]
        md.write_text(dump_frontmatter(data, key_order=order) + orig_body, encoding="utf-8")
    return {"name": name, "changed": changed, "scope": scope_id}


def remove_skill(scope_id: str, name: str, *, purge: bool = False) -> dict:
    if scope_id == "global":
        return _global_store().remove(name, purge=purge)
    scope = _scope_by_id(scope_id)
    if scope is None:
        raise StoreError(f"unknown scope {scope_id!r}")
    skill_dir = scope.base / name
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
    target = trash / f"{scope_id}__{name}-{ts}"
    counter = 1
    while target.exists():
        target = trash / f"{scope_id}__{name}-{ts}-{counter}"
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
    skill_dir = scope.base / name
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
    from .validator import MAX_NAME, NAME_RE

    if not NAME_RE.fullmatch(name) or len(name) > MAX_NAME:
        raise StoreError(f"invalid skill name {name!r}")
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
    for sid in to_scopes:
        if sid == from_scope:
            skipped.append({"scope": sid, "reason": "same as source"})
            continue
        scope = _scope_by_id(sid)
        if scope is None:
            skipped.append({"scope": sid, "reason": "unknown scope"})
            continue
        dest = scope.base / name
        if dest.exists() and not force:
            skipped.append({"scope": sid, "reason": "already exists (use force)"})
            continue
        scope.base.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src_dir, dest)
        synced.append(sid)
    return {"name": name, "from_scope": from_scope, "synced": synced, "skipped": skipped}


def search_all(term: str, scope_id: str | None = None) -> list[dict]:
    """Case-insensitive search over name/description/body.

    scope_id == None or 'all' -> all scopes; otherwise one scope.
    """
    if len(term) > 200:
        raise StoreError("search query too long")
    raw_term = term.lower()

    def _matches(rec: dict) -> bool:
        for key in ("name", "description", "body", "category"):
            v = rec.get(key)
            if isinstance(v, str) and raw_term in v.lower():
                return True
        return False

    if scope_id in (None, "all"):
        pool = list_all()
    elif scope_id == "global":
        pool = [dict(r, scope="global", scope_label="Global") for r in _global_store().search(term)]
        # Store.search already filtered; return as-is.
        return sorted(pool, key=lambda r: r["name"].lower())
    else:
        pool = scan_scope(scope_id)

    if scope_id in (None, "all") or scope_id not in ("global",):
        # For merged / agent scopes, filter in Python.
        if term:
            pool = [r for r in pool if _matches(r)]

    # Rank via search.py scoring for consistent ordering.
    try:
        from .search import rank_results

        ranked = rank_results(pool, term) if term else [(r, 0) for r in pool]
        ranked.sort(key=lambda p: (-p[1], p[0]["name"].lower()))
        return [r for r, _ in ranked]
    except Exception:
        pool.sort(key=lambda r: r["name"].lower())
        return pool
