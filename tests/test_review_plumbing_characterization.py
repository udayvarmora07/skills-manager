"""Characterization of the three review-artifact implementations before R15.

Three modules each keep their own private, expiring, single-use review:

* ``skillsmgr.registry``      ``<data>/registry-reviews/<id>.json``
* ``skillsmgr.backup_sync``   ``<data>/sync-reviews/<id>.json``
* ``skillsmgr.source_update`` ``<data>/source-update-reviews/<id>/review.json``

This file pins only facts a caller can observe, so the shared-mechanics
refactor cannot quietly change one module's contract: review id shape,
directory and file permission bits, the error type plus message/code for an
unknown id, a malformed id, an expired review, a replayed commit and a
cancelled review, the on-disk JSON keys of a fresh review, and that writing a
review touches nothing outside its own review directory.

It is deliberately written against the behaviour of the *unchanged* modules.
Do not edit it to accommodate a refactor.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from skillsmgr import context
from skillsmgr import backup_sync, registry, scopes, source_update
from skillsmgr.source_lock import local_manifest
from skillsmgr.store import Store


REVIEW_ID = re.compile(r"^[0-9a-f]{32}$")
MALFORMED_IDS = ("../x", "A" * 32, "0" * 31)


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def _tree(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


def _only_under(paths: set[str], relative: str) -> bool:
    return all(path == relative or path.startswith(relative + os.sep) for path in paths)


class _IsolatedCase(unittest.TestCase):
    """A private data root and HOME, as the other hermetic suites use."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.data = self.base / "data"
        self.data.mkdir(mode=0o700)
        environment = mock.patch.dict(
            os.environ,
            {"SKILLS_MANAGER_DATA": str(self.data), "HOME": str(self.base)},
        )
        environment.start()
        self.addCleanup(environment.stop)


def _registry_snapshot() -> dict:
    from skillsmgr.registry import registry_snapshot_hash

    files = [
        {"path": "SKILL.md", "contents": "---\nname: demo\ndescription: Demo.\n---\n# Demo\n"},
        {"path": "references/readme.txt", "contents": "reference\n"},
    ]
    snapshot = registry.validate_snapshot(
        {"id": "owner/repo/demo", "files": files, "hash": registry_snapshot_hash(files)}
    )
    snapshot.update(
        {
            "id": "owner/repo/demo",
            "source": "owner/repo",
            "slug": "demo",
            "api_url": "https://skills.sh/api/v1/skills/owner/repo/demo",
            "_registry": {"cache_state": "miss", "stale": False},
        }
    )
    return snapshot


class RegistryReviewCharacterization(_IsolatedCase):
    def setUp(self):
        super().setUp()
        self.snapshot = _registry_snapshot()
        self.inspection = {"validation": {"valid": True}, "risk": {"findings": []}}

    def _write(self, inspection=None) -> dict:
        return registry.write_registry_review(
            self.data, self.snapshot, self.inspection if inspection is None else inspection
        )

    def test_review_id_format_and_permission_bits(self):
        review = self._write()
        self.assertRegex(review["review_id"], REVIEW_ID)
        review_dir = self.data / registry.REGISTRY_REVIEW_DIRNAME
        review_path = review_dir / f"{review['review_id']}.json"
        self.assertEqual(0o700, _mode(self.data))
        self.assertEqual(0o700, _mode(review_dir))
        self.assertEqual(0o600, _mode(review_path))

    def test_fresh_review_on_disk_json_keys(self):
        review = self._write()
        path = self.data / registry.REGISTRY_REVIEW_DIRNAME / f"{review['review_id']}.json"
        raw = path.read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        record = json.loads(raw.decode("utf-8"))
        self.assertEqual(
            {
                "created_at",
                "expires_epoch",
                "inspection",
                "review_id",
                "snapshot",
                "status",
                "version",
            },
            set(record),
        )
        self.assertEqual("pending", record["status"])
        self.assertEqual(review["review_id"], record["review_id"])
        self.assertEqual(1, record["version"])

    def test_unknown_review_id(self):
        with self.assertRaises(registry.RegistryError) as caught:
            registry.read_registry_review(self.data, "0" * 32)
        self.assertEqual("registry review was not found", str(caught.exception))

    def test_malformed_review_ids_are_rejected_before_any_path(self):
        for review_id in MALFORMED_IDS:
            with self.assertRaises(registry.RegistryError) as caught:
                registry.read_registry_review(self.data, review_id)
            self.assertEqual("registry review id is invalid", str(caught.exception))
        self.assertEqual({"data"}, {path.name for path in self.base.iterdir()})

    def test_expired_review(self):
        review = self._write()
        with mock.patch.object(registry, "_now", return_value=10**12):
            with self.assertRaises(registry.RegistryError) as caught:
                registry.read_registry_review(self.data, review["review_id"])
        self.assertEqual("registry review has expired; fetch it again", str(caught.exception))

    def test_replayed_commit(self):
        review = self._write()
        committed = registry.mark_registry_review_committed(self.data, review["review_id"])
        self.assertEqual("committed", committed["status"])
        with self.assertRaises(registry.RegistryError) as caught:
            registry.read_registry_review(self.data, review["review_id"])
        self.assertEqual("registry review has already been committed", str(caught.exception))

    def test_credential_fields_are_rejected_without_writing(self):
        before = _tree(self.data)
        with self.assertRaises(registry.RegistryError) as caught:
            self._write({"validation": {"valid": True}, "risk": {"access_token": "redacted"}})
        self.assertEqual("registry review cannot contain credential fields", str(caught.exception))
        self.assertEqual(before, _tree(self.data))

    def test_a_review_writes_only_inside_its_directory(self):
        before = _tree(self.data)
        self._write()
        created = _tree(self.data) - before
        self.assertTrue(_only_under(created, registry.REGISTRY_REVIEW_DIRNAME), created)


