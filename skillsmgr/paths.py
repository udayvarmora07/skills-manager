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


def data_dir() -> Path:
    """Return the root data directory, creating it if needed."""
    override = os.environ.get("SKILLS_MANAGER_DATA")
    if override:
        base = Path(override).expanduser()
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            base = Path(xdg).expanduser()
        else:
            base = Path.home() / ".local" / "share"
    return base / "skills-manager"


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
        path.mkdir(parents=True, exist_ok=True)


def find_skill_dir(name: str) -> Path | None:
    """Locate an installed skill directory by name, or None if absent.

    The name must match the directory exactly (case-sensitive) to prevent
    ambiguous lookups across differently-cased skills.
    """
    candidate = skills_dir() / name
    if candidate.is_dir():
        return candidate
    return None
