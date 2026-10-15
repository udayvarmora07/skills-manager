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

## PHASE 4 — Build (order) [ ]
- [ ] 1 tokens+globals+fonts(polish) · 2 primitives (button/input/select/card/modal/
      drawer/toast/tabs/table/tooltip/badge/skeleton) · 3 app shell (nav/header/
      rail/footer/palette) · 4 Overview · 5 Library+detail · 6 Quality · 7 Profiles ·
      8 Workspaces · 9 Install · 10 Recovery · 11 Settings · 12 Trash · 13 dialogs depth ·
      14 states (empty/loading/error/success/offline/denied) · 15 responsive mobile-first ·
      16 dark-mode art direction · 17 motion polish (CSS-only) · 18 a11y pass · 19 perf ·
      20 cleanup (remove old CSS only after migrated)
- Critique bar: each page ≥9/10 on hierarchy, type, color, spacing, motion, clarity,
  a11y, perf, originality (max 3 rounds/page; log scores here)

## PHASE 5 — Verify (per item) [ ]
- Build/lint/typecheck/tests green; component + smoke tests added where valuable
- Screenshots 375/768/1280/1920 × light/dark in `.design/screenshots/`
- a11y (keyboard, focus, landmarks, contrast, reduced-motion, zero console errors)
- Strict diff review + commit per item on `design/<date>`

## Scores (fill during critique loop)
(none yet)

## BLOCKED
(none)
