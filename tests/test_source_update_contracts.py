"""Hermetic Phase 2 contracts for the filesystem-owned source-update service."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from skillsmgr import scopes
from skillsmgr.scopes import Scope
from skillsmgr.source_update import (
    SourceUpdateError,
    cancel_update_review,
    commit_update_review,
    list_update_snapshots,
    prepare_local_update,
    prepare_snapshot_update,
    read_update_review,
)
from skillsmgr.source_lock import SOURCE_LOCK_FILENAME
from skillsmgr.store import Store


class SourceUpdateContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / "manager"
        self.store = Store(data_dir=self.data)
        self.store.create("demo", "Use demo when testing.", body="old body\n")
        self.source_number = 0

    def tearDown(self):
        scopes.set_global_store(None)
        self.tmp.cleanup()

    @staticmethod
    def _document(name: str, body: str) -> str:
        return f"---\nname: {name}\ndescription: Use {name} when testing.\n---\n{body}"

    def _source(self, name="demo", body="new body\n", *, disabled=False) -> Path:
        self.source_number += 1
        source = self.root / f"source-{self.source_number}-{body.strip().replace(' ', '-') or 'empty'}"
        source.mkdir()
        filename = "SKILL.md.disabled" if disabled else "SKILL.md"
        (source / filename).write_text(self._document(name, body), encoding="utf-8")
        return source

    def _prepare(self, source: Path, **kwargs) -> dict:
        return prepare_local_update(self.data, "demo", "global", source, **kwargs)

    def test_prepare_stages_private_candidate_preserves_activation_and_apply_is_snapshot_backed(self):
        source = self._source(disabled=True)
        (source / ".skillsmgr-provenance.json").write_text("untrusted", encoding="utf-8")
        (source / ".skillsmgr-source-lock.json").write_text("untrusted", encoding="utf-8")
        result = self._prepare(source)

        self.assertEqual(result["review_state"], "pending")
        self.assertTrue(result["activation_preserved"])
        self.assertTrue(result["resulting_disabled"] is False)
        self.assertTrue(result["staged"])
        review_dir = self.data / "source-update-reviews" / result["review_id"]
        self.assertTrue((review_dir / "candidate" / "SKILL.md").is_file())
        self.assertFalse((review_dir / "candidate" / "SKILL.md.disabled").exists())
        self.assertFalse((review_dir / "candidate" / ".skillsmgr-provenance.json").exists())
        self.assertFalse((review_dir / "candidate" / ".skillsmgr-source-lock.json").exists())
        if os.name == "posix":
            self.assertEqual(review_dir.stat().st_mode & 0o777, 0o700)
            self.assertEqual((review_dir / "review.json").stat().st_mode & 0o777, 0o600)

        (source / "SKILL.md.disabled").write_text(self._document("demo", "mutated source\n"), encoding="utf-8")
        result = commit_update_review(
            self.data, result["review_id"], name="demo", scope="global", approve=True
        )
        self.assertTrue(result["committed"])
        self.assertTrue((self.store.skills_dir / "demo" / "SKILL.md").is_file())
        self.assertIn("new body", (self.store.skills_dir / "demo" / "SKILL.md").read_text())
        self.assertTrue((self.store.skills_dir / "demo" / SOURCE_LOCK_FILENAME).is_file())
        snapshots = list_update_snapshots(self.data, "demo", "global")
        self.assertEqual(len(snapshots), 1)
        self.assertTrue(snapshots[0]["readable"])

    def test_invalid_and_no_change_previews_are_not_reusable_reviews(self):
        invalid = self.root / "invalid"
        invalid.mkdir()
        (invalid / "SKILL.md").write_text("---\nname: wrong\ndescription: bad\n---\n", encoding="utf-8")
        result = self._prepare(invalid)
        self.assertEqual(result["review_state"], "blocked")
        self.assertIsNone(result["review_id"])
        review_root = self.data / "source-update-reviews"
        self.assertFalse(review_root.exists() and list(review_root.iterdir()))

        same = self.root / "same"
        same.mkdir()
        (same / "SKILL.md").write_text(self._document("demo", "old body\n"), encoding="utf-8")
        result = self._prepare(same)
        self.assertEqual(result["review_state"], "no-change")
        self.assertIsNone(result["review_id"])

    def test_candidate_symlinks_are_rejected_without_following_them(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are unavailable on this platform")
        source = self._source()
        outside = self.root / "outside"
        outside.write_text("must not be copied", encoding="utf-8")
        (source / "linked.txt").symlink_to(outside)
        with self.assertRaisesRegex(SourceUpdateError, "candidate-unsafe"):
            self._prepare(source)

    def test_staged_candidate_and_target_changes_have_stable_errors(self):
        result = self._prepare(self._source())
        review_id = result["review_id"]
        staged = self.data / "source-update-reviews" / review_id / "candidate" / "SKILL.md"
        staged.write_text(self._document("demo", "changed staged candidate\n"), encoding="utf-8")
        with self.assertRaisesRegex(SourceUpdateError, "review-candidate-changed") as candidate_error:
            commit_update_review(self.data, review_id, name="demo", scope="global", approve=True)
        self.assertEqual(candidate_error.exception.code, "review-candidate-changed")

        result = self._prepare(self._source(body="second body\n"))
        (self.store.skills_dir / "demo" / "SKILL.md").write_text(
            self._document("demo", "target changed after review\n"), encoding="utf-8"
        )
        with self.assertRaisesRegex(SourceUpdateError, "target-changed") as target_error:
            commit_update_review(self.data, result["review_id"], name="demo", scope="global", approve=True)
        self.assertEqual(target_error.exception.code, "target-changed")

    def test_exact_recursive_target_resolution_requires_observed_path(self):
        scope_root = self.root / "recursive"
        first = scope_root / "one" / "demo"
        second = scope_root / "two" / "demo"
        for target, body in ((first, "one old\n"), (second, "two old\n")):
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text(self._document("demo", body), encoding="utf-8")
        descriptor = Scope("test-recursive", "Test recursive", scope_root, "agent", True, True, True, "test")
        with mock.patch.object(scopes, "known_scopes", return_value=[descriptor]):
            with self.assertRaisesRegex(SourceUpdateError, "target-ambiguous"):
                prepare_local_update(self.data, "demo", "test-recursive", self._source())
            result = prepare_local_update(
                self.data, "demo", "test-recursive", self._source(body="new nested\n"),
                target_path=second,
            )
        self.assertEqual(Path(result["target"]["physical_path"]), second.resolve())

    def test_disabled_target_stays_disabled_when_source_is_active(self):
        self.store.disable("demo")
        result = self._prepare(self._source(body="active source\n"))
        self.assertTrue(result["resulting_disabled"])
        commit_update_review(self.data, result["review_id"], name="demo", scope="global", approve=True)
        target = self.store.skills_dir / "demo"
        self.assertTrue((target / "SKILL.md.disabled").is_file())
        self.assertFalse((target / "SKILL.md").exists())

    def test_snapshot_retention_and_rollback_use_the_same_review_pipeline(self):
        for index in range(6):
            result = self._prepare(self._source(body=f"version {index}\n"))
            commit_update_review(self.data, result["review_id"], name="demo", scope="global", approve=True)
        snapshots = list_update_snapshots(self.data, "demo", "global")
        self.assertEqual(len(snapshots), 5)
        self.assertEqual(snapshots, sorted(snapshots, key=lambda item: item["created_at"], reverse=True))
        rollback = prepare_snapshot_update(self.data, "demo", "global", snapshots[0]["snapshot_id"])
        self.assertEqual(rollback["review_state"], "pending")
        self.assertTrue(rollback["rollback_from_snapshot"])
        commit_update_review(self.data, rollback["review_id"], name="demo", scope="global", approve=True)
        self.assertEqual(len(list_update_snapshots(self.data, "demo", "global")), 5)

    def test_permissions_and_review_lifecycle_are_clean(self):
        target = self.store.skills_dir / "demo"
        original_mode = target.stat().st_mode & 0o777
        try:
            target.chmod(0o500)
            with self.assertRaisesRegex(SourceUpdateError, "target-not-writable"):
                self._prepare(self._source())
        finally:
            target.chmod(original_mode)

        result = self._prepare(self._source())
        self.assertEqual(read_update_review(self.data, result["review_id"])["review_state"], "pending")
        cancelled = cancel_update_review(self.data, result["review_id"])
        self.assertEqual(cancelled["review_state"], "cancelled")
        with self.assertRaisesRegex(SourceUpdateError, "review-not-pending"):
            commit_update_review(self.data, result["review_id"], name="demo", scope="global", approve=True)

    def test_concurrent_apply_commits_once(self):
        result = self._prepare(self._source())
        review_id = result["review_id"]

        def apply_once():
            try:
                return commit_update_review(self.data, review_id, name="demo", scope="global", approve=True)
            except SourceUpdateError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: apply_once(), range(2)))
        self.assertEqual(sum(isinstance(outcome, dict) and outcome.get("committed") for outcome in outcomes), 1)
        self.assertIn("review-not-pending", outcomes)


if __name__ == "__main__":
    unittest.main()
