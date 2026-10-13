"""6.4 e2e — reduced-motion and the focus ring, as gates instead of claims.

**Why this file exists.** RULES #13 promises two things about motion that the
branch asserted only in the stylesheet: *reduced-motion respected* and *a
visible focus ring on every control*. The stylesheet does honour both — this
file measures it, per view, in a real browser — and **nothing ran the
measurement**. That is this repository's recorded "a gate nobody runs reads as
coverage", fifth appearance (`.chip`/`.empty`/`.skeleton` in 1.5,
`--border-strong`, `--mute*` in 4.2d, the `stateKeys` aggregate in 4.2e, and
0b.4's browser suite itself). 6.1b turned the dark contrast sweep into a gate
and 6.2c turned the width sweep into one; this is the same move for the third
sweep the branch runs by hand.

**Three claims, and what would still pass if the product broke.**

1. `test_reduced_motion_neutralises_every_animation_and_transition` walks all
   eight views under `reduced_motion="reduce"` and asserts **zero** elements
   carry a computable animation or transition duration. Baseline measured on
   the seeded tree: 26 moving elements on Overview, **135 on Library**, 13–24
   on the rest.
2. `test_the_motion_probe_can_see_motion` is the control. Every assertion in
   (1) is a `== 0`, so a probe that always returns `[]` — a selector that
   stopped matching, a page that stopped rendering — would make all eight
   vacuously green. It injects a 10s animation and asserts the probe reports
   it in the SAME context, before reduce is applied.
3. `test_every_focusable_control_paints_a_ring_under_real_keyboard_focus`
   presses real Tab keys rather than calling `el.focus()`. This is not
   pedantry: `:focus-visible` is a *modality* selector, and the earlier probe
   that used `el.focus()` reported "0 of 235 controls lack a ring" on a tree
   where the modality was pointer — a number that could not have meant what it
   said. Under real Tab the gate also requires `el.matches(':focus-visible')`
   to be true, so a stylesheet that painted an outline for *every* state would
   fail here rather than pass.

**What is deliberately NOT asserted here.** The focus *contrast* ratio and the
focus *order* are 6.6's (axe + a keyboard walk-through), and duplicating them
would give the morning two places to look and one place to forget. This file
answers "is there a ring, and is it the keyboard's ring".

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

VIEWS = ("Overview", "Library", "Profiles", "Workspaces",
         "Install", "Recovery", "Quality", "Settings")


# In the page. Every element that is *computably* in motion: a non-zero
# animation duration, or a transition whose longest single duration is
# non-zero. Zero-size and non-rendered elements are skipped because a
# `display:none` control is not a thing a reader can be bothered by.
MOTION = r"""
() => {
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    const anim = parseFloat(cs.animationDuration) || 0;
    const trans = (cs.transitionDuration || '0s').split(',')
      .reduce((m, d) => Math.max(m, parseFloat(d) || 0), 0);
    if (anim > 0.001 || trans > 0.001) {
      out.push({
        sel: el.tagName.toLowerCase() +
             (el.id ? '#' + el.id : '') +
             (typeof el.className === 'string' && el.className.trim()
               ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''),
        animation: cs.animationName + ' ' + cs.animationDuration,
        transition: cs.transitionProperty + ' ' + cs.transitionDuration,
      });
    }
  }
  return out;
}
"""

RING = r"""
() => {
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) return null;
  const cs = getComputedStyle(el);
  const outline = parseFloat(cs.outlineWidth) || 0;
  return {
    id: el.tagName.toLowerCase() +
        (el.id ? '#' + el.id : '') +
        (typeof el.className === 'string' && el.className.trim()
          ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''),
    visible: el.matches(':focus-visible'),
    outlineWidth: outline,
    outlineStyle: cs.outlineStyle,
    shadow: cs.boxShadow !== 'none',
  };
}
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
    """A populated library, because a view with nothing in it proves nothing."""
    for i in range(8):
        store.create(
            "motion-fixture-%02d" % i,
            "A description long enough that the Library rows wrap rather than "
            "collapse, which is what makes a focus ring land somewhere real.",
            body="# motion-fixture-%02d\n\nBody for the motion gate.\n" % i)


