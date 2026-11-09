# Worktree and Branch Cleanup — 2026-11-09

**Version 1.0.0**

**AI manifest**: Evidence and preservation rules for the maintainer-authorized
cleanup of branches and worktrees already integrated into main. Read before
recovering an archived checkout or deleting remaining work.

## Authorization and baseline

**[SPEC]** The maintainer requested an in-depth review and double-check before
removing already-merged branches or worktrees. Remove only exact commit
ancestors of fetched `origin/main`; preserve dirty, active and unmerged work.
Superseded or patch-equivalent work is not treated as merged ancestry.

**[NOTE]** Baseline `origin/main` is `7bc7598`. Inventory: 27 local branches,
23 registered worktrees (21 existing and 2 missing temporary directories),
10 actual remote branch heads. Two Terra reviewers independently checked
ancestry, ignored files and residual work. No product code changes are needed.

## Checks before removal

- Prove `merge-base --is-ancestor HEAD origin/main` and zero unique commits.
- Check tracked, staged, untracked and ignored files, submodules, lock flags,
  worktree identity and the shared Git directory.
- Inspect visible process working directories and open file handles; preserve
  in-use worktrees. These are point-in-time checks, not a concurrency guarantee.
- Back up all Git refs in a verified bundle; archive complete candidate trees
  including ignored release/build files, bytecode and caches, plus per-worktree
  Git administration records. Verify file bytes and link targets from archives.
- Recheck each candidate immediately before ordinary `git worktree remove`;
  never force a refusal. Delete only unchanged local branch tips with
  `git branch -d` after their checked-out worktrees have been removed.
- For remote cleanup, preserve main, unmerged heads and open-PR sources.
  Protect each deletion with its audited expected SHA, so a branch advanced by
  another writer cannot be deleted. Never rewrite main.

## Preservation decisions

- The primary checkout on `feat/v2-feature-parity` has 47 tracked/untracked
  changes. Preserve it and verify its file hashes after cleanup.
- `redesign/ui-v2` contains 142 commits absent from main. Keep the branch and
  overnight-ui worktree, including its ignored research/test evidence.
- `backup/pre-message-rewrite` has 29 commits absent from main. Their patches
  are represented in redesign, but neither history is merged into main; keep it.
- `remaining-tasks-2528a4` is merged but a live shell holds its directory; keep
  its checkout and branch.
- `untangle-codebase-48bb34` holds main and live processes; keep it.
- `v2-remaining-features-design-d432e3` contains an untracked launch file; keep
  its checkout and branch.
- Historical research and Dependabot heads absent from main's ancestry remain
  intact even where newer changes supersede them. This is merged-only cleanup.

## Recovery and results

**[NOTE]** Private recovery directory:
`/home/uday-varmora/skillsmgr-cleanup-audit-d9orltgn`. `before.json`,
`remote-before.json`, `all-refs.txt` and `plan.json` record the pre-cleanup state.
`repository-before.bundle` passed `git bundle verify` before any deletion.
Candidate checkout archives and byte manifests are created and verified there
before removal. Recovery uses that bundle or an archive; do not overwrite an
existing checkout when recovering files.

**[NOTE]** Completed cleanup:

| Item | Before | Removed | Remaining |
|---|---|---|---|
| Existing registered worktrees | 21 | 16 | 5 |
| Missing temporary registrations | 2 | 2 | 0 |
| Local branches | 27 | 21 | 6 |
| Actual remote branch heads | 10 | 5 | 5 |

**[NOTE]** Three additional stale remote-tracking refs were pruned by fetch;
the corresponding remote branches were already absent before this cleanup.
No unmerged remote branch was deleted. No force worktree removal, force local
branch deletion, reset, deletion of unarchived local content or rewrite of main
was used. A documentation-only cleanup receipt follows on main.

### Removed checkouts and branches


The following inactive worktrees were byte-archived, rechecked and removed:

- `/home/uday-varmora/.codex-placementcell/worktrees/758b/skills-manager` at `781c1ed`.
- `/home/uday-varmora/.codex-placementcell/worktrees/ef42/skills-manager` at `d00cb78`.
- `/home/uday-varmora/.codex-udayvarmora007/worktrees/f1ed/skills-manager` at `3b05ae6`.
- `/home/uday-varmora/skills-manager.c4-one-document-invariant` at `cf40958`.
- `/home/uday-varmora/skills-manager.d1-lazy-observations` at `21b755c`.
- `/home/uday-varmora/skills-manager.d1-scope-observations` at `0eddcbd`.
- `/home/uday-varmora/skills-manager.docs-context-budget` at `911ca48`.
- `/home/uday-varmora/skills-manager.g8-ui-structure` at `6f72f0d`.
- `/home/uday-varmora/skills-manager.release-102-artifacts` at `522b81f`.
- `/home/uday-varmora/skills-manager.ui-dark-panes` at `2c3c124`.
- `/home/uday-varmora/skills-manager.ui-final` at `b97c742`.
- `/home/uday-varmora/skills-manager/.claude/worktrees/continue-remaining-tasks-13a380` at `f323f16`.
- `/home/uday-varmora/skills-manager/.claude/worktrees/project-perf-ux-review-4da40d` at `68e50f0`.
- `/home/uday-varmora/skills-manager/.claude/worktrees/project-tasks-research-status-85664d` at `c268c8b`.
- `/home/uday-varmora/skills-manager/.claude/worktrees/remaining-tasks-execution-c6adba` at `a4eb440`.
- `/home/uday-varmora/skills-manager/.claude/worktrees/research-roadmap-c0a574` at `fbe8ec2`.

