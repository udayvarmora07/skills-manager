"""Atomic filesystem primitives used by Store and scope adapters."""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
from pathlib import Path


_MUTATION_LOCKS: dict[str, threading.RLock] = {}
_MUTATION_LOCKS_GUARD = threading.Lock()


def mutation_lock(path: Path) -> threading.RLock:
    """Return a process-local lock for one resolved mutation path."""
    key = str(Path(path).expanduser().resolve())
    with _MUTATION_LOCKS_GUARD:
        return _MUTATION_LOCKS.setdefault(key, threading.RLock())


def atomic_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    replace=os.replace,
) -> None:
    """Write text through a sibling temp file, fsync, then atomically replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".skillsmgr-tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        replace(temp_path, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            except OSError:
                pass
            finally:
                os.close(directory_fd)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def tree_content_hash(root: Path) -> str:
    """Hash relative file names and bytes for a directory tree."""
    digest = hashlib.sha256()
    root = Path(root)
    if not root.is_dir():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()