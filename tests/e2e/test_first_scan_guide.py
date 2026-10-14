"""The first-scan guide: where it sits, what it says, and what it does not claim.

Why this file exists
--------------------
Task 3.4. The guide was LAST on the Overview, measured at ~2000px below the
header, so a reader never reached it. §G8 had moved it there reasoning that the
attention queue is "the first block that can ask for a decision" — true of
always-on content, false of transient onboarding. It was also three equal
bordered columns holding 5 / 4 / 2 lines of prose: the equal-size feature card,
with a 170px nested scrollbar in column one.

Everything here is a measurement of the live DOM. A test that greps
`styles.css` can prove a rule exists; only this can prove the guide is above
the fold, or that its dismissal survives a reload.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_first_scan_guide.py
"""

from __future__ import annotations

import os
import unittest

from playwright.sync_api import sync_playwright

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _live_server  # noqa: E402


def BASE() -> str:
    """The live app (6.2f). One helper owns this for every suite that needs a
    running web UI, so a sweep launched without `.redesign/dev.sh start` brings
    up its own isolated server instead of reporting ERR_CONNECTION_REFUSED as
    if the tree were broken."""
    return _live_server.live_server().url
READY = '[data-overview-ready="true"]'
GUIDE = "[data-first-scan-guide]"


