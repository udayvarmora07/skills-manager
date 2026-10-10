"""The 56px navigation rail, measured on the running app.

Why this file exists
--------------------
Task 2.1e. ``--rail-w: 240px`` was declared in the token layer and read by
nothing: the three grid tracks hard-coded ``220px``, and the tablet band
hard-coded ``136px``.  So the rail's width was emergent in two places while the
one place a reader would look carried a number that was not true.  These
assert the rendered track against the token, at both widths.

The second half is the part that matters more.  Collapsing a labelled column to
an icon column is only a layout change if the labels come back somewhere; if the
label was a bare text node that could not survive the collapse, then every
button in the rail loses its accessible name and the whole app becomes a column
of unlabelled glyphs.  That is not a styling regression, it is a silent one, and
no stylesheet assertion can catch it -- so the name is checked the way a screen
reader gets it.

Two measurements here are about defects that were real and are now fixed, and
both are worth keeping because the cause is not obvious from the rule:

- An overlay painted *outside* its rail (``overflow: visible`` is what lets the
  tooltip and the panel escape at all) also adds to the document scroll width.
  At 390px that was 117px of horizontal overflow from one ``::after``.
- A 44px icon button with a visible label does not clip its own text: the
  disclosure's words wrapped out of the rail and painted at x < 0.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_rail.py
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEBUI = ROOT / "skillsmgr" / "webui"

#: The width DESIGN.md §E specifies for the collapsed rail.
RAIL_W = 56
#: Every rail control, in every state.  The floor is 40px on coarse pointers.
TARGET = 44


def _base_url() -> str:
    """The live app, from the isolated dev server (never the real HOME)."""
    return os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")


def _token_value(css: str, name: str) -> str:
    """Read one custom property out of the raw stylesheet.

    Deliberately not a regex over the whole file for the number: the assertion
    this backs is "the token exists and holds the declared width", and a caller
    that wanted the resolved value already has ``getComputedStyle``.
    """
    marker = "%s:" % name
    idx = css.find(marker)
    if idx < 0:
        raise AssertionError("token %s is not declared in styles.css" % name)
    line = css[idx + len(marker):].split(";", 1)[0]
    return line.strip()


class RailWidthTests(unittest.TestCase):
    """The collapsed track, rendered."""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                f"Playwright is not importable ({exc}). This needs a real "
                f"engine and is NOT silently passed."
            )
        cls._pw = sync_playwright()
        cls._pw_cm = cls._pw.start()
        cls._browser = cls._pw_cm.chromium.launch(args=["--no-sandbox"])
        cls._base = _base_url()
        cls._page = cls._browser.new_page(viewport={"width": 1280, "height": 900})
        cls._console_errors: list[str] = []
        cls._page.on("console", lambda m: m.type == "error" and cls._console_errors.append(m.text))
        cls._page.on("pageerror", lambda e: cls._console_errors.append(str(e)))
        try:
            cls._page.goto(cls._base, wait_until="domcontentloaded", timeout=20000)
            cls._page.wait_for_selector(".navigation-rail .viewtabs button", timeout=15000)
        except Exception as exc:
            cls._browser.close()
            cls._pw_cm.stop()
            raise unittest.SkipTest(
                f"the dev server at {cls._base} did not render the rail ({exc}). "
                f"Start it with `.redesign/dev.sh start` — this test is NOT "
                f"silently passed when it cannot run."
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._pw_cm.stop()

    # -- helpers ---------------------------------------------------------
    def _rail_box(self) -> dict:
        return self._page.eval_on_selector(
            ".navigation-rail",
            "e => { const r = e.getBoundingClientRect();"
            " return {w: r.width, h: r.height, left: r.left, right: r.right}; }",
        )

    def _first_grid_track(self) -> float:
        """The resolved width of the layout's first column.

        Read from the computed value rather than from ``.navigation-rail``'s
        own box: the rail is a grid ITEM here, and the claim worth pinning is
        that the track it sits in is the declared width.
        """
        tracks = self._page.eval_on_selector(
            ".layout", "e => getComputedStyle(e).gridTemplateColumns"
        )
        return float(tracks.split(" ")[0].replace("px", ""))

    def _nav(self, js: str):
        return self._page.evaluate(js)

    # -- the width -------------------------------------------------------
    def test_the_rail_is_the_declared_56px_at_1280(self):
        self.assertEqual(round(self._rail_box()["w"]), RAIL_W)

    def test_the_first_grid_track_is_the_rail_and_nothing_else(self):
        self.assertEqual(round(self._first_grid_track()), RAIL_W)

    def test_the_tablet_band_collapses_to_the_same_width_not_a_second_number(self):
        """It used to be 136px here — a second hard-coded rail width, so the
        token was decorative and there were two truths."""
        self._page.set_viewport_size({"width": 900, "height": 900})
        try:
            self.assertEqual(round(self._first_grid_track()), RAIL_W)
            self.assertEqual(round(self._rail_box()["w"]), RAIL_W)
        finally:
            self._page.set_viewport_size({"width": 1280, "height": 900})

    def test_the_token_and_the_rendered_width_agree(self):
        """The regression this task was raised for: the token held 240px and
        the track held 220px, and both were 'the rail width'."""
        css = (WEBUI / "styles.css").read_text(encoding="utf-8")
        self.assertEqual(_token_value(css, "--rail-w"), "%dpx" % RAIL_W)

    # -- what an icon rail must give back --------------------------------
    def test_every_rail_control_keeps_an_accessible_name(self):
        """The load-bearing assertion of this task.

        A label that is ``display:none`` is removed from the accessibility
        tree, and a button whose only text was that label becomes unlabelled.
        So the check is not "there is a label element" but "the label is still
        rendered by the box model", which is the difference between clipped and
        hidden.
        """
        rows = self._nav("""() => [...document.querySelectorAll(
                '.navigation-rail .viewtabs button,'
              + ' .navigation-rail .rail-action,'
              + ' .navigation-rail .mobile-controls-toggle')]
            .map(b => {
              const l = b.querySelector('.nav-label');
              const cs = l ? getComputedStyle(l) : null;
              return {text: l ? l.textContent.trim() : '',
                      tip: b.getAttribute('data-tip') || '',
                      display: cs ? cs.display : 'MISSING'};
            })""")
        self.assertGreaterEqual(len(rows), 9, "found %d rail controls" % len(rows))
        for row in rows:
            self.assertTrue(row["text"], "a rail control has no label text: %r" % row)
            self.assertNotEqual(row["display"], "none",
                                "label %r is display:none, which removes it from the "
                                "accessibility tree" % row["text"])
            self.assertNotEqual(row["display"], "MISSING",
                                "control %r has no .nav-label element" % row["text"])

    def test_every_rail_control_has_a_tooltip_key_matching_its_label(self):
        rows = self._nav("""() => [...document.querySelectorAll('.navigation-rail [data-tip]')]
            .map(b => ({tip: b.getAttribute('data-tip'),
                        label: (b.querySelector('.nav-label') || {}).textContent || ''}))""")
        # 9, not 12: the rail's quick actions are `v-if="view === 'skills'"`
        # and the validate action is `v-if="selectedName"`, so the default
        # Overview renders 8 nav buttons + the disclosure.  Asserting 12 here
        # would have blamed the product for a count I had not derived.
        self.assertGreaterEqual(len(rows), 9)
        for row in rows:
            self.assertTrue(row["tip"].strip(), "an empty data-tip")
            self.assertEqual(row["tip"], row["label"],
                             "the tooltip and the accessible name disagree: %r vs %r"
                             % (row["tip"], row["label"]))

    def test_the_labels_do_not_paint_inside_the_rail(self):
        """Clipped, not merely small: a 1px box is the standard technique, a
        wrapped line 40px tall is the defect the screenshot caught."""
        bad = self._nav("""() => [...document.querySelectorAll(
                '.navigation-rail .viewtabs .nav-label,'
              + ' .navigation-rail .rail-action .nav-label')]
            .map(l => { const r = l.getBoundingClientRect();
                        return {t: l.textContent.trim(), w: r.width, h: r.height}; })
            .filter(r => r.w > 2 || r.h > 2)""")
        self.assertEqual(
            bad, [],
            "these rail labels are painting inside a %dpx column: %r" % (RAIL_W, bad))

    def test_the_tooltip_carries_the_label_and_is_real_content(self):
        content = self._page.eval_on_selector(
            '.navigation-rail .viewtabs button[data-tip]',
            "e => getComputedStyle(e, '::after').content")
        self.assertNotEqual(content, "none",
                            "the tooltip is content:none, so data-tip paints nothing")
        # The computed value is the SUBSTITUTED string, not `attr(data-tip)`.
        # That is the stronger claim: it proves the label reaches the pixels
        # rather than that an attribute is spelled a particular way.
        self.assertEqual(content, '"Overview"')

    def test_every_rail_control_meets_the_44px_target(self):
        small = self._nav("""() => [...document.querySelectorAll(
                '.navigation-rail .viewtabs button,'
              + ' .navigation-rail .rail-action')]
            .map(b => { const r = b.getBoundingClientRect();
                        return {t: (b.querySelector('.nav-label')||{}).textContent,
                                w: r.width, h: r.height}; })
            .filter(r => r.w < %d - 0.5 || r.h < %d - 0.5)""" % (TARGET, TARGET))
        self.assertEqual(small, [], "below the %dpx target: %r" % (TARGET, small))

    # -- the panel -------------------------------------------------------
    def test_the_rail_panel_opens_with_both_the_scope_switcher_and_the_meter(self):
        """One disclosure, everything the 56px column could not hold.  If the
        panel drops either, a datum silently disappeared in this commit."""
        self._page.click(".navigation-rail .mobile-controls-toggle")
        try:
            self._page.wait_for_selector(".compact-controls.open", timeout=5000)
            for sel, what in ((".scope-trigger", "the scope switcher"),
                              (".budgetbar", "the context meter"),
                              (".budgetbar-select", "the context-window control")):
                box = self._page.eval_on_selector(
                    sel, "e => { const r = e.getBoundingClientRect();"
                         " return {w: r.width, h: r.height}; }")
                self.assertGreater(box["w"], 0, "%s is not rendered in the panel" % what)
                self.assertGreater(box["h"], 0, "%s is not rendered in the panel" % what)
        finally:
            self._page.click(".navigation-rail .mobile-controls-toggle")

    def test_the_panel_escapes_the_rail_instead_of_being_clipped_by_it(self):
        """`overflow: visible` on the rail is what lets the panel paint beside
        it — and `overflow-x: visible` beside `overflow-y: auto` computes to
        `auto`, which would clip it.

        The first version of this assertion was a geometry comparison and it
        went GREEN against `overflow: hidden`, i.e. it could not fail.
        `getBoundingClientRect()` returns LAYOUT boxes: clipping is a paint
        operation, so no amount of comparing left edges can see it.  The
        question a reader actually has is "can I reach the thing", so that is
        what is measured — `elementFromPoint` at the panel's own centre.
        """
        self._page.click(".navigation-rail .mobile-controls-toggle")
        try:
            self._page.wait_for_selector(".compact-controls.open", timeout=5000)
            panel = self._page.eval_on_selector(
                ".compact-controls.open",
                "e => { const r = e.getBoundingClientRect();"
                " return {cx: r.left + r.width / 2, cy: r.top + r.height / 2,"
                "         left: r.left, right: r.right}; }")
            rail = self._rail_box()
            viewport = self._page.evaluate("() => window.innerWidth")
            self.assertGreaterEqual(panel["left"], rail["right"] - 0.5,
                                    "the panel overlaps the rail it belongs to")
            self.assertLessEqual(panel["right"], viewport + 0.5,
                                 "the panel runs past the viewport edge")
            hit = self._page.evaluate(
                """(p) => { const el = document.elementFromPoint(p.cx, p.cy);
                          return el ? (el.closest('.compact-controls.open') ? 'panel'
                                                                 : el.className || el.tagName)
                                    : null; }""",
                panel)
            self.assertEqual(
                hit, "panel",
                "the panel paints outside the rail but is not hit-testable there "
                "(clipped): elementFromPoint returned %r" % (hit,))
        finally:
            self._page.click(".navigation-rail .mobile-controls-toggle")

    def test_the_scope_menu_still_opens_from_inside_the_panel(self):
        """The rail panel wraps the scope switcher, so the popover now has two
        containers to escape.  If the panel clipped, the list would be
        unreachable — and a scope list you cannot open is worse than no rail."""
        self._page.click(".navigation-rail .mobile-controls-toggle")
        try:
            self._page.wait_for_selector(".compact-controls.open", timeout=5000)
            self._page.click(".scope-trigger")
            self._page.wait_for_selector(".scope-menu", timeout=5000)
            options = self._page.eval_on_selector_all(
                ".scope-option .scope-option-label", "es => es.map(e => e.textContent.trim())")
            self.assertGreaterEqual(len(options), 5)
            self.assertTrue(all(options), "a scope option lost its label in the rail")
        finally:
            self._page.keyboard.press("Escape")
            if self._page.query_selector(".compact-controls.open"):
                self._page.click(".navigation-rail .mobile-controls-toggle")

    # -- the phone -------------------------------------------------------
    def test_at_390_the_strip_keeps_its_words_and_adds_no_overflow(self):
        """The rail is a scrolling strip at this width, so it can afford the
        labels back — and it must, because an overlay painted outside a
        full-width strip adds to the document scroll width instead."""
        self._page.set_viewport_size({"width": 390, "height": 844})
        try:
            self._page.wait_for_selector(".navigation-rail .viewtabs button", timeout=5000)
            widths = self._page.eval_on_selector_all(
                ".navigation-rail .viewtabs .nav-label",
                "es => es.map(e => e.getBoundingClientRect().width)")
            self.assertTrue(widths)
            self.assertTrue(all(w > 8 for w in widths),
                            "the phone strip clipped its labels: %r" % widths)
            overflow = self._page.evaluate(
                "() => document.documentElement.scrollWidth - window.innerWidth")
            self.assertLessEqual(
                overflow, 0,
                "%dpx of horizontal overflow at 390" % overflow)
        finally:
            self._page.set_viewport_size({"width": 1280, "height": 900})

    def test_the_tooltip_is_suppressed_at_390(self):
        """Measured, not assumed: at opacity 0 an absolutely positioned
        ``::after`` still occupies space and still widens the document."""
        self._page.set_viewport_size({"width": 390, "height": 844})
        try:
            content = self._page.eval_on_selector(
                '.navigation-rail .viewtabs button[data-tip]',
                "e => getComputedStyle(e, '::after').content")
            self.assertEqual(content, "none",
                             "the tooltip still paints at 390 and widens the page")
        finally:
            self._page.set_viewport_size({"width": 1280, "height": 900})

    # -- the shell still marks where you are ------------------------------
    def test_the_active_view_is_marked_without_a_word(self):
        """The active marker used to be accent-soft plus a 3px left border.
        Neither depends on the label, so the icon rail must still carry both."""
        self._page.click('.navigation-rail .viewtabs button[data-tip="Library"]')
        self._page.wait_for_timeout(200)
        marked = self._page.eval_on_selector(
            '.navigation-rail .viewtabs button.active',
            """e => { const cs = getComputedStyle(e);
                     return {bg: cs.backgroundColor, bl: cs.borderLeftWidth,
                             current: e.getAttribute('aria-current')}; }""")
        self.assertEqual(marked["current"], "page")
        self.assertGreaterEqual(float(marked["bl"].replace("px", "")), 2.5,
                                "the active marker lost its left rule: %r" % marked)
        self.assertNotIn(marked["bg"], ("rgba(0, 0, 0, 0)", "transparent"),
                         "the active view lost its background: %r" % marked)

    def test_nothing_logged_to_the_console(self):
        self.assertEqual(self._console_errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
