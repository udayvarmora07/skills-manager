"""6.3c — the LOADING half of the 6.3 audit.

6.3 fixed the error half: a read that failed must not render the sentence that
claims emptiness. Its twin was left open, and this file closes it by asking the
same question of the state a view is in BEFORE the answer arrives:

    is there a moment where this view shows nothing and says nothing?

MEASURED ON ARRIVAL (this tree, 2026-10-14 — do not re-derive, do re-measure)

* `class="skeleton"` appears 13 times in `index.html`. On arrival **one** of
  the thirteen (`index.html:563`, the Library list) carried the full pattern
  2.3 settled: `role="status"`, `aria-busy="true"`, and an `sr-only` sentence
  — "Loading the observed skill inventory…". The other twelve were bare
  `<div class="skel-row">` shimmer with **no role and no text**: a sighted
  reader sees "waiting", a screen-reader user is told nothing at all, and the
  empty branch they are NOT being shown is the only sentence in the file that
  would have explained the wait. Three more carried `role="status"` with no
  text, which is a live region that announces nothing when it appears.
* The Install panel's loading sentence read `v-if="busy"`. `busy` is the
  app-wide flag every action sets, so that panel stated something it had not
  observed: a skill toggle anywhere printed "Reading <registry>…" here. It is
  the loading half of the defect 6.3 fixed for errors, and RULES #12 is the
  rule it breaks.

HOW A LOADING STATE IS REACHED HERE

Not by sleeping. A Playwright route handler runs on the dispatcher's thread, so
a `time.sleep` inside it blocks the very thread that has to ask the DOM a
question — measured: with a 2s sleep in the handler the skeleton was already
gone by the time the assertion ran. The hold is installed INSIDE the page, by
`add_init_script` wrapping `window.fetch` so a matching read resolves late
while the browser thread stays free. Three probes and one rewrite to get here;
the shape is the one every assertion below uses.

WHAT IS ASSERTED, AND WHAT IS NOT

* The DOM claims (1-3) are asked of the live page while the read is in flight.
* The exhaustive claim (4-5) is a SOURCE contract over all thirteen skeletons
  and the four text hints, because a browser cannot hold thirteen reads open
  at once and a contract that only covers the two it could is a contract about
  the two. The two halves are named rather than blended.
* Not asserted: that any AT actually speaks these strings. There is no screen
  reader in this suite, and claiming otherwise would be the thirteenth recorded
  gate reporting about a path it cannot see.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _live_server  # noqa: E402

TEMPLATE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "skillsmgr", "webui", "index.html")

#: Wraps `window.fetch` so a read whose URL contains one of `window.__hold`
#: resolves `HOLD_MS` later. Injected before any page script runs, so it is in
#: place before the app's first read — the app resolves the global `fetch` at
#: call time (`domain.js:24`), never by capturing it at load.
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
""" % 4000


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


def _template():
    with open(TEMPLATE, encoding="utf-8") as handle:
        return handle.read()


class SkeletonSourceContracts(unittest.TestCase):
    """Every loading skeleton announces itself and names what it is reading.

    A source contract, deliberately: it is the only way to hold thirteen reads
    open at once, and the branch has been bitten by the alternative — a check
    that covers only what it could reach reads as coverage of all of it.
    """

    def setUp(self):
        # Locator lesson, this branch's ninth and now tenth: `<div class=
        # "skeleton"` matched 2 of 13, because eight of them carry a `v-if`
        # BEFORE the class and the rest are `<li>`. Read the class, not the
        # tag name and not the attribute order.
        self.skeletons = re.findall(
            r'<[a-z]+ [^>]*class="skeleton"[^>]*>', _template())

    def test_there_is_a_skeleton_to_audit(self):
        # Without this, a markup rewrite that renames the class passes both
        # assertions below by finding nothing to check.
        self.assertGreaterEqual(
            len(self.skeletons), 13,
            "the skeleton class went from 13 occurrences to %d — either the "
            "loading states moved or this contract is reading a tree it no "
            "longer describes" % len(self.skeletons))

    def test_every_skeleton_declares_itself_a_live_region(self):
        silent = [tag for tag in self.skeletons if 'role="status"' not in tag]
        self.assertEqual(
            [], silent,
            "these loading states say nothing to a screen reader: %r" % silent)

    def test_every_skeleton_is_marked_busy(self):
        # `aria-busy` is what tells assistive tech the region is still being
        # filled, so a region that never stops being busy never re-announces.
        silent = [tag for tag in self.skeletons if 'aria-busy="true"' not in tag]
        self.assertEqual([], silent, "skeleton without aria-busy: %r" % silent)

    def test_every_skeleton_names_what_it_is_reading(self):
        """The half a role alone cannot do: the region has to have something
        to say. A `role="status"` element containing only shimmer announces
        nothing at all — the defect, not the fix."""
        template = _template()
        silent = []
        for tag in self.skeletons:
            start = template.index(tag)
            body = template[start:start + 400]
            if 'class="sr-only"' not in body:
                silent.append(tag)
        self.assertEqual(
            [], silent,
            "these skeletons are live regions with nothing in them: %r" % silent)


    # -- 2. the honesty half, at the binding --------------------------------

    def test_the_install_panel_is_not_told_by_the_global_busy_flag(self):
        """The defect 6.3c was opened for, asserted where it is decidable.

        `busy` is set by every action in the app, so binding the registry
        panel's "Reading <source>…" sentence to it made this panel state
        something it had not observed — a skill toggle anywhere printed a
        registry read here. RULES #12: the UI states observed facts.

        THIS IS A SOURCE CONTRACT, and the reason is recorded rather than
        glossed: the honest browser falsifier is "hold a NON-registry action
        open and read the panel", and driving one needs a selected skill, and
        the row control that selects one was not established inside this
        suite's box (four locators were wrong before this file was green —
        `.skilllist li` matches the batch-selection hint, `.row-select` opens
        no detail pane, and the toggle button sits in `.detail-actions`, not
        `.detail-head`). The control for 3 is the DOM half that DOES run in a
        browser, so a panel that never renders the sentence is still caught.
        A mutation — rebinding the sentence to `busy` — fails both halves.
        """
        template = _template()
        start = template.index('class="install-panel"')
        body = template[start:start + 4000]
        self.assertIn('v-if="install.reading"', body,
                      "the registry panel's loading sentence is no longer bound "
                      "to the read that is in flight")
        self.assertNotIn(
            'v-if="busy" class="hint"', body,
            "the registry panel's loading sentence is bound to the app-wide "
            "`busy` flag again, so any action in the product makes this panel "
            "claim a registry read it never made")
        self.assertIn(
            'role="status"', body,
            "the loading sentence is not announced, while the stale-cache "
            "banner and the precondition line beside it both are")


