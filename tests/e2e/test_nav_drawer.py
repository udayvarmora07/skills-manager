"""The phone navigation drawer, measured on the running app.

Why this file exists
--------------------
Task 2.1e2.  Below 761px the navigation rail was a 114px-tall horizontal
scrolling strip holding 908px of buttons in a 390px window: **3 of the 8
destinations were on screen, 5 were not**, and `elementFromPoint` at the centre
of every off-screen button returned nothing.  It was measured green only in the
sense that nothing overflowed — "nothing overflows" and "you can reach
Settings" are different claims.

The drawer is the *same element* as the desktop rail.  That is the design
decision this suite defends: there is no second copy of the navigation to fall
out of sync, and every destination keeps the markup, the handler and the
accessible name it had as a rail button.

Three measurements here are about defects that are real now, and each has a
cause worth naming:

- A drawer that is merely ``translateX(-100%)`` is still focusable and still in
  the accessibility tree.  Closing it has to remove it from *both*, which is
  ``visibility: hidden`` — a layout box alone is not enough.
- The collapsed rail hides its group captions by clipping them to a 1px box.
  ``display: block`` alone un-hides nothing, so the drawer shipped once with
  three invisible captions and one close button stranded in the middle of the
  panel.  Both were caught by looking at a screenshot, not by an assertion.
- Focus returning to the opener is the whole contract of a drawer; a drawer
  that closes into ``document.body`` hands a keyboard user back to the top of
  the document.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_nav_drawer.py
"""

from __future__ import annotations

import os
import unittest

from playwright.sync_api import sync_playwright

#: The band the drawer owns.  The rail is a 56px column at 761 and above.
NARROW = 390
DESKTOP = 1280
#: WCAG 2.2 target floor on coarse pointers; the drawer targets the repo's 44.
TARGET = 44


def _base_url() -> str:
    """The live app, from the isolated dev server (never the real HOME)."""
    return os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")