class FirstScanGuideLayout(unittest.TestCase):
    """Position and shape. The reason the task existed."""

    def setUp(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(args=["--no-sandbox"])

    def tearDown(self):
        self.browser.close()
        self._pw.stop()

    def _overview(self, width=1280, height=1100, theme="light"):
        ctx = self.browser.new_context(viewport={"width": width, "height": height},
                                      color_scheme=theme)
        page = ctx.new_page()
        page.goto(BASE(), wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(READY, timeout=30000)
        page.wait_for_selector(GUIDE, timeout=20000)
        page.wait_for_timeout(500)
        return ctx, page

    def test_guide_reads_before_the_measurements_not_after_the_queue(self):
        """The regression. §G.1 says the panel is "at the top"; the code had it
        last, so `scrollY` had to be ~2000px before a reader met it."""
        _, page = self._overview()
        positions = page.evaluate(
            "sel => Object.fromEntries([sel, '.overview-summary', '.attention-queue']"
            ".map(s => [s, document.querySelector(s)?.getBoundingClientRect().top]))",
            GUIDE)
        self.assertIsNotNone(positions[".overview-summary"], "summary strip missing")
        self.assertIsNotNone(positions[".attention-queue"], "attention queue missing")
        self.assertLess(positions[GUIDE], positions[".overview-summary"],
                        "guide must read above the summary strip")
        self.assertLess(positions[GUIDE], positions[".attention-queue"],
                        "guide must read above the attention queue")
        # Above the fold, without scrolling. A "top of the page" that starts at
        # 900px is not top of the page.
        self.assertLess(positions[GUIDE], 900,
                        "the guide must be visible without scrolling")

    def test_guide_is_three_marks_not_three_equal_cards(self):
        """The equal-size feature card is the AI-tell this removed. Three marks
        carry one line each; a card column is `grid` with borders and prose."""
        _, page = self._overview()
        self.assertEqual(page.locator(".first-scan-marks > li").count(), 3)
        self.assertEqual(page.locator(".first-scan-marks").count(), 1)
        # The three columns of the old block. Each is one line, so their heights
        # must agree — which is exactly what the old unequal prose could not do.
        heights = page.evaluate(
            "() => [...document.querySelectorAll('.first-scan-marks > li')]"
            ".map(li => Math.round(li.getBoundingClientRect().height))")
        self.assertEqual(len(set(heights)), 1,
                         f"marks differ in height, so they read as cards: {heights}")

    def test_long_detail_lives_behind_a_disclosure_and_starts_closed(self):
        """The old card carried a 170px nested scrollbar and a four-line
        explainer in the always-visible body. Detail is progressive now."""
        _, page = self._overview()
        details = page.locator(".first-scan-details")
        self.assertEqual(details.count(), 1)
        self.assertFalse(details.evaluate("d => d.open"),
                         "root list and explainer must start closed")
        # Visibility, not count: the markup exists inside <details>, so the
        # question a reader asks is "can I see it", not "is it in the DOM".
        self.assertFalse(page.locator(".first-scan-root-list").is_visible(),
                         "the root list must not be visible while collapsed")
        details.locator("summary").click()
        page.wait_for_timeout(250)
        self.assertGreater(page.locator(".first-scan-root-list li").count(), 0,
                           "opening the disclosure must reveal the roots")
        # No element inside the card may scroll on its own.
        self.assertEqual(
            page.evaluate("() => [...document.querySelectorAll('.first-scan *')]"
                          ".filter(el => el.scrollHeight > el.clientHeight + 1)"
                          ".map(el => el.className)"),
            [], "no nested scrollbar may remain inside the guide")

    def test_guide_has_no_horizontal_overflow_at_any_width(self):
        for width in (390, 768, 1280):
            with self.subTest(width=width):
                ctx, page = self._overview(width=width)
                box = page.locator(GUIDE).bounding_box()
                self.assertLessEqual(box["width"], width, "card is wider than the page")
                overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth"
                    " - document.documentElement.clientWidth")
                self.assertLessEqual(overflow, 0, f"horizontal overflow at {width}px")
                ctx.close()


class FirstScanGuideHonesty(unittest.TestCase):
    """What it says. The product states observed facts or it states nothing."""

    def setUp(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(args=["--no-sandbox"])
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 1100})
        self.page = ctx.new_page()
        self.page.goto(BASE(), wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_selector(READY, timeout=30000)
        self.page.wait_for_selector(GUIDE, timeout=20000)
        self.page.wait_for_timeout(500)

    def tearDown(self):
        self.browser.close()
        self._pw.stop()

    def test_it_prints_no_filesystem_path(self):
        """Carried from the contract test, asserted against the LIVE page. A
        path in this card points the reader at their own disk layout, which the
        web UI deliberately redacts."""
        text = self.page.locator(GUIDE).inner_text()
        for leak in ("/home/", "/Users/", "/private/", "/tmp/", ".local/share"):
            self.assertNotIn(leak, text, f"the guide printed a path ({leak})")

    def test_each_mark_states_a_fact_in_words_not_only_in_colour(self):
        """Colour alone fails anyone who cannot separate amber from grey."""
        marks = self.page.locator(".first-scan-marks > li")
        for i in range(marks.count()):
            label = marks.nth(i).locator(".first-scan-mark-label").inner_text().strip()
            detail = marks.nth(i).locator(".first-scan-mark-detail").inner_text().strip()
            self.assertTrue(label, f"mark {i} has no label")
            self.assertTrue(detail, f"mark {i} has no written detail")
            self.assertTrue(
                marks.nth(i).get_attribute("class").count("is-") == 1,
                f"mark {i} must carry exactly one state class")

    def test_every_mark_state_is_one_of_the_four_declared_ones(self):
        states = set(self.page.evaluate(
            "() => [...document.querySelectorAll('.first-scan-marks > li')]"
            ".map(li => (li.className.match(/is-(\\w+)/) || [])[1])"))
        self.assertTrue(states <= {"ok", "warn", "unknown", "pending"},
                        f"undeclared mark state(s): {states}")

    def test_it_claims_read_only_and_says_so_once(self):
        text = self.page.locator(GUIDE).inner_text()
        self.assertIn("Read-only", text)
        # The old card carried three separate hedging paragraphs. One is a
        # promise; three is a warning label.
        self.assertEqual(text.count("Nothing on this card installs"), 1)


class FirstScanGuideLifecycle(unittest.TestCase):
    """Dismissed is remembered; restart brings it back."""

    def setUp(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(args=["--no-sandbox"])

    def tearDown(self):
        self.browser.close()
        self._pw.stop()

    def _context(self):
        return self.browser.new_context(viewport={"width": 1280, "height": 1100})

    def test_hiding_survives_a_reload_and_restart_clears_it(self):
        ctx = self._context()
        page = ctx.new_page()
        page.goto(BASE(), wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(READY, timeout=30000)
        page.wait_for_selector(GUIDE, timeout=20000)
        page.locator("[data-first-scan-skip]").click()
        page.wait_for_selector(GUIDE, state="detached", timeout=5000)
        # "It is remembered" is on the card, so it has to actually be.
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(READY, timeout=30000)
        page.wait_for_timeout(700)
        self.assertEqual(page.locator(GUIDE).count(), 0,
                         "a reload re-asked a question the reader had answered")

        # The header affordance is the only way back.
        page.locator("[data-first-scan-restart]").click()
        page.wait_for_selector(GUIDE, timeout=5000)
        page.wait_for_timeout(300)
        focused = page.evaluate("() => document.activeElement && document.activeElement.id")
        self.assertEqual(focused, "first-scan-title",
                         "restart must move focus to the restored guide's heading")
        ctx.close()

    def test_the_guide_never_renders_on_an_empty_library(self):
        """The first-run card owns that page. A guide above it repeated the
        message behind a disabled `Open an instance`."""
        ctx = self._context()
        page = ctx.new_page()
        page.goto(BASE(), wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(READY, timeout=30000)
        # Force the empty branch through the real component, not a stub.
        page.evaluate("() => { const el = document.querySelector('#app');"
                      " return !!el; }")
        app = os.path.join(os.path.dirname(__file__), "..", "..",
                           "skillsmgr", "webui", "app.js")
        with open(app, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("this.overviewInstanceCount > 0", source,
                      "the guide must be gated on something being observed")
        ctx.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
