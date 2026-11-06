# DESIGN SYSTEM — "The Precision Instrument" (2026-10-15)

## Visual concept
Keep the soul (cool bone paper, one teal ink, mono identifiers, hairlines, status
never color-alone, honesty about the unobservable). Fix the BODY the audit proved is
still admin-panel: echo H1s, flat button hierarchy, tripled errors, jargon without
legend, document that isn't the hero, joyless motion. One focal point per screen;
chrome recedes, evidence leads. No new hues, no new fonts, no new deps.

## Color (semantic tokens; AA verified by `check_design_tokens.py` — the gate stays)
- Light: keep shipped tokens (`--bg #f2f3f1`, `--surface #fbfbfa`, inks 16.49–4.55:1,
  `--accent #0d6a63`, ok/warn/err/mute + washes). No new colors.
- Dark: keep shipped dark ramp (teal `--accent #4fc7bd`); art-direct surfaces so
  panes separate by tone + divider (existing technique), not by new hues.
- Rules: status = glyph + word + tint (kept); ONE solid primary per view (new
  enforcement — demote the rest to quiet/ghost); errors share ONE banner pattern
  (scope + cause + scoped retry + dismiss) replacing banner×2+toast×2 pileups.
- Focus: 2px teal outline + ring kept; fix 2.4.11 risk — sticky modal head/foot must
  never cover the focused control (scroll-margin + scrollIntoView block:'nearest'
  audit item).

## Typography
IBM Plex Sans (prose/UI) + Plex Mono (identifiers, ALL numerals tabular) — vendored,
self-hosted, unchanged. Scale: keep shipped ramp + laptop uplift (from re-skin);
reader prose 13–15px/1.65–1.7 with 68ch cap; H1 per screen exactly once (kill echo
H1s — left rail owns navigation/filters, content owns the single H1). Sentence case
everywhere; micro labels 11px floor kept.

## Spacing / radii / elevation / borders
4px base scale kept; panels 6px / controls 4px kept. Hairlines for structure; shadow
reserved for overlays + menus (kept). New: section rhythm — page head (context +
H1 + lede + ONE primary), content, footnotes; consistent 24–28px section gaps.

## Iconography
Keep the existing inline-SVG stroke set (17px, 1.75, round caps); extend ONLY with
same-style symbols (legend glyphs, outline-nav, shortcut kbd). Zero emoji. No icon
CDN ever.

## Motion (CSS-only; `prefers-reduced-motion` disables all)
120ms paint-only micro-feedback kept. ADD, gated on no-preference: same-document
View-Transition fade/slide for list→detail + dialog enter (instant fallback);
skeleton→content crossfade instead of pop; filter keystroke→paint budget <150ms
(INP headroom). No entrance choreography, no springs, no bounce (gate: y≤1).

## Layout grid
Desktop: rail 220 / list 320–380 / document 1fr (kept, pinned); tablet: rail 136 /
stacked health (fixed in re-skin); phone: top tabs + list↔detail + 44px targets
(kept) + tab-strip scroll affordance (new). Document pane: sticky mini header
(breadcrumb + state pill + actions) + 68ch reader + H2/H3 outline nav for long docs.

## UX principles (this product)
1. Answers before process: every view opens with the decision, then the evidence.
2. One primary per screen; destructive always behind preview + recovery path.
3. Undo over confirm; toasts carry the inverse action wherever backend allows.
4. Errors: one pattern — what failed (scope), why (cause, no jargon), what now
   (scoped retry + dismiss). Never tripled, never view-leaking.
5. Jargon earns a legend: first-use glossary for observed/divergent/linked/
   unaddressable/effective; pills capped at two + `+N` with full list on hover/focus.
6. Keyboard parity: `?` overlay, `g+key` prefixes, palette owns secondary verbs;
   list rows are real options with names (fix empty listitem names).
7. Local-first trust bar: `data stays on this machine + counts + theme/locale` as one
   13px high-contrast footer, not microcopy.
8. Offline honesty: local-only views (Settings, Recovery tools) work with zero
   network; failed loads state scope + offer scoped retry, never a dead page.

## What changes vs today (build order in STATE.md)
Composition + hierarchy + error pattern + legends + reader hero + motion + footer —
implemented in CSS + surgical Vue-template edits (attributes/labels/order only; no
logic, no API, no route changes). Every edit re-verified against the 326 pins.