**[NOTE]** The three Codex-managed checkout candidates had no active attachment
in the current task host and no visible working-directory or open-file handles.
They were clean exact ancestors, with no hidden index flags, pending Git
operation or submodule. Their complete archives also retain Git administration
metadata. The maintainer's explicit cleanup request covered these candidates.

Local branch refs removed with unchanged tips and `git branch -d`:

- `agents/complete-todo-plan-implementation` at `667fabb`.
- `agents/fix-bugs-in-frontend-test-report` at `667fabb`.
- `agents/frontend-comprehensive-testing-bug-fix` at `667fabb`.
- `c4-one-document-invariant` at `cf40958`.
- `claude/continue-remaining-tasks-13a380` at `f323f16`.
- `claude/project-perf-ux-review-4da40d` at `68e50f0`.
- `claude/project-tasks-research-status-85664d` at `c268c8b`.
- `claude/remaining-tasks-execution-c6adba` at `a4eb440`.
- `claude/research-roadmap-c0a574` at `fbe8ec2`.
- `claude/untangle-codebase-48bb34` at `e4e100b`.
- `codex/fix-tar-metadata-ci` at `d00cb78`.
- `codex/next-five-task-execution-2026-09-23` at `6733da9`.
- `d1-lazy-observations` at `21b755c`.
- `d1-scope-observations` at `0eddcbd`.
- `design/2026-10-15` at `781c1ed`.
- `docs-context-budget` at `911ca48`.
- `g8-ui-structure` at `6f72f0d`.
- `redesign/2026-10-15` at `bcf5e57`.
- `release-102-artifacts` at `522b81f`.
- `ui-dark-panes` at `2c3c124`.
- `ui/prototype-final` at `b97c742`.

Remote branch heads removed atomically with exact expected-SHA checks, after
confirming there were no open pull requests:

- `claude/project-tasks-research-status-85664d` at `c268c8b`.
- `claude/research-roadmap-c0a574` at `fbe8ec2`.
- `design/2026-10-15` at `781c1ed`.
- `redesign/2026-10-15` at `bcf5e57`.
- `ui/prototype-final` at `b97c742`.

**[NOTE]** Missing temporary registrations `headcheck` and `before` were pruned
only after both the complete prunable set and every dry-run administration
entry matched the audited paths. Independent review caught an earlier guard
that checked only absent directories; it was strengthened before execution.

### Retained work

| Worktree or branch | Reason |
|---|---|
| Primary `feat/v2-feature-parity` | 47 tracked/untracked file versions preserved byte-for-byte; commits merged, but checkout has local residue |
| `redesign/ui-v2` and overnight-ui worktree | 142 commits absent from main; alternate UI and test work retained |
| `backup/pre-message-rewrite` | 29 commits absent from main; all have patch equivalents in redesign, which is itself unmerged |
| `claude/remaining-tasks-2528a4` | Merged but held by a live shell; retained with its checkout |
| `claude/v2-remaining-features-design-d432e3` | Merged history, untracked `.claude/launch.json`; retained with its checkout |
| `main` in untangle-codebase worktree | Main checkout and visible live processes; retained |
| Remote historical research and two closed Dependabot heads | Their commit histories are not ancestors of main; superseded does not mean merged |

**[NOTE]** Future selective review may inspect old redesign tests for editor
navigation, loading state and semantic Trash lists. Main already has its own
related implementations, so commit titles do not establish missing behavior.
No old redesign code was ported or merged as part of cleanup.

### Verification and recovery evidence

**[NOTE]** Checks completed before and after removal:

- All candidate tips are exact ancestors of `7bc7598` with zero unique commits.
- Complete candidate file bytes/link targets and permissions were checked
  against their archives. Immediate rechecks also covered identity, clean
  status, hidden index flags, lock/pending-operation markers and live handles.
- The all-ref bundle was verified. An additional reflog-inclusive bundle
  preserves 19 commits reachable only through reflogs. Independent unbundling
  into `recovery-proof.git` confirmed all 43 distinct branch/reflog tip objects.
- Final local refs and checkout paths exactly match the protected set; all
  retained branch tips and unmerged remote heads match their initial values.
- All 47 primary-checkout file hashes still match, and its branch stays
  `feat/v2-feature-parity`. `.autogit` was not modified.
- Repository connectivity (`git fsck --connectivity-only --no-dangling`),
  documentation consistency and 18 documentation regression cases pass.
  The current main source suite passes 1,765 tests with 2 optional oracle skips;
  product source is unchanged by this cleanup.

**[NOTE]** Recovery directory contents include `repository-with-reflogs.bundle`,
`worktree-backups/*.tar.gz`, `manifests/*.json`, `backed-up-plan.json`,
`cleanup-results.json`, `deleted-remote-branches.json`, `after-local.json`,
remote push receipts, preservation hashes and test logs. The sixteen archives
retain approximately 683 MB of compressed source, local artifacts and metadata;
keep the recovery directory private. A separate bare restore proved the bundle
contains the recorded objects. Archive restore should target a separate empty
recovery directory, never overwrite a retained checkout.

**[NOTE]** This verifies local Git/filesystem state at cleanup time. Visible
process/handle checks cannot prevent a session resuming later; live worktrees
were therefore retained. No claim is made that unmerged branch patches are
safe to merge. Backups were retained and no Git garbage collection was run.
