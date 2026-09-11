# TODO — Skills Manager World-Class Execution Backlog

**Plan version:** 2.1.0
**Backlog date:** 2026-09-07
**Baseline:** `main` at `667fabb` in `/home/uday-varmora/skills-manager`
**Companion plan:** `/home/uday-varmora/skills-manager/PLAN.md`
**Research annex (2026-09-09):** loop-engineering probes plus a 200+-source
web survey, distilled into per-item verdicts in the Milestone 4 note, the
Deferred section, and the new Milestone 11 queue. Docs-only change: no
code, no locked-constraint changes. New sessions start at Milestone 11.
**Final-verdict round (2026-09-10):** all 14 blockers re-probed hermetically
(4 probe agents, stdlib only, zero product-code changes) and re-surveyed
(8-family workflow, 309 quoted URL entries / 194 unique sources, plus 3
targeted `web_search` batches on skills.sh API, minisign/PEP 740, Agent
Skills spec, pywebview/VS Code/GFS/Unicode, and TUF/Sigstore/CSRF/Claude
precedence). Baseline held green (301 unittest, both smokes, compile,
frontend, docs, complexity, diff). Verdicts below are FINAL per maintainer
authorization — each item now carries a **FINAL:** line with evidence.
**Execution update (2026-09-10):** L2 ZIP import is shipped in the approved
scoped `import` extension and hardened by an adversarial audit round (per-member
ratio budget, staged-commit rollback, transactional full-import restore, index
reconciliation; 315 unittest green). L6 is published successfully: the
`skill-control-plane` 1.0.1 release completed through TestPyPI, PyPI, GitHub
Release, provenance attestation, and post-publish install/CRUD verification.
This worktree only records the completed release; no publish, tag, or push is
performed here.

> This is the canonical execution backlog for the next product cycle. It is
> deliberately risk-first: protect user data and make future regressions
> difficult before adding more visible features.

## How to use this file

- `[ ]` = not started.
- `[/]` = actively being implemented.
- `[x]` = implemented in the current worktree and verified by the required acceptance checks; mark as shipped on `main` only after landing.
- `[!]` = blocked by a decision, external credential, or maintainer approval.
- Every bug fix must begin with a failing reproduction and end with a permanent
  regression test.
- Every behavior change must update the owning documentation plus this file and
  `docs/06-progress-log.md`.
- Anything requiring a new CLI command, new CLI flag, new `Store` method,
  SQLite schema change, runtime dependency, public network bind, or data-model
  change requires an issue/ADR and maintainer approval before implementation.
- Never modify `/home/uday-varmora/skills-manager/.autogit` as part of this work.

## Ground truth at the start of this backlog

### Verified on `main`

- [x] CLI, local web UI, scope support, validation, search, token estimates,
  trash/restore, import/export, history, templates, and rebuild/resync exist.
- [x] The filesystem is intended to be the source of truth; SQLite is intended
  to be a rebuildable index with `SCHEMA_VERSION = "1"`.
- [x] The current baseline passes 47 `unittest` tests, `smoke_store.py`,
  `smoke_web.py`, `node --check skillsmgr/webui/app.js`, and CLI help.
- [x] The repository is published to GitHub with tag `v1.0.0` and green CI.
- [x] PyPI publication is confirmed for `skill-control-plane` 1.0.1 through
  the controlled release workflow; TestPyPI, PyPI, GitHub Release, provenance,
  and post-publish install/CRUD verification all succeeded.
  **HISTORICAL/SUPERSEDED (2026-09-10):** This pre-registration observation
  recorded the then-current PyPI 404 and stale-artifact blocker. It is retained
  as history; the current release state is maintained in L6 below.

### Confirmed defects on `main` — release blockers

- [x] **P0-SEC-001: mutation path traversal fixed 2026-09-08.** Canonical skill
  names and resolved-root containment now guard Store, scope, REST, and CLI
  lookup/mutation paths; regression tests prove an outside victim survives.
- [x] **P0-SEC-002: cross-origin localhost mutation fixed 2026-09-08.** A request with an
  attacker `Origin` successfully called `POST /api/trash/purge` and permanently
  emptied trash. Loopback binding does not by itself prevent browser-to-localhost
  cross-origin requests.
- [x] **P0-SEC-003: invalid manifestless archive names fixed 2026-09-08.** The
  manifestless fallback now applies the canonical name rule and skips invalid
  directories without creating a destination.
- [x] **P0-SEC-004: wildcard search exhaustion fixed 2026-09-08.** A crafted alternating wildcard
  pattern caused `rank_results` to run beyond an eight-second probe timeout.
- [x] **P0-SEC-005: parser recursion failure fixed 2026-09-08.** Deep block and flow frontmatter
  caused raw `RecursionError` instead of a bounded, user-facing
  `FrontmatterError`.

### Important integration facts

- [x] Historical worktree `/home/uday-varmora/skills-manager.worktrees/todo-plan-implementation`
  was reviewed and archived at local tag
  `archive/todo-plan-implementation-2bb7280`; its 2 commits were not merged
  wholesale because their substantive behavior is already present in the
  stronger current `main` implementation.
- [x] Historical worktree `/home/uday-varmora/skills-manager.worktrees/milestone5-research-user-needs`
  was reviewed and archived at local tag
  `archive/milestone5-research-user-needs-c5a7161`; its 1 commit was not merged
  wholesale because its ZIP/UX behavior is already present or superseded on
  current `main`. Both clean worktrees and local branches were removed; the
  remaining three historical worktrees were left untouched because they are
  dirty and/or may still carry active work.
- [x] GitHub issues #1 and #2 are closed as approved design decisions, but their
  code must still be selectively integrated and re-reviewed on `main`.
- [!] `docs/01-architecture.md`, `docs/05-gui-plan.md`,
  `.commandcode/settings.json`, and several historical counters contain stale
  claims. Documentation reconciliation is planned work, not evidence that the
  stale behavior still exists. (2026-09-09 round-2 status: `01-architecture.md`
  repo-map refreshed to the split CLI/web policy modules + `insights.py` +
  harness + fixtures + package-data gate; `05-gui-plan.md` confirmed correctly
  labelled SUPERSEDED/historical with `gui.py`-deleted + alias facts;
  `.commandcode/settings.json` confirmed clean — the `gui.py` compile entry
  was replaced by `skillsmgr/*.py` on 2026-09-08 (`2ae27bf`), remaining hits
  are historical progress-log entries; CLI 27+7+3=37 and insights-57 counts
  corrected in SESSION-CONTEXT/CHANGELOG/task. Historical counters in dated
  evidence/progress entries stay append-only by policy.)
  **FINAL (2026-09-10): docs verified true (arch repo-map, SUPERSEDED label,
  settings.json clean, CLI 27+7+3=37, insights 57) — remaining `[!]` is only
  the append-only historical counters, which stay by policy.**

## Release policy

### Release blockers

No release, PyPI publication, or new feature expansion is allowed while any of
the following remains open:

- P0 security or data-loss defect.
- An unbounded parser, matcher, archive, upload, or filesystem operation.
- A state-changing HTTP route that accepts cross-origin browser traffic.
- A destructive operation without validation and an intentional recovery story.
- A changed interface without CLI, REST, UI, or package-level verification where
  that interface is exposed.
- A source/documentation contradiction in the touched behavior.
- A dirty release tree or artifact that was not the artifact tested in CI.

## Milestone 0 — Baseline, evidence, and integration freeze

