"""9.1d — the banner family's two declarations of membership, and neither held.

`.banner-info` had a complete rule and **zero** call sites; `.banner-success` had
a call site and **no rule at all**, so the Install panel's committed banner
rendered as the unstyled base `.banner` carrying a green check glyph. Both halves
of one set were wrong in opposite directions, on the same day, in the same block.

Neither was visible to a gate that already existed:

- ``check_unread_tokens`` (9.1a) counts ``var(--x)`` readers, so it cannot see an
  unread *selector*. ``.banner-info`` reads four tokens perfectly.
- ``test_redesign_banner_border`` measures a level it already knows about, so a
  level it does not know about cannot be unstyled in front of it.

So the vocabulary is DERIVED here, from both files, in both directions:

- declared = a ``.banner-<word>`` rule that paints a ``background`` (a tinted
  banner is what a level IS; the base ``.banner`` sets one too and is excluded
  because its selector has no ``-``)
- used = a ``banner-<word>`` class token in the markup

Both are read from strings the tests take as arguments, so the controls below can
inject the two shipped defects back into a copy and require the same arithmetic to
refuse them. Every helper strips CSS comments FIRST: the banner block's own prose
discusses these four names, and a gate that reads prose is this repo's sixth
recorded failure.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "skillsmgr" / "webui" / "styles.css"
HTML_PATH = ROOT / "skillsmgr" / "webui" / "index.html"
APP_PATH = ROOT / "skillsmgr" / "webui" / "app.js"

# A class token that is a LEVEL: `banner-ok`, `banner-info`. Excludes the base
# `banner`, the modifiers (`banner-body`, `banner-title`, `banner-actions`,
# `banner.flush`) and the glyph carriers (`banner-icon-ok`, which has a second
# hyphen) without any hand-kept list of them.
LEVEL_TOKEN = re.compile(r"\bbanner-([a-z]+)\b")

# A level's rule paints a background. Deliberately not "declares border-color":
# the intent is what makes a banner a level, not which of its three declarations
# happens to be spelled out.
_LEVEL_RULE = re.compile(r"\.banner-([a-z]+)\s*\{([^}]*)\}")


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _strip_html_comments(html: str) -> str:
    """Vue template comments carry the reasoning for a call site, and the
    reasoning NAMES the level it is reasoning about. Counting prose as a call
    site is the direction that lets a defect through; it is also how the first
    run of this file failed on its own edit."""
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def declared_levels(css: str) -> set:
    """Levels the stylesheet gives a rule to."""
    stripped = _strip_comments(css)
    return {
        level
        for level, body in _LEVEL_RULE.findall(stripped)
        if re.search(r"(?<!-)background\s*:", body)
    }


def used_levels(html: str) -> set:
    """Levels the markup asks for, read from class attributes only."""
    return set(LEVEL_TOKEN.findall(_strip_html_comments(html)))


def dynamic_types(js: str) -> set:
    """The `banner.type` values app.js can actually assign.

    The three global banners bind their class from `banner.type`, so a type the
    stylesheet does not declare renders as the unstyled base — the same failure
    as a literal unknown class, reached through a different door.
    """
    return set(re.findall(r"type:\s*([^,\n}]+)", _strip_comments(js)))


class DeclaredIsRendered(unittest.TestCase):
    """9.1d's own defect: a complete rule no call site ever reaches."""

    def test_every_declared_level_renders_somewhere_in_the_markup(self):
        html = HTML_PATH.read_text(encoding="utf-8")
        css = CSS_PATH.read_text(encoding="utf-8")
        declared, used = declared_levels(css), used_levels(html)
        self.assertTrue(declared, "no level was derived — the check is vacuous")
        orphans = declared - used
        self.assertEqual(
            orphans,
            set(),
            f"declared and never rendered: {sorted(orphans)}. A level nothing "
            "renders cannot be photographed, cannot be contrast-checked by a "
            "reader, and reads as coverage.",
        )
        self.assertGreaterEqual(
            len(used), 4, f"only {len(used)} levels found: {sorted(used)} — the "
            "markup scan found fewer than the family declares"
        )


class RenderedIsDeclared(unittest.TestCase):
    """The opposite half: `.banner-success`, which rendered as the base class."""

    def test_every_level_the_markup_asks_for_has_a_rule(self):
        html = HTML_PATH.read_text(encoding="utf-8")
        css = _strip_comments(CSS_PATH.read_text(encoding="utf-8"))
        unstyled = {
            level
            for level in used_levels(html)
            if not re.search(r"\.banner-" + re.escape(level) + r"\b", css)
        }
        self.assertEqual(
            unstyled,
            set(),
            f"rendered with no rule: {sorted(unstyled)}. It paints the base "
            "`.banner` — grey surface, `var(--border)` hairline — while carrying "
            "the level's glyph, which is the `banner-warn` defect 2.3 fixed, "
            "still live in the other direction.",
        )

    def test_a_dynamic_banner_type_always_has_a_rule(self):
        """The same failure reached through `banner.type` instead of a class."""
        css = CSS_PATH.read_text(encoding="utf-8")
        js = APP_PATH.read_text(encoding="utf-8")
        types = dynamic_types(js)
        self.assertTrue(types, "no banner.type producer was found — the scan is vacuous")
        undeclared = set()
        for expression in types:
            undeclared |= set(re.findall(r'"([a-z]+)"', expression))
        self.assertLessEqual(
            undeclared,
            declared_levels(css),
            f"app.js can set banner.type to {sorted(undeclared - declared_levels(css))}, "
            "which the stylesheet gives no rule — the three global banners bind "
            "their class from this value",
        )


class TheFloorCanFail(unittest.TestCase):
    """Controls. Two shipped defects re-injected, through the same arithmetic."""

    def test_a_level_with_no_call_site_is_rejected(self):
        html = HTML_PATH.read_text(encoding="utf-8").replace("banner-info", "banner-ok")
        self.assertEqual(
            declared_levels(CSS_PATH.read_text(encoding="utf-8")) - used_levels(html),
            {"info"},
            "removing every `banner-info` call site must make the orphan check "
            "name exactly that level",
        )

    def test_a_call_site_with_no_rule_is_rejected(self):
        html = HTML_PATH.read_text(encoding="utf-8").replace(
            'class="banner banner-ok install-fetch-banner"', 'class="banner banner-success install-fetch-banner"'
        )
        self.assertIn("success", used_levels(html))
        css = _strip_comments(CSS_PATH.read_text(encoding="utf-8"))
        self.assertNotRegex(css, r"\.banner-success\b")


if __name__ == "__main__":
    unittest.main()