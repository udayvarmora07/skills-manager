# Task Checklist — Skills Manager

**Version 0.3.0**

**AI manifest**: Single source of truth for remaining work on skills-manager. Update after every step. Notation: `[ ]` unstarted, `[/]` in progress, `[x]` done. Milestones: (1) docs layer, (2) GUI, (3) zero-error iteration loop.

## Current state — 2026-09-11 (authoritative; older milestones below are dated records)

- **Five issues closed out: DONE (#3, #4, #5, #12, #13).** Issue #13 (non-UTF8
  `SKILL.md` raising a raw `UnicodeDecodeError`) is fixed with the
  *read/report paths tolerate, write paths fail closed* contract: the loader
  marks the row `malformed` with an actionable `decode_error`, `Store.doctor`
  reports `undecodable_documents` as drift, and every rewrite path uses
  `read_skill_text_strict()` so lossy replacement characters can never reach a
  write. Issue #12 shipped as the read-only
  `doctor --explain CONSUMER [--project DIR] [--skill NAME]` diagnostic
  (`skillsmgr/effective.py`, also `GET /api/doctor?explain=…`), which derives
  the winner per consumer at read time from cited rules, persists nothing, and
  keeps `effective_state: unresolved`. Issues #3/#4 (offline registry bridge,
  file-based eval harness) and #5 (ZIP import) were re-verified end to end and
  committed. New tests: `tests/test_encoding_contracts.py` (23) and
  `tests/test_effective_explain_contracts.py` (36); suite total 435 OK, both
  smokes PASS, docs and complexity gates PASS.

- **Distribution rename: DONE.** The published package identity is
  `skill-control-plane`; imports remain `skillsmgr`, the CLI remains
  `skills-mgr`, the repository remains `udayvarmora07/skills-manager`, and
  internal `skills-manager` data/database names are unchanged. Trusted-publisher
  release references and artifact fixtures use the new distribution identity;
  historical notes are retained.

- **L2 ZIP import: DONE.** `Store.import_` accepts ZIP or tar content (sniffed),
  applies the shared budgets (`archive.py`), rejects symlink-bit/disallowed
  members, extracts only to contained staging paths, and reuses the staged
  commit pipeline. REST `PUT /api/import` accepts `.zip`. No new CLI command,
  schema change, or dependency. Hardened after an adversarial audit: per-member
  compression-ratio budget, a failed staging copy can no longer delete the
  existing skill, `--full` trash/templates install as one rolled-back
  transaction with index reconciliation, and manifest `full`/metadata types are
  validated before mutation. 315 unittest green (2026-09-10).
- **L6 release: PUBLISHED SUCCESSFULLY (2026-09-10).** The
  `skill-control-plane` 1.0.1 release completed through TestPyPI, PyPI, GitHub
  Release, provenance attestation, and post-publish install/CRUD verification.
  Imports, CLI, and internal data/database names remain unchanged. This
  worktree performs no publish, tag, or push action.
- CI portability defects (Windows glob, macOS resolved-path expectation, Chrome
  DevTools port discovery) are fixed in this round; dated milestones below are
  historical records and are not rewritten.


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
- [x] Resolve the two reviewed historical worktrees without wholesale merging:
  archive their exact tips as local tags, remove their clean worktrees and local
  branches, and preserve the three dirty/active historical worktrees.

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

## Milestone 48 — Registry bridge (offline) + eval harness (file-based), 2026-09-10

Decision record: @docs/ADR-003-registry-bridge-and-eval-harness.md. No new CLI
command, no new `Store` method, no schema change, no network access, and no
runtime dependency: both items extend existing surfaces only.

