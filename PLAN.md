# Implementation Plan — Skills Manager World-Class Roadmap

**Plan version:** 2.1.0
**Prepared:** 2026-09-07
**Research annex:** 2026-09-09 (loop probes + ~200 sources; verdicts in §9
and §11). Docs-only change: no code, no locked-constraint changes.
**Repository:** `/home/uday-varmora/skills-manager`
**Baseline:** `main` at `667fabb`
**Execution backlog:** `/home/uday-varmora/skills-manager/TODO.md`

## Executive summary

`skills-manager` already has a valuable functional core: a dependency-free
Python CLI, a localhost Vue UI, a filesystem-first store, a rebuildable SQLite
index, agent-scope operations, validation, token estimates, import/export,
trash/restore, history, templates, and a meaningful smoke/unit-test baseline.

It is not yet world-class because ordinary happy-path tests do not cover several
high-impact failure classes. The current `main` branch has confirmed defects in
filesystem mutation containment, localhost browser request protection,
manifestless archive validation, wildcard complexity, and frontmatter recursion.
The current architecture also treats a physical directory, an agent, an
installation target, and an effective resolved skill as one concept even though
modern agent clients share roots and apply precedence rules.

The implementation strategy is therefore:

```text
reproduce → test → centralize invariants → fix P0 risks → add recovery
→ model roots/consumers → deepen modules → expand verification
→ harden UX/accessibility → release reproducibly → add differentiation
```

This is an incremental hardening and architecture-deepening plan. It is not a
rewrite, framework migration, database replacement, or feature-count race.

## 1. Product mission and outcomes

### Mission

Build the safest local control plane for portable AI coding-agent skills: one
tool that shows what exists on disk, what each agent can actually discover,
which copies differ, how much context they consume, where they came from, and
how to change or recover them safely.

### User outcomes

The product succeeds when a user can:

1. Discover all relevant skills without double-counting shared roots.
2. Understand the effective skill set for a selected agent and project.
3. Create, edit, import, sync, disable, trash, restore, and migrate without
   accidental data loss or path escape.
4. See validation, portability, provenance, divergence, and token-footprint
   explanations before making a consequential change.
5. Use the CLI or web UI interchangeably without semantic drift.
6. Recover from mistakes and interrupted operations.
7. Upgrade/install from a verified artifact with a reproducible release path.

### Non-goals

- Becoming a remote hosted multi-user service.
- Replacing every agent client’s own loader or configuration system.
- Adding dependencies merely to make the project look conventional.
- Adding AI-powered recommendations before correctness, provenance, and
  evaluation foundations exist.
- Rewriting stable code without evidence that a seam or interface is failing.

## 2. Ground truth and evidence

### Current `main` baseline

As of this plan, `main` has:

- 47 passing `unittest` tests.
- Passing `smoke_store.py` and `smoke_web.py`.
- Passing frontend syntax validation with `node --check`.
- A working CLI help surface and package metadata.
- A stdlib-only runtime design.
- A localhost web server defaulting to `127.0.0.1`.

These are useful regression signals, not proof of production safety.

### Confirmed current-main defects

The following were reproduced in isolated temporary directories or controlled
local requests and must be fixed before feature expansion:

| ID | Defect | Impact | Primary location |
|---|---|---|---|
| P0-SEC-001 | Mutation name/path traversal can delete outside the skills root | Data loss | `skillsmgr/store.py`, `skillsmgr/scopes.py` |
| P0-SEC-002 | Cross-origin browser request can invoke trash purge | Local data destruction | `skillsmgr/webapp.py` |
| P0-SEC-003 | Manifestless archive accepts invalid directory names | Invalid/unportable state | `skillsmgr/store.py` |
| P0-SEC-004 | Wildcard translation can exhaust CPU | Availability/DoS | `skillsmgr/search.py` |
| P0-SEC-005 | Deep frontmatter causes raw `RecursionError` | Reliability/error leakage | `skillsmgr/frontmatter.py` |

### Unmerged work

Two worktrees contain useful but competing implementations. The plan treats
them as evidence and candidate patches, not as truth:

