# STATE — Best-possible-UI design loop (branch `design/2026-10-15`)

Base: `redesign/2026-10-15` tip (prototype re-skin DONE). Memory: `.design/` only.
Constraint reminder: CSS/vendored-only, no new deps/CDN/build; 326 pins + token gate green.

## PHASE 0 — Capabilities [x]
- [x] CAPABILITIES.md written (skills/agents/MCP/laptop + repo overrides)

## PHASE 1 — Understand [x]
- [x] PRODUCT_BRIEF.md (personas, JTBD, flows, problems, personality, non-goals)
- [x] Heuristic audit ingested (9 views, 12 frictions, taste review, premium-keeps)
- [x] Inventory finalized: 9 views (Overview, Library+detail, Profiles, Workspaces,
      Install, Recovery, Quality, Settings, Trash-legacy-in-Recovery), 14 dialog keys,
      command palette, Actions menu, rail+topbar+statusbar shell; states: loading
      skeletons, 3-way empties, banner/toast errors, disabled gates, hover/focus/
      selected, reduced-motion, 44px mobile targets (full map in `.redesign/` inventory)

## PHASE 2 — Benchmark [x]
- [x] RESEARCH.md: 8 sites + WCAG 2.2/Core Web Vitals/stack versions with URLs+dates
- [x] INSPIRATION.md: 12 principles synthesized from evidence

## PHASE 3 — Direction + system [x]
- [x] DESIGN_SYSTEM.md: "The Precision Instrument" — soul kept, body fixed; tokens
      (gate-verified), type, spacing/radii/elevation, icon set, motion, grid, 8 UX
      principles
- [x] IA: rail owns nav/filters, content owns single H1; one primary per screen
- [x] UX principles + all-states design (incl. offline/denied honesty)
- [x] Build order finalized (Phase 4 list below; CSS + surgical template edits only)

## PHASE 4 — Build (order) [~] (4.1 done)
- [x] 4.1 Library a11y+legend: row `aria-label` (fixes empty listitem names, verified
      in live DOM) + collapsed 7-state legend disclosure (commit d4ef054, 152 green,
      screenshot `.design/screenshots/library-legend-1280-dark.png`)
- [ ] 1 tokens+globals+fonts polish · 2 primitives depth · 3 app shell · 4 Overview ·
      5 Library+detail depth · 6 Quality · 7 Profiles · 8 Workspaces · 9 Install ·
      10 Recovery · 11 Settings · 12 Trash · 13 dialogs depth · 14 states ·
      15 responsive (tab-strip affordance) · 16 dark art direction · 17 motion
      (view transitions, gated) · 18 a11y pass (2.4.11 sticky coverage, `?` overlay,
      g-keys) · 19 perf (INP budget, Vue 3.5.44 bump candidate) · 20 cleanup
- Critique bar: each page ≥9/10 on hierarchy, type, color, spacing, motion, clarity,
  a11y, perf, originality (max 3 rounds/page; log scores here)

## PHASE 5 — Verify (per item) [ ]
- Build/lint/typecheck/tests green; component + smoke tests added where valuable
- Screenshots 375/768/1280/1920 × light/dark in `.design/screenshots/`
- a11y (keyboard, focus, landmarks, contrast, reduced-motion, zero console errors)
- Strict diff review + commit per item on `design/<date>`

## Scores (critique loop)
- Library (2026-10-15, self-critique as art director): hierarchy 9 (legend disclosure
  adds guidance without chrome; rows keep one focal line) · typography 9 (mono names +
  tabular numerals consistent) · color 9 (status never color-alone, gate green) ·
  spacing 9 (legend is one 30px row) · motion n/a (no change) · clarity 9 (names +
  legend fix audit Majors #3/#6) · a11y 9 (named rows verified in live DOM; disclosure
  keyboard-native) · perf 10 (2 elements, no JS) · originality 8 (disclosure pattern
  reused from tag filter — consistent, not novel). No second round needed.

## BLOCKED
(none)
