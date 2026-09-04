# Context Strategy — Session Loading Model

**Version 0.1.0**

**AI manifest**: How sessions (human or agent) should load context for skills-manager. The goal: full situational awareness at minimum tokens, no staleness, no duplicated facts. This file is the cold-tier spec; `AGENTS.md` is the hot tier that summarizes it.

## The model

**[SPEC]** Three tiers:

| Tier | Contents | Loaded |
|---|---|---|
| Hot | `AGENTS.md` (root): repo map, router table, judgment boundaries, toolchain | Always, fully |
| Warm | Docs physically near the code they describe (`@docs/...`); `task.md` checklist | Just-in-time per task |
| Cold | Everything else: source modules, history, old logs | On demand, then discarded |

**[SPEC]** Rules:
- Read `AGENTS.md` fully (it is deliberately small — the hot cache).
- Use the router table in `AGENTS.md` to pick the one or two `@docs/...` files for the current task. Never load all docs at once.
- Prefer explicit pointers (`@docs/04-store-api.md`, `file:line`) over inlining content in this doc or in answers.
- `task.md` is the live checklist; update it after every change, before ending a session.
- Flag stale facts in `docs/06-progress-log.md`, then fix the owning doc — never silently reuse a stale fact.

## What to load when

| Task | Load |
|---|---|
| Any change to `store.py` | @docs/04-store-api.md + run `python3 smoke_store.py` |
| Any CLI work / GUI mirroring | @docs/03-cli-surface.md |
| GUI build or testing | @docs/05-gui-plan.md + @docs/04-store-api.md |
| Any edit to `skillsmgr/` internals | @docs/02-modules.md |
| Anything touching paths/data | @docs/01-architecture.md |
| Long session or after compaction | `AGENTS.md` (re-anchor) + @docs/07-context-strategy.md + @docs/06-progress-log.md |

## Compaction anchors

**[NOTE]** After a context compaction, re-anchor on: `AGENTS.md` (rules and router), `task.md` (what is done/pending), `docs/06-progress-log.md` (recent facts). Do not re-read the full docs tree; load cold files lazily again only if the task touches them.

## Budget guidance

**[NOTE]** Keep hot cache small (AGENTS.md <=150 lines) so ~100% of it can stay resident. Aim to stay within comfortable context utilization (roughly 40–60%) on typical sessions; load cold files, extract the facts, then drop them. `docs/` files themselves follow HADS so they read compactly for models.

## Open questions

- `[?]` None. If a session reveals a better loading pattern, record it here and bump the version.