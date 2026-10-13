"""7.4d — the purge row was a list ROW, so its button got the dot track.

`styles.css` builds a three-track grid for every item of a `.skilllist`:

    .skilllist > li:not(.selection-hint):not(.skeleton):not(.empty) {
      display: grid;
      grid-template-columns: 16px 7px minmax(0, 1fr);   /* dot | gap | name */
      ...

The action that empties the global trash was an `<li>` inside that list, so its
only child auto-placed into the **16px dot track** and computed a 26px box
(16px track + the button's own `0 var(--s3)` side padding) around a 143px label.
Under `.btn`'s `justify-content: center` the text overflowed symmetrically, and
`.skilllist`'s `overflow-y: auto` clipped it to its TAIL — the pane showed a red
orphan reading "the global trash" under the list, which is the label's *second
half*, painted outside its own control.

The fix is the ELEMENT, not the selector: the row is a `<div>` now, so no list
rule reaches it. That is what these contracts hold — a purge row that becomes an
`<li>` again, in a future edit, would silently inherit the dot track, and the
symptom is a clipped label, not a console error.

The browser half is `tests/e2e/test_trash_purge_row.py`. It cannot be derived
from source: the defect was `width: 100%` DECLARED, losing the cascade to a
grid track, so every assertion here is about which rule the box obeys.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")

# The list-row grid, by its own selector. Read once so a reformat cannot make
# every assertion in this file vacuous. 7.4f added a fourth `:not()` clause to
# it (the failed-read branch is an `<li>` too), so this matches a CHAIN of
# exclusions rather than a literal: the assertions below are about the grid's
# geometry and about which elements can reach it, neither of which depends on
# how many branches are excluded. `assertIsNotNone` is the control — a selector
# with no `:not()` at all is a different rule, and the loop must not stop there.
ROW_GRID = re.search(
    r"\.skilllist\s*>\s*li:not\([^)]*\)(?::not\([^)]*\))*\s*\{",
    CSS)
TRASH_PANE = HTML.index('class="skilllist" aria-label="Trash"')
# 7.4f — the pane is a `<ul>` and this row is a SIBLING of it, so "not an item
# of the list" is now structural. Sliced from the `<ul>`'s own text so a row put
# back inside it fails here rather than only in the cascade.
TRASH_LIST = HTML[TRASH_PANE:HTML.index("</ul>", TRASH_PANE)]


class TrashPurgeRowMarkupTests(unittest.TestCase):
    def test_the_row_grid_this_defect_walked_into_is_really_declared(self):
        """CONTROL. If the row grid is ever renamed or removed, the assertion
        below ('the purge row cannot match it') would pass for the wrong reason
        — a detector that has stopped matching reports PASS about a path it
        cannot see, which is this repository's most repeated failure."""
        self.assertIsNotNone(
            ROW_GRID,
            "the .skilllist row-grid selector was not found; every assertion "
            "below reasons about whether the purge row can match it")
        block = CSS[ROW_GRID.end():CSS.index("}", ROW_GRID.end())]
        self.assertIn("grid-template-columns", block)
        self.assertIn("16px", block, "the dot track is the whole defect: the "
                                     "button was auto-placed into it")

    def test_the_purge_row_is_not_an_item_of_the_list(self):
        """The fix. As an `<li>` it matched the row grid above."""
        self.assertNotRegex(
            HTML, r"<li[^>]*class=\"trash-purge-row\"",
            "the purge row is an <li> again, so it inherits the three-track "
            "row grid and its button lands in the 16px dot track")

    def test_the_purge_row_is_not_even_a_descendant_of_the_list(self):
        """7.4f made the fix structural rather than notional.

        The pane is a `<ul>` now (a `<div>` carrying `aria-label` exposed no
        list, and the rows inside it were orphan `<li>`s), and a `<ul>` may only
        contain `<li>` — so an action could not stay inside it at all. Sliced
        from the `<ul>`'s own text: a row moved back inside fails HERE, which is
        a different failure from the one above and would be caught by nothing
        else in this file."""
        self.assertNotIn("trash-purge-row", TRASH_LIST,
                         "the purge row is inside the <ul> again; an action "
                         "belongs beside the list, not in it")

    def test_the_control_for_the_above_finds_a_real_list(self):
        """CONTROL. If `</ul>` were never found, the slice above would run to
        the end of the document and every element in it would 'fail' — so a
        slice that cannot find its end must fail the suite, not pass it."""
        self.assertGreater(len(TRASH_LIST), 0)
        self.assertIn("<li", TRASH_LIST)

    def test_the_control_the_same_way_really_finds_the_items(self):
        """CONTROL, the other direction: the detector above must be able to
        match. The trash items ARE `<li class=...>` inside the same list, and
        deleting every one of them would satisfy 'no purge <li>' too."""
        window = HTML[TRASH_PANE:TRASH_PANE + 2000]
        self.assertRegex(window, r"<li v-for=\"t in filteredTrash\"",
                         "no <li> trash items remain — 'the purge row is not an "
                         "<li>' is now satisfiable by having no list at all")

    def test_the_purge_row_has_a_rule_of_its_own(self):
        """`.trash-purge-row`, not scoped to a list it no longer lives in.

        The compound selector used to read `.skilllist > .trash-purge-row`,
        which 7.4d added deliberately: a bare rule is (0,1,0) and would lose to
        the row grid at (0,5,1) if anything ever put this row back in that list.
        7.4f answered that properly — the row is a sibling of the `<ul>`, so no
        list rule can reach it and the scoping is not merely unnecessary but
        false. `flex: none` is what this task added: as a flex item beside the
        list, the row would shrink when the list is long, and the one control
        that cannot be undone would be the one thing that disappears."""
        block = re.search(r"^\.trash-purge-row\s*\{([^}]*)\}", CSS, re.M)
        self.assertIsNotNone(block, ".trash-purge-row has no rule of its own")
        self.assertNotIn(".skilllist >", block.group(0),
                         "the rule is still scoped to a list the row no longer "
                         "sits inside")
        self.assertIn("flex: none", block.group(1),
                      "the footer is a flex item now and must not shrink away "
                      "under a long list")

    def test_the_button_is_declared_full_width(self):
        """7.4b's declaration, which the cascade ate. Kept in the suite so the
        regression this task fixed cannot come back as 'the rule was deleted'."""
        block = re.search(r"\.trash-purge-row \.btn\s*\{([^}]*)\}", CSS)
        self.assertIsNotNone(block, ".trash-purge-row .btn has no rule")
        self.assertIn("width: 100%", block.group(1))

    def test_the_row_is_marked_as_a_zone_and_not_as_an_item(self):
        """The hairline is the design claim: everything above it can be
        restored, the one control below it cannot be undone."""
        block = re.search(r"^\.trash-purge-row\s*\{([^}]*)\}", CSS, re.M)
        self.assertIsNotNone(block)
        self.assertIn("border-top", block.group(1),
                      "the action zone lost the line that separates it from "
                      "the restorable items above it")


class TrashPurgeRowInventoryTests(unittest.TestCase):
    def test_the_only_purge_row_in_the_markup_is_the_one_this_file_guards(self):
        self.assertEqual(HTML.count('class="trash-purge-row"'), 1)

    def test_no_rule_in_the_trash_block_can_re_introduce_a_list_item_shape(self):
        """A later edit adding `display: flex` here would be fine; adding
        `display: grid` with the dot track's template is the defect wearing a
        new hat. Assert the row's own rule carries no grid template."""
        block = re.search(r"^\.trash-purge-row\s*\{([^}]*)\}", CSS, re.M)
        self.assertIsNotNone(block)
        self.assertNotIn("grid-template", block.group(1))


if __name__ == "__main__":
    unittest.main()