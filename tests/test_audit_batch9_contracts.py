"""Red-first regressions for the next audit findings: SEC-19 and FM-19."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skillsmgr.frontmatter import dump_frontmatter
from skillsmgr.validator import validate_skill


class ValidatorReferenceNormalizationTests(unittest.TestCase):
    """FM-19: URL decorations and prose punctuation must not create warnings."""

    def test_fm19_existing_references_with_fragments_queries_encoding_and_punctuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "reference-check"
            (skill_dir / "scripts").mkdir(parents=True)
            (skill_dir / "references").mkdir()
            (skill_dir / "assets").mkdir()
            (skill_dir / "scripts" / "run task.py").write_text("run", encoding="utf-8")
            (skill_dir / "references" / "api.md").write_text("api", encoding="utf-8")
            (skill_dir / "assets" / "data.json").write_text("{}", encoding="utf-8")
            body = (
                "See [fragment](scripts/run%20task.py#main), "
                "[query](scripts/run%20task.py?raw=1), and "
                "[sentence](scripts/run%20task.py.).\n"
                "Also read scripts/run%20task.py#main, "
                "references/api.md?raw=1, and assets/data.json.\n"
            )
            document = dump_frontmatter(
                {
                    "name": "reference-check",
                    "description": "Use this skill when checking references.",
                }
            ) + body
            (skill_dir / "SKILL.md").write_text(document, encoding="utf-8")

            result = validate_skill("reference-check", skill_dir)

        self.assertEqual(
            [issue.message for issue in result.warnings if "does not exist" in issue.message],
            [],
        )


if __name__ == "__main__":
    unittest.main()
