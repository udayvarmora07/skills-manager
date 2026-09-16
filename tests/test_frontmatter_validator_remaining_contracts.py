"""Red-first regressions for the remaining FM-13 and FM-15..FM-19 findings."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skillsmgr.frontmatter import MAX_NESTING_DEPTH, dump_frontmatter, parse_frontmatter
from skillsmgr.templates import TEMPLATE_NAME_RE, template_path
from skillsmgr.validator import validate_skill_name, validate_text


class RemainingFrontmatterValidatorTests(unittest.TestCase):
    def test_fm20_dump_rejects_deep_programmatic_mappings_and_lists_cleanly(self):
        for container in (dict, list):
            value = "leaf"
            for _ in range(2000):
                value = {"next": value} if container is dict else [value]

            with self.subTest(container=container.__name__):
                with self.assertRaisesRegex(TypeError, str(MAX_NESTING_DEPTH)):
                    dump_frontmatter({"value": value})

    def test_fm21_template_path_uses_the_canonical_name_bounds_and_devices(self):
        templates_dir = Path("/tmp/templates")

        self.assertEqual(template_path(templates_dir, "review-code"), templates_dir / "review-code.md")
        self.assertEqual(TEMPLATE_NAME_RE.pattern, r"^[a-z0-9]+(-[a-z0-9]+)*$")

        with self.assertRaises(ValueError):
            template_path(templates_dir, "a" * 65)
        with self.assertRaisesRegex(ValueError, "reserved Windows device"):
            template_path(templates_dir, "con")

    def test_fm13_preserves_line_breaks_around_more_indented_folded_lines(self):
        source = (
            "---\n"
            "description: >\n"
            "  a\n"
            "    indented\n"
            "  b\n"
            "---\n"
        )

        parsed, _ = parse_frontmatter(source)

        self.assertEqual(parsed["description"], "a\n  indented\nb\n")

    def test_fm15_rejects_windows_reserved_device_names(self):
        for name in ("con", "nul", "aux", "prn", "com1", "com9", "lpt1", "lpt9"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "reserved Windows device"):
                    validate_skill_name(name)

    def test_fm16_nul_in_link_and_layout_mentions_is_a_validation_warning(self):
        text = (
            dump_frontmatter(
                {
                    "name": "demo",
                    "description": "Use this skill when checking links.",
                }
            )
            + "See [a](scripts/run.py\x00) and read references/api.py\x00.\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            result = validate_text(text, skill_dir=Path(tmp))

        messages = [issue.message for issue in result.warnings]
        self.assertTrue(
            any("cannot be resolved" in message for message in messages),
            messages,
        )

    def test_fm17_validates_frontmatter_name_without_a_caller_name(self):
        text = dump_frontmatter(
            {
                "name": "../evil",
                "description": "Use this skill when checking names.",
            }
        )

        result = validate_text(text)

        self.assertTrue(
            any(
                issue.key == "name"
                and "name must match lowercase pattern" in issue.message
                for issue in result.errors
            ),
            [issue.message for issue in result.issues],
        )

    def test_fm18_accepts_should_be_used_when_use_context(self):
        text = dump_frontmatter(
            {
                "name": "review-code",
                "description": "This skill should be used when reviewing code.",
            }
        )

        result = validate_text(text)

        self.assertFalse(
            any("use-context" in issue.message for issue in result.warnings),
            [issue.message for issue in result.issues],
        )

    def test_fm19_existing_link_and_layout_targets_ignore_reference_suffixes(self):
        frontmatter = dump_frontmatter(
            {
                "name": "demo",
                "description": "Use this skill when checking references.",
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "demo"
            (skill_dir / "scripts").mkdir(parents=True)
            (skill_dir / "references").mkdir()
            (skill_dir / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
            (skill_dir / "references" / "guide name.md").write_text(
                "# Guide\n", encoding="utf-8"
            )
            body = (
                "Links: [fragment](scripts/run.py#main), "
                "[query](scripts/run.py?raw=1), "
                "[encoded](references/guide%20name.md), "
                "[punctuated](scripts/run.py.).\n"
                "Read scripts/run.py#main, scripts/run.py?raw=1, "
                "references/guide%20name.md, and scripts/run.py.\n"
            )

            result = validate_text(frontmatter + body, skill_dir=skill_dir)

        self.assertEqual(result.warnings, [], [issue.message for issue in result.issues])

    def test_fm19_decoding_preserves_relative_escape_detection(self):
        text = dump_frontmatter(
            {
                "name": "demo",
                "description": "Use this skill when checking references.",
            }
        ) + "See [outside](%2e%2e/secret.md#top).\n"

        with tempfile.TemporaryDirectory() as tmp:
            result = validate_text(text, skill_dir=Path(tmp) / "demo")

        self.assertTrue(
            any("escapes the skill directory" in issue.message for issue in result.warnings),
            [issue.message for issue in result.issues],
        )
        self.assertFalse(
            any("does not exist" in issue.message for issue in result.warnings),
            [issue.message for issue in result.issues],
        )


if __name__ == "__main__":
    unittest.main()
