# DECISIONS

## 2026-10-15 — Base the design loop on `redesign/2026-10-15`, not main
Options: (a) branch from main and redo; (b) build on the prototype re-skin (DONE).
Chose (b): the re-skin is reviewed, tested (1234 green), and already encodes the
approved prototype tokens; redoing it would waste the evidence. New branch
`design/2026-10-15` keeps the two loops' histories separable.

## 2026-10-15 — Repo constraints override prompt's component-library suggestions
The mission text invites Radix/shadcn/Tailwind/Motion/Google Fonts/component MCPs.
All violate locked repo constraints (stdlib-only, no build step, no new runtime deps,
`font-src 'self'`, offline). Decision: CSS-only + vendored-Vue implementation; borrow
PRINCIPLES from great sites, never their code/assets. Logged in CAPABILITIES.md.

## 2026-10-15 — Audit + benchmarks delegated, brief written inline
Rationale: brief needs product judgment (done from direct knowledge); audit benefits
from fresh eyes (subagent with screenshots); benchmarks need web legwork (subagent).
Main context stays clean for synthesis (Phases 2-3) and build (Phase 4).

## 2026-10-15 — Audit triage: artifacts vs genuine (heuristic ses_ec0cc07f)
Dead-server artifacts (server died mid-audit; CSS-irrelevant, behavior untouched):
crit-1 detail-load failure, crit-2 global collapse, error-triplication instances,
Workspaces/Recovery toasts. GENUINE and in-scope: empty listitem names (a11y, needs
markup), search-scope confusion (product decision), error pattern triplication
(needs one pattern), jargon-without-legend, Actions-menu overflow, CTA competition,
Profiles free-text refs, Recovery handoff without deep link, 375 tab-strip
affordance, echo H1s, trust footer. Premium-keeps (do not touch): budget hero,
honest empties, palette+kbd, read-only posture copy, dark+Plex pairing, forms.

## 2026-10-15 — Direction: "The Precision Instrument" (evolution, not rebrand)
Options: (a) new visual identity; (b) keep approved tokens, fix composition/
hierarchy/errors/motion. Chose (b): tokens are gate-enforced + user-approved via
prototype; the audit's complaints are compositional (echo H1s, flat hierarchy,
tripled errors) and experiential (legends, keyboard, motion) — all fixable without
new hues/fonts/deps. Bolder rebrand would break pins and the offline constraint
for zero user-job gain.
Rationale: brief needs product judgment (done from direct knowledge); audit benefits
from fresh eyes (subagent with screenshots); benchmarks need web legwork (subagent).
Main context stays clean for synthesis (Phases 2-3) and build (Phase 4).
