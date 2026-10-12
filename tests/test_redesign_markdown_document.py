"""One Markdown renderer, so the editor's preview must look like the Source tab.

4.5b added a split live preview to the skill editor. The interesting part is
not the two columns - it is that `.body` (the Source tab's pane) and
`.markdown-preview` (the editor's preview) are handed the output of the SAME
`renderMarkdown` call. That makes a divergence possible and invisible: add a
`.body blockquote` rule and the preview keeps rendering the old one, and every
gate stays green because nothing ever renders a document next to another.

So the contract asserted here is the invariant, not a list of selectors:

  every document-element rule that carries one host carries BOTH.

`.body` on its own, with no element after it, is the pane's chrome (the rule
above the block: margin, padding, the top hairline, the measure) and is
deliberately not shared - the preview is not a pane. The test asserts that it
is the ONLY such rule, so a new bare-host rule is a decision rather than an
omission.

This suite reads the stylesheet as text. It does not render anything, so the
e2e suite owns the geometry; what is pinned here is the thing a screenshot
cannot show you, which is that the two renderings cannot drift apart.
"""

import re
import unittest
from pathlib import Path

WEBUI = Path(__file__).resolve().parents[1] / "skillsmgr" / "webui"
CSS = (WEBUI / "styles.css").read_text(encoding="utf-8")
HTML = (WEBUI / "index.html").read_text(encoding="utf-8")

HOSTS = (".body", ".markdown-preview")

BANNER_OPEN = "4.5b DOCUMENT HOSTS"
BANNER_END = "empty/loading"


def _strip_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _document_block():
    """The rules between the 4.5b banner and the empty/loading section.

    Sliced from the `/*` that OPENS the banner, not from the banner text: a
    slice that starts mid-comment hands the parser an unterminated comment and
    everything after it silently vanishes. That is this repo's recorded
    "the gate is reading prose, not structure" defect, and the banner is prose.
    """
    start = CSS.rindex("/*", 0, CSS.index(BANNER_OPEN))
    end = CSS.index("/*", CSS.index(BANNER_END) - 400)
    block = CSS[start:end]
    assert block.count("/*") == block.count("*/"), "banner slice is not comment-free"
    return _strip_comments(block)


def _rules(block):
    """[(selector_list, declarations)] for a comment-free block."""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", block):
        out.append((m.group(1).strip(), m.group(2)))
    return out


def _hosted_tails(block):
    """Map tail -> set of hosts, for selector items that name a document element.

    A "tail" is everything after the host class: `h1`, `> :first-child`,
    `pre code`. The bare host has no tail and is the pane chrome, handled by a
    separate assertion.
    """
    tails = {}
    bare = set()
    for selector, _body in _rules(block):
        for item in selector.split(","):
            item = item.strip()
            for host in HOSTS:
                if not item.startswith(host):
                    continue
                tail = item[len(host):].strip()
                if not tail:
                    bare.add(host)
                else:
                    tails.setdefault(tail, set()).add(host)
    return tails, bare


class MarkdownDocumentHostsAgree(unittest.TestCase):
    def setUp(self):
        self.block = _document_block()
        self.tails, self.bare = _hosted_tails(self.block)

    def test_the_block_is_actually_located(self):
        """A locator that silently returns "" makes every assertion vacuous."""
        self.assertGreater(len(_rules(self.block)), 20, "4.5b document block not found")
        self.assertGreaterEqual(len(self.tails), 12, "document element rules not found")

    def test_every_document_element_rule_carries_both_hosts(self):
        only_one = sorted(
            f"{next(iter(hs))} {tail}"
            for tail, hs in self.tails.items()
            if hs != set(HOSTS)
        )
        self.assertEqual(
            [], only_one,
            "these rules style a document element for one host only, so the "
            "editor preview and the Source tab render the same markdown "
            "differently: " + "; ".join(only_one),
        )

    def test_the_bare_host_rule_is_the_pane_chrome_and_is_the_only_one(self):
        self.assertEqual(
            {".body"}, self.bare,
            "a bare `.body` / `.markdown-preview` rule with no element is the "
            "pane's own box (margin, border, measure). Only `.body` may have "
            "one; the preview is not a pane.",
        )

    def test_both_hosts_are_actually_present_in_the_block(self):
        found = {h for hs in self.tails.values() for h in hs}
        self.assertEqual(set(HOSTS), found)

    def test_the_measure_is_not_applied_to_the_preview(self):
        """`.body`'s 72ch measure is a reading rule for a full pane. A split
        column is already narrower than 72ch, so copying the measure onto the
        preview would be a second width the two hosts could disagree about -
        and the disagreement would be invisible in a screenshot of a dialog."""
        self.assertIn("max-width: 72ch", self.block)
        for selector, body in _rules(self.block):
            items = [i.strip() for i in selector.split(",")]
            if ".body" in items:
                continue  # the pane's own box, which is where the measure lives
            self.assertNotIn("max-width", body,
                             "the measure belongs to the pane's own box rule, "
                             "not to a document-element rule shared by both hosts")

    def test_the_preview_inherits_its_base_size_instead_of_declaring_one(self):
        """A single `font-size` on the preview host shifts EVERY element inside
        it - heading, paragraph, list item, quote, table cell - by one step at
        once, which is why it is invisible in a screenshot of a dialog and
        obvious to a reader holding the two documents side by side. Measured:
        `--t-table` against `.body`'s inherited `--t-ui` made the whole preview
        13px where the Source tab was 14px, on all six probed elements."""
        m = re.search(r"\.markdown-preview\s*\{([^}]*)\}", _strip_comments(CSS))
        self.assertIsNotNone(m, "no .markdown-preview rule found")
        self.assertIsNone(
            re.search(r"(?<![\w-])font-size:", m.group(1)),
            "the preview must resolve its base size the way `.body` does - by "
            "inheriting it. Declaring one here desynchronises every element in "
            "the subtree from the Source tab: " + m.group(1).strip(),
        )


