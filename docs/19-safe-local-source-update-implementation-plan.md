# Safe Local Source Update Implementation Plan

**Version 1.1.0**

**AI manifest**: Implementation-ready specification for one complete feature: previewing and atomically applying a local-directory update to one exact installed skill instance, with persistent review evidence, validation, advisory risk evidence, whole-tree recovery snapshots, and previewed rollback. This is the primary handoff document for a GPT-5.6 Luna implementation run. Read `AGENTS.md`, `docs/SESSION-CONTEXT.md`, `docs/ADR-008-source-lock-and-update-preview.md`, and this document before editing. Do not expand the feature to Git/network updates, background checks, team policy, or a new SQLite schema.

## Handoff status and implementation agent

**[NOTE]** Selected feature: **Safe local source update and rollback**.

Recommended implementation model: `gpt-5.6-luna` with maximum reasoning. The
implementation must remain one-writer-per-working-tree and must preserve any
unrelated changes already present when the run begins.

This document specifies a complete vertical slice across domain service, CLI,
REST API, local web UI, documentation, and automated tests. The implementation
is complete only when every required surface and verification gate below is
green on the final current tree.

**[SPEC] Approval boundary — approved 2026-09-22**

The owner explicitly approved this design in the implementation session. It
adds one top-level CLI command, `update`, with the three documented
subcommands. No new public `Store` method, SQLite column, schema version,
runtime dependency, UI framework, or network behavior is proposed.

## Why this feature

**[NOTE]** `skillsmgr.source_lock` already implements the difficult low-level
mechanics:

- bounded whole-tree manifests and SHA-256 content identity;
- symlink, traversal, depth, count, file-size, and total-size rejection;
- added, removed, changed, binary, and line-ending-only comparisons;
- candidate validation and advisory risk evidence;
- stale-review detection;
- cross-process mutation locking;
- snapshot-before-apply;
- atomic tree replacement;
- a source-lock sidecar; and
- explicit snapshot restoration.

Those mechanics are caller-driven and have no CLI, REST, or UI workflow. The
feature closes that gap without inventing a second update engine. It also
directly addresses the most consistent user request found in the product audit:
show exactly what will change, require an explicit decision, and make recovery
obvious.

## User outcome

**[SPEC]** A user can select one exact installed skill instance, provide one
local candidate directory, review a bounded whole-tree diff and validation
evidence, apply exactly the reviewed bytes, and later prepare a rollback using
the same review process.

The happy path is:

```text
Choose exact installed instance
  -> choose or upload local candidate directory
  -> stage a private immutable review copy
  -> display diff, validation, risks, identity, and activation-state policy
  -> approve the review
  -> create whole-tree snapshot
  -> atomically replace target
  -> reindex global scope when applicable
  -> show snapshot and source-lock evidence
  -> optionally preview that snapshot as a rollback candidate
```

## Goals

**[SPEC]** The implementation must:

1. Update one exact physical skill instance, including recursive-scope cases
   where the same name appears more than once.
2. Copy the candidate into a private manager-owned review directory before
   returning the preview.
3. Apply only that staged reviewed copy, never the caller's mutable source path.
4. Reject a commit when the installed target changed after review.
5. Preserve whether the target was enabled or disabled.
6. Exclude manager provenance/source-lock sidecars supplied by the candidate.
7. Validate the normalized staged candidate before making it committable.
8. Keep risk findings advisory and visibly separate from validity.
9. Create a complete whole-tree snapshot before replacement.
10. Make rollback a new previewed update from a retained snapshot, not a blind
    one-click restore.
11. Keep the filesystem authoritative and reconcile the global SQLite index only
    after a successful filesystem mutation.
12. Produce stable human-readable and JSON CLI output.
13. Expose the same semantics through the REST API and local web UI.
14. Remain stdlib-only at runtime and preserve the no-build Vue architecture.

## Non-goals

**[SPEC]** Do not add any of the following:

- Git clone, pull, fetch, or remote-version discovery.
- Registry update checking.
- Background jobs, polling, file watchers, or scheduled updates.
- Automatic approval or unattended apply.
- Multi-skill/batch updating.
- Three-way merge or file-level conflict resolution.
- Semantic or model-based malware judgments.
- A hosted service, authentication system, or telemetry.
- SQLite state or a schema/version change.
- A public `Store` method.
- Dependency installation.
- Direct permanent snapshot deletion from the feature UI.
- A new frontend framework, package manager, or build step.

## Existing contracts to preserve

**[SPEC]** The implementation must preserve these repository invariants:

- Filesystem content is the source of truth.
- SQLite remains a rebuildable global-scope index.
- Agent scopes are read and written directly on disk.
- A skill directory contains exactly one of `SKILL.md` and
  `SKILL.md.disabled`.
- User-controlled skill names pass the canonical name guard before path
  construction.
- Every physical target is contained by and re-resolved from its observed
  scope root.
