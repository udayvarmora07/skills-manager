# GitHub Actions Dependency PR Review — 2026-09-23

**Version 1.1.0**

**AI manifest**: Dated, read-only review of Dependabot PRs #15–#19 against the exact workflow uses, upstream action metadata, current CI evidence, and the release artifact contract. Recommendations are review guidance only; no GitHub review, comment, branch update, or merge was posted. Re-verified 2026-10-06: all five PRs are still open, every SHA recorded below still matches the `uses:` ref its PR introduces, and the CI evidence is refreshed against the current (now green) `main`.

## Re-verification — 2026-10-06

**[NOTE] A method correction, recorded because the first check was wrong.**
`gh pr view N --json commits -q '.commits[-1].oid'` returns Dependabot's
**branch tip**, which includes its own "update branch" merge commits — not the
commit that made the change. Comparing that tip against the SHAs below appeared
to show all five had gone stale. They have not. Each PR here carries exactly one
commit, and it *is* the introducing commit, but that is a fact about these five
branches rather than a property of the query. The reliable check is the `uses:`
line in the diff:

```bash
gh pr diff N | grep -E '^\+.*uses:'
```

**[SPEC] All five reviewed SHAs are confirmed exact.**

| PR | `uses:` ref its PR introduces | Matches this doc |
|---|---|---|
| #15 | `actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97` | yes |
| #16 | `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` | yes |
| #17 | `softprops/action-gh-release@efb35369e0ad2afab669f228072c1b0d510eae64` | yes |
| #18 | `actions/setup-node@820762786026740c76f36085b0efc47a31fe5020` | yes |
| #19 | `actions/attest-build-provenance@e8998f949152b193b063cb0ec769d69d929409be` | yes |

### The CI reason cited below is no longer the reason

