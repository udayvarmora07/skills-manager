---
version: beta
name: Skills Manager
description: >-
  The v2 contract. A local control plane for people who live in terminals: it
  should feel like a precise instrument — dense, calm, and completely honest
  about what it observed rather than what it concluded.
colors:
  bg: "#f2f3f1"
  surface: "#fbfbfa"
  surface-2: "#eceef0"
  surface-3: "#e1e5e9"
  ink: "#1a1c1f"
  ink-2: "#454a50"
  ink-3: "#5f666d"
  ink-4: "#6b727a"
  accent: "#0d6a63"
  accent-2: "#0a524d"
  accent-3: "#083f3b"
  accent-ink: "#ffffff"
  accent-bg: "#e2f0ee"
  accent-line: "#a8d0cb"
  ok: "#3f6b3f"
  ok-bg: "#e9f0e9"
  warn: "#7d590e"
  warn-bg: "#f5f0e0"
  err: "#a33526"
  err-bg: "#f7e8e5"
  mute: "#5e646b"
  mute-bg: "#eceef0"
  line: "#e4e6e9"
  line-2: "#ccd0d6"
  line-3: "#868d95"
  line-strong: "#7d848c"
typography:
  sans: "Geist Sans"
  mono: "Geist Mono"
  weights: [400, 500, 600]
  scale:
    meta: "12px/1.45"
    table: "13px/1.45"
    ui: "14px/1.45"
    prose: "16px/1.55"
    page: "600 20px/1.30"
    empty: "600 28px/1.20"
space:
  base: 4
  steps: [4, 8, 12, 16, 20, 24, 32, 48]
rounded:
  ctl: 6px
  panel: 8px
  dialog: 12px
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.ctl}"
    height: 32px
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.ctl}"
    height: 32px
  button-danger:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.err}"
    rounded: "{rounded.ctl}"
    height: 32px
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.ctl}"
    height: 32px
  state-active:
    backgroundColor: "{colors.ok-bg}"
    textColor: "{colors.ok}"
    rounded: "{rounded.ctl}"
  state-divergent:
    backgroundColor: "{colors.warn-bg}"
    textColor: "{colors.warn}"
    rounded: "{rounded.ctl}"
  state-invalid:
    backgroundColor: "{colors.err-bg}"
    textColor: "{colors.err}"
    rounded: "{rounded.ctl}"
  state-unaddressable:
    backgroundColor: "{colors.mute-bg}"
    textColor: "{colors.mute}"
    rounded: "{rounded.ctl}"
  callout:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.panel}"
  meter-track:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.ctl}"
    height: 8px
  meter-fill-over:
    backgroundColor: "{colors.err}"
    rounded: "{rounded.ctl}"
    height: 8px
  meter-fill-under:
    backgroundColor: "{colors.ok}"
    rounded: "{rounded.ctl}"
    height: 8px
  divider:
    backgroundColor: "{colors.line}"
    rounded: "{rounded.ctl}"
    height: 1px
  focus-ring:
    backgroundColor: "{colors.accent}"
    rounded: "{rounded.ctl}"
    height: 2px
  row-selected:
    backgroundColor: "{colors.accent-bg}"
    textColor: "{colors.ink}"
  prose-body:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
  prose-muted:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink-4}"
---

## Overview

A skill is a markdown file that gets concatenated into a model's context
window. Users arrive because their agents behave differently and they suspect
their files. So this product's world is **paperwork**: documents, copies,
provenance, corrections, and the budget of one context window. The visual
source is the **printer's proof sheet** — a cool bone stock set with one ink
used like a stamp, ruled with hairlines instead of boxes, annotated in the
margin wherever a claim needs its evidence.

Structure comes from rules and alignment, not from cards and shadows. Colour
is spent on exactly one job — *state* — plus one reserved ink for
*interaction*.

### Why the palette did not become the proposal's blue

`.redesign/DESIGN-V2.md` §C proposed a near-monochrome grey with
`--accent-fill #2f6df6`. It labelled those "starting values — measured
contrast decides", and measurement decided against them, for three reasons
that are worth more than the hex codes:

1. **A saturated blue accent on near-black is the single most recognisable
   "generic SaaS template" tell.** `.redesign/DESIGN-V2.md` §B refuses it in
   prose and lists "could be any SaaS template" as the failure condition;
   adopting §C's number while keeping §B's rule would have contradicted the
   brief inside the same document.
