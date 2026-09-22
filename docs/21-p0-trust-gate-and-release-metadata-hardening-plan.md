# P0 Trust Gate and Release Metadata Hardening Plan

**Version 1.0.0**

**AI manifest**: Implementation-ready specification for a combined group of
small P0 improvements: repair the full-import rollback diagnostic, prevent
undefined-name regressions with a narrow Ruff gate, review and document every
current Bandit finding, make documentation checks operate on first-party
Markdown rather than arbitrary workspace files, and migrate package licensing
to PEP 639/SPDX metadata. This is a GPT-5.6 Luna Max handoff. Read `AGENTS.md`,
`docs/SESSION-CONTEXT.md`, `docs/18-project-improvement-audit-2026-09-22.md`,
and this file before editing.

## Handoff status

**[NOTE]** Selected combined task: **P0 Trust Gate and Release Metadata
Hardening**.

These items are combined because each is small, each protects release or
verification credibility, and together they close the engineering-trust work
identified ahead of broader product expansion. They do not form a new product
feature and must not change normal CLI or web behavior except for correcting
an already-broken rollback diagnostic and replacing silent internal failures
with diagnostics where the Bandit review proves that necessary.

Recommended implementation model: `gpt-5.6-luna` with maximum reasoning.

**[SPEC]** Do not begin implementation while the source-update or Skill
Hygiene work is still writing this working tree. Before the first edit:

1. Inspect `git status --short` and recent file modification times.
2. Confirm that no other session is changing `archive.py`, `cli_handlers.py`,
   `scopes.py`, `store.py`, `webapp.py`, tests, workflows, or shared docs.
3. Re-read the current versions and diffs of every expected file below.
4. If another writer remains active, wait or use a separate worktree.
5. Do not stash, reset, checkout, stage, or commit another session's changes.

The evidence in this plan was recorded against the shared-tree snapshot on
2026-09-22. The source-update and hygiene implementations were active during
planning, so line numbers are descriptive only. Symbols and behaviors are the
stable anchors.

## Why this bundle is next

**[NOTE]** The project audit found strong safety foundations but several small
credibility gaps at the exact places users and contributors depend on:

- a rollback failure can raise `NameError` while attempting to report the
  original recovery problem;
- the test suite can compile successfully while an undefined runtime name
  remains in a rarely executed branch;
- 18 Bandit findings have not been captured as explicit fix-or-accept
  decisions;
- the documentation gate can inspect unrelated Markdown placed inside the
  workspace; and
- the build emits deprecation warnings for legacy license metadata.

The changes are intentionally bundled into one trust-hardening task rather
than five tiny tasks. They share the same release/CI verification boundary,
are independently testable, and do not require a new subsystem.

## User and maintainer outcome

**[SPEC]** After this task:

1. A failed full-import rollback reports the original failure and the exact
   recoverable previous-payload location without a secondary exception.
2. CI rejects `F821`, `F822`, or `F823` undefined-name defects in first-party
   Python code.
3. Every current Bandit finding is either fixed or narrowly suppressed at the
   exact reviewed line with a rationale and regression evidence.
4. `check_docs.py` checks tracked Markdown plus explicitly first-party,
   intentionally untracked project documents, not arbitrary vendor/tool trees.
5. Built wheels and source archives declare `License-Expression: MIT`, include
   the `LICENSE` file, and no longer use the deprecated license classifier.
6. The installed CLI remains stdlib-only and no runtime package dependency is
   added.

## Scope

### Included

**[SPEC]** Implement all five workstreams:

1. Full-import rollback diagnostic repair and forced-failure regression.
2. Narrow Ruff correctness gate for `F821`, `F822`, and `F823` only.
3. Dated Bandit 1.9.4 review of `skillsmgr/`, including focused fixes,
   line-specific suppressions, and a maintained decision record.
4. Deterministic first-party Markdown discovery for `check_docs.py`.
5. PEP 639/SPDX license metadata plus artifact-level verification.

Also update the owning documentation, changelog, task tracker, and progress
log after the implementation is verified on the final settled tree.

### Excluded

**[SPEC]** Do not include:

- repository-wide formatting or the other Ruff findings;
- `ruff format`, auto-fix in CI, or a broad default Ruff ruleset;
- a global mypy migration;
- model-based or network-based security scanning;
- automatic dependency-update pull requests;
- a new CLI command, flag, public `Store` method, REST endpoint, or database
  field;
- a version bump, tag, publication, GitHub Release, or PyPI upload;
- public branding, screenshot, onboarding, contribution-access, or
  design-partner work;
- changes to the filesystem-as-truth model;
- blanket Bandit skips, an opaque baseline JSON file, or suppressions without
  a documented local reason;
- weakening archive validation, SQL parameter binding, executable trust
  checks, request security, or package-content exclusions; or
- converting developer tools into runtime dependencies.

## Locked constraints

**[SPEC]** Preserve every repository constraint:

1. Filesystem remains the source of truth.
2. SQLite schema and `SCHEMA_VERSION` remain unchanged.
3. The installed CLI remains stdlib-only.
4. The web backend remains stdlib-only and loopback-bound; the web UI keeps
   vendored Vue and no build step.
5. No new CLI command or public Store method is introduced.
6. Existing package builds still use the pinned, hash-verified build
   toolchain.
7. All external GitHub Actions remain pinned to full commit SHAs.
8. No recovery or security failure is swallowed silently.

