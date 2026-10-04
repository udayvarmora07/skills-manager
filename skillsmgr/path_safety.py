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


#: Entries that identify a directory as this tool's own data root.  Used only to
#: decide whether a too-permissive existing directory may be tightened, never to
#: grant access to anything.
_OWNED_ROOT_ENTRIES = ("skills", "trash", "templates", "backups", "skills-manager.db")


def tighten_private_root(root: Path, *, label: str = "data root") -> Path | None:
    """Tighten an over-permissive but recognisably-owned root to ``0o700``.

    A data directory created before the ownership control landed is permanently
    unusable: :func:`trusted_root` rejects it, every subcommand fails, and
    nothing in the product tells the user what to do about it.  This is the
    upgrade path.

    The repair is deliberately conservative and can only ever *reduce* access:

    * the directory already exists and is a directory;
    * it is owned by this user (or root);
    * its parent chain is itself an acceptable root;
    * its contents already look like this tool's data;
    * it is currently group- or world-writable.

    Anything else returns ``None`` and the caller reports the original refusal
    with instructions rather than silently changing a directory it does not own.
    """
    target = Path(root)
    try:
        info = target.stat()
    except OSError:
        return None
    if not os.path.isdir(target):
        return None
    if not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return None                                  # already tight enough
    if os.name == "posix" and info.st_uid not in (0, os.getuid()):
        return None                                  # not ours to change
    try:
        trusted_root(target.parent, label=label)
    except ValueError:
        return None                                  # parent chain is not safe
    try:
        if not any(entry.exists() for entry in
                   (target / name for name in _OWNED_ROOT_ENTRIES)):
            return None                              # not recognisably ours
        os.chmod(target, 0o700)
    except OSError:
        return None
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
    return contained_path_under(Path(root).expanduser().resolve(), *parts)


def contained_path_under(resolved_root: Path, *parts: str | Path) -> Path:
    """Return a resolved path below an **already-resolved** root.

    Identical guarantee to :func:`contained_path`, but the caller supplies the
    resolved root instead of this function resolving it on every call.  A tree
    scan resolves its root once and calls this per entry: re-resolving the same
    root for every entry cost about a quarter of the primary read path at 1,200
    skills (docs/24 §D1).  ``resolved_root`` **must** already be resolved, or
    the containment check would compare a resolved candidate against an
    unresolved prefix.

    This is the *resolved* counterpart of :func:`contained_entry_under`; keep
    the pair straight.  Use ``contained_entry_under`` when a name-addressed
    operation must act on the named entry rather than its link target (SCOPE-3),
    and this one when a resolved path is what the caller needs.
    """
    path_parts = tuple(Path(part) for part in parts)
    if any(part.is_absolute() for part in path_parts):
        raise ValueError("absolute paths are not valid below a managed root")
    _reject_windows_separators(path_parts)
    # ``os.path.realpath`` and ``Path.resolve()`` resolve the same set of
    # links; the former reaches the kernel without pathlib rebuilding every
    # component of the path first, which matters when a scan does this once
    # per row.  ``contained_entry_under`` already resolves this way.
    candidate = Path(os.path.realpath(Path(resolved_root).joinpath(*path_parts)))
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
    return safe_skill_path_under(Path(root).expanduser().resolve(), name)


def safe_skill_path_under(resolved_root: Path, name: str) -> Path:
    """Validate a canonical skill name below an **already-resolved** root.

    The scan-time counterpart of :func:`safe_skill_path`.  A tree scan resolves
    its root once and calls this per row instead of paying one root resolution
    per row (docs/24 §D1); the name rule and the containment check are
    unchanged, so a hoist that dropped either one would be a regression.
    """
    from .validator import validate_skill_name

    validate_skill_name(name)
    return contained_path_under(resolved_root, name)


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