2. **The shipped palette already clears every threshold**, on all three
   surfaces, in both themes, including the de-emphasised ink step that the
   v1 gate deliberately did *not* require to be text. A change that fixes
   nothing is churn, and churn in a design token is how a contract decays.
3. **The accent has a job beyond looking like a product.** It must not be
   confusable with any of the four status colours at a glance, because the
   whole point of this tool is that two agents disagreeing is a *fact* and
   facts must survive being printed in black and white. A cool teal-ink is
   separable from green/amber/red at a glance; the proposed blue is not
   separable from a cyan-tinted "active" state at small sizes.

So the v2 contract **keeps the measured bone-and-ink palette and re-derives
everything else**. What actually changed in v2 is the scale (type, space,
radius), the shell, and the honesty of the gate — not the hue.

## Colors

Every value below was **measured**, not chosen by eye. Ratios are computed
with the WCAG 2.x relative-luminance formula by `check_design_tokens.py`,
which re-derives them from the shipped `skillsmgr/webui/styles.css` on every
run and fails on a regression. These are the numbers as measured:

| pair | light | dark | threshold |
|---|---|---|---|
| `ink` on `surface` | 16.49:1 | 15.39:1 | 4.5 |
| `ink-2` on `surface` | 8.64:1 | 10.45:1 | 4.5 |
| `ink-3` on `surface` | 5.62:1 | 6.59:1 | 4.5 |
| `ink-3` on `surface-3` (worst surface) | 4.60:1 | 5.31:1 | 4.5 |
| `accent` on `surface` | 6.22:1 | 8.51:1 | 4.5 |
| `accent-ink` on `accent` (primary button) | 6.44:1 | 8.22:1 | 4.5 |
| `ok` on `ok-bg` (badge + dot) | 5.35:1 | 7.16:1 | 4.5 |
| `warn` on `warn-bg` | 5.57:1 | 7.73:1 | 4.5 |
| `err` on `err-bg` | 5.70:1 | 6.99:1 | 4.5 |
| `mute` on `mute-bg` | 5.14:1 | 6.04:1 | 4.5 |
| `line-3` on `surface` (control border) | 3.24:1 | 3.53:1 | 3 |
| `line-3` on `bg` | 3.01:1 | 3.77:1 | 3 |
| `line-strong` on `surface` (focus ring) | 3.65:1 | 3.74:1 | 3 |
| `surface` on `bg` (pane separation) | 1.08:1 | 1.07:1 | 1.05 |

Two decisions in that table are load-bearing:

- **There is deliberately no grey that fails AA** for text this interface
  actually renders as text, including the most de-emphasised step. De-emphasised
  text here is usually a file path, and a path you cannot read is a path you
  cannot debug. `ink-4` is therefore a *non-text* mark only (it bottoms out at
  3.85:1 on `surface-3` in light), and the gate asserts that floor rather than
  ignoring it.
- **Panes separate by a hairline, not by tone.** `surface` on `bg` is 1.08:1
  in both themes: adjacent surfaces are deliberately *not* contrast-separable,
  because WCAG 1.4.11 applies to the boundary that identifies the control, and
  a 1px rule carrying 3:1 is that boundary. The floor exists only so a future
  edit cannot quietly collapse two panes into one flat field.

**Status is never colour alone.** Every state is a glyph + colour + the word,
because two agents disagreeing is a fact, and facts must survive being printed
in black and white. Red means *malformed*, never *divergent*: divergent content
is attention-worthy but is not an error, and colouring it red would teach users
to ignore red.

The observed-state vocabulary is fixed and is not a styling decision:
Active, Disabled, Malformed, Unaddressable, Divergent, Linked outside root.

## Typography

Two families, both **vendored as static woff2** under
`skillsmgr/webui/static/fonts/` (SIL OFL 1.1, © 2023 Vercel + basement.studio,
licence text shipped beside the faces).

- **Geist Sans** for interface and prose. Chosen over `system-ui` for a
  functional reason: this tool's job is comparing a file on macOS with the same
  file on Linux, and identical glyphs on both machines is a correctness
  property, not only a taste one.
