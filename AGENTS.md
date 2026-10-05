# AGENTS.md — Skills Manager

**Version 0.3.0**

**AI manifest**: Operating manual for coding agents working in this repo. Read fully (it is the hot cache — deliberately small, router-style). For details, follow the `@docs/...` pointers instead of re-reading source. Human developers read this too.

## What this is

- `skills-mgr`: a Python CLI plus a **local web UI** for managing AI coding-agent skills: list, create, view, edit, search, validate, enable/disable, trash/restore, import/export, backup/restore, templates, history, db rebuild/resync. Tracks skills across **agent scopes** (claude-code, codex, cursor, opencode, gemini, commandcode, agents, project-local) — see @docs/08-web-ui.md.
- **Data model**: filesystem is the source of truth; SQLite at `<data>/skills-manager/skills-manager.db` is a rebuildable index only (`SCHEMA_VERSION = "1"`). Never trust SQLite over the filesystem; never hand-edit the DB.
- Skills live at `<data>/skills/<name>/SKILL.md`; disabled skills are `SKILL.md.disabled`. Data dir: `$SKILLS_MANAGER_DATA` -> `$XDG_DATA_HOME` -> `~/.local/share`, then `/skills-manager`.
- Agent scopes (e.g. `agents` = `~/.agents/skills`, the Command Code skills dir) are read/written directly on disk — no DB. `--scope agents` lists/creates/edits/removes/toggles the exact skills the `commandcode` CLI loads.

## Toolchain

- CLI: `python3 -m skillsmgr` (stdlib only). Parser/handlers are split behind the stable `skillsmgr.cli` adapter (`cli_parser.py`, `cli_handlers.py`). Web UI: `python3 -m skillsmgr webui` (alias `gui`) — stdlib backend, Vue 3 frontend (vendored, no build step); `domain.js` loads before `app.js`.
- Test suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (stdlib-only regression/contract tests). Smoke tests `python3 smoke_store.py` (Store API) and `python3 smoke_web.py` (web REST API) remain executable end-to-end checks.
- Docs format: HADS (see @docs/README.md). Markers: `[SPEC]` authoritative, `[NOTE]` context, `[?]` uncertainty.
- Packaging: build only with the pinned, hash-verified toolchain — `python3 -m pip install --require-hashes -r requirements-build.txt` then `python3 -m build --no-isolation --wheel --sdist --outdir dist` (SEC-8). `check_package_data.py` asserts the vendored Vue sha256 (SEC-9) and rejects an artifact shipping `tests/`, `docs/`, `.env`, a database or bytecode (SEC-13); `MANIFEST.in` prunes the suite from the sdist. `skillsmgr/examples/skills-manager-management/` is the agent-facing management skill, shipped as **package data** so it reaches every install (a repository-only `examples/` directory did not, in either the wheel or the sdist); `check_package_data.py` proves it is present and readable.

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

## Hostile self-review before declaring done

**[SPEC]** A green ladder is evidence about the *tests*, not about the change.
Run these before calling anything done — and again before committing, against
the diff rather than the intention:

1. How would a malicious or careless caller abuse this? (traversal, replay,
   race, enumeration, a value that reaches the filesystem or a terminal)
2. What happens at 0 items, 1 item, and 10,000 items?
3. What if it runs twice, concurrently, or out of order?
4. What if the client double-clicks, refreshes, or disconnects mid-flow?
5. Does every new branch also have a `finally`/rollback, and does every new
   claim in a docstring or doc have a reader?
6. Would this still be true if the thing I checked is partial, corrupt, or
   missing — not just happy?
7. Is there a simpler way?

Then: **re-run the ladder on the current tree** (another session may have
edited it), and state plainly what you verified, what you assumed, and what you
could not check.

**[NOTE]** This is not decorative. On 2026-10-05 a review against exactly this
list found **six** defects in a change that had already passed 937 tests and
every gate — including a `GET /api/history` that answered HTTP 500 with
`no such table: history`, and a docstring promising a write path behaved a way
it did not. See `docs/06-progress-log.md`.

**Stuck protocol.** Max 5 attempts at the same failure with the same approach;
after 2, change approach (re-read the error, check the docs for the *installed*
version, bisect, reduce to a minimal repro). After 5, write down what you tried
and what you learned, move to the next unblocked task, and say so. Never disable
a test, a lint rule, or a gate to get to green.

## Concurrent writers

**[SPEC]** One writer per working tree, per task. This repo has been edited by two
agent sessions at once (two GUI chats on the same workspace, or a linked
worktree), and it cost real work: `edit` calls failing with "file changed since
it was read", a gate going red for no visible cause, and one session's diff
reverting the other's.

- Before your first edit, check whether another session is mid-turn on this path.
- Do not start a batch another session already has in flight. Split by file or
  area, or serialize — never both write `store.py` / `webapp.py` at once.
- Never `git add` / commit / `stash pop` while another session is mid-batch.
- Pausing or handing off? Take a backup plus a non-destructive checkpoint
  (`git stash create` then `git update-ref refs/wip/<name> <sha>`) first.
- Symptom not to ignore: a complexity-ratchet failure on a function you did not
  touch means someone else's change landed without its baseline update.
- Before declaring work done, re-run the ladder on the *current* tree — a green
  result from earlier in the session is not evidence about a tree someone else
  has since edited.

## Locked constraints

**[SPEC]** Do not deviate without asking:

1. Filesystem stays the source of truth.
2. SQLite schema/`SCHEMA_VERSION` unchanged.
3. CLI stdlib-only.
4. Web UI: stdlib backend, no build step, no new runtime dependencies; Vue vendored in-repo; binds 127.0.0.1 by default.
5. No new CLI commands or Store methods without approval.

## Context strategy (short version)

Hot cache = this file. Warm = docs near the code they describe (incl. `docs/SESSION-CONTEXT.md` for fast re-anchor). Cold = anything else, loaded just-in-time. Explicit pointers beat dumping content inline. Full model: @docs/07-context-strategy.md.
