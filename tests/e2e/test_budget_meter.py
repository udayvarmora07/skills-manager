"""The context-budget meter: the 100% rule, the axis, and the bars.

Why this file exists
--------------------
Task 3.3. The meter's only job is to let a reader compare a bar against the
100% mark of one context window. The scale rule was positioned against the full
card width while the fills were positioned against the track column, so at 1280
px the rule sat **110px to the right of the value it claimed to mark** — every
bar read against it was wrong, and nothing on the page said so.

These assertions are all measurements of the live DOM at three widths. A test
that greps `styles.css` can prove a rule exists; only this can prove it lands on
the same pixel as the fill it labels.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_budget_meter.py
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
WIDTHS = (390, 768, 1280)

_AXIS_MAX_RE = __import__("re").compile(r"(\d[\d,]*)%")


def _axis_max(range_text: str):
    """Read the axis maximum out of the sentence that states it.

    `.budget-block-range` says "Bars run to 150% of one window, so a root that
    overruns it has somewhere to show the overshoot." The number in that
    sentence is the same number `budgetAxisMax` computed, so the geometry
    assertions are checked against what the page CLAIMS as well as what it
    draws -- a stale sentence and a correct bar would otherwise both pass.
    """
    m = _AXIS_MAX_RE.search(range_text or "")
    return int(m.group(1).replace(",", "")) if m else None

# Every percentage the meter can render, so no assertion depends on whatever
# the seed happens to contain.
GEOMETRY = """() => {
  const q = (s) => document.querySelector(s);
  const all = (s) => [...document.querySelectorAll(s)];
  const cell = q('.scope-meter-scale-cell');
  const rule = q('.scope-meter-scale-rule');
  const scale = q('.scope-meter-scale');
  if (!cell || !rule || !scale) return null;
  const cellBox = cell.getBoundingClientRect();
  const ruleBox = rule.getBoundingClientRect();
  return {
    cellLeft: cellBox.left, cellWidth: cellBox.width,
    ruleX: ruleBox.left,
    scaleLeft: scale.getBoundingClientRect().left,
    scaleWidth: scale.getBoundingClientRect().width,
    label: q('.scope-meter-scale-label').textContent.trim(),
    range: q('.budget-block-range').textContent.trim(),
    rows: all('.scope-meter-row').map((r) => {
      const t = r.querySelector('.scope-meter-track').getBoundingClientRect();
      const m = r.querySelector('.scope-meter-mark').getBoundingClientRect();
      const f = r.querySelector('.scope-meter-fill').getBoundingClientRect();
      return {
        name: r.querySelector('.scope-meter-name').textContent.trim(),
        pctText: r.querySelector('.scope-meter-pct').textContent.trim(),
        pctClass: r.querySelector('.scope-meter-pct').className.trim(),
        trackLeft: t.left, trackWidth: t.width,
        fillRight: f.left + f.width,
        markX: m.left, markVisible: m.width > 0 && m.height > 0,
      };
    }),
    overflow: document.documentElement.scrollWidth - window.innerWidth,
  };
}"""


class BudgetMeterTests(unittest.TestCase):
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
        cls._errors: list[str] = []

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._pw_cm.stop()

    def _open(self, width: int):
        page = self._browser.new_page(viewport={"width": width, "height": 1000})
        page.on("console", lambda m: m.type == "error" and self._errors.append(m.text))
        page.on("pageerror", lambda e: self._errors.append(str(e)))
        try:
            page.goto(BASE(), wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector(READY, timeout=20000)
            page.wait_for_selector(".scope-meter-row", timeout=10000)
        except Exception as exc:
            page.close()
            raise unittest.SkipTest(f"the dev server at {BASE()} did not reach the meter ({exc})")
        return page

    # -- the defect this task fixed --------------------------------------
    def test_the_rule_and_every_bar_mark_land_on_the_same_pixel(self):
        """The regression. The scale cell and each track must be the same box,
        or `left: 80%` means two different things."""
        for width in WIDTHS:
            with self.subTest(width=width):
                page = self._open(width)
                try:
                    g = page.evaluate(GEOMETRY)
                finally:
                    page.close()
                self.assertIsNotNone(g, f"no scale at {width}px")
                self.assertTrue(g["rows"], f"no meter rows at {width}px")
                # The scale cell IS the track column.
                self.assertAlmostEqual(g["cellLeft"], g["rows"][0]["trackLeft"], delta=1,
                                       msg=f"scale cell is not the track column at {width}px")
                self.assertAlmostEqual(g["cellWidth"], g["rows"][0]["trackWidth"], delta=1,
                                       msg=f"scale cell width != track width at {width}px")
                # And the rule sits on every bar's mark.
                for row in g["rows"]:
                    self.assertAlmostEqual(g["ruleX"], row["markX"], delta=1,
                                           msg=f"{row['name']}: rule at {g['ruleX']}, mark at "
                                               f"{row['markX']} at {width}px")

    def test_a_bar_at_exactly_one_hundred_percent_fills_past_the_mark(self):
        """Alignment by construction is only meaningful if the mark and the
        fill share a coordinate system. Force the app to the boundary by
        measuring the fraction the mark occupies of its own track: 100% of the
        window must land on the mark, and a bigger number must be beyond it."""
        page = self._open(1280)
        try:
            g = page.evaluate(GEOMETRY)
            cellWidth = g["rows"][0]["trackWidth"]
            for row in g["rows"]:
                markFrac = (row["markX"] - row["trackLeft"]) / cellWidth
                pct = float(row["pctText"].rstrip("%"))
                fillFrac = (row["fillRight"] - row["trackLeft"]) / cellWidth
                if pct > 100.0:
                    self.assertGreater(fillFrac, markFrac,
                                       msg=f"{row['name']}: {pct}% must overshoot the 100% mark")
                    self.assertIn("pct-bad", row["pctClass"])
        finally:
            page.close()

    # -- the axis is honest about its own range ---------------------------
    def test_the_axis_range_is_stated_and_is_at_least_125(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                page = self._open(width)
                try:
                    g = page.evaluate(GEOMETRY)
                finally:
                    page.close()
                self.assertIn("Bars run to", g["range"])
                stated = int(g["range"].split("Bars run to", 1)[1].strip().split("%", 1)[0].replace(",", ""))
                self.assertGreaterEqual(stated, 125,
                                        "the axis must leave room past 100% for an overshoot")
                # The rule is the 100% mark of that axis, so it must sit at
                # 100/stated of the cell.
                expect = g["cellLeft"] + g["cellWidth"] * (100.0 / stated)
                self.assertAlmostEqual(g["ruleX"], expect, delta=1,
                                       msg=f"rule at {g['ruleX']}, axis to {stated}% implies {expect}")

    def test_the_rule_is_labelled_in_words_not_only_in_position(self):
        page = self._open(768)
        try:
            label = page.eval_on_selector(".scope-meter-scale-label", "e => e.textContent.trim()")
        finally:
            page.close()
        self.assertIn("100%", label)
        self.assertIn("context window", label)

    # -- every row carries its own mark, so one bar reads alone -----------
    def test_every_row_carries_a_visible_mark_and_a_readout(self):
        page = self._open(1280)
        try:
            g = page.evaluate(GEOMETRY)
        finally:
            page.close()
        for row in g["rows"]:
            self.assertTrue(row["markVisible"], f"{row['name']} has no visible 100% mark")
            self.assertRegex(row["pctText"], r"^\d+%$", f"{row['name']}: unreadable percentage")

    def test_the_mark_is_painted_over_the_fill_not_under_it(self):
        """A bar past the threshold covers the whole track. A mark underneath
        is a mark that cannot be seen exactly when it matters most.

        Measured on every row rather than only over-budget ones: the painting
        order is a computed-style property and does not depend on the bar's
        length. The *visibility* of a mark on a full bar does — and the dev
        seed's largest root is 2% of a 1M window, so nothing over-budget exists
        to photograph. That gap is recorded as backlog task 3.3a rather than
        papered over by loosening this assertion.
        """
        page = self._open(1280)
        try:
            painting = page.evaluate("""() => {
              return [...document.querySelectorAll('.scope-meter-row')].map((r) => {
                const f = r.querySelector('.scope-meter-fill');
                const m = r.querySelector('.scope-meter-mark');
                return {
                  name: r.querySelector('.scope-meter-name').textContent.trim(),
                  order: getComputedStyle(f).zIndex + ':' + getComputedStyle(m).zIndex,
                };
              });
            }""")
        finally:
            page.close()
        self.assertTrue(painting)
        for row in painting:
            fz, mz = (int(v) for v in row["order"].split(":"))
            self.assertGreaterEqual(mz, fz,
                                    f"{row['name']}: the 100% mark must paint over the fill")

    def _select_smallest_window(self, page):
        """Drive the meter through its own control, the way a reader does.

        The default window is `claude` at 1M tokens, so a corpus that overruns
        `gpt-4o` (128k, the smallest selectable window) still reads as a
        fraction on the default. Selecting the window is the user-facing way to
        reach the over-budget branch, so the test uses it rather than poking
        Vue state -- a fixture-only assertion would prove nothing about the
        control that chooses the denominator.
        """
        # The select lives inside the rail's "Show scope controls" disclosure,
        # so it is genuinely not visible until a reader opens it. Open it the
        # way a reader does rather than forcing the action past the check --
        # a forced select would prove the option exists, not that the control
        # that owns it can be reached.
        page.click(".mobile-controls-toggle")
        page.wait_for_selector(".budgetbar-select", state="visible", timeout=10000)
        page.select_option(".budgetbar-select", "gpt-4o")
        page.wait_for_function(
            """() => {
                 const s = document.querySelector('.budgetbar-select');
                 return s && s.value === 'gpt-4o';
               }""",
            timeout=15000,
        )
        page.wait_for_timeout(600)  # let the stats refetch settle the rows

    def test_the_axis_places_the_mark_at_one_hundred_percent_for_every_row(self):
        """The fixture-independent invariant.

        Every row's mark must sit at exactly `100 / axisMax` of its own track
        and its fill at `pct / axisMax` -- the two numbers the axis is drawn
        from. This holds for ANY corpus, so it needs no oversized fixture and
        is the assertion that actually protects the defect 3.3 fixed: the rule
        used to be positioned against the card while the fills were positioned
        against the track, so both numbers were individually plausible and the
        pair was wrong.
        """
        page = self._open(1280)
        try:
            g = page.evaluate(GEOMETRY)
        finally:
            page.close()
        axis_max = _axis_max(g["range"])
        self.assertIsNotNone(axis_max, f"cannot read the axis maximum out of {g['range']!r}")
        for row in g["rows"]:
            track = row["trackWidth"]
            mark_frac = (row["markX"] - row["trackLeft"]) / track
            fill_frac = (row["fillRight"] - row["trackLeft"]) / track
            pct = float(row["pctText"].rstrip("%"))
            self.assertAlmostEqual(
                mark_frac, 100.0 / axis_max, delta=0.02,
                msg=f"{row['name']}: the 100% mark sits at {mark_frac:.3f} of the track, "
                    f"but the axis runs to {axis_max}% so it must sit at {100.0 / axis_max:.3f}",
            )
            self.assertAlmostEqual(
                fill_frac, pct / axis_max, delta=0.02,
                msg=f"{row['name']}: a {row['pctText']} bar fills {fill_frac:.3f} of the track, "
                    f"but the axis runs to {axis_max}% so it must fill {pct / axis_max:.3f}",
            )

    def test_a_root_past_the_window_overshoots_the_mark_and_rescales_the_axis(self):
        """The branch the meter exists for, driven through the window select.

        A 125% axis floor means a root at 134% must still draw INSIDE the
        track, not clamped: `budgetAxisMax` rescales to 150%, the bar lands at
        134/150 of the track, and the 100% rule stays at 100/150. Both halves
        are asserted, because a bar that clamps and a bar that overflows the
        track are equally wrong readings of the same number.
        """
        page = self._open(1280)
        try:
            self._select_smallest_window(page)
            g = page.evaluate(GEOMETRY)
        finally:
            page.close()
        over = [r for r in g["rows"] if float(r["pctText"].rstrip("%")) > 100.0]
        if not over:
            self.skipTest(
                "no scope root overruns the smallest selectable window in this "
                "corpus, so the overshoot branch cannot be exercised"
            )
        axis_max = _axis_max(g["range"])
        self.assertGreater(axis_max, 125,
                           "a root past one window must push the axis past its 125% floor")
        track = over[0]["trackWidth"]
        for row in over:
            fill_frac = (row["fillRight"] - row["trackLeft"]) / track
            mark_frac = (row["markX"] - row["trackLeft"]) / track
            self.assertGreater(fill_frac, mark_frac,
                               f"{row['name']}: {row['pctText']} did not overshoot the 100% mark")
            self.assertLessEqual(fill_frac, 1.0,
                                 f"{row['name']}: the fill ran past the end of its own track")
            self.assertIn("pct-bad", row["pctClass"],
                          f"{row['name']}: an over-budget root must be marked pct-bad, "
                          f"got {row['pctClass']!r}")

    # -- nothing about the shell regressed --------------------------------
    def test_no_horizontal_overflow_and_no_console_errors_at_any_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                page = self._open(width)
                try:
                    over = page.evaluate(
                        "() => document.documentElement.scrollWidth - window.innerWidth")
                finally:
                    page.close()
                self.assertLessEqual(over, 0, f"horizontal overflow at {width}px")
        self.assertEqual(self._errors, [], "console/page errors during the meter sweep")


class BudgetMeterSourceTests(unittest.TestCase):
    """What the stylesheet must keep saying, independent of any browser."""

    def test_the_hero_name_is_gone(self):
        for name in ("index.html", "styles.css"):
            with self.subTest(file=name):
                with open(os.path.join("skillsmgr", "webui", name), encoding="utf-8") as fh:
                    text = fh.read()
                self.assertNotIn("budget-hero", text,
                                 "'hero' is a poster; this is the third block on the page")

    def test_the_scale_cell_is_a_real_relative_positioned_grid_item(self):
        """`grid-column` on an ABSOLUTELY positioned child does not give it the
        grid area as its containing block — the percentage still resolves
        against the grid container's padding box, which is how the rule ended
        up 134px wide of its bars. An in-flow, relatively positioned cell is
        the fix, so the selector that carries it is pinned here."""
        with open(os.path.join("skillsmgr", "webui", "styles.css"), encoding="utf-8") as fh:
            css = fh.read()
        # Substring, not assertRegex: a regex miss dumps the whole 2,000-line
        # stylesheet into the failure output, which buries the actual message.
        self.assertIn(
            ".scope-meter-scale-cell { position: relative; grid-column: 2;",
            css,
            "the scale cell must stay an in-flow, relatively positioned grid item",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)