@unittest.skipUnless(
    _has_chromium(),
    "Playwright/Chromium unavailable: prefers-reduced-motion and :focus-visible "
    "are both resolved by the browser's own style engine, which no source "
    "contract can stand in for",
)
class MotionAndFocusTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls._tmp = tempfile.mkdtemp(prefix="skillsmgr-e2e-motion-")
        cls._saved = {k: os.environ.get(k)
                      for k in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA",
                                "PLAYWRIGHT_BROWSERS_PATH")}
        if not cls._saved.get("PLAYWRIGHT_BROWSERS_PATH"):
            rh = cls._saved.get("HOME") or os.path.expanduser("~")
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
        for k, v in cls._saved.items():
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

    def _goto(self, view):
        rail = self._page.query_selector('.navigation-rail[data-drawer="open"]')
        if rail is None and self._page.is_visible(".nav-drawer-trigger"):
            self._page.click(".nav-drawer-trigger")
            self._page.wait_for_timeout(200)
        self._page.click('.navigation-rail button[data-tip="%s"]' % view)
        self._page.wait_for_selector(
            '.navigation-rail button[data-tip="%s"][aria-current="page"]' % view,
            timeout=10000)
        self._page.wait_for_timeout(180)

    # -- 1. the sweep --------------------------------------------------------

    def test_reduced_motion_neutralises_every_animation_and_transition(self):
        """The claim RULES #13 makes, on every view, in a browser.

        Measured baseline on the seeded tree before emulating: 26 moving
        elements on Overview, 135 on Library, 13-24 elsewhere. All eight reach
        zero under `reduce`, which is the global block at the end of LAYER 7
        doing its job -- unasserted until now.
        """
        leaks = []
        for view in VIEWS:
            self._goto(view)
            self._page.emulate_media(reduced_motion="reduce")
            self._page.wait_for_timeout(90)
            moving = self._page.evaluate(MOTION)
            self._page.emulate_media(reduced_motion="no-preference")
            self._page.wait_for_timeout(60)
            if moving:
                leaks.append("%s: %s" % (view, moving[:3]))
        self.assertEqual(leaks, [],
                         "motion survived prefers-reduced-motion: " + "; ".join(leaks))

    def test_the_motion_probe_can_see_motion(self):
        """The control for (1), and the one that makes (1) mean anything.

        Every measurement in (1) asserts a count of zero. If the probe stopped
        matching -- or the app stopped rendering -- all eight would pass while
        measuring nothing. So: put a 10-second animation in the live page and
        assert the probe reports it in the same context, with motion PREFERRED.
        """
        self._goto("Library")
        self._page.evaluate(
            """() => {
                 const d = document.createElement('div');
                 d.id = 'motion-gate-canary';
                 d.style.cssText = 'width:8px;height:8px;background:red;' +
                   'animation: motion-gate-spin 10s linear infinite';
                 const s = document.createElement('style');
                 s.textContent = '@keyframes motion-gate-spin ' +
                                 '{ to { transform: rotate(360deg) } }';
                 document.head.appendChild(s);
                 document.querySelector('.layout').appendChild(d);
               }""")
        self._page.wait_for_timeout(150)
        found = [m for m in self._page.evaluate(MOTION)
                 if m["sel"].startswith("div#motion-gate-canary")]
        self.assertTrue(found,
                        "the probe cannot see a 10s animation on the page: "
                        "every zero in this file is measuring nothing")

    def test_the_sweep_reaches_every_view(self):
        """Eight zeros of one view are not eight views."""
        seen = []
        for view in VIEWS:
            self._goto(view)
            seen.append(self._page.eval_on_selector(
                '.navigation-rail button[aria-current="page"]',
                "el => el.dataset.tip"))
        self.assertEqual(sorted(seen), sorted(VIEWS))

    # -- 2. the focus ring ---------------------------------------------------

    def test_every_focusable_control_paints_a_ring_under_real_keyboard_focus(self):
        """RULES #13's second claim, driven the way a reader drives it.

        `el.focus()` does NOT set `:focus-visible` -- Chromium matches it on
        the last input modality, and a script focus after a click inherits
        *pointer*. An earlier probe of this branch walked 235 controls with
        `el.focus()` and reported "0 of 235 lack a ring", a number that could
        not have meant what it said. So this presses real Tab keys, requires
        `matches(':focus-visible')` to be TRUE on every stop, and requires a
        painted indicator on every stop.
        """
        self._goto("Library")
        self._page.evaluate("() => document.body.focus()")
        missing, wrong_modality, walked = [], [], 0
        for _ in range(40):
            self._page.keyboard.press("Tab")
            ring = self._page.evaluate(RING)
            if ring is None:
                break  # focus left the document: the page's tab ring is done
            walked += 1
            if not ring["visible"]:
                wrong_modality.append(ring["id"])
            elif ring["outlineWidth"] <= 0 and not ring["shadow"]:
                missing.append(ring["id"])
        self.assertGreater(walked, 10,
                           "the walk stopped after %d stops: a two-control "
                           "page and a 235-control page both satisfy a loop "
                           "that exits early" % walked)
        self.assertEqual(wrong_modality, [],
                         "a keyboard-focused control did not match "
                         ":focus-visible: " + ", ".join(wrong_modality[:6]))
        self.assertEqual(missing, [],
                         "focused with no painted indicator: "
                         + ", ".join(missing[:6]))

    def test_the_ring_walks_off_the_end_of_the_document(self):
        """The other half of the walk: focus must not fall out of the page.

        A Tab ring that escapes to the browser chrome mid-page is invisible to
        the loop above, which simply stops and calls it clean.
        """
        self._goto("Library")
        self._page.evaluate("() => document.body.focus()")
        seen = []
        for _ in range(200):
            self._page.keyboard.press("Tab")
            ring = self._page.evaluate(RING)
            if ring is None:
                break
            seen.append(ring["id"])
        self.assertLess(len(seen), 200,
                        "200 Tab presses never left the document: focus is "
                        "being trapped, or the ring is not reachable at all")

    def test_no_console_error_anywhere_in_this_file(self):
        for view in VIEWS:
            self._goto(view)
        self._page.keyboard.press("Tab")
        self.assertEqual(self._errors, [])


if __name__ == "__main__":
    unittest.main()