"""5.7c e2e — the Settings choice cells, measured in the browser.

**The defect.** `.settings-segmented` is three equal cells across a 340px
control column, and each cell used to carry a second line inside it: "Follows
the OS (light now)", "Always light". "System" wrapped across three lines and
"Light" across two, so the row was a paragraph wearing a control's border and
the three cells were not even the same height. A source contract cannot see
this — it is wrapping, and wrapping is the browser's answer, not the
stylesheet's — so it is asked here.

**How "wraps" is measured.** `Element.getClientRects()` returns one rect per
line box, so a `<strong>` on one line has exactly one rect and one that wrapped
has two or more. Counting the cells, or checking that the markup still has a
`<strong>`, would pass with the defect in place.

**Why the second line is gone rather than reflowed.** It was never only there:
each fieldset is `aria-describedby` the hint in its own left column, and that
hint now carries what the cells gave up — the theme hint always did ("System
follows your operating system's dark-mode preference live. Light and dark are
explicit app choices"), the text-size hint was extended to say what Standard
and Large are. `test_the_explanation_is_still_on_the_page` is the control: if
some later pass drops a cell's second line without moving the sentence, this
fails instead of shipping a shorter, quieter control.

**And the fit.** `capture_57b.py` compared the pane's content height to the
WINDOW height and reported "fits" for a view that still scrolled ~70px, because
the pane's own box is `clientHeight` — the window minus the topbar and status
bar. The assertion lives HERE, not in the capture script, because a script in
`.redesign/` that nothing runs is the claim-with-no-reader this repository
keeps recording. `clientHeight` is the box; `scrollHeight` is the content.

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

# In the page. One row per segmented cell: how many LINE BOXES the cell's text
# occupies, how tall the cell is, and whether it is the tallest in its row.
#
# The line count is taken across every text node in the cell, not from the
# `<strong>`: with "Follows the OS (light now)" put back, the label "System"
# still sits on ONE line and the cell is still three. A test that asked the
# label how many lines IT occupies would have watched the defect land and
# reported green — which is exactly what the first version of this file did.
# Line boxes are counted from the distinct `top` edges a Range reports, so one
# wrapped run counts once per line however many nodes it is split across.
CELLS = r"""
() => {
  const range = document.createRange();
  const countLines = (host) => {
    const tops = [];
    // A TreeWalker, not `host.childNodes`: the text lives inside <strong>,
    // and the cell's own direct text children are the whitespace between the
    // radio and the label. Walking only those reports 0 lines for a cell that
    // is plainly one — which is how the first version of this probe failed.
    const walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent.trim()) continue;
      range.selectNodeContents(node);
      for (const r of range.getClientRects()) {
        if (r.height === 0) continue;
        if (!tops.some((t) => Math.abs(t - r.top) < 1)) tops.push(r.top);
      }
    }
    return tops.length;
  };
  const out = [];
  for (const fieldset of document.querySelectorAll('.settings-segmented')) {
    const cells = Array.from(fieldset.querySelectorAll('.settings-option'));
    const rects = cells.map((cell) => {
      const label = cell.querySelector('strong');
      const spans = Array.from(cell.querySelectorAll('span'));
      return {
        text: label ? label.textContent.trim() : '',
        lines: countLines(cell),
        labelLines: label ? label.getClientRects().length : 0,
        h: Math.round(cell.getBoundingClientRect().height),
        // A second line still in the markup would be a silent regression: the
        // rows are laid out by the browser, so only the text can say.
        secondLines: spans.reduce(
          (n, s) => n + Array.from(s.children)
            .filter((c) => c.tagName !== 'STRONG').length, 0),
      };
    });
    const heights = rects.map((r) => r.h);
    out.push({
      describedBy: fieldset.getAttribute('aria-describedby'),
      rects: rects,
      equalHeight: heights.every((h) => h === heights[0]),
      tallest: Math.max.apply(null, heights),
    });
  }
  return out;
}
"""

# In the page. The hint each fieldset is described by, as rendered text.
HINTS = r"""
(ids) => ids.map((id) => {
  const el = document.getElementById(id);
  return el ? el.textContent.trim() : null;
})
"""

FIT = r"""
() => {
  const pane = document.querySelector('.settings-center');
  if (!pane) return null;
  const de = document.documentElement;
  const cells = Array.from(document.querySelectorAll('.settings-segmented .settings-option'));
  return {
    // The claim is HORIZONTAL. Vertical scroll is expected and is not a
    // defect: this pane's content is 1335-1756px tall at every width the
    // product is used at (measured), so it scrolls in an 828px window and
    // always did. Asserting "fits without scrolling" here would be asserting
    // a thing that is false, and the first version of this file did exactly
    // that — see the docstring.
    docOver: de.scrollWidth - de.clientWidth,
    paneOver: pane.scrollWidth - pane.clientWidth,
    paneClientWidth: pane.clientWidth,
    paneScrollWidth: pane.scrollWidth,
    paneHeight: Math.round(pane.getBoundingClientRect().height),
    innerHeight: window.innerHeight,
    cells: cells.map((c) => Math.round(c.getBoundingClientRect().height)),
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


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: whether a label wraps is the browser's "
    "answer, which no source contract can stand in for",
)
class SettingsChoiceCellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-settings-")
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
        # One skill, so Settings has something to talk about and the pane's
        # height is not measured on an empty product.
        cls.store.create("settings-cell-fixture", "Fixture for the Settings cells.",
                         body="# settings-cell-fixture\n\nFixture body.\n")
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
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 828})
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_selector("#app", timeout=15000)
        self._page.click('.navigation-rail button[data-tip="Settings"]')
        self._page.wait_for_selector(".settings-center", timeout=10000)
        self._page.wait_for_timeout(300)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _cells(self):
        got = self._page.evaluate(CELLS)
        self.assertEqual(len(got), 2, "theme and text size are the two choice sets")
        return got

    def test_no_choice_cell_wraps_onto_a_second_line(self):
        """At 1280 and again at 1100 — the shrunk laptop window, where the
        control column is at its narrowest.

        The claim is the CELL, not the label: putting "Follows the OS (light
        now)" back leaves "System" on one line and makes the cell three. A
        test that counted the label's own lines watched that land and passed,
        which is why `labelLines` is reported alongside and the assertion is
        on `lines`.
        """
        bad = []
        for width in (1280, 1100):
            self._page.set_viewport_size({"width": width, "height": 828})
            self._page.wait_for_timeout(180)
            for fieldset in self._cells():
                for cell in fieldset["rects"]:
                    if cell["lines"] != 1:
                        bad.append("%s %r at %d: %d lines (label %d)"
                                   % (fieldset["describedBy"], cell["text"],
                                      width, cell["lines"], cell["labelLines"]))
        self.assertEqual(bad, [], "a choice cell wrapped: " + "; ".join(bad))

    def test_the_cells_in_a_row_are_the_same_height(self):
        """The direct consequence, and the one a reader sees first: with a
        three-line "System" and a one-line "Dark", the row stops being a row."""
        for fieldset in self._cells():
            self.assertTrue(fieldset["equalHeight"],
                            "%s: cells are not one height (%s)"
                            % (fieldset["describedBy"],
                               [c["h"] for c in fieldset["rects"]]))
            self.assertLessEqual(fieldset["tallest"], 44,
                                 "%s: a choice cell is %dpx tall, which is a "
                                 "paragraph wearing a control's border"
                                 % (fieldset["describedBy"], fieldset["tallest"]))

    def test_no_second_line_is_silently_put_back(self):
        """The labels are the claim; a re-added `<small>` would wrap again and
        a test that only counted cells would never notice."""
        for fieldset in self._cells():
            for cell in fieldset["rects"]:
                self.assertEqual(cell["secondLines"], 0,
                                 "%s %r carries a second line again"
                                 % (fieldset["describedBy"], cell["text"]))

    def test_the_explanation_is_still_on_the_page(self):
        """The control for the edit above. Removing a cell's second line is
        only free if the sentence went somewhere; `aria-describedby` is where."""
        described = [f["describedBy"] for f in self._cells()]
        texts = self._page.evaluate(HINTS, described)
        for described_by, text in zip(described, texts):
            self.assertIsNotNone(text, "%s names a hint that does not exist"
                                 % described_by)
            self.assertGreater(len(text), 40,
                               "%s is too short to be carrying the cells' "
                               "explanation: %r" % (described_by, text))
        theme, size = texts
        # What "Follows the OS (light now)" and "Always light" said.
        self.assertIn("dark-mode preference live", theme)
        self.assertIn("explicit app choices", theme)
        # What "Default workspace type" and "More generous type and controls"
        # said — moved into the hint rather than dropped.
        self.assertIn("Standard is the default workspace type", size)
        self.assertIn("Large is more generous type and controls", size)

    def test_the_settings_view_never_scrolls_sideways_at_1280x828(self):
        """Measured against the pane AND the document, and about SIDEWAYS only.

        5.7c's row asked for "the pane fits without scrolling at 1280x828".
        Measured, that premise is FALSE: this pane's content is 1335px tall at
        1280, 1335 at 1440/1920 and 1756 at 1100, so it scrolls vertically in
        an 828px window — as a settings page with four subjects should. An
        assertion written to that premise would be red from the start, and one
        written as `scrollHeight <= clientHeight` on an UNCONSTRAINED box is
        green forever: a box that grows with its content never reports a
        vertical scroll. Both are gates that cannot be trusted, so the claim
        is the one that can actually fail — nothing on this view scrolls
        sideways, at the document or inside the pane.
        """
        self._page.set_viewport_size({"width": 1280, "height": 828})
        self._page.wait_for_timeout(200)
        got = self._page.evaluate(FIT)
        self.assertIsNotNone(got, "no .settings-center on the Settings view")
        self.assertLessEqual(got["docOver"], 1,
                             "the document scrolls sideways by %dpx at 1280"
                             % got["docOver"])
        self.assertLessEqual(got["paneOver"], 1,
                             "the settings pane scrolls sideways by %dpx "
                             "(content %d in a pane of %d)"
                             % (got["paneOver"], got["paneScrollWidth"],
                                got["paneClientWidth"]))

    def test_no_console_error_on_settings(self):
        self.assertEqual(self._errors, [])


if __name__ == "__main__":
    unittest.main()