- **Geist Mono** for every identifier — skill names, paths, content hashes,
  every number — with `font-variant-numeric: tabular-nums` so figures align
  without a layout hack.
- Weights **400 / 500 / 600 only**.

**The faces carry no `unicode-range`, and that is load-bearing.** An earlier
vendoring pass declared six faces whose every rule restricted them to
`latin-ext`: 176 KB of woff2 in the package, every "is the font vendored"
check green, and not one English character in the interface matched any of
them — the browser fetched nothing, reported no error, and every visitor got
the fallback silently. A subset range is an optimisation; omitting it costs a
few KB on loopback and cannot reproduce that failure.

**The scale is six steps** (CSS: `--t-meta` `--t-table` `--t-ui` `--t-prose`
`--t-page` `--t-empty`):

| token | size / line-height | role |
|---|---|---|
| `--t-meta` | 12px / 1.45 | de-emphasised metadata, captions |
| `--t-table` | 13px / 1.45 | table rows, dense UI |
| `--t-ui` | 14px / 1.45 | body UI, inputs, row primary line |
| `--t-prose` | 16px / 1.55 | rendered `SKILL.md` bodies |
| `--t-page` | 600 20px / 1.30 | page title, -0.012em tracking |
| `--t-empty` | 600 28px / 1.20 | empty-state and first-run titles only |

12px is the absolute floor for text a user must read. The v1 scale carried
seven steps (`26/17/13.5/13/12/12/12.5`) that were near-indistinguishable at
1x, which is not a scale but a queue of one-off decisions; v2 removes the
steps nobody could see and adds the one the document pane was missing.

Sentence case everywhere, including labels. **No ALL-CAPS eyebrow above a
heading** — a tracked-out caps label is chrome that appears whatever the
subject and reads as generated. Table header captions are the one legitimate
exception and are set in sentence case too.

The prose measure is capped at **68ch**. This tool renders `SKILL.md` bodies,
which are documents; letting them run the full width of a 1440px screen is the
most common way a document view becomes unreadable.

## Space and radius

**Space** is a 4px base with exactly eight steps — `--s1`…`--s7`, `--s9` —
`4 8 12 16 20 24 32 48`. The v1 scale shipped `--s7` and `--s9` both as
`32px`, so "the ninth step" was a name for the seventh and the sequence was
not a sequence; v2 makes it one and adds the 48px step a dialog body needs.
The gate asserts the step set exactly, so a ninth ad-hoc value cannot quietly
appear.

**Radius** is three steps and the *relationship* is the contract, not the
numbers: `--r-ctl 6px` (controls), `--r-panel 8px` (panels, callouts),
`--radius 12px` (dialogs). A control is rounder than a panel; a dialog is
squarer than a panel. One large radius applied to everything reads as
"template" before a single word of copy is read.

## Motion

`--dur 120ms` on paint properties only, `--ease cubic-bezier(0.2, 0, 0.2, 1)`,
inside the 100–160ms band. **No y control point may exceed 1.0** — overshoot
is the bounce/elastic tell and it makes a dense tool feel unsteady. No entrance
animation on content that was already there, no springs, no parallax.
`prefers-reduced-motion` disables all of it. The gate asserts the duration
bound, the curve, and the absence of an overshoot.

## Shell

```
┌──────────────────────────────────────────────────────────┐
│ topbar 48px: brand · search ⌘K · New skill · overflow     │
├──────────┬──────────────────┬────────────────────────────┤
│ 240px    │ 392px            │ 1fr                        │
│ rail     │ list             │ detail                     │
│          │                  │                            │
│ Scope    │                  │                            │
│ Views    │                  │                            │
│ Settings │                  │                            │
├──────────┴──────────────────┴────────────────────────────┤
│ status bar 24px: host:port · scope · last scan · locale   │
└──────────────────────────────────────────────────────────┘
```

The rail carries **the scope switcher with each root's token share**, so the
thing that determines whether your agents are truncated is visible from every
screen and not only from the overview. Library is full-bleed; Overview,
Quality and Settings are centred at a 1120px measure.

≥1280 sidebar + list + detail panel · 1024–1279 rail + list + overlay detail ·
768–1023 rail + single column, detail as a sheet · <768 drawer nav and
list/detail as separate full-height states with an explicit Back that returns
focus to the originating row. Zero horizontal page scroll from 320px up.

## Components