- `/home/uday-varmora/skills-manager.worktrees/todo-plan-implementation`
  contains approved snapshots/full migration and adversarial hardening.
- `/home/uday-varmora/skills-manager.worktrees/milestone5-research-user-needs`
  contains ZIP/import hardening, stricter link handling, preview, and shortcut
  UX work.

The correct action is selective replay onto `main`, with failing tests first,
not a wholesale branch merge.

## 3. Hard constraints

These remain locked unless the maintainer explicitly approves a change:

1. The filesystem remains the source of truth.
2. SQLite schema and `SCHEMA_VERSION` remain unchanged during the initial
   hardening cycle.
3. The CLI runtime remains standard-library-only.
4. The web backend remains standard-library-only; Vue remains vendored; there is
   no runtime CDN or build requirement; loopback is the safe default.
5. No new CLI commands, CLI flags, or `Store` methods without an issue/decision
   and maintainer approval.

Additional engineering rules:

- User data is more important than convenience or migration speed.
- Security controls fail closed; no silent weakening fallback.
- Every bug becomes a permanent regression test.
- Every destructive operation is validated before path construction.
- Every changed public behavior is documented in the owning file.
- Every release artifact is built once, tested, and then published unchanged.

## 4. Target architecture

### 4.1 Conceptual system

```text
                 ┌───────────────────────────────┐
                 │ CLI adapter                   │
                 └──────────────┬────────────────┘
                                │
                 ┌──────────────▼────────────────┐
                 │ Application/domain operations │
                 │ validation · recovery · diff  │
                 └───────┬──────────┬─────────────┘
                         │          │
          ┌──────────────▼───┐  ┌──▼────────────────┐
          │ Filesystem layer │  │ Index adapter     │
          │ source of truth  │  │ SQLite cache      │
          └──────────┬───────┘  └─────────┬─────────┘
                     │                    │
               SKILL.md trees       rebuild/resync
                     │
          ┌──────────▼───────────────────────┐
          │ Root/consumer resolution model   │
          │ physical roots → consumer views  │
          └──────────┬───────────────────────┘
                     │
                 ┌───▼──────────────────────────┐
                 │ HTTP adapter + Vue UI         │
                 │ localhost security + a11y     │
                 └───────────────────────────────┘
```

### 4.2 Root/consumer vocabulary

The current `Scope` abstraction is useful as a compatibility facade but too
coarse as the long-term domain model.

#### `SkillRoot`

A unique physical directory that may contain skills. It has a stable
identifier, resolved path, user/project/system level, writable/read-only state,
discovery depth, symlink policy, ownership/provenance, and recovery policy.

#### `Consumer`

An agent/client that discovers skills, such as Claude Code, Codex, Cursor,
OpenCode, Gemini CLI, Copilot/VS Code, or Command Code.

#### `ConsumerRootBinding`

Describes which consumer reads which root, at what precedence, for which project
context, and with which compatibility/native semantics.

#### `SkillInstance`

One physical skill document in one root, including name, content hash, metadata
hash, validity, enabled state, provenance, and observed timestamps.

#### `EffectiveSkill`

The instance a selected consumer would actually use after applying its root
precedence and duplicate/shadowing rules.

This model prevents shared `.agents` roots from being counted as independent
copies and makes “sync to all” a physical-root operation rather than a blind
agent-label loop.

### 4.3 Compatibility strategy

Do not immediately break the current CLI/API vocabulary. Introduce the richer
model behind adapters:

- Existing `--scope` values continue to resolve through a compatibility map.
- Existing Store methods remain stable while internal operations move behind
  safer primitives.
- Effective-resolution behavior is first exposed through diagnostics or an
  approved extension to existing output, not an unapproved command explosion.
- Any SQLite representation change waits for an explicit schema ADR and
  maintainer approval.

## 5. Execution phases and dependencies

