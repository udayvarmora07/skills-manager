"""7.4f — the Trash pane's list was a `<div>`, so it was not a list.

`index.html` carried the Trash column as:

    <div v-else-if="view === 'trash'" class="skilllist" aria-label="Trash">
      <div v-if="loadingTrash" class="skeleton">…</div>
      <div v-else-if="trashError" class="read-failed" …>…</div>
      <div v-else-if="filteredTrash.length === 0" class="empty">…</div>
      <template v-else><li v-for="t in filteredTrash">…</li></template>
    </div>

Three things were wrong at once and none of them looked wrong:

1. **`aria-label="Trash"` was inert.** A `<div>` with no `role` exposes no
   list, so a screen reader was offered no list at all and the three rows
   announced as unlabelled text. The Library's counterpart at `index.html:480`
   has been a real `<ul>` all along.
2. **The rows still looked like rows.** `.skilllist`'s row grid selects
   `li`, not anything semantic, so the orphan `<li>`s were painted as a
   proper 56px list. The markup was lying about its structure and the
   stylesheet was happy with the lie.
3. **Every branch was a `<div>`, including the ones that have to become list
   items.** Converting the container without converting them would put a
   `<div>` and a `<p>` inside a `<ul>`, which is invalid, and — because the row
   grid matches `li:not(.selection-hint):not(.skeleton):not(.empty)` at
   (0,4,1) — an `<li class="read-failed">` would auto-place its `<p>` and its
   Try again button into the **16px dot track** and the 7px gap. Hence the
   fourth `:not()`.

The browser half is `tests/e2e/test_trash_pane_list.py`; the computed `display`
of that error branch cannot be derived from source, which is 2.1b's lesson
again.
"""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = (ROOT / "skillsmgr" / "webui" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")

TRASH_PANE = HTML.index('class="skilllist" aria-label="Trash"')
# The `<ul>`'s own text. Every assertion about "inside the list" reads this
# slice, so an assertion that cannot see its subject fails here first.
TRASH_LIST = HTML[TRASH_PANE:HTML.index("</ul>", TRASH_PANE)]


def row_grid_selectors():
    """Every selector that starts the `.skilllist` row rule.

    Read from the stylesheet rather than hard-coded: the class has grown a
    `:not()` clause twice on this branch (7.4d, 7.4f) and a test that pins
    the old literal is a test that fails for the wrong reason.
    """
    return re.findall(
        r"(?m)^(\.skilllist > li:not\([^)]*\)(?::not\([^)]*\))*)", CSS)


class TrashPaneIsAListTests(unittest.TestCase):
    def test_the_control_first_the_library_list_is_a_ul_too(self):
        """CONTROL. Everything below reasons about this view's container being
        a list element. If the Library's list is not a `<ul>` either, then
        "matches the Library's shape" has stopped meaning anything and a
        detector that stops matching reports PASS about a path it cannot see."""
        self.assertRegex(HTML, r'<ul class="skilllist"[^>]*>')

    def test_the_trash_list_is_a_ul_and_not_a_div(self):
        """The fix. A `<div>` with `aria-label` and no role exposes no list."""
        opener = re.search(r"<(\w+)[^>]*class=\"skilllist\" aria-label=\"Trash\"", HTML)
        self.assertIsNotNone(opener, "the Trash pane's list could not be located")
        self.assertEqual(
            opener.group(1), "ul",
            "the Trash column is not a <ul> again, so aria-label=\"Trash\" "
            "names nothing and its <li>s are orphans of a list that is not there")

    def test_the_labelled_element_is_the_list_itself(self):
        """`aria-label` must ride the `<ul>`, not a wrapper — a label on an
        element with no role is the exact defect, one level out."""
        opener = re.search(r"<(\w+)[^>]*class=\"skilllist\" aria-label=\"Trash\"", HTML)
        self.assertIn("aria-label", opener.group(0))

    def test_every_branch_inside_the_list_is_an_li(self):
        """Loading, failed read and empty are list ITEMS of this list, so each
        branch opener has to be an `<li>`. A `<div>` inside a `<ul>` is invalid
        markup, and the `<li>` version is the one the row grid can reach — see
        the module docstring."""
        for branch in ('<li v-if="loadingTrash" class="skeleton"',
                       '<li v-else-if="trashError" class="read-failed"',
                       '<li v-else-if="filteredTrash.length === 0" class="empty"'):
            self.assertIn(branch, TRASH_LIST,
                          f"{branch!r} is not the branch it claims to be")

    def test_no_div_is_a_direct_child_of_the_list(self):
        """And no branch was quietly left a `<div>`.

        Checked by INDENTATION, not by searching for `<div`: `.skel-row`,
        `.empty-icon` and `.empty-actions` are legitimately nested inside their
        `<li>`s, so a text search for `<div` cannot tell a branch from a child
        and reports PASS about the thing it is meant to catch. Every line at the
        branches' own indentation must open an `<li>`, open or close a
        `<template>`, or close the `<ul>`."""
        lines = TRASH_LIST.splitlines()
        branch_indent = next(len(line) - len(line.lstrip())
                             for line in lines
                             if line.lstrip().startswith('<li v-if="loadingTrash"'))
        for line in lines:
            stripped = line.lstrip()
            if len(line) - len(stripped) != branch_indent or not stripped.startswith("<"):
                continue
            self.assertTrue(
                stripped.startswith(("<li ", "</li>", "<template", "</template>", "</ul>", "<!--")),
                f"{stripped[:60]!r} is a direct child of the <ul> and is neither "
                f"a list item nor the <template> that groups the rows")

    def test_the_rows_are_still_list_items(self):
        """CONTROL for the three above: deleting the rows would satisfy every
        'not a div' assertion in this file with no list at all."""
        self.assertIn('<li v-for="t in filteredTrash"', TRASH_LIST)


class TheErrorBranchCannotBecomeARowTests(unittest.TestCase):
    def test_every_row_rule_exempts_the_failed_read(self):
        """THE part that can bite. Every selector that opens the row grid must
        carry `:not(.read-failed)`, and there are five of them: a message in the
        16px dot track and a Try again button in the 7px gap is the 7.4d defect
        wearing a different element."""
        selectors = row_grid_selectors()
        self.assertGreaterEqual(len(selectors), 5,
                                "the row grid is no longer written five times "
                                "over — re-derive which branches it can reach")
        for sel in selectors:
            self.assertIn(":not(.read-failed)", sel,
                          f"{sel!r} would give the failed read the row grid")

    def test_the_control_the_exemption_is_not_vacuous(self):
        """CONTROL. If `:not(.read-failed)` were on nothing, or on a selector
        this file never reads, the assertion above would pass over a tree where
        the error branch IS a row."""
        self.assertEqual(
            len([s for s in row_grid_selectors() if ":not(.read-failed)" in s]),
            len(row_grid_selectors()))

    def test_the_failed_read_declares_a_block_display_of_its_own(self):
        """And it has to SAY so, because `.skilllist li` at (0,1,1) declares
        `display: flex`. A bare `.read-failed` rule at (0,1,0) would lose to it;
        this one is (0,2,0) and wins."""
        self.assertRegex(CSS, r"(?m)^\.skilllist > \.read-failed \{ display: block; \}$")

    def test_no_sixth_not_clause_is_hiding_the_exemption(self):
        """A later branch must not be exempted from the row grid by ACCIDENT.

        Written first as a rule over EVERY `:not()` in the row selector — and it
        failed on the **correct** tree, because `.selection-hint` (the Library's
        own branch) has no block display and never needed one: it is a `<li>` in
        a different list, governed by that list's rules. A check that cannot
        pass on a correct tree is worse than no check, so it is narrowed to the
        branch this task introduced, and the general rule is stated as the
        comment it deserves rather than shipped as a failing assertion.
        """
        for excluded in re.findall(r":not\(\.([a-z-]+)\)", row_grid_selectors()[0]):
            if excluded in ("selection-hint", "skeleton", "empty", "read-failed"):
                continue
            self.fail(f"{excluded!r} is exempt from the row grid but has no rule "
                      f"of its own; an exemption with no block display is an "
                      f"auto-placed <li>")


class ThePurgeActionIsGatedOnSomethingObservedTests(unittest.TestCase):
    """7.4d left the row inside the list, which meant inside its `v-else`
    branch — it rendered only when there was something to restore. 7.4f moved
    it out to a sibling (a `<ul>` may only contain `<li>`), and that moved the
    condition from the chain to the element. Getting it wrong in the easy
    direction offers to empty a trash nobody has been shown holds anything."""

    def test_the_purge_row_states_the_same_three_conditions_the_chain_does(self):
        row = HTML[HTML.index('class="trash-purge-row"') - 200:
                   HTML.index('class="trash-purge-row"')]
        for condition in ("!loadingTrash", "!trashError", "filteredTrash.length"):
            self.assertIn(condition, row,
                          f"the purge action is no longer gated on {condition}")

    def test_and_there_is_exactly_one_purge_row(self):
        self.assertEqual(HTML.count('class="trash-purge-row"'), 1)


if __name__ == "__main__":
    unittest.main()