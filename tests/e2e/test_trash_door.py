"""7.4c e2e — the Trash view has a door, and the door is the thing under test.

`tests/test_redesign_trash_door.py` derives reachability from the markup.
This file drives the door with a real click in a real browser, because the
class of defect it guards is precisely the class a source check cannot see:
a control that exists in the template, passes every grep, and is never
reachable because the click lands somewhere else — or because the view it
opens renders a fallback nobody navigated to.

Three failures this file would have caught on the broken tree, and why each
assertion is shaped the way it is:

  1. `test_the_door_opens_the_trash_view` — the door is pressed, not
     `switchView('trash')` called. Calling the method proves the view renders,
     which it always did; pressing the control proves a reader can get there.
  2. `test_the_door_leads_to_a_view_named_after_what_it_shows` — the pane was
     the chain's bare `v-else`, so it rendered "Global trash" for any unmatched
     view id. The assertion reads the heading *and* that the pane is the
     branch that names `trash`, not the fallback.
  3. `test_the_search_field_here_says_it_filters_trash` — the placeholder was
     already correct before this task, which is what made the missing door read
     as a copy detail instead of a missing feature.

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
    "Playwright/Chromium unavailable: this presses the door and reads the view "
    "it opens, which no source contract can stand in for",
)
class TrashDoorTests(unittest.TestCase):
    TRASHED = ("retired-skill-alpha", "retired-skill-beta", "retired-skill-gamma")

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-trashdoor-")
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
            cls.store.create(name, f"Fixture {name}.", body=f"# {name}\n\nFixture body.\n")
        # A populated live library, so "the trash is empty" cannot pass against
        # a library that simply failed to read.
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
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_selector("#app", timeout=15000)
        # Arrive at Recovery the way a reader does, then look at the door.
        self._page.click('.viewtabs button:has-text("Recovery")')
        self._page.wait_for_selector(".recovery-ledger tbody tr", timeout=15000)
        self._page.wait_for_timeout(300)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _door(self):
        return self._page.locator('.recovery-trash-door')

    # ------------------------------------------------------- the door itself

    def test_recovery_offers_exactly_one_door_onto_the_trash_view(self):
        self.assertEqual(self._page.locator('[data-nav-view="trash"]').count(), 1)

    def test_the_door_is_inside_the_global_trash_section_it_opens(self):
        """Placement is the decision, not decoration: 0.1 recorded that trash
        is not a rail destination, and a reader looking at Recovery must find
        the fuller surface on the section that owns the subject."""
        inside = self._page.evaluate(
            "() => { const d = document.querySelector('.recovery-trash-door');"
            " const s = document.getElementById('recovery-trash-title');"
            " return !!(d && s && (s.closest('section') || {}).contains(d)); }")
        self.assertTrue(inside, "the door is not inside the Global trash section")

    def test_the_door_has_an_accessible_name_that_says_where_it_goes(self):
        name = self._door().inner_text().strip()
        self.assertIn("Trash", name)
        # A glyph-only door in a 56px rail is the affordance 2.1e had to work
        # around; this one has room and must use it.
        self.assertGreater(len(name), 8, f"door text is {name!r}")

    def test_the_door_is_reachable_and_operable_by_keyboard(self):
        self._door().focus()
        focused = self._page.evaluate(
            "() => document.activeElement === document.querySelector('.recovery-trash-door')")
        self.assertTrue(focused, "the door cannot take keyboard focus")
        self._page.keyboard.press("Enter")
        self._page.wait_for_selector('.skilllist[aria-label="Trash"]', timeout=10000)

    # ----------------------------------------------------------- what it opens

    def test_the_door_opens_the_trash_view(self):
        self._door().click()
        self._page.wait_for_selector('.skilllist[aria-label="Trash"]', timeout=10000)
        self._page.wait_for_timeout(300)
        names = self._page.eval_on_selector_all(
            '.skilllist[aria-label="Trash"] .row-main',
            "els => els.map(e => e.textContent)")
        joined = " ".join(names)
        for name in self.TRASHED:
            self.assertIn(name, joined, f"{name} missing from the Trash view")

    def test_the_door_leads_to_a_view_named_after_what_it_shows(self):
        """The pane was the chain's bare `v-else`. Measured, not inferred:
        before this task `view === 'trash'` had no control AND the pane that
        showed the trash was reachable for any unmatched view id."""
        self._door().click()
        self._page.wait_for_selector('.detail-inner:has(h1)', timeout=10000)
        self._page.wait_for_timeout(300)
        heading = self._page.inner_text("#view-title").strip()
        self.assertEqual(heading, "Global trash")
        # The branch must NAME its view. A fallback cannot: it is the branch
        # that renders whatever no earlier branch claimed.
        self.assertEqual(self._page.evaluate(
            "() => window.__skillsManagerApp.view"), "trash")

    def test_the_view_there_are_facts_and_an_action_per_item(self):
        self._door().click()
        self._page.wait_for_selector('.skilllist[aria-label="Trash"] .row-main', timeout=10000)
        self._page.click('.skilllist[aria-label="Trash"] .row-main >> nth=0')
        self._page.wait_for_timeout(300)
        facts = self._page.inner_text(".meta-below-note")
        self.assertIn("Trashed as", facts)
        self.assertIn("trash", facts)

    # --------------------------------------------------------- and back out

    def test_the_view_offers_a_way_back_to_recovery(self):
        self._door().click()
        self._page.wait_for_selector('.skilllist[aria-label="Trash"]', timeout=10000)
        self._page.click('[data-nav-view="recovery"]')
        self._page.wait_for_selector(".recovery-ledger", timeout=10000)
        self._page.wait_for_timeout(300)
        self.assertEqual(self._page.evaluate(
            "() => window.__skillsManagerApp.view"), "recovery")

    def test_the_palette_opens_the_same_view_the_door_does(self):
        """The other door. `nav-recovery` used to carry the keyword `trash`, so
        the palette DID something for the word that names the missing view."""
        self._page.keyboard.press("Meta+k")
        self._page.wait_for_selector(".command-palette-input", timeout=10000)
        self._page.fill(".command-palette-input", "trash")
        self._page.wait_for_timeout(300)
        labels = self._page.eval_on_selector_all(
            ".command-palette-option-copy strong",
            "els => els.map(e => e.textContent.trim())")
        self.assertIn("Trash", labels,
                      f"no Trash row in the palette for 'trash': {labels}")
        # The option's id is `'command-option-' + command.id` in the markup, so
        # this clicks the row by its own identity rather than by a substring of
        # text that also appears in its `title` ("Open Trash").
        self._page.click("#command-option-nav-trash")
        self._page.wait_for_selector('.skilllist[aria-label="Trash"]', timeout=10000)

    def test_the_search_field_on_the_trash_view_says_it_filters_trash(self):
        """This placeholder existed before the door did, which is why the
        missing view read as a copy detail rather than a missing feature."""
        self._door().click()
        self._page.wait_for_selector('.skilllist[aria-label="Trash"]', timeout=10000)
        placeholder = self._page.get_attribute(".searchwrap input[type=search]",
                                              "placeholder")
        self.assertEqual(placeholder, "Search trash…")
        self._page.fill(".searchwrap input[type=search]", "beta")
        self._page.wait_for_timeout(400)
        rows = self._page.eval_on_selector_all(
            '.skilllist[aria-label="Trash"] .row-main',
            "els => els.map(e => e.textContent)")
        self.assertEqual(len(rows), 1, f"search did not narrow the trash list: {rows}")

    # ---------------------------------------------------- the narrow window

    def test_nothing_overflows_at_1100px(self):
        """The laptop window a reader shrinks. Added per task, not per branch:
        it is the width where a section-label row with a count and a door has
        least room, and nothing in the tree measures it otherwise.

        BOTH surfaces are measured: the door on Recovery (it has to paint
        before it can be pressed) and the view the door opens. The first version
        pressed the door, resized, and then measured `.recovery-trash-door` —
        an element that exists only on the view it just left — so the assertion
        was `width > 0` on `null`. The fallback selector it used instead
        (`[data-nav-view="trash"]`) is the same element, so it did not help."""
        self._page.set_viewport_size({"width": 1100, "height": 820})
        self._page.wait_for_timeout(400)
        rect = self._page.evaluate(
            "() => { const r = document.querySelector('.recovery-trash-door');"
            " return r ? r.getBoundingClientRect().width : 0; }")
        self.assertGreater(rect, 0, "the door paints nothing at 1100")
        overflow = self._page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        self.assertLessEqual(overflow, 1, f"horizontal overflow of {overflow}px at 1100 on Recovery")
        self._door().click()
        self._page.wait_for_selector('.skilllist[aria-label="Trash"]', timeout=10000)
        self._page.wait_for_timeout(400)
        overflow = self._page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        self.assertLessEqual(overflow, 1, f"horizontal overflow of {overflow}px at 1100 on Trash")

    def test_no_console_errors_on_the_way_through(self):
        self._door().click()
        self._page.wait_for_selector('.skilllist[aria-label="Trash"]', timeout=10000)
        self._page.wait_for_timeout(400)
        self.assertEqual(self._errors, [])


if __name__ == "__main__":
    unittest.main()