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
# every assertion in this file vacuous.
ROW_GRID = re.search(
    r"\.skilllist\s*>\s*li:not\(\.selection-hint\):not\(\.skeleton\):not\(\.empty\)\s*\{",
    CSS)
TRASH_PANE = HTML.index('class="skilllist" aria-label="Trash"')


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

    def test_the_control_the_same_way_really_finds_the_items(self):
        """CONTROL, the other direction: the detector above must be able to
        match. The trash items ARE `<li class=...>` inside the same list, and
        deleting every one of them would satisfy 'no purge <li>' too."""
        window = HTML[TRASH_PANE:TRASH_PANE + 2000]
        self.assertRegex(window, r"<li v-for=\"t in filteredTrash\"",
                         "no <li> trash items remain — 'the purge row is not an "
                         "<li>' is now satisfiable by having no list at all")

    def test_the_purge_row_has_a_rule_qualified_against_the_list(self):
        """`.skilllist > .trash-purge-row`, not a bare `.trash-purge-row`.

        A bare rule is (0,1,0) and would lose to `.skilllist > li:not(...)` at
        (0,4,1) if anything ever put this row back in that list. The compound
        selector states the relationship rather than relying on source order."""
        self.assertRegex(
            CSS, r"\.skilllist\s*>\s*\.trash-purge-row\s*\{",
            "the purge row's own rule must be scoped to its list parent")

    def test_the_button_is_declared_full_width(self):
        """7.4b's declaration, which the cascade ate. Kept in the suite so the
        regression this task fixed cannot come back as 'the rule was deleted'."""
        block = re.search(r"\.trash-purge-row \.btn\s*\{([^}]*)\}", CSS)
        self.assertIsNotNone(block, ".trash-purge-row .btn has no rule")
        self.assertIn("width: 100%", block.group(1))

    def test_the_row_is_marked_as_a_zone_and_not_as_an_item(self):
        """The hairline is the design claim: everything above it can be
        restored, the one control below it cannot be undone."""
        block = re.search(r"\.skilllist\s*>\s*\.trash-purge-row\s*\{([^}]*)\}", CSS)
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
        block = re.search(r"\.skilllist\s*>\s*\.trash-purge-row\s*\{([^}]*)\}", CSS)
        self.assertNotIn("grid-template", block.group(1))


if __name__ == "__main__":
    unittest.main()