"""Toasts, banners, the offline strip and loading skeletons, measured.

Why this file exists
--------------------
Task 2.3. These are the surfaces a reader meets when something went wrong, so
they are the ones where a rendering bug is least visible and most costly: a
banner that styles to nothing still *reads* as a banner in a diff, and a toast
that announces itself twice still looks correct in a screenshot.

The defects this file pins, all found by looking at the rendered surface:

- ``banner-warn`` had **no CSS rule at all**. It is used exactly once, in the
  update review's "Cancel this pending review?" confirmation -- the one banner
  whose whole job is to make a reader hesitate -- and it rendered as the
  unstyled base class: no tint, and ``border: 1px solid`` with no colour
  meaning ``currentColor``, so it inherited whatever text colour it landed on.
  A stylesheet rule that exists for three levels and is used at two is a hole
  nothing notices, because nothing renders the third during review.
- A toast could be **waited out but not dismissed**. 4s/8s was the only way to
  clear one, so a long error could not be read at the reader's pace.
- **The whole stack was the live region.** Each toast therefore announced
  itself on insertion AND on removal -- every toast spoke twice. A live region
  only speaks when its text *changes*, so two identical consecutive failures
  ("Could not load skills: …") were silent the second time, which is exactly
  when a repeating failure matters most.
- There was **no offline state at all**: a dead loopback server produced
  "Failed to fetch" inside a per-view message, indistinguishable from any
  other network error.

How toasts are produced here
----------------------------
Through ``window.__skillsManagerApp``, the handle ``app.js`` publishes for this
suite. That is the real ``toast()`` method on the real component -- the same
code a user reaches through "Tags updated" or a completed batch -- not a stub
and not DOM surgery. Clicking a real trigger for each message would mean a
five-step flow per test and would pin the *flow* rather than the *surface*,
which is what 2.3 changed.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_feedback_surfaces.py
"""

from __future__ import annotations

import os
import re
import unittest

from playwright.sync_api import sync_playwright

NARROW = 390
DESKTOP = 1280

#: DESIGN-V2 §F: "Toast (bottom-centre, Undo action, 4s/8s)".
TOAST_MS = 4000
TOAST_UNDO_MS = 8000
#: WCAG 2.2 target floor on coarse pointers; this repo targets 44.
TARGET = 44


def _base_url() -> str:
    """The live app, from the isolated dev server (never the real HOME)."""
    return os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")