```text
Phase 0  Baseline + branch archaeology
   │
   ├──► Phase 1  Filesystem/archive/parser/search P0 hardening
   │       │
   │       └──► Phase 2  Localhost HTTP mutation security
   │                    │
   │                    └──► Phase 3  Recovery + atomicity
   │                                 │
   │                                 ├──► Phase 4  Root/consumer model
   │                                 │        │
   │                                 │        └──► Phase 5  Module deepening
   │                                 │
   │                                 └──► Phase 6  Complete verification
   │                                          │
   │                                          └──► Phase 7  Browser UX/a11y
   │                                                   │
   │                                                   └──► Phase 8  Release engineering
   │                                                            │
   │                                                            └──► Phase 9  Differentiation
   │
   └──► Phase 10 Documentation truth runs continuously,
            with a formal reconciliation gate before release.
```

Phase 6 may begin test scaffolding in parallel with Phases 1–3, but a phase is
not complete until its predecessor’s acceptance gate passes. Documentation work
is continuous and must not be postponed until the end.

## 6. Detailed phase plan

### Phase 0 — Baseline and integration freeze

#### Steps

1. Capture the current-main baseline and all five P0 reproductions.
2. Compare both worktrees against `main`.
3. Import candidate regression tests without importing candidate fixes.
4. Produce a selective replay map and conflict list.
5. Freeze feature expansion until P0 gates pass.

#### Required output

- A dated evidence log.
- Failing regression tests for each P0 defect.
- A branch integration matrix.
- A list of files that must not be touched in the current change.

#### Acceptance criteria

- Reproductions are deterministic and hermetic.
- The test suite fails for the intended defect, not because of environment
  leakage.
- Current valid behavior is captured before fixes.

### Phase 1 — Filesystem, archive, parser, and search safety

#### Design

Use defense in depth:

```text
input → canonical validation → root containment → bounded operation
      → staged temp state → content validation → atomic commit
```

Do not rely on a single regex, archive library option, or caller-side check.

#### Acceptance criteria

- No user-controlled name can escape its intended root.
- No invalid archive name can become a destination directory.
- No archive member can create an unsupported filesystem object.
- No archive/parser/search input can exceed declared resource bounds silently.
- Valid Agent Skills documents remain readable and writable.
- Invalid input returns `StoreError`/`FrontmatterError` or a clean CLI/REST
  error, never a raw traceback.

### Phase 2 — Localhost web security

#### Design

Loopback is a deployment default, not a complete browser trust boundary. The
server must distinguish same-origin UI calls from cross-site browser attempts.

State-changing request policy:

1. Validate method and route.
2. Validate Host.
3. Validate Fetch Metadata when available.
4. Validate Origin/Referer when available.
5. Validate content type and body schema.
6. Apply domain/path authorization and mutation.

The policy must explicitly define how local non-browser clients call the API so
tests and supported integrations do not depend on accidental browser behavior.

#### Acceptance criteria

- Cross-site destructive requests fail before the handler reaches the Store.
- Same-origin UI operations continue to pass.
- No non-loopback bind is silently treated as safe.
- Response headers reduce framing, MIME confusion, and unintended cross-origin
  behavior.

### Phase 3 — Recovery and atomicity

#### Snapshot policy

Implement the approved issue #1 design only after revalidating its assumptions:

- newest five snapshots per scope/name;
- snapshots stored under a controlled data root;
- snapshots created before edit and force-overwrite operations;
- global and agent-scope destinations supported;
- restore validates target and snapshot identifier;
- history records snapshot creation/restoration;
- pruning is deterministic and tested.

#### Migration policy

Implement the approved issue #2 design only after the archive pipeline is
hardened:

- existing `export`/`import` flags rather than an unapproved new command;
- versioned manifest;
- skills, trash, and templates included;
- agent scopes and snapshots excluded unless separately approved;
- skip by default;
- explicit `--force` overwrite;
- complete preflight before commit;
- clear report of imported/skipped/rejected entries.

#### Atomicity policy

Every file mutation must preserve the prior valid state if the process exits or
an I/O error occurs during the write. The SQLite index must be repairable from
the filesystem after any interrupted operation.

#### Acceptance criteria

- Interrupted edit/import/sync tests leave either the old state or the complete
  new state, never an unexplained partial file.
- `doctor` identifies and explains drift.
- Snapshot restore and migration round trips are verified by content hash.

### Phase 4 — Root/consumer/effective-state model

