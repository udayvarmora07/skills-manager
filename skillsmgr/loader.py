"""Shared SKILL.md loader and directory scanner.

Single implementation used by Store (global DB) and scopes (external agent
dirs). Keeps FS parsing consistent; FS stays source of truth.
"""

from __future__ import annotations

from pathlib import Path

from .frontmatter import FrontmatterError, parse_frontmatter
from .paths import contained_path
from .store import SkillNotFound
from .tokens import estimate as _estimate_tokens


def _coerce_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def load_skill(skill_dir: Path) -> dict:
    """Load one skill directory (SKILL.md or SKILL.md.disabled)."""
    text = None
    disabled = 0
    if (skill_dir / "SKILL.md").is_file():
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        disabled = 0
    elif (skill_dir / "SKILL.md.disabled").is_file():
        text = (skill_dir / "SKILL.md.disabled").read_text(encoding="utf-8")
        disabled = 1
    if text is None:
        raise SkillNotFound(f"skill '{skill_dir.name}' has no SKILL.md (or SKILL.md.disabled)")
    malformed = False
    try:
        data, body = parse_frontmatter(text)
    except FrontmatterError:
        data, body = {}, text
        malformed = True
    metadata = data.get("metadata")
    category = "uncategorized"
    if isinstance(metadata, dict) and isinstance(metadata.get("category"), str):
        category = metadata["category"] or "uncategorized"
    raw_text = text or ""
    tok = _estimate_tokens(raw_text)
    return {
        "name": skill_dir.name,
        "disabled": disabled,
        "malformed": malformed,
        "description": _coerce_str(data.get("description")),
        "body": body,
        "category": category,
        "license": data.get("license") if data.get("license") is not None else None,
        "version": _coerce_str(data.get("version")) if data.get("version") else None,
        "tokens": tok["tokens"],
        "tokens_method": tok["method"],
        "tokens_pct": tok["pct_window"],
        "chars": tok["chars"],
    }


def scan_dir(root: Path) -> list[dict]:
    """One-level scan of root: each child dir with SKILL.md -> load_skill."""
    entries: list[dict] = []
    if not root.is_dir():
        return entries
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        try:
            child = contained_path(root, child.name)
        except ValueError:
            continue
        try:
            entries.append(load_skill(child))
        except SkillNotFound:
            continue
    return entries
