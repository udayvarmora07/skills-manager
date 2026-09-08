"""Root-containment primitives for filesystem-derived paths."""

from __future__ import annotations

import os
from pathlib import Path


def contained_path(root: Path, *parts: str | Path) -> Path:
    """Return a resolved path only when it remains below ``root``."""
    resolved_root = Path(root).expanduser().resolve()
    path_parts = tuple(Path(part) for part in parts)
    if any(part.is_absolute() for part in path_parts):
        raise ValueError("absolute paths are not valid below a managed root")
    candidate = resolved_root.joinpath(*path_parts).resolve()
    try:
        inside = candidate == resolved_root or candidate.is_relative_to(resolved_root)
    except AttributeError:  # pragma: no cover - Python 3.10 fallback
        inside = str(candidate) == str(resolved_root) or str(candidate).startswith(
            str(resolved_root) + os.sep
        )
    if not inside:
        raise ValueError(f"path escapes managed root: {candidate}")
    return candidate


def safe_skill_path(root: Path, name: str) -> Path:
    """Validate a canonical skill name and return its contained path."""
    from .validator import validate_skill_name

    validate_skill_name(name)
    return contained_path(root, name)