class LoadingHintSourceContracts(unittest.TestCase):
    """The loading sentences that were real text and still silent."""

    HINT = re.compile(
        r'<p[^>]*class="hint"[^>]*>\s*(?:Loading|Reading)[^<]*</p>')

    def setUp(self):
        self.hints = self.HINT.findall(_template())

    def test_there_are_loading_hints_to_audit(self):
        self.assertGreaterEqual(
            len(self.hints), 4,
            "found %d loading hints, expected at least 4 — the pattern or the "
            "markup moved" % len(self.hints))

    def test_every_loading_hint_is_announced(self):
        silent = [h for h in self.hints if 'role="status"' not in h]
        self.assertEqual(
            [], silent,
            "these sentences name a wait and are never announced: %r" % silent)


@unittest.skipUnless(_has_chromium(),
                     "Playwright/Chromium unavailable: a loading state exists "
                     "only between a click and a response, and no source "
                     "contract can stand in for what the page says meanwhile")
class LoadingStatesInFlight(unittest.TestCase):
    """What the page says while the answer is still on its way."""

    def setUp(self):
        self.url = _live_server.live_server().url

    def _page(self, hold=()):
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        # ALWAYS installed, never conditionally. The first version passed
        # `hold=None` for the two tests that set the hold later, so
        # `window.fetch` was never wrapped and `window.__hold` was written into
        # a page with nothing reading it — assertion 3 reported "the panel does
        # not say it is reading" about a harness that could not have held a
        # read open. The tenth instance of this branch's own lesson, and the
        # second in this file.
        page.add_init_script("window.__hold = %r;\n%s" % (list(hold), HOLD_JS))
        page.goto(self.url, wait_until="domcontentloaded")
        page.wait_for_selector("#app", timeout=15000)
        page.evaluate("window.__hold = []")
        return pw, browser, page

    def _reading_lines(self, page):
        """Every announced sentence in the registry panel, trimmed."""
        return [el.inner_text().strip() for el in
                page.query_selector_all(".install-panel [role=status]")]

    # -- 1. the loading state is perceivable --------------------------------

    def test_a_read_in_flight_says_what_it_is_reading(self):
        """The Overview's mount-time history read, held open.

        This is the general shape: the app has a sentence for this wait, and
        it is inside a live region, so the reader who cannot see the shimmer
        is still told.
        """
        pw, browser, page = self._page(hold=["/api/history"])
        try:
            page.wait_for_selector(".hint[role=status]", timeout=8000)
            said = page.query_selector(".hint[role=status]").inner_text().strip()
            self.assertTrue(said, "the loading region is live and says nothing")
            self.assertIn("recent activity", said.lower())
            # The control: the sentence belongs to the wait, not to the view.
            page.wait_for_timeout(5000)
            self.assertIsNone(
                page.query_selector(".hint[role=status]"),
                "the loading sentence is still on screen five seconds after the "
                "read finished, so it is not describing a wait")
        finally:
            browser.close()
            pw.stop()

    # -- 3. the control for 2 ----------------------------------------------

    def test_a_registry_read_in_flight_does_say_so(self):
        """Without this, 2 passes on a hint that never renders at all."""
        pw, browser, page = self._page()
        try:
            page.click('.navigation-rail button[data-tip="Install"]')
            page.wait_for_selector(".install-panel", timeout=10000)
            page.evaluate("window.__hold = ['/api/install']")
            page.click('.install-panel button:has-text("Read")')
            page.wait_for_timeout(700)
            said = self._reading_lines(page)
            self.assertTrue(
                said, "the registry read is in flight and the panel does not "
                      "say it is reading — assertion 2 would pass on a hint "
                      "that never appears")
            self.assertTrue(
                any(line.lower().startswith("reading") for line in said),
                "the loading sentence does not name the read: %r" % said)
            page.wait_for_timeout(5000)
            self.assertEqual(
                [], self._reading_lines(page),
                "the panel still claims to be reading after the read finished")
        finally:
            browser.close()
            pw.stop()


if __name__ == "__main__":
    unittest.main()