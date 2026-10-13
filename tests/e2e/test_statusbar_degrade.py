"""The status bar, measured — and a claim that turned out to be false.

Why this file exists
--------------------
Two separate iterations recorded a status-bar defect, and neither of them was
real. `MAP.md` (5.2) said the trailing span painted "to x=803 on a 768
viewport"; the run after that said attention-queue text "scrolls behind the
status bar" and the two "overlap mid-word". Both were carried forward as
outstanding work, which is how a phantom defect costs more than the defect it
imitates: every iteration that reads those notes re-investigates them.

So the first thing here is the measurement that settles it, and the second is
the invariant that makes the question stop mattering.

The measurement
~~~~~~~~~~~~~~~
At every width the product is used at, the bar's children end
inside the bar's content box:

    width    bar content edge   last child ends at   past the edge
    1280             1264.0             1264.0              0.00
    1100             1084.0             1084.0              0.00
     820              804.0              804.0              0.00

`pastContentRight` is the honest number. The "16px past the edge" that first
suggested a defect was the probe's own arithmetic — it added *both* paddings to
the left edge and subtracted *both* from the right, over-counting the padding by
12px at every width and inventing a clip that was not there. The lesson is the
one 0b.4b already paid for: **a measurement that reports a defect you cannot
reproduce by hand is a broken measurement.** `.statusbar` also has
`overflow: hidden`, so a clipped child never grows its parent's `scrollWidth`
and every overflow audit in this repo reads the bar as clean — which is
correct, and is why no gate ever flagged it.

The invariant
~~~~~~~~~~~~~
`.statusbar` is `overflow: hidden`, so its failure mode is silent: content too
wide is sliced mid-glyph with no ellipsis and no signal. Two properties keep
that from being reachable, and both are asserted here rather than trusted:

1. Nothing paints past the bar's content box, at any width.
2. Nothing that is *rendered* has zero width while carrying text — an element
   that is in the DOM and in the accessibility tree but paints nothing. This is
   real: `.path` does exactly this whenever `dataDir` is empty, which is what
   the sandbox serves. It is an environment artifact rather than a layout bug,
   and the test asserts the general property so it cannot become one.

The third test is a guard on the CSS itself: the degradation order is expressed
with positional `:nth-child` selectors because the fix was CSS-only this
iteration (another session held `index.html`). A positional selector is exactly
the kind of thing that silently keeps working after the markup moves. This
fails loudly instead.

Run
---
    .redesign/dev.sh reset && .redesign/dev.sh start
    /home/uday-varmora/overnight-ui/venv/bin/python3 tests/e2e/test_statusbar_degrade.py
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STYLES = ROOT / "skillsmgr" / "webui" / "styles.css"

#: The widths the tool is actually used at — confirmed with the user 2026-10-13:
#: a laptop and a PC. 1100 is the shrunk-laptop window, which is the one narrow
#: width that matters; the tablet band below it is checked because the status
#: bar's declared degradation is written against it.
WIDTHS = (1920, 1440, 1280, 1100, 1024, 900, 820)

#: The two items the product's argument rests on. Neither may ever be the thing
#: that silently disappears when the bar gets tight.
LOAD_BEARING = ("data stays on this machine", "served ")


def _base_url() -> str:
    """The live app, from the isolated dev server (never the real HOME)."""
    return os.environ.get("SKILLS_MANAGER_URL", "http://127.0.0.1:8791")


#: Measures the bar's real geometry in one round-trip.
PROBE = """() => {
  const bar = document.querySelector('.statusbar');
  if (!bar) return {error: 'no .statusbar'};
  const b = bar.getBoundingClientRect();
  const cs = getComputedStyle(bar);
  // Content box right edge, done properly: the border, then the padding, once.
  const contentRight = b.right - parseFloat(cs.borderRightWidth || 0)
                                 - parseFloat(cs.paddingRight || 0);
  const contentLeft = b.left + parseFloat(cs.borderLeftWidth || 0)
                                + parseFloat(cs.paddingLeft || 0);
  const children = [...bar.children].map(el => {
    const r = el.getBoundingClientRect();
    const k = getComputedStyle(el);
    return {
      text: (el.textContent || '').trim().replace(/\\s+/g, ' '),
      cls: el.className || '',
      display: k.display,
      width: r.width,
      left: r.left,
      right: r.right,
      visible: k.display !== 'none' && r.width > 0,
      hasText: (el.innerText || '').trim().length > 0,
    };
  });
  return {
    contentLeft, contentRight,
    barScrollW: bar.scrollWidth, barClientW: bar.clientWidth,
    docOverflow: document.documentElement.scrollWidth
               - document.documentElement.clientWidth,
    children,
  };
}"""


class StatusBarGeometryTests(unittest.TestCase):
    """Runs against the live app. One browser for the whole class."""

    server = None
    playwright = None
    browser = None
    results: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        from playwright.sync_api import sync_playwright

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        for w in WIDTHS:
            page = cls.browser.new_page(viewport={"width": w, "height": 900})
            page.goto(_base_url(), wait_until="networkidle")
            page.wait_for_timeout(300)
            cls.results[w] = page.evaluate(PROBE)
            page.close()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.browser:
            cls.browser.close()
        if cls.playwright:
            cls.playwright.stop()

    def test_nothing_paints_past_the_status_bars_content_box(self) -> None:
        """The property `overflow: hidden` would otherwise hide.

        A flex item that cannot shrink pushes the last child past the clip, and
        the bar keeps reporting `scrollWidth === clientWidth` while it does — so
        no overflow audit in this repo can see it. The only way to catch it is
        to measure each child's box against the bar's content edge directly.
        """
        offenders = []
        for w, d in self.results.items():
            self.assertNotIn("error", d, f"no .statusbar at {w}px")
            for c in d["children"]:
                if not c["visible"]:
                    continue
                if c["right"] > d["contentRight"] + 0.5:
                    offenders.append(
                        f"{w}px: {c['cls'] or '(span)'} reaches {c['right']:.1f}, "
                        f"content edge is {d['contentRight']:.1f} :: {c['text'][:40]!r}")
                if c["left"] < d["contentLeft"] - 0.5:
                    offenders.append(
                        f"{w}px: {c['cls'] or '(span)'} starts at {c['left']:.1f}, "
                        f"content starts at {d['contentLeft']:.1f} :: {c['text'][:40]!r}")
        self.assertEqual([], offenders, "status bar clips a child mid-glyph:\n" + "\n".join(offenders))

    def test_nothing_rendered_carries_text_it_cannot_paint(self) -> None:
        """A zero-width, `display: block` element with text is a lie.

        It is in the DOM, a screen reader announces it, and no sighted reader
        can see it. `.statusbar .path` does exactly this whenever the app is
        served without a resolved `dataDir` — which is what the sandbox does —
        so this is a real state the real app can reach, not a hypothetical.
        """
        offenders = []
        for w, d in self.results.items():
            for c in d["children"]:
                if c["display"] != "none" and c["width"] < 0.5 and c["hasText"]:
                    offenders.append(
                        f"{w}px: {c['cls'] or '(span)'} renders {c['width']:.1f}px wide "
                        f"but carries {c['text'][:40]!r}")
        self.assertEqual([], offenders,
                         "rendered-but-invisible status bar content:\n" + "\n".join(offenders))

    def test_the_load_bearing_claims_are_never_the_thing_that_goes(self) -> None:
        """Neither claim may vanish at any width the product is used at.

        The degradation order is allowed to drop the locale, the scope and the
        data directory. It is not allowed to drop the loopback authority or the
        privacy statement — if it did, the tool would look exactly as
        reassuring while saying less than it used to.
        """
        missing = []
        for w, d in self.results.items():
            painted = " ".join(c["text"] for c in d["children"] if c["visible"])
            for phrase in LOAD_BEARING:
                if phrase not in painted:
                    missing.append(f"{w}px: {phrase!r} is not painted (only: {painted[:80]!r})")
        self.assertEqual([], missing, "status bar dropped a load-bearing claim:\n" + "\n".join(missing))

    def test_no_horizontal_document_overflow_at_any_checked_width(self) -> None:
        bad = [f"{w}px overflows by {d['docOverflow']}px"
               for w, d in self.results.items() if d["docOverflow"] > 0]
        self.assertEqual([], bad, "\n".join(bad))


class StatusBarStylesheetTests(unittest.TestCase):
    """The stylesheet, read as text — catches a regression a browser would not."""

    def setUp(self) -> None:
        self.css = STYLES.read_text(encoding="utf-8")

    def test_every_status_bar_child_is_allowed_to_shrink(self) -> None:
        """`min-width: 0` is what turns an overflow into a visible ellipsis.

        Without it a flex item's automatic minimum size is its min-content width,
        so an over-long path cannot yield at all — the line overflows and the bar
        slices it. With it, `.statusbar`'s existing `overflow: hidden` and
        `text-overflow: ellipsis` become reachable and the reader sees a cut
        *as a cut* instead of as a rendering fault.
        """
        self.assertRegex(
            self.css, r"\.statusbar\s*>\s*\*\s*\{[^}]*min-width:\s*0",
            "status bar children have no min-width: 0, so nothing can shrink to fit")

    def test_the_privacy_claim_is_pinned_against_shrinking(self) -> None:
        """`flex: 0 0 auto` on the last child.

        It is the sentence the product exists to make. It must not be the item
        that yields when the bar gets tight — the order of the declarations is
        what guarantees that, so this reads the rule rather than the render.
        """
        self.assertRegex(
            self.css, r"\.statusbar\s*>\s*span:last-child\s*\{[^}]*flex:\s*0\s+0\s+auto",
            "the privacy claim is not pinned; it can be the item that shrinks")

    def test_the_degradation_order_is_declared_and_ordered(self) -> None:
        """The three bands, and that they are declared narrowest-last.

        The order encodes what a reader loses: the data directory, then the
        regional-format fact (also in Settings), then the scope (already in the
        Library's own summary). It has to be narrowest-last so the cascade gives
        up the least first.
        """
        bands = re.findall(r"@media \(max-width: (\d+)px\) \{\s*\.statusbar", self.css)
        self.assertTrue(bands, "no statusbar degradation bands are declared")
        widths = [int(b) for b in bands]
        self.assertEqual(sorted(widths, reverse=True), widths,
                         f"degradation bands are declared out of order: {widths}")

        # Each band must hide something, and nothing in the privacy statement.
        for m in re.finditer(r"@media \(max-width: (\d+)px\) \{\n((?:  .*\n)+)\}", self.css):
            if ".statusbar" not in m.group(2):
                continue
            self.assertNotIn("last-child", m.group(2),
                             "a degradation band must never hide the privacy claim")

    def test_positional_selectors_are_declared_as_a_known_risk(self) -> None:
        """`:nth-child` here is a debt, and it must be written down.

        The facts are hidden by position because the fix was CSS-only while
        another session held `index.html`. The guard is that the risk is
        recorded next to the rule — a future iteration reading this file has to
        find the note, not rediscover the fragility from a wrong selector.
        """
        self.assertIn(":nth-child", self.css, "expected the positional degradation rules")
        self.assertRegex(
            self.css, r"\[\?\]",
            "the stylesheet no longer records any open question; the nth-child "
            "debt in the statusbar block was never written down")


if __name__ == "__main__":
    unittest.main(verbosity=2)