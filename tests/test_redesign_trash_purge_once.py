"""7.4g — "Empty the global trash" existed twice on one view.

Once as the list pane's pinned footer and once as a red `.text-button` in the
detail header, ~500px apart, in two visual languages, both calling
`confirmPurge`. 5.3b's "the profile list existed twice", in a third view.

The deciding fact was not a taste argument about where a destructive control
belongs. It was that the two controls were **gated differently**:

    header:  v-if="trashSkills.length"        <- what is in the trash
    footer:  v-if="!loadingTrash && !trashError && filteredTrash.length"

After a failed read (6.3's `trashError`) the header still offered to empty a
trash the reader had never been shown, while the footer correctly said nothing
about a list it could not read. So one of the two doors was honest and one was
not, and the honest one is the survivor.

The dialog is untouched: `data-modal="purge"` names itself and its confirm
button calls `purgeTrash`, a different method, so it is the THIRD rendering of
the label and not a second door on the view. These contracts separate the three
rather than counting strings.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")

# The three surfaces, located by the thing that makes each of them itself.
FOOTER = HTML.index('class="trash-purge-row"')
TRASH_DETAIL = HTML.index('<div v-else-if="view === \'trash\'" class="detail-inner">')
PURGE_DIALOG = HTML.index('data-modal="purge"')

# Every control on the VIEW (i.e. before the dialogs open) that offers this
# verb. Derived, not listed: a fourth rendering has to fail this.
# The TRASH VIEW only. Recovery has its own "Purge all N items" control in its
# ledger and that one is not a duplicate of anything — it is the same verb on a
# different surface, which is the difference 5.3b's duplicate was not.
TRASH_SIDEPANEL = HTML.index("<template v-else-if=\"view === 'trash'\">")
TRASH_DETAIL = HTML.index('<div v-else-if="view === \'trash\'" class="detail-inner">')
# Two slices, because the view is two columns with everything else in between:
# the sidepanel list, then the detail pane. Recovery's own "Purge all N items"
# sits in that gap and is NOT a duplicate of anything — same verb, different
# surface — so counting handlers across the whole document would call it one.
VIEW = (HTML[TRASH_SIDEPANEL:HTML.index("</aside>", TRASH_SIDEPANEL)]
        + HTML[TRASH_DETAIL:HTML.index("</section>\n  </main>", TRASH_DETAIL)])
CONFIRMING = re.findall(r'@click="(\w+)"', VIEW)


class OneDoorTests(unittest.TestCase):
    def test_exactly_one_control_on_the_view_opens_the_purge_review(self):
        """The fix. `confirmPurge` is the handler both copies shared."""
        self.assertEqual(
            CONFIRMING.count("confirmPurge"), 1,
            "the view has more than one way into the purge review; a reader "
            "cannot tell from either of them what the other one does")

    def test_the_survivor_is_the_one_beside_the_list_it_acts_on(self):
        """NOT a preference. The footer acts on the list the reader is looking
        at; the header acted on whatever was selected, which is nothing until a
        row is clicked."""
        self.assertLess(FOOTER, PURGE_DIALOG)
        self.assertIn('@click="confirmPurge"', HTML[FOOTER:PURGE_DIALOG])

    def test_and_the_detail_header_no_longer_offers_it(self):
        # `@click=`, not the bare word: the comment explaining why the duplicate
        # was removed names the handler, and a prose mention is not a control.
        self.assertNotIn('@click="confirmPurge"', HTML[TRASH_DETAIL:HTML.index("</section>\n  </main>", TRASH_DETAIL)],
                         "the duplicate is back in the detail header")

    def test_the_header_keeps_the_action_that_is_about_the_selection(self):
        """Removing a control is not the same as emptying a pane. Restore lives
        with the selected item, and Back to Recovery is how the reader leaves."""
        header = HTML[TRASH_DETAIL:HTML.index("</section>\n  </main>", TRASH_DETAIL)]
        self.assertIn("switchView('recovery')", header)
        self.assertIn("restoreTrash", header)


class TheDoorsAreGatedDifferentlyTests(unittest.TestCase):
    def test_the_footer_gate_is_the_observation_the_header_never_made(self):
        """The reason the duplicate was worse than a duplicate. `trashError` is
        what 6.3 added: it survives until a read succeeds, so a gate that asks
        only how many items the trash holds will happily offer to empty it after
        the read that established that count never arrived."""
        row = HTML[FOOTER - 300:FOOTER]
        for condition in ("!loadingTrash", "!trashError", "filteredTrash.length"):
            self.assertIn(condition, row,
                          f"the purge action is no longer gated on {condition}")

    def test_no_control_anywhere_on_the_view_gates_on_a_count_it_cannot_see(self):
        """`trashSkills.length` was the header's gate and it is gone from the
        view entirely. An assertion that only looked for the label would have
        passed with the duplicate in place."""
        self.assertNotIn('v-if="trashSkills.length"', VIEW,
                         "a control is still gated on a count the reader has "
                         "not been shown")

    def test_the_dialog_is_a_review_and_still_exists(self):
        """Deleting a duplicate is not deleting the capability: the modal is
        the confirm step and it names itself."""
        dialog = HTML[PURGE_DIALOG:PURGE_DIALOG + 2000]
        self.assertIn("Empty the global trash", dialog)
        self.assertIn('@click="purgeTrash"', dialog)
        self.assertNotIn('@click="confirmPurge"', dialog,
                         "the dialog confirms; it must not re-open itself")


if __name__ == "__main__":
    unittest.main()