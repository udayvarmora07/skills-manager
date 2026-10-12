"""One rule: a RUN of consecutive source lines is ONE block (task 4.6b).

`renderMarkdown` used to emit one `<p>` per SOURCE LINE. A SKILL.md author
wraps prose at ~72 columns, so a single sentence became three paragraphs - and
task 4.6 made it worse by putting paragraph spacing on the type scale (16px,
up from ~10px), which is what had been hiding it. The defect was only ever
visible in a rendered document, which is why it survived a green gate.

These tests render through Node against the shipped `domain.js`. A Python
re-implementation would be a second renderer that passes while the shipped one
keeps the defect - the failure this repository has paid for more than once.

Every "one block" assertion is paired with a control that the joining must not
swallow: a blank line, a block start, a code fence. Without those, deleting the
paragraph entirely satisfies every `assertEqual(count(...), 1)`.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_NODE = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = { window: {} };
vm.runInNewContext(fs.readFileSync('skillsmgr/webui/domain.js', 'utf8'), sandbox);
const render = sandbox.window.SkillManagerDomain.renderMarkdown;
const input = JSON.parse(process.argv[1]);
console.log(JSON.stringify(input.map(render)));
"""


def render(*payloads):
    """HTML for each payload, via the real renderer in a real JS engine."""
    out = subprocess.run(
        ["node", "-e", _NODE, json.dumps(list(payloads))],
        capture_output=True, text=True, check=True, cwd=str(ROOT),
    )
    return json.loads(out.stdout)


def tags(html, name):
    return re.findall(r"<%s(?:\s[^>]*)?>" % name, html)


def text_of(html):
    """Visible text: tags out, entities left alone.

    Deliberately NOT `re.sub` over the whole string looking for a payload
    name: that proves escaping is broken when it is working. 4.6's escape
    sweep already had this defect and the fix was to inspect TAGS.
    """
    stripped = re.sub(r"<[^>]+>", "", html)
    return stripped.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


