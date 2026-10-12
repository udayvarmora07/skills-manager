"""4.7d — the destructive action is not promoted by the width of the pane.

Measured before anything changed: the four detail actions wrap at 390 and at
768, and the one left ALONE on the wrapped line grew to fill it. Remove
measured **358x44 inside a 358px row** at 390, against 98x44 for the three
buttons above it — the widest element in the pane, wider than any other action,
because of where it happened to land rather than what it means. A destructive
control that reads as a bigger decision than the row it belongs to is the
opposite of what the observed-state vocabulary (RULES #12) is for.

`flex: 1` in the narrow band was the cause. The interesting part is that the
FIRST fix was wrong about the mechanism: `flex: 1 1 auto` still measured 358px
while shrinking its siblings, because `flex-grow: 1` hands an item every pixel
of free space on a line where it is the only one. Only `flex-grow: 0` stops it.

**Every exclusion from a containment check needs a matching assertion on the
axis it excludes** (4.3b's lesson), so both halves are asserted at all three
widths: no action is wider than the row, and no action is dramatically wider
than its siblings.

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
import sys
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright


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
    "Playwright/Chromium unavailable: this measures rendered button widths, "
    "which are NOT verified by this skip",
)
class DetailActionRowTests(unittest.TestCase):
    WIDTHS = (390, 768, 1280)

    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-actions-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                real_home, ".cache", "ms-playwright")
        # RULES #8: agent SCOPES come from HOME, not the data dir.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        cls.store.create("row-target", "Row target.", body="# row\n\nBody text.")
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        import shutil

        cls.server.shutdown()
        cls.thread.join(timeout=5)
        for key, value in cls._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _row_at(self, width):
        page = self._browser.new_page(viewport={"width": width, "height": 900})
        page.goto(self.server.url, wait_until="networkidle")
        if width <= 760:
            # Below 761px the rail is the 2.1e2 drawer. Not cosmetic: the
            # Library tab lives behind it, and every capture script on this
            # project has been bitten by assuming otherwise.
            page.click(".nav-drawer-trigger")
            page.wait_for_timeout(300)
        page.click('.viewtabs button:has-text("Library")')
        page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        page.click('.skilllist > li[data-skill-key]:has-text("row-target")')
        page.wait_for_selector(".detail-actions", timeout=10000)
        page.wait_for_timeout(400)
        return page, page.evaluate(
            """() => {
              const row = document.querySelector('.detail-actions');
              const rb = row.getBoundingClientRect();
              return {
                rowWidth: Math.round(rb.width),
                buttons: [...row.querySelectorAll('button')].map(b => {
                  const r = b.getBoundingClientRect();
                  return { label: b.textContent.trim().replace(/\\s+/g, ' '),
                           w: Math.round(r.width), h: Math.round(r.height),
                           danger: b.className.includes('danger') };
                }),
              };
            }""")

    def test_no_action_is_wider_than_the_row_it_sits_in(self):
        for width in self.WIDTHS:
            with self.subTest(width=width):
                page, data = self._row_at(width)
                try:
                    for b in data["buttons"]:
                        self.assertLessEqual(
                            b["w"], data["rowWidth"],
                            f"{b['label']!r} measured {b['w']}px in a "
                            f"{data['rowWidth']}px row at {width}px")
                finally:
                    page.close()

    def test_the_destructive_action_is_not_promoted_by_the_width_of_the_pane(self):
        """The defect itself, and it is a RATIO claim rather than a width one.

        Asserted as "not dramatically wider than its siblings", because the
        absolute number depends on the label and the viewport. A test that
        pinned Remove at exactly 97px would break the day the label changes
        while the defect — a lone wrapped action growing to fill its line —
        came straight back.
        """
        for width in self.WIDTHS:
            with self.subTest(width=width):
                page, data = self._row_at(width)
                try:
                    danger = [b for b in data["buttons"] if b["danger"]]
                    self.assertEqual(len(danger), 1,
                                     f"expected exactly one destructive action, "
                                     f"measured: {data['buttons']}")
                    remove = danger[0]
                    peers = [b["w"] for b in data["buttons"] if not b["danger"]]
                    widest_peer = max(peers)
                    self.assertLessEqual(
                        remove["w"], widest_peer * 1.35,
                        f"the destructive action measured {remove['w']}px against "
                        f"a widest sibling of {widest_peer}px at {width}px: it is "
                        "being promoted by where it wrapped, not by what it does")
                finally:
                    page.close()

    def test_the_action_row_keeps_its_touch_target_floor_on_a_phone(self):
        """The honest cost of `flex-grow: 0`, asserted so it cannot be paid
        silently: the row stops distributing slack, and the target floor is a
        property of HEIGHT, so it must be unaffected. RULES #13."""
        page, data = self._row_at(390)
        try:
            for b in data["buttons"]:
                self.assertGreaterEqual(
                    b["h"], 40,
                    f"{b['label']!r} measured {b['h']}px tall at 390px, under "
                    "the 40px floor")
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()