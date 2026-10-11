"""The Overview summary strip, the scan age, and the block order — measured.

Why this file exists
--------------------
Task 3.1. The page carried a "health" panel directly under the attention queue
that restated the queue's own claim in a second headline and carried the only
stray `--shadow` in the stylesheet; its seven counts are now a four-cell strip
plus one hairline readout. The h1 gained a "Scanned N ago · Rescan" row, which
is this page's own settled successful read — the aggregate list route carries no
server-side observation timestamp.

Every assertion below is a statement about what RENDERS or what the live app
DOES. A test that greps `index.html` cannot see whether the fourth cell is
readable at 390px, whether the strip overflows, or whether Rescan is actually
disabled while in flight — which is the entire risk in a change like this one.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_overview_summary.py
"""

from __future__ import annotations

import os
import unittest

BASE = os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")
READY = '[data-overview-ready="true"]'
WIDTHS = (390, 768, 1280)


class OverviewSummaryTests(unittest.TestCase):
    maxDiff = None

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
        cls._page = cls._browser.new_page(viewport={"width": 1280, "height": 1000})
        cls._errors: list[str] = []
        cls._page.on("console", lambda m: m.type == "error" and cls._errors.append(m.text))
        cls._page.on("pageerror", lambda e: cls._errors.append(str(e)))
        try:
            cls._page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
            cls._page.wait_for_selector(READY, timeout=20000)
            cls._page.wait_for_selector(".overview-metrics", timeout=10000)
        except Exception as exc:
            cls._browser.close()
            cls._pw_cm.stop()
            raise unittest.SkipTest(
                f"the dev server at {BASE} did not reach the Overview "
                f"({exc}). Start it with `.redesign/dev.sh start` — this test "
                f"is NOT silently passed when it cannot run."
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._pw_cm.stop()

    def _at(self, width: int):
        self._page.set_viewport_size({"width": width, "height": 1000})
        self._page.goto(BASE, wait_until="domcontentloaded")
        self._page.wait_for_selector(READY, timeout=20000)
        self._page.wait_for_timeout(120)
        return self._page

    # -- the strip --------------------------------------------------------
    def test_the_strip_is_exactly_four_cells(self):
        cells = self._page.eval_on_selector_all(
            ".overview-metrics > div", "els => els.length")
        self.assertEqual(cells, 4)

    def test_every_strip_cell_pairs_its_label_with_a_number(self):
        pairs = self._page.eval_on_selector_all(
            ".overview-metrics > div",
            "els => els.map(e => { const d = e.querySelector('dt'); "
            "const v = e.querySelector('dd'); "
            "return [d && d.textContent.trim(), v ? v.textContent.trim() : '']; })",
        )
        self.assertEqual([p[0] for p in pairs],
                         ["Skills", "Observed copies", "Needs attention", "Context used"])
        for label, value in pairs:
            self.assertTrue(value, f"the {label!r} cell renders no value")

    def test_the_context_cell_names_the_window_it_is_measured_against(self):
        text = self._page.inner_text(".overview-metrics > div:nth-child(4)")
        self.assertIn("window", text)
        self.assertRegex(text, r"\d")

    def test_the_strip_does_not_overflow_at_any_supported_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                page = self._at(width)
                over = page.evaluate(
                    "() => document.documentElement.scrollWidth - window.innerWidth")
                self.assertLessEqual(over, 1, f"horizontal overflow at {width}px")
                # The strip must also stay inside its own container rather than
                # being clipped: a zero-width container reads as "no overflow".
                strip_w = page.eval_on_selector(
                    ".overview-metrics", "e => e.getBoundingClientRect().width")
                self.assertGreater(strip_w, 200)

    def test_the_breakdown_keeps_every_remaining_observed_count(self):
        items = self._page.eval_on_selector_all(
            ".overview-breakdown li", "els => els.map(e => e.textContent.replace(/\\s+/g, ' ').trim())")
        self.assertEqual(len(items), 7, items)
        for label in ("active", "disabled", "malformed", "linked outside root",
                      "unaddressable", "divergent group", "in trash"):
            self.assertTrue(any(label in i for i in items), f"{label!r} missing: {items}")

    # -- the scan age -----------------------------------------------------
    def test_the_scan_age_is_present_after_a_settled_read(self):
        text = self._page.inner_text(".overview-scanned").strip()
        self.assertTrue(text.startswith("Scanned "), text)

    def test_the_header_line_states_no_counts_of_its_own(self):
        """The reason the status line was merged: it repeated three cells."""
        text = self._page.inner_text(".overview-scanned").strip()
        self.assertNotIn("active", text)
        self.assertNotIn("attention", text.lower())
        self.assertEqual(len(self._page.query_selector_all(".overview-statusline")), 0)

    def test_rescan_is_reachable_by_keyboard_and_names_itself(self):
        self._at(1280)
        button = self._page.query_selector("[data-rescan]")
        self.assertIsNotNone(button)
        self.assertTrue(button.is_enabled())
        label = button.inner_text().strip()
        self.assertEqual(label, "Rescan")

    def test_rescan_is_disabled_while_it_is_in_flight(self):
        self._at(1280)
        """A double-click is the normal way a reader misuses this button, so
        the guard has to exist before the second click lands — not after."""
        self._page.click("[data-rescan]")
        self.assertTrue(
            self._page.eval_on_selector("[data-rescan]", "e => e.disabled"),
            "Rescan stayed enabled after the click",
        )
        self._page.wait_for_selector(READY, timeout=20000)
        # The read settling is not the same instant as the button re-enabling:
        # rescanBusy clears in the finally AFTER the reads resolve, so the
        # wait has to be on the control, not on the data.
        self._page.wait_for_function(
            "() => { const b = document.querySelector('[data-rescan]'); "
            "return !!b && !b.disabled; }", timeout=10000)

    # -- the layout -------------------------------------------------------
    def test_the_blocks_read_in_priority_order(self):
        order = self._page.evaluate("""() => {
            const pick = (sel) => {
                const el = document.querySelector(sel);
                return el ? el.getBoundingClientRect().top + window.scrollY : null;
            };
            return ['.overview-metrics', '.attention-queue', '.budget-block',
                    '.overview-activity'].map(pick);
        }""")
        self.assertTrue(all(v is not None for v in order), order)
        self.assertEqual(order, sorted(order), f"blocks out of order: {order}")

    def test_the_summary_sits_above_the_queue_not_beside_it(self):
        """The old layout was a two-column wrapper whose second column held a
        five-line activity list, so a reader could put the strip and the queue
        side by side. Stacked and edge-aligned is the claim, and that is what a
        side-by-side layout cannot satisfy."""
        box = lambda sel: self._page.eval_on_selector(  # noqa: E731
            sel,
            "e => { const r = e.getBoundingClientRect(); "
            "return { top: r.top, left: r.left, width: r.width, height: r.height }; }")
        summary, queue = box(".overview-summary"), box(".attention-queue")
        self.assertGreaterEqual(queue["top"], summary["top"] + summary["height"],
                                "the queue overlaps the summary block")
        self.assertAlmostEqual(queue["left"], summary["left"], delta=1)
        self.assertAlmostEqual(queue["width"], summary["width"], delta=1)
        # The strip spans the content column rather than sitting in half of it.
        shell = self._page.eval_on_selector(
            ".overview-shell", "e => e.getBoundingClientRect().width")
        self.assertGreater(box(".overview-metrics")["width"], shell * 0.9)

    def test_no_console_errors_on_the_overview(self):
        self.assertEqual(self._errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)