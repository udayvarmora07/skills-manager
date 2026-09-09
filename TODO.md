# TODO — Skills Manager World-Class Execution Backlog

**Plan version:** 2.0.0
**Backlog date:** 2026-09-07
**Baseline:** `main` at `667fabb` in `/home/uday-varmora/skills-manager`
**Companion plan:** `/home/uday-varmora/skills-manager/PLAN.md`

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
- [!] PyPI publication is not confirmed by the repository history; publishing
  must use a clean artifact and a controlled release workflow.

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

- [!] `/home/uday-varmora/skills-manager.worktrees/todo-plan-implementation`
  contains approved rollback/full-migration work plus adversarial fixes and
  tests; it is not part of `main`.
- [!] `/home/uday-varmora/skills-manager.worktrees/milestone5-research-user-needs`
  contains a different archive hardening/ZIP/UX implementation; it is not part
  of `main` and must not be merged wholesale.
- [x] GitHub issues #1 and #2 are closed as approved design decisions, but their
  code must still be selectively integrated and re-reviewed on `main`.
- [!] `docs/01-architecture.md`, `docs/05-gui-plan.md`,
  `.commandcode/settings.json`, and several historical counters contain stale
  claims. Documentation reconciliation is planned work, not evidence that the
  stale behavior still exists.

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
- [x] Decide and document ZIP support: ZIP remains intentionally unsupported;
  archive content is sniffed and rejected before tar parsing.
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
- [!] Calculate effective resolution for a selected consumer and project; blocked
  until the approval-gated runtime ConsumerRootBinding model is introduced.
- [!] Show active, shadowed, divergent, unmanaged, invalid, disabled, and
  duplicated instances; observed states are implemented, but shadowing requires
  the approval-gated effective resolver.
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
- [x] Remove or qualify PyPI badge/install claims until publication is real.
  (2026-09-09: PyPI badge removed; README states PyPI is a future release
  and points at source/CI artifacts; regression-tested.)

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

## Deferred and approval-required work

- [!] Registry bridge: issue #3; decide API, caching, provenance, trust, and
  whether to extend `install` or add a new surface.
- [!] Eval harness: issue #4; decide provider abstraction, credentials,
  persistence, isolation, and advisory versus blocking behavior.
- [!] ZIP import: issue #5; use the Milestone 1 archive pipeline if approved.
- [!] Python <3.12 tar policy: issue #6; prefer capability detection and safe
  independent validation over a silent unsafe fallback.
- [!] Out-of-root link severity: issue #7; decide strictness and legitimate
  project-relative link policy.
- [!] VS Code extension: issue #8; keep it separate until REST contracts and
  local API security are stable.
- [!] Native desktop wrapper: issue #9; optional only, never replacing the
  dependency-free browser path.
- [!] Live preview and shortcut help: issue #10; frontend-only after browser
  and accessibility foundations.
- [!] Team sharing/signatures: issue #11; requires a trust/key-distribution
  design and a new threat-model review.

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