class SplitPreviewLayout(unittest.TestCase):
    """The split is declared, not emergent."""

    def _mq_block(self, condition):
        # `condition` starts at its own "@media", so the search start IS i.
        # `CSS.rindex("@media", 0, i)` searches CSS[0:i], which excludes the
        # "@media" it is looking for and hands back the *previous* block. Same
        # off-by-one shape as 3.4b's "a line that moved when I changed a
        # comment's length" - the failure is silent and the wrong block still
        # parses.
        i = CSS.index(condition)
        start = i
        depth = 0
        for j in range(start, len(CSS)):
            if CSS[j] == "{":
                depth += 1
            elif CSS[j] == "}":
                depth -= 1
                if depth == 0:
                    return CSS[start:j + 1]
        raise AssertionError("unterminated @media")

    def test_the_split_declares_two_tracks_from_900px(self):
        block = _strip_comments(self._mq_block("@media (min-width: 900px)"))
        m = re.search(r"\.body-split\s*\{([^}]*)\}", block)
        self.assertIsNotNone(m, "no .body-split rule in the 900px band")
        decls = m.group(1)
        tracks = re.search(r"grid-template-columns:\s*([^;]+);", decls)
        self.assertIsNotNone(tracks, "the split has no declared columns at 900px")
        self.assertEqual(2, tracks.group(1).count("minmax(0,"),
                         "the split must be two equal flexible tracks: " + tracks.group(1))

    def test_the_shared_height_is_declared_once_on_the_container(self):
        """Two panes of 'about the same height' is how a shared height rots."""
        block = _strip_comments(self._mq_block("@media (min-width: 900px)"))
        m = re.search(r"\.body-split\s*\{([^}]*)\}", block)
        self.assertIn("height:", m.group(1),
                      "the container must declare the shared height")
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", block):
            if ".body-split >" in selector:
                # `min-height:` contains the substring `height:` - the same
                # substring trap 2.2's adoption check fell into. Look for a
                # standalone property instead.
                self.assertIsNone(
                    re.search(r"(?<![\w-])height:", body.replace("height: 100%", "")),
                    "a child must fill the declared height, not declare one of "
                    "its own: " + selector,
                )

    def test_both_panes_scroll_in_place_and_only_in_the_split(self):
        block = _strip_comments(self._mq_block("@media (min-width: 900px)"))
        shared = [
            body for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", block)
            if "> textarea" in selector and "> .markdown-preview" in selector
        ]
        self.assertEqual(1, len(shared),
                         "the two panes must be given ONE shared rule; found "
                         f"{len(shared)}, which means the heights can drift")
        self.assertIn("overflow-y: auto", shared[0])
        self.assertIn("height: 100%", shared[0])

    def test_resize_is_disabled_only_inside_the_split(self):
        self.assertIn(".body-split > textarea { resize: none; }", _strip_comments(CSS))
        self.assertIn(".form-field textarea { resize: vertical;", _strip_comments(CSS))

    def test_the_split_beats_the_coarse_pointer_minimum_on_specificity(self):
        """`@media (pointer: coarse) .form-field textarea { min-height: 44px }`
        sits 400 lines further down the file and has the SAME specificity as a
        bare `.body-split > textarea`. Source order then decides, silently, and
        the measured result was a 266px textarea on a phone: the rule appeared
        in the stylesheet and never applied. Every split rule is scoped through
        `.form-field` so the outcome does not depend on where the next rule is
        inserted."""
        coarse = ".form-field textarea, .form-field select { min-height: 44px; }"
        self.assertIn(coarse, _strip_comments(CSS),
                      "the coarse-pointer minimum has moved; re-measure the "
                      "specificity this test relies on")
        for selector, _body in re.findall(r"([^{}]+)\{([^{}]*)\}", _strip_comments(CSS)):
            if "> textarea" in selector or ".body-split" in selector:
                self.assertIn(".form-field .body-split", selector,
                              "a split rule must out-specify the coarse-pointer "
                              "band, not out-order it: " + selector.strip())


class OneRendererTwoPlaces(unittest.TestCase):
    def test_the_source_tab_and_the_editor_call_the_same_function(self):
        self.assertEqual(
            2, HTML.count("v-html=\"renderMarkdown("),
            "the document is rendered in exactly two places: the Source tab "
            "and the editor's preview. A third is a second renderer, which is "
            "the defect this row exists to prevent.",
        )

    def test_the_editor_preview_keeps_the_document_host_class(self):
        self.assertIn(
            'class="markdown-preview" role="region" aria-label="Markdown preview" '
            'tabindex="0" v-html="renderMarkdown(modals.skill.form.body)"', HTML,
            "the preview must carry the host class and a name; a bare div with "
            "v-html has neither, and a scrollable region with no name is "
            "unreachable by keyboard without one.",
        )

    def test_the_two_panes_are_siblings_in_one_split_container(self):
        self.assertIn('<div class="body-split">', HTML)

    def test_the_hint_no_longer_names_an_orientation_it_does_not_have(self):
        self.assertNotIn("Preview below.", HTML,
                         "at >=900px the preview is beside the textarea")


if __name__ == "__main__":
    unittest.main()