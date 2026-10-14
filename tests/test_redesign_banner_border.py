"""9.1c — a banner's border is its TEXT step, and the `-line` steps are hairlines.

The backlog row that produced this file proposed one declaration: change
`.banner-ok`'s border from `var(--ok)` to `var(--ok-line)`, because `--ok-line`
was declared in both themes and read by nothing while its three siblings in the
warn/err families were read elsewhere.

Measured, that proposal is a 4:1 contrast regression in both themes. Against
its own `--ok-bg`:

    step      light   dark
    --ok       5.35   7.16   <- what the banner paints
    --ok-line  1.32   1.37   <- what the row proposed

Every `-line` step behaves the same way (warn 1.38/1.38, err 1.45/1.26, mute
1.33/1.33), which is the actual finding: the `-line` family draws separators
INSIDE a tinted block, not the block's own edge. So `--ok-line` was deleted
from both themes rather than adopted.

These assertions exist so that nobody re-derives this by reading a token list.
The CONTRAST FLOOR is the primary one and the token identity the secondary,
because a floor is the property that actually matters: it fails for a wrong
token, for a token whose value is retuned into invisibility, and for a
`-line` step adopted in the banner's place. The secondary assertion is stated
as a floor and not as an equality, so retuning `--ok` darker is allowed.
"""

import re
import unittest
from pathlib import Path

from check_design_tokens import contrast, read_block

ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "skillsmgr" / "webui" / "styles.css"
HTML_PATH = ROOT / "skillsmgr" / "webui" / "index.html"

LIGHT_OPENER = '[data-theme="light"], [data-theme="system"] {'
DARK_OPENER = '[data-theme="dark"] {'

# The floor is WCAG 1.4.11's 3:1 for a boundary that identifies a thing, with
# margin. A banner is already told apart by its tint, so its border is the step
# that has to READ at 1px rather than merely be present.
MIN_BORDER_CONTRAST = 3.0

# level -> (text step, background step). `.banner-info` rides the accent pair.
BANNERS = (
    ("error", "err", "err-soft"),
    ("ok", "ok", "ok-soft"),
    ("warn", "warn", "warn-soft"),
    ("info", "accent-text", "accent-soft"),
)

# The `-soft` names are legacy aliases (1.4 retired the `--t-*` role aliases in
# the same way); resolve them the way the cascade does rather than assuming.
ALIASES = {
    "err-soft": "err-bg",
    "ok-soft": "ok-bg",
    "warn-soft": "warn-bg",
    "accent-soft": "accent-bg",
    "accent-text": "accent",
}

CSS_TEXT = CSS_PATH.read_text(encoding="utf-8")


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _banner_rule(css: str, level: str) -> str:
    """The single declaration block for `.banner-<level>`, comments removed."""
    match = re.search(
        r"\.banner-" + level + r"\s*\{([^}]*)\}", _strip_comments(css)
    )
    if match is None:
        raise AssertionError(f".banner-{level} has no rule — the banner is unstyled")
    return match.group(1)


class OkLineIsGone(unittest.TestCase):
    """The deletion is the deliverable; it must not creep back in a re-tune."""

    def test_ok_line_is_not_declared_in_either_theme(self):
        for opener in (LIGHT_OPENER, DARK_OPENER):
            with self.subTest(opener=opener):
                self.assertNotIn("--ok-line", read_block(CSS_PATH.read_text(), opener))

    def test_ok_line_is_not_read_anywhere_in_the_cascade(self):
        # Vacuous if the token is gone, and that is the point: the check proves
        # no later change reintroduced a reader for a token nobody declares.
        self.assertEqual(re.findall(r"var\(--ok-line\)", _strip_comments(CSS_TEXT)), [])


