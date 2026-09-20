# ADR-008 — Read-only Source Locks and Update Preview

**Version 1.1.0**

**AI manifest:** Decision record for DEL-07 source locks. It defines the
filesystem-owned evidence boundary and the review-first local update operation
without adding SQLite state or a new public Store method.

## Status

Accepted — September 20, 2026. The live workflow is implemented as an explicit
prepare/review → snapshot/apply → rollback seam in `source_lock.py`. It remains
caller-driven: no background update, network fetch, or implicit approval exists.

## Decision

`skillsmgr.source_lock` owns a bounded, stdlib-only inspection seam:

- local candidates are represented by a canonical regular-file manifest,
  SHA-256 file hashes, a framed whole-tree digest, and explicit source identity;
- manager provenance sidecars remain the existing filesystem-owned registry
  format. This module excludes the sidecar from candidate content so registry
  evidence cannot become candidate skill content;
- traversal, symlink, file-count, path-depth, per-file, and total-size limits
  fail closed before a preview is produced;
- comparisons include added, removed, and changed files. Raw hashes/sizes stay
  visible; CRLF/LF-only changes are identified separately and never conceal a
  non-line-ending change;
- candidate validation runs before readiness is reported. `risk_scan()` findings
  remain advisory and heuristic, not a safety, malware, or trust verdict;
- every preview requires an explicit physical target record. The preview is
  always `commit_allowed: false`, `staged: false`, and reports whether a future
  snapshot would be required.

Source states are deliberately explicit: `local-only`, `known-verified`,
`known-unverified`, `changed`, `missing`, and `inaccessible`. A URL or registry
identifier alone never upgrades a source to verified or current, and source
identities reject credentials, query strings, and fragments.

## Consequences

The filesystem-owned `.skillsmgr-source-lock.json` sidecar records a bounded
source identity, candidate content digest, explicit physical target, review
timestamp/state, and review id. It is excluded from candidate content hashes
and is written atomically with owner-only permissions. `review_local_update()`
returns a stale-detecting review id without mutating the target.
`commit_local_update()` requires that id, `approve=True`, and an explicit
snapshot root; it re-reviews under the cross-process mutation lock, snapshots
the complete current tree, atomically swaps the candidate tree into place, and
returns a rollback path. `restore_source_snapshot()` requires a separate
explicit approval.

The workflow still adds no CLI command, Store method, SQLite column/schema
value, network request, cache write, or REST mutation. Callers can use the
module seam from a future review UI without weakening the filesystem source of
truth.

The preview and sidecar are not a source-authentication service. Local, Git,
archive, and registry identity values are accepted as bounded evidence; a
`known-verified` state is caller-supplied evidence tied to a digest, not a
claim that the source is safe. Existing registry sidecars retain their own
verified remote hash semantics.

## Verification

`tests/test_source_lock_contracts.py` covers identity validation, sidecar
exclusion, whole-tree additions/removals, line-ending-only versus real changes,
missing and symlinked sources, validation blocking, advisory risk evidence,
review staleness, atomic snapshot/apply, sidecar persistence, and explicit
rollback.
