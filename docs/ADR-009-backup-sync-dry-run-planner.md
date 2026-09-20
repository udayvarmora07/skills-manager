# ADR-009 — Backup and Sync Dry-Run Planner

**Version 1.1.0**

**AI manifest:** Decision record for the DEL-09 backup/sync alpha. It defines
bounded manifests, Git delegation, credential-free review artifacts, and
explicit snapshot-backed apply without adding a CLI or Store surface.

## Status

Accepted — September 19, 2026, for planning; Git/fetch/review/apply integration
added September 20, 2026. The workflow remains caller-driven and has no
implicit approval or background sync.

## Decision

`skillsmgr.backup_sync` owns bounded, deterministic planning over caller-owned
manifests:

- manifests contain sorted canonical skill names, SHA-256 content/metadata
  digests, optional bounded file members, a source label, and an explicit
  credential-redacted marker;
- source labels reject credentials, query strings, fragments, NUL bytes, and
  oversized values; file paths reject absolute, traversal, and backslash forms;
- `dry_run()` reports exact local changes, remote changes, and three-way
  conflicts without choosing a write operation;
- `three_way_plan()` defaults to review for true conflicts. Explicit
  keep-mine, use-remote, and keep-both strategies are reported as plans only;
- keep-both names are canonical and bounded, and remote deletion always calls
  for explicit recovery approval;
- interrupted operations return completed/pending work and a snapshot handle,
  marked retryable while asserting no local filesystem mutation occurred.
- `git_remote_info()` and `git_fetch()` delegate authentication to the user's
  configured Git credential helper or SSH agent. No token argument is accepted,
  Git terminal prompting is disabled, remote URLs with embedded credentials are
  rejected, and returned metadata is credential-redacted.
- `prepare_sync_review()` stores the bounded manifests, explicit target,
  candidate digest, Git revision evidence, and deterministic three-way plan in
  a private expiring `<data>/sync-reviews/` artifact. `commit_sync_review()`
  requires a fresh review, unchanged candidate digest, explicit containment,
  `approve=True`, and an explicit snapshot root; it applies through the
  existing source-lock atomic replacement and marks the review single-use.

## Consequences

The pure planner remains safe to exercise without a repository. The optional
integration invokes the local Git executable for an explicitly requested fetch,
but never passes or persists credentials. Review artifacts are owner-only and
expire after 24 hours; apply is disabled until the candidate, target, plan, and
snapshot requirements are revalidated. No Store method, SQLite state, or CLI
command is added; managed-tree mutation is routed through the existing
filesystem source-lock seam.

The planner does not claim merge correctness for file contents beyond the
manifest decisions supplied by its caller. A future apply layer must verify a
fresh snapshot, re-read the filesystem, and require an explicit target and
recovery decision before any remote deletion or local replacement.

## Verification

`tests/test_backup_sync_contracts.py` covers canonical ordering, credential
redaction, exact dry-run changes/conflicts, non-destructive strategies,
retryable interruption state, fail-closed names/paths/strategies, local Git
remote/fetch delegation, private review artifacts, revalidation, snapshot-
backed apply, and single-use commit behavior.
