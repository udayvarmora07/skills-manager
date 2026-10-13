"""7.4d e2e — a button that is 26px wide can still have the right WIDTH for
nothing, so the assertion is about painted text, not about a box.

Before this task, on the Trash view, the "Empty the global trash" button
computed a 26x32px box. `.trash-purge-row .btn { width: 100% }` was DECLARED
and lost the cascade to `.skilllist > li:not(...)`'s 16px dot track, which the
`<li>` row auto-placed the button into. The 143px label overflowed
symmetrically under `justify-content: center` and `.skilllist`'s
`overflow-y: auto` clipped it to its TAIL: the pane showed a red orphan reading
"the global trash" under the list.

So every assertion here is PAINT, not geometry:

  * a `Range` over the button's contents compared against the button's own
    box — the label must be inside the control that owns it. A 26px box with
    clipped text has a perfectly plausible width;
  * `document.elementFromPoint` at the label's own centre, because clipping is
    a paint operation and `getBoundingClientRect()` reports layout boxes that
    no amount of clipping changes (2.1e's lesson);
  * a CONTROL that plants the old geometry and requires the containment probe
    to fail — the mutation that proves the test can be the thing that lies.

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


# Button geometry + whether its painted label is fully inside it. Both in one
# evaluate so the assertions compare numbers from ONE layout pass.
PROBE = """() => {
  const btn = document.querySelector('.trash-purge-row .btn');
  if (!btn) return {error: 'no purge button'};
  const box = btn.getBoundingClientRect();
  const r = document.createRange();
  r.selectNodeContents(btn);
  const text = r.getBoundingClientRect();
  const hit = document.elementFromPoint(
    text.left + text.width / 2, text.top + text.height / 2);
  const cs = getComputedStyle(btn);
  const row = document.querySelector('.trash-purge-row');
  return {
    label: btn.textContent.trim(),
    box: {w: box.width, h: box.height, left: box.left, right: box.right},
    text: {w: text.width, left: text.left, right: text.right},
    // 0.5px of slack: subpixel layout, not a claim about clipping.
    contained: text.left >= box.left - 0.5 && text.right <= box.right + 0.5,
    hitIsButton: hit === btn,
    declaredWidth: cs.width,
    whiteSpace: cs.whiteSpace,
    rowDisplay: getComputedStyle(row).display,
    rowTag: row.tagName,
  };
}"""


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: this measures PAINTED text against its "
    "own control, which no source contract can stand in for",
)
class TrashPurgeRowTests(unittest.TestCase):
    TRASHED = ("retired-skill-alpha", "retired-skill-beta")

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-purgerow-")
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
        # A live skill, so "the trash is empty" cannot pass against a library
        # that simply failed to read — and so the purge row renders at all: it
        # lives in the branch where there IS something to empty.
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
        self._page.wait_for_selector(".trash-purge-row .btn", timeout=15000)
        self._page.wait_for_timeout(300)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _probe(self):
        got = self._page.evaluate(PROBE)
        self.assertNotIn("error", got, f"probe failed: {got}")
        return got

    # ------------------------------------------------------------- the defect

    def test_the_label_is_painted_inside_its_own_button(self):
        got = self._probe()
        self.assertTrue(
            got["contained"],
            f"label {got['label']!r} paints {got['text']['w']:.0f}px across "
            f"[{got['text']['left']:.0f},{got['text']['right']:.0f}] but the "
            f"button is {got['box']['w']:.0f}px "
            f"[{got['box']['left']:.0f},{got['box']['right']:.0f}] — the text "
            "overflows its own control and the list clips it to its tail")

    def test_the_button_is_hit_testable_where_its_label_is(self):
        """`elementFromPoint`, not a bounding box: clipping is a paint
        operation and layout boxes do not report it."""
        self.assertTrue(self._probe()["hitIsButton"],
                        "something other than the purge button is on screen at "
                        "the centre of its own label")

    def test_the_declared_full_width_is_the_width_that_rendered(self):
        """`width: 100%` was DECLARED and lost the cascade. A declared value
        nobody reads is exactly this repository's recurring failure, so the
        contract is between the declaration and the box."""
        got = self._probe()
        self.assertEqual(float(got["declaredWidth"].rstrip("px")),
                         round(got["box"]["w"]),
                         "the computed width is not the declared one — "
                         "something between the rule and the box is winning")

    def test_the_row_is_not_shaped_like_a_list_item(self):
        got = self._probe()
        self.assertEqual(got["rowTag"], "DIV",
                         "the purge row is an <li> again, so the three-track "
                         "row grid applies and the button lands in the 16px "
                         "dot track")
        self.assertNotEqual(got["rowDisplay"], "grid")

    # --------------------------------------------------- controls that can fail

    def test_the_probe_detects_the_defect_it_guards_against(self):
        """CONTROL — plant the old geometry and require the containment probe
        to FAIL. Without this, a probe that returned `contained: true`
        unconditionally would pass every assertion above."""
        self._page.add_style_tag(content=(
            ".trash-purge-row .btn { width: 26px !important; }"))
        self._page.wait_for_timeout(150)
        got = self._probe()
        self.assertFalse(got["contained"],
                         "a 26px button containing a 143px label reported its "
                         "label as contained — the probe cannot see clipping, "
                         "so every assertion built on it is vacuous")

    def test_the_trash_actually_has_something_in_it(self):
        """CONTROL — the purge row only renders in the branch where there IS
        something to empty, so a read failure would remove the subject and
        leave this file passing on nothing."""
        rows = self._page.locator('.skilllist[aria-label="Trash"] li').count()
        self.assertGreaterEqual(rows, len(self.TRASHED))

    def test_no_console_error_on_the_view(self):
        self.assertEqual(self._errors, [])