def _srgb(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(rgb: list[int]) -> float:
    r, g, b = (_srgb(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: list[int], b: list[int]) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


class FeedbackSurfaceTest(unittest.TestCase):
    """One browser; every assertion is about what renders."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch()
        cls.page = cls._browser.new_page(viewport={"width": DESKTOP, "height": 900})
        cls.console_errors: list[str] = []
        cls.failed_requests: list[str] = []
        cls.page.on(
            "console",
            lambda m: cls.console_errors.append(m.text) if m.type == "error" else None,
        )
        cls.page.on("requestfailed", lambda r: cls.failed_requests.append(r.url))
        try:
            cls.page.goto(_base_url(), wait_until="domcontentloaded", timeout=20000)
            cls.page.wait_for_selector("#app", state="attached", timeout=15000)
            cls.page.wait_for_selector(".topbar", timeout=15000)
        except Exception as exc:  # pragma: no cover - environment dependent
            cls._browser.close()
            cls._pw.stop()
            raise unittest.SkipTest(
                f"the dev server at {_base_url()} did not load ({exc}). Start it "
                f"with `.redesign/dev.sh start` — this test is NOT silently "
                f"passed when it cannot run."
            )
        cls._assert_vue_mounted()

    @classmethod
    def _assert_vue_mounted(cls) -> None:
        """`mount()` returns the instance and Vue hangs `__vue_app__` off the
        root element. If neither is reachable, every test below would silently
        exercise nothing, so this fails loudly instead."""
        mounted = cls.page.evaluate(
            "() => !!(window.__skillsManagerApp"
            " && typeof window.__skillsManagerApp.toast === 'function')"
        )
        if not mounted:
            cls._browser.close()
            cls._pw.stop()
            raise unittest.SkipTest(
                "the app handle window.__skillsManagerApp is missing; the "
                "toast methods cannot be exercised. NOT silently passed."
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.page.close()
        cls._browser.close()
        cls._pw.stop()

    # -- helpers ---------------------------------------------------------

    def toast(self, text: str, type_: str = "ok", undo: bool = False) -> None:
        """Call the app's real toast() with a short-lived undo so the stack
        does not outlive the test."""
        self.page.evaluate(
            """([text, type, undo]) => {
              const vm = window.__skillsManagerApp;
              vm.toast(text, type, undo ? async () => {} : null);
            }""",
            [text, type_, undo],
        )
        self.page.wait_for_selector(".toast", timeout=5000)

    def goto_view(self, name: str) -> None:
        """The banner is rendered per-view (Library, Overview, Quality), so a
        test that sets one without saying where it lives is testing whichever
        view happened to load first. 2.3's suite inherited that and produced
        three timeouts."""
        self.page.click(f'.viewtabs button:has-text("{name}")')
        self.page.wait_for_timeout(200)

    def clear_toasts(self) -> None:
        self.page.evaluate(
            "() => { const vm = window.__skillsManagerApp;"
            " vm.toasts.forEach((t) => vm.dismissToast(t)); }"
        )
        self.page.wait_for_timeout(120)

    def set_theme(self, theme: str) -> None:
        self.page.evaluate(
            "(theme) => { document.documentElement.setAttribute('data-theme', theme);"
            " localStorage.setItem('skillsmgr-theme', theme); }",
            theme,
        )
        self.page.wait_for_timeout(120)

    def computed_rgb(self, selector: str, prop: str = "color") -> list[int]:
        raw = self.page.eval_on_selector(
            selector, "(e, p) => getComputedStyle(e)[p]", prop
        )
        nums = re.findall(r"[\d.]+", raw)
        return [int(round(float(n))) for n in nums[:3]]

    def box(self, selector: str) -> dict:
        return self.page.eval_on_selector(
            selector,
            "e => { const r = e.getBoundingClientRect();"
            " return {x: r.x, y: r.y, w: r.width, h: r.height, bottom: r.bottom,"
            "         right: r.right, cx: r.x + r.width / 2}; }",
        )

    # ==================================================================
    # Toasts
    # ==================================================================

    def test_a_toast_carries_a_dismiss_control(self):
        """The defect: 4s/8s was the ONLY way to clear a toast, so a long error
        could not be read at the reader's pace."""
        self.clear_toasts()
        self.toast("A message long enough that a reader would want to keep it.")
        self.assertGreaterEqual(
            self.page.eval_on_selector_all(".toast .toast-dismiss", "es => es.length"),
            1,
            "a toast with no Undo must offer a way to dismiss it",
        )

    def test_the_dismiss_button_names_the_message_it_dismisses(self):
        """An icon-only control needs an accessible name that is not its glyph,
        or a screen-reader user hears "button"."""
        self.clear_toasts()
        self.toast("Named dismissal target")
        label = self.page.eval_on_selector(
            ".toast .toast-dismiss", "e => e.getAttribute('aria-label') || ''"
        )
        self.assertIn("Named dismissal target", label)

    def test_dismissing_removes_the_toast(self):
        self.clear_toasts()
        self.toast("Remove me on click")
        self.page.click(".toast .toast-dismiss")
        self.page.wait_for_timeout(200)
        self.assertEqual(
            self.page.eval_on_selector_all(".toast", "es => es.length"),
            0,
            "clicking dismiss left the toast on screen",
        )

    def test_the_stack_is_bottom_centred(self):
        """DESIGN-V2 §F says bottom-centre; it was pinned bottom-right, on the
        same edge as the scrollbar and the pointer already travelling along."""
        self.clear_toasts()
        self.toast("Centre me")
        box = self.box(".toast")
        viewport = self.page.viewport_size["width"]
        self.assertLessEqual(
            abs(box["cx"] - viewport / 2), 2.0,
            f"toast centre {box['cx']:.0f}px vs viewport centre {viewport / 2:.0f}px",
        )

    def test_the_toast_clears_the_status_bar(self):
        """The status bar is fixed chrome at the same edge. A toast sitting on
        top of it hides the loopback authority the status bar exists to name."""
        self.clear_toasts()
        self.toast("Above the status bar")
        self.assertLessEqual(
            self.box(".toast")["bottom"],
            self.box(".statusbar")["y"] + 1.0,
            "the toast overlaps the status bar",
        )

    def test_a_long_message_wraps_instead_of_overflowing(self):
        """`max-width: 380px` with no width clamp meant the box grew to fit the
        message and the viewport clipped it -- with no margin left at 390px."""
        self.page.set_viewport_size({"width": NARROW, "height": 800})
        self.clear_toasts()
        self.toast(
            "Could not load skills: the local server did not answer. Start it, "
            "then retry - what is shown below is the last observed state."
        )
        box = self.box(".toast")
        self.assertLessEqual(box["right"], NARROW, f"toast ends at {box['right']}px")
        self.assertGreaterEqual(box["x"], 0, "toast starts left of the viewport")
        overflow = self.page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        self.assertEqual(overflow, 0, f"{overflow}px of horizontal page overflow")
        self.page.set_viewport_size({"width": DESKTOP, "height": 900})

    def test_a_burst_keeps_the_newest_message_on_screen(self):
        """Ten toasts stacked past the top of the viewport, pushing the newest
        -- the one describing the failure that caused the other nine -- off the
        top. The cap drops the OLDEST for exactly that reason."""
        self.clear_toasts()
        for i in range(8):
            self.toast(f"Burst message {i}")
        self.page.wait_for_timeout(250)
        count = self.page.eval_on_selector_all(".toast", "es => es.length")
        self.assertLessEqual(count, 3, f"{count} toasts stacked with no cap")
        newest = self.page.eval_on_selector_all(".toast-text", "es => es.map(e => e.textContent)")
        self.assertIn("Burst message 7", newest[-1], "the newest toast was dropped")
        top = self.box(".toasts")["y"]
        self.assertGreaterEqual(top, 0, "the stack overflowed the top of the viewport")
        self.clear_toasts()

    def test_a_toast_announces_once_and_only_once(self):
        """The defect: the whole stack was `aria-live`, so each toast announced
        itself on insertion AND on removal -- every message spoke twice."""
        self.clear_toasts()
        self.toast("Announced exactly once")
        # The container must not itself be a live region.
        live = self.page.eval_on_selector(".toasts", "e => e.getAttribute('aria-live')")
        self.assertIsNone(
            live,
            "the toast stack is itself a live region, so every toast speaks on "
            "insert AND on removal",
        )
        # Each toast carries its own role instead.
        self.assertEqual(
            self.page.eval_on_selector(".toast", "e => e.getAttribute('role')"),
            "status",
        )
        self.assertEqual(
            self.page.eval_on_selector_all(".toast", "es => es.filter(e => e.getAttribute('role')).length"),
            self.page.eval_on_selector_all(".toast", "es => es.length"),
            "a toast with no role is announced by nothing",
        )

    def test_an_error_toast_is_alert_role_and_the_rest_are_status(self):
        """An error interrupts; a confirmation should not."""
        self.clear_toasts()
        self.toast("Something failed", "err")
        self.assertEqual(
            self.page.eval_on_selector(".toast", "e => e.getAttribute('role')"), "alert"
        )
        self.clear_toasts()
        self.toast("Saved", "ok")
        self.assertEqual(
            self.page.eval_on_selector(".toast", "e => e.getAttribute('role')"), "status"
        )

    def test_a_repeating_identical_message_announces_again(self):
        """A live region only speaks when its text CHANGES.

        The old code set `liveAnnouncement` and never cleared it, so a second
        IDENTICAL failure produced no text change and was therefore silent --
        exactly when a repeating failure matters most.

        WHAT IS ASSERTED, AND WHY IT IS NOT THE OBVIOUS THING. The first
        version sampled the rendered text and it passed with the clear REMOVED,
        because Vue does not re-render a reactive value that did not change:
        the DOM holds the same string either way, so reading it proves nothing
        about whether a repeat can be announced. Two other samplers (a
        synchronous read, and an animation-frame read) both saw "" and looked
        like a product defect -- see the comment in the body.

        The observable, and the thing a screen reader actually gets, is the
        VALUE the component clears: it must return to empty after a toast, so
        that the next identical write is a change again. That is what is
        asserted, and it fails when the clear is deleted.
        """
        self.clear_toasts()
        self.page.evaluate(
            """() => {
              const vm = window.__skillsManagerApp;
              vm.banner = null;
              window.__trace = [];
              vm.toast('Could not load skills: boom', 'err');
              vm.$nextTick(() => {
                window.__trace.push(['held', vm.liveAnnouncement]);
                requestAnimationFrame(() => {
                  window.__trace.push(['cleared', vm.liveAnnouncement]);
                  window.__done = true;
                });
              });
            }"""
        )
        self.page.wait_for_function("() => window.__done === true", timeout=5000)
        trace = dict(self.page.evaluate("() => window.__trace"))
        self.assertEqual(
            trace["held"], "Could not load skills: boom",
            "the message was never published to the live region",
        )
        self.assertEqual(
            trace["cleared"], "",
            "the live region still holds the message after it was announced, so "
            "an identical repeat is not a change and is therefore silent -- "
            "the exact defect this guards",
        )
        self.clear_toasts()

    def test_an_undo_toast_keeps_its_action_and_its_longer_life(self):
        self.clear_toasts()
        self.toast("Removed", "ok", undo=True)
        self.assertEqual(
            self.page.eval_on_selector_all(".toast .toast-undo", "es => es.length"), 1
        )
        # An undoable toast must NOT also offer dismiss: two exits, one of which
        # throws the action away, is worse than one.
        self.assertEqual(
            self.page.eval_on_selector_all(".toast .toast-dismiss", "es => es.length"),
            0,
            "an undoable toast must not also offer a dismiss that discards the undo",
        )

    def test_undo_removes_the_toast_before_it_can_be_reused(self):
        self.clear_toasts()
        self.toast("Undo target", "ok", undo=True)
        self.page.click(".toast .toast-undo")
        self.page.wait_for_timeout(200)
        self.assertEqual(self.page.eval_on_selector_all(".toast", "es => es.length"), 0)

    def test_a_toast_action_meets_the_target_floor_on_a_coarse_pointer(self):
        """Undo was a bare `padding: 2px 6px` text node -- roughly 20px tall."""
        self.clear_toasts()
        self.toast("Coarse pointer target", "ok", undo=True)
        height = self.box(".toast .toast-undo")["h"]
        self.assertGreaterEqual(
            height, 28,
            f"the Undo control is {height:.0f}px tall in the default state",
        )

    # ==================================================================
    # Banners
    # ==================================================================

    def test_every_banner_level_has_a_real_rule(self):
        """The 2.3 defect in one assertion.

        `banner-warn` was used exactly once -- in the update review's "Cancel
        this pending review?" confirmation -- and had NO rule at all. It
        rendered as the unstyled base class: `--surface-2` on `--border`, with
        `color: var(--text)`. `banner-info` was declared nowhere.

        The assertion is DISTINCTNESS, not "has a background". That is the
        version that failed when this test was first written: every level
        inherits the base `.banner` rule, so a missing level still had a
        background and a border, and the test stayed green with the rule
        deleted -- the same "gate reporting PASS about a path it cannot see"
        failure this repository has now recorded six times. Each level must
        therefore resolve to a colour set no other level uses, and a level with
        no rule is exactly the one that collapses onto the base values.
        """
        self.goto_view("Library")
        seen: dict[str, tuple] = {}
        for level in ("ok", "warn", "error", "info"):
            self.page.evaluate(
                """(level) => {
                  window.__skillsManagerApp.banner = {type: level, text: 'Banner body'};
                }""",
                level,
            )
            sel = f".sidebar .banner-{level}"
            self.page.wait_for_selector(sel, timeout=4000)
            seen[level] = (
                self.computed_rgb(sel, "backgroundColor"),
                self.computed_rgb(sel, "color"),
                self.computed_rgb(sel, "borderTopColor"),
            )

        # Each level must be visually its own thing.
        for level, values in seen.items():
            others = [v for k, v in seen.items() if k != level]
            self.assertNotIn(
                values, others,
                f"banner-{level} resolves to the same colours as another level, "
                f"so one of them has no rule and renders as the unstyled base: "
                f"{seen}",
            )

        # And no level may fall back to the base .banner tokens, which is what
        # an absent rule resolves to.
        base = self.base_banner_values()
        for level, values in seen.items():
            self.assertNotEqual(
                values, base,
                f"banner-{level} renders as the unstyled base .banner — the "
                f"rule for it does not exist",
            )
        self.page.evaluate(
            "() => { window.__skillsManagerApp.banner = null; }"
        )

    def base_banner_values(self) -> tuple:
        """The computed values an unstyled `.banner` resolves to.

        Measured, not assumed: a level name with no rule in the stylesheet
        inherits the base `.banner` block exactly, so rendering one is the
        honest way to learn what "no rule" looks like. Hard-coding the token
        names would just re-assert my own belief about the cascade, which is
        how the first version of this test passed against a deleted rule.
        """
        self.page.evaluate(
            """() => {
              // `banner-zzz` is deliberately not a level: no rule exists for
              // it, so it resolves to the base block alone.
              window.__skillsManagerApp.banner = {type: 'zzz', text: 'base probe'};
            }"""
        )
        self.page.wait_for_selector(".sidebar .banner-zzz", timeout=4000)
        sel = ".sidebar .banner-zzz"
        values = (
            self.computed_rgb(sel, "backgroundColor"),
            self.computed_rgb(sel, "color"),
            self.computed_rgb(sel, "borderTopColor"),
        )
        self.page.evaluate(
            "() => { window.__skillsManagerApp.banner = null; }"
        )
        return values

    def test_a_banner_carries_a_glyph_not_just_a_tint(self):
        self.goto_view("Library")
        """Status is never colour-only: the meaning must survive greyscale,
        forced-colors, and every form of colour-vision deficiency."""
        self.page.evaluate(
            "() => { const vm = window.__skillsManagerApp;"
            " vm.banner = {type: 'error', text: 'Could not load skills: boom'}; }"
        )
        self.page.wait_for_selector(".banner-error", timeout=4000)
        self.assertGreaterEqual(
            self.page.eval_on_selector_all(".banner-error svg", "es => es.length"),
            1,
            "the banner is a tint and nothing else, which is colour-only status",
        )
        self.page.evaluate(
            "() => { const vm = window.__skillsManagerApp;"
            " vm.banner = null; }"
        )

    def test_a_banner_meets_text_contrast_in_both_themes(self):
        self.goto_view("Library")
        for theme in ("light", "dark"):
            self.set_theme(theme)
            for level in ("ok", "warn", "error", "info"):
                self.page.evaluate(
                    """(level) => {
                      const vm = window.__skillsManagerApp;
                      vm.banner = {type: level, text: 'Could not load skills: boom'};
                    }""",
                    level,
                )
                self.page.wait_for_selector(f".skilllist ~ .banner-{level}, .listpane .banner-{level}, .sidebar .banner-{level}", timeout=4000)
                fg = self.computed_rgb(f".sidebar .banner-{level}")
                bg = self.computed_rgb(f".sidebar .banner-{level}", "backgroundColor")
                ratio = _contrast(fg, bg)
                self.assertGreaterEqual(
                    ratio, 4.5,
                    f"banner-{level} in {theme}: {fg} on {bg} = {ratio:.2f}:1",
                )
        self.set_theme("light")
        self.page.evaluate(
            "() => { const vm = window.__skillsManagerApp;"
            " vm.banner = null; }"
        )

    def test_no_banner_carries_an_inline_style(self):
        self.goto_view("Library")
        """Five sites carried `style="margin:0 0 12px"` -- a layout decision
        made per call site instead of once in the cascade."""
        self.page.evaluate(
            """() => {
              const vm = window.__skillsManagerApp;
              vm.banner = {type: 'error', text: 'inline style probe'};
            }"""
        )
        self.page.wait_for_selector(".banner", timeout=4000)
        self.assertEqual(
            self.page.eval_on_selector_all(
                ".banner", "es => es.filter(e => e.getAttribute('style')).length"
            ),
            0,
            "a banner still carries an inline style",
        )
        self.page.evaluate(
            "() => { const vm = window.__skillsManagerApp;"
            " vm.banner = null; }"
        )

    # ==================================================================
    # Offline
    # ==================================================================

    def test_the_offline_strip_is_hidden_while_the_server_answers(self):
        self.assertEqual(
            self.page.eval_on_selector_all(".offline-banner", "es => es.length"),
            0,
            "the offline strip is showing while the server is answering /api/stats",
        )

    def test_the_offline_strip_appears_on_a_transport_failure_and_names_the_fix(self):
        """The defect: a dead loopback server produced "Failed to fetch" inside
        a per-view message, indistinguishable from any other network error."""
        self.page.route("**/api/skills*", lambda route: route.abort("connectionrefused"))
        self.page.evaluate(
            "() => { const vm = window.__skillsManagerApp;"
            " vm.loadSkills(); }"
        )
        try:
            self.page.wait_for_selector(".offline-banner", timeout=8000)
            text = self.page.eval_on_selector(".offline-banner", "e => e.textContent")
            self.assertIn("not responding", text.lower())
            self.assertGreaterEqual(
                self.page.eval_on_selector_all(".offline-banner .btn", "es => es.length"),
                1,
                "the offline strip states a problem with no action attached",
            )
            # Polite, not assertive: going offline is not an emergency and must
            # not interrupt whatever a screen-reader user is reading.
            self.assertEqual(
                self.page.eval_on_selector(
                    ".offline-banner", "e => e.getAttribute('role')"
                ),
                "status",
                "the offline strip interrupts; it should be polite",
            )
        finally:
            self.page.unroute("**/api/skills*")
        # Recovery is a real request, not a re-render.
        self.page.click(".offline-banner .btn")
        self.page.wait_for_timeout(1500)
        self.assertEqual(
            self.page.eval_on_selector_all(".offline-banner", "es => es.length"),
            0,
            "Retry did not clear the strip after the server answered again",
        )

    def test_the_offline_strip_does_not_push_the_page_down(self):
        """It is the one banner that must be visible from every view, so it is
        fixed -- and fixed means it cannot reflow the content when it appears."""
        self.page.evaluate(
            "() => { const vm = window.__skillsManagerApp;"
            " vm.offline = true; }"
        )
        try:
            self.page.wait_for_selector(".offline-banner", timeout=4000)
            self.assertEqual(
                self.page.eval_on_selector(
                    ".offline-banner", "e => getComputedStyle(e).position"
                ),
                "fixed",
                "the offline strip is in the document flow, so it pushes the "
                "content down every time it appears",
            )
        finally:
            self.page.evaluate(
                "() => { const vm = window.__skillsManagerApp;"
                " vm.offline = false; }"
            )

    # ==================================================================
    # Skeletons
    # ==================================================================

    def test_reduced_motion_leaves_a_skeleton_as_a_static_fill(self):
        """The defect: the global reduced-motion block sets
        `animation-iteration-count: 1`, which STOPS the shimmer -- and stopping
        it at its `to` frame left every row permanently displaced by one full
        width instead of settling back to a flat fill. Stopping is not the same
        as resting."""
        self.page.emulate_media(reduced_motion="reduce")
        try:
            self.goto_view("Library")
            self.page.evaluate(
                "() => { window.__skillsManagerApp.loadingList = true; }"
            )
            # A `.skel-row` is an EMPTY div, so it has no box and Playwright's
            # visibility test never matches it. Wait on the container.
            self.page.wait_for_selector(".skeleton", timeout=4000)
            overlay = self.page.eval_on_selector(
                ".skel-row",
                """e => { const s = getComputedStyle(e, '::after');
                   return {content: s.content, animation: s.animationName}; }""",
            )
            self.assertIn(
                "none", overlay["content"],
                "the shimmer overlay is still painted under reduced motion, so a "
                "stopped animation leaves a displaced highlight on every row",
            )
            self.page.evaluate(
                "() => { const vm = window.__skillsManagerApp;"
                " vm.loadingList = false; }"
            )
        finally:
            self.page.emulate_media(reduced_motion="no-preference")

    def test_a_loading_list_is_announced_as_loading(self):
        """A skeleton is decoration; the state it stands for is not, and a
        screen-reader user gets no signal at all without a live region."""
        self.goto_view("Library")
        self.page.evaluate(
            "() => { window.__skillsManagerApp.loadingList = true; }"
        )
        try:
            self.page.wait_for_selector(".skeleton", timeout=4000)
            self.assertGreaterEqual(
                self.page.eval_on_selector_all(
                    ".skeleton[role='status'], .skeleton[aria-busy='true']", "es => es.length"
                ),
                1,
                "a skeleton is shown with no status role and no aria-busy, so "
                "the loading state is silent",
            )
        finally:
            self.page.evaluate(
                "() => { const vm = window.__skillsManagerApp;"
                " vm.loadingList = false; }"
            )

    # ==================================================================
    # Cross-cutting
    # ==================================================================

    def test_the_run_produced_no_console_errors(self):
        """Everything except the transport failure this suite causes on purpose.

        `test_the_offline_strip_appears_on_a_transport_failure...` aborts the
        request with `connectionrefused`, and Chrome logs that as a console
        error. Counting it would fail the run for the defect it is testing, so
        the marker it leaves is subtracted rather than the assertion dropped --
        the remaining errors still fail.
        """
        deliberate = "net::ERR_CONNECTION_REFUSED"
        unexpected = [e for e in self.console_errors if deliberate not in e]
        self.assertEqual(unexpected, [], f"console errors: {unexpected}")

    def test_every_viewport_and_theme_stayed_inside_the_window(self):
        for width in (NARROW, 768, DESKTOP):
            for theme in ("light", "dark"):
                self.page.set_viewport_size({"width": width, "height": 900})
                self.set_theme(theme)
                self.page.wait_for_timeout(150)
                overflow = self.page.evaluate(
                    "() => document.documentElement.scrollWidth"
                    " - document.documentElement.clientWidth"
                )
                self.assertEqual(
                    overflow, 0, f"{overflow}px horizontal overflow at {width}px {theme}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)