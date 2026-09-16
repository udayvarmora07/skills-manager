"""Root-containment primitives for filesystem-derived paths."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def mkdir_private(path: Path) -> Path:
    """Create missing directory components with owner-only permissions."""
    target = Path(path)
    missing: list[Path] = []
    current = target
    while not current.exists():
        missing.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    if not current.is_dir():
        raise ValueError(f"cannot create directory below non-directory {current}")
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            if not directory.is_dir():
                raise ValueError(f"cannot create directory {directory}")
    return target


def trusted_root(root: Path, *, label: str = "data root") -> Path:
    """Return a canonical root only when it is safe to read and write.

    Environment-selected roots become the boundary for every containment check
    below them.  A path that is group/world-writable, owned by another user, or
    not writable by the current process would let an untrusted directory choose
    what the manager treats as its own data.  The nearest existing ancestor of
    a new root must therefore be a private writable directory; shared sticky
    directories such as ``/tmp`` are allowed only above that private subtree.
    """
    try:
        candidate = Path(root).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"unsafe {label}: could not resolve the path") from exc
    if candidate.parent == candidate:
        raise ValueError(f"unsafe {label}: filesystem root is not a data directory")

    existing = candidate
    try:
        while not existing.exists():
            parent = existing.parent
            if parent == existing:
                break
            existing = parent
        if not existing.is_dir():
            raise ValueError(f"unsafe {label}: {existing} is not a directory")
        if not os.access(existing, os.W_OK | os.X_OK):
            raise ValueError(f"unsafe {label}: {existing} is not writable")

        if os.name == "posix":
            uid = os.getuid()
            component = existing
            while True:
                info = component.stat()
                if info.st_uid not in (0, uid):
                    raise ValueError(
                        f"unsafe {label}: {component} is owned by another user"
                    )
                writable = info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                if writable and not (
                    info.st_mode & stat.S_ISVTX and component != existing
                ):
                    raise ValueError(
                        f"unsafe {label}: {component} is writable by another user"
                    )
                if component.parent == component:
                    break
                component = component.parent
    except (OSError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("unsafe "):
            raise
        raise ValueError(f"unsafe {label}: could not inspect the path") from exc

    return candidate


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


def contained_entry(root: Path, *parts: str | Path) -> Path:
    """Return the *named* entry under ``root``, requiring containment of its target.

    ``contained_path`` returns the resolved path, which throws the final
    component away.  For a skill addressed by name that is wrong (SCOPE-3): an
    in-root symlink ``alias -> real`` made ``alias`` resolve to ``real``, so
    ``get_skill('alias')`` reported ``real``, ``remove('alias')`` deleted
    ``real`` and left a dangling link, and the physical skill was listed twice.

    This helper keeps the named entry -- so a read and a write address the same
    thing -- while still refusing a link whose target escapes ``root``.
    """
    return contained_entry_under(Path(root).expanduser().resolve(), *parts)


def contained_entry_under(resolved_root: Path, *parts: str | Path) -> Path:
    """Return the *named* entry below an already-resolved root.

    Identical guarantee to :func:`contained_entry`, but the caller supplies the
    resolved root rather than this function resolving it on every call.  A tree
    scan resolves its root once and calls this per candidate: re-resolving the
    same root for every entry was about a third of a merged-scope request's CPU
    (SEC-10).  ``resolved_root`` **must** already be resolved, or the containment
    check would compare a resolved target against an unresolved prefix.
    """
    from .validator import validate_skill_name

    path_parts = tuple(Path(part) for part in parts)
    if not path_parts or any(part.is_absolute() for part in path_parts):
        raise ValueError("absolute paths are not valid below a managed root")
    _reject_windows_separators(path_parts)
    # A single part is a skill name, so it must satisfy the canonical name rule.
    # A deeper path is a discovered location below the root, so the containment
    # check below is what constrains it.
    if len(path_parts) == 1:
        validate_skill_name(str(path_parts[0]))
    candidate = resolved_root.joinpath(*path_parts)
    target = Path(os.path.realpath(candidate))
    try:
        inside = target == resolved_root or target.is_relative_to(resolved_root)
    except AttributeError:  # pragma: no cover - Python 3.10 fallback
        inside = str(target) == str(resolved_root) or str(target).startswith(
            str(resolved_root) + os.sep
        )
    if not inside:
        raise ValueError(f"path escapes managed root: {target}")
    return candidate


def realpath_or_none(path: Path) -> Path | None:
    """Return the symlink target of *path*, or ``None`` when it is not a link."""
    try:
        if not path.is_symlink():
            return None
        return Path(os.path.realpath(path))
    except OSError:
        return None
