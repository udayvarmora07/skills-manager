"""4.5c — the editor says so as you leave the field, and says it once.

The stdlib suite (`tests/test_redesign_editor_validation.py`) drives the real
`app.js` in a Node VM and proves the blur path and the submit path cannot
disagree. It cannot prove that the error is *seen*: `$nextTick` is stubbed there
and there is no layout at all. So this file asks the reader's question against
the real dialog — did anything appear under the field, in the words the rule
already used, and did it go away when the field was fixed.

Three directions, because only the first is the defect and only the third is the
guard against over-correcting into 4.5 slice A's failure (a form that talks back
when it should not teaches the reader to dismiss it without reading).

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
import shutil
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
    "Playwright/Chromium unavailable: this drives real typing and real Tab "
    "presses against a rendered dialog, and is NOT verified by this skip",
)
class EditorInlineValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-inlinevalidation-")
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
        cls.store.create("already-here", "A fixture the editor can open.")
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
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
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_function(
            "() => document.getElementById('app').children.length > 0", timeout=15000)
        self._page.evaluate("() => window.__skillsManagerApp.openCreate()")
        self._page.wait_for_selector('[data-modal="skill"] #f-name', timeout=10000)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    # ------------------------------------------------------------- helpers

    def _error(self, field):
        """The message PAINTED under a field, or "".

        `textContent` alone would report a message inside a hidden element, and
        an invisible error is not an error the reader was given. So this is
        rendered state: a non-zero box, plus `elementFromPoint` at its centre to
        confirm nothing is painted on top of it (2.1e's lesson).
        """
        return self._page.evaluate(
            """(id) => {
              const el = document.querySelector('[data-modal="skill"] #' + id);
              if (!el) return '';
              const r = el.getBoundingClientRect();
              if (!r.width || !r.height) return '';
              const hit = document.elementFromPoint(r.left + r.width / 2,
                                                   r.top + r.height / 2);
              if (!hit || !el.contains(hit)) return '';
              return (el.textContent || '').trim();
            }""",
            field,
        )

    def _type_and_leave(self, selector, field, value):
        self._page.fill('[data-modal="skill"] ' + selector, value)
        self._page.keyboard.press("Tab")   # a real blur, the way a reader leaves
        self._page.wait_for_timeout(120)
        return self._error(field)

    # --------------------------------------------------------------- tests

    def test_an_untouched_form_says_nothing_at_all(self):
        """The direction that matters most. 4.5 slice A's unsaved-changes guard
        fails this way when it is wrong, and the learned response to a form that
        talks back spuriously is to dismiss messages without reading."""
        self.assertEqual("", self._error("f-name-error"))
        self.assertEqual("", self._error("f-description-error"))
        self._page.click('[data-modal="skill"] #f-name')
        self._page.keyboard.press("Tab")
        self._page.wait_for_timeout(120)
        self.assertEqual("", self._error("f-name-error"),
                         "leaving an empty untouched field produced a message")

    def test_a_name_the_server_would_refuse_is_refused_on_the_way_out(self):
        message = self._type_and_leave("#f-name", "f-name-error", "My Skill")
        self.assertNotEqual("", message,
                            "the field's own hint states the rule and nothing "
                            "checked it, so the reader met it as a 400")
        self.assertIn("Not a valid name", message)

    def test_fixing_the_field_removes_the_message(self):
        self._type_and_leave("#f-name", "f-name-error", "snake_case")
        self.assertNotEqual("", self._error("f-name-error"))
        message = self._type_and_leave("#f-name", "f-name-error", "snake-case")
        self.assertEqual("", message,
                         "the message survived a valid name, so the reader has "
                         "to work out on their own whether the field is fixed")

    def test_a_description_filled_and_emptied_is_reported_and_another_field_is_untouched(self):
        """Typed into, then emptied, then left — not merely "left empty". A field
        the reader never typed in is not something a blur may complain about,
        which is the whole of the preceding test."""
        self._page.fill('[data-modal="skill"] #f-name', "release-checklist")
        self._page.fill('[data-modal="skill"] #f-desc', "Something")
        self._page.fill('[data-modal="skill"] #f-desc', "")
        self._page.click('[data-modal="skill"] #f-desc')
        self._page.keyboard.press("Tab")
        self._page.wait_for_timeout(120)
        self.assertNotEqual("", self._error("f-description-error"))
        self.assertEqual("", self._error("f-name-error"),
                         "blurring one field spoke about another")

    def test_the_message_is_announced_and_associated_with_its_field(self):
        """`aria-invalid` and `aria-describedby` are what make the message reach
        a screen reader. A painted red sentence is not the same thing."""
        self._type_and_leave("#f-name", "f-name-error", "My Skill")
        state = self._page.evaluate(
            """() => { const i = document.querySelector('[data-modal="skill"] #f-name');
                 return {invalid: i.getAttribute('aria-invalid'),
                         described: i.getAttribute('aria-describedby') || ''}; }"""
        )
        self.assertEqual("true", state["invalid"])
        self.assertIn("f-name-error", state["described"])


if __name__ == "__main__":
    unittest.main()