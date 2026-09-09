"""Root-containment primitives for filesystem-derived paths."""

from __future__ import annotations

import os
from pathlib import Path


def _reject_windows_separators(parts: tuple[Path, ...]) -> None:
    """Reject ``\\`` and drive-letter prefixes on every host.

    Tar archives and POSIX paths use ``/`` as the separator; Windows also
    treats ``\\`` and ``C:...`` as separators/absolute paths. Rejecting them
    here keeps the containment guarantee identical on Linux, macOS, and
    Windows instead of passing only on the developer's host.
    """
    for part in parts:
        text = str(part)
        if "\\" in text:
            raise ValueError("absolute paths are not valid below a managed root")
        if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
            raise ValueError("absolute paths are not valid below a managed root")


def contained_path(root: Path, *parts: str | Path) -> Path:
    """Return a resolved path only when it remains below ``root``."""
    resolved_root = Path(root).expanduser().resolve()
    path_parts = tuple(Path(part) for part in parts)
    if any(part.is_absolute() for part in path_parts):
        raise ValueError("absolute paths are not valid below a managed root")
    _reject_windows_separators(path_parts)
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