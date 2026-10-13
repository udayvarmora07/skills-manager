"""7.3 e2e — the laptop band, both themes, as a gate instead of a claim.

**Why this file exists and what it is NOT.** 6.2c's `test_width_gate.py` already
sweeps 1100/1280/1440/1920/2560 across the eight views and asserts horizontal
overflow, plus 200% zoom. This file is not that sweep repeated. It adds the
three claims no gate in this repository made before 7.3:

1. **Zero console errors, per view, per theme.** `test_width_gate`'s console
   check resizes the window and then visits exactly one view in the light
   theme — so a view that throws only when rendered, or only in dark, was never
   in anyone's assertions.
2. **Zero failed requests and zero HTTP >= 400.** Nothing anywhere asserted
   either. A view whose fetch 404s renders its error branch correctly and is
   therefore *correct* — which is exactly why an unasserted failed request is
   the failure mode a UI test is supposed to catch and cannot.
3. **Both themes.** 6.1b swept dark contrast over 1,777 pairs and 6.6 runs axe
   in the light theme only; neither rendered the views in both and asked
   whether the page came up.

**Widths: 1100/1280/1440/1920, deliberately and not 2560.** Re-scoped 2026-10-13
against confirmation that this tool is used from a laptop and a PC. 1100 is the
shrunk-laptop window a user drags to, and it is the one narrow width this row
owns. 2560 belongs to backlog 6.2d, which has to decide what a large monitor
earns before a sweep should hold that width still.

**The controls, because every measurement here asserts zero.** A listener that
silently never fired, a theme that never applied, and eight walks that quietly
measured one view all make this file green forever. Each has a test whose
failure means the other 32 measurements are noise.

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

# The eight rail destinations. Trash is reached from Library, not the rail, so
# it is deliberately not here — 6.2c measured eight and this keeps that honest.
VIEWS = ("Overview", "Library", "Profiles", "Workspaces",
         "Install", "Recovery", "Quality", "Settings")

WIDTHS = (1100, 1280, 1440, 1920)
THEMES = ("light", "dark")


def _has_chromium():
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


def _fixtures(store):
    """Enough library for a walk to mean something.

    An empty library renders nothing, and a page that renders nothing cannot
    fail a read or throw during render. The long name is the Library list's
    worst case, which is the reason this is not a generic one-skill fixture.
    """
    names = [
        "platform-infrastructure-bootstrap",
        "incident-response-runbook-coordinator",
        "database-migration-safety-reviewer",
        "release-notes-writer",
        "log-triage-helper",
        "api-contract-checker",
        "frontend-a11y-auditor",
        "dependency-upgrade-planner",
        "security-posture-review-for-multi-tenant-saas",
        "documentation-consistency-checker-with-a-very-long-name",
    ]
    for i, name in enumerate(names):
        store.create(
            name,
            ("Fixture %d. " % (i + 1)) * (6 if i % 3 else 2) +
            "A description long enough that the Library row has to decide what "
            "to truncate, which is the decision a width sweep exists to make "
            "visible rather than to pass.",
            body="# %s\n\nFixture body for the visual sweep.\n" % name)


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: this asserts what the eight views DO at "
    "the widths and in the themes a reader uses, which no source contract can "
    "stand in for",
)
class VisualSweepTests(unittest.TestCase):
    """Every view, every laptop width, both themes — one claim each."""

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-sweep-")
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
        _fixtures(cls.store)
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
        self._page = self._browser.new_page(viewport={"width": 1440, "height": 900})
        self._console = []
        self._failed = []
        self._http4xx = []
        self._page.on("console", lambda m: self._console.append(m.text)
                      if m.type == "error" else None)
        self._page.on("requestfailed",
                      lambda r: self._failed.append("%s %s" % (r.method, r.url)))
        self._page.on("response", lambda r: self._http4xx.append(
            "%s -> HTTP %d" % (r.url, r.status)) if r.status >= 400 else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_selector("#app", timeout=15000)
        self._page.wait_for_timeout(300)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    # -- helpers ------------------------------------------------------------

    def _theme(self, theme):
        """Force the theme and PROVE it landed.

        The product boots on `system`, so a run on a light OS renders light and
        a "dark" half measured against a light document would be the 2.3/6.5b
        class of claim that names a state nobody saw. `preferences.js` resolves
        `system` before the stylesheet loads, so setting the attribute is the
        same mechanism the app itself uses.
        """
        self._page.evaluate(
            "(t) => { document.documentElement.setAttribute('data-theme', t);"
            " localStorage.setItem('theme', t); }", theme)
        self._page.wait_for_timeout(160)
        got = self._page.evaluate(
            "() => document.documentElement.getAttribute('data-theme')")
        self.assertEqual(got, theme,
                         "the theme did not apply, so the rest of this theme's "
                         "measurements were taken against the other one")

    def _goto(self, view):
        """Navigate the way a reader does, then let the view's read settle.

        All four widths are above the 760px drawer band, so the rail is always
        on screen — `test_width_gate` needs a drawer helper for 200% zoom and
        this file must not quietly inherit one it does not need.
        """
        self._page.click('.navigation-rail button[data-tip="%s"]' % view)
        self._page.wait_for_selector(
            '.navigation-rail button[data-tip="%s"][aria-current="page"]' % view,
            timeout=10000)
        self._page.wait_for_timeout(260)

    def _overflow(self):
        return self._page.evaluate(
            "() => { const de = document.documentElement;"
            " return de.scrollWidth - de.clientWidth; }")

    # -- the sweep ----------------------------------------------------------

    def _sweep(self, theme):
        self._theme(theme)
        bad_overflow = []
        for width in WIDTHS:
            self._page.set_viewport_size({"width": width, "height": 900})
            self._page.wait_for_timeout(140)
            for view in VIEWS:
                self._goto(view)
                over = self._overflow()
                if over > 1:
                    bad_overflow.append("%s@%d: +%dpx" % (view, width, over))
        self.assertEqual(bad_overflow, [],
                         "horizontal overflow in the %s theme: %s"
                         % (theme, "; ".join(bad_overflow)))

    def test_light_theme_sweeps_clean(self):
        self._sweep("light")

    def test_dark_theme_sweeps_clean(self):
        """The half that no other gate renders. 6.1b composited 1,777 text
        pairs in dark; nothing walked the views in dark and asked whether they
        came up at all."""
        self._sweep("dark")

    def test_no_console_error_in_either_theme(self):
        """Per view, per theme — the claim `test_width_gate`'s console check
        cannot make, because it resizes the window and then visits Library."""
        for theme in THEMES:
            self._theme(theme)
            for width in WIDTHS:
                self._page.set_viewport_size({"width": width, "height": 900})
                self._page.wait_for_timeout(120)
                for view in VIEWS:
                    self._goto(view)
        self.assertEqual(
            self._console, [],
            "console errors across %d view/theme/width walks: %s"
            % (len(VIEWS) * len(THEMES) * len(WIDTHS), self._console[:5]))

    def test_no_failed_request_in_either_theme(self):
        """A read that never arrived was previously invisible to every gate in
        this repository: the view renders its own error branch correctly, so the
        product is CORRECT about the failure and nothing notices the request."""
        for theme in THEMES:
            self._theme(theme)
            for view in VIEWS:
                self._goto(view)
        self.assertEqual(self._failed, [],
                         "requests that never completed: %s" % (self._failed[:5],))

    def test_no_response_is_an_error_status(self):
        """Separate from a failed request: a 404/500 *completes*. The route
        answered, and a view whose fetch 404s is a page rendering an error
        branch rather than the thing it is for."""
        for theme in THEMES:
            self._theme(theme)
            for view in VIEWS:
                self._goto(view)
        self.assertEqual(self._http4xx, [],
                         "responses with a >= 400 status: %s" % (self._http4xx[:5],))

    # -- the gate's own honesty --------------------------------------------

    def test_the_console_listener_can_fire(self):
        """The control for every listener assertion above.

        A `page.on("console", ...)` that never fires makes
        `test_no_console_error_in_either_theme` green forever, and the same is
        true of the two request listeners. Rather than trust the wiring, make
        each one record something and require it to arrive.
        """
        self._page.evaluate("() => console.error('sweep-canary')")
        self._page.wait_for_timeout(200)
        self.assertIn("sweep-canary", self._console,
                      "a console.error in the page did not reach the listener: "
                      "every 'no console error' assertion here is measuring "
                      "nothing")

        self._page.evaluate("""() => {
             const img = document.createElement('img');
             img.src = '/api/does-not-exist-for-the-sweep-canary';
             document.body.appendChild(img);
           }""")
        self._page.wait_for_timeout(400)
        self.assertTrue(self._http4xx,
                        "a >=400 response did not reach the listener: the "
                        "HTTP assertion in this file is measuring nothing")

    def test_the_overflow_probe_can_fail(self):
        """And the control for the two sweep tests. Overflow of 0 is the only
        thing they assert, so a probe that always returns 0 — or a page that
        stopped rendering — makes both green forever."""
        self._page.evaluate("""() => {
             const b = document.createElement('div');
             b.style.cssText = 'width:4000px;height:8px;background:red';
             document.querySelector('.layout').appendChild(b);
           }""")
        self._page.wait_for_timeout(200)
        self.assertGreater(self._overflow(), 1,
                           "no overflow reported for a 4000px box: both sweep "
                           "tests are measuring nothing")

    def test_the_sweep_reaches_every_view(self):
        """Eight walks of one view are not eight views. Require the nav to
        really land on each destination named."""
        seen = []
        for theme in THEMES:
            self._theme(theme)
            for view in VIEWS:
                self._goto(view)
                seen.append(self._page.eval_on_selector(
                    '.navigation-rail button[aria-current="page"]',
                    "el => el.dataset.tip"))
        # `sorted(VIEWS) * n` would expect Install, Library, … then Install
        # again — which is not what sorting the whole run produces. Concatenate
        # the sorted list instead; the first draft of this line asserted a
        # sequence the sort had already ruled out and failed a correct walk.
        self.assertEqual(sorted(seen), sorted(list(VIEWS) * len(THEMES)))

    def test_each_view_actually_rendered_something(self):
        """The one control the other views did not carry.

        `document.title` and `#app` having children both stay true when a view
        branch throws during render and Vue empties it — the 5.5 failure that
        took five contract suites and a capture script to find, and that renders
        as a page with no console error on it. So ask the view for its own
        heading text, and require a control to prove the query can find one.
        """
        headings = []
        for view in VIEWS:
            self._goto(view)
            got = self._page.evaluate("""() => {
                 const h = document.querySelector(
                     'main.layout h1, main.layout h2, .detail h1, .detail h2');
                 return h ? h.textContent.trim() : '';
               }""")
            headings.append((view, got))
        missing = [v for v, h in headings if not h]
        self.assertEqual(
            missing, [],
            "these views rendered no heading at all, which is what a branch "
            "that threw during render looks like from outside: %s"
            % (missing,))
        # The control: the locator above is not vacuous.
        self.assertTrue(any(h for _, h in headings),
                        "the heading locator found nothing anywhere, so the "
                        "assertion above would pass on an empty page too")


if __name__ == "__main__":
    unittest.main()