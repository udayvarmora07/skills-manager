"""Contract checks for the opt-in skills-manager management skill example."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import cli


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples/skills-manager-management/SKILL.md"


class ManagementSkillExampleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.data = self.root / "data"
        self.env = mock.patch.dict(os.environ, {
            "HOME": str(self.home),
            "SKILLS_MANAGER_DATA": str(self.data),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def invoke(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", str(self.data), *argv])
        return code, out.getvalue(), err.getvalue()

    @staticmethod
    def write_skill(path: Path, name: str, body: str = "stable body"):
        path.mkdir(parents=True, exist_ok=True)
        (path / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Test {name}\n---\n{body}\n",
            encoding="utf-8",
        )

    def skill_snapshot(self, *roots: Path):
        return {
            str(path): path.read_bytes()
            for root in roots
            if root.exists()
            for path in sorted(root.rglob("SKILL.md"))
            if path.is_file()
        }

    def test_documented_inventory_validate_explain_and_install_dry_run_are_safe(self):
        self.assertEqual(self.invoke(["init", "--json"])[0], cli.EXIT_OK)
        observed = self.home / ".agents/skills/group/observed-skill"
        self.write_skill(observed, "observed-skill")
        before = self.skill_snapshot(self.data / "skills", self.home / ".agents/skills")

        code, out, err = self.invoke(["list", "--scope", "all", "--json"])
        self.assertEqual((code, err), (cli.EXIT_OK, ""))
        self.assertTrue(any(row["name"] == "observed-skill" for row in json.loads(out)))

        code, out, err = self.invoke(["validate", "--path", str(observed), "--json"])
        self.assertEqual((code, err), (cli.EXIT_OK, ""))
        self.assertTrue(json.loads(out)["valid"])

        code, out, err = self.invoke(["doctor", "--scope", "all", "--hygiene", "--json"])
        self.assertEqual((code, err), (cli.EXIT_OK, ""))
        report = json.loads(out)
        self.assertIn("hygiene", report)

        code, out, err = self.invoke([
            "doctor", "--explain", "cursor", "--project", str(self.home),
            "--skill", "observed-skill", "--json",
        ])
        self.assertEqual((code, err), (cli.EXIT_OK, ""))
        self.assertIn("resolution", json.loads(out))

        with mock.patch("skillsmgr.cli_handlers.subprocess.run") as runner:
            code, out, err = self.invoke([
                "install", "owner/repo", "--scope", "global", "--dry-run", "--json",
            ])
        self.assertEqual((code, err), (cli.EXIT_OK, ""))
        self.assertFalse(json.loads(out)["executed"])
        runner.assert_not_called()
        self.assertEqual(
            self.skill_snapshot(self.data / "skills", self.home / ".agents/skills"),
            before,
        )

    def test_update_preview_is_non_mutating_and_stale_or_ambiguous_reviews_fail_closed(self):
        self.assertEqual(self.invoke(["init", "--json"])[0], cli.EXIT_OK)
        target = self.home / ".agents/skills/demo"
        candidate = self.root / "candidate"
        self.write_skill(target, "demo", "target version")
        self.write_skill(candidate, "demo", "candidate version")
        before = self.skill_snapshot(target, candidate)

        code, out, err = self.invoke([
            "update", "preview", "demo", "--from", str(candidate),
            "--scope", "agents", "--target-path", str(target), "--json",
        ])
        self.assertEqual((code, err), (cli.EXIT_OK, ""))
        review = json.loads(out)
        self.assertEqual(review["review_state"], "pending")
        self.assertFalse(review["commit_allowed"])
        self.assertEqual(self.skill_snapshot(target, candidate), before)

        changed_target = "---\nname: demo\ndescription: Test demo\n---\nchanged after preview\n"
        (target / "SKILL.md").write_text(changed_target, encoding="utf-8")
        code, out, err = self.invoke([
            "update", "apply", "demo", review["review_id"], "--scope", "agents",
            "--target-path", str(target), "--yes", "--json",
        ])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("target changed after review", err.lower())
        self.assertNotIn("Traceback", err)
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), changed_target)

        code, _, err = self.invoke([
            "update", "preview", "demo", "--from", str(candidate),
            "--scope", "future-scope", "--json",
        ])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("target-not-found", err.lower())
        self.assertNotIn("Traceback", err)

        code, _, err = self.invoke([
            "update", "preview", "missing", "--from", str(candidate),
            "--scope", "agents", "--json",
        ])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertNotIn("Traceback", err)

        first = self.home / ".agents/skills/one/duplicate"
        second = self.home / ".agents/skills/two/duplicate"
        self.write_skill(first, "duplicate", "first body")
        self.write_skill(second, "duplicate", "different body")
        code, _, err = self.invoke([
            "update", "preview", "duplicate", "--from", str(candidate),
            "--scope", "agents", "--json",
        ])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("target_path is required", err)
        self.assertNotIn("Traceback", err)

        with mock.patch("skillsmgr.scopes.scan_scope", side_effect=OSError("root unavailable")):
            code, _, err = self.invoke([
                "update", "preview", "demo", "--from", str(candidate),
                "--scope", "agents", "--json",
            ])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertNotIn("Traceback", err)
        reviews = self.data / "source-update-reviews"
        self.assertFalse(reviews.exists() and any(reviews.iterdir()))

    def test_skill_documents_explicit_evidence_and_human_write_boundaries(self):
        text = EXAMPLE.read_text(encoding="utf-8")
        for required in (
            "docs/03-cli-surface.md",
            "effective_state` is `unresolved",
            "undocumented-precedence",
            "degraded",
            "--dry-run",
            "--target-path",
            "Never apply a preview",
            "sync` has no dry-run flag",
            "Manual opt-in installation",
            "rmdir",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertNotIn("skills-mgr sync --dry-run", text)
        self.assertNotIn("--apply", text)


if __name__ == "__main__":
    unittest.main()
