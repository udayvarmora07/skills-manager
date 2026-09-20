# ADR-006 — Catalog Metadata and Previewable Batch Plans

**Version 1.0.0**

**AI manifest:** Decision record for manager-owned tags, profiles, full archive
round trips, and bounded multi-instance batch operations delivered by DEL-05.

## Status

Accepted — September 18, 2026. This decision adds organization metadata and
previewable UI operations without changing the skill document authority,
SQLite schema, CLI surface, or `Store` public API.

## Context

The filesystem remains the source of truth for skill content and enabled state,
but users need lightweight organization that is not frontmatter: tags,
saved target profiles, and operations over a selected set of physical
instances. A batch action must remain reviewable when the same logical name is
present in several scopes or when aliases resolve to one path.

## Decision

### Metadata home and shape

Manager-owned metadata lives in the filesystem sidecar
`<data>/skills-manager/catalog/metadata.json`. It is versioned independently
of SQLite and written with the existing atomic-write and mutation-lock seams.
The current shape is:

```json
{
  "version": 1,
  "tags": {"skill-name": ["tag"]},
  "profiles": {
    "profile-name": {
      "description": "optional explanation",
      "skills": ["skill-name"],
      "targets": ["scope-or-consumer"]
    }
  }
}
```

Names are canonical skill names; tags and profile members are bounded and
normalized deterministically. Metadata never becomes a substitute for
`SKILL.md`, `SKILL.md.disabled`, or observed scope records. SQLite does not
store it and `db rebuild`/`resync` leave it untouched.

### Lifecycle and archive rules

- Full exports include `catalog/metadata.json`; full imports validate and stage
  it with the other full-archive payload before replacing the destination.
- Slim exports remain skill-content exports. Templates keep their existing
  archive layout and are not converted into profiles.
- A missing profile member is reported as `missing`; disabled-only members are
  `disabled`; unequal observed content is `divergent`; an available member is
  `observed`. These states are read-only preview facts.
- Soft trash, purge, disabled files, and rebuild do not silently rewrite or
  erase catalog entries. This preserves user intent and makes missing members
  visible until the user edits the metadata explicitly.
- There is no automatic rename propagation: a future rename must make its
  metadata policy explicit rather than guessing whether a tag/profile reference
  should follow it.

### Batch plans

The UI sends selected rows as exact `(name, scope, physical_path)` targets.
`catalog.plan_hash()` hashes those targets plus operation options. Preview
returns the exact target count, operation, options, hash, and the recovery
policy. Execute re-resolves the targets and rejects a stale plan rather than
widening the selection.

The supported operations are enable, disable, soft remove, and sync. Each
target is attempted independently, so the plan reports successes and failures
with `partial_failure: true`; it is not an all-or-nothing transaction. A
remove is reversible through the existing scope trash where that scope
supports it. Purge is deliberately not a batch operation. Sync requires an
explicit non-empty target-scope list and uses the existing scope operation.

No new CLI command or `Store` method is added. The web layer coordinates
existing `scopes` operations and never writes the SQLite index directly.

## Consequences

Users can filter tagged or untagged skills, select the visible filtered set,
review exact physical targets, save reusable profiles, and see missing or
divergent members before acting. Metadata remains portable in full archives
and independent of index rebuilds. Partial batch results are honest and
recoverable, at the cost of requiring users to review failed items when a
multi-target operation is interrupted.

## Verification

`tests/test_catalog_contracts.py` covers sidecar persistence, profile states,
full export/import, rebuild preservation, batch preview and exact-target
execution. The final current-tree ladder and browser viewport evidence are
recorded in @docs/06-progress-log.md.