- No candidate symlink is followed or copied.
- No manager sidecar from an untrusted candidate becomes installed evidence.
- Mutations remain cross-process locked and recoverable.
- `StoreError` and `SkillNotFound` reach users as clean errors, never raw
  tracebacks.
- The web server retains its Host, Origin, content-type, size, and method
  protections.
- Risk evidence never becomes a safety verdict.

## Terminology and state model

**[SPEC]** Use these terms consistently in code, JSON, UI, CLI, and docs:

| Term | Meaning |
|---|---|
| Target | One exact installed physical skill directory selected from an observed scope instance |
| Source | The caller-provided local directory or a retained recovery snapshot |
| Candidate | The normalized, private, manager-owned copy of the source used for review and apply |
| Review | Expiring filesystem artifact binding target hash, candidate hash, diff, validation, risks, and target identity |
| Apply | Snapshot the target and atomically replace it with the reviewed candidate |
| Recovery snapshot | Complete pre-apply skill tree retained under manager data, including previous manager sidecars |
| Rollback preview | A normal review whose candidate is a recovery snapshot |

Allowed review statuses:

```text
pending
committed
cancelled
expired
```

Only `pending` can be applied or cancelled. Expiry is derived from time and does
not require a background mutation. A committed, cancelled, expired, missing, or
malformed review cannot be replayed.

## Product behavior

### Target selection

**[SPEC]** The caller supplies `name`, `scope`, and optionally
`target_path`. The service must discover current instances through the existing
scope layer; it must never accept the supplied path as authority.

Resolution rules:

1. `scope=all` is invalid for mutations.
2. Unknown or unavailable scopes fail cleanly.
3. Match observed records by canonical name within the requested scope.
4. If exactly one match exists, select it.
5. If more than one match exists, require `target_path`.
6. When `target_path` is supplied, resolve it and require exact equality with
   one currently observed instance path.
7. Verify the selected path remains contained in its current physical root.
8. Require the target directory to be accessible and writable.
9. Record the canonical resolved `physical_path`, `physical_root`, scope, name,
   consumer, and activation state in the review.

This rule is required for recursive project/agent scopes, where `(scope, name)`
alone can be ambiguous.

### Candidate normalization

**[SPEC]** Preparation copies the source into the review directory before
reviewing it. The staged copy is normalized as follows:

1. Validate the source with `local_manifest()` before and after copying.
2. Refuse symlinks, unsafe paths, excessive depth/count/size, or a missing skill
   document.
3. Strip `.skillsmgr-provenance.json` and `.skillsmgr-source-lock.json` from the
   staged candidate even though manifest generation already excludes them.
4. Reject a candidate containing both primary skill filenames.
5. Preserve the target's activation state:
   - active target -> candidate contains `SKILL.md`;
   - disabled target -> candidate contains `SKILL.md.disabled`.
6. Rename the candidate's one primary document when needed; do not treat a
   candidate filename as permission to enable or disable the target.
7. Validate frontmatter against the target's canonical skill name.
8. Retain other regular files and their modes as copied by `shutil.copytree`.
9. Recompute the manifest after normalization; this hash is the candidate hash
   bound to the review.

The public preview must state `activation_preserved: true` and identify the
resulting activation state.

### Review behavior

**[SPEC]** A preview operation creates a durable private review artifact and
returns public evidence. It never mutates the installed target.

The public evidence must include:

- review id and expiration time;
- review state;
- exact target identity;
- source identity without credentials, query strings, or fragments;
- current and candidate tree hashes;
- file counts and byte totals;
- added, removed, and changed file lists;
- bounded text diffs and explicit truncation flags;
- binary-difference messages where applicable;
- line-ending-only classifications;
- structural validation errors and warnings;
- advisory risk findings and their policy text;
- activation-state preservation;
- snapshot requirement;
- `commit_allowed: false`; and
- an explicit instruction that a separate apply operation is required.

A structurally invalid candidate may return a review response for inspection,
but its state must be `blocked`, it must have no applicable review token, and no
apply request can make it committable. Do not persist a reusable pending review
for a blocked or no-change result; remove its staged directory after producing
the response.

No-change previews must be explicit and non-committable.

### Diff bounds

**[SPEC]** Retain the existing per-file diff limit and add a total preview diff
budget so a candidate with many changed text files cannot generate an
unbounded JSON response.

Required behavior:

- Maximum 200 rendered diff lines per file.
- Maximum 1,000 rendered diff lines across the preview.
- Each changed-file record reports `diff_truncated: true|false`.
- The comparison reports `diff_lines_returned` and
  `diff_total_truncated: true|false`.
- Hashes, byte counts, and change classifications remain present even when text
  is truncated.
- Binary data is never embedded in the response.

### Apply behavior

**[SPEC]** Apply requires all of the following:

- a syntactically valid review id;
- a pending, unexpired, readable review;
- explicit `approve=true` at the service/REST layer;
- mandatory `--yes` at the CLI layer;
- a caller-supplied name and scope matching the review;
- `target_path` equality when the review binds an ambiguous instance;
- an unchanged private candidate hash;
- an unchanged target tree hash;
- revalidation of the staged candidate; and
- acquisition of the review lock before the target mutation lock.

