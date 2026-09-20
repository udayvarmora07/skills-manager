# Web UI — Skills Manager

**Version 0.7.0**

**AI manifest**: The GUI of skills-manager is a **local web UI** (browser frontend + Python stdlib backend). It replaces the former GTK4 GUI. This doc is the single source of truth for the web UI: how it runs, what endpoints exist, and how the frontend is structured. Do not re-read source to answer questions this doc already answers.

## Why web and not GTK

- GTK4 + PyGObject made cross-version GUI work slow and fragile (progress log has the receipts: `set_data` unsupported, Popover API differences between GTK4/GTK3).
- The Store layer is UI-agnostic, so it became the backend unchanged.
- Web tech gives a far better polish-to-effort ratio for a local tool (same approach as Jan / LM Studio / AnythingLLM / Open WebUI).
- "Website" here means **localhost only** — nothing is hosted or exposed.

## Architecture

```text
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

The Install modal also exposes the skills.sh registry through the existing
`POST /api/install` route. Browse/search/curated and the first fetch request are
read-only and cache-aware; fetch returns a bounded review id. A separate POST
with that `review_id` and `trust_confirmed: true` revalidates and commits the
single-use, expiring snapshot into the global Store without another network
request. The backend delegates to `registry.py`, which validates the HTTPS
endpoint, optional bearer token, response/snapshot bounds, cache state, private
review artifact, and provenance sidecar before calling the existing Store
`add()` path. Trust confirmation does not imply malware scanning or a signature.

## How to run

```bash
python3 -m skillsmgr webui            # serves on http://127.0.0.1:8765, opens browser
python3 -m skillsmgr gui              # alias (same thing)
python3 -m skillsmgr webui --no-browser
python3 -m skillsmgr webui --port 9000
```

`gui` remains as an alias of `webui` so old muscle memory and scripts keep working.

**Optional desktop window (issue #9):** the recorded verdict rejects bundling a
third-party webview (`pywebview`) — it would add an install plus OS webview
runtimes and native failure modes to a deliberately dependency-free UI. The most
that may exist is an *unbundled, loopback-only launcher*, and that is
`desktop_launcher.py` (repo root, **not** in the wheel, no new dependency): it
starts the same stdlib server and opens the page in a Chromium-family
`--app=` window, falling back to the default browser when none is installed.

```bash
python3 desktop_launcher.py                 # chromeless app window on 127.0.0.1:8765
python3 desktop_launcher.py --plain         # force the default browser
python3 desktop_launcher.py --print-only    # show what would happen, exit
```

It refuses any non-loopback `--host`, and `skills-mgr webui` stays the supported
entry point; the launcher never replaces it. Both it and the harness resolve
Chromium through `launcher_security.trusted_executable()`, so an unsafe PATH
match is skipped rather than executed. The harness leaves Chrome's renderer
sandbox enabled and passes `--remote-debugging-address=127.0.0.1` with an OS-
selected ephemeral port; its CDP endpoint is intentionally a local developer
seam, not a network service.

## Scopes (tracking other agents' skills)

The aggregate list adds `physical_root` and `physical_path` as derived
observations. The default Library view groups same-name rows, collapses aliases
to one resolved document, retains distinct physical instances, and marks
unequal content as divergent; the explicit Instances view and selected-scope
actions preserve physical targeting.

**[SPEC]** The web UI tracks skills across agent scopes — the same scopes the CLI exposes (`--scope`). Scope ids: `global` (the manager's own store), `claude-code`, `codex`, `cursor`, `opencode`, `gemini`, `commandcode`, `agents`, plus project-local scopes. `cursor` maps to `~/.cursor/skills`; `agents` maps to `~/.agents/skills`. Aggregate scope views deduplicate aliases by resolved physical path (first stable descriptor wins), while direct scope ids remain compatible. Rows whose on-disk directory name fails the canonical `NAME_RE` rule are still listed — the filesystem is the source of truth — but carry `addressable: false` and an `unaddressable` instance state, so the UI does not offer a row that would error the moment it is clicked (SCOPE-14). See @docs/ADR-002-root-consumer-effective-state.md and @docs/12-agent-root-discovery-2026-09-08.md.

- **Scope switcher** in the topbar (`activeScope` persisted to `localStorage` as `skillsmgr-scope`; default `all`).
- Agent scopes are read/written directly on disk (no DB index). Disable/enable renames `SKILL.md` <-> `SKILL.md.disabled` in place; remove trashes to `<scope-base>/../trash` (e.g. `~/.agents/trash`).
- Global scope is the manager's Store + SQLite index; export is global-only.

## REST API

All endpoints return JSON unless noted. Errors: `{"error": "message"}` with status 400 (StoreError/invalid bounded input), 403 (host or cross-origin rejection), 404 (SkillNotFound / unknown — an unrecognised `/api/…` path is answered as JSON `404 {"error": "unknown endpoint"}` and never falls through to the static handler), 405 (an unrouted verb, see below), 415 (non-JSON body on a JSON mutation endpoint), and 500 (internal). Reads share the mutation status codes: `GET` with a bad `Host` is a `403`, not a silent success.

**[SPEC]** Requests are accepted only on a loopback-bound server with the
configured loopback `Host` and port. This policy applies to **every** request,
`GET` included — not only to state-changing methods (SEC-1). Before this was
fixed, an attacker-controlled `Host` plus cross-site Fetch Metadata still
returned `GET /api/skills` and the full `GET /api/export` archive, and the
response was readable because a browser enforces CORS only on non-simple reads.
`web_security.validate_request()` is therefore run by `do_GET`, `do_HEAD`,
`do_POST`, `do_PATCH`, `do_PUT`, and `do_DELETE`.

- `Sec-Fetch-Site: cross-site` is rejected (`403`), as are a mismatched `Origin`
  and a mismatched `Referer` (only the scheme+authority of a `Referer` is
  compared).
- Local CLI/test clients may omit browser-only headers; a header-absent request
  is valid by design. If `Origin`, `Referer`, or `Sec-Fetch-Site` is supplied it
  must pass the same-origin policy.
- The historical name `validate_mutation_request` survives as an alias of
  `validate_request`; it is now a misnomer.
- JSON mutation endpoints require `Content-Type: application/json`; raw archive
  and multipart import keep their explicitly documented content types.

**Other verbs.** `HEAD` mirrors the equivalent `GET`: identical status, headers
and `Content-Length`, with the body suppressed (a `HEAD /api/skills` is how a
client checks reachability without transferring data). `OPTIONS` and `TRACE` are
**not** routed: they return `405` with a JSON body `{"error": "method not
allowed"}`, an `Allow: GET, HEAD, POST, PATCH, PUT, DELETE` header, and the full
security-header set. They previously fell through to the stdlib default handler,
which answered with an HTML `501` carrying **no** security headers at all
(`BUG-9`).

Responses, including archive downloads, include `Content-Security-Policy` with `frame-ancestors 'none'`,
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, and `Cross-Origin-Resource-Policy: same-origin`.

**CSP details and one recorded trade-off (SEC-4, SEC-5).** The full policy is
`default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self'
'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none';
frame-ancestors 'none'; form-action 'none'`.

- `form-action 'none'` is stated explicitly because `form-action` does **not**
  fall back to `default-src`; without it a future injected `<form
  action="https://…">` could submit. There is no `<form>` in the UI, so this is
  free defence-in-depth (`SEC-5`).
- `script-src 'unsafe-eval'` is a **known, deliberate trade-off**, not an
  oversight (`SEC-4`). The vendored file is the *runtime + compiler* build, and
  `app.js` passes no `template:`/`render:` option, so Vue compiles the in-DOM
  markup of `index.html` with `Function(code)()` at start-up. Removing the
  directive is therefore impossible without a build step, which locked rule 3
  below forbids. Its cost is real but bounded: `'unsafe-inline'` is absent from
  `script-src`, so an injected `<script>` or `onerror=` is still blocked, and no
  HTML-injection sink exists today. What it does remove is CSP as the safety net
  for the *next* injection bug — most plausibly the hand-rolled Markdown
  renderer, which processes attacker-authored `SKILL.md` bodies, so keep that
  renderer escaping everything (locked rule 4). The decision is pinned by
  `tests/test_audit_batch5_contracts.py`, which fails if the directive is dropped
  without also documenting the replacement.

Skill path parameters are URL-decoded by segment and then validated by the
canonical skill-name/root-containment guards before any Store or scope path is
constructed. Encoded traversal attempts therefore receive HTTP 400 and do not
mutate an outside directory.

### Skills

The list response includes derived `physical_root` and `physical_path` values
when the filesystem can resolve them; these are presentation observations, not
new persistence or authority.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/skills[?scope=SCOPE]` | — | list of skills (scope-aware; default global), including root availability, consumer, discovery recursion, `addressable`, observed instance state, and unresolved effective-state metadata |
| GET | `/api/skills/<name>[?scope=SCOPE]` | — | full record incl. body + path |
| GET | `/api/skills/<name>/raw[?scope=SCOPE]` | — | raw SKILL.md text (text/plain) |
| POST | `/api/skills[?scope=SCOPE]` | `{name, description, category?, version?, license?, compatibility?, allowed_tools?, body?}` | created record (201) |
| PATCH | `/api/skills/<name>[?scope=SCOPE]` | partial fields (same keys as POST) | `{name, changed}` |
| POST | `/api/skills/<name>/disable[?scope=SCOPE]` | — | `{name, disable: true}` |
| POST | `/api/skills/<name>/enable[?scope=SCOPE]` | — | `{name, enable: true}` |
| DELETE | `/api/skills/<name>?purge=0\|1[&scope=SCOPE]` | — | Store.remove / scopes.remove_skill result |

### Search / maintenance

| Method | Path | Notes |
|---|---|---|
| GET | `/api/search?q=term[&scope=SCOPE]` | search over name/description/body (scope-aware); bounded wildcard failures return the standard JSON `StoreError` 400 |
| GET | `/api/stats` | Store.stats plus scope/token enrichment: `scopes`, `all_total`, `all_tokens`, `all_avg_tokens`, `window`, `window_tokens`, `all_pct_window`, `largest`, `has_tiktoken`. When an enrichment step fails, the documented keys are still filled with safe fallbacks and the step is named in a `degraded` array (e.g. `"largest"`, `"scopes"`) |
| GET | `/api/doctor[?scope=all]` | Store.doctor (global), including filesystem/index drift and transaction-artifact diagnostics; `?scope=all` adds `scopes` + `duplicates` (`scopes.find_duplicates()`), and on an enrichment failure both are returned as `[]` with an entry appended to `degraded` (`[{"section", "reason"}]`), so a client can tell "no duplicates" from "the scan crashed" |
| GET | `/api/doctor?explain=CONSUMER[&project=DIR][&skill=NAME]` | adds the read-only effective-resolution report (issue #12, `effective.explain`) under `explain`; derived at read time, writes nothing, and reports `unknown-consumer`/`missing-project` as explicit results. **The report is confined to the manager's data directory** plus any extra root the operator passed at server construction; a request cannot widen that boundary (SEC-2/SEC-3): every path outside it is replaced by `<redacted>` with `paths_redacted: true`, and a `project` outside it returns resolution `project-outside-managed-roots` **without being walked** (no nested-root search, no instance read). The CLI passes no boundary and stays fully transparent |
| GET | `/api/tokens?window=&name=&scope=&text=` | token/context estimate: with `text=` it estimates that text, with `name=` it estimates one skill's document (scope-qualified when `scope=` is a scope id, otherwise the first match across scopes), and with neither it aggregates over `scope` (default `all`). Aggregate responses add `window`, `window_tokens` and `pct_window`; `window` selects the context window (claude, claude-haiku, gpt-5.6, gpt-5, gpt-4o, gemini, gemini-2m) |
| GET | `/api/history?name=&limit=` | Store.history (name optional) |
| GET | `/api/history?name=NAME&scope=SCOPE&snapshots=1` | retained snapshot IDs for a skill |
| POST | `/api/validate` | body `{name}` → `{valid, issues: [{level, key, message}]}`; `{evals: true}` adds the advisory eval report for `evals/evals.json` (read-only); `{runs: [...], iteration?}` scores and records results inside the store's `evals/` workspace |
| POST | `/api/rebuild` | Store.db_rebuild |
| POST | `/api/resync` | Store.resync |
| GET | `/api/scopes` | `list_scopes()`: id/label/path/kind/writable/availability/recursive/supported/consumer/exists/count/tokens |
| POST | `/api/sync` | body `{name, from_scope, to_scopes[], force}` → `{synced[], skipped[]}` |
| GET | `/api/catalog` | manager-owned tags and saved profiles from the filesystem sidecar |
| POST | `/api/catalog/tags` | body `{names[], operation: add\|remove\|replace, tags[]}` → normalized catalog |
| POST | `/api/catalog/profiles` | body `{name, description?, skills[], targets[]}` → normalized catalog |
| GET | `/api/catalog/profiles/<name>/preview` | read-only profile membership states: observed, disabled, divergent, or missing |
| DELETE | `/api/catalog/profiles/<name>` | removes only the saved profile metadata |
| POST | `/api/batch/preview` | body `{operation, targets[], options?}` → exact target count, plan hash, and recovery/partial-failure policy |
| POST | `/api/batch/execute` | body `{operation, targets[], options?, plan_id}` → per-target results; stale or widened plans are rejected |
| GET | `/api/workspaces?project=DIR` | read-only adapter catalog plus contained project-root observation; outside paths are redacted |
| POST | `/api/install` | Legacy body `{source, runner?, scope?, agents[], skills[], copy?, list_only?, run?}` builds/runs `skills add`; `{preview: true, trust_confirmed?, registry_hash?, description?}` returns the offline bridge plan with no request/execution. Registry body uses one of `{browse: true, page?, per_page?, view?, allow_stale?}`, `{search: QUERY, limit?, owner?, allow_stale?}`, `{curated: true, allow_stale?}`, `{fetch: true, source: ID, registry_hash?, allow_stale?}` for a read-only review, or `{fetch: true, review_id: ID, trust_confirmed: true}` for a no-network commit. Browse/search/curated return bounded catalog data. Fetch is global-store-only, writes a private expiring review artifact after full validation/risk evidence, and only the separate reviewed commit writes credential-free `.skillsmgr-provenance.json` and calls `Store.add`. Cache state is returned under `_registry`; stale fallback is opt-in. |

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

A multipart upload stages every part into a private temporary tree before any
skill is added, and it reports a name conflict as a plain `400` instead of
failing mid-request (SEC-6): one upload that contains both `a` (a file) and
`a/b/SKILL.md` (needing directory `a`) answers `{"error": "a file and a
directory share the name 'a'"}` in either part order, and a filename containing
a NUL byte answers an explicit message rather than the interpreter's own
`embedded null byte` text. Parts with an absolute path or a `..` segment are
still skipped silently, as before.

### Local client integration contract (non-browser clients — issue #8)

The REST API is the product surface for local integrations (an editor/VS Code
extension, a script, another tool). Everything such a client needs already
exists — reads, CRUD, toggle, trash/snapshots, search, scopes, sync, install,
validate, doctor, stats, tokens, templates, export/import — so an extension is a
separate repository with **no backend change here** (`tests/test_web_client_contracts.py`
pins the contract). What a client must know:

- **Address it at `127.0.0.1`.** The server binds loopback only and rejects a
  non-loopback bind host. With the default bind, its `Host` allowlist holds only
  `127.0.0.1:<port>`; a client configured with the equally-loopback name
  `localhost` gets **403 on every request, `GET` included**. Using the same host
  for bind and link keeps the header valid — which is why `desktop_launcher.py`
  does exactly that. Tracked as issue #14 F-2.
- **Call from the extension host (Node), not a webview origin.** No CORS headers
  are served on purpose: the server has no authentication, so a cross-origin
  browser request must stay rejectable. Requests carrying `Origin`/`Referer`
  outside the loopback origin set, or `Sec-Fetch-Site: cross-site`, get 403 on
  **every** method; header-absent local clients are allowed by design, which is
  exactly the extension-host path.
- **Errors are JSON and machine-readable** (`{"error": "..."}` with 400/403/404/409/415),
  and mutations require `Content-Type: application/json`.
- **There is no health endpoint** (adding one would be a new surface). A client
  confirms it reached this tool by reading `/api/stats` (counts, sizes,
  categories) at the loopback URL it started or discovered.
- **Reads are validated too.** `GET` and `HEAD` run the same
  Host/Fetch-Metadata/Origin/Referer policy as the mutations, so a DNS-rebound
  page whose origin *is* the rebound host can no longer read `/api/skills` or
  download `/api/export` (SEC-1; this closed the F-1 half of issue #14, and
  `tests/test_web_client_contracts.py` now pins the closed behaviour).
- **`OPTIONS` and `TRACE` are refused** with a JSON `405` plus `Allow` and the
  security headers — do not use them as a reachability probe; use `HEAD` (which
  mirrors `GET`, headers only) or `/api/stats`.

## Frontend map (app.js)

The state also derives `logicalSkills`/`visibleSkills` through
`groupLogicalSkills()` and persists `libraryMode` (`library` or `instances`) in
local storage; the default is the logical Library. Initial scopes, skills, and
trash reads run once in parallel; stats and token-budget data follows as a
secondary request, so the list can paint without waiting for aggregate work.
When the all-scopes library is empty, the detail pane shows a local-only
getting-started checklist based on the detected scope roots and completed scan.
Its create, archive-import, folder-add, and health-check actions call existing
workflows; Skip hides it only in memory, and the empty state can restart it.

- **State**: `view` (skills|trash|profiles|workspaces), `filter` (all|active|disabled), `tagFilter` (tag or `__untagged`), `query` (live search, 220ms debounce), `skills`, `trashSkills`, `catalog`, exact `selectedKeys`, `selected`/`selectedName`, `workspaces`, `profileForm`/`profilePreview`, `theme` (light|dark, localStorage), `modals.*` (one object per dialog, including batch/help), `toasts`/`liveAnnouncement`, focus lifecycle state, `scopes` (from `/api/scopes`), `activeScope` (persisted).
- **Domain seam (`domain.js`)**: `api()` fetch wrapper, formatting/token helpers, raw frontmatter enrichment, and hand-rolled escaped Markdown rendering; all load before `app.js` without a bundler.
- **Flow helpers**: `loadSkills`/`loadTrash`/`loadDetail`/`applySearch`; `toast(text, type, undoFn)` with auto-dismiss (8s when undoable, else 4s). The scope query string is built inline per call (`"?scope=" + encodeURIComponent(scope)`); the former `_scopeParam`/`_scopeQs` helpers were dead code and were removed (`BUG-15`).
- **Actions**: `saveSkill` (create/update, scope-aware), `toggleSelected` (disable/enable), `removeSkill` (trash with **Undo toast**, or purge), `restoreTrash`, snapshot rollback from History, `purgeTrash`, `runValidate`, `openDoctor/Stats/History/Templates`, slim/full `doImport`/`exportArchive` (browser download), `rebuildIndex`/`resyncIndex`, `openSync`/`doSync` (copy skill between scopes with resolution preview), exact visible-set selection and tag changes, `prepareBatch`/`executeBatch` (preview-locked enable/disable/remove/sync), `saveProfile`/`previewProfile`/`deleteProfile`, `loadWorkspaces` (read-only adapter/project evidence), `openInstall`/`runInstall` (build/run `skills add` or browse/search/curate/fetch skills.sh), `runRegistry` (cache-aware reads and explicit provenance fetch), and escaped editor preview.
- **Markdown**: block-level only, everything HTML-escaped (XSS-safe, no raw HTML), supports headings, paragraphs, lists, quotes, fenced code, inline code/bold/italic/links, tables.
- **Keyboard**: `/` focuses search; `?` opens shortcut help; `Esc` closes menus/modals; `Tab` is trapped within the active dialog and focus returns to its opener. Destructive dialogs focus the safer cancel action first. Dialog backgrounds expose `inert`/`aria-hidden` while open, with labelled dialogs and live status/error announcements.
- **Preview and safety**: skill editors show an escaped live Markdown preview; sync dialogs show source/target resolution, skip-versus-overwrite behavior, and rollback expectations before commit.
- **Responsive**: <900px stacks sidebar above detail; <640px presents Library
  and detail as separate states, with an explicit Back action that returns focus
  to the selected row. Secondary controls are behind a keyboard-accessible
  disclosure; the topbar also drops brand text and the stat pill. The dev-only
  `browser_harness.py` uses system Chrome DevTools Protocol with the browser
  sandbox enabled, an explicit loopback address, and trusted executable
  discovery to capture console/runtime/network failures across
  320/400/640/900/desktop viewports.

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
