"""Hermetic DEL-09 dry-run and conflict-planning contracts."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from skillsmgr.backup_sync import (
    BackupSyncError,
    build_manifest,
    commit_sync_review,
    dry_run,
    git_fetch,
    git_remote_info,
    interrupted_sync,
    prepare_sync_review,
    read_sync_review,
    three_way_plan,
)
from skillsmgr.source_lock import local_manifest


class BackupSyncContracts(unittest.TestCase):
    def setUp(self):
        self.base = build_manifest({"demo": {"digest": "base", "metadata_digest": "meta"}}, source="local")
        self.local = build_manifest({"demo": {"digest": "mine", "metadata_digest": "meta"}, "local-only": "x"}, source="local")
        self.remote = build_manifest({"demo": {"digest": "theirs", "metadata_digest": "meta"}, "remote-only": "y"}, source="origin")

    def test_build_manifest_is_sorted_bounded_and_credential_free(self):
        manifest = build_manifest({"zeta": "z", "alpha": "a"}, source="git:origin")
        self.assertEqual(list(manifest["skills"]), ["alpha", "zeta"])
        self.assertTrue(manifest["credential_redacted"])
        with self.assertRaises(BackupSyncError):
            build_manifest({}, source="https://user:secret@example.invalid/repo")

    def test_dry_run_reports_exact_local_remote_and_conflicting_names(self):
        report = dry_run(self.local, self.remote, base=self.base)
        self.assertEqual(report["local_changes"], ["demo", "local-only"])
        self.assertEqual(report["remote_changes"], ["demo", "remote-only"])
        self.assertEqual(report["conflicts"], ["demo"])
        self.assertTrue(report["dry_run"])
        self.assertTrue(report["remote_delete_requires_explicit_recovery"])

    def test_three_way_strategies_never_choose_destructive_default(self):
        review = three_way_plan(self.base, self.local, self.remote)
        self.assertEqual(review["conflicts"], ["demo"])
        self.assertTrue(review["writes"] is False)
        self.assertEqual(three_way_plan(self.base, self.local, self.remote, strategy="keep-mine")["decisions"][0]["action"], "keep-mine")
        both = three_way_plan(self.base, self.local, self.remote, strategy="keep-both")
        conflict = next(item for item in both["decisions"] if item["name"] == "demo")
        self.assertEqual(conflict["result_names"], ["demo-local", "demo-remote"])

    def test_interrupted_operation_is_retryable_and_snapshot_visible(self):
        report = interrupted_sync(["demo"], ["remote-only"], "snapshot-1")
        self.assertTrue(report["retryable"])
        self.assertTrue(report["local_filesystem_valid"])
        self.assertEqual(report["snapshot"], "snapshot-1")

    def test_invalid_names_paths_and_strategies_fail_closed(self):
        with self.assertRaises(BackupSyncError):
            build_manifest({"../escape": "x"}, source="local")
        with self.assertRaises(BackupSyncError):
            build_manifest({"demo": {"digest": "x", "files": [{"path": "../escape", "digest": "x"}]}}, source="local")
        with self.assertRaises(BackupSyncError):
            three_way_plan(self.base, self.local, self.remote, strategy="overwrite")

    def test_git_metadata_and_fetch_delegate_auth_without_persisting_credentials(self):
        if shutil.which("git") is None:
            self.skipTest("Git is not installed")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote = root / "remote.git"
            repo = root / "repo"
            subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)

            def git(*args):
                return subprocess.run(
                    ["git", *args], cwd=repo, check=True, capture_output=True, text=True
                )

            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            (repo / "README").write_text("one\n", encoding="utf-8")
            git("add", "README")
            git("commit", "-qm", "initial")
            git("remote", "add", "origin", str(remote))
            git("push", "-q", "origin", "HEAD")
            info = git_remote_info(repo)
            fetched = git_fetch(repo)
            self.assertEqual(info["remote"], "origin")
            self.assertEqual(fetched["fetched_revision"], info["revision"])
            self.assertTrue(fetched["credential_redacted"])
            self.assertNotIn("secret", str(fetched))

    def test_review_apply_is_private_revalidated_snapshot_backed_and_single_use(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "current"
            candidate = root / "candidate"
            target.mkdir()
            candidate.mkdir()
            original = "---\nname: demo\ndescription: Demo skill.\n---\n# Original\n"
            updated = "---\nname: demo\ndescription: Demo skill.\n---\n# Updated\n"
            (target / "SKILL.md").write_text(original, encoding="utf-8")
            (candidate / "SKILL.md").write_text(updated, encoding="utf-8")
            review = prepare_sync_review(
                root,
                self.base,
                self.local,
                self.remote,
                target={"physical_path": str(target), "contained": True},
                candidate_hash=local_manifest(candidate)["sha256"],
                strategy="keep-mine",
                git={
                    "url": "https://example.invalid/skills.git",
                    "revision": "a" * 40,
                    "auth_delegation": "Git credential helper",
                    "credential_redacted": True,
                },
            )
            review_path = root / "sync-reviews" / f"{review['review_id']}.json"
            self.assertEqual((root / "sync-reviews").stat().st_mode & 0o777, 0o700)
            self.assertEqual(review_path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("secret", review_path.read_text(encoding="utf-8"))
            with self.assertRaises(BackupSyncError):
                commit_sync_review(root, review["review_id"], candidate, snapshot_root=root / "snapshots")
            result = commit_sync_review(
                root,
                review["review_id"],
                candidate,
                approve=True,
                snapshot_root=root / "snapshots",
            )
            self.assertTrue(result["committed"])
            self.assertIn("Updated", (target / "SKILL.md").read_text(encoding="utf-8"))
            self.assertTrue((target / ".skillsmgr-source-lock.json").is_file())
            self.assertTrue(Path(result["snapshot"]).is_dir())
            with self.assertRaisesRegex(BackupSyncError, "already been committed"):
                read_sync_review(root, review["review_id"])


if __name__ == "__main__":
    unittest.main()
