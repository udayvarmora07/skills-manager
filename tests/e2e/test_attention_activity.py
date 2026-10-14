"""The attention queue rows and the activity list, as they actually render.

Why this file exists
--------------------
Task 3.2. Two changes, both of which a source-grepping test cannot check:

- the activity list prints **relative** time ("6 min ago") with the exact
  timestamp in `datetime`/`title`, because an absolute timestamp does not answer
  "was that before or after I last looked?";
- the queue row's state marker is the **sprite icon** the banners already use,
  not a literal `!` glyph, and the row lost the `--shadow` the summary strip
  deliberately refuses.

`now` is a parameter of `formatRelative`, so the formatter is tested against
fixed inputs rather than against a clock that moves under the assertion.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_attention_activity.py
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _live_server  # noqa: E402

def BASE() -> str:
    """The live app. 6.2f: one helper owns the base URL for every suite that
    needs a running web UI, so a sweep launched without `.redesign/dev.sh start`
    brings up its own isolated server instead of reporting ERR_CONNECTION_REFUSED
    as if the tree were broken. See tests/e2e/_live_server.py for the order."""
    return _live_server.live_server().url

READY = '[data-overview-ready="true"]'
NOW = 1_760_000_000_000  # fixed clock; see module docstring


class AttentionAndActivityTests(unittest.TestCase):
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
            cls._page.goto(BASE(), wait_until="domcontentloaded", timeout=20000)
            cls._page.wait_for_selector(READY, timeout=20000)
            cls._page.wait_for_selector(".attention-queue", timeout=10000)
        except Exception as exc:
            cls._browser.close()
            cls._pw_cm.stop()
            raise unittest.SkipTest(
                f"the dev server at {BASE()} did not reach the Overview "
                f"({exc}). Start it with `.redesign/dev.sh start` — this test "
                f"is NOT silently passed when it cannot run."
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._pw_cm.stop()

    # -- formatRelative, against a fixed clock ---------------------------
    def _relative(self, iso: str) -> str:
        return self._page.evaluate(
            """(args) => window.__skillsManagerApp.formatRelative(args[0], args[1])""",
            [iso, NOW],
        )

    def test_relative_time_reads_as_a_duration_at_every_scale(self):
        # NOW is 2025-10-09T08:53:20Z; the offsets are written out because a
        # fixture that computes its own inputs from the same constant as the
        # assertion proves nothing.
        cases = {
            "2025-10-09T08:53:00Z": "just now",       # 20s
            "2025-10-09T08:51:20Z": "2 min ago",      # 2m
            "2025-10-09T05:53:20Z": "3 hours ago",    # 3h
            "2025-10-07T08:53:20Z": "2 days ago",     # 2d
        }
        for iso, expected in cases.items():
            with self.subTest(iso=iso):
                self.assertEqual(self._relative(iso), expected)

    def test_relative_time_bottoms_out_at_an_absolute_date(self):
        """A week-old entry stops pretending to be precise and prints the date
        it actually happened. It must not read "91 days ago"."""
        out = self._relative("2025-07-10T08:53:20Z")  # 91d before NOW
        self.assertNotIn("ago", out)
        self.assertRegex(out, r"\d")

    def test_a_future_timestamp_is_not_reported_as_zero_seconds(self):
        """Clock skew and bad records both land here; 'just now' would be a lie
        in the one direction that matters."""
        out = self._relative("2025-10-09T10:53:20Z")  # 2h AFTER NOW
        self.assertNotEqual(out, "just now")

    def test_an_unparseable_value_is_echoed_rather_than_invented(self):
        self.assertEqual(self._relative("not-a-date"), "not-a-date")
        self.assertEqual(self._relative(""), "—")

    # -- what the page renders -------------------------------------------
    def test_activity_rows_carry_relative_time_and_the_exact_timestamp(self):
        rows = self._page.eval_on_selector_all(
            ".activity-list time",
            "els => els.map(e => [e.textContent.trim(), e.getAttribute('datetime'), "
            "e.getAttribute('title')])",
        )
        self.assertTrue(rows, "the seed fixture always writes history rows")
        for text, dt, title in rows:
            self.assertTrue(dt, "a machine-readable datetime is missing")
            self.assertTrue(title, "the exact timestamp must stay reachable")
            # An ABSOLUTE stamp here always carries a clock time -- formatDate
            # is called with timeStyle:"short" -- so the absence of a clock is
            # what distinguishes the two. Asserting "no T" (the first attempt)
            # could not fail, because the absolute form is "Oct 10, 2:30 AM"
            # and contains no T at all. See TEST-CHANGES.md.
            self.assertNotRegex(text, r"\d{1,2}:\d{2}",
                                f"{text!r} looks like an absolute timestamp")
        # ...and at least one row must actually read as a duration, so a
        # formatter that returned "" everywhere cannot pass the loop above.
        self.assertTrue(any(t == "just now" or t.endswith(" ago") for t, _, _ in rows),
                        f"no row reads as relative time: {[r[0] for r in rows][:5]}")

    def test_the_queue_marker_is_the_sprite_icon_not_a_glyph(self):
        self.assertTrue(self._page.query_selector(".attention-index svg"),
                        "the queue marker has no sprite icon")
        self.assertEqual(self._page.inner_text(".attention-index").strip(), "")

    def test_queue_rows_are_flat_like_the_summary_strip(self):
        """The strip set the rule on this page: a readout carries a boundary,
        not a drop shadow."""
        shadowed = self._page.eval_on_selector_all(
            ".attention-item, .queue-clear",
            "els => els.filter(e => getComputedStyle(e).boxShadow !== 'none')"
            ".map(e => e.className)",
        )
        self.assertEqual(shadowed, [])

    def test_no_console_errors(self):
        self.assertEqual(self._errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)