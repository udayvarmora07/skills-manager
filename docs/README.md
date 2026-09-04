# Docs Index — Skills Manager

**Version 0.1.0**

**AI manifest**: Entry point to the project docs. Every doc follows HADS: H1 title, version line, AI manifest, then `[SPEC]`/`[NOTE]`/`[?]` block markers on their own bold lines. All facts here were verified against source code on 2026-08-13; flag stale facts in `06-progress-log.md`.

## Document map

| Doc | Covers | Load when |
|---|---|---|
| @docs/01-architecture.md | Data model, data-dir layout, FS vs SQLite roles | Any task touching data or paths |
| @docs/02-modules.md | Module-by-module inventory, constants, key behavior | Any edit to `skillsmgr/` internals |
| @docs/03-cli-surface.md | Every command, alias, flag, exit code | Web UI work (must mirror CLI) or CLI QA |
| @docs/04-store-api.md | `Store` public API + SQLite schema | Any UI/store integration |
| @docs/08-web-ui.md | Web UI architecture, REST API, frontend map | Any web UI build or testing |
| @docs/06-progress-log.md | Dated log of changes, decisions, bugs | Before/after any session; keep updated |
| @docs/07-context-strategy.md | Hot/warm/cold loading model, compaction anchors | Long sessions, context management |
| @docs/SESSION-CONTEXT.md | Fast re-anchor cache: current state, common tasks, gotchas | Start of any session (preferred over re-reading source) |

## Reading order

1. `AGENTS.md` (root, hot cache — 5 min).
2. `docs/README.md` (this file).
3. Topic docs just-in-time per the map above — never all at once.
4. `docs/06-progress-log.md` to sync on recent changes, then update it when done.

## HADS conventions used here

- Version line within first 20 lines of each doc.
- AI manifest block before the first content section.
- `[SPEC]` = authoritative contract; `[NOTE]` = context/history; `[?]` = open question — resolve or remove it, never leave silently.

## Open questions

- `[?]` None currently. Resolved questions are recorded in 06-progress-log.md.
