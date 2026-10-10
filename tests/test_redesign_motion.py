"""Motion contracts (redesign task 2.1d).

Why this file exists
--------------------
Task 2.1d. ``check_design_tokens.py`` had shipped a motion check that read the
``--dur`` token — and **nothing in the cascade read it**. The three entrance
animations carried raw ``0.15s`` / ``0.18s`` / ``0.18s``, so the gate reported
PASS about a path it could not see (this repository's fourth recorded instance
of its own failure mode) while ``.modal`` ran 180ms, **20ms outside** the
100-160ms band the gate claimed to enforce.

The product half of the defect: a ``.menu`` is an opaque surface — background,
hairline border, shadow — and fading it from ``opacity: 0`` shows the page
through the reader's own menu for its whole entrance. One screenshot in this
repo's evidence directory was captured at ``opacity: 0.386`` and read as a
rendering fault. DESIGN-V2 §H permits opacity and a ≤4px translateY on
popovers, so the fade was *permitted* and still wrong: it is the wrong half of a
permission, on a surface that has an edge to lose.

These tests assert the properties, not the copy: a surface rises without
touching opacity, the scrim and the toast may fade, and no finite duration is a
literal. Each was written to be able to FAIL — which is checked in
TEST-CHANGES.md, because three of this repo's earlier "new" tests could not.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CSS_PATH = ROOT / "skillsmgr" / "webui" / "styles.css"
GATE_PATH = ROOT / "check_design_tokens.py"

MOTION_MIN_MS, MOTION_MAX_MS = 100, 160
# The only keyframes allowed to touch opacity, and why each one may.
#   fade      — the modal scrim: a wash over the page, not a surface.
#   toast-in  — new content arriving, which is what §H's "no entrance animation
#               on page content" is actually about.
#   spin/shimmer — progress loops, filtered out before this set is consulted.
OPACITY_ALLOWED = {"fade", "toast-in"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), css, flags=re.S)


def _keyframes(css: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r"@keyframes\s+([A-Za-z_][\w-]*)\s*\{", css):
        depth, i = 1, m.end()
        while i < len(css) and depth:
            depth += 1 if css[i] == "{" else (-1 if css[i] == "}" else 0)
            i += 1
        out[m.group(1)] = css[m.end():i - 1]
    return out


def _rule_bodies(css: str, selector: str) -> list[str]:
    """Every declaration block whose prelude is exactly ``selector``, in source
    order.

    All of them, not the first and not the last. ``.modal`` is declared twice —
    once in the cascade and once inside a narrow-viewport media query — and a
    helper that returned one of them answered a question nobody asked: which
    single block carries the entrance. The property that matters is "no rule
    for this selector animates opacity", which needs every block."""
    out = []
    for m in re.finditer(r"(?<![\w.-])" + re.escape(selector) + r"\s*\{", css):
        depth, i = 1, m.end()
        while i < len(css) and depth:
            depth += 1 if css[i] == "{" else (-1 if css[i] == "}" else 0)
            i += 1
        out.append(css[m.end():i - 1])
    if not out:
        raise AssertionError(f"no rule for {selector!r} in the cascade")
    return out


def _rule_body(css: str, selector: str) -> str:
    """All blocks for ``selector``, joined. A property absent from the join is
    absent from the cascade; one present in any block is present."""
    return "\n".join(_rule_bodies(css, selector))