class NavDrawerTest(unittest.TestCase):
    """One browser for the whole class; the drawer is pure client state."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch()
        cls.page = cls._browser.new_page(viewport={"width": NARROW, "height": 800})
        cls.console_errors: list[str] = []
        cls.failed_requests: list[str] = []
        cls.page.on(
            "console",
            lambda m: cls.console_errors.append(m.text) if m.type == "error" else None,
        )
        cls.page.on("requestfailed", lambda r: cls.failed_requests.append(r.url))
        cls.page.goto(_base_url(), wait_until="networkidle")
        cls.page.wait_for_selector(".nav-drawer-trigger", state="attached")
        cls.page.wait_for_timeout(600)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.page.close()
        cls._browser.close()
        cls._pw.stop()

    # -- helpers ----------------------------------------------------------

    def open_drawer(self) -> None:
        self.page.click(".nav-drawer-trigger")
        self.page.wait_for_timeout(320)

    def close_drawer(self) -> None:
        self.page.click(".drawer-close")
        self.page.wait_for_timeout(320)

    def reset(self) -> None:
        """Return to a known closed state without asserting along the way.

        Deliberately the close button, never the trigger: while the drawer is
        open the topbar is ``inert``, and Chrome drops a programmatic
        ``.click()`` on an inert subtree exactly as it drops a real one. A
        helper that reaches for the trigger can therefore never close the
        drawer, and every later test inherits an open one.
        """
        self.page.evaluate(
            "() => { const d = document.getElementById('nav-drawer');"
            " if (d.classList.contains('open')) d.querySelector('.drawer-close').click(); }"
        )
        self.page.wait_for_timeout(320)

    # -- what replaced the strip -----------------------------------------

    def test_the_phone_no_longer_spends_a_strip_on_navigation(self) -> None:
        """The strip's own cost: 114px of viewport, and 5 of 8 destinations off screen.

        Measured as *flow*, not as a bounding box: a closed drawer is still a
        800px-tall fixed box (that is how it stays on screen when it opens), so
        asserting on its height would be asserting that the drawer does not
        exist. What a reader pays is the gap between the topbar and the list.
        """
        self.reset()
        self.page.click(".viewtabs button:nth-of-type(2)") if False else None
        self.page.evaluate(
            "() => { const b = document.querySelector('.viewtabs button:nth-of-type(2)');"
            " b.click(); }"
        )
        self.page.wait_for_timeout(700)
        self.reset()
        gap = self.page.evaluate(
            """() => {
                 const top = document.querySelector('.topbar').getBoundingClientRect();
                 const pane = document.querySelector('.sidebar.list-pane');
                 const r = pane.getBoundingClientRect();
                 return { topBottom: Math.round(top.bottom), paneTop: Math.round(r.top),
                          paneH: Math.round(r.height) };
               }"""
        )
        self.assertLessEqual(
            gap["paneTop"] - gap["topBottom"], 0,
            "content must start flush under the topbar; the strip cost 114px",
        )
        self.assertGreater(gap["paneH"], 200, "the list must own the phone viewport")
        reachable = self.page.evaluate(
            """() => [...document.querySelectorAll('.viewtabs button')].filter(b => {
                 const r = b.getBoundingClientRect();
                 const el = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
                 return el && b.contains(el);
               }).length"""
        )
        self.assertEqual(
            reachable, 0, "a closed drawer must offer no destination to the pointer"
        )

    def test_every_destination_is_reachable_when_open(self) -> None:
        """The defect this task exists for: 3 of 8, measured with elementFromPoint."""
        self.reset()
        self.open_drawer()
        labels = self.page.evaluate(
            """() => {
              const bad = [];
              for (const b of document.querySelectorAll('.viewtabs button')) {
                const r = b.getBoundingClientRect();
                const el = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
                if (!el || !b.contains(el)) bad.push(b.textContent.trim());
              }
              return bad;
            }"""
        )
        self.assertEqual(labels, [], "every destination must be hit-testable when open")

    def test_the_drawer_is_the_rail_not_a_second_copy(self) -> None:
        """One nav, one id, one set of buttons — a copy is a sync bug waiting."""
        self.reset()
        self.assertEqual(
            self.page.locator(".navigation-rail").count(), 1, "exactly one rail"
        )
        self.assertEqual(
            self.page.locator("nav.viewtabs").count(), 1, "exactly one nav landmark"
        )
        self.assertEqual(
            self.page.locator("#nav-drawer").count(), 1, "the drawer IS the rail"
        )
        self.assertEqual(self.page.locator(".viewtabs button").count(), 8)

    # -- accessibility floor ---------------------------------------------

    def test_a_closed_drawer_is_not_focusable_or_exposed(self) -> None:
        """translateX alone leaves the panel focusable: an off-screen keyboard trap."""
        self.reset()
        state = self.page.evaluate(
            """() => {
              const d = document.getElementById('nav-drawer');
              const cs = getComputedStyle(d);
              d.querySelector('.viewtabs button').focus();
              return {
                visibility: cs.visibility,
                focusStayedOutside: !d.contains(document.activeElement),
              };
            }"""
        )
        self.assertEqual(state["visibility"], "hidden")
        self.assertTrue(
            state["focusStayedOutside"],
            "a closed drawer must not accept focus",
        )

    def test_opening_moves_focus_inside_and_closing_returns_it_to_the_opener(self) -> None:
        self.reset()
        self.open_drawer()
        inside = self.page.evaluate(
            "() => !!document.getElementById('nav-drawer').contains(document.activeElement)"
        )
        self.assertTrue(inside, "focus must move into the drawer when it opens")
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(320)
        after = self.page.evaluate(
            "() => (document.activeElement.className || '') + '|' +"
            " (document.activeElement.getAttribute('aria-label') || '')"
        )
        self.assertIn("nav-drawer-trigger", after, "focus must return to the opener")

    def test_tab_wraps_at_both_ends(self) -> None:
        """A drawer that leaks Tab into the page behind it is not a trap."""
        self.reset()
        self.open_drawer()
        self.page.keyboard.press("Shift+Tab")
        self.page.wait_for_timeout(120)
        self.assertTrue(
            self.page.evaluate(
                "() => document.getElementById('nav-drawer').contains(document.activeElement)"
            ),
            "Shift+Tab from the first control must wrap to the last, not leave the drawer",
        )
        for _ in range(30):
            self.page.keyboard.press("Tab")
        self.page.wait_for_timeout(120)
        self.assertTrue(
            self.page.evaluate(
                "() => document.getElementById('nav-drawer').contains(document.activeElement)"
            ),
            "Tab must never escape an open drawer",
        )

    def test_the_background_is_inert_while_open(self) -> None:
        self.reset()
        self.open_drawer()
        for selector in (".topbar", ".detail", ".statusbar", ".sidebar.list-pane"):
            self.assertTrue(
                self.page.evaluate(f"() => document.querySelector('{selector}').hasAttribute('inert')"),
                f"{selector} must be inert while the drawer is open",
            )
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(320)
        self.assertFalse(
            self.page.evaluate("() => document.querySelector('.topbar').hasAttribute('inert')"),
            "inert must be released when the drawer closes",
        )

    def test_the_trigger_reports_its_state(self) -> None:
        self.reset()
        self.assertEqual(
            self.page.locator(".nav-drawer-trigger").get_attribute("aria-expanded"), "false"
        )
        self.open_drawer()
        self.assertEqual(
            self.page.locator(".nav-drawer-trigger").get_attribute("aria-expanded"), "true"
        )
        self.assertEqual(
            self.page.locator(".nav-drawer-trigger").get_attribute("aria-controls"), "nav-drawer"
        )

    # -- the drawer carries what the phone used to hide -------------------

    def test_scope_and_context_travel_into_the_drawer(self) -> None:
        """Decision recorded in STATE.md: the phone keeps one disclosure, not two."""
        self.reset()
        self.open_drawer()
        for selector, label in (
            ("#compact-controls .scope-trigger", "scope switcher"),
            ("#compact-controls .budgetbar", "context meter"),
        ):
            # "display is not none" rather than a specific value: these are
            # flex rows on purpose, and pinning `block` would fail a correct
            # stylesheet the moment someone made one of them a grid.
            self.assertGreater(
                self.page.evaluate(
                    f"() => document.querySelector('{selector}').getBoundingClientRect().height"
                ),
                0,
                f"the {label} must be visible inside the drawer",
            )
        self.assertFalse(
            self.page.evaluate(
                "() => document.querySelector('.mobile-controls-toggle')"
                " && getComputedStyle(document.querySelector('.mobile-controls-toggle')).display !== 'none'"
            ),
            "the separate scope-controls disclosure must not also show on a phone",
        )

    def test_quick_actions_are_reachable_on_a_phone(self) -> None:
        """They were display:none at every phone width before this task."""
        self.reset()
        self.open_drawer()
        self.page.click(".viewtabs button:nth-of-type(2)")
        self.page.wait_for_timeout(700)
        self.open_drawer()
        visible = self.page.evaluate(
            """() => [...document.querySelectorAll('.rail-action')]
                 .filter(b => b.getBoundingClientRect().width > 0).length"""
        )
        self.assertGreaterEqual(visible, 2, "New skill / Add from folder must be reachable")

    def test_group_captions_are_actually_painted(self) -> None:
        """display:block does not undo the rail's 1px sr-only clipping."""
        self.reset()
        self.open_drawer()
        rows = self.page.evaluate(
            """() => [...document.querySelectorAll('.nav-group-label')].map(el => {
                 const r = el.getBoundingClientRect();
                 const style = getComputedStyle(el);
                 return { text: el.textContent.trim(), w: Math.round(r.width),
                          h: Math.round(r.height), clip: style.clipPath };
               })"""
        )
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertGreater(row["w"], 100, f"{row['text']} caption is still clipped")
            self.assertGreater(row["h"], 8, f"{row['text']} caption has no height")

    def test_every_drawer_control_meets_the_touch_target_floor(self) -> None:
        self.reset()
        self.open_drawer()
        short = self.page.evaluate(
            """() => [...document.querySelectorAll('#nav-drawer button, #nav-drawer select')]
                 .filter(el => el.getBoundingClientRect().height > 0)
                 .map(el => ({ t: (el.textContent || el.tagName).trim().slice(0, 24),
                               h: Math.round(el.getBoundingClientRect().height),
                               w: Math.round(el.getBoundingClientRect().width) }))
                 .filter(m => m.h < %d || m.w < %d)"""
            % (TARGET, TARGET)
        )
        self.assertEqual(short, [], "every drawer control must be at least 44x44")

    # -- it must not leak onto the desktop --------------------------------

    def test_the_desktop_rail_is_untouched(self) -> None:
        wide = self._browser.new_page(viewport={"width": DESKTOP, "height": 900})
        wide.goto(_base_url(), wait_until="networkidle")
        wide.wait_for_timeout(500)
        self.assertFalse(
            wide.locator(".nav-drawer-trigger").is_visible(),
            "the drawer trigger is a phone affordance and must not appear at 1280",
        )
        self.assertEqual(
            wide.evaluate("() => Math.round(document.querySelector('.navigation-rail').getBoundingClientRect().width)"),
            56,
            "the desktop rail keeps its declared 56px",
        )
        wide.close()

    # -- no regressions in the page itself --------------------------------

    def test_no_console_errors_failed_requests_or_overflow(self) -> None:
        self.reset()
        for width in (NARROW, 768, DESKTOP):
            self.page.set_viewport_size({"width": width, "height": 800})
            self.page.wait_for_timeout(350)
            overflow = self.page.evaluate(
                "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            self.assertEqual(overflow, 0, f"horizontal overflow at {width}px")
        self.page.set_viewport_size({"width": NARROW, "height": 800})
        self.page.wait_for_timeout(350)
        self.assertEqual(self.console_errors, [], "console errors during the drawer run")
        self.assertEqual(self.failed_requests, [], "failed requests during the drawer run")


if __name__ == "__main__":
    unittest.main()