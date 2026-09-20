# Progress Log — Skills Manager

**Version 0.1.0**

**AI manifest**: Dated, append-only record of changes, decisions, and bugs for skills-manager. Read before/after every session (docs/README.md reading order). Facts flagged stale here are corrected in the owning doc. Newest entry on top.

**Verification (current tree, 2026-09-20):** 787 unittest tests pass; Store/Web
  smoke tests, docs, complexity (238 functions), frontend syntax, compilation,
  CLI help, five-viewport browser harness, vendored Vue source hash, and diff
  checks pass. Optional package artifact coverage is `UNAVAILABLE` because
  `python3 -m build` is not installed. Earlier counts in dated entries remain
  historical.

## 2026-09-20 — Execution-queue reconciliation

Reconciled the active checklist with the shipped tree. The historical Milestone
11 L2 line now records the approved ZIP-import slice as complete, and the stale
deep-audit T11 line now records the current tracker result: no open findings,
with `SEC-4` retained as the documented accepted trade-off. External screenshots
and consented human usability sessions remain explicitly open because local
automation cannot provide that evidence.

## 2026-09-20 — Current plan action refresh

Updated `PLAN.md` §13 so its live next-action statement matches the current
delivery state: ZIP import is shipped and `doctor --explain` is shipped as a
read-only diagnostic. The historical Phase 0–1 checklist remains unchanged;
future provider-backed evaluation, hosted coordination, and human research stay
approval- or evidence-gated.

## 2026-09-20 — Session-context truth refresh

Refreshed `docs/SESSION-CONTEXT.md`'s current Milestone 11 summary to record the
published and verified `skill-control-plane` 1.0.1 release, the shipped ZIP
slice, and the intentionally deferred provider-backed work. The cache now also
names external screenshots and consented participant sessions as human-gated
instead of implying they are automated deliverables.

## 2026-09-20 — Product-baseline evidence owner refresh

Updated `docs/16-product-baseline-2026-09-18.md` to include the current
synthetic all-fixture report at
`.specs/evidence/del-11-2026-09-20-run3/baseline.json`, its expected
0/12/4/2/2,000 row shapes, and the separate status of local viewport PNGs.
The document continues to leave participant research explicitly unclaimed.

## 2026-09-20 — Current-tree verification close-out

Ran the complete current-tree ladder sequentially: `python3 -m unittest
discover -s tests` (**787 tests OK**), `smoke_store.py`, `smoke_web.py`, Python
compilation, `check_docs.py`, `check_complexity.py` (**238 functions**), both
frontend `node --check` probes, CLI help, `git diff --check`, and the five
browser-harness viewports (320/400/640/900/1280; no errors or overflow). The
vendored Vue hash check passed. `check_package_data.py` honestly reported
`UNAVAILABLE` only for optional artifact inspection because `python3 -m build`
is not installed.

## 2026-09-20 — DEL-11 local evidence refresh

Re-ran the current-build developer browser harness with
`--screenshots-dir .specs/evidence/del-11-2026-09-20-run3`. The 320, 400, 640,
900, and 1280 px probes all reported the expected `Skills Manager` title, zero
console/runtime/network failures, and no horizontal overflow. The five PNGs
are dated local automated evidence, and the 320 px and 1280 px states were
visually inspected. A fresh `baseline_harness.py --fixture all` run also wrote
`baseline.json` in the same directory with the expected 0/12/4/2/2,000 row
shapes and no telemetry. This does not satisfy the separate
external-screenshot or consented-participant gates; no human evidence or
adoption claim is made.

## 2026-09-20 — DEL-11 local screenshot evidence

Extended the dev-only Chrome/CDP browser harness with an opt-in
`--screenshots-dir` switch. The fresh current-build run wrote five local PNGs
under `.specs/evidence/del-11-2026-09-20-run2/` for 320, 400, 640, 900, and
1280 px viewports. All five probes reported the expected title, zero console,
runtime, and network failures, and no horizontal overflow. The screenshots
are dated local automated evidence, not external communication or participant
evidence. Playwright was not installed; no runtime dependency was added.

## 2026-09-20 — DEL-08 review/commit split

Split the existing registry fetch path into a networked prepare/review
transaction and a separate no-network commit transaction. The first CLI or
`POST /api/install` fetch validates and risk-inspects the complete snapshot,
then writes a private 0700/0600, 24-hour, credential-free review artifact
without touching the managed Store. The second request supplies the review id
and explicit trust confirmation, revalidates the snapshot, installs through
the existing `Store.add()` seam, writes provenance, and marks the review
single-use. Review artifacts reject credential-shaped inspection fields and
preserve remote hash evidence across frontmatter normalization.

No new command, Store method, SQLite schema, dependency, or network request is
used during commit. Focused registry contract and CLI/REST integration tests
pass; the final verification ladder is rerun after the remaining queued tasks.

## 2026-09-20 — DEL-09 Git/review/apply integration

Extended `skillsmgr.backup_sync` beyond pure planning with an explicit local
Git seam. `git_remote_info()` and `git_fetch()` use a trusted Git executable,
disable terminal prompting, and delegate authentication to existing Git
credential helpers or SSH agents without accepting a token or writing a
credential. Remote URLs containing credentials are rejected. The review seam
stores bounded manifests, plan, target, candidate digest, and Git revision in
owner-only 24-hour `sync-reviews` artifacts; apply rechecks the candidate,
rejects unresolved conflicts, requires explicit approval and a snapshot root,
and delegates atomic replacement/rollback evidence to `source_lock.py` before
marking the review single-use.

No CLI command, Store method, SQLite schema, or runtime dependency was added.
Focused DEL-09 contracts now cover local Git fetch, credential redaction,
private review permissions, revalidation, apply, snapshot, and replay refusal.

## 2026-09-20 — DEL-10 ADR-004 policy resolution

Resolved ADR-004 §6 without changing runtime behavior: team integrity uses the
stdlib HMAC-SHA256 shared-secret model only; distribution is an offline file
passed through existing approved channels; and signed metadata is content-only
(member paths, digests, and format fields), excluding eval results, review
notes, participant data, identity claims, approval labels, and telemetry. The
honest guarantee remains group authenticity/integrity, not named-person
identity or safety. The existing `bundles.py` evidence helper remains narrow;
archive signing/import, key transport, approval state, and team governance are
still unimplemented and require a separate implementation review.

Updated ADR-004, the threat model, roadmap, session context, module/index
references, task record, and this log. No command, Store method, schema,
dependency, or product mutation was added.

## 2026-09-20 — DEL-07 review/apply/rollback workflow

Extended `skillsmgr.source_lock` from read-only evidence to an explicit,
filesystem-owned transaction seam. Bounded `.skillsmgr-source-lock.json`
sidecars are validated, atomically written with owner-only permissions, and
excluded from whole-tree content hashes. `review_local_update()` returns a
review id over the candidate/current hashes, diff, source identity, and exact
physical target without mutation. `commit_local_update()` requires that fresh
review, explicit target containment, `approve=True`, and an explicit snapshot
root; it rechecks under the existing cross-process mutation lock, snapshots the
complete current tree, atomically swaps the staged candidate, and reports a
rollback path. `restore_source_snapshot()` requires a separate explicit
approval.

No CLI command, Store method, SQLite schema, network request, dependency, or
REST route was added. The focused source-lock contracts now cover sidecar
drift, stale review rejection, snapshot/apply, and rollback.

Focused verification: `tests/test_source_lock_contracts.py` — 10 tests pass;
compile and `git diff --check` pass. The full ladder is rerun at the end of the
serial task sequence.

## 2026-09-19 — DEL-09 backup/sync dry-run planner

Added `skillsmgr.backup_sync`, a pure stdlib planner for bounded canonical
manifests, exact local/remote deltas, three-way conflict decisions, and
retryable interrupted-sync evidence. Source labels and member paths reject
credentials, traversal, and unsafe forms; default conflicts remain review
only; remote deletion requires explicit recovery. The module does not invoke
Git, contact a remote, read credentials, write files, mutate SQLite/Store, or
add a CLI surface. ADR-009, module/architecture/index docs, task tracking, and
hermetic contracts were added.

Focused verification: `tests/test_backup_sync_contracts.py` — 5 tests pass.
Git/remote/auth/apply integration remains deferred pending explicit decisions.

## 2026-09-19 — DEL-10 offline team-integrity foundation

Added `skillsmgr.bundles`, a pure stdlib helper for bounded deterministic
version-1 member manifests, SHA-256 manifest identity, and detached
HMAC-SHA256 evidence. Verification distinguishes valid, wrong-key, tampered,
revoked, and malformed-signature states while stating the only guarantee is
shared-secret group integrity. No key is read from the environment or stored;
there is no archive, import/export integration, distribution, approval state,
CLI/REST/Store/SQLite change, or mutation. The docs-symbol gate also received a
hyphenated filename boundary guard exposed by the new `bundles.py` module.
ADR-004 now records this narrow
foundation while keeping its crypto, distribution, and metadata decisions
open.

The warm session-context cache was refreshed to the 781-test current tree and
now inventories the source-lock, backup/sync, bundle-evidence, and network
registry seams.

Focused verification: `tests/test_bundle_contracts.py` — 4 tests pass.

## 2026-09-19 — DEL-07 read-only source locks and update preview

Added `skillsmgr.source_lock`, a pure stdlib evidence seam for bounded local,
Git, archive, and registry source identities and complete candidate-tree
manifests. Previews compare every regular file, retain hashes/sizes and text
diff evidence, distinguish additions/removals, explain CRLF/LF-only changes,
and fail closed on missing, inaccessible, symlinked, traversal, oversized, or
overlarge sources. Candidate validation runs before readiness; `risk_scan()`
findings stay explicitly advisory/heuristic. Every result carries an explicit
physical target and is permanently non-committing, with no snapshot,
provenance, cache, SQLite, CLI, Store, network, or REST mutation.

Focused verification: `tests/test_source_lock_contracts.py` — 7 tests pass.
The live source-lock persistence and update/commit workflow remains approval-
gated and is not represented as shipped.

## 2026-09-19 — DEL-08 trust-first registry install evidence

The existing skills.sh fetch path now materializes its bounded snapshot in a
private temporary directory, runs full skill validation, and collects advisory
heuristic `risk_scan()` findings before the first managed-store mutation.
Validation errors fail closed; warnings and risk findings are returned as
evidence under the existing CLI/REST fetch result `inspection` block. Explicit
trust confirmation, global-only fetch, auth-isolated cache, hash verification,
atomic materialization, and credential-free provenance remain unchanged.

Focused verification: registry bridge/core/integration contracts — 47 tests
pass. A separate staged-review/commit transaction remains approval-gated.

## 2026-09-19 — DEL-11 positioning, distribution, and adoption brief

Added `docs/17-adoption-and-distribution.md` with the control-plane headline,
manual-root migration path, four-scene proof story, current install/loopback
claims, and a consent-safe design-partner protocol. It explicitly separates
verified repository evidence from future screenshots, human sessions, adoption
metrics, hosted sync, and team-governance claims. README and ROADMAP now point
to the brief; no product runtime, packaging, telemetry, dependency, command,
Store method, schema, bind, or network behavior changed.

## 2026-09-18 — DEL-06 workspaces, projects, and adapter catalog

Added the read-only `skillsmgr.adapters` catalog derived from the existing
consumer/root evidence. Adapter records expose candidate roots, tiered
precedence evidence, verified versus experimental status, explicit
`unknown-precedence`, reload guidance, platform notes, and verification date.
The new `/api/workspaces` surface observes an optional project only inside the
server's managed roots, redacts outside paths, and reports unavailable or
missing projects without walking them. The UI renders this as workspace
evidence; it does not create bindings, delete projects, or invent effective
state. Focused adapter/containment contracts and the five-viewport browser
harness pass.

## 2026-09-18 — DEL-05 tags, profiles, and previewable batch plans

Added filesystem-owned catalog metadata at `catalog/metadata.json` for bounded
tags and saved profiles. Full archives preserve and validate the catalog;
rebuild/resync and templates remain independent. The web UI now filters tagged
and untagged skills, selects the exact visible physical instances, previews and
executes enable/disable/soft-remove/sync batches with stale-plan rejection and
partial-failure reports, and previews profile members as observed, disabled,
divergent, or missing. No CLI command, Store method, SQLite schema, runtime
dependency, or purge batch was added. Focused catalog/web contracts, both
smokes, frontend syntax, and the browser harness pass. The final current-tree
ladder then passed 764 unittest tests, both smokes, compilation, docs,
complexity, package-source integrity, CLI help, diff checks, frontend syntax,
and all five browser-harness viewports. Optional artifact coverage remains
unavailable because `python3 -m build` is not installed.

## 2026-09-18 — DEL-00 current-tree delivery checkpoint

The pre-existing registry network/provenance changes were inventoried and kept
separate from the product UX delivery work. A recoverable non-destructive
checkpoint of the dirty diff and untracked files was created before UI work;
no staging, commit, reset, stash, or branch mutation was performed.

The current tree passed 750 unittest tests, `smoke_store.py`, `smoke_web.py`,
Python compilation, both frontend syntax checks, `check_docs.py`,
`check_complexity.py` at 226 functions, CLI help, `git diff --check`, and the
vendored Vue source-hash check. The optional artifact build remains unavailable
because `python3 -m build` is not installed. `browser_harness.py` passed at
320/400/640/900/1280 px with no browser errors or overflow. Its client-abort
probe still caused the server to log a raw `BrokenPipeError`; this is carried
into DEL-03 as a required clean-disconnect fix.

## 2026-09-18 — DEL-01 product baseline and research harness

Added `baseline_harness.py`, a stdlib-only disposable fixture/probe for empty,
small, divergent, malformed, and 2,000-instance libraries. It records the
startup-critical `/api/scopes`, `/api/skills?scope=all`, `/api/stats`, and
`/api/doctor?scope=all` timings and response shapes in a stable JSON schema,
with no telemetry or user-content access. Five focused contracts cover the
fixture plan. The existing browser harness remains the viewport procedure.
Five human usability sessions are explicitly left unclaimed because they need
consented participants; the baseline records the protocol rather than inventing
results.

## 2026-09-18 — DEL-02 logical Library and navigation foundation

Scope list observations now carry resolved `physical_root` and `physical_path`
values for derived presentation only. The Vue domain seam groups rows by
canonical name, collapses aliases to one resolved document, preserves each
distinct physical instance, and flags divergent content hashes. The default UI
is now a logical Library with a deliberate Instances toggle; the detail pane
lists observed copies and every existing action still receives an explicit
scope/name/path-backed instance. No Store method, SQLite schema, CLI contract,
or filesystem authority changed. Focused frontend/scopes contracts, both smoke
suites, frontend syntax, and `check_docs.py` pass.

## 2026-09-18 — DEL-04 first-run onboarding

The empty all-scopes Library now presents a local-only getting-started
checklist: detected consumer roots, completed scan, and the next safe action.
Create, archive import, folder add, and doctor actions reuse existing
workflows. Skip and restart are in-memory UI state, so onboarding never adds a
persistence contract or blocks direct expert access. Focused frontend coverage
pins the copy and escape routes. The final current-tree ladder then passed 760
unittest tests, both smoke suites, compile, docs, complexity, package-source
integrity, CLI help, diff checks, frontend syntax, and all five browser-harness
viewports; optional artifact coverage remains unavailable without `python3 -m
build`.

## 2026-09-18 — DEL-03 responsive shell and progressive startup

Startup now fetches scopes, skills, and trash exactly once in parallel, then
loads secondary stats and token budget data. On narrow screens the Library and
detail pane become separate states: selecting a row opens the detail screen,
Back returns focus to the originating row, and secondary filters sit behind an
explicit disclosure. Response writes catch expected client disconnects so a
browser abort does not produce a raw `BrokenPipeError` traceback. Focused UI and
handler contracts were added; the web/module docs describe the state flow.

## 2026-09-16 — Registry network browsing, fetching, and provenance

The network half of registry issue #3 is implemented behind the existing
`install` CLI and `POST /api/install` surfaces. The new stdlib-only
`skillsmgr.registry` client supports bounded skills.sh browse/search/curated
reads, explicit global fetch, optional bearer authentication, private
auth-isolated caching, opt-in stale fallback, redirect/response limits, and
clean errors. Fetched snapshots are checked with the upstream-compatible
registry hash plus a framed local integrity hash, then materialized atomically
with traversal/symlink/resource-limit defenses.

Successful fetches write a credential-free `.skillsmgr-provenance.json`
sidecar containing source, URLs, hashes, cache state, fetch time, and a
per-file manifest. `loader.py` validates and reconciles the sidecar so malformed
or changed files are surfaced as malformed observations. Fetch requires
explicit `--trust-confirmed`, remains global-store-only, and does not claim
malware scanning or signature verification. No CLI command, Store method,
SQLite schema, runtime dependency, or bind changed. Decisions are recorded in
@docs/ADR-005-registry-network-and-provenance.md; the offline preview remains
the historical contract in ADR-003.

## 2026-09-16 — Worktree comparison and frontend report close-out

Compared all three linked worktrees and the local backup branch against the
pushed `main`. Snapshot/full-migration work from the first agent worktree was
already present in the current refactored implementation; its stale CLI/UI
patch was not merged. The third worktree contained a report only. The valid
remaining findings from the second worktree's historical frontend report were
ported to the current `domain.js`, `app.js`, `index.html`, `styles.css`, and
`webapp.py`: CRLF Markdown normalization, array compatibility formatting,
definition-list Path markup, chip-count contrast, raw-metadata failure
feedback, and drained oversized-body `413` handling. Focused source and
request-body regressions were added; ZIP-hint changes were intentionally not
ported because ZIP import is now supported.

## 2026-09-16 — FM-9 dumper-key fidelity

The final partial audit finding is closed through two focused fixes. Mapping keys
containing representable control characters now use escaped double-quoted output
so the parser reconstructs the exact key, including newline and tab characters.
Distinct Python keys that would serialize to the same frontmatter key are
rejected at both the root and nested mapping levels before invalid duplicate-key
output can be emitted.

Red-first regressions are in
`tests/test_frontmatter_contracts.py::BlockScalarFidelityTests` for escaped-key
round-tripping and serialized-key collision rejection. No command, Store
method, schema, dependency, or bind changed; accepted SEC-4 remains untouched.
At that close-out, the suite was **722 tests OK** and complexity was **221 functions**.

## 2026-09-16 — Final audit tail (FM-20, FM-21, INFO-1, INS-1, INS-2)

The final five low/info audit findings are closed without adding a product
command, Store method, schema change, runtime dependency, or public bind.
`dump_frontmatter()` now rejects over-depth and cyclic programmatic container
graphs iteratively before recursive rendering, while `templates.template_path()`
uses the canonical bounded/reserved-name validator. `risk_scan()` keeps its
broader shell-pattern coverage explicitly advisory and heuristic. Offline
registry previews retain compatibility fields but never claim verified trust,
hash, or install eligibility; caller intent and supplied hash material are
reported as unverified. The `cmd_open` report is a verified false positive:
editor arguments remain an inert argv list, and the path/name boundary is
validated before lookup.

Red-first regressions cover all five findings in the frontmatter, CLI, insights,
and registry contract modules. Final verification on the current tree:
**721 unittest tests OK**, both smoke scripts, `check_docs.py`,
`check_complexity.py` (**219 functions**), frontend syntax checks, CLI help,
package-data source-hash assertion, and `git diff --check` pass. Optional
artifact coverage remains unavailable locally because `python3 -m build` is not
installed.

## 2026-09-15 — Trust-root and validator reference hardening (SEC-19, FM-19)

The next two low-severity audit findings are closed without adding a command,
Store method, schema change, runtime dependency, or public bind. `paths.data_dir()`
now canonicalizes and validates both the selected environment base and the
appended `skills-manager` root: filesystem roots, regular files, non-writable or
other-owned roots, and non-sticky group/other-writable roots fail closed instead
of selecting an untrusted boundary. Missing manager-owned components are
created with owner-only permissions, including intermediate directories.

Validator link and layout checks now decode percent-encoded paths, remove
fragment/query components, and retry without sentence punctuation. Existing
targets such as `scripts/run%20task.py#main`, `references/api.md?raw=1`, and
`assets/data.json.` no longer produce false missing-target warnings; containment
and the warning-only out-of-root link contract are unchanged.

Red-first contracts are recorded in `tests/test_audit_sec19_contracts.py` and
`tests/test_audit_batch9_contracts.py`. The full current suite is **712 tests
OK**; complexity remains **218 functions** and no product surface or persistence
contract changed.

## 2026-09-15 — Launcher, workflow, governance, and hygiene hardening (SEC-14…SEC-18)

The next five low/info audit findings are closed without adding a product
command, Store method, schema change, runtime dependency, or public bind.
First-party GitHub Actions in CI and release now use reviewed full commit SHAs.
The browser harness leaves Chrome's renderer sandbox enabled, binds its
ephemeral DevTools listener explicitly to `127.0.0.1`, and both developer
launchers use `skillsmgr.launcher_security.trusted_executable()` to skip unsafe
PATH matches. `.github/CODEOWNERS`, weekly GitHub Actions Dependabot updates,
and the protected `release` environment strengthen release governance.
`.gitignore` now covers local configuration, databases, credentials, and
private-key material.

Red-first coverage is in `tests/test_audit_batch8_contracts.py`; the existing
desktop-launcher tests now use hermetic private executable fixtures. The live
`browser_harness.py` passed all five viewport probes after the hardening. The
CDP seam remains intentionally local and unauthenticated because this is a
dev-only process workflow; it is not a product service or public bind.

## 2026-09-15 — Frontmatter and validator follow-up (FM-13, FM-15…FM-18)

The next five self-contained findings in the audit tail are closed without
adding commands, Store methods, schema changes, or dependencies. Folded `>`
scalars now retain line breaks around more-indented content; the canonical skill
name gate rejects Windows device names; NUL-byte links and layout mentions are
reported as validation warnings instead of leaking `ValueError`; frontmatter
`name` is validated even when `validate_text()` has no caller name; and passive
"should be used when" descriptions satisfy the use-context heuristic.

Red-first coverage lives in
`tests/test_frontmatter_validator_remaining_contracts.py`, with one focused
regression per finding. The audit tracker is now **88 fixed, 1 partial, 1
accepted, 12 open** of 102. No public product surface or persistence contract
changed.

## 2026-09-15 — Competitive product, UX, and business planning

Two HADS planning documents turn the dated comparison with
`xingkongliang/skills-manager` into an actionable product direction. The
strategy record fixes the recommended category and differentiation, customer
jobs, free/paid packaging boundary, pricing hypotheses, GTM, success measures,
risks, and unresolved business decisions. Its delivery companion specifies the
logical-library mental model, target navigation and mobile behavior, token
semantics, phased workstreams, dependency order, observable acceptance criteria,
experiments, decision register, security/privacy gates, and definitions of
ready/done.

The docs index and public `ROADMAP.md` link the new records while retaining the
roadmap as the shipped/proposed status authority.

The plan explicitly preserves the filesystem source of truth, rebuildable
SQLite index, stdlib CLI/backend, vendored no-build Vue frontend, and loopback
bind. Profiles, persistent provenance, new consumer/project entities, network
discovery, hosted backup, signing/team governance, new commands/Store methods,
and packaging changes remain approval-gated and are not described as shipped.
No product behavior changed.

## 2026-09-15 — EVAL-2 iteration safety and workspace aliases

`record_runs` now stages a complete iteration and restores the prior iteration if any `BaseException` interrupts the commit after the backup move; if rollback itself fails, the backup is preserved and the raised error identifies its location. `normalize_runs` rejects duplicate `(case, variant)` pairs before any output is written. Eval workspace selection checks both lexical and resolved containment, including `--path` symlink aliases under `data_dir/skills`, while external authoring remains beside the skill. Regressions cover the exact post-backup `KeyboardInterrupt`, duplicate pairs, lexical/resolved workspace containment, and valid external authoring.

**Verification:** focused eval contracts pass; full suite and smoke/gate checks are run on the current tree. No new commands, Store methods, schema, dependencies, staging, or commit.

## 2026-09-14 — FM-11 directory-name validation

`validate_skill()` now compares frontmatter `name` with the actual skill
directory basename, rather than the caller-provided name. Caller-name format
validation remains in `validate_text()`. The focused stdlib regressions cover
 mismatched and matching caller/directory names plus symlink-resolved directory
 basenames. Malformed symlink resolution now returns a clean validation error
instead of leaking `Path.resolve()` failures. No CLI/Store API, schema,
dependency, or unrelated behavior changed.

**Verification:** 6 focused FM-11 tests pass, including the existing caller-name
format contract and an unresolvable-directory regression; `git diff --check`
passes. No staging or commit.

## 2026-09-14 — CLI-8 bounded install-value validation

CLI and REST install bridges now share validation that rejects empty, option-like,
traversal-shaped, absolute, Windows drive-prefixed, and over-256-character source,
agent, and skill values. Runner argv remains list-form and shell-free. Red-first
CLI and REST parity tests cover the audit's examples (`..`, `../../tmp/pwn`,
`/etc/passwd`, `C:/Windows`) and the length cap.

## 2026-09-14 — Batch 7 complete: CLI-4 through CLI-8

The five next audit findings after batch 6 are closed: eval workspace containment,
doctor scope validation, raw/JSON output-mode exclusivity, list-only runner execution,
and bounded install-value validation. No CLI command, Store API, SQLite schema,
runtime dependency, or public bind changed. The tracker disposition is **77 fixed,
1 partial, 1 accepted, 23 open** of 102.


**AI manifest**: Dated, append-only record of changes, decisions, and bugs for skills-manager. Read before/after every session (docs/README.md reading order). Facts flagged stale here are corrected in the owning doc. Newest entry on top.

## 2026-09-14 — CLI-7 install list-only execution

`install --list-only` now executes the generated ecosystem runner command in list
mode instead of returning a command preview. It preserves list-form subprocess
invocation, reports the runner's stdout/stderr and exit code using the existing
human/JSON contracts, and leaves `--dry-run` and `--preview` non-executing.
REST parity was inspected: its explicit `run:true` path already executes the same
list-form command and remains unchanged. No new command, Store method, schema
change, or runtime dependency.

**Verification:** red-first subprocess-mock contracts failed before the fix, then
passed for list-flag argv/output, non-zero JSON exit behavior, and dry-run no-call;
the focused registry/CLI contract suite passes.

## 2026-09-14 — CLI-6 view output-mode contract

`view --raw --json` is now rejected with a clean exit-1 `StoreError` instead of
printing raw Markdown while claiming JSON output. The existing `view --raw` and
`view --json` modes remain unchanged, and the rejection applies to global and
agent-scoped views. Red-first CLI contracts cover both scopes. No new command,
Store method, schema change, or runtime dependency.

**Verification:** focused incompatibility tests pass; full CLI contract suite and
repository test/gate ladder are run for the final tree.

## 2026-09-14 — CLI-5 doctor scope validation and filesystem audit

