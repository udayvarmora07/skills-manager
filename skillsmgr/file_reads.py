"""Bounded reads from checked regular-file descriptors."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path


class FileTooLarge(ValueError):
    """The file contains more bytes than the caller permits."""


class NotRegularFile(ValueError):
    """The opened object is not a regular file."""


class SymlinkNotAllowed(ValueError):
    """The caller forbids following a final symlink."""


def _verify_identity(path: Path, before, opened) -> None:
    after = os.lstat(path)
    if stat.S_ISLNK(after.st_mode):
        raise SymlinkNotAllowed(str(path))
    identities = [(getattr(item, "st_dev", None), getattr(item, "st_ino", None))
                  for item in (before, opened, after)]
    if any(dev is None or not ino for dev, ino in identities) or len(set(identities)) != 1:
        raise OSError(getattr(errno, "ESTALE", errno.EIO),
                      "file identity changed or is unavailable", str(path))


def _read_bounded(descriptor: int, limit: int, path: Path) -> bytes:
    chunks = []
    remaining = limit + 1
    while remaining:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    data = b"".join(chunks)
    if len(data) > limit:
        raise FileTooLarge(str(path))
    return data


def read_regular_file(path: Path, limit: int, *, follow_symlinks: bool = True) -> bytes:
    """Read at most ``limit + 1`` bytes and reject non-regular or oversized files.

    Where O_NOFOLLOW is unavailable, no-follow opens compare path identity
    before and after opening with the opened descriptor and reject any change.
    """
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    verify_identity = not follow_symlinks and not nofollow
    if not follow_symlinks and nofollow:
        flags |= nofollow
    if verify_identity:
        before = os.lstat(path)
        if stat.S_ISLNK(before.st_mode):
            raise SymlinkNotAllowed(str(path))
        if not stat.S_ISREG(before.st_mode):
            raise NotRegularFile(str(path))
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if not follow_symlinks and exc.errno == errno.ELOOP:
            raise SymlinkNotAllowed(str(path)) from exc
        raise
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise NotRegularFile(str(path))
        if verify_identity:
            _verify_identity(path, before, opened)
        return _read_bounded(descriptor, limit, path)
    finally:
        os.close(descriptor)
