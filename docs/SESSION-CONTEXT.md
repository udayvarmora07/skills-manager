# Session Context — Skills Manager

**Version 0.2.0**

**AI manifest**: Fast-load context for agents working on skills-manager. One compact doc replaces re-reading source for the most common questions. For anything this doc does not answer, follow `@docs/...` pointers. This doc is a cache, not a spec — `docs/` files and source remain authoritative.

## What exists today (2026-09-08)

- **CLI**: `python3 -m skillsmgr` — 27 top-level commands + 7 subcommands + 3 aliases (`ls`, `rm`, `gui`) = 37 invocable names, exit codes 0/1/2/130. Works.
- **Scopes**: `skillsmgr/scopes.py` — global store + per-agent filesystem roots. `--scope agents` = `~/.agents/skills` (Command Code's live skills dir), read/written directly on disk, no DB. Other agent scopes: claude-code, codex, cursor, opencode, gemini, commandcode. `--scope all` merges everything. `sync`/`scopes`/`tokens`/`install` commands are scope-aware. See @docs/03-cli-surface.md.
- **Store**: `skillsmgr/store.py` — FS source of truth + SQLite index. Public API in @docs/04-store-api.md. **Signatures that surprise people** (docs used to lie about these, fixed on 2026-08-14):
  - `export()` / `backup()` return a **Path**, not a dict.
  - `db_rebuild()` returns `{"added", "updated", "removed"}` (no `"skills"` key).
  - `doctor()` returns `ok`/`db_integrity` etc. (no `trash_mismatch`/`db_rebuilt` keys).
- **GUI**: **local web UI** (see @docs/08-web-ui.md). Replaced GTK4 (`gui.py` deleted 2026-08-14). `webui` is the command, `gui` is its alias.
  - Backend: `skillsmgr/webapp.py` (stdlib `ThreadingHTTPServer`, 127.0.0.1, port 8765 default).
  - Frontend: `skillsmgr/webui/` (Vue 3.5.13 vendored, no build step). Scope switcher in topbar persists `activeScope` to `localStorage` (`skillsmgr-scope`).
 - **Tests**: stdlib `unittest` regression/contract suite (`python3 -m unittest discover -s tests`), plus `python3 smoke_store.py` (Store API), `python3 smoke_web.py` (REST API), and repository gates `python3 check_docs.py`, `python3 check_complexity.py`, and `python3 check_package_data.py` (package check may report `UNAVAILABLE` when optional build tooling is absent).
- **CLI bugs fixed 2026-08-14** (were crashing): `export`, `backup`, `db rebuild` (all treated Path/dict wrong), `doctor` (printed "integrity check failed" when ok).

## Common tasks (router)

| Want | Do |
|---|---|
| Run the UI | `python3 -m skillsmgr webui` |
| Run UI without browser | `--no-browser` |
| Track Command Code's skills (CLI) | `python3 -m skillsmgr list --scope agents` (also create/edit/remove/toggle) |
| Track Command Code's skills (UI) | web UI → scope switcher → **Agents** |
| Copy a skill between scopes | `python3 -m skillsmgr sync NAME --from global --to agents` (or UI Sync modal) |
| Change an API endpoint | `skillsmgr/webapp.py` route methods + `smoke_web.py` + re-run both smokes |
| Change a screen/behavior | `skillsmgr/webui/app.js` (Vue methods) / `index.html` (templates) / `styles.css` (design tokens in `:root`) |
| Add a field to create/edit form | app.js `_SKILL_FIELDS`-equivalent list in saveSkill payload + form in index.html + webapp.py `_SKILL_FIELDS` |
| Anything touching store.py | @docs/04-store-api.md + `python3 smoke_store.py` |
| CLI surface question | @docs/03-cli-surface.md |

## Design system (short form)

- Palette: warm ivory `#f7f3ec` + copper accent `#b4531f` (dark: charcoal `#191613` + `#d9894a`). CSS variables in `styles.css :root`, theme via `data-theme` on `<html>`.
- Spacing: 4/16/36px. Radius 6/10. Ubuntu system stack + mono for code.
- Product register: master-detail, dense list left, doc view right. Trash tab. Actions menu top-right.
- States required: empty/loading/error/disabled/focus/toast(ok/err/undo). `prefers-reduced-motion` respected.

## Gotchas learned (do not re-discover)

1. **agent-browser fill with `\n`** inserts literal backslash-n into textareas. Use `eval` + native setter for real newlines in tests. (Humans typing are unaffected.)
2. **agent-browser eval** wraps code in the same scope — redeclaring `const x` twice fails. Use fresh names each call.
3. **element refs go stale** after any DOM change; re-snapshot before every click sequence.
4. **Multipart parsing** in webapp.py is hand-rolled (`_parse_multipart`) — browsers send `\r\n\r\n` separators; keep the `sep` truthiness check (the `_`-shadow bug was caught in smoke).
5. **webapp.py static route** must join all `parts[1:]` for nested paths (e.g. `/static/vendor/vue.global.prod.js`).
6. **Trash routes**: `/api/trash/<name>` restore (POST, 3 parts), `/api/trash/purge` purge (POST, also 3 parts — check `parts[2] == "purge"` first).
7. **Mobile topbar** overflowed at 400px before the `max-width: 640px` rules; keep brand text/stat-pill hidden there.
8. Vue is **vendored** — bump it by replacing `skillsmgr/webui/static/vendor/vue.global.prod.js`, not by adding a CDN script.
9. **Agent-scope writes go straight to the agent dir** (no DB): disable/enable renames `SKILL.md` <-> `SKILL.md.disabled` in place; remove trashes to `<scope-base>/../trash` (e.g. `~/.agents/trash`), NOT the global store trash. Export is global-only.

## Verification loop (run all, all must pass)

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py check_*.py
PYTHONDONTWRITEBYTECODE=1 python3 check_complexity.py
PYTHONDONTWRITEBYTECODE=1 python3 check_docs.py
PYTHONDONTWRITEBYTECODE=1 python3 check_package_data.py  # UNAVAILABLE if optional build tooling is absent
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
PYTHONDONTWRITEBYTECODE=1 python3 smoke_store.py          # "ALL STORE SMOKE TESTS PASSED"
PYTHONDONTWRITEBYTECODE=1 python3 smoke_web.py            # "ALL WEB SMOKE TESTS PASSED"
PYTHONDONTWRITEBYTECODE=1 python3 -m skillsmgr --help   # webui (gui) listed, no tracebacks
```

Browser click-through (when UI changed): `PYTHONDONTWRITEBYTECODE=1 python3 browser_harness.py` starts a hermetic server and system Chrome CDP probe, captures console/runtime/network failures, and checks 320/400/640/900/1280px viewports. For interactive debugging use `python3 -m skillsmgr webui --no-browser` + Chrome DevTools: exercise create/edit/disable/remove+undo/restore/trash-purge/validate/doctor/stats/history/templates/import/export/theme-toggle. The harness is dev-only and adds no runtime dependency.

## File inventory (build-relevant)

```
skillsmgr/
  webapp.py            # backend: routing + multipart + server (read before changing endpoints)
  scopes.py            # agent-scope reads/writes (list/create/edit/remove/toggle/sync/search)
  loader.py            # shared SKILL.md loader + dir scanner (Store + scopes)
  tokens.py            # token/context estimation (tiktoken or chars/4)
  webui/
    index.html         # Vue templates for every screen/modal
    styles.css         # design tokens + components + responsive
    domain.js          # no-build transport/formatting/frontmatter/Markdown seam
    app.js             # Vue app: state, actions, dialogs, keyboard/focus
    static/vendor/vue.global.prod.js   # Vue 3.5.13 (vendored)
  cli.py               # stable adapter: main/build_parser + compatibility names
  cli_parser.py        # argparse construction
  cli_handlers.py      # command behavior
  store.py             # FS/index/recovery/archive policy
  insights.py          # read-only Milestone 9 helpers (pure, no CLI/Store/schema)
tests/test_insights_contracts.py  # insights hermetic contracts (52 tests)
smoke_store.py         # store smoke (green)
smoke_web.py           # REST smoke (green)
docs/08-web-ui.md      # authoritative web UI doc
docs/06-progress-log.md# web UI entries (newest top)
```

## Open questions / next steps

- `[?]` None for the web UI itself. Native window wrapper remains deferred; high-zoom/contrast/touch manual browser coverage remains follow-up. Effective consumer shadowing remains approval-gated.
