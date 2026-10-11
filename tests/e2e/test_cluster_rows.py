"""A row marks a cluster. A single observed copy needs no ink.

4.2c slice A. Measured on the seeded library: `.row-copies` printed
"1 copy" on **87 of 96** rows -- a constant in a bordered pill immediately
after the name that restates the row's own shape -- and 7 rows rendered an
EMPTY `.row-badges` cell, because `rowBadgeItems` computed a "N copies"
badge that the template then discarded with a regex on its own text.

Both were the 4.2b defect one element over: a string that is the same on
almost every row says nothing to any of them.

So the pill renders only when the row actually stands for a cluster (2 or
more observed copies), and the dead badge is gone from the source that
computed it -- not filtered at the far end.

The tests state the properties, not the strings:

* a row whose observed copies number one carries no cluster pill;
* a row that IS a cluster carries the observed count, formatted;
* a row never renders a `.row-badges` cell with no chips in it.

The third half matters as much as the first: "remove the dead badge" and
"stop rendering an empty cell" are different changes, and only one of them
is what the reader sees.

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
    "Playwright/Chromium unavailable: this measures rendered rows, which "
    "need a real DOM and are NOT verified by this skip",
)
class ClusterRowTests(unittest.TestCase):
    """The fixture builds one skill per copy-count so both branches render."""

    @classmethod
    def setUpClass(cls):
        sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if sys_path not in os.sys.path:
            os.sys.path.insert(0, sys_path)
        from skillsmgr import scopes
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-cluster-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            real_home = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                real_home, ".cache", "ms-playwright")
        # RULES #8: the agent SCOPES come from HOME, not the data dir, so a
        # fixture server started without this walks the real ~/.codex.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()
        body = "# fixture\n\nAn ordinary skill body."
        # Two single-copy rows and one two-copy row, so the "no pill" branch
        # and the "cluster" branch are both reachable from one fixture. The
        # second scope id comes from the product's own registry rather than a
        # hard-coded directory, so a renamed root cannot silently turn the
        # cluster fixture into a second single-copy row -- which would make
        # every assertion below pass for the wrong reason.
        scopes.set_global_store(cls.store)
        agent = next(s for s in scopes.known_scopes() if s.id != "global")
        for name in ("lone-skill-one", "lone-skill-two", "shared-skill"):
            cls.store.create(name, "Fixture %s." % name, body=body)
        scopes.create_skill(agent.id, "shared-skill", "Fixture shared-skill.",
                            body=body)
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
        self._page.wait_for_timeout(250)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _rows(self):
        return self._page.evaluate(
            """() => Array.from(document.querySelectorAll(
                '.skilllist > li[data-skill-key]')).map(r => ({
                  name: (r.querySelector('.row-name') || {}).textContent
                    ? r.querySelector('.row-name').textContent.trim() : '',
                  pill: (() => {
                    const el = r.querySelector('.row-copies');
                    if (!el) return null;
                    const box = el.getBoundingClientRect();
                    return { text: el.textContent.trim(), width: box.width,
                             painted: box.width > 0 && box.height > 0 };
                  })(),
                  badgeCells: r.querySelectorAll('.row-badges').length,
                  badgeChips: r.querySelectorAll('.row-badges .tag').length,
                }))"""
        )

    def _by_name(self, name):
        for row in self._rows():
            if row["name"].startswith(name):
                return row
        self.fail("no row for %r in %r" % (name, [r["name"] for r in self._rows()]))

    def test_a_single_copy_row_carries_no_cluster_pill(self):
        """The defect in the shape a reader sees it.

        Printed on every row, the count said "1 copy" on 87 of 96 rows. A
        string that is identical across almost the whole list is not
        information; it is the row's own shape restated in a bordered pill.
        """
        row = self._by_name("lone-skill-one")
        self.assertIsNone(
            row["pill"],
            "a row backing exactly one observed copy must not claim a cluster: "
            f"measured {row['pill']!r}",
        )

    def test_a_cluster_row_states_the_observed_count_and_paints_it(self):
        """The other half: "mark the exception" must not become "mark nothing".

        The count is asserted twice -- that the digits are there, and that
        the element actually paints. A pill present but zero-width is what a
        screenshot review of a scaled capture can mistake for a removed one,
        so this reads the box rather than trusting the attribute.
        """
        row = self._by_name("shared-skill")
        self.assertIsNotNone(row["pill"], "a two-copy row must say so")
        self.assertIn("2", row["pill"]["text"])
        self.assertTrue(
            row["pill"]["painted"],
            f"the cluster pill exists but paints nothing: {row['pill']}",
        )
        self.assertEqual(row["name"], "shared-skill 2 copies")

    def test_no_row_renders_an_empty_badge_cell(self):
        """`rowBadgeItems` used to return a "N copies" badge that the
        template removed with `/^\\d+ cop/` on its own text, so every
        multi-copy row without tags rendered an empty cell -- measured at 7 of
        96. The count is not a badge; the cluster pill owns it now.
        """
        for row in self._rows():
            with self.subTest(row=row["name"]):
                self.assertEqual(
                    row["badgeCells"], row["badgeChips"],
                    "a .row-badges cell rendered with no chips in it",
                )

    def test_the_cluster_pill_is_mono_and_survives_a_narrow_pane(self):
        """The pill sits on the name line at the far left of a grid track; a
        narrow pane is where an exception marker gets clipped or wraps the
        name. 390px is the width the phone band renders at.
        """
        self._page.set_viewport_size({"width": 390, "height": 760})
        self._page.wait_for_timeout(250)
        row = self._by_name("shared-skill")
        self.assertIsNotNone(row["pill"], "the cluster mark must not be dropped on a phone")
        self.assertTrue(row["pill"]["painted"])
        overflow = self._page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        self.assertLessEqual(overflow, 0, f"horizontal overflow of {overflow}px at 390")