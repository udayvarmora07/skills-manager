"""6.1 — the dark theme is the palette, not a second set of colours beside it.

A "dark theme full pass" is not a look. It is a claim that every colour the UI
paints resolves through the token layer, in both themes, with no one-off value
sitting outside either theme block where no gate can see it.

**The measurement that started this.** Scanning `styles.css` (comments
stripped) for a hard-coded hex / rgb / hsl found 58 hits: 56 are the two
palettes in LAYER 1, and **two** were in the cascade.

    [data-theme="dark"] .navigation-rail { background: #1b1f27; }
    .batchbar { box-shadow: 0 -6px 16px -12px rgb(0 0 0 / 45%); }

Both are dark-relevant, and neither was a style opinion:

1. **`#1b1f27` is a fifth dark surface.** The dark palette declares exactly
   four: `--bg` #101316, `--surface` #171a1e, `--surface-2` #1e2227,
   `--surface-3` #272c32. The navigation rail - the one chrome column every
   reader looks at all day - painted a colour belonging to none of them and
   answering to no token. It is also a v1 value that predates the measured
   palette 1.3 shipped, so it survived that rewrite: 1.4's parity gate asserts
   the two theme blocks declare the same token set, and a rule OUTSIDE both
   blocks is invisible to it. That is this repository's own recorded class - a
   gate reporting PASS about a path it cannot see - found twice already in the
   token layer and now here.

   Two consequences, both measured rather than argued. The rail was
   `--surface-2` in LIGHT and `#1b1f27` in DARK, so the same column changed
   colour with the theme while no token recorded that it had. And below 761px
   the drawer band sets `background: var(--surface-2)` and OVERRODE it, so one
   element was two different colours either side of the drawer breakpoint.

2. **The batch bar's shadow contradicted the rule's own comment.** 4.3 slice A
   states directly above that rule that the bar "is a FLEX ITEM, not an
   overlay, so the list shrinks to make room". A shadow says "this floats above
   the page". It did not float. It was also the file's second shadow definition
   after `--shadow` / `--shadow-lg`, written as a raw rgba rather than a token,
   which puts it outside DESIGN.md's "One shadow token for popovers+dialogs
   only". In dark the same light-theme alpha over `--surface` on `--bg` lifted
   the bar by approximately nothing, so the one cue meant to separate the bar
   from the list was the one cue the dark theme erased.

**Why these are source assertions and not screenshots.** A capture shows what a
surface looks like; it cannot show that the colour answering it is not in the
palette. `#1b1f27` sits between `#171a1e` and `#1e2227` and renders as a
perfectly plausible dark panel - a screenshot review passed it, which is
precisely why it survived a measured palette rewrite.

**A third `[data-theme="dark"]` rule exists and is CORRECT**, which is why the
first version of this file failed and why its failure is worth keeping in the
reasoning: `[data-theme="dark"] .sidebar.list-pane` sets `background: var(--bg)`
and `border-right-color: var(--border-strong)`. A per-component theme override
that resolves through tokens is legitimate - the list pane wants a different
TOKEN in dark. What is forbidden is a per-component theme override carrying a
raw colour, because that is a value neither theme block declares. The
assertion is therefore about the raw colour, not about the count of theme
rules, which a counting assertion would get wrong in the direction that makes
the check unadoptable.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "skillsmgr" / "webui" / "styles.css").read_text(encoding="utf-8")

# Every hard-coded colour spelling a stylesheet can use.
_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(")
# A custom property's own declaration IS the token layer, wherever it sits.
_TOKEN_DECL = re.compile(r"^\s*--[\w-]+\s*:")

# Comments are stripped BEFORE anything is measured, for the reason 1.6's floor
# check recorded: a guard that scans raw CSS including comments fails on prose
# that merely mentions the thing, and the fix people reach for is to weaken the
# assertion rather than reword the prose. Both fixes below QUOTE the selector
# and the rgba they remove, on purpose - an unstripped scan fails on its own
# explanation, which is how a correct fix gets reverted.
_STRIPPED = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"),
                   CSS, flags=re.S)


def _is_palette(text):
    """True for a line that declares a custom property (the token layer)."""
    return bool(_TOKEN_DECL.match(text))


class TheCascadeDeclaresNoColourOfItsOwn(unittest.TestCase):
    def _offenders(self):
        return [(i, l.strip()) for i, l in enumerate(_STRIPPED.split("\n"), 1)
                if _COLOUR.search(l) and not _is_palette(l)]

    def test_no_hard_coded_colour_outside_the_token_declarations(self):
        offenders = self._offenders()
        self.assertEqual(
            offenders, [],
            "every colour below the palettes must resolve through a token; a "
            "raw value is invisible to the two-theme parity gate because it is "
            "in neither theme block: %r" % offenders)

    def test_no_theme_override_outside_the_palettes_carries_a_raw_colour(self):
        # Derived rather than counted. A third theme rule that resolves through
        # tokens is legitimate (the list pane wants `--bg` in dark); one that
        # carries `#1b1f27` is a colour no palette declares.
        bodies = re.findall(r'\[data-theme="(?:dark|light)"\][^{]*\{([^}]*)\}',
                            _STRIPPED)
        raw = [b.strip() for b in bodies
               if any(_COLOUR.search(l) and not _is_palette(l)
                      for l in b.split("\n"))]
        self.assertEqual(raw, [],
                         "a per-component theme override must choose a TOKEN, "
                         "not a colour: %r" % raw)

    def test_the_scan_is_measuring_something(self):
        # The control for the assertion above. If the palettes were renamed,
        # moved, or emptied, "no offenders" would be indistinguishable from
        # "the scan matched nothing" - the failure mode 1.7 recorded four
        # times. The palettes must still be the only place raw colours live.
        self.assertGreater(len(self._offenders()) + len(
            [1 for l in _STRIPPED.split("\n")
             if _COLOUR.search(l) and _is_palette(l)]), 40,
            "the palette itself went missing - the scan is not measuring what "
            "it claims to measure")


class TheRailIsTheSameSurfaceInBothThemes(unittest.TestCase):
    """The specific defect: one chrome column that changed colour with the theme."""

    def test_there_is_no_dark_override_for_the_rail(self):
        self.assertNotIn('[data-theme="dark"] .navigation-rail', _STRIPPED,
                         "the rail paints a fifth dark surface that belongs to "
                         "no palette entry; the base rule already says "
                         "var(--surface-2)")

    def test_the_base_rule_resolves_the_rail_through_a_token(self):
        m = re.search(r"^\.navigation-rail \{(.*?)^\}", _STRIPPED, re.M | re.S)
        self.assertIsNotNone(m, "the rail's base rule was not found")
        self.assertIn("background: var(--surface-2);", m.group(1),
                      "the rail must resolve its background through the token "
                      "so both themes get it from the palette")


class ShadowsBelongToTheToken(unittest.TestCase):
    """DESIGN.md: one shadow token, for popovers and dialogs only."""

    def test_every_box_shadow_in_the_cascade_resolves_through_a_token(self):
        # `box-shadow: none` is the REMOVAL of a shadow, not a second
        # definition of one, so it is exempt - but it is named here rather
        # than filtered silently, because it is also the shape a rule takes
        # when it is cancelling someone else's elevation cue.
        offenders = [(i, l.strip()) for i, l in enumerate(_STRIPPED.split("\n"), 1)
                     if "box-shadow" in l and "var(--" not in l
                     and "box-shadow: none" not in l]
        self.assertEqual(offenders, [],
                         "a raw shadow is a second definition of depth that no "
                         "theme can measure: %r" % offenders)

    def test_the_shadow_tokens_are_still_defined_in_both_themes(self):
        # `--focus-ring` is a shadow by another name and is declared in both
        # blocks; this asserts the token a rule points at exists at all, so
        # `var(--shadow)` cannot become a no-op that silently removes every
        # elevation cue in the product.
        names = set(re.findall(r"(--[\w-]+):\s*0 (?:1px|8px|10px|0px)", _STRIPPED))
        self.assertTrue({"--shadow", "--shadow-lg"} <= names,
                        "the shadow tokens are gone: %r" % names)


if __name__ == "__main__":
    unittest.main()