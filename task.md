# Task Checklist — Skills Manager

**Version 0.3.0**

**AI manifest**: Single source of truth for remaining work on skills-manager. Update after every step. Notation: `[ ]` unstarted, `[/]` in progress, `[x]` done. Milestones: (1) docs layer, (2) GUI, (3) zero-error iteration loop.

## Milestone 1 — Docs layer (2026-08-13)

- [x] Confirm repo layout and module inventory
- [x] Verify CLI command surface (27 top-level + 7 nested + 3 aliases, 37 invocable names) from `skillsmgr/cli.py`
- [x] Verify Store public API via grep of `skillsmgr/store.py`
- [x] Verify GUI toolkit availability (GTK4 4.14 selected, GTK3 3.24 fallback)
- [x] Capture AGENTS.md research takeaways (Red Hat article + context-engineering / agent-legibility skills)
- [x] Create `docs/` directory
- [x] Write `task.md` (this file)
- [x] Write `AGENTS.md` (hot cache, router, <=150 lines)
- [x] Write `docs/README.md` (docs index, hot/warm/cold map)
- [x] Write `docs/01-architecture.md` (data model, data-dir layout)
- [x] Write `docs/02-modules.md` (module-by-module facts)
- [x] Write `docs/03-cli-surface.md` (command table, exit codes)
- [x] Write `docs/04-store-api.md` (public API + SQLite schema)
- [x] Write `docs/06-progress-log.md` (dated log entries)
- [x] Write `docs/07-context-strategy.md` (hot/warm/cold model for sessions)
- [x] QA docs: every @docs/ pointer resolves, HADS format valid, no stale facts

## Milestone 2 — GUI (local web UI, replaced GTK4 on 2026-08-14)

- [x] Scaffold `skillsmgr/gui.py` + `__main__` integration (GTK4, later deleted)
- [x] Main window: skill list (mirror `list` output, status columns)
- [x] Detail view: view skill metadata + body (mirror `view`)
- [x] Actions: create, add, edit, disable, enable, remove (trash/purge), restore
- [x] Search bar (mirror `search` scoring, live filtering)
- [x] Manage: validate, doctor, stats, history, trash views, templates list/new, db rebuild/resync
- [x] Import/export/backup/restore (import modal + export download + folder upload)
- [x] Error paths: StoreError/SkillNotFound surfaced as dialogs/toasts, never tracebacks
- [x] Launch check: web UI serves on 127.0.0.1 and opens in browser

## Milestone 3 — Zero-error iteration loop

- [x] Run `python3 -m skillsmgr --help` — no CLI regressions
- [x] Run `python3 smoke_store.py` — passes
- [x] Run `python3 smoke_web.py` — passes (all REST endpoints)
- [x] Browser click-through: create/edit/disable/remove+undo/restore/trash/validate/doctor/stats/history/templates/import/export/theme — zero console errors
- [x] Mobile 400px viewport: no topbar overflow
- [x] Fix 4 CLI bugs (export/backup/db rebuild/doctor) found by reproduction
## Milestone 4 — Security + hardening audit (2026-09-04)

- [x] Security audit + bug audit via subagents (P0/P1/P2 triaged with evidence)
- [x] P0 fixes: `validate --all` fs-scan, PATCH name ignored, import traversal/type/empty guards, 25 MB body + Content-Length caps, generic 500 + stderr log, tar `filter="data"`, restore timestamp-regex, purge skips non-timestamp dirs
- [x] P1/P2 fixes: scopes injectable global store (`set_global_store`, wired in `WebAppServer`), `sync_skill` name validation, loader `malformed` flag, frontend `listSeq`/`detailSeq` race guards + scope-aware undo/restore, docs `--scope`/`--raw`/zip corrections, web-UI rule-1 correction
- [x] `smoke_store.py` made hermetic (tmp fixture replaces external opencode path)
- [x] Full CLI E2E matrix on temp data dir (create/list/view/raw/edit/search/limit/disable/enable/validate/stats/doctor/history/export/remove/trash/restore/purge/templates/db/sync/scopes/tokens/install-dry-run + error paths; exit codes 0/1/2 verified)
- [x] Full REST edge matrix (traversal→400, empty→400, zip→400, bad-archive→400, oversize→400, long-query→400, history clamp, PATCH-name-ignored, disable/enable, static `..`→404, unknown→404)
- [x] `node --check` on `webui/app.js`; UI serve check (index + vendored Vue 200)
- [x] `security_best_practices_report.md` (no criticals; H-1 supply-chain note, M-1 tar-fallback, M-2 member allowlist, M-3 path disclosure)
- [x] `skills-manager-threat-model.md` v1.0 (assets A-1..A-4, boundaries B-1..B-5, paths T-1..T-10, risks R-1..R-5)

## Milestone 6 — OSS launch kit (2026-09-05)