class SyncReviewCharacterization(_IsolatedCase):
    def setUp(self):
        super().setUp()
        self.base_manifest = backup_sync.build_manifest(
            {"demo": {"digest": "base", "metadata_digest": "meta"}}, source="local"
        )
        self.local_manifest = backup_sync.build_manifest(
            {"demo": {"digest": "mine", "metadata_digest": "meta"}, "local-only": "x"},
            source="local",
        )
        self.remote_manifest = backup_sync.build_manifest(
            {"demo": {"digest": "theirs", "metadata_digest": "meta"}, "remote-only": "y"},
            source="origin",
        )
        self.target = self.base / "current"
        self.target.mkdir()
        (self.target / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Demo.\n---\n# Original\n", encoding="utf-8"
        )

    def _candidate(self, body: str = "Updated") -> Path:
        candidate = self.base / f"candidate-{body}"
        candidate.mkdir()
        (candidate / "SKILL.md").write_text(
            f"---\nname: demo\ndescription: Demo.\n---\n# {body}\n", encoding="utf-8"
        )
        return candidate

    def _prepare(self) -> dict:
        candidate = self._candidate()
        return backup_sync.prepare_sync_review(
            self.data,
            self.base_manifest,
            self.local_manifest,
            self.remote_manifest,
            target={"physical_path": str(self.target), "contained": True},
            candidate_hash=local_manifest(candidate)["sha256"],
            strategy="keep-mine",
        )

    def test_review_id_format_and_permission_bits(self):
        review = self._prepare()
        self.assertRegex(review["review_id"], REVIEW_ID)
        review_dir = self.data / backup_sync.SYNC_REVIEW_DIRNAME
        review_path = review_dir / f"{review['review_id']}.json"
        self.assertEqual(0o700, _mode(review_dir))
        self.assertEqual(0o600, _mode(review_path))

    def test_fresh_review_on_disk_json_keys(self):
        review = self._prepare()
        path = self.data / backup_sync.SYNC_REVIEW_DIRNAME / f"{review['review_id']}.json"
        raw = path.read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        record = json.loads(raw.decode("utf-8"))
        self.assertEqual(
            {
                "base",
                "candidate_hash",
                "created_at",
                "expires_epoch",
                "git",
                "local",
                "plan",
                "remote",
                "remote_manifest_hash",
                "remote_source",
                "review_id",
                "status",
                "target",
                "version",
            },
            set(record),
        )
        self.assertEqual("pending", record["status"])

    def test_unknown_review_id(self):
        with self.assertRaises(backup_sync.BackupSyncError) as caught:
            backup_sync.read_sync_review(self.data, "0" * 32)
        self.assertEqual("sync review was not found", str(caught.exception))

    def test_malformed_review_ids_are_rejected_before_any_path(self):
        for review_id in MALFORMED_IDS:
            with self.assertRaises(backup_sync.BackupSyncError) as caught:
                backup_sync.read_sync_review(self.data, review_id)
            self.assertEqual("sync review id is invalid", str(caught.exception))
        self.assertFalse((self.data / backup_sync.SYNC_REVIEW_DIRNAME).exists())

    def test_expired_review(self):
        review = self._prepare()
        with mock.patch.object(backup_sync.time, "time", return_value=10**12):
            with self.assertRaises(backup_sync.BackupSyncError) as caught:
                backup_sync.read_sync_review(self.data, review["review_id"])
        self.assertEqual("sync review has expired; prepare it again", str(caught.exception))

    def test_replayed_commit(self):
        candidate = self._candidate()
        review = backup_sync.prepare_sync_review(
            self.data,
            self.base_manifest,
            self.local_manifest,
            self.remote_manifest,
            target={"physical_path": str(self.target), "contained": True},
            candidate_hash=local_manifest(candidate)["sha256"],
            strategy="keep-mine",
        )
        backup_sync.commit_sync_review(
            self.data,
            review["review_id"],
            candidate,
            approve=True,
            snapshot_root=self.base / "snapshots",
        )
        with self.assertRaises(backup_sync.BackupSyncError) as caught:
            backup_sync.read_sync_review(self.data, review["review_id"])
        self.assertEqual("sync review has already been committed", str(caught.exception))

    def test_a_review_writes_only_inside_its_directory(self):
        before = _tree(self.data)
        self._prepare()
        created = _tree(self.data) - before
        self.assertTrue(_only_under(created, backup_sync.SYNC_REVIEW_DIRNAME), created)


