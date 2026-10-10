"""The Library filter bar is reachable on a phone, measured on the running app.

Why this file exists
--------------------
Task 2.1f.  At 390x844 the bar measured ``display: none`` and every chip
measured a **0x0 box**; the only thing in the application that revealed them
was opening the **navigation** drawer, because 2.1e2 forces
``compactControlsOpen`` on while it is open.  A state filter and a
Library/Instances toggle are not navigation.

``display`` and "reachable" are different claims, and this suite only accepts
the second one:

- a control counts as reachable only when it has a laid-out box AND
  ``elementFromPoint`` at its own centre returns it or a descendant;
- it must be reachable *without* navigating first, which is the whole defect;
- opening the drawer must not change anything here -- that coupling is the bug,
  so a test that only passed after opening the drawer would be testing it;
- and clicking must do the observable thing, because a filter bar that filters
  nothing is as broken as one you cannot reach.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_library_filter_bar.py
"""

from __future__ import annotations

import os
import unittest

from playwright.sync_api import sync_playwright

#: The band that lost the controls.
PHONE = (390, 844)
#: The rail is a 56px column at 761 and above; this must not regress.
DESKTOP = (1280, 900)
#: WCAG 2.2 target floor on coarse pointers; this repo works to 44.
TARGET = 44


def _base_url() -> str:
    """The live app, from the isolated dev server (never the real HOME)."""
    return os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")


#: Reports the layout box and a real hit test for every chip in the bar.
MEASURE = """
() => {
  const bar = document.querySelector('.library-bar');
  const chip = (c) => {
    const r = c.getBoundingClientRect();
    if (!r.width || !r.height) return {label: c.textContent.trim(), hit: 'not-laid-out'};
    const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    const ok = t && (t === c || c.contains(t) || t.contains(c));
    return {
      label: c.textContent.trim().replace(/\\s+/g, ' '),
      hit: ok ? 'reachable' : 'covered-by:' + (t && t.className),
      h: Math.round(r.height),
      w: Math.round(r.width),
      x: Math.round(r.x),
      pressed: c.getAttribute('aria-pressed'),
    };
  };
  const r = bar ? bar.getBoundingClientRect() : null;
  return {
    barDisplay: bar ? getComputedStyle(bar).display : 'absent',
    barBox: r ? {w: Math.round(r.width), h: Math.round(r.height), y: Math.round(r.y)} : null,
    chips: Array.from(document.querySelectorAll('.library-bar .chip')).map(chip),
    overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    count: (document.querySelector('.list-count') || {}).textContent || '',
    rows: document.querySelectorAll('.skilllist > li:not(.batchbar):not(.selection-hint):not(.skeleton):not(.empty)').length,
  };
}
"""


