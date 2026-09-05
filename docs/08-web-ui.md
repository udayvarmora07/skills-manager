# Web UI — Skills Manager

**Version 0.2.0**

**AI manifest**: The GUI of skills-manager is a **local web UI** (browser frontend + Python stdlib backend). It replaces the former GTK4 GUI. This doc is the single source of truth for the web UI: how it runs, what endpoints exist, and how the frontend is structured. Do not re-read source to answer questions this doc already answers.

## Why web and not GTK

- GTK4 + PyGObject made cross-version GUI work slow and fragile (progress log has the receipts: `set_data` unsupported, Popover API differences between GTK4/GTK3).
- The Store layer is UI-agnostic, so it became the backend unchanged.
- Web tech gives a far better polish-to-effort ratio for a local tool (same approach as Jan / LM Studio / AnythingLLM / Open WebUI).
- "Website" here means **localhost only** — nothing is hosted or exposed.

## Architecture

```
Browser (Vue 3, no build step)
   │  JSON REST + static files
   ▼
webapp.py (http.server ThreadingHTTPServer, 127.0.0.1)
   │  Store public API only (scopes layer for agent dirs)
   ▼
store.py ──> filesystem (source of truth) + SQLite index
```

- **Backend**: `skillsmgr/webapp.py`. Stdlib only. Serves the static frontend from `skillsmgr/webui/` and a REST API under `/api/`. Scope-aware endpoints delegate to the `scopes` layer (`skillsmgr/scopes.py`), which reads/writes agent skill dirs directly (no DB).
- **Frontend**: `skillsmgr/webui/` — `index.html`, `styles.css`, `app.js`, `static/vendor/vue.global.prod.js` (Vue 3.5.13, vendored so the app works offline).
- **No build step**: Vue global production build, plain CSS, plain JS. No npm, no bundler, no CDN at runtime.

## How to run

```bash
python3 -m skillsmgr webui            # serves on http://127.0.0.1:8765, opens browser
python3 -m skillsmgr gui              # alias (same thing)
python3 -m skillsmgr webui --no-browser
python3 -m skillsmgr webui --port 9000
```

`gui` remains as an alias of `webui` so old muscle memory and scripts keep working.

## Scopes (tracking other agents' skills)

