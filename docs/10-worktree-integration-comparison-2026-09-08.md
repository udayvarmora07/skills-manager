# Worktree Integration Comparison — Skills Manager

**Version:** 1.0.0
**Comparison date:** 2026-09-08 local / 2026-09-07 UTC
**Repository:** `/home/uday-varmora/skills-manager`
**Comparison base:** `main` at `667fabb7ddb41fcd0db6fb9a58128665bba0190c`

**AI manifest:** This document completes Milestone 0 task 3 from `TODO.md`.
It compares the two unmerged candidate worktrees file-by-file against current
`main`, classifies their changes, records test evidence, identifies overlap and
conflict risk, and defines a safe replay order. It does not merge or modify any
candidate worktree.

## 1. Executive decision

Do **not** merge either candidate branch wholesale.

The correct integration strategy is:

```text
current main
  → replay adversarial regression tests
  → fix P0 filesystem/parser/search defects centrally
  → add localhost request-security tests and fix the web boundary
  → replay approved snapshot/migration behavior selectively
  → reconcile archive implementation and security policy
  → add ZIP/link/UX work only after the safety gates
  → reconcile docs and run full verification
```

The security replay sequence is specifically responsible for the five confirmed
current-main findings: `P0-SEC-001`, `P0-SEC-002`, `P0-SEC-003`, `P0-SEC-004`,
and `P0-SEC-005`.

The two candidate branches represent different workstreams:

| Candidate | Head | Primary purpose | Recommendation |
|---|---|---|---|
| `agents/todo-plan-implementation` | `2bb72800c137548934b9ee76b136551c3892d95c` | Approved snapshots/full migration, then adversarial hardening | **Primary security/recovery source**, selectively replay |
| `agents/milestone5-research-user-needs` | `c5a7161f4832d4240f14b19098ea2aeb0be18b3a` | ZIP import, stricter link validation, preview, shortcut help, launcher | **Secondary feature source**, defer until safety integration |

## 2. Candidate verification evidence

### `agents/todo-plan-implementation`

- Commits ahead of `main`:
  - `bf6ab2e` — rollback snapshots + full-library migration.
  - `2bb7280` — adversarial security hardening.
- Changed files versus `main`: **22**.
- Diff size: **1,004 insertions, 59 deletions**.
- `git diff --check`: PASS.
- Unit tests: **74 PASS**.
- `smoke_store.py`: PASS.
- `smoke_web.py`: PASS.
- No tracked `__pycache__`, `dist/`, `build/`, or `*.egg-info` additions.

### `agents/milestone5-research-user-needs`

- Commit ahead of `main`:
  - `c5a7161` — research-backed Milestone 5 features and exhaustive testing.
- Changed files versus `main`: **17**.
- Diff size: **445 insertions, 42 deletions**.
- `git diff --check`: PASS.
- Unit tests: **55 PASS**.
- `smoke_store.py`: PASS.
- `smoke_web.py`: PASS.
- Emits a Python tarfile deprecation warning during tests because its fallback
  path does not fully align with the current interpreter’s extraction behavior.
- No tracked `__pycache__`, `dist/`, `build/`, or `*.egg-info` additions.

Passing branch tests prove internal branch consistency; they do not prove that
either branch is safe to merge onto the current working tree. Both were tested
against their own source and their own documentation state.

## 3. File-by-file classification

### 3.1 Files changed by both candidate branches — manual reconciliation required

There are 13 overlapping files. These 13 files overlap and must not be
cherry-picked from both branches without
manual conflict review:

| File | `todo-plan-implementation` | `milestone5-research-user-needs` | Integration decision |
|---|---|---|---|
| `CHANGELOG.md` | Snapshot/migration entries | ZIP/UX/launcher entries | Rebuild one current Unreleased section after code lands |
| `ROADMAP.md` | Marks snapshots/migration shipped | Marks ZIP/link/preview/shortcut work shipped | Do not copy either status wholesale; derive from `main` integration |
| `TODO.md` | Old checklist states approved work as done | Separate old checklist states Milestone 5 work as done | Preserve current world-class TODO and update only verified `main` items |
| `docs/03-cli-surface.md` | `--full`, snapshot flags, history changes | ZIP import surface | Update after final CLI behavior is chosen |
| `docs/06-progress-log.md` | Recovery/security history | Milestone 5 feature history | Append a new integration entry; retain history, correct stale current claims |
| `skillsmgr/cli.py` | Full migration and snapshot flags | Small ZIP/help adjustments | Replay security-compatible CLI changes first; manually reapply final flags |
| `skillsmgr/store.py` | Snapshots, full migration, name guards, wildcard and parser-adjacent changes | ZIP extraction and guarded tar fallback | **Highest-risk conflict. Design one archive pipeline; do not combine by text merge.** |
| `skillsmgr/webapp.py` | Snapshot/full import-export routes | ZIP filename acceptance | Reapply request-security gate first, then final archive route behavior |
| `skillsmgr/webui/app.js` | Snapshot/history/rollback and migration controls | Preview/shortcut controls | Integrate only after API contracts stabilize; test each feature independently |
| `skillsmgr/webui/index.html` | Snapshot/import/export UI | Preview/shortcut UI | Manual UI composition required |
| `smoke_web.py` | Snapshot/full migration endpoint tests | ZIP import tests | Merge test scenarios only after final endpoint/archive contract exists |
| `task.md` | Recovery/security milestone edits | Milestone 5 edits | Append current facts; never copy branch checklist wholesale |
| `tests/test_store.py` | Snapshot and full migration tests | ZIP/link/archive tests | Replay tests in dependency order and adapt fixtures to the final pipeline |