`doctor --scope` now validates against known global/agent/project scope IDs and
rejects unknown values with a clean exit-1 error in both human and JSON modes.
`global` and `all` retain their existing Store/aggregate behavior. A known
non-global scope is audited directly from its filesystem through the shared
loader, so malformed agent documents produce a scoped report and non-zero human
status instead of being hidden behind a healthy global Store doctor result.

**Verification:** red-first `DoctorScopeCliTests` failed on the pre-fix code;
32 focused CLI/scope tests pass, the full suite passes (657 tests), both smoke
scripts pass, Python compilation and `git diff --check` pass. No new command,
Store method, schema change, or runtime dependency.

## 2026-09-14 — CLI-4 eval workspace containment

`validate --evals-run FILE --workspace DIR` now resolves the explicit workspace
before recording and rejects any path that resolves inside the managed
`data_dir/skills` tree. This closes the export/backup pollution path while
preserving explicit workspaces outside the tree and the existing `--path`
authoring layout. Direct and symlink-resolved in-tree paths are covered by CLI
contracts. No CLI command, Store API, schema, or dependency changed.

**Verification:** the eval harness contract suite passes (42 tests), including
focused rejection, valid override, and `--path` workspace tests.

## 2026-09-14 — Deep-audit remediation, batch 6: concurrency, scope, scan and multipart findings (5)

This batch follows the audit severity order and closes `STORE-11`, `SCOPE-5`,
`SCOPE-8`, `SEC-10`, and `SEC-11`; `SEC-12` is closed with the same concurrency
seam. No locked constraint moved: no new CLI command, `Store` method, SQLite
schema change, runtime dependency, or public bind.

- **`STORE-11` / `SEC-12`: cross-process mutation exclusion and repair.** The
  bounded reentrant lock table now wraps each lock key with POSIX `flock` (and a
  Windows `msvcrt` region where available). Lock files live in a private temp
  directory keyed by the absolute path digest, so a missing skill path is not
  materialized as a fake data-tree entry. Toggle rename races become clean
  `StoreError`s. `resync()` removes only transaction/temp artifacts older than a
  five-minute live-writer grace window and emits a stderr diagnostic for each
  repair batch; fresh staging files remain untouched.
- **`SCOPE-5`: resolved-root consistency.** Recursive lookup now derives the
  observed path relative to one resolved scope root and returns the named entry
  below that root. Symlinked-home, symlinked-scope-root, nested-category,
  grouping-directory and toggle behavior are pinned.
- **`SCOPE-8`: sync result integrity.** Implicit targets use live root
  availability, explicit read-only roots are skipped with an actionable reason,
  each target rolls back independently, completed targets remain in `synced`,
  failed targets are in `skipped`, and an all-failed run raises `StoreError`
  rather than leaking an `OSError` or REST 500.
- **`SEC-10`: aggregate request cost.** `list_all()` now scans each unique
  physical root once; `/api/stats` reuses the merged records for descriptors and
  largest entries. A scan-count regression confirms no duplicate filesystem
  walk in the aggregate path.
- **`SEC-11`: multipart fidelity.** Parsing recognizes RFC multipart framing
  instead of splitting on a bare boundary, removes only framing CRLF, preserves
  trailing newlines and embedded boundary lookalikes, and uses the email parser's
  compat32/RFC2231 parameter decoding for filenames.

**Verification:** 652 unittest tests pass, including 25 new batch-6 contracts;
`smoke_store.py` and `smoke_web.py` pass; `check_docs.py`, `check_complexity.py`,
frontend `node --check`, package-data source integrity, Python compilation and
`git diff --check` pass. The local package-data gate reports `UNAVAILABLE` only
because optional `python -m build` is not installed; the source Vue hash passes
(and the real-artifact gate remains covered by the existing batch-5 test path).


**AI manifest**: Dated, append-only record of changes, decisions, and bugs for skills-manager. Read before/after every session (docs/README.md reading order). Facts flagged stale here are corrected in the owning doc. Newest entry on top.

## 2026-09-12 — Deep-audit remediation, batch 5: the medium security/supply-chain findings (5 + 1)

Continues the audit's severity order past batch 4, which left every Critical,
High and most Medium row closed. This batch takes the remaining Medium
security and supply-chain findings — `SEC-5`…`SEC-9`, with `SEC-4` recorded as an
accepted trade-off — and settles the one `[?]` batch 4 could not
(`SEC-13`). Per-finding status lives in
`docs/13-audit-remediation-status-2026-09-11.md` (updated with a new `ACCEPTED`
disposition for `SEC-4`); this entry records the work and the evidence.

**No locked constraint moved:** no new CLI command, no `Store` method, no schema
or `SCHEMA_VERSION` change, no runtime dependency, web UI still stdlib-backend
with no build step and still loopback-only. Two thirds of the batch is repo
tooling and CI configuration, not product code.

- **`SEC-5` closed (`form-action`).** `form-action` does not fall back to
  `default-src`, so an injected `<form action="https://…">` was unconstrained
  even though `default-src 'self'` was set. `webapp.py::_send_security_headers`
  now sends `form-action 'none'`; the `501`-without-headers half was already
  closed by `BUG-9`. Pinned on live `200`/`404`/`405` responses.
- **`SEC-6` closed (upload staging).** `web_upload.upload_folder` wrote each
  multipart part with a bare `target.write_bytes`, so one upload holding both `a`
  (file) and `a/b/SKILL.md` (directory) raised a raw `IsADirectoryError` — HTTP
  `500 internal error`, with the exception printed to the server log — in either
  part order, and a NUL-byte filename returned the interpreter's own
  `embedded null byte` string as the entire client-facing message. A new
  `_stage_path()` decides the staging path (and both name-conflict directions)
  before any write; leftover `OSError`/`ValueError` become a `StoreError`
  carrying only the OS reason. Four regressions pin both part orders, the NUL
  case, a clean server log, and the unchanged happy path.
- **`SEC-7` closed (a write-capable job executing a PyPI distribution).**
  `github-release` holds `contents: write` yet `pip install`ed
  `skill-control-plane==<tag>` from public PyPI. Every install in that job is now
  `--no-index` against the artifacts this workflow built and attested, and the
  post-publish PyPI check moved to a new `postpublish-verify` job with
  `contents: read` and no `id-token: write`.
- **`SEC-8` closed (build toolchain).** `[build-system] requires` was
  `setuptools>=61`, so the bytes that provenance attests were decided by whatever
  PyPI served at release time. Now `setuptools==84.0.0` plus a new
  `requirements-build.txt` locking `build`, `packaging`, `pyproject_hooks` and
  `setuptools` with every file digest, installed `--require-hashes` and used via
  `python3 -m build --no-isolation` in both `ci.yml` and `release.yml`.
  **Verified for real**: hash-checked install in a throwaway venv, a successful
  `--no-isolation` build, and `check_package_data.py --dist-dir` PASS on both
  artifacts. PEP 518 cannot carry hashes in `[build-system] requires`, so the
  backend itself is pinned by exact version — recorded as the honest limit.
- **`SEC-9` closed (vendored bundle integrity).** A 158 KB minified file that
  executes same-origin with access to every mutation endpoint could be swapped by
  any PR with no gate noticing. `check_package_data.py` now records
  `VUE_VERSION`/`VUE_UPSTREAM_URL`/`VUE_SHA256`/`VUE_SIZE` and verifies the
  checked-in file as well as the payload inside the wheel and the sdist — and it
  does so **before** the optional build step, so the check still runs on an
  ordinary local run where packaging coverage reports `UNAVAILABLE`. The digest
  was verified independently: the payload is byte-identical to
  `https://unpkg.com/vue@3.5.13/dist/vue.global.prod.js` (157,924 B, sha256
  `c459ba7cc8db…`). `.gitattributes` marks the file `-text` so cross-platform EOL
  translation cannot break the recorded hash.
- **`SEC-4` recorded as `ACCEPTED`, not fixed.** `script-src 'unsafe-eval'` is
  required by the vendored runtime+compiler build (no `template:`/`render:` in
  `app.js`, so Vue compiles `index.html` with `Function(code)()`); removing it
  needs precompiled render functions, i.e. a build step, which locked constraint
  4 forbids. The trade-off, its cost, and the condition that would change it are
  now written in `docs/08-web-ui.md`, and a test fails if the directive is dropped
  without that documentation. `'unsafe-inline'` must never join `script-src`.

### What installing the build toolchain uncovered (`SEC-13`)

Batch 4 left `SEC-13` `PARTIAL` with `[?]` on whether the sdist ships `tests/`,
because `python -m build` was absent here. With the batch-5 toolchain installed
that question has an answer — and answering it exposed a **second, unreported
defect**:

- The sdist **did** ship the whole suite: 73 members, 29 of them `tests/test_*.py`.
- `check_package_data.py` never noticed. `read_archive_files()` canonicalized
  sdist members by *searching* for `skillsmgr/` and dropping everything else, so
  the `BUG-13` "inspect every member" policy only ever saw package content. Its
  own regression test passed because it exercised a **wheel** fixture, where
  every member is kept — a gate that reported `PASS` about a path it could not
  see. (Recorded as a rule for future sessions in the tracker.)
- Both halves are now closed: sdist members are kept (the `<name>-<version>/`
  root is stripped) so the policy can inspect them, and `MANIFEST.in` `prune
  tests` stops the suite from shipping. A real rebuild went from 73 members to 45
  and the gate passes on both exact artifacts. `SEC-13` is `FIXED`.

### Verification (current tree)

**627 unittest OK** (was 607: +20 new regressions), `smoke_store.py` PASSED,
`smoke_web.py` PASSED, `check_docs.py` PASSED, `check_complexity.py` PASSED (216
functions — ratchet flat, no baseline edit), `node --check` clean on `app.js` and
`domain.js`, `check_package_data.py` PASS including a `--dist-dir` run on freshly
built artifacts, `python -m py_compile` clean, `git diff --check` clean, and both
workflow files parse as YAML with the new job list
(`build, verify, attest, publish-testpypi, publish-pypi, github-release,
postpublish-verify`). Red-first was respected: the new test module reported 16
failures + 3 errors before any fix landed.

Files touched: `skillsmgr/webapp.py`, `skillsmgr/web_upload.py`,
`check_package_data.py`, `pyproject.toml`, `.github/workflows/ci.yml`,
`.github/workflows/release.yml`, `requirements-build.txt` (new), `MANIFEST.in`
(new), `.gitattributes` (new), `tests/test_audit_batch5_contracts.py` (new),
`tests/test_package_data.py`, `tests/test_ci_release_contracts.py`,
`CONTRIBUTING.md`, `docs/08-web-ui.md`,
`docs/13-audit-remediation-status-2026-09-11.md`, `docs/SESSION-CONTEXT.md`,
`task.md`, `TODO.md`, `CHANGELOG.md`, and this log.

## 2026-09-11 — Docs gate hardened, and a whole-repo markdown lint pass

Follow-on to the truth pass below. That pass fixed drift by reading and probing;
this one **stops the same classes from returning** and finishes the sweep with a
real linter. No product behaviour changed.

**Method: derive the docs from the source with code, not with prose.** Six
purpose-built checkers, all offline and stdlib-only:

| Checker | Compares |
|---|---|
| CLI parity | the argparse parser ↔ `docs/03-cli-surface.md` (every command, alias, subcommand and flag, both directions) |
| REST parity | `/api/*` routes in `webapp.py` ↔ the tables in `docs/08-web-ui.md`, both directions |
| `Store` parity | public methods on the class ↔ `docs/04-store-api.md`, both directions plus parameter names |
| constants | every `MAX_*` value quoted in a doc ↔ its definition in `skillsmgr/` |
| symbols | every `name()` a doc names ↔ a definition somewhere in `skillsmgr/` |
| inventory | every file in `docs/SESSION-CONTEXT.md`'s tree ↔ the filesystem |

### Real defects it found (all fixed)

- **`/api/tokens` was implemented but undocumented.** `docs/08-web-ui.md` calls
  itself "the single source of truth for … what endpoints exist" and its own
  client-contract section lists `tokens` among the surfaces a client can rely on,
  yet the endpoint had no row. Row added with its real query parameters
  (`window`, `name`, `scope`, `text`) and response shape, read from the handler.
- **`docs/04-store-api.md` documented a method that does not exist.**
  `db_rebuild(self) / db_resync(self)` — there is no `Store.db_resync`; the method
  is `resync()`, and `db resync` is only the *CLI* spelling. Worse, the real
  `resync()` was nowhere in the public-methods list. Both fixed, `resync()`'s
  return shape verified by calling it (`{"added", "updated", "removed"}`).
  This is the STORE-14 class surviving in the one place `check_docs.py` could not
  see it: a bare `name(self` rather than a `Store.name` reference.
- **`add(self, path, name=None)`** — the parameter is `src`, not `path`.
- **A broken table in `docs/08-web-ui.md`.** The `DELETE /api/skills/…?purge=0|1`
  row carried an unescaped `|`, so the table rendered with five cells in a
  four-column table. Escaped as `\|` (pre-existing; verified against `HEAD`).
- **A spurious H1 in `docs/10-worktree-integration-comparison-2026-09-08.md`.** A
  line began `#2’s approved scope.` mid-paragraph, so the second half of a
  sentence rendered as a top-level heading. Escaped to `\#2’s`.

### Whole-repo lint (`markdownlint-cli2`, structural ruleset, installed outside the repo)

All 39 markdown files linted. **103 real defects**: 91 unlabelled fences (85 of
them in `DEEP-AUDIT-2026-09-11.md`, whose blocks are plain-text reproductions),
**11 files that did not end with a newline** (`PLAN.md`, `TODO.md`, `docs/05`,
`docs/06`, `docs/07`, `docs/09`, `docs/10`, `docs/11`, `docs/12`, `docs/ADR-001`,
`docs/PRE-MERGE-CHECKLIST.md` — all pre-existing, confirmed against `HEAD`, not
introduced here), and the spurious heading above. The 137 remaining hits are
`MD022`/`MD031`/`MD032`/`MD012` (blank lines around headings, fences and lists),
which are render-neutral in GFM and left alone so each doc keeps its voice.

**Content-neutrality proved, not asserted:** after applying the repairs, diffing
each touched file against a pre-change copy *with the fence labels stripped*
yields no content difference (`DEEP-AUDIT` and `loop-engineering-findings.md` diff
empty; `docs/10` differs only in the escaped `#` and the final newline).

### The gate itself was hardened (this is the durable part)

`check_docs.py` previously checked only the `REQUIRED_DOCS` subset, `@docs/`
pointers, `Store.x` symbols, a few current claims, and version alignment — which
is exactly why the defects above survived. It now also enforces, offline and
AST-only like the rest of the file:

1. HADS header facts (H1, version line within 20 lines, AI manifest) for **every**
   `docs/*.md`, not just the required set.
2. Local markdown links **and their `#anchors`**.
3. Table cell-count integrity — catches the unescaped-pipe class.
4. A single trailing newline.
5. `/api/*` route parity with `docs/08-web-ui.md`, both directions.
6. Public `Store` method parity with `docs/04-store-api.md`, both directions.
7. CLI command/alias/subcommand heading parity with `docs/03-cli-surface.md`.
8. The `docs/SESSION-CONTEXT.md` file inventory.

**Nine regression tests** added in `tests/test_docs_consistency.py` (suite
598 → **607**). **The new checks were proved by mutation, not by passing:** 15
defects were injected into the real tree one at a time, confirmed to fail the
gate, and restored byte-for-byte (hash-checked). Three checks were **too lenient
on the first attempt** and had to be tightened before they caught their own
defect — a route regex that stopped at a hyphen (so `/api/tokens-DISABLED` still
matched `/api/tokens`), a `Store` check testing only "is it mentioned" and not
"does the documented signature exist", and a `\b`-based CLI match for which
`init-DISABLED` still contained the word `init`. A check that has never failed is
not evidence; all 15 now fail the gate.

**Final ladder:** `607 tests OK`, both smokes, `check_docs.py`,
`check_complexity.py` (216 functions, unchanged — the gate lives outside the four
measured files), `node --check` on both frontend files, CLI help,
`check_package_data.py` (`UNAVAILABLE`, standing).

## 2026-09-11 — Documentation truth pass: every living doc reconciled with the source

A documentation truth pass after the deep-audit remediation. **No product
behaviour changed** — no CLI command, flag, exit code, endpoint, `Store` method,
schema value, or locked constraint was touched, and nothing was committed.

**Method.** Every tracked `.md` was first classified *living* (describes the
present) versus *historical* (a dated record), so only living documents were
edited. Then every count was re-derived by **running the gate**, and every
behaviour claim was read out of the source or probed on a hermetic temporary data
dir — never copied from another document.