class MotionSurfaceTests(unittest.TestCase):
    """An opaque surface rises; it never fades."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.css = _read(CSS_PATH)
        cls.scan = _strip_comments(cls.css)
        cls.frames = _keyframes(cls.css)

    def test_the_shared_surface_curve_animates_translate_only(self):
        """`rise` is what both `.menu` and `.modal` use. If it fades, every
        surface in the app does, and the assertion below (which reads the
        classes) would still pass — so the curve itself is checked."""
        body = self.frames.get("rise", "")
        self.assertTrue(body, "@keyframes rise is missing: .menu and .modal both use it")
        self.assertNotRegex(body, r"(^|[;{\s])opacity\s*:",
                            "the surface curve fades opacity — that is the defect 2.1d fixed")
        self.assertIn("translateY(4px)", body,
                      "rise must be the <=4px translateY DESIGN-V2 section H permits")

    def test_the_rise_is_within_the_four_pixel_ceiling(self):
        body = self.frames["rise"]
        px = [int(m) for m in re.findall(r"translateY\((-?[\d.]+)px\)", body)]
        self.assertTrue(px, f"rise has no translateY: {body!r}")
        for value in px:
            self.assertLessEqual(abs(value), 4,
                                 f"rise translates {value}px; §H caps a popover at 4px")

    def test_a_popover_and_a_dialog_never_animate_opacity(self):
        """Reads the selectors, not the curve name: renaming `rise` must not
        make this vacuous, and reintroducing a fade under a NEW keyframe must
        still fail here."""
        for selector in (".menu", ".modal"):
            body = _rule_body(self.scan, selector)
            name = re.search(r"animation:\s*([A-Za-z_][\w-]*)", body)
            self.assertIsNotNone(name, f"{selector} has no entrance animation to audit")
            frame = self.frames.get(name.group(1), "")
            self.assertNotRegex(frame, r"(^|[;{\s])opacity\s*:",
                                f"{selector} fades in; it is an opaque surface")

    def test_the_popover_appears_opaque_from_its_first_frame(self):
        """The property that actually matters, stated as one: nothing in the
        menu's own cascade animates opacity, so it cannot be captured
        semi-transparent. This is the ``opacity: 0.386`` screenshot."""
        body = _rule_body(self.scan, ".menu")
        self.assertNotRegex(body, r"(^|[;{\s])opacity\s*:",
                            ".menu declares a partial opacity")

    def test_only_the_scrim_and_the_toast_may_animate_opacity(self):
        fading = {n for n, b in self.frames.items() if re.search(r"(^|[;{\s])opacity\s*:", b)}
        unexpected = fading - OPACITY_ALLOWED - {"rise"}
        self.assertEqual(unexpected, set(),
                         f"these curves fade: {sorted(unexpected)}. A surface that owns a "
                         f"background and a border shows the page through itself while it does.")

    def test_the_scrim_still_fades(self):
        """Guards the over-correction. Removing every fade would make a dialog
        appear out of nowhere; the scrim is a wash, and the wash is the signal."""
        self.assertIn("fade", self.frames)
        self.assertRegex(self.frames["fade"], r"opacity\s*:\s*0")


class MotionTokenTests(unittest.TestCase):
    """A duration that is a literal is a decision nobody re-checks."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.scan = _strip_comments(_read(CSS_PATH))

    def _root(self) -> dict[str, str]:
        body = _rule_body(_read(CSS_PATH), ":root")
        return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body))

    def test_every_finite_animation_duration_is_a_token(self):
        raw = []
        for shorthand in re.findall(r"(?<![\w-])animation\s*:\s*([^;}]+)", self.scan):
            body = shorthand.strip()
            if re.search(r"\binfinite\b", body):
                continue
            if re.search(r"(?<![\w.-])\d*\.?\d+m?s\b", body):
                raw.append(body)
        self.assertEqual(raw, [], f"raw entrance durations, outside the gate: {raw}")

    def test_the_only_raw_durations_are_the_two_progress_loops(self):
        """Stated as a positive list so a THIRD raw literal cannot slip in
        beside `spin` and `shimmer` unnoticed."""
        loops = {
            body.strip().split()[0]
            for body in re.findall(r"(?<![\w-])animation\s*:\s*([^;}]+)", self.scan)
            if re.search(r"\binfinite\b", body)
        }
        self.assertEqual(loops, {"spin", "shimmer"},
                         f"these loops carry a raw duration: {sorted(loops)}")

    def test_every_transition_takes_its_timing_from_a_token(self):
        raw = []
        for shorthand in re.findall(r"(?<![\w-])transition\s*:\s*([^;}]+)", self.scan):
            body = shorthand.strip()
            if body in ("none", "", "all 0s"):
                continue
            if not re.search(r"var\(--", body):
                raw.append(body)
        self.assertEqual(raw, [], f"transitions with a literal timing: {raw}")

    def test_every_motion_token_is_inside_the_band(self):
        for name, value in self._root().items():
            if not name.startswith("--dur"):
                continue
            m = re.fullmatch(r"(\d+)ms", value.strip())
            self.assertIsNotNone(m, f"{name}: {value!r} is not a plain ms value")
            self.assertGreaterEqual(int(m.group(1)), MOTION_MIN_MS, f"{name} is too fast")
            self.assertLessEqual(int(m.group(1)), MOTION_MAX_MS, f"{name} is too slow")

    def test_the_entrance_token_is_actually_read_by_the_surfaces(self):
        """The check that would have caught the original defect. `--dur` alone
        passing is worth nothing; a popover and a dialog must consume the token
        that carries the band."""
        for selector in (".menu", ".modal"):
            self.assertRegex(
                _rule_body(_read(CSS_PATH), selector), r"animation:\s*rise\s+var\(--",
                f"{selector} does not take its entrance duration from a token")


class MotionGateIsLiveTests(unittest.TestCase):
    """The gate is only a gate if it can fail."""

    def test_the_gate_exposes_check_motion(self):
        self.assertIn("def check_motion(", _read(GATE_PATH),
                      "the motion check was deleted; the band is enforced against nothing again")

    def test_the_gate_strips_comments_before_scanning(self):
        """The gate's own first run failed on the sentence "No transition: the
        file has exactly ONE reduced-motion hook" — prose in a comment, read as
        a declaration. Without stripping it reads English as CSS, which is the
        parser defect task 1.7 recorded for the primitives block."""
        src = _read(GATE_PATH)
        self.assertIn("def strip_css_comments(", src)
        body = src[src.index("def check_motion("):src.index("def _keyframes_bodies(")]
        self.assertIn("scan = strip_css_comments(css)", body,
                      "check_motion scans raw CSS, so any comment naming a property fails it")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()