### 3.2 Files unique to `agents/todo-plan-implementation`

| File | Change class | Decision |
|---|---|---|
| `docs/02-modules.md` | Documents snapshot/security helpers | Reapply after final code; do not copy stale line references |
| `docs/04-store-api.md` | Documents new snapshot/full behavior | Reconcile with unchanged schema constraint and final public signatures |
| `docs/08-web-ui.md` | Documents rollback/migration UI | Reapply after final REST contract |
| `skillsmgr/frontmatter.py` | Converts deep parser `RecursionError` to `FrontmatterError` | Replay as a minimal P0 fix, then add explicit bounds later |
| `skillsmgr/scopes.py` | Adds shared mutation name validation and snapshot scope helpers | Replay name/root guards first; review snapshot API separately |
| `skillsmgr/search.py` | Caps wildcard complexity | Replay security behavior, then decide whether to replace regex with a deterministic matcher |
| `smoke_store.py` | Snapshot/full migration smoke coverage | Replay after Store contract is final |
| `tests/test_adversarial.py` | 19 adversarial regression tests | **Highest-value test artifact; add early before fixes** |
| `tests/test_web_scopes.py` | Snapshot scope tests | Add after snapshot design is selected |

### 3.3 Files unique to `agents/milestone5-research-user-needs`

| File | Change class | Decision |
|---|---|---|
| `README.md` | ZIP, launcher, preview/shortcut claims | Reapply only after behavior is shipped on `main` |
| `assets/skills-manager.desktop` | Desktop launcher | Defer; independent and not needed for P0 safety |
| `skillsmgr/validator.py` | Out-of-root links become errors | Requires policy decision; keep separate from P0 replay until approved |
| `skillsmgr/webui/styles.css` | Preview/shortcut UI styling | Defer until browser/a11y phase |

## 4. Workstream-level comparison

### 4.1 Security and adversarial hardening

The `todo-plan-implementation` branch contains the stronger security foundation:

- centralized `check_skill_name` usage across Store/scope mutation paths;
- archive name gates for manifest and manifestless imports;
- wildcard complexity cap;
- parser recursion error conversion;
- snapshot-scope validation;
- 19 adversarial regression tests.

This directly addresses the five current-main P0 reproductions. It should be
replayed before any feature branch code.

Important limitation: the branch’s `check_skill_name` is primarily a path-escape
guard and intentionally permits some unusual contained names. The integration
must still separately enforce the Agent Skills canonical name contract at
creation/import boundaries and independently verify resolved-root containment.

### 4.2 Rollback snapshots

The `todo-plan-implementation` branch adds:

- filesystem snapshots under `<data>/snapshots/<scope>/<name>/`;
- newest-five retention;
- snapshot restore behavior;
- snapshot history/UI endpoints;
- scope-aware snapshot handling for agent operations;
- snapshot tests for edit/sync and retention.

This work is approved by issue #1 but depends on safe names, safe scopes, and
atomic writes. Replay it only after the P0 path guards are on `main`. Snapshot
writes also need a final atomic-write review; the branch implementation should
not be assumed crash-safe merely because it is tested in ordinary execution.

### 4.3 Full-library migration

The `todo-plan-implementation` branch adds approved `--full` behavior for
existing export/import/backup surfaces:

- skills;
- trash;
- templates;
- versioned manifest;
- skip-by-default behavior;
- explicit force overwrite;
- full import/export smoke tests.

It intentionally does not include agent scopes or snapshots according to issue
#2’s approved scope. This is the preferred starting point for migration, but its
archive format must be routed through the final hardened archive pipeline.

### 4.4 ZIP import and tar fallback

The `milestone5-research-user-needs` branch adds:

- content-based ZIP detection;
- guarded ZIP extraction;
- guarded tar fallback for interpreters without `filter=`;
- GitHub-style archive layout handling;
- manifestless `skills/` scanning;
- tests for traversal and link behavior.

This overlaps directly with the migration/archive code in the other branch and
must be treated as an implementation design input, not a drop-in patch. The
final archive pipeline should have one preflight/validation/commit path for tar
and ZIP, with explicit member limits and no unsafe fallback.

The branch’s own test warning confirms this area needs review: current Python
tarfile behavior emits a deprecation warning for the fallback path. Do not merge
that behavior without deciding the supported-Python and feature-detection policy.

### 4.5 Link validation policy

