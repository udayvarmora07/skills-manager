"""Contracts for read-only evidence from ``skills`` CLI lockfiles."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import hygiene, lockfiles


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def _tree_hash(path: Path) -> str:
    return lockfiles.skill_folder_tree_sha(path)


class SanitizeNameTests(unittest.TestCase):
    def test_matches_upstream_sanitisation(self):
        cases = {
            "My Skill": "my-skill",
            "../evil": "evil",
            "...": "unnamed-skill",
            "": "unnamed-skill",
            "Foo__Bar.Baz!!": "foo__bar.baz",
            "--abc--": "abc",
            "ümlaut": "mlaut",
        }
        for raw, expected in cases.items():
            self.assertEqual(lockfiles.sanitize_name(raw), expected, raw)

    def test_truncates_to_255_characters(self):
        self.assertEqual(len(lockfiles.sanitize_name("a" * 300)), 255)


class ReadLockTests(unittest.TestCase):
    def _lock(self, root: Path, payload) -> Path:
        path = root / "lock.json"
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_missing_lock_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = lockfiles.read_lock(Path(tmp) / "absent.json", kind="global")
            self.assertEqual(result["state"], "missing")
            self.assertEqual(result["entries"], [])

    def test_invalid_json_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = lockfiles.read_lock(self._lock(Path(tmp), "{not json"), kind="global")
            self.assertEqual(result["state"], "invalid")
            self.assertTrue(result["reason"])

    def test_wrong_version_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._lock(Path(tmp), {"version": 2, "skills": {}})
            result = lockfiles.read_lock(path)
            self.assertEqual(result["state"], "invalid")
            self.assertIn("version", result["reason"])

    def test_a_project_lock_cannot_claim_to_be_global(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._lock(Path(tmp), {"version": 1, "skills": {}})
            self.assertEqual(lockfiles.read_lock(path, kind="global")["state"], "invalid")
            self.assertEqual(lockfiles.read_lock(path, kind="project")["state"], "ok")

    def test_an_oversize_lock_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lock.json"
            path.write_text(" " * (lockfiles.MAX_LOCK_BYTES + 1), encoding="utf-8")
            result = lockfiles.read_lock(path, kind="global")
            self.assertEqual(result["state"], "invalid")
            self.assertIn("exceeds", result["reason"])

    def test_a_non_dict_entry_invalidates_the_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._lock(Path(tmp), {"version": 3, "skills": {"a": ["nope"]}})
            result = lockfiles.read_lock(path, kind="global")
            self.assertEqual(result["state"], "invalid")
            self.assertIn("a", result["reason"])

    def test_entries_are_bounded_with_an_omitted_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = {f"skill-{i:04d}": {"source": "o/r"} for i in range(501)}
            path = self._lock(Path(tmp), {"version": 3, "skills": skills})
            result = lockfiles.read_lock(path, kind="global")
            self.assertEqual(result["state"], "ok")
            self.assertEqual(len(result["entries"]), 500)
            self.assertEqual(result["omitted"], 1)
            self.assertEqual(result["total_entries"], 501)


class HashTests(unittest.TestCase):
    def test_computed_hash_matches_a_hand_computation_for_ascii_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "a.txt", b"one")
            _write(root / "b" / "c.txt", b"two")
            expected = hashlib.sha256(b"a.txt" + b"one" + b"b/c.txt" + b"two").hexdigest()
            self.assertEqual(lockfiles.computed_folder_hash(root, "codepoint"), expected)

    def test_casefold_order_differs_from_codepoint_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "B.txt", b"bee")
            _write(root / "a.txt", b"aye")
            codepoint = hashlib.sha256(b"B.txt" + b"bee" + b"a.txt" + b"aye").hexdigest()
            casefold = hashlib.sha256(b"a.txt" + b"aye" + b"B.txt" + b"bee").hexdigest()
            self.assertEqual(lockfiles.computed_folder_hash(root, "codepoint"), codepoint)
            self.assertEqual(lockfiles.computed_folder_hash(root, "casefold"), casefold)
            self.assertNotEqual(codepoint, casefold)

    def test_computed_hash_skips_git_and_node_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "a.txt", b"one")
            _write(root / ".git" / "config", b"ignored")
            _write(root / "node_modules" / "pkg" / "index.js", b"ignored")
            expected = hashlib.sha256(b"a.txt" + b"one").hexdigest()
            self.assertEqual(lockfiles.computed_folder_hash(root, "codepoint"), expected)

    @unittest.skipUnless(shutil.which("git"), "git is not available")
    def test_tree_sha_matches_real_git_for_nested_exec_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "SKILL.md", b"---\nname: demo\n---\nbody\n")
            _write(root / "nested" / "deep" / "file.txt", b"deep\n")
            _write(root / "run.sh", b"#!/bin/sh\nexit 0\n")
            (root / "run.sh").chmod(0o755)
            os.symlink("SKILL.md", root / "link.md")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            expected = subprocess.run(
                ["git", "-C", str(root), "write-tree"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(lockfiles.skill_folder_tree_sha(root), expected)

    def test_an_oversize_folder_is_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "a.txt", b"x")
            with mock.patch.object(lockfiles, "MAX_HASH_FILES", 0):
                with self.assertRaises(lockfiles.LockfileTooLarge):
                    lockfiles.computed_folder_hash(root, "codepoint")


class EvidenceTests(unittest.TestCase):
    def _home(self, root: Path) -> Path:
        home = root / "home"
        (home / ".agents" / "skills").mkdir(parents=True)
        return home

    def _global_lock(self, home: Path, skills: dict) -> None:
        _write(
            home / ".agents" / ".skill-lock.json",
            json.dumps({"version": 3, "skills": skills}),
        )

    def test_missing_install_and_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            self._global_lock(home, {"one": {"source": "o/r", "skillFolderHash": "deadbeef"}})
            evidence = lockfiles.lockfile_evidence(home)
            row = evidence["global"]["entries"][0]
            self.assertFalse(row["present"])
            self.assertEqual(row["hash_status"], "missing")
            self.assertEqual(evidence["summary"]["declared"], 1)
            self.assertEqual(evidence["summary"]["missing"], 1)
            self.assertEqual(evidence["summary"]["match"], 0)

    def test_present_disabled_and_matching_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            skill = home / ".agents" / "skills" / "one"
            _write(skill / "SKILL.md.disabled", b"---\nname: one\n---\n")
            self._global_lock(
                home,
                {"one": {"source": "o/r", "skillFolderHash": _tree_hash(skill)}},
            )
            row = lockfiles.lockfile_evidence(home)["global"]["entries"][0]
            self.assertTrue(row["present"])
            self.assertTrue(row["disabled"])
            self.assertEqual(row["hash_status"], "match")

    def test_changed_tree_is_reported_as_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            skill = home / ".agents" / "skills" / "one"
            _write(skill / "SKILL.md", b"# local\n")
            self._global_lock(
                home,
                {"one": {"source": "o/r", "skillFolderHash": "0" * 40}},
            )
            row = lockfiles.lockfile_evidence(home)["global"]["entries"][0]
            self.assertEqual(row["hash_status"], "differs_from_recorded_tree")
            self.assertIn("recorded upstream tree", row["hash_reason"])

    def test_an_empty_recorded_hash_is_not_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            skill = home / ".agents" / "skills" / "one"
            _write(skill / "SKILL.md", b"# x\n")
            self._global_lock(home, {"one": {"source": "local", "skillFolderHash": ""}})
            row = lockfiles.lockfile_evidence(home)["global"]["entries"][0]
            self.assertEqual(row["hash_status"], "not_recorded")

    def test_a_symlinked_skill_directory_is_unverifiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            target = Path(tmp) / "elsewhere"
            _write(target / "SKILL.md", b"# x\n")
            os.symlink(target, home / ".agents" / "skills" / "one")
            self._global_lock(
                home,
                {"one": {"source": "o/r", "skillFolderHash": _tree_hash(target)}},
            )
            row = lockfiles.lockfile_evidence(home)["global"]["entries"][0]
            self.assertEqual(row["hash_status"], "unverifiable")
            self.assertEqual(row["hash_reason"], "symlinked directory")

    def test_undeclared_installed_skills_are_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            declared = home / ".agents" / "skills" / "one"
            _write(declared / "SKILL.md", b"# x\n")
            _write(home / ".agents" / "skills" / "extra" / "SKILL.md", b"# y\n")
            self._global_lock(
                home,
                {"one": {"source": "o/r", "skillFolderHash": _tree_hash(declared)}},
            )
            undeclared = lockfiles.lockfile_evidence(home)["undeclared"]
            self.assertEqual(undeclared["names"], ["extra"])

    def test_source_url_credentials_are_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            self._global_lock(
                home,
                {
                    "one": {
                        "source": "o/r",
                        "sourceType": "github",
                        "sourceUrl": "https://user:tok@host/x?a=b",
                        "skillFolderHash": "",
                    }
                },
            )
            source = lockfiles.lockfile_evidence(home)["global"]["entries"][0]["source"]
            self.assertEqual(source["label"], "https://host/x")
            self.assertEqual(lockfiles.safe_source_url("https://user:tok@host/x?a=b"), "https://host/x")

    def test_project_lock_accepts_the_casefold_ordering(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            skill = project / ".agents" / "skills" / "one"
            _write(skill / "B.txt", b"bee")
            _write(skill / "a.txt", b"aye")
            recorded = lockfiles.computed_folder_hash(skill, "casefold")
            _write(
                project / "skills-lock.json",
                json.dumps({
                    "version": 1,
                    "skills": {
                        "one": {
                            "source": "o/r",
                            "sourceType": "github",
                            "computedHash": recorded,
                        }
                    },
                }),
            )
            evidence = lockfiles.lockfile_evidence(Path(tmp) / "home", project_root=project)
            row = evidence["project"]["entries"][0]
            self.assertEqual(row["hash_status"], "match")
            self.assertEqual(evidence["project"]["state"], "ok")

    def test_project_lock_is_unavailable_without_a_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            evidence = lockfiles.lockfile_evidence(home)
            self.assertEqual(evidence["project"]["state"], "unavailable")
            self.assertIn("project root", evidence["project"]["reason"])

    def test_an_apm_lock_is_an_unavailable_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "apm.lock.yaml").write_text("version: 1\n", encoding="utf-8")
            evidence = lockfiles.lockfile_evidence(Path(tmp) / "home", project_root=project)
            signals = {item["signal"]: item for item in evidence["unavailable_signals"]}
            self.assertIn("apm-lock", signals)
            self.assertIn("standard library", signals["apm-lock"]["explanation"])

    def test_a_folder_over_the_hash_budget_is_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            skill = home / ".agents" / "skills" / "one"
            _write(skill / "SKILL.md", b"# x\n")
            self._global_lock(home, {"one": {"source": "o/r", "skillFolderHash": "abc"}})
            with mock.patch.object(lockfiles, "MAX_HASH_FILES", 0):
                evidence = lockfiles.lockfile_evidence(home)
            self.assertEqual(evidence["global"]["entries"][0]["hash_status"], "too_large")
            self.assertEqual(evidence["summary"]["too_large"], 1)

    def test_a_corrupt_lock_is_invalid_and_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            _write(home / ".agents" / ".skill-lock.json", "{bad")
            evidence = lockfiles.lockfile_evidence(home)
            self.assertEqual(evidence["global"]["state"], "invalid")
            self.assertEqual(evidence["summary"]["declared"], 0)


class DisabledAndUnreadableTests(unittest.TestCase):
    """Two sources of false 'differs' found against a real 131-entry lock."""

    def _home(self, root: Path) -> Path:
        home = root / "home"
        (home / ".agents" / "skills").mkdir(parents=True)
        return home

    @unittest.skipUnless(shutil.which("git"), "git is not available")
    def test_a_skill_disabled_by_this_tool_still_matches_the_upstream_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            skill = home / ".agents" / "skills" / "one"
            _write(skill / "SKILL.md", b"---\nname: one\n---\nbody\n")
            _write(skill / "rules" / "a.md", b"rule\n")
            subprocess.run(["git", "init", "-q", str(skill)], check=True)
            subprocess.run(["git", "-C", str(skill), "add", "-A"], check=True)
            upstream = subprocess.run(["git", "-C", str(skill), "write-tree"],
                                      check=True, capture_output=True, text=True).stdout.strip()
            shutil.rmtree(skill / ".git")
            (skill / "SKILL.md").rename(skill / "SKILL.md.disabled")
            _write(home / ".agents" / ".skill-lock.json",
                   json.dumps({"version": 3, "skills": {"one": {"source": "o/r", "skillFolderHash": upstream}}}))
            row = lockfiles.lockfile_evidence(home)["global"]["entries"][0]
            self.assertTrue(row["disabled"])
            self.assertEqual(row["hash_status"], "match")
            self.assertIn("SKILL.md.disabled", row.get("hash_note") or row.get("reason") or json.dumps(row))

    def test_an_edited_disabled_skill_still_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            skill = home / ".agents" / "skills" / "one"
            _write(skill / "SKILL.md", b"original\n")
            recorded = lockfiles.skill_folder_tree_sha(skill)
            (skill / "SKILL.md").unlink()
            _write(skill / "SKILL.md.disabled", b"edited\n")
            _write(home / ".agents" / ".skill-lock.json",
                   json.dumps({"version": 3, "skills": {"one": {"source": "o/r", "skillFolderHash": recorded}}}))
            row = lockfiles.lockfile_evidence(home)["global"]["entries"][0]
            self.assertEqual(row["hash_status"], "differs_from_recorded_tree")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads everything")
    def test_an_unreadable_file_is_unverifiable_not_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(Path(tmp))
            skill = home / ".agents" / "skills" / "one"
            _write(skill / "SKILL.md", b"x\n")
            secret = skill / "private.md"
            _write(secret, b"y\n")
            _write(home / ".agents" / ".skill-lock.json",
                   json.dumps({"version": 3, "skills": {"one": {"source": "o/r", "skillFolderHash": "0" * 40}}}))
            secret.chmod(0)
            try:
                row = lockfiles.lockfile_evidence(home)["global"]["entries"][0]
            finally:
                secret.chmod(0o600)
            self.assertEqual(row["hash_status"], "unverifiable")


class HygieneIntegrationTests(unittest.TestCase):
    def test_the_report_contains_a_json_serializable_lockfiles_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            (home / ".agents" / "skills").mkdir(parents=True)
            _write(
                home / ".agents" / ".skill-lock.json",
                json.dumps({"version": 3, "skills": {"one": {"source": "o/r"}}}),
            )
            report = hygiene.hygiene_report([], scope="all", home=home)
            self.assertIn("lockfiles", report)
            self.assertEqual(report["lockfiles"]["global"]["state"], "ok")
            json.dumps(report)


if __name__ == "__main__":
    unittest.main()