- [x] Packaging: `pyproject.toml` (`skills-manager`, `requires-python >=3.10`, `skills-mgr` entry, stdlib-only, no dev deps), `.gitignore`, `LICENSE` (MIT)
- [x] Docs: `README.md` (badges, quickstart, scopes table, web UI, data model), `CONTRIBUTING.md` (stdlib-unittest, locked constraints), `SECURITY.md` (72h ack / 14d fix, localhost scope notes), `CHANGELOG.md` (Keep a Changelog, Unreleased + 1.0.0), `ROADMAP.md` (v1.1 / v1.2+ / non-goals)
- [x] Reports: `security_best_practices_report.md`, `skills-manager-threat-model.md` (T-1…T-10, R-1…R-5)
- [x] Tests: `tests/test_store.py` (22), `tests/test_webapp.py` (3, serve_forever thread + shutdown/join/close), `tests/test_web_scopes.py` (13, hermetic HOME+DATA override) — 38 total, all OK via `python3 -m unittest discover -s tests`
- [x] CI: `.github/workflows/ci.yml` (3.10/3.11/3.12, py_compile + unittest + both smokes + node --check), bug/feature templates, PR template
- [x] Fixes in this pass: test `_skill_body` helper (dump_frontmatter takes dict only, body appended separately); real `Store.restore()` prefix-collision bug (now `_strip_trash_suffix(p.name) == name`); README cursor path (`~/.cursor/skills`); pytest→unittest everywhere (offline env)
- [x] Verified: compile OK, 38 unittest OK, both smokes pass, `node --check` OK, `--help` OK, `--scope agents` OK (empty — no ~/.agents on this box)
- [x] Published: `udayvarmora07/skills-manager` created via `gh`, `main` + `v1.0.0` pushed, CI green (run 33914953774); PyPI name `skills-manager` confirmed free, `dist/` built (sdist+wheel) — upload blocked pending PyPI API token (`/tmp/buildenv/bin/python -m twine upload dist/*`)

## Milestone 7 — v1.1 spec-lint+ (in progress, 2026-09-05)

