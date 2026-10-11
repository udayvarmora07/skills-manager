"""Library list-pane chrome: the selection hint must never be amputated.

4.1c. Every other assertion about this hint checked that the sentence was
*present* in the DOM. It was present and it was clipped: `.selection-hint
> span` declared `text-overflow: ellipsis` over a 51-character sentence in a
257px box, so the safety warning rendered as "Batch actions apply only to the
visible filtere..." -- losing the word that says what the batch will touch.

Presence is not legibility, which is why the check here is
`scrollWidth <= clientWidth`: the question a reader has is whether the sentence
survives, and a text node answers that truthfully and a screenshot does not.

Runs under `python3 -m unittest discover -s tests/e2e` with Playwright on
PATH; it SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
import unittest

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

# Every width the list pane is laid out at, including the 320px floor the
# narrow band exists for.
WIDTHS = (320, 390, 768, 1280)


def _has_chromium():
    """True only when a browser is actually launchable."""
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: the selection-hint clipping check needs a "
    "real layout engine and is NOT verified by this skip",
)
class LibraryChromeTests(unittest.TestCase):
    server = None
    thread = None
    store = None

    @classmethod
    def setUpClass(cls):
        import tempfile
        import threading

        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)

        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-chrome-")
        cls.store = Store(cls._tmp)
        cls.store.init_db()
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        import shutil

        if cls.server:
            cls.server.shutdown()
            cls.thread.join(timeout=5)
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.click(".viewtabs button:has-text('Library')")
        self._page.wait_for_selector(".library-bar", timeout=15000)
        self._page.wait_for_selector(".selection-hint", timeout=15000)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _measure(self, width):
        self._page.set_viewport_size({"width": width, "height": 900})
        self._page.wait_for_timeout(150)
        return self._page.evaluate(
            """() => {
              const hint = document.querySelector('.selection-hint > span');
              if (!hint) return null;
              const cs = getComputedStyle(hint);
              return {
                text: hint.textContent,
                scrollW: hint.scrollWidth,
                clientW: hint.clientWidth,
                // How many separate client rects the painted line occupies: a
                // clipped single line paints one, a wrapped sentence two.
                rects: (() => { const r = document.createRange();
                  r.selectNodeContents(hint);
                  return Array.from(r.getClientRects()).map(b => Math.round(b.width)).filter(w => w > 0); })(),
                ellipsis: cs.textOverflow === 'ellipsis',
                nowrap: cs.whiteSpace === 'nowrap',
              };
            }"""
        )

    def test_the_selection_hint_is_never_clipped_at_any_pane_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                measured = self._measure(width)
                self.assertIsNotNone(measured)
                self.assertLessEqual(
                    measured["scrollW"],
                    measured["clientW"] + 1,
                    f"the hint is clipped at {width}px: {measured}",
                )

    def test_the_hint_is_not_configured_to_clip_at_all(self):
        """The mechanism, not the outcome.

        Measuring `scrollWidth <= clientWidth` alone passes on a rule that
        clips everything gracefully, so this pins the rule too: an ellipsis on
        this sentence is the defect returning, whatever the current copy
        happens to measure.
        """
        for width in (320, 1280):
            with self.subTest(width=width):
                measured = self._measure(width)
                self.assertFalse(measured["ellipsis"], width)
                self.assertFalse(measured["nowrap"], width)

    def test_the_hint_still_states_what_a_batch_will_touch(self):
        """Shortening the sentence must not have shortened the warning away.

        A hint that fits because it stopped saying anything is the failure this
        test exists to distinguish from the one it fixed.
        """
        text = self._page.eval_on_selector(".selection-hint > span", "el => el.textContent").strip()
        for word in ("Batch actions", "only", "visible"):
            self.assertIn(word, text, text)

    def test_the_select_button_is_still_reachable_at_the_narrow_floor(self):
        """The wrap must not have pushed the control out of reach."""
        for width in WIDTHS:
            with self.subTest(width=width):
                self._page.set_viewport_size({"width": width, "height": 900})
                self._page.wait_for_timeout(120)
                state = self._page.evaluate(
                    """() => {
                      const b = document.querySelector('.selection-toggle');
                      const r = b.getBoundingClientRect();
                      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
                      const hit = document.elementFromPoint(cx, cy);
                      return {w: Math.round(r.width), h: Math.round(r.height),
                              reachable: !!(hit && (hit === b || b.contains(hit)))};
                    }"""
                )
                self.assertTrue(state["reachable"], f"{width}px: {state}")
                self.assertGreaterEqual(state["h"], 24, f"{width}px: {state}")


if __name__ == "__main__":
    unittest.main()