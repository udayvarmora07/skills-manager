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
# The scale lives in the same :root block but is mostly not a hex colour, so
# the colour-only matcher above cannot see it. This one captures any value up
# to the statement terminator, which is enough for `4px`, `120ms`,
# `cubic-bezier(0.2, 0, 0.2, 1)` and the font shorthand.
_ANY_VALUE = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")


def _block_body(css: str, opener: str) -> str:
    """Return the source between the braces of the first ``opener`` block."""
    start = css.find(opener)
    if start == -1:
        raise SystemExit(f"FAIL: could not find {opener!r} in {CSS.name}")
    depth = 0
    for idx in range(start + len(opener) - 1, len(css)):
        ch = css[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return css[start + len(opener):idx]
    raise SystemExit(f"FAIL: unterminated block after {opener!r} in {CSS.name}")


def read_block(css: str, opener: str) -> dict[str, str]:
    """Return the custom properties declared inside the first ``opener`` block."""
    return {m.group(1): m.group(2).lower() for m in _TOKEN.finditer(_block_body(css, opener))}


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
    # ink-4 is checked against the surface it is *worst* on, not against
    # --surface, because "non-text" is a claim about every surface it can land
    # on and the light theme's --surface-3 is where that claim is thinnest.
    ("ink-4", "surface", 3.0, "non-text mark (not used for text)"),
    ("ink-4", "surface-3", 3.0, "non-text mark on the deepest surface"),
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
    not the other is a real inconsistency, not a formatting difference. The
    v1 version of this check compared nine aliased names out of twenty-five, so
    most of the palette was documented but unverified; every colour token the
    document declares is compared now.
    """
    if not DESIGN_MD.exists():
        return ["DESIGN.md is missing — the design contract must be checked in"]
    doc = DESIGN_MD.read_text(encoding="utf-8")
    failures = []
    # Documented name -> stylesheet name. They are the same names in v2; the
    # mapping is kept explicit so a rename on either side fails loudly instead
    # of silently comparing a different token.
    alias = {
        "bg": "bg", "surface": "surface", "surface-2": "surface-2",
        "surface-3": "surface-3",
        "ink": "ink", "ink-2": "ink-2", "ink-3": "ink-3", "ink-4": "ink-4",
        "accent": "accent", "accent-2": "accent-2", "accent-3": "accent-3",
        "accent-ink": "accent-ink", "accent-bg": "accent-bg",
        "accent-line": "accent-line",
        "ok": "ok", "ok-bg": "ok-bg", "warn": "warn", "warn-bg": "warn-bg",
        "err": "err", "err-bg": "err-bg", "mute": "mute", "mute-bg": "mute-bg",
        "line": "line", "line-2": "line-2", "line-3": "line-3",
        "line-strong": "line-strong",
    }
    checked = 0
    missing_css = 0
    for doc_name, css_name in alias.items():
        m = re.search(rf"^  {re.escape(doc_name)}:\s*\"?(#[0-9a-fA-F]{{6}})\"?\s*$",
                      doc, re.M)
        if not m:
            failures.append(f"DESIGN.md declares no palette value for {doc_name}")
            continue
        doc_hex = m.group(1).lower()
        # The parsed stylesheet keys carry the CSS prefix. The v1 version of
        # this loop looked the bare name up, got None for every token, and its
        # `if css_hex and …` guard then skipped all nine comparisons — a
        # DESIGN.md/styles.css drift check that had never once compared
        # anything, and reported nothing. Prefix at lookup instead, and count
        # real comparisons so a future rename is visible.
        css_hex = tokens.get(f"--{css_name}")
        if css_hex is None:
            missing_css += 1
            failures.append(f"styles.css declares no --{css_name} for DESIGN.md {doc_name}")
            continue
        checked += 1
        if doc_hex != css_hex:
            failures.append(
                f"DESIGN.md {doc_name} ({doc_hex}) != styles.css --{css_name} ({css_hex})"
            )
            print(f"  FAIL DESIGN.md {doc_name} {doc_hex} != css --{css_name} {css_hex}")
    print(f"\n=== DESIGN.md ===\n  {'OK  ' if not failures else 'FAIL'} "
          f"{checked}/{len(alias)} palette value(s) compared against the stylesheet"
          + (f", {missing_css} missing in css" if missing_css else ""))
    return failures


# --------------------------------------------------------------------------
# The v2 scale: space, radius, type, motion
# --------------------------------------------------------------------------

SPACE_STEPS = (4, 8, 12, 16, 20, 24, 32, 48)
TYPE_STEPS = ("--t-meta", "--t-table", "--t-ui", "--t-prose", "--t-page", "--t-empty")
# Non-text mark only. ink-4 is the one ink step the palette does NOT promise as
# text: on --surface-3 in light it measures 3.85:1. Recording that floor here
# means a future edit that darkens or lightens ink-4 cannot quietly turn a
# non-text mark into failing text.
INK4_FLOOR = 3.0
MOTION_MIN_MS, MOTION_MAX_MS = 100, 160


# The complete set of `font-size` declarations allowed to be a literal rather
# than a step, each with the reason it cannot be one. Keeping the list here,
# in the gate, is what makes "no off-scale size" checkable at all — a rule
# that says "no raw sizes, except the ones I thought of" is not a gate.
FONT_SIZE_EXCEPTIONS = {
    # Rescales `html`, so every step is multiplied by it. Pointing it at a step
    # would make the Large preference equal the standard size: a silent no-op.
    'html[data-text-size="large"] { font-size: 1.125rem; }',
    # Two rules hide a text glyph behind an icon at the narrow breakpoint. Zero
    # is not a step and pretending otherwise would put a 0 on the scale.
    ".topbar-new { min-width: 40px; width: 40px; padding: 0; font-size: 0; }",
    ".command-trigger { min-width: 44px; min-height: 44px; width: 44px; padding: 0; font-size: 0; gap: 0; }",
}


def check_type_scale(css: str, root_map: dict, note) -> None:
    """A declared scale that nothing reads is a table of intent.

    This is the fourth recorded instance of the repository's own failure mode —
    a gate that reports PASS about a path it cannot see. The six `--t-*` steps
    were declared and documented for a whole release while **zero** of the 163
    `font-size` declarations in the cascade referenced one, so the scale
    governed nothing and the real sizes were 25 distinct ad-hoc rem literals
    (three of them below the 12px floor DESIGN.md calls absolute). So this
    checks two things the earlier presence-only check could not:

    1. the steps are rem and ascend (a `font:` shorthand cannot be consumed by
       `font-size:`, so a shorthand step is a step the cascade cannot use), and
    2. the cascade contains no size literal outside the named exceptions —
       which is the property that makes 1. observable in the first place.
    """
    rems = {}
    for step in TYPE_STEPS:
        raw = (root_map.get(step) or "").strip()
        m = re.fullmatch(r"([0-9.]+)rem", raw)
        note(bool(m), f"{step} is a rem size a rule can consume", raw or "absent")
        if m:
            rems[step] = float(m.group(1))

    ascending = len(rems) == len(TYPE_STEPS) and all(
        rems[a] < rems[b] for a, b in zip(TYPE_STEPS, TYPE_STEPS[1:]))
    note(ascending, "type steps ascend meta < table < ui < prose < page < empty",
         "" if ascending else f"got {rems}")

    # Every `font-size:` value in the file, minus the declared exceptions, must
    # be a step. Comment text is stripped first so the prose in this very
    # function cannot fail its own check.
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    allowed = "\n".join(FONT_SIZE_EXCEPTIONS)
    literals = [
        m.group(1).strip() for m in re.finditer(r"font-size:\s*([^;{}]+)", body)
    ]
    offenders = []
    for value in literals:
        if value.startswith("var(--t-"):
            if value not in {f"var({s})" for s in TYPE_STEPS}:
                offenders.append(value)
            continue
        if value and f"font-size: {value}" not in allowed:
            offenders.append(value)
    note(not offenders,
         f"every font-size is one of the {len(TYPE_STEPS)} steps "
         f"({len(literals) - len(offenders)} declarations, "
         f"{len(FONT_SIZE_EXCEPTIONS)} declared exceptions)",
         "" if not offenders else f"off-scale: {sorted(set(offenders))}")

    used = {m.group(1) for m in re.finditer(r"font-size:\s*var\((--t-[a-z]+)\)", body)}
    unused = [t for t in TYPE_STEPS if t not in used]
    note(not unused, "every declared step is read by at least one rule",
         "" if not unused else f"declared and unread: {unused}")


def check_scale(css: str, failures: list[str]) -> None:
    """The scale is as much a contract as the palette, and it decays the same way.

    The v1 spacing scale shipped ``--s7: 32px; --s9: 32px`` — two names for the
    same step — so "the ninth step" was a fiction and nothing noticed. These
    checks are the answer to that: the step set is asserted exactly, not merely
    spot-checked.
    """
    root = _block_body(css, ":root {")
    root_map = {m.group(1): m.group(2) for m in _ANY_VALUE.finditer(root)}

    def note(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            failures.append(label + (f" — {detail}" if detail else ""))
        print(f"  {'OK  ' if ok else 'FAIL'} {label}" + (f" ({detail})" if detail else ""))

    # -- space -------------------------------------------------------------
    # `step` is the token's own name (…--s7, --s9), not a list index. Writing
    # this with enumerate() and using the index probed --s0…--s7, so the
    # missing eighth step was invisible — the failure this check exists for,
    # reproduced by the check itself on its first run.
    found = {}
    for step in (1, 2, 3, 4, 5, 6, 7, 9):
        raw = root_map.get(f"--s{step}")
        if raw is not None:
            found[f"--s{step}"] = raw
    expected = {f"--s{step}": f"{value}px" for step, value in zip(
        (1, 2, 3, 4, 5, 6, 7, 9), SPACE_STEPS)}
    note(found == expected, "space scale is 4/8/12/16/20/24/32/48",
         "" if found == expected else f"got {sorted(found.items())}")

    # -- radius ------------------------------------------------------------
    radii = {}
    for name in ("--r-ctl", "--r-panel", "--radius"):
        raw = root_map.get(name)
        if raw and raw.endswith("px"):
            radii[name] = float(raw[:-2])
    ordered = (len(radii) == 3
               and radii.get("--r-ctl", 0) < radii.get("--r-panel", 0)
               < radii.get("--radius", 0))
    note(ordered, "radius steps ascend control < panel < dialog",
         "" if ordered else f"got {radii}")

    # -- type --------------------------------------------------------------
    missing_type = [t for t in TYPE_STEPS if t not in root_map]
    note(not missing_type, f"{len(TYPE_STEPS)} type steps declared",
         "" if not missing_type else f"missing {missing_type}")
    check_type_scale(css, root_map, note)

    # -- motion ------------------------------------------------------------
    dur = root_map.get("--dur", "")
    m = re.match(r"(\d+)ms$", dur)
    ok_dur = bool(m) and MOTION_MIN_MS <= int(m.group(1)) <= MOTION_MAX_MS
    note(ok_dur, f"--dur is within {MOTION_MIN_MS}-{MOTION_MAX_MS}ms", dur or "absent")
    overshoot = [c for c in re.findall(r"cubic-bezier\(([^)]*)\)", css)
                 if len(c.split(",")) == 4
                 and any(float(p.strip()) > 1.0 for p in (c.split(",")[1], c.split(",")[3]))]
    note(not overshoot, "no easing curve overshoots", "; ".join(overshoot))

    # -- one palette, not three -------------------------------------------
    # `index.html` starts at data-theme="system" and preferences.js resolves it
    # to an explicit light/dark *before* styles.css loads, so a
    # prefers-color-scheme palette can only fire before that script runs or not
    # at all. One did, carrying an orange accent and pre-dates-the-values
    # surfaces, and this gate read only the two explicit blocks: PASS about a
    # path it could not see.
    third = re.findall(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{[^@]*?\[data-theme",
                       css, re.S)
    note(not third, "no third (media-query) palette shadows the two themes",
         f"{len(third)} found")

    # -- refused defaults, in the token layer ------------------------------
    for pattern, why in ((r"--[a-z0-9-]*grad[a-z0-9-]*\s*:", "a gradient token"),
                         (r"\bfilter:\s*blur\(", "a blur/glass panel"),
                         (r"backdrop-filter", "a backdrop-filter panel")):
        hit = re.search(pattern, css, re.I)
        note(hit is None, f"no {why} in the stylesheet", hit.group(0) if hit else "")


def check_fonts() -> list[str]:
    """Fonts must be vendored, declared, and actually present.

    Three separate failures live here and all three are silent at runtime:

    * a CDN reference (checked in ``main``) puts a third party in the page;
    * a ``@font-face`` naming a file that is not in the package 404s quietly,
      because a relative URL in a stylesheet resolves against the *stylesheet's*
      own URL and nothing reports the miss;
    * a face whose ``unicode-range`` excludes basic Latin is fetched for
      nothing. That one shipped here once: six rules, 176 KB of woff2, and not
      one English character in the interface matched any of them.

    Nothing here names a family. The contract is "every declared face resolves
    to bytes this package ships, and none of them is restricted away from
    ASCII", so a future typeface change is a data edit rather than a code edit.
    """
    failures = []
    if not FONTS_DIR.is_dir():
        return ["static/fonts/ is missing — the interface has no vendored typeface"]

    sheets = sorted(FONTS_DIR.glob("*.css"))
    if not sheets:
        return [f"static/fonts/ has no face stylesheet to derive the contract from"]

    faces = 0
    for sheet in sheets:
        css = sheet.read_text(encoding="utf-8")
        blocks = re.findall(r"@font-face\s*\{(.*?)\}", css, re.S)
        for block in blocks:
            faces += 1
            family = re.search(r"font-family:\s*([^;]+);", block)
            label = family.group(1).strip().strip("'\"") if family else "?"
            for src in re.findall(r"url\(([^)]+)\)", block):
                src = src.strip().strip("'\"")
                if "http" in src:
                    failures.append(f"{sheet.name}: {label} is a remote reference ({src})")
                elif not (FONTS_DIR / src).is_file():
                    failures.append(f"{sheet.name}: {label} names {src}, which is not shipped")
            unicode_range = re.search(r"unicode-range:\s*([^;]+);", block)
            if unicode_range and "U+0000-00FF" not in unicode_range.group(1):
                failures.append(
                    f"{sheet.name}: {label} is restricted by unicode-range to "
                    f"{unicode_range.group(1).strip()} — basic Latin would fall back"
                )
    if faces < 4:
        failures.append(f"expected at least 4 declared faces, found {faces}")

    woffs = sorted(FONTS_DIR.glob("*.woff2"))
    for face in woffs:
        if face.stat().st_size <= 1000:
            failures.append(f"{face.name} looks empty ({face.stat().st_size} bytes)")
            continue
        # A `.woff2` extension is a claim; `wOF2` is the proof.  Size alone is
        # not a check on the bytes — a truncated download, an HTML error page
        # saved under the name, or 27 KB of noise all clear 1000 bytes and were
        # reported PASS here.  Mutation-proved: replacing a face with random
        # bytes of the correct length left this gate green.
        if face.read_bytes()[:4] != b"wOF2":
            failures.append(f"{face.name} is not a WOFF2 container — the file is "
                            f"not the font it claims to be")

    licences = [p.name for p in FONTS_DIR.iterdir() if "LICEN" in p.name.upper()]
    if not licences:
        failures.append("static/fonts/ ships woff2 with no licence file beside it")

    print(f"\n=== fonts ===\n  {'OK  ' if not failures else 'FAIL'} "
          f"{faces} declared face(s), {len(woffs)} vendored woff2, "
          f"licence: {', '.join(licences) or 'NONE'}")
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
    print("\n=== scale (space, radius, type, motion, one palette) ===")
    check_scale(css, failures)
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