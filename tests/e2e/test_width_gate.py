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

**The wide end, and what a ceiling cannot see (6.2d, 6.2e).** Everything above is
`scrollWidth - clientWidth <= 1` — the absence of a defect, which a page that
ignores its 2560 window also satisfies. `WideEndPlacementTests` adds what can be
measured instead: the content column is centred in its pane (as a gutter PAIR,
with a control that the pane is really wider), the detail measure did not grow,
the product name reads before the actions at 640 CSS px, and **6.2e's floor** —
a wider window never takes space away, the column keeps a floor share of its
pane, and the layout reaches both window edges. Each of the last three has a
mutation injected into the live page that the same probe reports as a violation,
so the floor cannot be green because the probe reads nothing.

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


# In the page. 6.2d: where the content column sits inside its pane, and where the
# topbar's four children sit inside the topbar's three tracks. Both are about
# POSITION, so both are measured as geometry and not as a class or a property.
#
# `gutter` is reported as a signed pair rather than a boolean: "is it centred"
# is true of a column that fills its pane, and it is also true of a column that
# never got to the wide end at all. The tests below require the pane to be
# genuinely wider than the column FIRST, so a fixture that stopped exercising
# the defect cannot go green.
GEOMETRY = r"""
() => {
  const box = (s) => { const e = document.querySelector(s); if (!e) return null;
    const r = e.getBoundingClientRect();
    return {x: r.x, w: r.width, right: r.right}; };
  const pane = box('.detail');
  const inner = box('.detail-inner') || box('.install-shell') ||
                box('.quality-center') || box('.settings-center') ||
                box('.overview-shell');
  const detailInner = box('.detail-inner');
  const paneEl = document.querySelector('.detail');
  const pcs = paneEl ? getComputedStyle(paneEl) : null;
  const t = document.querySelector('.topbar');
  const kids = t ? [...t.children].map((e) => {
    const r = e.getBoundingClientRect();
    return {cls: (e.className || '').split(' ')[0],
            x: Math.round(r.x), right: Math.round(r.right),
            col: getComputedStyle(e).gridColumnStart};
  }) : [];
  return {
    paneW: pane ? Math.round(pane.w) : null,
    paneX: pane ? pane.x : null,
    padL: pcs ? parseFloat(pcs.paddingLeft) : 0,
    padR: pcs ? parseFloat(pcs.paddingRight) : 0,
    colX: inner ? inner.x : null,
    colW: inner ? Math.round(inner.w) : null,
    detailInnerW: detailInner ? Math.round(detailInner.w) : null,
    innerWidth: window.innerWidth,
    // 6.2e: `.detail` starts AFTER the rail and the side list, so `paneX` is not
    // the left edge of the layout — the rail's own x is. Measured dead canvas is
    // read off these two, not off `paneX` (which was 436px on a 2560 window and
    // made "nothing is stranded on the left" fail for a correct tree).
    railX: box('.navigation-rail') ? box('.navigation-rail').x : null,
    railW: box('.navigation-rail') ? Math.round(box('.navigation-rail').w) : null,
    topbarCols: t ? getComputedStyle(t).gridTemplateColumns : null,
    kids: kids,
  };
}
"""


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: 6.2d's two claims are about where the "
    "column and the product name are painted, which no source contract can see",
)
class WideEndPlacementTests(unittest.TestCase):
    """6.2d — the two findings the 6.2c screenshots produced.

    (1) At 2560 the content column is 820px inside a 2124px pane and all of the
    surplus sat on the left, so a large monitor got a page that looks cut off.
    (2) At 640 CSS px — 200% zoom on a 1280 window, the width this file already
    emulates for the zoom sweep — the product name rendered to the RIGHT of the
    actions, because `.brand` was the one child of the topbar row with no
    placement and auto-placement resolves after every definite position.

    6.2e added the FLOOR to this class. (1) and (2) say the column went where it
    should; nothing said the wide end was *used*, because the sweep above is a
    ceiling and a ceiling cannot tell a page that uses 2560 from a page that
    ignores it. The three tests below are the measurable form of that: a wider
    window never takes space away, the column keeps a floor share of its pane,
    and the layout reaches both window edges.
    """

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-wide-")
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
        self._errors = []
        self._contexts = []

    def tearDown(self):
        # The contexts close BEFORE the driver stops. Closing them after
        # `sync_playwright().stop()` raises "Event loop is closed" from
        # tearDown and reports it as an error in a test that passed.
        for context in self._contexts:
            try:
                context.close()
            except Exception:
                pass
        self._browser.close()
        self._pw.stop()

    def _page(self, width, height=900, dpr=1):
        context = self._browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=dpr)
        self._contexts.append(context)
        page = context.new_page()
        page.on("console",
                lambda m: self._errors.append(m.text) if m.type == "error" else None)
        page.goto(self.server.url, wait_until="networkidle")
        page.wait_for_selector("#app", timeout=15000)
        return page

    def test_the_content_column_is_centred_in_its_pane_at_2560(self):
        """The defect, stated as the reader would see it: the empty canvas was
        all on one side. Asserted as a gutter PAIR, because a centred column in
        a pane the width of itself satisfies any boolean."""
        page = self._page(2560)
        page.wait_for_timeout(250)
        got = page.evaluate(GEOMETRY)
        self.assertIsNotNone(got["colW"], "no content column was found")
        # The control: if the pane were not genuinely wider than the column,
        # "centred" would be true of every layout including the broken one.
        self.assertGreater(got["paneW"], got["colW"] + 100,
                           "at 2560 the pane must be wider than its column or "
                           "this test cannot see the defect (pane %s, column %s)"
                           % (got["paneW"], got["colW"]))
        left = got["colX"] - (got["paneX"] + got["padL"])
        right = (got["paneX"] + got["paneW"] - got["padR"]) - (got["colX"] + got["colW"])
        self.assertLessEqual(abs(left - right), 2,
                             "the surplus is not shared: %dpx left, %dpx right"
                             % (round(left), round(right)))

    def test_the_column_is_centred_on_every_view_at_the_wide_end(self):
        page = self._page(2560)
        bad = []
        for view in VIEWS:
            self._goto(page, view)
            got = page.evaluate(GEOMETRY)
            if got["colW"] is None:
                bad.append("%s: no content column" % view)
                continue
            if got["paneW"] <= got["colW"] + 100:
                continue          # the pane fits; centring is a no-op there
            left = got["colX"] - (got["paneX"] + got["padL"])
            right = (got["paneX"] + got["paneW"] - got["padR"]) - (got["colX"] + got["colW"])
            if abs(left - right) > 2:
                bad.append("%s: %dpx left / %dpx right" % (view, round(left), round(right)))
        self.assertEqual(bad, [], "content column not centred at 2560: " + "; ".join(bad))

    def test_the_measure_did_not_move(self):
        """The decision 6.2d made was to CENTRE the column, not to widen it —
        so this is the assertion that keeps the other answer from creeping back
        in as a kindness. `.detail-inner` is `max-width: 82ch`; a 900px+ column
        at 2560 would be a prose measure nobody chose."""
        page = self._page(2560)
        self._goto(page, "Library")
        got = page.evaluate(GEOMETRY)
        # `.detail-inner` specifically: the Overview's own shell is a WIDER
        # 1180px column by design and is already centred, so measuring "the
        # column" here would report that number and say nothing about the
        # measure 6.2d decided not to touch.
        self.assertIsNotNone(got["detailInnerW"], "the Library detail column was not found")
        self.assertLessEqual(got["detailInnerW"], 860,
                             "the detail column grew past its measure (%dpx): "
                             "6.2d centred it on purpose"
                             % got["detailInnerW"])

    # --- 6.2e: the FLOOR. Everything above is a ceiling. ------------------
    #
    # The sweep this file was built on asserts `scrollWidth - clientWidth <= 1`,
    # which is the absence of a defect. It cannot tell a layout that USES a
    # 2560 window from one that draws an 820px column on the left of it and
    # leaves 1256px of nothing — 6.2d's finding, and the reason "wide is clean"
    # was not a claim anyone could check. These three are what is measurable:
    #
    #   FLOOR  a wider window never takes space away. The same view at 2560 and
    #          1920 must not be NARROWER than it is at 1440, the primary laptop
    #          width. This is the counterpart of the overflow ceiling: overflow
    #          is "the window is too small for the content", this is "the window
    #          grew and the content shrank", and only the second one is the wide
    #          end being wasted.
    #   SHARE  where the pane IS wider than its column, the column must keep a
    #          floor share of the pane's own content box, so the surplus cannot
    #          be parked beside a ribbon.
    #   EDGE   the layout reaches BOTH window edges: the rail starts at 0 and
    #          the pane ends at the last pixel. A pane that stopped 300px short
    #          of the right edge would satisfy every assertion above.
    #
    # The floor is 30% and is deliberately loose: measured on this fixture at
    # 2560 the share runs 40.4% (Library, Profiles, Workspaces, Recovery) to
    # 49.0% (Overview), so 30 leaves ten points of slack for a font-size or
    # padding change. It is there to catch a COLLAPSE, not to police a design.

    FLOOR = 0.30

    def _columns_at(self, page, width):
        """{view: GEOMETRY} at one window width, every view, in rail order."""
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_timeout(150)
        out = {}
        for view in VIEWS:
            self._goto(page, view)
            out[view] = page.evaluate(GEOMETRY)
        return out

    def test_a_wider_window_never_takes_space_away(self):
        """6.2e's floor. The gate this file already had is a ceiling: it says a
        2560 window does not overflow, which is also true of a page that ignores
        it. This says the content got at least as big when the window did —
        measured against 1440, the width the user actually has."""
        page = self._page(2560)
        wide = self._columns_at(page, 2560)
        mid = self._columns_at(page, 1920)
        base = self._columns_at(page, 1440)
        bad = []
        for view in VIEWS:
            for width, got in ((1920, mid[view]), (2560, wide[view])):
                col, ref = got["colW"], base[view]["colW"]
                if col is None or ref is None:
                    bad.append("%s @%d: no content column" % (view, width))
                elif col < ref - 1:
                    bad.append("%s @%d: column %dpx, narrower than the %dpx it has "
                               "at 1440" % (view, width, col, ref))
        self.assertEqual(bad, [], "the wide end gave space away: " + "; ".join(bad))

    def test_the_column_keeps_a_floor_share_of_its_pane_at_2560(self):
        """The share floor, with the control that makes it mean something: a
        column that FILLS its pane has a share of 1 and has stranded nothing, so
        such a view is skipped rather than being satisfied by it — and the count
        of views that were actually checked is asserted, so the floor cannot go
        quiet by every view falling into the skip."""
        page = self._page(2560)
        bad, checked = [], []
        for view in VIEWS:
            self._goto(page, view)
            g = page.evaluate(GEOMETRY)
            if g["colW"] is None:
                bad.append("%s: no content column" % view)
                continue
            content = g["paneW"] - g["padL"] - g["padR"]
            if content <= g["colW"] + 100:
                continue          # the pane fits: there is no surplus to strand
            share = g["colW"] / float(content)
            checked.append("%s %d/%d=%.0f%%" % (view, g["colW"], content, share * 100))
            if share < self.FLOOR:
                bad.append("%s: column is %.0f%% of a %dpx pane (floor %.0f%%)" % (
                    view, share * 100, content, self.FLOOR * 100))
        self.assertEqual(bad, [], "the column collapsed inside its pane — " + "; ".join(bad))
        self.assertGreaterEqual(len(checked), len(VIEWS) - 1,
                                "the share floor never ran: %r" % (checked,))

    def test_the_layout_reaches_both_window_edges_at_2560(self):
        """The claim the share floor cannot make on its own: nothing is parked
        beside the content. The RAIL starts at 0 and the pane ends at the last
        pixel, so 2560 has no dead strip on either side.

        The left edge is the rail's, not the pane's: `.detail` legitimately begins
        after a 56px rail and a 380px side list, and measuring the pane there
        reported 436px of "unused" canvas on a correct tree — the same class of
        probe error as 6.1b's font shorthand, and the reason this note exists."""
        page = self._page(2560)
        bad = []
        for view in VIEWS:
            self._goto(page, view)
            g = page.evaluate(GEOMETRY)
            if g["paneX"] is None or g["railX"] is None:
                bad.append("%s: no rail or detail pane" % view)
                continue
            left = g["railX"]
            right = g["innerWidth"] - (g["paneX"] + g["paneW"])
            if left > 1 or right > 1:
                bad.append("%s: %dpx unused on the left, %dpx on the right"
                           % (view, round(left), round(right)))
        self.assertEqual(bad, [], "2560 is not filled edge to edge: " + "; ".join(bad))

    def test_the_usage_probe_can_fail(self):
        """Without this the three tests above are green noise: a probe that
        cannot report a defect reports nothing. Both mutations are injected into
        the LIVE page, and both are plausible accidents — a `max-width` typo on
        the column, a stray margin on the pane."""
        page = self._page(2560)
        self._goto(page, "Library")
        before = page.evaluate(GEOMETRY)
        self.assertIsNotNone(before["colW"], "the Library detail column was not found")

        page.add_style_tag(content=".detail-inner { max-width: 120px !important; }")
        page.wait_for_timeout(150)
        shrunk = page.evaluate(GEOMETRY)
        pane_content = shrunk["paneW"] - shrunk["padL"] - shrunk["padR"]
        # What `test_a_wider_window_never_takes_space_away` compares, and what
        # `test_the_column_keeps_a_floor_share_of_its_pane_at_2560` measures.
        self.assertLess(shrunk["colW"], before["colW"] - 1,
                        "the column did not shrink: the usage probe is measuring "
                        "something that is not the column")
        share = shrunk["colW"] / float(pane_content)
        self.assertLess(share, self.FLOOR,
                        "a %dpx column in a %dpx pane is %.0f%% of it; the floor must "
                        "report that as a violation"
                        % (shrunk["colW"], pane_content, share * 100))

        page.add_style_tag(content=".detail { margin-right: 300px !important; }")
        page.wait_for_timeout(150)
        stranded = page.evaluate(GEOMETRY)
        # What `test_the_layout_reaches_both_window_edges_at_2560` measures.
        dead = stranded["innerWidth"] - (stranded["paneX"] + stranded["paneW"])
        self.assertGreater(dead, 1,
                           "a 300px right margin left no dead strip (measured %dpx): "
                           "the edge probe cannot see the defect it was written for"
                           % round(dead))

    def test_the_product_name_reads_before_the_actions_at_640(self):
        """200% zoom on a 1280 window. The defect was the name landing in
        column 3, right of the actions, because it was the only unplaced child
        and auto-placement resolves after every definite position."""
        page = self._page(640, 900, dpr=2)
        page.wait_for_timeout(250)
        got = page.evaluate(GEOMETRY)
        self.assertEqual(got["innerWidth"], 640)
        by = {k["cls"]: k for k in got["kids"]}
        for name in ("btn", "brand", "topbar-actions"):
            self.assertIn(name, by, "topbar child %r not found in %s" % (name, got["kids"]))
        # The control: the reading order is only a claim if the three really
        # are in one row and inside the window.
        self.assertEqual(by["brand"]["col"], "2")
        self.assertEqual(by["topbar-actions"]["col"], "3")
        self.assertEqual(by["btn"]["col"], "1")
        # Reading order as GEOMETRY, not as DOM order — DOM order was already
        # correct, which is why every source-text check of this passed while the
        # name painted to the right of the actions.
        self.assertGreater(by["brand"]["x"], by["btn"]["right"],
                           "the product name does not start after the drawer trigger")
        self.assertLessEqual(by["brand"]["right"], by["topbar-actions"]["x"],
                             "the product name overlaps the actions")
        self.assertGreater(by["topbar-actions"]["x"], by["brand"]["x"],
                           "the actions still render left of the product name")
        self.assertLessEqual(by["topbar-actions"]["right"], 640)

    def test_no_console_error_on_either_surface(self):
        wide = self._page(2560)
        narrow = self._page(640, 900, dpr=2)
        self._goto(wide, "Library")
        self._goto(narrow, "Library")
        self.assertEqual(self._errors, [])

    @staticmethod
    def _goto(page, view):
        """Switch view the way a reader does. Below 760 CSS px the rail is an
        off-canvas drawer, so at 640 the button is not on screen until it opens.
        """
        rail = page.query_selector('.navigation-rail[data-drawer="open"]')
        if rail is None and page.is_visible(".nav-drawer-trigger"):
            page.click(".nav-drawer-trigger")
            page.wait_for_timeout(200)
        page.click('.navigation-rail button[data-tip="%s"]' % view)
        page.wait_for_selector(
            '.navigation-rail button[data-tip="%s"][aria-current="page"]' % view,
            timeout=10000)
        page.wait_for_timeout(180)


if __name__ == "__main__":
    unittest.main()