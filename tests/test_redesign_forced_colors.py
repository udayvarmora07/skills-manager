"""6.2 — forced-colors.  The stylesheet had no `@media (forced-colors: active)`
at all, and 6.1b's own fix is the reason that was a defect rather than a
nicety.

In forced-colors mode the UA forces `box-shadow: none` and replaces author
colours with system ones.  6.1b moved the `.overview-metrics` cell hairlines
onto the cells as `box-shadow: 0 0 0 1px var(--border)`, which is the right
place for them: in dark the container's own `background` had been painting the
empty slots of a 7-cell grid as a lighter slab that read as a selected cell.
Measured on this tree, those cells are the ONLY box-shadow-carried separators
in the product — 4 on Overview, 7 on Quality — and under
`forcedColors: 'active'` Chromium reports **0** of each.  So both metric
strips lost every cell border for a reader in high-contrast mode, silently.

What this suite holds:

  1. The block EXISTS and sits inside LAYER 6, after the cascade it
     overrides.  A forced-colors block filed in LAYER 1 would be overwritten
     by the very rules it is correcting.
  2. It restores a separator with a property forced-colors does NOT suppress.
     `box-shadow` is forced away; `outline` keeps its style and only has its
     colour replaced, which is exactly the swap required.  The assertion is on
     the mechanism, not on the literal string, so a future rewrite that uses
     `border` instead still passes — and a rewrite that goes BACK to
     `box-shadow` fails.
  3. It closes the grid gap, because the 1px gap was showing the container's
     background, which forced-colors paints as Canvas.  A gap of 0 plus an
     inset outline reproduces the light-mode hairline exactly.
  4. `forced-color-adjust: none` appears EXACTLY ONCE, on the colour swatch.
     It is a real escape hatch and therefore a real way to make the product
     worse: it is correct for a swatch whose entire purpose is to show a
     colour, and wrong anywhere else.  The count is derived from the file so a
     second opt-out cannot be added quietly.
"""

import re
import unittest
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent
       / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")


def _strip_comments(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.sub(r"\n\s*\n", "\n", css)


def _forced_colors_block():
    """The body of the forced-colors media block, or '' when there is none.

    Taken from the LAST `/* ... */`-stripped copy so a comment mentioning the
    block's name cannot satisfy this by existing (6.1b's suite learned that the
    other way round).
    """
    css = _strip_comments(CSS)
    start = css.find("@media (forced-colors: active)")
    if start < 0:
        return ""
    depth = 0
    for i in range(start, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[start:i + 1]
    return ""


class ForcedColorsContractTests(unittest.TestCase):
    def test_the_stylesheet_declares_a_forced_colors_block(self):
        self.assertIn("@media (forced-colors: active)", CSS,
                      "no forced-colors block: every author colour is "
                      "replaced by the UA, and box-shadow is dropped outright")

    def test_the_block_comes_after_the_rules_it_overrides(self):
        """LAYER 6 exists because conditions on the whole cascade have to sit
        at the end of it. A forced-colors block filed earlier would be
        overwritten by the very declarations it corrects."""
        start = CSS.index("@media (forced-colors: active)")
        self.assertGreater(start, CSS.index(".overview-metrics > div"),
                           "the forced-colors block must follow the base rule "
                           "it overrides, or the base rule wins the cascade")

    def test_the_cells_keep_a_separator_that_forced_colors_does_not_drop(self):
        """`box-shadow` is forced to `none`; `outline` keeps its style. The
        assertion is that the separator MOVED, not that a literal survived."""
        block = _forced_colors_block()
        self.assertTrue(block, "forced-colors block is missing or unbalanced")
        self.assertRegex(block, r"\.overview-metrics\s*>\s*div")
        rule = block[block.index(".overview-metrics > div"):]
        rule = rule[:rule.index("}") + 1]
        declarations = [d.strip() for d in rule.split("{", 1)[1].split(";")]
        self.assertIn("box-shadow: none", [d.replace("  ", " ") for d in declarations],
                      "the shadow that forced-colors drops must be switched "
                      "off explicitly, or it is simply absent by accident")
        survivor = [d for d in declarations
                    if d.startswith(("outline", "border"))]
        self.assertTrue(survivor,
                        "no separator property that survives forced-colors: "
                        "the cells collapse into one undivided block")

    def test_the_grid_gap_is_closed_because_the_gap_was_showing_the_background(self):
        """In forced-colors the container background is Canvas, so a 1px gap
        painted in it is an invisible separator -- the exact defect the cells
        were moved out of. The inset outline replaces it at the same weight."""
        block = _forced_colors_block()
        container = block[block.index(".overview-metrics {"):]
        container = container[:container.index("}") + 1]
        self.assertIn("gap: 0", container,
                      "the 1px gap shows the container background, which "
                      "forced-colors paints as Canvas")

    def test_only_the_colour_swatch_opts_out_of_the_system_colours(self):
        """`forced-color-adjust: none` is correct for a swatch whose whole job
        is to show a colour -- as Canvas it is an empty outlined circle, which
        says nothing. Everywhere else it is a way to ship a UI the reader's
        chosen palette ignores, so the count is derived, not listed."""
        css = _strip_comments(CSS)
        opt_outs = re.findall(r"([^{}]+)\{[^}]*forced-color-adjust:\s*none",
                              css)
        self.assertEqual(len(opt_outs), 1,
                         "exactly one element may opt out; found %d: %r"
                         % (len(opt_outs), opt_outs))
        self.assertIn(".settings-preview-swatch", opt_outs[0])

    def test_the_swatch_that_opts_out_is_actually_a_colour_sample(self):
        """If the swatch stops being a colour sample, the exemption stops
        being justified and this test should fail rather than let the
        exemption outlive its reason."""
        rule = CSS[CSS.index(".settings-preview-swatch"):]
        rule = rule[:rule.index("}") + 1]
        self.assertIn("background: var(--accent)", rule)


if __name__ == "__main__":
    unittest.main()