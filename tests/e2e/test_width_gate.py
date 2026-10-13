"""6.2c e2e — the laptop widths and 200% zoom, as a gate instead of a probe.

**Why this file exists.** 6.2a swept 1100/1280/1440/1920/2560 plus 640/960/1280
and wrote the answer into `.redesign/STATE.md`: *0 document horizontal overflow on
all 8 views*. 6.2b re-measured the search placeholder at those widths and found
the inherited `[?]` false. Both were PROBES — scripts in `.redesign/` that
nothing runs. A sweep nobody executes is a claim, and this repository has
already shipped three of them. So the sweep lives here now, where `verify.sh`
runs it one process per module.

**What is asserted, and what would still pass if the product broke.**

Per view per width: `documentElement.scrollWidth - clientWidth <= 1`. That is
the definition of horizontal overflow and it is the only claim. A view that
renders nothing at all would satisfy it, so `test_the_probe_can_fail` injects a
4000px box and asserts the same probe REPORTS it — if the probe were broken, the
other 39 measurements would be green noise.

`test_the_sweep_reaches_every_view` walks all eight and asserts the nav button
for each one reaches `aria-current="page"`, so "0 overflow on 8 views" cannot be
earned by quietly measuring the same view eight times.

**200% zoom, which nothing had ever measured.** Browser zoom is not a viewport
setting: the window keeps its physical size and the CSS viewport halves. There
is no zoom API in Playwright, so it is reproduced by what it *is* — the CSS
viewport at `window / 2` with `device_scale_factor=2`, which is the same layout
the UA computes and the same physical pixels a screenshot would have.
`test_the_zoom_context_is_actually_zoomed` asserts `clientWidth == window / 2`
and `devicePixelRatio == 2` in that context, because a gate that silently ran at
100% would report the 100% result under a 200% name.

At 200% the 1280 window is 640 CSS px, which is **inside the `<760px` drawer
band** — a path no capture had walked. That is the point of measuring it here
rather than claiming 1100's answer holds.

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

# The eight destinations in the rail. Trash is reached from Library, not the
# rail, and 6.2a's sweep counted eight — this keeps that count honest.
VIEWS = ("Overview", "Library", "Profiles", "Workspaces",
         "Install", "Recovery", "Quality", "Settings")

# The laptop-first band: a shrunk laptop window through a large external monitor.
WINDOWS = (1100, 1280, 1440, 1920, 2560)

# The same windows at 200% browser zoom. The CSS viewport is half of each.
ZOOM_WINDOWS = (1100, 1280, 1440, 1920)

# In the page. Reports the DOCUMENT's horizontal overflow and, when there is
# any, which element produced it — a bare boolean sends the reader to the
# debugger with no suspect attached.
OVERFLOW = r"""
() => {
  const de = document.documentElement;
  const over = de.scrollWidth - de.clientWidth;
  const offenders = [];
  if (over > 1) {
    const limit = de.clientWidth;
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      if (r.right <= limit + 1 && r.left >= -1) continue;
      // A closed drawer is `position: fixed` and parked off-canvas; it is
      // meant to be outside the viewport and it never overflows the document.
      const cs = getComputedStyle(el);
      if (cs.position === 'fixed' && r.left < -1) continue;
      if (cs.visibility === 'hidden' || cs.display === 'none') continue;
      offenders.push({
        sel: el.tagName.toLowerCase() +
             (el.id ? '#' + el.id : '') +
             (el.className && typeof el.className === 'string'
               ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''),
        left: Math.round(r.left), right: Math.round(r.right),
      });
      if (offenders.length >= 6) break;
    }
  }
  return {clientWidth: de.clientWidth, scrollWidth: de.scrollWidth,
          over: over, offenders: offenders};
}
"""

# In the page. The search field's usable TEXT width, and the width the longest
# placeholder in the product actually needs at this font.
#
# `fontSize` and `fontFamily` are set SEPARATELY on purpose: assigning the
# `font` shorthand makes the probe silently fall back to the 16px serif default
# whenever the shorthand cannot be re-serialised, and every "needed" width then
# comes out ~40% too large. That mistake is recorded in MAP.md.
SEARCH_FIELD = r"""
() => {
  const wrap = document.querySelector('.searchwrap');
  const input = document.querySelector('.searchwrap input');
  if (!wrap || !input) return null;
  const cs = getComputedStyle(input);
  const probe = document.createElement('span');
  probe.style.position = 'absolute';
  probe.style.visibility = 'hidden';
  probe.style.whiteSpace = 'nowrap';
  probe.style.left = '-9999px';
  probe.style.fontSize = cs.fontSize;
  probe.style.fontFamily = cs.fontFamily;
  probe.style.fontWeight = cs.fontWeight;
  probe.style.letterSpacing = cs.letterSpacing;
  probe.textContent = input.placeholder;
  document.body.appendChild(probe);
  const needed = probe.getBoundingClientRect().width;
  probe.remove();
  return {
    placeholder: input.placeholder,
    needed: Math.round(needed),
    has: Math.round(input.clientWidth -
                     parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)),
    wrapWidth: Math.round(wrap.getBoundingClientRect().width),
  };
}
"""

ZOOM_STATE = r"""
() => ({
  clientWidth: document.documentElement.clientWidth,
  innerWidth: window.innerWidth,
  dpr: window.devicePixelRatio,
})
"""


def _has_chromium():
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


def _fixtures(store):
    """Enough library to make the sweep mean something.

    A view with nothing in it cannot overflow, so an empty fixture library
    would make every measurement below vacuously green. The long name and the
    long description are the Library table's worst case at 1100px and are the
    reason this fixture exists rather than a generic one.
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
        "sql-query-explainer",
        "test-fixture-author",
        "changelog-editor",
        "performance-profiler",
        # Worst case on purpose: 44 characters, and a description long enough
        # to fill a cell three times over.
        "security-posture-review-for-multi-tenant-saas",
        "documentation-consistency-checker-with-a-very-long-name",
    ]
    for i, name in enumerate(names):
        store.create(
            name,
            ("Fixture %d. " % (i + 1)) * (6 if i % 3 else 2) +
            "A description long enough that the Library table has to decide what "
            "to truncate, which is the decision a width sweep exists to make "
            "visible rather than to pass.",
            body="# %s\n\nFixture body for the width gate.\n" % name)


