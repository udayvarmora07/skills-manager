"""Silent-failure warnings for frontmatter an agent's YAML parser would drop.

Agents parse SKILL.md frontmatter with a strict YAML parser.  An empty block
or an unquoted ``: `` inside a plain scalar makes that parser reject the whole
block, so the skill loads with no name or description and is silently
ignored.  These are advisory findings only: ``valid`` is decided by errors.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skillsmgr.validator import validate_skill

EMPTY_FRAGMENT = "frontmatter block is present but empty"
COLON_FRAGMENT = "value contains an unquoted ': '"
BODY = "# Instructions\n\nFollow these steps.\n"


class SilentFrontmatterFailureTests(unittest.TestCase):
    def _validate(self, frontmatter: str, body: str = BODY):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "demo"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(frontmatter + body, encoding="utf-8")
            return validate_skill("demo", skill_dir)

    @staticmethod
    def _empty_warnings(result):
        return [i for i in result.warnings if EMPTY_FRAGMENT in i.message]

    @staticmethod
    def _colon_warnings(result):
        return [i for i in result.warnings if COLON_FRAGMENT in i.message]

    def test_empty_block_warns_once(self):
        result = self._validate("---\n---\n")
        warnings = self._empty_warnings(result)
        self.assertEqual(len(warnings), 1, [i.message for i in result.issues])
        self.assertEqual(warnings[0].level, "warning")
        self.assertEqual(warnings[0].key, "frontmatter")

    def test_comment_only_block_warns(self):
        result = self._validate("---\n# notes for a future human\n\n---\n")
        self.assertEqual(len(self._empty_warnings(result)), 1)

    def test_normal_frontmatter_has_no_silent_failure_warning(self):
        result = self._validate(
            "---\nname: demo\n"
            "description: Use this when checking silent failures.\n---\n"
        )
        self.assertEqual(self._empty_warnings(result), [])
        self.assertEqual(self._colon_warnings(result), [])

    def test_unquoted_colon_space_in_plain_scalar_warns(self):
        result = self._validate(
            "---\nname: demo\ndescription: Use when: the user asks\n---\n"
        )
        warnings = self._colon_warnings(result)
        self.assertEqual(len(warnings), 1, [i.message for i in result.issues])
        self.assertEqual(warnings[0].key, "description")
        self.assertNotIn("the user asks", warnings[0].message)

    def test_quoted_value_does_not_warn(self):
        result = self._validate(
            '---\nname: demo\ndescription: "Use when: the user asks"\n---\n'
        )
        self.assertEqual(self._colon_warnings(result), [])

    def test_url_in_value_does_not_warn(self):
        result = self._validate(
            "---\nname: demo\n"
            "description: see https://example.com for details\n---\n"
        )
        self.assertEqual(self._colon_warnings(result), [])

    def test_comment_after_value_does_not_warn(self):
        result = self._validate(
            "---\nname: demo\ndescription: a # note: b\n---\n"
        )
        self.assertEqual(self._colon_warnings(result), [])

    def test_block_scalar_does_not_warn(self):
        result = self._validate(
            "---\nname: demo\ndescription: |\n  Use when: the user asks\n---\n"
        )
        self.assertEqual(self._colon_warnings(result), [])

    def test_repeated_colons_warn_once_per_key(self):
        result = self._validate(
            "---\nname: demo\ndescription: first: second: third\n---\n"
        )
        self.assertEqual(len(self._colon_warnings(result)), 1)

    def test_warning_only_cases_stay_valid(self):
        for frontmatter in (
            "---\nname: demo\ndescription: Use when: the user asks\n---\n",
            '---\nname: demo\ndescription: "Use when: the user asks"\n---\n',
            "---\nname: demo\ndescription: |\n  Use when: the user asks\n---\n",
        ):
            with self.subTest(frontmatter=frontmatter):
                result = self._validate(frontmatter)
                self.assertTrue(
                    result.valid, [i.message for i in result.errors]
                )

    def test_malformed_frontmatter_does_not_raise_or_warn(self):
        result = self._validate("---\nname: demo\n")  # missing closing marker
        self.assertFalse(result.valid)
        self.assertFalse(
            any(EMPTY_FRAGMENT in i.message or COLON_FRAGMENT in i.message
                for i in result.issues)
        )


if __name__ == "__main__":
    unittest.main()


BOM_FRAGMENT = "starts with a UTF-8 byte-order mark"


class ByteOrderMarkTests(unittest.TestCase):
    """openai/codex#13918: a BOM before ``---`` makes Codex skip the skill.

    This tool's own parser strips the mark, so without a warning the skill
    looks valid here while one agent silently never lists it.
    """

    def _warnings(self, raw: bytes):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "demo"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_bytes(raw)
            result = validate_skill("demo", skill_dir)
        return result, [i for i in result.warnings if BOM_FRAGMENT in i.message]

    DOC = "---\nname: demo\ndescription: Use when testing the byte order mark lint.\n---\nBody\n"

    def test_bom_before_frontmatter_warns_once_and_stays_valid(self):
        result, warnings = self._warnings(b"\xef\xbb\xbf" + self.DOC.encode())
        self.assertTrue(result.valid)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].key, "frontmatter")
        self.assertIn("Codex", warnings[0].message)

    def test_no_bom_no_warning(self):
        _result, warnings = self._warnings(self.DOC.encode())
        self.assertEqual(warnings, [])

    def test_bom_with_crlf_line_endings_still_warns(self):
        _result, warnings = self._warnings(b"\xef\xbb\xbf" + self.DOC.replace("\n", "\r\n").encode())
        self.assertEqual(len(warnings), 1)

    def test_bom_without_a_frontmatter_block_adds_nothing_new(self):
        _result, warnings = self._warnings(b"\xef\xbb\xbf# Just a body\n")
        self.assertEqual(warnings, [])
