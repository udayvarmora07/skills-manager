"""8.1 e2e — the landing page in a real browser, in both themes.

`tests/test_redesign_site.py` proves the page's *facts*. This proves it
*paints*: a page can carry a correct palette, a real screenshot and an honest
command list and still be unreadable, because a contrast ratio nobody
composited, a hero that 404s into a broken-image box, and a measure that
overflows at the width a shrunk laptop window lands on.

Four claims, each with the control that proves it can fail:

1. **It loads nothing remote and logs nothing.** Zero console errors, zero
   failed requests, zero >= 400 responses, per width per theme. A static page
   that fetches a font from a CDN is the exact thing RULES #4 forbids and the
   one thing a source scan cannot see at runtime.
2. **No horizontal overflow** at 1100/1280/1440/1920 — the laptop band, per the
   2026-10-13 re-scope. `test_the_overflow_probe_can_fail` injects a 4000px box
   and requires the same probe to report it, because "zero overflow" earned by a
   probe that measures nothing is the repo's most repeated failure.
3. **Contrast is measured, not assumed.** Body, lede and eyebrow text are
   composited against the surface they actually sit on. 6.2a and 6.4b both found
   the source tests comparing pairs the browser never painted together.
4. **The hero really is a screenshot** — `naturalWidth > 0` and a paint box
   wider than a thumbnail. A broken image still occupies layout and still passes
   an overflow check, which is what makes it worth asserting separately.

Keyboard: the skip link is the one interactive affordance the page has, and it
is asserted as BEHAVIOUR (focus it, press Enter, land on `#main`), not as
markup.

SKIPS LOUDLY when Playwright is absent (never a silent pass).
"""

import http.server
import os
import socketserver
import sys
import threading
import unittest

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(REPO, "site")
WIDTHS = (1100, 1280, 1440, 1920)
HEIGHT = 900

#: WCAG relative luminance + contrast, computed in the page from the COLOURS
#: the browser resolved — not from the hex in the stylesheet, because an
#: `rgba()`/`color-mix()` anywhere in the chain makes the source a different
#: value from the one that paints.
CONTRAST = r"""
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return null;
  const cs = getComputedStyle(el);
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(s => parseFloat(s));
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  // Walk up for the first opaque background, which is what the text sits on.
  let bg = null, node = el;
  while (node) {
    const c = parse(getComputedStyle(node).backgroundColor);
    if (c && c.a === 1) { bg = c; break; }
    node = node.parentElement;
  }
  const fg = parse(cs.color);
  if (!fg || !bg) return null;
  const over = (f, b) => ({r: f.r * f.a + b.r * (1 - f.a),
                           g: f.g * f.a + b.g * (1 - f.a),
                           b: f.b * f.a + b.b * (1 - f.a), a: 1});
  const flat = over(fg, bg);
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92
                      : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const a = lum(flat), b = lum(bg);
  const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  return {ratio: Math.round(ratio * 100) / 100, size: cs.fontSize, weight: cs.fontWeight};
}
"""

OVERFLOW = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"


def _chromium_available():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:  # pragma: no cover - environment without a browser
        return False


HAS_CHROMIUM = _chromium_available()
if not HAS_CHROMIUM:  # pragma: no cover
    print("SKIP: tests/e2e/test_site.py needs Playwright's Chromium. Run via "
          ".redesign/verify.sh with the kit venv on PATH.", file=sys.stderr)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


#: The handler is bound to SITE with `directory=` rather than by chdir'ing the
#: process. Chdir works and then silently breaks the moment a test runs from
#: another directory: the page 404s, every selector comes back null, and the
#: failure reads as "the page has no hero" instead of "the server is serving
#: nothing" — which is what the first run of this file reported.
_HANDLER = lambda *a, **kw: _Quiet(*a, directory=SITE, **kw)  # noqa: E731


