# PRODUCT BRIEF — Skills Manager web UI (2026-10-15)

## What it is
The local control plane for AI coding-agent skills (`SKILL.md` files). A loopback-only
web UI (vendored Vue 3, stdlib Python backend, offline) to inventory, inspect, compare,
sync, validate, recover, and budget the context footprint of skill documents spread
across agent scopes (global store + claude-code/codex/cursor/opencode/gemini/
commandcode/agents dirs). Filesystem is the source of truth; the UI is read-first,
explicit-action-second: nothing mutates without a review/preview step.

## Core value
Answer in seconds, with file-level evidence: "what can each of my agents load, where
does each copy live, do copies disagree, what is malformed, and how much context
window does it all cost?" — then offer safe, reversible operations (sync, update
preview, trash/restore, export/import).

## Personas
1. **Divergent-degrees Dan** — 4+ agents installed, behaviors differ; suspects file
   drift. Needs: Library grouping by logical skill, copy comparison, divergence calls.
2. **Context-budget Priya** — agent instructions feel truncated; needs per-root token
   meters vs window, largest-file triage, honest measurement (never scores).
3. **Careful-operator Cole** — syncs/edits across scopes; needs previews, trust gates
   (registry), update reviews with diffs, trash+undo, batch plans with frozen targets.
4. **First-run Fern** — just installed; needs the first-scan guide to teach the mental
   model (a skill NAME is not one FILE) without breaking anything.

## Top jobs-to-be-done
- Triage "what needs attention" from Overview in <30s (attention queue → deep link).
- Find a skill, read its exact copies, copy a path, check validity (Library).
- Decide what fits in context (budget meters, largest lists, quality sizes).
- Sync/enable/disable/remove with preview + recovery (batch bar, sync modal, trash).
- Install vetted registry skills through an explicit trust gate (Install).
- Recover from mistakes (Recovery: trash restore, snapshots, export/import).
- Configure once (Settings: theme, text size, locale) and never think about it again.

## Critical flows
Onboarding (first-scan guide) → triage (Overview) → inspect (Library detail) →
act-with-preview (sync/update/batch/install) → recover (trash/snapshots). Settings and
Quality are supporting loops. Command palette + search are the power-user shortcuts.

## Current UX problems (author's read; auditor's list lands separately)
- Reads as a competent admin panel, not a premium instrument: cards-with-shadows
  mostly removed in the re-skin, but composition is still chrome-heavy (rail + bar +
  head + sidepanel stack before content on several views).
- Overview leads with process ("Reading the observed skill inventory…") rather than
  answers; greeting/orientation is thin vs the prototype's guided hero.
- Library list carries 4 concerns per row (checkbox, dot, name, identities, badges,
  tokens) — scannable but dense; grid mode exists yet cards repeat identically.
- Detail pane mixes actions/meta/instances/prose with even visual weight; the DOCUMENT
  (the actual SKILL.md) doesn't feel like the hero.
- Dialogs are solid but numerous (14 keys); some could be progressive (e.g. update
  review is necessarily long — fine; sync/install could be tighter).
- Empty states are honest but generic; first-run Fern gets guidance only on Overview.
- Motion is correct (120ms paint-only) but joyless: no purposeful transitions between
  list→detail, no skeleton-to-content choreography beyond shimmer.
- Dark theme is consistent, not designed (carried tokens, no art direction).
- Mobile: list↔detail works, but power flows (batch, update review) are desktop-shaped.

## Brand personality (assumption, logged)
Calm, exact, old-fashioned-in-a-good-way — "a measuring instrument laid over a pile
of documents." Cool paper, one teal ink, mono identifiers, hairlines not boxes, status
never color-alone, honest about what cannot be observed. Audience: developers who
distrust dashboards that invent numbers.

## Non-goals for the design loop
No backend/API/route changes; no new deps/CDN/build; no invented scores or inferred
provenance; no marketing voice; no gamification; no AI-generated look (no purple
gradients, no glassmorphism, no emoji icons, no template card grids).