The service delegates replacement to `source_lock.commit_local_update()` and
passes a manager-owned snapshot root. On success it:

1. marks the outer review committed atomically;
2. returns the new source-lock evidence and opaque snapshot id;
3. reconciles the global index with `Store.resync()` only for global scope;
4. rescans and returns the resulting installed instance; and
5. prunes old recovery snapshots only after success.

If filesystem commit succeeds but review-status persistence or global index
reconciliation fails, return an explicit `committed_with_warning` result. Never
claim that no mutation occurred. The response must include recovery guidance
and the snapshot id. Index reconciliation can be retried; the filesystem stays
authoritative.

### Snapshot behavior

**[SPEC]** Store source-update snapshots under the manager data directory:

```text
<data>/source-update-snapshots/
  <scope>/
    <skill-name>/
      <review-id>/
        <source-lock-generated-snapshot-id>/
          SKILL.md or SKILL.md.disabled
          ...complete previous tree...
```

Rules:

- Directory creation is private (`0700` where supported).
- Snapshot identifiers exposed publicly are the outer review ids, not absolute
  paths.
- Resolve every snapshot id through canonical patterns and containment checks.
- Retain the newest five successful snapshots per exact target instance.
- Do not prune a snapshot involved in an active rollback review.
- A recursive-scope target path must participate in the internal snapshot key
  so two same-name instances never share recovery history. Use a stable
  credential-free path digest internally; do not replace the human scope/name
  hierarchy.
- Snapshot listing returns creation time, source review id, tree hash,
  activation state, and whether the directory remains readable.
- Unreadable or malformed snapshots are reported as unavailable; they do not
  crash the complete listing.

### Rollback behavior

**[SPEC]** Rollback reuses the normal review pipeline:

1. User selects a retained snapshot.
2. Service resolves it inside the snapshot root.
3. Snapshot becomes the source for a new normalized staged candidate.
4. User receives the same diff, validation, risk, and target evidence.
5. User explicitly applies the rollback review.
6. The apply creates a new snapshot of the current tree, so rollback itself is
   reversible.

Do not expose `restore_source_snapshot()` directly through CLI or REST for this
feature.

## Filesystem review artifacts

**[SPEC]** Add a new private filesystem-owned review area:

```text
<data>/source-update-reviews/
  <review-id>/
    review.json
    candidate/
      SKILL.md or SKILL.md.disabled
      ...reviewed files...
```

Use a 32-character lowercase hexadecimal random review id. Review directories
must be `0700`; `review.json` must be `0600` where supported. Candidate files
are protected by their private ancestor and retain source file modes.

Default expiry is 24 hours. Bound `review.json` to 2 MiB. Preparation and read
operations may remove expired review directories, but cleanup must:

- operate only below the resolved review root;
- reject symlinked review roots or entries;
- ignore an entry currently protected by its review mutation lock;
- never traverse a candidate symlink;
- never remove committed snapshot data; and
- never turn cleanup failure into target mutation.

Suggested internal record shape:

```json
{
  "version": 1,
  "review_id": "32-lowercase-hex",
  "status": "pending",
  "created_at": "2026-09-22T00:00:00Z",
  "expires_epoch": 0,
  "target": {
    "name": "demo",
    "scope": "codex",
    "consumer": "codex",
    "physical_root": "/resolved/root",
    "physical_path": "/resolved/root/demo",
    "path_digest": "sha256",
    "contained": true,
    "disabled": false,
    "ambiguous": false
  },
  "source": {
    "kind": "local",
    "value": "/caller/source"
  },
  "candidate": {
    "content_hash": "sha256",
    "file_count": 2,
    "total_bytes": 1234
  },
  "source_review": {
    "review_id": "source-lock-review-id",
    "current_hash": "sha256",
    "candidate_hash": "sha256"
  },
  "preview": {},
  "rollback_from_snapshot": null
}
```

Do not store access tokens, environment values, HTTP headers, cookies,
credential-bearing URLs, or uploaded raw bytes inside `review.json`.

## Service architecture

**[SPEC]** Create `skillsmgr/source_update.py` as the orchestration boundary.
It may call existing public scope and source-lock functions, but it must not
become a new persistence owner for installed skills.

Required public module functions:

```python
class SourceUpdateError(StoreError): ...

def prepare_local_update(
    data_dir: str | Path,
    name: str,
    scope: str,
    source_dir: str | Path,
    *,
    target_path: str | Path | None = None,
) -> dict: ...

def prepare_snapshot_update(
    data_dir: str | Path,
    name: str,
    scope: str,
    snapshot_id: str,
    *,
    target_path: str | Path | None = None,
) -> dict: ...

def read_update_review(data_dir: str | Path, review_id: str) -> dict: ...

def cancel_update_review(data_dir: str | Path, review_id: str) -> dict: ...

def commit_update_review(
    data_dir: str | Path,
    review_id: str,
    *,
    name: str,
    scope: str,
    target_path: str | Path | None = None,
    approve: bool = False,
) -> dict: ...

def list_update_snapshots(
    data_dir: str | Path,
    name: str,
    scope: str,
    *,
    target_path: str | Path | None = None,
) -> list[dict]: ...
```

