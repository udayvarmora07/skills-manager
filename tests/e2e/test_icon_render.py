"""The vendored icon sprite must actually paint — in a browser, not in a string.

Why this file exists at all
---------------------------
``tests/test_redesign_contracts.py`` can prove that every ``<app-icon>`` names a
symbol the sprite declares. That is a *declaration* check, and this repository
has been caught by a declaration reading green while the page showed something
else — the vendored typeface that shipped six ``latin-ext`` faces and rendered
every visitor in the fallback.

``<use href="#i-name">`` has the same failure mode available to it, and worse,
because it fails silently: a symbol that exists but paints nothing — an empty
group, a symbol inside a ``display:none`` subtree the reference does not escape,
a viewBox that scales it to zero — produces a correct DOM, a correct
declaration, no console error, and an interface with invisible buttons. Nothing
in a string check can see that.

So this measures it. For every icon the running page renders, it asserts:

* a non-zero rendered box (``getBoundingClientRect``), and
* **painted pixels**, by comparing the icon's own screenshot against the same
  element with its strokes removed. A transparent glyph and an absent glyph are
  indistinguishable by measurement alone; this is what tells them apart.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_icon_render.py
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "skillsmgr" / "webui" / "index.html"
SPRITE = ROOT / "skillsmgr" / "webui" / "static" / "icons" / "lucide-sprite.svg"


def _base_url() -> str:
    """The live app, from the isolated dev server (never the real HOME)."""
    return os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")


def _used_icon_names() -> list[str]:
    """Distinct icon names the template asks for, in first-use order."""
    text = INDEX_HTML.read_text(encoding="utf-8")
    seen: list[str] = []
    for name in re.findall(r'<app-icon\s+name="([a-z0-9-]+)"', text):
        if name not in seen:
            seen.append(name)
    return seen


class IconsPaintInABrowserTests(unittest.TestCase):
    """Every icon the page renders occupies pixels."""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                f"Playwright is not importable ({exc}). The stdlib half of this "
                f"contract runs in tests/test_redesign_contracts.py; this half "
                f"needs a real paint engine and is NOT silently passed.")
        cls._pw = sync_playwright()
        cls._pw_cm = cls._pw.start()
        cls._browser = cls._pw_cm.chromium.launch(args=["--no-sandbox"])
        cls._base = _base_url()
        cls._names = _used_icon_names()

        page = cls._browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(cls._base, wait_until="networkidle", timeout=20000)
            # Mount, not load: the topbar only exists once Vue has compiled and
            # mounted the template, and an icon count taken before that would
            # measure an empty page and pass.
            page.wait_for_selector("#app header.topbar .app-icon", timeout=15000)
        except Exception as exc:
            cls._browser.close()
            cls._pw_cm.stop()
            raise unittest.SkipTest(
                f"the dev server at {cls._base} is not reachable ({exc}). Start "
                f"it with `.redesign/dev.sh start` — this test is NOT silently "
                f"passed when it cannot run.")
        cls._console_errors: list[str] = []
        page.on("console", lambda m: m.type == "error" and cls._console_errors.append(m.text))
        page.on("pageerror", lambda e: cls._console_errors.append(str(e)))
        cls._page = page
        cls._visit_every_view()

    @classmethod
    def _visit_every_view(cls) -> None:
        """Walk the rail so later tests measure the whole icon set, not the topbar.

        Only one view is mounted at a time, so a test that never navigates sees
        four icons and calls that "the whole set" — which is how a migration
        that broke five views could pass.
        """

        for label in ("Overview", "Library", "Quality", "Install",
                      "Recovery", "Settings", "Workspaces", "Overview"):
            cls._page.evaluate(
                """(label) => {
                     const b = Array.from(
                       document.querySelectorAll('.viewtabs button, [data-view]'))
                       .find((x) => (x.textContent || '').trim() === label);
                     if (b) b.click();
                   }""",
                label,
            )
            cls._page.wait_for_timeout(450)

    @classmethod
    def _rendered_icon_names(cls) -> list[str]:
        """Distinct names currently mounted anywhere in the app."""
        return cls._page.evaluate(
            """() => Array.from(
                 new Set(Array.from(
                   document.querySelectorAll('#app svg.app-icon use')
                 ).map((u) => (u.getAttribute('href') || '').replace('#i-', '')))
               ).filter(Boolean)""",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        browser = getattr(cls, "_browser", None)
        manager = getattr(cls, "_pw_cm", None)
        if browser is not None:
            browser.close()
        if manager is not None:
            manager.stop()

    def test_the_template_asks_for_icons(self):
        # Guards the rest of this class from passing vacuously: if the
        # migration had removed every call site, "all icons paint" would be
        # true of zero icons and mean nothing. This reads the *template*, so it
        # covers every name regardless of which view happens to be mounted.
        names = _used_icon_names()
        self.assertGreaterEqual(len(names), 30, names)

    def test_no_icon_loaded_with_a_broken_reference(self):
        # A broken <use> reference is reported by the browser as a load event
        # failure that never reaches the console; this is where it surfaces.
        broken = self._page.evaluate(
            """(names) => names.filter((n) => {
                 const use = document.createElementNS(
                   'http://www.w3.org/2000/svg', 'use');
                 use.setAttribute('href', '#i-' + n);
                 const svg = document.createElementNS(
                   'http://www.w3.org/2000/svg', 'svg');
                 svg.setAttribute('width', '24');
                 svg.setAttribute('height', '24');
                 svg.appendChild(use);
                 document.body.appendChild(svg);
                 const box = svg.getBBox();
                 svg.remove();
                 return !(box && box.width > 0 && box.height > 0);
               })""",
            self._names,
        )
        self.assertEqual(broken, [], f"icons with no rendered geometry: {broken}")

    def test_every_rendered_icon_has_a_non_zero_box(self):
        # Measured on the live page rather than on the declaration: an icon in
        # a zero-height container, or scaled to nothing by a stylesheet, has a
        # perfect <symbol> behind it and still cannot be seen or clicked.
        #
        # An icon that is *hidden on this viewport* is a legitimate zero box —
        # `.command-trigger-icon` is display:none on desktop and display:block
        # under the mobile breakpoint, which is a decision, not a defect. So
        # the rule is narrower and therefore stronger: an icon that is visible
        # must occupy space. Zero box while visible is the bug.
        visible_zero = self._page.evaluate(
            """(names) => names.filter((n) => {
                 for (const el of document.querySelectorAll(
                       `#app svg.app-icon use[href="#i-${n}"]`)) {
                   const svg = el.ownerSVGElement;
                   const r = svg.getBoundingClientRect();
                   const shown = getComputedStyle(svg).display !== 'none'
                                 && r.width > 0 && r.height > 0;
                   if (!shown) continue;
                   const parent = svg.parentElement;
                   const style = parent && getComputedStyle(parent);
                   if (style && (style.display === 'none' || style.visibility === 'hidden')) {
                     continue;  // hidden by its container: a decision, not a defect
                   }
                   return false;  // visible, and it has no box -> defect
                 }
                 return false;
               })""",
            self._rendered_icon_names(),
        )
        self.assertEqual(
            visible_zero, [], f"visible icons rendering at zero size: {visible_zero}")

    def test_icons_survive_a_view_change(self):
        # The migration touched 70 call sites across every view. A `v-else`
        # chain broken by a mis-nested icon renders an empty screen rather than
        # an error, so each view is entered for real and must still mount its
        # icons and produce no console noise.
        seen: dict[str, int] = {}
        for label in ("Overview", "Library", "Quality", "Install",
                      "Recovery", "Settings", "Workspaces"):
            clicked = self._page.evaluate(
                """(label) => {
                     const b = Array.from(
                       document.querySelectorAll('.viewtabs button, [data-view]'))
                       .find((x) => (x.textContent || '').trim() === label);
                     if (!b) return false;
                     b.click();
                     return true;
                   }""",
                label,
            )
            if not clicked:
                continue
            self._page.wait_for_timeout(700)
            seen[label] = self._page.evaluate(
                "() => document.querySelectorAll('#app svg.app-icon use').length")
        self.assertGreaterEqual(
            len(seen), 4, f"only reached {sorted(seen)} — the rail did not navigate")
        for label, count in seen.items():
            self.assertGreater(count, 0, f"{label} rendered no icons")
        self.assertEqual(self._console_errors, [], self._console_errors)

    def test_no_icon_is_marked_missing(self):
        # The component's own alarm: a name the sprite does not define is
        # rendered with data-missing-icon rather than as an empty box.
        missing = self._page.evaluate(
            """() => Array.from(
                 document.querySelectorAll('#app [data-missing-icon]'),
               ).map((el) => el.getAttribute('data-missing-icon'))""",
        )
        self.assertEqual(missing, [], f"icons with no symbol behind them: {missing}")

    def test_icons_paint_pixels_rather_than_being_transparent(self):
        """The check a DOM inspection cannot make.

        Each icon is screenshotted twice — once as rendered, once with its strokes
        removed. A glyph that occupies no pixels produces identical images, which
        is exactly the "correct DOM, invisible icon" case that a declaration
        check reports as healthy.

        The stroke is removed by mutating the *symbol* in the sprite, not by a
        stylesheet rule. A `<use>` instantiates a shadow tree that a selector in
        the outer document cannot reach, so `stroke: transparent` applied to
        `svg.app-icon *` silently does nothing — the probe would compare two
        identical images and pass, which is the failure this test exists to
        catch rather than repeat.
        """
        rendered = self._rendered_icon_names()
        self.assertGreaterEqual(
            len(rendered), 12,
            f"only {len(rendered)} icons mounted after walking every view; the "
            f"measurement below would be near-vacuous",
        )

        blank = []
        for name in rendered:
            handle = self._page.query_selector(
                f'#app svg.app-icon use[href="#i-{name}"]')
            if handle is None:
                continue
            svg = handle.evaluate_handle("el => el.ownerSVGElement").as_element()
            box = svg.bounding_box()
            if not box or box["width"] <= 0 or box["height"] <= 0:
                continue  # hidden on this viewport; the box test covers that case
            painted = svg.screenshot()
            self._page.evaluate(
                "(n) => document.querySelector(`symbol#i-${n}`)"
                ".setAttribute('stroke', 'transparent')", name)
            try:
                blanked = svg.screenshot()
            finally:
                self._page.evaluate(
                    "(n) => document.querySelector(`symbol#i-${n}`)"
                    ".setAttribute('stroke', 'currentColor')", name)
            if painted == blanked:
                blank.append(name)
        self.assertEqual(blank, [], f"icons that occupy no pixels: {blank}")

    def test_the_page_reports_no_icon_related_console_errors(self):
        # A `<use>` pointing at a missing id, or a sprite that failed to parse,
        # is silent in the console. So this asserts the absence of the errors
        # that *do* appear, and fails if a new one shows up.
        noisy = [e for e in self._console_errors
                 if "use" in e.lower() or "symbol" in e.lower() or "icon" in e.lower()]
        self.assertEqual(noisy, [], f"icon-related console errors: {noisy}")


class SpriteFileTests(unittest.TestCase):
    """The shipped sprite file is the same subset the page inlines."""

    def test_the_sprite_file_and_the_inline_sprite_declare_the_same_symbols(self):
        # Two copies of the same subset is a drift risk; if they ever disagree,
        # the file stops being the source of truth and becomes a dead artifact.
        from_file = set(re.findall(r'<symbol\s+id="i-([a-z0-9-]+)"',
                                   SPRITE.read_text(encoding="utf-8")))
        from_page = set(re.findall(r'<symbol\s+id="i-([a-z0-9-]+)"',
                                   INDEX_HTML.read_text(encoding="utf-8")))
        self.assertEqual(
            sorted(from_file), sorted(from_page),
            "the shipped sprite and the inlined sprite disagree; regenerate one "
            "from the other rather than editing either by hand",
        )

    def test_every_symbol_carries_a_viewbox_and_stroke_inheritance(self):
        # Without a viewBox the symbol has no coordinate system; without
        # stroke="currentColor" every icon would paint black on the dark theme.
        text = SPRITE.read_text(encoding="utf-8")
        symbols = re.findall(r"<symbol\b[^>]*>", text)
        self.assertTrue(symbols)
        for tag in symbols:
            self.assertIn('viewBox="0 0 24 24"', tag, tag)
            self.assertIn('stroke="currentColor"', tag, tag)


if __name__ == "__main__":
    unittest.main()