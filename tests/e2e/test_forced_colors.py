"""6.2 e2e — forced-colors, measured in the browser.

`tests/test_redesign_forced_colors.py` reads the stylesheet and can only say
what was WRITTEN.  It cannot say what the reader gets, because in forced-colors
mode the UA overrides the author: it forces `box-shadow: none`, repaints every
author colour from the system palette, and reports no error while it does.

So this asks the browser, with `forcedColors: 'active'`:

  1. Every `.overview-metrics` cell still carries a visible separator.  The
     control is measured, not asserted: under the old rule Chromium reports
     `box-shadow: none` on every one of them and the strip is undivided.  A
     test that only counted cells would have passed all along -- there is text
     in every cell -- which is why the property has to be the claim.

  2. The separator is `outline`/`border`, never `box-shadow`, so it survives.

  3. The grid gap is 0, because the 1px gap was painted in the container
     background and forced-colors paints that as Canvas.

  4. The cells still sit on a 4-column grid at 1440 -- an `outline` that also
     broke the layout would satisfy 1 and 3.

  5. The colour swatch still shows a colour: `forced-color-adjust: none` is a
     real escape hatch and this is the one element entitled to it.

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
import shutil
import sys
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# In the page.  Reports the cells' separator state as the UA actually resolves
# it -- not what the stylesheet said.
CELLS = r"""
() => {
  const host = document.querySelector('.overview-metrics');
  if (!host) return null;
  const hc = getComputedStyle(host);
  const cells = Array.from(host.children).map((el) => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      w: Math.round(r.width), h: Math.round(r.height),
      shadow: cs.boxShadow,
      outlineWidth: cs.outlineWidth,
      outlineStyle: cs.outlineStyle,
      outlineColor: cs.outlineColor,
      borderTop: cs.borderTopWidth,
      adjust: cs.forcedColorAdjust,
      text: (el.textContent || '').trim().slice(0, 24),
    };
  });
  return {
    gap: hc.gap, cols: hc.gridTemplateColumns.split(' ').filter(Boolean).length,
    bg: hc.backgroundColor, cells,
  };
}
"""


def _has_chromium():
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


def _px(value):
    """`computedStyle.outlineWidth` is `'1px'` or `'medium'`; float() rejects
    both, so the unit is stripped rather than the value guessed at."""
    text = str(value or "0").strip()
    if text.endswith("px"):
        text = text[:-2]
    return float(text) if text.replace(".", "", 1).isdigit() else 0.0


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: this measures what the UA does to the "
    "author's colours, which no source contract can stand in for",
)
class ForcedColorsRenderedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-forced-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            rh = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                rh, ".cache", "ms-playwright")
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        # An empty library renders an empty state and every assertion about the
        # metric cells would pass without reaching one of them.
        cls.store.create("forced-colors-alpha", "Fixture.",
                         body="# forced-colors-alpha\n\nFixture body.\n")
        cls.store.create("forced-colors-beta", "Second fixture.",
                         body="# forced-colors-beta\n\nFixture body.\n")
        cls.store.create("forced-colors-gamma", "Third fixture.",
                         body="# forced-colors-gamma\n\nFixture body.\n")
        cls.store.create("forced-colors-delta", "Fourth fixture.",
                         body="# forced-colors-delta\n\nFixture body.\n")
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        for k, v in cls._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self._page = self._browser.new_page(viewport={"width": 1440, "height": 900})
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_selector("#app", timeout=15000)

    def tearDown(self):
        self._page.emulate_media(forced_colors="none")
        self._browser.close()
        self._pw.stop()

    def _cells_forced(self):
        self._page.emulate_media(forced_colors="active")
        self._page.wait_for_timeout(200)
        try:
            return self._page.evaluate(CELLS)
        finally:
            self._page.emulate_media(forced_colors="none")

    def test_the_metric_cells_keep_a_separator_the_ua_does_not_drop(self):
        """The claim is the separator, not the cell count: every cell has text
        and would pass a test that only asked whether the strip rendered."""
        got = self._cells_forced()
        self.assertIsNotNone(got, "no .overview-metrics on the default view")
        cells = got["cells"]
        self.assertGreaterEqual(len(cells), 4, "fixture must reach a full row")
        for c in cells:
            survives = (c["shadow"] in (None, "none")) and (
                (_px(c["outlineWidth"]) > 0 and c["outlineStyle"] != "none")
                or _px(c["borderTop"]) > 0)
            self.assertTrue(
                survives,
                "cell “%s” lost its only separator in forced-colors: "
                "box-shadow=%s outline=%s/%s border=%s"
                % (c["text"], c["shadow"], c["outlineWidth"], c["outlineStyle"],
                   c["borderTop"]))

    def test_the_separator_is_not_carried_by_box_shadow(self):
        """The control for the test above: forced-colors resolves
        `box-shadow` to `none`, so a cell still reporting a shadow would mean
        the browser is NOT in forced-colors and the whole suite is vacuous."""
        got = self._cells_forced()
        for c in got["cells"]:
            self.assertIn(c["shadow"], (None, "none"))

    def test_the_gap_is_closed_so_the_separator_is_not_the_container_background(self):
        got = self._cells_forced()
        self.assertEqual(got["gap"], "0px",
                         "a 1px gap is painted in the container background, "
                         "which forced-colors renders as Canvas")

    def test_the_grid_is_untouched_by_the_substitution(self):
        """An outline that also broke the layout would satisfy the first test."""
        got = self._cells_forced()
        self.assertEqual(got["cols"], 4)
        self.assertEqual(len({c["w"] for c in got["cells"]}), 1,
                         "cells in a row must be the same width")

    def test_the_colour_swatch_still_shows_a_colour(self):
        """The one element entitled to `forced-color-adjust: none`. As Canvas
        it is an empty outlined circle, which says nothing about anything."""
        self._page.click('.viewtabs button:has-text("Settings"), '
                         '.navigation-rail button[data-tip="Settings"]')
        self._page.wait_for_timeout(400)
        self._page.click('.viewtabs button:has-text("Settings"), '
                         '.navigation-rail button[data-tip="Settings"]')
        self._page.wait_for_timeout(400)
        if self._page.query_selector(".settings-preview-swatch") is None:
            self.skipTest("no colour swatch rendered on Settings in this build")
        self._page.emulate_media(forced_colors="active")
        self._page.wait_for_timeout(180)
        painted = self._page.eval_on_selector(
            ".settings-preview-swatch",
            "el => { const c = getComputedStyle(el).backgroundColor;"
            " const m = c.match(/rgba?\\(([^)]+)\\)/);"
            " const cs = getComputedStyle(el);"
            " return {alpha: m ? (m[1].split(',')[3] ? +m[1].split(',')[3] : 1) : 0,"
            "         adjust: cs.forcedColorAdjust}; }")
        # Read BOTH under forced colors: `forcedColorAdjust` outside it is
        # `auto` by definition, so checking it after restoring the media
        # emulation asserts the browser's default, not this stylesheet.
        self._page.emulate_media(forced_colors="none")
        self.assertGreater(painted["alpha"], 0,
                           "the swatch is transparent under forced-colors: "
                           "as Canvas it is an empty outlined circle, which "
                           "says nothing about the colour it exists to show")
        self.assertEqual(painted["adjust"], "none")

    def test_no_view_logs_an_error_in_forced_colors(self):
        for view in ("Library", "Profiles", "Workspaces", "Install",
                     "Recovery", "Quality", "Settings"):
            self._page.emulate_media(forced_colors="active")
            self._page.click(
                f'.viewtabs button:has-text("{view}"), '
                f'.navigation-rail button[data-tip="{view}"]')
            self._page.wait_for_timeout(240)
        self._page.emulate_media(forced_colors="none")
        self.assertEqual(self._errors, [])


if __name__ == "__main__":
    unittest.main()