#### Discovery research tasks

- Confirm each client’s current user/project roots, recursion, precedence,
  shared-root aliases, reload behavior, and client-specific metadata.
- Store that knowledge in descriptors with a review date and source reference.
- Distinguish facts from assumptions in documentation.

#### Migration sequence

1. Normalize current scope descriptors into unique physical roots.
2. Add consumer bindings behind the existing scope facade.
3. Add duplicate/shadow/effective diagnostics.
4. Update sync to target physical roots.
5. Expose effective resolution in CLI/REST/UI after contract approval.

#### Acceptance criteria

- Shared physical roots appear once in aggregate counts.
- A user can see why a skill is active, shadowed, disabled, or divergent.
- Sync never copies to the same physical directory twice.
- Unknown consumer-specific metadata survives round trips.

### Phase 5 — Architecture deepening without a rewrite

#### Hotspot order

1. `skillsmgr/store.py` — filesystem/index/recovery/archive responsibilities.
2. `skillsmgr/webapp.py` — route methods and repeated enrichment/error handling.
3. `skillsmgr/scopes.py` — global/agent behavior and path semantics.
4. `skillsmgr/cli.py` — parser construction and output mixed with operations.
5. `skillsmgr/webui/app.js` — state, transport, rendering, and workflows.
6. `skillsmgr/frontmatter.py` — custom parser complexity and resource bounds.

#### Refactoring rule

Only extract a module when it creates a deep, testable interface that hides
meaningful policy. Do not create wrappers that merely rename existing calls.
Preserve compatibility adapters and run contract tests after each extraction.

#### Acceptance criteria

- The largest functions become smaller without moving complexity into equally
  opaque helpers.
- Safety-critical policy has one authoritative implementation.
- Tests can exercise policy through stable interfaces.
- No user-visible behavior changes without a deliberate contract update.

### Phase 6 — Verification system

#### Test layers

```text
pure unit tests
  → contract tests
  → adversarial/resource-bound tests
  → Store/filesystem integration
  → real HTTP smoke
  → real-browser UX/a11y
  → clean package install
  → cross-platform CI
  → release artifact verification
```

#### Required test families

- Name/path/root containment and symlink/link-target behavior.
- Archive traversal, links, limits, duplicates, malformed manifests, ZIP if
  accepted, and interrupted commits.
- Frontmatter valid corpus, round-trip, malformed, and nesting exhaustion.
- Search ranking, wildcard limits, and complexity.
- Store CRUD, trash, restore, snapshots, migration, index drift, and history.
- Scope/root discovery, duplicate physical roots, precedence, and sync.
- CLI output/exit codes and REST statuses/schemas.
- Browser console, keyboard, focus, responsive, and destructive workflows.
- Wheel/sdist installation and package-data completeness.
- Documentation links, stale facts, source symbols, and version alignment.

#### Acceptance criteria

- Every confirmed bug has a regression test.
- No test relies on the developer’s real home directory or live agent roots.
- Every server test shuts down and closes its server.
- Failure messages identify the violated invariant without leaking unnecessary
  internals.

### Phase 7 — Browser UX and accessibility

#### Design priorities

The UI manages potentially destructive filesystem operations. Its most important
UX job is not visual novelty; it is preventing an incorrect target, scope, or
overwrite from being misunderstood.

Required interaction details:

- Show source root, target root, consumer, and effective result.
- Explain overwrite and rollback before confirmation.
- Use undo for reversible trash operations.
- Use explicit confirmation for purge and force sync.
- Preserve selection and focus after refreshes and asynchronous responses.
- Keep loading/error states local to the operation that failed.

#### Accessibility requirements

- Dialog focus enters the dialog, stays within it, and returns to the opener.
- Background content is inert while a modal is active.
- Destructive dialogs default focus to cancel/safer action.
- Every control has an accessible name and state.
- Live regions announce success/error/undo availability.
- Keyboard shortcuts never override text editing unexpectedly.
- Reduced motion, zoom, contrast, and narrow widths are tested.

#### Acceptance criteria

- Real-browser tests report zero console errors in the supported workflow.
- Keyboard-only users can complete create/edit/disable/trash/restore/import and
  cancel every destructive action.