The implementation also accepts an adapter-only optional source label for a
browser upload; the REST route uses `browser-upload` so a temporary staging
path is never returned as public source identity. CLI/local-directory callers
retain the credential-free local path evidence described above.

These are module functions, not `Store` methods. Keep private helpers small and
single-purpose. No new function in `webapp.py`, `cli.py`, `store.py`, or
`frontmatter.py` may exceed the complexity threshold of 15.

### Target adapter

**[SPEC]** `source_update.py` must resolve targets through `scopes.scan_scope()`
or a narrow new module-level helper in `scopes.py`. It must not duplicate the
scope catalog or construct agent roots from hard-coded home-directory strings.

If a narrow reusable helper is added to `scopes.py`, it is not a new Store
method and should return an evidence record, not mutate anything. The helper
must use the current injected global Store so custom `--data-dir` and web-server
instances stay isolated.

### Error translation

**[SPEC]** Domain code raises `SourceUpdateError`. CLI and web adapters translate
it to `StoreError` or their existing clean error path. Error strings must be
actionable but must not disclose staged private paths, Python representations,
or raw OS tracebacks.

Stable error categories should include:

```text
invalid-review-id
review-not-found
review-expired
review-not-pending
review-candidate-changed
target-not-found
target-ambiguous
target-mismatch
target-changed
target-not-writable
candidate-invalid
candidate-unsafe
candidate-no-change
snapshot-not-found
snapshot-unavailable
approval-required
commit-failed
committed-with-warning
```

Expose `code` in JSON responses while retaining readable `error` text. Existing
unrelated error response shapes must remain compatible.

## CLI contract

**[SPEC]** After explicit owner approval, add one top-level command with three
subcommands:

```text
skills-mgr update preview NAME (--from DIR | --snapshot SNAPSHOT_ID)
    [--scope SCOPE] [--target-path PATH] [--json]

skills-mgr update apply NAME REVIEW_ID
    [--scope SCOPE] [--target-path PATH] --yes [--json]

skills-mgr update snapshots NAME
    [--scope SCOPE] [--target-path PATH] [--json]
```

Rules:

- Default scope is `global`.
- `--from` and `--snapshot` are mutually exclusive and exactly one is required.
- `--scope all` is rejected.
- `--yes` is mandatory for apply and means only that the displayed review was
  approved; it is not a trust or safety claim.
- Apply does not accept another source directory.
- Preview never prompts and never mutates the target.
- Text output sanitizes untrusted source, validation, risk, and diff text before
  terminal display.
- JSON emits the structured evidence unchanged.
- A blocked/no-change preview exits 1 only for unsafe/unreadable input; a valid
  no-change comparison exits 0 and reports `review_state: no-change`.
- Stale/expired/replayed apply exits 1 and leaves target bytes unchanged.
- Snapshot listing exits 0 with an empty list when none exist.

Human-readable preview order:

1. Target name, scope, and path.
2. Source kind and value.
3. Review state and expiry.
4. Current/candidate hashes and file summary.
5. Activation-state preservation.
6. Validation errors and warnings.
7. Advisory risk findings with policy label.
8. File changes and bounded diffs.
9. Exact apply command using the returned review id.

JSON preview top-level keys:

```text
review_id
review_expires_at
review_state
target
source
current_hash
candidate_hash
comparison
validation
risk
activation_preserved
resulting_disabled
snapshot_required_before_commit
commit_allowed
staged
```

`staged` is true for the outer durable review, while the embedded source-lock
preview remains truthful about its own preparation state. Do not overwrite or
misrepresent the existing source-lock response; compose a public update-review
response around it.

## REST API contract

**[SPEC]** Add the following local API surface:

| Method | Path | Input | Result |
|---|---|---|---|
| POST | `/api/source-updates/reviews` | `multipart/form-data`: `name`, `scope`, optional `target_path`, and directory files | Creates local-candidate review |
| POST | `/api/source-updates/reviews/from-snapshot` | JSON `{name, scope, target_path?, snapshot_id}` | Creates rollback review |
| GET | `/api/source-updates/reviews/<review_id>` | None | Public pending-review evidence |
| POST | `/api/source-updates/reviews/<review_id>/commit` | JSON `{name, scope, target_path?, approve: true}` | Applies reviewed candidate |
| DELETE | `/api/source-updates/reviews/<review_id>` | None | Cancels pending review and removes its staging directory |
| GET | `/api/source-updates/snapshots?name=&scope=&target_path=` | Query | Lists retained snapshots for exact target |

HTTP behavior:

- `201` for a newly persisted pending review.
- `200` for no-change/blocked preview evidence, review reads, commit success,
  cancellation, and snapshot listing.
