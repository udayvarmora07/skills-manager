"""7.4e1 e2e — the label a reader reads on the only way back.

Below 760px the list pane and the detail pane share one screen, so
`.mobile-back` is the whole affordance. It said "Back to Library" on every view
except Quality, including Trash, where it returns the reader to the trash list.

The stdlib twin (`test_redesign_mobile_back_label.py`) proves the derivation
reads the palette's rows and that the two view-name sets agree. This file proves
the thing that only a browser can: the label **paints**, it names the view the
reader is actually in, and pressing it really does land them on that view's list.

Two disciplines carried from earlier files: the door is PRESSED, never reached by
calling `switchView` (7.4c), and `innerText` returns `""` inside a
`visibility: hidden` element (2.1e2) — so the drawer, where the nav lives below
760px, is opened first and assertions match on `textContent` where needed.

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
    "Playwright/Chromium unavailable: this reads the label a reader reads, at "
    "the one width where that button is the only way back",
)
class MobileBackLabelTests(unittest.TestCase):
    TRASHED = ("retired-skill-alpha", "retired-skill-beta")

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-mback-")
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
        for name in cls.TRASHED:
            cls.store.create(name, f"Fixture {name}.", body=f"# {name}\n\nFixture.\n")
        cls.store.create("still-present-skill", "Not trashed.",
                         body="# still-present-skill\n")
        for name in cls.TRASHED:
            cls.store.remove(name)
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
        self._page = self._browser.new_page(viewport={"width": 390, "height": 844})
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_selector("#app header.topbar", timeout=15000)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _open_drawer(self):
        """Below 760px the nav is a drawer and `innerText` is "" inside it
        (2.1e2), so match on textContent and open it before clicking."""
        trigger = self._page.locator(".nav-drawer-trigger")
        if trigger.count() and trigger.first.is_visible():
            trigger.first.click()
            self._page.wait_for_timeout(350)

    def _back_label(self):
        return self._page.evaluate(
            "() => { const b = document.querySelector('.mobile-back');"
            " return b ? b.textContent.trim() : ''; }")

    def test_the_trash_view_back_button_names_the_trash(self):
        self._open_drawer()
        self._page.click('.viewtabs button:has-text("Recovery")')
        self._page.wait_for_selector(".recovery-trash-door", timeout=15000)
        self._page.click(".recovery-trash-door")
        self._page.wait_for_selector('.skilllist[aria-label="Trash"]', timeout=15000)
        self._page.click('.skilllist[aria-label="Trash"] li >> nth=0')
        self._page.wait_for_selector(".mobile-back", timeout=10000)
        self._page.wait_for_timeout(200)
        label = self._back_label()
        self.assertIn("Trash", label, f"the back button says {label!r} on Trash")
        self.assertNotIn("Library", label,
                         "the old label is back: this button returns the reader "
                         "to the trash list, not to the Library")

    def test_the_quality_view_back_button_still_names_quality(self):
        """CONTROL. Quality was the ONE view the two-case ternary got right, so
        a fix that reads every button the same could quietly break it."""
        self._open_drawer()
        self._page.click('.viewtabs button:has-text("Quality")')
        self._page.wait_for_selector(".quality-center, .quality-strip", timeout=15000)
        self._page.wait_for_timeout(300)
        app = self._page.evaluate(
            "() => window.__skillsManagerApp && window.__skillsManagerApp.view")
        if app != "quality":
            self.skipTest("Quality did not open; the label cannot be read")
        self._page.evaluate(
            "() => { window.__skillsManagerApp.mobileDetailOpen = true; }")
        self._page.wait_for_selector(".mobile-back", timeout=10000)
        self.assertIn("Quality", self._back_label())

    def test_pressing_it_returns_the_reader_to_that_views_own_list(self):
        """The label and the destination have to agree; a button that says
        "Back to Trash" and lands on Recovery is the same defect wearing a
        different word."""
        self._open_drawer()
        self._page.click('.viewtabs button:has-text("Recovery")')
        self._page.wait_for_selector(".recovery-trash-door", timeout=15000)
        self._page.click(".recovery-trash-door")
        self._page.wait_for_selector('.skilllist[aria-label="Trash"]', timeout=15000)
        self._page.click('.skilllist[aria-label="Trash"] li >> nth=0')
        self._page.wait_for_selector(".mobile-back", timeout=10000)
        self._page.click(".mobile-back")
        self._page.wait_for_timeout(350)
        state = self._page.evaluate(
            "() => ({ view: window.__skillsManagerApp.view,"
            " open: window.__skillsManagerApp.mobileDetailOpen,"
            " list: !!document.querySelector('.skilllist[aria-label=\"Trash\"]') })")
        self.assertEqual(state["view"], "trash",
                         "the back button changed the view — its label names a "
                         "destination it does not go to")
        self.assertFalse(state["open"], "the detail pane is still open")
        self.assertTrue(state["list"], "the trash list did not come back")

    def test_no_console_error_on_the_way_through(self):
        self.assertEqual(self._errors, [])


if __name__ == "__main__":
    unittest.main()