# ADR-007 — Adapter Catalog and Project Workspaces

**Version 1.0.0**

**AI manifest:** Decision record for DEL-06 consumer adapter evidence,
project-root observations, precedence disclosure, and deployment-preview
boundaries.

## Status

Accepted — September 18, 2026. The first implementation is deliberately
read-only and derived from the existing consumer/root inventory.

## Context

Users need to understand which agents may discover a skill, which roots are
candidate locations, how reload works, and where precedence is known or
unknown. The existing scope facade and `effective.py` diagnostic already
contain the compatibility and primary-source vocabulary, but introducing a
persisted binding or an effective winner would exceed the approved model in
@docs/ADR-002-root-consumer-effective-state.md.

## Decision

### Adapter records

`skillsmgr.adapters.catalog()` derives a record for every consumer in
`effective.CONSUMERS`. Each record contains:

- stable id and label;
- candidate roots, tier labels, recursion/nested observations, and platform
  availability guidance;
- a tier of `verified` for documented ordered precedence or `experimental`
  otherwise;
- precedence policy, evidence URL, notes, and an explicit
  `unknown-precedence` status where the primary source does not document an
  order;
- reload guidance and the last verification date.

The evidence URLs and root vocabulary remain sourced from
@docs/12-agent-root-discovery-2026-09-08.md and the existing effective-state
inventory. An undocumented order is displayed as unknown; the manager never
invents a winner, deployment target, or reload guarantee.

### Project observations

`GET /api/workspaces?project=DIR` optionally observes a project only after
resolved-path containment succeeds against the server's managed roots. It
returns `not-requested`, `missing`, `inaccessible`, `outside-managed-roots`, or
`accepted`, plus known project skill-root candidates. Outside paths are
redacted and are not walked. The endpoint makes no project directory, copy,
delete, or deployment mutation.

The current deployment UI is therefore an evidence and planning surface: it
shows adapter roots, precedence status, reload notes, and project candidates.
It does not create project bindings, delete projects, or claim that all
candidate roots are loadable on every platform. Any future deployment action
must first define containment, precedence, lifecycle, and rollback rules in a
new approved decision.

## Consequences

The UI can explain verified versus experimental adapters and make uncertainty
visible without changing the current compatibility API. Project paths are
safe to inspect within the configured boundary, while hostile or unrelated
paths cannot be used as a filesystem oracle. The catalog is derived at read
time, so it follows source documentation changes and has no stale database
state; conversely, it is not a deployment engine.

## Verification

`tests/test_catalog_contracts.py` covers primary-source evidence, explicit
unknown precedence, root containment, redaction, and the REST payload. The
five-viewport browser harness verifies the rendered workspace surface without
console errors or horizontal overflow. See @docs/06-progress-log.md.