**Goal:** establish one authoritative starting point and prevent duplicated or
stale work.

- [x] Capture baseline command output in the dated evidence report
  `docs/09-baseline-evidence-2026-09-07.md`: compile, unit, smoke, frontend
  syntax, help, package build, and Git status. Package build is explicitly
  recorded as blocked because `python3 -m build` is unavailable.
- [x] Record exact current-main behavior for all five P0 reproductions in
  `docs/09-baseline-evidence-2026-09-07.md` before changing product code.
- [x] Compare both unmerged worktrees file-by-file against `main`; record the
  candidate commits, changed files, overlaps, conflicts, and safe replay order
  in `docs/10-worktree-integration-comparison-2026-09-08.md`.
- [x] Build a cherry-pick/replay map: security tests, recovery code, archive
  code, UX code, and docs must be reviewed independently. See
  `docs/11-integration-status-2026-09-08.md`.
- [x] Mark every task as `main`, `worktree-only`, `approved-not-integrated`, or
  `speculative`; do not infer completion from a branch commit. See
  `docs/11-integration-status-2026-09-08.md`.
- [x] Add a pre-merge checklist that rejects stale docs, hidden source changes,
  untracked generated files, and unverified branch-only tests. See
  `docs/PRE-MERGE-CHECKLIST.md`.
- [x] Decide whether `dist/` and `skills_manager.egg-info/` are local artifacts
  or release inputs; record the decision before changing packaging behavior. They
  remain ignored local artifacts, not release inputs.

**Acceptance gate:** baseline is reproducible, all five P0 defects have failing
tests or scripts, and the integration map identifies the smallest safe change
from each worktree.

## Milestone 1 — P0 filesystem, archive, parser, and search safety

**Goal:** make all untrusted names, paths, archive members, and resource costs
fail closed.

### 1A. Centralized names and containment

- [x] Add one authoritative skill-name validation primitive: `validate_skill_name()`.
- [x] Add one root-containment primitive using resolved paths: `contained_path()`
  plus the `safe_skill_path()` composition helper.
- [x] Apply both before every current-main read, write, rename, move, copy,
  restore, export/import destination, and delete operation. Snapshot helpers are
  not present on current `main` and remain a recovery-phase task.
- [x] Apply guards to `Store.get`, `edit`, `remove`, `restore`, `disable`,
  `enable`, `add`, import, export, sync, and all agent-scope equivalents.
- [x] Validate REST path parameters after URL decoding and before path joins.
- [x] Validate CLI names before command handlers construct paths.
- [x] Ensure `--force` cannot turn an invalid destination into a valid delete.
- [x] Ensure trash matching cannot confuse a valid name with a path fragment or
  prefix collision.

### 1B. Archive intake

- [x] Create an archive preflight pipeline separate from mutation: identify
  format, inspect members, validate names/types/paths, extract into a private
  temporary directory, validate contents and resource budgets, then commit.
- [x] Reject absolute paths, `..` components, duplicate members, device files,
  FIFOs, hard links, symlinks, unsupported member types, and unexpected layouts
  unless explicitly supported.
- [x] Feature-detect `tarfile.data_filter`; never silently fall back to
  unfiltered extraction. Older interpreters use the guarded manual extractor.
- [x] Keep independent member validation even when the interpreter provides a
  safe extraction filter.
- [x] Enforce compressed-size, expanded-size, member-count, individual-member,
  path-length, nesting-depth, and compression-ratio limits.
- [x] Validate manifest schema, version, names, paths, and duplicate entries.
- [x] Validate manifestless fallback names with the canonical name rule.
- [x] Decide and document ZIP support (as of 2026-09-10): the approved scoped
  `import` extension now accepts ZIP content after the same bounded preflight
  and guarded manual extraction policy; no new command was added. This replaces
  the original 2026-09-08 baseline decision recorded below.
- [x] Make imports all-or-nothing per skill or clearly report partial commits;
  never leave an unexplained half-imported tree.

### 1C. Parser and resource bounds

- [x] Add document-size, key-count, collection-size, scalar-length, and
  nesting-depth limits to the frontmatter parser.
- [x] Convert recursion-limit failures and malformed flow structures into
  `FrontmatterError`.
- [x] Preserve valid Agent Skills and client-extension frontmatter fixtures.
- [x] Add a deterministic malformed-input corpus.

### 1D. Search resource bounds

- [x] Replace unbounded wildcard-to-regex expansion with a bounded matcher or a
  rigorously constrained translation.
- [x] Collapse repeated `*`, cap pattern length and wildcard complexity, and
  define a clean CLI/REST/UI error.
- [x] Use the same search implementation for global, agent, merged, CLI, and
  REST search paths.
- [x] Add timing-bounded tests for adversarial patterns.

**Acceptance gate:** P0-SEC-001, P0-SEC-003, P0-SEC-004, and P0-SEC-005
reproductions fail safely; valid names, imports, patterns, and frontmatter
remain compatible; no security fallback is silent.

## Milestone 2 — P0 localhost web security

**Goal:** retain the local-first model while preventing hostile browser pages
from invoking destructive operations.

- [x] Centralize request-origin validation for every state-changing method.
- [x] Validate `Host` against the configured loopback host and bound port.
- [x] Reject `Sec-Fetch-Site: cross-site` mutation requests.
- [x] Validate `Origin` when present and use strict `Referer` origin validation
  as a documented fallback.
- [x] Define behavior for non-browser local clients so tests and integrations do
  not rely on accidental browser behavior.
- [x] Require JSON for JSON mutation endpoints and reject unnecessary browser
  form posts.
- [x] Decide whether a per-process mutation token is warranted; ADR-001 records
  the decision not to add one because the tool has no sessions/cookies and local
  non-browser clients are a supported contract.
- [x] Reject non-loopback `--host` values by default, or require an explicit
  unsafe override with a separate documented threat model.
