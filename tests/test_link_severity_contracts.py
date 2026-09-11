"""Issue #7 decision pins: out-of-root links warn, they do not fail validate.

The standing verdict (2026-09-10, recorded on the issue) REJECTS promoting the
out-of-root relative-link finding from warning to error. The reasons are
measured, not stylistic: a walk of live skill trees found 34-55 entirely
legitimate out-of-root references per root (sibling-skill and monorepo-relative
targets such as ``../postgresql/`` or
``../../../devops/ai/agent-observability/``), so a hard failure would break
working layouts, and the threat is already covered by ``risk_scan()`` findings
plus stage-only quarantine for untrusted imports.

These tests make the decision executable: they fail if a future edit promotes
the finding to an error, drops the warning, or loses the risk-scan signal that
replaced enforcement.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skillsmgr.frontmatter import dump_frontmatter
from skillsmgr.insights import risk_scan
from skillsmgr.validator import validate_skill


def write_skill(root: Path, name: str, body: str, *, description: str | None = None) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    front = {"name": name, "description": description or f"Use this when validating {name} links"}
    (skill_dir / "SKILL.md").write_text(dump_frontmatter(front) + body, encoding="utf-8")
    return skill_dir


class OutOfRootLinkSeverityPins(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def warnings_for(self, skill_dir: Path, fragment: str) -> list[str]:
        result = validate_skill(skill_dir.name, skill_dir)
        return [issue.message for issue in result.warnings if fragment in issue.message]

    def test_parent_escape_link_warns_and_stays_valid(self):
        skill_dir = write_skill(
            self.root, "deploy", "See [secrets](../../../etc/shadow) for details.\n"
        )
        result = validate_skill("deploy", skill_dir)
        self.assertTrue(
            result.valid,
            "out-of-root links must not fail validation (issue #7 verdict)",
        )
        self.assertEqual(result.errors, [])
        warnings = self.warnings_for(skill_dir, "escapes the skill directory")
        self.assertEqual(len(warnings), 1)
        self.assertIn("../../../etc/shadow", warnings[0])

    def test_absolute_path_link_warns_and_stays_valid(self):
        skill_dir = write_skill(self.root, "audit", "Read [passwd](/etc/passwd) first.\n")
        result = validate_skill("audit", skill_dir)
        self.assertTrue(result.valid)
        self.assertEqual(
            len(self.warnings_for(skill_dir, "escapes the skill directory")), 1
        )

    def test_legitimate_sibling_skill_link_still_warns_without_failing(self):
        """The measured false-positive shape: a monorepo/sibling-skill reference."""
        write_skill(self.root, "postgresql", "Use this when working with Postgres.\n")
        skill_dir = write_skill(
            self.root,
            "mysql",
            "Migrate with [postgresql](../postgresql/SKILL.md) in mind.\n",
        )
        result = validate_skill("mysql", skill_dir)
        self.assertTrue(result.valid)
        self.assertEqual(
            len(self.warnings_for(skill_dir, "escapes the skill directory")), 1
        )

    def test_in_root_missing_link_warns_separately(self):
        skill_dir = write_skill(self.root, "docs", "See [notes](references/notes.md).\n")
        result = validate_skill("docs", skill_dir)
        self.assertTrue(result.valid)
        self.assertEqual(
            len(self.warnings_for(skill_dir, "does not exist in the skill directory")), 1
        )
        self.assertEqual(self.warnings_for(skill_dir, "escapes the skill directory"), [])

    def test_external_and_anchor_links_stay_clean(self):
        skill_dir = write_skill(
            self.root,
            "clean",
            "See [docs](https://example.com/x), [mail](mailto:a@b.c), and [top](#heading).\n",
        )
        result = validate_skill("clean", skill_dir)
        self.assertTrue(result.valid)
        self.assertEqual(self.warnings_for(skill_dir, "escapes the skill directory"), [])
        self.assertEqual(self.warnings_for(skill_dir, "does not exist"), [])

    def test_risk_scan_carries_the_enforcement_signal(self):
        """What replaced enforcement: an explainable medium finding."""
        write_skill(
            self.root, "risky", "See [secrets](../../../etc/shadow) for details.\n"
        )
        record = {
            "name": "risky",
            "body": "See [secrets](../../../etc/shadow) for details.\n",
            "path": str(self.root / "risky"),
            "malformed": False,
        }
        findings = risk_scan(record)
        link_findings = [item for item in findings if item["kind"] == "link"]
        self.assertEqual(len(link_findings), 1)
        self.assertEqual(link_findings[0]["severity"], "medium")
        self.assertIn("../../../etc/shadow", link_findings[0]["evidence"])
        self.assertIn("escape the skill directory", link_findings[0]["why"])

    def test_promotion_regression_guard(self):
        """A promote-to-error edit would surface here, not in a user's repo."""
        skill_dir = write_skill(
            self.root, "guard", "See [secrets](../../../etc/shadow) and [x](/etc/passwd).\n"
        )
        result = validate_skill("guard", skill_dir)
        escaping = [
            issue for issue in result.issues
            if "escapes the skill directory" in issue.message
        ]
        self.assertEqual(len(escaping), 2)
        for issue in escaping:
            self.assertEqual(
                issue.level,
                "warning",
                "issue #7 verdict: out-of-root links warn; promotion needs a new "
                "maintainer decision (and an allowlist key) first",
            )
        self.assertTrue(result.valid)


if __name__ == "__main__":
    unittest.main()
