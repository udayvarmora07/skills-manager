"""Descriptor bounds and each caller's file and error policy."""

import errno
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import evals, file_reads, lockfiles, native_state


class BoundedReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "input"

    def test_exact_limit_and_one_byte_over(self):
        self.path.write_bytes(b"abcd")
        self.assertEqual(file_reads.read_regular_file(self.path, 4), b"abcd")
        with self.assertRaises(file_reads.FileTooLarge):
            file_reads.read_regular_file(self.path, 3)

    def test_growth_after_open_is_bounded(self):
        self.path.write_bytes(b"a")
        real_read = os.read
        read_sizes = []

        def grow_then_read(fd, count):
            read_sizes.append(count)
            with self.path.open("ab") as stream:
                stream.write(b"x" * 200)
            return real_read(fd, count)

        with mock.patch.object(file_reads.os, "read", side_effect=grow_then_read):
            with self.assertRaises(file_reads.FileTooLarge):
                file_reads.read_regular_file(self.path, 8)
        self.assertEqual(read_sizes, [9])

    def test_replacement_after_open_reads_the_checked_descriptor(self):
        self.path.write_bytes(b"old")
        replacement = self.root / "replacement"
        replacement.write_bytes(b"new data")
        real_fstat = os.fstat

        def replace_then_stat(fd):
            os.replace(replacement, self.path)
            return real_fstat(fd)

        with mock.patch.object(file_reads.os, "fstat", side_effect=replace_then_stat):
            self.assertEqual(file_reads.read_regular_file(self.path, 3), b"old")
        self.assertEqual(self.path.read_bytes(), b"new data")

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "atomic no-follow is unavailable")
    def test_replacement_with_symlink_is_rejected_when_nofollow_requested(self):
        self.path.write_text("old", encoding="utf-8")
        target = self.root / "target"
        target.write_text("new", encoding="utf-8")
        real_open = os.open

        def replace_before_open(path, flags):
            self.path.unlink()
            self.path.symlink_to(target)
            return real_open(path, flags)

        with mock.patch.object(file_reads.os, "open", side_effect=replace_before_open):
            with self.assertRaises(file_reads.SymlinkNotAllowed):
                file_reads.read_regular_file(self.path, 10, follow_symlinks=False)
        self.assertEqual(file_reads.read_regular_file(self.path, 10), b"new")

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"), "FIFO unavailable")
    def test_fifo_and_directory_are_rejected_without_waiting(self):
        os.mkfifo(self.path)
        with self.assertRaises(file_reads.NotRegularFile):
            file_reads.read_regular_file(self.path, 8)
        with self.assertRaises(file_reads.NotRegularFile):
            file_reads.read_regular_file(self.root, 8)

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK") and hasattr(os, "O_NOFOLLOW"), "FIFO/no-follow unavailable")
    def test_callers_report_fifo_without_waiting(self):
        os.mkfifo(self.path)
        self.assertEqual(native_state._load(self.path), ("unavailable", None))
        self.assertEqual(lockfiles.read_lock(self.path, kind="project")["reason"], "lock path is not a regular file")
        skill = self.root / "skill"
        (skill / "evals").mkdir(parents=True)
        (skill / "evals" / "evals.json").symlink_to(self.path)
        self.assertFalse(evals.load_cases(skill)["present"])

    def test_descriptor_is_closed_when_read_fails(self):
        self.path.write_bytes(b"a")
        seen = []

        def fail_read(fd, count):
            seen.append(fd)
            raise OSError("simulated read failure")

        with mock.patch.object(file_reads.os, "read", side_effect=fail_read):
            with self.assertRaisesRegex(OSError, "simulated read failure"):
                file_reads.read_regular_file(self.path, 8)
        with self.assertRaises(OSError) as exc:
            os.fstat(seen[0])
        self.assertEqual(exc.exception.errno, errno.EBADF)

    def test_no_nofollow_support_accepts_stable_regular_file(self):
        self.path.write_bytes(b"a")
        with mock.patch.object(file_reads.os, "O_NOFOLLOW", 0, create=True):
            self.assertEqual(file_reads.read_regular_file(self.path, 8, follow_symlinks=False), b"a")

    def test_no_nofollow_support_refuses_swapped_final_link(self):
        self.path.write_bytes(b"a")
        target = self.root / "target"
        target.write_bytes(b"other")
        real_fstat = os.fstat

        def replace_then_stat(fd):
            self.path.unlink()
            self.path.symlink_to(target)
            return real_fstat(fd)

        with mock.patch.object(file_reads.os, "O_NOFOLLOW", 0, create=True):
            with mock.patch.object(file_reads.os, "fstat", side_effect=replace_then_stat):
                with self.assertRaises(file_reads.SymlinkNotAllowed):
                    file_reads.read_regular_file(self.path, 8, follow_symlinks=False)

    def test_no_nofollow_support_refuses_swapped_regular_file(self):
        self.path.write_bytes(b"a")
        replacement = self.root / "replacement"
        replacement.write_bytes(b"other")
        real_fstat = os.fstat

        def replace_then_stat(fd):
            os.replace(replacement, self.path)
            return real_fstat(fd)

        with mock.patch.object(file_reads.os, "O_NOFOLLOW", 0, create=True):
            with mock.patch.object(file_reads.os, "fstat", side_effect=replace_then_stat):
                with self.assertRaises(OSError):
                    file_reads.read_regular_file(self.path, 8, follow_symlinks=False)

    def test_native_readers_keep_json_and_toml_policies(self):
        self.path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
        self.assertEqual(native_state._load(self.path), ("unavailable", None))
        self.path.write_text("key = 1\n", encoding="utf-8")
        self.assertEqual(native_state._load_toml(self.path), ("ok", {"key": 1}))
        link = self.root / "link"
        link.symlink_to(self.path)
        self.assertEqual(native_state._load_toml(link), ("ok", {"key": 1}))
        with mock.patch.object(native_state, "MAX_CONFIG_BYTES", 3):
            self.assertEqual(native_state._load_toml(link), ("unavailable", None))

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "atomic no-follow is unavailable")
    def test_lockfile_policy_and_error_messages(self):
        self.path.write_text(json.dumps({"version": 1, "skills": {}}), encoding="utf-8")
        self.assertEqual(lockfiles.read_lock(self.path, kind="project")["state"], "ok")
        link = self.root / "link"
        link.symlink_to(self.path)
        self.assertEqual(lockfiles.read_lock(link, kind="project")["reason"], "lockfile is a symlink")
        self.assertEqual(lockfiles.read_lock(self.root, kind="project")["reason"], "lock path is not a regular file")
        with mock.patch.object(lockfiles, "MAX_LOCK_BYTES", 3):
            self.assertEqual(lockfiles.read_lock(self.path, kind="project")["reason"], "lockfile exceeds 3 bytes")
        self.assertEqual(lockfiles.read_lock(self.root / "missing", kind="project")["state"], "missing")

    def test_evals_follow_symlink_and_report_oversize(self):
        skill = self.root / "skill"
        (skill / "evals").mkdir(parents=True)
        self.path.write_text('{"evals": [{"id": 1, "prompt": "hello"}]}', encoding="utf-8")
        (skill / "evals" / "evals.json").symlink_to(self.path)
        self.assertTrue(evals.load_cases(skill)["present"])
        with mock.patch.object(evals, "MAX_EVALS_FILE_BYTES", 3):
            report = evals.load_cases(skill)
        self.assertEqual(report["issues"][0]["message"], "evals.json is unreadable: evals.json exceeds 3 bytes")


if __name__ == "__main__":
    unittest.main()
