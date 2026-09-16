"""Small trust checks for executables discovered from ``PATH``.

The developer browser harness and optional desktop launcher execute programs
selected through the caller's environment. A PATH entry must therefore point
to a real executable whose file and containing directories are not writable by
another Unix user. On Windows, the POSIX ownership bits do not describe the
effective ACL, so the portable regular-file/executable checks remain in force
and the platform's normal executable policy applies.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from typing import Callable


def _trusted_path(path: str | os.PathLike[str] | None) -> str | None:
    """Return a resolved executable path only when its trust checks pass."""
    if not path:
        return None
    try:
        resolved = Path(path).expanduser().resolve(strict=True)
        file_info = resolved.stat()
    except (OSError, RuntimeError, ValueError):
        return None
    if not stat.S_ISREG(file_info.st_mode) or not os.access(resolved, os.X_OK):
        return None
    if os.name == "nt":
        return str(resolved)

    trusted_uids = {os.getuid(), 0}
    if file_info.st_uid not in trusted_uids or file_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return None
    for parent in resolved.parents:
        try:
            directory_info = parent.stat()
        except OSError:
            return None
        if not stat.S_ISDIR(directory_info.st_mode):
            return None
        if directory_info.st_uid not in trusted_uids:
            return None
        writable_by_others = directory_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        if writable_by_others and not directory_info.st_mode & stat.S_ISVTX:
            return None
    return str(resolved)


def trusted_executable(
    name: str, *, which: Callable[[str], str | None] = shutil.which
) -> str | None:
    """Return the first trusted PATH match for *name*.

    The standard ``which`` API returns only one result. When it is the real
    :func:`shutil.which`, inspect every POSIX PATH entry so an unsafe earlier
    match is skipped rather than executed or allowed to mask a safe one. A
    custom resolver remains a single-candidate seam for callers and tests.
    """
    if which is shutil.which and os.name != "nt":
        for directory in os.get_exec_path():
            candidate = Path(directory or ".") / name
            trusted = _trusted_path(candidate)
            if trusted:
                return trusted
        return None
    try:
        candidate = which(name)
    except (OSError, ValueError):
        return None
    return _trusted_path(candidate)
