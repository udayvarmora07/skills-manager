"""Failure paths and path handling retained by the review extraction."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import backup_sync, registry, source_update


class ReviewArtifactFailures(unittest.TestCase):
    def test_sync_rejects_symlink_before_dotdot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'elsewhere' / 'child').mkdir(parents=True)
            (root / 'link').symlink_to(root / 'elsewhere' / 'child', target_is_directory=True)
            with self.assertRaisesRegex(backup_sync.BackupSyncError, 'path cannot contain a symlink'):
                backup_sync._review_path(root / 'link' / '..' / 'data', 'a' * 32)

    def test_source_writer_cleans_temp_after_directory_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / 'review'
            directory.mkdir()
            moved = root / 'moved'

            def move_then_fail(fd):
                directory.rename(moved)
                raise OSError('simulated concurrent move')

            with mock.patch('skillsmgr.atomic_io.os.fsync', side_effect=move_then_fail):
                with self.assertRaises(OSError):
                    source_update._write_record(directory, {'status': 'pending'})
            self.assertEqual([], list(moved.iterdir()))

    def test_registry_closes_descriptor_if_fchmod_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured = []

            def fail(fd, mode):
                captured.append(fd)
                raise OSError('simulated fchmod failure')

            with mock.patch('skillsmgr.review_artifacts.os.fchmod', side_effect=fail):
                with self.assertRaises(OSError):
                    registry.write_private_bytes(root / 'review.json', b'{}')
            self.assertEqual(1, len(captured))
            with self.assertRaises(OSError):
                os.fstat(captured[0])
            self.assertEqual([], list(root.iterdir()))

    def test_source_writer_does_not_require_fchmod(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch('skillsmgr.review_artifacts.os.fchmod', side_effect=OSError('unsupported')):
                source_update._write_record(Path(tmp), {'status': 'pending'})