The Milestone 5 branch changes out-of-root links from warning to error. This is
an approved-pending policy proposal (issue #7), not an unconditional integration
item. It can create false positives for project-relative or intentionally
external layouts. Keep it isolated until the maintainer decides strictness and
an allowlist/exception model.

### 4.6 Frontend preview and shortcuts

The Milestone 5 branch adds:

- Write/Preview tabs for Markdown editing;
- shortcut cheatsheet modal;
- `?` keyboard behavior;
- associated CSS and HTML.

The code is frontend-only and conceptually low risk, but it belongs after the
browser verification and accessibility phase. The current UI already needs a
formal modal focus/inertness/restore test strategy, so this work should not be
replayed before that foundation.

## 5. Conflict map

### Highest-risk conflict: `skillsmgr/store.py`

Both branches independently modify the archive import path. One branch also
adds snapshots, migration, name guards, and shared helpers. A textual merge can
silently reintroduce:

- invalid manifestless names;
- unsafe tar fallback;
- archive traversal;
- partial full-migration state;
- snapshot path traversal;
- inconsistent `--force` behavior.

**Resolution:** design and implement one archive intake pipeline after the P0
tests are added. Port behavior through tests, not by accepting a combined diff.

### Medium-risk conflicts

- `skillsmgr/cli.py`: snapshot/full flags versus ZIP/help changes.
- `skillsmgr/webapp.py`: migration/snapshot endpoints versus ZIP acceptance.
- `skillsmgr/webui/app.js` and `index.html`: rollback controls versus preview/
  shortcut controls.
- `tests/test_store.py` and `smoke_web.py`: overlapping archive fixtures and
  expected response shapes.
- `TODO.md`, `task.md`, `ROADMAP.md`, and `docs/06-progress-log.md`: both
  branches record their own work as shipped relative to their branch, not
  current `main`.

### Low-risk but still manual

- `CHANGELOG.md`: combine only after final behavior lands.
- `README.md`: update only after final install/import/UI behavior is verified.
- `assets/skills-manager.desktop`: independent, can be deferred.
- `skillsmgr/webui/styles.css`: defer with preview/shortcut UI.

## 6. Safe replay map

### Replay group A — tests first

Source: `agents/todo-plan-implementation`.

- Add `tests/test_adversarial.py`.
- Port any required fixture helpers into current test conventions.
- Add the relevant P0 tests from the branch’s expanded Store tests.
- Run them against current `main` and preserve the expected failures.

Do not add branch implementation code in this group.

### Replay group B — P0 implementation fixes

Implement or selectively port, in this order:

1. Canonical skill-name validation plus root containment for every mutation.
2. Manifest and manifestless archive name validation.
3. Bounded wildcard behavior.
4. Frontmatter recursion/resource bounds.
5. Localhost request-origin/Host security, which is not fixed by either
   candidate branch and must be implemented separately.

After each item, run its focused tests, then all current tests and smokes.

### Replay group C — approved recovery

Source: `agents/todo-plan-implementation`, commit `bf6ab2e`.

- Snapshot tests and implementation, after name/root guards.
- Full migration tests and implementation, after the final archive pipeline.
- CLI/REST/UI changes only after Store contracts are stable.

### Replay group D — archive capability decision

Use the Milestone 5 ZIP/tar work as design input. Before implementation:

- decide ZIP support under issue #5;
- decide Python <3.12 behavior under issue #6;
- define member limits and symlink/hardlink policy;
- define manifestless layout policy;
- test one shared archive preflight/commit pipeline.

### Replay group E — frontend features

After API/security/browser foundations:

- Markdown preview;
- keyboard shortcut cheatsheet;
- associated UI styles;
- real-browser focus, keyboard, console, and responsive tests.

### Replay group F — documentation and release metadata

Only after verified behavior lands on `main`:

- owning module/API docs;
- `CHANGELOG.md`;
- `ROADMAP.md`;
- `README.md`;
- `task.md`;
- `docs/06-progress-log.md`.

## 7. Files that must not be cherry-picked wholesale

- `skillsmgr/store.py` from either branch.
- `TODO.md`, `task.md`, `ROADMAP.md`, or `docs/06-progress-log.md` from either
  branch.
- `smoke_web.py` until endpoint/archive contracts are finalized.
- `tests/test_store.py` until fixtures reflect the final archive and snapshot
  semantics.
- `skillsmgr/webapp.py` until request-security behavior is added separately.

## 8. Integration acceptance criteria

- [x] Both candidate worktrees were compared file-by-file against `main`.
- [x] Candidate heads, commits, changed-file counts, diff sizes, and tests were
  recorded.
- [x] Overlap files were enumerated.
- [x] Security, recovery, archive, UX, docs, and test changes were classified.
- [x] Conflict risks and a safe replay sequence were documented.
- [x] No candidate worktree was modified.
- [x] No current-`main` product source or tests were modified by this comparison.
- [ ] The next task is to add the five P0 regression tests to the implementation
  branch and begin P0-SEC-001 hardening.

## 9. Final recommendation

Treat `agents/todo-plan-implementation` as the primary source for security
regression tests and approved recovery behavior, but replay it in separate
groups. Treat `agents/milestone5-research-user-needs` as a secondary research
and feature source. Do not merge the two `store.py` versions. Build one final
archive pipeline after the P0 tests and localhost security gate exist.