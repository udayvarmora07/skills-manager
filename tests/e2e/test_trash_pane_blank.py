"""7.4e e2e — the Trash pane's blank state, and the back button's label.

`tests/test_redesign_trash_pane_blank.py` can read the markup. It cannot read
a blank pane that has 700px of nothing under it, and it cannot read a button
whose label is wrong on the view the test never visited — so this file drives
the real thing at the widths that matter.

Two disciplines this file inherits rather than re-invents:

  * it PRESSES the door from Recovery (7.4c) instead of calling
    `switchView('trash')`, because calling the method would only prove the view
    renders, which it always did;
  * the blank-state assertions ask the DOM **what is painted**, and pair every
    fact by its label — 2.1c's own lesson was that "some dd has a value" passed
    with one row blanked, and `hidden` does not change `textContent`, so
    "is this fact actually shown" has to go through `getBoundingClientRect`.

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


BLANK_PROBE = """() => {
  const blank = document.querySelector('.detail-inner .pane-blank');
  if (!blank) return {present: false};
  const box = blank.getBoundingClientRect();
  const pane = blank.closest('.detail');
  const paneBox = pane.getBoundingClientRect();
  const facts = [...blank.querySelectorAll('.pane-blank-facts > div')].map(div => {
    const dt = div.querySelector('dt');
    const dd = div.querySelector('dd');
    if (!dt || !dd) return {label: null, value: null, painted: false};
    const r = dd.getBoundingClientRect();
    return {
      label: dt.textContent.trim(),
      value: dd.textContent.trim(),
      painted: r.width > 0 && r.height > 0 && r.top >= box.top - 1
               && r.bottom <= box.bottom + 1,
    };
  });
  const title = blank.querySelector('.pane-blank-title');
  const tr = title ? title.getBoundingClientRect() : {width: 0, height: 0};
  return {
    present: true,
    title: title ? title.textContent.trim() : '',
    titlePainted: tr.width > 0 && tr.height > 0,
    box: {top: box.top, height: box.height, width: box.width},
    paneHeight: paneBox.height,
    voidBelow: Math.round(paneBox.bottom - box.bottom),
    facts,
    actions: [...blank.querySelectorAll('.empty-actions button')]
               .map(b => b.textContent.trim()),
  };
}"""


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: this asks what the blank pane PAINTS, "
    "which no source contract can stand in for",
)
class TrashPaneBlankTests(unittest.TestCase):
    TRASHED = ("retired-skill-alpha", "retired-skill-beta", "retired-skill-gamma")

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-trashblank-")
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
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_selector("#app", timeout=15000)
        self._page.click('.viewtabs button:has-text("Recovery")')
        self._page.wait_for_selector(".recovery-trash-door", timeout=15000)
        self._page.click(".recovery-trash-door")
        self._page.wait_for_selector('.skilllist[aria-label="Trash"]', timeout=15000)
        self._page.wait_for_timeout(350)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _blank(self):
        got = self._page.evaluate(BLANK_PROBE)
        self.assertTrue(got.get("present"),
                        "the Trash pane paints no blank state when nothing is "
                        "selected — a heading, a lead, and a void")
        return got

    # ------------------------------------------------------- the blank state

    def test_the_blank_state_states_a_title_and_it_is_painted(self):
        got = self._blank()
        self.assertTrue(got["titlePainted"], "the blank title paints nothing")
        self.assertGreater(len(got["title"]), 6,
                           f"blank title is {got['title']!r} — it must name the state")

    def test_every_fact_is_paired_by_label_and_painted(self):
        got = self._blank()
        labels = [f["label"] for f in got["facts"]]
        self.assertGreaterEqual(len(got["facts"]), 3, f"facts: {labels}")
        self.assertEqual(len([x for x in labels if x]), len(labels),
                         f"a fact rendered without a label: {labels}")
        blank = [f for f in got["facts"] if not f["painted"] or not f["value"]]
        self.assertEqual(blank, [],
                         f"facts present but not painted/valued: {blank}")

    def test_the_pane_states_something_anchored_at_the_top(self):
        """The measured defect was a heading, a lead, a note, and then ~700px of
        nothing. What this asserts is the shape 2.1c decided, NOT a magic
        remaining-height number: the state is ANCHORED at the top of the pane
        (a state, not an illustration floating down it) and it carries a
        substantial block of evidence rather than a sentence or two.

        The first version of this assertion was `voidBelow < 260`, a constant
        invented here — and it FAILED against the finished pane for doing the
        right thing: 2.1c anchors the block top-left and the whitespace below it
        is deliberate, shared with the Library. A number I chose cannot tell a
        void from the space beneath an anchored state; the two properties above
        can, and neither of them has a constant in it."""
        got = self._blank()
        self.assertGreater(got["box"]["height"], 200,
                           f"the blank state is {got['box']['height']}px tall — a "
                           "sentence or two over an empty column is what this "
                           "pane was")
        self.assertLess(got["box"]["top"], 240,
                        f"the state starts {got['box']['top']}px down the pane — "
                        "2.1c anchored it because nothing-selected is a STATE, "
                        "not an illustration")

    def test_selecting_an_item_replaces_the_blank_state_with_its_facts(self):
        self._page.click('.skilllist[aria-label="Trash"] li >> nth=0')
        self._page.wait_for_selector(".meta", timeout=10000)
        self._page.wait_for_timeout(250)
        self.assertFalse(self._page.evaluate(BLANK_PROBE).get("present"),
                         "the blank state is still painted with an item selected")

    # ------------------------------------------------------ the back button

    def test_the_view_back_button_names_the_view_you_are_in(self):
        """390 CSS px: below 760 the list and the detail are one screen at a
        time, so this button is the only way back — and it said "Back to
        Library" on seven of the eight views it renders on."""
        self._page.set_viewport_size({"width": 390, "height": 844})
        self._page.wait_for_timeout(300)
        self._page.click('.skilllist[aria-label="Trash"] li >> nth=0')
        self._page.wait_for_selector(".mobile-back", timeout=10000)
        label = self._page.inner_text(".mobile-back").strip()
        self.assertIn("Trash", label,
                      f"the back button says {label!r} on the Trash view — it "
                      "does not go to the Library")
        self.assertNotIn("Library", label)


if __name__ == "__main__":
    unittest.main()