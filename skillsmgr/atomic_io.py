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

from .errors import LockTimeoutError
from . import paths
from .path_safety import mkdir_private


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


#: R5/S3: how long a blocking acquisition waits for *another process* before
#: giving up with a clean ``LockTimeoutError``.  A lock file nobody releases --
#: a wedged process, or another user holding it -- used to block forever.
#: In-process contention is not bounded: those holders are this process's own
#: threads and always release.
MUTATION_LOCK_TIMEOUT = 60.0

#: Directory, under a validated data root, that holds the advisory lock files.
#: It is a sibling of ``skills/``, never inside any managed skill tree, so
#: acquiring a lock for a path that does not exist yet cannot materialise a
#: fake skill directory.
LOCK_DIRNAME = "locks"

#: Data roots registered by ``Store`` construction, most recent last.  Bounded
#: so a test process that builds thousands of stores cannot grow it forever.
_LOCK_ROOTS: "OrderedDict[str, Path]" = OrderedDict()
_LOCK_ROOTS_GUARD = threading.Lock()
MAX_LOCK_ROOTS = 64


def register_lock_root(data_dir: Path) -> None:
    """Record *data_dir* as a root whose lock files live in ``<data_dir>/locks``.

    ``Store`` calls this on construction.  Nothing is created here: a read
    must create nothing (docs/24 §D3-4); the directory appears on the first
    acquisition.
    """
    resolved = Path(os.path.realpath(Path(data_dir).expanduser()))
    with _LOCK_ROOTS_GUARD:
        _LOCK_ROOTS.pop(str(resolved), None)
        _LOCK_ROOTS[str(resolved)] = resolved
        while len(_LOCK_ROOTS) > MAX_LOCK_ROOTS:
            _LOCK_ROOTS.popitem(last=False)


def registered_root_containing(path: Path) -> Path | None:
    """The longest registered data root that contains *path*, if any."""
    with _LOCK_ROOTS_GUARD:
        roots = list(_LOCK_ROOTS.values())
    matches = [root for root in roots if path.is_relative_to(root)]
    return max(matches, key=lambda root: len(root.parts)) if matches else None


def _lock_root_for(identity: Path) -> Path:
    """Choose the data root whose ``locks/`` directory serialises *identity*.

    A path inside a registered root uses that root (longest match).  Anything
    else -- an agent-scope skill, a review artifact elsewhere -- uses the most
    recently registered root, so a CLI and a Web UI on the same data directory
    agree.  With no registered root the validated ``paths.data_dir()`` is used.
    Unlike ``tempfile.gettempdir()``, none of these depend on ``TMPDIR`` (S3).
    """
    containing = registered_root_containing(identity)
    if containing is not None:
        return containing
    with _LOCK_ROOTS_GUARD:
        latest = next(reversed(_LOCK_ROOTS.values()), None)
    return latest if latest is not None else paths.data_dir()


def _private_lock_dir(root: Path) -> Path:
    """Create or verify ``<root>/locks`` as an owner-only, non-symlink directory."""

    directory = root / LOCK_DIRNAME
    mkdir_private(directory)
    info = os.lstat(directory)
    if not os.path.isdir(directory) or os.path.islink(directory):
        raise OSError(f"lock directory is not a plain directory: {directory}")
    getuid = getattr(os, "getuid", None)
    if getuid is not None:
        if info.st_uid != getuid():
            raise OSError(f"lock directory is owned by another user: {directory}")
        if info.st_mode & 0o077:
            os.chmod(directory, 0o700)
    return directory


def _lock_file_path(path: Path) -> Path:
    """Return the lock file for *path* under a validated data root.

    The absolute path remains part of the digest, so independent keys never
    contend.  The file is opened with ``O_NOFOLLOW`` by the caller, so a planted
    symlink cannot redirect the create to an arbitrary path (S3).
    """
    identity = Path(os.path.realpath(Path(path).expanduser()))
    digest = hashlib.sha256(str(identity).encode("utf-8")).hexdigest()
    return _private_lock_dir(_lock_root_for(identity)) / f"{digest}.lock"


def _open_lock_file(path: Path):
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags, 0o600)
    return os.fdopen(fd, "r+b")


def _lock_timeout_error(path: Path, waited: float):
    return LockTimeoutError(
        f"timed out after {waited:g}s waiting for another process to release the "
        f"lock on {path}; retry, or stop the other skills-mgr process"
    )


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
        explicit = timeout is not None and timeout >= 0
        if explicit:
            deadline = time.monotonic() + timeout
            if not self._thread_lock.acquire(True, timeout):
                return False
        else:
            self._thread_lock.acquire()
            deadline = None
        if self._depth:
            self._depth += 1
            return True
        if deadline is None:
            deadline = time.monotonic() + MUTATION_LOCK_TIMEOUT
        try:
            self._acquire_file(True, deadline=deadline)
        except TimeoutError:
            self._thread_lock.release()
            if explicit:
                return False
            raise _lock_timeout_error(self.path, MUTATION_LOCK_TIMEOUT) from None
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
        handle = _open_lock_file(_lock_file_path(self.path))
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
                    if not blocking:
                        handle.close()
                        raise BlockingIOError("mutation lock is held")
                    if deadline is not None and time.monotonic() >= deadline:
                        handle.close()
                        raise TimeoutError("timed out acquiring mutation lock")
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
        os.replace(temp_path, path)
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


def is_sha256_hex(value: object) -> bool:
    """True for a 64-character hexadecimal string (either case)."""
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value)


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