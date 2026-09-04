# Session Context — Skills Manager

**Version 0.2.0**

**AI manifest**: Fast-load context for agents working on skills-manager. One compact doc replaces re-reading source for the most common questions. For anything this doc does not answer, follow `@docs/...` pointers. This doc is a cache, not a spec — `docs/` files and source remain authoritative.

## What exists today (2026-08-16)

- **CLI**: `python3 -m skillsmgr` — 26 top-level commands + 7 subcommands + 3 aliases (`ls`, `rm`, `gui`) = 40 invocable names, exit codes 0/1/2/130. Works.
- **Scopes**: `skillsmgr/scopes.py` — global store + per-agent filesystem roots. `--scope agents` = `~/.agents/skills` (Command Code's live skills dir), read/written directly on disk, no DB. Other agent scopes: claude-code, codex, cursor, opencode, gemini, commandcode. `--scope all` merges everything. `sync`/`scopes`/`tokens`/`install` commands are scope-aware. See @docs/03-cli-surface.md.
- **Store**: `skillsmgr/store.py` — FS source of truth + SQLite index. Public API in @docs/04-store-api.md. **Signatures that surprise people** (docs used to lie about these, fixed on 2026-08-14):
  - `export()` / `backup()` return a **Path**, not a dict.
  - `db_rebuild()` returns `{"added", "updated", "removed"}` (no `"skills"` key).
  - `doctor()` returns `ok`/`db_integrity` etc. (no `trash_mismatch`/`db_rebuilt` keys).
- **GUI**: **local web UI** (see @docs/08-web-ui.md). Replaced GTK4 (`gui.py` deleted 2026-08-14). `webui` is the command, `gui` is its alias.
  - Backend: `skillsmgr/webapp.py` (stdlib `ThreadingHTTPServer`, 127.0.0.1, port 8765 default).
  - Frontend: `skillsmgr/webui/` (Vue 3.5.13 vendored, no build step). Scope switcher in topbar persists `activeScope` to `localStorage` (`skillsmgr-scope`).
- **Tests**: `python3 smoke_store.py` (store API), `python3 smoke_web.py` (REST API). Both green.
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
python3 -m py_compile skillsmgr/*.py smoke_*.py
python3 smoke_store.py          # "ALL STORE SMOKE TESTS PASSED"
python3 smoke_web.py            # "ALL WEB SMOKE TESTS PASSED"
python3 -m skillsmgr --help     # webui (gui) listed, no tracebacks
python3 -m skillsmgr list --scope agents --json   # lists Command Code's skills
```

Browser click-through (when UI changed): `python3 -m skillsmgr webui --no-browser` + agent-browser: open → snapshot -i → exercise create/edit/disable/remove+undo/restore/trash-purge/validate/doctor/stats/history/templates/import/export/theme-toggle/400px viewport. Watch `window.__consoleErrors` (attach error listeners first).

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
    app.js             # Vue app: state, actions, markdown renderer, toasts
    static/vendor/vue.global.prod.js   # Vue 3.5.13 (vendored)
  cli.py               # cmd_gui → webapp.run; webui/gui parser
  store.py             # unchanged by this build (read only)
smoke_store.py         # store smoke (green)
smoke_web.py           # REST smoke (green)
docs/08-web-ui.md      # authoritative web UI doc
docs/06-progress-log.md# web UI entries (newest top)
```

## Open questions / next steps

- `[?]` None for the web UI itself. Possible future work (not requested): native window wrapper (pywebview), skill-body editor with live preview, keyboard shortcut cheat-sheet modal.