- `400` for malformed fields, invalid candidates, approval omission, ambiguity,
  stale target, expired/replayed review, or unavailable snapshot.
- `404` for an unknown target, review, or snapshot.
- `409` for a valid review whose target changed after review.
- `413` for body/part/count/preview-artifact limits.
- `415` when a JSON endpoint receives the wrong content type.

Do not put absolute target paths into query strings when the target is
unambiguous. When `target_path` is required for a recursive duplicate, the UI
may use the query parameter for snapshot listing because the server is
loopback-only, but all responses must retain `Cache-Control: no-store`.

The multipart parser must accept both `SKILL.md` and `SKILL.md.disabled`, retain
relative paths, enforce the existing upload part/body bounds, and require
exactly one skill root. A multi-skill upload is rejected rather than partially
processed.

Route implementation must use a dedicated small dispatcher such as
`_route_source_updates()` and must not materially increase the already-high
complexity of `_route_get`, `_route_post`, or `_route_delete`.

## Web UI contract

**[SPEC]** Add an **Update from folder** action for an exact Library instance
and a **Source snapshots** section in Recovery.

### Entry and target context

- The action is available only when the selected record is addressable and its
  root is writable.
- The modal freezes `{name, scope, physical_path}` when opened, following the
  existing batch-dialog exact-target pattern.
- Changing Library selection while the modal is open cannot retarget it.
- The modal always displays target name, scope, consumer, physical path, and
  current active/disabled state.

### Review step

- Use a directory input (`webkitdirectory`) and multipart upload.
- Explain that files are copied into a private expiring review before apply.
- Display separate sections for target/source identity, changes, validity,
  advisory risk, and recovery policy.
- Show added, removed, changed, line-ending-only, binary, and truncated states
  without relying on color alone.
- Render diff content as text, never `v-html`.
- Collapse large per-file diffs but keep file status and hashes visible.
- A validation error disables apply.
- Risk findings do not automatically disable apply and are labelled advisory.
- A no-change result offers no apply action.
- The primary apply control is labelled **Apply reviewed update**.
- Require an unchecked confirmation control reading: `I reviewed the target,
  file changes, validation, and recovery snapshot policy.`
- Closing the modal offers to cancel a pending review; cancellation failure is
  reported but does not lie about cleanup.

### Success and recovery

- Success displays the resulting instance, source-lock state, and opaque
  snapshot id.
- Refresh Library, Quality, and Recovery data after success.
- Provide **Review rollback** beside a retained snapshot.
- Review rollback opens the same review UI and shows the reverse diff.
- Never label rollback instantaneous or guaranteed; it is another validated,
  snapshot-backed update.

### Accessibility and responsive behavior

- Dialog has an accessible name, initial focus, focus restoration, Escape
  behavior, and keyboard-reachable file/diff controls.
- Status changes use the existing live-announcement mechanism.
- Every input has a stable `id` or `name` and an associated label.
- Validation, risk, change type, truncation, and success are understandable
  without color.
- At 320 and 400 pixels, action buttons remain reachable and diff text scrolls
  inside its own region without page-level horizontal overflow.
- Reduced-motion and both themes continue to work.

Do not add a new top-level navigation destination. Reuse the selected-skill
action surface and Recovery center to avoid expanding navigation.

## Internal sequencing and concurrency

**[SPEC]** Use this lock order everywhere:

```text
review artifact lock
  -> source_lock target mutation lock
  -> global Store index lock during post-commit resync
```

Never acquire these in the reverse order. Preparation does not need the target
mutation lock because apply rechecks the target hash under that lock.

Two processes applying the same review must produce exactly one successful
commit. The loser returns `review-not-pending` or equivalent and performs no
target mutation. Two different reviews against the same original target may be
prepared; after one commits, the other must fail stale-target revalidation.

Cancellation and apply race on the review artifact lock. Whichever wins first
determines the final state; the other performs no target mutation or unsafe
deletion.

## Failure semantics

**[SPEC]** Every failure point has an explicit result:

| Failure | Required outcome |
|---|---|
| Source disappears while preparing | No persistent review; target unchanged |
| Candidate contains symlink or unsafe path | Fail closed; target unchanged |
| Review artifact write fails | Remove partial review directory; target unchanged |
| Target changes after review | Return conflict/stale error; target unchanged; review stays pending for inspection/cancel |
| Snapshot creation fails | Target unchanged; review remains pending |
| Candidate staging/swap fails before replacement | Restore original target; review remains pending |
| Target replacement succeeds but review status write fails | Report committed-with-warning with snapshot/recovery guidance |
| Global resync fails after filesystem commit | Report committed-with-warning; do not roll back a valid filesystem commit solely for index failure |
| Snapshot pruning fails | Commit remains successful with warning; newest snapshot is not deleted |
| UI refresh fails after successful commit | Preserve success message and snapshot id; offer Retry refresh |

Never convert a partial or post-commit warning into a generic `500 internal
error` that conceals whether the filesystem changed.

## Expected file changes

**[SPEC]** The implementation should touch the following areas. Keep deviations
small and document why they were necessary.

