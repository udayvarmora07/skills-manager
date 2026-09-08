# Baseline and P0 Reproduction Evidence — Skills Manager

**Version:** 1.0.0
**Evidence date:** 2026-09-07 UTC
**Host clock observed:** 2026-09-08T00:53:07+0530
**Repository:** `/home/uday-varmora/skills-manager`
**Measured branch:** `main`
**Measured commit:** `667fabb7ddb41fcd0db6fb9a58128665bba0190c`

**AI manifest:** This document records the reproducible baseline and the exact
current-`main` behavior for the five release-blocking P0 findings in `TODO.md`.
It is evidence, not a fix report. Product source code was not changed during
evidence collection. All destructive probes used temporary directories; no live
user or agent skill directory was used.

## 1. Executed Milestone 0 tasks

1. Capture baseline command output before implementation changes.
2. Record exact current-`main` behavior for all five P0 reproductions before
   implementation changes.

The repository already contained approved changes to `TODO.md` and `PLAN.md`,
plus a pre-existing untracked `.autogit`. Those states were preserved and are
reported below rather than treated as product changes.

## 2. Repository and environment baseline

### Repository state

```text
UTC=2026-09-07T19:23:07Z
LOCAL=2026-09-08T00:53:07+0530
repo=/home/uday-varmora/skills-manager
commit=667fabb7ddb41fcd0db6fb9a58128665bba0190c
commit_date=2026-09-05T10:52:30+05:30
commit_subject=Close out v1.1 dedup+budget: record push, CI, issues #1 #2
```

Working-tree state before this evidence change:

```text
## main...origin/main
 M PLAN.md
 M TODO.md
?? .autogit
```

`PLAN.md` and `TODO.md` were the approved documentation changes from the prior
task. `.autogit` was not modified.

### Tool versions

```text
Python 3.12.3
Node v22.22.3
git version 2.43.0
gh version 2.97.0 (2026-07-31)
SQLite 3.50.6 2025-09-22
```

## 3. Baseline verification matrix

Commands were run from `/home/uday-varmora/skills-manager`. Python checks used
`PYTHONDONTWRITEBYTECODE=1` and a temporary `PYTHONPYCACHEPREFIX` so the
repository received no bytecode artifacts.

| Check | Command | Exit | Result |
|---|---|---:|---|
| Compile | `python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py` | 0 | PASS |
| Unit tests | `python3 -m unittest discover -s tests` | 0 | PASS; 47 tests |
| Store smoke | `python3 smoke_store.py` | 0 | PASS |
| Web smoke | `python3 smoke_web.py` | 0 | PASS |
| Frontend syntax | `node --check skillsmgr/webui/app.js` | 0 | PASS |
| CLI help | `python3 -m skillsmgr --help` | 0 | PASS |
| Package build | `python3 -m build --outdir <temporary-dir>` | 1 | BLOCKED: module unavailable |
| Diff whitespace | `git diff --check` | 0 | PASS before evidence edits |

### Captured successful outputs

```text
Ran 47 tests in 0.966s
OK

ALL STORE SMOKE TESTS PASSED

ALL WEB SMOKE TESTS PASSED
frontend_syntax=ok
```

### Package-build gap

The exact package-build command returned:

```text
/usr/bin/python3: No module named build
[exit=1]
```

Existing artifacts were present in `dist/` before this task:

```text
skills_manager-1.0.0-py3-none-any.whl 132577 bytes
skills_manager-1.0.0.tar.gz          130668 bytes
```

They were inspected as existing artifacts, not rebuilt. Their presence is not
evidence that a clean current checkout can build successfully. Packaging remains
open for Milestone 8.

## 4. P0 reproduction matrix

