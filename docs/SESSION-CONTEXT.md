# Session Context — Skills Manager

**AI manifest**: Fast-load context for agents working on skills-manager. One compact doc replaces re-reading source for the most common questions. For anything this doc does not answer, follow `@docs/...` pointers. This doc is a cache, not a spec — `docs/` files and source remain authoritative.

**Version 1.4.0** (2026-09-16: worktree comparison and frontend report
close-out; 728 tests, 222 complexity-tracked functions.)

**Version 1.3.0** (2026-09-16: FM-9 dumper-key fidelity close-out; 722 tests,
221 complexity-tracked functions.)

**Version 1.2.0** (2026-09-16: final audit-tail remediation; 721 tests, 219
complexity-tracked functions.)

**Version 1.1.0** (2026-09-15: SEC-19/FM-19 remediation; 712 tests, 218
complexity-tracked functions.)

**Version 1.0.0** (2026-09-15: SEC-14…SEC-18 remediation; 699 tests, 218
complexity-tracked functions.)

**Version 0.9.0** (2026-09-15: follow-up close-out for CLI-9…CLI-11, EVAL-2,
and FM-11; 685 tests, 217 functions.)

**Version 0.8.0** (2026-09-12: audit-remediation batch 5 — `form-action 'none'`,
clean upload name-conflict errors, no PyPI execution inside a `contents: write`
job, a pinned + hash-verified build toolchain, a sha256 assertion on the vendored
Vue bundle, and an sdist that no longer ships `tests/`. Gate counts here come from
a run in this session: **627 tests**, **216 functions**.
*History:* 0.7.0 was the 2026-09-11 documentation truth pass (this cache no longer
claims reads are unvalidated — `SEC-1` closed that, the request policy guards
`GET` and `HEAD` too) and the extended docs gate. Earlier: all open issues
resolved (#6/#7/#8/#9/#11, with the probes' two new findings filed as issue #14);
the read-only `doctor --explain` diagnostic plus the non-UTF8 `SKILL.md` fix; and
the 2026-09-10 offline registry bridge (`install --preview`) with the file-based
advisory eval harness, both shipped by extending existing surfaces only — see
@docs/ADR-003-registry-bridge-and-eval-harness.md.)
## What exists today (2026-09-16)

- **CLI**: `python3 -m skillsmgr` — 27 top-level commands + 7 subcommands (trash/templates/db) + 3 aliases (`ls`, `rm`, `gui`) = 37 invocable names (`prog="skills-mgr"`); exit codes 0/1/2/130. Parser/handlers/output split behind the stable `skillsmgr.cli` adapter (`cli_parser.py`, `cli_handlers.py`, `cli_output.py`). Works. See @docs/03-cli-surface.md.
- **Scopes**: `skillsmgr/scopes.py` — global store + per-agent filesystem roots. `--scope agents` = `~/.agents/skills` (Command Code's live skills dir), read/written directly on disk, no DB. Other agent scopes: claude-code, codex, cursor, opencode, gemini, commandcode. `--scope all` merges everything. `sync`/`scopes`/`tokens`/`install` commands are scope-aware. Discovery research: @docs/12-agent-root-discovery-2026-09-08.md v1.2.0 (all three `[?]`s closed 2026-09-09; facade ids are compat-only). The read-only `doctor --explain` diagnostic shipped 2026-09-11 (`skillsmgr/effective.py`; per-consumer rules cited from that doc, `unknown-consumer`/`undocumented-precedence` instead of a guess, nothing persisted). See @docs/03-cli-surface.md.
- **Effective-resolution diagnostic (2026-09-11, #12)**: `python3 -m skillsmgr doctor --explain commandcode --project DIR [--skill NAME] [--json]` (also `GET /api/doctor?explain=…&project=…&skill=…`). Policies: `commandcode` six-way order, `codex` no-merge (no winner elected), `claude-code` personal > project with nested copies in `also_loads`, `gemini` built-in < extension < user < workspace (`ambiguous` on same-tier ties), `cursor`/`opencode` `undocumented-precedence`. `unknown-consumer`/`missing-project` → exit 1, everything else → exit 0. `skillsmgr/effective.py`. Over HTTP the report is **confined to the manager's data directory** (plus only those extra roots the operator configured at server construction): paths outside it are replaced by `<redacted>` (with `paths_redacted: true`), and an out-of-boundary `project` returns `project-outside-managed-roots` **without walking it** (SEC-2/SEC-3); the CLI passes no boundary and stays fully transparent.
- **Store**: `skillsmgr/store.py` — FS source of truth + SQLite index. Public API in @docs/04-store-api.md. **Signatures that surprise people** (docs used to lie about these, fixed on 2026-08-14):
  - `export()` / `backup()` return a **Path**, not a dict.
  - `db_rebuild()` returns `{"added", "updated", "removed"}` (no `"skills"` key).
  - `doctor()` returns `ok`/`db_integrity` etc. (no `trash_mismatch`/`db_rebuilt` keys).
- **GUI**: **local web UI** (see @docs/08-web-ui.md). Replaced GTK4 (`gui.py` deleted 2026-08-14; @docs/05-gui-plan.md kept as a labelled historical record). `webui` is the command, `gui` is its alias.
  - Backend: `skillsmgr/webapp.py` (stdlib `ThreadingHTTPServer`, 127.0.0.1, port 8765 default) + private policy modules `web_security.py` / `web_serialization.py` / `web_upload.py`.
  - Frontend: `skillsmgr/webui/` (`domain.js` loads before `app.js`; Vue 3.5.13 vendored, no build step). Scope switcher in topbar persists `activeScope` to `localStorage` (`skillsmgr-scope`).
- **Tests**: stdlib `unittest` regression/contract suite — 728 tests green 2026-09-16 (`python3 -m unittest discover -s tests`), plus `python3 smoke_store.py` (Store API), `python3 smoke_web.py` (REST API, shared `smoke_fixtures.py` lifecycle helpers), and repository gates `python3 check_docs.py`, `python3 check_complexity.py` (222 functions, budget ≤ 15), and `python3 check_package_data.py` (always asserts the vendored Vue sha256, then reports `UNAVAILABLE` when optional build tooling is absent — standing behavior, not a regression). Dev-only `browser_harness.py` (system-Chrome CDP with sandbox enabled, explicit loopback binding, trusted PATH discovery, 320/400/640/900/1280px) is green.
- **Client contract (2026-09-11, #8)**: the REST API is the surface for local non-browser
  clients (editor extensions, scripts). Address it at `127.0.0.1` — `Host: localhost:<port>`
  is rejected on **every** request under the default bind, reads included (issue #14 F-2) —
  and call from the host process, not a webview origin: no CORS headers are served on purpose. Pinned by
  `tests/test_web_client_contracts.py`; documented in @docs/08-web-ui.md.
- **Optional desktop window (2026-09-11, #9)**: `python3 desktop_launcher.py` (repo root,
  **not** packaged, no new dependency) serves the stdlib UI on loopback and opens it in a
  Chromium `--app=` window, falling back to the default browser. `skills-mgr webui`/`gui`
  remains canonical; `pywebview` stays rejected (```tests/test_desktop_launcher_contracts.py```).
  Chromium discovery uses `skillsmgr.launcher_security.trusted_executable()` and skips
  unsafe PATH matches rather than executing them.
- **Data-root trust (SEC-19)**: `SKILLS_MANAGER_DATA` and `XDG_DATA_HOME` are
  canonicalized and fail closed when the selected base or manager root is a
  filesystem root, regular file, non-writable, owned by another user, or
  writable by group/other users outside a sticky parent. Missing manager-owned
  components are created with owner-only permissions; explicit `Store(data_dir=…)`
  injection remains an internal/test seam.
- **Team sharing (design only, 2026-09-11, #11)**: @docs/ADR-004-team-sharing-signed-bundles.md
  defines the trust model (HMAC shared secret is the only stdlib option), the canonical-MAC
  format sketch, and the draft → review → publish stages. No signing code exists; blocked on
  ADR-004 §6.
- **Insights (read-only, Milestone 9)**: `skillsmgr/insights.py` — pure stdlib helpers over existing seams (`consumer_view` with precedence `unresolved` per ADR-002, diff/three-way, ownership, provenance, update preview, stage-only quarantine, `risk_scan`, offline `registry_preview`, `registry_reference`/`registry_bridge_plan` + the shared `install_argv`/`install_command_line` renderer, advisory `eval_plan`/`eval_score`, deferred `bundle_policy`). Script-risk findings are machine-marked advisory/heuristic and are not enforcement evidence. Locked by hermetic tests in `tests/test_insights_contracts.py` and `tests/test_registry_bridge_contracts.py`.
- **Registry bridge (offline half, 2026-09-10)**: `install --preview [--trust-confirmed] [--registry-hash HEX]` / `POST /api/install {preview: true}` parse a registry reference (`owner/repo`, `owner/repo/slug`, skills.sh page URL, GitHub URL), record caller trust intent, surface linkable `/security/{provider}` audit pages plus the hash slot, and map a skill id onto `npx skills add … -s <slug>`. Because there is no authenticated request or content comparison, offline plans keep trust, hash, eligibility, and `may_install` unverified/false; network browse/fetch is still deferred (#3, @docs/ADR-003-registry-bridge-and-eval-harness.md).
- **Eval harness (file-based, advisory, 2026-09-10)**: `skillsmgr/evals.py` reads `evals/evals.json` from a skill dir and records `iteration-N/eval-<slug>/{with_skill,without_skill}/{outputs/output.txt,grading.json,timing.json}` plus a per-iteration `benchmark.json` (per-variant case pass rate and the `with_skill` − `without_skill` delta). Surfaces: `validate --evals`, `validate --evals-run FILE [--workspace DIR]`, `POST /api/validate {evals|runs}`. Workspaces default to `<data>/evals/<name>-workspace` (outside `skills/`; `--path` uses beside-the-skill only outside the store's `skills/` tree). Scores never change `valid`, never gate installs/edits, never enter SQLite (#4).
- **Milestone 11 queue (2026-09-10)**: L1/L2/L3/L4 done; L2 ZIP import is shipped as an `import`-only extension with bounded preflight and guarded extraction, and L5's offline/file-based halves are now shipped (#3/#4 partially closed; their network/backend halves stay deferred). L6 release remains gated on a fresh exact artifact build and authorized publication.
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
| Open the UI as a desktop window | `python3 desktop_launcher.py` (`--plain` for the browser, `--print-only` to preview) |
| Integrate a local client (editor/extension) | @docs/08-web-ui.md → "Local client integration contract" + `tests/test_web_client_contracts.py` |
| Explain which skill copy an agent actually loads | `python3 -m skillsmgr doctor --explain <consumer> --project DIR [--skill NAME]` (`skillsmgr/effective.py`) |
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
10. **A non-UTF8 `SKILL.md` must never raise a raw `UnicodeDecodeError`** (#13). Read/report paths go through `loader.read_skill_text()` (U+FFFD text + a message) and mark the row `malformed` with `decode_error`; `doctor` reports it under `undecodable_documents` and `ok` is False. Any path that rewrites a document must call `loader.read_skill_text_strict()` so lossy replacement characters can never be written back — never use a bare `read_text(encoding="utf-8")` on a skill document.
11. **Out-of-root links warn, they never fail `validate`** (#7 verdict, pinned by `tests/test_link_severity_contracts.py`). Promoting them to errors would break legitimate sibling/monorepo references; the enforcement signal is `risk_scan()`'s medium finding. Changing this needs a new maintainer decision plus an allowlist key.
12. **Never rely on `tarfile.data_filter`** (#6 verdict, pinned by `TarFallbackPolicyPins`). Keep capability detection plus the independent pre-validator; a permissive (bypassed) filter must not weaken `import`.
13. **`doctor --explain` never elects a winner it cannot cite** (#12). Add a consumer only with a primary-source row in @docs/12-agent-root-discovery-2026-09-08.md; an unrecorded order must stay `undocumented-precedence`, and `skill_count`/`effective_state` contracts (`unresolved`) must not be bent into a runtime resolver — the `EffectiveSkill` model is still approval-gated (ADR-002).
14. **Every request runs the request policy — `GET` included** (SEC-1, closing the F-1 half of issue #14). `web_security.validate_request()` guards all routed verbs, so a hostile `Host`, `Sec-Fetch-Site: cross-site`, or a mismatched `Origin`/`Referer` now gets a `403` on reads too, not only on mutations; `validate_mutation_request` survives as an alias of the same function. `HEAD` mirrors `GET` (identical headers, no body, with `Content-Length` still describing the entity a `GET` would return); `OPTIONS`/`TRACE` return a JSON `405` carrying `Allow: GET, HEAD, POST, PATCH, PUT, DELETE` and the full security-header set (they used to be a header-less HTML `501`). Pinned by `tests/test_web_client_contracts.py` and the `BUG-9` contracts.
15. **`script-src 'unsafe-eval'` is load-bearing, not an oversight, and `form-action` needs stating** (SEC-4 `ACCEPTED` / SEC-5). The vendored bundle is the runtime+compiler build and `app.js` passes no `template:`/`render:`, so Vue compiles `index.html`'s in-DOM markup with `Function(code)()`; dropping the directive needs precompiled render functions, i.e. a build step, which locked constraint 4 forbids. Never add `'unsafe-inline'` to `script-src`. `form-action` does **not** fall back to `default-src`, so `form-action 'none'` is written out explicitly. Both are pinned by `tests/test_audit_batch5_contracts.py`; the trade-off is reasoned in @docs/08-web-ui.md.
16. **Multipart upload name conflicts are decided before any write** (SEC-6). `web_upload._stage_path()` returns the staging path and rejects a name that is both a file and a directory (`400 a file and a directory share the name 'a'`) and a NUL-byte filename; never call `write_bytes` on a path derived straight from a client-supplied filename. Raw Python exception text must not become the client's error message.
17. **Build with the lock, never with a floating toolchain** (SEC-8). `python3 -m pip install --require-hashes -r requirements-build.txt` then `python3 -m build --no-isolation --wheel --sdist --outdir dist`. `[build-system] requires` is exact-pinned in `pyproject.toml` and must stay equal to the `setuptools==` line in the lock; PEP 518 cannot carry hashes, which is why the build runs `--no-isolation` against the hash-verified venv. `check_package_data.py` reads **every** sdist member now, so a build that ships `tests/`/`docs/`/`.env` fails loudly (`MANIFEST.in` prunes `tests`).
18. **The vendored Vue file is pinned by sha256** (SEC-9): `check_package_data.py` holds `VUE_VERSION`/`VUE_UPSTREAM_URL`/`VUE_SHA256`/`VUE_SIZE` and verifies the checked-in file plus the payload inside both artifacts, before the optional build step. A Vue bump updates all four values in one commit, and `.gitattributes` keeps the file `-text` so EOL translation cannot break the hash.
19. **Developer launchers do not trust the first PATH match** (SEC-15/SEC-16). `browser_harness.py` keeps Chrome's sandbox enabled, binds its ephemeral CDP listener to `127.0.0.1`, and uses `launcher_security.trusted_executable()` for Chrome and Node. `desktop_launcher.py` uses the same resolver; POSIX checks ownership and write permissions and allows a safe later PATH match when an earlier one is unsafe.
20. **Environment-selected data roots are validated** (SEC-19). `paths.data_dir()` canonicalizes the selected base and appended manager directory, rejects unsafe ownership/permissions and broad roots, fails closed rather than falling back, and creates missing components privately. Validator local references are URL-decoded and ignore fragments, queries, and prose punctuation when checking existing targets (FM-19).

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

`check_docs.py` is not just a link checker any more (extended 2026-09-11): it enforces
the HADS header facts (H1, version line within 20 lines, AI manifest) for **every**
`docs/*.md`, validates local markdown links **and their anchors**, rejects a table
row whose cell count disagrees with its table (an unescaped `|` silently adds a
column), requires a single trailing newline, and checks surface parity in both
directions — every implemented `/api/*` route documented in @docs/08-web-ui.md,
every public `Store` method documented in @docs/04-store-api.md, every CLI command
and alias with a `###` heading in @docs/03-cli-surface.md, and every file named in
this doc's inventory existing on disk. Each check has a regression test in
`tests/test_docs_consistency.py`.

Browser click-through (when UI changed): `PYTHONDONTWRITEBYTECODE=1 python3 browser_harness.py` starts a hermetic server and system Chrome CDP probe, captures console/runtime/network failures, and checks 320/400/640/900/1280px viewports. For interactive debugging use `python3 -m skillsmgr webui --no-browser` + Chrome DevTools: exercise create/edit/disable/remove+undo/restore/trash-purge/validate/doctor/stats/history/templates/import/export/theme-toggle. The harness is dev-only and adds no runtime dependency.

## File inventory (build-relevant)

```text
skillsmgr/
  webapp.py + web_security.py  # backend: routing + server + loopback mutation policy
      web_serialization.py     # JSON body/response helpers
      web_upload.py            # multipart folder-upload staging policy
  scopes.py            # agent-scope reads/writes (list/create/edit/remove/toggle/sync/search)
  loader.py            # shared SKILL.md loader + dir scanner (Store + scopes)
  observations.py      # non-persisted hashes, provenance, frontmatter partitions
  root_discovery.py    # physical-root + observed-scope policy
  atomic_io.py         # atomic text writes, mutation locks, tree hashes
  archive.py           # archive preflight, extraction, staged commit policy
  tokens.py            # token/context estimation (tiktoken or chars/4)
  diagnostics.py       # stderr-only recovery diagnostics (no schema change)
  launcher_security.py  # trusted PATH executable discovery for dev launchers
  webui/
    index.html         # Vue templates for every screen/modal
    styles.css         # design tokens + components + responsive
    domain.js          # no-build transport/formatting/frontmatter/Markdown seam
    app.js             # Vue app: state, actions, dialogs, keyboard/focus
    static/vendor/vue.global.prod.js   # Vue 3.5.13 (vendored)
  cli.py               # stable adapter: main/build_parser + compatibility names
  cli_parser.py        # argparse construction
  cli_handlers.py      # command behavior
  cli_output.py        # JSON/errors/table rendering
  store.py             # FS/index/recovery/archive policy
  insights.py          # read-only Milestone 9 helpers (pure, no CLI/Store/schema)
tests/test_insights_contracts.py  # insights hermetic contracts (57 tests)
tests/test_audit_batch5_contracts.py  # SEC-4..SEC-9 + SEC-13 regressions
tests/test_audit_batch8_contracts.py  # SEC-14..SEC-18 regressions
tests/test_audit_batch9_contracts.py  # FM-19 reference normalization regression
tests/test_audit_sec19_contracts.py   # SEC-19 trust-root regressions
tests/test_eval_harness_contracts.py  # eval case/path/atomicity contracts
tests/test_validator_fm11.py  # FM-11 directory-name validation
requirements-build.txt  # hash-verified build toolchain (SEC-8)
MANIFEST.in            # sdist contents: prune tests (SEC-13)
.gitattributes         # keeps the vendored Vue bundle byte-stable (SEC-9)
smoke_store.py         # store smoke (green)
smoke_web.py           # REST smoke (green)
smoke_fixtures.py      # shared tmp-store + loopback-server lifecycle helpers
browser_harness.py     # dev-only Chrome CDP viewport probe (green, 5 viewports)
docs/08-web-ui.md      # authoritative web UI doc
docs/12-agent-root-discovery-2026-09-08.md  # discovery inventory v1.2.0 ([?]s closed)
docs/06-progress-log.md# dated entries (newest top)
```

## Open questions / next steps

- `[?]` None for the web UI itself. Native window wrapper remains deferred; high-zoom/contrast/touch manual browser coverage remains follow-up. Effective consumer shadowing remains approval-gated.
