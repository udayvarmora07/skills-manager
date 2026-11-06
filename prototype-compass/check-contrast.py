#!/usr/bin/env python3
"""Re-derive WCAG contrast ratios from the tokens in styles.css (light and dark).

Text pairs must reach 4.5:1; control boundaries and status icons 3:1 (WCAG 1.4.3 / 1.4.11).
Exits non-zero on any failure, so a token edit cannot silently break contrast.
"""
import re, sys, pathlib

css = pathlib.Path(__file__).with_name("styles.css").read_text()

def block(selector):
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\n\}", css, re.S)
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\b", m.group(1)))

light = block(":root")
dark = {**light, **block(':root[data-theme="dark"]')}

def lum(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)

TEXT = [("ink", "surface"), ("ink", "ground"), ("ink-2", "surface"), ("ink-2", "ground"), ("muted", "surface"),
        ("muted", "sunken"), ("primary", "surface"), ("primary-ink", "primary"), ("primary-soft-ink", "primary-soft"),
        ("s-ok", "s-ok-bg"), ("s-warn", "s-warn-bg"), ("s-bad", "s-bad-bg"), ("s-off", "s-off-bg"),
        ("s-ok", "surface"), ("s-warn", "surface"), ("s-bad", "surface"), ("ink-2", "hover"), ("ink", "primary-soft")]
UI = [("line-strong", "surface"), ("line-strong", "ground"), ("primary", "ground")]

fails = 0
for name, t in (("light", light), ("dark", dark)):
    print(f"== {name}")
    for pairs, need in ((TEXT, 4.5), (UI, 3.0)):
        for fg, bg in pairs:
            r = ratio(t[fg], t[bg]); ok = r >= need; fails += not ok
            print(f"  {'PASS' if ok else 'FAIL'} {r:5.2f}:1 (need {need})  --{fg} on --{bg}")
print("ALL PASS" if not fails else f"{fails} FAILURES")
sys.exit(1 if fails else 0)
