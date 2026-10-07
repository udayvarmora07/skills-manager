---
version: alpha
name: Skills Manager
description: >-
  A local authority over the skill files that coding agents actually load. For a
  developer whose four agents disagree and who has no way to see why. It should
  feel like a measuring instrument laid over a pile of documents: calm, exact,
  and slightly old-fashioned in the way good laboratory equipment is.
colors:
  ground: "#f2f3f1"
  surface: "#fbfbfa"
  surface-2: "#eceef0"
  ink: "#1a1c1f"
  ink-2: "#454a50"
  muted: "#5f666d"
  muted-faint: "#6b727a"
  primary: "#0d6a63"
  primary-deep: "#0a524d"
  primary-ink: "#ffffff"
  primary-bg: "#e2f0ee"
  ok: "#3f6b3f"
  ok-bg: "#e9f0e9"
  warn: "#7d590e"
  warn-bg: "#f5f0e0"
  error: "#a33526"
  error-bg: "#f7e8e5"
  line: "#e4e6e9"
  line-strong: "#868d95"
typography:
  display:
    fontFamily: "IBM Plex Sans"
    fontSize: 26px
    fontWeight: 600
    letterSpacing: "-0.021em"
  body:
    fontFamily: "IBM Plex Sans"
    fontSize: 13px
    lineHeight: 1.55
rounded:
  sm: 4px
  md: 6px
spacing:
  sm: 4px
  md: 12px
  lg: 24px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-ink}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  button-quiet:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  button-danger:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.error}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    height: 30px
  state-active:
    backgroundColor: "{colors.ok-bg}"
    textColor: "{colors.ok}"
    rounded: "{rounded.sm}"
    padding: "2px 7px"
  state-divergent:
    backgroundColor: "{colors.warn-bg}"
    textColor: "{colors.warn}"
    rounded: "{rounded.sm}"
    padding: "2px 7px"
  state-invalid:
    backgroundColor: "{colors.error-bg}"
    textColor: "{colors.error}"
    rounded: "{rounded.sm}"
    padding: "2px 7px"
  state-unaddressable:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.muted}"
    rounded: "{rounded.sm}"
    padding: "2px 7px"
  callout:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.sm}"
    padding: "12px 14px"
  meter-track:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    height: 8px
  meter-fill-over:
    backgroundColor: "{colors.error}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    height: 8px
  meter-fill-under:
    backgroundColor: "{colors.ok}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    height: 8px
  divider:
    backgroundColor: "{colors.line}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    height: 1px
  focus-ring:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.line-strong}"
    rounded: "{rounded.sm}"
    height: 2px
  primary-pressed:
    backgroundColor: "{colors.primary-deep}"
    textColor: "{colors.primary-ink}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  row-selected:
    backgroundColor: "{colors.primary-bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
  prose-body:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
  prose-muted:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.muted-faint}"
    typography: "{typography.body}"
---

## Overview

A skill is a markdown file that gets concatenated into a model's context window.
Users of this tool arrive because their agents are behaving differently and they
suspect the cause is their files. So the product's world is not "developer
dashboard" — it is **paperwork**: documents, copies, provenance, corrections,
and the budget of a single context window.

The visual source is the **printer's proof sheet**: a bone-coloured stock that
is cool rather than warm, set with one ink used like a stamp, ruled with
hairlines instead of boxes, and annotated in the margin wherever a claim needs
its evidence. Structure comes from rules and alignment, not from cards and
shadows. Colour is spent on exactly one job — *state* — plus one reserved ink
for *interaction*.

This direction was chosen by the maintainer from three rendered candidates
(`docs/prototype-decision.md`). Prototype A — "Warm Instrument" — supplied the
composition, density and information architecture. Its palette was replaced for
the reasons in **Don't change** below.

## Colors

Every value below was **measured**, not chosen by eye. The ratios are against
`--surface` (`#fbfbfa` light, `#171a1e` dark), computed with the WCAG 2.x
relative-luminance formula, and re-checked whenever a token changes. The
checking script is `check_design_tokens.py` and it runs in CI.

- **Ground `#f2f3f1` (light) / `#101316` (dark):** a cool bone, not a parchment.
  This product is stared at for hours while debugging an agent; warm cream is
  fatiguing at that duration and is also the first entry in the "tasteful AI"
  cluster list. Cool bone reads as office paper under fluorescent light.
- **Surface `#fbfbfa`:** one step above ground so panes separate without a rule
  (1.07:1) — the boundary is carried by a hairline, not by a tonal jump.
- **Ink `#1a1c1f` → `#6b727a`:** four steps, every one of which clears 4.5:1 on
  surface (16.49, 8.64, 5.62, 4.55). There is deliberately **no grey that
  fails AA**, including the most de-emphasised step, because this tool's
  de-emphasised text is usually a file path and a path you cannot read is a
  path you cannot debug.
- **Signal `#0d6a63` (light) / `#4fc7bd` (dark):** one reserved ink for
  selection, focus and the single primary action per view. Chosen from a hue
  family with zero overlap against the rejected copper — not because teal is
  fashionable, but because it must not be confusable with any of the four
  status colours at a glance, which is its entire job.
- **Status:** `ok #3f6b3f`, `warn #7d590e`, `err #a33526`, `mute #5e646b`.
  Red means *malformed*, never *divergent*. Divergent content is amber: it is
  attention-worthy but it is not an error, and colouring it red would teach
  users to ignore red.

**Status is never colour alone.** Every state is a square glyph + colour + the
word, because the whole point of this tool is that two agents disagreeing is a
*fact* and facts must survive being printed in black and white.

## Typography

Two families, and both are **vendored as static woff2** (`webui/static/fonts/`).
Never fetched from a CDN at runtime: this app must work offline and inside a
locked-down network, and a font request to a third party is a third party in
the page.