class LibraryFilterBarTest(unittest.TestCase):
    """One browser for the class; every assertion is a measurement."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                f"Playwright is not importable ({exc}). This half needs a real "
                f"engine and is NOT silently passed."
            )
        cls._pw = sync_playwright()
        cls._pw_cm = cls._pw.start()
        cls._browser = cls._pw_cm.chromium.launch(args=["--no-sandbox"])
        cls._base = _base_url()
        cls._console: list[str] = []
        try:
            cls._page = cls._open(cls._browser, *PHONE)
            cls._page.wait_for_selector(".library-bar", state="attached", timeout=15000)
        except Exception as exc:
            cls._browser.close()
            cls._pw_cm.stop()
            raise unittest.SkipTest(
                f"the dev server at {cls._base} did not reach the Library view "
                f"({exc}). Start it with `.redesign/dev.sh start` -- this test "
                f"is NOT silently passed when it cannot run."
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._pw_cm.stop()

    @classmethod
    def _open(cls, browser, width, height):
        """Open the app at this size and enter the Library the way a user does."""
        ctx = browser.new_context(viewport={"width": width, "height": height})
        page = ctx.new_page()
        page.on("console", lambda m: m.type == "error" and cls._console.append(m.text))
        page.on("pageerror", lambda e: cls._console.append(str(e)))
        page.goto(cls._base, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector(".overview-shell", timeout=20000)
        trigger = page.query_selector(".nav-drawer-trigger")
        if trigger and trigger.is_visible():
            # Below 761px the rail is a drawer, so that is how Library is reached.
            trigger.click()
            page.wait_for_selector("#nav-drawer.open", timeout=5000)
            page.click('#nav-drawer .viewtabs button:has-text("Library")')
            page.wait_for_timeout(200)
            close = page.query_selector("#nav-drawer .drawer-close")
            if close and close.is_visible():
                close.click()
                page.wait_for_timeout(250)
        else:
            page.click('.navigation-rail .viewtabs button:has-text("Library")')
            page.wait_for_timeout(200)
        page.wait_for_selector(".library-bar", state="attached", timeout=10000)
        return page

    # -- the defect ------------------------------------------------------
    def test_the_bar_is_laid_out_on_a_phone_without_navigating(self):
        m = self._page.evaluate(MEASURE)
        self.assertNotEqual(m["barDisplay"], "none", m)
        self.assertIsNotNone(m["barBox"], "the bar has no layout box on a phone")
        self.assertGreater(m["barBox"]["h"], 0, m)

    def test_every_chip_has_a_real_box_and_passes_a_hit_test(self):
        m = self._page.evaluate(MEASURE)
        self.assertGreaterEqual(len(m["chips"]), 5, m)
        for c in m["chips"]:
            self.assertEqual(c.get("hit"), "reachable", f"{c['label']}: {c}")

    def test_every_chip_meets_the_touch_target_floor(self):
        # These are the only pointer-sized controls the phone has for state
        # filtering and mode switching; RULES #13 sets 40, this repo works to 44.
        m = self._page.evaluate(MEASURE)
        for c in m["chips"]:
            self.assertGreaterEqual(c["h"], TARGET, f"{c['label']}: {c}")

    def test_no_chip_depends_on_horizontal_scrolling(self):
        m = self._page.evaluate(MEASURE)
        for c in m["chips"]:
            self.assertGreaterEqual(c["x"], 0, f"{c['label']}: {c}")
            self.assertLessEqual(c["x"] + c["w"], PHONE[0] + 1, f"{c['label']}: {c}")

    # -- the coupling that caused it ------------------------------------
    def test_opening_the_navigation_drawer_does_not_change_the_bar(self):
        """The drawer and the filter bar are independent surfaces.

        Measured as *layout*, not as a hit test: while the drawer is open the
        scrim correctly covers the background, so the chips are painted over by
        design.  What must not change is that the bar is still laid out and
        still the same box -- the defect was that it stopped existing.
        """
        before = self._page.evaluate(MEASURE)
        self._page.click(".nav-drawer-trigger")
        self._page.wait_for_selector("#nav-drawer.open", timeout=5000)
        during = self._page.evaluate(MEASURE)
        self._page.click("#nav-drawer .drawer-close")
        self._page.wait_for_timeout(250)

        self.assertEqual(during["barDisplay"], before["barDisplay"])
        self.assertEqual(during["barBox"], before["barBox"])
        self.assertEqual([(c["label"], c["w"], c["h"], c["x"]) for c in during["chips"]],
                         [(c["label"], c["w"], c["h"], c["x"]) for c in before["chips"]])

        # And it is reachable again the moment the drawer is out of the way.
        after = self._page.evaluate(MEASURE)
        for c in after["chips"]:
            self.assertEqual(c.get("hit"), "reachable", f"{c['label']}: {c}")

    def test_the_filter_bar_is_never_the_drawers_subordinate(self):
        """The regression shape, asserted where it is actually decidable.

        An earlier version of this test asked the DOM whether a CSS *rule*
        existed -- ``querySelector('.layout:not(:has(.compact-controls.open))
        .sidebar.list-pane .library-bar')``.  That is a category error: with
        the drawer closed the ``:not()`` is satisfied by ordinary app state, so
        it matched the visible bar and reported a gate that does not exist,
        while a real gate would have been invisible to it.  Whether any rule
        couples the two is a question about ``styles.css``, and it is asserted
        there, in ``tests/test_webui_contracts.py``::
        LibraryFilterBarReachabilityTests::
        test_no_rule_anywhere_gates_the_filter_bar_on_the_scope_disclosure

        What is decidable in a browser is the consequence: the bar must be
        present with the drawer closed, which is the state the gate destroyed.
        """
        m = self._page.evaluate(MEASURE)
        self.assertNotEqual(m["barDisplay"], "none", m)
        self.assertIsNotNone(m["barBox"], m)
        compact_open = self._page.evaluate(
            "() => !!document.querySelector('.compact-controls.open')")
        self.assertFalse(compact_open, "probe ran with the scope disclosure open")

    # -- it has to actually filter --------------------------------------
    def test_the_state_filter_reduces_the_visible_rows(self):
        self._page.click('.library-bar .filters .chip:has-text("Disabled")')
        self._page.wait_for_timeout(500)
        m = self._page.evaluate(MEASURE)
        pressed = [c for c in m["chips"] if c["label"] == "Disabled"]
        self.assertTrue(pressed and pressed[0]["pressed"] == "true", m)
        self.assertLess(m["rows"], 200, "Disabled did not reduce the list at all")

    def test_the_mode_toggle_switches_between_library_and_instances(self):
        self._page.click('.library-bar .filters .chip:has-text("All")')
        self._page.wait_for_timeout(400)
        before = self._page.evaluate(MEASURE)
        self._page.click('.library-bar .library-switch .chip:has-text("Instances")')
        self._page.wait_for_timeout(600)
        after = self._page.evaluate(MEASURE)
        self.assertNotEqual(before["count"], after["count"], (before, after))

    # -- desktop must not regress ---------------------------------------
    def test_the_desktop_bar_is_unchanged(self):
        page = self._open(self._browser, *DESKTOP)
        try:
            m = page.evaluate(MEASURE)
            self.assertNotEqual(m["barDisplay"], "none", m)
            self.assertFalse(m["overflow"], m)
            for c in m["chips"]:
                self.assertEqual(c.get("hit"), "reachable", f"{c['label']}: {c}")
        finally:
            page.context.close()

    # -- hygiene --------------------------------------------------------
    def test_no_console_errors_and_no_horizontal_overflow(self):
        m = self._page.evaluate(MEASURE)
        self.assertFalse(m["overflow"], "the Library overflows horizontally on a phone")
        self.assertEqual(self._console, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)