**[SPEC]** The web UI tracks skills across agent scopes — the same scopes the CLI exposes (`--scope`). Scope ids: `global` (the manager's own store), `claude-code`, `codex`, `cursor`, `opencode`, `gemini`, `commandcode`, `agents`, plus project-local scopes. `agents` is the Command Code skills dir (`~/.agents/skills`), so the UI can list/create/edit/disable/remove/sync the exact skills the `commandcode` CLI loads.

- **Scope switcher** in the topbar (`activeScope` persisted to `localStorage` as `skillsmgr-scope`; default `all`).
- Agent scopes are read/written directly on disk (no DB index). Disable/enable renames `SKILL.md` <-> `SKILL.md.disabled` in place; remove trashes to `<scope-base>/../trash` (e.g. `~/.agents/trash`).
- Global scope is the manager's Store + SQLite index; export is global-only.

## REST API

All endpoints return JSON unless noted. Errors: `{"error": "message"}` with status 400 (StoreError), 404 (SkillNotFound / unknown), 500 (internal).

### Skills

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/skills[?scope=SCOPE]` | — | list of skills (scope-aware; default global) |
| GET | `/api/skills/<name>[?scope=SCOPE]` | — | full record incl. body + path |
| GET | `/api/skills/<name>/raw[?scope=SCOPE]` | — | raw SKILL.md text (text/plain) |
| POST | `/api/skills[?scope=SCOPE]` | `{name, description, category?, version?, license?, compatibility?, allowed_tools?, body?}` | created record (201) |
| PATCH | `/api/skills/<name>[?scope=SCOPE]` | partial fields (same keys as POST) | `{name, changed}` |
| POST | `/api/skills/<name>/disable[?scope=SCOPE]` | — | `{name, disable: true}` |
| POST | `/api/skills/<name>/enable[?scope=SCOPE]` | — | `{name, enable: true}` |
| DELETE | `/api/skills/<name>?purge=0|1[&scope=SCOPE]` | — | Store.remove / scopes.remove_skill result |

### Search / maintenance

| Method | Path | Notes |
|---|---|---|
| GET | `/api/search?q=term[&scope=SCOPE]` | search over name/description/body (scope-aware) |
| GET | `/api/stats` | Store.stats |
| GET | `/api/doctor[?scope=all]` | Store.doctor (global); `?scope=all` adds `scopes` + `duplicates` (`scopes.find_duplicates()`) |
| GET | `/api/history?name=&limit=` | Store.history (name optional) |
| POST | `/api/validate` | body `{name}` → `{valid, issues: [{level, key, message}]}` |
| POST | `/api/rebuild` | Store.db_rebuild |
| POST | `/api/resync` | Store.resync |
| GET | `/api/scopes` | `list_scopes()`: id/label/path/kind/writable/exists/count/tokens |
| POST | `/api/sync` | body `{name, from_scope, to_scopes[], force}` → `{synced[], skipped[]}` |
| POST | `/api/install` | body `{source, runner?, scope?, agents[], skills[], copy?, list_only?, run?}` → built `skills add` command, or runs it when `run:true` |

### Trash

| Method | Path | Notes |
|---|---|---|
| GET | `/api/trash` | Store.trash_list (global trash only) |
| POST | `/api/trash/<name>` | restore |
| POST | `/api/trash/purge` | purge everything |

### Templates

| Method | Path | Notes |
|---|---|---|
| GET | `/api/templates` | `{templates: [names]}` |
| POST | `/api/templates` | body `{name, body?}` → created path (201) |

### Import / export

| Method | Path | Notes |
|---|---|---|
| GET | `/api/export` | downloads gzip archive (attachment; global scope only) |
| PUT | `/api/import?filename=&force=` | raw archive bytes in body → Store.import_ |
| PUT | `/api/import` (multipart/form-data) | webkitdirectory folder upload → Store.add per SKILL.md |

## Frontend map (app.js)

- **State**: `view` (skills|trash), `filter` (all|active|disabled), `query` (live search, 220ms debounce), `skills`, `trashSkills`, `selected`/`selectedName`, `theme` (light|dark, localStorage), `modals.*` (one object per dialog), `toasts`, `scopes` (from `/api/scopes`), `activeScope` (persisted).
- **Flow helpers**: `api()` fetch wrapper; `loadSkills`/`loadTrash`/`loadDetail`/`applySearch`; `toast(text, type, undoFn)` with auto-dismiss (8s when undoable, else 4s). Scope helpers `_scopeParam`/`_scopeQs` append `?scope=` to skill/detail/search calls.
- **Actions**: `saveSkill` (create/update, scope-aware), `toggleSelected` (disable/enable), `removeSkill` (trash with **Undo toast**, or purge), `restoreTrash`, `purgeTrash`, `runValidate`, `openDoctor/Stats/History/Templates`, `saveTemplate`, `doImport`/`exportArchive` (browser download), `rebuildIndex`/`resyncIndex`, `openSyncModal`/`runSync` (copy skill between scopes), `openInstall`/`runInstall` (build or run `skills add`).
- **Markdown**: hand-rolled `renderMarkdown()` — block-level only, everything HTML-escaped (XSS-safe, no raw HTML), supports headings, paragraphs, lists, quotes, fenced code, inline code/bold/italic/links, tables.
- **Keyboard**: `/` focuses search; `Esc` closes menus/modals.
- **Responsive**: <900px stacks sidebar above detail; <640px compacts the topbar (no brand text, no stat pill, tighter padding).

## Design system (styles.css)

- Register: product. Palette: warm ivory/cream neutrals + copper accent (`#b4531f` light / `#d9894a` dark) — a "workbench" identity, deliberately not the generic tech blue-violet.
- Spacing rhythm: 4 / 16 / 36px. Radius 6/10px. System font stack (Ubuntu first) + mono for code/paths.
- Full state coverage: loading (skeleton shimmer), empty (teaching empty states), error (banners + toasts), disabled, focus-visible rings, hover/active transitions, `prefers-reduced-motion` respected.
- Dark theme: authored (not inverted) — warm charcoal surfaces, softened accent, light border trace.
- Toasts support an **Undo** action (used for trash → restore).

## Tests

- `python3 smoke_web.py` — starts the server on an ephemeral port and hits every endpoint above (static, CRUD, search, validate, toggle, stats/doctor/history, templates, export→import round-trip, trash/restore/purge, rebuild/resync, multipart folder upload, error paths). Must pass after any change to `webapp.py`.

## Locked rules

1. Backend uses the **Store public API only** — no direct sqlite3 access. Reading `SKILL.md`/`SKILL.md.disabled` files for the `raw` endpoint and token enrichment is allowed (filesystem is the source of truth); never hand-edit the DB. (Agent scopes go through the `scopes` layer, which is the same rule for those dirs.)
2. `127.0.0.1` bind by default. Never expose publicly.
3. No build step, no new runtime dependencies (stdlib backend; Vue is vendored).
4. Frontend never renders raw HTML from skill bodies (XSS).
5. CLI surface: `webui` (primary) + `gui` (alias) — both documented in @docs/03-cli-surface.md.
