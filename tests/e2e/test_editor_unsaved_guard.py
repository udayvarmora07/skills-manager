"""The editor asked before discarding; it had four ways out and none of them asked.

4.5 slice A. `closeModal('skill')` was reachable from the Cancel button, the
close glyph, a `mousedown` on the scrim, and Escape -- and all four were a bare
`this.modals.skill = null`. A reader who spent twenty minutes in a body and
mis-clicked the scrim lost all of it: no error, no undo, and the modal closing
is exactly what they asked for, so it reads as the app having saved.

The update review already answered this shape (`requestCloseUpdate` +
`confirmingClose`); this task copies it rather than inventing a second way of
saying "you are about to drop something".

**The test that matters most is `test_the_apps_own_backfill_is_not_the_readers_typing`.**
`openEdit` fetches `/api/skills/<name>/raw` *after* the modal is on screen and
back-fills `compatibility` and `allowed_tools` from the document on disk. A
baseline captured at open therefore reports the *application's* edit as the
reader's, and the first Cancel demands they discard a change they never made --
a guard that fires on an untouched form is worse than no guard, because the
learned response to it is "click Discard". The fixture writes frontmatter the
catalog does not carry so the back-fill has something to do.

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
    "Playwright/Chromium unavailable: this drives real keypresses and mousedowns "
    "against a rendered dialog, and is NOT verified by this skip",
)
class EditorUnsavedGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-editorguard-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                real_home, ".cache", "ms-playwright")
        # RULES #8: agent SCOPES come from HOME, not the data dir, so a fixture
        # server started without this walks the real ~/.codex.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        cls.store.create(
            "with-frontmatter",
            "A fixture whose raw document carries fields the catalog does not.",
            body=("# with-frontmatter\n\nA body.\n"),
        )
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
        self._page.wait_for_function("() => document.getElementById('app').children.length > 0",
                                     timeout=15000)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    # ------------------------------------------------------------- helpers

    def _reload(self):
        """One browser, a fresh page per case.

        A nested `sync_playwright()` inside a test raises ("Sync API inside the
        asyncio loop"), which is why this reloads rather than re-entering
        setUp -- the same lesson STATE records for the scope-switcher suite.
        """
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_function(
            "() => document.getElementById('app').children.length > 0", timeout=15000)

    def _open_new_skill(self):
        self._page.evaluate("() => window.__skillsManagerApp.openCreate()")
        self._page.wait_for_selector('[data-modal="skill"] #f-name', timeout=10000)

    def _select_fixture(self, name="with-frontmatter"):
        """Drive the real selection path.

        STATE records that the FIRST row of `.skilllist` has been observed not
        to select, so the row is clicked by name and only falls back to the
        app's own `selectSkill` if that click did not land -- it sets real
        state through real methods rather than writing `selectedName`.
        """
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        self._page.click(f'.skilllist > li[data-skill-key]:has-text("{name}")')
        self._page.wait_for_timeout(300)
        selected = self._page.evaluate(
            "() => (window.__skillsManagerApp.selectedName || '')")
        if selected != name:
            self._page.evaluate(
                """(n) => { const a = window.__skillsManagerApp;
                   const rec = (a.skills || []).find(s => s.name === n);
                   if (rec) a.selectSkill(rec); }""",
                name,
            )
            self._page.wait_for_timeout(300)

    def _open_edit(self, name="with-frontmatter"):
        self._select_fixture(name)
        self._page.evaluate("() => window.__skillsManagerApp.openEdit()")
        self._page.wait_for_selector('[data-modal="skill"] #f-name', timeout=10000)

    def _type_body(self, text):
        self._page.fill('[data-modal="skill"] #f-body', text)

    def _modal_open(self):
        return bool(self._page.query_selector('[data-modal="skill"]'))

    def _confirm_visible(self):
        """`getBoundingClientRect` is a LAYOUT box; a band scrolled out of the
        scrolling `.modal-body` still has one. Asking whether the reader can
        actually SEE the question is `elementFromPoint` (2.1e's lesson)."""
        return bool(self._page.evaluate(
            """() => {
              const band = document.querySelector('[data-modal="skill"] .banner');
              if (!band) return false;
              const r = band.getBoundingClientRect();
              if (!r.width || !r.height) return false;
              const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
              return !!(hit && band.contains(hit));
            }"""
        ))

    def _dismissals(self):
        """Each returns a zero-arg callable that dismisses the dialog the way a
        reader would. Escape and the scrim are page-level/mouse-level actions
        and cannot be expressed as a click on an element."""
        return {
            "cancel button": lambda: self._page.click('[data-modal="skill"] .modal-foot .btn-secondary'),
            "close glyph": lambda: self._page.click('[data-modal="skill"] .modal-close'),
            "scrim mousedown": lambda: self._page.mouse.click(5, 5),
            "Escape": lambda: self._page.keyboard.press("Escape"),
        }

    # --------------------------------------------------------------- tests

    def test_every_dismissal_path_asks_before_discarding_typed_work(self):
        for label, dismiss in self._dismissals().items():
            with self.subTest(dismissal=label):
                self._reload()
                self._open_new_skill()
                self._type_body("# a draft\n\nWork that has not been saved.")
                dismiss()
                self._page.wait_for_timeout(150)
                self.assertTrue(
                    self._modal_open(),
                    f"dismissal via {label} destroyed unsaved work",
                )
                self.assertTrue(
                    self._confirm_visible(),
                    f"dismissal via {label} asked a question the reader "
                    "cannot see",
                )

    def test_an_untouched_form_closes_without_asking(self):
        """The guard must be silent when there is nothing to lose.

        A prompt on a pristine form teaches the reader that "Discard" is the
        answer, which is exactly the reflex that loses work once there IS some.
        """
        self._open_new_skill()
        self._page.click('[data-modal="skill"] .modal-foot .btn-secondary')
        self._page.wait_for_timeout(200)
        self.assertFalse(self._modal_open(),
                         "a form nobody touched must not demand confirmation")
        self.assertFalse(self._confirm_visible())

    def test_keep_editing_returns_to_the_form_and_keeps_the_work(self):
        self._open_new_skill()
        self._type_body("# a draft\n\nStill here.")
        self._page.keyboard.press("Escape")
        self._page.click('[data-modal="skill"] .banner .btn-secondary')
        self._page.wait_for_timeout(150)
        self.assertTrue(self._modal_open(), "Keep editing closed the dialog")
        self.assertFalse(self._confirm_visible(), "the question stayed up")
        self.assertEqual(
            self._page.input_value('[data-modal="skill"] #f-body'),
            "# a draft\n\nStill here.",
            "Keep editing discarded the very work it promised to keep",
        )

    def test_discard_actually_discards(self):
        self._open_new_skill()
        self._type_body("# a draft\n\nGone in a moment.")
        self._page.keyboard.press("Escape")
        self._page.click('[data-modal="skill"] .banner .btn-danger-ghost')
        self._page.wait_for_timeout(200)
        self.assertFalse(self._modal_open(), "Discard left the dialog open")

    def test_escape_while_the_question_is_up_clears_it_rather_than_destroying(self):
        """The one asymmetry this task buys.

        A second Escape that destroyed the work would reintroduce the exact
        failure being fixed, for the reader who reflexively presses Escape to
        back out of anything new. So Escape clears the confirmation, and Escape
        again re-asks.
        """
        self._open_new_skill()
        self._type_body("# a draft\n\nEscaped twice.")
        self._page.keyboard.press("Escape")
        self._page.wait_for_timeout(120)
        self.assertTrue(self._confirm_visible(), "first Escape did not ask")
        self._page.keyboard.press("Escape")
        self._page.wait_for_timeout(120)
        self.assertTrue(self._modal_open(),
                        "a second Escape destroyed unsaved work")
        self.assertFalse(self._confirm_visible(),
                         "a second Escape should clear the question, not re-ask")
        self.assertEqual(
            self._page.input_value('[data-modal="skill"] #f-body'),
            "# a draft\n\nEscaped twice.",
        )

    def test_the_question_is_reachable_after_scrolling_to_the_body(self):
        """The reader who has scrolled to the textarea is the one who pressed
        Escape -- it is the longest field in the form. A band rendered above
        the fold for them reads as 'nothing happened'."""
        self._open_new_skill()
        self._page.fill('[data-modal="skill"] #f-body', "\n\n".join(
            f"## Section {n}\n\nFiller paragraph {n}." for n in range(120)))
        self._page.evaluate(
            """() => { const b = document.querySelector('[data-modal="skill"] .modal-body');
                       if (b) b.scrollTop = b.scrollHeight; }"""
        )
        self._page.wait_for_timeout(150)
        scrolled = self._page.evaluate(
            """() => { const b = document.querySelector('[data-modal="skill"] .modal-body');
                       return b ? b.scrollTop : -1; }"""
        )
        self.assertGreater(scrolled, 0, "the body did not scroll, so this proves nothing")
        self._page.keyboard.press("Escape")
        self._page.wait_for_timeout(200)
        self.assertTrue(self._modal_open())
        self.assertTrue(self._confirm_visible(),
                        "the confirmation rendered off-screen for a reader who "
                        "had scrolled to the field they were editing")

    def test_the_apps_own_backfill_is_not_the_readers_typing(self):
        """`openEdit` fetches `/raw` after the modal is on screen and fills
        `compatibility` and `allowed_tools` from the document on disk.

        A baseline captured at open therefore counts the application's own
        edit as the reader's, and the very first Cancel demands they discard a
        change they never made. Asserted against a real Edit open -- the code
        path where the fetch happens -- because only the live page has the
        ordering this is about.
        """
        self._select_fixture()
        # The back-fill runs after the `/raw` response resolves, so wait for the
        # response itself rather than sleeping an assumed interval.
        with self._page.expect_response(lambda r: "/raw" in r.url, timeout=10000):
            self._page.evaluate("() => window.__skillsManagerApp.openEdit()")
        self._page.wait_for_selector('[data-modal="skill"] #f-name', timeout=10000)
        self._page.wait_for_timeout(400)
        self._page.click('[data-modal="skill"] .modal-foot .btn-secondary')
        self._page.wait_for_timeout(250)
        self.assertFalse(
            self._confirm_visible(),
            "the editor demanded confirmation for a form nobody edited -- the "
            "reader did not type this, the back-fill did",
        )
        self.assertFalse(self._modal_open(),
                         "an untouched Edit did not close at all")