- [x] Add CSP, `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, a
  restrictive Referrer Policy, and an appropriate cross-origin resource policy.
- [x] Add tests for hostile `Origin`, `Referer`, `Sec-Fetch-Site`, `Host`,
  content type, and method combinations.
- [x] Update `SECURITY.md` and `skills-manager-threat-model.md` after testing.

**Acceptance gate:** the reproduced cross-origin purge is rejected, same-origin
UI calls continue to work, loopback defaults remain intact, and every unsafe
HTTP method is covered by tests.

## Milestone 3 — Recovery, atomicity, and data integrity

**Goal:** make edits, sync, imports, overwrites, trash, and index repair safe in
the presence of crashes, concurrent requests, and partial I/O.

- [x] Selectively integrate the approved snapshot design from issue #1:
  `<data>/snapshots/<scope>/<name>/`, newest-five retention, global and agent
  destinations, and CLI/UI restore integration.
- [x] Rebase snapshot code onto the P0 name/root guards before accepting it.
- [x] Selectively integrate the approved full-library migration design from
  issue #2: existing export/import flags, versioned manifest, skills + trash +
  templates, skip by default, and `--force` overwrite.
- [x] Resolve overlap between migration code and the selected archive pipeline.
- [x] Add atomic text writes using a sibling temporary file, flush/replace, and
  a documented durability policy.
- [x] Preserve original content if validation, serialization, or replacement
  fails.
- [x] Stage sync/overwrite operations and snapshot the destination before force
  for the integrated edit/sync/import recovery paths.
- [x] Define concurrency behavior for two CLI processes or UI requests touching
  the same skill.
- [x] Add failure-injection tests between filesystem and SQLite operations.
- [x] Make `doctor` report incomplete transactions, temporary files, stale
  snapshots, and index/filesystem drift.
- [x] Verify backup restore using content hashes, not only row counts.

**Acceptance gate:** approved recovery behavior is present on `main`, interrupted
operations are recoverable or explicitly reported, and all baseline plus failure
injection tests pass.

## Milestone 4 — Root, consumer, and effective-state architecture

**Goal:** stop conflating physical directories with the agents that consume
them.

- [x] Write an ADR for `SkillRoot`, `Consumer`, `ConsumerRootBinding`,
  `SkillInstance`, and `EffectiveSkill`.
- [x] Inventory official discovery roots, precedence, recursion, reload, and
  client-specific metadata for supported agents.
- [x] Correct the stale Cursor path and shared-root assumptions.
- [x] Deduplicate roots by resolved physical path before counting or syncing.
- [x] Model global, user, project, and nested project roots explicitly in the
  approval-gated ADR and discovery inventory; runtime entities remain deferred.
- [x] Support recursive discovery only where the consumer actually does so.
- [x] Represent read-only, writable, missing, and unsupported roots distinctly.
- [x] Calculate effective resolution for a selected consumer and project.
  **SHIPPED 2026-09-11 AS THE NARROW READ-ONLY DIAGNOSTIC (issue #12).** The
  runtime `EffectiveSkill`/winner model stays blocked exactly as recorded
  below; what landed is the derived-at-read-time diagnostic the entry's own
  "Next:" line called for, with no persistence and no locked-constraint
  change. `skillsmgr/effective.py` (`effective.explain(consumer, project,
  skill=None)`), surfaced as `doctor --explain CONSUMER [--project DIR]
  [--skill NAME]` and `GET /api/doctor?explain=…[&project=…][&skill=…]`.
  Per-consumer precedence rows are cited to
  @docs/12-agent-root-discovery-2026-09-08.md and never invented:
  `commandcode` six-way order (project `.commandcode/` > project `.agents/` >
  user `~/.commandcode/` > user `~/.agents/` > extras > bundled), `codex`
  explicit no-merge (no winner elected; every copy reported), `claude-code`
  personal > project for the conflict pair with project-root and nested copies
  both loading (`also_loads`), `gemini` built-in < extension < user <
  workspace with same-tier ties reported as `ambiguous`, and
  `cursor`/`opencode` as `undocumented-precedence` (their order is not
  documented). An unknown consumer returns `unknown-consumer` (CLI exit 1) and
  a missing project returns `missing-project` (exit 1); nothing that resolves
  nothing (`no-merge`, `undocumented-precedence`, `no-instances`) is an error.
  Observable tiers whose path this facade cannot read (Claude enterprise,
  Codex `SYSTEM`, Command Code `extras`/`bundled`, Gemini extension/built-in)
  are listed in `unobservable_tiers` with a warning that a lower-tier win is
  provisional; the `codex` facade id is warned as compatibility-only and
  reported as facade-only observations. Disabled (`SKILL.md.disabled`) and
  invalid (malformed/undecodable) instances are reported under `skipped` and
  can never win. Writes nothing (no file, no SQLite row, no cache; proven by
  tree-hash and no-DB assertions), `SCHEMA_VERSION = "1"` untouched,
  `effective_state: unresolved` everywhere else, and no new `Store` method.
  Contract tests: `tests/test_effective_explain_contracts.py` (36).
  **FINAL (2026-09-10) — historical entry that scoped this diagnostic:**
  **KEEP BLOCKED — `unresolved` is the correct contract.**
  Re-probes (hermetic loopback + isolated-HOME probes, zero code): project
  scopes require live project-CWD input (`scopes.py` appends project roots
  only `if cand.is_dir()` under CWD — absent in `/tmp`, present in a project
  CWD); same-name global+project duplicates both report
  `duplicated`/`divergent` with `effective_state: unresolved`
  (`root_discovery.py:61`, `scopes.py:269`), no winner elected anywhere;
  `SCHEMA_VERSION = "1"` (`store.py:39`) frozen. 2026-09-09 research
  (`docs/12-agent-root-discovery-2026-09-08.md` v1.1.0, `[?]`s CLOSED
  against primaries) plus 2026-09-10 re-survey (Claude enterprise >
  personal > project > plugins per
  [Datadog](https://securitylabs.datadoghq.com/articles/malicious-skills-supply-chain-risks-in-coding-agents-with-dynamic-context/) /
  [Amp](https://ampcode.com/manual); Gemini tiered discovery per
  `https://geminicli.com/docs/cli/using-agent-skills/`; OpenCode upward
  CWD-to-root per `https://opencode.ai/docs/skills/`;
  Cursor nested scoping per `https://cursor.com/docs/rules`; Codex
  REPO/USER/ADMIN/SYSTEM no-merge per
  `https://learn.chatgpt.com/docs/build-skills`; Command Code six-way order
  per `https://commandcode.ai/docs/skills`) prove precedence is per-consumer,
  not global: a single winner function is wrong for at least one consumer,
  needs a project-CWD input the CLI/REST contracts do not carry, and must not
  be persisted (schema frozen). Landing a resolver now would silently hide
  losing instances and break filesystem-as-source-of-truth. Next: the narrow
  read-only diagnostic (issue #12, derived at read time, cites source per
  winner, persists nothing). Blocked until the approval-gated runtime
  ConsumerRootBinding model is introduced.
- [!] Show active, shadowed, divergent, unmanaged, invalid, disabled, and
  duplicated instances; **FINAL (2026-09-10): observed states SHIPPED,
  `shadowed` STAYS BLOCKED.** Observed states (`active`, `disabled`,
  `invalid`, `duplicated`, `divergent`, `unmanaged` in `root_discovery.py`
  and `insights.py` `consumer_view()`/`ownership_states()`) are implemented
  and probed green with zero disk mutation (tree-hash proven); `shadowed`
  requires the approval-gated effective resolver above and stays blocked
  with it.
- [x] Make sync operate on unique physical roots exactly once.
- [x] Preserve unknown/client-specific frontmatter while separating portable
  standard fields from consumer extensions.
- [x] Add content hashes, metadata hashes, provenance, and observed timestamps
  without changing SQLite schema until explicitly approved.

**Acceptance gate:** CLI and UI can explain physical state and effective
consumer state; shared roots are not double-counted or overwritten twice.

## Milestone 5 — Architecture deepening without a rewrite

**Goal:** reduce change risk in hotspot modules while keeping public behavior
stable.

- [x] Extract archive inspection/extraction/commit logic from `store.py`.
- [x] Extract atomic document I/O and root-containment primitives.
- [x] Extract root discovery and consumer binding from `scopes.py`.
- [x] Extract webapp request security, JSON serialization, and multipart upload
  policy into private stdlib-only modules while retaining compatibility adapters;
  route dispatch remains in `webapp.py`.
- [x] Split `cli.py` parser construction (`cli_parser.py`), command handlers (`cli_handlers.py`), and output (`cli_output.py`) behind stable compatibility adapters.
- [x] Split `app.js` into no-build `domain.js` plus Vue workflow code; package-data coverage includes the new asset.
- [x] Preserve current public interfaces as compatibility adapters; parser/output/CLI contract tests remain green.
- [x] Replace correctness-critical rollback cleanup swallowing with stderr-only
  diagnostics that preserve the original failure and public contracts.
