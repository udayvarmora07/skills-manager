# Docs Archive — Skills Manager

**Version 1.0.0**

**AI manifest**: Append-only history moved out of the live docs tree, kept
verbatim. Nothing in this directory is a current contract: every file here
describes the repository as it stood on the date its entries carry. Read
@docs/06-progress-log.md first — it holds the current digest and the entries that
stayed resident.

## What is here

| File | Entry dates | Entries | Lines | Words | Bytes |
|---|---|---|---|---|---|
| [06-progress-log-2026-09.md](06-progress-log-2026-09.md) | 2026-09-04 … 2026-09-22 | 160 | 3,069 | 31,488 | 245,934 |
| [06-progress-log-2026-08.md](06-progress-log-2026-08.md) | 2026-08-13 … 2026-08-16 (+2 undated) | 10 + 2 | 134 | 2,490 | 19,969 |

Counts are for the files as written, including their headers.

## The rule that created this directory

**[SPEC]** Adopted 2026-10-05. `docs/06-progress-log.md` was measured at
313,968 characters / 40,906 words / 4,004 lines and was injected into the context
window of every session at roughly 14.5% of a 1M-token budget before any work
started — larger than the entire MCP tool surface. The rule:

> **An entry stays in the resident log if and only if its dated heading is
> 2026-09-23 or later. Everything dated 2026-09-22 or earlier moves into
> `docs/archive/`, byte-for-byte.**

2026-09-23 is the boundary because it is where the current module set stops being
described and starts being recorded: the DEL-07…DEL-11 series from 2026-09-19
onward is the construction record for `source_lock.py`, `backup_sync.py`,
`bundles.py`, `registry.py`, `catalog.py` and `adapters.py`, all of which ship
today and each of which has its own owning HADS doc (the ADR set plus
@docs/19-safe-local-source-update-implementation-plan.md,
@docs/20-skill-hygiene-report-implementation-plan.md and
@docs/21-p0-trust-gate-and-release-metadata-hardening-plan.md).

**Why this is a lossless move, not a deletion.** Every archived entry that
describes a decision has a surviving owning doc, and the per-finding dispositions
for the 2026-09-11 audit batches live in
@docs/13-audit-remediation-status-2026-09-11.md rather than in the log entries
that recorded the fixes.

## Rules for this directory

**[SPEC]**

1. **Verbatim only.** No rewording, reordering, summarising, or reformatting of
   an archived entry. Adding a file header above the entries is allowed; changing
   an entry is not. The archived text was verified byte-identical to the source
   file at the moment of the cut.
2. **Append, never rewrite.** A correction to an archived entry is recorded in
   the resident log, with a pointer to the entry it corrects.
3. **No current claims.** Nothing here is enforced by `check_docs.py`'s
   surface-parity checks, and nothing here should be cited as how the product
   behaves now. If an archived entry disagrees with the owning doc, the owning
   doc wins.