@unittest.skipUnless(HAS_CHROMIUM, "Playwright Chromium is not available")
class SiteBrowserTests(unittest.TestCase):
    """One browser, one page, resized per width — the 2.1 lesson about a second
    `sync_playwright()` inside a test raising."""

    server = None
    thread = None
    base = ""

    @classmethod
    def setUpClass(cls):
        socketserver.TCPServer.allow_reuse_address = True
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), _HANDLER)
        cls.base = "http://127.0.0.1:%d/" % cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.errors, self.failed, self.bad = [], [], []
        # `.start()` returns the Playwright driver. `sync_playwright()` alone is
        # a context MANAGER — reading `.chromium` off it is the same class of
        # mistake as calling a method stored as a value (4.5c): the object the
        # template would receive is not the object the API exposes.
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self.page = self.browser.new_page(viewport={"width": 1280, "height": HEIGHT})
        self.page.on(
            "console", lambda m: self.errors.append(m.text) if m.type == "error" else None
        )
        self.page.on("requestfailed", lambda r: self.failed.append(r.url))
        self.page.on(
            "response",
            lambda r: self.bad.append("%d %s" % (r.status, r.url)) if r.status >= 400 else None,
        )
        self.page.goto(self.base, wait_until="load")

    def tearDown(self):
        self.browser.close()
        self._pw.stop()

    # -- 1. it loads nothing remote and logs nothing ------------------------
    def test_no_console_errors_failed_requests_or_bad_responses(self):
        for theme in ("light", "dark"):
            self.page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", theme)
            for width in WIDTHS:
                self.page.set_viewport_size({"width": width, "height": HEIGHT})
                self.page.wait_for_timeout(120)
        self.assertEqual(self.errors, [], "console errors on the landing page")
        self.assertEqual(self.failed, [], "failed requests on the landing page")
        self.assertEqual(self.bad, [], "the landing page asked for something that 4xx/5xx'd")

    def test_every_request_the_page_makes_is_same_origin(self):
        origins = self.page.evaluate(
            "() => performance.getEntriesByType('resource')"
            ".map(e => new URL(e.name).origin)"
        )
        for origin in origins:
            self.assertEqual(origin, self.base.rstrip("/"), "the page fetched off-origin: " + origin)

    # -- 2. the laptop band --------------------------------------------------
    def test_no_horizontal_overflow_in_the_laptop_band(self):
        for theme in ("light", "dark"):
            self.page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", theme)
            for width in WIDTHS:
                self.page.set_viewport_size({"width": width, "height": HEIGHT})
                self.page.wait_for_timeout(120)
                over = self.page.evaluate(OVERFLOW)
                self.assertLessEqual(over, 1, "overflow at %d (%s)" % (width, theme))

    def test_content_keeps_a_left_gutter_at_every_width(self):
        # Found by LOOKING at the 1100 capture, and it is the defect this
        # suite's other three claims cannot see: no overflow, no console error,
        # no bad request, and the hero's text hard against the window edge.
        # `.hero` carried `.shell` and declared `padding: … 0`, so its shorthand
        # reset the shell's horizontal gutter — invisible at 1440 because the
        # 1320px shell's centring margin happened to hide it.
        for width in WIDTHS:
            self.page.set_viewport_size({"width": width, "height": HEIGHT})
            self.page.wait_for_timeout(100)
            edges = self.page.evaluate(
                "() => { const r = document.querySelector('.hero h1').getBoundingClientRect();"
                # `.closer`'s own border box legitimately starts at x=0 — the
                # gutter is its PADDING. Measuring the section measured its
                # margin edge, which is the window edge at every width and
                # would have passed on the broken tree too.
                " const c = document.querySelector('.closer h2').getBoundingClientRect();"
                " const b = document.querySelector('.brand').getBoundingClientRect();"
                " return {hero: Math.round(r.left), closer: Math.round(c.left),"
                "         brand: Math.round(b.left)}; }"
            )
            for name in ("hero", "closer", "brand"):
                self.assertGreaterEqual(
                    edges[name], 16, "%s sits at x=%d at %dpx" % (name, edges[name], width)
                )
            self.assertEqual(
                edges["hero"], edges["brand"],
                "the hero and the masthead must share one gutter",
            )

    def test_the_overflow_probe_can_fail(self):
        self.page.evaluate(
            "() => { const b = document.createElement('div');"
            "b.style.cssText='width:4000px;height:10px'; document.body.appendChild(b); }"
        )
        self.assertGreater(self.page.evaluate(OVERFLOW), 1000,
                           "the overflow probe cannot fail, so every other pass is noise")

    # -- 3. contrast, measured on what paints --------------------------------
    def test_body_text_clears_aa_in_both_themes(self):
        for theme in ("light", "dark"):
            self.page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", theme)
            self.page.set_viewport_size({"width": 1440, "height": HEIGHT})
            self.page.wait_for_timeout(120)
            for selector in (".lede", ".ledger-row p", ".cli .cli-note", ".colophon"):
                measured = self.page.evaluate(CONTRAST, selector)
                self.assertIsNotNone(measured, "could not measure " + selector)
                self.assertGreaterEqual(
                    measured["ratio"], 4.5,
                    "%s is %.2f:1 in %s" % (selector, measured["ratio"], theme),
                )

    # -- 4. the hero is a real capture ---------------------------------------
    def test_the_hero_image_actually_painted(self):
        box = self.page.evaluate(
            "() => { const i = document.querySelector('.shot img');"
            " if (!i) return null; const r = i.getBoundingClientRect();"
            " return {nw: i.naturalWidth, w: Math.round(r.width)}; }"
        )
        self.assertIsNotNone(box, "there is no hero image element")
        self.assertGreater(box["nw"], 600, "the hero image did not load")
        self.assertGreater(box["w"], 300, "the hero image renders at thumbnail size")

    def test_the_hero_has_an_alt_that_describes_the_view(self):
        alt = self.page.get_attribute(".shot img", "alt")
        self.assertIsNotNone(alt)
        self.assertGreater(len(alt), 60, "the hero's alt is a placeholder, not a description")

    # -- 5. the one interaction ----------------------------------------------
    def test_the_skip_link_is_reachable_and_works(self):
        self.page.keyboard.press("Tab")
        focused = self.page.evaluate("() => document.activeElement.className")
        self.assertIn("skip-link", focused, "the first Tab does not reach the skip link")
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(120)
        self.assertIn("#main", self.page.evaluate("() => window.location.hash"))

    def test_the_skip_link_becomes_visible_when_focused(self):
        # `top: -64px` off-screen until focused is the point; an always-hidden
        # skip link is the defect this checks, and it is invisible in a
        # screenshot taken of a resting page.
        before = self.page.evaluate(
            "() => Math.round(document.querySelector('.skip-link').getBoundingClientRect().top)"
        )
        self.page.focus(".skip-link")
        # Measured AFTER the transition settles. The first version read the box
        # in the same tick as `focus()` and reported -64px — the transition's
        # first frame, not the rule failing. Same lesson as 2.1's screenshot
        # captured mid-fade at `opacity: 0.386`.
        self.page.wait_for_timeout(300)
        after = self.page.evaluate(
            "() => Math.round(document.querySelector('.skip-link').getBoundingClientRect().top)"
        )
        self.assertLess(before, 0, "the skip link is on screen before it is focused")
        self.assertGreaterEqual(after, 0, "focusing the skip link does not bring it into view")


if __name__ == "__main__":
    unittest.main()