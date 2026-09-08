# AGENTS.md — Skills Manager

**Version 0.3.0**

**AI manifest**: Operating manual for coding agents working in this repo. Read fully (it is the hot cache — deliberately small, router-style). For details, follow the `@docs/...` pointers instead of re-reading source. Human developers read this too.

## What this is

- `skills-mgr`: a Python CLI plus a **local web UI** for managing AI coding-agent skills: list, create, view, edit, search, validate, enable/disable, trash/restore, import/export, backup/restore, templates, history, db rebuild/resync. Tracks skills across **agent scopes** (claude-code, codex, cursor, opencode, gemini, commandcode, agents, project-local) — see @docs/08-web-ui.md.
- **Data model**: filesystem is the source of truth; SQLite at `<data>/skills-manager/skills-manager.db` is a rebuildable index only (`SCHEMA_VERSION = "1"`). Never trust SQLite over the filesystem; never hand-edit the DB.
- Skills live at `<data>/skills/<name>/SKILL.md`; disabled skills are `SKILL.md.disabled`. Data dir: `$SKILLS_MANAGER_DATA` -> `$XDG_DATA_HOME` -> `~/.local/share`, then `/skills-manager`.
- Agent scopes (e.g. `agents` = `~/.agents/skills`, the Command Code skills dir) are read/written directly on disk — no DB. `--scope agents` lists/creates/edits/removes/toggles the exact skills the `commandcode` CLI loads.

## Toolchain

- CLI: `python3 -m skillsmgr` (stdlib only). Web UI: `python3 -m skillsmgr webui` (alias `gui`) — stdlib backend, Vue 3 frontend (vendored, no build step).
- Test suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (stdlib-only regression/contract tests). Smoke tests `python3 smoke_store.py` (Store API) and `python3 smoke_web.py` (web REST API) remain executable end-to-end checks.
- Docs format: HADS (see @docs/README.md). Markers: `[SPEC]` authoritative, `[NOTE]` context, `[?]` uncertainty.

## Navigation (router)

| Need | Go to |
|---|---|
| Where things live / repo map | @docs/01-architecture.md |
| Module-by-module inventory | @docs/02-modules.md |
| Exact CLI commands/flags/exit codes | @docs/03-cli-surface.md |
| Store public API + SQLite schema | @docs/04-store-api.md |
| Web UI architecture, REST API, frontend map | @docs/08-web-ui.md |
| What changed and when | @docs/06-progress-log.md |
| How sessions should load context | @docs/07-context-strategy.md |
| Fast session re-anchor (common tasks, gotchas) | @docs/SESSION-CONTEXT.md |

## Judgment boundaries

- **ASK** before: adding a new CLI command or Store method, changing the SQLite schema or `SCHEMA_VERSION`, deleting/trashing data, switching UI framework, deviating from locked constraints (below).
- **ALWAYS**: keep the filesystem as source of truth; surface `StoreError`/`SkillNotFound` as clean dialogs/errors, never raw tracebacks; run `python3 smoke_store.py` after touching `store.py` and `python3 smoke_web.py` after touching `webapp.py`; update `task.md` and `docs/06-progress-log.md` after each change.
- Never fabricate metrics or docs facts; if unsure, mark `[?]` and ask.

## Locked constraints

**[SPEC]** Do not deviate without asking:

1. Filesystem stays the source of truth.
2. SQLite schema/`SCHEMA_VERSION` unchanged.
3. CLI stdlib-only.
4. Web UI: stdlib backend, no build step, no new runtime dependencies; Vue vendored in-repo; binds 127.0.0.1 by default.
5. No new CLI commands or Store methods without approval.

## Context strategy (short version)

Hot cache = this file. Warm = docs near the code they describe (incl. `docs/SESSION-CONTEXT.md` for fast re-anchor). Cold = anything else, loaded just-in-time. Explicit pointers beat dumping content inline. Full model: @docs/07-context-strategy.md.
