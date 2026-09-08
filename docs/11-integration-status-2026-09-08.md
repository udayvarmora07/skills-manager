# Integration Status — Skills Manager

**Version 1.0.0**

**AI manifest:** Current-state record for the first ten executable tasks and the
next-five archive/trash safety slice from `TODO.md`. This is a selective replay
map for `main`; it does not approve a wholesale merge of either unmerged
worktree.

## 1. Selective replay map

| Workstream | Source | Status on current `main` | Replay rule |
|---|---|---|---|
| Baseline/P0 evidence | `docs/09-baseline-evidence-2026-09-07.md` | `main` | Keep as measured evidence; do not rewrite historical observations. |
| Worktree comparison | `docs/10-worktree-integration-comparison-2026-09-08.md` | `main` | Use its order, but manually replay tests and fixes. |
| Adversarial regression tests | `agents/todo-plan-implementation` | `worktree-only` except independently reproduced tests | Port one seam at a time; never cherry-pick the branch wholesale. |
| Snapshot/full migration | current working tree | `main` candidate, selectively integrated and locally verified | Current code uses the P0 path guards and the hardened tar/resource/manifest pipeline; candidate worktree remains reference-only. |
| ZIP/archive UX | `agents/milestone5-research-user-needs` | `worktree-only` | Defer until the shared archive safety pipeline and approval gates exist. |
| Current path-safety slice | current working tree | `main` candidate, locally verified | Canonical name/root guards, CLI validation, decoded REST validation, and regression tests only. |
| Documentation/checklist controls | current working tree | `main` candidate, locally verified | Record current truth; do not mark later P0, recovery, UX, or release work shipped. |

### Safe replay order

```text
baseline evidence
  → adversarial tests
  → canonical name/root guards
  → Store and scope enforcement
  → decoded REST and pre-handler CLI validation
  → localhost request-security gate
  → recovery/atomicity
  → archive policy and limits
  → UX/accessibility
  → release/package verification
```

## 2. First-ten task status

| # | Task | Status | Evidence |
|---:|---|---|---|
| 1 | Build the cherry-pick/replay map | `main` | This document and `docs/10-worktree-integration-comparison-2026-09-08.md`. |
| 2 | Classify work as `main`, `worktree-only`, `approved-not-integrated`, or `speculative` | `main` | Classification table above; candidate branches remain unmerged. |
| 3 | Add a pre-merge checklist | `main` | `docs/PRE-MERGE-CHECKLIST.md`. |
| 4 | Decide whether `dist/` and `skills_manager.egg-info/` are artifacts or release inputs | `main` | They are ignored, untracked local artifacts; see section 3. |
| 5 | Add one authoritative skill-name validation primitive | `main` | `skillsmgr/validator.py:validate_skill_name`; unit coverage in `tests/test_path_safety.py`. |
| 6 | Add one resolved-path root-containment primitive | `main` | `skillsmgr/paths.py:contained_path` and `safe_skill_path`; symlink, absolute, and parent tests. |
| 7 | Apply guards before current filesystem reads/writes/moves/copies/restores/deletes | `main` | Store, scope, trash, import, export, sync, and snapshot paths use shared helpers. |
| 8 | Apply guards to Store and agent-scope equivalents | `main` | Store CRUD/toggle/restore/import/export and scope get/raw/create/edit/remove/toggle/sync paths are covered. |
| 9 | Validate URL-decoded REST path parameters before path joins | `main` | `webapp.py` decodes segments after splitting; guarded Store/scope reads and mutations return HTTP 400 for encoded traversal and preserve the victim. |
| 10 | Validate CLI names before command handlers construct paths | `main` | `cli.main()` rejects invalid names before `_make_store`; regression confirms no database is created. |

## 3. Packaging artifact decision

`dist/` and `skills_manager.egg-info/` are **local build/metadata artifacts**,
not source-controlled release inputs. `.gitignore` excludes both, and neither
path is tracked by Git in this checkout. Existing files under `dist/` are useful
for inspection only; a release must build a fresh artifact in a clean tree,
test that exact artifact, and publish it unchanged. The package-build gap remains
open because `python3 -m build` is unavailable in the baseline environment.

## 4. Historical non-goals for the initial path-safety slice

- The initial path-safety slice added no new CLI command, CLI flag, Store method,
  SQLite table, or schema version. The later recovery slice selectively added
  the approved `--full`/`--snapshot` flags and module-level snapshot helpers;
  the SQLite schema remains unchanged.
- No localhost Origin/Host/Fetch-Metadata security implementation.
- No archive member count/size/compression-ratio limits, ZIP support, parser
  limits, or wildcard matcher redesign. The archive preflight pipeline is
  included in the next-five slice below.
- No candidate-worktree snapshot/migration code was merged wholesale. Snapshot,
  full migration, UX, browser accessibility, and release work are tracked
  independently; snapshot/full migration behavior is now selectively integrated
  on current `main` and verified by current tests/smokes.
- No modification of `.autogit`.

## 5. Acceptance evidence

The path-safety slice was verified on **September 8, 2026** with:

```text
python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py   PASS
python3 -m unittest discover -s tests                       PASS (57 tests)
python3 smoke_store.py                                      PASS
python3 smoke_web.py                                        PASS
node --check skillsmgr/webui/app.js                         PASS
python3 -m skillsmgr --help                                 PASS
git diff --check                                            PASS
```

The raw global skill-read route also resolves through `Store.get()` before
opening a file. This closes the previously uncovered encoded-traversal read
seam; `tests.test_webapp.WebAppTestCase.test_encoded_skill_traversal_is_rejected_before_raw_read`
proves an outside `SKILL.md` is not disclosed.

## 6. Next-five archive/trash safety status

| # | Task | Status | Evidence |
|---:|---|---|---|
| 11 | Prevent invalid forced-import destinations | `main` | Canonical manifest-name validation and force regression preserve existing destinations. |
| 12 | Prevent unsafe/prefix-collision trash matching | `main` | Exact canonical timestamp parsing is shared by list, restore, purge, and doctor. |
| 13 | Preflight archives before mutation | `main` | Private temporary extraction plus planned imports completes before the first destination delete/copy. |
| 14 | Reject unsafe archive members/types/layouts | `main` | Absolute/traversal, duplicate, unexpected-layout, symlink, hard-link, FIFO, and special-member tests pass. |
| 15 | Feature-detect tar safe extraction | `main` | `tarfile.data_filter` path and guarded no-filter regular-file/directory fallback both pass. |

### Next-five acceptance evidence

```text
python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py   PASS
python3 -m unittest discover -s tests                       PASS (65 tests)
python3 smoke_store.py                                      PASS
python3 smoke_web.py                                        PASS
node --check skillsmgr/webui/app.js                         PASS
python3 -m skillsmgr --help                                 PASS
git diff --check                                            PASS
```

The following archive concerns remain intentionally open: member count/size/
compression-ratio limits, ZIP support, full manifest schema/version policy, and
transactional rollback after a destination filesystem failure.

The remaining P0 and release gaps stay open in `TODO.md` until their own
failing-first tests, implementation, owning documentation, and acceptance
checks are complete.