### Create

- `skillsmgr/source_update.py` — target resolution, review persistence,
  candidate normalization, commit orchestration, snapshot listing, cleanup.
- `tests/test_source_update_contracts.py` — hermetic domain and concurrency
  contracts.

### Modify

- `skillsmgr/source_lock.py` — total diff bound/truncation evidence and only the
  smallest reusable hardening needed by the service.
- `tests/test_source_lock_contracts.py` — total diff bounds and unchanged
  existing semantics.
- `skillsmgr/web_upload.py` — reusable single-skill staging/validation callback,
  without regressing existing folder import.
- `skillsmgr/cli_parser.py` — approved `update` command and subcommands.
- `skillsmgr/cli_handlers.py` — thin source-update handlers and sanitized text
  rendering.
- `skillsmgr/cli.py` — stable adapter exports/imports only.
- `skillsmgr/webapp.py` — isolated REST dispatch and error/status translation.
- `skillsmgr/webui/app.js` — modal state/actions and Recovery integration.
- `skillsmgr/webui/index.html` — accessible update review and snapshot UI.
- `skillsmgr/webui/styles.css` — only feature-specific responsive/diff styles.
- `tests/test_cli_contract.py` — parser, text, JSON, error, and help contracts.
- `tests/test_webapp.py` and/or `tests/test_web_scopes.py` — REST behavior and
  exact target resolution.
- `tests/test_web_client_contracts.py` — request-shape/client behavior.
- `tests/test_webui_contracts.py` — source-level accessibility and UI contract.
- `smoke_web.py` — one complete preview/apply/snapshot/rollback-preview smoke
  journey.
- `docs/02-modules.md` — new module inventory.
- `docs/03-cli-surface.md` — exact command/flags/exit behavior and updated
  command counts.
- `docs/08-web-ui.md` — endpoints, state, actions, and feature behavior.
- `docs/ADR-008-source-lock-and-update-preview.md` — record the approved caller
  surface and durable review decision; bump version.
- `docs/SESSION-CONTEXT.md` — file inventory, commands, and gotchas.
- `README.md` — concise safe-update capability and example after verification.
- `task.md` and `docs/06-progress-log.md` — phased progress and final evidence.

### Do not modify unless a discovered defect requires it

- SQLite schema or `SCHEMA_VERSION`.
- `Store` public API.
- Registry network behavior.
- `backup_sync.py` or bundle semantics.
- Build dependencies or runtime dependency metadata.

## Implementation phases

### Phase 0 preflight and approval

**[SPEC]** Before editing:

1. Read the files named in the AI manifest and the current diff of every file
   this plan expects to modify.
2. Confirm no other writer is mid-turn on those paths.
3. Preserve current uncommitted changes; do not reset, checkout, or stash them.
4. Obtain explicit approval for the new `update` command.
5. Add a task section marked in progress and a progress-log entry.
6. Run the current focused source-lock tests to establish the starting point.

Phase gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_source_lock_contracts
```

### Phase 1 bounded source-lock evidence

**[SPEC]** Add the total diff budget and explicit truncation fields without
changing successful review/apply behavior. Test binary files, many changed
files, one very large text diff, line-ending-only changes, and deterministic
ordering.

Phase gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_source_lock_contracts
```

### Phase 2 source-update service

**[SPEC]** Implement exact target resolution, private candidate staging,
activation preservation, review persistence/expiry/cancel/read, apply,
snapshot retention/listing, and rollback preparation. Keep all target mutation
delegated to `source_lock.commit_local_update()`.

Phase gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_source_lock_contracts \
  tests.test_source_update_contracts \
  tests.test_scope_contracts \
  tests.test_concurrency_contracts
```

### Phase 3 approved CLI surface

**[SPEC]** Add parser and thin handlers only after Phase 2 is green. Test help,
mutual exclusion, required approval, global and agent scopes, recursive target
ambiguity, JSON stability, sanitized text, no-change, blocked, stale, expired,
replayed, apply success, snapshot listing, and rollback preview.

Phase gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_cli_contract \
  tests.test_source_update_contracts
python3 -m skillsmgr update --help
```

### Phase 4 REST and upload surface

**[SPEC]** Add isolated routes and reuse a generalized bounded single-skill
upload helper. Cover content types, body limits, multipart filename edge cases,
exact instance selection, HTTP status mapping, cancel/apply races, and security
headers.

Phase gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_webapp \
  tests.test_web_scopes \
  tests.test_web_client_contracts \
  tests.test_source_update_contracts
python3 smoke_web.py
```

### Phase 5 web UI and Recovery integration

**[SPEC]** Add the exact-target update dialog, evidence display, approval
control, success/recovery behavior, snapshot listing, and rollback preview.
Keep code split into small methods and avoid growing unrelated modal logic.

Phase gate:

```bash
node --check skillsmgr/webui/app.js
node --check skillsmgr/webui/domain.js
node --check skillsmgr/webui/preferences.js
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_webui_contracts \
  tests.test_web_client_contracts \
  tests.test_webapp
