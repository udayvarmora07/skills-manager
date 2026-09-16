"""Centralized path resolution for the skills manager.

Resolution order for the data directory:
  1. $SKILLS_MANAGER_DATA  (explicit override, used by tests and power users)
  2. $XDG_DATA_HOME        (XDG convention)
  3. ~/.local/share        (default on Linux)

The skills-manager subdirectory is always appended to the resolved base.
"""

from __future__ import annotations

import os
from pathlib import Path

from .path_safety import (
    contained_entry,
    contained_entry_under,
    contained_path,
    mkdir_private,
    safe_skill_path,
    trusted_root,
)


def home_dir() -> Path:
    """Return the user's home directory, treating an empty ``$HOME`` as unset.

    SCOPE-17: ``HOME=""`` makes ``Path.home()`` return ``/``, so every agent
    scope became ``/.claude/skills``, ``/.codex/skills``, … -- roots this tool
    both reads *and writes*.  An empty or whitespace-only value is a broken
    environment, not a request to use the filesystem root, so it falls back to
    the passwd entry the same way an unset variable does.
    """
    raw = os.environ.get("HOME")
    if raw is not None and raw.strip():
        return Path(raw).expanduser()
    try:
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError, OSError):  # pragma: no cover - non-POSIX
        return Path.home()


def _absolute(base: Path) -> Path:
    """Anchor a possibly-relative root so its meaning cannot drift with the CWD.

    SCOPE-17: a relative ``SKILLS_MANAGER_DATA``/``XDG_DATA_HOME`` resolved
    against whatever directory the process happened to start in, so the same
    environment pointed at different data depending on where the tool was run.
    """
    return base if base.is_absolute() else (Path.cwd() / base)


def data_dir() -> Path:
    """Return the validated root data directory, creating it if needed."""
    override = os.environ.get("SKILLS_MANAGER_DATA")
    if override and override.strip():
        base = _absolute(Path(override).expanduser())
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg and xdg.strip():
            base = _absolute(Path(xdg).expanduser())
        else:
            base = home_dir() / ".local" / "share"
    # Validate the selected base itself before appending the manager-owned
    # subtree.  This rejects broad/shared overrides such as ``/`` or ``/tmp``
    # even when the final ``skills-manager`` directory does not exist yet.
    selected = trusted_root(base)
    return trusted_root(selected / "skills-manager")


def skills_dir() -> Path:
    """Directory holding one subdirectory per installed skill."""
    return data_dir() / "skills"


def trash_dir() -> Path:
    """Directory holding soft-deleted skills as <name>-<timestamp> subdirs."""
    return data_dir() / "trash"


def templates_dir() -> Path:
    """Directory holding skill templates (plain .md files)."""
    return data_dir() / "templates"


def backups_dir() -> Path:
    """Directory holding exported/backup archives."""
    return data_dir() / "backups"


def db_path() -> Path:
    """Path of the SQLite index database."""
    return data_dir() / "skills-manager.db"


def ensure_dirs() -> None:
    """Create all data directories if they do not exist."""
    for path in (data_dir(), skills_dir(), trash_dir(), templates_dir(), backups_dir()):
        mkdir_private(path)


def find_skill_dir(name: str) -> Path | None:
    """Locate an installed skill directory by name, or None if absent.

    The name must match the directory exactly (case-sensitive) to prevent
    ambiguous lookups across differently-cased skills.
    """
    candidate = safe_skill_path(skills_dir(), name)
    if candidate.is_dir():
        return candidate
    return None
