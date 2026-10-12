"""4.7d — the narrow band's `flex` on the detail action row.

The defect was rendered, so the e2e suite (`tests/e2e/test_detail_action_row.py`)
is what proves it fixed. This module pins the **cause** in the stylesheet, for
the reason this repo keeps recording: a CSS rule can be reverted and every
existing assertion still passes, because "does this selector exist" cannot see
what it renders, and `tests/e2e/` is not collected by `unittest discover -s
tests` (1.1's deliberate choice, so a CI unit job never launches a browser).

Specifically it pins the two facts the fix turned on, both of which were wrong
in my first attempt:

1. the narrow band's rule is **`flex: 0 1 auto`**, and specifically not
   `flex: 1` — the defect — nor `flex: 1 1 auto` — which measured identically
   bad, because `flex-grow: 1` hands a lone wrapped item every pixel of free
   space on its line;
2. it is scoped to `.detail-actions .btn`, not to `.btn` generally, so the many
   other button rows in the app keep whatever distribution they had.

Both assertions were run against the reverted stylesheet before being written.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")


def _narrow_band():
    """The media-query block that actually contains the fixed rule.

    Located by finding the rule itself and taking the nearest `@media` that
    opens before it — NOT by taking the last query in the file, and not by a
    brace-matching walk.

    Both of those were tried and both were wrong, for the one recorded reason
    (1.7): the stylesheet is full of long prose comments, and a walker that does
    not strip comments first reads their characters as structure. My own comment
    above this rule — which quotes a CSS example — was enough to make a
    brace-counting walk report the rule was inside no query at all, and taking
    "the last @media" returned a 33KB region ending before the band.

    The locator is therefore the rule, with the *content* of the query located by
    its own distinctive member (`flex: 0 1 auto`) rather than by position, and
    both are asserted below. A locator that silently returns the wrong region is
    the defect this repository has recorded seven times; the two assertions after
    this one are what stop that recurring quietly.
    """
    rule = CSS.index(".detail-actions .btn {")
    starts = [m.start() for m in re.finditer(r"@media[^{]*\{", CSS[:rule])]
    assert starts, "the rule must live inside a media query"
    start = starts[-1]
    after = [m.start() for m in re.finditer(r"@media[^{]*\{", CSS[rule:])]
    end = rule + after[0] if after else len(CSS)
    region = CSS[start:end]
    assert ".detail-actions .btn {" in region, (
        "the located region does not contain the rule it was built around; this "
        "locator is wrong, not the stylesheet")
    return region


class DetailActionRowFlexTests(unittest.TestCase):
    def test_the_narrow_band_pins_zero_growth_not_just_a_smaller_basis(self):
        band = _narrow_band()
        m = re.search(r"\.detail-actions \.btn \{([^}]*)\}", band, re.S)
        self.assertIsNotNone(m, "the narrow band must still pin the action row")
        body = m.group(1)
        self.assertIn("flex: 0 1 auto", body,
                      "growth is the mechanism: `flex: 1 1 auto` measured "
                      "IDENTICALLY bad, because flex-grow hands a lone wrapped "
                      "item every free pixel on its line")

    def test_the_rule_is_scoped_to_the_detail_row_and_not_to_every_button(self):
        band = _narrow_band()
        # Scoping: THIS rule must not be `.btn { flex: … }`, which would
        # redistribute every button row in the app — the modal footer's, the
        # first-scan actions', the toasts'. Those other rules already exist in
        # this band and predate the task (`.first-scan-actions .btn`,
        # `.modal-foot .btn`), so the claim is about *this* declaration, found by
        # its own value rather than by counting selectors that were never mine.
        #
        # My first version asserted the band contains no unscoped `.btn { flex:`
        # at all and failed against three pre-existing rules. That is the 1.7
        # class inverted: a scope check that can only ever fail describes the
        # file, not the change.
        self.assertEqual(
            len(re.findall(r"\.detail-actions \.btn \{ flex: 0 1 auto; \}", band)), 1,
            "the fix must appear once, scoped to `.detail-actions .btn`")
        self.assertNotRegex(
            band, r"(?<!detail-actions )\.btn \{ flex: 0 1 auto; \}",
            "an unscoped `.btn { flex: 0 1 auto; }` would redistribute every "
            "button row in the app, not the detail action row")

    def test_the_shipped_comment_records_that_align_items_was_not_the_fix(self):
        """A comment claiming a cause that measurement has disproved is worse
        than no comment — it sends the next reader to re-apply `align-items`
        and call the task done. 4.7d's own first attempt."""
        self.assertIn("align-items: center", CSS)
        self.assertRegex(
            CSS,
            r"align-items: center.{0,400}?NOT the fix",
            "the stylesheet must record that align-items was tried and measured "
            "to make no difference, so nobody re-applies it as the fix")

    def test_the_defect_is_stated_with_its_measurement(self):
        """The number the fix is about, kept in the file. A comment that says
        'the destructive button stretched' without saying what it measured to
        is a claim; 358px in a 358px row is a fact someone can check."""
        self.assertRegex(CSS, r"358x44 in a 358px row")


if __name__ == "__main__":
    unittest.main()