- [x] Add a stdlib AST complexity ratchet for route/parser/store hotspots;
  existing violations are baselined and new growth fails CI.

**Acceptance gate:** each extraction reduces coupling or increases testability;
all public behavior tests remain green; no speculative abstraction is added.

## Milestone 6 — Complete verification and regression defense

**Goal:** catch the classes of errors the original 47-test baseline missed.

- [x] Add broad hermetic unit coverage for public `Store` methods and representative error branches; a few internal failure-injection seams remain documented in the test module.
- [x] Add scope adapter contract tests shared by every root type.
- [x] Add focused CLI contract tests for scopes output, aliases/parser shape,
  JSON shape, and exit codes 0/1/2.
- [x] Add REST regression coverage for full archive import, security headers,
  and malformed/security paths; broader method/schema matrix remains follow-up.
- [x] Retain executable smoke scripts while factoring reusable fixtures/helpers.
- [x] Add parser round-trip and bounded-failure/property-style tests using the
  standard library only.
- [x] Add archive corpus tests for tar, ZIP if accepted, traversal, links,
  duplicates, limits, manifests, and partial failures.
- [x] Add search complexity and timeout tests.
- [x] Add concurrency tests for simultaneous reads/writes and requests.
- [x] Add wheel/sdist package-data assertions; optional clean-install probing is implemented in `check_package_data.py`.
- [x] Add documentation link, source-symbol, stale-fact, and version checks.
- [x] Generate verification summaries instead of hardcoding counts in docs; `tests/test_ci_release_contracts.py` now asserts workflow/release structure (matrix, jobs, pins, build-once, attestation, environments, post-publish checks) rather than blessed test counts.
  (2026-09-09: 10 CI/release contract tests + 5 xplat/package tests + 2 PyPI-claim tests; counts live in test output, not prose.)

**Acceptance gate:** every confirmed defect has a permanent test, all public
surfaces have contract coverage, and a clean checkout can build/install/run the
same artifact CI verifies.

## Milestone 7 — Browser UX, accessibility, and human-error reduction

**Goal:** make destructive and complex workflows understandable, reversible,
keyboard-usable, and robust at real viewport sizes.

- [x] Add `browser_harness.py`, a dev-only system-Chrome CDP harness with no runtime dependencies.
- [x] Capture console errors, warnings, runtime/unhandled exceptions, failed requests,
  and horizontal overflow across the viewport matrix.
- [x] Exercise the loaded app shell and verify all modal/dialog markup, screen/action
  controls, and static asset loading; interactive destructive flows remain a manual
  DevTools click-through responsibility documented in `docs/SESSION-CONTEXT.md`.
- [x] Add keyboard contract for search (`/`), shortcut help (`?`), menu/dialog Escape,
  Tab focus movement, tabs, filters, forms, and destructive confirmations.
- [x] Implement modal initial focus, focus trapping, Escape behavior, background
  `inert`/`aria-hidden`, and focus restoration.
- [x] Add accessible names, labelled dialogs, descriptions, pressed/current states,
  live regions, and error/status associations.
- [x] Initially focus the safer cancel/secondary action in destructive dialogs.
- [x] Add effective-scope/resolution preview before overwrite or sync.
- [x] Integrate escaped live Markdown preview; the shared renderer remains XSS-safe.
- [x] Add shortcut help after the keyboard contract.
- [x] Test 320px, 400px, 640px, 900px, desktop, reduced motion, and overflow safety;
  high-zoom/contrast/touch remain browser-operator follow-up.

**Acceptance gate:** zero browser console errors in supported flows, no keyboard
trap, conforming modal focus behavior, and clear scope/target/recovery warnings.

## Milestone 8 — CI, packaging, and controlled release

**Goal:** make releases repeatable, reviewable, and difficult to publish with
stale or untested artifacts.

- [x] Run CI on supported Python 3.10–3.14; add next-interpreter release-
  candidate coverage without silently changing support policy.
  (2026-09-09: `unit` matrix is 3.10–3.14; classifiers extended to match.)