class SourceUpdateReviewCharacterization(_IsolatedCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(context.set_active_store, None)
        self.store = Store(data_dir=self.data)
        self.store.create("demo", "Use demo when testing.", body="old body\n")
        self.sources = 0

    def _source(self, body: str = "new body\n") -> Path:
        self.sources += 1
        source = self.base / f"source-{self.sources}"
        source.mkdir()
        (source / "SKILL.md").write_text(
            f"---\nname: demo\ndescription: Use demo when testing.\n---\n{body}",
            encoding="utf-8",
        )
        return source

    def _prepare(self) -> dict:
        return source_update.prepare_local_update(self.data, "demo", "global", self._source())

    def test_review_id_format_and_permission_bits(self):
        review = self._prepare()
        self.assertRegex(review["review_id"], REVIEW_ID)
        review_dir = self.data / "source-update-reviews" / review["review_id"]
        self.assertEqual(0o700, _mode(review_dir))
        self.assertEqual(0o600, _mode(review_dir / "review.json"))

    def test_fresh_review_on_disk_json_keys(self):
        review = self._prepare()
        path = self.data / "source-update-reviews" / review["review_id"] / "review.json"
        raw = path.read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        record = json.loads(raw.decode("utf-8"))
        self.assertEqual(
            {
                "activation_preserved",
                "candidate",
                "created_at",
                "expires_epoch",
                "preview",
                "resulting_disabled",
                "review_expires_at",
                "review_id",
                "rollback_from_snapshot",
                "source",
                "source_review",
                "status",
                "target",
                "version",
            },
            set(record),
        )
        self.assertEqual("pending", record["status"])

    def test_unknown_review_id(self):
        with self.assertRaises(source_update.SourceUpdateError) as caught:
            source_update.read_update_review(self.data, "0" * 32)
        self.assertEqual("review-not-found", caught.exception.code)
        self.assertEqual("update review is unavailable", caught.exception.message)

    def test_malformed_review_ids_are_rejected_before_any_path(self):
        for review_id in MALFORMED_IDS:
            with self.assertRaises(source_update.SourceUpdateError) as caught:
                source_update.read_update_review(self.data, review_id)
            self.assertEqual("invalid-review-id", caught.exception.code)
            self.assertEqual(
                "review id must be 32 lowercase hexadecimal characters",
                caught.exception.message,
            )
        self.assertFalse((self.data / "source-update-reviews").exists())

    def test_expired_review_is_marked_and_rejected(self):
        review = self._prepare()
        future = datetime.now(timezone.utc) + timedelta(days=2)
        with mock.patch.object(source_update, "_now", return_value=future):
            with self.assertRaises(source_update.SourceUpdateError) as caught:
                source_update.read_update_review(self.data, review["review_id"])
        self.assertEqual("review-expired", caught.exception.code)
        self.assertEqual("update review has expired", caught.exception.message)
        path = self.data / "source-update-reviews" / review["review_id"] / "review.json"
        self.assertEqual("expired", json.loads(path.read_bytes())["status"])

    def test_replayed_commit(self):
        review = self._prepare()
        source_update.commit_update_review(
            self.data, review["review_id"], name="demo", scope="global", approve=True
        )
        with self.assertRaises(source_update.SourceUpdateError) as caught:
            source_update.commit_update_review(
                self.data, review["review_id"], name="demo", scope="global", approve=True
            )
        self.assertEqual("review-not-pending", caught.exception.code)
        self.assertEqual("update review is no longer pending", caught.exception.message)

    def test_cancelled_review(self):
        review = self._prepare()
        cancelled = source_update.cancel_update_review(self.data, review["review_id"])
        self.assertEqual("cancelled", cancelled["review_state"])
        self.assertEqual(
            "cancelled",
            source_update.read_update_review(self.data, review["review_id"])["review_state"],
        )
        with self.assertRaises(source_update.SourceUpdateError) as caught:
            source_update.commit_update_review(
                self.data, review["review_id"], name="demo", scope="global", approve=True
            )
        self.assertEqual("review-not-pending", caught.exception.code)

    def test_a_review_writes_only_inside_its_directory(self):
        before = _tree(self.data)
        self._prepare()
        created = _tree(self.data) - before
        self.assertTrue(_only_under(created, "source-update-reviews"), created)


if __name__ == "__main__":
    unittest.main()