- **Buttons:** one primary per view (accent fill, white ink). Everything else
  is secondary (1px border) or ghost. Row actions are text buttons, never
  icon-only. 32px default, 28px compact.
- **Rows:** the primary line is the scope and observed state; paths are
  demoted into a disclosure. Selection is a 2px accent marker plus a tint —
  never a card lift, never a shadow.
- **State pill:** dot + label, tinted background at 12%.
- **Callout** (the "learn layer"): explains the concept sitting next to the
  number, not the number. **One per screen maximum** — two of them is chrome.
- **Meter (the signature component):** the context-budget bar. Track, fill, and
  a labelled 100% threshold rule on an axis running to **125%**, so a root at
  111% and one at 121% render as visibly different bars. On a 0–100% axis both
  clamp full and the chart hides its own point.
- **Diff view:** unified, mono, line numbers, add/remove tint **plus a sign
  glyph**, so it is not colour-only.
- **Stepper:** three steps, for Registry Fetch → Review → Commit.

## Don't change

These are refused defaults, recorded so a later pass cannot slide back.

- **Cream/parchment ground + terracotta accent.** `#faf7f1` + `#9e4415` is the
  "tasteful AI" cluster's exact coordinates and the first entry in every tell
  catalogue. Do not move the ground back toward warm.
- **Near-black ground + one vermilion accent in dark mode.** Also a named
  cluster, and the one finding the mechanical scanner raised on the prototype.
- **The blue accent proposed in `.redesign/DESIGN-V2.md` §C.** See *Why the
  palette did not become the proposal's blue*.
- **A third palette.** `index.html` starts at `data-theme="system"` and
  `preferences.js` resolves that to an explicit light/dark *before*
  `styles.css` loads, so no `@media (prefers-color-scheme: dark)` palette
  exists. One did, for years of accumulated drift, and it was the only way a
  dark-OS user on the default theme saw a different product from the one every
  test measured. The gate now fails if one reappears.
- **Purple gradients, gradient-filled headline text, glassmorphism, neon glow.**
- **Decorative `01 / 02 / 03` numbering** on unordered ideas. Number only
  genuine sequences.
- **One accented word inside a headline.** Emphasis lives in the type system.
- **Uppercase tracked-out labels above headings, and middle-dot-joined
  metadata.**
- **Bounce or elastic easing. Emoji as iconography — zero, anywhere.**
- **A runtime CDN.** No font link, no icon CDN, no webfont fetch. The icon set
  is a vendored Lucide subset (ISC) inlined as one `<symbol>` sprite; the
  sprite is `display:none` inline rather than a fetched file, because a sprite
  fetched over the network is a second round trip and a second failure mode.
- **A `unicode-range` on the vendored faces.**
- **Vendored bytes without their licence**, named so the gate can find it.
- **Invented scores, safety verdicts, or "recommended" claims.** The interface
  states observed facts. Where the product cannot observe something, the row
  says the signal is unavailable; it never substitutes a guess.

## Verification

Three layers, because guidance alone decays:

1. **This file** — the constraint. Read before designing any screen.
2. **`check_design_tokens.py`** — the enforcement. Re-derives every contrast
   ratio from the shipped stylesheet with the WCAG formula, asserts the space
   and radius scales, the type-step set, the motion bound, the absence of an
   overshoot, the absence of a third palette, and that this document's declared
   palette still equals the stylesheet's. No model, no network.
3. **`check_docs.py`** and the contract tests — the behaviour.

Plus `node ~/.claude/skills/avoid-ai-design/scripts/detect.mjs skillsmgr/webui/`
as an advisory anti-slop scan. It reports code-certain tells only; a clean scan
is necessary and not sufficient.

### One known validator artefact

`npx @google/design.md lint DESIGN.md` reports **0 errors and 1 warning**. The
warning is on `components.focus-ring`, complaining that the accent ring on the
surface is below the 4.5:1 text threshold.

That is the validator applying the **text** rule (1.4.3) to a **non-text**
component. A focus ring is a graphical object under 1.4.11, whose threshold is
**3:1** — which `line-strong` clears at 3.65:1 light / 3.74:1 dark. The token
was left correct and the warning left visible rather than darkening a border
until a checker that does not apply to it was satisfied.
`check_design_tokens.py` is the authority here.