class TheRunRule(unittest.TestCase):
    def test_a_wrapped_sentence_is_one_paragraph_not_three(self):
        """The defect. Three source lines, one sentence, three `<p>` blocks -
        and with 4.6's 16px paragraph spacing that reads as broken prose with
        holes in it rather than as wrapped text."""
        html = render("enough words to have a measurable leading\n"
                      "value rather than a nominal one.")[0]
        self.assertEqual(1, len(tags(html, "p")),
                         "a wrapped sentence must render as ONE paragraph: %r" % html)
        self.assertIn("measurable leading value rather than",
                      text_of(html),
                      "the joined words must still be in order and readable")

    def test_a_blank_line_still_starts_a_new_paragraph(self):
        """The control. If joining is unconditional this fails; without it the
        assertion above is satisfied by emitting no paragraph at all."""
        html = render("first paragraph\n\nsecond paragraph")[0]
        self.assertEqual(2, len(tags(html, "p")),
                         "a blank line is the author's own paragraph break and "
                         "must survive: %r" % html)

    def test_every_block_kind_ends_the_run(self):
        """A heading, a list, a table, a quote and a fence are all block
        starts. Each must close the paragraph above it, or the joining would
        swallow document structure as well as line wraps.

        The claim is that the paragraph exists and says exactly what it said
        before the block - not that some number of `<p>` came out, which
        depends on what follows (a trailing line is a lazy continuation of the
        list item it sits under, and is correctly not its own paragraph).
        """
        cases = {
            "heading": ("intro line\ncontinued\n# Section\nafter", "h1"),
            "list": ("intro line\ncontinued\n- item\nafter", "ul"),
            "ordered list": ("intro line\ncontinued\n1. item\nafter", "ol"),
            "table": ("intro line\ncontinued\n| a | b |\n|---|---|---|\n"
                      "| c | d |", "table"),
            "quote": ("intro line\ncontinued\n> quoted\nafter", "blockquote"),
            "code fence": ("intro line\ncontinued\n```\nraw()\n```\nafter", "pre"),
            "rule": ("intro line\ncontinued\n---\nafter", "hr"),
        }
        for label, (md, block) in cases.items():
            with self.subTest(block=label):
                html = render(md)[0]
                self.assertTrue(tags(html, block),
                                "%s did not render its own element: %r" % (label, html))
                texts = [text_of(p) for p in re.findall(r"<p>(.*?)</p>", html)]
                self.assertTrue(texts, "the prose above %s vanished: %r" % (label, html))
                self.assertEqual(
                    "intro line continued", texts[0],
                    "%s must end the paragraph run, so the prose above it is "
                    "a complete paragraph of its own: %r" % (label, html))

    def test_a_wrapped_quote_is_one_blockquote(self):
        """Same rule, one element over. Two `>` lines are one quoted
        paragraph, and the bare `>` between two quotes is the author's break."""
        html = render("> a quoted line\n> continued here\n>\n> a second quote")[0]
        self.assertEqual(2, len(tags(html, "blockquote")), repr(html))
        self.assertIn("a quoted line continued here", text_of(html))
        self.assertIn("a second quote", text_of(html))

    def test_a_wrapped_list_item_is_one_item(self):
        """A list item wrapped across lines used to become two bullets: the
        continuation line started no block, so it fell through to the
        paragraph branch. That is the same defect with a bullet in front."""
        html = render("- first item that wraps\n  and continues here\n- second")[0]
        self.assertEqual(2, len(tags(html, "li")), repr(html))
        self.assertIn("first item that wraps and continues here", text_of(html))

    def test_source_indentation_is_not_rendered(self):
        """Indented continuation lines are a source convention. Rendering the
        leading whitespace would collapse the joined run back into a visual
        break, which is the defect in a different guise."""
        html = render("first line\n    second line")[0]
        self.assertEqual("first line second line", text_of(html))

    def test_a_code_fence_keeps_its_line_breaks(self):
        """The control against a joining that is too eager. A fence holds
        literal text whose newlines are the content; collapsing them would
        silently rewrite the author's code."""
        html = render("```js\nconst a = 1;\nconst b = 2;\n```")[0]
        body = re.search(r"<code>(.*?)</code>", html, re.S)
        self.assertIsNotNone(body, repr(html))
        self.assertIn("const a = 1;\nconst b = 2;", body.group(1))

    def test_escaping_still_applies_across_a_joined_run(self):
        """Joining concatenates attacker-controlled source into one string
        before `inlineMd` sees it. The join is `\\n` -> ` " " `, never `""` -
        concatenating without a separator would let `**` or `` ` `` from one
        line open a span on another."""
        html = render("a **bold start\nbold end** here")[0]
        self.assertEqual("<p>a <strong>bold start bold end</strong> here</p>",
                         html.replace("\n", " "))
        hostile = render("text <script>alert(1)</script>\nstill the same run")[0]
        self.assertEqual([], re.findall(r"<script", hostile),
                         "a joined run must not create an element")
        self.assertIn("<script>alert(1)</script>", text_of(hostile),
                      "escaped text must stay VISIBLE - an escaper that "
                      "deletes the payload is not escaping it either")

    def test_a_table_row_is_not_absorbed_by_a_run(self):
        """The renderer holds the first row back until a `|---|` row proves it
        a header (4.6). Joining must not let a prose line flush the held row
        into the paragraph instead, which would lose the table's first line."""
        html = render("| a | b |\n|---|---|\n| c | d |")[0]
        self.assertEqual(["a", "b"], re.findall(r"<th>(.*?)</th>", html))
        self.assertEqual(["c", "d"], re.findall(r"<td>(.*?)</td>", html))
        self.assertEqual([], tags(html, "p"), "a table is not a paragraph")

    def test_the_rendered_text_is_identical_to_the_source_words(self):
        """Whatever the block structure becomes, no word may be lost or
        duplicated. This is the assertion that survives a future rewrite of
        the joining itself."""
        words = "alpha bravo charlie delta echo foxtrot golf hotel".split()
        html = render("\n".join(words))[0]
        got = text_of(html).split()
        self.assertEqual(words, got)


class TheSeamIsUnchanged(unittest.TestCase):
    def test_render_markdown_is_still_the_exported_seam(self):
        """4.5b's contract: there is exactly ONE renderer and it is on the
        frozen `window.SkillManagerDomain`. A local copy introduced to dodge
        the joining would be two documents again."""
        source = (ROOT / "skillsmgr/webui" / "domain.js").read_text("utf8")
        export = source.index("window.SkillManagerDomain = Object.freeze({")
        self.assertIn("renderMarkdown", source[export:])
        self.assertEqual(1, source.count("function renderMarkdown("),
                         "a second renderer is a second document")


if __name__ == "__main__":
    unittest.main()