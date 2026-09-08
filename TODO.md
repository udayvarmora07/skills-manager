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
- `[x]` = implemented on `main` and verified by the required acceptance checks.
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
- [ ] **P0-SEC-002: cross-origin localhost mutation.** A request with an
  attacker `Origin` successfully called `POST /api/trash/purge` and permanently
  emptied trash. Loopback binding does not by itself prevent browser-to-localhost
  cross-origin requests.
- [x] **P0-SEC-003: invalid manifestless archive names fixed 2026-09-08.** The
  manifestless fallback now applies the canonical name rule and skips invalid
  directories without creating a destination.
- [ ] **P0-SEC-004: wildcard search exhaustion.** A crafted alternating wildcard
  pattern caused `rank_results` to run beyond an eight-second probe timeout.
- [ ] **P0-SEC-005: parser recursion failure.** Deep block and flow frontmatter
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
- [ ] Ensure `--force` cannot turn an invalid destination into a valid delete.
- [ ] Ensure trash matching cannot confuse a valid name with a path fragment or
  prefix collision.

### 1B. Archive intake

- [ ] Create an archive preflight pipeline separate from mutation: identify
  format, inspect members, validate names/types/paths, enforce limits, extract
  into a private temporary directory, validate contents, then commit.
- [ ] Reject absolute paths, `..` components, duplicate members, device files,
  FIFOs, hard links, symlinks, unsupported metadata, and unexpected layouts
  unless explicitly supported.
- [ ] Feature-detect `tarfile.data_filter`; never silently fall back to
  unfiltered extraction.
- [ ] Keep independent member validation even when the interpreter provides a
  safe extraction filter.
- [ ] Enforce compressed-size, expanded-size, member-count, individual-member,
  path-length, nesting-depth, and compression-ratio limits.
- [ ] Validate manifest schema, version, names, paths, and duplicate entries.
- [ ] Validate manifestless fallback names with the canonical name rule.
- [ ] Decide and document ZIP support; if accepted, use the same security
  pipeline and content sniffing rather than suffix checks alone.
- [ ] Make imports all-or-nothing per skill or clearly report partial commits;
  never leave an unexplained half-imported tree.

### 1C. Parser and resource bounds

- [ ] Add document-size, key-count, collection-size, scalar-length, and
  nesting-depth limits to the frontmatter parser.
- [ ] Convert recursion-limit failures and malformed flow structures into
  `FrontmatterError`.
- [ ] Preserve valid Agent Skills and client-extension frontmatter fixtures.
- [ ] Add a deterministic malformed-input corpus.

### 1D. Search resource bounds

- [ ] Replace unbounded wildcard-to-regex expansion with a bounded matcher or a
  rigorously constrained translation.
- [ ] Collapse repeated `*`, cap pattern length and wildcard complexity, and
  define a clean CLI/REST/UI error.
- [ ] Use the same search implementation for global, agent, merged, CLI, and
  REST search paths.
- [ ] Add timing-bounded tests for adversarial patterns.

**Acceptance gate:** P0-SEC-001, P0-SEC-003, P0-SEC-004, and P0-SEC-005
reproductions fail safely; valid names, imports, patterns, and frontmatter
remain compatible; no security fallback is silent.

## Milestone 2 — P0 localhost web security

**Goal:** retain the local-first model while preventing hostile browser pages
from invoking destructive operations.

- [ ] Centralize request-origin validation for every state-changing method.
- [ ] Validate `Host` against the configured loopback host and bound port.
- [ ] Reject `Sec-Fetch-Site: cross-site` mutation requests.
- [ ] Validate `Origin` when present and use strict `Referer` origin validation
  as a documented fallback.
- [ ] Define behavior for non-browser local clients so tests and integrations do
  not rely on accidental browser behavior.
- [ ] Require JSON for JSON mutation endpoints and reject unnecessary browser
  form posts.
- [ ] Decide whether a per-process mutation token is warranted; record the
  decision in an ADR instead of adding an undocumented secret.
- [ ] Reject non-loopback `--host` values by default, or require an explicit
  unsafe override with a separate documented threat model.