- [x] `insights.registry_reference()` parses a registry reference offline (`owner/repo`, `owner/repo/slug`, `https://skills.sh/{source}/{slug}`, `https://github.com/owner/repo`), length-caps and validates every segment, and rejects traversal, separators, absolute paths, and non-registry hosts.
- [x] `insights.registry_bridge_plan()` maps a skill id onto the exact `npx skills add … -s <slug>` command, keeps the explicit-trust gate (`blockers`, `may_install`), surfaces the linkable `/security/{provider}` audit pages, and carries the `content_hash` slot for change detection.
- [x] `insights.install_argv()`/`install_command_line()` became the single renderer behind the printed dry-run text, the executed argv, and the bridge plan; `install_command_for_display()` delegates to it and one test pins the historical output.
- [x] Surfaces: `install --preview [--trust-confirmed] [--registry-hash HEX]` and `POST /api/install {preview: true, …}`; `install` behavior, the runner allowlist, dry-run-first, and the REST legacy payload shape are unchanged.
- [x] `skillsmgr/evals.py` implements the official file contract: `evals/evals.json` cases (optional `slug`/`assertions`), `iteration-N/eval-<slug>/{with_skill,without_skill}/{outputs/output.txt,grading.json,timing.json}`, and a per-iteration `benchmark.json` with per-variant case pass rates and the `with_skill` − `without_skill` delta.
- [x] Deterministic assertion subset only (`equals`, `contains`, `not_contains`, `regex`, `is_json`); a case without assertions is recorded `graded: false` instead of passing or failing; bounds on cases, file size, case text, output length, run count, pattern length, and regex input.
- [x] Surfaces: `validate --evals` (read-only report), `validate --evals-run FILE` (explicit recording, single target), `--workspace DIR` (CLI-only), and `POST /api/validate {evals: true}` / `{runs: […], iteration?}` with the historical read-only response shape preserved when neither is sent.
- [x] Workspaces default to `<data>/evals/<name>-workspace` (outside `skills/`, so scans, `doctor` orphans, exports, and the index never see run data); with `--path` the beside-the-skill layout is used only when the directory is outside the store's `skills/` tree, otherwise it falls back to the store workspace; recording writes atomically and never touches skill files or SQLite.
- [x] Advisory by construction: eval findings never change `valid` or the exit code, scores never gate installs or edits, and no registry value is cached or fetched.
- [x] Tests: `tests/test_registry_bridge_contracts.py` (21) and `tests/test_eval_harness_contracts.py` (38), including a no-network-import pin and no-mutation assertions.
- [x] Verify: compile PASS, **376 unittest PASS**, both smokes PASS, `node --check` PASS, `check_docs.py` PASS, `check_complexity.py` PASS (159 functions), CLI help PASS, `git diff --check` PASS.
- [!] Still open on both items and requiring their own ADR: registry browse/fetch, caching, auth, and provenance persistence (#3); eval provider abstraction, credentials, isolation, and persisted cross-machine results (#4).

## Milestone 5 — Proposed ideas (research verdicts 2026-09-09, see Milestone 31)

- [!] Native window wrapper (pywebview/Electron) — verdict: REJECT as a product direction; browser stays canonical. At most an unbundled loopback-only launcher, never a shipped dependency.
- [x] Skill-body editor has an escaped live markdown preview; no renderer dependency added.
- [x] Keyboard-shortcut cheatsheet modal (`?` key) added after the keyboard contract.
- [!] Pytest suite is not planned: `tests/` uses the approved stdlib `unittest` suite; adding third-party test tooling would require an explicit tooling decision
- [x] CI workflow (compile + unittest + smokes on push) is present in `.github/workflows/ci.yml`; future CI expansion remains tracked in the roadmap
- [x] Zip-import support, approved 2026-09-10: extended `import` only with a
  shared bounded ZIP preflight, explicit contained-path extractor, symlink-bit
  rejection, staged commit/hash verification, and malicious-ZIP regressions. No
  new command or runtime dependency was added.
- [!] Tar-fallback refusal on Python < 3.12 — verdict: REJECT (keep feature-detect + guarded manual extractor; refusal breaks supported 3.10/3.11 for zero fail-closed gain). Record on issue #6.
- [!] Out-of-root link warning → validation error — verdict: REJECT strict promotion (keep warning + `risk_scan()`; 200-target probe found 0 real escapes). Record on issue #7.

## Milestone 12 — Archive resource, manifest, and commit safety (2026-09-08)

- [x] Add compressed-size, expanded-size, per-member-size, member-count,
  path-length, nesting-depth, and compression-ratio limits to tar preflight.
- [x] Validate the `skills-mgr` manifest app/version/timestamp contract,
  canonical unique names, manifest-to-path alignment, and extracted
  frontmatter names before any destination mutation.
- [x] Preserve canonical manifestless fallback validation and support ZIP
  archives by content sniffing; both tar and ZIP formats use the shared
  preflight/validation/commit pipeline.
- [x] Stage each skill commit, restore the prior destination on replacement
  failure, clean failed new destinations, and report completed/failed skills
  explicitly in `imported`/`skipped`.
- [x] Add hermetic regressions for archive budgets, strict manifests, ZIP
  traversal/absolute/backslash/drive/symlink/duplicate cases, frontmatter/name
  mismatch, forced-destination preservation, and injected per-skill copy
  failures.
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
- [x] **HISTORICAL/SUPERSEDED pre-publish record:** Qualified PyPI claims before publication: badge removed, README stated PyPI was a future release with source/CI-artifact install paths; classifiers extended to 3.13/3.14 to match the tested matrix. The README now records the successful 1.0.1 publication.
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

## Milestone 48 — Final-verdict loop-engineering round (2026-09-10, FINAL per maintainer authorization)

Method: 4 hermetic re-probe agents (archive ZIP/TAR; parser/search/links;
REST/effective/insights; release/docs/worktrees/encoding/signing/atomicity —
stdlib only, `/tmp` probes, zero product-code changes) + 8-family survey
workflow (309 quoted URL entries, 194 unique sources) + 3 targeted
`web_search` batches. Baseline held green (301 unittest, both smokes,
compile, frontend, docs, complexity, diff).

- [x] F1 archive re-probes (Python 3.12.3, `data_filter` present): ZIP
  rejected cleanly (`StoreError`, `store.py:1221`, no destination);
  `zipfile` preserves all hostile names verbatim + dupes + symlink-bit
  (`(external_attr>>16)&0o170000==0o120000`); tar `validate_members`
  9/9 hostile rejections (`archive.py:50`); budgets exact (200 ok/201
  reject, path 512/513, nesting 16/17, 9MB member, 40000:1 ratio;
  `archive.py:20-26`); feature-detect `archive.py:131-153`.
- [x] F2 parser/search/link re-probes: dup/huge/400-deep/2000-deep all
  clean `FrontmatterError`, never `RecursionError`; >10 stars/>200 chars
  instant `ValueError` (worst valid 11ms); link matrix exact
  (`validator.py:323-360` warning-only); walk: `~/.agents` 55/0,
  `~/.claude` + `~/.codex` 34 legitimate out-of-root each (sibling-skill
  refs, not escapes) + regex artifacts documented.
- [x] F3 REST/effective/insights re-probes: x-origin purge 403 + trash kept,
  bad/missing CT 415, bad install 400, long query 400, same-origin
  201/200, 5 headers live; `consumer_view`/`effective_state` unresolved,
  10 `risk_scan` findings hostile / 0 clean, registry trust gate,
  eval advisory-only, bundle deferred; tree-hash zero-mutation proven;
  no network/backend/extension/signing code (`urllib` parse-only);
  CWD-dependent project scopes + `SCHEMA_VERSION = "1"` frozen.
- [x] F4 release/docs/worktree/encoding/signing/atomicity re-probes:
  versions/tag `1.0.0` aligned, release gate present, PyPI 404, UNAVAILABLE
  branch code-real; **HISTORICAL/SUPERSEDED: `dist/` wheel stale (missing `domain.js`,
  `--dist-dir` FAILs — rebuild from clean tree before release)**; docs
  truth all green (CLI 27+7+3=37, insights 57); **worktrees: 3 merged-but-stale
  + 2 genuinely unmerged** (via `merge-base`); **#13 confirmed**
  (`loader.py:31` raw escape breaks store-wide scans; validator catches);
  HMAC ok / `ed25519` absent; atomic writes + newest-5 snapshots green.
- [x] F5 survey synthesis: registry DEFER (ToxicSkills 13.4% critical);
  eval ADVISORY-ONLY (promptfoo + judge-bias lit); ZIP APPROVE (PEP 706
  has no zip equivalent — manual validation mandatory); tar-refusal REJECT
  (CVE-2025-4138 bypasses filters); link REJECT (68 legit layouts +
  warn-precedent); extension SEPARATE; wrapper REJECT; signing DEFER
  (NIST non-repudiation gap + threshold=0 flaw).
- [x] F6 verdicts recorded FINAL in `TODO.md` (header + M4 ×2 + Deferred
  ×8 + L6), `PLAN.md` (§9 + §11), this milestone, and progress log; full
  ladder re-run green (recorded in progress log).
- [x] Standing order: L2 ZIP is the only code item (needs approval #5);
  issue #12 diagnostic next (needs approval); REJECT items (#6/#7/#9)
  ready to close with evidence; DEFER items (#3/#4/#8/#11) untouched;
  L6 gate holds with one pre-release fix (rebuild `dist/`).

## Milestone 49 — Approval-safe verification campaign, round 17 (2026-09-10, 10 tasks)

Goal: execute the latest `TODO.md`/`PLAN.md` queue without crossing locked
constraints. This round made no product-code, schema, dependency, release, or
live-user-data changes. ZIP support and the effective-resolution diagnostic
remain approval-gated; the release gate remains intentionally unfulfilled until
an authorized clean build/publish.

- [x] T1 baseline ladder: 301 `unittest` tests, both smoke suites, compile,
  frontend syntax, docs, complexity, diff, and CLI help all passed.
- [x] T2 skills catalog: 62 installed skills audited; `find-skills` and
  `first-principles-production-engineering` were loaded; no new skill installed
  because the stdlib-only and hermetic-workflow constraints need no dependency.
- [x] T3 P0 rotation: P0-001 traversal victim survived; P0-002 hostile-origin
  purge returned 403 and preserved trash; P0-003 hostile archive was rejected
  before destination creation; P0-004 wildcard complexity was bounded; and
  P0-005 deep flow input returned `FrontmatterError`, never raw recursion.
- [x] T4 issue #13 characterization: an invalid UTF-8 `SKILL.md` still causes
  raw `UnicodeDecodeError` in `scan_dir`, `Store.list`, `doctor`, and `resync`,
  while validator handling remains clean. No fix was applied because the issue
  is an explicit behavior decision and approval is unavailable.
- [x] T5 L6 hygiene: package/`__version__`/`v1.0.0` remain aligned; the existing
  release workflow has build-once, exact-artifact, attestation, TestPyPI,
  protected-release, and GitHub Release gates; the stale local wheel still
  fails `check_package_data.py --dist-dir` for missing `domain.js`, so no publish
  or version/tag action was taken.
- [x] T6 REST matrix: hostile Origin, Referer, Fetch Metadata, and Host were
  rejected with 403; missing JSON content type returned 415; malformed install
  input and overlong search returned 400; same-origin create returned 201; all
  five defensive response headers were present.
- [x] T7 resource bounds: archive member-count/path/nesting limits, parser
  deep/large-document limits, and search length/star limits rejected or returned
  clean bounded errors through their public seams.
- [x] T8 CLI contracts: fresh-data create/list/search/doctor/remove paths worked;
  missing skills, invalid names, missing restore targets, and invalid token
  windows returned clean nonzero results without tracebacks.
- [x] T9 browser/live seam: `browser_harness.py` passed all five viewports with
  zero errors and no overflow; a fresh temporary Store served one live skill
  through a loopback `WebAppServer`.
- [x] T10 docs hygiene and finalization: this milestone and the progress log
  record exact evidence; only the four intended documentation files were
  committed and pushed; the final ladder and Git status/diff review passed.

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

## Milestone 35 — Recovery/contract re-verification campaign, round 4 (2026-09-09, 15 tasks)

Hermetic probes (stdlib only, `/tmp` scripts, no product-code changes) over recovery + contract surfaces; no locked-constraint changes. L2 ZIP and issue #12 both await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, complexity, diff).
- [x] T2 failure injection (dropped-table edit preserves FS content + stderr-only rollback diagnostic; rebuild heals; row-delete drift flagged then resynced).
- [x] T3 upload bounds (oversize/bad Content-Length → 400; 250-part multipart → 400; valid folder PUT → 200).
- [x] T4 history clamp (limit 5/0/huge/missing) + stats shape + tokens estimate/aggregate + long-search `ValueError`.
- [x] T5 backup/restore hash-verified (`content_hash` + file bytes equal, not row counts) + template dup/bad-name guards.
- [x] T6 doctor drift (`.skillsmgr-tmp` + `.skillsmgr-stage` leftovers flagged; orphan dir flagged then resynced; stale snapshot flagged).
- [x] T7 two-data-dir CLI isolation (each dir finds only its own skill) + REST two-server contracts (11 search tests incl. isolation, all OK).
- [x] T8 REST isolation suite green (same 11-test run covers global/agent/merged + two-server cases).
- [x] T9 concurrent same-skill writes (4×25 zero errors, doctor clean, no stranded temps, 101 history rows).
- [x] T10 insights E2E (views/diff/ownership/preview/quarantine-stage-only/risk/registry-trust/eval-1-1/bundle-deferred + store purity).
- [x] T11 browser harness `"passed": true` file-verified (5 viewports, zero failures; `tail`-pipe artifact explained — JSON split across streams).
- [x] T12 fresh-tmp live seam (create→validate→doctor→remove→purge→doctor, all OK).
- [x] T13 docs hygiene (this milestone + progress-log entries; no backlog wording changes needed).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 36 — CI/contracts/migration re-verification campaign, round 5 (2026-09-09, 15 tasks)

Hermetic probes (stdlib only, `/tmp` scripts, no product-code changes) over CI/release structure, docs/frontend/security contracts, migration, snapshots, and process concurrency; no locked-constraint changes. L2 ZIP and issue #12 both await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest after one flaky concurrency rerun, docs, complexity, diff; 9 issues OPEN).
- [x] T2 CI/release audit (unit 3.10–3.14 + adversarial/package/docs/xplat-3OS/browser jobs; `contents:read`; build-once + `--dist-dir`; release tag-gate + attest + TestPyPI→`release` + GitHub Release + post-publish verify).
- [x] T3 package-data offline (exact-accept wheel+sdist, vue-missing reject, `--require-build` exit 2).
- [x] T4 docs deep-links (all `@docs/` resolve; module paths exist; `Store.*` methods exist).
- [x] T5 frontend wiring (9 domain exports, 19 menuDo actions dispatched, `/` `?` Esc + focus-trap, 13 modals `role=dialog`).
- [x] T6 live security headers (CSP/`frame-ancestors 'none'`/nosniff/referrer/CORP/Cache-Control on `/`, `/api/*`, `/app.js`).
- [x] T7 threat-model/ADR file:line refs (all resolve to real files + in-range lines).
- [x] T8 complexity baseline (151 functions, budget ≤ 15, gate exit 0; no drift).
- [x] T9 full migration (skip-by-default respected; `--full --force` restores skills + trash + templates).
- [x] T10 snapshot retention (7 edits → newest 5 kept; byte-accurate `--snapshot` restore).
- [x] T11 cross-process CLI (2 procs × 10 edits rc 0; doctor consistent).
- [x] T12 version alignment (`1.0.0` everywhere) + gitignore (`dist/`, egg-info, pycache ignored).
- [x] T13 harness `"passed": true` (5 viewports, exit 0) + fresh-tmp live seam OK.
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 37 — P0 acceptance-gate re-verification, round 6 (2026-09-09, 15 tasks)

Direct replay of the five Milestone 1 acceptance reproductions on current `main` (hermetic `/tmp` scripts, no product-code changes) + red-first proof + compatibility + protocol self-audit; no locked-constraint changes. L2 ZIP and issue #12 both await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, diff; P0 regression tests inventoried: path-safety, webapp x-origin, archive traversal, frontmatter bounds, search bounds).
- [x] T2 P0-SEC-001 replay (get/edit/remove/disable/enable `../../victim` all rejected; victim + sentinel survive).
- [x] T3 P0-SEC-002 replay (x-origin purge → 403, trash preserved; same-origin purge → 200).
- [x] T4 P0-SEC-003 replay (`skills/weird name` manifestless import rejected; no destination created).
- [x] T5 P0-SEC-004 replay (201-char alternating wildcard → clean `ValueError`, instant).
- [x] T6 P0-SEC-005 replay (400-deep block + 2000-deep flow → clean `FrontmatterError`, never raw `RecursionError`).
- [x] T7 red-first proof (copied tree: `NAME_RE=^.*$` → traversal test RED; archive guard `if False` → traversal test RED).
- [x] T8 guard centralization (`validator.validate_skill_name` + `path_safety.contained_path`/`safe_skill_path`; 61 call-sites; REST decodes-then-guards per `webapp.py:198-200`).
- [x] T9 alternate surfaces (CLI view/edit/remove/disable/enable/restore + REST `%2e%2e` forms + scopes — all rejected).
- [x] T10 valid compatibility (64-char/boundary names, disable/enable `0`, plain + `my-*` search, Agent Skills extensions, export→import round-trip).
- [x] T11 protocol self-audit (12/12 steps evidenced in this round; see progress log).
- [x] T12 harness `"passed": true` (5 viewports, exit 0) + fresh-tmp live seam OK.
- [x] T13 docs hygiene (this milestone + progress-log entries).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 38 — Module-seam + backlog-truth campaign, round 7 (2026-09-09, 15 tasks)

Hermetic probes (stdlib only, `/tmp` scripts, no product-code changes) over loader/observations/roots/tokens/templates/web/sync/ranking/diagnostics + stale-note refresh; no locked-constraint changes. L2 ZIP and issue #12 both await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, diff).
- [x] T2 loader edges (good/badfm/dupkey/disabled/noload all exact; latin-1 behavior recorded — see T2b note in log).
- [x] T3 observations (stable 64-char hashes, portable/extension split, observed_at/provenance, body-sensitive).
- [x] T4 root discovery (dup `duplicated`+`divergent`, `unresolved`, skip-without-force, dup-root single-touch).
- [x] T5 tokens (windows/estimate/aggregate shapes) + templates (dup/bad-name guards; 100-char names valid by rule).
- [x] T6 web serialization (object/array/415/malformed) + install allowlist (injection/runner/types rejected, dry-run 200).
- [x] T7 sync semantics (skip-without-force, force-converge, dup-root single-touch, bad-name rejected).
- [x] T8 ranking (exact 100 first, shuffle-deterministic, body-match 40, 50× stable).
- [x] T9 diagnostics (stderr-only, `None` return, context preserved).
- [x] T10 TODO M4 note refreshed (`[?]`s closed in v1.1.0; issue #12 filed; gate PASS).
- [x] T11 PLAN §13 rewritten as completed audit trail + `CIE`→`CI` typo (gate PASS).
- [x] T12 harness `"passed": true` (5 viewports, exit 0) + fresh-tmp live seam OK.
- [x] T13 docs hygiene (this milestone + progress-log entries incl. T2b finding).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 39 — Trust-surface + docs-contract campaign, round 8 (2026-09-09, 15 tasks)

Hermetic probes (stdlib only, `/tmp` scripts, no product-code changes) over locked constraints, secrets, README/CONTRIBUTING verbatim, roadmap verdicts, CLI/REST error shapes, XSS, REST/Store doc coverage, git hygiene; no locked-constraint changes. L2 ZIP and issue #12 both await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, diff).
- [x] T2 locked constraints (no ORM import; schema `1`; stdlib-only with optional-guarded tiktoken; loopback + vendored Vue + no CDN; commands preserved across the `cli.py`→`cli_parser.py` split).
- [x] T3 secrets scan (98 tracked files; no keys/tokens/private-keys; no world-writable; `.autogit` untracked-ignored).
- [x] T4 README quickstart verbatim E2E (list/create/search/tokens/validate/export/install-dry-run all rc 0 on fresh tmp).
- [x] T5 CONTRIBUTING checklist (compile/complexity/docs/package-UNAVAILABLE/init/create all green).
- [x] T6 roadmap verdicts wired (v1.2+ six lines + `pywebview` line now quote their research verdicts; gate PASS).
- [x] T7 CLI UX (26/26 `--help` rc 0; bad-command exit 2; invalid names exit 1 with clean message; no traceback on `SkillNotFound`).
- [x] T8 REST errors (8/8 JSON `{error}`, no `Traceback`: 404/400 shapes + form-415).
- [x] T9 XSS audit (`esc()` full entity map; 2 `v-html` sinks both via `renderMarkdown`; no `innerHTML`; `rel=noopener`; no `javascript:`).
- [x] T10 REST table audit (skills/search/maintenance/trash/templates/import-export rows verified; no phantom `/api/tokens` or `/api/db` routes — tokens ride `stats`/`scopes`, maintenance is `/api/rebuild`+`/api/resync`).
- [x] T11 Store API audit (every documented `Store.*` exists in source).
- [x] T12 git hygiene (only `ROADMAP.md` modified + ignored `.autogit`; no large files; `dist/`/egg-info ignored).
- [x] T13 harness `"passed": true` on rerun (first run: one `net::ERR_ABORTED` at 320px + server `BrokenPipeError` — probe-race flake, zero console errors) + fresh-tmp live seam OK.
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 40 — Steady-state verification, round 9 (2026-09-09, 15 tasks)

Hermetic spot-probes (stdlib only, `/tmp` scripts, no product-code changes) confirming the steady state holds; no locked-constraint changes. L2 ZIP and issue #12 both await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, complexity, diff).
- [x] T2 L2/L6 still gated (issues #5 + #12 OPEN, zero comments; ZIP rejection-only, no `ZipFile` extraction).
- [x] T3 deferred #3/#4/#8/#11 untouched (all OPEN zero comments).
- [x] T4 P0 spot (001 traversal rejected + victim survives; 002 x-origin 403).
- [x] T5 archive (ZIP reject with reason; valid versioned-manifest tar round-trips `['ok']`).
- [x] T6 search/validator (alternating wildcard clean `ValueError`; escape warns, `https` clean).
- [x] T7 release dry-run (`1.0.0` aligned, no bump/tag/publish; PyPI still 404; package-data UNAVAILABLE).
- [x] T8 docs gates (docs/complexity PASS; package-data honest UNAVAILABLE).
- [x] T9 CLI isolation (each data-dir finds only its own; exit 1 missing / 2 usage).
- [x] T10 REST fail-closed (purge 403 + trash preserved; form 415; bad install 400 JSON; long query 400).
- [x] T11 hygiene (versions aligned; `dist/` ignored; 5 worktrees unmerged as documented; tree clean but `.autogit`).
- [x] T12 harness `"passed": true` (5 viewports, exit 0) + fresh-tmp live seam OK.
- [x] T13 docs hygiene (this milestone + progress-log entry).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 41 — Support-module + finding-filing campaign, round 10 (2026-09-09, 15 tasks)

Hermetic probes (stdlib only, inline heredocs, no product-code changes) over colors/cli_output/history/web-static/path_safety/validator/frontmatter/atomic_io/insights-trust + T2b filed as issue #13; no locked-constraint changes. L2 ZIP and issues #12/#13 await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, diff).
- [x] T2 T2b encoding finding filed as issue #13 (repro + smallest-fix sketch + scope questions; no code).
- [x] T3 colors (`Colors.paint`, NO_COLOR/FORCE_COLOR, empty-text, helpers).
- [x] T4 `cli_output` (`render_table` list-of-lists + header bold, `truncate`, `print_json`, `err` to stderr).
- [x] T5 history/stats (limit clamp/0/missing; total/active/disabled/trashed counts).
- [x] T6 web static (`/`, `/app.js`, vendored Vue) + raw (`text/plain`, scope-404, traversal-404).
- [x] T7 `path_safety` (`\`/drive/`..`/absolute rejected on POSIX; valid composes under root).
- [x] T8 validator (valid/use-context/token-over-5000/name-mismatch contracts).
- [x] T9 frontmatter dump (quote/nested round-trips; flow-mapping `TypeError` scoped to bracket lists; dup-key loud).
- [x] T10 `atomic_io` (write/replace, no stranded temps, deterministic + sensitive tree hash, lock context).
- [x] T11 insights trust gates (quarantine `stage-only`/`activated:false`, blank/non-string rejected; registry trust gate both ways; JSON-clean).
- [x] T12 harness `"passed": true` (5 viewports, exit 0) + fresh-tmp live seam OK.
- [x] T13 docs hygiene (this milestone + progress-log entry).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 42 — Frontend-contract + steady-state campaign, round 11 (2026-09-09, 15 tasks)

Hermetic probes (stdlib only, inline heredocs, no product-code changes) over CSS/a11y/viewports/counts/claims/gating/P0-spots/protocol; no locked-constraint changes. L2 ZIP and issues #12/#13 await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, diff).
- [x] T2 issues #5/#12/#13 + #3/#4/#8/#11 + #6/#7/#9 all still OPEN (rejections carry 1 comment each).
- [x] T3 T2b encoding repro unchanged (raw `UnicodeDecodeError`; issue #13 stands).
- [x] T4 CSS (900/640 stacked-layout/topbar rules + 380/420/780 component caps; `prefers-reduced-motion`; `overflow-x`; focus styles; 3 `@media` blocks).
- [x] T5 a11y (13 labelled dialogs, `aria-modal`, live region, `sr-only`, `kbd`, Esc + focus trap, `inert`).
- [x] T6 viewports (5/5 no overflow, zero errors, exit 0).
- [x] T7 counts (insights 57, CLI 27+7+3=37 re-derived from AST).
- [x] T8 PyPI still 404; README future-release claim accurate.
- [x] T9 deferred untouched (zero comments each).
- [x] T10 P0 spots (001 victim survives; 002 purge 403 + trash kept).
- [x] T11 protocol compliance (12-step checklist lives in `TODO.md`; rounds evidence each step).
- [x] T12 harness green + fresh-tmp live seam OK.
- [x] T13 docs hygiene (this milestone + progress-log entry).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 43 — CLI-surface behavior campaign, round 12 (2026-09-09, 15 tasks)

Hermetic CLI-behavior probes (fresh `$SKILLS_MANAGER_DATA` per probe, no product-code changes) over history/trash/states/edit/scopes/sync/tokens/validate/templates/db; no locked-constraint changes. L2 ZIP and issues #12/#13 await approval — no code until then. (Live-`~/.agents` note: one R12-T7 probe wrote `sy-1` to the real agents scope; removed immediately after, verified clean.)

- [x] T1 baseline ladder green (301 unittest, docs, diff).
- [x] T2 history (create+edit story, `--limit`, `--json` rows, missing → empty, `doctor --json ok`).
- [x] T3 trash (list/restore/purge cycle; double-remove honest error; purge empties; doctor consistent).
- [x] T4 states (disable→`disabled`, re-disable honest error; enable→`active`, re-enable honest error; JSON `disabled: 0`).
- [x] T5 edit (description-only keeps category; body-only keeps description; `--metadata` accepted; missing → clean error).
- [x] T6 scopes (7 ids incl. `cursor`; missing `~/.cursor/skills` → clean empty, documented in `03-cli-surface`; bogus scope → clean error).
- [x] T7 sync (`--from/--to/--force/--json`; skip-without-force message; force converges).
- [x] T8 tokens (skill/text/scope/window shapes; bad window lists choices cleanly).
- [x] T9 validate (name/all/external-`--path`/json/missing contracts; `--path` takes an external skill dir).
- [x] T10 templates (empty hint, `new`, list, dup `FileExistsError` as clean error).
- [x] T11 db (`rebuild` added-counts; `resync` complete-counts).
- [x] T12 harness `"passed": true` (5 viewports, exit 0) + fresh-tmp live seam OK.
- [x] T13 docs hygiene (this milestone + progress-log entry).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 44 — Remaining-CLI + frontend-seam campaign, round 13 (2026-09-09, 15 tasks)

Hermetic probes (fresh tmp envs, no product-code changes) over add/view/create/list/search/install/export-open/snapshots/domain.js; no locked-constraint changes. L2 ZIP and issues #12/#13 await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, diff) + issues #5/#12/#13 OPEN.
- [x] T2 gating re-confirmed (zero comments; ZIP rejection-only).
- [x] T3 add (existing dir, `--name` requires frontmatter rename first, missing-dir + bad-name clean errors).
- [x] T4 view (`--raw` round-trips body; `--json` 17-key record incl. hashes/provenance).
- [x] T5 create (`--body-file`, `--allowed-tools`, `--license/--category/--version`; dup clean error).
- [x] T6 list (`--disabled`, `--category`, `--json` shapes) + search (`--limit`, `--json` hits).
- [x] T7 scopes note (7 ids; `cursor` clean-empty) — see round 12.
- [x] T8 install (dry-run default print vs `--dry-run` bare command; `../evil` passes char-allowlist — runner allowlist + dry-run-first is the control; bad runner clean error).
- [x] T9 export/backup alias (both write tarballs) + `open` (`EDITOR=true` resyncs; missing → clean error).
- [x] T10 snapshots (`history --json` ids; `--snapshot` byte-accurate rollback; bogus id clean error).
- [x] T11 `domain.js` via browser-global seam (compat/tools enrichment, `1.5k`, `rel=noopener` strong/link render).
- [x] T12 harness `"passed": true` on rerun (first run: one `net::ERR_ABORTED` at 1280px + `BrokenPipeError` — probe-race flake, zero console errors) + fresh-tmp live seam OK.
- [x] T13 docs hygiene (this milestone + progress-log entry).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 45 — Global-flags + lifecycle-defaults campaign, round 14 (2026-09-09, 15 tasks)

Hermetic probes (fresh tmp envs incl. isolated `HOME` for scope tests, no product-code changes) over init/webui/globals/version/remove/sync-defaults/JSON-shapes/name-errors/smoke-idempotence; no locked-constraint changes. L2 ZIP and issues #12/#13 await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, diff) + issues #5/#12/#13 OPEN.
- [x] T2 gating re-confirmed (zero comments; ZIP rejection-only).
- [x] T3 init (layout skills/db/templates/backups/trash; idempotent re-init).
- [x] T4 webui (`--host/--port/--no-browser` flags; `gui` alias shares help).
- [x] T5 globals (`--data-dir` creates alt root; `--color/--no-color` accepted).
- [x] T6 version (`skills-mgr 1.0.0`, `prog="skills-mgr"`).
- [x] T7 remove (default trash with hint; `--purge` deletes; `--trash` explicit; missing-restore clean error).
- [x] T8 sync defaults (isolated `HOME`: `(none)` targets + clean message; no live-scope writes this round).
- [x] T9 JSON parity (list/view-17/search/doctor-15/stats/history shapes all parse).
- [x] T10 name errors (uniform `must match` message; `-lead` hits argparse option parsing — CLI convention, not a bug).
- [x] T11 smokes idempotent (store + web PASS twice in a row).
- [x] T12 harness `"passed": true` (5 viewports, exit 0) + fresh-tmp live seam OK.
- [x] T13 docs hygiene (this milestone + progress-log entry).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 46 — Skills-catalog + encoding-deep-dive + bounds-rotation campaign, round 15 (2026-09-09, 15 tasks)

Hermetic probes (stdlib only, inline heredocs, no product-code changes) covering the goal's skill requirements plus bound-family rotation; no locked-constraint changes. L2 ZIP and issues #12/#13 await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, complexity, diff).
- [x] T2 catalog audit (62 `~/.agents/skills`, incl. `sy-1` probe residue already cleaned round 12) + `first-principles-production-engineering` loaded and applied (smallest-change, verification-before-claims, root-cause loops).
- [x] T3 `find-skills` loaded; decision: no install — stdlib-only constraint + hermetic-probe workflow need no ecosystem skill; recorded here.
- [x] T4 T2b deep-dive (26 `read_text` sites classified; only archive/validator catch decode; user-visible is fail-closed exit-1/JSON-error; finding commented on issue #13 with fix options).
- [x] T5 P0 rotation (003 rejected + no dest; 004 bounded `ValueError`; 005 block+flow `FrontmatterError`).
- [x] T6 archive budgets (member-count 201, nesting 20, path-length 520 — all rejected).
- [x] T7 parser limits (keys/scalar bounded; deep-nest + huge-doc parsed without crash).
- [x] T8 search timing (6 adversarial patterns ≤ 184ms or clean `ValueError`).
- [x] T9 REST matrix (Host/Fetch/Referer/Origin → 403; 5 security headers live).
- [x] T10 CLI contracts (8 missing-skill + 3 invalid-name paths: rc 1, clean messages, zero tracebacks).
- [x] T11 docs truth (gates PASS; insights 57; CLI 27+7+3=37; versions `1.0.0`).
- [x] T12 harness `"passed": true` (5 viewports, exit 0) + fresh-tmp live seam OK.
- [x] T13 docs hygiene (this milestone + progress-log entry).
- [x] T14 clean diff review, commit, and push of exactly the intended files.
- [x] T15 final ladder re-run + evidence (recorded in progress log).

## Milestone 47 — Suite-health + stability campaign, round 16 (2026-09-09, 15 tasks)

Hermetic probes (stdlib only, inline heredocs, no product-code changes) over suite stability, gate coverage, workflows, hygiene, and P0 rotation; no locked-constraint changes. L2 ZIP and issues #12/#13 await approval — no code until then.

- [x] T1 baseline ladder green (301 unittest, docs, complexity, diff).
- [x] T2 gating re-confirmed (#5 OPEN 0 comments; #13 OPEN 1 deep-dive comment; ZIP rejection-only).
- [x] T3 concurrency file 5/5 green (no flake this round; round-5 single slow-join noted as scheduling).
- [x] T4 full suite 2/2 green back-to-back (18.2s + 18.4s).
- [x] T5 suite health (0 skips; 301 counted; per-file table recorded; `-v` shows 300 `ok` + 1 diagnostic-print line, not a skip).
- [x] T6 gate coverage (`CURRENT_DOCS` pins v1.1.0 discovery + v0.3.0 context; round milestones live in `task.md`/progress-log by design).
- [x] T7 workflows (ci: unit/adversarial/package/docs/xplat/browser; release: build/verify/attest/testpypi/pypi/github-release; CI contracts 20/20).
- [x] T8 tracked-junk zero (`dist/`/egg-info/pycache/`.pyc` untracked).
- [x] T9 deferred untouched (zero comments each) + PyPI still 404.
- [x] T10 P0 rotation (003 rejected + no dest; 004 bounded; 005 flow `FrontmatterError`).
- [x] T11 compliance (AGENTS.md ALWAYS + 12-step protocol present; rounds evidence each step).
- [x] T12 harness `"passed": true` (5 viewports, exit 0) + fresh-tmp live seam OK.
- [x] T13 docs hygiene (this milestone + progress-log entry).
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

## Milestone 50 — GitHub issue close-out (#3, #4, #5, #12, #13) (2026-09-11, 12 tasks)

Delivered against the five maintainer-selected issues with `gh` as the surface:
one real bug fix, one approved read-only diagnostic, and three already-built
items verified end to end before closing. No locked constraint changed.

- [x] T1 baseline ladder green before any edit (376 unittest, both smokes, docs, complexity).
- [x] T2 #13 red-first: 20 failing assertions reproducing the raw `UnicodeDecodeError` contract gap (scan_dir/resync/doctor/list + write paths).
- [x] T3 #13 fix: `loader.read_skill_text()`/`read_skill_text_strict()`; rows marked `malformed` + `decode_error`; `doctor.undecodable_documents` drift class (in `ok`) + CLI line; `Store.list`/`get` surface the flags; validator reuses the message.
- [x] T4 #13 write paths fail closed (`Store.edit`/`restore`, `read_snapshot`, `scopes.get_raw`/`edit_skill`/`restore_snapshot`/sync overwrite) and leave files byte-identical.
- [x] T5 #13 complexity ratchet: `doctor` artifact discovery extracted into `_doctor_artifacts`/`_stale_snapshots`/`_is_*` so the new drift class adds no hotspot growth.
- [x] T6 #13 tests: `tests/test_encoding_contracts.py` (23) incl. REST list/detail/doctor drift reporting and clean CLI exit codes.
- [x] T7 #3/#4 verification: registry preview (audit links, trust gate, hash slot) and eval harness (`--evals`, `--evals-run` recording `iteration-N/eval-*/` + benchmark delta, no SQLite rows) re-run hermetically, then committed.
- [x] T8 #5 verification: hermetic zip import parity with tar plus a hostile-zip probe (traversal member rejected, nothing outside staging).
- [x] T9 #12 implementation: `skillsmgr/effective.py` (cited per-consumer rows, ordered/no-merge/undocumented policies, skipped disabled-invalid instances, bounded reads) + `doctor --explain` + `GET /api/doctor?explain=`.
- [x] T10 #12 tests: `tests/test_effective_explain_contracts.py` (36) incl. six-way/no-merge/triple+both-load/ambiguous/unknown/missing-project and read-only tree-hash + no-DB proofs.
- [x] T11 docs truth: `docs/01-architecture.md`, `docs/02-modules.md`, `docs/03-cli-surface.md`, `docs/08-web-ui.md`, `docs/06-progress-log.md`, `docs/SESSION-CONTEXT.md`, `ROADMAP.md`, `TODO.md` (Milestone 4 + Milestone 11 L3 + deferred intro), `task.md`.
- [x] T12 final ladder (435 unittest, smokes, docs, complexity, help) then commit, push, and close each issue with file/line evidence.
