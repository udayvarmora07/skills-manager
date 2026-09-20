"""Hermetic DEL-07 source-lock and update-preview contracts."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from skillsmgr.source_lock import (
    SourceLockError,
    commit_local_update,
    local_manifest,
    preview_local_update,
    read_source_lock,
    restore_source_snapshot,
    review_local_update,
    source_identity,
    source_lock_status,
    write_source_lock,
)


class SourceLockContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.current = self.root / "current"
        self.candidate = self.root / "candidate"
        self.current.mkdir()
        self.candidate.mkdir()
        self._write(self.current, "SKILL.md", "---\nname: demo\ndescription: Use demo when testing.\n---\nhello\n")
        self._write(self.current, "references/old.md", "old\n")
        self._write(self.candidate, "SKILL.md", "---\nname: demo\ndescription: Use demo when testing.\n---\nhello\r\n")
        self._write(self.candidate, "references/new.md", "new\n")

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _write(root: Path, name: str, value: str):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8", newline="")

    def test_source_identity_supports_kinds_and_rejects_credentials(self):
        for kind in ("local", "git", "archive", "registry"):
            self.assertEqual(source_identity(kind, "owner/repo")["kind"], kind)
        with self.assertRaises(SourceLockError):
            source_identity("git", "https://user:secret@example.invalid/repo")
        digest = hashlib.sha256(b"x").hexdigest().upper()
        self.assertEqual(source_identity("git", "owner/repo", revision="abc", digest=digest)["digest"], digest.lower())

    def test_manifest_is_bounded_and_excludes_manager_sidecar(self):
        self._write(self.current, ".skillsmgr-provenance.json", "secret-free")
        manifest = local_manifest(self.current)
        self.assertNotIn(".skillsmgr-provenance.json", {item["path"] for item in manifest["files"]})
        self.assertEqual(len(manifest["sha256"]), 64)

    def test_preview_reports_add_remove_and_line_ending_only_without_mutation(self):
        before = local_manifest(self.current)["sha256"]
        preview = preview_local_update(
            self.current,
            self.candidate,
            target={"scope": "global", "physical_root": str(self.root), "physical_path": str(self.current), "contained": True},
        )
        self.assertEqual(preview["review_state"], "review-required")
        self.assertEqual(preview["source_state"], "local-only")
        self.assertEqual(preview["comparison"]["line_ending_only"], ["SKILL.md"])
        self.assertEqual(preview["comparison"]["added"], ["references/new.md"])
        self.assertEqual(preview["comparison"]["removed"], ["references/old.md"])
        self.assertFalse(preview["commit_allowed"])
        self.assertFalse(preview["staged"])
        self.assertEqual(local_manifest(self.current)["sha256"], before)

    def test_real_change_is_not_misclassified_as_line_ending_only(self):
        self._write(self.candidate, "SKILL.md", "---\nname: demo\ndescription: Use demo when testing.\n---\nchanged\r\n")
        preview = preview_local_update(self.current, self.candidate, target={"physical_path": str(self.current)})
        changed = next(item for item in preview["comparison"]["changed_files"] if item["path"] == "SKILL.md")
        self.assertFalse(changed["line_ending_only"])
        self.assertEqual(changed["explanation"], "raw file content differs")
        self.assertTrue(changed["diff"])

    def test_missing_source_and_missing_target_are_explicit(self):
        missing = preview_local_update(self.current, self.root / "missing", target={"physical_path": str(self.current)})
        self.assertEqual(missing["source_state"], "missing")
        self.assertEqual(missing["review_state"], "source-unavailable")
        target_required = preview_local_update(self.current, self.candidate)
        self.assertTrue(target_required["target"]["required"])
        self.assertEqual(target_required["review_state"], "target-required")
        self.assertIsNone(target_required["target"]["physical_path"])

    def test_validation_errors_block_and_risk_remains_advisory(self):
        self._write(self.candidate, "SKILL.md", "---\nname: demo\n---\nRun rm -rf /tmp/x\n")
        preview = preview_local_update(self.current, self.candidate, target={"physical_path": str(self.current)})
        self.assertEqual(preview["review_state"], "blocked")
        self.assertFalse(preview["validation"]["valid"])
        self.assertEqual(preview["risk"]["policy"].split(";")[0], "advisory-only")

    def test_symlink_candidate_fails_closed(self):
        outside = self.root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        (self.candidate / "escape.txt").symlink_to(outside)
        preview = preview_local_update(self.current, self.candidate, target={"physical_path": str(self.current)})
        self.assertEqual(preview["source_state"], "inaccessible")
        self.assertFalse(preview["commit_allowed"])

    def test_source_lock_sidecar_is_bounded_and_reports_drift(self):
        manifest = local_manifest(self.current)
        lock = {
            "version": 1,
            "source": source_identity("git", "owner/repo", revision="abc"),
            "content_hash": manifest["sha256"],
            "checked_at": "2026-09-20T00:00:00Z",
            "state": "known-unverified",
            "target": {"scope": "global", "physical_path": str(self.current), "contained": True},
        }
        write_source_lock(self.current, lock)
        self.assertEqual(read_source_lock(self.current)["content_hash"], manifest["sha256"])
        self.assertEqual(source_lock_status(self.current)["state"], "known-unverified")
        self._write(self.current, "references/old.md", "changed\n")
        self.assertEqual(source_lock_status(self.current)["state"], "changed")

    def test_review_commit_snapshot_and_explicit_rollback(self):
        target = {"scope": "global", "physical_path": str(self.current), "contained": True}
        source = source_identity("git", "owner/repo", revision="abc", digest="a" * 64)
        review = review_local_update(self.current, self.candidate, target=target, source=source)
        self.assertEqual(review["review_state"], "review-required")
        self.assertFalse(review["commit_allowed"])
        with self.assertRaises(SourceLockError):
            commit_local_update(self.current, self.candidate, target=target, review=review)
        result = commit_local_update(
            self.current,
            self.candidate,
            target=target,
            review=review,
            approve=True,
            snapshot_root=self.root / "snapshots",
            source=source,
        )
        self.assertTrue(result["committed"])
        self.assertTrue(result["rollback_available"])
        self.assertEqual(read_source_lock(self.current)["state"], "known-verified")
        self.assertEqual((self.current / "SKILL.md").read_text(encoding="utf-8"), (self.candidate / "SKILL.md").read_text(encoding="utf-8"))
        restored = restore_source_snapshot(self.current, result["snapshot"], approve=True)
        self.assertTrue(restored["restored"])
        self.assertEqual((self.current / "SKILL.md").read_text(encoding="utf-8"), "---\nname: demo\ndescription: Use demo when testing.\n---\nhello\n")

    def test_commit_rejects_stale_review_and_invalid_sidecar(self):
        target = {"physical_path": str(self.current), "contained": True}
        review = review_local_update(self.current, self.candidate, target=target)
        self._write(self.candidate, "references/new.md", "changed\n")
        with self.assertRaisesRegex(SourceLockError, "stale"):
            commit_local_update(
                self.current,
                self.candidate,
                target=target,
                review=review,
                approve=True,
                snapshot_root=self.root / "snapshots",
            )
        (self.current / ".skillsmgr-source-lock.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(SourceLockError):
            read_source_lock(self.current)


if __name__ == "__main__":
    unittest.main()