- [x] Add Linux, macOS, and Windows path/archive coverage where practical.
  (2026-09-09: `xplat` job runs path/archive/package-data contracts on all
  three OSes × 3.10/3.14, plus host-independent `\`/drive-letter rejections.)
- [x] Pin GitHub Actions to reviewed commit SHAs or document an update policy.
  (2026-09-09: third-party release actions pinned with review dates; policy
  header records verified first-party SHAs and the moving-tag exception.)
- [x] Add separate adversarial/security, package, browser, and documentation
  jobs with clear failure ownership.
  (2026-09-09: `unit`/`adversarial`/`package`/`docs`/`xplat`/`browser` jobs;
  least-privilege `permissions: read-all`.)
- [x] Build wheel and sdist once, test those exact files, and publish only them.
  (2026-09-09: CI builds once, uploads `dist`, and gates on
  `check_package_data.py --dist-dir dist`; release reuses the same gate.)
- [x] Configure PyPI Trusted Publishing with a protected release environment;
  do not store a long-lived PyPI token in the repository.
  (2026-09-09: `release.yml` uses OIDC `id-token: write`, `testpypi` then
  `release` environments, no token secrets; regression-tested.)
- [x] Add artifact provenance/attestation where supported.
  (2026-09-09: `attest` job uses `actions/attest-build-provenance@v2`.)
- [x] Create a GitHub Release for every published tag.
  (2026-09-09: `github-release` job creates the release from `v*` tags.)
- [x] Verify TestPyPI, PyPI, CLI help, web assets, and hermetic CRUD after
  publication.
  (2026-09-09: TestPyPI publish, then PyPI publish, then tag/version/asset/
  CRUD/PyPI-install verification steps; regression-tested.)
- [x] Update PyPI badge/install claims after publication.
  (2026-09-10: README links the published `skill-control-plane` project and
  documents `pip install`/`pipx install`; regression-tested.)

**Acceptance gate:** release is reproducible from a clean checkout, the tested
artifact is the published artifact, provenance is available, and post-publish
installation verification passes.

## Milestone 9 — Product differentiation after safety foundations

> Read-only foundation landed 2026-09-09 in `skillsmgr/insights.py` (pure,
> stdlib-only, zero disk mutation, no new CLI/Store/schema surfaces):
> per-consumer observed views stay precedence-unresolved per ADR-002; diff,
> ownership, provenance, update preview, quarantine planning, risk scan,
> registry dry-run, provider-neutral eval, and deferred bundle policy are
> available as tested helpers over existing public seams. Runtime CLI/REST/UI
> exposure remains approval-gated work.

- [x] Per-consumer “what this agent sees” view (observed instances only; effective resolution stays `unresolved`).
- [x] Side-by-side and three-way skill diff (`diff_skills`/`diff_three_way`).
- [x] Managed, unmanaged, adopted, quarantined, and invalid ownership states (`ownership_states`).
- [x] Provenance: source, revision, install mechanism, content hash, importer,
  and validation history (`provenance_summary` over loader observations; persistence approval-gated).
- [x] Update preview with changed files, metadata, risks, and rollback status (`update_preview`).
- [x] Quarantine untrusted imports before activation (stage-only `quarantine_plan`; activation approval-gated).
- [x] Explainable static risk scan for scripts, links, tools, and suspicious
  instruction patterns (`risk_scan` with why + evidence).
- [x] Registry browsing with source preview, provenance, scope selection,
  dry-run, and explicit trust confirmation (offline `registry_preview`; network browse deferred).
- [x] Evaluation harness with provider adapters and no mandatory runtime SDK (stdlib-only `eval_plan`/`eval_score`, advisory-only).
- [x] Revisit signed/team bundles only after the single-user trust model,
  quarantine, provenance, and recovery behavior are mature (`bundle_policy` records `deferred`).

## Milestone 10 — Documentation truth and project hygiene

- [x] Reconcile `AGENTS.md` with the final architecture and constraints.
- [x] Correct stale GTK and legacy database-path claims in `docs/01-architecture.md`.
- [x] Mark `docs/05-gui-plan.md` as historical only or remove it through an
  explicit documentation decision.
- [x] Correct scope paths, shared-root semantics, test inventory, and current
  CLI/API signatures in owning docs.
- [x] Update `.commandcode/settings.json`, which references deleted
  `skillsmgr/gui.py`, through a separate hygiene change.
- [x] Reconcile `task.md`, `TODO.md`, `PLAN.md`, `ROADMAP.md`, `CHANGELOG.md`,
  and `docs/06-progress-log.md` without marking worktree-only code as shipped.
- [x] Add a machine-checkable docs/source consistency command.
- [x] Keep historical entries append-only while moving current truth into
  owning documents.

## Milestone 11 — Research-verdict implementation queue (2026-09-09; new sessions start here)

**Goal:** execute the 2026-09-09 research verdicts in order. Every code
item follows the error-prevention protocol below (failing reproduction
first, full ladder green, owning docs plus the progress log). Nothing
here changes a locked constraint; each `[!]` keeps its stated approval.

- [x] L1 — Closed issue #10 with evidence 2026-09-09 (no code):
  commented the shipped file/line facts
  (`skillsmgr/webui/index.html:70,373,756-760`,
  `skillsmgr/webui/domain.js:60`, `skillsmgr/webui/app.js:6,130`),
  closed the issue (`gh issue view 10` = CLOSED). Deferred line for #10
  dropped below in this same pass.
- [x] L2 — ZIP import slice (issue #5, approved 2026-09-10): red-first
  malicious-ZIP corpus (traversal, absolute, `\`, drive-letter, symlink-bit,
  duplicate, bomb-ratio, garbage/truncated) through the shared preflight,
  private extraction, validation, and staged-commit pipeline. ZIP support extends
  the existing `import` command/REST route only; no new command was added.
- [x] L3 — Effective-explain research track done docs-only 2026-09-09
  (no code; runtime model stays approval-gated): closed the three `[?]`
  in `docs/12-agent-root-discovery-2026-09-08.md` (v1.1.0) against
  primary sources — Codex `.agents/skills/` REPO/USER/ADMIN/SYSTEM roots
  with no-merge same-name policy (facade `~/.codex/skills` is compat-only)
  per `https://learn.chatgpt.com/docs/build-skills`; Command Code six-way
  selection order + Duplicate-names warnings + `/skill:<name>` hatch +
  live reload per `https://commandcode.ai/docs/skills`; Claude
  enterprise > personal > project with both-load nested/plugin exceptions
  per `https://code.claude.com/docs/en/skills`. Proposed narrow
  read-only diagnostic (`doctor --explain CONSUMER --project DIR`,
  derived at read time, cites source per winner, persists nothing, keeps
  `effective_state: unresolved`) — filed as issue #12 on 2026-09-09;
  **IMPLEMENTED 2026-09-11** (constraint-5 approval given for the read-only
  `doctor --explain` flag; see the Milestone 4 entry and
  `tests/test_effective_explain_contracts.py`).
- [x] L4 — Recorded the three rejections 2026-09-09 (no code): commented
  issue #6 (keep feature-detect plus guarded manual extractor in
  `skillsmgr/archive.py:133-158`; refusal breaks the supported 3.10/3.11
  matrix for zero fail-closed gain), #7 (keep the warning in
  `skillsmgr/validator.py:323-352` plus `risk_scan()` in
  `skillsmgr/insights.py:342-354`; promotion hard-fails legitimate
  monorepo-relative layouts), and #9 (browser stays canonical per locked
  constraint 4; at most an unbundled loopback-only launcher). Each issue
  carries the rationale with file/line evidence.
- [x] L5 — Held the deferred four 2026-09-09 (no code; verified): issues
  #3/#4/#8/#11 all still OPEN with zero comments; no network
  (`urllib` only in `webapp.py`/`web_security.py` for URL parsing),
  backend (eval stays stdlib `eval_plan`/`eval_score`, no SDK/model
  calls), extension (no TS/VS Code surface), or signing
  (`bundle_policy()` returns `deferred`) code in `skillsmgr/`; ZIP import is
  now implemented in the approved scoped extension with guarded preflight and
  manual extraction. Staged paths unchanged: registry #3 (offline preview
  gate, then id-to-`install` mapping, then a network ADR), eval #4
  (advisory-only, file-based, never blocking), extension #8 (separate
  repo; missing endpoints get their own ASK), team sharing #11
  (design-only ADR plus threat-model delta before any bundle format).
- [x] L6 — Release completed through the existing gate (2026-09-10): package
  `1.0.1` == `__version__`; the published distribution is
  `skill-control-plane` while `skills-mgr`, `skillsmgr`, and the
  `skills-manager` repository/data names remain unchanged. `release.yml`
  validated the tag/version, built once, checked exact artifacts, attested
  provenance, published to TestPyPI → protected PyPI → GitHub Release, and
  passed post-publish install/CRUD verification. This worktree performs no
  publish, tag, or push action.
  **HISTORICAL/SUPERSEDED executed record (2026-09-10, pre-rename artifacts):** built once from a clean copy of the
  current tree with `build==1.2.2.post1`; wheel
  `skills_manager-1.0.0-py3-none-any.whl` sha256 `6e2dbac79f06…` (172 KB) and
  sdist `skills_manager-1.0.0.tar.gz` sha256 `1d1bb1fe8251…` (208 KB);
  `check_package_data.py --dist-dir` PASS on both (5 web UI files, Vue 157,924 B)
  and `--dist-dir --install` clean-installs the inspected wheel; a separate
  pristine venv installed the wheel with `--no-index --no-deps`, ran `--help`
  and `create demo`, and asserted the vendored Vue bundle plus `webui/domain.js`
  are present. The sdist clean-install reports an honest `UNAVAILABLE` offline,
  so it was verified separately instead: a venv with `setuptools` provisioned
  installed `dist/skills_manager-1.0.0.tar.gz` (`--no-deps
  --no-build-isolation`), ran `--help` and `create sdist-demo`, and asserted the
  vendored Vue bundle (157,924 B), `webui/domain.js` (5,537 B), and
  `webui/index.html` (55,840 B) are present. Cross-artifact consistency: the
  wheel and sdist each carry 32 `skillsmgr/` files whose SHA-256 digests are
  equal to each other and to the source tree at `80bc02a`, with `METADATA`
  `Version: 1.0.0` and the console entry point present.
  Wheel members are byte-identical across rebuilds (only ZIP timestamps differ);
  the stale 2026-09-05 artifacts are preserved under `dist/stale-2026-09-05/`
  (they fail the gate: missing `domain.js`).
  **HISTORICAL/SUPERSEDED publication blocker (evidence, 2026-09-10):** `gh api
  repos/udayvarmora07/skills-manager/environments` → `total_count: 0` (no
  `release`/`testpypi` environment, so no protected approval gate exists);
  `https://pypi.org/pypi/skills-manager/json` → 404 and
  `https://test.pypi.org/pypi/skills-manager/json` → 404 (no project and no
  registered trusted publisher, so OIDC publishing would be rejected);
  `git ls-remote --tags origin` → only `v1.0.0` at `d94cc02` (an earlier release
  commit), so publishing this slice needed a maintainer-owned version bump and
  tag decision. The subsequent `skill-control-plane` 1.0.1 release completed
  successfully; this blocker is retained only as pre-publish history. The CI
  prerequisite was met — run 34488162920 for `a3a055d` was **success** across
  all 15 jobs.
  **HISTORICAL/SUPERSEDED rehearsal (2026-09-10, nothing published at that
  time):** the workflow's build + verify half was run against a clean
  `git archive HEAD` copy with a candidate version applied only in that copy —
  tag/version gate PASS for `v1.0.1`, build once, `--dist-dir` gate PASS on the
  candidate artifacts, 315 unittest OK, `check_docs.py` PASS, complexity PASS,
  clean wheel install PASS. The rehearsal found that `check_docs.py` pins the
  documented `__version__` in `docs/01-architecture.md` and
  `docs/02-modules.md`, so a version bump was a 4-line change.
  **HISTORICAL/SUPERSEDED exact remaining steps (maintainer-gated):** (1) register a PyPI trusted
  publisher (and TestPyPI) for this repository/workflow/environments; (2) create
  the GitHub `testpypi` and protected `release` environments; (3) choose the
  release version and apply the 4-line bump; (4) tag `v<version>` and push. The
  subsequent workflow completed all remaining steps successfully; this list is
  retained only as pre-publish history.

