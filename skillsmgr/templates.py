"""Skill template management over the data templates directory.

Templates are plain ``.md`` files living in ``<data>/templates``; a
template's body is the starting point for ``create``.
"""

from __future__ import annotations

import re
from pathlib import Path

from .store import _atomic_write_text, _mutation_lock

__all__ = [
    "TEMPLATE_NAME_RE",
    "DEFAULT_TEMPLATE",
    "list_templates",
    "template_path",
    "read_template",
    "create_template",
]

TEMPLATE_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

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
    if not TEMPLATE_NAME_RE.fullmatch(name):
        raise ValueError(
            f"invalid template name {name!r}: must match {TEMPLATE_NAME_RE.pattern}"
        )
    return templates_dir / f"{name}.md"


def read_template(templates_dir: Path, name: str) -> str:
    """Return the text of template *name* (raises FileNotFoundError)."""
    return template_path(templates_dir, name).read_text(encoding="utf-8")


def create_template(
    templates_dir: Path, name: str, body: str | None = None
) -> Path:
    """Create template *name* with default content and return its path."""
    path = template_path(templates_dir, name)
    with _mutation_lock(path):
        if path.exists():
            raise FileExistsError(f"template '{name}' already exists")
        templates_dir.mkdir(parents=True, exist_ok=True)
        content = body if body is not None else DEFAULT_TEMPLATE.format(name=name)
        _atomic_write_text(path, content)
    return path
