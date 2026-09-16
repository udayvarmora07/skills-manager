"""Atomic filesystem primitives used by Store and scope adapters."""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import time

try:  # POSIX: advisory locks survive process exit and cover CLI + Web UI.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows fallback below
    _fcntl = None
try:  # Windows: keep the same cross-process contract where supported.
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - POSIX
    _msvcrt = None
from collections import OrderedDict
from pathlib import Path


_MUTATION_LOCKS: "OrderedDict[str, threading.RLock]" = OrderedDict()
_MUTATION_LOCKS_GUARD = threading.Lock()
#: BUG-12: one ``RLock`` used to be retained for every distinct resolved path
#: ever touched, for the whole life of the process -- a long-lived Web UI that
#: edits many transient paths (trash copies, staging siblings, snapshots) grew
#: the table without bound.  A lock is only needed while it is held or awaited,
#: so the table keeps at most this many entries and evicts the least recently
#: used locks that are provably free.
MAX_MUTATION_LOCKS = 512


def _lock_is_free(lock: threading.RLock) -> bool:
    """True only when *lock* is provably held by no thread.

    ``acquire(blocking=False)`` alone is not enough: an ``RLock`` is reentrant,
    so it succeeds for the thread that already owns it -- which made a lock in
    use look free and evictable mid-critical-section.  Current-thread ownership
    is checked first, and the registry guard means no other thread can be
    looking the same lock up while this runs.
    """
    is_owned = getattr(lock, "_is_owned", None)
    if callable(is_owned) and is_owned():
        return False
    try:
        if lock.acquire(blocking=False):
            lock.release()
            return True
    except (BlockingIOError, OSError):
        # Another process may hold the advisory sidecar even though no local
        # thread owns the wrapper; that lock is not evictable either.
        return False
    return False


def _evict_idle_locks() -> None:
    """Drop least-recently-used locks that nobody holds.

    Must be called with ``_MUTATION_LOCKS_GUARD`` held.
    """
    while len(_MUTATION_LOCKS) >= MAX_MUTATION_LOCKS:
        for key, lock in list(_MUTATION_LOCKS.items()):
            if _lock_is_free(lock):
                del _MUTATION_LOCKS[key]
                break
        else:
            # Every lock is currently held: the table is legitimately at its
            # peak, so allow a temporary overshoot rather than break exclusion.
            return


def _lock_file_path(path: Path) -> Path:
    """Return a stable sidecar outside managed data trees.

    Keeping lock files in ``/tmp`` avoids creating a fake skill directory when
    the lock key names a skill that does not exist yet, and avoids leaving
    ``.skillsmgr-*`` entries in the user's data tree after a successful request.
    The absolute path remains part of the digest, so independent data roots do
    not contend.
    """
    identity = str(Path(path).expanduser().resolve()).encode("utf-8")
    digest = hashlib.sha256(identity).hexdigest()
    root = Path(tempfile.gettempdir()) / "skillsmgr-locks"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    return root / f"{digest}.lock"


