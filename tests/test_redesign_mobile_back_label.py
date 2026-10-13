"""7.4e1 — the back button that said "Back to Library" on seven of eight views.

`index.html` had:

    <button v-if="view !== 'skills' && mobileDetailOpen" class="mobile-back"
            @click="closeMobileView">← {{ view === 'quality' ? 'Back to Quality'
            : 'Back to Library' }}</button>

The button renders on **every view except the Library** — so on Trash, Recovery,
Profiles, Install, Workspaces, Settings and Overview, the control that takes the
reader back to *that view's own list* named the Library. Below 760px the list and
the detail share one screen, so that button is the only way back and its label
IS the affordance. RULES #12: the UI states only observed facts, and a
navigation control naming a destination it does not go to is the loudest
version of that.

The label is now derived from the palette's `nav-*` rows — the view-name list
that already exists and already drives `switchView` (5.7a's "one definition, two
hosts", the rule `SEARCH_VIEWS` was created for). A new view cannot arrive with
a wrong label by omission, because the suite asserts the two sets agree.

**Why this is a source contract and not only an e2e.** The derivation is pure and
the relationship it must preserve is between two lists in two files. The browser
half (`tests/e2e/test_mobile_back_label.py`) proves the label is right on a
real view at the width where it is the only way back.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "skillsmgr" / "webui" / "app.js").read_text(encoding="utf-8")

VIEW_BACK = re.search(
    r'<button[^>]*class="mobile-back"[^>]*@click="closeMobileView"[^>]*>(.*?)</button>',
    HTML, re.S)


class MobileBackLabelMarkupTests(unittest.TestCase):
    def test_the_view_level_button_binds_the_derived_label(self):
        self.assertIsNotNone(VIEW_BACK, "the view-level back button is gone")
        self.assertIn("{{ mobileBackLabel }}", VIEW_BACK.group(1))

    def test_the_two_case_ternary_is_gone(self):
        """The defect, named. Scoped to THIS button: the Library's own detail
        back button (`closeMobileDetail`) says "Back to Library" and is correct
        there, because it does go back to the Library list."""
        body = VIEW_BACK.group(1)
        self.assertNotIn("Back to Library", body)
        self.assertNotIn("Back to Quality", body)
        self.assertNotIn("view ===", body,
                         "a view test is back in the label; derive it instead")

    def test_the_librarys_own_back_button_is_left_alone(self):
        """CONTROL, the other direction. If this button were "fixed" too it
        would read "Back to Library" for a control that goes to the Library —
        correct today, and the reason the assertion above is scoped rather than
        a page-wide ban on the string."""
        self.assertRegex(
            HTML, r'class="mobile-back"[^>]*@click="closeMobileDetail"[^>]*'
                  r'>\s*←\s*Back to Library',
            "the Library's own back button must keep its literal label")

    def test_the_button_still_only_renders_where_it_did(self):
        """The `v-if` is the other half of the control: a correct label on a
        button that appears on the Library too would be a different defect."""
        self.assertRegex(VIEW_BACK.group(0), r'v-if="view !== \'skills\' && mobileDetailOpen"')


class MobileBackLabelDerivationTests(unittest.TestCase):
    def _block(self):
        block = re.search(r"\n    mobileBackLabel\(\) \{(.*?)\n    \},", APP, re.S)
        self.assertIsNotNone(block, "mobileBackLabel is not a computed in app.js")
        return block.group(1)

    def test_it_is_a_computed_and_not_a_method(self):
        """A function the template CALLS must be a method (5.5's trap: Vue's
        render proxy unwraps a computed before the template sees it, so calling
        one throws during render with every stdlib gate green). This one is
        interpolated, not called — and that is exactly why it belongs in
        `computed`: the template must never invoke it."""
        computed = APP.index("\n  computed: {")
        methods = APP.index("\n  methods: {")
        start = APP.index("mobileBackLabel() {")
        self.assertTrue(computed < start < methods,
                        "mobileBackLabel is outside the computed block — it is "
                        "interpolated, so it must be a computed")

    def test_it_reads_the_palette_navigation_rows_rather_than_restating_a_list(self):
        body = self._block()
        self.assertIn("commandPaletteCommands", body)
        self.assertIn('c.action === "switchView"', body)
        self.assertIn("c.args[0] === this.view", body)

    def test_it_invents_no_destination_when_no_row_matches(self):
        body = self._block()
        self.assertIn('"Back"', body,
                      "the fallback must be a bare 'Back' — naming a "
                      "destination the derivation could not find is exactly the "
                      "lie this task removes")

    def test_every_view_that_renders_a_pane_has_a_palette_row(self):
        """CONTROL, both directions. Without it, adding a view without a
        palette row would leave the button reading a bare "Back" — and the
        template-level assertions would still pass, because the binding is
        right either way."""
        rendered = set(re.findall(r"v-(?:else-)?if=\"view === '([a-z]+)'\"", HTML))
        rows = set(re.findall(r'action: "switchView", args: \["([a-z]+)"\]', APP))
        self.assertTrue(rendered, "no view branches found — the regex broke")
        self.assertEqual(rendered - rows, set(),
                         f"views with a pane but no palette navigation row: "
                         f"{sorted(rendered - rows)}")


if __name__ == "__main__":
    unittest.main()