| ID | Reproduction | Current result | Expected after fix |
|---|---|---|---|
| P0-SEC-001 | `Store.remove("../../victim", purge=True)` in an isolated store | Deletes `victim` outside `skills/`; exit 0 | Reject before mutation; victim survives |
| P0-SEC-002 | Cross-origin `POST /api/trash/purge` with attacker `Origin` | HTTP 200; trash is purged | Reject before Store mutation |
| P0-SEC-003 | Archive contains `skills/weird name/SKILL.md` | Imports `weird name`; destination exists | Reject invalid name; no destination |
| P0-SEC-004 | Crafted `*a*...` wildcard query | Three-second probe exits 124 | Bounded fast rejection or bounded match |
| P0-SEC-005 | Deep block/flow frontmatter | Raw `RecursionError` | Clean bounded `FrontmatterError` |

## 5. Detailed P0 evidence

### P0-SEC-001 — mutation path traversal

`Store.remove` constructs a path from the supplied name without a canonical
name guard and root-containment check. The isolated probe created a victim at
`<temporary>/victim` while the Store skills root was
`<temporary>/manager/skills`.

```text
skills_root= /tmp/tmpb_6f9pll/manager/skills
victim_before= True
result= {'name': '../../victim', 'action': 'purged'}
victim_after= False
exit=0
```

**Impact:** a Store mutation caller can delete a directory outside the intended
skill tree. This is a direct user-data integrity failure.

### P0-SEC-002 — cross-origin localhost mutation

The server was started on `127.0.0.1` with an ephemeral port. A temporary skill
was moved to trash, then the following request was sent:

```text
POST /api/trash/purge
Origin: https://attacker.example
Content-Type: application/x-www-form-urlencoded
empty body
```

Observed result:

```text
status= 200
response= {"purged": ["demo"]}
trash_after= []
exit=0
```

**Impact:** a hostile website visited in the same browser can submit a
cross-origin request to the local server and cause irreversible trash deletion.
Loopback socket binding is not same-origin authorization.

### P0-SEC-003 — invalid manifestless archive name

The crafted tar archive contained:

```text
manifest.json: {"skills": []}
skills/weird name/SKILL.md
```

The document itself declared `name: weird name`. The fallback import path
accepted it:

```text
result= {'imported': ['weird name'], 'skipped': [],
         'source': 'invalid-name.tar.gz', 'created': '2026-09-07T19:23:16Z'}
invalid_dir_exists= True
exit=0
```

**Impact:** archive intake can create invalid and unportable skill state while
the normal create path enforces a stricter name contract.

### P0-SEC-004 — wildcard search exhaustion

`skillsmgr/search.py` translates each `*` into `.*`. The probe used a
200-character record name and a 201-character alternating wildcard pattern. The
matcher did not complete within three seconds:

```text
term_length= 201
starting_rank=
exit=124 (timeout killed the unbounded matcher)
```

**Impact:** a local CLI, UI, or API search caller can consume excessive CPU with
a crafted pattern.

### P0-SEC-005 — frontmatter recursion failure

Two malformed documents were tested: a 400-level nested block mapping and a
2,000-level nested flow collection.

```text
deep_block RecursionError maximum recursion depth exceeded
deep_flow RecursionError maximum recursion depth exceeded
exit=0
```

**Impact:** malformed input reaches an implementation-level exception instead of
the documented `FrontmatterError` contract and can consume excessive stack
resources.

## 6. Safety conclusions

1. The happy-path baseline is green but incomplete: 47 tests did not cover the
   five confirmed P0 classes.
2. P0-SEC-001 is the first implementation priority because it directly permits
   deletion outside the intended data root.
3. P0-SEC-002 must be fixed before treating the localhost UI as a safe desktop
   control plane.
4. Archive, parser, and search limits must be centralized so CLI, Store, REST,
   and UI cannot diverge.
5. The approved recovery worktree must be replayed only after these findings are
   converted into tests and fixed.
6. The package-build failure is an environment/release gap and remains open for
   Milestone 8; it was not hidden by using pre-existing `dist/` files.

## 7. Next action

Proceed to Milestone 0 task 3: compare the two unmerged worktrees against
`main`, then add the five failing reproductions to the main implementation
branch before applying fixes. Do not merge either worktree wholesale.