No owner approval is required for the design in this plan. Stop and request
approval if implementation evidence suggests changing any locked constraint.

## Current evidence snapshot

**[NOTE]** Reproduce this snapshot after the active writers have finished.
Differences caused by completed source-update or hygiene work must be recorded,
not overwritten.

### Undefined runtime name

Ruff 0.16.8 with only the intended rule set currently reports:

```text
skillsmgr/archive.py: _rollback_full_install: F821 Undefined name `_diagnose`
Found 1 error.
```

`skillsmgr.archive._rollback_full_install()` invokes `_diagnose()` when moving
a previous payload back into place raises `OSError`, but `archive.py` does not
import that symbol. This branch runs only after another destructive recovery
operation has failed, so ordinary success-path tests do not expose it.

### Documentation discovery

The current in-flight `check_docs.py::_all_markdown()` uses `root.rglob("*.md")`
and excludes `.git`, `.autogit`, `dist`, and `node_modules`. That patch fixes
the observed `.mimocode/node_modules` failure but still makes the gate depend
on what unrelated directories happen to exist in a developer workspace.

The target contract is stronger: Git-tracked Markdown plus explicitly defined
first-party untracked Markdown roots.

### Bandit inventory

Bandit 1.9.4 over `skillsmgr/` reports 18 findings: three medium and fifteen
low. The settled implementation must regenerate the list, because active work
may add, remove, or move sites.

| Rule | Current symbol/site | Severity/confidence | Initial disposition |
|---|---|---:|---|
| `B202` | `archive.extract_members` guarded `tar.extractall` | medium/medium | Review validation chain; suppress only with hostile-archive regressions |
| `B404` | `backup_sync` subprocess import | low/high | Accept only because each call is separately controlled |
| `B603` | `backup_sync._run_git` | low/high | Accept after trusted executable and argument validation are pinned by tests |
| `B105` | `bundles.verify_manifest` boolean trust field | low/medium | False positive; line-specific suppression |
| `B404` | `cli_handlers` subprocess import | low/high | Accept only with each call site separately reviewed |
| `B603` | `cli_handlers.cmd_open` | low/high | Explicit user-requested editor execution; test argv construction |
| `B110` | `cli_handlers.cmd_doctor` JSON duplicate enrichment | low/high | Replace silence with diagnostic and explicit degraded evidence |
| `B110` | `cli_handlers.cmd_doctor` text scope enrichment | low/high | Replace silence with diagnostic without hiding the base Doctor result |
| `B603` | `cli_handlers.cmd_install` | low/high | Existing allowlisted runner and argv validation; pin with tests |
| `B105` | `evals.aggregate_benchmark` explanatory text | low/medium | False positive; line-specific suppression |
| `B110` | `scopes.get_skill` global token enrichment | low/high | Replace silence with diagnostic; retain best-effort response |
| `B110` | `scopes.get_skill` scope metadata enrichment | low/high | Replace silence with diagnostic; retain best-effort response |
| `B608` | `store._live_index_totals` disabled query | medium/medium | Placeholders are generated internally and values remain parameter-bound; document and suppress |
| `B608` | `store._live_index_totals` category query | medium/medium | Same bounded placeholder construction; document and suppress |
| `B404` | `webapp` subprocess import | low/high | Accept only while reviewed process sites remain controlled |
| `B603` | web install runner execution | low/high | Existing runner allowlist and argv validation; pin with tests |
| `B607` | `webapp._open_browser` partial `xdg-open` path | low/high | Fix by using trusted executable discovery or a proven safer stdlib seam |
| `B603` | `webapp._open_browser` | low/high | Review again after fixing `B607`; suppress only at the exact validated call |

**[SPEC]** This table is a starting inventory, not permission to paste
suppression comments. Reproduce each finding, inspect the settled source and
tests, and choose fix or accept based on executable evidence.

### Packaging metadata

The current `[project]` table contains:

```toml
license = { text = "MIT" }
classifiers = [
  "License :: OSI Approved :: MIT License",
]
```

The pinned setuptools version is already new enough for PEP 639. The target is:

```toml
license = "MIT"
license-files = ["LICENSE"]
```

and the deprecated `License ::` classifier is removed.

## External technical basis

**[NOTE]** Only free and open-source tools are involved.

