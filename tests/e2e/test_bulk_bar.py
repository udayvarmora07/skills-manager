"""The bulk bar floats, and a selection can always be undone.

4.3. The Library's selection surface is the largest thing DESIGN-V2 §G.2 asks
for by name ("Floating bulk bar on selection") and the least built: the bar was
the first `<li>` **inside** the scrolling `.skilllist`, so ticking one checkbox
inserted a 179px block above 96 rows and pushed every one of them down. It is
now the pane's last flex child.

Four properties, none of which a screenshot settles on its own:

1. **Choosing must not move what you are choosing from.** The first row's y and
   the pane's scrollHeight must be identical before and after a selection. The
   old bar fails this by exactly its own height, which is why the assertion is
   on geometry rather than on a class name.
2. **The bar must not sit on top of the last row.** It is a sibling of the
   scroller, so the list is padded by the bar's height; dropping the padding
   leaves row 96 rendered but unreachable behind it.
3. **There must always be a way out.** `toggleSelectAll` only ever acted on the
   VISIBLE keys, so three hand-picked rows out of 96 could not be cleared -- the
   one control on offer would have *added* the other 93 -- and changing the
   filter afterwards hid the chosen rows while leaving them counted.
4. **The bar is a group, and its verbs are buttons.** A floating bar of `<div>`s
   would be Tab-blind.

Plus the dialog's two omissions: the plan hash -- the one value that makes
"cannot widen after review" checkable, and the one `webapp.py` actually enforces
-- and a per-target transition for EVERY operation rather than only `enable`.

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright


def _seed(store, count=8):
    """Real skill documents, written through the Store's own write path.

    Seven rows is past the point where the pane scrolls, so "the last row is
    reachable" is a question about scrolling rather than about fitting.
    """
    names = ["bulk-alpha", "bulk-bravo", "bulk-charlie", "bulk-delta",
             "bulk-echo", "bulk-foxtrot", "bulk-golf", "bulk-hotel"]
    for name in names[:count]:
        store.create(
            name,
            f"A fixture skill named {name} for the bulk-bar suite.",
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
    "Playwright/Chromium unavailable: the float property is a geometry claim "
    "about the real layout, and is NOT verified by this skip",
)
class BulkBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-bulkbar-")
        # RULES #8. The Store takes a data dir, but the AGENT SCOPES are read
        # from HOME, so a fixture server started without redirecting HOME walks
        # the real ~/.codex, ~/.claude and friends. Redirect FIRST, restore in
        # teardown. Pinning the browsers path keeps chromium launchable after
        # HOME moves (the same trap 0b.4a's sibling suites hit).
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
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
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        self._rows = ".skilllist > li[data-skill-key]"
        self._boxes = self._page.locator(f"{self._rows} .row-select")
        self._row_count = self._boxes.count()
        if self._row_count < 3:
            self.skipTest("the fixture produced fewer than 3 rows; nothing to select")

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    # -- helpers ---------------------------------------------------------

    def _geometry(self):
        return self._page.evaluate(
            """() => {
              const list = document.querySelector('.skilllist');
              const bar = document.querySelector('.batchbar');
              const first = document.querySelector('.skilllist > li[data-skill-key]');
              const rows = [...document.querySelectorAll('.skilllist > li[data-skill-key]')];
              const last = rows[rows.length - 1];
              const box = bar ? bar.getBoundingClientRect() : null;
              return {
                firstTop: Math.round(first.getBoundingClientRect().top),
                scrollHeight: list.scrollHeight,
                clientHeight: list.clientHeight,
                barTop: box ? Math.round(box.top) : null,
                barHeight: box ? Math.round(box.height) : null,
                barBottom: box ? Math.round(box.bottom) : null,
                lastTop: Math.round(last.getBoundingClientRect().top),
                lastBottom: Math.round(last.getBoundingClientRect().bottom),
                padBottom: getComputedStyle(list).paddingBottom,
              };
            }"""
        )

    # -- 1. choosing must not move the list ------------------------------

    def test_selecting_a_row_does_not_displace_the_list(self):
        """The property that made the old bar fail by exactly 179px."""
        before = self._geometry()
        self.assertIsNone(before["barHeight"], "a bar is visible with nothing selected")
        self._boxes.nth(0).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        after = self._geometry()

        self.assertEqual(after["firstTop"], before["firstTop"],
                         "selecting a row moved the first row down")
        # `scrollHeight` alone is the wrong measure: with eight short rows the
        # list does not overflow, so scrollHeight collapses to clientHeight and
        # a floating bar (which shrinks the pane) reads as a 73px "reduction".
        # What must not change is the SCROLLABLE CONTENT.
        self.assertEqual(after["scrollHeight"] - after["clientHeight"],
                         before["scrollHeight"] - before["clientHeight"],
                         "selecting a row changed how much there is to scroll")
        self.assertGreater(after["barHeight"], 0)

    def test_the_bar_is_outside_the_scrolling_list(self):
        """Not a styling preference: it is why the geometry above can hold."""
        self._boxes.nth(0).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        state = self._page.evaluate(
            """() => {
              const pane = document.querySelector('.list-pane');
              const bar = document.querySelector('.batchbar');
              return {
                barParent: bar ? bar.parentElement.className : null,
                kids: [...pane.children].map((el) => el.tagName + '.' + el.className),
                last: pane.lastElementChild ? pane.lastElementChild.className : null,
                inList: !!document.querySelector('.skilllist .batchbar'),
              };
            }"""
        )
        self.assertFalse(state["inList"], ".batchbar is still a child of .skilllist")
        # It is the pane's LAST child, so it sits under the scroller and cannot
        # scroll with it.
        self.assertEqual(state["last"], "batchbar", state)

    def test_the_bar_does_not_scroll_away_from_the_reader(self):
        """It floats: scrolling the list keeps it on screen at a fixed y."""
        self._boxes.nth(0).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        first = self._page.evaluate("() => Math.round(document.querySelector('.batchbar').getBoundingClientRect().top)")
        self._page.evaluate("() => document.querySelector('.skilllist').scrollTop = 400")
        self._page.wait_for_timeout(150)
        after = self._page.evaluate("() => Math.round(document.querySelector('.batchbar').getBoundingClientRect().top)")
        self.assertEqual(after, first, "the bar scrolled with the list")

    # -- 2. it must not cover the last row -------------------------------

    def test_the_last_row_is_not_hidden_behind_the_bar(self):
        self._boxes.nth(0).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        self._page.evaluate("() => { const l = document.querySelector('.skilllist'); l.scrollTop = l.scrollHeight; }")
        self._page.wait_for_timeout(200)
        state = self._page.evaluate(
            """() => {
              const list = document.querySelector('.skilllist');
              const bar = document.querySelector('.batchbar');
              const rows = [...document.querySelectorAll('.skilllist > li[data-skill-key]')];
              const last = rows[rows.length - 1].getBoundingClientRect();
              return { lastBottom: Math.round(last.bottom), barTop: Math.round(bar.getBoundingClientRect().top),
                       pad: getComputedStyle(list).paddingBottom };
            }"""
        )
        self.assertLessEqual(state["lastBottom"], state["barTop"] + 1,
                             f"the last row is behind the bar: {state}")

    # -- 3. a selection can always be undone -----------------------------

    def test_clear_empties_a_hand_picked_selection(self):
        """`toggleSelectAll` cannot do this: it only acts on the visible keys."""
        for i in range(3):
            self._boxes.nth(i).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        count = self._page.inner_text(".batchbar-count")
        self.assertIn("3", count, count)

        self._page.click(".batchbar-clear")
        self._page.wait_for_selector(".batchbar", state="detached", timeout=5000)
        self.assertEqual(
            self._page.evaluate(
                "() => document.querySelectorAll('.row-select:checked').length"), 0,
            "rows stayed checked after Clear")

    def test_clear_works_when_the_selection_is_not_on_screen(self):
        """The trap: filter the rows away and the count has no visible subject.

        `toggleSelectAll` adds every VISIBLE key when the visible set is not
        fully selected, so on three-of-eight hand-picked rows the one control on
        offer would have grown the selection to eight rather than emptied it.
        """
        for i in range(3):
            self._boxes.nth(i).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        # Move the selection out of the rendered set: search for nothing.
        self._page.fill(".topbar input[type='search'], .topbar input", "zzz-no-such-skill")
        self._page.wait_for_timeout(500)
        bar_visible = self._page.evaluate("() => !!document.querySelector('.batchbar')")
        self.assertTrue(bar_visible, "the bar vanished while a selection was still counted")

        self._page.click(".batchbar-clear")
        self._page.wait_for_selector(".batchbar", state="detached", timeout=5000)
        self._page.fill(".topbar input[type='search'], .topbar input", "")
        self._page.wait_for_timeout(500)
        self.assertEqual(
            self._page.evaluate(
                "() => document.querySelectorAll('.row-select:checked').length"), 0,
            "the hidden selection survived Clear")

    # -- 4. it is operable ----------------------------------------------

    def test_every_verb_is_a_button_inside_a_labelled_group(self):
        self._boxes.nth(0).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        state = self._page.evaluate(
            """() => {
              const bar = document.querySelector('.batchbar');
              const buttons = [...bar.querySelectorAll('button, summary')];
              const r = buttons.map((b) => { const x = b.getBoundingClientRect();
                return { tag: b.tagName.toLowerCase(), text: b.textContent.trim(),
                         w: Math.round(x.width), h: Math.round(x.height) }; });
              return { label: bar.getAttribute('aria-label'), role: bar.getAttribute('role'), r };
            }"""
        )
        self.assertEqual(state["role"], "group", state)
        self.assertTrue(state["label"], "the bar is not labelled")
        labels = [item["text"] for item in state["r"]]
        for verb in ("Clear", "Tags", "Enable", "Disable", "Sync", "Remove"):
            self.assertIn(verb, labels, f"{verb} is not a control in the bar: {labels}")
        for item in state["r"]:
            self.assertGreaterEqual(item["h"], 24, f"{item['text']} is {item['h']}px tall")

    def test_the_tag_field_is_labeled_not_a_bare_placeholder(self):
        """It was a permanently-open input whose only name was a placeholder."""
        self._boxes.nth(0).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        self._page.click(".batchbar-tags > summary")
        self._page.wait_for_selector("#batch-tags", timeout=5000)
        state = self._page.evaluate(
            """() => {
              const input = document.querySelector('#batch-tags');
              const label = document.querySelector('label[for="batch-tags"]');
              return { labelled: !!label, text: label ? label.textContent.trim() : '',
                       aria: input.getAttribute('aria-label'), placeholder: input.placeholder };
            }"""
        )
        self.assertTrue(state["labelled"], "the tag field has no <label for>")
        self.assertTrue(state["text"], "the tag field's label is empty")

    # -- the dialog's two omissions --------------------------------------

    def test_the_dialog_states_the_plan_hash_it_will_execute(self):
        self._boxes.nth(0).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        self._page.click(".batchbar-verb:has-text('Disable')")
        self._page.wait_for_selector('[data-modal="batch"]', timeout=15000)
        self._page.wait_for_selector(".plan-fingerprint code", timeout=15000)
        self._page.wait_for_function(
            "() => { const c = document.querySelector('.plan-fingerprint code');"
            " return c && c.textContent.trim() && !c.textContent.includes('not yet built'); }",
            timeout=15000)
        plan_id = self._page.inner_text(".plan-fingerprint code").strip()
        self.assertGreaterEqual(len(plan_id), 8, plan_id)
        # The same identifier the request carries, so the reader can check the
        # promise rather than take it.
        self.assertIn(
            "This plan is partial-failure safe and cannot widen after review.",
            self._page.inner_text('[data-modal="batch"]'))

    def test_every_target_states_its_transition_for_a_non_enable_operation(self):
        """`disable` used to list names and paths and say nothing else."""
        self._boxes.nth(0).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        self._page.click(".batchbar-verb:has-text('Disable')")
        self._page.wait_for_selector('[data-modal="batch"] .batch-target-list li', timeout=15000)
        rows = self._page.evaluate(
            """() => [...document.querySelectorAll('[data-modal="batch"] .batch-target-list li')]
                .map((li) => {
                  const out = li.querySelector('.batch-target-outcome');
                  const r = out ? out.getBoundingClientRect() : null;
                  return { text: out ? out.textContent.trim() : '',
                           w: r ? Math.round(r.width) : 0, h: r ? Math.round(r.height) : 0 };
                })"""
        )
        self.assertTrue(rows, "the dialog listed no targets")
        for row in rows:
            self.assertTrue(row["text"], f"a target states no transition: {row}")
            self.assertGreater(row["w"], 0, f"the transition is collapsed: {row}")

    def test_no_target_row_renders_an_empty_path_cell(self):
        """A malformed skill has no path; the cell used to render as nothing."""
        self._page.fill(".topbar input[type='search'], .topbar input", "zzz-no-such-skill")
        self._page.wait_for_timeout(300)
        self._page.fill(".topbar input[type='search'], .topbar input", "")
        self._page.wait_for_timeout(400)
        self._boxes.nth(0).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        self._page.click(".batchbar-verb:has-text('Enable')")
        self._page.wait_for_selector('[data-modal="batch"] .batch-target-list li', timeout=15000)
        empties = self._page.evaluate(
            """() => [...document.querySelectorAll('[data-modal="batch"] .batch-target-list li')]
                .filter((li) => { const c = li.querySelector('code'); return !c || !c.textContent.trim(); })
                .map((li) => li.textContent.trim())"""
        )
        self.assertEqual(empties, [], f"targets rendered with an empty path cell: {empties}")

    # -- 5. every width, not just 1280 (4.3b) ---------------------------
    #
    # This file ran at ONE width until 4.3b. The 390px wrap regression was caught
    # by a capture script measuring a 22px document overflow -- not by a test --
    # which is exactly how it came back. The properties below are the ones that
    # break silently at narrow widths, asserted at all three.

    WIDTHS = (390, 768, 1280)

    def _open_library_at(self, width):
        self._page.set_viewport_size({"width": width, "height": 900})
        self._page.wait_for_timeout(250)
        drawer = self._page.locator(".nav-drawer-trigger")
        if width <= 760:
            drawer.click()
            self._page.wait_for_timeout(250)
            self._page.click("button[data-tip='Library']")
        else:
            # A drawer opened by the PREVIOUS subTest is still up and covers the
            # rail, so closing it is part of changing width, not of navigating.
            if drawer.get_attribute("aria-expanded") == "true":
                drawer.click()
                self._page.wait_for_timeout(250)
            self._page.click("button[data-tip='Library']")
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        self._page.wait_for_timeout(250)

    def _select_three(self):
        boxes = self._page.locator(".skilllist > li[data-skill-key] .row-select")
        for i in range(min(3, boxes.count())):
            # `check()`, not `click()`: the loop runs once per width on ONE page,
            # and a plain click on an already-ticked row unticks it -- so the
            # second subTest would empty the selection the first one made and
            # then wait forever for a bar that is correctly gone.
            boxes.nth(i).check()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        self._page.wait_for_timeout(200)

    def test_the_bar_fits_every_measured_width_on_one_verb_row(self):
        """Six verbs measured 373px inside a 362px bar at 390 and wrapped.

        `Clear` moved onto the count row -- it ends the selection rather than
        acting on it -- taking 57px off the verb row. The assertion is the
        geometry, not the intent: sum the verb row and compare it to the room
        the bar actually has.
        """
        for width in self.WIDTHS:
            with self.subTest(width=width):
                self._open_library_at(width)
                self._select_three()
                state = self._page.evaluate(
                    """() => {
                      const bar = document.querySelector('.batchbar');
                      const cs = getComputedStyle(bar);
                      const verbs = [...bar.querySelectorAll('.batchbar-actions > *')];
                      const used = verbs.reduce((n, el) => n + el.getBoundingClientRect().width, 0);
                      const inner = bar.getBoundingClientRect().width
                        - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
                      const tops = [...new Set(verbs.map((el) => Math.round(el.getBoundingClientRect().top)))];
                      return { used: Math.round(used), inner: Math.round(inner), rows: tops.length,
                               barH: Math.round(bar.getBoundingClientRect().height) };
                    }"""
                )
                self.assertLessEqual(
                    state["used"], state["inner"],
                    f"at {width}px the verb row needs {state['used']}px of {state['inner']}px")
                self.assertEqual(
                    state["rows"], 1,
                    f"at {width}px the verbs wrapped onto {state['rows']} rows "
                    f"(bar {state['barH']}px tall)")

    def test_no_width_pushes_the_document_past_the_viewport(self):
        """The 22px overflow that 4.3 found by hand. `scrollWidth` on the ROOT,
        not on an element: an inner scroller absorbs overflow and hides it."""
        for width in self.WIDTHS:
            with self.subTest(width=width):
                self._open_library_at(width)
                self._select_three()
                self.assertEqual(
                    self._page.evaluate(
                        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"),
                    0, f"the document overflows horizontally at {width}px")

    def test_every_verb_stays_inside_the_bar_at_every_width(self):
        """A verb that renders outside its container is present and unclickable.

        Scoped to the verb row, NOT to every descendant: the tag panel is a
        popover positioned above the bar and is meant to overhang it. Asserting
        on the whole subtree flags the panel's own Add/Remove buttons as
        escapes -- a check that fails for the right-looking reason and is
        therefore useless.
        """
        for width in self.WIDTHS:
            with self.subTest(width=width):
                self._open_library_at(width)
                self._select_three()
                escaped = self._page.evaluate(
                    """() => {
                      const bar = document.querySelector('.batchbar').getBoundingClientRect();
                      return [...document.querySelectorAll('.batchbar-actions > *, .batchbar-count > button')]
                        .filter((el) => { const r = el.getBoundingClientRect();
                          return r.right > bar.right + 1 || r.left < bar.left - 1; })
                        .map((el) => el.textContent.trim());
                    }"""
                )
                self.assertEqual(escaped, [], f"at {width}px these left the bar: {escaped}")

    # -- 6. the tag path tells the truth (4.3b) --------------------------
    #
    # The bar counts EXACT PHYSICAL INSTANCES. `/api/catalog/tags` is keyed by
    # LOGICAL NAME, so one selected copy of a three-copy skill writes all three.
    # The REST contract is frozen and the catalog has no per-instance key, so the
    # fix is the sentence -- and a sentence that only exists when it is true.

    def test_the_tag_panel_states_catalog_names_not_selected_instances(self):
        """The defect: the control beneath "exact physical instances" was not
        exact, and nothing said so."""
        self._boxes.nth(0).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        self._page.click(".batchbar-tags > summary")
        self._page.wait_for_selector(".batchbar-tagplan", timeout=5000)
        plan = self._page.evaluate(
            """() => {
              const p = document.querySelector('.batchbar-tagplan');
              const entries = [...p.querySelectorAll('.batchbar-tagentry')];
              return { text: p.textContent.trim(), role: p.getAttribute('role'),
                       entries: entries.map((e) => e.textContent.trim()) };
            }"""
        )
        self.assertEqual(plan["role"], "note", plan)
        self.assertTrue(plan["entries"], f"the tag plan named no entry: {plan}")
        self.assertIn("catalog name", plan["text"], plan)
        # Every entry names a skill and a copy count -- an entry without a count
        # would restate the problem it exists to fix.
        for entry in plan["entries"]:
            self.assertRegex(entry, r"\d+\s+cop", f"entry states no copy count: {entry}")

    def test_the_tag_plan_matches_what_the_api_would_be_given(self):
        """The sentence must be TRUE, not decorative: it counts from the same
        `this.skills` the request's `names` are derived from."""
        for i in range(3):
            self._boxes.nth(i).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        self._page.click(".batchbar-tags > summary")
        self._page.wait_for_selector(".batchbar-tagplan", timeout=5000)
        state = self._page.evaluate(
            """() => {
              const shown = [...document.querySelectorAll('.batchbar-tagplan code')]
                .map((c) => c.textContent.trim());
              const count = document.querySelector('.batchbar-count strong').textContent.trim();
              return { shown, count };
            }"""
        )
        self.assertEqual(
            len(set(state["shown"])), len(state["shown"]),
            f"the plan lists one entry twice: {state}")
        self.assertLessEqual(
            len(state["shown"]), int(state["count"]),
            f"the plan claims more names ({state['shown']}) than instances selected ({state['count']})")

    def test_the_dialog_says_when_a_target_is_no_longer_loaded(self):
        """`selectedSnapshot` bounds staleness to targets that fell out of the
        loaded set -- but a review built from stale fields has to admit it."""
        for i in range(3):
            self._boxes.nth(i).click()
        self._page.wait_for_selector(".batchbar", timeout=5000)
        self._page.fill(".topbar input[type='search'], .topbar input", "zzz-no-such-skill")
        self._page.wait_for_timeout(600)
        self._page.click(".batchbar-verb:has-text('Disable')")
        self._page.wait_for_selector('[data-modal="batch"] .batch-target-list li', timeout=15000)
        note = self._page.evaluate(
            """() => { const n = document.querySelector('.batch-stale-note');
                       return n ? n.textContent.trim() : null; }"""
        )
        self.assertIsNotNone(note, "3 targets fell out of the loaded list and the dialog did not say so")
        self.assertIn("no longer in the loaded list", note, note)
        self.assertIn("selected", note, note)


if __name__ == "__main__":
    unittest.main()