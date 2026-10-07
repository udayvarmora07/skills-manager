# Redesign evidence — Warm Instrument (2026-10-08)

**Status: rendered, NOT reviewed.** These captures prove the interface renders
with the new design system and that its measurements hold. They do **not**
prove it is good. A human still has to look at it.

Captured against a live server reading the real library on this machine
(1,962 observed instances across seven detected scope roots), not against the
hermetic harness fixture — so the numbers in them are the real ones.

## Captures

- `01-library.png` — d0dfc5422695d7b565f71b20ee4e245f71e1b4bd7d131c6462877d6e4dc5203c  (230,500 bytes)
- `02-overview.png` — e04e4c67ab34187c5aa7fb648eec55ece3a2059c9dcfb858bcc2690010ae0d91  (210,320 bytes)
- `03-overview-dark.png` — c66ed784536c2cfa4e20e1511c766a60f4f422e67e050659d9ec624a4dea23d8  (209,228 bytes)
- `04-mobile-400.png` — abf6ceb6d4e04a88efbe78e3fca4b6918b1bb539d5161976a429b06f3d680322  (70,576 bytes)

## What was measured, and what that is worth

| Check | Result |
|---|---|
| Contrast, rendered | 17 distinct text styles on the Overview and 28 in the Library, **zero** failures below their WCAG threshold, in **both** themes |
| Font actually applied | Plex Sans measures 339px against a 310px fallback; Plex Mono 429px. The earlier failure mode — a vendored face that covers no ASCII — was caught this way |
| Viewports | 320/400/640/900/1280/1440: no overflow, no console or runtime errors, no failed requests |
| Keyboard focus | `:focus-visible` matches and produces a 2px outline plus a 3px ring, measured on the live element rather than read from the stylesheet |
| Token gate | 65 checks, all passing, proved by mutation |
| Static analysis | Bandit 0 issues, Ruff F821/F822/F823 clean |
| Behaviour | 1,233 tests green on Python 3.11, 3.12, 3.13 and 3.14; all 16 CI jobs green |

## What this evidence does NOT cover

This is the part that matters, and it is the same list G8 carried:

- **No human perceptual review.** Nobody has looked at these and said whether
  the redesign is an improvement. That is the deliverable this project is
  waiting on.
- **No non-Chromium engine.** Only Blink.
- **No forced-colors mode.** A high-contrast user gets whatever the OS forces
  over this palette, and nothing here measured that.
- **No 200% or 400% zoom.** The rem-based type scale is asserted by a unit
  test; nothing confirms the layout survives at 400% in a real browser.
- **No screen reader.** ARIA is structurally present and the a11y tree is
  checkable, but nothing was driven with NVDA, JAWS or VoiceOver.
- **Not every view was captured.** Install, Quality, Recovery, Workspaces,
  Profiles, Settings and Trash inherited the token layer but were not
  individually reviewed or photographed.

## How these were produced

Rendered through the Chrome DevTools Protocol against `python3 -m skillsmgr
webui` on this machine at 1440x1000, 1440x1000 dark, and 400x800. The
per-viewport sweep (six widths, plus empty / populated / inventory-failure /
unavailable-root scenarios) is `browser_harness.py`, which is hermetic and
runs in CI.