- [x] Spec-lint+ in `validator.py` (no new commands/Store methods): name regex already rejects `--` (`^[a-z0-9]+(-[a-z0-9]+)*$`, verified); `description_score()` (use-context detection + vague-filler hits); description warnings (missing use-context, filler words); body token warning (>5000 tokens, progressive-disclosure guidance); `scripts/`/`references/`/`assets/` layout check (dangling mentions)
- [x] Tests: 5 new `unittest` cases (43 total OK) + `smoke_store.py` spec-lint section
- [x] Cross-scope dedup (same-name detect + descriptions-differ flag + converge via existing sync): `scopes.find_duplicates()` read-only over `list_all()`; surfaced in `doctor --scope all` (text + `duplicates` JSON key), `/api/doctor?scope=all` (`duplicates` + `scopes` keys), doctor modal section with Sync… converge buttons; 4 hermetic tests (47 total OK) + `smoke_web.py` shape assertion
- [x] Token budget view in CLI + UI (verified already complete, no new code needed): `tokens --scope all` aggregate (`total/avg/max`, `largest[]`, `pct_window`), `/api/stats?window=` (`all_tokens/all_avg/all_pct`, top-5 `largest`), `/api/tokens`, frontend budget bar + window selector + per-row tokens + sync-mirror cost hint
- [x] Rollback snapshots + one-command migration (constraint-5 ASK → issues #1 + #2 opened via `gh`, no code until approved)

## Milestone 8 — World-class roadmap baseline (2026-09-07 UTC / 2026-09-08 local)

- [x] Capture reproducible baseline command output in `docs/09-baseline-evidence-2026-09-07.md` (compile, 47 unit tests, both smoke suites, frontend syntax, CLI help, package-build result, Git state)
- [x] Record exact current-`main` behavior for P0-SEC-001 through P0-SEC-005 in `docs/09-baseline-evidence-2026-09-07.md` using isolated temporary data and no product-code changes
- [x] Compare both unmerged worktrees file-by-file against `main`; record the overlap/conflict map and safe replay order in `docs/10-worktree-integration-comparison-2026-09-08.md`

## Milestone 9 — Selective replay and path safety (2026-09-08)

- [x] Build the selective replay/status map in `docs/11-integration-status-2026-09-08.md`; candidate worktrees remain unmerged and classified.
- [x] Add `docs/PRE-MERGE-CHECKLIST.md` for provenance, source/artifact integrity, safety, verification, and documentation gates.
- [x] Decide `dist/` and `skills_manager.egg-info/` are ignored local artifacts, not release inputs.
- [x] Add canonical `validate_skill_name()` and resolved `contained_path()`/`safe_skill_path()` helpers without changing the public Store API or SQLite schema.
- [x] Guard Store and agent-scope filesystem operations, URL-decoded REST names, CLI names, trash destinations, and manifestless import fallback names.
- [x] Add hermetic regression coverage for symlink/absolute/parent escapes, Store/scope mutations, encoded REST reads/deletion, pre-handler CLI rejection, invalid archive fallback names, and victim preservation.
- [x] Verify: compile PASS, **57 unittest PASS**, `smoke_store.py` PASS, `smoke_web.py` PASS, `node --check` PASS, CLI help PASS, and `git diff --check` PASS.

## Milestone 10 — Archive and trash safety (2026-09-08)

- [x] Prevent forced imports from treating invalid manifest destinations as
  filesystem paths or deleting an outside destination.
- [x] Make trash list/restore/purge/doctor accept only exact canonical skill
  names with valid timestamp suffixes; ignore malformed, symlinked, and
  prefix-collision entries.
- [x] Add tar archive preflight before destination mutation: validate member
  layout and duplicates, extract privately, validate the manifest and skill
  documents, then commit planned skills.
- [x] Reject absolute/traversal members, unexpected layouts, symlinks, hard
  links, FIFOs, device/special members, and duplicate archive names.
- [x] Feature-detect `tarfile.data_filter` and use a guarded regular-file/
  directory extractor when it is unavailable; never use unfiltered extraction.
- [x] Add hermetic regressions for forced invalid destinations, archive
  traversal/duplicates/special members, no-filter compatibility, malformed
  trash entries, and valid archive round trips.
- [x] Verify: compile PASS, **65 unittest PASS**, `smoke_store.py` PASS,
  `smoke_web.py` PASS, `node --check` PASS, CLI help PASS, and `git diff --check`.

## Milestone 11 — Parser, search, and localhost request safety (2026-09-08)

- [x] Add frontmatter document/key/collection/scalar/nesting resource limits and
  convert deep parser failures into clean `FrontmatterError` responses.
- [x] Preserve valid frontmatter round trips and add deterministic malformed/deep
  input regressions.
- [x] Bound wildcard search length and star complexity, collapse repeated stars,
  and return clean errors instead of allowing regex exhaustion.
- [x] Route Store, global, agent, merged, CLI, and REST searches through the same
  bounded matcher; preserve body matching.
- [x] Centralize mutation request checks for Host, Origin, Referer, and
  `Sec-Fetch-Site`; define header-absent local-client behavior explicitly.
- [x] Require JSON for JSON mutation bodies, reject non-loopback server binds,
  and add defensive CSP/cross-origin/MIME/framing response headers.
- [x] Add hermetic regressions for hostile origins, referers, fetch metadata,
  hosts, content types, every mutating HTTP method, wildcard exhaustion, body
  matching, and frontmatter limits.
- [x] Verify: compile PASS, **76 unittest PASS**, `smoke_store.py` PASS,
  `smoke_web.py` PASS, `node --check` PASS, CLI help PASS, focused REST probes
  PASS, and `git diff --check` PASS.

## Milestone 5 — Proposed ideas (research verdicts 2026-09-09, see Milestone 31)

- [!] Native window wrapper (pywebview/Electron) — verdict: REJECT as a product direction; browser stays canonical. At most an unbundled loopback-only launcher, never a shipped dependency.
- [x] Skill-body editor has an escaped live markdown preview; no renderer dependency added.
- [x] Keyboard-shortcut cheatsheet modal (`?` key) added after the keyboard contract.
- [!] Pytest suite is not planned: `tests/` uses the approved stdlib `unittest` suite; adding third-party test tooling would require an explicit tooling decision
- [x] CI workflow (compile + unittest + smokes on push) is present in `.github/workflows/ci.yml`; future CI expansion remains tracked in the roadmap
- [ ] Zip-import support, APPROVED-direction (research 2026-09-09): extend `import` only, no new command — red-first malicious-ZIP corpus through the Milestone 1 pipeline shape (zip preflight mirroring tar guards, manual extractor with symlink-bit check, staged commit + hash verify). See Milestone 31 L2.
- [!] Tar-fallback refusal on Python < 3.12 — verdict: REJECT (keep feature-detect + guarded manual extractor; refusal breaks supported 3.10/3.11 for zero fail-closed gain). Record on issue #6.
- [!] Out-of-root link warning → validation error — verdict: REJECT strict promotion (keep warning + `risk_scan()`; 200-target probe found 0 real escapes). Record on issue #7.

## Milestone 12 — Archive resource, manifest, and commit safety (2026-09-08)

- [x] Add compressed-size, expanded-size, per-member-size, member-count,
  path-length, nesting-depth, and compression-ratio limits to tar preflight.
- [x] Validate the `skills-mgr` manifest app/version/timestamp contract,
  canonical unique names, manifest-to-path alignment, and extracted
  frontmatter names before any destination mutation.
- [x] Preserve canonical manifestless fallback validation and explicitly reject
  ZIP archives by content; ZIP support remains deferred by policy.
- [x] Stage each skill commit, restore the prior destination on replacement
  failure, clean failed new destinations, and report completed/failed skills
  explicitly in `imported`/`skipped`.
- [x] Add hermetic regressions for archive budgets, strict manifests, ZIP
  rejection, frontmatter/name mismatch, forced-destination preservation, and
  injected per-skill copy failures.
- [x] Verify: compile PASS, **86 unittest PASS**, both smoke suites PASS,
  frontend syntax PASS, CLI help PASS, and `git diff --check` PASS.

## Milestone 13 — Recovery snapshots, migration, and localhost policy (2026-09-08)

- [x] Decide the localhost mutation-token question in ADR-001: no token is
  warranted while the server is loopback-only, sessionless, and supports local
  non-browser clients.
- [x] Add validated snapshots under `<data>/snapshots/<scope>/<name>/` with
  newest-five retention, canonical scope/name/path guards, automatic snapshots
  before global/agent edits and forced sync overwrite, and global/agent restore.
- [x] Add `--snapshot` restore/history visibility to the existing CLI and REST
  surfaces, plus web UI snapshot listing and rollback controls.
- [x] Add `--full` to existing export/backup/import surfaces without adding a
  command: full exports include skills, validated trash, and templates; full
  imports remain skip-by-default and require an explicit full archive.
- [x] Route full migration through the hardened tar/resource/manifest pipeline;
  agent scopes and snapshots stay excluded from migration archives.
- [x] Add rollback, five-retention, agent-scope, full migration, slim/full
  compatibility, and REST snapshot regression coverage.
- [x] Verify focused recovery tests PASS; final full-suite/smoke/frontend/help
  evidence is recorded after the final verification run.

## Milestone 14 — Atomic recovery and documentation truth (2026-09-08)

- [x] Add atomic sibling-temp text writes with flush/fsync/replace and a documented durability policy.
- [x] Preserve original skill content across replacement, serialization, index, and history failures.
- [x] Serialize same-process per-skill mutations; document cross-process recovery through atomic replacement plus doctor/resync.
- [x] Add failure-injection, concurrent-edit, doctor-drift, and content-hash backup regressions.
- [x] Extend doctor diagnostics for transaction artifacts, temporary files, stale snapshots, and filesystem/index drift.
- [x] Reconcile architecture, module, Store API, CLI, README, settings, and session-context documentation with current source.
- [x] Add `check_docs.py` and a CI documentation/source consistency gate without adding a product CLI command.

## Milestone 15 — Root and consumer discovery baseline (2026-09-08)

- [x] Record the approval-gated `SkillRoot`/`Consumer`/binding/instance/effective-state model in `docs/ADR-002-root-consumer-effective-state.md`.
- [x] Inventory official discovery roots, precedence, recursion, reload, and client metadata in `docs/12-agent-root-discovery-2026-09-08.md`; unresolved Codex/Command Code behavior is marked `[?]`.
- [x] Correct Cursor's user root to `~/.cursor/skills` and document shared compatibility roots.
- [x] Deduplicate resolved physical roots before aggregate scope counts/listing and sync target expansion.
- [x] Document global, user, project, and nested-project semantics without introducing approval-gated runtime entities or schema changes.

## Milestone 16 — Root capability and observed instance states (2026-09-08)

- [x] Enable recursive discovery only for consumer roots whose official inventory supports it; flat roots remain one-level scans.
- [x] Expose root availability as `writable`, `read-only`, `missing`, or `unsupported` in scope descriptors.
- [!] Keep true consumer/project effective resolution approval-gated; compatibility output explicitly reports `effective_state: unresolved`.
- [!] Add observed instance states (`active`, `disabled`, `invalid`, `duplicated`, `divergent`, `unmanaged`); `shadowed` remains blocked on precedence-aware effective resolution.
- [x] Preserve the unique physical-root sync guarantee and add recursive/state regression coverage.

## Milestone 17 — Observations and internal hotspot extraction (2026-09-08)

- [x] Preserve unknown/client frontmatter and partition portable fields from extensions without losing round-trip data.
- [x] Add non-persisted content/metadata hashes, observed timestamps, and provenance to loaded/public records.
- [x] Extract archive inspection/extraction/staged-commit policy into `skillsmgr/archive.py` with Store compatibility adapters.
- [x] Extract atomic writes/locks/tree hashing into `skillsmgr/atomic_io.py` and root discovery/state policy into `skillsmgr/root_discovery.py`.
- [x] Keep public CLI/Store signatures, SQLite schema, and filesystem source-of-truth behavior unchanged.

## Milestone 18 — Web/CLI contract hardening and complexity ratchet (2026-09-08)

- [x] Extract web request security, JSON serialization, and multipart upload policy into private modules with compatibility wrappers.
- [x] Fix text `scopes` output regression and forward REST import `full=1` to full archive restoration.
- [x] Add CLI, REST, and AST complexity regression tests; add stderr-only rollback diagnostics.
- [x] Wire `check_complexity.py` into contributor and CI verification.
- [x] Deep-test REST malformed input, security, upload, archive, CLI, diagnostics, and complexity seams; fix type-validation 500s and integrate CLI output helpers.
- [x] Add an audit regression test proving extracted web helpers, `RequestError`, and CLI output aliases retain their historical private call shapes.

## 2026-09-08 — REST validation regression closeout (17:20 UTC)

- [x] Reject non-string `/api/install` `source`, `scope`, and `runner` values with JSON HTTP 400 before command construction.
- [x] Enforce string-only scalar skill metadata at REST create/patch boundaries; preserve ignored `name` patch behavior.
- [x] Reject unsupported `allowed_tools` lists consistently for global and agent-scope create/patch requests, while preserving accepted strings.
- [x] Add focused hermetic REST regressions for malformed install/create/patch payloads and global/agent `allowed_tools` behavior.
- [x] Verification recorded in the progress log: targeted web tests, full unittest (128 tests), both smoke suites, compile, frontend syntax, docs, complexity, and diff checks.

## Milestone 19 — Hermetic smoke fixture refactor (2026-09-08)

- [x] Share only minimal temporary-store and loopback-server lifecycle helpers between `smoke_store.py` and `smoke_web.py`.
- [x] Preserve executable smoke output and behavior; add focused helper lifecycle tests in `tests/test_smoke_fixtures.py`.
- [x] Run final full unittest, both smokes, compile, docs, complexity, and diff checks; record exact results in the progress log.

## Milestone 21 — Documentation consistency gate (2026-09-08)

- [x] Check all local `@docs/*.md` pointers, including historical Markdown, without network access.
- [x] Check documented `Store.method`, module symbols, and explicit `skillsmgr/*.py` paths against AST source facts.
- [x] Derive current CLI command counts from `cli.py`; check stale current command/UI claims while preserving historical docs semantics.
- [x] Check package/source/documented version alignment and add focused stdlib tests for each failure class.
- [x] Wire `check_docs.py` into contributor checks; CI already runs the docs gate.

## Milestone 20 — Distribution package-data verification (2026-09-08)

- [x] Add stdlib-only `check_package_data.py` to build exact wheel/sdist outputs in a temporary directory and inspect `skillsmgr/webui/` plus vendored Vue contents.
- [x] Add deterministic offline archive assertions for wheel/sdist member sets and missing Vue/package-data rejection.
- [x] Add optional isolated temporary-venv install probes for both artifacts without network or runtime dependency changes.
- [!] Build/install coverage reports `UNAVAILABLE` when optional `python -m build` tooling is absent; existing `dist/` artifacts are never treated as fresh evidence. `--require-build` returns exit 2 for release-required jobs.

## 2026-09-08 — CLI data-dir search regression closeout (18:27 UTC)

- [x] Make CLI global search use the Store selected by `--data-dir`, not `scopes._GLOBAL_STORE`.
- [x] Keep merged search global records on the requested Store while agent records continue through scope adapters.
- [x] Add hermetic two-data-dir CLI regressions for global and merged search isolation.
- [x] Preserve global body matches in scope and merged searches by building ranking records through public `Store.list()`/`Store.get()` seams, without changing result schemas or ranking rules.
- [x] Convert wildcard-complexity `ValueError` to the established `StoreError` contract in `scopes.search_all`, including CLI and REST callers.
- [x] Update search documentation and retain the focused body/ranking/error regressions in `tests/test_search_contracts.py`.
- [x] Verification: focused search tests and final full unittest suite (208) passed; smoke, compile, docs, complexity, frontend, and diff checks also passed; package-data build remains environment-unavailable as recorded in the progress log.

## 2026-09-08 — REST two-server search isolation regression closeout

- [x] Pass each REST global and merged search call through the handler's `self.store`; preserve agent-scope adapters, body-aware ranking, output schemas, singleton compatibility, and all locked constraints.
- [x] Add a hermetic two-`WebAppServer` regression proving each server's `scope=global` search returns only its own global result and `scope=all` returns that global result plus the shared agent result; stop both servers during cleanup.
- [x] Verification: focused search contracts (11 tests) PASS; final full unittest suite (208 tests) PASS; `smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); Python compile PASS; `node --check skillsmgr/webui/app.js` PASS; `check_docs.py` PASS; `check_complexity.py` PASS (168 functions); `git diff --check` PASS.

## Milestone 22 — Advanced loop-engineering campaign (2026-09-09)

- [x] Ran nine deterministic hermetic probe loops (stdlib only, probe code kept outside the repo in `~/sm-probes/`): store-lifecycle burst (600 ops), frontmatter round-trip/hostile fuzz (1,200 docs), failure injection, REST fuzz (700 requests), concurrency stress, search/validator/loader-templates/CLI-env fuzz, CLI adversarial matrix (182 checks), archive boundary+grammar fuzz (450 archives), scope differential loop (1,200 ops).
- [x] Fixed 15 genuine defects surgically with red-first hermetic regressions (no new commands/flags, no Store public methods, no schema change — private helpers and internal `_unlocked` splits only): trashed-row reactivation on create/add (FIX-1), same-second trash counter recognition (FIX-2), honest double-remove error (FIX-3), import backup-move recovery preserving the original (FIX-4), truncated-gzip clean StoreError (FIX-5), CLI schema bootstrap on first run (FIX-6), install source/agent validation parity (FIX-7), flow scalar + quote-char key quoting (FIX-8), list doc correction (FIX-9), nested-block mapping emission with inline empty collections (FIX-10), post-sync global resync + resync reactivation (FIX-11), per-skill lock coverage + stranded-temp cleanup (FIX-12), purge StoreError wrapping (FIX-13), duplicate frontmatter keys now fail loudly (FIX-14, promoted from OBS-1), `purged` names deduped (FIX-15, promoted from OBS-3).
- [x] Kept every gate green without baseline inflation: 224 unittest PASS, both smokes PASS, compile/`node --check`/`git diff --check` PASS, `check_docs.py` PASS, `check_complexity.py` PASS (194 functions, new helpers under budget).
- [x] Recorded the full method, evidence, and per-finding repro/root-cause/fix detail in `loop-engineering-findings.md`; updated `docs/02-modules.md` (store atomicity/index, frontmatter round-trip incl. duplicate-key rejection), `docs/04-store-api.md` (`purged` dedup) and `docs/03-cli-surface.md` (`list` status semantics).

## Milestone 24 — Browser UX, accessibility, module seams, and documentation truth (2026-09-09)

- [x] Split CLI parser construction and handlers into `cli_parser.py` and `cli_handlers.py` while preserving `skillsmgr.cli` imports and output aliases.
- [x] Split frontend transport/formatting/frontmatter/escaped-Markdown policy into no-build `webui/domain.js`, loaded before `app.js`; package-data discovery remains recursive.
- [x] Add dialog focus lifecycle: safer initial focus, Tab trap, Escape close, opener restoration, labelled dialogs, `inert`/`aria-hidden` background, live status/error announcements, and shortcut help.
- [x] Add escaped editor Markdown preview and pre-sync resolution/overwrite/rollback preview.
- [x] Add `browser_harness.py`: hermetic Store + loopback server + system Chrome CDP, console/runtime/network failure capture, and 320/400/640/900/1280px overflow matrix.
- [x] Reconcile AGENTS, web UI/module/session docs, TODO/PLAN/task/CHANGELOG/progress claims; current effective shadowing and native-wrapper work remain explicitly approval-gated/deferred.
- [x] Verification during implementation: CLI/web/package/docs focused tests PASS; smoke web PASS; frontend syntax PASS; browser harness PASS across all five viewports.

## Milestone 23 — Controlled release engineering (2026-09-09)

- [x] Rewrote `ci.yml` into separate `unit` (3.10–3.14 matrix) / `adversarial` / `package` (build-once + `--dist-dir` gate + artifact upload + clean-install smoke) / `docs` / `xplat` (Linux/macOS/Windows × 3.10/3.14 path/archive contracts) / `browser` jobs with least-privilege `contents: read` permissions and a pin-policy header.
- [x] Added `check_package_data.py --dist-dir` build-once inspection mode with hermetic regressions (pass on exact wheel+sdist, fail on missing member).
- [x] Closed the Windows-separator containment gap hermetically: `contained_path()` and archive member validation reject `\` and drive-letter prefixes on every host (red-first, prior suite stayed green).
- [x] Added tag-gated `release.yml`: validate tag/package-version alignment before build or publish; build once → verify exact artifacts → attest provenance → TestPyPI → protected `release` environment PyPI via Trusted Publishing (no long-lived token) → GitHub Release → tag/version/asset/CRUD/PyPI-install verification.
- [x] Qualified PyPI claims honestly: badge removed, README states PyPI is a future release with source/CI-artifact install paths; classifiers extended to 3.13/3.14 to match the tested matrix.
- [x] Locked all of the above with `tests/test_ci_release_contracts.py` (CI structure, xplat containment, build-once, release, PyPI-claim contracts); updated `TODO.md` Milestone 8, `CHANGELOG.md` Unreleased, `CONTRIBUTING.md` checks, and `docs/06-progress-log.md`.
- [x] Verified: full unittest suite PASS, both smokes PASS, compile/`node --check`/`git diff --check` PASS, `check_docs.py` PASS, `check_complexity.py` PASS, YAML parses, `git status` shows only intended files.
- [x] Closed release-integrity and cross-platform CI gaps found in review: release tags must equal the package version before build/publish; xplat jobs use the portable `python` executable on Windows; workflows use least-privilege permissions; browser CI runs the CDP harness plus both frontend syntax checks.

## Milestone 25 — Milestone 9 read-only insight foundation (2026-09-09)

- [x] T1 per-consumer “what this agent sees” observed view (`insights.consumer_view`; precedence stays unresolved per ADR-002).
- [x] T2 two-way and three-way skill diff (`insights.diff_skills`/`diff_three_way`; conflicts hold base).
- [x] T3 ownership-state classifier (`managed`/`unmanaged`/`adopted`/`quarantined`/`invalid`).
- [x] T4 provenance summary over loader observations (known/unknown split; persistence approval-gated).
- [x] T5 update preview (changed files, token/body/snapshot risks, rollback flag from snapshot list).
- [x] T6 quarantine staging planner (stage-only plan, `validate_skill_name`, zero disk mutation).
- [x] T7 explainable static risk scan (script/link/tool/pattern findings with why + evidence).
- [x] T8 offline registry preview (dry-run steps, explicit trust gate; network browse deferred).
- [x] T9 provider-neutral eval harness skeleton (stdlib-only plan, caller-supplied deterministic scorer, advisory-only).
- [x] T10 signed/team bundle deferral policy (`deferred` pending issue #11 trust review).
- [x] T11 red-first hermetic contracts in `tests/test_insights_contracts.py` (57 tests: 20 foundation + 11 fail-closed + 9 round-3 + 7 round-4 + 5 E2E + 5 round-5 audit locks; all red-first).
- [x] T12 `skillsmgr/insights.py` implementation (pure, stdlib-only, no CLI/Store/schema/network changes).
- [x] T13 docs reconciliation (`docs/02-modules.md`, `TODO.md` Milestone 9, this milestone, `CHANGELOG.md`, progress log).
- [x] T14 full verification ladder plus fresh-tmp live-seam exercise (recorded in progress log).
- [x] T15 clean diff review and commit of exactly the intended files.

## Milestone 26 — Insights fail-closed hardening (2026-09-09, second 15)

- [x] T1 input-type guards: dict/list `ValueError` policy across diff, provenance, risk, consumer, ownership seams.
- [x] T2 safe token coercion in `update_preview` (non-numeric/negative/bool tokens coerce to `None`, no raw raises).
- [x] T3 bounded `body_diff` output (`MAX_BODY_DIFF_LINES` = 200 + `body_diff_truncated` flag).
- [x] T4 strict `registry_preview`/`eval_plan`/`eval_score` shape validation (non-dict cases, missing keys rejected).
- [x] T5 name edge cases (`quarantine_plan`/`registry_preview` reject blank and non-string names).
- [x] T6 11 red-first hermetic hardening tests (2 failures + 9 errors before green).
- [x] T7 `skillsmgr/insights.py` hardening implementation (pure, stdlib-only, no locked-constraint changes).
- [x] T8 16-probe adversarial fuzz re-run (all clean `ValueError`/safe values after fix).
- [x] T9 `docs/SESSION-CONTEXT.md` file inventory gains `insights.py` + contracts.
- [x] T10 stale "20 tests" claims corrected; fail-closed policy documented in `docs/02-modules.md`.
- [x] T11 full ladder: 275 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS.
- [x] T12 fresh-tmp live-seam re-exercise (huge-body bound, weird-token, registry-gate, eval all OK).
- [x] T13 `browser_harness.py` re-run PASS (`"passed": true`).
- [x] T14 staged diff review and commit of exactly the intended files.
- [x] T15 progress log entry with final evidence.

## Milestone 27 — Insights robustness round 3 (2026-09-09, third 15)

- [x] T1 strict-string names (`_canonical_name`; `123`/`True`/list/dict rejected; padded strings trim).
- [x] T2 JSON-serializability contract across all 11 helper outputs.
- [x] T3 deterministic ordering under shuffle (consumer view sorts; ownership preserves input order).
- [x] T4 non-string fields locked (int body, dict description, list tools/extensions).
- [x] T5 hostile strings (null bytes, 100KB, emoji) fast and JSON-clean.
- [x] T6 scorer propagation + plan-shape locks (`eval_score` malformed/misaligned `ValueError`).
- [x] T7 three-way missing-key + registry extra-key behavior locks.
- [x] T8 whitespace names + huge-input timing bounds (4000-line diff, 100k-line scan < 5s).
- [x] T9 4-thread concurrency smoke (100 iterations each, zero errors).
- [x] T10 `risk_scan` refactor (19 → max 9 local complexity; hotspot ratchet unaffected).
- [x] T11 strict-name gaps implemented to green (1 red failure first).
- [x] T12 full ladder: 284 unittest PASS, smokes, compile/frontend/docs/complexity/diff/help PASS.
- [x] T13 fresh-tmp live seam + `browser_harness.py` PASS.
- [x] T14 staged diff review and commit of exactly the intended files.
- [x] T15 progress log entry with final evidence.

## Milestone 28 — Deep E2E audit of all 45 insights tasks (2026-09-09, E1–E9)

- [x] E1 real lifecycle E2E (global + cursor creates, dup, disabled, list/scan/find_duplicates).
- [x] E2 views/ownership/provenance E2E (counts, unresolved precedence, five states, content hashes).
- [x] E3 diff/preview/rollback E2E (cross-scope diff, snapshot auto-capture, byte-accurate restore).
- [x] E4 risk/quarantine/registry/eval/bundle E2E (hostile skill findings, trust gate, 1/1 scoring).
- [x] E5 purity audit (SHA-256 tree hash + input deepcopy: zero mutation).
- [x] E6 JSON/determinism/concurrency/perf probe (30× instant, 8×150 threads, 6000-line bound).
- [x] E7 REST matrix + CLI lifecycle (200s, validate/purge clean).
- [x] E8 one genuine defect fixed red-first (`_record_invalid` via real skill-dir validation; first wrong fix reverted with evidence).
- [x] E9 full ladder green (289 unittest, smokes, gates, harness) recorded here and in the progress log.

## Milestone 29 — Insights boundary round 4 (2026-09-09, next 10)

- [x] T1 deep-copy records in `consumer_view` (nested mutation leak closed).
- [x] T2 scorer must be callable (`eval_score` clean `ValueError`).
- [x] T3 quarantine source must be a string.
- [x] T4 snapshot items must be non-empty strings.
- [x] T5 registry description non-string becomes a blocker, not a crash.
- [x] T6 consumer argument must be a string.
- [x] T7 registry source/scope/content_hash must be strings or missing.
- [x] T8 7 red-first boundary tests (5 failures + 2 errors before green; 52 total).
- [x] T9 ladder green: 296 unittest, smokes, compile/frontend/docs/complexity/diff/help, harness, fresh-tmp.
- [x] T10 per-group commits plus push (this entry, then push step).

## Milestone 31 — Loop-engineering research verdicts (2026-09-09, start here next session)

Research: 9 hermetic probe scripts (isolated temp dirs, stdlib only, no
product-code changes) + ~30 web-search batches (~200 sources) + 5 primary
`web_fetch` reads + repo evidence. Baseline held green throughout (301
unittest PASS, `check_docs.py` PASS, `check_complexity.py` PASS).

- [x] R1 probes recorded: link matrix (`../`, absolute, deep escape warn;
  `https://`/`#`/`<angled>` clean; 200-target walk = 145
  external/anchor, 55 in-root, 0 out-of-root); zip (`zipfile` keeps
  hostile names verbatim; symlink-bit detectable); tar (6/6 hostile
  classes rejected); search (`*a*a*a*a*` instant, 500-char query clean
  `ValueError`); frontmatter (dup/huge/flow-bomb all clean
  `FrontmatterError`); eval/risk/registry/quarantine (9 findings on
  hostile skill, trust gate `False→True`, stage-only); effective
  boundary (`consumer_view` count + `unresolved`, 3-way sides, preview
  risks, `unknown` provenance); REST (x-origin 403, no-CT 415, bad
  install 400, long query 400); signing (HMAC ok, `ed25519` absent).