class _CrossProcessLock:
    """Reentrant thread lock plus an advisory lock held by this process.

    The file descriptor is opened lazily for each outermost acquisition and
    closed on the matching release.  ``flock`` is process-aware on POSIX, so a
    CLI and a Web UI using the same data directory now exclude one another;
    the in-process RLock still handles reentrancy and keeps the existing lock
    table bounded.  Windows uses a one-byte ``msvcrt.locking`` region when that
    module is available; unsupported platforms retain the thread-only behavior.
    """

    def __init__(self, path: Path):
        self.path = path
        self._thread_lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._depth = 0
        self._handle = None

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        if not blocking:
            acquired = self._thread_lock.acquire(False)
            if not acquired:
                return False
            if self._depth:
                self._depth += 1
                return True
            try:
                self._acquire_file(False)
            except BlockingIOError:
                self._thread_lock.release()
                return False
            except OSError:
                self._thread_lock.release()
                raise
            self._depth = 1
            return True
        if timeout is not None and timeout >= 0:
            deadline = time.monotonic() + timeout
            if not self._thread_lock.acquire(True, timeout):
                return False
        else:
            self._thread_lock.acquire()
            deadline = None
        if self._depth:
            self._depth += 1
            return True
        try:
            self._acquire_file(True, deadline=deadline)
        except Exception:
            self._thread_lock.release()
            raise
        self._depth = 1
        return True

    def _is_owned(self) -> bool:
        """Compatibility hook used by the bounded-table eviction probe."""
        return self._thread_lock._is_owned()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return False

    def release(self):
        if self._depth <= 0:
            raise RuntimeError("cannot release an unlocked mutation lock")
        self._depth -= 1
        if self._depth == 0:
            try:
                self._release_file()
            finally:
                self._thread_lock.release()
        else:
            self._thread_lock.release()

    def _acquire_file(self, blocking: bool, deadline=None):
        handle = open(_lock_file_path(self.path), "a+b")
        if _fcntl is not None:
            flags = _fcntl.LOCK_EX | (0 if blocking else _fcntl.LOCK_NB)
            if deadline is None:
                _fcntl.flock(handle.fileno(), flags)
            else:
                while True:
                    try:
                        _fcntl.flock(handle.fileno(), flags | _fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            handle.close()
                            raise TimeoutError("timed out acquiring mutation lock")
                        time.sleep(min(0.01, remaining))
        elif _msvcrt is not None:
            while True:
                try:
                    handle.seek(0)
                    _msvcrt.locking(handle.fileno(), _msvcrt.LK_NBLCK if not blocking else _msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    if not blocking or (deadline is not None and time.monotonic() >= deadline):
                        handle.close()
                        raise BlockingIOError("mutation lock is held")
                    time.sleep(0.01)
        self._handle = handle

    def _release_file(self):
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            if _fcntl is not None:
                _fcntl.flock(handle.fileno(), _fcntl.LOCK_UN)
            elif _msvcrt is not None:
                handle.seek(0)
                _msvcrt.locking(handle.fileno(), _msvcrt.LK_UNLCK, 1)
        finally:
            handle.close()


def mutation_lock(path: Path) -> _CrossProcessLock:
    """Return a bounded, reentrant cross-process lock for one path."""
    key = str(Path(path).expanduser().resolve())
    with _MUTATION_LOCKS_GUARD:
        lock = _MUTATION_LOCKS.get(key)
        if lock is None:
            _evict_idle_locks()
            lock = _CrossProcessLock(Path(key))
            _MUTATION_LOCKS[key] = lock
        else:
            _MUTATION_LOCKS.move_to_end(key)
        return lock


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
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        # A concurrent whole-directory move (cross-process trash/remove) may
        # have carried the unique temp file away; find it by name under the
        # surrounding tree so no .skillsmgr-tmp residue survives.
        try:
            search_root = path.parent.parent
            if search_root.is_dir():
                for hit in search_root.rglob(temp_path.name):
                    try:
                        hit.unlink()
                    except OSError:
                        pass
        except OSError:
            pass
        raise


def tree_content_hash(root: Path) -> str:
    """Hash relative file names and bytes for a directory tree.

    Only regular, non-symlink files are hashed, and symlinked directories are
    never descended into (STORE-9).  The digest has to describe exactly the
    members an export puts in the archive -- ``tar.add`` stores a symlink as a
    ``SYMTYPE`` member, which ``archive.validate_members`` rejects -- otherwise
    the manifest hash covers bytes the archive does not contain and the whole
    archive becomes unimportable.  It also used to follow a link that escaped
    the managed root, hashing (and thereby oracling) data outside it.
    """
    digest = hashlib.sha256()
    root = Path(root)
    if not root.is_dir():
        return digest.hexdigest()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = [
            name for name in sorted(dirnames) if not (current / name).is_symlink()
        ]
        for name in sorted(filenames):
            path = current / name
            if path.is_symlink():
                continue
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()