**Counts on the current tree (this session's runs):** `598 tests OK`;
`check_complexity.py` **216 functions**, budget ≤ 15; both smokes PASSED;
`check_docs.py` PASSED; `node --check` clean on `app.js` and `domain.js`; CLI help
runs; `check_package_data.py` `UNAVAILABLE` (optional `build` tooling absent —
standing behaviour, not a regression).

### Documents changed, and what was wrong

- **`docs/SESSION-CONTEXT.md`** (v0.6.0 → v0.7.0). The worst one: its gotcha said
  *"Reads are not `Host`-validated today (issue #14, open): only state-changing
  methods run the request policy"*, and pointed at a characterization test as the
  reason fixing it would be hard. Both halves were false —
  `web_security.validate_request()` is called by `do_GET`/`do_HEAD` too (SEC-1) and
  `tests/test_web_client_contracts.py` already pins the **closed** behaviour. A
  stale cache that under-reports a security control is worse than no cache, so the
  entry was rewritten to describe the current policy (all routed verbs; `HEAD`
  mirrors `GET`; `OPTIONS`/`TRACE` → JSON `405` with `Allow` and the security
  headers). Also: `475 tests` → **598**, `check_complexity.py (164 functions)` →
  **216**, the section date, the client-contract bullet (a `localhost` `Host` is
  rejected on **every** request, reads included — not only on mutations), and the
  gotcha list's broken numbering (1–10, 12, 13, 14, 11) renumbered to 11–14. The
  `doctor --explain` bullet now records the HTTP confinement.
- **`docs/03-cli-surface.md`** (v0.3.0 → v0.4.0). Three user-visible behaviours had
  no documentation at all, and the header claimed verification on 2026-09-10
  against a `cli.py` that now only holds the adapter. Added: `--metadata` rejects a
  key containing a control character (clean error, exit 1, nothing written — probed
  with a newline and with `ESC`); `edit` fails closed on an unparseable document
  (probed: byte-for-byte untouched file, exit 1); and a new **Untrusted display
  text** section for the `cli_output.sanitize_text()` seam (C0/C1/DEL, separators,
  format characters, lone surrogates → `?`), including the honest limit that
  `--json` and `view --raw` are deliberately exempt.
- **`docs/08-web-ui.md`** (v0.3.0 → v0.4.0). Security/response section said the
  Host/Origin/Referer/Sec-Fetch-Site policy applied to *mutations*; it applies to
  **every** request. Added the `HEAD`/`OPTIONS`/`TRACE` contract, `degraded` on
  `/api/doctor?scope=all` and `/api/stats` (with the two different shapes), the
  `doctor?explain` disclosure boundary (`<redacted>`, `paths_redacted: true`,
  `project-outside-managed-roots` without walking), `addressable: false` /
  `unaddressable`, and replaced a reference to the removed `_scopeParam`/`_scopeQs`
  helpers (`BUG-15`) with the current inline construction. The client-contract
  bullets "`localhost` → 403 on mutations" and "Reads are not Host-validated today"
  were both rewritten.
- **`docs/01-architecture.md`** (v0.2.1 → v0.3.0). Two whole policies were missing, so
  they were written down from source: the **symlink policy** (`contained_entry`
  keeps the *named* entry while still requiring containment; `sync_skill` copies
  links as links and refuses escaping ones; `export`/`tree_content_hash` do not
  follow links; out-of-root link targets stay a warning) and the **locking model**
  (per-skill lock + library-wide index lock at `<data>/skills/.skillsmgr-index-lock`,
  trash lock at `<data>/trash/.trash-lock`, `threading.RLock`, therefore not
  cross-process — STORE-11/SEC-12 still open). Both stale counters
  (`315-test suite`, `475 tests`) corrected to 598.
- **`docs/12-agent-root-discovery-2026-09-08.md`** (v1.1.0 → v1.2.0) and
  **`docs/ADR-002-root-consumer-effective-state.md`** (v1.0.0 → v1.1.0). Both read as
  though the read-only diagnostic were still a *proposal* ("proposed as the
  read-only `doctor --explain` … in TODO L3") and as though physical-root dedup
  were unimplemented. They now record it as **shipped** (2026-09-11), record
  invariant 1 as **enforced** (with the SCOPE-7 dedup), and add `unaddressable` to
  the observed instance-state vocabulary. The `[?]` about the absent `EffectiveSkill`
  entity is kept — it is still true — with a note on what does exist instead.
- **`docs/ADR-001-localhost-mutation-token.md`** (v1.0.0 → v1.1.0). Its Context claimed
  the policy guarded state-changing requests, and its Consequences pointed at
  `webapp.py` for checks that now live in `web_security.py`. Both corrected, with an
  explicit note that widening the policy to reads **supports** the no-token
  decision rather than reopening it.
- **`skills-manager-threat-model.md`** (v1.2 → v1.3). T-14 (read-path DNS rebinding)
  was still **OPEN** although `SEC-1` closed it: now `MITIGATED`, with the residual
  limited to issue #14 **F-2** (a `localhost` `Host` is over-rejected). Added
  **T-15** for the `doctor?explain` disclosure (fixed, with the bounded-scan effort
  residual tied to the still-open SEC-10) and **T-16** for CLI terminal injection
  (fixed, with `--json`/`view --raw` named as the deliberate exemption). R-7 closed;
  recommendation 5 rewritten from "decide issue #14" to "F-1 decided, F-2 open".
- **`SECURITY.md`**: the localhost-browser-boundary section named only the four
  mutating methods; it now documents the all-method boundary, the `OPTIONS`/`TRACE`
  405, and the two disclosure limits a reporter needs to know (the `explain`
  confinement, and that `--json`/`--raw` intentionally emit raw stored bytes).
- **`security_best_practices_report.md`** (re-dated 2026-09-11): the executive
  summary and control tables now include the read-path gate, the `HEAD`/`OPTIONS`/
  `TRACE` contract, terminal sanitization, and the `explain` boundary, and the live
  probes run for this revision are recorded. **Corrected a class of error, not just
  instances:** the `file.py:line` citations in that report, the threat model, and
  `docs/04-store-api.md` were exhaustively checked, and **most had drifted onto
  unrelated code** — `webapp.py:192` pointed at a token-enrichment line,
  `store.py:814` at an index-row check, `validator.py:234-238` at an unrelated
  warning string, `scopes.py:150` and `282` at closing brackets; only `archive.py`'s
  two ranges (`22-235`, `309-364`) still resolved to the intended functions. All of
  them were replaced with symbol names (`WebAppHandler._serve_static`,
  `archive.extract_members`, `validator._check_links`, …), which cannot drift
  silently.
- **`docs/13-audit-remediation-status-2026-09-11.md`** (v0.3.0 → v0.5.0). Its
  "Current tree state" table published `check_complexity.py … (208 functions)`,
  which the gate now contradicts (**216** across the same four files) — and which
  was **already wrong when published**, not merely stale: running the gate against
  the checkpoint refs gives `208` at `refs/wip/audit-b4-193107` but `216` at
  `refs/wip/audit-b4-done-194837`, i.e. the number had moved before that document
  was written and was never re-derived. Its checkpoint note also claimed "four
  refs, one per batch" when eight `refs/wip/audit-*` refs exist. Both corrected
  with a dated re-derivation note.
- **Two `OPEN` rows in the same tracker were wrong**, found by re-probing **every**
  `OPEN` row against the current tree instead of trusting the label. `SEC-5`
  ("CSP lacks `form-action`; 501 responses from unmatched methods carry no security
  headers") had already lost its second half to `BUG-9`, and `SEC-13` ("sdist ships
  `tests/test*.py`; no gate inspects non-`webui` archive members") had already lost
  its gate half to `BUG-13` — both in batch 4, i.e. **before** the tracker was
  first written, so the original tally never counted them. The table's own
  definition ("`OPEN` = no change was made for that finding") made the label false,
  so both are now `PARTIAL` with the genuinely-remaining half named:
  `form-action` is still absent from the CSP, and whether the sdist still
  *contains* `tests/` is `[?]` in this checkout because `python3 -m build` is
  unavailable (it would now fail the gate loudly if it did). Tally corrected
  `61/1/40` → **`61/3/38`**, with the remaining-work groupings and the
  traceability block updated to match. The other 38 `OPEN` rows were each re-probed
  (CLI-4…CLI-11, EVAL-2, FM-11/13/15–21, INFO-1, INS-1/2, SCOPE-5/8,
  SEC-4/6–12, SEC-14–19, STORE-11) and **all stand** — by probe or by reading
  the code path, e.g. `doctor --scope bogus` still exits 0, `view --raw --json`
  still prints Markdown, `trash purge` still prints the Python list, `validate
  nosuch --all` still reports the other skills as ok, `record_runs` still writes
  without a transaction, `upload_folder` still leaks a raw `IsADirectoryError`,
  `validate_skill_name("con")` still accepts, `dump_frontmatter` still hits
  `RecursionError` at 2000 levels, and `--workspace` inside `skills/` is still
  uncontained.
- **The "Remaining work" grouping in that tracker was also incomplete**: it
  enumerated only 36 ids while calling 40 rows open — `SEC-6`, `FM-13`,
  `SCOPE-5` and `SCOPE-8` were missing, and there was no Scopes row at all. It now
  enumerates **all 38**, verified by extracting the ids from both tables and
  diffing them (0 missing, 0 extra).
- **`docs/README.md`** (v0.1.0 → v0.2.0): the HADS index omitted
  `docs/13-audit-remediation-status-2026-09-11.md`; added in the table's own format,
  and the manifest's verification date refreshed.
- **`docs/02-modules.md`**: `web_security.py` was described as owning "loopback
  mutation validation"; it owns loopback **request** validation. Also recorded the
  index/trash lock keys, the `cli_output` sanitization seam, the `--metadata`
  control-character rejection, the fail-closed edit contract, and `unaddressable`.
- **`docs/04-store-api.md`** (v0.2.0 → v0.2.1): the three `store.py:NN` citations
  corrected to symbol references.
- **`TODO.md`**: the "Ground truth at the start of this backlog" block asserted
  *"The current baseline passes 47 `unittest` tests"* in the present tense. It now
  labels that as the 2026-09-07 backlog-start record and states today's re-derived
  baseline beside it (598 tests, both smokes, docs, complexity 216, frontend
  syntax, CLI help, package-data `UNAVAILABLE`); the published-tag line names
  `v1.0.1`. **Milestone 51** records this pass.
- **`task.md`** (v0.3.0 → v0.4.0): the authoritative "Current state" block now leads
  with this session's verified ladder, and **Milestone 56** records the pass.
- **`docs/06-progress-log.md`**: this entry.

### Documents re-verified claim-by-claim and left unchanged

"Checked" in this entry means the claims were tested, not skimmed:

- **`README.md`** — every scope id/path in the table matches `scopes.known_scopes()`
  (`opencode` = `~/.config/opencode/skills`, `agents` = `~/.agents/skills`, …); all
  37 invocable names; every command and flag used in the quickstart and the
  registry/eval examples exists in the parser (checked via `--help` for all 27
  commands, their subcommands and all 43 documented flags); the `desktop_launcher.py`
  flags, the distribution name and `1.0.1` all match the source.
- **`ROADMAP.md`** — every shipped marker resolves: the named tests and classes
  (`test_desktop_launcher_contracts.py`, `test_web_client_contracts.py`,
  `test_link_severity_contracts.py`, `TarFallbackPolicyPins`), `insights.risk_scan`,
  `validator.description_score`, ADR-004, the `v1.0.1` publication, `restore
  --snapshot`, `--preview`/`--evals-run`.
- **`CONTRIBUTING.md`** — the checks block matches the real gates, including
  `check_package_data.py --dist-dir` (the flag exists).
- **`AGENTS.md`**, **`docs/ADR-003`**, **`docs/ADR-004`**, **`docs/07-context-strategy.md`**
  (after correction), **`.github/*` templates** — no claim contradicted by the
  current tree.
- **`PLAN.md`** — a plan-of-record; its `301 unittest` lines sit inside dated
  research-round records and are correct as history.
- **`loop-engineering-findings.md`** — dated report with a pinned baseline commit;
  two live claims spot-verified rather than assumed (`FIX-14`: all four
  duplicate-key mapping forms still raise a clean `FrontmatterError`; `FIX-11`:
  sync into the global scope still reconciles the row).

### Historical documents deliberately not rewritten

`docs/09-baseline-evidence-2026-09-07.md`, `docs/10-worktree-integration-comparison-2026-09-08.md`
and `docs/11-integration-status-2026-09-08.md` are dated evidence records and
present themselves as such; `docs/05-gui-plan.md` is already labelled
SUPERSEDED/historical (and `check_docs.py` enforces that label);
`docs/06-progress-log.md`'s own older entries are append-only; and the older
test counters inside `task.md`/`TODO.md`/`PLAN.md` milestones ("301 unittest",
"435 unittest", "477 unittest") are correct **as history** for the slices that
recorded them. `DEEP-AUDIT-2026-09-11.md` is a findings-only record and was not
edited.

### Verified but deliberately not changed (reported instead)

- `effective.REDACTION_NOTE` tells an HTTP caller to "run the CLI with
  `--disclose-paths` for the full local view". **There is no `--disclose-paths`
  flag** — `doctor --help` lists only `--json`, `--explain`, `--project`,
  `--skill`, `--scope`, and the CLI simply passes no boundary. This is a
  user-visible string in `skillsmgr/effective.py`, i.e. product code, so it is
  reported here rather than fixed under a documentation task.
- The same file's docstring says the local CLI passes `disclose_paths=True`; the
  actual mechanism is `allowed_root=None`. Same reason.
- `.autogit` was not touched, and nothing was staged, committed, or pushed. A
  pre-change checkpoint exists at `refs/wip/docs-*`.

## 2026-09-11 — Audit tracking reconciliation: traceability gaps closed

Prompted by the question "is the tracking file updated?", the new
`docs/13-audit-remediation-status-2026-09-11.md` was **audited** rather than
trusted — both its counts and its per-row claims.

- **Structure verified:** 102 rows, one per finding ID, matching the audit's own
  master tables. Tally `61 FIXED / 1 PARTIAL / 40 OPEN`.
- **Traceability audited and two gaps found.** Counting which `FIXED` rows are
  backed by a test that names the finding ID showed **59 of 61** — `SCOPE-13` and
  `BUG-2` were implemented and probe-verified, but had **no committed test**.
  That made the "every closed finding carries a red-first regression test" claim
  I had just added to `TODO.md`'s *Definition of done* untrue, so the claim was
  made true rather than softened:
  - `tests/test_web_scopes.py::test_toggle_refuses_a_mixed_document_state` —
    `SCOPE-13`, the scope-side twin of `STORE-3` (only the store side had been
    tested).
  - `tests/test_scope_contracts.py::test_the_loader_and_the_validator_agree_about_an_invalid_document`
    and `::test_effective_does_not_offer_an_invalid_document_as_a_candidate` —
    `BUG-2`, both at the loader and at the diagnostic layer.
  - `tests/test_frontmatter_contracts.py` — `FM-9`'s **partial** state pinned in
    both directions: the closed half (an unwritable key raises) and the open half
    (an escaped-key round trip is still not implemented and `{1:'x','1':'y'}`
    still emits a duplicate-key document), so the gap stays visible instead of
    being assumed closed.
  All three were confirmed **failing against the pre-fix code** first
  (`SCOPE-13` fails for both toggle directions; `BUG-2` errors).  Traceability is
  now `61 of 61`.
- **A limitation is now recorded in the tracker:** the check proves a test *names*
  each finding ID; it does not prove every test is as strong as the audit's
  original reproduction.  Batch 3 and batch 4 were additionally spot-verified by
  independent probes; batches 1 and 2 were not re-probed end to end.
- **Count reconciliation:** `TODO.md` and `CHANGELOG.md` had said "46 findings
  closed", which counted *agenda items* (20+5+7+14) rather than distinct IDs.
  Both now say **61 finding IDs closed, 1 partial, 40 open out of 102**, with the
  46-vs-61 difference explained, because several agenda items closed more than one
  finding (batch 1's `STORE-3` item also closed `SCOPE-13`).
  **SUPERSEDED 2026-09-11:** the `1 partial / 40 open` half of that count was
  wrong — `SEC-5` and `SEC-13` were each partly closed by `BUG-9`/`BUG-13` in
  batch 4 and so were `PARTIAL`, not `OPEN`. The tracker and the files named here
  now read **61 fixed / 3 partial / 38 open**; see the newest entry above.
- **`TODO.md` gained Milestone 50**, the repository's canonical execution
  backlog had not recorded any of this work; its own rule at the top requires
  updating it.  It now lists the four batches as tasks, the 40 open findings by
  area, and `FM-9` as `[!]` blocked-partial.
- **Known flake, not root-caused.** One full-suite run reported
  `598 tests, FAILED (errors=2)` at 100 s wall-clock; three consecutive
  subsequent runs were clean (`OK`) at 51-77 s.  The pattern (only under load,
  never reproducible in isolation) matches the earlier `test_web_client_contracts`
  timeout seen when the suite ran concurrently with `check_complexity.py`.  The
  two erroring tests were not identified, so this is recorded as an open
  loose end rather than a resolved one.
- Final ladder on the reconciled tree: `598 tests OK`, both smokes,
  `check_docs.py`, `check_complexity.py`.

## 2026-09-11 — Deep-audit remediation, batch 4: low/info findings (14)

- **Source:** `DEEP-AUDIT-2026-09-11.md` — **STORE-14**, **BUG-8**–**BUG-15**,
  **SCOPE-14**–**SCOPE-18**.  61 of 102 findings are now closed (from 47).
- **Verification:** `python3 -m unittest discover -s tests` — **593 tests OK**
  (29 new in `tests/test_audit_batch4_contracts.py`; 25 of them fail against the
  pre-fix code); **598** after the traceability follow-up described below.  Both smokes, `check_docs.py` and `check_complexity.py` PASS.
- **Two audit claims were wrong and are recorded as such rather than "fixed":**
  - *BUG-9*'s title says wrong-arity `/api/…` paths "are served by the static
    handler".  Probing a live server shows they already return a JSON 404 with
    the security headers; the real, reproducible defect is that the stdlib
    answered **HEAD/OPTIONS/TRACE** with a **header-less HTML 501**, bypassing
    the entire response policy.  HEAD now mirrors GET (headers, no body) and
    OPTIONS/TRACE return JSON 405 with `Allow` and the security headers.
  - *BUG-15* lists `webbrowser` as a dead import (correct) and `webapp.RequestError`
    as unused (wrong): `tests/test_compatibility.py` pins that re-export.  The
    import is restored and documented as deliberate.
- **Fixes:** the loader marks any name failing the canonical rule
  `addressable: false` and surfaces an `unaddressable` state (BUG-10, SCOPE-14);
  an undecodable document no longer reports replacement-character text as its
  description (BUG-10); one rogue index row can no longer abort
  `scan_scope("global")`, `list_all()` and `search_all()` together (SCOPE-15);
  `_both_load`/`_facade_warnings` are inside the shared `MAX_INSTANCES` budget and
  report truncation (SCOPE-16); `HOME=""` no longer relocates every agent scope to
  `/` and a relative data-dir override is anchored absolutely (SCOPE-17); the flat
  path short-circuit no longer accepts a grouping directory in place of the skill
  (SCOPE-18); `create_template` creates the directory before taking the lock
  (BUG-11); the `_MUTATION_LOCKS` table is bounded and evicts only provably free
  locks (BUG-12); all nine `except Exception: pass` blocks in `webapp.py` now
  diagnose and, where a client is affected, report the degradation in the payload
  (BUG-8); `check_package_data.py` refuses builds shipping `tests/`, `docs/`,
  `.env`, databases or bytecode (BUG-13); the SHA-pin contract now matches
  reusable-workflow refs (BUG-14); the dead `_scopeParam`/`_scopeQs`/`esc`
  export/`_dump_scalar_value`/`_dump_block_item` and a dead local are removed
  (BUG-15, frontend + frontmatter).
- **STORE-14** closed in both directions: the five false claims in
  `docs/04-store-api.md` are corrected to match the implementation, **and** three
  latent defects the finding listed as likely are fixed — a failed re-create no
  longer erases the original `create` history row, a failed full-import rollback
  is now reported instead of swallowed, and a user's own `notes.tmp` no longer
  turns `doctor().ok` into `False`.
- Per-finding disposition: @docs/13-audit-remediation-status-2026-09-11.md.

## 2026-09-11 — Deep-audit remediation, batch 3: Store integrity (7 findings)

- **Source:** `DEEP-AUDIT-2026-09-11.md` — **STORE-6**, **STORE-7**, **STORE-8**,
  **STORE-9**, **STORE-10**, **STORE-12**, **STORE-13**.  Authored by a
  **parallel session** in the same working tree (see *Concurrent writers* in
  @AGENTS.md); finished off and verified here.
- **Verification:** `python3 -m unittest discover -s tests` — **564 tests OK**.
  Both smokes, `check_docs.py` and `check_complexity.py` PASS.
- **Fixes:** `purge_trash` no longer holds one write transaction across every
  `rmtree` (a concurrent writer used to time out and fail with a raw
  `sqlite3.OperationalError`); `remove(purge=True)` displaces the tree before
  deleting it, so a partial purge cannot advertise a skill whose document is
  already gone and never leaks a raw `PermissionError`; `export()` is atomic, no
  longer reuses a second-resolution filename, and leaves no truncated archive;
  `export`/`tree_content_hash` no longer follow symlinks (an archive containing
  one used to be rejected by the store's own `import_`); `list`/`get`/`search`
  and `stats` count filesystem truth rather than index residue; `resync` and
  `db_rebuild` take the shared library lock; and `doctor` sees document-less
  directories as drift while still not mistaking its own staging markers for
  husks.
- **Finished here, because batch 3 landed incomplete:**
  - its `test_remove_purge_never_advertises_a_destroyed_skill` raised
    `FileNotFoundError` from its own `addCleanup` (a failed purge *displaces* the
    tree, so the teardown chmod'd a vanished path). The product behaviour was
    already correct; the teardown now restores permissions wherever the tree
    ended up, with every original assertion kept.
  - its `test_resync_holds_the_skills_directory_lock` locked a hand-written path
    (`<data>/skills`) while the shared key is
    `<data>/skills/.skillsmgr-index-lock`, so it failed against correct code. It
    now resolves the key through the module's own `_index_lock_path`, and a new
    sibling test pins the *property* (resync and create share a lock) so a future
    lock redesign cannot silently stop testing anything.
  - the **complexity ratchet was red** on four functions batch 3 had grown
    (`Store._scan_dir` 1→5, `Store.edit` 2→3, `Store.purge_trash` 4→6,
    `Store.stats` 5→9). Restored by **refactoring, not re-baselining**: five
    extractions (`_without_transaction_artifacts`, `_skill_and_index_locks`,
    `_purge_trash_files`, `_drop_trash_rows`, `_live_index_totals`,
    `_skills_tree_size`) with no behaviour change and no baseline masking.
- **Independent verification:** each batch-3 finding was spot-checked against the
  audit's own described symptom rather than trusting its tests. STORE-10 keeps its
  documented shape: `get()` reports `installed: False` instead of raising, which
  matches the existing trashed-skill contract.
- Per-finding disposition: @docs/13-audit-remediation-status-2026-09-11.md.

## 2026-09-11 — Deep-audit remediation, batch 2: precedence and scope-identity defects

- **Source:** `DEEP-AUDIT-2026-09-11.md`, continuing the remediation order from
  the first batch (items 20-21).  Five findings: **SCOPE-6**, **SCOPE-7**,
  **SCOPE-9**, **SCOPE-10**, **SCOPE-11**.  No locked constraint moved.
- **Verification:** `python3 -m unittest discover -s tests` — **542 tests OK**
  (three consecutive clean runs; batch 1 closed at 530).  `check_docs.py` and
  `check_complexity.py` PASS, both smokes PASS.

**SCOPE-6 — `explain()` over-claimed and contradicted itself** (`effective.py`).
`_overall()` returned the policy outcome — `resolved` — whenever no ambiguity
was present, *including* when every skill was `no-instances`, so a report could
say `resolved` while every entry under it said nothing was installed.  It is now
derived from the per-skill resolutions: `no-instances` when no skill holds one,
`partially-resolved` when some do and others do not, `both-load-only` when the
only loadable copies are nested ones.  Separately, a nested-only Claude skill was
reported `no-instances` with the reason "no loadable instance … in any documented
root" while that entry's own `also_loads` list held the very loadable instance;
it is now `both-load-only` with those instances as its `candidates`.  Confirmed
before/after: `[A]` disabled-only → `resolved`→`no-instances`; `[B]` nested-only
→ `no-instances`→`both-load-only`; `[C]` mixed → `resolved`→`partially-resolved`.

**SCOPE-7 — no physical-root deduplication** (`effective.py`).  The module never
used `root_discovery.resolved_root`, so a root reached through a symlink was
scanned twice: `.gemini/skills -> .agents/skills` produced two candidates for one
file and a false `ambiguous`, and in an ordered policy the winner was listed as
its own `shadowed` copy (`.claude/skills -> ~/.claude/skills` reported
`winner: personal` *and* `shadowed: [project]` for the same inode).  Reads are now
claimed by physical identity through a shared `physical_roots` set across tiers
and the both-load scan; an already-scanned alias is recorded per tier as an
`alias` rather than silently dropped, and an alias of the winner is filtered out
of `shadowed`.  This is ADR-002 invariant 1 ("aliases and symlinks do not create
a second root") applied to the diagnostic.

**SCOPE-9 — "global" had two identities** (`scopes.py`).  `known_scopes()`
derived the global root from the *environment* while `scan_scope("global")`
derived it from the *injected `Store`*.  With an injected Store on another data
dir they disagreed: `sync_skill(..., ["global"])` reported
`{'synced': ['global']}` while writing into a tree that `store.list()`,
`scan_scope("global")`, `list_scopes()` and `get_skill("global", …)` could not
see (the audit measured five views disagreeing).  `_global_skills_dir()` is now
the single source: the injected Store's own tree when one is injected, otherwise
the environment-derived data dir.  After the fix the sync lands in the store's
data dir and all five views agree.

**SCOPE-10 — module-global store cross-talk** (`scopes.py`, `webapp.py`).  The
injectable global store was a plain module global, so the last
`set_global_store()` won for every caller in the process: with two in-process
`WebAppServer`s on different data dirs, server A's `?scope=all` answered with
server B's skill and an agent-scope edit made through A wrote its snapshot into
**B's** data dir.  `_GLOBAL_STORE` is now a `ContextVar` (per-thread), and
`_StoreBoundHTTPServer.process_request_thread` binds the server's own store at
the start of each request thread.  Measured after the fix: A returns `a-only` for
both `?scope=global` and `?scope=all`, B returns `b-only`, and A's snapshot lands
in A's data dir with B's untouched.

**SCOPE-11 — `list_all()` erased the duplicate signal** (`scopes.py`).  The
dedupe key was `(scope, name)`, which is wrong for a *recursive* scope: the
documented monorepo shape (`apps/*/<root>/`) can hold two genuinely different
skills with the same name.  The second was dropped, the survivor was
re-annotated `['active']`, `find_duplicates()` reported nothing, and the All view
disagreed with both `scan_scope` and the summed `/api/stats` counts (3 vs 2).
The key now includes the on-disk path; both copies are listed, both carry
`duplicated`/`divergent`, and `len(list_all())` matches the per-scope count.

**New tests (12):** `tests/test_effective_explain_contracts.py` —
`TestOverallResolutionHonesty` (5) and `TestPhysicalRootDeduplication` (3);
`tests/test_scope_contracts.py` — global identity and same-name listing (2);
`tests/test_web_scopes.py` — `TestTwoServersDoNotCrossTalk` (2, covering both the
read cross-talk and the snapshot-write cross-talk).  Every one was confirmed red
against the pre-fix code before being made green.

**Not changed, deliberately:** `find_duplicates()` still reports only *cross-scope*
same-name groups — its documented contract.  The within-scope duplicate is now
visible through `instance_states` on both rows instead.

## 2026-09-11 — Deep-audit remediation: 20 findings fixed

- **Source:** `DEEP-AUDIT-2026-09-11.md` (102 findings across seven subsystems,
  baseline commit `0b82094`).  Twenty findings were remediated in dependency
  order, each with its own red-first regression test.  No locked constraint
  moved: filesystem stays the source of truth, `SCHEMA_VERSION = "1"` is
  unchanged, the CLI stays stdlib-only, the web UI stays stdlib-backend with no
  build step and still binds loopback, and no new CLI command or `Store` method
  was introduced.
- **Verification ladder:** `python3 -m unittest discover -s tests` — **530 tests
  OK** (baseline was 477; every fix added its own contract).  `smoke_store.py`
  and `smoke_web.py` — both PASSED.  `check_docs.py` — PASSED.
  `check_complexity.py` — PASSED (the six functions whose complexity moved were
  refactored so the checked-in ratchet stays flat).  `node --check` on
  `webui/app.js` and `webui/domain.js` — clean.

**Data loss / unrecoverable state (1-6)**

- **FM-1** — an indented `---` inside a multi-line value terminated the
  frontmatter block early, silently truncating the value *and* promoting the
  rest into the body, which every write path then persisted.
  `_find_closing_marker` now skips block-scalar content; a bare `---` at column
  zero still closes.  (`frontmatter.py`)
- **STORE-1** — an interrupt (Ctrl-C) in `import_`'s commit move escaped the
  `except Exception` rollback, and the caller then deleted the staging directory
  holding the user's only copy.  The rollback is now `except BaseException` and
  `moved_original` is cleared once the original is truly gone.  (`archive.py`)
- **STORE-3 / SCOPE-13** — `add()` installed a directory holding both `SKILL.md`
  and `SKILL.md.disabled`; a later toggle renamed one over the other and
  destroyed it silently.  The one-document invariant is now enforced in `add`,
  `disable`, `enable`, `scopes.toggle_skill`, and reported by
  `doctor.conflicting_documents` (so `ok` is False).  (`store.py`, `scopes.py`,
  `loader.py`)
- **STORE-4** — `import_(force=True)` displaced and replaced a document while a
  concurrent `edit()` was mid-write, discarding a committed edit with
  `doctor()` reporting healthy.  `import_` now takes the destination's
  per-skill lock.  (`store.py`)
- **STORE-5** — `restore()`/`purge_trash()` raced: a raw `FileNotFoundError`
  escaped, and a lost race left a `trashed` row that `resync()` could never
  repair.  Both now share one trash lock, `restore()` translates move failures
  into `StoreError`, and `resync()` reconciles `trashed` rows with no trash
  copy.  (`store.py`)
- **STORE-2** — `add()` copied into the live tree with no lock, so a concurrent
  `remove()` left a husk `doctor()` called healthy.  `add()` now holds the
  per-skill lock and copies to a staging sibling renamed into place.  (`store.py`)

**Crashes on one bad file (7-10)**

- **FM-2** — a top-level YAML sequence returned a `list`, so every consumer died
  with a raw `AttributeError`.  It is now a clean `FrontmatterError`.
- **FM-3 / FM-4** — out-of-range `\U` escapes raised raw `ValueError`/
  `OverflowError`, and lone surrogates parsed fine then killed every write with
  `UnicodeEncodeError`.  Both are `FrontmatterError` at parse time.
  (`frontmatter.py`)
- **BUG-1** — `Store.create()` on a fresh data dir raised a raw
  `sqlite3.OperationalError`; the rollback failed the same way.  `create` now
  bootstraps the schema, and `_open_index_db` / `_bootstrap_schema` /
  `_commit_history` / `_upsert_entry` translate driver errors into `StoreError`
  so none can reach the CLI's "unexpected error" path.  (`store.py`)
- **SCOPE-4** — one unreadable `SKILL.md` aborted every scope view with a raw
  `PermissionError` (all three REST routes answered 500).  `read_skill_or_report`
  turns it into a `malformed` row carrying the reason.  (`loader.py`)

**Remote attack surface (11-13)**

- **SEC-1** — the Host/Origin/Fetch-Metadata policy ran only for mutating
  methods, so any web page could read the whole library and the full export
  archive.  `validate_mutation_request` is renamed `validate_request` and now
  guards `do_GET` too, closing the tracked DNS-rebinding gap (#14).
- **SEC-3** — `GET /api/doctor?explain=…` returned the user's real
  `~/.agents/skills` + `~/.cursor/skills` inventory, the home directory, and
  `data_dir`.  `effective.explain` now takes an `allowed_root` boundary and
  redacts every path outside it; the HTTP layer always passes one.
- **SEC-2** — `MAX_ROOTS` bounded results, not work, so `project=/` walked the
  filesystem to completion.  `_bounded_walk` is an `os.scandir` walk bounded by
  entries visited and depth, and a project outside the boundary is not walked at
  all (`project-outside-managed-roots`).  (`effective.py`, `webapp.py`)

**Untrusted input (14-16)**

- **CLI-1** — a regex assertion in a hostile `evals.json` hung the CLI forever
  and froze the web-UI process GIL-wide (Ctrl-C could not run).  Every pattern
  now runs under a `SIGALRM` wall-clock budget and aborts as a failed assertion;
  off the main thread it is refused instead of risking a hang.  (`evals.py`)
- **CLI-2 / SCOPE-12** — a control character in a `--metadata` key wrote a
  document the tool cannot parse (exit 0 throughout, `doctor` said ok), and a
  later `edit` emitted a *second* frontmatter block.  Keys are validated, the
  dumper refuses an unwritable key, and both `Store.edit` and
  `scopes.edit_skill` now fail closed on an unparseable document, mirroring the
  undecodable-document policy.  (`cli_handlers.py`, `frontmatter.py`, `store.py`,
  `scopes.py`)
- **CLI-3** — hostile descriptions/categories printed raw ANSI, spoofing
  `list`/`view` output and corrupting column widths.  `cli_output.sanitize_text`
  replaces C0/C1/DEL, line separators, and format characters at the display
  seam (`truncate`, `render_table`, the `view`/`stats` field printers).

**Correctness and silent failure (17-20)**

- **FM-5, FM-6, FM-7, FM-8, FM-10, FM-12, FM-14** — the block-scalar round-trip
  group: eaten common indentation, lost whitespace-only lines, stripped CR content,
  values truncated by a tab before `#`, `\n`-only values collapsing to `''`, and
  mis-chomped trailing blank lines.  **FM-9 is only partially closed** (a key the
  dumper cannot render now raises instead of emitting unparseable output, but the
  escaped-key round trip is not implemented) and **FM-11 is untouched** — the
  fixed IDs are enumerated here because the earlier `FM-5..FM-12` range wrongly
  read as a claim about FM-11.  Per-finding status: @docs/13-audit-remediation-status-2026-09-11.md.  The dumper now emits a correct header
  (`|-`/`|`/`|+` plus a `2` indentation indicator when needed), quotes
  whitespace-only values, treats a `:` before whitespace as a key separator, and
  the parser keeps whitespace-only lines and treats an indicator as
  parent-relative.  A 20,000-case scalar fuzz and a 6,000-case nested-structure
  fuzz both round-trip exactly (previously 1,517 failures in 6,000).  A bare
  `- |` sequence element now parses instead of tripping the indentation guard.
- **BUG-2** — `loader`/`effective` called a document with no `name`/`description`
  `loadable` while `validate_skill` reported two errors, so `doctor --explain`
  gave a confidently wrong answer.  `required_field_gaps` aligns them.
- **SCOPE-1 / SCOPE-2 / SCOPE-3** — the symlink policy now lives in one place:
  `sync_skill` copies with `symlinks=True` and refuses a link that escapes the
  skill (an 88-byte skill used to exfiltrate 65 KB into another agent scope); an
  escaping link in a scope root is reported as drift instead of being invisible
  to reads while blocking every write; and `contained_entry` preserves the
  *named* entry, so `get_skill('alias')` reports `alias` and `remove('alias')`
  moves the link instead of destroying its target.  (`scopes.py`,
  `path_safety.py`, `loader.py`)
- **BUG-5 / BUG-3 / BUG-4 / BUG-6 / BUG-7** — the frontend: the destructive
  remove modal is bound to the record it was opened for (it re-derived the scope
  at confirm time and could remove the wrong skill permanently); `selectSkill`
  compares the scope as well as the name; a live query is re-applied on a scope
  change and when re-entering the skills view; `modals.validate.error` is
  rendered; and the budget tooltip uses `formatTokens` instead of an unguarded
  `toLocaleString()`.  Pinned by the new `tests/test_webui_contracts.py`.

**New tests added:** `tests/test_webui_contracts.py` (5 frontend state
contracts) plus 48 new assertions across `test_frontmatter_contracts.py`
(FM-1..FM-12, FM-14, block-scalar fidelity), `test_store.py` (STORE-1..STORE-5,
BUG-1), `test_archive_contracts.py` (STORE-1, STORE-4), `test_scope_contracts.py`
(SCOPE-4), `test_web_scopes.py` (SCOPE-1/2/3), `test_webapp.py` and
`test_web_client_contracts.py` (SEC-1), `test_effective_explain_contracts.py`
(SEC-2, SEC-3, BUG-2), `test_eval_harness_contracts.py` (CLI-1), and
`test_cli_contract.py` (CLI-2, CLI-3).

## 2026-09-11 — Remaining issues #6, #7, #8, #9, #11 resolved; two new findings filed (#14)

- **The five remaining issues are decided and closed**, each with its verdict made
  executable rather than restated. No locked constraint moved: filesystem still
  the source of truth, schema and `SCHEMA_VERSION = "1"` frozen, CLI
  stdlib-only, web UI still dependency-free and loopback-only, and no new CLI
  command or `Store` method.
- **#6 (Python < 3.12 tar policy) — closed as not-planned; decision pinned.**
  `tests/test_path_safety.py::TarFallbackPolicyPins` now (a) replaces
  `tarfile.data_filter` with a permissive pass-through — the CVE-2025-4138
  bypass shape — and asserts the archive is still refused by our own
  pre-validator, (b) proves the no-filter (3.10/3.11) branch rejects a traversal
  member and writes nothing, and (c) imports successfully through both
  capability branches. The recorded rationale (feature-detect per PEP 706;
  refusal would break the supported matrix for zero fail-closed gain; the
  independent validator is the real defense) is unchanged.
- **#7 (out-of-root link severity) — closed as not-planned; decision pinned.**
  `tests/test_link_severity_contracts.py` pins that parent-escape, absolute, and
  legitimate sibling/monorepo-relative links warn while `valid` stays True, that
  in-root-missing and external/anchor targets keep their own classifications,
  and that `risk_scan()` still carries the medium finding that replaced
  enforcement. A promotion guard asserts the issue level stays `warning`, so a
  future severity bump fails loudly instead of silently breaking monorepo
  layouts.
- **#8 (VS Code extension) — closed as not-planned for this repo; contract
  verified and documented.** `tests/test_web_client_contracts.py` empirically
  proves backend sufficiency for an editor client: the read/edit endpoints it
  needs answer, the header-absent extension-host mutation path is allowed by
  design, cross-site browser requests stay 403, no CORS headers are advertised,
  errors stay JSON, and the bind is loopback-only (a non-loopback bind raises
  `StoreError`). `docs/08-web-ui.md` gained a "Local client integration contract"
  section recording what a client must know. The extension itself stays a
  separate repository.
- **#9 (desktop wrapper) — rejected direction upheld, the one allowed artefact
  shipped.** `desktop_launcher.py` (repo root, outside the wheel, no new
  dependency) serves the existing stdlib UI on loopback and opens it in a
  Chromium-family `--app=` window, falling back to the default browser when none
  is installed, and refuses any non-loopback `--host`.
  `tests/test_desktop_launcher_contracts.py` pins the boundary: stdlib-only
  imports, no packaged entry point, no webview import anywhere, `webui`/`gui`
  still canonical, plus host validation, browser preference/fallback, and the
  serve/shutdown flow.
- **#11 (team sharing) — design scope closed.** The required
  design-before-code artefact now exists:
  @docs/ADR-004-team-sharing-signed-bundles.md records that stdlib-only rules out
  Ed25519/X.509, selects HMAC shared-secret integrity as the only available
  option together with its honest limit (group authenticity, not individual
  authorship), sketches the canonical-MAC bundle extension, maps
  draft → review → publish onto existing filesystem seams with no schema change,
  and lists the blocking decisions. The matching threat-model delta is recorded
  (T-13, R-6, plus recommendations 4-6). No bundle format, signing code, CLI
  surface, or `Store` method was added.
- **Two findings from those probes were filed, not silently fixed — issue #14.**
  (1) F-1: the pre-handler request policy runs only for state-changing methods,
  so reads are not `Host`-validated; a DNS-rebound page whose origin *is* the
  rebound host can read skill metadata and full document bodies (measured:
  `GET /api/skills` and `/api/skills/<name>/raw` return 200 with
  `Host: evil.example`, while the same `Host` gives 403 on `POST`). The no-CORS
  reasoning covers ordinary cross-origin reads but not that shape.
  (2) F-2: with the default `127.0.0.1` bind, `allowed_hosts` holds only
  `127.0.0.1:<port>`, so a client configured with the equally-loopback
  `localhost` name gets 403 on every state-changing call — a concrete
  integration limitation for editors. Threat-model rows T-14/R-7 record F-1 as
  **open**, and the read-path behavior is pinned in the client-contract test as
  characterization with a pointer to #14 so a fix fails loudly until updated.
- **Verification:** 477 `unittest` tests OK (up from 435); `smoke_store.py` and
  `smoke_web.py` PASS; `check_docs.py` PASS; `check_complexity.py` PASS (164
  functions); the launcher was also run for real against a temp data dir
  (`GET /`, `/api/stats`, `/api/skills` all 200).

## 2026-09-11 — Issues #3, #4, #5, #12, #13 closed out (one bug fix + one diagnostic)

- **Issue #13 — non-UTF8 `SKILL.md` no longer escapes as a raw
  `UnicodeDecodeError`.** Contract decided and pinned: *read/report paths
  tolerate, write paths fail closed*. `loader.read_skill_text()` decodes UTF-8
  and, on failure, keeps the document readable with U+FFFD while returning an
  actionable message (file, offending byte, offset, fix); `load_skill()` marks
  the row `malformed` and adds `decode_error`, so the directory stays visible
  (filesystem is the source of truth) and `root_discovery`/`insights` classify
  it `invalid` as before. `Store.doctor()` gained the explicit
  `undecodable_documents` drift class (included in `ok`; the CLI names the
  skills and the fix), and `Store.list`/`get` now surface
  `malformed`/`decode_error` for global rows. Mutation paths that would rewrite
  a document from text read back (`Store.edit`, `Store.restore`,
  `read_snapshot`, `scopes.get_raw`, `scopes.edit_skill`,
  `scopes.restore_snapshot`, `scopes.sync_skill` overwrite) use
  `loader.read_skill_text_strict()` and raise a clean `StoreError` naming the
  skill and the fix, leaving the file byte-identical — lossy replacement
  characters can never reach a write. The validator reuses the same message
  instead of a bare codec error. Answering the issue's second question: the
  agent-scope readers get the same treatment (the reporting readers were
  already inside broad `except Exception` guards; the text-returning and
  editing readers now fail closed cleanly). `Store.doctor`'s artifact discovery
  was extracted into `_doctor_artifacts`/`_stale_snapshots`/`_is_*` helpers so
  the new drift class does not grow a baselined hotspot (complexity ratchet
  satisfied without a baseline update). Tests:
  `tests/test_encoding_contracts.py` (23).
- **Issue #12 — read-only effective-resolution diagnostic shipped.** New
  stdlib-only `skillsmgr/effective.py` derives, at read time, which instance of
  a skill a consumer would load for a `(consumer, project-CWD, skill)` triple,
  surfaced as `doctor --explain CONSUMER [--project DIR] [--skill NAME]` and
  `GET /api/doctor?explain=…`. The locked constraints are untouched: no new CLI
  command (an approved flag on `doctor`), no new `Store` method, no SQLite
  access or schema change, no persistence, and `effective_state` stays
  `unresolved` (ADR-002). Per-consumer rows are cited to
  @docs/12-agent-root-discovery-2026-09-08.md and never invented — Command Code
  six-way order, Codex no-merge (no winner elected), Claude personal > project
  with nested copies reported under `also_loads` because they both load,
  Gemini built-in < extension < user < workspace with same-tier ties reported
  `ambiguous`, and Cursor/Opencode `undocumented-precedence`. Unknown consumer
  → `unknown-consumer` (exit 1), missing project → `missing-project` (exit 1),
  and a diagnostic that legitimately resolves nothing exits 0. Unobservable
  documented tiers are listed with a provisional-win warning; the `codex`
  facade id is warned as compatibility-only; disabled/invalid instances are
  reported under `skipped` and can never win. Read-only proof: tree-hash
  equality across every consumer plus a no-database assertion. Tests:
  `tests/test_effective_explain_contracts.py` (36).
- **Issues #3, #4, #5 — verified and closed.** The offline registry bridge
  (issue #3) and the file-based eval harness (issue #4) landed as
  @docs/ADR-003-registry-bridge-and-eval-harness.md describes; this session
  re-verified both end to end (registry preview with audit links and the trust
  gate; `validate --evals`/`--evals-run` recording `iteration-N/eval-*/`
  workspaces with a benchmark delta and no SQLite rows) and committed them.
  ZIP import (issue #5) was already on `main`; re-verified hermetic parity with
  tar plus a hostile-zip probe (traversal member rejected, nothing written
  outside staging).
- **CI flake found and fixed.** The second CI run on this work failed on
  `py3.10` in `test_record_runs_never_touches_skill_files_or_the_index`:
  `Store.list()` decorates rows with observations computed at read time and
  `observed_at` is stamped with `datetime.now()`, so comparing rows before and
  after a recording run straddles a UTC second boundary and fails even though
  nothing was written. The test now drops the read-time stamp before comparing
  persisted state (the same fix `tests/test_webapp.py` already applies in its
  `_persisted()` helper); the test passes 20/20 in isolation and the full suite
  3/3. CI is green on the fixing commit.
- **Second CI failure on `py3.10`, found and fixed the same way.** The launcher
  boundary pins imported `tomllib`, which is Python 3.11+ while the project
  declares `requires-python >= 3.10` and CI runs 3.10 as its floor
  (`ModuleNotFoundError: No module named 'tomllib'`). The packaging pins now read
  `pyproject.toml` as text through a small `section()` helper, so the
  outside-the-wheel / no-extra-console-script / no-dependency assertions hold on
  every supported interpreter, and the three assertions were split so a failure
  names its own boundary. An AST scan confirms no 3.11+-only stdlib import
  remains in `tests/` or `desktop_launcher.py`. Suite is 477 tests; CI green on
  the fixing commit. Lesson recorded: local 3.12 cannot vouch for the 3.10 floor,
  so a new test file's imports deserve the same 3.10 check as product code.
- **Verification:** 435 `unittest` tests OK; `smoke_store.py` and
  `smoke_web.py` PASS; `check_docs.py` PASS; `check_complexity.py` PASS. No
  locked constraint changed: filesystem still the source of truth, schema and
  `SCHEMA_VERSION = "1"` frozen, CLI stdlib-only, web UI still dependency-free
  and loopback-only.

## 2026-09-10 — Registry bridge (offline) + eval harness (file-based) shipped

- **Scope decision recorded in @docs/ADR-003-registry-bridge-and-eval-harness.md**:
  both TODO items shipped their approved offline/file-based halves by extending
  existing surfaces only. No new CLI command, no new `Store` method, no SQLite
  change, no runtime dependency, no network access. Network browse/fetch for the
  registry (issue #3) and any eval runtime backend/provider (issue #4) remain
  deferred, exactly as their verdicts require.
- **Registry bridge (offline half)**: `insights.registry_reference()` parses
  `owner/repo`, `owner/repo/slug`, `https://skills.sh/{source}/{slug}`, and
  `https://github.com/owner/repo` offline with per-segment length caps and
  rejection of traversal/separators/absolute paths/foreign hosts;
  `insights.registry_bridge_plan()` maps a registry skill id onto the exact
  `npx skills add … -s <slug>` command, keeps the explicit-trust gate
  (`blockers`/`may_install`), surfaces the linkable
  `/owner/repo/skill/security/{provider}` audit pages, and carries the
  `content_hash` slot for change detection. `insights.install_argv()`/
  `install_command_line()` are now the single renderer for the printed dry-run
  text, the executed argv, and the plan, so preview and reality cannot drift.
  Surfaces: `install --preview [--trust-confirmed] [--registry-hash HEX]` and
  `POST /api/install {preview: true, …}`; the executed install path, runner
  allowlist, dry-run-first posture, and the legacy REST payload shape are
  unchanged. Absent registry metadata is reported as `description_status`/
  `provenance_note` instead of being invented (an authenticated catalog read is
  still deferred).
- **Eval harness (file contract)**: new stdlib-only `skillsmgr/evals.py`
  implements the official evaluating-skills layout — `evals/evals.json` cases
  (`id`/`prompt`/`expected_output`/`files`, optional `slug`, optional
  deterministic `assertions`), `iteration-N/eval-<slug>/{with_skill,without_skill}/`
  with `outputs/output.txt`, `grading.json`, and `timing.json`, plus a
  per-iteration `benchmark.json` carrying per-variant case pass rates and the
  `with_skill` − `without_skill` delta. Assertions are the deterministic subset
  (`equals`, `contains`, `not_contains`, `regex`, `is_json`); a case with no
  assertions is recorded `graded: false`, never as a pass. Surfaces:
  `validate --evals` (read-only), `validate --evals-run FILE` (explicit
  recording, single target), `--workspace DIR` (CLI-only), and
  `POST /api/validate {evals: true}` / `{runs: […], iteration?}`. Workspaces
  default to `<data>/evals/<name>-workspace` — deliberately outside `skills/`,
  so the skill scan, `doctor` orphan detection, export, and the SQLite index
  never see run data. With `--path`, the beside-the-skill layout is used only
  when that directory is outside the store's `skills/` tree (otherwise it falls
  back to the store workspace — a sibling workspace inside `skills/` would be
  scanned as skill data). Recording uses atomic
  sibling-temp writes and provably leaves skill files and the index untouched.
- **Advisory invariants held**: eval findings never change `valid` or the exit
  code, scores never gate installs or edits, no score or registry value is
  persisted in SQLite, and one test pins that the bridge modules import no
  network client (`urllib.request`, `http.client`, `socket`, `ssl`).
- **Bug found and fixed while wiring**: the first bridge plan made a missing
  registry `description` a hard install blocker, which made `may_install`
  unreachable from the CLI (there is no way to supply registry metadata without
  the deferred API read). Description is now reported as provenance state, and
  trust remains the only blocker.
- **Verification**: `python3 -m py_compile skillsmgr/*.py` PASS;
  `python3 -m unittest discover -s tests` → **376 OK** (317 prior + 21 registry
  + 38 eval); `smoke_store.py` PASS; `smoke_web.py` PASS;
  `node --check skillsmgr/webui/app.js` PASS; `check_docs.py` PASS (ADR-003
  added to the enforced current-doc set); `check_complexity.py` PASS
  (**159 functions**, new functions ≤ 15; moving the `/api/install` and
  `/api/validate` payload construction into helpers lowered `_route_post`
  complexity from 88 to 81);
  `--help` PASS; `git diff --check` PASS.
- **Docs**: new `docs/ADR-003-registry-bridge-and-eval-harness.md` (plus the
  `docs/README.md` map entry and the `check_docs.py` current-doc set),
  `docs/02-modules.md` (insights additions + new `evals.py` row),
  `docs/03-cli-surface.md` (`install` and `validate` flags),
  `docs/08-web-ui.md` (`/api/install` preview and `/api/validate` eval fields),
  `docs/01-architecture.md` (`evals/` subdir and workspace placement),
  `ROADMAP.md`, `TODO.md` (#3/#4 shipped halves vs remaining deferrals),
  `task.md` (Milestone 48), and `docs/SESSION-CONTEXT.md`.

## 2026-09-10 — `skill-control-plane` 1.0.1 published successfully

- The release workflow completed successfully through TestPyPI, PyPI, GitHub
  Release, provenance attestation, and post-publish install/CRUD verification.
- The published distribution is `skill-control-plane`; Python imports remain
  `skillsmgr`, the executable remains `skills-mgr`, and the repository and
  internal data/database names remain `skills-manager`.
- README installation guidance now points to the published PyPI project with
  `pip install skill-control-plane` and `pipx install skill-control-plane`.
- This append-only documentation cleanup performs no publication, tag, or push.

## 2026-09-10 — Distribution renamed to `skill-control-plane`

**HISTORICAL/SUPERSEDED pre-publish record:** Publisher registration and GitHub
release environments were complete. The then-pending repository action was to
create and push tag `v1.0.1`; the subsequent release workflow completed
publication successfully, as recorded in the newer entry above.

- Package/release identity was set to `skill-control-plane`; Python imports
  remain `skillsmgr`, the executable remains `skills-mgr`, and the GitHub
  repository remains `udayvarmora07/skills-manager`.
- Release verification and README install commands used the new distribution
  only where artifact/PyPI identity was required. Internal data paths, database
  names, product terminology, repository URLs, and historical release facts
  intentionally retained `skills-manager`.
- PyPI and TestPyPI trusted publishers were registered for distribution
  `skill-control-plane` against `release.yml`; no tag or publication had yet
  occurred.


**AI manifest**: Dated, append-only record of changes, decisions, and bugs for skills-manager. Read before/after every session (docs/README.md reading order). Newest entry on top.

## 2026-09-10 — Historical worktree cleanup (unmerged branches archived)

- Inspected the two genuinely unmerged historical worktrees against current `main`:
  `agents/todo-plan-implementation` (2 commits) and
  `agents/milestone5-research-user-needs` (1 commit), both based at `667fabb`.
- Confirmed their substantive recovery, archive, ZIP, parser, search, and UI work
  is already present on `main` in the stronger evolved implementations; neither
  branch was merged wholesale or cherry-picked. Current verification remains
  **317 unittest OK**, both smoke suites PASS, frontend syntax PASS, and diff
  checks PASS.
- Archived the exact historical tips as local tags
  `archive/todo-plan-implementation-2bb7280` and
  `archive/milestone5-research-user-needs-c5a7161`, then removed only those two
  clean worktrees and local branches. The three other historical worktrees remain
  untouched because they are dirty and/or may still carry active work.
- `.autogit` remains unmodified and untracked by policy. No product behavior or
  SQLite schema changed in this cleanup.
 Facts flagged stale here are corrected in the owning doc.

## 2026-09-10 — `v1.0.1` prepared and release infrastructure created

**HISTORICAL/SUPERSEDED release-preparation record:** This entry preserves
pre-registration and pre-environment observations. Publication is recorded in
the newer entry above; this historical entry is not the current release state.

- Version bumped to `1.0.1` in the four places the repository enforces:
  `pyproject.toml`, `skillsmgr/__init__.py`, `docs/01-architecture.md`, and
  `docs/02-modules.md` (the last two are pinned by `check_docs.py`; the earlier
  rehearsal is what identified them). The workflow's tag/version gate was
  simulated locally: `v1.0.1` == `pyproject` == `__version__`.
- GitHub environments created via the API: `testpypi` (plain) and `release`
  with a `required_reviewers` rule naming `udayvarmora07`, and
  `prevent_self_review: false` so a single maintainer can approve their own tag
  push instead of deadlocking the publish job. Verified by reading the
  environment back (`environments: 2`).
- The earlier exact artifacts remain historical `skills_manager-1.0.1` records;
  after the distribution rename, fresh release artifacts must be named
  `skill_control_plane-1.0.1-py3-none-any.whl` and
  `skill_control_plane-1.0.1.tar.gz`. `check_package_data.py --dist-dir` must
  PASS on both (5 web UI files, Vue 157,924 B); the wheel clean-installs into a fresh venv with
  `--no-index --no-deps` and reports `skills-mgr 1.0.1`; the sdist installs with
  `--no-deps --no-build-isolation` and reports the same, with the vendored Vue
  bundle and `webui/domain.js` present. Full ladder on the bump: 315 unittest OK,
  both smokes PASSED, `check_docs.py` PASSED, complexity PASSED (157 functions),
  frontend syntax OK, compile OK, `git diff --check` OK.
- **Recorded gotcha (found by a false verification result):** a stale,
  gitignored `skills_manager.egg-info/` in the repo root (PKG-INFO `Version:
  1.0.0`, left by a 2026-09-10 in-tree build) shadows the *installed*
  distribution for `importlib.metadata` whenever Python runs with the repository
  as cwd, so `importlib.metadata.version("skills-manager")` reported `1.0.0`
  while the artifact was `1.0.1`. The stale tree was quarantined and the check
  re-verified from both the repo cwd and a neutral cwd. CI is unaffected: a fresh
  clone has no `egg-info`, and both post-publish verification steps compare
  `skillsmgr.__version__` or install into a new venv.
- **HISTORICAL/SUPERSEDED post-publish follow-up:** Before publication, README
  line 9 and its pinning test carried a future-release claim. The newer entry
  records their update after the successful publish.
- **HISTORICAL/SUPERSEDED external blocker:** publishing then needed the PyPI
  **and** TestPyPI trusted publishers to be registered under the maintainer's
  account (`pypi.org/manage/account/publishing/`,
  `test.pypi.org/manage/account/publishing/`), which was a web login no API
  could perform. Nothing was tagged or published in that historical state.

## 2026-09-10 — Release-pipeline rehearsal for a candidate version

- The `release.yml` build + verify half was rehearsed against a clean
  `git archive HEAD` copy with a candidate version (`1.0.1`) applied **only in
  the copy**, so the remaining publication path is proven rather than assumed:
  `RELEASE_TAG=v1.0.1` passes the workflow's tag/version gate
  (`tag == "v" + version`), `python -m build --wheel --sdist` succeeds,
  `check_package_data.py --dist-dir` PASSes on the exact candidate artifacts,
  all 315 unittest pass, `check_docs.py` PASSes, `check_complexity.py` PASSes,
  and a fresh venv clean-installs the candidate wheel with `--no-index --no-deps`
  and runs `--help`.
- The rehearsal found two concrete release-pipeline requirements that a
  maintainer version bump must satisfy, which is exactly the kind of thing it
  existed to find: `check_docs.py` pins the documented `__version__` in
  `docs/01-architecture.md` and `docs/02-modules.md`, so bumping
  `pyproject.toml` + `skillsmgr/__init__.py` alone fails BOTH the `docs`
  consistency test and the `verify` job. With those two doc lines updated the
  whole rehearsal goes green. A release bump is therefore a 4-line change
  (`pyproject.toml`, `skillsmgr/__init__.py`, `docs/01-architecture.md`,
  `docs/02-modules.md`) followed by rebuild + re-verification.
- CI is green for every commit in this round, including `f0aea5d` (15/15 jobs).

## 2026-09-10 — CI flake root cause: read-time stamp in no-mutation assertions

- CI run 34490116017 failed only on `unit (py3.14)`:
  `test_malformed_patch_fields_return_json_400_without_mutation` reported
  `updated_at`-looking timestamps `...:36:23Z` vs `...:36:22Z`. Root cause (not a
  product mutation): `Store.get()` decorates the stored row with observations
  computed at read time, and `observations.document_observations()` stamps
  `observed_at` with `datetime.now(timezone.utc)`. The test compared two full
  `Store.get()` snapshots, so it failed whenever the three 400-returning HTTP
  requests straddled a UTC second boundary — a race in the test, exactly like the
  earlier fixed-timeout join, and it happened to surface on the slowest leg.
- Fixed at the root in `tests/test_webapp.py`: a `_persisted()` helper compares
  the stored row (minus only the read-time `observed_at` stamp) plus the document
  bytes. Verified that the assertion still fails on a real mutation
  (`store.edit()` between reads) and passes on a stamp-only change, so the
  no-mutation contract keeps its teeth while the timing assumption is gone.
- Verification: 315 unittest → OK, `check_docs.py` → PASSED,
  `check_complexity.py` → PASSED (157 functions), `git diff --check` → OK.

## 2026-09-10 — ZIP import verified end to end through the real CLI

- Unit tests exercise `Store.import_` directly, so the shipped surface was also
  verified the way a user touches it: a full tar export
  (`skills` + `trash` + `templates`) was converted to a ZIP that includes
  explicit directory entries (`skills/`, `skills/<name>/`, `trash/…`) and
  imported into a fresh data directory with
  `python3 -m skillsmgr import full.zip --full --json`. Result: the live skill
  restored, `restored_trash` and `restored_templates` both populated,
  `trash list` showed the trashed skill, `stats` reported `trashed: 1`, the
  template file was restored, and `doctor` reported `ok: true` — i.e. the index
  and the filesystem agree after a full import.
- Real-world writer compatibility was checked against third-party ZIP tools, not
  only Python's `zipfile`: the system `zip -r` archive (with DOS-style explicit
  directory entries, including the root `skills/` entry that a naive layout
  allowlist rejects) and a `7z a -tzip` archive both imported successfully
  through the CLI (`imported: ['real-zip']`). This is the compatibility case the
  slash-only-directory and layout-allowlist changes were made for.

## 2026-09-10 — Release-gate execution (fresh artifacts) + CI portability fixes

**HISTORICAL/SUPERSEDED environment-blocker record:** The blocker details
below describe the state before publisher/environment registration and remain
append-only history. They do not describe the current release state.

- L6 executed as far as the environment permits. Built once from a clean copy of
  the current tree with the pinned `build==1.2.2.post1`: wheel
  `skills_manager-1.0.0-py3-none-any.whl` (172,365 B, sha256 `8131d7ae8670…`)
  and sdist `skills_manager-1.0.0.tar.gz` (208,280 B, sha256 `38e43041c65a…`).
  `python3 check_package_data.py --dist-dir` → PASS on both (5 web UI files,
  Vue 157,924 B). A fresh venv installed the wheel with `--no-index --no-deps`,
  ran `--help` and `create demo`, and asserted the vendored Vue bundle plus
  `webui/domain.js` are present. The sdist clean-install reports an honest
  `UNAVAILABLE` offline (the pristine venv has no `setuptools` and the check
  installs with `--no-index`). The stale 2026-09-05 artifacts are preserved under
  `dist/stale-2026-09-05/`; `dist/` now holds the verified rebuild.
- **HISTORICAL/SUPERSEDED publication blocker:** Publication was blocked by
  external configuration, not by code: `gh api
  repos/udayvarmora07/skills-manager/environments` → `total_count: 0` (no
  `release`/`testpypi` environment); PyPI and TestPyPI both return 404 for
  `skills-manager` (no project, no registered trusted publisher); the only
  remote tag is `v1.0.0` at `d94cc02`, so publishing this slice requires a
  maintainer-owned version bump and tag. Nothing was tagged or published and no
  PyPI-install claim was added.
- CI portability defects that gated the release were fixed with evidence from
  the failing run (`gh run view 34478740147`): the cross-platform job failed
  because Windows shells do not expand `skillsmgr/*.py` (`[Errno 22] Invalid
  argument`), so it now compiles with `python -m compileall`; the macOS leg
  failed because `contained_path()` resolves the root and the test compared an
  unresolved `/var/...` temp path against a resolved `/private/var/...` one, so
  the expectation resolves too; and the browser job failed with "Chrome DevTools
  endpoint did not start", so `browser_harness.py` now lets the OS pick the
  DevTools port (`--remote-debugging-port=0`), reads the bound port from
  `DevToolsActivePort`, and allows a 30 s cold start instead of assuming 9222.
- `check_package_data.py --dist-dir` printed no install line even with
  `--install` because the exact-artifact branch returned before the install
  step; the flag now installs the artifacts it inspected, with a regression
  asserting both artifacts are passed to `clean_install`.
- Verification after these changes: 315 unittest → OK; `smoke_store.py` →
  PASSED; `smoke_web.py` → PASSED; `browser_harness.py` → `passed: true` on
  Chrome for all five viewports; `check_docs.py` → PASSED;
  `check_complexity.py` → PASSED (157 functions, budget ≤ 15); `py_compile` →
  OK; `git diff --check` → OK.
- First CI re-run after the portability fixes (run 34487469333) went green on
  both macOS legs and every Linux leg, and exposed two remaining defects with
  exact causes: (1) the Windows leg failed
  `test_zip_traversal_absolute_windows_and_symlink_members_rejected_before_extraction`
  (`label='backslash'`) because `zipfile.ZipInfo` rewrites `\` to `/` in
  `filename` on Windows for both writing and reading, so the member can no
  longer smuggle a separator — the test now asserts the contained-import
  invariant on Windows and still requires rejection on POSIX; (2) the browser
  job reached Chrome but the CDP probe died with
  `TypeError: WebSocket is not a constructor`, because the global `WebSocket`
  the client uses only exists in Node ≥ 22 while the job pinned Node 20. The
  browser job now pins Node 22 and the harness fails with a clear message on
  older Node. Verification after both: 315 unittest → OK, browser harness
  `passed: true`.
- Third CI run (34487833099): every Windows, macOS, and Linux leg green; the
  only failure was the known flaky `unit (py3.10)` concurrency contract
  (`test_remove_and_edit_race_leaves_no_residue_or_raw_errors`, one churn
  thread still finishing after the fixed 10 s join). The real contract is that
  the workers finish and leave no residue, so `_join_all` now waits until a
  120 s deadline before reporting stuck threads, removing the timing assumption
  while keeping hang detection.
- CI is green on `main`: run 34488162920 for `a3a055d` → **success**, all 15 jobs
  (unit 3.10–3.14, adversarial, package + release-artifact check, docs, browser
  smoke, and the 3 OS × 2 interpreter cross-platform matrix). This was the last
  repository-side prerequisite for the tag-triggered release.
- Artifacts were rebuilt from the final tree after the CI fixes and re-verified:
  wheel sha256 `6e2dbac79f06…`, sdist sha256 `1d1bb1fe8251…`; the exact-artifact
  package gate PASSes for both, `--dist-dir --install` clean-installs the
  inspected wheel, and the wheel's 38 members are byte-identical to the previous
  build (only ZIP entry timestamps differ, so wheel bytes are not reproducible
  without `SOURCE_DATE_EPOCH` — recorded, not hidden). The remaining publication
  blockers are external: no GitHub `release`/`testpypi` environments, no PyPI
  trusted publisher registered (PyPI/TestPyPI 404), and tag `v1.0.0` already
  pointing at the earlier release commit, so a version bump + tag is a
  maintainer decision.
- Both exact artifacts were then verified end to end, closing the one honest
  `UNAVAILABLE` gap in the gate. The sdist has no offline install backend on this
  box (a fresh venv has no `setuptools` and the gate installs with `--no-index`),
  so a separate venv provisioned `setuptools` once and then installed
  `dist/skills_manager-1.0.0.tar.gz` with `--no-deps --no-build-isolation`:
  `python -m skillsmgr --help` OK, `create sdist-demo` OK, and the installed tree
  contains the vendored Vue bundle (157,924 B), `webui/domain.js` (5,537 B), and
  `webui/index.html` (55,840 B). The hermetic `--no-index` gate still reports
  `UNAVAILABLE` for the sdist, which is the honest result and is unchanged.
- Cross-artifact consistency was checked directly: the wheel and the sdist each
  carry 32 `skillsmgr/` files whose SHA-256 digests are equal to each other and
  to the source tree at `80bc02a`, `METADATA` reports `Version: 1.0.0`, and the
  console entry point is present in the wheel. That is the strongest available
  local evidence that the tested source is exactly what the gate would publish.

## 2026-09-10 — ZIP import hardening round (adversarial audit fixes)

- Four independent audit agents reviewed the uncommitted ZIP slice (security,
  compatibility, docs, and a deep archive/full-import audit). Every confirmed
  finding was fixed red-first; six new regression tests were added
  (`tests/test_archive_contracts.py`).
- P0 fixed — a staged skill commit deleted an existing skill. When
  `copytree(source, staged)` failed before the original was moved aside,
  `moved_original=False` was treated as "no original existed" and the user's
  skill directory was removed. `commit_staged_skill` now records `dest_existed`
  up front and only removes a destination this call created (`archive.py`).
- P1 fixed — the ZIP compression ratio was only checked cumulatively, so a
  stored incompressible member masked a later bomb (probe: 1 MB `ZIP_STORED`
  padding + 8 MB zero-filled `ZIP_DEFLATED` at ~1028:1 previously imported).
  The budget is now a per-member invariant plus the archive-total check.
- P1 fixed — full-import trash/templates were copied non-transactionally with
  raw `shutil` calls after skills were committed: an injected mid-copy failure
  raised raw `OSError`, deleted an existing trash entry before copying, and left
  mixed old/new templates. `_plan_full_restore` now validates every payload
  before any mutation, `archive.restore_full_payload` stages each payload,
  moves the previous entry aside, and rolls the whole set back on failure, and
  the failure surfaces as a clean `StoreError` (REST → 400).
- Fixed — restored trash entries were absent from the index, so
  `stats()["trashed"]` reported 0 while `trash_list()` returned 1;
  `_record_restored_trash` now reconciles those rows and `doctor()` stays `ok`.
- Fixed — manifest `full` must now be a real boolean and `trash`/`templates`
  entries must be plain names; malformed metadata previously fell through to
  `skipped_full`/truthiness instead of failing preflight. Malformed ZIP central
  metadata (`NotImplementedError`/`UnicodeError`) and slash-only ZIP directory
  entries (no Unix/DOS directory bits) are handled cleanly too.
- Independent verification probe (hermetic temp data, no repo writes) confirmed:
  the original skill survives a failed staging copy, the ratio bomb is rejected,
  full-payload failure is a clean `StoreError` with the previous template intact
  and no staging residue, `stats()["trashed"] == 1` with `doctor()["ok"]`, and
  the REST route returns 400 for malformed full metadata and 200 for a valid ZIP.
- Verification: 314 unittest → OK; `smoke_store.py` → PASSED;
  `smoke_web.py` → PASSED; `check_docs.py` → PASSED; `check_complexity.py` →
  PASSED (157 functions, budget ≤ 15); `py_compile` → OK; `git diff --check` →
  OK. The ignored local `dist/` wheel predates `domain.js` and stays a stale
  pre-release artifact until the controlled release gate rebuilds it.

## 2026-09-10 — ZIP import completion and release-gate preparation

- Implemented the approved issue #5 scoped `import` extension. ZIP archives are
  content-sniffed, bounded and preflighted with canonical path/layout/type and
  duplicate checks, compressed/expanded/member/path/nesting/ratio budgets, and
  symlink-bit rejection. Validated members are manually copied to contained
  staging paths; existing manifest/frontmatter/hash/commit recovery is reused.
- Red-first tests now cover valid ZIP round-trip, traversal, absolute,
  backslash, drive-letter, symlink-bit, duplicate, malformed/empty manifest,
  and live REST import. Existing tar tests remain green. Web filename validation
  accepts `.zip`; no new CLI command, schema, or dependency was added.
- Verification at that point: 305 unit tests, both smoke suites, docs
  consistency, complexity, and diff checks passed (superseded by the hardening
  round above). The local ignored `dist/` artifact is stale; the release gate
  must build fresh artifacts before publication.

## 2026-09-10 — Approval-safe verification campaign, round 17 (10 tasks, zero code)

- T1 baseline ladder: `check_docs.py`, 301 `unittest` tests, both smokes,
  compile, `node --check` for both frontend files, complexity, `git diff --check`,
  and CLI help passed.
- T2 catalog: 62 installed skills audited; required skills were loaded; no new
  skill installed because the repository's stdlib-only and hermetic constraints
  make installation unnecessary.
- T3 P0 rotation: traversal victim preserved; hostile-origin purge 403 with trash
  preserved; hostile archive rejected before destination mutation; wildcard
  bounds returned clean `ValueError`; deep frontmatter returned clean
  `FrontmatterError`.
- T4 issue #13 read-only repro remains: a latin-1 byte produces raw
  `UnicodeDecodeError` from `scan_dir`, `Store.list`, `doctor`, and `resync`, while
  `validator.validate_skill` returns a structured error. No product fix was made
  because the issue's behavior choice is not approved and approval prompts are
  unavailable.
- T5 L6: package metadata, `__version__`, and `v1.0.0` remain aligned; the stale
  ignored wheel fails `check_package_data.py --dist-dir` because it predates
  `domain.js`. No publish, version bump, tag, or artifact replacement was done.
- T6 REST: Origin/Referer/Fetch-Metadata/Host hostile mutations → 403, missing
  content type → 415, malformed install and long query → 400, same-origin create
  → 201, and all five security headers verified live.
- T7 archive/parser/search bounds, T8 fresh-data CLI contracts, and T9 browser
  harness plus fresh temporary live seam all passed. T10 documentation is updated
  in `task.md`, `TODO.md`, `PLAN.md`, and this append-only log.
- Scope decision: L2 ZIP, issue #12 diagnostic, and issue #13 remediation stay
  untouched; deferred/rejected roadmap items remain unchanged. The release gate
  **HISTORICAL/SUPERSEDED:** remained blocked only by the stale local artifact and absent authorized publish.

## 2026-09-10 — Final-verdict loop-engineering round (maintainer-authorized; all 14 FINAL, zero code)

- Method: 4 hermetic re-probe agents (stdlib only, `/tmp` probes, isolated temp dirs/HOME/loopback servers, zero product-code changes) + 8-family survey workflow (309 quoted URL entries, 194 unique sources across registry/eval/zip/tar-localhost/link/discovery/signing/release families) + 3 targeted `web_search` batches (skills.sh API, minisign/PEP 740/Agent Skills spec, pywebview/VS Code/GFS/Unicode, TUF/Sigstore/CSRF/Claude precedence).
- F1 archive (Python 3.12.3, `data_filter` present): `Store.import_` rejects ZIP cleanly (`StoreError` "ZIP archives are not supported", `store.py:1221`, no `skills/ok`, no tmp residue); `zipfile` preserves hostile names verbatim (`../../evil.txt`, `/abs.txt`, `skills/ok/../../escape.md`, `skills\evil`, `C:/evil`, dupes count 2, symlink-bit `(external_attr>>16)&0o170000==0o120000` True); tar `validate_members` 9/9 hostile rejections (`unsafe`/`unsupported`/`duplicate ArchiveError`, `archive.py:50`); budgets exact (members 200 ok/201 reject, path 512/513, nesting 16/17, 9MB reject, ratio 40000:1 reject; `archive.py:20-26`); feature-detect `archive.py:131-153`. ZIP parity map: verbatim `normalize_member_name` + `contained_path`, all budgets/layout/dup/exactly-one-manifest, symlink-bit→unsupported, manual contained extraction (no `data_filter` equivalent per PEP 706), manifest preflight before dest writes, `StoreError` hygiene + mkdtemp/finally.
- F2 parser/search/links: dup keys (block+flow), 600KB doc, 400-deep block, 2000-deep flow → all clean `FrontmatterError`, never raw `RecursionError` (P0-SEC-005 holds); valid Agent-Skills + client-extension fixtures round-trip; >10 stars/>200 chars → instant `ValueError` ~0.0ms, worst valid 11.1ms (P0-SEC-004 holds), valid plain+wildcard searches work; link matrix warns (`../../../etc/shadow`, `/etc/passwd`, `../shared/common.md`) and stays clean (`https://`, `#anchor`, `<angled>`) per `validator.py:323-360` (warning-only); walk: live skills 12/0, `~/.agents` 55/0, `~/.claude` 40+34 legit sibling/monorepo refs, `~/.codex` 51+34 same, repo 0 SKILL.md; `_LINK_RE`/`_SCRIPT_RE` artifacts documented (nested parens, titles, `chmod +x` prose) — promotion would convert them into false errors.
- F3 REST/effective/insights: x-origin purge → 403 + trash preserved, bad/missing JSON CT → 415, bad install scalars → 400 JSON, 300-char query → 400, same-origin → 201/200, all 5 security headers live (CSP `frame-ancestors 'none'`, nosniff, DENY, no-referrer, same-origin CORP); `consumer_view` count + `unresolved-precedence-approval-gated`, `effective_state: unresolved` everywhere, diff/3-way (conflict holds base), 5 ownership states, provenance known/unknown, preview risks + rollback flag, quarantine stage-only/`activated:false`, 10 risk findings hostile / 0 clean, registry trust gate False→True, eval advisory-only, bundle deferred; tree hash unchanged (zero mutation); product `urllib` is parse-only (`urlparse`/`parse_qs`/`unquote`), no urlopen/http.client/socket/SDK, no `.ts`, `zipfile.is_zipfile` rejection-only; project scopes require live CWD (absent in `/tmp`, present in project CWD), duplicates stay `duplicated+unresolved` with no winner, `SCHEMA_VERSION = "1"` frozen.
- F4 release/docs/worktrees/encoding/signing/atomicity: `1.0.0` aligned everywhere (pyproject/`__version__`/tag `v1.0.0`, HEAD 43 commits on); release gate present (tag check `:36-52`, build-once `:56`, `--dist-dir` `:58`/`:83`, attest `:110`, testpypi `:118`→release `:138`→GitHub Release); README makes no false PyPI claim (":9 not on PyPI yet"); live PyPI 404; UNAVAILABLE branch code-real; **NEW FINDING: `dist/` stale — wheel missing `skillsmgr/webui/domain.js`, live `--dist-dir` FAILs; rebuild from clean tree before release (config covers `webui/*`)**; docs truth all green (arch repo-map, SUPERSEDED label, settings clean, CLI 27+7+3=37, insights 57); **worktrees: 3 merged-but-stale + 2 genuinely unmerged** (`merge-base` proof; local dirt noted); **#13 confirmed**: single latin-1 byte breaks store-wide scans (`loader.py:31` raw `UnicodeDecodeError` escapes `scan_dir`/doctor/resync; `validator.py:382-385` catches; fix seam = loader per-skill catch, no code); HMAC-SHA256 works / `ed25519` absent / crypto-nacl are OS packages not stdlib; atomic sibling-temp/fsync/replace preserves prior content with no residue; snapshots newest-5 confirmed.
- Survey synthesis (final): #3 DEFER (ToxicSkills 13.4% critical/76 malicious, [Snyk](https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/)); #4 ADVISORY-ONLY ([promptfoo](https://www.promptfoo.dev/docs/configuration/expected-outputs/), [arXiv 2410.21819](https://arxiv.org/abs/2410.21819)); #5 APPROVE (no zip `data_filter` per [PEP 706](https://peps.python.org/pep-0706/), ZipSlip per [Snyk](https://security.snyk.io/research/zip-slip-vulnerability), symlink-bit per [discussion](https://discuss.python.org/t/how-info-zip-represents-symlinks/4104)); #6 REJECT ([CVE-2025-4138](https://www.sentinelone.com/vulnerability-database/cve-2025-4138)); #7 REJECT (68 legit layouts + [mlc](https://github.com/becheran/mlc)/[REF-001](https://contextlint.dev/docs/rules/ref-001/) warn-precedent); #8 SEPARATE ([REST Client](https://github.com/Huachao/vscode-restclient)); #9 REJECT ([pywebview](https://github.com/r0x0r/pywebview) runtimes); #11 DEFER ([NIST SP 800-224](https://csrc.nist.gov/pubs/sp/800/224/ipd), [threshold=0](https://cvereports.com/reports/CVE-2026-23992), [minisign](https://jedisct1.github.io/minisign/), [TUF](https://theupdateframework.github.io/specification/latest/), [Sigstore](https://docs.sigstore.dev/cosign/signing/overview/), [PEP 740](https://peps.python.org/pep-0740/)); M4 `unresolved` ([Datadog](https://securitylabs.datadoghq.com/articles/malicious-skills-supply-chain-risks-in-coding-agents-with-dynamic-context/), [Amp](https://ampcode.com/manual)).
- Docs: `TODO.md` (header + M4 ×2 FINAL + Deferred ×8 FINAL + L6 stale-dist), `PLAN.md` (§9 + §11 final-verdict round), `task.md` Milestone 48, this entry. `git status` shows only intended files (plus ignored `.autogit`).

## 2026-09-10 — Final-verdict ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK (19.5s); both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Suite-health + stability campaign, round 16 (11 probes green, zero code)

- Hermetic probes (stdlib only, inline heredocs, outside the repo; zero product-code changes): T3 concurrency file 5/5 green (round-5 slow-join stands as scheduling, not a contract break); T4 full suite 2/2 back-to-back green; T5 suite health — 0 skips, 301 counted (per-file: insights 57, store 47, web_scopes 27, store_contracts 27, webapp 21, ci_release 20, path_safety 22, archive 14, frontmatter 14, search 11, scope 11, cli 6, complexity 6, docs 5, package 4, concurrency 4, compat 3, smoke_fixtures 2; `-v` shows 300 `... ok` lines + 1 diagnostic-print line, not a skip); T6 gate pins v1.1.0 + v0.3.0 in `CURRENT_DOCS`; T7 workflows + CI contracts 20/20; T8 tracked-junk zero; T9 deferred + PyPI 404; T10 P0 rotation green.
- T12/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-16 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Skills-catalog + encoding-deep-dive + bounds-rotation campaign, round 15 (12 probes green, zero code)

- Goal skill requirements: catalog audited (62 installed incl. both required skills); `first-principles-production-engineering` loaded and applied throughout (smallest-change, verification-before-claims, root-cause-not-symptom); `find-skills` loaded with a recorded no-install decision (stdlib-only + hermetic workflow needs nothing external).
- T2b deep-dive (commented on issue #13, no code): all 26 `read_text(encoding="utf-8")` sites classified — only `archive.py:167` + `validator.py:382` catch decode errors; user-visible behavior is fail-closed (CLI exit 1 clean message via `cli.py:107` `ValueError` path, REST JSON errors) with the sharp edge narrowed to `scan_dir` raising raw + codec-naming messages. Fix options (a)/(b)/(c) recorded on the issue.
- Rotation probes: P0-003/004/005 green; archive budgets (201 members / 20 nesting / 520 path) rejected; parser keys+scalar bounded; search ≤184ms; REST 4×403 + 5 headers; CLI 11 paths rc-1 clean.
- T12/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-15 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Global-flags + lifecycle-defaults campaign, round 14 (11 probes green, zero code)

- Hermetic probes (fresh tmp envs, isolated `HOME` for scope tests, outside the repo; zero product-code changes): T3 init layout + idempotent re-init; T4 webui flags + `gui` alias; T5 `--data-dir` alt-root + color flags; T6 `skills-mgr 1.0.0`; T7 remove default-trash/`--purge`/`--trash` + missing-restore error; T8 sync defaults with isolated `HOME` → `(none)` targets, no live writes (round-12 `sy-1` lesson applied); T9 JSON parity across six commands; T10 uniform name-error message (`-lead` reaches argparse option parsing first — CLI convention, recorded not flagged); T11 smokes PASS twice each.
- T12/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-14 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Remaining-CLI + frontend-seam campaign, round 13 (11 probes green, zero code)

- Hermetic probes (fresh tmp envs, outside the repo; zero product-code changes): T3 add (`--name` requires frontmatter rename first — `store.py:728-732` contract, not a bug); T4 view raw/JSON (17 keys); T5 create extended flags; T6 list/search filters; T8 install (dry-run default prints `running:` banner, `--dry-run` bare command; `../evil` passes the shared char-allowlist — the control is runner-allowlist + dry-run-first + confirm gate per threat-model H-1, probe recorded not flagged); T9 export/backup alias + `open` resync; T10 snapshot rollback byte-accurate; T11 `domain.js` (`parseFrontmatter` enriches compat/tools only — first-pass probe assumed full frontmatter, corrected with evidence).
- Flake note: first harness run `passed:false` (one `net::ERR_ABORTED` at 1280px + server `BrokenPipeError` — viewport probe race, zero console errors). Rerun `passed:true`, exit 0. Recorded per the never-guess rule.
- T12/T15: harness green on rerun + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-13 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — CLI-surface behavior campaign, round 12 (11 probes green, zero code)

- Hermetic CLI probes (fresh `$SKILLS_MANAGER_DATA` per probe, outside the repo; zero product-code changes): T2 history story + limits + JSON; T3 trash cycle + honest double-remove; T4 disable/enable state machine + honest re-toggle errors; T5 partial-edit field preservation; T6 scopes (7 ids; `cursor` documented though `~/.cursor/skills` absent on this box → clean empty); T7 sync skip/force messages; T8 tokens skill/text/scope/window + bad-window choices; T9 validate name/all/external-dir/JSON/missing (`--path` is an external skill dir, not the data dir — first-pass flag was a probe path mistake, corrected with evidence); T10 templates empty/dup messages; T11 db rebuild/resync counts.
- Live-scope note: the R12-T7 probe synced `sy-1` into the real `~/.agents/skills` (default `SKILLS_MANAGER_DATA` leaked into one probe env). Removed immediately (`rm -rf ~/.agents/skills/sy-1`); live global store verified clean. Lesson recorded: scope-touching probes must export an isolated `HOME` as well as `SKILLS_MANAGER_DATA`.
- T12/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-12 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Frontend-contract + steady-state campaign, round 11 (11 probes green, zero code)

- Hermetic probes (stdlib only, inline heredocs, outside the repo; zero product-code changes): T2 all 10 ASK/BUG issues OPEN (#6/#7/#9 carry their 1 rationale comment); T3 T2b repro unchanged (issue #13 stands); T4 CSS (900px stack + 640px topbar rules verified against the SESSION-CONTEXT gotcha; 380/420/780 are component caps, not missing breakpoints — first-pass flag was a probe regex over-match; reduced-motion/overflow-x/focus present); T5 a11y (13 labelled `aria-modal` dialogs, live region, `sr-only`, `kbd`, Esc + trap, `inert`); T6 5/5 viewports no-overflow zero-errors; T7 counts (57 + 37 re-derived); T8 PyPI 404; T9 deferred zero comments; T10 P0 spots green; T11 protocol checklist present and evidenced per-round.
- T12/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-11 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Support-module + finding-filing campaign, round 10 (11 probes green, zero code)

- Filed round-7 T2b as issue #13 (`[BUG] Non-UTF8 SKILL.md escapes scan_dir/doctor/resync as raw UnicodeDecodeError`; repro + smallest-fix sketch + skip-vs-malformed-vs-error scope questions; no code).
- Hermetic probes (stdlib only, inline heredocs, outside the repo; zero product-code changes): T3 `Colors` (piped-off default, NO_COLOR/FORCE_COLOR, empty-text, helper codes); T4 `cli_output` (`render_table` is list-of-lists→str with bold header, `truncate`, `print_json`, `err` to stderr); T5 history/stats edges; T6 web static + raw (`text/plain`, scope-404, traversal-404); T7 `path_safety` (`\`/drive/`..`/absolute rejected on POSIX); T8 validator limits; T9 dump edges (flow-mapping `TypeError` is bracket-list-only — block sequences of mappings are the supported shape); T10 atomic writes + tree hashes; T11 quarantine/registry trust gates. First-pass probe bugs (module-level `color()`, dict-shaped `render_table`, flow-vs-block scope) corrected against source with evidence.
- T12/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-10 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Steady-state verification, round 9 (spot-probes green, zero code)

- Hermetic spot-probes (stdlib only, inline heredocs, outside the repo; zero product-code changes): L2/L6 still gated (#5 + #12 OPEN zero comments; ZIP rejection-only); deferred #3/#4/#8/#11 untouched; P0-001 traversal rejected + victim survives; archive ZIP-rejects with reason and versioned tar round-trips; alternating wildcard → clean `ValueError`; escape warns / `https` clean; REST purge-403 + trash-preserved / form-415 / bad-install-400-JSON / long-query-400; CLI isolation per data-dir + exit 1/2 contracts; versions `1.0.0` aligned with no bump/tag/publish, PyPI still 404, package-data honest UNAVAILABLE; worktrees all unmerged as documented.
- T12/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-9 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Trust-surface + docs-contract campaign, round 8 (13 probes green, zero code)

- Hermetic probes (stdlib only, scripts in `/tmp/r8_*.py`, outside the repo; zero product-code changes): T2 constraints (no ORM import; schema `1`; tiktoken optional-guarded; loopback + vendored Vue + no CDN; command set preserved across the parser split — first-pass flags were probe bugs: `orm` substring in "form", relative `store`/`validator` imports, v1 `cli.py` vs split-file comparison); T3 secrets (98 files clean; `.autogit` untracked, not ignored — pre-existing, untouched); T4 README quickstart verbatim (all 7 commands rc 0); T5 CONTRIBUTING checklist green; T6 roadmap now quotes verdicts; T7 CLI (26/26 help, exit 2/1 contracts, no traceback — first-pass `create bad UX` flag was argparse multi-word usage, real invalid names exit 1 cleanly); T8 REST (8/8 JSON `{error}` + 415); T9 XSS (`esc()` map, 2 sinks via renderer, no `innerHTML`); T10 REST table (no phantom `/api/tokens` or `/api/db` — tokens ride `stats`/`scopes`, maintenance is `/api/rebuild`+`/api/resync`); T11 Store API (zero drift); T12 git (1 modified file, no large blobs).
- Flake note: first harness run `passed:false` (one `net::ERR_ABORTED` at 320px; server logged `BrokenPipeError` on a static write — viewport-resize probe race, zero console errors). Rerun `passed:true`, exit 0. Not a product change; recorded per the never-guess rule.
- T13/T15: harness green on rerun + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-8 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Module-seam + backlog-truth campaign, round 7 (9 probes green, zero code)

- Hermetic probes (stdlib only, scripts in `/tmp/r7_*.py`, outside the repo; zero product-code changes): T2 loader (good/badfm/dupkey/disabled/noload exact) + T2b latin-1 finding below; T3 observations (stable hashes, partition, provenance); T4 roots (dup states, `unresolved`, force/skip semantics); T5 tokens + templates (100-char names valid per `TEMPLATE_NAME_RE` — probe corrected); T6 web serialization + install allowlist; T7 sync (skip-without-force, force-converge, dup-root single-touch); T8 ranking deterministic (100/80/40, 50× stable); T9 diagnostics stderr-only.
- T2b finding (pre-existing, NOT introduced this round; no product change per locked constraints — recorded, not fixed): a non-UTF8 `SKILL.md` raises raw `UnicodeDecodeError` from `loader.load_skill` (`loader.py:31`), which escapes `scan_dir` (catches `SkillNotFound` only, `loader.py:92-96`) and `Store.doctor`/`resync` (one probe each). `Store.list`/`stats` and CLI list/doctor/search/validate survive (index-backed paths catch `OSError`/`SkillNotFound` or read the DB). `validator.validate_skill` already handles it cleanly (`validator.py:382-385` catches `UnicodeDecodeError`); `archive.validate_imported_skill` catches `UnicodeError` (`archive.py:168`). Smallest correct fix (needs maintainer ASK as a behavior change, not done here): catch `UnicodeDecodeError` alongside `SkillNotFound` in `scan_dir` + the `Store.list` enrichment loop (`store.py:516`), or mark the row `malformed` — mirroring the validator contract. Repro: write `b"caf\xe9"` into any `SKILL.md`, run `Store.doctor`.
- Stale-note refresh: TODO M4 `[?]` paragraph now records the v1.1.0 closure + issue #12; PLAN §13 rewritten from stale "begin Phase 0" imperatives to the completed audit trail; `CIE`→`CI` typo fixed. `check_docs.py` PASS after each edit.
- T12/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-7 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — P0 acceptance-gate re-verification, round 6 (5/5 replays green, zero code)

- Direct replays on current `main` (hermetic `/tmp/r6_*.py`, zero product-code changes): P0-001 all five mutations reject `../../victim` with sentinel surviving; P0-002 x-origin purge 403/trash-preserved + same-origin 200; P0-003 `weird name` manifestless import rejected with no destination; P0-004 201-char alternating wildcard → clean instant `ValueError`; P0-005 400-deep block + 2000-deep flow → clean `FrontmatterError` (never raw `RecursionError`).
- Red-first proof (copied tree, product untouched): `NAME_RE=^.*$` → traversal regression RED; archive guard `if False` → traversal regression RED. Guards are centralized: one `validate_skill_name` (`validator.py:71`), one `contained_path` + `safe_skill_path` (`path_safety.py:25,44`), 61 call-sites across store/scopes/archive/CLI/REST; REST URL-decodes before guarding (`webapp.py:198-200`).
- Compatibility: boundary names (1..64 chars), disable/enable `0`, plain + wildcard search, Agent Skills extensions (`x-custom` scalar-coerced, round-trip stable), export→import green. Probe-vs-contract notes: `disabled` is SQLite `0/1` (not bool); flow scalars coerce per parser grammar.
- Protocol self-audit (12/12): 1 outcome+invariant stated per probe header; 2 isolated tmp/hermetic server every probe; 3 red-first proven in T7; 4 shared invariants audited in T8 (not call-sites); 5 neighboring inputs + alternate surfaces in T9; 6 targeted probes then full ladder in T15; 7 failure paths reviewed (tracebacks/raw leaks/stale index/misleading success — none found); 8 all surfaces covered (Store/CLI/REST/scopes/archive/UI-unchanged/package-unchanged/docs); 9 owning docs updated here + `task.md` Milestone 37; 10 diff review in T14; 11 fresh-tmp seam in T12; 12 no `[?]` left open in this round (L2/#12 approvals explicitly out of scope).
- T12/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-6 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — CI/contracts/migration re-verification campaign, round 5 (12 probes green, zero code)

- Hermetic probes (stdlib only, scripts in `/tmp/r5_*.py`, outside the repo; zero product-code changes): T2 CI/release structure (unit 3.10–3.14 matrix, adversarial/package/docs/xplat-3OS×3.10-3.14/browser jobs, least-privilege `contents:read`, build-once + `--dist-dir` gate, release tag/version gate + attestation + TestPyPI→`release` env + GitHub Release + post-publish CRUD/asset checks); T3 package-data offline (exact wheel+sdist accept with 5 webui members, vue-missing reject, `--require-build` exit 2); T4 docs links (all `@docs/` resolve modulo the `...` shorthand, module paths exist, `Store.*` refs exist); T5 frontend (9 domain exports present, 19 menuDo actions dispatched, `/`/`?`/Esc + `trapModalFocus`, 13 modals `role=dialog`); T6 live headers (CSP with `frame-ancestors 'none'`, nosniff, DENY, no-referrer, same-origin CORP, no-store on `/`, `/api/*`, `/app.js`); T7 threat-model/ADR file:line refs all resolve in-range; T8 complexity gate green (151 functions, budget ≤ 15, no drift); T9 full migration (skip-by-default respected — same-tree `--full` import skips live names; wiped-tree `--full --force` restores `m-a` live + `m-b` trash + `tpl-a.md` template); T10 snapshots (7 edits → newest 5 kept `...-Z-5..-Z-1`, byte-accurate `--snapshot` restore); T11 cross-process CLI (2 procs × 10 edits all rc 0, doctor consistent); T12 versions aligned `1.0.0`, `dist/`/egg-info/pycache ignored.
- Flake note: the opening full-suite run failed once in `test_remove_and_edit_race_leaves_no_residue_or_raw_errors` (one churn thread alive after the 10s join — scheduling slowness, not a contract break: no raw errors, doctor clean). The file passes 3/3 standalone and the full suite passes on rerun (301 OK). Not a product change; recorded here per the never-guess rule.
- T13/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-5 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Recovery/contract re-verification campaign, round 4 (10 probes green, zero code)

- Hermetic probes (stdlib only, scripts in `/tmp/r4_*.py`, outside the repo; zero product-code changes): T2 failure injection (dropped-table edit raises while FS content survives + stderr-only `edit rollback failed` diagnostic, `db_rebuild` heals, row-delete drift flagged then `resync` heals); T3 upload bounds (oversize/bad `Content-Length` → 400, 250-part multipart → 400 on the real `PUT /api/import` route, valid folder → 200); T4 history clamp (5/0/huge/missing) + stats keys + tokens estimate/aggregate + long-search `ValueError`; T5 full backup/restore verified by `content_hash` + file bytes (not row counts) + template dup/bad-name guards; T6 doctor (real `.skillsmgr-tmp`/`.skillsmgr-stage` shapes flagged, orphan dir flagged then resynced, stale snapshot flagged); T7 CLI two-data-dir isolation (each dir finds only its own) + REST `test_search_contracts` 11/11 incl. two-server isolation; T9 concurrent same-skill writes 4×25 zero errors, doctor clean, no stranded temps, 101 history rows; T10 insights E2E over a live Store world (view unresolved, ownership, diff/3-way, preview, quarantine `stage-only`/`activated:false`, risk script+link, registry trust-gate, eval 1/1, bundle deferred, store hash unchanged).
- Probe-vs-contract notes (no product change): DB lives at `<data>/skills-manager.db` (not `<data>/skills-manager/`); `dump_frontmatter(data)` takes the mapping only; import tars need the exact versioned manifest; `aggregate()` wants `total_tokens`; `list()` rows carry `content_hash` (path via `get()`); doctor temp/stage detection matches `.skillsmgr-tmp`/`.tmp`/`.skillsmgr-stage` shapes only; upload route is `PUT /api/import`; `quarantine_plan` uses `action:"stage-only"`; `consumer_view` keys on `consumer`.
- T11/T12/T15: harness `"passed": true` file-verified across 5 viewports (an earlier `"passed": false` tail was a shell-pipe JSON-splitting artifact — rerun to file shows `passed:true`, exit 0); fresh-tmp lifecycle all OK; final ladder below.

## 2026-09-09 — Round-4 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Loop-engineering re-verification campaign, round 3 (9 probes green, zero code)

- Hermetic probes (stdlib only, scripts in `/tmp/r3_*.py`, outside the repo; zero product-code changes): T2 store burst (600+ ops incl. honest `SkillNotFound` double-remove, same-second trash cycle, doctor ok); T3 frontmatter 1200 round-trips + 8 hostile inputs (dup/deep/huge/no-close → clean `FrontmatterError`; nested-flow/large-body accepted without crash); T4 search (7 adversarial patterns fast or clean `ValueError`) + validator link matrix 8/8 exact; T5 archive (8 hostile tar classes + garbage + truncated → `StoreError`; ZIP rejection-only; valid manifest tar round-trips `['ok']`); T6 scopes (404 rows, dup flagged, isolation, sync converges); T7 concurrency (8×100 zero errors) + perf (100k-line 0.03s, 20k views 0.10s); T8 REST fuzz (655 requests, 0 fail-opens — purge takes no body by contract, no-CT probe covers `/api/skills`); T9 CLI matrix (81 checks, 0 fail-opens); T10 insights (degenerate/purity/determinism/concurrency clean; `eval_score` missing-`expect` tolerant by design, `eval_plan` strict).
- Probe-vs-contract notes (no product change): `dump_frontmatter(data)` takes the mapping only (body appended by caller); valid import tars need the exact `{"app","version":__version__,"created":"...+Z","skills":[{"name"}]}` manifest; `consumer_view` matches on `consumer` (not `scope`); purge reads no body so the JSON-CT gate applies to body-taking routes.
- Docs hygiene: dropped the #10 Deferred close-record line (retention pass elapsed); L3 now references filed issue #12; `task.md` Milestone 34 (this round).
- T15 final ladder below.

## 2026-09-09 — Round-3 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK. Harness + fresh-tmp recorded in the round-3 entry above.

## 2026-09-09 — Milestone 11 round 2: docs truth, diagnostic proposal, re-verification (15 tasks, zero code)

- T1 baseline green on the round-1 commit: 301 unittest OK, both smokes PASS, compile/frontend PASS, `check_docs.py` PASS, `check_complexity.py` PASS (151 functions), `git diff --check` PASS.
- T2 docs-truth audit: `docs/01-architecture.md` repo-map was missing the split modules (`cli_parser/handlers/output`, `scopes`/`loader`/`tokens`, `diagnostics`, `web_security/serialization/upload`, `insights`, harness, fixtures, package-data gate) — refreshed. `docs/05-gui-plan.md` confirmed correctly labelled SUPERSEDED with `gui.py`-deleted + alias facts (body stays historical by design). `.commandcode/settings.json` confirmed clean (the `gui.py` compile entry was replaced by `skillsmgr/*.py` in `2ae27bf`; remaining `gui.py` hits are append-only history). CLI 27+7+3=37 re-derived from `check_docs._command_inventory` AST walk + live parser (30 top-level names incl. aliases + 7 nested); insights 57 re-counted (`grep -c "def test"`).
- T3/T4 fixes: `docs/SESSION-CONTEXT.md` v0.3.0 (date, counts, full inventory, insights-57, Milestone 11 status, discovery v1.1.0); `docs/01-architecture.md` repo-map + data-flow diagram; `CHANGELOG.md` Unreleased 52→57 with round breakdown; `task.md` T11 52→57. `check_docs.py` PASS after each edit (one interim fail caught a `nested subcommands` phrasing the gate regex does not accept — fixed to the canonical `subcommands (trash/templates/db)` form).
- T5 L2 still gated: issue #5 OPEN zero comments; `store.py:1221` ZIP rejection-only, no `ZipFile` extraction anywhere in `skillsmgr/`.
- T6 diagnostic proposal filed as issue #12 (`[ASK] Read-only effective-resolution diagnostic (doctor --explain CONSUMER --project DIR)`): read-only, per-winner source citations, no persistence/schema change, hermetic per-consumer fixtures sketched, constraint-5 approval explicitly requested.
- T7 deferred re-verified: #3/#4/#8/#11 all OPEN zero comments; no `urlopen`/`http.client`/`socket`/SDK/model-subprocess code in `skillsmgr/` (`urllib` is URL-parsing only in `webapp.py`/`web_security.py`).
- T8/T9 release dry-run: `pyproject.toml` version == `__version__` == `1.0.0` == tag `v1.0.0`; `release.yml` tag/version gate + least-privilege perms verified; no bump/tag/publish performed. `check_package_data.py` honestly UNAVAILABLE; README PyPI-future claim accurate; live PyPI `skills-manager` JSON still 404.
- T10 worktrees: 5 Carson dirs exist; `git worktree list` heads recorded (`todo-plan-implementation 2bb7280`, `milestone5-research-user-needs c5a7161`, three at `667fabb`); `docs/10` scope is the 2-candidate comparison, not a live 5-dir map — no doc change needed.
- T11/T12 re-verification: `browser_harness.py` `"passed": true` (5 viewports); fresh-tmp lifecycle (create→validate→doctor→search→remove→purge→doctor) all OK.
- T13 docs updated for round 2: `TODO.md` (L6 dry-run note, stale-claim status note), `task.md` Milestones 31-L6 + 33 (this round), `PLAN.md` annex (issue #12 filed), this log.
- T14/T15 below: diff review + commit/push, then the final ladder re-run.

## 2026-09-09 — Milestone 11 round-2 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK; `check_package_data.py` → honestly UNAVAILABLE (standing behavior).

## 2026-09-09 — Milestone 11 verdict execution round 1 (L1/L3/L4/L5/L6; docs + GitHub, zero code)

- L1: pinned live-preview + cheatsheet evidence (`skillsmgr/webui/index.html:70,373,756-760`, `skillsmgr/webui/domain.js:60`, `skillsmgr/webui/app.js:6,130`), commented it on issue #10, and CLOSED the issue (`gh issue view 10` = CLOSED). No code.
- L4: recorded all three rejections with file/line evidence and zero code changes — #6 keep `archive.py:133-158` feature-detect + guarded manual extractor (PEP 706; refusal breaks the 3.10/3.11 `requires-python >= 3.10` matrix); #7 keep `validator.py:323-352` warning + `insights.py:342-354` `risk_scan()` (200-target walk: 0 real escapes); #9 browser canonical per locked constraint 4 (`browser_harness.py:28` 320–1280px matrix, zero runtime deps).
- L3: closed all three `[?]`s docs-only in `docs/12-agent-root-discovery-2026-09-08.md` v1.1.0 against primary sources fetched in-session — Codex `.agents/skills/` REPO/USER/ADMIN/SYSTEM roots with explicit no-merge same-name policy (`https://learn.chatgpt.com/docs/build-skills`; facade `~/.codex/skills` flagged compat-only; `AGENTS.md` layering kept distinct via `.../agent-configuration/agents-md`); Command Code six-way selection order (project `.commandcode/` > project `.agents/` > user `~/.commandcode/` > user `~/.agents/` > extras > bundled) with Duplicate-names warnings, `/skill:<name>` hatch, ≤10-level `.agents/` walk stopping at `$HOME`, recursive nested folders, live reload (`https://commandcode.ai/docs/skills`); Claude enterprise > personal > project with both-load nested/plugin, bundled/commands/synced rows (`https://code.claude.com/docs/en/skills`). Proposed read-only `doctor --explain CONSUMER --project DIR` (read-time derivation, per-winner source citation, no persistence, `effective_state: unresolved` elsewhere) — needs its own issue/ADR approval per locked constraint 5. `check_docs.py` PASS after the edit.
- L5: verified the deferred four untouched — issues #3/#4/#8/#11 all OPEN with zero comments; no network (`urllib` only for URL parsing in `webapp.py`/`web_security.py`), backend (eval stays stdlib caller-scored), extension (no TS surface), or signing (`bundle_policy()` = `deferred`) code in `skillsmgr/`; ZIP stays rejection-only (`store.py:1221`).
- L6: verified the release gate without publishing — package `1.0.0` == tag `v1.0.0`; `release.yml` tag/version gate + build-once + `--dist-dir` + attestation + TestPyPI→protected `release` env; README makes no PyPI-install claim; `check_package_data.py` honestly UNAVAILABLE (no `build` module).
- Docs: `TODO.md` L1/L3/L4/L5 marked done with evidence (L2 ZIP stays the only approval-gated code item; #10 Deferred line retained one pass as close record), `task.md` Milestone 31 updated + Milestone 32 (this round) added, `PLAN.md` annex verdicts updated, `docs/12-agent-root-discovery-2026-09-08.md` v1.1.0.
- Verification: T14 ladder re-run recorded in the next entry below (kept separate so commands stay copy-verifiable).

## 2026-09-09 — Milestone 11 round-1 verification ladder (T14)

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → 301 tests OK.
- `python3 smoke_store.py` → ALL STORE SMOKE TESTS PASSED; `python3 smoke_web.py` → ALL WEB SMOKE TESTS PASSED.
- `py_compile` (all tracked `skillsmgr/*.py` + root `*.py`) → OK; `node --check` `app.js` + `domain.js` → OK; `check_docs.py` → PASSED; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.
- `python3 browser_harness.py` (system Chrome CDP) → `"passed": true` across 320/400/640/900/1280px, zero console errors/warnings/network failures/overflow.
- Fresh-tmp live seam (`SKILLS_MANAGER_DATA=$(mktemp -d)`): create → validate (ok + 2 description warnings) → doctor (consistent) → search (hit) → remove → `trash purge` (`purged ['l3verify']`) → doctor (consistent) → OK.
- `check_package_data.py` → honestly UNAVAILABLE (no `build` module; no `dist/` artifact used as evidence) — unchanged standing behavior, not a regression.

## 2026-09-09 — Loop-engineering research verdicts (probes + 200-source survey)

- Ran 9 hermetic probe scripts (isolated temp dirs, stdlib only, no product-code changes; scripts in `/tmp/probe_*.py`, outside the repo): link matrix (`../`, absolute, deep escape warn; `https://`/`#`/`<angled>` clean; 200-target live walk = 145 external/anchor, 55 in-root, 0 out-of-root); zip (`zipfile` keeps hostile names verbatim; symlink-bit detectable); tar (6/6 hostile classes rejected); search (`*a*a*a*a*` instant, 500-char query clean `ValueError`); frontmatter (dup/huge/flow-bomb all clean `FrontmatterError`); eval/risk/registry/quarantine (9 findings on hostile skill, trust gate `False→True`, stage-only); effective boundary (`consumer_view` + `unresolved`, 3-way sides, preview risks, `unknown` provenance); REST (x-origin 403, no-CT 415, bad install 400, long query 400); signing (HMAC ok, `ed25519` absent).
- Surveyed ~200 web sources in ~30 batches plus 5 primary fetches (agentskills spec/eval, skills.sh CLI/API, Socket×skills.sh, Codex skills doc, Command Code skills, Claude priority explainer) across registry, eval, archive, localhost, signing, discovery, atomicity, and accessibility families.
- Verdicts: CLOSE #10 (already shipped); APPROVE ZIP as a scoped `import` extension (red-first corpus; ~90% of tar policy ports; new = symlink-bit check, zip manual extractor, bomb ratio); REJECT tar-refusal #6 (keep feature-detect + guarded extractor), link-to-error #7 (keep warning + `risk_scan()`), desktop wrapper #9 (browser canonical); DEFER registry network #3 (OIDC-gated API; staged offline→passthrough), eval backend #4 (advisory-only, file-based, never blocking), extension in-repo #8 (separate repo), team sharing #11 (trust ADR + threat-model delta first); keep effective resolution `unresolved` (per-consumer precedence is not global; close 3 `[?]`s, then propose read-only `doctor --explain`).
- Docs-only change recorded in `TODO.md` (v2.1.0: Milestone 4 note, Deferred verdicts, Milestone 11 queue L1–L6), `task.md` (Milestone 5 verdicts, Milestone 31), `PLAN.md` (§9 bullets, §11 annex). No code, no locked-constraint changes.
- Verification: `python3 check_docs.py` PASS; full ladder re-run is the new session's first job (L1–L6 start there).

## 2026-09-09 — Insights audit round 5 (degenerate, fs, perf, docs truth)

- Swept degenerate inputs (empty lists/dicts, `None`/`0` bodies, empty consumer), nested/odd structures (list provenance, dict hashes, falsy flags, nested body values, int names, bool skill, int/None eval fields, unicode), and large inputs (500KB body 0.06s, 10k links 0.03s, 20k-line diff 0.01s, 5k eval cases instant, 10k-record views): all JSON-clean, no raw errors.
- Filesystem audit: dangling/file/deleted/locked paths classify `invalid`; non-string paths skip dir validation (`managed`, documented); locked-file probe confirmed `scopes.get_skill()` itself raises `PermissionError` before insights runs (Store/scopes seam, out of scope); `insights.py` performs no direct `open()`.
- Perf: 8-thread × 150 mixed-helper workload 2.49s zero errors; 200k-line scan 0.06s; 20k-record views under 0.1s. REST/CLI regression clean (validate/search/purge).
- Docs truth: stale "31 tests" claims in SESSION-CONTEXT/task/CHANGELOG corrected to 52. Added 5 round-5 lock tests (57 total in the file).
- Verification: 301 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS, package-data honestly UNAVAILABLE (no `build` module), `browser_harness.py` PASS (`"passed": true`), fresh-tmp validate/purge OK.

## 2026-09-09 — Insights boundary round 4 (deep-copy, callable, strings)

- Probed 7 hypothesized boundaries; all 7 confirmed genuine: `consumer_view()` shallow-copied nested dicts (caller mutation leaked into inputs), `eval_score()` let non-callable scorers raise raw `TypeError`, `quarantine_plan()` accepted non-string sources into JSON output, `update_preview()` accepted non-string snapshot items, `registry_preview()` crashed on non-string descriptions and accepted non-string source/scope, `consumer_view()` accepted non-string consumers.
- Fixed red-first (7 new tests, 52 total in the file; 5 failures + 2 errors before green): `copy.deepcopy` record copies, `callable()` scorer guard, `isinstance(str)` source guard, non-empty-string snapshot items, description non-string becomes a blocker, `_require_optional_str()` for source/scope/content_hash, consumer `isinstance(str)` guard. No locked-constraint changes.
- Verification: 296 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS, package-data honestly UNAVAILABLE (no `build` module), `browser_harness.py` PASS (`"passed": true`), fresh-tmp validate/purge OK.

## 2026-09-09 — Deep E2E audit of all 45 insights tasks (E1–E9)

- Built isolated-tmp E2E worlds (global + cursor scopes, duplicates, disabled, risky, real snapshots): E1 lifecycle OK (4 global incl. disabled, 2 cursor, `find_duplicates` flags `e2e-dup`); E2 views OK (3 vs 2, precedence unresolved) with all-five ownership states and 64-char provenance hashes; E3 diff OK (description+body, 6-line bound) and snapshot rollback byte-accurate; E4 risk OK (script/link/pattern on the hostile skill, clean skill empty), quarantine stage-only, registry trust-gated, eval 1/1, bundle deferred.
- E5 purity proved by SHA-256 tree hash before/after running every helper over every record pair: disk and inputs unchanged. E6: 30× JSON sweep instant, ordering deterministic, 8-thread × 150-iteration concurrency clean, 6000-line diff truncates to 200 in <0.05s. E7: REST matrix (skills/stats/doctor/scopes/search) 200 OK, CLI create/list/search/doctor/purge OK.
- E8 genuine defect (red-first): global `Store.list()` rows lack the loader `malformed` flag, so validator-failing global skills classified `managed`. First fix attempt (re-validating `record["body"]`) was wrong — body-only text always errors without frontmatter — and broke 2 tests. Correct fix: `_record_invalid()` checks the loader flag, else `validator.validate_skill(name, path)` against the record's real skill directory; synthetic no-path records stay non-invalid. 5 permanent E2E tests in `TestInsightsDeepE2E` (45 total in the file).
- Verification: 289 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS, package-data honestly UNAVAILABLE (no `build` module), `browser_harness.py` PASS (`"passed": true`), fresh-tmp CLI validate/purge OK.

## 2026-09-09 — Insights robustness round 3 (strict names, JSON, determinism, hostile data)

- Strict-string name policy: `quarantine_plan()`/`eval_plan()` now reject non-string names (`123`, `True`, lists, dicts) with clean `ValueError` via `_canonical_name()`; padded real strings still trim. Found red-first (1 failure), green after.
- Locked behavior contracts (9 new tests, 40 total in `tests/test_insights_contracts.py`): JSON-serializability of all 11 helper outputs; deterministic consumer-view ordering under shuffle with input-order-preserving ownership; non-string fields (`int` body, `dict` description, list tools/extensions) never raise raw errors; null-byte/100KB/emoji bodies scan in milliseconds and stay JSON-clean; scorer exceptions propagate while malformed plans/misaligned outputs raise `ValueError`; three-way missing keys and registry extra keys locked; 4000-line diffs and 100k-line scans complete under 5s within the 200-line bound; 4-thread × 100-iteration concurrency smoke clean.
- Hygiene refactor: `risk_scan()` decomposed into six single-purpose scanners (peak complexity 19 → 9, all `insights.py` functions ≤ 9 by local audit; file is outside the `check_complexity.py` hotspot set so the CI ratchet is unaffected).
- Verification: 284 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS, package-data honestly UNAVAILABLE (no `build` module), `browser_harness.py` PASS (`"passed": true`), fresh-tmp live-seam OK.

## 2026-09-09 — Insights fail-closed hardening follow-up (T1–T15, second round)

- Hardened `skillsmgr/insights.py` after a 16-probe hostile-input sweep found raw `AttributeError`/`TypeError`/`ValueError` leaks: every record-dict entry point now raises clean `ValueError`; `consumer_view()` skips non-dict list items; `update_preview()` coerces tokens safely (`None` for non-numeric, negatives/bools rejected) and rejects non-list snapshots; `diff_skills()` caps `body_diff` at `MAX_BODY_DIFF_LINES` (200) with `body_diff_truncated`; `eval_plan()` requires dict cases carrying input/expect; `registry_preview()`/`eval_score()` reject non-dict/non-list shapes. No locked-constraint changes.
- Added 11 red-first hardening tests (`tests/test_insights_contracts.py` now 31 tests; 2 failures + 9 errors before the fix, all green after). Re-ran the adversarial sweep: every hostile probe now returns clean `ValueError` or a safe value; 5000-line bodies truncate to 200 lines.
- Reconciled `docs/02-modules.md` (fail-closed policy section), `docs/SESSION-CONTEXT.md` (file inventory gains `insights.py` + tests), and stale "20 tests" claims in `task.md`/`CHANGELOG.md`/progress log.
- Verification: 275 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS, package-data honestly UNAVAILABLE (no `build` module), `browser_harness.py` PASS (`"passed": true`), fresh-tmp live-seam exercise OK.

## 2026-09-09 — Milestone 9 read-only insight foundation (T1–T15)

- Added `skillsmgr/insights.py`: twelve pure stdlib-only helpers with zero disk mutation and no locked-constraint changes (no new CLI commands/flags, no new `Store` methods, `SCHEMA_VERSION = "1"` unchanged, no network/dependencies). `consumer_view()` lists one consumer's observed instances with precedence explicitly unresolved per ADR-002; `diff_skills()`/`diff_three_way()` preview field/body changes and hold base on conflict; `ownership_states()` classifies `managed`/`unmanaged`/`adopted`/`quarantined`/`invalid`; `provenance_summary()` splits known loader observations from explicit unknowns; `update_preview()` reports changed files, token/body/snapshot risks, and rollback availability; `quarantine_plan()` returns a stage-only plan validated by `validate_skill_name()`; `risk_scan()` explains script/link/tool/pattern findings with why + evidence; `registry_preview()` is an offline dry-run gated on explicit trust; `eval_plan()`/`eval_score()` are provider-neutral, deterministic, and advisory-only; `bundle_policy()` records signatures as `deferred` pending issue #11.
- Added `tests/test_insights_contracts.py` (31 red-first hermetic tests: all failed on missing-module import before the implementation; all pass after). Exercised the helpers against live public seams in an isolated temp dir (`Store.create` + `scopes.list_all`/`get_skill`): consumer view, diff, ownership, provenance, preview, risk, registry gate, eval, bundle, and quarantine plan all behaved as specified.
- Reconciled `docs/02-modules.md` (new `insights.py` section), `TODO.md` Milestone 9 (foundation checked with approval-gated runtime exposure noted), `task.md` Milestone 25 (T1–T15), and `CHANGELOG.md` Unreleased.
- Verification: full ladder below in T14; `git status` shows exactly the intended files (no live skill roots touched).

## 2026-09-09 — Browser UX, accessibility, module seams, and documentation truth

- Split the CLI behind compatibility-preserving seams: `cli_parser.py` owns argparse construction, `cli_handlers.py` owns command behavior, `cli_output.py` owns rendering, and `cli.py` remains the stable adapter (`main`, `build_parser`, handler/private helper names). The parser inventory and CLI contract tests remain green.
- Split the no-build frontend: `webui/domain.js` owns fetch/formatting/frontmatter/escaped-Markdown policy and `app.js` owns Vue state/workflows. `index.html` loads domain before app; package-data uses recursive source discovery and includes the new file.
- Added accessible modal behavior: labelled dialogs, safer initial focus, Tab trap, Escape close, focus restoration, `inert`/`aria-hidden` background, pressed/current state attributes, live announcements, and a `?` keyboard shortcut help dialog. Added escaped editor Markdown preview and pre-sync source/target/overwrite/rollback resolution preview.
- Added `browser_harness.py`, a dev-only stdlib + system Chrome DevTools Protocol probe. It starts a hermetic server, captures console/runtime/network failures and horizontal overflow, and passed 320, 400, 640, 900, and 1280px viewport probes. CSP was corrected to permit the vendored Vue global runtime compiler while retaining the existing localhost security headers.
- Reconciled `AGENTS.md`, `docs/02-modules.md`, `docs/08-web-ui.md`, `docs/SESSION-CONTEXT.md`, `TODO.md`, `task.md`, `CHANGELOG.md`, and current plan/backlog claims. Effective consumer shadowing and native wrapper remain explicitly deferred/approval-gated.
- Verification: targeted web/CLI/docs/package tests PASS, `smoke_web.py` PASS, `node --check` PASS, browser harness PASS. Final ladder also passes: 244 unittest tests, both smoke suites, Python compile, frontend syntax, `check_docs.py`, `check_complexity.py`, CLI help, browser harness (5/5 viewports), and `git diff --check`; fresh package-data verification is unavailable in the base interpreter because the optional `build` module is not installed. Review follow-up also closes release tag/version validation, Windows xplat interpreter selection, least-privilege workflow permissions, and CI browser/domain coverage with contract tests.


## 2026-09-09 — Controlled release engineering (Milestone 8 CI/packaging half)

- Reworked CI into separate `unit` (Python 3.10–3.14 matrix) / `adversarial` / `package` / `docs` / `xplat` (Linux/macOS/Windows × 3.10/3.14) / `browser` jobs with least-privilege `contents: read`, a documented action-pin policy (third-party release actions pinned to reviewed SHAs; first-party `actions/*` on tags with verified SHAs recorded), and a build-once package gate: CI builds one wheel+sdist, uploads `dist`, and `check_package_data.py --dist-dir dist` inspects those exact artifacts, followed by a clean-venv wheel install smoke.
- Added `check_package_data.py --dist-dir DIR` (inspect exactly one wheel + one sdist already in DIR; exit 1 on count mismatch or package-data failure) for the build-once/test-exact-artifacts contract; `pyproject.toml` classifiers extended to 3.13/3.14 to match the tested matrix.
- Closed a genuine cross-platform containment gap found while writing the xplat matrix: neither `contained_path()` nor archive member validation rejected Windows `\` separators or `C:` drive prefixes on POSIX hosts (POSIX `pathlib` treats them as plain characters/relative paths, while Windows resolves them as separators/absolute paths). Both now reject them on every host; red-first hermetic regressions prove it and the pre-existing path/archive/scope/store/CLI suites stayed green.
- Added tag-gated `.github/workflows/release.yml`: validate the tag against the package version before building or publishing; build once → verify exact artifacts (package-data, unit, docs, clean-install CLI smoke) → attest build provenance → TestPyPI (`testpypi` environment) → PyPI (protected `release` environment, OIDC Trusted Publishing, no long-lived token) → GitHub Release with the exact assets → tag/version/web-asset/hermetic-CRUD verification plus a PyPI-install check. Workflow defaults are least-privilege `contents: read`; only publish/release jobs request additional permissions.
- Qualified PyPI claims honestly per the release policy: PyPI badge removed from `README.md`; README states PyPI is a future release and points at source/CI-artifact installs. PyPI `skills-manager` JSON still 404s as of this change (checked 2026-09-09), so no published-install claim is made.
- Locked with `tests/test_ci_release_contracts.py` (red-first): CI matrix/jobs/permissions/artifact assertions, xplat containment + build-once mode assertions, release workflow assertions (tag gate, environments, Trusted Publishing, attestation, TestPyPI/PyPI, GitHub Release, post-publish checks), and PyPI-claim assertions. `TODO.md` Milestone 8 marked accordingly, `task.md` Milestone 23 added, `CHANGELOG.md` Unreleased and `CONTRIBUTING.md` checks updated.
- Verification: full unittest suite PASS; `smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); Python compile PASS; `node --check skillsmgr/webui/app.js` PASS; `check_docs.py` PASS; `check_complexity.py` PASS; both workflow YAML files parse; `git diff --check` PASS. Browser/a11y work is tracked in the newer 2026-09-09 entry above; this entry records the release-engineering checkpoint as it stood before that follow-up, not a current open-status claim. The xplat workflow uses the portable `python` executable so Windows matrix legs invoke the configured interpreter.

## 2026-09-09 — Advanced loop-engineering campaign closeout

- Ran nine deterministic hermetic probe loops (stdlib-only, seeded; probe code kept outside the repo): store-lifecycle burst, frontmatter round-trip/hostile fuzz, failure injection, REST fuzz, concurrency stress, search/validator/loader-templates/CLI-env fuzz, CLI adversarial matrix, archive boundary+grammar fuzz, scope differential loop.
- Fixed 15 genuine defects surgically with red-first hermetic regressions and no locked-constraint changes (no new commands/flags, no new Store public methods, `SCHEMA_VERSION = "1"` unchanged): trashed-row reactivation on create/add (incl. resync of any returned live directory), same-second trash counter recognition, honest double-remove error, import backup-move recovery preserving the original, truncated-gzip clean StoreError, CLI first-run schema bootstrap, install validation parity, flow-scalar and quote-char key quoting, nested-block mapping emission with inline empty collections, post-sync global index reconciliation, shared per-skill lock coverage with stranded-temp cleanup, purge StoreError wrapping, loud duplicate frontmatter-key errors (FIX-14, promoted from OBS-1), and deduped `purged` names (FIX-15, promoted from OBS-3).
- Full findings with repro/root-cause/fix evidence live in `loop-engineering-findings.md`; owning docs updated (`docs/02-modules.md` store/frontmatter behavior incl. duplicate-key rejection, `docs/04-store-api.md` `purged` dedup, `docs/03-cli-surface.md` list semantics) and `task.md` Milestone 22 closed.
- Verification: full unittest suite (224 tests) PASS; `smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); Python compile PASS; `node --check skillsmgr/webui/app.js` PASS; `check_docs.py` PASS; `check_complexity.py` PASS (194 functions); `git diff --check` PASS; package-data gate remains honestly `UNAVAILABLE` (no `build` module in this environment; CI installs it).

## 2026-09-08 — REST two-server search isolation regression closeout (18:42 UTC)

- Fixed both REST search routes (`/api/search` and `/api/skills?q=...`) to pass the request handler's `self.store` into global and merged `scopes.search_all()` calls. Agent-scope searches still use filesystem adapters; body-aware ranking, response schemas, and singleton compatibility for non-WebAppServer callers are unchanged.
- Added a hermetic two-server regression in `tests/test_search_contracts.py`: separate Stores are served concurrently, and each server's `scope=global` response contains only its own global skill while `scope=all` contains its own global skill plus the shared agent skill. Both server lifecycles are cleaned up.
- No commands, Store methods, schema, dependencies, or `.autogit` contents were changed.
- Verification: focused search contracts (11 tests) PASS; full unittest suite (208 tests) PASS; `smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); Python compile PASS; `node --check skillsmgr/webui/app.js` PASS; `check_docs.py` PASS; `check_complexity.py` PASS (168 functions); `git diff --check` PASS.

## 2026-09-08 — CLI data-dir search regression closeout (18:27 UTC)

- Fixed `cmd_search()` to pass the Store created for `--data-dir` into the scope search adapter. Global search and the global portion of merged search now read only the requested data directory; agent-scope records still come from scope filesystem adapters.
- Added a hermetic two-data-dir regression in `tests/test_search_contracts.py` proving global isolation and merged results contain the requested global result plus the agent result, never the other Store's result.
- Preserved body-aware global/merged ranking, historical output shapes, error contracts, and all locked constraints; no commands, Store methods, schema, dependencies, or `.autogit` contents changed.
- Verification: focused search/CLI tests PASS (15 tests); full unittest PASS (207 tests); `smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); Python compile PASS; `node --check skillsmgr/webui/app.js` PASS; `check_docs.py` PASS; `check_complexity.py` PASS (168 functions); `git diff --check` PASS.

## 2026-09-08 — Uncommitted-change review and verification

- Reviewed all tracked and untracked changes except `.autogit`; inspected `AGENTS.md`, owning docs, tests, smoke scripts, CI, and production diffs. The review identified a high-impact CLI `--data-dir` search regression; the subsequent closeout above fixed it and added isolation coverage.
- Applied only permitted surgical changes to tests, docs, smoke scripts, and CI: strengthened smoke history assertions, synchronized fixture server readiness, made concurrency readers prove execution, made secondary smoke cleanup exception-safe, removed brittle package-asset count assumptions, corrected current test/gate guidance and duplicate CLI documentation, and made CI install packaging build tooling before the package-data gate.
- Local package-data verification remains `UNAVAILABLE` because this environment has no `build` module; no stale `dist/` artifacts were used. CI now installs `build==1.2.2.post1` and requires the fresh-build gate.

## 2026-09-08 — Search contract defect closeout (17:51 UTC)

- Fixed scope and merged searches dropping global body-only matches: `scopes.search_all()` now obtains global list rows through `Store.list()` and body content through `Store.get()` before applying the existing bounded scorer. CLI and REST global search paths use this same body-aware public seam, preserving ranking and response shapes.
- Fixed wildcard complexity errors escaping from `scopes.search_all()`: bounded matcher `ValueError`s are translated to `StoreError`, so CLI returns its normal clean exit-1 error and REST returns the standard JSON HTTP 400 error.
- No commands, Store methods, schema, dependencies, or `.autogit` contents were changed. Existing focused regressions in `tests/test_search_contracts.py` remain authoritative; no fixture assumptions required correction.
- Verification: `python3 -m unittest tests.test_search_contracts` — 9 tests PASS; the later CLI and REST isolation closeouts raised the final full suite to 208 passing tests. Final smoke, compile, frontend syntax, docs, complexity, and diff checks are recorded in the newest entries.

## 2026-09-08 — Documentation consistency gate

- Extended `check_docs.py` with offline checks for all local `@docs/*.md` links, explicit documented source paths, qualified `Store.method`/module symbols, current CLI command inventory, current web UI claims, and source/package/documented version alignment.
- Current command counts are derived from `skillsmgr/cli.py` (27 top-level + 7 nested + 3 aliases = 37 invocable names); superseded GTK planning and append-only historical entries remain exempt from current-claim checks.
- Added five focused stdlib tests covering the clean repository gate, broken pointers, missing Store symbols, version mismatch, and parser-derived command inventory.
- Verification: `python3 check_docs.py` PASS; focused docs tests PASS (5 tests). Full suite and smoke verification remain delegated to the parent session.

## 2026-09-08 — Distribution package-data verification

- Added stdlib-only `check_package_data.py`, which builds exactly one wheel and one sdist in a fresh temporary directory via `python -m build`, then checks deterministic `skillsmgr/webui/` contents including vendored Vue.
- Added offline `tests/test_package_data.py` archive fixtures and exact member-set assertions; no network or third-party test dependency is required.
- Optional `--install` probes install each fresh artifact into an isolated temporary venv with `pip --no-index --no-deps`; runtime dependencies and product APIs are unchanged.
- Exact limitation: this environment lacks the optional `build` module (`/usr/bin/python3: No module named build`), so the live check reports `UNAVAILABLE` and does not inspect stale `dist/` artifacts. `--require-build` is available for release CI to make unavailable tooling non-zero.

## 2026-09-08 — Hermetic smoke fixture refactor

- Added `smoke_fixtures.py` with only shared temporary Store setup/cleanup and loopback WebAppServer start/stop lifecycle helpers; refactored both executable smokes to use those helpers without changing their assertions or printed checkpoints.
- Added two stdlib `unittest` regressions covering initialized-store cleanup and ephemeral loopback-server lifecycle.
- Verification: `python3 smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `python3 smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); focused fixture tests PASS (2 tests); `python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py` PASS; `python3 check_complexity.py` PASS (166 functions); `git diff --check` PASS. An intermediate full unittest run covered 202 tests but reported 3 failures plus 1 error in search-contract tests; it was superseded by the later search closeout at the top of this log. An intermediate `check_docs.py` run also reported stale command-inventory mismatches; those docs were corrected before the later passing gate.

## 2026-09-08 — Helper compatibility audit

- Audited the extracted web policy/serialization/upload modules and CLI output helpers against their pre-extraction interfaces and recent history.
- Found no concrete compatibility regression: `webapp._json_bytes`, `webapp._parse_multipart`, `webapp.RequestError`, and CLI output aliases preserve their historical call shapes and behavior.
- Added `tests/test_compatibility.py` to lock those private compatibility seams, including the historically ignored `_json_bytes` status argument and one-argument CLI helper calls.
- Verification: focused compatibility/web/CLI tests passed (29 tests); compile, docs consistency, and complexity checks passed.

## 2026-09-08 — Web policy extraction, contract regressions, and complexity ratchet

- Extracted request security, JSON serialization/body parsing, and bounded multipart upload staging into private stdlib-only modules while retaining `webapp.py` compatibility wrappers.
- Fixed text `scopes` output attempting to access unrelated skill snapshot arguments and fixed raw REST archive import to forward `full=1`.
- Added focused CLI and REST regression tests plus an AST complexity ratchet with a checked-in baseline, contributor instructions, and CI wiring.
- Added stderr-only diagnostics for rollback cleanup failures so recovery problems are visible without changing public schemas.
- Deep verification found malformed JSON field types that leaked as HTTP 500 and a CLI color documentation mismatch; added 4xx validation, integrated CLI output helpers, and corrected the CLI docs.
- Verification: full repository suite passed (128 tests), store/web smoke, docs gate, frontend syntax, compile, CLI color/output probes, and complexity check.

## 2026-09-08 — Atomic recovery, hash verification, and documentation truth

- Completed ten executable backlog tasks: atomic sibling-temp writes with flush/fsync/replace, rollback preservation across filesystem/index failures, same-process per-skill mutation serialization, failure-injection coverage, richer doctor diagnostics, and content-hash backup verification.
- Scope and template writers now use the same atomic document policy; snapshots are also written atomically. Cross-process behavior is explicitly documented as atomic-file replacement plus `doctor`/`db resync` recovery, without adding lock files or public API surface.
- Export manifests now carry optional SHA-256 skill-tree hashes; imports verify hashes during staged and committed copies while preserving the existing per-skill `imported`/`skipped` contract.
- Reconciled current architecture/scope/API/CLI documentation, removed the deleted GUI path from Command Code settings, and added `check_docs.py` as a machine-checkable docs/source gate wired into CI.
- Verification evidence for this slice is recorded after the final full-suite, smoke, frontend, help, docs-gate, and diff checks.

## 2026-09-08 — Root/consumer discovery baseline

- Completed the next five executable Milestone 4 tasks without introducing a new
  public data model, CLI command, Store method, or SQLite field.
- Added ADR-002 for `SkillRoot`, `Consumer`, `ConsumerRootBinding`,
  `SkillInstance`, and `EffectiveSkill`; runtime expansion remains approval-gated.
- Added the official discovery inventory for Claude Code, Cursor, Gemini CLI, and
  OpenCode. Codex and Command Code precedence/reload behavior remain `[?]` until
  primary documentation is available.
- Corrected Cursor's user root to `~/.cursor/skills`. Aggregate scope listings and
  sync target planning now deduplicate resolved physical roots while direct scope
  ids remain compatible.
- Primary-source verification narrowed the Claude Code inventory: discovery and
  live change detection are confirmed, while exact same-name precedence remains
  `[?]` instead of being guessed.

## 2026-09-08 — Root capability and observed instance states

- Completed the next five scope/effective-state tasks as far as the locked
  compatibility boundary permits.
- Recursive scanning is now opt-in per consumer root: Cursor, OpenCode, shared
  agent, and matching project roots recurse; flat roots remain one-level scans.
- Scope descriptors now expose `writable`, `read-only`, `missing`, and
  `unsupported` availability, plus consumer and recursive-discovery metadata.
- Scope records expose observed `active`, `disabled`, `invalid`, `duplicated`,
  `divergent`, and `unmanaged` states. Effective resolution is explicitly
  reported as `unresolved`; `shadowed` classification remains approval-gated
  until ConsumerRootBinding precedence is a runtime model.
- Sync continues to target each resolved physical root once. Added recursive,
  capability, disabled/malformed, divergent, and unresolved-state regressions.

## 2026-09-08 — Observation and hotspot extraction slice

- Preserved unknown/client-specific frontmatter through edits and exposed a
  non-persisted portable/extension partition in loaded records.
- Added non-persisted content hash, metadata hash, observed timestamp, and
  provenance observations without changing SQLite or public Store signatures.
- Extracted atomic I/O, archive policy, and root-discovery helpers into internal
  modules, plus the root-containment primitives into `path_safety.py`, while
  keeping Store/scopes/paths compatibility adapters and existing error contracts.

## 2026-09-08 — Recovery snapshots, migration, and localhost policy slice

- Completed the next five executable backlog tasks after archive hardening.
- ADR-001 records the decision **not** to add a per-process mutation token:
  loopback-only binding, pre-handler browser request checks, no cookies/sessions,
  and supported local non-browser clients provide the simpler correct boundary.
- Added guarded snapshots under `<data>/snapshots/<scope>/<name>/` with canonical
  scope/name/path validation, newest-five retention, automatic pre-edit and
  force-sync-overwrite capture, and global/agent restore. CLI, REST, and web UI
  expose retained snapshot IDs and rollback.
- Added `--full` to existing export/backup/import surfaces. Full archives include
  skills, validated trash, and templates; snapshots and agent scopes remain
  excluded. Full migration uses the current hardened tar/resource/manifest
  pipeline and rejects slim archives when `--full` is requested.
- Added focused tests for snapshot retention/rollback, agent-scope snapshots,
  full migration round trips, slim/full compatibility, REST snapshot routes, and
  staged sync failure preservation.
- Selective replay status: approved candidate worktree code was not merged
  wholesale. Current source retains the hardened archive pipeline and adds only
  the reviewed snapshot/full-migration seams needed by this slice.

## 2026-09-08 — Next-five archive contract and resource-safety slice

- Completed the next five executable archive tasks: resource budgets, strict
  manifest validation, canonical manifestless fallback handling, explicit ZIP
  policy, and per-skill staged/rollback import behavior.
- Tar preflight now enforces compressed-size (25 MiB), expanded-size (16 MiB),
  individual-member (8 MiB), member-count (200), path-length (512), nesting
  depth (16), and compression-ratio (1000:1) limits before extraction.
- Manifests must identify `skills-mgr`, use a supported semantic major version,
  contain a UTC creation timestamp, and list unique canonical skill names whose
  extracted directories and frontmatter agree. Invalid names fail closed.
- ZIP remains intentionally unsupported; content sniffing rejects ZIP bytes even
  when the filename has a tar extension. Each skill is staged independently,
  failed replacements restore the previous destination, and results report
  imported/skipped names.
- Added hermetic tests for all archive limits, strict schema/path/frontmatter
  validation, ZIP rejection, malformed fallback names, forced-destination
  preservation, and injected per-skill copy failure.

## 2026-09-08 — P0 parser, search, and localhost request-safety slice

- Completed ten executable risk-first tasks from the latest `TODO.md` across
  parser bounds, wildcard search, and localhost web request security.
- Frontmatter parsing now enforces document, key, collection, scalar, and nesting
  budgets; deep recursion and malformed bounded structures surface as clean
  `FrontmatterError` values. Valid round trips remain covered.
- Wildcard search collapses repeated stars, caps query length and effective star
  count, preserves body matching, and uses one bounded scorer across Store,
  global/agent/merged scopes, CLI, and REST paths. Adversarial patterns return a
  clean 400 through REST instead of exhausting regex backtracking.
- All state-changing HTTP methods now validate loopback Host/port, reject
  cross-site Fetch Metadata and mismatched Origin/Referer values before route
  handlers, require JSON for JSON mutations, reject non-loopback binds, and add
  CSP/framing/MIME/referrer/cross-origin response headers. Header-absent local
  clients remain supported.
- Added hermetic regressions for hostile browser headers and every mutating
  method, wildcard exhaustion/body matching, parser resource limits, and clean
  error contracts.
- Verified on September 8, 2026: compile PASS, **76 unittest PASS**,
  `smoke_store.py` PASS, `smoke_web.py` PASS, frontend syntax PASS, CLI help
  PASS, focused REST probes PASS, and `git diff --check` PASS.

## 2026-09-08 — Next-five archive and trash safety slice

- Completed the next five executable tasks after the first-ten path-safety
  slice: forced-destination protection, exact trash matching, archive
  preflight, unsafe archive-member rejection, and safe `tarfile.data_filter`
  feature detection.
- `Store.import_()` now validates tar member paths, duplicate names, supported
  regular-file/directory types, manifest structure, canonical skill names,
  and extracted skill documents in a private temporary directory before any
  forced destination deletion or copy. Interpreters without `data_filter` use
  an explicit guarded extractor rather than unfiltered `extractall()`.
- Trash list/restore/purge/doctor now share exact canonical timestamped-entry
  recognition and ignore malformed or symlinked entries consistently.
- Added hermetic regressions for forced invalid names, unsafe members,
  duplicates, symlinks, hard links, FIFOs, no-filter extraction, valid archive
  compatibility, malformed trash entries, and doctor consistency.
- Verified: compile PASS, **65 unittest PASS**, `smoke_store.py` PASS,
  `smoke_web.py` PASS, `node --check` PASS, CLI help PASS, and `git diff
  --check` PASS.

## 2026-09-08 — Close encoded REST raw-read seam

- Added a regression test for an encoded traversal request targeting the global
  `/api/skills/<name>/raw` endpoint. The test first demonstrated the missing
  guard by receiving the wrong 404 behavior for an outside path.
- Fixed the raw-read route to resolve the decoded name through `Store.get()`
  before constructing the file path, preventing disclosure of an outside
  `SKILL.md` while preserving the existing clean HTTP error contract.
- Verified the focused REST safety tests and the full suite: **57 unittest
  tests PASS**. The broader smoke/compile/help/diff checks remain green.

## 2026-09-08 — Selective replay controls and canonical path safety

- Completed the first ten executable tasks selected from the latest `TODO.md`:
  selective replay map, status classification, pre-merge checklist, packaging
  artifact decision, canonical skill-name validation, resolved-root containment,
  Store/scope enforcement, decoded REST validation, and pre-handler CLI
  validation.
- Added `docs/11-integration-status-2026-09-08.md` and
  `docs/PRE-MERGE-CHECKLIST.md`. Candidate worktrees remain classified as
  `worktree-only` or `approved-not-integrated`; no wholesale branch merge was
  performed. `dist/` and `skills_manager.egg-info/` remain ignored local build
  artifacts, not release inputs.
- Added `validate_skill_name()` and `contained_path()`/`safe_skill_path()`.
  Store and agent-scope reads, writes, renames, moves, copies, restores,
  imports, exports, sync destinations, and deletes now validate names and keep
  resolved paths inside their managed roots. Existing symlink escapes and
  absolute path parts are rejected.
- REST path segments are decoded after splitting, so encoded separators reach
  the canonical guard. CLI skill names are rejected before Store construction;
  invalid input does not create a database or touch the filesystem.
- Added hermetic regressions for path/symlink/absolute escapes, Store and scope
  mutation paths, encoded REST deletion, pre-handler CLI rejection, and invalid
  manifestless archive fallback names.
- Verified: compile PASS, **56 unittest PASS**, `smoke_store.py` PASS,
  `smoke_web.py` PASS, `node --check` PASS, CLI help PASS, and `git diff
  --check` PASS.
- Remaining by design: P0-SEC-002 localhost request-origin security,
  P0-SEC-004 wildcard exhaustion, P0-SEC-005 parser resource bounds, the full
  archive preflight/limit policy, recovery/atomicity, UX/accessibility, and
  release packaging. These remain open in `TODO.md`.

## 2026-09-07 — Milestone 0 baseline and P0 reproduction evidence

- **Completed the first two world-class roadmap tasks** from `TODO.md`.
- Captured a reproducible baseline in `docs/09-baseline-evidence-2026-09-07.md` at commit `667fabb7ddb41fcd0db6fb9a58128665bba0190c`: compile PASS, **47 unittest PASS**, `smoke_store.py` PASS, `smoke_web.py` PASS, `node --check` PASS, and CLI help PASS.
- The package-build check was run honestly and returned exit 1 because `/usr/bin/python3: No module named build`; this remains a Milestone 8 release-engineering gap and was not hidden by using existing `dist/` artifacts.
- Reproduced all five current-`main` P0 behaviors in isolated temporary environments before product-code changes: mutation path traversal deletion, cross-origin localhost trash purge, invalid manifestless archive name import, wildcard matcher timeout, and raw frontmatter `RecursionError`.
- Updated `TODO.md`, `task.md`, and `docs/README.md` to point to the evidence report. No source code or `.autogit` was modified.

## 2026-09-08 — Milestone 0 worktree integration comparison

- **Completed the third world-class roadmap task** from `TODO.md`.
- Compared `agents/todo-plan-implementation` (`2bb7280`, 22 changed files, 74 tests) and `agents/milestone5-research-user-needs` (`c5a7161`, 17 changed files, 55 tests) file-by-file against current `main` (`667fabb`). Both candidate worktrees pass their own unit and smoke suites and both diffs pass `git diff --check`.
- Found **13 overlapping files**, with `skillsmgr/store.py` the highest-risk conflict because both branches independently change archive intake. The comparison report requires manual archive-pipeline design rather than a textual merge.
- Classified the security/adversarial branch as the primary P0/recovery source and the Milestone 5 branch as a secondary ZIP/UX source. Defined replay order: tests → P0 security → localhost security → recovery → archive policy → UX → docs.
- Wrote `docs/10-worktree-integration-comparison-2026-09-08.md`. No candidate worktree, product source, test file, or `.autogit` was modified.

## 2026-09-05 — Dedup + token-budget closeout (Milestone 7, v1.1 items 3–4 done)

- **Cross-scope dedup (code, no constraint-5 impact)**: `scopes.find_duplicates()` — read-only grouping over `list_all()`, same-name groups with `scopes`/`count`/`descriptions_differ`/`records`, converge via existing `sync_skill()`. Surfaced in `doctor --scope all` (text lines + `duplicates` JSON key), `/api/doctor?scope=all` (`duplicates` + `scopes` keys), doctor modal section with per-name Sync… buttons (jump into existing sync modal via `syncDupe()`). No new commands/flags/Store methods.
- **Smoke gotcha**: `smoke_web.py` is NOT HOME-hermetic — real `~/.agents/skills` leaks into `/api/doctor?scope=all`, so the new smoke section asserts shape (`isinstance list`), not emptiness. Unit tests stay hermetic (HOME+DATA redirected).
- **Frontend**: `openDoctor()` appends `?scope=all` when `activeScope === "all"`; new `.btn-sm`/`.pill-warn`/`.dupe-list` styles.
- **Token budget (verified complete, no new code)**: `tokens --scope all` aggregate + `largest`, `/api/stats?window=` (`all_tokens/all_avg/all_pct`, top-5 `largest`), `/api/tokens`, frontend budget bar + window selector + per-row tokens + sync cost hint.
- **Verified**: compile OK, **47 unittest OK** (4 new dedup tests), both smokes PASS, `node --check` OK, `--help` OK, live `doctor --scope all` shows dupes in text + JSON.
- **Docs**: task.md M7 dedup+budget [x], TODO.md v1.1 items 3–4 [x], ROADMAP v1.1 dedup+budget [x], CHANGELOG Unreleased entries, 03-cli-surface doctor line, 08-web-ui doctor row, 02-modules scopes line.
- **Remaining**: PyPI upload needs token; rollback/migration ASK issues opened (#1 snapshots, #2 full-migration) — no code until approved.
- **Pushed**: commit `0eeb0ac` (v1.1 dedup + budget), CI green (run 33946982582, 21s); issues #1 + #2 opened via `gh`.

## 2026-09-05 — Publish + v1.1 spec-lint+ (Milestone 7 in progress)

- **Published**: `gh repo create skills-manager --public` → `udayvarmora07/skills-manager`; `main` + `v1.0.0` pushed; CI green (run 33914953774, 20s). Placeholders replaced (YOUR-USER→udayvarmora07; security@example.com→private advisories link). PyPI name `skills-manager` free; `dist/` built (sdist+wheel 1.0.0); upload blocked pending PyPI API token.
- **Spec-lint+ (v1.1, no constraint-5 impact)**: `NAME_RE` already rejects `--` (verified empirically); new `description_score()` (use-context regex + filler-word set); description warnings (missing use-context, vague filler); body token warning (`MAX_BODY_TOKENS=5000` via `tokens.count_tokens`, progressive-disclosure guidance); `scripts/`/`references/`/`assets/` layout check (dangling mentions). Sourced from agentskills.io best-practices + optimizing-descriptions guides.
- **Tests**: 5 new unittest cases → **43 OK**; `smoke_store.py` gains a spec-lint section (vague + oversize + score asserts). Both smokes PASS, `node --check` OK.
- **Docs**: task.md Milestone 7, TODO.md v1.1 items 1–2 [x], ROADMAP spec-lint [x], CHANGELOG Unreleased entry, 02-modules validator line.
- **Remaining**: PyPI upload needs token; cross-scope dedup + token budget view next (code, no ASK); rollback/migration need issue-first ASK.

## 2026-09-05 — OSS launch kit completion (Milestone 6)

- **Packaging/docs verified present**: pyproject.toml, .gitignore, LICENSE (MIT), README.md, CONTRIBUTING.md, SECURITY.md, CHANGELOG.md, ROADMAP.md, both security reports, tests/test_store.py + test_webapp.py, CI + issue/PR templates. Recreated missing `tests/test_web_scopes.py` (13 hermetic scope tests). Deleted `__pycache__/` dirs.
- **Test fixes (2 test bugs, 1 real bug)**: `_skill_body` helper called `dump_frontmatter(dict, body)` but signature is `dump_frontmatter(data, /, *, key_order)` — fixed to append body separately (3 errors). **Real bug**: `Store.restore()` matched `p.name.startswith(name + "-")` + regex on remainder, so restoring `demo` could grab `demo-x-<ts>` (test proved: got "Demo x skill"). Fixed to `_strip_trash_suffix(p.name) == name`.
- **Webapp test hang fixed**: `setUpClass` created `WebAppServer` but never started `serve_forever`; `tearDownClass` referenced nonexistent `server._thread`. Fixed: daemon thread + `server.shutdown()` + join + `server_close()`. Suite: 22 + 3 + 13 = **38 tests OK**.
- **Offline-env decision enforced**: no network for pip (PEP 668 + no dist). CI + CONTRIBUTING + PR template + pyproject switched pytest→stdlib `python3 -m unittest discover -s tests`; dropped `[dependency-groups] dev = pytest`. Also fixed stale README cursor path (`~/.cursor/skills-cursor`) and venv-based setup (no deps to install).
- **Verified**: `py_compile` OK, 38 unittest OK, `smoke_store` PASS, `smoke_web` PASS, `node --check` JS_OK, `--help` OK, `list --scope agents --json` → `[]` (no ~/.agents on this box).
- **Remaining before publish**: replace `YOUR-USER` (README ×3, pyproject ×5, CONTRIBUTING ×1) + `security@example.com` (SECURITY.md). Launch: `git init && git add -A && git commit`, create GitHub repo, push, `git tag v1.0.0`, PyPI via build+twine.
- **task.md**: added Milestone 6 (all [x] except pre-publish placeholders).

## 2026-09-04 — Hardening audit + E2E + security closeout (Milestones 4–5)

- **Security/bug audits** (subagents): P0 confirmed — `validate --all` KeyError, PATCH `name` TypeError 500, import filename traversal, unbounded body DoS. Fixed: fs-scan for `--all`, `name` popped before field filter, basename + tar-type + empty guards, 25 MB cap + Content-Length validation, generic 500 + stderr log, tar `filter="data"`, restore timestamp-regex, purge skips non-timestamp dirs.
- **P1/P2 fixes**: scopes injectable global store (`set_global_store`, wired in `WebAppServer.__init__`); `sync_skill` NAME_RE/MAX_NAME validation; loader `malformed` flag; frontend `listSeq`/`detailSeq` race guards + scope-aware undo/restore; docs `--scope`/`--raw`/zip corrections (03-cli-surface) and rule-1 correction (08-web-ui).
- **smoke_store.py hermetic**: tmp-dir `fixture-skill` replaces external opencode path dependency.
- **E2E matrices green**: full CLI matrix (all commands + trash/templates/db, `--json`, error paths, exits 0/1/2); REST edge matrix 18/18 (traversal→400, empty→400, zip→400, bad-archive→400, oversize→400, long-query→400, history clamp, PATCH-name-ignored, static `..`→404); `node --check` JS_OK; UI serve 200s.
- **Reports**: `security_best_practices_report.md` (no criticals; H-1 install supply-chain, M-1 tar fallback, M-2 member allowlist, M-3 path disclosure) and `skills-manager-threat-model.md` v1.0 (A-1..A-4, B-1..B-5, T-1..T-10, R-1..R-5).
- **Ideas proposed** (task.md Milestone 5, all need ASK): native wrapper, live-preview editor, shortcut cheatsheet, pytest suite, CI, zip-import, tar-fallback refusal, link-warning→error.
- **Verified**: `py_compile` COMPILE_OK, both smokes PASS, `--help` OK, `list --scope agents --json` OK (`[]` in this env — no agent dirs present).
- **Note**: full browser click-through not re-run in this env (no browser tool); last verified 2026-08-14 zero-console-error pass stands; curl-based UI checks (index/Vue/static-jail) green.

## 2026-08-16 — Docs refresh: scopes / commandcode tracking (no code changes)

- **Confirmed live**: tracking the skills the `commandcode` CLI loads is already built in — `--scope agents` reads/writes `~/.agents/skills` directly (verified: lists the 4 live skills find-skills, karpathy-guidelines, kubernetes-skill, security-audit), and the web UI's scope switcher exposes the same **Agents** scope. No symlink created (would have risked the live dir); no code changes needed.
- **Docs were stale** (said 29 commands, no `--scope`, no `sync`/`scopes`/`tokens`/`install`, listed gui.py which is deleted). Refreshed: `docs/03-cli-surface.md` v0.2.0→v0.3.0 (40 invocable names, `--scope` flag, 4 scope-aware commands), `docs/02-modules.md` v0.2.0→v0.3.0 (added scopes.py/loader.py/tokens.py, removed gui.py), `docs/08-web-ui.md` v0.1.0→v0.2.0 (Scopes section, scope-aware API table), `AGENTS.md` v0.2.0→v0.3.0 (scope tracking in What-this-is), `docs/SESSION-CONTEXT.md` v0.1.0→v0.2.0 (scopes router rows, agent-scope gotcha, `--scope agents` in verification loop).
- **Verified**: `python3 -m py_compile skillsmgr/*.py smoke_*.py`, `python3 smoke_store.py`, `python3 smoke_web.py`, `python3 -m skillsmgr --help`, `python3 -m skillsmgr list --scope agents --json` — all pass.

## 2026-08-14 — Deep UI QA loop (agent-browser exploratory testing)

- **Method**: launched the web UI with a 6-skill corpus, attached a console error/warn tracker, and ran an iterative test loop (test → log → fix → re-test) covering every screen, action, modal, import/export, keyboard, theme, and responsive breakpoint (1280/900/640/400px).
- **CRITICAL BUG FOUND AND FIXED** (`webui/app.js` markdown renderer): `renderMarkdown()` referenced undefined `inTableSep` on every table row → `ReferenceError` thrown during any render of a skill body containing a table. Symptom: **completely blank page after reload** when a table skill was selected (Vue render crashed). Removed the dead `if (!inTableSep) {}` line.
- **BUG FOUND AND FIXED** (same renderer): tables rendered as **two separate `<table>` elements** (header row in one, data rows in another) because the separator row is skipped without closing the table. Added `inTable` state + `closeTable()` — header + body rows now render as one table.
- **BUG FOUND AND FIXED** (`webui/index.html`): skills list had **no empty state** for zero results (search no-match or Disabled filter) — bare empty `ul`. Added teaching empty states ("No matching skills", "No disabled skills", "No skills installed") with guidance text.
- **BUG FOUND AND FIXED** (`webui/index.html`): detail-pane empty state said "No skills installed" when a search/filter yielded zero results (misleading; skills existed). Now distinguishes `skills.length === 0 && !query` (truly empty store) from search/filter no-match ("Select a skill").
- **CLI BUG FOUND AND FIXED** (`cli.py:212`): `cmd_edit` checked `result.get("updated")` but `store.edit()` returns `{"name", "changed"}` — every successful edit printed "no changes for X" despite applying the change (history confirmed). Fixed to check `changed`; verified "updated" vs "no changes" behavior.
- **Verified working**: create (validation banner, full form, body via textarea), edit (pre-filled, partial update, compatibility/allowed-tools render), disable/enable, remove→trash→undo toast→restore, remove→purge, trash list/restore/empty-with-confirm, live search (name/description/body), filters, detail metadata + markdown (headings/lists/code/inline/bold/italic/links/quotes/table), validate (valid + empty), doctor, stats, history (skill filter + limit), templates (list + new), import archive (new + duplicate-skip), export (download lands in ~/Downloads), multipart folder upload (alpha/beta via API simulation), rebuild/resync index, Copy path (Clipboard API + execCommand fallback), theme toggle + localStorage persistence, `/` search focus, Esc menu/modal close, responsive stacking at 900px, compact topbar at 640px, no overflow at 400px. **Zero console errors across all flows post-fix.**
- **Re-test after fixes**: fresh browser session — page loads and reloads clean, table renders as one element, empty states correct, `python3 smoke_store.py` and `python3 smoke_web.py` both still ALL PASS.

## 2026-08-14 — Local web UI replaces GTK4 (Milestone 3 complete)

- **Decision**: abandoned the GTK4 GUI (toolkit fights: PyGObject `set_data` unsupported, GTK4/GTK3 Popover/`append` differences). Built a **local web UI** instead — same architecture as Jan / LM Studio / AnythingLLM / Open WebUI. User chose this direction explicitly.
- **Backend**: wrote `skillsmgr/webapp.py` — stdlib `ThreadingHTTPServer` bound to 127.0.0.1, JSON REST API over the Store public API, static file serving from `skillsmgr/webui/`. Hand-rolled `_parse_multipart` for webkitdirectory folder uploads (browser "Add from folder" → `Store.add` per SKILL.md).
- **Frontend**: wrote `skillsmgr/webui/` — Vue 3.5.13 vendored (`static/vendor/vue.global.prod.js`, no build step, works offline), `index.html` (all screens/modals), `styles.css` (design tokens, warm ivory + copper palette, authored dark theme), `app.js` (state, actions, hand-rolled XSS-safe markdown renderer, undo toasts).
- **CLI**: `webui` subcommand added (flags: `--host`, `--port`, `--no-browser`), `gui` kept as alias; `skillsmgr/gui.py` deleted; `cmd_gui` now calls `webapp.run`.
- **CLI bugs fixed** (found by reproducing before touching code): `cmd_export`/`cmd_backup` treated the `Path` return as a dict (`TypeError: 'PosixPath' object is not subscriptable`); `cmd_db_rebuild` used non-existent `result['skills']` key; `cmd_doctor` printed "database integrity check failed: ok" (guard now checks `!= "ok"`).
- **Tests**: wrote `smoke_web.py` — starts the server on an ephemeral port, hits every endpoint (static, CRUD, search, validate, toggle, stats/doctor/history, templates, export→import round-trip, trash/restore/purge, rebuild/resync, multipart folder upload, error paths). ALL WEB SMOKE TESTS PASSED.
- **Browser click-through (agent-browser 0.27 + Chrome)**: exercised create, detail view (real multi-line skill markdown: 333 elements rendered), live search, filters, disable/enable, remove+undo, trash/restore, validate (valid + 3-issue invalid skill), doctor, stats, history, templates, import (new + duplicate), export (download landed in ~/Downloads), theme toggle + persistence, 400px mobile viewport. **Zero console errors** across all flows.
- **BUG FOUND AND FIXED**: mobile topbar overflowed at 400px (`scrollWidth 458 > clientWidth 385`) — added `max-width: 640px` rules hiding brand text + stat pill, tightening padding/buttons. Verified no overflow after fix.
- **BUG FOUND AND FIXED**: webapp static route dropped `parts[2:]` (Vue file 404) — now joins all parts.
- **Docs**: wrote `docs/08-web-ui.md` (authoritative) and `docs/SESSION-CONTEXT.md` (fast re-anchor cache). Updated AGENTS.md v0.2.0 (locked constraints: web UI instead of GTK), docs/README.md, 02-modules v0.2.0, 03-cli-surface v0.2.0, 05-gui-plan marked SUPERSEDED.
- task.md Milestone 2+3 items all `[x]`.

## 2026-08-13 — Manage views (Milestone 2)

- Implemented the Manage section in `skillsmgr/gui.py` (handlers inserted after `_on_refresh_skills`, before `class SkillsManagerApp`), mirroring CLI command shapes via the Store public API only: `_on_validate_skill` (`Store.get` → `validate_skill(name, Path(record["path"]))`, catching `(OSError, ValueError)`; issues rendered via `getattr(issue, 'message', issue)`), `_on_doctor` (`Store.doctor`), `_on_stats` (`Store.stats` via `_format_dict`), `_on_history`/`_on_history_response` (GTK4 DropDown + GTK3 ComboBoxText over `["All skills"] + names` from `Store.list`, limit entry default 50, `int(limit_text)`/ValueError→50, empty → `_notify(self, "No history records.")`, rows `f"{record['at']}  {record['name']}  {record['action']}"`), `_on_trash` (`Store.trash_list`), `_on_purge_trash`/`_on_purge_trash_response` (confirm dialog, Cancel / `_RESPONSE_PURGE=2` → `Store.purge_trash`, `_notify` + `_reload_list()`), `_on_templates` (`list_templates(self._store.templates_dir)`; OSError → plain `_alert`, no `_log_store_error`), `_on_new_template`/`_on_new_template_response` (name entry + body TextView in ScrolledWindow, `create_template(..., body or None)`, empty name → `_alert(self, "Template name is required.")`, `(ValueError, FileExistsError)` → `_alert(self, str(exc))`), `_on_rebuild_index` (`Store.db_rebuild`), `_on_resync` (`Store.resync`, added/updated/removed counts + `_reload_list()`). Shared helpers: `_render_store_output` (single `set_text(f"{title}\n{'-' * len(title)}\n\n{text}")`), `_format_dict` (`@staticmethod`, recursive via `SkillsWindow._format_dict`, dicts indented +2, lists joined ", ").
- Pattern: PyGObject attrs attached to the dialog (`dialog._history_dropdown`, `dialog._template_body`, etc.), read via `getattr` in response handlers; response guard `response != Gtk.ResponseType.OK` → destroy + return (cancel path).
- Verified: `python3 -m py_compile skillsmgr/gui.py` — COMPILE_OK; `DISPLAY=:0 timeout 6 python3 -m skillsmgr gui` exited 124 with no traceback; `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `python3 -m skillsmgr --help` unchanged (no CLI regressions). task.md M2 item 6 `[x]`.

## 2026-08-13 — Search bar (Milestone 2)

- Implemented the search bar in `skillsmgr/gui.py`, mirroring CLI `search` behavior via the Store public API (`Store.search` at store.py:365 — case-insensitive LIKE over name/description/body with wildcard escaping, same row shape as `Store.list`).
- `_search_entry.connect("search-changed", self._on_search_changed)` added at entry build (gui.py:203-206); `_on_search_changed` added after `_reload_list` (gui.py:366).
- Design decisions: no debounce — direct signal connection (fast local SQLite LIKE; KISS). Empty/whitespace term → `_reload_list()` (full list). Otherwise: clear list + selection, reset `_text_buffer` to "Select a skill to view its SKILL.md content.", wrap `Store.search(term)` in `try/except StoreError` → `_log_store_error` + `_alert(self, f"Could not search skills: {exc}")` with "Could not search skills." placeholder (no tracebacks, window stays usable); no matches → "no matching skills" placeholder.
- Verified: `python3 -m py_compile skillsmgr/gui.py` — COMPILE_OK; `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `python3 -m skillsmgr --help` unchanged (no CLI regressions); `DISPLAY=:0 timeout 6 python3 -m skillsmgr gui` exited 124 with no traceback (search bar + live filtering run until timeout). task.md M2 item 5 `[x]`.

## 2026-08-13 — Skill actions (Milestone 2)

- Implemented all action methods in `skillsmgr/gui.py` (methods before `SkillsManagerApp`), mirroring CLI command shapes: `_on_new_skill`/`_on_new_skill_response` (create dialog → `Store.create`), `_on_add_skill`/`_on_add_skill_picked`/`_do_add_skill` (file picker → `Store.add`), `_on_edit_skill`/`_on_edit_skill_response` (edit dialog → `Store.edit`, partial semantics, only non-empty fields sent), `_on_disable_skill`/`_on_enable_skill` (`Store.disable`/`enable`), `_on_remove_skill`/`_on_remove_response` (Cancel / `_RESPONSE_TRASH=1` / `_RESPONSE_PURGE=2` → `Store.remove`), `_on_restore_skill`/`_on_restore_response` (`Store.restore`), `_on_refresh_skills` (`_reload_list`). Menu wired via `Gtk.MenuButton` + `Gtk.Popover` + `_add_menu_item` (8 items: New/Add/Edit/Disable/Enable/Remove/Restore/Refresh).
- **BUG FOUND (PyGObject limitation)**: `set_data`/`get_data` raise `RuntimeError: Data access methods are unsupported. Use normal Python attributes instead`. Converted all 19 sites (14 edit ops) to Python attributes: `obj._attr = value` / `getattr(obj, "_attr", None)`. Sites covered: dialog rows, detail-view selection (GTK4 `SingleSelection` + GTK3 `ListBox` `set_data`), response handlers (`_current_name`, `_dialog`, `_current_item`, `_purge` flags).
- **BUG FOUND (GTK4 API)**: `Gtk.Popover` has no `append`; `_content_add(popover, menu_box)` raised `AttributeError: 'Popover' object has no attribute 'append'`. Fixed `_content_add` to prefer `set_child` when the container has it (Popover), else GTK4 `append` (Box/dialog content areas), else GTK3 `pack_start`.
- Verified: `python3 -m py_compile skillsmgr/gui.py` — COMPILE_OK; `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `python3 -m skillsmgr --help` unchanged (no CLI regressions); `DISPLAY=:0 timeout 6 python3 -m skillsmgr gui` exited 124 with no traceback (window + menu popover launch until timeout). task.md M2 item 4 `[x]`.

## 2026-08-13 — Skill detail view (Milestone 2)

- Implemented the detail view in `skillsmgr/gui.py`, mirroring CLI `view` (`cli.py:172-192`): right pane renders 8 metadata lines (`name`, `status` with `"disabled" if record["disabled"] else "active"` mapping, `category`, `license`, `version`, `description`, `path`, `updated` from `updated_at`; each `or "-"`), a blank line, then the SKILL.md body — all fetched via `Store.get(name)`.
- GTK4 branch: `Gtk.SingleSelection` `"selection-changed"` → `_on_selection_changed` (guards `self._text_buffer is None`, uses `get_selected_item()` → `_SkillItem.name`); GTK3 branch: `Gtk.ListBox` `"row-selected"` → `_on_row_selected` via `row.get_data("skill-name")` (name attached with `box.set_data` at insert time). No selection → placeholder "Select a skill to view its SKILL.md content."
- `_render_detail(name)` wraps `Store.get` in `try/except StoreError` → `_log_store_error(exc)` + `_alert(self, f"Could not load skill '{name}': {exc}")` (no tracebacks; satisfies M2 item 7 constraint early).
- Verified: `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `python3 -m skillsmgr --help` unchanged (no CLI regressions); `timeout 6 python3 -m skillsmgr gui` exited 124 (GUI + detail pane launch on DISPLAY=:0 until timeout). task.md M2 item 3 `[x]`.

## 2026-08-13 — Main window skill list (Milestone 2)

- Implemented the skill list in `skillsmgr/gui.py`, mirroring CLI `list` output: columns NAME/STATUS/CATEGORY/DESCRIPTION via `Store.list()` (active-only, ORDER BY name), rows = bold name + `status · category — description` detail line (description truncated at 60 chars, same `_truncate` semantics as cli.py:38-41).
- GTK4 branch: `Gio.ListStore.new(_SkillItem)` + `Gtk.SingleSelection` + `Gtk.SignalListItemFactory` (`_setup_row`/`_bind_row`) + `Gtk.ListView`; `_SkillItem` is a GObject with str properties (name/status/category/description) and `from_row()` mapping (`"disabled" if row["disabled"] else "active"`, `category or "-"`). `self._model`/`self._selection` kept for the detail view.
- GTK3 fallback: `Gtk.ListBox` with per-row vertical Boxes (`pack_start`, `list_box.insert` — 3.24-safe), same row layout.
- `__init__` now loads the list under `try/except StoreError`: error → `_log_store_error` + `_alert` dialog + "Could not load skill list." label; empty store → "no skills installed" label; `_show(self)` at end of `__init__` (show_all only on GTK3).
- Verified: `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `python3 -m skillsmgr --help` unchanged (no CLI regressions); `timeout 6 python3 -m skillsmgr gui` exited 124 (list renders on DISPLAY=:0 until timeout). task.md M2 item 2 `[x]`.

## 2026-08-13 — GTK4 GUI scaffold (Milestone 2)

- Wrote `skillsmgr/gui.py` (scaffold): GTK4 4.14 → GTK3 3.24 fallback, `SkillsManagerApp`, `SkillsWindow` (HeaderBar with search entry + actions menu, Paned layout 900x600), `_alert` (AlertDialog GTK4 / MessageDialog GTK3), `_log_store_error`, `run()` entry point.
- Wired `gui` subcommand in `skillsmgr/cli.py`: `cmd_gui` (lazy import of the gui module; `ImportError`/`ValueError`/`RuntimeError` → clean `_err` + EXIT_ERROR) plus `gui` subparser; parent `--data-dir` flows through `_make_store`.
- Verified: `python3 -m skillsmgr --help` lists `gui    launch the desktop GUI (GTK4)` with all other commands unchanged (no CLI regressions); `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `timeout 6 python3 -m skillsmgr gui` exited 124 (GUI launched on DISPLAY=:0 and ran until timeout — GTK init OK).

## 2026-08-13 — Docs layer (Milestone 1)

- Created `docs/` directory; wrote `task.md` (v0.2.0), `AGENTS.md` (v0.1.0), `docs/README.md` (v0.1.0).
- Wrote `docs/01-architecture.md` (v0.1.0): data model, data-dir layout, FS vs SQLite roles.
- Wrote `docs/02-modules.md` (v0.1.0): module inventory, constants, search scoring, exit codes.
- **FACT CORRECTION**: command count corrected from "25" to "29 commands (22 top-level + 7 subcommands) plus 2 aliases (`ls`, `rm`) — 31 invocable names". Fixed in `task.md` and `docs/02-modules.md` line 17. `docs/03-cli-surface.md` records the stale-fact note.
- Wrote `docs/03-cli-surface.md` (v0.1.0): full command/flag/exit-code surface.
- Wrote `docs/04-store-api.md` (v0.1.0): `Store` public API + SQLite schema, verified against `store.py`.
- Toolkit verification: GTK4 4.14 (PyGObject 3.48.2) present; GTK3 3.24 fallback; Wayland session; PySide6/PyQt6/wx absent → GTK confirmed.
- Wrote `docs/05-gui-plan.md` (v0.1.0): GUI blueprint, CLI→view mapping, Milestone 3 iteration loop.
- Wrote `docs/07-context-strategy.md` (v0.1.0): hot/warm/cold loading model.
- Wrote this file (v0.1.0).
- **QA PASSED** (Milestone 1 close-out): `python3 -m skillsmgr --help` runs with no regressions; `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; all 8 `docs/*.md` exist with H1 + version line; every `@docs/` pointer in the repo resolves (no missing files); HADS markers valid. task.md Milestone 1 fully `[x]`.

## Milestone 2 — GTK4 GUI (pending)

- [x] Scaffold `skillsmgr/gui.py` + `__main__` integration
- [ ] Main window, detail view, actions, search, manage, dialogs
- [ ] Launch check on DISPLAY=:0

## Milestone 3 — Zero-error loop (pending)

- [ ] `--help` no-regression, `smoke_store.py` passes
- [ ] Exercise every GUI action; log each iteration here
- [ ] Loop until zero errors/bugs
