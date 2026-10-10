"""The stylesheet's layer order is a contract, so it is checked like one.

`styles.css` is read in six layers (see the file header and DESIGN.md). The
order is not a matter of taste: tokens must exist before anything consumes
them, and a global primitive must be able to override a component. Nothing in
the product observes the layers directly, so nothing would notice if a later
edit merged them back into one 2,000-line list — which is what happened once
already, and why the file carried a `topbar` banner next to a `modals` banner
with no relationship between them.

So this gate asserts the structure rather than the styling:

* the seven banners exist, exactly once each, in order;
* the primitives that belong to the utilities layer are actually in it;
* the retired type-role aliases stay retired (they were a migration seam that
  outlived its migration, and a name nothing resolves is worse than no name);
* both theme blocks declare the same tokens, so neither can grow a private
  colour the other silently lacks;
* the reduced-motion hook stays the last thing in the file and still covers
  iteration count, which it once did not.

Red-first for the ordering check: reordering two banners or duplicating one
fails here. A stylesheet with no banners at all fails too.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "skillsmgr" / "webui" / "styles.css"

LAYERS = (
    (0, "PRELUDE"),
    (1, "TOKENS"),
    (2, "RESET"),
    (3, "TYPOGRAPHY"),
    (4, "UTILITIES"),
    (5, "COMPONENTS"),
    (6, "RESPONSIVE"),
)


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def _block_body(css: str, opener: str) -> str:
    """Return the declarations inside the first block opened by ``opener``."""
    start = css.index(opener) + len(opener)
    depth = 1
    for index in range(start, len(css)):
        char = css[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return css[start:index]
    raise AssertionError(f"unterminated block: {opener!r}")


def _banner_offsets(css: str) -> dict[int, int]:
    """Character offset of each layer banner.

    Offsets, not line numbers: every comparison below is against
    ``css.index(...)``, which is a character offset. The first version of this
    gate returned line numbers and compared them to offsets, so "the skip link
    is below the components layer" failed while the file plainly had it in the
    utilities layer. Both units were right in isolation and wrong together.
    """
    found: dict[int, int] = {}
    for number, name in LAYERS:
        pattern = re.compile(
            r"^/\* =+ LAYER " + str(number) + r"\n\s+" + name + r"\b", re.M)
        hits = list(pattern.finditer(css))
        if len(hits) != 1:
            raise AssertionError(
                f"expected exactly one 'LAYER {number} {name}' banner, "
                f"found {len(hits)}")
        found[number] = hits[0].start()
    return found


class StylesheetLayerContract(unittest.TestCase):
    def setUp(self) -> None:
        self.css = _css()

    def test_seven_layer_banners_exist_once_and_in_order(self):
        offsets = _banner_offsets(self.css)
        ordered = [offsets[number] for number, _ in LAYERS]
        self.assertEqual(ordered, sorted(ordered),
                         "layer banners are not in declared order: %r" % (offsets,))
        self.assertEqual(len(set(ordered)), len(LAYERS),
                         "two layers start at the same offset")

    def test_the_header_declares_the_same_layer_order_the_banners_use(self):
        # Cut at the LAYER 0 banner, not at "@import": the header itself
        # mentions @import while describing the prelude, so slicing on it
        # truncated the list mid-way and reported a missing layer that was
        # plainly on screen. The first version of this test did exactly that.
        header = self.css[:self.css.index("LAYER 0")]
        for number, name in LAYERS:
            self.assertIn(f"{number} {name}", header,
                          f"layer {number} {name} is not declared in the header")

    def test_reset_and_typography_rules_sit_in_their_declared_layers(self):
        lines = _banner_offsets(self.css)
        # `#app` is the document box the shell fills; it belongs to the shell's
        # reset, not to TYPOGRAPHY, and this asserts the weaker true fact —
        # that it sits above the utilities and below the reset — because the
        # stronger one is not true of the shipped order.
        document_box = self.css.index("#app {")
        # Anchor on the standalone rule: a bare "body {" also matches inside
        # the `html, body {` selector in RESET, which is how the first run
        # reported body as being above the typography banner.
        body_rule = self.css.index("\nbody {")
        self.assertGreater(document_box, lines[2], "the document box left RESET")
        self.assertLess(document_box, lines[4], "the document box is below UTILITIES")
        self.assertGreater(body_rule, lines[3], "body is not in TYPOGRAPHY")
        self.assertLess(body_rule, lines[4], "body is below UTILITIES")

    def test_shared_primitives_live_in_the_utilities_layer(self):
        lines = _banner_offsets(self.css)
        for selector in (".skip-link {", ".sr-only {", ":focus-visible {"):
            position = self.css.index(selector)
            self.assertGreater(position, lines[4],
                               f"{selector} is not in the UTILITIES layer")
            self.assertLess(position, lines[5],
                            f"{selector} is below the COMPONENTS layer")

    def test_each_utility_is_declared_once(self):
        # A helper declared in two places is one override waiting to happen,
        # and the cascade that wins depends on which block a later edit lands in.
        for selector in (".skip-link {", ".sr-only {"):
            self.assertEqual(self.css.count(selector), 1,
                             f"{selector} is declared more than once")

    def test_retired_type_role_aliases_stay_retired(self):
        for name in ("--t-display", "--t-title", "--t-head", "--t-body", "--t-sm"):
            self.assertNotRegex(self.css, re.escape(name) + r"\s*:",
                                f"{name} was retired as dead; it must not come back")

    def test_both_themes_declare_the_same_tokens(self):
        light = set(re.findall(r"(--[a-z0-9-]+)\s*:", _block_body(
            self.css, '[data-theme="light"], [data-theme="system"] {')))
        dark = set(re.findall(r"(--[a-z0-9-]+)\s*:", _block_body(
            self.css, '[data-theme="dark"] {')))
        self.assertTrue(light and dark)
        self.assertEqual(light - dark, set(),
                         "tokens only in light: %r" % sorted(light - dark))
        self.assertEqual(dark - light, set(),
                         "tokens only in dark: %r" % sorted(dark - light))

    def test_there_is_still_exactly_one_reduced_motion_hook_and_it_is_last(self):
        start = self.css.index("@media (prefers-reduced-motion: reduce)")
        self.assertEqual(self.css.count("@media (prefers-reduced-motion: reduce)"), 1)
        body = _block_body(self.css, "@media (prefers-reduced-motion: reduce) {")
        for prop in ("animation-duration", "animation-iteration-count",
                     "transition-duration"):
            self.assertIn(prop, body,
                          f"reduced motion must also neutralise {prop}")

    def test_text_size_hook_scales_the_document_and_not_one_selector(self):
        # The hook changes `html`, so rem-based rules scale with it. Targeting
        # `body` as well would double-apply; that regression is pinned in
        # tests/test_webui_contracts.py and this gate exists so the two halves
        # stay visible together.
        self.assertIn('html[data-text-size="large"] { font-size: 1.125rem; }', self.css)
        self.assertNotIn("html[data-text-size=\"large\"] body", self.css)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