- [x] R2 verdicts written into `TODO.md` (Milestone 4 note, Deferred
  section, Milestone 11 queue), this milestone, `PLAN.md` (§9 + §11),
  and `docs/06-progress-log.md`.
- [x] L1 closed issue #10 with evidence 2026-09-09 (no code; CLOSED) — see `TODO.md` L1.
- [ ] L2 ZIP slice on approval (red-first corpus, extend `import` only) — see `TODO.md` L2. Remains the only code item.
- [x] L3 effective-explain research done docs-only 2026-09-09 (3 `[?]`s closed in `docs/12-agent-root-discovery-2026-09-08.md` v1.1.0; diagnostic proposal filed as issue #12, awaiting approval) — see `TODO.md` L3.
- [x] L4 rejections #6/#7/#9 recorded with file/line evidence 2026-09-09 — see `TODO.md` L4.
- [x] L5 deferred #3/#4/#8/#11 verified untouched 2026-09-09 (all OPEN, zero comments; no network/backend/signing code) — see `TODO.md` L5.
- [x] L6 release-gate verified 2026-09-09 (dry-run green, no publish; tag `v1.0.0` = package `1.0.0`; `release.yml` tag/version gate + build-once + `--dist-dir` + attestation + TestPyPI→`release` env; package-data honestly UNAVAILABLE without `build`) — see `TODO.md` L6.

## Milestone 32 — Milestone 11 verdict execution, round 1 (2026-09-09, 15 tasks)

Docs + GitHub only; zero product-code changes; no locked-constraint changes.

- [x] T1 baseline ladder green on clean tree (301 unittest, smokes, compile/frontend/docs/complexity/diff recorded).
- [x] T2 L1 evidence pinned (`index.html:70,373,756-760`, `domain.js:60`, `app.js:6,130`).
- [x] T3 issue #10 commented with evidence and CLOSED.
- [x] T4 tar-fallback rejection recorded on issue #6 (`archive.py:133-158`, PEP 706, 3.10/3.11 matrix).
- [x] T5 link-warning rejection recorded on issue #7 (`validator.py:323-352`, 200-target walk, `risk_scan()`).
- [x] T6 desktop-wrapper rejection recorded on issue #9 (constraint 4, harness 320–1280px).
- [x] T7 Codex `[?]` closed (`.agents/skills/` REPO/USER/ADMIN/SYSTEM + no-merge; facade compat-only) — `https://learn.chatgpt.com/docs/build-skills`.
- [x] T8 Command Code `[?]` closed (six-way order, Duplicate-names, `/skill:<name>`, live reload) — `https://commandcode.ai/docs/skills`.
- [x] T9 Claude same-name `[?]` closed (triple-winner + both-load exceptions) — `https://code.claude.com/docs/en/skills`.
- [x] T10 read-only `doctor --explain CONSUMER --project DIR` diagnostic proposed (issue/ADR approval needed; `check_docs.py` PASS).
- [x] T11 deferred #3/#4/#8/#11 verified untouched (all OPEN zero comments; no network/backend/extension/signing code; ZIP rejection-only).
- [x] T12 release gate verified without publishing (tag=version, `--dist-dir`/attestation/TestPyPI→release env; package-data UNAVAILABLE honestly).
- [x] T13 TODO/task/PLAN/progress-log updated for L1/L3/L4/L5/L6 (L2 stays the only code item, approval-gated).
- [x] T14 full ladder + harness + fresh-tmp re-run (recorded in progress log).
- [x] T15 clean diff review, commit, and push of exactly the intended files.

## Milestone 33 — Milestone 11 verdict execution, round 2 (2026-09-09, 15 tasks)

Docs truth + GitHub proposals + verification; zero product-code changes; no locked-constraint changes.

- [x] T1 baseline ladder green (301 unittest, smokes, compile/frontend/docs/complexity/diff).
- [x] T2 docs-truth audit (`01-architecture` repo-map gaps, `05-gui-plan` SUPERSEDED label, `settings.json` history, historical counters).
- [x] T3 `SESSION-CONTEXT.md` v0.3.0 (date, 27+7+3=37 counts, full module inventory, insights-57, Milestone 11 status, discovery v1.1.0 pointer).
- [x] T4 counts truth (`CHANGELOG` 52→57 with round breakdown; `task.md` T11 52→57; `01-architecture` repo-map refresh; CLI 27+7+3=37 re-derived from `check_docs._command_inventory` + live parser).
- [x] T5 L2 confirmed approval-gated (issue #5 OPEN zero comments; `store.py:1221` ZIP rejection-only, no `ZipFile` extraction).
- [x] T6 `doctor --explain CONSUMER --project DIR` proposal filed as issue #12 (read-only, cited, unpersisted; constraint-5 approval requested).
- [x] T7 deferred #3/#4/#8/#11 re-verified untouched (all OPEN zero comments; no network/backend/extension/signing code).
- [x] T8 release dry-run (package/`__version__`/tag `1.0.0` aligned; tag gate + perms verified; no bump/tag/publish).
- [x] T9 package-data honestly UNAVAILABLE; README PyPI-future claim + live 404 confirmed.
- [x] T10 worktree map checked (5 Carson dirs; `git worktree list` heads recorded; `docs/10` scope is the 2-candidate comparison, not a live map).
- [x] T11 browser harness re-run `"passed": true` (5 viewports, zero failures).
- [x] T12 fresh-tmp live seam (create→validate→doctor→search→remove→purge→doctor, all OK).
- [x] T13 TODO/task/PLAN/progress-log updated for round 2 (this milestone; L6 dry-run note; stale-claim status note).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 34 — Loop-engineering re-verification campaign, round 3 (2026-09-09, 15 tasks)

Hermetic probes (stdlib only, `/tmp` scripts, no product-code changes) + docs hygiene + verification; no locked-constraint changes. L2 ZIP and issue #12 both await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, complexity, diff; issues #5 + #12 OPEN).
- [x] T2 store-lifecycle burst (600+ ops, honest double-remove `SkillNotFound`, same-second trash cycle, doctor ok).
- [x] T3 frontmatter 1200 round-trips + 8 hostile inputs (dup/deep/huge/no-close fail-closed `FrontmatterError`; nested-flow/large-body accepted without crash).
- [x] T4 search bounds (7 adversarial patterns fast or clean `ValueError`) + validator link matrix (8/8 exact).
- [x] T5 archive boundary (8 hostile tar classes + garbage + truncated fail-closed; ZIP rejection-only; valid manifest tar round-trips).
- [x] T6 scope differential (404 rows, dup flagged `descriptions_differ`, global/agent isolation, sync converges).
- [x] T7 concurrency (8×100 mixed reads zero errors) + perf (100k-line scan 0.03s, 20k views 0.10s).
- [x] T8 REST fuzz (655 requests, 0 fail-opens; purge takes no body by contract so the no-CT probe covers `/api/skills`).
- [x] T9 CLI matrix (81 checks, 0 fail-opens: traversal/invalid names, search/hostile, lifecycle, exit codes 0/1/2).
- [x] T10 insights sweep (degenerate/purity/determinism/concurrency clean; `eval_score` missing-`expect` tolerant by design, `eval_plan` strict).
- [x] T11 browser harness `"passed": true` (5 viewports, zero failures).
- [x] T12 fresh-tmp live seam (create→validate→doctor→search→remove→purge→doctor, all OK).
- [x] T13 docs hygiene (drop #10 Deferred line now its retention pass elapsed; ref issue #12; L3 wording).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 30 — Insights audit round 5 (2026-09-09, next 10)

- [x] T1 baseline ladder green on clean tree (296 unittest, smokes, gates recorded).
- [x] T2 adversarial sweep: degenerate/nested/unicode/large inputs all JSON-clean.
- [x] T3 filesystem audit: dangling/file/deleted/locked paths `invalid`; insights performs no direct `open()`.
- [x] T4 concurrency + perf: 8×150 mixed 2.49s clean; 200k-line scan 0.06s; 20k views < 0.1s.
- [x] T5 REST/CLI/Store regression: validate/search/purge clean, no drift.
- [x] T6 docs truth: stale "31 tests" claims corrected to 52 in three files.
- [x] T7 5 red-first round-5 lock tests (57 total in the file).
- [x] T8 minimal fixes (docs truth only; zero product-code changes needed).
- [x] T9 full ladder + harness + fresh-tmp recorded here and in the progress log.
- [x] T10 per-group commits plus push (this entry, then push step).