- No modal traps focus or leaves focus in a removed DOM subtree.

### Phase 7 implementation evidence (2026-09-09)

The browser/accessibility gate is now implemented without changing the locked runtime constraints:

- CLI parser/handler/output seams are split into `cli_parser.py`, `cli_handlers.py`, and `cli_output.py`; `cli.py` is a compatibility adapter.
- The no-build frontend has `domain.js` for transport/formatting/frontmatter/escaped Markdown and `app.js` for Vue workflows.
- Dialogs have labelled focus lifecycle, Tab trapping, Escape, safer destructive defaults, background inertness, focus restoration, and live status/error announcements. The editor previews escaped Markdown and sync previews source/targets/overwrite/rollback behavior.
- `browser_harness.py` uses only Python stdlib plus an already installed system Chrome CDP endpoint; it captures runtime/console/network failures and checks 320/400/640/900/1280px viewports. It passed with zero errors and no horizontal overflow.

### Phase 8 — CI, packaging, and release

#### CI design

Required jobs:

1. Compile and static syntax.
2. Unit/contract tests.
3. Store/web smoke tests.
4. Adversarial security tests.
5. Documentation consistency.
6. Clean package build/install.
7. Browser/a11y tests when the approved harness is available.
8. Cross-platform path/archive matrix.

Use Python 3.10–3.14 as the supported matrix after confirming project policy;
test the next release candidate separately rather than silently changing support.

#### Release design

```text
tag → protected release workflow → build once → test exact artifacts
     → attest/provenance → manual environment approval → publish
     → clean install verification → GitHub Release
```

Use PyPI Trusted Publishing instead of a long-lived repository secret. Keep the
release environment protected and require approval for publication.

#### Acceptance criteria

- A clean checkout builds the same wheel and sdist that CI tests.
- Package data includes `skillsmgr/webui/` and the vendored Vue file.
- Published package installs in a clean environment and runs CLI/UI smoke tests.
- Release notes, version, tag, package metadata, and badges agree.

### Phase 9 — Product differentiation

Only after Phases 1–8 are green (research verdicts 2026-09-09; the
read-only `insights.py` foundation for the first seven bullets is
shipped, runtime exposure stays approval-gated):

- effective per-consumer views — observed views shipped with
  `effective_state: unresolved`; the precedence resolver is DEFERRED.
  Per-consumer precedence is not global (Claude Code enterprise >
  personal > project > plugins; Gemini built-in < extension < user <
  workspace; OpenCode upward CWD-to-root; Cursor nested file-scoping;
  Command Code ≤10 levels to `$HOME`). Close the Codex/Command-Code/
  Claude `[?]`s against primaries first, then propose a read-only
  `doctor --explain CONSUMER --project DIR` diagnostic, derived at
  read time, persisting nothing;
- provenance and content hashes — observations shipped, persistence
  approval-gated (schema frozen);
- safe adoption of unmanaged skills — via the approved
  explain/diff/preview seams, not silent mutation;
- explainable static risk findings — `risk_scan()` shipped (9 findings
  on the hostile probe skill);
- quarantine and approval workflow — `quarantine_plan()` stage-only
  shipped; activation approval-gated;
- side-by-side/three-way diff — `diff_skills()`/`diff_three_way()`
  shipped (conflicts hold base);
- update preview and rollback — `update_preview()` shipped (risks plus
  rollback flag from snapshot list);
