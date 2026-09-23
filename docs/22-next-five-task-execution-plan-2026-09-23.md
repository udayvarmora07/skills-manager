# Next Five Task Execution Plan — 2026-09-23

**Version 1.0.1**

**AI manifest**: Implementation-ready queue of five next tasks selected from @docs/18-project-improvement-audit-2026-09-22.md after reconciling the 2026-09-23 worktree. Use this plan to implement one bounded task at a time. Recheck external release and pull-request state immediately before acting; dated observations below are not permanent facts. This file authorizes planning only, not a merge, tag, package publication, or external outreach.

## Reconciliation with the audit

**[NOTE]** Baseline for this plan is `main` at `6733da9`, plus the existing local
README, screenshot, contributor-guide, and tracking edits. Those local edits
were verified but had not been committed or pushed when this plan was written.
Preserve them and the unrelated untracked `.autogit` file.

| Audit item | Status on 2026-09-23 | Evidence and remaining boundary |
|---|---|---|
| P0 1–5: rollback, docs discovery, narrow lint, Bandit, SPDX metadata | Implemented on `main` | @docs/21-p0-trust-gate-and-release-metadata-hardening-plan.md and @docs/STATIC-ANALYSIS.md; no repeat task |
| P0 6, 7, 9: README comparison, visual, contribution route | Completed locally, not yet shipped | Working-tree README, `docs/images/overview-2026-09-23-1280x900.png`, and CONTRIBUTING; keep their review/commit status explicit |
| P0 8: corrected package release | Open | `pyproject.toml` has `1.0.1`; [PyPI still serves 1.0.1](https://pypi.org/project/skill-control-plane/) with old README claims and license metadata |
| P0 10: dependency PRs | Open | [Five Dependabot GitHub Actions PRs](https://github.com/udayvarmora07/skills-manager/pulls) were open on 2026-09-23; no compatibility disposition recorded here |
| P1 1: source-aware update journey | Partially delivered | @docs/19-safe-local-source-update-implementation-plan.md shipped exact-target local candidate review/apply/snapshot/rollback; upstream check/fetch and one end-to-end source journey remain separate decisions |
| P1 2 and 4: state clarity and first-run guidance | Partially delivered | Library and Quality distinguish observations; the existing getting-started checklist is mainly an empty-library state, not a populated scan-to-action journey |
| P1 3: hygiene inspection | Substantial read-only slice delivered | @docs/20-skill-hygiene-report-implementation-plan.md covers observed duplicates, drift, references, and context; it does not claim usage or safe deletion |
| P1 5: agent management skill | Open | JSON CLI and REST surfaces exist; no shipped dry-run-first management skill is identified in this repository |
| P1 6: 100/1,000/10,000 performance evidence | Partial | @docs/16-product-baseline-2026-09-18.md measures up to 2,000 real files; the 10,000 hygiene result is record-only, not an end-to-end inventory measurement |
| P1 7: design partners | Human/external gate | @docs/17-adoption-and-distribution.md defines the consent protocol; no participant result is claimed |

**[SPEC]** The five tasks below are the next implementation queue. The
selection favors a bounded release trust pass and an observable first-run
workflow. Do not reimplement the completed P0 fixes, invent usage evidence, or
turn a proposal in the dated audit into an already-shipped capability.

## Shared execution contract

**[SPEC]** One writer per working tree and task. Before each task, inspect
`git status`, the current branch/remote, open PRs where relevant, and any
active writer. Keep earlier local edits intact. Use a separate worktree or
serialize work touching the same source or docs. Update `task.md` and
@docs/06-progress-log.md after each implementation; update the owning public
documentation and CHANGELOG for behavior/release changes.

The filesystem remains the source of truth; SQLite schema and
`SCHEMA_VERSION` stay unchanged. The CLI and web backend remain stdlib-only;
the Vue frontend remains vendored with no build step and a loopback default.
Any proposed new CLI command, public Store method, schema change, runtime
dependency, or change to those locked constraints needs maintainer approval
before implementation. Security and effective-state claims must be backed by
observed evidence, not heuristics presented as certainty.

The common verification ladder for code changes is Python compilation,
`python3 -m unittest discover -s tests`, both smoke scripts, `check_docs.py`,
`check_complexity.py`, `git diff --check`, and the narrow Ruff gate. Run the
browser harness and Node syntax checks when the UI changes. Run the pinned,
hash-verified wheel/sdist build and `check_package_data.py --dist-dir` for a
release candidate. The default interpreter's optional `build` absence does
not count as artifact verification.

## Task 1 — Triage the five GitHub Actions dependency PRs

**[NOTE] Audit source:** P0 item 10. **Priority:** first. **Size:** one grouped
maintenance review, with five independent PR verdicts.

**[SPEC] Outcome:** Each open Dependabot PR receives an evidence-backed
recommendation: accept, request changes, or defer. At plan creation these are
[#15 setup-python](https://github.com/udayvarmora07/skills-manager/pull/15),
[#16 checkout](https://github.com/udayvarmora07/skills-manager/pull/16),
[#17 action-gh-release](https://github.com/udayvarmora07/skills-manager/pull/17),
[#18 setup-node](https://github.com/udayvarmora07/skills-manager/pull/18), and
[#19 attest-build-provenance](https://github.com/udayvarmora07/skills-manager/pull/19).
Refresh the list first; PR numbers or states may have changed.

**Work:**

1. For each PR, inspect its exact action commit, upstream release notes,
   runner/runtime requirements, permission changes, and every workflow use
   site. Identify whether a major version alters arguments, outputs, or
   artifact/provenance behavior. Keep first-party action references pinned to
   reviewed full commit SHAs with adjacent version comments.
2. Compare each proposed change against the pinned CI and release workflow
   contract, including build-once artifact reuse, tag/version gate, TestPyPI,
   PyPI Trusted Publishing, attestation, and post-publish verification.
3. Record a per-PR disposition, supporting links, CI status, and any local
   contract adjustment in a dated HADS review note. If a PR is accepted,
   integrate and verify it individually or in a justified compatible group;
   do not treat a green Dependabot label as a review.

**Acceptance:** All five current PRs have explicit verdicts; every accepted
change has green relevant CI and release-workflow contract checks on the
resulting tree; deferred changes retain a reason and revisit condition. A
triage report can finish this task without merging any PR. Repository writes,
reviews, comments, and merges occur only when separately authorized for this
execution.

**Execution status (2026-09-23):** Complete as a read-only triage. All five
current PRs remain open; @docs/23-github-actions-dependency-pr-review-2026-09-23.md
records five evidence-backed request-changes recommendations, CI status,
upstream compatibility notes, and revisit conditions. No action pin was
integrated because the relevant runs are red or stale and PR #19 still uses a
Node 20 nested action at the Node 20 removal date.

## Task 2 — Prepare and release corrected package metadata and copy

**[NOTE] Audit source:** P0 item 8. **Dependency:** Task 1 verdicts and the
local README/contributor/screenshot changes reviewed and committed. **Size:**
one release candidate plus a guarded publication step.

**[SPEC] Outcome:** A new `skill-control-plane` release carries the current
README description and the already-implemented PEP 639 `MIT` license metadata,
and the published wheel/sdist match the checked artifacts exactly.

**Work:**

1. Recheck the current PyPI version and repository tags; choose an unused next
   version (provisionally `1.0.2`) only after confirming version policy.
   Reconcile `pyproject.toml`, README installation claims, CHANGELOG, and
   release notes. No old artifact may be reused.
2. Build once with `requirements-build.txt` hashes and `--no-isolation`.
   Verify both artifacts with `check_package_data.py --dist-dir`, inspect wheel
   `METADATA` and sdist `PKG-INFO`, and clean-install the exact wheel in an
   isolated environment for CLI CRUD/web-asset smoke checks.
3. Review the exact commit, tag, artifact names, and SHA-256 digests with the
   maintainer. Only after release approval, use the existing protected tag
   workflow; verify TestPyPI, PyPI, provenance/attestation, GitHub Release,
   and post-publish install against those exact digests.

**Acceptance:** Before publication, tests, docs, static checks, package-data,
release contracts, and clean-wheel smoke pass on the intended release tree.
After approved publication, the new PyPI page shows corrected copy and SPDX
metadata, and the published artifact hashes match the reviewed build. If
approval or external configuration is absent, stop with a reviewable release
candidate and keep P0 item 8 open; do not label an unpublished build released.

**Execution status (2026-09-23):** The `1.0.2` candidate was selected after
rechecking PyPI's latest release (`1.0.1`) and repository tags (`v1.0.0`,
`v1.0.1`). The README says the distribution is available on PyPI. The pinned,
hash-verified build produced `skill_control_plane-1.0.2-py3-none-any.whl`
(SHA-256 `2d7beb9ba9545e38384da0ace95f2f64ba3c1ff750a225053fb641ecb7f25de8`)
and `skill_control_plane-1.0.2.tar.gz` (SHA-256
`3e8aa27a9a3d3e8b0cda395490a57217bbe598ff6c0c9687cbd73c3a6635311c`) once
under `/tmp/skillsmgr-release-candidate-2026-09-23/dist/`. `check_package_data.py`
passed both artifacts; wheel `METADATA` and sdist `PKG-INFO` report version
1.0.2 and `License-Expression: MIT`; the clean wheel install passed isolated
CLI CRUD/validation and web asset/API smoke checks. The source remains an
uncommitted worktree based on `6733da9`; no release commit, tag, or upload was
made. Exact-commit review and separate maintainer approval remain required for
publication.

## Task 3 — Measure full inventories at 100, 1,000, and 10,000 skills

**[NOTE] Audit source:** P1 item 6. **Dependency:** none; can proceed while
Tasks 1–2 are reviewed, in a separate worktree or serialized. **Size:**
bounded performance evidence, not a performance rewrite.

**[SPEC] Outcome:** Reproducible, privacy-safe cold and warm evidence for
actual filesystem inventories and their startup-critical REST paths. Reuse or
extend `baseline_harness.py`; do not mistake the existing record-only 10,000
hygiene benchmark for a full-inventory result.

**Work:**

1. Add deterministic 100, 1,000, and 10,000 real `SKILL.md` fixture shapes
   under a disposable data root. Keep file creation time separate from read
   timing. Bound fixture bytes, cleanup, runtime, and memory so the check can
   be run intentionally without becoming a default fast CI gate.
2. Measure first/cold and repeat/warm observations for scopes, merged list,
   stats, Doctor, and the Hygiene Report where applicable. Record at least 20
   samples for a reported p95, sample order, cache/process reset policy,
   median, p95, timeout/degradation status, peak memory where available, and
   Python/OS/CPU context. Use an explicit, documented percentile method.
3. Save a machine-readable report and update @docs/16-product-baseline-2026-09-18.md
   with exact commands and dated results. Identify the first bottleneck and a
   proposed budget; do not invent a passing target after observing the data.

**Acceptance:** All three sizes complete or fail with a reproducible bounded
reason; counts agree with created fixtures; cold and warm numbers are clearly
separated; the 10,000 run never silently truncates evidence; and harness
contracts plus the relevant existing tests pass. No production optimization is
required by this task unless a correctness failure is found.

**Execution status (2026-09-23):** Complete with a bounded incomplete 10,000
result. All 100 and 1,000 cold/warm route groups completed 20/20 samples with
matching fixture counts. At 10,000, cold scopes, merged list, and Stats
completed 20 samples; Doctor completed 11 before the 900-second total budget,
then Doctor/Hygiene and all warm routes are explicitly `not_run`. The JSON
report records sample order, timeout/runtime policy, peak RSS, and count
checks. Harness contracts now suppress p95 unless 20 successful samples
exist. See @docs/16-product-baseline-2026-09-18.md and
`benchmarks/full-inventory-2026-09-23.json`.

## Task 4 — Complete the first-run scan-to-action journey

**[NOTE] Audit source:** P1 items 2 and 4. **Dependency:** Task 3's baseline
helps set loading and degraded-state expectations. **Size:** one UI journey
using existing read APIs, not a new onboarding subsystem.

**[SPEC] Outcome:** A first-time user can inspect detected roots, the initial
inventory, scope/instance differences, and supported effective-resolution
evidence, then reach one safe next action. Extend the current empty-library
getting-started state so a pre-existing populated library is also guided.

**Work:**

1. Define visible meanings for installed/observed, enabled/disabled,
   project-observed, and effective/shadowed/unknown. A discovered file is not
   proof of activation or effective load. Use existing `/api/scopes`, skills,
   Doctor/Quality, and supported explain evidence; display unavailable or
   undocumented precedence explicitly.
2. Add a short, skippable, restartable path: scan status and roots, one
   example physical instance with its scope, any evidenced conflict, then
   links to Library, Quality, and a safe preview. Reuse existing view routing,
   selection, focus, and responsive patterns. No automatic sync, cleanup,
   install, or update happens during onboarding.
3. Cover empty, populated, divergent, malformed, unavailable-root, and
   degraded-scan states. Make keyboard and screen-reader progress clear, keep
   mobile targets reachable, and avoid exposing raw local paths beyond the
   current REST redaction boundary.

**Acceptance:** Synthetic first-run scenarios reach a useful observed scan
without mutation; labels never assert an uncited effective winner; skip and
restart work; selected actions land on an exact existing surface; tests, Node
syntax, six-viewport browser harness, and relevant smoke checks pass. Record
measured time-to-first-useful-result, but do not claim the audit's five-minute
human target without participant evidence.

**Execution status (2026-09-23):** Complete locally. The populated guide covers
observed roots, exact scope/instance identity, divergence and scan failures,
the supported effective-state explanation, Skip/Restart, and safe links to
existing Library, Quality, and preview surfaces. The browser harness passed
six viewport sizes plus scope-failure, inventory-failure, unavailable-root,
and empty-inventory scenarios. The populated fixture asserted visible
malformed/unaddressable and divergent-copy attention items. Median synthetic
time-to-settled-scan was 955 ms; this is not participant evidence. Details
and the run command are in
@docs/16-product-baseline-2026-09-18.md.

## Task 5 — Publish a dry-run-first agent management skill

**[NOTE] Audit source:** P1 item 5. **Dependency:** none for the first draft;
align final wording with Task 4's state vocabulary. **Size:** a repository
example and contract verification, not a new product API.

**[SPEC] Outcome:** A portable `SKILL.md` example teaches an AI coding agent
to inventory, validate, explain, preview, request explicit human approval for
mutations, and verify the exact result using the existing `skills-mgr` CLI.
Place it under a clearly labeled `examples/` path and document manual opt-in
installation; do not auto-install it into any user's agent scope.

**Work:**

1. Specify trigger text, supported Python/CLI prerequisites, workspace/data
   boundaries, and JSON reading rules. Cite the current @docs/03-cli-surface.md
   contract. Keep read-only inventory and Doctor steps first.
2. Include tested examples for `list --scope all --json`, validation/Doctor,
   `update preview ... --json`, and `install --dry-run`. Distinguish preview
   from commit; `sync` has no dry-run flag and must not be described as if it
   does. A mutation example must require the user's exact target and explicit
   approval, then re-read and report the outcome plus recovery path.
3. Validate the example with the project's validator and isolated CLI probes;
   test refusal/stop behavior for unknown scope, divergent same-name copies,
   missing target path, degraded evidence, and stale review. Keep raw skill
   body/credentials out of sample output and do not claim agent runtime
   integration without an actual opt-in test.

**Acceptance:** Every documented command exists and runs as described;
read-only commands do not write managed skills; a preview may write only its
private, expiring review record and leaves the candidate and managed target
unchanged; the skill never guesses an effective winner or auto-approves a
write; manual installation and removal instructions are clear; docs and
package-data gates remain green.

**Execution status (2026-09-23):** Complete locally. Added the opt-in example
under `examples/skills-manager-management/`, with manual install/removal
instructions and no package auto-install. The project validator reported no
errors or warnings. Isolated CLI contracts passed for inventory, per-instance
validation, Doctor/Explain, `install --dry-run`, non-mutating update preview,
ambiguous target, unavailable scope evidence, unknown scope, missing target,
and stale-review refusal. The examples use the existing command surface and
do not claim agent-runtime integration.

## Order, handoff, and decision gates

**[SPEC]** Execute Task 1 before Task 2. Task 3 can be prepared independently,
then informs Task 4. Task 5 can be drafted independently, but its final state
vocabulary must match Task 4. If implementation overlaps the same files,
serialize those edits under the one-writer rule.

Task 1 triage does not imply authority to merge or post to GitHub. Task 2
requires review of the exact candidate before tagging or publishing. Task 4
must pause if it needs a new command, Store method, API contract, schema, or
runtime dependency; propose the change first. Human usability sessions and
design-partner recruitment require consent and external coordination and are
not silently folded into these five implementation tasks.

**[?]** The maintainer still needs to review the exact release commit and
artifact digests and approve the protected publication step. Tasks 1, 3, 4,
and 5 can complete without publishing.

## Definition of done for this five-task queue

**[SPEC]** The queue is complete only when each task's acceptance evidence is
recorded with date, exact tree/commit, and reproducible commands; the shared
verification ladder is green on the final tree; `task.md`, the owning docs,
CHANGELOG, and @docs/06-progress-log.md agree; and any external action is
reported as performed only after it actually succeeds. A deferred release,
unreviewed PR, synthetic benchmark, or automated UI run must not be described
as a published package, merged dependency update, or human usability result.

**Queue status (2026-09-23):** Tasks 1, 3, 4, and 5 have local evidence recorded.
Task 2 has a verified `1.0.2` candidate, but remains open because it is not an
exact release commit and publication has not been approved. The queue remains
open through that review gate.