- **IBM Plex Sans** — interface and prose. Chosen over `system-ui` for a
  functional reason as much as an aesthetic one: `system-ui` renders
  differently on every platform, and this tool's job is comparing a file on
  macOS with a file on Linux. Identical glyphs on both machines is a correctness
  property here.
- **IBM Plex Mono** — every identifier: skill names, file paths, content
  hashes, and every number. With `font-variant-numeric: tabular-nums` so columns
  of figures align without a layout hack.

Scale: `display 26/1.18`, `title 17/1.30`, `head 13.5/1.35`, `body 13/1.55`,
`small 12/1.45`, `micro 10.5/1.3` at 0.075em tracking, `num 12/1`,
`id 12.5/1.35` mono. **11px is the absolute floor** for any text a user must
read; `micro` is for non-essential labels only.

The prose measure is capped at **68ch**. This tool renders `SKILL.md` bodies,
which are documents; letting them run the full width of a 1440px screen is the
single most common way a document view becomes unreadable.

## Layout

Three columns plus a header and a status footer, all full-height:

```
┌──────────────────────────────────────────────────────────┐
│ topbar: brand · search · nav · primary action            │
├──────────┬──────────────────┬────────────────────────────┤
│ 210px    │ 392px            │ 1fr                        │
│ rail     │ list             │ document                   │
│          │                  │                            │
│ Workspace│                  │                            │
│ Scopes   │                  │                            │
│ Index    │                  │                            │
└──────────┴──────────────────┴────────────────────────────┘
```

The rail is not navigation-plus-decoration: **Scopes** lives in it with the
token share of each root, so the thing that determines whether your agents are
truncated is visible from every screen, not only the overview.

Below 1080px the three columns become two (the rail collapses into the topbar);
below 760px list and document become separate full-height states with an
explicit Back action that returns focus to the originating row.

## Components

- **Buttons:** one primary per view, filled `signal`. Everything else is quiet —
  a bordered ghost. A row's actions are text buttons, never icon-only.
- **Rows:** 56px minimum target, 11px type floor, a 1px rule between rows and
  **no card border**. The row's primary line is the name; the scope list and
  observed state sit under it in `--ink-3`. Selection is a 2px left rule plus a
  tint — never a card lift, never a shadow.
- **Badges:** square glyph + colour + word. `--warn-bg`/`--warn` etc.
- **Callouts** (the "learn layer"): a 2px left rule in `signal`, `--surface-2`
  fill, `--ink-2` text. They explain the concept sitting next to the number, not
  the number. There is one per screen maximum.
- **Meter (the signature component):** the context-budget bar. Track, fill, and a
  labelled 100% threshold rule. The axis runs 0–125% so the threshold sits at
  80% of the track — on a 0–100% axis, 111% and 121% both render as a full bar
  and the chart hides its own point.
- **Motion:** 120ms, `cubic-bezier(0.2, 0, 0.2, 1)`, on paint properties only.
  No transforms, no springs, no bounce/elastic easing, no entrance animation on
  content that was already there. `prefers-reduced-motion` disables all of it.

## Don't change

These are refused defaults, recorded so a later pass cannot slide back into them.

- **Cream/parchment ground + terracotta accent.** Prototype A used `#faf7f1` +
  `#9e4415`. That is the "tasteful AI" cluster's exact coordinates, and it is
  the first entry in every tell catalogue. Ground and signal were re-derived
  from the subject instead. **Do not move the ground back toward warm.**
- **Near-black ground + one vermilion accent in dark mode.** Also a named
  cluster, and the one finding the mechanical scanner actually raised on the
  prototype. The dark theme is a full palette, not one neon on black.
- **Purple gradients, gradient-filled headline text, glassmorphism, neon glow.**
- **Decorative `01 / 02 / 03` numbering.** Prototype A numbered three unordered
  ideas; the numbering was removed. Number only genuine sequences.
- **One accented word inside a headline.** Prototype A set "3 of 7" apart in the
  hero. Emphasis is built into the type system, not painted onto one word.
- **Uppercase tracked-out labels above every heading, and metadata joined with
  middle dots.** Both were flagged mechanically in the current codebase
  (`SD4`, `SD4d`). Keep a label only when it carries information the heading
  does not; set it in sentence case, in the body face.
- **Bounce or elastic easing.** Dated.
- **Emoji as iconography.** Zero emoji anywhere in this interface.
- **A runtime CDN.** No Google Fonts link, no icon CDN, no webfont fetch. See
  the CSP: `font-src 'self'`.

## Verification

Three layers, because guidance alone decays:

1. **This file** — the constraint. Read before designing any screen.
2. **`check_design_tokens.py`** — the enforcement. Re-computes every contrast
   ratio in `styles.css` against the WCAG formula and fails on a regression.
   Runs with no model and no network.
3. **`check_docs.py`** and the frontend contract tests — the behaviour.

Plus `node ~/.claude/skills/avoid-ai-design/scripts/detect.mjs skillsmgr/webui/`
as an advisory anti-slop scan. It reports code-certain tells only; a clean scan
is necessary and not sufficient.

### One known validator artefact

`npx @google/design.md lint DESIGN.md` reports **0 errors and 1 warning**. The
warning is on `components.focus-ring`, complaining that `line-strong` on
`surface` is `3.24:1`, "below WCAG AA minimum of 4.5:1".

That warning is the validator applying the **text** threshold (1.4.3, 4.5:1) to a
**non-text** component. A focus ring is a graphical object and falls under
1.4.11, whose threshold is **3:1** — which `3.24:1` clears. The token was left
correct and the warning left visible rather than darkening `line-strong` until a
checker that does not apply to it was satisfied. `check_design_tokens.py` is the
authority here and it tests the ring against 3.0.