"""6.1b e2e — the RENDERED dark pass, as two things a source scan cannot do.

6.1 slice A proved no colour in the cascade sits outside the token layer.  That
is a claim about the stylesheet.  Everything here is a claim about the colours
a reader actually gets, measured in the browser on every view in dark mode:

  1. `test_every_views_text_passes_aa_in_dark` walks every element that paints
     visible text, composites its `color` against the nearest ancestor
     background that is not transparent, and fails anything under WCAG 2.2 AA
     (4.5:1 body text, 3:1 at/above 24px).  The token layer makes this
     automatic; the sweep is what proves it rather than assuming it.

  2. `test_a_grid_slot_with_nothing_in_it_is_not_painted` is the defect the
     sweep is structurally blind to.  `.overview-metrics` drew its 1px cell
     hairlines by putting `background: var(--border)` on the *container*, so
     every slot the children did not fill was painted that colour too.  Seven
     children on three columns left two, and on the Quality view those two
     rendered in dark as a lighter slab that read like a selected cell.  In
     light the same hole is white on white and reads as an ordinary gap, which
     is why no capture and no earlier test saw it.  There is no text in the
     hole, so test 1 passes over it by construction — this test is the one
     that could notice.

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

VIEWS = ["Overview", "Library", "Profiles", "Workspaces",
         "Install", "Recovery", "Quality", "Settings"]


def _has_chromium():
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


# One element = one row per text node the reader can see, plus every grid's
# fill state.  Runs in the page; kept as one string so the logic under test is
# the logic that ships in the sweep.
SWEEP = r"""
() => {
  const parse = (s) => {
    const m = String(s).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    return { rgb: p.slice(0, 3), a: p.length > 3 ? p[3] : 1 };
  };
  const over = (fg, bg) => fg.rgb.map((c, i) => c * fg.a + bg[i] * (1 - fg.a));
  const lum = (a) => {
    const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(a[0]) + 0.7152 * f(a[1]) + 0.0722 * f(a[2]);
  };
  const ratio = (a, b) => {
    const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };
  const bgOf = (el) => {
    const stack = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage && cs.backgroundImage !== "none") return null;
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; }
    }
    if (!stack.length) return [255, 255, 255];
    let base = stack[stack.length - 1].a >= 1 ? stack.pop().rgb : [255, 255, 255];
    while (stack.length) base = over(stack.pop(), base);
    return base;
  };
  const text = [], grids = [];
  for (const el of document.querySelectorAll("body *")) {
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none" || +cs.opacity === 0) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) continue;
    if (el.closest("[aria-hidden='true']")) continue;
    if (cs.display === "grid" || cs.display === "inline-grid") {
      const kids = Array.from(el.children)
        .filter((k) => getComputedStyle(k).display !== "none"
                    && k.getBoundingClientRect().width > 0);
      if (kids.length) {
        const cols = cs.gridTemplateColumns.split(" ").filter(Boolean).length;
        const rows = new Set(kids.map((k) => Math.round(k.getBoundingClientRect().top))).size;
        grids.push({
          sel: el.tagName.toLowerCase() + "." + el.className.toString().trim().split(/\s+/).join("."),
          filled: kids.length, slots: rows * cols,
          own: bgOf(el), behind: bgOf(el.parentElement || el),
        });
      }
    }
    const own = Array.from(el.childNodes).filter((n) => n.nodeType === 3)
      .map((n) => n.textContent.trim()).join(" ").trim();
    if (!own) continue;
    const fg = parse(cs.color);
    const bg = bgOf(el);
    if (!fg || !bg) continue;
    const painted = fg.a < 1 ? over(fg, bg) : fg.rgb;
    const size = parseFloat(cs.fontSize);
    const weight = parseInt(cs.fontWeight, 10) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    text.push({
      sel: el.tagName.toLowerCase() + "." + el.className.toString().trim().split(/\s+/)[0],
      sample: own.slice(0, 32),
      ratio: +ratio(painted, bg).toFixed(2),
      need: large ? 3 : 4.5, size, weight,
    });
  }
  return { text, grids };
}
"""


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: this measures the colours the browser "
    "actually composites, which no source contract can stand in for",
)
class RenderedDarkPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-dark-")
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
        # Two skills: an empty library renders an empty state and every sweep
        # over it would pass without reaching a cell at all.
        cls.store.create("dark-sweep-alpha", "Fixture.",
                         body="# dark-sweep-alpha\n\nFixture body.\n")
        cls.store.create("dark-sweep-beta", "Second fixture.",
                         body="# dark-sweep-beta\n\nFixture body.\n")
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
        self._errors = []
        self._page.on("console",
                      lambda m: self._errors.append(m.text) if m.type == "error" else None)
        self._page.goto(self.server.url, wait_until="networkidle")
        self._page.wait_for_selector("#app", timeout=15000)
        self._page.evaluate(
            "() => document.documentElement.setAttribute('data-theme', 'dark')")

    def tearDown(self):
        self._browser.close()
        self._pw.stop()

    def _sweep(self, view):
        self._page.click(f'.viewtabs button:has-text("{view}"), .navigation-rail button[data-tip="{view}"]')
        self._page.wait_for_timeout(280)
        return self._page.evaluate(SWEEP)

    def test_every_views_text_passes_aa_in_dark(self):
        """Contrast is measured, not assumed: the token layer makes it pass, the
        sweep is what shows it does."""
        measured = 0
        failures = []
        for view in VIEWS:
            sweep = self._sweep(view)
            self.assertGreater(
                len(sweep["text"]), 5,
                f"{view} rendered {len(sweep['text'])} text elements in dark; a "
                "view that rendered nothing proves nothing about its colours")
            measured += len(sweep["text"])
            for row in sweep["text"]:
                if row["ratio"] < row["need"]:
                    failures.append(f"{view}: {row['ratio']}:1 needs {row['need']} "
                                    f"({row['size']}px/{row['weight']}) {row['sel']} "
                                    f"{row['sample']!r}")
        self.assertEqual([], failures, "WCAG 2.2 AA failures in dark:\n  "
                                       + "\n  ".join(failures[:12]))
        self.assertGreater(measured, 200, "the sweep must reach the whole app, "
                                           "not one view's worth of text")
        self.assertEqual([], self._errors, "console errors while sweeping dark")

    def test_a_grid_slot_with_nothing_in_it_is_not_painted(self):
        """The defect the contrast sweep is blind to, because there is no text
        in it.  An unfilled grid slot must show the panel behind the grid, or
        it renders as a slab that reads like content."""
        seen_dangling = 0
        offenders = []
        for view in VIEWS:
            sweep = self._sweep(view)
            for g in sweep["grids"]:
                if g["filled"] >= g["slots"]:
                    continue
                seen_dangling += 1
                delta = [abs(a - b) for a, b in zip(g["own"], g["behind"])]
                if max(delta) > 2:
                    offenders.append(
                        f"{view}: {g['sel']} fills {g['filled']}/{g['slots']} and "
                        f"paints rgb({','.join(str(round(c)) for c in g['own'])}) "
                        f"where there is nothing, on rgb({','.join(str(round(c)) for c in g['behind'])})")
        self.assertEqual([], offenders, "a grid slot with nothing in it is painted:\n  "
                                        + "\n  ".join(offenders[:12]))
        # Control: deleting every cell satisfies "nothing is painted" by
        # rendering nothing at all, which is why the dangling state is asserted.
        self.assertGreater(seen_dangling, 0,
                           "no grid on any view has an unfilled slot, so this "
                           "test asserted nothing")

    def test_the_dangling_slot_is_the_quality_summary_and_is_still_reached(self):
        """Names the defect so a later change cannot delete the grid, drop the
        cell that leaves the hole, or move the view out of the sweep, and still
        pass a suite whose other assertions are all conditional."""
        sweep = self._sweep("Quality")
        hits = [g for g in sweep["grids"]
                if "quality-metrics" in g["sel"] and g["filled"] < g["slots"]]
        self.assertTrue(hits, "the Quality summary no longer leaves an empty "
                              "slot; the defect is gone or the view moved, and "
                              "only one of those is good news")
        # 7 observed cells on 3 columns, per the seeded payload.
        self.assertGreaterEqual(hits[0]["filled"], 6)
        self.assertGreater(hits[0]["slots"], hits[0]["filled"])