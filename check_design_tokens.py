#!/usr/bin/env python3
"""Re-derive every design-system contrast claim from the shipped CSS.

This is the enforcement layer described in ``DESIGN.md``: the document states the
contract, this script proves the stylesheet still honours it. It reads the real
token blocks out of ``skillsmgr/webui/styles.css``, recomputes every ratio with
the WCAG 2.x relative-luminance formula, and fails on a regression.

It exists because a design token is a *claim*. A palette that once measured 4.5:1
stops measuring 4.5:1 the moment someone nudges one hex, and nothing in an
ordinary test run notices. Nothing here calls a model or the network.

Run:  python3 check_design_tokens.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSS = ROOT / "skillsmgr" / "webui" / "styles.css"
DESIGN_MD = ROOT / "DESIGN.md"
FONTS_DIR = ROOT / "skillsmgr" / "webui" / "static" / "fonts"

# --------------------------------------------------------------------------
# WCAG 2.x contrast
# --------------------------------------------------------------------------


def _channel(value: int) -> float:
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(f"not a 6-digit hex colour: {hex_colour!r}")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# --------------------------------------------------------------------------
# Token extraction
# --------------------------------------------------------------------------

_TOKEN = re.compile(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;")


def read_block(css: str, opener: str) -> dict[str, str]:
    """Return the custom properties declared inside the first ``opener`` block."""
    start = css.find(opener)
    if start == -1:
        raise SystemExit(f"FAIL: could not find {opener!r} in {CSS.name}")
    # Walk braces so a nested rule cannot end the block early.
    depth = 0
    for idx in range(start + len(opener) - 1, len(css)):
        ch = css[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = css[start + len(opener):idx]
                return {m.group(1): m.group(2).lower() for m in _TOKEN.finditer(body)}
    raise SystemExit(f"FAIL: unterminated block after {opener!r} in {CSS.name}")


# --------------------------------------------------------------------------
# The contract
# --------------------------------------------------------------------------

REQUIRED = (
    "bg", "surface", "surface-2", "surface-3",
    "ink", "ink-2", "ink-3", "ink-4",
    "line", "line-2", "line-3", "line-strong",
    "accent", "accent-2", "accent-ink", "accent-bg", "accent-line",
    "ok", "ok-bg", "warn", "warn-bg", "err", "err-bg", "mute", "mute-bg",
)

# (foreground, background, minimum, why)
TEXT_CONTRACTS = (
    ("ink", "surface", 4.5, "body text"),
    ("ink-2", "surface", 4.5, "secondary text"),
    ("ink-3", "surface", 4.5, "tertiary text"),
    ("ok", "surface", 4.5, "active state label"),
    ("warn", "surface", 4.5, "divergent state label"),
    ("err", "surface", 4.5, "invalid state label"),
    ("mute", "surface", 4.5, "muted state label"),
    ("accent", "surface", 4.5, "accent text / link"),
    ("ok", "ok-bg", 4.5, "active badge"),
    ("warn", "warn-bg", 4.5, "divergent badge"),
    ("err", "err-bg", 4.5, "invalid badge"),
    ("mute", "mute-bg", 4.5, "muted badge"),
    ("accent", "accent-bg", 4.5, "accent badge"),
    ("accent-ink", "accent", 4.5, "primary button label"),
)

# Text does not only land on the base surface. The first version of this gate
# checked `--surface` alone and reported PASS, while the rail's group labels
# measured **4.19:1 on --surface-2** in the real render — a gate reporting PASS
# about a path it could not see, which is this repository's most repeated
# lesson. Every ink step is therefore measured against every surface it can be
# painted on.
EVERY_SURFACE_CONTRACTS = tuple(
    (ink, surface, 4.5, f"{ink} on {surface}")
    for ink in ("ink", "ink-2", "ink-3")
    for surface in ("surface", "surface-2", "surface-3")
)

# Non-text contrast is WCAG 1.4.11: 3:1. A boundary only needs it when it is
# the thing that identifies the control.
NONTEXT_CONTRACTS = (
    ("line-3", "surface", 3.0, "control border"),
    ("line-3", "bg", 3.0, "control border on the page ground"),
    ("line-strong", "surface", 3.0, "focus ring"),
    ("accent", "surface", 3.0, "selection mark"),
    # Non-text only. There is no room for a fourth *text* step in this ramp: it
    # bottoms out at 4.60:1 on --surface-3, so nothing de-emphasised enough to
    # be useful also clears 4.5:1 there. De-emphasised text uses --ink-3.
    ("ink-4", "surface", 3.0, "non-text mark (not used for text)"),
    ("ok", "ok-bg", 3.0, "state dot"),
    ("warn", "warn-bg", 3.0, "state dot"),
    ("err", "err-bg", 3.0, "state dot"),
)

# Two adjacent dark surfaces cannot both be dark enough to separate by tone
# alone; the divider carries it. This is a floor, not a target.
SEPARATION_FLOOR = 1.05


def check_theme(name: str, t: dict[str, str], failures: list[str]) -> None:
    print(f"\n=== {name} ===")
    # Contract tables name tokens bare ("ink"); the parsed stylesheet keys them
    # with the CSS prefix ("--ink"). Resolve at lookup rather than duplicating
    # the prefix in every table.
    tok = lambda n: t.get(f"--{n}")  # noqa: E731
    missing = [k for k in REQUIRED if tok(k) is None]
    if missing:
        failures.append(f"{name}: missing token(s): {', '.join(missing)}")
        print(f"  FAIL missing {len(missing)} token(s): {', '.join(missing)}")
        return

    def check(fg: str, bg: str, need: float, why: str) -> None:
        a, b = tok(fg), tok(bg)
        if a is None or b is None:
            return
        ratio = contrast(a, b)
        ok = ratio >= need
        if not ok:
            failures.append(
                f"{name}: {why} — {fg} on {bg} is {ratio:.2f}:1, needs {need}:1"
            )
        print(f"  {'OK  ' if ok else 'FAIL'} {ratio:6.2f}:1 (need {need}) {why}")

    for fg, bg, need, why in TEXT_CONTRACTS:
        check(fg, bg, need, why)
    for fg, bg, need, why in EVERY_SURFACE_CONTRACTS:
        check(fg, bg, need, why)
    for fg, bg, need, why in NONTEXT_CONTRACTS:
        check(fg, bg, need, why)

    sep = contrast(tok("surface"), tok("bg"))
    if sep < SEPARATION_FLOOR:
        failures.append(f"{name}: surface and bg are not separable ({sep:.2f}:1)")
    print(f"  {'OK  ' if sep >= SEPARATION_FLOOR else 'FAIL'} "
          f"{sep:6.2f}:1 (need {SEPARATION_FLOOR}) pane separation")


def check_doc_matches(tokens: dict[str, str]) -> list[str]:
    """DESIGN.md is the contract; the stylesheet is its implementation.

    The document declares the light palette, so a token that drifts in one and
    not the other is a real inconsistency, not a formatting difference.
    """
    if not DESIGN_MD.exists():
        return ["DESIGN.md is missing — the design contract must be checked in"]
    doc = DESIGN_MD.read_text(encoding="utf-8")
    failures = []
    # The document uses different names for a few tokens on purpose
    # (signal/primary, err/error); map them so the check is about colour.
    alias = {
        "primary": "accent",
        "primary-deep": "accent-2",
        "primary-ink": "accent-ink",
        "primary-bg": "accent-bg",
        "error": "err",
        "error-bg": "err-bg",
        "surface-2": "surface-2",
        "surface": "surface",
        "ground": "bg",
        "muted": "ink-3",
        "ink-2": "ink-2",
        "ink": "ink",
        "line-strong": "line-strong",
    }
    for doc_name, css_name in alias.items():
        m = re.search(rf"^\s*{re.escape(doc_name)}:\s*\"?(#[0-9a-fA-F]{{6}})\"?\s*$",
                      doc, re.M)
        if not m:
            continue
        doc_hex = m.group(1).lower()
        css_hex = tokens.get(css_name)
        if css_hex and doc_hex != css_hex:
            failures.append(
                f"DESIGN.md {doc_name} ({doc_hex}) != styles.css --{css_name} ({css_hex})"
            )
            print(f"  FAIL DESIGN.md {doc_name} {doc_hex} != css --{css_name} {css_hex}")
    return failures


def check_fonts() -> list[str]:
    """Fonts must be vendored. A runtime CDN is a third party in the page."""
    failures = []
    if not FONTS_DIR.is_dir():
        return ["static/fonts/ is missing — the interface has no vendored typeface"]
    woffs = sorted(FONTS_DIR.glob("*.woff2"))
    if len(woffs) < 4:
        failures.append(f"expected vendored woff2 faces, found {len(woffs)}")
    for family in ("IBMPlexSans", "IBMPlexMono"):
        if not any(f.name.startswith(family) for f in woffs):
            failures.append(f"{family} is not vendored")
    print(f"\n=== fonts ===\n  {'OK  ' if not failures else 'FAIL'} "
          f"{len(woffs)} vendored woff2 face(s)")
    return failures


def main() -> int:
    if not CSS.exists():
        print(f"FAIL: {CSS} does not exist")
        return 1
    css = CSS.read_text(encoding="utf-8")

    if "fonts.googleapis.com" in css or "fonts.gstatic.com" in css:
        print("FAIL: styles.css references a font CDN. This app must work offline; "
              "see DESIGN.md -> Don't change.")
        return 1

    light = read_block(css, '[data-theme="light"], [data-theme="system"] {')
    dark = read_block(css, '[data-theme="dark"] {')

    failures: list[str] = []
    check_theme("LIGHT", light, failures)
    check_theme("DARK", dark, failures)
    failures.extend(check_doc_matches(light))
    failures.extend(check_fonts())

    print()
    if failures:
        print(f"{len(failures)} design-token failure(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("DESIGN TOKENS OK — every measured pair still clears its threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())