**Acceptance gate:** L1 and L4 recorded on their issues; L2 green on the
full ladder with corpus regressions; L3 `[?]`s closed with sources; L5
untouched without approvals; L6 artifacts equal the tested artifacts.

## Milestone 49 — Approval-safe verification campaign (2026-09-10, round 17)

- [x] T1 baseline ladder: 301 `unittest` tests, both smoke suites, compile,
  frontend syntax, docs, complexity, diff, and CLI help passed.
- [x] T2 catalog: 62 installed skills audited; required skills loaded; no install
  performed because stdlib-only and hermetic constraints make it unnecessary.
- [x] T3 P0 rotation: P0-001 traversal, P0-002 cross-origin purge, P0-003 archive
  destination safety, P0-004 wildcard bounds, and P0-005 parser recursion all
  failed closed in hermetic probes.
- [x] T4 issue #13 remains characterized but unfixed: invalid UTF-8 still leaks
  `UnicodeDecodeError` from store-wide scan paths; validator catches it cleanly.
  No behavior decision or code change was made without approval.
- [x] T5 L6 hygiene: versions/tag align and workflow gates are present; stale
  ignored `dist/` wheel fails exact package-data verification due to missing
  `domain.js`, so no release action was taken.
- [x] T6 REST fail-closed matrix passed: hostile browser metadata 403, missing
  JSON 415, malformed input/long query 400, same-origin create 201, five headers.
- [x] T7 archive/parser/search resource-bound probes passed.
- [x] T8 fresh temporary-data CLI contract probes passed with clean errors.
- [x] T9 browser harness passed five viewports and fresh loopback live seam passed.
- [x] T10 docs updated in `task.md`, this file, `PLAN.md`, and the append-only
  progress log; final verification and Git review are recorded in the log.

## Deferred and approval-required work

> Research verdicts 2026-09-09 (loop-engineering probes in isolated temp
> dirs, stdlib only, no product-code changes; ~200 web sources across
> registry, eval, archive, localhost, signing, discovery, atomicity, and
> accessibility families; full detail in `docs/06-progress-log.md`
> 2026-09-09 entry). **Final-verdict round 2026-09-10:** 4 hermetic
> re-probe agents (archive, parser/search/links, REST/effective/insights,
> release/docs/worktrees/encoding/signing/atomicity — all stdlib-only,
> zero product-code changes) + 8-family survey workflow (309 quoted URL
> entries, 194 unique sources) + 3 targeted `web_search` batches. Baseline
> held green (301 unittest, both smokes, all gates). Each item keeps its
> `[!]` until its stated approval lands. New sessions implement in the
> order given here: ~~close #10~~ DONE 2026-09-09 (#10 CLOSED), ~~ZIP on
> approval~~ DONE 2026-09-10 (L2 shipped in the scoped `import` extension),
> ~~effective-explain diagnostic~~ DONE 2026-09-11 (issue #12 shipped as
> `doctor --explain`, read-only, persisting nothing — see the Milestone 4
> entry). The remaining items below keep their stated approvals.

- [!] Registry bridge: issue #3. Research verdict: DEFER network
  browse/fetch. **FINAL (2026-09-10): DEFERRED — confirmed by Snyk
  ToxicSkills audit.** **OFFLINE HALF SHIPPED 2026-09-10** (approved staging
  items 1-3), design in @docs/ADR-003-registry-bridge-and-eval-harness.md:
  `insights.registry_reference()` parses `owner/repo`, `owner/repo/slug`,
  `https://skills.sh/{source}/{slug}`, and `https://github.com/owner/repo`
  offline; `insights.registry_bridge_plan()` keeps the explicit-trust gate
  (`blockers`/`may_install`), maps a registry skill id onto the exact
  `npx skills add … -s <slug>` command through the shared
  `insights.install_argv()` renderer used by the real install path, and
  surfaces the linkable `/security/{provider}` audit pages plus the
  `hash` slot for change detection. Surfaces are extensions of existing ones
  only: `install --preview [--trust-confirmed] [--registry-hash HEX]` and
  `POST /api/install {preview: true}`; `install` behavior (runner allowlist,
  dry-run-first, delegation) is unchanged, no network request, cache, or
  credential exists anywhere in the product, and one test pins that the bridge
  modules import no network client. Contract tests:
  `tests/test_registry_bridge_contracts.py` (21). Remaining for this item:
  network browse/fetch, caching, auth, and provenance persistence still need
  their own ADR. Historical research verdict follows. `skills.sh` exposes a real catalog API (`GET
  /api/v1/skills|search|curated|{source}/{skill}|audit/{source}/{skill}`
  with file contents plus a SHA-256 `hash`, per
  `https://www.skills.sh/docs/api`), but authenticated reads require a
  Vercel OIDC bearer token (600/min per team/project, HTTP 401 without,
  per the same reference) — `vercel link` plus token plumbing is
  unsuitable for a local-first stdlib tool. New 2026-09-10 evidence
  hardens the deferral: Snyk's ToxicSkills audit of 3,984 skills
  (ClawHub + skills.sh) found 13.4% (534) critical, 36.82% any issue,
  and 76 confirmed malicious payloads with prompt-injection+malware
  convergence (per
  [Snyk](https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/));
  re-probes confirm the product has zero network imports today
  (`urllib` is URL-parsing only in `webapp.py`/`web_security.py`) and
  `install` deliberately delegates to the ecosystem runner with
  dry-run-first plus allowlist validation (threat-model H-1 posture).
  Install itself is `npx skills add owner/repo` (per
  `https://www.skills.sh/docs/cli`); the third-party audit surface
  (Socket/Snyk/Trust-Hub verdicts) is linkable, not proxyable. Approved
  staging: (1)
  keep the preview gate, (2) map registry ids to `npx skills add`
  through the existing `install` dry-run machinery, (3) surface the audit
  link plus `hash` for invalidation. Network fetch, caching, auth, and
  provenance design need their own ADR first: decide API, caching,
  provenance, trust, and whether to extend `install` or add a new
  surface.
