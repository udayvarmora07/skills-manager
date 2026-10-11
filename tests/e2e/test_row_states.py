"""Every row states its state in words, so nothing may restate it as a tooltip.

4.2b. The row dot carries `title="Skill instance"` on any row that is not
divergent -- measured at **84 of 96 rows** in the seeded library, a string that
restates what the row already is and informs nobody. The remaining 12 said
"Divergent copies", which IS information, which is why the defect was easy to
miss by reading one row.

The fix is that the dot is decorative: the state is stated in words by
`.identity-state` immediately beside it (Active / Disabled / Malformed /
Unaddressable / Divergent / Linked outside root), so the dot is
`aria-hidden` with no title. The colour stays as the at-a-glance cue.

The test asserts the stronger property, not just this string: **no row may
carry a tooltip whose text is identical across the whole list**, because a
constant tooltip carries zero information by construction. And it asserts the
state is still reachable as TEXT, so "decorative" cannot become "gone".

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import os
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
    "Playwright/Chromium unavailable: this reads rendered tooltips, which "
    "need a real DOM and are NOT verified by this skip",
)
class RowStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-rowstate-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                real_home, ".cache", "ms-playwright")
        # RULES #8: the agent SCOPES come from HOME, not from the data dir, so
        # a fixture server started without this walks the real ~/.codex.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        for name, body in (("plain-active", "# plain\n\nAn ordinary skill."),
                           ("broken-doc", "# broken\n\nbody")):
            cls.store.create(name, f"Fixture {name}.", body=body)
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
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.click('.viewtabs button:has-text("Library")')
        self._page.wait_for_selector(".skilllist > li[data-skill-key]", timeout=15000)
        self._page.wait_for_timeout(300)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _rows(self):
        return self._page.evaluate(
            """() => Array.from(document.querySelectorAll(
                '.skilllist > li[data-skill-key]')).map(r => ({
                  key: r.getAttribute('data-skill-key'),
                  dotTitle: (r.querySelector('.dot') || {}).getAttribute
                    ? r.querySelector('.dot').getAttribute('title') : undefined,
                  dotAriaHidden: (r.querySelector('.dot') || {}).getAttribute
                    ? r.querySelector('.dot').getAttribute('aria-hidden') : undefined,
                  stateText: (() => {
                    const el = r.querySelector('.identity-state');
                    return el ? el.textContent.trim() : null;
                  })(),
                }))"""
        )

    def test_no_row_carries_a_tooltip_that_says_the_same_thing_on_every_row(self):
        rows = self._rows()
        self.assertGreaterEqual(len(rows), 2, "fixture must render at least two rows")
        titles = {r["dotTitle"] for r in rows}
        self.assertEqual(
            titles, {None},
            "a constant tooltip carries zero information by construction; "
            f"measured: {titles}",
        )

    def test_the_row_dot_is_marked_decorative(self):
        """`aria-hidden` is what makes "decorative" true rather than asserted.

        Without it the dot is still a labelled node in the accessibility tree
        announcing a colour that the words beside it already state.
        """
        for row in self._rows():
            with self.subTest(row=row["key"]):
                self.assertEqual(row["dotAriaHidden"], "true")

    def test_the_state_is_still_stated_in_words_on_every_row(self):
        """The other half: the dot became decorative, the WORDS must remain.

        "Remove the redundant tooltip" is a one-line change that also removes
        the only thing some readers were using. Every row must still name its
        observed state as text.
        """
        allowed = {"Active", "Disabled", "Malformed", "Unaddressable",
                   "Divergent", "Linked outside root"}
        for row in self._rows():
            with self.subTest(row=row["key"]):
                self.assertIsNotNone(row["stateText"], "a row must state its state in words")
                for part in row["stateText"].split("·"):
                    self.assertIn(part.strip(), allowed, row["stateText"])

    def test_the_colour_cue_is_still_painted(self):
        """Decorative must not become invisible. The dot is the at-a-glance cue
        the words support; removing the tooltip is not a licence to stop
        painting it."""
        painted = self._page.evaluate(
            """() => {
              const dots = [...document.querySelectorAll(
                '.skilllist > li[data-skill-key] > .dot')];
              return dots.filter(d => d.getBoundingClientRect().width > 0).length;
            }"""
        )
        self.assertGreater(painted, 0, "the row dot must still paint")


if __name__ == "__main__":
    unittest.main()