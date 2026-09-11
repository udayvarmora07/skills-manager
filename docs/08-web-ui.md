# Web UI — Skills Manager

**Version 0.3.0**

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

- **Backend**: `skillsmgr/webapp.py`. Stdlib only. Serves the static frontend from `skillsmgr/webui/` and a REST API under `/api/`. Request security, JSON serialization/body parsing, and multipart folder-upload staging live in private `web_security.py`, `web_serialization.py`, and `web_upload.py` modules; `webapp.py` keeps the route and compatibility interfaces. Scope-aware endpoints delegate to the `scopes` layer (`skillsmgr/scopes.py`), which reads/writes agent skill dirs directly (no DB).
- **Frontend**: `skillsmgr/webui/` — `index.html`, `styles.css`, `domain.js`, `app.js`, `static/vendor/vue.global.prod.js` (Vue 3.5.13, vendored so the app works offline). `domain.js` owns transport/formatting/frontmatter/escaped Markdown rendering behind a small browser-global seam; `app.js` owns Vue state and workflows. The split is plain script loading and keeps the no-build contract.
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

**[SPEC]** The web UI tracks skills across agent scopes — the same scopes the CLI exposes (`--scope`). Scope ids: `global` (the manager's own store), `claude-code`, `codex`, `cursor`, `opencode`, `gemini`, `commandcode`, `agents`, plus project-local scopes. `cursor` maps to `~/.cursor/skills`; `agents` maps to `~/.agents/skills`. Aggregate scope views deduplicate aliases by resolved physical path, while direct scope ids remain compatible. See @docs/ADR-002-root-consumer-effective-state.md and @docs/12-agent-root-discovery-2026-09-08.md.

- **Scope switcher** in the topbar (`activeScope` persisted to `localStorage` as `skillsmgr-scope`; default `all`).
- Agent scopes are read/written directly on disk (no DB index). Disable/enable renames `SKILL.md` <-> `SKILL.md.disabled` in place; remove trashes to `<scope-base>/../trash` (e.g. `~/.agents/trash`).
- Global scope is the manager's Store + SQLite index; export is global-only.

## REST API

All endpoints return JSON unless noted. Errors: `{"error": "message"}` with status 400 (StoreError/invalid bounded input), 403 (host or cross-origin mutation rejection), 404 (SkillNotFound / unknown), 415 (non-JSON body on a JSON mutation endpoint), and 500 (internal).

State-changing requests are accepted only on a loopback-bound server with the
configured loopback `Host` and port. `Sec-Fetch-Site: cross-site`, hostile
`Origin`, and hostile `Referer` values are rejected before route handlers run.
JSON mutation endpoints require `Content-Type: application/json`; raw archive and
multipart import keep their explicitly documented content types. Local CLI/test
clients may omit browser-only headers, but if `Origin`, `Referer`, or
`Sec-Fetch-Site` is supplied it must pass the same-origin policy.

Responses, including archive downloads, include `Content-Security-Policy` with `frame-ancestors 'none'`,
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, and `Cross-Origin-Resource-Policy: same-origin`.

Skill path parameters are URL-decoded by segment and then validated by the
canonical skill-name/root-containment guards before any Store or scope path is
constructed. Encoded traversal attempts therefore receive HTTP 400 and do not
mutate an outside directory.

### Skills

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/skills[?scope=SCOPE]` | — | list of skills (scope-aware; default global), including root availability, consumer, discovery recursion, observed instance state, and unresolved effective-state metadata |
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
| GET | `/api/search?q=term[&scope=SCOPE]` | search over name/description/body (scope-aware); bounded wildcard failures return the standard JSON `StoreError` 400 |
| GET | `/api/stats` | Store.stats |
| GET | `/api/doctor[?scope=all]` | Store.doctor (global), including filesystem/index drift and transaction-artifact diagnostics; `?scope=all` adds `scopes` + `duplicates` (`scopes.find_duplicates()`) |
| GET | `/api/history?name=&limit=` | Store.history (name optional) |
| GET | `/api/history?name=NAME&scope=SCOPE&snapshots=1` | retained snapshot IDs for a skill |
| POST | `/api/validate` | body `{name}` → `{valid, issues: [{level, key, message}]}`; `{evals: true}` adds the advisory eval report for `evals/evals.json` (read-only); `{runs: [...], iteration?}` scores and records results inside the store's `evals/` workspace |
| POST | `/api/rebuild` | Store.db_rebuild |
| POST | `/api/resync` | Store.resync |
| GET | `/api/scopes` | `list_scopes()`: id/label/path/kind/writable/availability/recursive/supported/consumer/exists/count/tokens |
| POST | `/api/sync` | body `{name, from_scope, to_scopes[], force}` → `{synced[], skipped[]}` |
| POST | `/api/install` | body `{source, runner?, scope?, agents[], skills[], copy?, list_only?, run?}` → built `skills add` command, or runs it when `run:true`; `{preview: true, trust_confirmed?, registry_hash?, description?}` adds the offline registry bridge plan under `registry` and makes `command` the recommended `skills add` mapping (no request, no execution) |

### Trash

| Method | Path | Notes |
|---|---|---|
| GET | `/api/trash` | Store.trash_list (global trash only) |
| POST | `/api/trash/<name>` | restore; `?snapshot=ID&scope=SCOPE` rolls back to a snapshot |
| POST | `/api/trash/purge` | purge everything |

### Templates

| Method | Path | Notes |
|---|---|---|
| GET | `/api/templates` | `{templates: [names]}` |
| POST | `/api/templates` | body `{name, body?}` → created path (201) |

### Import / export

| Method | Path | Notes |
|---|---|---|
| GET | `/api/export[?full=1]` | downloads slim or full gzip archive (attachment; global scope only) |
| PUT | `/api/import?filename=&force=&full=` | raw tar or ZIP archive bytes → Store.import_; `full=1` restores trash/templates from a full archive |
| PUT | `/api/import` (multipart/form-data) | webkitdirectory folder upload → Store.add per SKILL.md |

## Frontend map (app.js)

- **State**: `view` (skills|trash), `filter` (all|active|disabled), `query` (live search, 220ms debounce), `skills`, `trashSkills`, `selected`/`selectedName`, `theme` (light|dark, localStorage), `modals.*` (one object per dialog, including help), `toasts`/`liveAnnouncement`, focus lifecycle state, `scopes` (from `/api/scopes`), `activeScope` (persisted).
- **Domain seam (`domain.js`)**: `api()` fetch wrapper, formatting/token helpers, raw frontmatter enrichment, and hand-rolled escaped Markdown rendering; all load before `app.js` without a bundler.
- **Flow helpers**: `loadSkills`/`loadTrash`/`loadDetail`/`applySearch`; `toast(text, type, undoFn)` with auto-dismiss (8s when undoable, else 4s). Scope helpers `_scopeParam`/`_scopeQs` append `?scope=` to skill/detail/search calls.
- **Actions**: `saveSkill` (create/update, scope-aware), `toggleSelected` (disable/enable), `removeSkill` (trash with **Undo toast**, or purge), `restoreTrash`, snapshot rollback from History, `purgeTrash`, `runValidate`, `openDoctor/Stats/History/Templates`, slim/full `doImport`/`exportArchive` (browser download), `rebuildIndex`/`resyncIndex`, `openSync`/`doSync` (copy skill between scopes with resolution preview), `openInstall`/`runInstall` (build or run `skills add`), and escaped editor preview.
- **Markdown**: block-level only, everything HTML-escaped (XSS-safe, no raw HTML), supports headings, paragraphs, lists, quotes, fenced code, inline code/bold/italic/links, tables.
- **Keyboard**: `/` focuses search; `?` opens shortcut help; `Esc` closes menus/modals; `Tab` is trapped within the active dialog and focus returns to its opener. Destructive dialogs focus the safer cancel action first. Dialog backgrounds expose `inert`/`aria-hidden` while open, with labelled dialogs and live status/error announcements.
- **Preview and safety**: skill editors show an escaped live Markdown preview; sync dialogs show source/target resolution, skip-versus-overwrite behavior, and rollback expectations before commit.
- **Responsive**: <900px stacks sidebar above detail; <640px compacts the topbar (no brand text, no stat pill, tighter padding). The dev-only `browser_harness.py` uses system Chrome DevTools Protocol to capture console/runtime/network failures and checks 320/400/640/900/desktop viewports.

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
   Non-loopback bind hosts are rejected by the server.
3. No build step, no new runtime dependencies (stdlib backend; Vue is vendored).
4. Frontend never renders raw HTML from skill bodies (XSS).
5. CLI surface: `webui` (primary) + `gui` (alias) — both documented in @docs/03-cli-surface.md.
