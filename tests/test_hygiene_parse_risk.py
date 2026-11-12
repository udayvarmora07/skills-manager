"""Silent agent-parse warnings reach the hygiene report (Doctor and Quality).

The validator already warns about frontmatter an agent's parser drops (an
empty block, an unquoted ``: ``, a byte-order mark before ``---``), but the
hygiene report surfaced only validator errors, so Quality never showed them.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skillsmgr import hygiene, loader

GOOD = "---\nname: {n}\ndescription: Use when testing the parse risk finding in hygiene reports.\n---\nBody {n}\n"


class ParseRiskFindingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()

    def skill(self, name: str, raw: bytes) -> None:
        (self.root / name).mkdir()
        (self.root / name / "SKILL.md").write_bytes(raw)

    def findings(self):
        records = loader.scan_dir(self.root, annotate_paths=True)
        for record in records:
            record["scope"] = "codex"
        report = hygiene.hygiene_report(records, scope="codex", home=self.root)
        return [f for f in report["findings"] if f["category"] == "agent-parse-risk"]

    def test_bom_and_unquoted_colon_each_become_one_warning(self):
        self.skill("bommed", b"\xef\xbb\xbf" + GOOD.format(n="bommed").encode())
        self.skill("colon", b"---\nname: colon\ndescription: Use when: testing the parse risk finding here.\n---\nB\n")
        self.skill("clean", GOOD.format(n="clean").encode())
        found = self.findings()
        self.assertEqual(sorted(f["instances"][0]["name"] for f in found), ["bommed", "colon"])
        for finding in found:
            self.assertEqual(finding["severity"], "warning")
            self.assertTrue(finding["evidence"]["issues"])
        bom = next(f for f in found if f["instances"][0]["name"] == "bommed")
        self.assertIn("byte-order mark", bom["evidence"]["issues"][0]["message"])

    def test_clean_library_has_none(self):
        self.skill("clean", GOOD.format(n="clean").encode())
        self.assertEqual(self.findings(), [])


if __name__ == "__main__":
    unittest.main()
