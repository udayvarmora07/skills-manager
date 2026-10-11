"""Library row keys: j/k (and arrows) move focus between rows.

4.2 slice A. INVENTORY recorded that **no j/k handler existed at all** -- the
Library's rows carry `tabindex="0"` and handle Enter and Space on themselves, so
a keyboard reader had to Tab through every row to reach the one they wanted.

These are real keypresses through the real handler, not calls into the method:
the interesting failures are precedence ones (the scope menu, the actions menu,
a text field, an open dialog) and calling `moveRowFocus(1)` directly cannot
observe any of them.

The collision INVENTORY asked about has a measured answer: `j` and `k` are
different keys from `/`, `?`, Escape and Cmd-K, so the only question is whether
the ARROWS collide -- and they do, with two menus that bind ArrowUp/ArrowDown
without `activeModal` being set. Both directions are asserted below.

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright


def _seed(store, count=6):
    """Write real skill documents through the Store's own write path.

    An empty Store renders zero rows, and every test here would SKIP -- a suite
    that skips is a suite that reports green while verifying nothing, which is
    the exact shape this repository keeps finding. Names deliberately contain
    the letters j and k ("jumbo-kernel-notes") so the typing test cannot pass
    just because its sample term is free of them.
    """
    names = ["jumbo-kernel-notes", "kubectl-runbook", "jsonl-parser",
             "known-good-defaults", "keep-changelog-order", "jwt-claims-map"]
    for name in names[:count]:
        store.create(
            name,
            f"A fixture skill named {name} for the row-key suite.",
            body=f"# {name}\n\nFixture body for {name}.\n",
        )


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
    "Playwright/Chromium unavailable: row-key precedence is only observable "
    "through real keypresses, and is NOT verified by this skip",
)
class RowKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-rowkeys-")
        # RULES #8, and the exact trap task 0.2's STATE entry records. The
        # Store takes a data dir, but the AGENT SCOPES are read from HOME, so a
        # fixture server started without redirecting HOME walks the real
        # ~/.codex, ~/.claude and friends. The first run of this file reported
        # "644 of 1,963 observed" -- the maintainer's own skills, read-only
        # but not permitted, and invisible to any assertion. Redirect this
        # process FIRST, and restore it in teardown.
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        # Redirecting HOME also moves Playwright's browser cache, so every
        # `chromium.launch()` in setUp dies with "It looks like you are using
        # Playwright Sync API inside the asyncio loop" -- a message about
        # nothing. Pin the browsers path to wherever it already was.
        browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if not browsers:
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            browsers = os.path.join(real_home, ".cache", "ms-playwright")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers

        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        _seed(cls.store)
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
        if cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH") is None:
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".library-bar", timeout=15000)
        # A store with nothing in it has no rows, so there is nothing to move
        # between; the tests below say which ones need rows and skip loudly.
        self._row_count = self._page.evaluate(
            "() => document.querySelectorAll('.skilllist > li[data-skill-key]').length"
        )

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _focused_row_index(self):
        return self._page.evaluate(
            """() => {
              const rows = Array.from(document.querySelectorAll(
                '.skilllist > li[data-skill-key]'));
              return rows.indexOf(document.activeElement);
            }"""
        )

    def _first_row_name(self):
        return self._page.evaluate(
            """() => {
              const row = document.querySelector('.skilllist > li[data-skill-key]');
              return row ? row.getAttribute('data-skill-key') : null;
            }"""
        )

    def test_j_and_k_walk_the_rows_and_stop_at_the_ends(self):
        if self._row_count < 3:
            self.skipTest(f"fixture has {self._row_count} rows; needs 3 to walk")
        # j from nowhere enters at the first row.
        self._page.keyboard.press("j")
        self._page.wait_for_timeout(120)
        self.assertEqual(self._focused_row_index(), 0)
        self._page.keyboard.press("j")
        self._page.wait_for_timeout(120)
        self.assertEqual(self._focused_row_index(), 1)
        self._page.keyboard.press("k")
        self._page.wait_for_timeout(120)
        self.assertEqual(self._focused_row_index(), 0)

        # Clamp, do not wrap: a list is positional. (Contrast 2.2, where the
        # command palette deliberately wraps -- that decision is recorded and
        # this one is its opposite on purpose.)
        self._page.keyboard.press("k")
        self._page.wait_for_timeout(120)
        self.assertEqual(
            self._focused_row_index(), 0,
            "k on the first row must stay on the first row, not wrap to the last",
        )

    def test_j_past_the_last_row_does_not_wrap(self):
        if self._row_count < 2:
            self.skipTest(f"fixture has {self._row_count} rows; needs 2")
        for _ in range(self._row_count + 5):
            self._page.keyboard.press("j")
        self._page.wait_for_timeout(150)
        self.assertEqual(self._focused_row_index(), self._row_count - 1)

    def test_enter_opens_the_focused_row(self):
        """Focus is only useful if the row's own Enter handler still runs."""
        if self._row_count < 1:
            self.skipTest("fixture has no rows")
        self._page.keyboard.press("j")
        self._page.wait_for_timeout(120)
        expected = self._first_row_name()
        self._page.keyboard.press("Enter")
        self._page.wait_for_timeout(700)
        self.assertTrue(
            self._page.evaluate(
                """() => {
                  const d = document.querySelector('.detail-inner, .detail-pane');
                  return !!d && !!(d.innerText || '').trim();
                }"""
            ),
            "Enter on a j-focused row must load its detail",
        )
        self.assertIn(expected.split("/")[-1], self._page.evaluate(
            """() => (document.querySelector('.detail-inner, .detail-pane') || {}).innerText || ''"""),
            f"the detail pane should describe {expected}",
        )

    def test_j_is_ignored_while_typing_in_the_search_field(self):
        """The letters must be typeable. A shortcut that ate them would make the
        field unusable for any skill whose name contains a j or a k."""
        if not self._page.evaluate(
            "() => !!document.querySelector('.searchwrap input')"
        ):
            self.skipTest("this view renders no search field")
        self._page.click(".searchwrap input")
        self._page.keyboard.type("junk")
        self._page.wait_for_timeout(500)
        self.assertEqual(
            self._page.eval_on_selector(".searchwrap input", "el => el.value"), "junk",
            "j/k must be literal characters inside the search field",
        )
        self.assertEqual(
            self._focused_row_index(), -1,
            "typing must not move focus into the list",
        )

    def test_the_arrow_keys_do_not_steal_scrolling_before_the_reader_enters(self):
        """ArrowDown with focus on the body is a scroll. Taking it on the first
        press would move focus without the pane having moved."""
        if self._row_count < 2:
            self.skipTest(f"fixture has {self._row_count} rows; needs 2")
        self._page.evaluate("() => document.body.focus()")
        self._page.wait_for_timeout(120)
        self._page.keyboard.press("ArrowDown")
        self._page.wait_for_timeout(120)
        self.assertEqual(
            self._focused_row_index(), -1,
            "ArrowDown before entering the list must not grab focus",
        )
        # Once a row HAS focus, the arrows do take over.
        self._page.keyboard.press("j")
        self._page.wait_for_timeout(120)
        self._page.keyboard.press("ArrowDown")
        self._page.wait_for_timeout(120)
        self.assertEqual(self._focused_row_index(), 1)

    def test_the_scope_menu_keeps_its_own_arrow_keys(self):
        """The collision INVENTORY predicted. The scope menu binds
        ArrowUp/ArrowDown and opens without `activeModal`, so a row-key branch
        that does not exclude it steals the key."""
        # Since 2.1e the scope switcher lives in the rail panel behind the
        # disclosure; clicking a hidden trigger is not how a reader opens it.
        toggle = self._page.query_selector(".mobile-controls-toggle")
        if toggle and toggle.is_visible():
            self._page.click(".mobile-controls-toggle")
            self._page.wait_for_timeout(250)
        self._page.click(".scope-trigger")
        self._page.wait_for_selector(".scope-menu", timeout=10000)
        # FOCUS, not selection. The scope menu is a listbox: ArrowDown moves the
        # active option and the selection only follows on Enter or a click. My
        # first version watched `aria-selected`/`active`, which does not move on
        # an arrow -- so it reported the menu broken when the menu was correct,
        # and would have passed had the row-keys branch stolen the key and the
        # menu happened to leave its selection alone.
        def focused_option():
            return self._page.evaluate(
                """() => Array.from(document.querySelectorAll(
                     '.scope-menu [role=option]')).findIndex(el => el === document.activeElement)"""
            )

        before = focused_option()
        self.assertGreaterEqual(before, 0, "the scope menu must own focus when it is open")
        self._page.keyboard.press("ArrowDown")
        self._page.wait_for_timeout(200)
        after = focused_option()
        self.assertEqual(after, before + 1,
                         "ArrowDown must still walk the scope menu's own options")
        self.assertEqual(self._focused_row_index(), -1,
                         "and must not move a Library row")

    def test_the_existing_shortcuts_still_work_with_row_keys_in_place(self):
        """`/`, `?` and Cmd-K are the neighbours of this branch in the same
        handler. A guard added for j/k that leaked would eat one of them."""
        self._page.keyboard.press("/")
        self._page.wait_for_timeout(150)
        self.assertTrue(
            self._page.evaluate("() => !!document.activeElement.closest('.searchwrap')"),
            "`/` must still reach the search field",
        )
        self._page.keyboard.press("Escape")
        self._page.evaluate("() => document.querySelector('.searchwrap input').blur()")
        self._page.keyboard.press("?")
        self._page.wait_for_timeout(250)
        self.assertTrue(
            self._page.evaluate("() => !!document.querySelector('[data-modal=help]')"),
            "`?` must still open the shortcut reference",
        )



if __name__ == "__main__":
    unittest.main()