"""Skill template management over the data templates directory.

Templates are plain ``.md`` files living in ``<data>/templates``; a
template's body is the starting point for ``create``.
"""

from __future__ import annotations

from pathlib import Path

from .store import _atomic_write_text, _mutation_lock
from .validator import NAME_RE, validate_skill_name

__all__ = [
    "TEMPLATE_NAME_RE",
    "DEFAULT_TEMPLATE",
    "list_templates",
    "template_path",
    "read_template",
    "create_template",
]

# Keep the historical public export while making the validator the one source
# of truth for template names too.
TEMPLATE_NAME_RE = NAME_RE

DEFAULT_TEMPLATE = """---
name: {name}
description: A concise one-line summary of what this skill does.
metadata:
  category: uncategorized
---

# {name}

Explain what the skill does, when it should be invoked, and how it behaves.
"""


def list_templates(templates_dir: Path) -> list[str]:
    """Return template names (without the ``.md`` suffix), sorted."""
    if not templates_dir.is_dir():
        return []
    names = []
    for path in sorted(templates_dir.glob("*.md")):
        if path.is_file():
            names.append(path.stem)
    return names


def template_path(templates_dir: Path, name: str) -> Path:
    """Return the path for template *name*, rejecting unsafe names."""
    validate_skill_name(name)
    return templates_dir / f"{name}.md"


def read_template(templates_dir: Path, name: str) -> str:
    """Return the text of template *name* (raises FileNotFoundError)."""
    return template_path(templates_dir, name).read_text(encoding="utf-8")


def create_template(
    templates_dir: Path, name: str, body: str | None = None
) -> Path:
    """Create template *name* with default content and return its path."""
    path = template_path(templates_dir, name)
    # BUG-11: the directory must exist before the lock is taken.  Today
    # ``_mutation_lock`` is a pure in-memory lookup so the old ordering could not
    # fail, but it read as though the lock guarded the mkdir -- and any future
    # file-backed lock would have created its lock file inside a directory that
    # did not exist yet.
    templates_dir.mkdir(parents=True, exist_ok=True)
    with _mutation_lock(path):
        if path.exists():
            raise FileExistsError(f"template '{name}' already exists")
        content = body if body is not None else DEFAULT_TEMPLATE.format(name=name)
        _atomic_write_text(path, content)
    return path