- Ruff is open source and its stable Pyflakes-derived rules define `F821` as
  undefined name, `F822` as undefined export, and `F823` as a local referenced
  before assignment: [Ruff rule index](https://docs.astral.sh/ruff/rules/).
- Ruff 0.16.8 was the current release checked on 2026-09-22, and the official
  action supports selecting an exact Ruff version. The task pins action
  `astral-sh/ruff-action` v4.1.0 to commit
  `278981a28ce3188b1e39527901f38254bf3aac89`: [official Ruff integration guide](https://github.com/astral-sh/ruff/blob/main/docs/integrations.md).
- Bandit is Apache-2.0 open-source software. Its documentation supports
  line-level `# nosec` suppressions and named test ids; this task forbids broad
  skips: [Bandit documentation](https://bandit.readthedocs.io/).
- The packaging specification defines `license` as an SPDX expression and
  `license-files` as project-relative globs whose matches must be shipped:
  [pyproject.toml specification](https://packaging.python.org/specifications/declaring-project-metadata/).
- Metadata 2.4 deprecates `License ::` classifiers in favor of
  `License-Expression`: [core metadata specification](https://packaging.python.org/en/latest/specifications/core-metadata/).
- Setuptools 84 documents the exact migration from a license table and
  classifier to `license = "MIT"` plus `license-files = ["LICENSE"]`:
  [setuptools PEP 639 migration guide](https://setuptools.pypa.io/en/stable/userguide/license_migration.html).

## Architecture and policy decisions

### Decision 1: fail on undefined names, not style

**[SPEC]** Configure Ruff only for:

```toml
[tool.ruff]
target-version = "py310"

[tool.ruff.lint]
select = ["F821", "F822", "F823"]
```

The implementation may add explicit first-party excludes only if the source
path list does not already make them unnecessary. Do not enable all `F`
rules, default Ruff rules, formatting, import sorting, modernization, or
auto-fix.

The CI command must scan these first-party Python surfaces:

```text
skillsmgr/
tests/
smoke_store.py
smoke_web.py
browser_harness.py
desktop_launcher.py
check_complexity.py
check_docs.py
check_package_data.py
```

If another tracked first-party Python entry point exists when implementation
starts, add it deliberately. Do not scan virtual environments, `.mimocode`,
tool caches, build output, or arbitrary files outside the repository set.

### Decision 2: one pinned Ruff execution in CI

**[SPEC]** Add a single Ubuntu static-correctness job or equivalent one-time
step, not one Ruff execution per Python-version matrix member.

Use:

```yaml
uses: astral-sh/ruff-action@278981a28ce3188b1e39527901f38254bf3aac89
with:
  version: "0.16.8"
  args: "check --output-format=github"
```

Pass the explicit source set through the action's supported `src` input or an
immediately following command, and prove the chosen form in a workflow
contract test. Preserve `permissions: contents: read` and the repository's
full-SHA pin policy.

The action and Ruff are developer/CI tools only. They must not appear under
`[project].dependencies`, in the wheel, or on the installed CLI's import path.

### Decision 3: Bandit is a reviewed audit, not a hidden baseline

**[SPEC]** Run exactly:

```text
bandit 1.9.4
bandit -r skillsmgr -q
```

from a disposable environment during implementation and final verification.
Do not add Bandit to runtime dependencies. Do not use:

- a repository-wide `skips` list;
- `--baseline` to hide existing findings;
- a severity threshold that omits low findings;
- an unqualified `# nosec`; or
- a suppression copied to an import when the risky call itself remains
  unreviewed.

Every accepted site must use the narrow form `# nosec BNNN` and a nearby
human-readable comment explaining the trusted input, validation, or false
positive. The current decision and test anchor must also be recorded in
`docs/STATIC-ANALYSIS.md`.

**[SPEC]** The final Bandit run must produce zero unsuppressed findings over
`skillsmgr/`. This is not a claim that Bandit proves the application secure;
the decision document must say that explicitly.

### Decision 4: fix behaviors that are genuinely weak

**[SPEC]** At minimum:

- import `diagnostics.diagnose` under the private name expected by
  `archive._rollback_full_install`;
- replace silent `except Exception: pass` sites identified by `B110` with
  diagnostics and an explicit degraded result where the enclosing contract
  exposes degradation;
- replace `webapp._open_browser`'s unresolved `xdg-open` execution with
  `launcher_security.trusted_executable()` or another solution that satisfies
  the same owner/permission/PATH trust contract; and
- retain clean failure behavior if no trusted opener exists.

Do not silence these findings without fixing the behavior.

### Decision 5: suppress only proven false positives or accepted boundaries

**[SPEC]** The expected accepted boundaries are:

- `archive.extract_members`: members have already passed path, type, count,
  depth, size, duplicate, and layout validation; Python versions with
  `tarfile.data_filter` apply it; older versions use the manual contained-path
  extraction fallback. Keep or add traversal, link, device, and size tests.
- `store._live_index_totals`: only a comma-separated sequence of literal `?`
  placeholders is constructed; all names remain DB-API parameters. Add a test
  using quote/metacharacter-containing valid inputs where applicable, and
  assert no input enters SQL text.
- `backup_sync._run_git`: executable discovery is trusted, repository path is
  validated, argv is a list, prompts are disabled, timeout/output are bounded,
  and user-controlled revision/remote/ref values are validated before use.
- `cli_handlers.cmd_open`: launching `$EDITOR`/`$VISUAL` is the command's
  explicit user-authorized purpose; argv is parsed without a shell. Ensure the
  skill path is appended as one argument and shell execution remains false.
- install execution: runner and options remain allowlisted by the existing
  validators and argv construction remains list-based without a shell.
- `B105` strings are booleans or explanatory prose, never credentials.

If the settled source no longer satisfies one of these statements, fix it or
leave the finding unsuppressed and report the blocker. Do not make the decision
record match an unsafe implementation.

### Decision 6: tracked plus first-party Markdown

**[SPEC]** Replace broad workspace recursion with a deterministic union:

```text
Git-tracked *.md files
  UNION
untracked *.md files directly under docs/
  UNION
explicit top-level first-party Markdown names
```

The exact contract is:

1. Query Git with a NUL-delimited command equivalent to
   `git -C ROOT ls-files -z -- '*.md'`.
2. Decode paths safely and resolve them beneath the supplied repository root.
3. Include only existing regular files.
4. Add every regular `docs/**/*.md` file so a newly written plan is checked
   before it is tracked.
5. Add an explicit allowlist of first-party top-level Markdown files such as
   `AGENTS.md`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `ROADMAP.md`,
   `TODO.md`, and `task.md` when they exist.
6. Deduplicate and sort by repository-relative POSIX path.
7. Never follow a symlink outside the repository root.
8. If Git is unavailable or the directory is not a worktree, fall back to the
   explicit first-party roots and report no raw traceback.

This model intentionally ignores untracked Markdown in `.mimocode`, virtual
environments, `node_modules`, cache directories, editor state, and unrelated
tool folders without maintaining an ever-growing exclusion list.

Tracked Markdown remains checked regardless of where it lives; tracking the
file is the explicit project decision.

### Decision 7: PEP 639 artifact truth

**[SPEC]** Change only the licensing metadata needed for standards compliance:

```toml
license = "MIT"
license-files = ["LICENSE"]
```

Remove the deprecated MIT license classifier. Do not change the LICENSE text,
project license, package name, version, author, dependencies, build backend,
or build-tool pins.

Extend package verification so both the wheel and source archive prove:

- `License-Expression: MIT` exists in generated core metadata;
- `License-File: LICENSE` exists in generated core metadata;
- the exact repository `LICENSE` bytes are present in the artifact's expected
  license location;
- no deprecated `License ::` classifier remains; and
- existing forbidden-content and vendored-Vue checks still pass.

Use `email.parser`, `zipfile`, and `tarfile` from the standard library in test
and checker code. Do not add a runtime metadata parser.

## Detailed workstream A: rollback correctness

### Required implementation

**[SPEC]** In `skillsmgr/archive.py`:

1. Import `diagnose` from `skillsmgr.diagnostics` as `_diagnose`, matching the
   symbol already called by `_rollback_full_install`.
2. Preserve the current rollback order: remove the partially installed
   destination, attempt to restore the prior payload, then clean remaining
   staged paths.
3. If restoration raises `OSError`, emit a diagnostic containing:
   - the logical destination name;
   - the surviving previous-payload path; and
   - the restoration exception as diagnostic context.
4. Do not replace the original import failure with the restoration failure.
5. Do not delete the surviving previous payload after restoration fails.
6. Do not emit a raw traceback through the CLI or REST layer.
7. Preserve `BaseException`/interrupt handling already covered elsewhere.

### Red-first regression

**[SPEC]** Add a regression in `tests/test_archive_contracts.py` that exercises
the public full-payload restore path, not just a mocked call to `_diagnose`:

1. Create an existing destination with recognizable old bytes.
2. Stage at least two payloads so one install succeeds and a later install
   fails, causing transaction rollback.
3. Inject `move()` behavior that also raises `OSError` when restoring the
   successful destination's prior payload.
4. Assert the operation raises the original clean `ArchiveError` rather than
   `NameError` or the injected restore exception.
5. Capture stderr and assert it names the rollback problem and surviving
   previous-payload location without a traceback.
6. Assert the previous payload still exists at the named backup path with
   byte-identical content.
7. Assert unrelated paths are not removed.

Prove the regression is red against the pre-fix code, then restore and apply
the fix.

## Detailed workstream B: undefined-name CI gate

### Configuration

**[SPEC]** Add the minimal Ruff configuration to `pyproject.toml`. Keep it
separate from `[project]` runtime dependencies and from build-system
requirements.

### Workflow

**[SPEC]** Extend `.github/workflows/ci.yml` with one pinned Ruff execution.
The workflow contract test must assert:

- the action reference is the exact full SHA;
- the adjacent comment identifies v4.1.0 and its review date;
- Ruff version is exactly `0.16.8`;
- `F821`, `F822`, and `F823` are the only selected lint rules;
- all first-party Python surfaces are scanned;
- the job has no write permissions;
- no `--fix` or formatter command is present; and
- the existing unit, adversarial, package, docs, cross-platform, and browser
  jobs remain present.

### Mutation proof

**[SPEC]** In a disposable copy or reversible patch:

1. Introduce an undefined name inside a rarely executed function.
2. Show `py_compile` still succeeds.
3. Show the Ruff command fails with `F821`.
4. Restore the file.
5. Repeat with a bad `__all__` entry or referenced-before-assignment fixture if
   feasible, demonstrating `F822`/`F823` are active.

Record commands and results in the progress log. Never leave mutation fixtures
in product files.

## Detailed workstream C: Bandit decision pass

### Decision document

**[SPEC]** Create `docs/STATIC-ANALYSIS.md` with:

- a version and AI manifest;
- tool/version/scope commands;
- a clear statement that static analysis is advisory evidence, not proof of
  security;
- one row per current finding keyed by rule and owning symbol;
- disposition `fixed` or `accepted`;
- local rationale;
- exact regression test or invariant that supports the disposition;
- date reviewed; and
- policy for future findings.

Do not rely on line numbers as the primary identity. Use module plus symbol;
line numbers may be included only as dated context.

### Required review behavior

**[SPEC]** For every current and newly introduced finding:

1. Read the full owning function and its callers.
2. Identify user-controlled inputs and validation.
3. Prefer a code fix when behavior is silent, PATH-dependent, shell-like,
   unbounded, or not covered by a regression.
4. Use a line-level named suppression only for a false positive or an explicit
   product boundary.
5. Add or cite a test that would fail if the rationale becomes false.
6. Run Bandit again and require zero unsuppressed results.

### Silent exception handling

**[SPEC]** Reassess the four observed `B110` sites after the active feature
work settles. The final behavior must:

- call the shared diagnostic seam with a stable, non-secret context message;
- preserve a usable base response;
- populate an existing `degraded` list when that response contract supports
  it;
- never fabricate successful enrichment; and
- never leak raw exception text to a web response.

Do not introduce a new generic result field solely to satisfy Bandit. Use the
existing response's degradation convention where available and diagnostics
otherwise.

### Browser opener

**[SPEC]** `webapp._open_browser` must not execute the first untrusted
`xdg-open` found on PATH. Use `launcher_security.trusted_executable` with an
injected or patchable `which` seam consistent with the existing launcher
tests. If no trusted opener is found, return cleanly and leave the printed
loopback URL usable. Opening the browser remains convenience behavior, not a
server-start requirement.

Tests must cover:

- a trusted opener receives `[absolute_executable, url]` with `shell=False`;
- an unsafe first PATH match is skipped in favor of a safe later match;
- no trusted opener causes no process launch and no crash;
- an `OSError` during launch is diagnosed or cleanly ignored according to the
  established browser-open contract; and
- URL text cannot become extra argv elements.

## Detailed workstream D: deterministic docs gate

### Implementation seam

**[SPEC]** Keep `_all_markdown(root)` as the compatibility seam used by the
existing checks, but implement it through small private helpers rather than a
single complex function. Suggested private ownership:

```text
_tracked_markdown(root) -> list[Path]
_first_party_untracked_markdown(root) -> list[Path]
_all_markdown(root) -> sorted union
```

Names may vary, but one helper must own Git output decoding and one must own
fallback/first-party discovery. Do not grow an existing complexity hotspot.

### Tests

**[SPEC]** Extend `tests/test_docs_consistency.py` with isolated temporary
repositories or controlled subprocess mocks proving:

- a tracked Markdown file under an unusual directory is included;
- an untracked `docs/new-plan.md` is included;
- explicit top-level project docs are included when untracked;
- untracked `.mimocode/node_modules/noise.md` is excluded;
- untracked `.venv`, cache, build, and arbitrary tool Markdown is excluded;
- spaces and non-ASCII characters in tracked paths survive NUL parsing;
- duplicates appear once in stable POSIX-path order;
- a symlinked Markdown file escaping the repository is excluded;
- missing Git falls back cleanly; and
- a malformed or failing Git subprocess produces no traceback.

Run the real checker with the current untracked implementation plans present.
It must pass without special-casing their filenames.

## Detailed workstream E: SPDX package metadata

### Source metadata

**[SPEC]** Update `[project]` in `pyproject.toml` exactly as defined above.
Do not update the build-system setuptools pin; version 84.0.0 already supports
the target fields.

### Source-tree tests

**[SPEC]** Extend the existing CI/release or package-data contracts to assert:

- `license` is a string equal to `MIT`;
- `license-files` is exactly or semantically equivalent to `["LICENSE"]`;
- no classifier starts with `License ::`;
- `LICENSE` exists and is UTF-8 decodable; and
- the setuptools pin stays aligned with `requirements-build.txt`.

Python 3.10 compatibility matters: if parsing TOML in a test would require
`tomllib`, use the project's existing text-based metadata inspection pattern
or another stdlib-compatible approach. Do not add `tomli`.

### Artifact tests

**[SPEC]** Extend `check_package_data.py` and `tests/test_package_data.py` so
the exact built wheel and source archive are inspected. The checker must fail
cleanly when:

- license expression is missing or not `MIT`;
- the license file declaration is missing;
- the license file is absent from either artifact;
- the artifact's license bytes differ from repository `LICENSE`; or
- the deprecated license classifier survives in core metadata.

Keep the checker's current `UNAVAILABLE` behavior when build artifacts or
build tooling are intentionally absent, unless `--dist-dir` or the existing
required-build mode makes artifacts mandatory.

## Error handling and security boundaries

**[SPEC]** The implementation must satisfy all of these boundaries:

- Diagnostics must not include skill bodies, credentials, environment values,
  remote URLs containing credentials, or raw HTTP exception text.
- The rollback message may expose a local backup path to the local operator;
  it must not be returned through a new network endpoint.
- Ruff and Bandit never execute project Python modules as part of analysis.
- Git output from documentation discovery is treated as untrusted bytes and
  every path is containment-checked.
- Documentation discovery does not follow out-of-root symlinks.
- No linter suppression broadens process execution, archive extraction, SQL,
  or web request authority.
- Package verification reads archives without extracting them into the
  workspace.
- External-tool absence locally is reported as `UNAVAILABLE`, never falsely
  recorded as a pass; CI is responsible for the mandatory Ruff gate.

## Compatibility contract

**[SPEC]** Preserve:

- every existing CLI command, flag, JSON shape, and exit code;
- normal web server startup even when no GUI opener exists;
- full-import success behavior and existing rollback order;
- Python 3.10 through 3.14 support;
- wheel and source-archive names and package version;
- all existing archive, SQL, subprocess, docs, workflow, and package security
  tests;
- stdlib-only runtime imports; and
- the current `check_docs.py` public script behavior: exit zero on success,
  nonzero with readable findings on failure.

If replacing silent enrichment changes a JSON field, it must use an already
documented degradation field and retain the prior base keys.

## Expected file changes

### Create

**[SPEC]** Expected new implementation artifact:

- `docs/STATIC-ANALYSIS.md` — maintained static-analysis scope, decisions,
  suppressions, and rerun policy.

A dedicated `tests/test_static_analysis_contracts.py` may be created if the
workflow/config/decision-document contracts do not fit cleanly in existing
test modules.

### Modify

**[SPEC]** Expected modifications after concurrent work has settled:

- `skillsmgr/archive.py`
- `skillsmgr/backup_sync.py`
- `skillsmgr/bundles.py`
- `skillsmgr/cli_handlers.py`
- `skillsmgr/evals.py`
- `skillsmgr/scopes.py`
- `skillsmgr/store.py`
- `skillsmgr/webapp.py`
- `check_docs.py`
- `check_package_data.py`
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `tests/test_archive_contracts.py`
- `tests/test_docs_consistency.py`
- `tests/test_package_data.py`
- relevant subprocess/web/workflow contract tests
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `docs/02-modules.md`
- `docs/06-progress-log.md`
- `docs/README.md`
- `docs/SESSION-CONTEXT.md`
- `task.md`

Modify only the subset still required after reproducing the settled baseline.
For example, if hygiene work has already replaced a silent exception with an
equivalent diagnostic, test and document it rather than rewriting it.

### Prefer not to modify

**[SPEC]** No change is expected to:

- `skillsmgr/cli_parser.py`
- `skillsmgr/cli.py`
- `skillsmgr/source_update.py`
- `skillsmgr/hygiene.py`
- `skillsmgr/effective.py`
- `skillsmgr/validator.py`
- `skillsmgr/source_lock.py`
- database migrations or schema constants
- web UI HTML, CSS, or JavaScript

If one becomes necessary, explain why before editing and confirm it does not
expand the task.

## Implementation phases

### Phase 0: serialize and refresh evidence

**[SPEC]** Before editing:

1. Confirm the other writers have stopped or move to an isolated worktree.
2. Re-read `AGENTS.md` and the relevant current docs.
3. Run the baseline unit suite, both smokes, docs check, complexity gate, and
   `git diff --check` on the current tree.
4. Re-run Ruff 0.16.8 with only `F821,F822,F823`.
5. Re-run Bandit 1.9.4 over `skillsmgr/`.
6. Build artifacts once with the pinned build toolchain and capture the current
   license warnings and metadata.
7. Record any delta from this plan without reverting concurrent work.
8. Register this plan in `docs/README.md`, `task.md`, and the progress log if
   that registration was deferred during concurrent writing.

Deliverable: a dated baseline with exact commands and no edits to product
behavior.

### Phase 1: recovery correction

**[SPEC]** Work red-first:

1. Add the forced rollback-failure regression.
2. Demonstrate the `NameError` failure on the pre-fix implementation.
3. Add the missing diagnostic import and only the smallest supporting change.
4. Run the focused archive tests.
5. Run `python3 smoke_store.py` if the public restore/import path is exercised
   through Store behavior.

Milestone: rollback recovery fails honestly, retains recoverable bytes, and no
longer masks the original failure.

### Phase 2: deterministic docs and SPDX metadata

**[SPEC]** These are independent in design but one writer still edits them
serially:

1. Add docs-discovery tests and replace workspace-wide recursion.
2. Run the documentation checker with hostile workspace noise fixtures.
3. Add source metadata tests and migrate to PEP 639 fields.
4. Extend artifact verification and its tests.
5. Build wheel and source archive through the pinned toolchain.
6. Inspect generated metadata and exact license bytes.

Milestone: docs checks are workspace-stable and artifact licensing is
standards-correct.

### Phase 3: static correctness and Bandit triage

**[SPEC]** After active source edits have settled:

1. Add minimal Ruff config.
2. Repair the undefined rollback name already fixed in Phase 1 and any new
   settled-tree undefined findings.
3. Add the pinned one-time CI gate and workflow contract tests.
4. Triage every Bandit result, fixing weak behavior first.
5. Add focused regressions for each rationale.
6. Add only named, line-local suppressions.
7. Write `docs/STATIC-ANALYSIS.md` from the verified final dispositions.
8. Run Ruff and Bandit again; require zero selected Ruff findings and zero
   unsuppressed Bandit findings.

Milestone: static correctness fails closed in CI, and the security-analysis
surface is explicit and reviewable.

### Phase 4: documentation and complete verification

**[SPEC]** Only after behavior is stable:

1. Update module, session, contributor, changelog, docs index, task, and
   progress documents with current facts.
2. Run focused tests again.
3. Run the full verification ladder sequentially on the final current tree.
4. Inspect the final diff for unrelated writer changes; do not claim them as
   part of this task.
5. Record unavailable optional tools honestly.

Milestone: all gates pass on the final tree and the documentation describes
the shipped behavior rather than the plan.

## Test plan

### Recovery tests

**[SPEC]** Cover:

- ordinary full restore success;
- failure before any destination replacement;
- failure after one destination replacement;
- successful rollback restoration;
- rollback restoration `OSError` with surviving backup;
- original exception preserved;
- diagnostic context present;
- no raw traceback; and
- interrupt/BaseException behavior unchanged.

### Ruff and workflow tests

**[SPEC]** Cover:

- exact selected rule list;
- Python 3.10 target;
- exact action SHA and Ruff version;
- explicit source surfaces;
- read-only workflow permissions;
- no auto-fix;
- no runtime dependency entry; and
- mutation proof for each selected rule family where practical.

### Bandit decision tests

**[SPEC]** Cover behavior behind each accepted boundary rather than testing
comments alone:

- hostile TAR members remain rejected;
- SQL names remain DB-API-bound values;
- Git executable and revisions remain validated;
- editor and installer invocations remain list argv with no shell;
- unsafe browser opener is not launched;
- silent enrichment failures emit diagnostics/degradation;
- false-positive credential strings never carry secret data; and
- full Bandit 1.9.4 scan is clean after named suppressions.

### Documentation tests

**[SPEC]** Cover the ten discovery cases listed in workstream D plus existing
link, symbol, version, anchor, house-style, and surface-parity checks.

### Packaging tests

**[SPEC]** Cover:

- source configuration;
- generated wheel metadata;
- generated sdist metadata;
- exact LICENSE inclusion and bytes;
- removal of deprecated classifier;
- warning-free license build output;
- malformed/missing license metadata failures; and
- all pre-existing forbidden-artifact checks.

### Compatibility and integration tests

**[SPEC]** Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_archive_contracts
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_docs_consistency
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_package_data
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_ci_release_contracts
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
python3 smoke_store.py
python3 smoke_web.py
python3 check_docs.py
python3 check_complexity.py
python3 check_package_data.py
node --check skillsmgr/webui/app.js
node --check skillsmgr/webui/domain.js
git diff --check
```

Run `smoke_web.py` because `webapp.py` is expected to change. If a final
implementation avoids `webapp.py`, document why but still retain the smoke in
the final ladder.

### External-tool verification

**[SPEC]** In a disposable environment, pin the analyzed tool versions:

```bash
ruff 0.16.8
ruff check <explicit first-party paths>

bandit 1.9.4
bandit -r skillsmgr -q
```

Record the tool versions and exit codes. Do not write the disposable
environment into the repository or add it to runtime metadata.

### Artifact verification

**[SPEC]** Use the repository's exact build procedure:

```bash
python3 -m pip install --require-hashes -r requirements-build.txt
python3 -m build --no-isolation --wheel --sdist --outdir dist
python3 check_package_data.py --dist-dir dist
```

Use a disposable virtual environment. Do not change pinned versions merely to
silence a local environment mismatch.

## Performance and operability

**[SPEC]** These gates must remain inexpensive and deterministic:

- Ruff runs once per CI workflow, not per interpreter matrix entry.
- Documentation file discovery scales with tracked paths plus `docs/`, not the
  size of arbitrary workspace vendor directories.
- Bandit is a developer/security audit command unless a future separately
  approved supply-chain-safe CI installation is added.
- Package metadata inspection reads archive members directly and does not
  extract them.
- No gate uses network access after its explicitly pinned tool is available.
- Failures identify the owning file/symbol and corrective action.

Measure and record local elapsed time for Ruff, Bandit, docs, and package-data
checks as context only. Do not turn one machine's times into universal budgets.

## Documentation requirements

**[SPEC]** Final documentation must explain:

- why only three Ruff rules are mandatory;
- how contributors run Ruff and Bandit without making them runtime
  dependencies;
- how and why each Bandit suppression is reviewed;
- that zero Bandit findings is not a security proof;
- how `check_docs.py` decides which Markdown belongs to the project;
- that intentionally untracked files under `docs/` are still checked;
- the PEP 639/SPDX package metadata contract;
- the exact rollback defect and regression; and
- all verification commands and final counts.

Do not repeat volatile finding/test counts across many current docs. Keep the
detailed dated evidence in `docs/STATIC-ANALYSIS.md` and the progress log.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---:|---|
| A broad Ruff rollout creates 167 unrelated cleanup changes | High | Select only `F821,F822,F823`; forbid auto-fix and drive-by formatting |
| Bandit suppression hides a real process/archive/SQL weakness | High | Full function/caller review, named line-level suppression, regression anchor, zero blanket skips |
| Browser-opener hardening breaks `webui` startup | Medium | Make opener optional; always preserve the printed loopback URL and server startup |
| Docs discovery ignores a real project document | Medium | Include all tracked Markdown plus `docs/**/*.md` and explicit top-level files; test unusual tracked locations |
| Docs discovery follows an escaping symlink | High | Resolve and containment-check every candidate; include only regular in-root files |
| License appears in source but not artifacts | High | Inspect both built artifacts and generated metadata, byte-for-byte |
| New action weakens supply-chain posture | High | Pin action and tool versions; keep read-only permissions; add workflow contract tests |
| Active source-update/hygiene work is overwritten | High | Serialize writers or use an isolated worktree; re-read files immediately before each edit |
| A suppression line drifts away from its invariant | Medium | Key decision docs by symbol, cite tests, rerun Bandit on final current tree |
| Python 3.10 tests import `tomllib` | Medium | Use existing text parsing or a Python-3.10-compatible stdlib seam |
| Temporary analysis environments pollute the repo | Low | Create outside the worktree and never add them to package metadata |

## Acceptance criteria

**[SPEC]** All criteria are mandatory:

- [ ] TH-01: The source-update and hygiene writers are finished or this task
  runs in a separate worktree before shared files are edited.
- [ ] TH-02: A red-first regression reproduces the rollback-path `NameError`.
- [ ] TH-03: Full-import rollback restoration failure reports through the
  shared diagnostic seam without masking the original error.
- [ ] TH-04: The surviving previous-payload path remains visible and its bytes
  remain recoverable after an injected restore failure.
- [ ] TH-05: Ruff selects only `F821`, `F822`, and `F823` with Python 3.10 as
  the target.
- [ ] TH-06: One CI execution uses Ruff 0.16.8 through the full-SHA-pinned
  Ruff action and scans every first-party Python surface.
- [ ] TH-07: Ruff is not a runtime or build dependency and CI never auto-fixes
  repository files.
- [ ] TH-08: Mutation evidence proves the gate catches an undefined name that
  compilation misses.
- [ ] TH-09: Every Bandit 1.9.4 finding in the settled tree has a fix or a
  line-specific named suppression with rationale and test evidence.
- [ ] TH-10: No global Bandit skip, opaque baseline, threshold hiding, or bare
  `# nosec` is introduced.
- [ ] TH-11: `bandit -r skillsmgr -q` produces zero unsuppressed findings.
- [ ] TH-12: Silent `B110` sites are diagnosed and expose degradation when the
  owning result contract supports it.
- [ ] TH-13: The web browser opener never executes an untrusted first PATH
  match and server startup survives opener absence/failure.
- [ ] TH-14: `docs/STATIC-ANALYSIS.md` records scope, versions, decisions,
  invariants, test anchors, and the limits of static-analysis evidence.
- [ ] TH-15: Documentation discovery is the stable union of tracked Markdown,
  `docs/**/*.md`, and explicit top-level first-party documents.
- [ ] TH-16: Untracked vendor, virtual-environment, cache, editor, and tool
  Markdown cannot break the docs gate.
- [ ] TH-17: Tracked unusual paths and untracked `docs/` plans remain checked,
  with NUL-safe filenames, stable ordering, and no duplicates.
- [ ] TH-18: Escaping Markdown symlinks are excluded and Git absence has a
  clean first-party fallback.
- [ ] TH-19: `pyproject.toml` uses `license = "MIT"` and
  `license-files = ["LICENSE"]` with no `License ::` classifier.
- [ ] TH-20: Wheel and source archive metadata both declare MIT via
  `License-Expression` and declare the LICENSE file.
- [ ] TH-21: Both artifacts contain byte-identical LICENSE content and all
  existing package-content exclusions still pass.
- [ ] TH-22: The package build emits no legacy-license deprecation warning.
- [ ] TH-23: No CLI command, Store method, REST endpoint, schema, runtime
  dependency, package version, or public behavior beyond the specified fixes
  changes.
- [ ] TH-24: Focused tests, full suite, both smokes, docs, complexity,
  package-data, JS syntax, Ruff, Bandit, artifact builds, and
  `git diff --check` pass on the final current tree.
- [ ] TH-25: Contributor, module, session, changelog, docs index, task, and
  progress documentation match verified behavior and exact final commands.
- [ ] TH-26: The final diff preserves unrelated concurrent changes and claims
  only files/lines actually implemented by this task.

## Definition of done

**[SPEC]** The task is complete only when:

1. The destructive recovery regression passes and proves retained bytes.
2. Selected Ruff rules are mandatory in CI and green.
3. The complete settled-tree Bandit inventory is fixed or explicitly justified
   with no unsuppressed findings.
4. Documentation discovery is independent of unrelated workspace contents.
5. Built artifacts contain correct PEP 639 metadata and LICENSE bytes.
6. All 26 acceptance criteria have automated or explicit manual evidence.
7. The complete ladder is rerun after every concurrent change has stopped.
8. `task.md` and `docs/06-progress-log.md` contain exact final test counts,
   tool versions, build commands, and unavailable checks.
9. No unrelated change is staged, committed, or attributed to this task.

## Implementation cautions for Luna Max

**[SPEC]** During implementation:

- Use `apply_patch` for source edits.
- Treat this plan's line numbers and counts as dated evidence; anchor edits to
  symbols after reading the settled files.
- Do not start while another writer is changing overlapping files.
- Do not solve `F821` by renaming or deleting the rollback diagnostic call.
- Do not catch `NameError` or broaden an exception handler to mask the defect.
- Do not run Ruff auto-fix or expand the selected rules.
- Do not add Ruff or Bandit to `[project].dependencies` or build-system
  requirements.
- Do not add a Bandit baseline file or global skip list.
- Do not annotate `# nosec` until the owning behavior and regression have been
  inspected.
- Do not replace safe argv lists with shell strings.
- Do not trust `xdg-open` merely because it exists on PATH.
- Do not turn docs discovery back into a growing directory-exclusion list.
- Do not follow documentation symlinks outside the repository.
- Do not extract built archives merely to inspect metadata.
- Do not update the package version or publish artifacts.
- Do not change the setuptools pin; it already supports PEP 639.
- Do not update complexity baselines to excuse new hotspots.
- Re-run the final ladder on the current tree immediately before completion.

## Open decisions

**[?]** No product or architecture decision is intentionally left open.

If the official Ruff action cannot pass the repository's full-SHA or
download-integrity policy in the actual CI environment, stop and document the
evidence. The acceptable fallback is a separately reviewed, hash-pinned Ruff
installation strategy; an unpinned `pip install ruff` is not an acceptable
silent substitution.

If Bandit 1.9.4 produces new findings after active feature work settles, they
join this task's review scope only when they are in files already changed by
the source-update or hygiene work. A materially new security design problem
must be documented and escalated rather than suppressed to make the count
zero.
