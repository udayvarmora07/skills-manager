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

    def test_flow_list_scalars_with_commas_quotes_and_brackets_round_trip(self):
        # dump_frontmatter must never emit a flow list that its own parser
        # rejects: scalar items containing commas, quotes, or brackets need
        # quoting inside "[...]" (loop regression found by fuzzing).
        tricky = [
            "5,,CPKCxrr'JKqeJFEQi^ (7\\OPu h,.,;/:nd*Vg/*",
            "a[b]c",
            'say "hi"',
            "trail,",
            ",lead",
            "x#y",
            "x # y",
            "a:b",
            "c: d",
            "",
            "  ",
            "true",
            "~",
            "'quoted'",
            "line\nbreak",
            "back\\slash",
            "sp ace",
            "-dash",
            "[bracket",
            "}brace",
            "\u00e9\u4e2d",
        ]
        doc = {"name": "tricky", "description": "d", "items": tricky}
        dumped = dump_frontmatter(doc)
        parsed, body = parse_frontmatter(dumped)
        self.assertEqual(parsed["items"], tricky)
        self.assertEqual(body, "")

    def test_malformed_block_mapping_is_clean_error(self):
        self.assert_frontmatter_error("---\nname: valid\n  unexpectedly-indented\n---\nbody\n")

    def test_document_limit_is_enforced(self):
        text = "x" * (MAX_DOCUMENT_CHARS + 1)
        self.assert_frontmatter_error(text)

    def test_round_trip_keys_containing_quote_characters(self):
        # OPEN-1 regression: keys with embedded ' or " were emitted unquoted,
        # making dump_frontmatter output unparseable.
        keys = [
            "x'y",
            'x"y',
            "1oi1Va0`sl&B&e}^^q`GMRv('wxnK",
            '=.~Mp"@l3R0wgfTFL4X<[cANgMq.5lWh(Mf5W4',
            "a'b\"c",
            "'lead",
            'trail"',
        ]
        for key in keys:
            with self.subTest(key=key):
                doc = {key: None}
                dumped = dump_frontmatter(doc)
                parsed, _ = parse_frontmatter(dumped)
                self.assertEqual(list(parsed), [key])
        nested = {"outer": {"a'1": "v", 'b"2': None}}
        dumped = dump_frontmatter(nested)
        parsed, _ = parse_frontmatter(dumped)
        self.assertEqual(parsed, nested)

    def test_dump_serializes_mappings_inside_flow_lists(self):
        # Mappings nested inside flow (bracket) lists used to be silently
        # str()-ified ({"n": 1} -> "{'n': 1}"); the dumper now emits flow maps
        # the parser already accepts, so such data round-trips.
        docs = [
            {"k": [["a", {"n": "1"}]]},
            {"k": [[{"a": "1"}, {"b": "2"}]]},
            {"k": [{"a": "1"}]},
            {"k": [{}, {"a": "1"}]},
            {"k": {"wrapped": [{"deep": {"n": "1"}}]}},
            # Empty collections must stay inline so they parse back to the
            # same empty value instead of silently becoming None.
            {"k": [{"deep": {}}, {"list": []}]},
            {"body": [{"x": {}}]},
            {"k": [{"a": {}, "b": []}, {"c": "v"}]},
        ]
        for doc in docs:
            with self.subTest(doc=doc):
                dumped = dump_frontmatter(doc)
                parsed, _ = parse_frontmatter(dumped)
                self.assertEqual(parsed, doc)
        # unparseable nesting depth fails loudly instead of corrupting
        deep = ["x"]
        for _ in range(100):
            deep = [deep]
        with self.assertRaises(TypeError):
            dump_frontmatter({"k": deep})

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