class _SweepMixin(object):
    """Navigation and measurement, shared by the 100% and 200% classes."""

    def _goto(self, view):
        """Switch view the way a reader does, drawer included.

        Below 760 CSS px the rail is a fixed off-canvas drawer, so at 200% zoom
        the buttons this clicks are not on screen until the drawer is opened.
        Clicking them anyway (or reaching into the app) would measure a state
        no user can reach.
        """
        rail = self._page.query_selector('.navigation-rail[data-drawer="open"]')
        if rail is None and self._page.is_visible(".nav-drawer-trigger"):
            self._page.click(".nav-drawer-trigger")
            self._page.wait_for_timeout(200)
        self._page.click('.navigation-rail button[data-tip="%s"]' % view)
        self._page.wait_for_selector(
            '.navigation-rail button[data-tip="%s"][aria-current="page"]' % view,
            timeout=10000)
        # A view switch fetches and paints; the band below it is measured after
        # layout settles so a half-painted row cannot be called clean.
        self._page.wait_for_timeout(180)

    def _overflow(self):
        return self._page.evaluate(OVERFLOW)

    def _sweep(self, widths, views=VIEWS):
        bad = []
        for width in widths:
            self._page.set_viewport_size({"width": width, "height": 900})
            self._page.wait_for_timeout(120)
            for view in views:
                self._goto(view)
                got = self._overflow()
                if got["over"] > 1:
                    bad.append("%s @%d: +%dpx %s"
                               % (view, width, got["over"], got["offenders"]))
        self.assertEqual(bad, [], "horizontal overflow: " + "; ".join(bad))


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: this measures layout at widths and zoom "
    "levels that no source contract can stand in for",
)
class LaptopWidthTests(_SweepMixin, unittest.TestCase):
    """1100 → 2560, the widths a laptop window and a desktop actually reach."""

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-width-")
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
        self._page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_selector("#app", timeout=15000)

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    # -- the sweep, one test per width so a failure names its width ----------

    def test_1100_the_shrunk_laptop_window(self):
        """The one narrow width this pass is about: a real laptop window the
        user dragged smaller. Below 900 the stat pill and the command hint are
        dropped to keep the field useful, so this is where that band earns its
        keep."""
        self._sweep((1100,))

    def test_1280(self):
        self._sweep((1280,))

    def test_1440(self):
        self._sweep((1440,))

    def test_1920(self):
        self._sweep((1920,))

    def test_2560_the_large_external_monitor(self):
        self._sweep((2560,))

    # -- the gate's own honesty ---------------------------------------------

    def test_the_probe_can_fail(self):
        """The control for the other five.

        Every sweep test asserts an overflow of 0. A probe that always returns
        0 — a selector that stopped matching, a page that stopped rendering —
        would make all of them pass forever. So break the page on purpose and
        assert the probe says so.
        """
        self._page.evaluate(
            """() => {
                 const b = document.createElement('div');
                 b.id = 'width-gate-canary';
                 b.style.cssText = 'width:4000px;height:8px;background:red';
                 document.querySelector('.layout').appendChild(b);
               }""")
        self._page.wait_for_timeout(150)
        got = self._overflow()
        self.assertGreater(got["over"], 1,
                           "the probe reported no overflow for a 4000px box: "
                           "every other assertion in this file is measuring "
                           "nothing")
        self.assertTrue(got["offenders"],
                        "overflow was reported without naming the element")

    def test_the_sweep_reaches_every_view(self):
        """Eight measurements of one view are not eight views. Assert the nav
        really landed on the destination named."""
        seen = []
        for view in VIEWS:
            self._goto(view)
            seen.append(self._page.eval_on_selector(
                '.navigation-rail button[aria-current="page"]',
                "el => el.dataset.tip"))
        self.assertEqual(sorted(seen), sorted(VIEWS))

    def test_the_longest_placeholder_is_not_truncated(self):
        """6.2b's measurement as a gate.

        The Install view carries the longest placeholder in the product,
        "Search registry sources…". It needs more width than the field has to
        give below ~1000px, which the `<760px` band owns; at 1100 and above it
        must fit in full, at every width including 2560.
        """
        self._page.set_viewport_size({"width": 1100, "height": 900})
        self._goto("Install")
        self.assertIsNotNone(self._page.query_selector(".searchwrap input"),
                             "Install must carry the search field")
        bad = []
        for width in WINDOWS:
            self._page.set_viewport_size({"width": width, "height": 900})
            self._page.wait_for_timeout(120)
            got = self._page.evaluate(SEARCH_FIELD)
            if got["has"] < got["needed"]:
                bad.append("%d: needs %d, has %d (%r)"
                           % (width, got["needed"], got["has"], got["placeholder"]))
        self.assertEqual(bad, [], "truncated placeholder: " + "; ".join(bad))

    def test_the_search_field_keeps_its_declared_cap(self):
        """The decision 6.2b deliberately left open, made here.

        `.searchwrap` is `flex: 1` with `max-width: 420px`, so it is 420px at
        2560 exactly as it is at 1100. Measured, that is 17% of a 2560 topbar
        with the remainder collected between the field and the right-aligned
        actions — which is what GitHub and Linear do, and a search field that
        stretches with the window stops being a fixed affordance and starts
        reading as a stretched layout. So the cap STAYS, and this test is what
        stops the next iteration "fixing" it into fluid without a decision.
        """
        self._goto("Install")
        widths = []
        for width in WINDOWS:
            self._page.set_viewport_size({"width": width, "height": 900})
            self._page.wait_for_timeout(120)
            got = self._page.evaluate(SEARCH_FIELD)
            widths.append((width, got["wrapWidth"]))
        over = [w for w in widths if w[1] > 421]
        self.assertEqual(over, [],
                         "the search field grew past its declared 420px cap: "
                         "%s — if the cap is being revisited, that is a design "
                         "decision with a new commit, not a drive-by" % (over,))

    def test_no_console_error_at_any_width(self):
        for width in WINDOWS:
            self._page.set_viewport_size({"width": width, "height": 900})
            self._page.wait_for_timeout(100)
        self._goto("Library")
        self.assertEqual(self._errors, [])


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: 200% zoom halves the CSS viewport, which "
    "no source contract can stand in for",
)
class Zoom200Tests(_SweepMixin, unittest.TestCase):
    """200% browser zoom — never measured before this file.

    Same server, same fixtures, same eight views. The only difference is the
    viewport: `window / 2` CSS px at `device_scale_factor: 2`, which is what
    the UA computes when a reader zooms, and what a screenshot at that window
    size would show.
    """

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-zoom-")
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
        # device_scale_factor 2 is the other half of the emulation: the halved
        # viewport gives the CSS pixels zoom produces, the doubled factor gives
        # back the physical pixels the window still has.
        self._context = self._browser.new_context(
            viewport={"width": 1280 // 2, "height": 900 // 2},
            device_scale_factor=2)
        self._page = self._context.new_page()
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_selector("#app", timeout=15000)

    def tearDown(self):
        self._context.close()
        self._browser.close()
        self._pw.stop()

    def _at(self, window_width):
        self._page.set_viewport_size({"width": window_width // 2,
                                      "height": 900 // 2})
        self._page.wait_for_timeout(120)

    def test_the_zoom_context_is_actually_zoomed(self):
        """The control. A context that quietly ran at 100% would publish the
        100% answer under a 200% name, which is the failure this repository
        keeps recording in a different hat."""
        self._at(1280)
        got = self._page.evaluate(ZOOM_STATE)
        self.assertEqual(got["innerWidth"], 640)
        self.assertEqual(got["clientWidth"], 640)
        self.assertEqual(got["dpr"], 2.0)

    def test_1100_window_at_200_percent(self):
        """550 CSS px — well inside the drawer band."""
        self._at(1100)
        self._sweep((550,))

    def test_1280_window_at_200_percent(self):
        """640 CSS px. This is the number that had never been measured."""
        self._at(1280)
        self._sweep((640,))

    def test_1440_window_at_200_percent(self):
        """720 CSS px — the widest the drawer band allows before it ends at 760."""
        self._at(1440)
        self._sweep((720,))

    def test_1920_window_at_200_percent(self):
        """960 CSS px — back above the band, still inside the 900px degradation."""
        self._at(1920)
        self._sweep((960,))

    def test_the_probe_can_fail_at_200_percent(self):
        """The 100% control again, on the path where a claim is most likely to
        be hollow. The drawer band is a different layout with a fixed rail, so
        it deserves its own proof that the same probe still sees an overflow
        there — and not a pass earned by measuring a page that has collapsed
        into a fixed overlay."""
        self._at(1280)
        self._page.evaluate(
            """() => {
                 const b = document.createElement('div');
                 b.id = 'zoom-gate-canary';
                 b.style.cssText = 'width:4000px;height:8px;background:red';
                 document.querySelector('.layout').appendChild(b);
               }""")
        self._page.wait_for_timeout(150)
        self.assertGreater(self._overflow()["over"], 1,
                           "no overflow reported at 640 CSS px for a 4000px box")

    def test_the_drawer_is_the_navigation_at_200_percent(self):
        """At 640 CSS px the rail is a fixed drawer, so the destination buttons
        are off-canvas until it is opened. Asserting that is asserting the
        reachability the sweep above depends on — without it those eight
        measurements were made through a door the reader does not have."""
        self._at(1280)
        self.assertIsNone(
            self._page.query_selector('.navigation-rail[data-drawer="open"]'),
            "the rail should be a closed drawer at 640 CSS px")
        self.assertTrue(self._page.is_visible(".nav-drawer-trigger"))
        self._page.click(".nav-drawer-trigger")
        self._page.wait_for_timeout(220)
        self.assertIsNotNone(
            self._page.query_selector('.navigation-rail[data-drawer="open"]'))
        self._page.click('.navigation-rail button[data-tip="Quality"]')
        self._page.wait_for_timeout(220)
        self.assertEqual(self._overflow()["over"] <= 1, True)

    def test_no_console_error_at_200_percent(self):
        self._at(1280)
        for view in VIEWS:
            self._goto(view)
        self.assertEqual(self._errors, [])


if __name__ == "__main__":
    unittest.main()