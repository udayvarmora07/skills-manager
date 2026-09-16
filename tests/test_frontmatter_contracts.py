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


class BlockScalarFidelityTests(unittest.TestCase):
    """FM-5..FM-12: dump -> parse must return exactly what was dumped."""

    def assert_round_trips(self, document):
        dumped = dump_frontmatter(document)
        parsed, body = parse_frontmatter(dumped)
        self.assertEqual(parsed, document, f"dumped as {dumped!r}")
        self.assertEqual(body, "")

    def test_common_leading_indentation_is_preserved(self):
        # FM-5: min-indent detection plus a fixed pad ate the value's own
        # indentation.  An explicit indentation indicator removes the guesswork.
        self.assert_round_trips({"description": "  code line 1\n  code line 2"})

    def test_single_indented_line_keeps_its_indentation(self):
        self.assert_round_trips({"k": "   indented\n"})

    def test_whitespace_only_lines_keep_their_whitespace(self):
        # FM-6: a whitespace-only line was treated as blank and collapsed to "".
        self.assert_round_trips({"description": "a\n  \nb"})

    def test_value_of_only_whitespace_survives(self):
        self.assert_round_trips({"k": " \n "})

    def test_carriage_return_inside_a_value_is_preserved(self):
        # FM-7: rstrip("\r") on every line could not tell a CRLF terminator
        # from CR content.
        self.assert_round_trips({"description": "line1\r\nline2"})

    def test_a_tab_before_a_hash_does_not_truncate_the_value(self):
        # FM-8: the parser starts a comment at '#' after a tab, but the dumper
        # only quoted for ' #', so "a\t#b" silently became "a".
        self.assert_round_trips({"description": "a\t#b"})

    def test_colon_before_a_tab_does_not_become_a_mapping(self):
        self.assert_round_trips({"k": "a:\tb"})

    def test_control_bearing_key_uses_escaped_output(self):
        # FM-9: representable control characters stay on one physical mapping
        # line and are reconstructed by the parser from double-quoted escapes.
        dumped = dump_frontmatter({"a\nb": "v"})
        self.assertIn('"a\\nb": v', dumped)
        parsed, _ = parse_frontmatter(dumped)
        self.assertEqual(parsed, {"a\nb": "v"})

    def test_fm9_escaped_key_round_trips(self):
        # FM-9: the parser already understands escaped double-quoted keys, so
        # the dumper must use that representation for a key containing a line
        # break instead of emitting a second physical mapping line.
        document = {"a\nb": "v", "metadata": {"line\tkey": "nested"}}
        dumped = dump_frontmatter(document)
        self.assertIn('"a\\nb": v', dumped)
        self.assertIn('"line\\tkey": nested', dumped)
        parsed, body = parse_frontmatter(dumped)
        self.assertEqual(parsed, document)
        self.assertEqual(body, "")

    def test_fm9_duplicate_serialized_keys_fail_loudly(self):
        # Distinct Python keys can render to the same string key (for example,
        # 1 and "1").  The dumper must reject the collision before writing a
        # document its own parser would reject as a duplicate key.
        with self.assertRaisesRegex(ValueError, "duplicate.*key"):
            dump_frontmatter({1: "x", "1": "y"})
        with self.assertRaisesRegex(ValueError, "duplicate.*key"):
            dump_frontmatter({"outer": {1: "x", "1": "y"}})

    def test_newline_only_values_do_not_collapse(self):
        # FM-10: a value of "\n" re-parsed as "".
        self.assert_round_trips({"description": "\n"})
        self.assert_round_trips({"description": "\n\n"})
        self.assert_round_trips({"description": "\n\n\n"})

    def test_a_value_without_a_trailing_newline_uses_strip_chomping(self):
        self.assert_round_trips({"description": "a\nb"})

    def test_chomping_indicators_match_yaml(self):
        # FM-12: clip kept too many trailing blank lines and keep dropped one.
        clipped, _ = parse_frontmatter("---\nk: |\n  a\n\n\nz: 1\n---\n")
        self.assertEqual(clipped["k"], "a\n")
        kept, _ = parse_frontmatter("---\nk: |+\n  a\n\nz: 1\n---\n")
        self.assertEqual(kept["k"], "a\n\n")
        stripped, _ = parse_frontmatter("---\nk: |-\n  a\n\nz: 1\n---\n")
        self.assertEqual(stripped["k"], "a")

    def test_explicit_indentation_indicator_is_parent_relative(self):
        # FM-14: the indicator was treated as an absolute indentation.
        parsed, _ = parse_frontmatter("---\nmetadata:\n  k: |2-\n      a\n      b\n---\n")
        self.assertEqual(parsed, {"metadata": {"k": "  a\n  b"}})

    def test_block_scalar_as_a_bare_sequence_element(self):
        # The dumper emitted "- |" for a multi-line list item, which its own
        # parser then rejected as unexpected indentation.
        self.assert_round_trips({"f": [{"k": ["a\nb"]}]})
        self.assert_round_trips({"f": [["a\nb", "c\nd"]]})

    def test_nested_and_sequence_values_round_trip(self):
        for document in (
            {"metadata": {"description": "  x\n  y"}},
            {"items": [{"note": "  x\n  y"}]},
            {"items": [{"a": "x\n\n", "b": "  z"}]},
            {"a": {"b": {"c": "  p\n  q\n\n"}}},
        ):
            with self.subTest(document=document):
                self.assert_round_trips(document)

    def test_crlf_documents_are_still_normalized(self):
        parsed, body = parse_frontmatter("---\r\nname: demo\r\n---\r\nbody\r\n")
        self.assertEqual(parsed, {"name": "demo"})
        self.assertEqual(body, "body\n")


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

    def test_sequence_root_is_a_clean_frontmatter_error(self):
        # FM-2: a top-level YAML sequence used to be returned as a list, so
        # every consumer (doctor, resync, db_rebuild, validate, scan) died with
        # a raw AttributeError on ``.get``.
        self.assert_frontmatter_error("---\n- a\n- b\n---\nbody\n")

    def test_out_of_range_unicode_escape_is_a_clean_error(self):
        # FM-3: chr() used to raise a raw ValueError that bypassed every guard.
        self.assert_frontmatter_error('---\ndescription: "x \\U00110000 y"\n---\nb\n')

    def test_unpaired_surrogate_escape_is_a_clean_error(self):
        # FM-4: the escape parsed, validation passed, then every write died
        # with a raw UnicodeEncodeError.
        self.assert_frontmatter_error('---\ndescription: "x \\uD800 y"\n---\nb\n')

    def test_raw_surrogate_scalar_is_a_clean_error(self):
        self.assert_frontmatter_error('---\ndescription: "a\ud800b"\n---\nb\n')

    def test_valid_escapes_still_decode(self):
        parsed, _ = parse_frontmatter('---\ndescription: "a\\nb \\u00e9 \\x41"\n---\n')
        self.assertEqual(parsed, {"description": "a\nb é A"})

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

    def test_duplicate_keys_are_clean_errors(self):
        # OBS-1 resolution: duplicate keys used to resolve last-wins silently,
        # hiding authoring mistakes (e.g. two `name:` lines). Every mapping
        # form now fails as a clean FrontmatterError instead.
        self.assert_frontmatter_error("---\nk: 1\nk: 2\n---\nbody\n")
        self.assert_frontmatter_error("---\nname: a\nname: b\ndescription: d\n---\n")
        self.assert_frontmatter_error("---\nitems:\n  - a: 1\n    a: 2\n---\n")
        self.assert_frontmatter_error("---\nitems: [{a: 1, a: 2}]\n---\n")
        self.assert_frontmatter_error("---\nouter:\n  k: 1\n  k: 2\n---\n")

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

    def test_indented_marker_inside_block_scalar_is_content_not_a_marker(self):
        # FM-1: an indented '---' inside a multi-line value used to terminate
        # the block early, silently truncating the value and promoting the
        # rest of it into the document body -- and every rewrite persisted it.
        document = {"description": "Use this skill when a doc has\n---\na rule in it."}
        dumped = dump_frontmatter(document)
        parsed, body = parse_frontmatter(dumped)
        self.assertEqual(parsed, document)
        self.assertEqual(body, "")

    def test_column_zero_marker_inside_body_of_value_still_closes_the_block(self):
        # A '---' at column zero is the documented terminator: block-scalar
        # awareness must not swallow the real closing marker.
        source = "---\nname: demo\n---\n# body\n\nnot: frontmatter\n"
        parsed, body = parse_frontmatter(source)
        self.assertEqual(parsed, {"name": "demo"})
        self.assertEqual(body, "# body\n\nnot: frontmatter\n")

    def test_explicit_indentation_indicator_marker_is_content(self):
        parsed, body = parse_frontmatter("---\ndescription: |2-\n    ---\n    x\n---\nb\n")
        self.assertEqual(parsed, {"description": "  ---\n  x"})
        self.assertEqual(body, "b\n")

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

    def test_dump_nesting_limit_is_enforced_without_recursion_error(self):
        # FM-20: programmatically supplied containers bypass the parser's
        # depth guard and used to crash the dumper with RecursionError.
        value = "leaf"
        for _ in range(MAX_NESTING_DEPTH + 100):
            value = {"nested": value}
        with self.assertRaises(TypeError) as caught:
            dump_frontmatter({"value": value})
        self.assertNotIsInstance(caught.exception, RecursionError)
        self.assertIn("nesting", str(caught.exception))

    def test_flow_nesting_limit_is_enforced_without_recursion_error(self):
        depth = MAX_NESTING_DEPTH + 1
        value = "[" * depth + "value" + "]" * depth
        self.assert_frontmatter_error(f"---\nvalue: {value}\n---\nbody\n")


if __name__ == "__main__":
    unittest.main()
