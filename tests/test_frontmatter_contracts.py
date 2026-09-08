"""Contract tests for the stdlib frontmatter parser and dumper."""

import unittest

from skillsmgr.frontmatter import (
    FrontmatterError,
    MAX_COLLECTION_ITEMS,
    MAX_DOCUMENT_CHARS,
    MAX_KEYS,
    MAX_NESTING_DEPTH,
    MAX_SCALAR_LENGTH,
    dump_frontmatter,
    parse_frontmatter,
)


class FrontmatterRoundTripTests(unittest.TestCase):
    def test_valid_agent_skills_frontmatter_round_trips_with_body(self):
        source = (
            "---\n"
            "name: review-code\n"
            "description: Use this skill when reviewing code changes.\n"
            "license: MIT\n"
            "compatibility: Requires Python 3.10 and git.\n"
            "version: 1.2.3\n"
            "allowed-tools: git diff, git status\n"
            "---\n"
            "# Review\n\nCheck the changed files.\n"
        )
        expected = {
            "name": "review-code",
            "description": "Use this skill when reviewing code changes.",
            "license": "MIT",
            "compatibility": "Requires Python 3.10 and git.",
            "version": "1.2.3",
            "allowed-tools": "git diff, git status",
        }

        parsed, body = parse_frontmatter(source)
        dumped = dump_frontmatter(parsed) + body
        reparsed, reparsed_body = parse_frontmatter(dumped)

        self.assertEqual(parsed, expected)
        self.assertEqual(reparsed, expected)
        self.assertEqual(reparsed_body, body)

    def test_extension_metadata_round_trips_through_dump(self):
        source = (
            "---\n"
            "name: deploy\n"
            "description: Use this skill when deploying an application.\n"
            "metadata:\n"
            "  owner: platform\n"
            "  tags: [release, production]\n"
            "  policy:\n"
            "    approval: required\n"
            "    dry-run: false\n"
            "x-company:\n"
            "  channel: stable\n"
            "  flags:\n"
            "    - audited\n"
            "    - rollback\n"
            "---\n"
            "body\n"
        )

        parsed, body = parse_frontmatter(source)
        dumped = dump_frontmatter(parsed) + body
        reparsed, reparsed_body = parse_frontmatter(dumped)

        self.assertEqual(reparsed, parsed)
        self.assertEqual(reparsed_body, body)
        self.assertEqual(parsed["metadata"]["policy"]["dry-run"], False)
        self.assertEqual(parsed["x-company"]["flags"], ["audited", "rollback"])


class FrontmatterFailureContractTests(unittest.TestCase):
    def assert_frontmatter_error(self, text):
        """Require a bounded, public parser error rather than a raw failure."""
        try:
            parse_frontmatter(text)
        except FrontmatterError as exc:
            self.assertNotIsInstance(exc, RecursionError)
        except Exception as exc:  # pragma: no cover - gives a useful contract failure
            self.fail(f"expected FrontmatterError, got {type(exc).__name__}: {exc}")
        else:
            self.fail("expected FrontmatterError")

    def test_malformed_flow_collection_is_clean_error(self):
        self.assert_frontmatter_error("---\nitems: [one, two\n---\nbody\n")

    def test_malformed_block_mapping_is_clean_error(self):
        self.assert_frontmatter_error("---\nname: valid\n  unexpectedly-indented\n---\nbody\n")

    def test_document_limit_is_enforced(self):
        text = "x" * (MAX_DOCUMENT_CHARS + 1)
        self.assert_frontmatter_error(text)

    def test_key_limit_is_enforced(self):
        entries = "".join(f"key-{index}: value\n" for index in range(MAX_KEYS + 1))
        self.assert_frontmatter_error(f"---\n{entries}---\nbody\n")

    def test_collection_limit_is_enforced(self):
        values = ", ".join(f"item-{index}" for index in range(MAX_COLLECTION_ITEMS + 1))
        self.assert_frontmatter_error(f"---\nitems: [{values}]\n---\nbody\n")

    def test_scalar_limit_is_enforced(self):
        value = "x" * (MAX_SCALAR_LENGTH + 1)
        self.assert_frontmatter_error(f"---\ndescription: {value}\n---\nbody\n")

    def test_block_nesting_limit_is_enforced_without_recursion_error(self):
        lines = ["---"]
        for depth in range(MAX_NESTING_DEPTH + 2):
            lines.append("  " * depth + f"level-{depth}:")
        lines.extend(["  " * (MAX_NESTING_DEPTH + 2) + "leaf: value", "---", "body", ""])
        self.assert_frontmatter_error("\n".join(lines))

    def test_flow_nesting_limit_is_enforced_without_recursion_error(self):
        depth = MAX_NESTING_DEPTH + 1
        value = "[" * depth + "value" + "]" * depth
        self.assert_frontmatter_error(f"---\nvalue: {value}\n---\nbody\n")


if __name__ == "__main__":
    unittest.main()