**[SPEC]** The original review cited failing unit jobs as a reason to request
changes. `main` was red on 2026-09-16 for an unrelated cause (the purge test,
since fixed by A1) and is **green now** — run
[37311664410](https://github.com/udayvarmora07/skills-manager/actions/runs/37311664410)
at `522b81f` is success on all 15 jobs. The PR heads have not been re-run since,
so their recorded failures are from a tree whose base has since moved. Querying
the head commit directly (`/commits/<sha>/check-runs`, not
`statusCheckRollup`) gives:

| PR | Head commit | Head-commit check state |
|---|---|---|
| #15 | `43c357fb` | unit py3.10–3.14 **all five failed**; adversarial/browser/docs/package skipped; xplat green |
| #16 | `66191bbf` | unit py3.10–3.14 **all five failed**; adversarial/browser/docs/package skipped; xplat + static-correctness green |
| #17 | `21028449` | unit py3.10, py3.11 **failed**; py3.12–3.14 green; adversarial/browser/docs/package skipped; xplat green |
| #18 | `07084c85` | unit py3.10–3.14 **green**; **browser smoke and frontend syntax FAILED**; every other job green |
| #19 | `dd39fd39` | unit py3.10, py3.11 **failed**; py3.12–3.14 green; adversarial/browser/docs/package skipped; xplat green |

**[?]** The skipped jobs on #15/#16/#17/#19 are consequences of the `needs: unit`
coupling, not independent results. Their content is unverified on those heads.

### #18's failure is not what the original review predicted — and the fix is known

**[SPEC] This is the substantive new finding.** The original review predicted a
"v7.0.0 ESM/runtime migration risk". The actual failure is neither ESM nor
runtime. The job log ends:

```text
RuntimeError: a trusted Node executable is required for browser_harness.py
```

That is `launcher_security` refusing an untrusted executable — the same SEC-15/SEC-16
boundary, working correctly. Its cause is **staleness, not the bump**: `setup-node`
is used in exactly one place (`ci.yml`, the `browser` job), and the fix for this
failure — the `Tighten the Node tool cache permissions` step, added because
`setup-node` extracts with mode `0777` — is **absent from PR #18's branch**. The
PR's base is `3388b93`, and the tighten step landed in `2d7d6a7`, two commits
later. `git merge-base --is-ancestor 3388b936 2d7d6a7` confirms the base predates it.

**[SPEC]** So the correct disposition for #18 is unchanged in direction
(request changes) but wrong in reason: the branch must be rebased onto current
`main` first, and only then does the bump's own compatibility become testable.
Reviewing a `setup-node` bump against a branch that predates the step that makes
`setup-node` usable measures the base, not the proposal.

**[NOTE] `statusCheckRollup` is not a substitute for the head query.** It is a
convenience aggregate that mixes in base-branch results, so on a branch whose base
has moved it can report a state the head commit never had. The #18 head above
shows `browser smoke and frontend syntax` failing while `statusCheckRollup` for
the same PR renders the same job green. Query the head commit.

### Which PRs the pin gate would and would not have caught

**[SPEC]** This is now precise because of `b50ca1e` (see below). Both action-pin
gates required a leading `- ` before `uses:`, so the two-line `- name:` / `uses:`
step form was invisible to both.

- **Before the fix, #19 would not have been caught at all** — the release
  provenance attestation is written in the two-line form, and repinning it to a
  floating `@v2` tag or to 40 zeros left
  `test_sec14_every_first_party_action_is_pinned` **green**.
- **Before the fix, #18 would not have been caught either**, for the same reason:
  `setup-node` sits in the two-line form.
- **Before the fix, #17 would not have been caught either** —
  `softprops/action-gh-release`, the GitHub Release upload step, is two-line form
  and the third-party gate had the identical blind spot.
- **#15 and #16 were always covered.** Both write `- uses:` on the dash line, so
  the mandatory-dash regex read them. Their `EXPECTED_FIRST_PARTY_SHAS` mismatch
  failures described below are genuine and were never masked.

**[NOTE]** After `b50ca1e` both parsers treat the dash as optional and four new
tests pin it, each mutation-caught. The real tree passes with the fix, so all nine
previously-invisible sites already carried correct reviewed SHAs — **the gate was
blind, not the workflows wrong.**

## Review snapshot (original, 2026-09-23)

**[NOTE]** Refreshed on 2026-09-23 with `gh pr list`, `gh pr view`, `gh pr diff`, and the linked run logs. The repository default branch was at `6733da9a9b17f6947a317248709c046da4c6cbfd`. All five PRs were open, unmerged, and had no submitted review decision. Their latest observed CI runs were created on 2026-09-16 except #16, which had a newer run on 2026-09-22.

| PR | Proposed reviewed commit and current workflow use | Latest observed checks | Recommendation |
|---|---|---|---|
| [#15 setup-python 5.6.0 → 7.0.0](https://github.com/udayvarmora07/skills-manager/pull/15) | `5fda3b95a4ea91299a34e894583c3862153e4b97`; every `setup-python` use in `ci.yml` and `release.yml` | [Run 35085427807](https://github.com/udayvarmora07/skills-manager/actions/runs/35085427807): all five Python unit jobs failed; package, docs, security, and browser jobs skipped | **Request changes** |
| [#16 checkout 4.4.0 → 7.0.1](https://github.com/udayvarmora07/skills-manager/pull/16) | `3d3c42e5aac5ba805825da76410c181273ba90b1`; all checkout uses in both workflows | [Run 35774043493](https://github.com/udayvarmora07/skills-manager/actions/runs/35774043493): all five Python unit jobs failed; downstream jobs skipped | **Request changes** |
| [#17 action-gh-release 2.3.3 → 3.0.3](https://github.com/udayvarmora07/skills-manager/pull/17) | `efb35369e0ad2afab669f228072c1b0d510eae64`; release upload step only | [Run 35085438756](https://github.com/udayvarmora07/skills-manager/actions/runs/35085438756): Python 3.10 and 3.11 unit jobs failed; downstream jobs skipped | **Request changes** |
| [#18 setup-node 4.4.0 → 7.0.0](https://github.com/udayvarmora07/skills-manager/pull/18) | `820762786026740c76f36085b0efc47a31fe5020`; browser syntax step in `ci.yml` | [Run 35085439962](https://github.com/udayvarmora07/skills-manager/actions/runs/35085439962): Python 3.10 and 3.11 unit jobs failed; downstream jobs skipped | **Request changes** |
| [#19 attest-build-provenance → v2.4.0](https://github.com/udayvarmora07/skills-manager/pull/19) | `e8998f949152b193b063cb0ec769d69d929409be`; release attestation step only | [Run 35085441318](https://github.com/udayvarmora07/skills-manager/actions/runs/35085441318): Python 3.10 and 3.11 unit jobs failed; downstream jobs skipped | **Request changes** |

The workflow file changes are action-reference updates. None changes the release trigger, tag/package-version gate, build-once artifact upload/download, TestPyPI stage, PyPI Trusted Publishing permissions, attestation subject path, GitHub Release asset path, or read-only post-publish verification job.

## Compatibility and contract findings

### Runtime transition

**[SPEC]** GitHub's [Node 20 runner notice](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/) sets 2026-09-23 as the date Node 20 is removed. The listed action commits for #15–#18 declare `runs.using: node24`. The workflows use GitHub-hosted `ubuntu-latest`, `macos-latest`, and `windows-latest` runners; the latest observed runner log reports version `2.337.0`. The four updates therefore move these uses onto the current supported JavaScript runtime.

### Per-action review

| PR | Upstream and local-contract result |
|---|---|
| #15 | The [v7.0.0 notes](https://github.com/actions/setup-python/releases/tag/v7.0.0) include an ESM/runtime migration and remove the `pip-install` input. This repository does not pass that input; its `python-version` input remains available and no action outputs are consumed. The patch changes the SHA but leaves adjacent workflow comments at `v5`. `test_sec14_every_first_party_action_is_pinned` also still expects the old reviewed SHA, so the contract test must be updated alongside a fresh review. |
| #16 | The [v7.0.1 notes](https://github.com/actions/checkout/releases/tag/v7.0.1) describe safe handling of the default unsafe-PR-check input plus branch and shell escaping fixes. Workflow calls use defaults only, run on `pull_request` rather than `pull_request_target`, and have `contents: read`; no checkout outputs are consumed. The diff leaves comments at `v4`, and the exact-pin contract test still expects the old SHA. |
| #17 | The [v3.0.3 notes](https://github.com/softprops/action-gh-release/releases/tag/v3.0.3) describe dependency maintenance and safer classification of malformed GitHub API errors. The workflow still passes `files: dist/*`, uses the same `contents: write` release job, and consumes no outputs. The new Node 24 runtime suits the hosted runner. The adjacent comment still says `v2.3.3`, which mislabels the v3.0.3 commit. |
| #18 | The [v7.0.0 notes](https://github.com/actions/setup-node/releases/tag/v7.0.0) include an ESM/runtime migration and add cache outputs. This workflow supplies only `node-version: "22"`, does not configure caching, and consumes no outputs. The adjacent comment still says `v4`. **Superseded 2026-10-06:** the head's only failing job is `browser smoke and frontend syntax`, and the cause is the branch's missing `Tighten the Node tool cache permissions` step, not the ESM migration — see the re-verification above. |
| #19 | The proposed commit is [v2.4.0](https://github.com/actions/attest-build-provenance/releases/tag/v2.4.0), not a v3 update. It retains `subject-path: "dist/*"` and the existing `id-token: write` and `attestations: write` job permissions; its new run-summary file behavior does not alter the subject artifact. However, its nested `actions/attest@v2.4.0` declares `runs.using: node20`. It does not meet the 2026-09-23 Node 20 removal boundary. Request a Node 24 compatible replacement (the upstream [v4 release line](https://github.com/actions/attest-build-provenance/releases) is a wrapper around `actions/attest`) and review that exact full SHA and unchanged artifact/permission contract. |

The Dependabot patches keep full commit SHAs, but the adjacent version comments are stale for #15–#18; #19's comment does not identify the v2.4.0 commit or its review date. Update each comment only after reviewing its exact commit.

## CI interpretation

**[NOTE]** #15's run fails `test_sec14_every_first_party_action_is_pinned` because its test baseline still expects setup-python SHA `a26af69be951a213d495a4c3e4e4022e16d87065`, while the PR uses `5fda3b95...`. The newer #16 run has the equivalent mismatch for checkout (`11d5960...` expected, `3d3c42e...` proposed). In both, Python 3.10 and 3.11 also fail `test_remove_purge_never_advertises_a_destroyed_skill` with a surviving `demo` row.

The latest observed `main` run at the time of the original review, [35773770784](https://github.com/udayvarmora07/skills-manager/actions/runs/35773770784), also fails that purge test on Python 3.10 and 3.11 while the other three matrix versions pass. **Resolved 2026-10-04:** the purge test asserted one of two correct branches of `_purge_skill` and was replaced with the invariant (finding A1); `main` is green on all 15 jobs as of run [37311664410](https://github.com/udayvarmora07/skills-manager/actions/runs/37311664410). The #17–#19 runs are still from 2026-09-16 and still need fresh CI on the current tree.

## Dispositions and revisit conditions

**[SPEC]** No PR was merged, rebased, commented on, or reviewed through GitHub. The local recommendations are:

- **#15 — Request changes.** Rebase on current `main`, update the SHA contract test and version/date comments, then require green full CI. The `EXPECTED_FIRST_PARTY_SHAS` mismatch below is a real, currently-detected failure; the five unit jobs fail because that mismatch propagates, and no other reason has been established.
- **#16 — Request changes.** Rebase, update the SHA contract test and version/date comments, and require green full CI. Same as #15 — a real, currently-detected pin-contract failure.
- **#17 — Request changes.** Rebase, correct the v3.0.3 comment to the reviewed release, then rerun CI on current `main`; the workflow input and release permissions remain compatible by source review. Note that before `b50ca1e` this PR's step was invisible to the pin gate, so its pin was never machine-enforced.
- **#18 — Request changes, for a corrected reason.** **Rebase first**: the branch predates the `Tighten the Node tool cache permissions` step and its only failing job is that missing step's `RuntimeError`, not the proposed bump. Once rebased, correct the v7.0.0 comment and require green current-tree CI before the ESM migration is actually exercised. The only configured Node version remains 22.
- **#19 — Request changes.** Replace the Node 20 based v2.4.0 ref with an explicitly reviewed Node 24 compatible ref, correct its version/date comment, and verify attestations over the exact `dist/*` files with the existing permissions. Note that before `b50ca1e` this step was invisible to **both** gates, so the release attestation's pin was never machine-enforced — a repin to a floating tag or to 40 zeros left the suite green.

**[SPEC] What stands unchanged.** All five recommendations remain *request
changes*. What changed is that three of the five reasons are now different from
what was originally recorded: #17, #18 and #19 need a rebase and, for #19, a
different action version — none of which was the original reason. #15 and #16
retain their original reason.

**[NOTE]** Revisit each after its PR head is current, the action pin comments and source-contract expectations match the reviewed commit, and every required CI job is green. Any resulting workflow edits need individual review against the build-once and post-publish release contract before integration.
