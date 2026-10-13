"""5.6a e2e — Recovery: the Global trash list.

`tests/e2e/` had NO recovery file, so the one place the product can undo a
deletion was covered by source contracts only.

Three of these tests exist because the defect they describe was invisible to
every test that already passed:

  1. Every row said "Select for restore" and the Restore button lived in a card
     300px above, behind `v-if="selectedTrash"`. A row whose verb is not the
     verb is a two-step flow that reads as one.
  2. `query` is component state and `switchView` does not clear it, while the
     search field does not render on this view at all. A query typed in Library
     silently narrowed this list with nothing on screen to explain it.
  3. A query matching nothing rendered "Global trash is empty" — a claim about
     the disk, made by a filter, over three trashed skills still sitting there.

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
    "Playwright/Chromium unavailable: this drives real clicks against a real "
    "restore request, which no source contract can stand in for",
)
class RecoveryTrashTests(unittest.TestCase):
    TRASHED = ("retired-skill-alpha", "retired-skill-beta", "retired-skill-gamma")

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-recovery-")
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
            cls.store.create(name, f"Fixture {name}.",
                             body=f"# {name}\n\nFixture body.\n")
        # An empty library would make every "the trash has N rows" assertion
        # pass against a list that simply failed to render.
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
        # Two tests below RESTORE for real, so the trash they leave behind is
        # depleted for whatever runs next. Repair it here rather than letting
        # the suite depend on alphabetical order — a test that only passes
        # because it runs before another one is not a test.
        present = {t["name"] for t in self.store.trash_list()}
        for name in self.TRASHED:
            if name in present:
                continue
            try:
                # A previous test RESTORED it, so it is live again and
                # `create` would refuse the duplicate — that is the honest
                # signal that only the remove below is needed.
                self.store.create(name, f"Fixture {name}.",
                                  body=f"# {name}\n\nFixture body.\n")
            except Exception:
                pass
            self.store.remove(name)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.click('.viewtabs button:has-text("Recovery")')
        self._page.wait_for_selector("#app", timeout=15000)
        self._page.wait_for_selector(".recovery-ledger tbody tr", timeout=15000)
        self._page.wait_for_timeout(400)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _names(self):
        return self._page.eval_on_selector_all(
            ".recovery-ledger tbody th",
            "els => els.map(e => e.childNodes[0].textContent.trim())")

    # -------------------------------------------------- the list is a ledger

    def test_every_trashed_skill_is_a_row_with_its_own_verb(self):
        self.assertEqual(sorted(self._names()), sorted(self.TRASHED))

    def test_the_rows_verb_is_restore_not_select(self):
        """The row's verb must be the verb. "Select for restore" described a
        step the reader could not see the end of."""
        labels = self._page.eval_on_selector_all(
            ".recovery-ledger-action button",
            "els => els.map(e => e.textContent.trim())")
        self.assertEqual(labels, ["Restore"] * len(self.TRASHED))

    def test_no_control_anywhere_on_the_view_asks_the_reader_to_select_first(self):
        body = self._page.inner_text(".recovery-center")
        self.assertNotIn("Select for restore", body)

    def test_the_restore_button_is_in_the_row_that_has_the_skill(self):
        """Not merely present — in the same row. A view-wide Restore behind a
        selection is what this task removed."""
        per_row = self._page.eval_on_selector_all(
            ".recovery-ledger tbody tr",
            "els => els.map(e => e.querySelectorAll('button').length)")
        self.assertEqual(per_row, [1] * len(self.TRASHED))

    def test_the_content_is_not_two_equal_bordered_cards(self):
        """Profiles' `.profile-preview` panel class painted two plain blocks
        as equal boxes. Measure the borders, not the class name."""
        boxes = self._page.eval_on_selector_all(
            ".recovery-center section",
            "els => els.map(e => { const s = getComputedStyle(e);"
            " return { h: Math.round(e.getBoundingClientRect().height),"
            "  bw: s.borderTopWidth, br: s.borderTopStyle }; })")
        self.assertTrue(boxes)
        self.assertTrue(all(b["bw"] == "0px" or b["br"] == "none" for b in boxes),
                        f"a Recovery section still paints a box: {boxes}")

    def test_each_row_states_what_it_will_put_back_and_where(self):
        first = self._page.inner_text(".recovery-ledger tbody tr")
        self.assertIn("trash", first)
        self.assertRegex(first, r"\d")

    # ------------------------------------------------------- the hidden filter

    def test_a_query_carried_over_from_another_view_is_not_applied_silently(self):
        """`query` is not cleared by `switchView` and the search field does not
        render here, so the list used to shrink with no on-screen cause."""
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".searchwrap input[type=search]", timeout=10000)
        self._page.fill(".searchwrap input[type=search]", "beta")
        self._page.click('.viewtabs button:has-text("Recovery")')
        self._page.wait_for_selector(".recovery-ledger", timeout=10000)
        self._page.wait_for_timeout(300)
        self.assertEqual(self._names(), ["retired-skill-beta"])
        note = self._page.inner_text(".recovery-filter-note")
        self.assertIn("1 of 3", note)
        self.assertIn("beta", note)

    def test_a_filter_that_matches_nothing_never_says_the_trash_is_empty(self):
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".searchwrap input[type=search]", timeout=10000)
        self._page.fill(".searchwrap input[type=search]", "no-such-skill")
        self._page.click('.viewtabs button:has-text("Recovery")')
        self._page.wait_for_timeout(600)
        text = self._page.inner_text(".recovery-center")
        self.assertNotIn("Global trash is empty", text)
        self.assertIn("still on disk", text)

    def test_no_filter_note_when_nothing_is_filtered(self):
        self.assertEqual(self._page.eval_on_selector_all(".recovery-filter-note",
                                                         "els => els.length"), 0)

    # ---------------------------------------------------------------- acting

    def test_restoring_a_row_restores_that_skill_and_removes_only_that_row(self):
        before = set(self._names())
        target = "retired-skill-beta"
        self._page.click(f".recovery-ledger tbody tr:has-text('{target}') button")
        self._page.wait_for_function(
            "n => document.querySelectorAll('.recovery-ledger tbody tr').length === n",
            arg=len(before) - 1, timeout=15000)
        self.assertEqual(set(self._names()), before - {target})
        # The list route is a bare JSON array; `/api/skills/<name>` is the
        # single-record one. Asserted against the API, not against the row
        # that was clicked, because a row that vanishes and a row that was
        # never restored look identical on screen.
        live = self._page.evaluate(
            "async () => (await (await fetch('/api/skills?scope=all')).json())"
            ".map(s => s.name)")
        self.assertIn(target, live)

    def test_restore_leaves_no_console_error(self):
        self._page.click(".recovery-ledger tbody tr:first-child button")
        self._page.wait_for_timeout(1500)
        self.assertEqual(self._errors, [])

    def test_every_row_stays_reachable_at_the_shrunk_laptop_width(self):
        """1100px is the width a real laptop window lands at. A row whose
        Restore button overflowed its cell is not reachable, and a
        `getBoundingClientRect` comparison cannot see clipping — ask what is
        on top."""
        self._page.set_viewport_size({"width": 1100, "height": 900})
        self._page.wait_for_timeout(500)
        reach = self._page.eval_on_selector_all(
            ".recovery-ledger-action button",
            "els => els.map(e => { const r = e.getBoundingClientRect();"
            " const hit = document.elementFromPoint(r.left + r.width / 2,"
            " r.top + r.height / 2); return !!hit && (hit === e || e.contains(hit)); })")
        self.assertTrue(reach)
        self.assertTrue(all(reach), f"a Restore button is not reachable: {reach}")
        overflow = self._page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        self.assertEqual(overflow, 0)

    def test_the_view_does_not_leave_focus_on_the_body(self):
        focused = self._page.evaluate(
            "() => document.activeElement && document.activeElement.tagName")
        self.assertNotEqual(focused, "BODY",
                            "Recovery must move focus to its heading")


if __name__ == "__main__":
    unittest.main()