python3 browser_harness.py
```

The browser run must exercise active and disabled targets, validation-blocked
preview, successful apply, snapshot visibility, and rollback preview at desktop
and mobile widths. Capture evidence only after the current tree passes.

### Phase 6 documentation and full verification

**[SPEC]** Update every surface document, remove stale source-lock statements
that say no caller exists, and record exact final evidence. Do not claim a test
passed based on an earlier tree.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
python3 smoke_store.py
python3 smoke_web.py
node --check skillsmgr/webui/app.js
node --check skillsmgr/webui/domain.js
node --check skillsmgr/webui/preferences.js
PYTHONDONTWRITEBYTECODE=1 python3 check_docs.py
PYTHONDONTWRITEBYTECODE=1 python3 check_complexity.py
PYTHONDONTWRITEBYTECODE=1 python3 check_package_data.py
python3 browser_harness.py
git diff --check
```

Build wheel and source archive using the pinned hash-verified toolchain and run
the package-data checker against both artifacts. If optional tooling is absent,
install only from `requirements-build.txt` with `--require-hashes` in a temporary
environment.

## Test strategy

**[SPEC]** Tests must prove behavior, failure recovery, and boundary safety. A
happy-path REST test alone is insufficient.

### Domain unit and contract cases

- Prepare creates a private pending review and does not change target bytes.
- Candidate is copied; editing the original source after preview does not change
  the staged candidate or commit result.
- Editing the staged candidate is detected before apply.
- Active target remains active when candidate supplied `SKILL.md.disabled`.
- Disabled target remains disabled when candidate supplied `SKILL.md`.
- Candidate with both primary documents is rejected.
- Candidate manager sidecars are stripped and replaced by manager-created
  source-lock evidence.
- Symlink file, symlink directory, path escape, excessive depth/count/bytes,
  invalid UTF-8 primary document, and missing document fail closed.
- Invalid frontmatter creates blocked preview and no reusable pending review.
- No-change preview creates no reusable pending review.
- Added/removed/changed/binary/line-ending-only files are classified correctly.
- Per-file and total diff truncation are deterministic and explicitly flagged.
- Ambiguous recursive-scope target requires exact observed path.
- Supplied unobserved target path is rejected.
- Unknown/missing/unwritable scope or target returns stable error code.
- Review file and directory permissions are private where supported.
- Credential-bearing source identity is rejected.
- Expired, malformed, oversized, symlinked, committed, and cancelled reviews
  cannot be applied.
- Target change after review is rejected without mutation.
- Candidate change after review is rejected without mutation.
- Apply without explicit approval is rejected.
- Successful apply creates source lock and complete snapshot.
- Global apply resyncs the index; agent-scope apply never creates a DB row.
- Snapshot listing is contained, ordered, and degrades per unreadable snapshot.
- Retention keeps newest five without pruning active rollback material.
- Snapshot rollback preparation returns reverse diff.
- Applying rollback creates another recovery snapshot.

### Failure-injection cases

- Review JSON write failure removes partial staging.
- Snapshot copy failure leaves target byte-for-byte unchanged.
- Staged replacement failure restores the original target.
- Review status write failure after commit reports committed-with-warning.
- Global resync failure after commit reports committed-with-warning and leaves
  the filesystem authoritative.
- Snapshot pruning failure reports a warning without reversing a valid commit.
- Cleanup failure does not block reading/applying an otherwise valid review.

Use mocks only at filesystem failure boundaries. Normal behavior should use
real temporary directories and real files.

### Concurrency cases

- Two threads/processes apply the same review: one success, one no-op error.
- Two reviews against the same original target: first success, second stale.
- Cancel races apply: exactly one final state and no partial target.
- Source-update apply racing ordinary edit/toggle/remove respects existing
  target mutation locks and never produces both primary documents.
- Global apply plus concurrent list/search never exposes a traceback or a
  permanently stale index.

### CLI cases

- Help and parser shape.
- Missing or conflicting preview source flags.
- `scope=all` refusal.
- Apply without `--yes` refusal.
- Text sanitization for terminal control characters in candidate content.
- Stable JSON keys for preview, apply, list, and errors.
- Exit codes for success, no-change, blocked, stale, expired, and replayed.
- Custom `--data-dir` isolation.

### REST security and contract cases

- Host and Origin rejection on every new route.
- `Cache-Control: no-store` and existing security headers.
- JSON/multipart content-type enforcement.
- Request body, part count, file count, and review JSON bounds.
- Encoded slashes, NULs, traversal, RFC 2231 filenames, file/directory name
  collisions, and literal multipart-boundary bytes inside content.
- Multi-skill upload rejection with no partial review.
- Unknown route and wrong method behavior.
- No staged filesystem path in public responses.
- No raw exception or credential leakage.

### UI and browser cases