- registry discovery with trust/provenance — DEFER network
  browse/fetch: `skills.sh` reads need Vercel OIDC bearer auth
  (unsuitable for a local-first stdlib tool); keep the offline
  `registry_preview()` trust gate, map ids through existing `install`
  dry-run, link (don't proxy) the Socket/Snyk/Trust-Hub audit surface;
- provider-neutral skill evaluation — ADVISORY-ONLY stays: deterministic
  stdlib `eval_plan()`/`eval_score()` shipped; no in-product model
  backend, file-based results per the official evaluating-skills guide,
  verdicts never block installs (LLM-judge bias is systematic);
- optional signed/team bundles — DEFERRED: stdlib has HMAC but no
  asymmetric signing; needs a trust/key-distribution ADR plus a
  threat-model delta first (minisign-style, TUF delegation, in-toto, and
  SLSA/Sigstore models surveyed).

These features should make the manager trusted and understandable, not merely a
larger installer front-end.

## 7. Branch integration method

### Never do this

- Do not merge either worktree wholesale.
- Do not mark a feature complete because another branch’s smoke tests pass.
- Do not copy branch docs without checking current source and dates.
- Do not combine archive implementations until their security invariants are
  compared.

### Required replay sequence

1. Create a clean branch from current `main`.
2. Add adversarial tests from the security worktree only.
3. Confirm the expected failures.
4. Implement the smallest centralized fix.
5. Run targeted tests and all baseline tests.
6. Re-review neighboring paths for the same invariant.
7. Add snapshot/migration tests from issues #1/#2.
8. Replay selected recovery code only after P0 fixes.
9. Resolve archive and docs overlap manually.
10. Add ZIP/UX work only after security and recovery gates.
11. Run full verification and inspect the final diff.

### Per-phase quality gate

Every phase requires:

- implementation result;
- targeted test output;
- full verification output;
- security/error-path review;
- docs update list;
- Git status/diff review;
- explicit remaining-risk statement.

## 8. Error-prevention operating system

### Before coding

- Identify the user outcome and invariant.
- Read the owning documentation and current source.
- Search for all callers and alternate surfaces.
- Classify the decision as reversible or expensive to reverse.
- Write the smallest failing reproduction.

### During coding

- Centralize the invariant.
- Keep filesystem containment independent from input regex validation.
- Keep security controls fail closed.
- Avoid broad exception swallowing.
- Preserve unknown metadata unless the contract says otherwise.
- Keep operations idempotent or report non-idempotence explicitly.
- Maintain a recovery path for destructive writes.

### Before declaring done

- Run the new regression test.
- Run neighboring adversarial tests.
- Run applicable unit, smoke, CLI, REST, browser, and package checks.
- Re-run in a fresh temporary data directory.
- Confirm no live user/agent directory was touched.
- Inspect `git status --short` and `git diff --check`.
- Check docs/source/version consistency.
- Record exact dates, commands, and remaining uncertainty.

## 9. Risk register

| Risk | Likelihood | Impact | Treatment |
|---|---:|---:|---|
| Mutation path escape | Medium | Critical | P0 centralized name + containment guards |
| Cross-origin localhost mutation | Medium | High | P0 request-origin policy and tests |
| Malicious archive | Medium | High | Preflight, limits, type/path validation, staged commit |
| Parser/search exhaustion | Medium | Medium/High | Explicit complexity budgets and bounded algorithms |
| Partial filesystem/index update | Medium | High | Atomic writes, snapshots, doctor, failure injection |
| Shared-root double counting | High | Medium | Root/consumer/effective-state model |
| Supply-chain install execution | Low/Medium | High | Dry-run default, explicit trust, provenance, docs |
| Stale documentation | High | Medium | Machine-checkable consistency gate |
| Accessibility regression | Medium | Medium | Real-browser keyboard/focus tests |
| Untested release artifact | Medium | High | Build-once/test-exact-artifact workflow |
| Over-refactoring | Medium | Medium | Incremental deepening and compatibility contracts |

## 10. Decision records required

Create or update ADRs before implementing these decisions:

1. Root/consumer/effective-state domain model.
2. Localhost mutation-origin policy and non-loopback behavior.
3. Archive format support and safe extraction contract.
4. Snapshot retention, naming, and restore semantics.
5. Full migration archive scope and force behavior.
6. Client-specific metadata preservation and portability profiles.
7. Optional browser test tooling under the no-runtime-dependency constraint.
8. Release/trusted-publishing and artifact provenance policy.
9. Evaluation harness provider/credential/isolation policy.
10. Team-sharing trust and key-distribution model, if pursued.

## 11. Research basis

The roadmap is based on repository evidence plus current primary documentation
and security guidance. These references should be rechecked when implementing a
phase because client discovery behavior and tooling specifications change.

### Agent skill format and authoring

- Agent Skills specification: `https://agentskills.io/specification`
- Agent Skills best practices: `https://agentskills.io/skill-creation/best-practices`
- Agent Skills description guidance: `https://agentskills.io/skill-creation/optimizing-descriptions`

### Client discovery and portability

- Gemini CLI skills: `https://geminicli.com/docs/cli/skills/`
- Cursor skills: `https://cursor.com/docs/context/skills`
- OpenCode skills: `https://opencode.ai/docs/skills/`
- Codex skills: `https://developers.openai.com/codex/skills/`
- GitHub Copilot custom instructions/skills: `https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions`

### Secure parsing, local web behavior, and accessibility

- Python `tarfile`: `https://docs.python.org/3/library/tarfile.html`
- OWASP CSRF Prevention: `https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html`
- W3C Fetch Metadata specification: `https://www.w3.org/TR/fetch-metadata/`
- WAI-ARIA modal dialog pattern: `https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/`

### Packaging and supply-chain integrity

- PyPA Trusted Publishers: `https://docs.pypi.org/trusted-publishers/`
- GitHub artifact attestations: `https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations`
- Python Packaging User Guide: `https://packaging.python.org/`

### 2026-09-09 research annex (loop probes + ~200 sources)

Probes (hermetic, isolated temp dirs, stdlib only, no product-code
changes; scripts kept in `/tmp/probe_*.py`, outside the repo):
link-warning matrix, zip hostile-member plus symlink-bit behavior, tar
hostile-member rejection, wildcard-bounds timing, frontmatter
limits/round-trip, eval/risk/registry/quarantine behavior, effective
boundary, REST fail-closed matrix (403/415/400s), stdlib signing
reality. Baseline held green (301 unittest, docs, complexity gates).

### 2026-09-10 final-verdict round (maintainer-authorized; all 14 FINAL)

Method: 4 hermetic re-probe agents (archive ZIP/TAR, parser/search/links,
REST/effective/insights, release/docs/worktrees/encoding/signing/atomicity;
stdlib only, `/tmp` probes, zero product-code changes) + 8-family survey
workflow (309 quoted URL entries, 194 unique sources) + 3 targeted
`web_search` batches. New decisive evidence: Snyk ToxicSkills audit
(3,984 skills: 13.4% critical, 76 confirmed malicious — hardens registry
DEFER); CVE-2025-4138 filter-bypass cluster (independent validator is the
real defense — hardens tar-refusal REJECT); 68 legitimate cross-skill
relative links measured in `~/.claude` + `~/.codex` (promotion would break
them — hardens link REJECT); `dist/` wheel missing `domain.js`
(stale-artifact pre-release fix); `git merge-base` shows 3 of 5 worktree
dirs already merged-but-stale, 2 genuinely unmerged; single poisoned
SKILL.md (latin-1 byte) breaks store-wide scans via `loader.py:31`
(issue #13, fix seam identified, no code). Baseline held green throughout
(301 unittest, both smokes, compile, frontend, docs, complexity, diff).

Verdicts distilled into `TODO.md` (Milestone 4 note, Deferred
section, Milestone 11 queue), `task.md` Milestones 5 and 31, and PLAN
§9 above. Standing answers for a new session:

- ZIP import: APPROVE as a scoped `import` extension (red-first
  malicious-ZIP corpus; ~90% of tar policy ports verbatim; new work is
  the symlink-bit check, a zip manual extractor, and the bomb ratio).
- Tar-fallback refusal: REJECT (keep feature-detect plus guarded manual
  extractor; CI matrix stays 3.10–3.14; filter-bypass CVEs prove the
  independent validator is the real defense).
- Link warning→error: REJECT (keep warning plus `risk_scan()`; 2026-09-10
  walk: 68 legitimate sibling-skill/monorepo-relative links in
  `~/.claude` + `~/.codex` would break under promotion, plus regex
  artifacts).
- Registry: DEFER network (OIDC-gated API); staged offline→passthrough
  path only.
- Eval: ADVISORY-ONLY, file-based, never blocking.
- VS Code extension: separate repo; no backend changes here.
- Desktop wrapper: REJECT as product direction (browser canonical).
  Recorded on issue #9 2026-09-09 with constraint-4 + harness evidence.
- Live preview + cheatsheet: CLOSED 2026-09-09 (issue #10 commented with
  file/line evidence and closed; zero work remained).
- Team sharing: DEFERRED pending a trust/key-distribution ADR plus a
  threat-model delta.
- Effective resolution: keep `unresolved`; the three `[?]`s were CLOSED
  2026-09-09 in `docs/12-agent-root-discovery-2026-09-08.md` v1.1.0
  against primary sources (Codex `.agents/skills/` REPO/USER/ADMIN/SYSTEM
  + no-merge per `https://learn.chatgpt.com/docs/build-skills`; Command
  Code six-way order + Duplicate-names + `/skill:<name>` + live reload
  per `https://commandcode.ai/docs/skills`; Claude triple-winner +
  both-load exceptions per `https://code.claude.com/docs/en/skills`).
  Next: the read-only `doctor --explain CONSUMER --project DIR`
  diagnostic needs its own issue/ADR approval (locked constraint 5); L2
  ZIP remains the only approval-gated code item. (2026-09-09 round 2:
  the diagnostic proposal is now filed as issue #12; round 3 re-verified
  every probe family green with zero product-code changes. L2/Diagnostic
  both await maintainer approval — no code until then.)

External products are used to understand user expectations and portability
patterns, not to justify copying their architecture. Repository constraints,
measured failures, and user-data safety remain the decision authority.

## Milestone 49 — Approval-safe verification campaign (2026-09-10)

Round 17 completed ten read-only, approval-safe verification tasks over the
latest backlog: baseline ladder, installed-skill catalog audit, P0 fail-closed
rotation, issue #13 characterization, release-artifact hygiene, REST security,
resource bounds, CLI contracts, browser/live checks, and documentation hygiene.
No product code, SQLite schema, dependencies, release artifacts, tags, or live
user skill roots were changed. The stale ignored `dist/` wheel remains a known
pre-release finding because it predates `domain.js`; the existing release
workflow must build once from a clean tree before publication. ZIP support,
the effective-resolution diagnostic, and issue #13 remediation remain gated by
explicit decisions that were not available in this session.

## 12. Final definition of done

The world-class baseline is complete only when:

- P0-SEC-001 through P0-SEC-005 are fixed and permanently tested.
- All filesystem mutations validate names and containment before touching disk.
- Archive, parser, search, upload, and history operations have explicit bounds.
- Cross-origin destructive localhost requests are rejected.
- Recovery and atomicity behavior is tested under injected failure.
- Physical roots and consuming agents are represented separately.
- CLI, REST, UI, package, browser, and documentation contracts agree.
- Accessibility-critical workflows pass keyboard/focus verification.
- CI tests supported environments and exact release artifacts.
- Publishing uses controlled credentials/provenance and post-publish verification.
- Every known bug has a cause, a regression test, and a prevention rule.
- A clean temporary run completes without touching live skill roots.

## 13. Immediate next implementation action

Milestone 11 queue order still governs (L2 ZIP and issue #12 both await
maintainer approval — no code until then). The Phase 0–1 history below is
complete on `main` and retained as the audit trail:

1. ~~Capture baseline evidence~~ — done (`docs/09-baseline-evidence-2026-09-07.md`).
2. ~~Add the five failing P0 reproductions~~ — done (regression tests in
   `tests/test_path_safety.py`, `tests/test_webapp.py`,
   `tests/test_archive_contracts.py`, `tests/test_frontmatter_contracts.py`,
   `tests/test_search_contracts.py`; re-verified green in round 6).
3. ~~Review the unmerged adversarial branch tests~~ — done
   (`docs/10-worktree-integration-comparison-2026-09-08.md`,
   `docs/11-integration-status-2026-09-08.md`).
4. ~~Fix P0-SEC-001 first~~ — done 2026-09-08 (traversal guards + victim
   regression).
5. ~~Phase 1 acceptance gate~~ — green (round-6 replay: 5/5 P0 replays
   fail-closed, compatibility held).