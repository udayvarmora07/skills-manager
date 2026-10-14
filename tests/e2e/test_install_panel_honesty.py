"""6.3d — the browser falsifier for 6.3c's honesty half.

6.3c rebound the registry panel's loading sentence from the app-wide `busy`
flag to the registry panel's own `install.reading`, and asserted the binding as
a SOURCE contract because this suite had no way to get a selected skill in
front of a held request. It said so in the test's own docstring, and left the
sentence to stand. This file is the other half: the defect is now stated in a
browser, with the app genuinely busy on something that is not a registry read.

THE QUESTION

    While an action that is NOT a registry read is in flight, does the Install
    panel claim the app is reading a registry?

Under the old binding the answer was yes, for every action in the product: a
skill toggle set `busy`, and `busy` printed "Reading <source>…" in a panel
that had made no request. RULES #12 — the UI states observed facts.

HOW THE ROW IS SELECTED, AND WHY IT IS THE KEYBOARD CONTRACT

`test_row_keys.py` already proves that `j` then `Enter` selects a Library row,
and this suite reuses that rather than inventing a click target — a click
target is a second, weaker contract that can drift away from the one the branch
depends on. Two measured facts about that journey, both from 6.3c's exit and
neither re-derived here:

  * the row is `.skilllist > li[data-skill-key]` — NOT `.skilllist li`, whose
    first match is the batch-selection hint and whose second is the skeleton.
  * row 0 on the dev seed is `global/.hidden-skill`, a Malformed hidden skill
    whose detail pane renders no `.detail-actions` at all, so `j`+`Enter` must
    walk past it. The walk below stops at the first row that actually offers
    the verb, and FAILS if no row does — it does not skip, because a skip here
    would be a silently-empty falsifier for the one claim this file exists to
    make.

THE HOLD COVERS BOTH VERBS, and the reason is not tidiness

The verb on a row is "Disable" or "Enable" depending on that skill's observed
state, so the endpoint is `/api/skills/<name>/disable?scope=…` on the first
pass and `/enable?…` on the next. A test written against one of them passes
once and then fails on the second run against the same seeded server, which is
how a falsifier stops falsifying without anybody changing the product. The
hold matches on the `?scope=` query, which `toggleSkillState` (`app.js:4817`)
always appends, so it holds the toggle endpoint and not some other read.

WHAT MAKES THIS NOT VACUOUS

An assertion that the panel shows no `Reading` line is satisfied by a click
that never happened, a row that was never selected, or a hold that never
matched. So the file also asserts, in this order:

  1. a row offering the verb was found, and its detail pane names it;
  2. while the toggle is in flight the app is BUSY — observed as
     `:disabled="busy"` on the very button that started it, read before
     navigating away, because the detail pane does not survive the switch;
  3. the panel shows no `Reading` line;
  4. and the hold was real — after it releases, the skill's state HAS changed,
     which is the only evidence that the request in (2) was this suite's and
     not something else that happened to be slow.

(4) is the one a careful reviewer will ask for, and it is why this file waits
out the hold instead of asserting and closing.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _live_server  # noqa: E402

#: How long a held request stays open. Long enough to select, navigate and
#: assert with margin on a loaded machine; the suite waits it out at the end.
HOLD_MS = 4000

#: Wraps `window.fetch` so a matching request resolves HOLD_MS later. Installed
#: with `add_init_script`, i.e. before any page script runs, so it is in place
#: before the app's first read (the app resolves the global `fetch` at call
#: time — `domain.js:24` — never by capturing it at load).
HOLD_JS = """
window.__hold = window.__hold || [];
const __orig = window.fetch;
window.fetch = function (url, opts) {
  const u = String(url && url.url ? url.url : url);
  const hold = window.__hold.find(function (m) { return u.indexOf(m) !== -1; });
  const p = __orig.apply(this, arguments);
  if (!hold) return p;
  return new Promise(function (resolve, reject) {
    setTimeout(function () { p.then(resolve, reject); }, %d);
  });
};
""" % HOLD_MS

#: The toggle endpoint, matched on the query `toggleSkillState` always adds.
#: Both verbs, because which one fires is the skill's observed state and
#: changes under the test's own feet.
TOGGLE_HOLDS = ("/disable?scope=", "/enable?scope=")

#: The verb on a row, in either state. The label is the only thing that
#: distinguishes them and the label is data, not structure.
VERB = ".detail-actions button:has-text('Disable'), .detail-actions button:has-text('Enable')"


def _has_chromium():
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    try:
        pw = sync_playwright().start()
        try:
            pw.chromium.launch(args=["--no-sandbox"])
        finally:
            pw.stop()
        return True
    except Exception:
        return False


class InstallPanelHonestyInFlight(unittest.TestCase):

    def setUp(self):
        from playwright.sync_api import sync_playwright
        self.url = _live_server.live_server().url
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(args=["--no-sandbox"])
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        self.requests = []
        self.page.on("request", lambda r: self.requests.append(r.url))
        # ALWAYS installed. An earlier draft passed `hold=None` for the test
        # that sets the hold later, so `window.fetch` was never wrapped and
        # `window.__hold` was written into a page with nothing reading it.
        self.page.add_init_script("window.__hold = [];\n%s" % HOLD_JS)
        self.page.goto(self.url, wait_until="domcontentloaded")
        self.page.wait_for_selector("#app", timeout=15000)
        self.page.evaluate("window.__hold = []")

    def tearDown(self):
        self.browser.close()
        self.pw.stop()

    # -- helpers -----------------------------------------------------------

    def _open_library(self):
        self.page.click('.viewtabs button:has-text("Library")')
        self.page.wait_for_selector(".library-bar", timeout=15000)
        self.page.wait_for_timeout(300)

    def _select_a_row_offering_the_toggle(self):
        """`j` then `Enter` until the detail pane offers the verb.

        Fails rather than skips: a skip would leave this file with no
        falsifier at all, which is indistinguishable from the defect being
        absent.
        """
        self._open_library()
        rows = self.page.evaluate(
            "() => document.querySelectorAll('.skilllist > li[data-skill-key]').length")
        for _ in range(min(rows, 10)):
            self.page.keyboard.press("j")
            self.page.wait_for_timeout(120)
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(350)
            if self.page.query_selector(VERB):
                return self.page.inner_text("#view-title").strip()
        self.fail(
            "walked %d Library rows with j+Enter and no detail pane offered "
            "Disable/Enable in .detail-actions — the row selector or the verb's "
            "location moved, and this falsifier is now asserting nothing"
            % min(rows, 10))

    def _reading_lines(self):
        """Every announced sentence inside the registry panel, trimmed."""
        return [el.inner_text().strip() for el in
                self.page.query_selector_all(".install-panel [role=status]")]

    def _state_word(self):
        """'Disable' before the toggle, 'Enable' after: the observed state."""
        button = self.page.query_selector(VERB)
        return button.inner_text().strip() if button else None

    # -- the falsifier -----------------------------------------------------

    @unittest.skipUnless(
        _has_chromium(),
        "Playwright/Chromium unavailable: this claim is only decidable while "
        "a request is in flight, and no source contract can stand in for what "
        "the page says meanwhile")
    def test_a_non_registry_action_in_flight_makes_the_registry_panel_silent(self):
        self.skill = self._select_a_row_offering_the_toggle()
        before = self._state_word()
        self.assertIn(before, ("Disable", "Enable"))

        self.page.evaluate("window.__hold = %r" % (list(TOGGLE_HOLDS),))
        self.page.click(VERB)
        self.page.wait_for_timeout(500)

        # (2) the app really is busy. Read HERE, on the button that started
        # it: the detail pane does not survive the navigation below, so this
        # is the last moment the flag is observable.
        self.assertTrue(
            self.page.query_selector(VERB + "[disabled]") is not None
            or self.page.evaluate(
                """(sel) => { const b = document.querySelector(sel);
                   return !!b && b.hasAttribute('disabled'); }""", VERB),
            "the toggle click did not put the app in its busy state, so every "
            "assertion below would pass about a request that was never sent")

        # (3) the claim. Navigate while busy — the nav rail is deliberately
        # NOT disabled during a request, which is what makes this state
        # reachable at all and is worth its own test (see the note below).
        self.page.click('.navigation-rail button[data-tip="Install"]')
        self.page.wait_for_selector(".install-panel", timeout=10000)
        self.page.wait_for_timeout(200)
        said = self._reading_lines()
        self.assertEqual(
            [], said,
            "a %s of %r is in flight and the registry panel still claims a "
            "registry read: %r — the panel is stating something it has not "
            "observed" % (before, self.skill, said))

        # (4) the hold was real. If the request never went out, (3) is
        # vacuous — and "no Reading line because nothing was happening" is
        # exactly the false pass this file exists to prevent.
        self.page.wait_for_timeout(HOLD_MS + 1500)
        self.assertTrue(
            any("/disable?scope=" in u or "/enable?scope=" in u
                for u in self.requests),
            "no toggle request was ever issued — the hold never matched and "
            "the silence asserted above was the silence of an app doing "
            "nothing: %r" % (self.requests[-5:],))

        self.page.click('.navigation-rail button[data-tip="Library"]')
        self.page.wait_for_selector(".library-bar", timeout=10000)
        self.page.wait_for_timeout(400)
        self._open_library()
        self._select_a_row_offering_the_toggle()
        self.assertNotEqual(
            before, self._state_word(),
            "the request was issued but the skill's observed state is "
            "unchanged, so the 'in flight' window this test measured was not "
            "the toggle's")


if __name__ == "__main__":
    unittest.main()