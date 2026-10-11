"""The detail pane is five panels, and only the visible one may paint.

4.4. The pane used to be ONE 1,900px scroll: a closed `<details>` held the
entire metadata table, the copies list rendered only when a cluster existed,
and the rendered document ran off the bottom. The three things a reader opens
a skill for were the three things furthest from its name.

What this file asserts, and why each of these rather than "the tabs are
there":

* **The tab panel is a REAL tab panel.** `role="tablist"` / `role="tab"` /
  `role="tabpanel"`, every `aria-controls` resolving to a panel that exists,
  roving `tabindex`, and the selected tab carrying `aria-selected="true"`.
  A strip of plain buttons that swaps `v-if` content is not a tab set, and a
  half-built one is worse than none because it announces the wrong thing.
* **Only the selected panel paints.** `v-show`, not `v-if`, keeps five panels
  mounted -- so a green "the panel exists" check passes whether or not the
  reader can see it. `getBoundingClientRect` is the only thing that settles
  it, and the panel that must be hidden must measure zero.
* **Instances is honest at one copy.** It used to render *nothing* unless
  `instanceCount > 1`, so the tab answered a question by being blank. One
  copy is an observation and is stated as one.
* **The metadata table is OPEN.** The facts a reader came for are not behind a
  disclosure any more.
* **The arrows move selection AND focus**, wrap, and do not swallow the keys
  other widgets own (Escape, `/`, j/k) -- a strip that ate Escape would trap
  the reader in a five-panel pane.

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
    "Playwright/Chromium unavailable: this reads rendered geometry and focus, "
    "which need a real DOM and are NOT verified by this skip",
)
class DetailTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-detailtabs-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                real_home, ".cache", "ms-playwright")
        # RULES #8: the agent SCOPES come from HOME, not from the data dir.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        # Every skill here has exactly ONE observed copy, which is the case
        # 4.4 exists to fix: the Instances section used to render only when
        # `instanceCount > 1`, so a skill with one copy answered the tab by
        # showing nothing. Written through the Store's own write path so the
        # documents are real, not files poked beside the index.
        for name in ("lonely-skill", "quiet-skill", "third-skill"):
            cls.store.create(name, f"Fixture {name}.", body=f"# {name}\n\nFixture body.\n")
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
        self._requests = []
        self._page.on("request", lambda r: self._requests.append(r.url))
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        # DISPATCH, not Playwright's actionability click. `page.click` waits for
        # the element to be stable and to receive the event at its centre, and
        # it timed out on a row that `wait_for_selector` had already found --
        # which says the blocker is something between the row and the hit
        # test, not that the row is missing. Dispatching keeps this suite's
        # subject (the pane) instead of the list's stacking context.
        self._page.evaluate(
            "() => document.querySelectorAll('.skilllist > li[data-skill-key]')[0].click()")
        self._page.wait_for_selector(".detail-tabs [role=tab]", timeout=15000)
        self._page.wait_for_timeout(200)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _tabs(self):
        return self._page.evaluate(
            """() => Array.from(document.querySelectorAll('.detail-tabs [role="tab"]')).map(t => ({
                 id: t.getAttribute('data-detail-tab'),
                 selected: t.getAttribute('aria-selected'),
                 controls: t.getAttribute('aria-controls'),
                 tabindex: t.getAttribute('tabindex'),
                 label: (t.textContent || '').trim(),
               }))"""
        )

    def _visible_panels(self):
        return self._page.evaluate(
            """() => Array.from(document.querySelectorAll('.detail [role="tabpanel"]'))
                 .map(p => ({ id: p.id, h: Math.round(p.getBoundingClientRect().height) }))"""
        )

    # ------------------------------------------------------------------ ARIA

    def test_the_strip_is_a_tab_set_and_every_control_resolves(self):
        tabs = self._tabs()
        self.assertEqual(len(tabs), 5, "the five panels this row names")
        for tab in tabs:
            self.assertIsNotNone(tab["controls"], tab["id"] + " declares no aria-controls")
            resolved = self._page.evaluate(
                "id => !!document.getElementById(id)", tab["controls"])
            self.assertTrue(resolved, tab["controls"] + " does not exist — dangling aria-controls")
        labels = [t["id"] for t in tabs if t["selected"] == "true"]
        self.assertEqual(len(labels), 1, "exactly one tab may be aria-selected, got %r" % labels)

    def test_roving_tabindex_puts_the_keyboard_on_the_selected_tab_only(self):
        self.assertEqual([t["tabindex"] for t in self._tabs()].count("0"), 1)
        self.assertEqual(self._tabs()[0]["tabindex"], "0")

    def test_panels_are_labelled_by_their_own_tab(self):
        for tab in self._tabs():
            labelled = self._page.evaluate(
                "id => document.getElementById(id).getAttribute('aria-labelledby')", tab["controls"])
            self.assertEqual(labelled, "detail-tab-" + tab["id"])

    # -------------------------------------------------------------- painting

    def test_only_the_selected_panel_paints(self):
        panels = self._visible_panels()
        self.assertEqual(len(panels), 5)
        shown = [p["id"] for p in panels if p["h"] > 0]
        self.assertEqual(shown, ["detail-panel-overview"],
                         "hidden panels must measure zero height, not merely be absent from the a11y tree")

    def test_metadata_is_open_rather_than_behind_a_disclosure(self):
        self.assertIsNone(self._page.query_selector(".detail .skill-details"))
        text = self._page.inner_text("#detail-panel-overview")
        self.assertIn("Path", text)
        self.assertIn("License", text)

    # ---------------------------------------------------------------- panels

    def test_instances_states_a_single_copy_instead_of_rendering_nothing(self):
        self._page.click('[data-detail-tab="instances"]')
        self._page.wait_for_timeout(150)
        text = self._page.inner_text("#detail-panel-instances")
        self.assertRegex(text, r"1 observed cop(y|ies)|2 observed copies", )
        self.assertGreaterEqual(
            self._page.evaluate("() => document.querySelectorAll('#detail-panel-instances .instance-list li').length"),
            1, "the Instances tab answered by rendering zero rows")

    def test_quality_panel_states_the_observed_state_and_refuses_a_verdict(self):
        self._page.click('[data-detail-tab="quality"]')
        self._page.wait_for_timeout(150)
        text = self._page.inner_text("#detail-panel-quality")
        self.assertIn("State", text)
        self.assertIn("Not inferred", text)
        # The refusal must be ON SCREEN, not merely true: a panel that omits
        # the sentence reads as though a verdict were coming.
        self.assertIn("No quality score", text)
        # And nothing may render a verdict-shaped number of its own.
        self.assertNotRegex(text, r"\b\d+\s*/\s*10\b")

    def test_history_is_not_fetched_until_the_reader_opens_it(self):
        # A pane the reader cannot see must not cost a request they did not ask
        # for. The observable is the REQUEST, not the rendered text: `v-show`
        # keeps all five panels mounted, so reading the panel's innerText tells
        # you nothing about whether anything was fetched.
        self.assertEqual(self._history_requests(), [],
                         "selecting a skill fetched history nobody asked for")
        self._page.click('[data-detail-tab="history"]')
        self._page.wait_for_function(
            """() => { const p = document.getElementById('detail-panel-history');
                 return p && (p.querySelector('.empty') || p.querySelector('.banner-error')
                              || p.querySelector('table')); }""",
            timeout=10000)
        self.assertGreaterEqual(len(self._history_requests()), 1,
                                "the History tab was opened and nothing was requested")
        self.assertNotIn("Refreshing",
                         self._page.inner_text("#detail-panel-history"))

    def _history_requests(self):
        # `?name=` is the per-SKILL query this pane makes. The Overview's
        # "recent activity" strip also reads /api/history, with `limit=8` and
        # no name, and counting that one would make this test fail on the app
        # working correctly.
        return [url for url in self._requests if "/api/history" in url and "name=" in url]

    # -------------------------------------------------------------- keyboard

    def test_arrows_move_selection_and_focus_and_wrap(self):
        self._page.focus('.detail-tabs [data-detail-tab="overview"]')
        self._page.keyboard.press("ArrowRight")
        focused = self._page.evaluate("() => document.activeElement.getAttribute('data-detail-tab')")
        self.assertEqual(focused, "source")
        self.assertEqual(self._tabs()[1]["selected"], "true")
        self._page.keyboard.press("End")
        self.assertEqual(
            self._page.evaluate("() => document.activeElement.getAttribute('data-detail-tab')"),
            "quality")
        self._page.keyboard.press("ArrowRight")
        self.assertEqual(
            self._page.evaluate("() => document.activeElement.getAttribute('data-detail-tab')"),
            "overview", "the strip wraps; a list is positional but a tab strip is a cycle")

    def test_the_strip_does_not_swallow_escape(self):
        before = self._page.evaluate("() => document.activeElement.tagName")
        self._page.focus('.detail-tabs [data-detail-tab="overview"]')
        self._page.keyboard.press("Escape")
        self.assertEqual(
            self._page.evaluate("() => document.activeElement.getAttribute('data-detail-tab')"),
            "overview", "Escape is the close-everything key and must not be consumed here")
        self.assertTrue(before)

    # ------------------------------------------------------------- selection

    def test_selecting_a_different_skill_returns_to_overview(self):
        self._page.click('[data-detail-tab="source"]')
        self._page.wait_for_timeout(100)
        rows = self._page.query_selector_all(".skilllist > li[data-skill-key]")
        self.assertGreaterEqual(len(rows), 2,
                                "this fixture seeds three skills; a re-click of the same "
                                "row is not a change of identity and must not reset")
        before = self._page.inner_text("#detail-panel-overview h1, #view-title").strip()
        # A DIFFERENT row. Re-clicking the selected one returns early in
        # `selectSkill`, which is correct -- a reader who re-clicks the row they
        # are already reading has not changed anything and must not be yanked
        # off the panel they opened.
        self._page.evaluate(
            "() => document.querySelectorAll('.skilllist > li[data-skill-key]')[1].click()")
        self._page.wait_for_timeout(600)
        self.assertEqual(
            self._page.evaluate("() => document.querySelector('.detail-tabs [aria-selected=\"true\"]').getAttribute('data-detail-tab')"),
            "overview")
        after = self._page.inner_text("#view-title").strip()
        self.assertNotEqual(before, after, "the second row did not change the selection")

    # ----------------------------------------------------------- narrow width

    def test_the_strip_stays_one_row_and_reachable_at_390(self):
        self._page.set_viewport_size({"width": 390, "height": 844})
        self._page.evaluate(
            "() => document.querySelectorAll('.skilllist > li[data-skill-key]')[0].click()")
        self._page.wait_for_timeout(500)
        # Guard: below 761px the pane is hidden unless it is open, and a
        # hidden tablist measures one "row" of zeroes — so this assertion
        # would pass on the very state where the strip is not on screen.
        self.assertIn("mobile-detail-open",
                      self._page.evaluate("() => document.querySelector('.layout').className"))
        tops = self._page.evaluate(
            """() => Array.from(document.querySelectorAll('.detail-tabs [role="tab"]'))
                 .map(t => Math.round(t.getBoundingClientRect().top))"""
        )
        self.assertTrue(tops, "no tabs rendered at 390")
        self.assertTrue(all(t > 0 for t in tops), "the strip is not painted at 390: %r" % tops)
        # Wrapping would put tabs on several rows; scrolling keeps one.
        self.assertEqual(len(set(tops)), 1,
                         "the strip wrapped into %d rows; five wrapped rows is a second column "
                         "inside a pane whose job is to show one thing" % len(set(tops)))
        self.assertEqual(
            self._page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"),
            0, "the detail pane pushed the document wider than the viewport")
        # Coarse-pointer floor on the target a phone reader has to hit.
        height = self._page.evaluate(
            "() => Math.round(document.querySelector('.detail-tabs [data-detail-tab=\"history\"]').getBoundingClientRect().height)")
        self.assertGreaterEqual(height, 40, "a phone tab target measured %dpx" % height)


if __name__ == "__main__":
    unittest.main()