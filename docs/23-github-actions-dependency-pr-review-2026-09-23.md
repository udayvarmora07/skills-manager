# GitHub Actions Dependency PR Review — 2026-09-23

**Version 1.0.0**

**AI manifest**: Dated, read-only review of Dependabot PRs #15–#19 against the exact workflow uses, upstream action metadata, current CI evidence, and the release artifact contract. Recommendations are review guidance only; no GitHub review, comment, branch update, or merge was posted.

## Review snapshot

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
| #18 | The [v7.0.0 notes](https://github.com/actions/setup-node/releases/tag/v7.0.0) include an ESM/runtime migration and add cache outputs. This workflow supplies only `node-version: "22"`, does not configure caching, and consumes no outputs. The adjacent comment still says `v4`. |
| #19 | The proposed commit is [v2.4.0](https://github.com/actions/attest-build-provenance/releases/tag/v2.4.0), not a v3 update. It retains `subject-path: "dist/*"` and the existing `id-token: write` and `attestations: write` job permissions; its new run-summary file behavior does not alter the subject artifact. However, its nested `actions/attest@v2.4.0` declares `runs.using: node20`. It does not meet the 2026-09-23 Node 20 removal boundary. Request a Node 24 compatible replacement (the upstream [v4 release line](https://github.com/actions/attest-build-provenance/releases) is a wrapper around `actions/attest`) and review that exact full SHA and unchanged artifact/permission contract. |

The Dependabot patches keep full commit SHAs, but the adjacent version comments are stale for #15–#18; #19's comment does not identify the v2.4.0 commit or its review date. Update each comment only after reviewing its exact commit.

## CI interpretation

**[NOTE]** #15's run fails `test_sec14_every_first_party_action_is_pinned` because its test baseline still expects setup-python SHA `a26af69be951a213d495a4c3e4e4022e16d87065`, while the PR uses `5fda3b95...`. The newer #16 run has the equivalent mismatch for checkout (`11d5960...` expected, `3d3c42e...` proposed). In both, Python 3.10 and 3.11 also fail `test_remove_purge_never_advertises_a_destroyed_skill` with a surviving `demo` row.

The latest observed `main` run, [35773770784](https://github.com/udayvarmora07/skills-manager/actions/runs/35773770784), also fails that purge test on Python 3.10 and 3.11 while the other three matrix versions pass. The failure was not reproduced by the local Python 3.11.15 focused test or the Python 3.12 full suite (878 tests); its cause remains unresolved. This is baseline CI evidence, not evidence that an action update caused the failure. The #17–#19 runs are from 2026-09-16 and need fresh CI on the current tree after the baseline issue is resolved.

## Dispositions and revisit conditions

**[SPEC]** No PR was merged, rebased, commented on, or reviewed through GitHub. The local recommendations are:

- **#15 — Request changes.** Rebase on current `main`, update the SHA contract test and version/date comments, then require green full CI.
- **#16 — Request changes.** Rebase, update the SHA contract test and version/date comments, and require green full CI.
- **#17 — Request changes.** Correct the v3.0.3 comment to the reviewed release, then rerun CI on current `main`; the workflow input and release permissions remain compatible by source review.
- **#18 — Request changes.** Correct the v7.0.0 comment and require green current-tree CI. The only configured Node version remains 22.
- **#19 — Request changes.** Replace the Node 20 based v2.4.0 ref with an explicitly reviewed Node 24 compatible ref, correct its version/date comment, and verify attestations over the exact `dist/*` files with the existing permissions.

**[NOTE]** Revisit each after its PR head is current, the action pin comments and source-contract expectations match the reviewed commit, and every required CI job is green. Any resulting workflow edits need individual review against the build-once and post-publish release contract before integration.