class BannerBordersAreTheTextStep(unittest.TestCase):
    def setUp(self):
        self.themes = {
            "light": read_block(CSS_TEXT, LIGHT_OPENER),
            "dark": read_block(CSS_TEXT, DARK_OPENER),
        }

    def test_every_banner_border_clears_the_boundary_floor(self):
        """The assertion the proposed fix would have failed, in both themes."""
        checked = 0
        for level, text_step, bg_step in BANNERS:
            rule = _banner_rule(CSS_TEXT, level)
            match = re.search(r"border-color:\s*var\((--[\w-]+)\)", rule)
            self.assertIsNotNone(match, f".banner-{level} paints no token border")
            for theme, tokens in self.themes.items():
                with self.subTest(level=level, theme=theme):
                    border = "--" + ALIASES.get(
                        match.group(1).lstrip("-"), match.group(1).lstrip("-")
                    )
                    bg = "--" + ALIASES.get(bg_step, bg_step)
                    self.assertIn(border, tokens, f"{border} is not a theme token")
                    self.assertIn(bg, tokens, f"{bg} is not a theme token")
                    ratio = contrast(tokens[border], tokens[bg])
                    self.assertGreaterEqual(
                        ratio,
                        MIN_BORDER_CONTRAST,
                        f".banner-{level} border {border} on {bg} is {ratio:.2f}:1 "
                        f"in {theme} — below {MIN_BORDER_CONTRAST}:1",
                    )
                    checked += 1
        self.assertEqual(checked, len(BANNERS) * 2, "a banner level did not measure")

    def test_no_banner_paints_a_line_step_as_its_edge(self):
        """The secondary claim, stated as the specific mistake this row made."""
        for level, _, _ in BANNERS:
            with self.subTest(level=level):
                rule = _banner_rule(CSS_TEXT, level)
                border = re.search(r"border-color:\s*var\((--[\w-]+)\)", rule)
                self.assertIsNotNone(border, f".banner-{level} paints no token border")
                self.assertFalse(
                    border.group(1).endswith("-line"),
                    f".banner-{level} paints {border.group(1)}; the `-line` steps "
                    "are hairlines for separators INSIDE a tinted block "
                    "(1.32-1.45:1 against their own background), not its edge",
                )


class TheFloorCanFail(unittest.TestCase):
    """The control. A floor nobody has seen reject anything is not a floor."""

    def test_the_proposed_substitution_is_rejected(self):
        # Re-create the exact declaration 9.1c was written to prevent, against
        # the shipped values, and require the same arithmetic to refuse it.
        for theme, opener in (("light", LIGHT_OPENER), ("dark", DARK_OPENER)):
            with self.subTest(theme=theme):
                tokens = read_block(CSS_TEXT, opener)
                # `--ok-line`'s shipped values, from the pre-9.1c stylesheet.
                ok_line = "#c3d6c3" if theme == "light" else "#2a3a2a"
                ok_bg = tokens["--ok-bg"]
                self.assertLess(
                    contrast(ok_line, ok_bg),
                    MIN_BORDER_CONTRAST,
                    f"the rejected value now PASSES in {theme} — either the "
                    "floor is too low or the palette was retuned; re-measure "
                    "before trusting this control",
                )
                self.assertGreaterEqual(contrast(tokens["--ok"], ok_bg), MIN_BORDER_CONTRAST)


class TheSubjectRenders(unittest.TestCase):
    """A rule nothing renders cannot be photographed and must not be trusted."""

    def test_banner_ok_is_in_the_markup_not_just_the_stylesheet(self):
        html = HTML_PATH.read_text(encoding="utf-8")
        self.assertRegex(html, r'class="[^"]*\bbanner-ok\b')

    def test_the_banner_levels_this_file_measures_are_the_shipped_vocabulary(self):
        html = HTML_PATH.read_text(encoding="utf-8")
        used = set(re.findall(r"\bbanner-(ok|warn|error|info)\b", html))
        self.assertEqual(
            used - {level for level, _, _ in BANNERS},
            set(),
            "a banner level renders that this file does not measure",
        )




if __name__ == "__main__":
    unittest.main()