- [!] Eval harness: issue #4. Research verdict: ADVISORY-ONLY stays;
  defer any runtime backend indefinitely. **FINAL (2026-09-10):
  ADVISORY-ONLY — confirmed by promptfoo + LLM-judge-bias literature.**
  **FILE CONTRACT SHIPPED 2026-09-10**, design in
  @docs/ADR-003-registry-bridge-and-eval-harness.md: `skillsmgr/evals.py`
  implements the official layout — `evals/evals.json` cases
  (`id`/`prompt`/`expected_output`/`files` plus optional `slug` and optional
  deterministic `assertions`), `iteration-N/eval-<slug>/{with_skill,without_skill}/`
  holding `outputs/output.txt`, `grading.json`, and `timing.json`, and a
  per-iteration `benchmark.json` with per-variant case pass rates and the
  `with_skill` − `without_skill` delta. Surfaces extend existing ones only:
  `validate --evals` (read-only report) and `validate --evals-run FILE`
  (explicit opt-in recording, single target), plus
  `POST /api/validate {evals: true}` / `{runs: […]}`. Workspaces default to
  `<data>/evals/<name>-workspace` (outside `skills/`, so scans, `doctor`
  orphans, exports, and the index never see run data) or `<DIR>-workspace`
  with `--path`; `--workspace` is CLI-only so REST cannot choose a write
  location. Assertion set is the deterministic subset (`equals`, `contains`,
  `not_contains`, `regex`, `is_json`); a case with no assertions is recorded
  `graded: false`, never as a pass; scores never change `valid`, never gate
  installs or edits, and never touch SQLite. Contract tests:
  `tests/test_eval_harness_contracts.py` (38). Remaining for this item: a
  provider abstraction, credentials, isolation model, and persisted
  cross-machine results — the standing answer stays advisory-only. Historical research verdict follows.
  The official evaluating-skills guide prescribes `evals/evals.json`
  (prompt/expected/files), with-skill versus without-skill (or
  previous-version) baselines, and
  `iteration-N/eval-*/{with_skill,without_skill}/` workspaces (per
  `https://agentskills.io/skill-creation/evaluating-skills`); promptfoo's
  assertion model (deterministic equals/contains/regex/is-json plus
  weighted model-graded llm-rubric, per
  [promptfoo](https://www.promptfoo.dev/docs/configuration/expected-outputs/))
  confirms deterministic-first is the stdlib-safe subset; LLM-judge
  position (~65% flip on swap), verbosity, and self-preference biases are
  measured and systematic (per [arXiv 2410.21819](https://arxiv.org/abs/2410.21819)
  and [bias survey](https://ai-tldr.dev/learn/evaluation-safety/llm-as-judge/llm-judge-biases/)).
  The stdlib-safe subset is already shipped
  (`insights.eval_plan()`/`eval_score()`: deterministic cases,
  caller-supplied scorer, "scores never block installs", no SDK, no
  network). Backend = none in-product (bring your own runner outside the
  trust boundary); results live as skill-dir files per the spec, never in
  SQLite (schema frozen); verdicts never gate installs or edits. Decide
  provider abstraction, credentials, persistence, isolation, and advisory
  versus blocking behavior — the standing answer is advisory-only.
- [x] ZIP import: issue #5. Research verdict: APPROVE as a scoped
  extension of the existing `import` (highest-value feature approval, one
  focused slice, no new command). **COMPLETED 2026-09-10:** `Store.import_`
  content-sniffs ZIP files, applies the shared normalized-name/layout/type and
  compressed/expanded/member/path/nesting/ratio budgets, rejects symlink bits,
  manually extracts only to contained staging paths, then reuses manifest,
  frontmatter, staged commit, and content-hash verification. Red-first tests
  cover valid round-trip, traversal, absolute, backslash, drive-letter,
  symlink-bit, duplicate, malformed, and REST ZIP cases. Existing tar imports
  and the schema remain unchanged. Historical research follows:
  `zipfile` preserves hostile names verbatim
  (`../../evil.txt`, `/abs.txt`, `skills/ok/../../escape.md`,
  `skills\evil`, `C:/evil`, duplicates count 2, symlink-bit
  `(external_attr >> 16) & 0o170000 == 0o120000`), so a manual guard is
  mandatory; budgets re-verified exact (200 members ok/201 reject;
  path 512 ok/513 reject; nesting 16 ok/17 reject; 9MB member reject;
  40000:1 ratio reject; `archive.py:20-26`). The research below is retained as historical context.
  External authorities: ZipSlip ([Snyk
  research](https://security.snyk.io/research/zip-slip-vulnerability))
  — `zipfile.extract` strips drive/leading slashes but `extractall` docs
  still warn files CAN land outside path and `zipfile.Path` does NOT
  sanitize (caller must abspath+commonpath check), per
  [zipfile docs](https://docs.python.org/3/library/zipfile.html);
  `ZipInfo.external_attr` symlink semantics per
  [discussion](https://discuss.python.org/t/how-info-zip-represents-symlinks/4104);
  42.zip (42KB → 4.5PB nested deflate) per
  [Zip bomb](https://en.wikipedia.org/wiki/Zip_bomb); PEP 706 explicitly
  deferred zipfile filters as out-of-scope (no `data_filter`
  equivalent), per [PEP 706](https://peps.python.org/pep-0706/) — manual
  member-list validation is required. Parity map: ~90% of the tar policy ports verbatim (name
  normalization, `\`/drive rejection, duplicate detection, layout
  allowlist, six budgets via `file_size`/`compress_size`, staged commit
  plus content-hash verify); genuinely new work is only (1) the
  ZipInfo symlink-bit check, (2) a zip manual extractor (zip has no
  `data_filter` equivalent), (3) the zip-bomb ratio on `compress_size`.
  Required: red-first malicious-ZIP corpus (traversal, absolute, `\`,
  drive-letter, symlink-bit, duplicate, bomb-ratio, garbage/truncated)
  through the same preflight, private extraction, validation, and
  staged-commit pipeline. Use the Milestone 1 archive pipeline if
  approved.
- [!] Python <3.12 tar policy: issue #6. Research verdict: REJECT refusal;
  keep feature-detect plus the guarded manual extractor. **FINAL
  (2026-09-10): REJECTED — CVE-2025-4138 proves the independent validator
  is the real defense.** Probes: this environment is Python 3.12.3
  (`data_filter` present); hostile-tar probe rejects traversal,
  `skills\evil`, symlink, and `C:/evil` through the independent
  pre-validator (`archive.py:29-60` + `extract_members`
  `archive.py:131-153`). Authorities: [PEP
  706](https://peps.python.org/pep-0706/) and the [tarfile
  docs](https://docs.python.org/3/library/tarfile.html) say to
  feature-detect (`hasattr(tarfile, "data_filter")`), not version-gate
  (3.14 flips the default to `data`); [CVE-2025-4138](https://www.sentinelone.com/vulnerability-database/cve-2025-4138)
  (plus the PATH_MAX/hardlink/errorlevel=0 cluster, CPython issue 135034)
  proves data/tar filters are bypassable via symlink targets — the
  independent validator is the real defense even on new interpreters.
  Refusal would break `import` on the supported 3.10/3.11 matrix
  (`requires-python >= 3.10`) for zero fail-closed gain. Prefer capability detection and safe independent validation over
  a silent unsafe fallback — the current design already does this.
- [!] Out-of-root link severity: issue #7. Research verdict: REJECT the
  warning-to-error promotion; keep the warning plus `risk_scan()`.
  **FINAL (2026-09-10): REJECTED — promotion would break 68 legitimate
  layouts (measured).** Probes: `../../../etc/shadow`, `/etc/passwd`, and `../shared/common.md`
  all warn correctly today (`validator.py:323-360`, warning-only);
  `https://`, `#anchor`, and `<angled>` targets stay clean; walk found
  `~/.agents` 55 in-root/0 out-of-root and `~/.claude` + `~/.codex` 34
  out-of-root EACH — ALL legitimate sibling-skill/monorepo-relative
  references (e.g. mysql→`../postgresql/`, convex-backend→
  `../../../devops/ai/agent-observability/`), not `/etc` escapes; plus
  `_LINK_RE`/`_SCRIPT_RE` regex artifacts (nested parens, titles,
  `chmod +x` prose) would become false errors. Authorities: the Agent
  Skills spec requires SKILL.md-relative references with upward
  project-root discovery (OpenCode walks cwd→root every level, Codex
  scans `.agents/skills` upward, per
  [Agent Skills spec](https://agentskills.io/specification) and
  [OpenCode](https://opencode.ai/v2/docs/skills)); warn-by-default is the
  consistent tooling precedent (zudo-doc warn mode, mlc/linkspector
  internal-only gating, REF-001 per-file resolution, per
  [mlc](https://github.com/becheran/mlc) and
  [REF-001](https://contextlint.dev/docs/rules/ref-001/)). Threat-model R-4 is Low/Low with
  "consider/optionally" language, and `risk_scan()` already flags
  out-of-root links as medium findings with why plus evidence while
  quarantine staging covers untrusted imports. Decide strictness and
  legitimate project-relative link policy — the standing answer is warn,
  not error.
- [!] VS Code extension: issue #8. Research verdict: separate-repo spike
  when pursued; no backend changes here. **FINAL (2026-09-10):
  SEPARATE REPO — backend already sufficient.** The REST table in
  `docs/08-web-ui.md` already covers everything an extension needs
  (CRUD, search, validate, sync, install, trash/snapshots, templates,
  export/import, scopes, tokens, doctor/history); loopback binding is
  enforced with Host/Origin/Referer/Fetch-Metadata plus JSON
  content-type gates (ADR-001), and the REST probe matrix stays
  fail-closed (cross-origin purge 403, missing content-type 415, bad
  install types 400, long query 400 — re-verified hermetically this
  round, headers CSP/`frame-ancestors 'none'`/nosniff/DENY/no-referrer/CORP
  live). Extension work (TypeScript client, tree view, webview,
  spawn/attach lifecycle, vsix/marketplace) sits outside the stdlib
  product and its gates (per [REST Client precedent](https://github.com/Huachao/vscode-restclient)
  and [publishing docs](https://code.visualstudio.com/api/working-with-extensions/publishing-extension)).
  Keep it separate until REST contracts and local API security are
  stable; any missing endpoint gets its own ASK first.
- [!] Native desktop wrapper: issue #9. Research verdict: REJECT as a
  product direction; keep the browser canonical. **FINAL (2026-09-10):
  REJECTED — pywebview adds runtimes for cosmetic gain.** The GTK4 GUI was deleted
  2026-08-14 in favor of the web UI, which `browser_harness.py` verifies
  across 320–1280px viewports with zero console errors (re-verified this
  round). `pywebview` ([repo](https://github.com/r0x0r/pywebview)) is a
  native webview wrapper needing a third-party install plus OS webview
  runtimes (WebView2/GTK-WebKit/Cocoa) — allowed only as an optional
  extra under locked constraint 4, never the default — while adding
  native failure modes and accessibility-regression surface for a
  cosmetic gain. Optional only, never replacing the dependency-free
  browser path; an unbundled loopback-only launcher script is the most
  that should ever exist.
- [!] Team sharing/signatures: issue #11. Research verdict: correctly
  DEFERRED; design-before-code with honest stdlib limits. **FINAL
  (2026-09-10): DEFERRED — HMAC cannot sign for a team (NIST), Ed25519
  is not stdlib.** Probes: HMAC-SHA256 sign/verify plus tamper detection
  work in stdlib, but no asymmetric signing exists there (`ed25519`
  absent; `cryptography`/`nacl` are OS packages, not stdlib — unusable
  under the stdlib-only constraint); HMAC is symmetric, so anyone who can
  verify can also forge — "not transferable to third parties, contrary
  to non-repudiation provided by digital signatures" (per
  [NIST SP 800-224](https://csrc.nist.gov/pubs/sp/800/224/ipd)); TUF
  delegation needs threshold>=1 validation (threshold=0 bypasses
  verification entirely, per
  [CVE-2026-23992](https://cvereports.com/reports/CVE-2026-23992)).
  External models: minisign-style Ed25519 file signing (per
  [minisign](https://jedisct1.github.io/minisign/)), TUF
  trust delegation with thresholds (per
  [TUF spec](https://theupdateframework.github.io/specification/latest/)),
  in-toto layouts with functionary link metadata, and SLSA/Sigstore
  keyless provenance (Fulcio short-lived cert + Rekor transparency, per
  [Sigstore](https://docs.sigstore.dev/cosign/signing/overview/) and
  [PEP 740](https://peps.python.org/pep-0740/) / [PyPI
  attestations](https://blog.pypi.org/posts/2024-11-14-pypi-now-supports-digital-attestations/)).
  None of `bundle_policy()`'s prerequisites hold yet (explicit trust
  model, approved plus tested quarantine activation — today stage-only —
  persisted provenance/hashes — today observation-only — verified
  recovery). Requires a trust/key-distribution design and a new
  threat-model review — no bundle format code until that ADR lands.

## Error-prevention protocol

This protocol is mandatory for every future change:

1. State the user outcome and invariant that must remain true.
2. Reproduce current behavior in an isolated temporary directory or hermetic
   browser session.
3. Write the failing regression test first whenever technically possible.
4. Fix the shared invariant, not only the first call site that failed.
5. Run adversarial probes against neighboring inputs and alternate surfaces.
6. Run targeted checks, then the complete verification ladder.
7. Review failure paths for tracebacks, swallowed exceptions, partial writes,
   stale indexes, and misleading success responses.
8. Review every exposed surface: Store, CLI, REST, UI, archive/package, and docs.
9. Update owning docs and the progress log with exact dates and commands.
10. Inspect Git diff/status and confirm no unrelated file changed.
11. Re-run from a fresh temporary data directory before declaring done.
12. Record uncertainty as `[!]` or `[?]`; never silently guess.

## Definition of done for the world-class baseline

- [x] No confirmed P0 defects remain.
- [x] All destructive paths validate names and roots before touching disk.
- [x] Archive, parser, search, upload, and history costs are bounded.
- [x] Cross-origin browser mutations are rejected.
- [x] Every overwrite has tested recovery or an explicit irreversible policy.
- [x] Filesystem/index drift is detectable and repairable.
- [x] Physical roots and consuming agents are modeled separately.
- [x] CLI, REST, UI, package, browser, and documentation contracts are tested.
- [x] Accessibility-critical workflows pass keyboard/focus checks.
- [x] CI tests exact release artifacts and supported environments.
- [x] Release provenance and post-publish installation checks exist.
- [x] Current documentation agrees with source and Git state.
- [x] Every historical bug has a permanent regression test and recorded cause.