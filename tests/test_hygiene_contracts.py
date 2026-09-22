"""Contracts for the deterministic read-only Skill Hygiene Report."""

from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import hygiene


def _record(root: Path, name: str, *, scope: str = "global", body: str = "# Work\nDo the work.\n", description: str = "Use this skill when doing the work.") -> dict:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}",
        encoding="utf-8",
    )
    return {"name": name, "scope": scope, "scope_label": scope, "path": str(directory)}


class HygieneContracts(unittest.TestCase):
    def test_instruction_normalization_is_narrow(self):
        self.assertEqual(
            hygiene.normalize_instruction_body("\r\n  A  \r\n\r\nB\t \r\n"),
            "  A\n\nB\n",
        )
        self.assertEqual(hygiene.normalize_instruction_body("\n\r\n"), "")

    def test_aliases_collapse_but_recursive_same_name_paths_remain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _record(root, "same", scope="agents")
            alias = dict(first, scope="cursor", physical_path=str(root / "same"))
            second = _record(root / "nested", "same", scope="agents", body="# Work\nDifferent.\n")
            result = hygiene.hygiene_report([first, alias, second], scope="all")
            self.assertEqual(result["summary"]["observed_records"], 3)
            self.assertEqual(result["summary"]["physical_instances"], 2)
            self.assertEqual(result["summary"]["logical_names"], 1)
            categories = {finding["category"] for finding in result["findings"]}
            self.assertIn("divergent-name", categories)

    def test_exact_groups_are_distinct_and_stable_when_input_is_shuffled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one = _record(root, "one")
            two = _record(root, "two")
            three = _record(root, "three", body="# Other\nOther instructions.\n")
            # Make the first two complete documents equal, then make the body
            # of the third equal after narrow normalization only.
            (root / "two" / "SKILL.md").write_bytes((root / "one" / "SKILL.md").read_bytes())
            (root / "three" / "SKILL.md").write_text(
                "---\nname: three\ndescription: Use this skill when doing the work.\n---\n# Work  \r\nDo the work.\r\n",
                encoding="utf-8",
            )
            rows = [one, two, three]
            with mock.patch("skillsmgr.hygiene.source_lock.source_lock_status", return_value={"state": "missing"}):
                left = hygiene.hygiene_report(rows, scope="global")
                random.Random(4).shuffle(rows)
                right = hygiene.hygiene_report(rows, scope="global")
            self.assertEqual(left["findings"], right["findings"])
            categories = {finding["category"] for finding in left["findings"]}
            self.assertIn("exact-document-duplicate", categories)
            self.assertIn("exact-instruction-duplicate", categories)

    def test_reference_and_description_evidence_reuses_validator_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = _record(Path(tmp), "broken", description="Handles various things")
            validation = {
                "issues": [
                    {"level": "warning", "key": "body", "message": "link target `references/nope.md` does not exist in the skill directory"},
                    {"level": "warning", "key": "description", "message": "description contains vague filler 'various'"},
                ]
            }
            row["validation"] = validation
            result = hygiene.hygiene_report([row], scope="global")
            categories = {finding["category"] for finding in result["findings"]}
            self.assertIn("broken-reference", categories)
            self.assertIn("activation-description", categories)
            ref = next(item for item in result["findings"] if item["category"] == "broken-reference")
            self.assertEqual(ref["evidence"]["issues"][0]["message"], validation["issues"][0]["message"])

    def test_near_duplicate_is_bounded_and_deterministic(self):
        rows = [
            {"name": f"review-pr-{index}", "description": "Use this skill when reviewing pull requests and changes.", "body": f"# Review\nInspect changed files {index}."}
            for index in range(200)
        ]
        result = hygiene.near_duplicate_candidates(rows, max_pairs=17, max_results=3)
        self.assertLessEqual(result["candidate_pairs_scored"], 17)
        self.assertLessEqual(len(result["candidates"]), 3)
        self.assertTrue(result["candidate_pairs_truncated"])
        shuffled = list(rows)
        random.Random(9).shuffle(shuffled)
        other = hygiene.near_duplicate_candidates(shuffled, max_pairs=17, max_results=3)
        self.assertEqual(result, other)

    def test_source_lock_missing_is_unavailable_not_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = _record(Path(tmp), "local")
            with mock.patch("skillsmgr.hygiene.source_lock.source_lock_status", return_value={"state": "missing"}):
                result = hygiene.hygiene_report([row], scope="global")
            self.assertFalse(any(item["category"].startswith("source-lock") for item in result["findings"]))
            self.assertTrue(any(item["signal"] == "source-lock" for item in result["unavailable_signals"]))

    def test_report_does_not_mutate_input(self):
        rows = [{"name": "x", "scope": "global", "body": "body", "content_hash": "x", "path": "/missing"}]
        before = [dict(row) for row in rows]
        with mock.patch("skillsmgr.hygiene.source_lock.source_lock_status", return_value={"state": "missing"}):
            hygiene.hygiene_report(rows, scope="global")
        self.assertEqual(rows, before)


if __name__ == "__main__":
    unittest.main()
