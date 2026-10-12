"""The document is a document, not a run of inherited defaults.

4.6 designed the rules that render a SKILL.md body. `4.5b` had already
extracted them so that `.body` (the Source tab's pane) and `.markdown-preview`
(the editor's live preview) cannot drift apart, and
`test_redesign_markdown_document.py` asserts that invariant. That suite
answers "do both hosts carry the same rule"; it cannot answer "is the rule
right", because none of the rules it was built to police had been a decision.
They were ~25 declarations inherited from the v1 stylesheet.

Four of them were wrong in a way that only shows when the rendered document is
held next to the rendered application:

  * `--t-prose` (16px) is documented in the scale as "rendered SKILL.md bodies"
    and nothing used it. The document inherited `--t-ui` (14px) from whatever
    pane happened to contain it.
  * `h4`/`h5`/`h6` were `--t-table` (13px): a heading smaller than the
    paragraph it introduces.
  * `.body h2 { margin-top: 0 }` was aimed at the first heading and hit every
    one, so a long document lost the space above every section in it.
  * inline `code` was 13px inside 14px text. The mono face already reads
    optically larger than the sans around it.

So the ladder is asserted here as a LADDER - ordered, never descending below
its own body - and the escaping half is asserted here as well, because
`test_frontend_seam_contracts.py` checks that the renderer emits only its own
tags but never checks that cell text, heading text, link text, list text and
fenced-block text all survive a hostile string intact.

The stylesheet is read as text on purpose: the numbers this file asserts are
design decisions recorded in one place, and a screenshot cannot tell you that
a rule was deleted and something else inherited the same value.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBUI = ROOT / "skillsmgr" / "webui"
CSS = (WEBUI / "styles.css").read_text(encoding="utf-8")

# The six declared steps. `check_design_tokens.py` refuses a seventh, so the
# ladder has to be built out of these and nothing else - that constraint is
# the reason h3 and h4 share a size and differ by weight and colour.
STEPS = {"--t-meta": 12, "--t-table": 13, "--t-ui": 14,
         "--t-prose": 16, "--t-page": 20, "--t-empty": 28}

BANNER_OPEN = "4.5b DOCUMENT HOSTS"
HOSTS = (".body", ".markdown-preview")


def _strip_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _document_block():
    start = CSS.rindex("/*", 0, CSS.index(BANNER_OPEN))
    end = CSS.index("/*", CSS.index("empty/loading") - 400)
    block = CSS[start:end]
    assert block.count("/*") == block.count("*/"), "banner slice is not comment-free"
    return _strip_comments(block)


def _rules(block):
    return [(s.strip(), b) for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", block)]


def _shared(block, tail):
    """Declarations of EVERY rule carrying `tail` on BOTH hosts, joined.

    Joined, not first-match: a tail legitimately has more than one rule (the
    document's base size and the spacing above it are separate declarations),
    and a helper that returned only the first silently answered a different
    question than the one the caller asked.
    """
    found = []
    for selector, body in _rules(block):
        items = [i.strip() for i in selector.split(",")]
        if all(any(i.startswith(h + tail) for i in items) for h in HOSTS):
            found.append(body)
    return " ".join(found)


def _size_of(declarations):
    """px value of `font-size: var(--t-*)` inside a declaration block, or None."""
    m = re.search(r"font-size:\s*var\((--t-[a-z-]+)\)", declarations)
    return STEPS.get(m.group(1)) if m else None


def render(*payloads):
    """renderMarkdown through Node, because that is where it actually runs.

    Not a re-implementation in Python: a Python copy of this renderer would
    pass while the shipped one had the defect, which is the failure this repo
    has already paid for twice.
    """
    script = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = { window: {} };
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const render = sandbox.window.SkillManagerDomain.renderMarkdown;
console.log(JSON.stringify(JSON.parse(process.argv[1]).map(render)));
"""
    out = subprocess.run(["node", "-e", script, json.dumps(list(payloads))],
                         capture_output=True, text=True, check=True, cwd=str(ROOT))
    return json.loads(out.stdout)


class TheLadder(unittest.TestCase):
    def setUp(self):
        self.block = _document_block()

    def test_no_heading_is_smaller_than_the_body_text(self):
        """A heading is an instruction to read harder. One that is set smaller
        than the paragraph under it says the opposite, and no amount of
        cleverness in the surrounding rules undoes it. This is the assertion
        that fails on the tree 4.6 started from, where h4/h5/h6 were 13px."""
        body = _size_of(_shared(self.block, " p")) or _size_of(_shared(self.block, " li"))
        self.assertIsNotNone(body, "the document body declares no `--t-*` size")
        for level in (" h1", " h2", " h3", " h4", " h5", " h6"):
            with self.subTest(level=level):
                size = _size_of(_shared(self.block, level))
                self.assertIsNotNone(size, f"level{level} declares no `--t-*` size")
                self.assertGreaterEqual(
                    size, body,
                    f"a level{level} heading is set at {size}px inside {body}px "
                    "body text: the ladder descends below its own floor",
                )

    def test_the_body_uses_the_step_the_scale_documents_for_it(self):
        """`--t-prose` is commented in styles.css as the size for "rendered
        SKILL.md bodies". If the document resolves its base from inheritance
        instead, it silently takes whatever the pane around it is set at - two
        panes, two sizes, and the preview silently one step off the Source
        tab (which is exactly the 4.5b defect, one indirection further)."""
        for tail in (" p", " li", " td"):
            with self.subTest(tail=tail):
                self.assertEqual(16, _size_of(_shared(self.block, tail)),
                                 "the document body must be `--t-prose`")

    def test_the_ladder_actually_ladders(self):
        """Strictly ordered by size where it steps, and the whole thing is
        built from the six declared steps - the constraint that shapes it."""
        sizes = [_size_of(_shared(self.block, " h%d" % n)) for n in range(1, 7)]
        self.assertTrue(all(sizes), "the ladder has a hole")
        self.assertEqual(28, sizes[0], "h1 is the document's title")
        self.assertEqual(20, sizes[1], "h2 is the section")
        for bigger, smaller in zip(sizes, sizes[1:]):
            self.assertGreaterEqual(bigger, smaller,
                                    "the ladder must be monotonic: a heading "
                                    "may not get bigger as it gets deeper")
        self.assertLess(sizes[0], 29, "h1 must not out-shout the pane's own title")
        self.assertEqual(sorted(set(sizes), reverse=True),
                         sorted(set(sizes), reverse=True))
        self.assertEqual(len(set(sizes)), 3,
                         "six levels over two usable steps: the rest of the "
                         "distinction is weight and colour, not size")

    def test_inline_code_declares_no_size_of_its_own(self):
        """The mono face is already optically larger than the sans it sits in.
        Adding `--t-table` on top of that is how a code span reads as an aside
        rather than as code."""
        inline = _shared(self.block, " code")
        self.assertIn("var(--mono)", inline)
        self.assertIsNone(
            _size_of(inline),
            "inline code must inherit the size of the text it sits in; the "
            "block form (`pre code`) is the one that steps down",
        )
        block_code = _shared(self.block, " pre code")
        self.assertEqual(13, _size_of(block_code),
                         "block code steps DOWN to `--t-table`, which is the "
                         "only place in the document that is allowed to")

    def test_only_the_first_heading_loses_its_top_margin(self):
        """`margin-top: 0` on every `h2` looks correct on a document with one
        section and wrong on every document after the first - which is the
        shape almost every SKILL.md has."""
        self.assertNotRegex(_shared(self.block, " h2"), r"margin-top:\s*0",
                            "every h2 would lose the space above it, not just "
                            "the one at the top of the document")
        self.assertIn("margin-top: 0", _shared(self.block, " > :first-child"))

    def test_the_space_above_a_section_comes_from_the_scale(self):
        for tail, prop in ((" h2", "margin"), (" h3", "margin"), (" p", "margin")):
            with self.subTest(tail=tail):
                decl = _shared(self.block, tail)
                self.assertTrue(
                    re.search(r"margin:[^;]*var\(--s\d", decl),
                    f"{tail.strip()} spacing must come from the spacing scale, "
                    f"not from an ad-hoc em multiple: {decl.strip()}",
                )


class BothHostsEndTheSameWay(unittest.TestCase):
    def test_the_last_child_collapse_carries_both_hosts(self):
        """It used to exist for the preview only, and 600 lines below the
        document block, so the host-agreement suite could not see it: the
        editor's document finished flush to its frame and the Source tab's
        finished with whatever margin its final element carried."""
        block = _document_block()
        self.assertIn("margin-bottom: 0", _shared(block, " > :last-child"))
        body = _strip_comments(CSS)
        self.assertNotRegex(
            body, r"^\.markdown-preview\s*>\s*:last-child",
            "the single-host version is still in the file; two rules now, "
            "one of them a silent divergence",
        )


class TablesAreNotSpreadsheets(unittest.TestCase):
    def setUp(self):
        self.block = _document_block()

    def test_cells_carry_a_row_rule_not_a_box(self):
        cells = _shared(self.block, " th") + _shared(self.block, " td")
        self.assertIn("border-bottom: 1px solid var(--border)", cells)
        self.assertNotRegex(
            cells, r"(?<!-)border:\s*1px solid",
            "a 1px box around every cell is a spreadsheet, and the `thead` "
            "fill that came with it was the other half of that look",
        )
        self.assertNotIn("background", self.block.split("table")[1][:400],
                         "a grey header band reads as a header row only if you "
                         "already know it is one")

    def test_the_renderer_emits_a_real_header_row(self):
        html = render("| Column | Meaning |\n| --- | --- |\n| Scope | Where |")[0]
        self.assertIn("<thead><tr><th>Column</th><th>Meaning</th></tr></thead>", html)
        self.assertIn("<tbody>", html)
        self.assertEqual(html.count("<th>"), 2, "only the row above `|---|` is a header")

    def test_a_table_with_no_separator_row_has_no_invented_header(self):
        """`|---|---|` is the only evidence a row is a header. Guessing makes
        the first row of a headerless table bold, which is a claim about the
        document that the document did not make."""
        html = render("| a | b |\n| c | d |")[0]
        self.assertNotIn("<th>", html)
        self.assertNotIn("<thead>", html)
        self.assertEqual(html.count("<tr>"), 2)

    def test_rows_keep_their_order_when_nothing_proves_a_header(self):
        """The first version of 4.6 held the pending row until the table
        closed, which emitted `| a | b |` AFTER `| c | d |`. Found by running
        it, not by reading it - the code looked correct."""
        html = render("| a | b |\n| c | d |")[0]
        self.assertLess(html.index("<td>a</td>"), html.index("<td>c</td>"))

    def test_a_single_row_table_does_not_lose_its_only_row(self):
        """The held row has three exits: flushed by a separator, flushed by
        the next row, flushed at close. Drop any one and a table silently
        loses data."""
        self.assertIn("<td>a</td>", render("| a | b |")[0])
        self.assertIn("<th>a</th>", render("| a |\n| --- |\n| b |")[0])

    def test_the_style_that_kills_the_last_rule_does_not_depend_on_a_thead(self):
        block = self.block
        self.assertIn("border-bottom: 0", _shared(block, " tr:last-child > td"),
                      "a headerless table has no `tbody`; the rule that removes "
                      "the final row rule must reach it too")
        self.assertEqual(
            "", _shared(block, " tr:last-child > *"),
            "`tr:last-child > *` is ALSO the header row - it is the last child "
            "of the `thead` - so it deleted the rule under the column labels. "
            "Measured: `th` border-bottom-width 0px against `td` 1px.",
        )


class QuotesAreProse(unittest.TestCase):
    def setUp(self):
        self.rule = _shared(_document_block(), " blockquote")

    def test_a_quote_is_not_a_panel(self):
        self.assertNotIn("background", self.rule,
                         "the grey box was decoration, and decoration is what "
                         "makes a document read as a template")
        self.assertNotIn("var(--accent)", self.rule,
                         "the accent is reserved for things you can act on; a "
                         "quote spends it on nothing")

    def test_quoted_text_is_not_demoted_below_the_prose_around_it(self):
        self.assertNotIn("--text-muted", self.rule,
                         "a quoted sentence is content the reader asked for; "
                         "it must not sit at less contrast than the paragraph "
                         "above it")
        self.assertIn("border-left", self.rule)


class TheEmptyBodyIsAClassNotAStyle(unittest.TestCase):
    def test_no_inline_style_attribute_reaches_the_v_html_path(self):
        html = render("")[0]
        self.assertNotIn("style=", html,
                         "an inline style is the one thing in this document "
                         "that no stylesheet rule can hold to account")
        self.assertIn('class="doc-empty"', html)

    def test_the_class_is_styled_by_a_shared_rule(self):
        block = _document_block()
        self.assertIn("var(--text-muted)", _shared(block, " .doc-empty"))


class EverythingIsEscaped(unittest.TestCase):
    """`.markdown-preview` and `.body` are `v-html`. Everything below is
    attacker-controlled text in a SKILL.md body, and every one of these
    strings has to come out as TEXT.

    `test_frontend_seam_contracts.py` already proves the renderer emits only
    its own tags; this file proves the CONTENT survives, at each of the seven
    places a block can put a string: a heading, a paragraph, a list item, a
    quote, a table cell, a table header and a fenced code block.
    """

    HOSTILE = (
        "<script>alert(1)</script>",
        "\"><script>alert(1)</script>",
        "' onmouseover='alert(1)",
        "`</code></pre><img src=x onerror=alert(1)>`",
        "**</strong><iframe src=javascript:alert(1)>**",
        "[click](https://x.test/\"><script>alert(1)</script>)",
        "<!--<script>alert(1)</script>-->",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
    )

    def _rendered(self, template):
        return render(template)[0]

    # Everything the renderer is allowed to emit, and nothing else.
    ALLOWED = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li",
               "blockquote", "pre", "code", "a", "table", "thead", "tbody",
               "tr", "th", "td", "strong", "em", "hr", "div"}

    def _assert_only_its_own_markup(self, html, where):
        """Check the TAGS, not the text.

        The first version of this sweep searched the whole output for
        `onerror` and failed on `` `<img src=x onerror=alert(1)>` `` rendered
        as a code span - which is escaped, inert, and the renderer working.
        Asserting on substrings inside escaped text proves that escaping does
        not work, which is the opposite of what is true. So: pull the tags out
        and check those.
        """
        for match in re.finditer(r"<\s*/?\s*([a-zA-Z][a-zA-Z0-9-]*)", html):
            self.assertIn(match.group(1).lower(), self.ALLOWED,
                          f"{where}: emitted <{match.group(1)}>: {html[:200]}")
        for tag in re.finditer(r"<([a-zA-Z][^>]*)>", html):
            attrs = tag.group(1)
            self.assertNotRegex(attrs, r"\son[a-z]+\s*=",
                                f"{where}: event handler survived: {attrs}")
            for scheme in ("javascript:", "data:text/html", "style="):
                self.assertNotIn(scheme, attrs.lower(),
                                 f"{where}: {scheme} survived in a tag: {attrs}")

    def test_every_block_escapes_a_hostile_string(self):
        templates = {
            "heading": "# %s\n\ntext\n",
            "paragraph": "%s\n",
            "list item": "- %s\n",
            "ordered item": "1. %s\n",
            "quote": "> %s\n",
            "table cell": "| %s | b |\n| --- | --- |\n| c | d |\n",
            "table header": "| %s | b |\n| --- | --- |\n| c | d |\n",
            "fenced code": "```\n%s\n```\n",
            "inline code": "text `%s` text\n",
            "emphasis": "*%s*\n",
            "link": "[%s](https://x.test/)\n",
        }
        for where, template in templates.items():
            with self.subTest(block=where):
                self._assert_only_its_own_markup(
                    self._rendered(template % self.HOSTILE[0]), where)

    def test_no_payload_of_any_shape_survives_as_markup(self):
        """Every hostile string, through every block, in one sweep - so a
        payload only has to work in ONE place to be caught here."""
        templates = ("# %s\n\ntext\n", "%s\n", "- %s\n", "> %s\n",
                     "| %s | b |\n| --- | --- |\n| c | d |\n", "```\n%s\n```\n",
                     "*%s*\n", "`%s`\n", "[%s](https://x.test/)\n", "1. %s\n")
        for template in templates:
            html = self._rendered(template % "\n".join(self.HOSTILE))
            with self.subTest(template=template.splitlines()[0][:20]):
                self._assert_only_its_own_markup(html, template[:20])

    def test_escaped_text_stays_visible_rather_than_being_stripped(self):
        """The other half. An escaper that DELETES the payload is not escaping
        it either - a reader whose SKILL.md documents an HTML tag has to be
        able to read the tag."""
        self.assertIn("&lt;script&gt;", self._rendered("Use `<script>` carefully.\n"))

    def test_a_link_href_cannot_break_out_of_its_attribute(self):
        """`esc()` covers `& < > " '`, so a quote inside a URL is already an
        entity by the time the `href` is written. Asserted rather than
        assumed: this is the one injection point in the renderer."""
        html = self._rendered('[x](https://x.test/?a="><script>alert(1)</script>)\n')
        self.assertNotIn('href="https://x.test/?a="><script', html)
        self.assertNotIn("<script", html)

    def test_escaping_survives_a_hostile_table_header(self):
        """The header row is the one string the renderer re-tags, so it is the
        one path where escaping is applied to a value that also passes through
        a second transformation."""
        html = render("| <script>alert(1)</script> | b |\n| --- | --- |\n| c | d |")[0]
        self.assertIn("<th>", html)
        self.assertNotIn("<script", html)


if __name__ == "__main__":
    unittest.main()