"""5.4b e2e — the Workspaces view, which had NO e2e at all.

`tests/test_redesign_workspaces.py` runs the computed properties in a Node VM
against the real `catalog()`, which is real coverage of the FACTS and none of
the RENDERING. Nothing had ever driven this page in a browser, which is how two
of its three 5.4 defects survived: every candidate path wearing `.tag`'s shared
`max-width: 90px` (so the one fact the page exists to show read "path unkno…"),
and a `not-requested` badge painted as a finding.

This file drives:
  * the project-path flow end to end — accepted / missing / outside-managed-roots,
    and the path being WITHHELD when the root says so (a redaction that renders
    the path anyway is a privacy claim with no reader);
  * the geometry the 5.4b CSS fix is about, at four laptop widths.

Every assertion measures the LIVE DOM. SKIPS LOUDLY when Playwright is absent.
"""

import os
import shutil
import sys
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WIDTHS = (1100, 1280, 1440, 1920)


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
    "Playwright/Chromium unavailable: this reads rendered geometry, painted "
    "text and redaction, which need a real DOM and are NOT verified by this skip",
)
class WorkspacesViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-workspaces-")
        cls._saved_env = {k: os.environ.get(k)
                          for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                    "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved_env.get("PLAYWRIGHT_BROWSERS_PATH"):
            rh = cls._saved_env.get("HOME") or os.path.expanduser("~")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
                rh, ".cache", "ms-playwright")
        # RULES #8: the agent SCOPES come from HOME, not the data dir, so the
        # fake home is set BEFORE anything reads a scope root.
        home = os.path.join(cls._tmp, "home")
        os.makedirs(home, exist_ok=True)
        os.environ["HOME"] = home
        os.environ["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls._tmp, "data")

        cls.store = Store(cls._tmp)
        cls.store.init_db()

        # `/api/workspaces` contains the project path against
        # `store.data_dir` ONLY (webapp.py:1078), so the fixture paths below are
        # relative to it. `project_observation` checks six candidate roots under
        # the project; one existing and one missing makes both states of the
        # per-root mark reachable in a single observation.
        data_dir = os.path.realpath(cls.store.data_dir)
        cls.project = os.path.join(data_dir, "workspace-fixture")
        os.makedirs(os.path.join(cls.project, ".claude", "skills"), exist_ok=True)
        cls.missing = os.path.join(data_dir, "workspace-fixture-absent")
        # A real directory that is NOT under the managed data root — the
        # redaction branch. First draft used `realpath(cls._tmp)` for this and
        # the panel reported "accepted": `Store(dir)` uses that directory
        # verbatim, so the whole temp tree IS the managed root. The parent of
        # the temp dir is the nearest directory that is genuinely outside it.
        cls.outside = os.path.dirname(os.path.realpath(cls._tmp))
        assert not (os.path.realpath(cls.outside) == data_dir
                    or data_dir in os.path.realpath(cls.outside).split(os.sep)), (
            "the fixture's 'outside' path is inside the managed root, so the "
            "redaction assertions would be testing the accepted branch")

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
        self._failed = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.on("requestfailed",
                      lambda r: self._failed.append(r.url))
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.click('.viewtabs button:has-text("Workspaces")')
        self._page.wait_for_selector(".adapter-table", timeout=15000)
        self._page.wait_for_timeout(400)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _check_project(self, path):
        self._page.fill("#workspace-project", path)
        self._page.click('.workspace-project-form .btn-secondary')
        self._page.wait_for_timeout(1200)

    # --------------------------------------------------- the catalogue facts

    def test_the_catalogue_lists_every_consumer_the_api_reports(self):
        api = self._page.evaluate(
            "async () => (await (await fetch('/api/workspaces')).json()).adapters"
            ".filter(Boolean).map(a => a.label || a.id)")
        painted = self._page.eval_on_selector_all(
            ".adapter-row .adapter-label", "els => els.map(e => e.textContent.trim())")
        self.assertEqual(painted, api,
                         "the table must show every adapter the API returns, and "
                         "nothing else")

    def test_each_root_keeps_the_tier_that_gives_it_meaning(self):
        """The 5.4 defect: `candidate_roots` is the FLAT union of `tiers`, so a
        table built from it loses the tier note that bounds a lower-tier win."""
        tiers = self._page.eval_on_selector_all(
            ".adapter-row", "els => els.map(e => e.querySelectorAll("
            "'.adapter-tier').length)")
        notes = self._page.eval_on_selector_all(
            ".adapter-tier-note", "els => els.map(e => e.textContent.trim())")
        self.assertTrue(any(n > 1 for n in tiers) or any(notes),
                        "at least one consumer must keep its tier grouping or its "
                        "tier note — a flat root list has thrown both away")

    def test_a_candidate_root_is_never_truncated(self):
        """The defect `.tag` caused: `max-width: 90px` amputated every path.
        Measure the TEXT against its own box — `scrollWidth === clientWidth` on a
        clipped element reports success (see MAP.md, 4.7), so this compares a
        Range over the text with the box that is supposed to contain it."""
        worst = self._page.evaluate(
            """() => {
              const out = [];
              document.querySelectorAll('.adapter-root code, .workspace-root code')
                .forEach(el => {
                  const r = document.createRange();
                  r.selectNodeContents(el);
                  const t = r.getBoundingClientRect(), b = el.getBoundingClientRect();
                  out.push({text: el.textContent.trim(),
                            over: Math.round(t.right - b.right),
                            under: Math.round(b.bottom - t.bottom)});
                });
              return out;
            }""")
        self.assertTrue(worst, "the catalogue rendered no candidate roots at all")
        clipped = [w for w in worst if w["over"] > 1 or w["under"] < -1]
        self.assertEqual(clipped, [],
                         f"root paths are clipped by their own box: {clipped[:4]}")

    def test_an_unknown_root_is_named_rather_than_dropped(self):
        """A root the catalogue records no path for is a gap in the evidence."""
        unknown = self._page.eval_on_selector_all(
            ".adapter-root.is-unknown code", "els => els.map(e => e.textContent.trim())")
        for label in unknown:
            self.assertTrue(label, "an unknown root rendered an empty path")

    # ------------------------------------------------------- the 5.4b fix

    def test_the_consumer_name_never_wraps(self):
        """The defect: `.adapter-consumer-head` was a flex ROW and the badge is
        `flex: none` carrying two words, so in a 27% column flex shrink handed
        the label the remainder and "Claude Code" wrapped mid-name."""
        for width in WIDTHS:
            with self.subTest(width=width):
                self._page.set_viewport_size({"width": width, "height": 900})
                self._page.wait_for_timeout(250)
                tall = self._page.evaluate(
                    """() => {
                      const out = [];
                      document.querySelectorAll('.adapter-label').forEach(el => {
                        const lh = parseFloat(getComputedStyle(el).lineHeight);
                        const lines = Math.round(el.getBoundingClientRect().height
                                                 / (isNaN(lh) ? 16 : lh));
                        if (lines > 1) out.push([el.textContent.trim(), lines]);
                      });
                      return out;
                    }""")
                self.assertEqual(tall, [],
                                 f"a consumer name wraps onto {tall} at {width}px")
        self._page.set_viewport_size({"width": 1280, "height": 900})

    def test_everything_in_a_row_header_starts_at_the_same_edge(self):
        """Stacking moved the badge under the name; a row header whose parts
        start at two different x values reads as two columns."""
        offs = self._page.evaluate(
            """() => {
              const out = [];
              document.querySelectorAll('.adapter-consumer').forEach(cell => {
                const head = cell.querySelector('.adapter-consumer-head');
                const badge = head && head.querySelector('.badge');
                if (!badge) return;
                out.push([Math.round(head.getBoundingClientRect().left),
                          Math.round(badge.getBoundingClientRect().left)]);
              });
              return out;
            }""")
        self.assertTrue(offs, "no consumer row painted a badge at all")
        self.assertEqual([o for o in offs if o[0] != o[1]], [],
                         "the badge and the name must share a left edge")

    # ------------------------------------------------------ the project flow

    def test_the_idle_page_says_one_sentence_and_wears_no_badge(self):
        """The 5.4 defect: `not-requested` wore `badge-warn`, styling the page's
        resting state as a finding the reader has to dismiss."""
        self.assertEqual(
            self._page.eval_on_selector_all(".workspace-observation", "e => e.length"), 0,
            "nothing is observed until a path is requested")
        self.assertEqual(
            self._page.eval_on_selector_all(".workspace-idle .badge", "e => e.length"), 0,
            "the idle state must not be painted as a finding")
        self.assertIn("No project has been observed",
                      self._page.inner_text(".workspace-idle"))

    def test_an_existing_path_inside_the_managed_root_is_accepted(self):
        self._check_project(self.project)
        self._page.wait_for_selector(".workspace-observation", timeout=8000)
        self.assertEqual(
            self._page.inner_text(".workspace-observation .badge").strip(), "accepted")
        self.assertIn(self.project, self._page.inner_text(".workspace-project-path"))
        marks = self._page.eval_on_selector_all(
            ".workspace-root",
            "els => els.map(e => [e.querySelector('code').textContent.trim(),"
            " e.classList.contains('is-present')])")
        self.assertTrue(any(m[1] for m in marks),
                        f"the fixture created .claude/skills; none read as present: {marks}")
        self.assertTrue(any(not m[1] for m in marks),
                        f"the other five candidates must read as absent: {marks}")
        self.assertIn("1 of 6", self._page.inner_text(".workspace-observation"),
                      "the sentence must count what exists, not just list roots")

    def test_a_missing_path_is_reported_as_missing_not_as_read(self):
        self._check_project(self.missing)
        self._page.wait_for_selector(".workspace-observation", timeout=8000)
        self.assertEqual(
            self._page.inner_text(".workspace-observation .badge").strip(), "missing")
        self.assertIn("does not exist", self._page.inner_text(".workspace-observation"))
        self.assertEqual(
            self._page.eval_on_selector_all(".workspace-root", "e => e.length"), 0,
            "a path that does not exist has no roots to report")

    def test_a_path_outside_the_managed_root_has_its_path_withheld(self):
        """The redaction claim. A page that says 'its path is withheld' and then
        prints the path has a privacy control that a reader cannot see."""
        self._check_project(self.outside)
        self._page.wait_for_selector(".workspace-observation", timeout=8000)
        panel = self._page.inner_text(".workspace-observation")
        self.assertIn("outside-managed-roots", panel)
        self.assertIn("withheld", panel)
        self.assertNotIn(self.outside, panel,
                         "the withheld path was printed in the panel")
        self.assertEqual(
            self._page.eval_on_selector_all(".workspace-root", "e => e.length"), 0)

    def test_a_rejected_path_is_not_painted_as_a_success(self):
        for path in (self.missing, self.outside):
            with self.subTest(path=path):
                self._check_project(path)
                tone = self._page.get_attribute(
                    ".workspace-observation .badge", "class")
                self.assertIn("badge-warn", tone,
                              "a path that was not accepted must not wear the "
                              "accepted tone")

    # ---------------------------------------------------------- hygiene

    def test_nothing_overflows_at_any_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                self._page.set_viewport_size({"width": width, "height": 900})
                self._page.wait_for_timeout(250)
                over = self._page.evaluate(
                    "() => document.documentElement.scrollWidth - window.innerWidth")
                self.assertLessEqual(over, 0, f"overflows at {width}px")
        self._page.set_viewport_size({"width": 1280, "height": 900})

    def test_the_page_is_silent(self):
        self._check_project(self.project)
        self._page.wait_for_timeout(800)
        self.assertEqual(self._errors, [], f"console errors: {self._errors}")
        self.assertEqual(self._failed, [], f"failed requests: {self._failed}")


if __name__ == "__main__":
    unittest.main()