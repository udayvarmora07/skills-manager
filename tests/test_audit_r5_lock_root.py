"""R5 / S3 (docs/28): lock files live under the validated data dir, with a timeout.

Lock files used to live in ``tempfile.gettempdir()/skillsmgr-locks``.  Two
processes with different ``TMPDIR`` values therefore never excluded each other,
the shared directory had no ownership check (a planted symlink created a file
at an arbitrary path), and a lock nobody released blocked forever.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import atomic_io
from skillsmgr.store import LockTimeoutError, Store, StoreError

REPO = Path(__file__).resolve().parents[1]

_HOLDER = """
import sys, time
from pathlib import Path
from skillsmgr import atomic_io
atomic_io.register_lock_root(Path(sys.argv[1]))
lock = atomic_io.mutation_lock(Path(sys.argv[2]))
lock.acquire()
print("held", flush=True)
time.sleep(30)
"""


class LockRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="r5-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data = self.tmp / "data"
        self.store = Store(self.data)
        self.store.init_db()

    def _hold_in_child(self, key: Path, tmpdir: Path) -> subprocess.Popen:
        tmpdir.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, TMPDIR=str(tmpdir), PYTHONPATH=str(REPO), PYTHONDONTWRITEBYTECODE="1")
        child = subprocess.Popen(
            [sys.executable, "-c", _HOLDER, str(self.data), str(key)],
            stdout=subprocess.PIPE, env=env, cwd=str(REPO), text=True,
        )
        self.addCleanup(child.stdout.close)
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        self.assertEqual(child.stdout.readline().strip(), "held")
        return child

    def test_lock_files_live_under_the_data_dir_and_outside_skill_trees(self) -> None:
        self.store.create("alpha", "Use when testing lock placement.")
        lock_dir = self.data / "locks"
        self.assertTrue(lock_dir.is_dir())
        self.assertTrue(any(lock_dir.glob("*.lock")))
        self.assertEqual(stat.S_IMODE(lock_dir.stat().st_mode), 0o700)
        under_skills = [p for p in (self.data / "skills").rglob("*") if p.suffix == ".lock" or p.name == "locks"]
        self.assertEqual(under_skills, [])

    def test_lock_path_does_not_depend_on_tmpdir(self) -> None:
        key = self.data / "skills" / "alpha" / "SKILL.md"
        first = atomic_io._lock_file_path(key)
        with mock.patch.object(tempfile, "tempdir", str(self.tmp / "elsewhere")):
            second = atomic_io._lock_file_path(key)
        self.assertEqual(first, second)
        self.assertEqual(first.parent, (self.data / "locks").resolve())

    @unittest.skipUnless(hasattr(os, "fork"), "needs a second POSIX process")
    def test_processes_with_different_tmpdir_still_exclude_each_other(self) -> None:
        key = self.data / "skills" / ".skillsmgr-index-lock"
        self._hold_in_child(key, self.tmp / "tmp-a")
        with mock.patch.object(tempfile, "tempdir", str(self.tmp / "tmp-b")):
            lock = atomic_io.mutation_lock(key)
            acquired = lock.acquire(timeout=0.3)
        if acquired:
            lock.release()
        self.assertFalse(acquired, "a second process acquired a lock another process holds")

    @unittest.skipUnless(hasattr(os, "fork"), "needs a second POSIX process")
    def test_a_lock_held_elsewhere_times_out_as_a_clean_store_error(self) -> None:
        self._hold_in_child(self.data / "skills" / ".skillsmgr-index-lock", self.tmp / "tmp-a")
        outcome: dict = {}

        def attempt() -> None:
            try:
                self.store.create("beta", "Use when testing lock timeouts.")
            except Exception as exc:  # noqa: BLE001 - asserted below
                outcome["error"] = exc

        with mock.patch.object(atomic_io, "MUTATION_LOCK_TIMEOUT", 0.3):
            worker = threading.Thread(target=attempt, daemon=True)
            started = time.monotonic()
            worker.start()
            worker.join(10)
        self.assertFalse(worker.is_alive(), "the acquisition blocked instead of timing out")
        self.assertLess(time.monotonic() - started, 5)
        self.assertIsInstance(outcome.get("error"), LockTimeoutError)
        self.assertIsInstance(outcome["error"], StoreError)
        self.assertEqual(outcome["error"].status, 409)
        self.assertFalse((self.data / "skills" / "beta").exists())

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "O_NOFOLLOW unavailable")
    def test_a_planted_lock_symlink_is_not_followed(self) -> None:
        key = self.data / "skills" / "gamma" / "SKILL.md"
        lock_file = atomic_io._lock_file_path(key)
        victim = self.tmp / "victim.txt"
        lock_file.symlink_to(victim)
        with self.assertRaises(OSError):
            with atomic_io.mutation_lock(key):
                pass
        self.assertFalse(victim.exists())

    def test_a_symlinked_lock_directory_is_refused(self) -> None:
        other = self.tmp / "other-root"
        other.mkdir()
        atomic_io.register_lock_root(other)
        outside = self.tmp / "outside"
        outside.mkdir()
        (other / "locks").symlink_to(outside, target_is_directory=True)
        with self.assertRaises((OSError, ValueError)):
            atomic_io._lock_file_path(other / "x")
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
