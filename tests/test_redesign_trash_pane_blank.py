"""7.4e — the Trash detail pane's blank state, and a back button that lies.

Two defects, one view, both measured on the tree this branch already had:

  1. **The pane was ~700px of void.** 2.1c fixed exactly this for the Library
     with the `.pane-blank` vocabulary — an anchored state, not an illustration:
     eyebrow, title, lede, a `dl` of labelled OBSERVED facts, and the one action
     that resolves it. The Trash pane never got any of it: a heading, a lead, a
     scope note, and then nothing at 1280. The fix reuses the SAME vocabulary
     rather than inventing a second blank state, which is the class 5.3b and
     5.6a each found in a different view.

  2. **`.mobile-back` said "Back to Library" on seven of the eight views it
     renders on.** It picked its label from a two-case ternary
     (`view === 'quality' ? 'Back to Quality' : 'Back to Library'`), and it is
     `v-if="view !== 'skills'"` — so on Trash, Recovery, Profiles, Install,
     Workspaces and Settings the button that takes the reader BACK TO THAT
     VIEW'S OWN LIST claimed to return them to the Library. RULES #12: the UI
     states only observed facts, and a navigation control naming a destination
     it does not go to is the loudest version of that. The label is now derived
     from the palette's own `nav-*` rows — one list of view names, already the
     single source for `switchView` targets (5.7a's "one definition, two
     hosts"), so a new view cannot get a wrong label by being added.

The facts the blank pane states are DERIVED, not invented (RULES #12): the count
the filter left visible, the total size of what is in the trash, and the oldest
and newest removal — every one computed from the records the API returned. No
count about a skill nobody observed, and no claim about scope copies, which
have no endpoint (5.6a's recorded API gap).
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")

TRASH_BRANCH = HTML.index('v-else-if="view === \'trash\'" class="detail-inner"')
NEXT_BRANCH = HTML.index('v-else-if="view === ', TRASH_BRANCH + 40)
TRASH_PANE = HTML[TRASH_BRANCH:NEXT_BRANCH]
MOBILE_BACK = re.search(r'<button[^>]*class="mobile-back"[^>]*>[^<]*</button>', HTML)


class MobileBackLabelTests(unittest.TestCase):
    def test_the_button_exists_and_binds_a_derived_label(self):
        self.assertIsNotNone(MOBILE_BACK, "no .mobile-back button in the markup")
        self.assertIn("{{ mobileBackLabel }}", MOBILE_BACK.group(0))

    def test_the_two_case_ternary_is_gone(self):
        """The defect: `view === 'quality' ? ... : 'Back to Library'`, which is
        correct for exactly one view and lies on the other seven.

        Scoped to the button that calls `closeMobileView` — the Library's own
        detail back button (`:1325`, `closeMobileDetail`) says "Back to Library"
        and is CORRECT there, because it does go back to the Library list."""
        back = re.search(r'<button[^>]*class="mobile-back"[^>]*@click="closeMobileView"[^>]*>'
                         r'(.*?)</button>', HTML, re.S)
        self.assertIsNotNone(back, "the view-level back button is gone")
        self.assertNotIn("Back to Library", back.group(1),
                         "the view-level back button still names the Library on "
                         "every view but one")
        self.assertNotIn("view === 'quality'", back.group(1),
                         "the two-case ternary is back; derive the label from "
                         "the view list instead")

    def test_the_label_is_a_computed_derived_from_the_palette_nav_rows(self):
        """It must read the palette's `nav-*` rows rather than restate a list:
        5.7a established `SEARCH_VIEWS` as the single list for the `/` claim,
        and the view NAME list already exists as the palette's navigation rows."""
        block = re.search(r"\n    mobileBackLabel\(\) \{(.*?)\n    \}", APP, re.S)
        self.assertIsNotNone(block, "mobileBackLabel is not a computed in app.js")
        body = block.group(1)
        self.assertIn("commandPaletteCommands", body)
        self.assertIn("switchView", body,
                      "the derivation must find the row whose action navigates, "
                      "not match on a literal view id")

    def test_every_view_that_renders_the_button_has_a_palette_row(self):
        """CONTROL, both directions. Without it the derivation could fall back
        to a bare 'Back' on a view nobody added to the palette, and the fallback
        would be indistinguishable from the fix at the template level."""
        rendered = set(re.findall(r'v-else-if="view === \'([a-z]+)\'"', HTML))
        rows = set(re.findall(r'action: "switchView", args: \["([a-z]+)"\]', APP))
        missing = rendered - rows
        self.assertEqual(missing, set(),
                         f"views with a pane but no palette navigation row: "
                         f"{sorted(missing)} — mobileBackLabel would fall back "
                         "to a label that names nothing")


class TrashPaneBlankTests(unittest.TestCase):
    def test_the_pane_offers_a_blank_state_when_nothing_is_selected(self):
        self.assertIn('v-if="!selectedTrash"', TRASH_PANE,
                      "the Trash pane has no blank state, so a reader who has "
                      "not clicked a row reads a heading and 700px of nothing")

    def test_it_reuses_the_shared_blank_vocabulary(self):
        """A second blank-state class is 5.3b's "it existed twice" in a new
        place. `.pane-blank` and its parts are 2.1c's, and the Library still
        renders them, so this view must too."""
        for cls in ("pane-blank", "pane-blank-title", "pane-blank-lede",
                    "pane-blank-facts"):
            self.assertIn(cls, TRASH_PANE,
                          f"the blank state must use 2.1c's .{cls}")
        self.assertGreaterEqual(
            HTML.count('class="pane-blank-facts"'), 2,
            "a second blank state is being defined; the Trash pane must render "
            "2.1c's vocabulary, not its own")

    def test_the_facts_are_paired_by_label(self):
        """2.1c's own lesson: four of its five rows are conditionally
        rendered, so 'some dd has a value' passed with one blanked. Every fact
        here is inside its own <div> with a <dt> next to a <dd>."""
        rows = re.findall(r"<div><dt>(.*?)</dt><dd", TRASH_PANE)
        self.assertGreaterEqual(len(rows), 3,
                                f"the blank state states {len(rows)} paired facts")

    def test_the_title_is_focusable_and_addressable(self):
        """`tabindex="-1"` is what lets the pane take focus; 5.7b's rail jumps
        to sections the same way."""
        self.assertRegex(TRASH_PANE, r'class="pane-blank-title" tabindex="-1"')

    def test_the_blank_state_states_no_count_it_has_not_observed(self):
        """RULES #12 as a mechanical rule: no invented figure. Every number in
        the blank state must come from a computed/derived name."""
        for bad in ("items in agent scopes", "recommended", "safe to", "score"):
            self.assertNotIn(bad, TRASH_PANE.lower())


if __name__ == "__main__":
    unittest.main()