- [ ] Add CSP, `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, a
  restrictive Referrer Policy, and an appropriate cross-origin resource policy.
- [ ] Add tests for hostile `Origin`, `Referer`, `Sec-Fetch-Site`, `Host`,
  content type, and method combinations.
- [ ] Update `SECURITY.md` and `skills-manager-threat-model.md` after testing.

**Acceptance gate:** the reproduced cross-origin purge is rejected, same-origin
UI calls continue to work, loopback defaults remain intact, and every unsafe
HTTP method is covered by tests.

## Milestone 3 — Recovery, atomicity, and data integrity

**Goal:** make edits, sync, imports, overwrites, trash, and index repair safe in
the presence of crashes, concurrent requests, and partial I/O.

- [ ] Selectively integrate the approved snapshot design from issue #1:
  `<data>/snapshots/<scope>/<name>/`, newest-five retention, global and agent
  destinations, and CLI/UI restore integration.
- [ ] Rebase snapshot code onto the P0 name/root guards before accepting it.
- [ ] Selectively integrate the approved full-library migration design from
  issue #2: existing export/import flags, versioned manifest, skills + trash +
  templates, skip by default, and `--force` overwrite.
- [ ] Resolve overlap between migration code and the selected archive pipeline.
- [ ] Add atomic text writes using a sibling temporary file, flush/replace, and
  a documented durability policy.
- [ ] Preserve original content if validation, serialization, or replacement
  fails.
- [ ] Stage sync/overwrite operations and snapshot the destination before force.
- [ ] Define concurrency behavior for two CLI processes or UI requests touching
  the same skill.
- [ ] Add failure-injection tests between filesystem and SQLite operations.
- [ ] Make `doctor` report incomplete transactions, temporary files, stale
  snapshots, and index/filesystem drift.
- [ ] Verify backup restore using content hashes, not only row counts.

**Acceptance gate:** approved recovery behavior is present on `main`, interrupted
operations are recoverable or explicitly reported, and all baseline plus failure
injection tests pass.

## Milestone 4 — Root, consumer, and effective-state architecture

**Goal:** stop conflating physical directories with the agents that consume
them.

- [ ] Write an ADR for `SkillRoot`, `Consumer`, `ConsumerRootBinding`,
  `SkillInstance`, and `EffectiveSkill`.
- [ ] Inventory official discovery roots, precedence, recursion, reload, and
  client-specific metadata for supported agents.
- [ ] Correct the stale Cursor path and shared-root assumptions.
- [ ] Deduplicate roots by resolved physical path before counting or syncing.
- [ ] Model global, user, project, and nested project roots explicitly.
- [ ] Support recursive discovery only where the consumer actually does so.
- [ ] Represent read-only, writable, missing, and unsupported roots distinctly.
- [ ] Calculate effective resolution for a selected consumer and project.
- [ ] Show active, shadowed, divergent, unmanaged, invalid, disabled, and
  duplicated instances.
- [ ] Make sync operate on unique physical roots exactly once.
- [ ] Preserve unknown/client-specific frontmatter while separating portable
  standard fields from consumer extensions.
- [ ] Add content hashes, metadata hashes, provenance, and observed timestamps
  without changing SQLite schema until explicitly approved.

**Acceptance gate:** CLI and UI can explain physical state and effective
consumer state; shared roots are not double-counted or overwritten twice.

## Milestone 5 — Architecture deepening without a rewrite

**Goal:** reduce change risk in hotspot modules while keeping public behavior
stable.

- [ ] Extract archive inspection/extraction/commit logic from `store.py`.
- [ ] Extract atomic document I/O and root-containment primitives.
- [ ] Extract root discovery and consumer binding from `scopes.py`.
- [ ] Split `webapp.py` route dispatch, request security, serialization, and
  upload handling into cohesive internal modules or tables.
- [ ] Split `cli.py` parser construction, output rendering, and command handlers.
- [ ] Split `app.js` into no-build domain modules only after package-data tests.
- [ ] Preserve current public interfaces as compatibility adapters.
- [ ] Replace broad `except Exception: pass` in correctness-critical paths with
  explicit expected failures and diagnostics.
- [ ] Add complexity budgets for the largest functions and reject new growth in
  route/parser/store hotspots.

**Acceptance gate:** each extraction reduces coupling or increases testability;
all public behavior tests remain green; no speculative abstraction is added.

## Milestone 6 — Complete verification and regression defense

**Goal:** catch the classes of errors the original 47-test baseline missed.

- [ ] Add unit coverage for every public `Store` method and error branch.
- [ ] Add scope adapter contract tests shared by every root type.
- [ ] Add CLI tests for every command, alias, flag combination, JSON shape, and
  exit code 0/1/2/130.
- [ ] Add REST tests for every method/path/status/schema and malformed input.
- [ ] Retain executable smoke scripts while factoring reusable fixtures/helpers.
- [ ] Add parser round-trip and bounded-failure/property-style tests using the
  standard library only.
- [ ] Add archive corpus tests for tar, ZIP if accepted, traversal, links,
  duplicates, limits, manifests, and partial failures.
- [ ] Add search complexity and timeout tests.
- [ ] Add concurrency tests for simultaneous reads/writes and requests.
- [ ] Add wheel/sdist clean-install tests and package-data assertions.
- [ ] Add documentation link, source-symbol, stale-fact, and version checks.
- [ ] Generate verification summaries instead of hardcoding counts in docs.

**Acceptance gate:** every confirmed defect has a permanent test, all public
surfaces have contract coverage, and a clean checkout can build/install/run the
same artifact CI verifies.

## Milestone 7 — Browser UX, accessibility, and human-error reduction

**Goal:** make destructive and complex workflows understandable, reversible,
keyboard-usable, and robust at real viewport sizes.

- [ ] Add a dev-only real-browser harness; keep runtime dependencies unchanged.
- [ ] Capture console errors, warnings, unhandled rejections, failed requests,
  and unexpected navigation.
- [ ] Exercise every screen, modal, action, filter, scope, import/export path,
  undo path, empty state, loading state, and error state.
- [ ] Add keyboard-only coverage for search, menus, tabs, dialogs, forms, and
  destructive confirmations.
- [ ] Implement modal initial focus, focus trapping, Escape behavior, background
  inertness, and focus restoration.
- [ ] Add consistent accessible names, labels, descriptions, live regions, and
  error associations.
- [ ] Initially focus the least destructive action in destructive dialogs.
- [ ] Add an effective-scope/resolution preview before overwrite or sync.
- [ ] Integrate live Markdown preview only after renderer and XSS tests.
- [ ] Add shortcut help after the keyboard contract is stable.
- [ ] Test 320px, 400px, 640px, 900px, desktop, high zoom, reduced motion,
  contrast, and touch targets.

**Acceptance gate:** zero browser console errors in supported flows, no keyboard
trap, conforming modal focus behavior, and clear scope/target/recovery warnings.

## Milestone 8 — CI, packaging, and controlled release

**Goal:** make releases repeatable, reviewable, and difficult to publish with
stale or untested artifacts.

- [ ] Run CI on supported Python 3.10–3.14; add next-interpreter release-
  candidate coverage without silently changing support policy.
- [ ] Add Linux, macOS, and Windows path/archive coverage where practical.
- [ ] Pin GitHub Actions to reviewed commit SHAs or document an update policy.
- [ ] Add separate adversarial/security, package, browser, and documentation
  jobs with clear failure ownership.
- [ ] Build wheel and sdist once, test those exact files, and publish only them.
- [ ] Configure PyPI Trusted Publishing with a protected release environment;
  do not store a long-lived PyPI token in the repository.
- [ ] Add artifact provenance/attestation where supported.
- [ ] Create a GitHub Release for every published tag.
- [ ] Verify TestPyPI, PyPI, CLI help, web assets, and hermetic CRUD after
  publication.
- [ ] Remove or qualify PyPI badge/install claims until publication is real.

**Acceptance gate:** release is reproducible from a clean checkout, the tested
artifact is the published artifact, provenance is available, and post-publish
installation verification passes.

## Milestone 9 — Product differentiation after safety foundations

- [ ] Per-consumer “what this agent sees” view.
- [ ] Side-by-side and three-way skill diff.
- [ ] Managed, unmanaged, adopted, quarantined, and invalid ownership states.
- [ ] Provenance: source, revision, install mechanism, content hash, importer,
  and validation history.
- [ ] Update preview with changed files, metadata, risks, and rollback status.
- [ ] Quarantine untrusted imports before activation.
- [ ] Explainable static risk scan for scripts, links, tools, and suspicious
  instruction patterns.
- [ ] Registry browsing with source preview, provenance, scope selection,
  dry-run, and explicit trust confirmation.
- [ ] Evaluation harness with provider adapters and no mandatory runtime SDK.
- [ ] Revisit signed/team bundles only after the single-user trust model,
  quarantine, provenance, and recovery behavior are mature.

## Milestone 10 — Documentation truth and project hygiene

- [ ] Reconcile `AGENTS.md` with the final architecture and constraints.
- [ ] Correct stale GTK and legacy database-path claims in `docs/01-architecture.md`.
- [ ] Mark `docs/05-gui-plan.md` as historical only or remove it through an
  explicit documentation decision.
- [ ] Correct scope paths, shared-root semantics, test inventory, and current
  CLI/API signatures in owning docs.
- [ ] Update `.commandcode/settings.json`, which references deleted
  `skillsmgr/gui.py`, through a separate hygiene change.
- [ ] Reconcile `task.md`, `TODO.md`, `PLAN.md`, `ROADMAP.md`, `CHANGELOG.md`,
  and `docs/06-progress-log.md` without marking worktree-only code as shipped.
- [ ] Add a machine-checkable docs/source consistency command.
- [ ] Keep historical entries append-only while moving current truth into
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

- [ ] No confirmed P0 defects remain.
- [ ] All destructive paths validate names and roots before touching disk.
- [ ] Archive, parser, search, upload, and history costs are bounded.
- [ ] Cross-origin browser mutations are rejected.
- [ ] Every overwrite has tested recovery or an explicit irreversible policy.
- [ ] Filesystem/index drift is detectable and repairable.
- [ ] Physical roots and consuming agents are modeled separately.
- [ ] CLI, REST, UI, package, browser, and documentation contracts are tested.
- [ ] Accessibility-critical workflows pass keyboard/focus checks.
- [ ] CI tests exact release artifacts and supported environments.
- [ ] Release provenance and post-publish installation checks exist.
- [ ] Current documentation agrees with source and Git state.
- [ ] Every historical bug has a permanent regression test and recorded cause.