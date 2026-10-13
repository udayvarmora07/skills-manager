"""5.3c e2e — the Profiles flow, which had NO e2e at all.

`tests/e2e/` did not contain a profiles file, so the view with create → edit →
preview → enable-plan → delete behaviour was covered by source-text contracts
only — the weakest coverage on the branch. This drives the master list (5.3b's
shape) rather than the detail pane, at four widths.

Every assertion here measures the LIVE DOM. Source contracts cannot see a
dialog that is visible and completely inert, which is exactly the defect this
file was written to catch: an overlay whose `data-modal` attribute does not
match its state key renders perfectly and has no focus trap, no Escape, and no
focus — with no error anywhere.

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
    "Playwright/Chromium unavailable: this reads rendered focus, geometry and "
    "request counts, which need a real DOM and are NOT verified by this skip",
)
class ProfileFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-profiles-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            rh = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                rh, ".cache", "ms-playwright")
        # RULES #8: the agent SCOPES come from HOME, not the data dir.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        # Named after the letters the typing tests use, and present as OBSERVED
        # copies so the enable-plan branch is reachable — a fixture with no
        # members would make every preview assertion vacuous.
        for name in ("kubectl-runbook", "jumbo-kernel-notes"):
            cls.store.create(name, f"Fixture {name}.",
                             body=f"# {name}\n\nFixture body.\n")
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
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.click('.viewtabs button:has-text("Profiles")')
        self._page.wait_for_selector("#app", timeout=15000)
        self._page.wait_for_timeout(500)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _master_rows(self):
        return self._page.eval_on_selector_all(
            ".profile-master-select strong", "els => els.map(e => e.textContent)")

    def _create(self, name, skills="kubectl-runbook"):
        self._page.fill("#profile-name", name)
        self._page.fill("#profile-description", "Made by the e2e.")
        self._page.fill("#profile-skills", skills)
        self._page.click(".profile-editor-actions .btn-primary")
        self._page.wait_for_timeout(1200)

    # ------------------------------------------------------------- creating

    def test_creating_a_profile_puts_it_in_the_master_list(self):
        self._create("release-captain")
        self._page.wait_for_selector(
            ".profile-master-row:has-text('release-captain')", timeout=10000)
        self.assertIn("release-captain", self._master_rows())

    def test_an_empty_library_says_so_rather_than_showing_nothing(self):
        self.assertEqual(self._master_rows(), [])
        self._page.wait_for_selector(".compact-empty", timeout=5000)
        text = self._page.inner_text(".compact-empty")
        self.assertIn("No profiles yet", text)

    # ------------------------------------------------------------ selecting

    def test_selecting_a_profile_fills_the_detail_pane(self):
        self._create("second-opinion")
        self._page.click(".profile-master-row:has-text('second-opinion') "
                         ".profile-master-select")
        self._page.wait_for_selector("#profile-detail", timeout=10000)
        self.assertIn("second-opinion", self._page.inner_text("#profile-detail"))

    def test_the_selection_is_announced_by_aria_pressed(self):
        self._create("third-call")
        row = ".profile-master-row:has-text('third-call')"
        self._page.click(f"{row} .profile-master-select")
        self._page.wait_for_selector("#profile-detail", timeout=10000)
        pressed = self._page.get_attribute(
            f"{row} .profile-master-select", "aria-pressed")
        self.assertEqual(pressed, "true",
                         "the selected row must say so to assistive tech, not "
                         "only paint a highlight")

    # -------------------------------------------------------------- editing

    def test_editing_loads_the_stored_values_and_a_rename_is_refused(self):
        self._create("editable-one")
        self._page.click(".profile-master-row:has-text('editable-one') "
                         ".profile-master-actions .btn-secondary")
        self._page.wait_for_timeout(700)
        self.assertEqual(self._page.input_value("#profile-name"), "editable-one")
        self.assertEqual(self._page.input_value("#profile-skills"), "kubectl-runbook")
        # The name is the identity; the editor must not let it change.
        self.assertTrue(self._page.is_disabled("#profile-name"))

    # ------------------------------------------------------- deleting (5.3c)

    def test_the_delete_button_does_not_delete(self):
        """The defect: one click destroyed a profile. Now it asks."""
        self._create("doomed-profile")
        deletes = []
        self._page.on("request",
                      lambda r: deletes.append(r.url) if r.method == "DELETE" else None)
        self._page.click(".profile-master-row:has-text('doomed-profile') "
                         ".profile-master-actions .btn-danger-ghost")
        self._page.wait_for_timeout(1200)
        self.assertEqual(deletes, [],
                         "one click on Delete issued a destructive request")
        self.assertIn("doomed-profile", self._master_rows(),
                      "the profile must still be there")

    def test_the_confirm_names_the_profile_and_what_is_lost(self):
        self._create("named-loss")
        self._page.click(".profile-master-row:has-text('named-loss') "
                         ".profile-master-actions .btn-danger-ghost")
        self._page.wait_for_selector('[data-modal="deleteProfile"]', timeout=8000)
        title = self._page.inner_text('[data-modal="deleteProfile"] .modal-head h2')
        self.assertIn("named-loss", title)
        body = self._page.inner_text('[data-modal="deleteProfile"] .modal-body')
        self.assertIn("No skill is changed on disk", body)
        self.assertIn("trash", body)

    def test_the_dialog_takes_focus_and_keeps_it(self):
        self._create("focus-holding")
        self._page.click(".profile-master-row:has-text('focus-holding') "
                         ".profile-master-actions .btn-danger-ghost")
        self._page.wait_for_selector('[data-modal="deleteProfile"]', timeout=8000)
        self._page.wait_for_timeout(500)
        self.assertTrue(
            self._page.evaluate(
                "() => document.querySelector('[data-modal=\"deleteProfile\"] "
                ".modal').contains(document.activeElement)"),
            "the dialog opened without taking focus — it is visible and inert, "
            "which is what a data-modal attribute that does not match the state "
            "key produces")
        for _ in range(5):
            self._page.keyboard.press("Tab")
        self.assertTrue(
            self._page.evaluate(
                "() => document.querySelector('[data-modal=\"deleteProfile\"] "
                ".modal').contains(document.activeElement)"),
            "Tab escaped the dialog")

    def test_escape_cancels_and_returns_focus_to_the_opener(self):
        self._create("escapee")
        # A CSS selector with spaces passed to `querySelector` from a JS
        # string is a syntax error, not a miss — quote the value.
        opener = (".profile-master-row:has-text('escapee') "
                  ".profile-master-actions .btn-danger-ghost")
        self._page.click(opener)
        self._page.wait_for_selector('[data-modal="deleteProfile"]', timeout=8000)
        self._page.wait_for_timeout(400)
        self._page.keyboard.press("Escape")
        self._page.wait_for_timeout(600)
        self.assertFalse(
            self._page.evaluate(
                "() => !!document.querySelector('[data-modal=\"deleteProfile\"]')"),
            "Escape must dismiss")
        # Compare against the element HANDLE, not a re-queried string: the
        # handle is the very node that was clicked, which is the only thing
        # "focus returned to the opener" can mean once the list re-renders.
        handle = self._page.locator(opener)
        self._page.click(opener)
        self._page.wait_for_selector('[data-modal="deleteProfile"]', timeout=8000)
        self._page.wait_for_timeout(400)
        self._page.keyboard.press("Escape")
        self._page.wait_for_timeout(600)
        self.assertFalse(
            self._page.evaluate(
                "() => !!document.querySelector('[data-modal=\"deleteProfile\"]')"),
            "Escape must dismiss")
        self.assertEqual(
            handle.evaluate("el => document.activeElement === el"), True,
            "focus must return to the control that opened the dialog")

    def test_cancelling_keeps_the_profile(self):
        self._create("survivor")
        self._page.click(".profile-master-row:has-text('survivor') "
                         ".profile-master-actions .btn-danger-ghost")
        self._page.wait_for_selector('[data-modal="deleteProfile"]', timeout=8000)
        self._page.click('[data-modal="deleteProfile"] .modal-foot .btn-secondary')
        self._page.wait_for_timeout(800)
        self.assertIn("survivor", self._master_rows())

    def test_confirming_deletes_exactly_once_and_names_it(self):
        self._create("temporary-profile")
        deletes = []
        self._page.on("request",
                      lambda r: deletes.append(r.url) if r.method == "DELETE" else None)
        self._page.click(".profile-master-row:has-text('temporary-profile') "
                         ".profile-master-actions .btn-danger-ghost")
        self._page.wait_for_selector('[data-modal="deleteProfile"]', timeout=8000)
        self._page.click('[data-modal="deleteProfile"] .modal-foot .btn-danger')
        self._page.wait_for_timeout(1800)
        self.assertEqual(len(deletes), 1, "exactly one destructive request")
        self.assertNotIn("temporary-profile", self._master_rows())
        # Read the toast STACK, and require the delete's own message to be in
        # it. `inner_text('.toast-text')` returns the first toast, which is the
        # "Profile saved." from `_create` still on screen — the first version
        # of this assertion failed on a message that was correct and second.
        toasts = self._page.eval_on_selector_all(
            ".toast-text", "els => els.map(e => e.textContent)")
        self.assertTrue(any("temporary-profile" in t for t in toasts),
                        f"the delete must name the profile: {toasts}")
        self.assertTrue(
            any("temporary-profile" in t and "trash" in t for t in toasts),
            "the toast must say the profile is NOT recoverable, or a reader who "
            f"deleted it by mistake has no way to know: {toasts}")

    def test_deleting_the_previewed_profile_clears_the_detail_pane(self):
        self._create("previewed-then-deleted")
        self._page.click(".profile-master-row:has-text('previewed-then-deleted') "
                         ".profile-master-select")
        self._page.wait_for_selector("#profile-detail", timeout=10000)
        self._page.click(".profile-master-row:has-text('previewed-then-deleted') "
                         ".profile-master-actions .btn-danger-ghost")
        self._page.wait_for_selector('[data-modal="deleteProfile"]', timeout=8000)
        self._page.click('[data-modal="deleteProfile"] .modal-foot .btn-danger')
        self._page.wait_for_timeout(1800)
        self.assertFalse(
            self._page.evaluate("() => !!document.querySelector('#profile-detail')"),
            "the detail pane still names a profile that no longer exists")

    # ----------------------------------------------------------- geometry

    def test_nothing_overflows_at_any_width(self):
        self._create("width-probe")
        for width in (390, 768, 1280, 1920):
            with self.subTest(width=width):
                self._page.set_viewport_size({"width": width, "height": 900})
                self._page.wait_for_timeout(300)
                over = self._page.evaluate(
                    "() => document.documentElement.scrollWidth - window.innerWidth")
                self.assertLessEqual(over, 0, f"overflows at {width}px")
        self._page.set_viewport_size({"width": 1280, "height": 900})

    def test_no_console_errors(self):
        self._create("error-probe")
        self._page.wait_for_timeout(800)
        self.assertEqual(self._errors, [], f"console errors: {self._errors}")


if __name__ == "__main__":
    unittest.main()