- Action availability follows addressable/writable evidence.
- Frozen exact target survives Library selection changes.
- Directory selection and review request.
- Blocked/no-change/applicable states.
- Risk and validation displayed separately.
- Apply disabled until explicit confirmation.
- Diff text is escaped and cannot execute markup.
- Successful apply refreshes Library, Quality, and Recovery.
- Snapshot listing and rollback preview.
- Keyboard focus entry/exit, Escape, labels, live announcements, reduced motion,
  dark theme, large text, and 320px layout.
- No console errors, request failures, or horizontal page overflow.

## Acceptance criteria

**[SPEC]** Every item must be demonstrated by automated evidence unless marked
manual.

- [x] SU-01: Preview targets exactly one currently observed physical instance (`tests/test_source_update_contracts.py`).
- [x] SU-02: Candidate bytes are copied into a private expiring review before
  preview is returned.
- [x] SU-03: Apply uses only the staged reviewed candidate.
- [x] SU-04: Enabled/disabled target state is preserved.
- [x] SU-05: Candidate validation blocks structurally invalid updates.
- [x] SU-06: Advisory risk findings remain distinct from validity and trust.
- [x] SU-07: Whole-tree diff covers additions, removals, changes, binary files,
  and line-ending-only changes with deterministic bounds.
- [x] SU-08: Changed target or candidate makes the review stale and prevents
  mutation.
- [x] SU-09: Apply requires explicit approval and is single-use.
- [x] SU-10: Every successful apply creates a complete retained recovery
  snapshot before replacement.
- [x] SU-11: Replacement is atomic or restores the original target.
- [x] SU-12: Rollback uses the same preview/apply pipeline and is itself
  reversible.
- [x] SU-13: Global index reconciliation occurs only after filesystem success;
  non-global scopes remain DB-free.
- [x] SU-14: CLI text and JSON behavior match the documented contract.
- [x] SU-15: REST statuses, content types, limits, security headers, and error
  shapes match the documented contract.
- [x] SU-16: UI exposes exact target, diff, validation, risk, approval, result,
  snapshots, and rollback preview accessibly.
- [x] SU-17: Two concurrent applies cannot both commit the same review.
- [x] SU-18: No credential, private staged path, traceback, or unescaped HTML is
  exposed.
- [x] SU-19: No runtime dependency, build step, schema change, or public Store
  method is introduced.
- [?] SU-20: All focused tests, full suite, smoke checks, docs/complexity/package
  gates, browser harness, package builds, and `git diff --check` pass on the
  final tree. All available checks pass on the final tree; `check_package_data.py`
  passes its integrity checks but reports the optional `python3 -m build` tool as
  unavailable in this environment.
- [x] SU-21: CLI/API/module/UI docs, task tracking, and progress evidence reflect
  the shipped behavior without overstating network or trust capabilities.
- [?] SU-22: Manual review confirms mobile/desktop readability and that a user
  can identify the exact target, changed files, blocking errors, advisory risks,
  and recovery action before apply. Automated UI contracts and the responsive
  browser harness pass; a human visual sign-off remains an explicit follow-up.

## Definition of done

**[SPEC]** The feature is done only when:

1. The owner-approved public CLI surface is implemented exactly as documented.
2. All acceptance criteria are checked with references to tests or manual
   evidence.
3. No old source-lock, CLI-count, REST, module-inventory, or README statement is
   stale.
4. No pre-existing working-tree change has been overwritten or reverted.
5. The final full verification ladder is green on the current tree.
6. The wheel and source archive contain the new module and updated web assets,
   but no tests, docs, databases, review artifacts, snapshots, or bytecode.
7. A clean temporary data directory can complete preview, apply, snapshot list,
   rollback preview, and rollback apply through both CLI and browser-backed REST
   paths.
8. `docs/06-progress-log.md` records exact commands, counts, and any explicitly
   unavailable optional check.

## Implementation cautions for Luna Max

**[SPEC]** During implementation:

- Use `apply_patch` for source edits.
- Do not run destructive Git commands.
- Do not hand-edit SQLite.
- Do not broaden filesystem allowlists to make a test pass.
- Do not use `except Exception` around a mutation to conceal the changed state.
- Do not import a private Store helper when a module-level safe seam exists.
- Do not couple review correctness to browser state; the backend owns every
  invariant.
- Do not trust the name/scope/path returned by the client; re-resolve it.
- Do not reuse registry `trust_confirmed` wording. Local review approval is not
  publisher trust.
- Do not claim source authentication for a local directory.
- Do not display full candidate content when the diff budget is exceeded.
- Do not update complexity baselines merely to permit a regression. New
  functions must remain at or below the threshold; decompose route/handler
  logic.
- If a pre-existing gate fails, record and isolate it, but still prove the
  feature did not introduce additional failures.
- If another writer changes a touched file, stop and reconcile rather than
  overwriting it.

## Open decisions

**[?]** Owner approval is required for the exact `update` CLI command and its
three subcommands. No other product decision should be needed to begin.

If implementation reveals that the current scope layer cannot resolve an exact
recursive instance without a new public Store method or schema change, stop and
request approval. Do not weaken exact-target binding as a workaround.
