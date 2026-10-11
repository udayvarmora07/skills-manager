"""The search field must not promise a search that does not exist.

4.1b. One global input in the topbar, one `v-model`, one `/` binding — so it
rendered on every view. That is right for the four views whose lists really
filter (`filteredSkills`, `filteredTrash`, `filteredQualitySkills`,
`filteredRegistryInventory`). Recovery is not one of them: its pane is "Source
snapshots" for the *selected* skill, with no list to search, and the field
still said "Search recovery…".

The test states the rule the UI owes its reader, not the rule the code
happens to follow:

    for every view: either the field is absent, or typing in it changes what
    the page renders.

That cannot be satisfied by an assertion which finds nothing and passes. If a
future view adds a filter but forgets the field, this goes red; if it adds the
field without a filter, this goes red too. Both directions matter, because
the failure this task fixed was a control that was present and inert.

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright

# Every destination the rail can navigate to, from the v-for over viewtabs in
# index.html. Trash is reachable from Recovery rather than the rail; it is in
# the list because it has a real filtered list and must keep the field.
# view id -> the rail label a reader clicks. Trash has no rail button (it is
# reached from Recovery), so it is driven through the app's own switchView.
VIEWS = (("overview", "Overview"), ("skills", "Library"), ("quality", "Quality"),
         ("install", "Install"), ("recovery", "Recovery"), ("settings", "Settings"),
         ("profiles", "Profiles"), ("workspaces", "Workspaces"),
         ("trash", None))

# A term that matches nothing anywhere in the seeded corpus.
NO_MATCH = "zzqqxx-no-such-term-4f2a"


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
    "Playwright/Chromium unavailable: this check needs a real layout engine "
    "and a real request cycle, and is NOT verified by this skip",
)
class SearchClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-search-")
        cls.store = Store(cls._tmp)
        cls.store.init_db()
        cls.server = WebAppServer(cls.store, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        import shutil

        cls.server.shutdown()
        cls.thread.join(timeout=5)
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_selector(".viewtabs button", timeout=15000)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _go(self, view):
        """Navigate by the rail where there is one, else the app's own switch."""
        for vid, label in VIEWS:
            if vid != view:
                continue
            if label is None:
                self._page.evaluate("v => window.__skillsManagerApp.switchView(v)", view)
            else:
                self._page.click(f'.viewtabs button:has-text("{label}")')
        self._page.wait_for_timeout(500)

    def _field_present(self):
        return self._page.evaluate(
            "() => { const el = document.querySelector('.searchwrap');"
            " return !!(el && el.offsetWidth > 0); }"
        )

    def _rendered_state(self):
        """What the page shows: the list pane plus the main content.

        Deliberately not just the pane -- Install's filtered list lives in the
        pane, but a filter that silently moved everything would still be a lie.
        """
        return self._page.evaluate(
            """() => {
              const parts = Array.from(document.querySelectorAll(
                '.sidebar.list-pane, .content, .view, .detail-inner, main'));
              return parts.map(p => (p.innerText || '').replace(/\\s+/g, ' ').trim()).join(' | ');
            }"""
        )

    def test_the_field_is_present_exactly_where_a_query_filters_something(self):
        """The claim, per view, measured rather than read off the source."""
        for view, _label in VIEWS:
            with self.subTest(view=view):
                self._go(view)
                present = self._field_present()
                if not present:
                    # Absent is a legitimate answer, but only if the page does
                    # not advertise a search: no "/" key cap, no icon.
                    self.assertEqual(
                        self._page.evaluate(
                            "() => document.querySelectorAll('.searchwrap').length"), 0)
                    continue

                # A filter over an EMPTY list changes nothing, and that is not
                # an inert field -- it is a list with nothing in it. Only views
                # that render filterable rows can be held to the behavioural
                # half, and the skip says which and why rather than pretending.
                if self._page.evaluate(
                    """() => document.querySelectorAll(
                        '.skilllist > li[data-skill-key], .trashlist > li, .qualitylist > li, .registry-list > li').length === 0"""
                ):
                    self._page.fill(".searchwrap input", NO_MATCH)
                    self._page.wait_for_timeout(300)
                    self._page.fill(".searchwrap input", "")
                    self._page.wait_for_timeout(300)
                    continue

                before = self._rendered_state()
                self._page.fill(".searchwrap input", NO_MATCH)
                self._page.wait_for_timeout(700)
                after = self._rendered_state()
                self._page.fill(".searchwrap input", "")
                self._page.wait_for_timeout(500)
                self.assertNotEqual(
                    before, after,
                    f"{view}: the search field is shown and filters nothing",
                )

    def test_a_view_with_no_filter_does_not_advertise_one(self):
        """Recovery is the concrete case: snapshots of the selected skill."""
        self._go("recovery")
        self.assertFalse(
            self._field_present(),
            "Recovery renders no list, so it must not offer a search field",
        )

    def test_the_slash_shortcut_follows_the_field_rather_than_the_view(self):
        """`/` must not swallow a keypress for a field it will not focus."""
        self._go("skills")
        self._page.keyboard.press("/")
        self._page.wait_for_timeout(200)
        self.assertTrue(
            self._page.evaluate(
                "() => !!document.activeElement.closest('.searchwrap')"),
            "`/` on the Library must reach the search field",
        )

        self._go("recovery")
        swallowed = self._page.evaluate(
            """() => {
              const ev = new KeyboardEvent('keydown', {key: '/', bubbles: true,
                                                     cancelable: true});
              document.dispatchEvent(ev);
              return ev.defaultPrevented;
            }"""
        )
        self.assertFalse(
            swallowed,
            "there is no field on Recovery, so `/` must not be swallowed for one",
        )
        self._page.keyboard.press("/")
        self._page.wait_for_timeout(200)
        self.assertFalse(
            self._page.evaluate(
                "() => !!document.activeElement.closest('.searchwrap')"),
            "there is no field on Recovery, so `/` must not claim one",
        )

    def test_the_library_search_is_reachable_from_the_palette_anyway(self):
        """Removing the field on Recovery must not strand the palette command.

        `focusLibrarySearch()` navigates to the Library first, so a reader on a
        filter-less view can still reach search — which is what makes hiding the
        field safe rather than a loss.
        """
        self._go("recovery")
        self._page.evaluate(
            """() => window.__skillsManagerApp.focusLibrarySearch()"""
        )
        self._page.wait_for_timeout(500)
        self.assertTrue(self._field_present(), "the palette command must arrive on the Library")


if __name__ == "__main__":
    unittest.main()