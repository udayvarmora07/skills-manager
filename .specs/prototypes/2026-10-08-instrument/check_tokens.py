#!/usr/bin/env python3
"""Prove the prototype's token claims instead of asserting them.

A gate that reports PASS about a path it cannot see is not a gate — the
shipped repo records four instances of that failure, one of which shipped a
release whose changelog never mentioned its largest change. So this script
does three things the prose cannot:

  1. re-derives every contrast ratio from the shipped token file, using the
     WCAG 2.x relative-luminance formula;
  2. re-derives every tracking value against Apple's published optical
     tracking table, rather than trusting the comment beside it;
  3. is proved by mutation — `selfcheck()` deliberately breaks each rule and
     asserts the gate goes red, because a green gate nobody has seen fail is
     an assumption wearing a checkmark.

Usage:
    python3 check_tokens.py           # run the gate
    python3 check_tokens.py --selfcheck  # prove the gate has teeth
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
TOKENS = ROOT / "assets" / "tokens.css"

# ── WCAG 2.x relative luminance ──────────────────────────────────────────────
def _lin(v: float) -> float:
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def _rgb(value: str) -> tuple[float, float, float]:
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(color: str) -> float:
    r, g, b = (_lin(v / 255) for v in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def flatten(color: str, backdrop: str) -> str:
    """Composite an rgba() token over the surface it is painted on.

    A translucent rule is not a colour on its own — it is what the eye sees
    after the surface shows through. Measuring the raw rgba() against a
    background would report a ratio that does not exist on screen.
    """
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)", color.strip())
    if not m:
        return color
    alpha = float(m.group(4))
    src = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    dst = _rgb(backdrop)
    mixed = tuple(s * alpha + d * (1 - alpha) for s, d in zip(src, dst))
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in mixed)


def contrast(a: str, b: str) -> float:
    """Contrast of `a` as painted on `b`. Translucent values are composited."""
    a = flatten(a, b)
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ── Apple HIG: tracking, in 1/1000 em, from the Typography page ──────────────
# Cross-checked against a second fetch of the same page during research; both
# agreed. Only the sizes this design actually uses are listed.
APPLE_TRACKING = {
    6: 41, 7: 34, 8: 26, 9: 19, 10: 12, 11: 6, 12: 0,
    13: -6, 14: -11, 15: -16, 16: -20, 17: -26, 18: -25, 19: -24,
    20: -23, 21: -18, 22: -12, 23: -4, 24: 3, 25: 6, 26: 8, 27: 11,
    28: 14, 29: 14, 30: 14, 31: 13, 32: 13, 33: 12, 34: 12, 35: 11,
    36: 10, 37: 10, 38: 10, 40: 10, 44: 8, 48: 8, 52: 6, 56: 6,
    60: 4, 64: 4, 68: 2, 72: 2, 76: 1, 80: 0,
}

# the step each tracking token is measured at
TRACK_AT_SIZE = {
    "track-hero": 52,
    "track-display": 31,
    "track-title": 21,
    "track-lead": 16,
    "track-head": 14,
    "track-body": 14,
    "track-small": 13,
    "track-micro": 11,
}

# Ink steps are body text at 11–14px, so Apple states 7:1 as the target for
# small text (4.5:1 is the floor). The faintest step carries file paths, and a
# path you cannot read is a path you cannot debug — so the target is the bar.
TEXT_TARGET = 7.0
TEXT_FLOOR = 4.5
NON_TEXT_FLOOR = 3.0

failures: list[str] = []
checks = 0


def check(ok: bool, msg: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(msg)


def _reset() -> None:
    """Clear the accumulators. Without this, main() called twice — which is
    exactly what --selfcheck does after every mutation — reports the previous
    run's failures against the restored file, and the selfcheck can never
    prove it left the tree green."""
    global checks
    checks = 0
    failures.clear()


def parse_tokens() -> dict[str, dict[str, str]]:
    """Return {scope: {token: value}} for :root and [data-theme=dark]."""
    text = TOKENS.read_text()
    scopes: dict[str, dict[str, str]] = {}
    for scope, body in re.findall(r"(:root|\[data-theme=\"dark\"\])\s*\{(.*?)\n\}", text, re.S):
        tok = dict(re.findall(r"(--[a-z0-9-]+):\s*([^;]+);", body))
        scopes[scope] = tok
    return scopes


def main() -> int:
    _reset()
    scopes = parse_tokens()
    if ":root" not in scopes or '[data-theme="dark"]' not in scopes:
        print("FAIL: tokens.css did not parse into both scopes")
        return 1
    light = scopes[":root"]
    dark = scopes['[data-theme="dark"]']

    # ── 1. every ink step clears the 7:1 small-text target on its own surface
    for name, scope, surface in (("light", light, light["--surface"]),
                                 ("dark", dark, dark["--surface"])):
        steps = ["--ink", "--ink-2", "--ink-3", "--ink-4"]
        ratios = [contrast(scope[s], surface) for s in steps]
        for step, r in zip(steps, ratios):
            check(r >= TEXT_TARGET,
                  f"{name} {step} {scope[step]} is {r:.2f}:1 on {surface}, "
                  f"below the {TEXT_TARGET}:1 target for small text")
        # a scale that steps down monotonically is a scale; one that does not
        # is four unrelated colours that happen to be named ink
        check(all(a > b for a, b in zip(ratios, ratios[1:])),
              f"{name} ink steps are not monotonic: "
              + ", ".join(f"{s}={r:.2f}" for s, r in zip(steps, ratios)))

    # ── 2. every status colour is legible on its own wash AND on the surface
    for name, scope in (("light", light), ("dark", dark)):
        for base in ("ok", "warn", "bad", "mute", "signal"):
            on_wash = contrast(scope[f"--{base}"], scope[f"--{base}-wash"])
            on_surface = contrast(scope[f"--{base}"], scope["--surface"])
            check(on_wash >= TEXT_FLOOR,
                  f"{name} --{base} is {on_wash:.2f}:1 on its own wash, below "
                  f"{TEXT_FLOOR}:1 — a status mark nobody can read is not a status mark")
            check(on_surface >= TEXT_FLOOR,
                  f"{name} --{base} is {on_surface:.2f}:1 on --surface, below {TEXT_FLOOR}:1")

    # ── 3. the fill behind a filled button carries its label
    check(contrast(light["--signal-ink"], light["--signal"]) >= TEXT_TARGET,
          "light --signal-ink on --signal is below the small-text target")
    check(contrast(dark["--signal-ink"], dark["--signal"]) >= TEXT_TARGET,
          "dark --signal-ink on --signal is below the small-text target")
    check(contrast(light["--ink"], light["--raised"]) >= TEXT_TARGET,
          "light --ink on --raised is below the small-text target")
    check(contrast(dark["--ink"], dark["--raised"]) >= TEXT_TARGET,
          "dark --ink on --raised is below the small-text target")

    # ── 4. rules that carry a boundary are a graphical object (WCAG 1.4.11),
    #       which is a 3:1 threshold and NOT the 4.5:1 text threshold
    for name, scope, fg, bg in (("light", light, "--rule-strong", "--surface"),
                                ("dark", dark, "--rule-strong", "--surface")):
        r = contrast(scope[fg], scope[bg])
        check(r >= NON_TEXT_FLOOR,
              f"{name} {fg} is {r:.2f}:1 against {bg}, below the {NON_TEXT_FLOOR}:1 "
              f"a boundary must clear (WCAG 1.4.11)")

    # ── 5. tracking is re-derived against Apple's table, not trusted
    for token, size in TRACK_AT_SIZE.items():
        raw = light[f"--{token}"].strip()
        m = re.fullmatch(r"(-?[\d.]+)em", raw)
        if not m:
            check(False, f"--{token} is {raw!r}, which is not a plain em value")
            continue
        got = round(float(m.group(1)) * 1000)
        want = APPLE_TRACKING[size]
        check(abs(got - want) <= 1,
              f"--{token} is {got}/1000 em at {size}px; Apple's table says "
              f"{want}/1000. Large display type tracks POSITIVE and body type "
              f"NEGATIVE — a negative value on a 31px display is a 14px rule "
              f"applied at the wrong size.")

    # ── 6. the two surfaces of each theme must differ, or the depth model
    #       is decoration with nothing behind it
    for name, scope in (("light", light), ("dark", dark)):
        check(scope["--canvas"] != scope["--surface"],
              f"{name} --canvas and --surface are identical, so the recessed "
              f"plane and the working surface are the same plane")
        check(scope["--raised"] != scope["--surface"],
              f"{name} --raised and --surface are identical, so no card lifts")

    # ── report
    print(f"checks run: {checks}")
    if failures:
        print(f"\nFAILED ({len(failures)}):")
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    print("PASSED — every ink step clears 7:1, every status colour clears 4.5:1 "
          "on its own wash, every boundary clears 3:1, and every tracking value "
          "matches Apple's optical table.")
    return 0


def selfcheck() -> int:
    """Break each rule on purpose and prove the gate notices."""
    original = TOKENS.read_text()
    mutations = [
        ("an ink step below 7:1",
         "--ink-4:       #4f565b;", "--ink-4:       #8d949a;"),
        ("a status colour on its own wash",
         "--bad:      #a52f1d;", "--bad:      #f0b4aa;"),
        ("a negative tracking value on 31px display type",
         "--track-display:  0.013em;", "--track-display:  -0.026em;"),
        ("a canvas identical to its surface",
         "--canvas:      #e4e6e3;", "--canvas:      #f8f9f7;"),
        ("a boundary under the 3:1 non-text floor",
         "--rule-strong: #868d94;", "--rule-strong: #d3d7da;"),
        ("a button label below 7:1 on its own fill",
         "--signal:        #0a6257;", "--signal:        #7fbfb6;"),
    ]
    print("proving the gate has teeth\n")
    allgood = True
    try:
        for label, find, replace in mutations:
            assert find in original, f"mutation anchor missing: {find!r}"
            TOKENS.write_text(original.replace(find, replace, 1))
            rc = main()
            caught = rc == 1
            allgood &= caught
            print(f"  {'✓ caught' if caught else '✗ MISSED'} — {label}\n")
    finally:
        TOKENS.write_text(original)

    rc = main()
    if rc != 0:
        print("restoring the file did not return the gate to green")
        return 1
    if not allgood:
        return 1
    print(f"all {len(mutations)} mutations caught; the real file is green again")
    return 0


if __name__ == "__main__":
    sys.exit(selfcheck() if "--selfcheck" in sys.argv else main())