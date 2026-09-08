# ADR-002 — Physical Roots, Consumers, and Effective Skill State

**Version 1.0.0**

**AI manifest:** Proposed domain vocabulary and discovery policy for separating
physical skill roots from the agents that consume them. This ADR deliberately
does not add runtime entities, SQLite columns, CLI commands, or Store methods.

## Status

Accepted as a design constraint and research baseline — September 8, 2026.
Runtime data-model introduction remains approval-gated under `AGENTS.md`.

## Context

The current compatibility facade exposes `Scope(id, label, base, kind,
writable)`. That is useful for existing CLI/UI behavior, but it combines several
different concepts:

- a physical directory on disk;
- an agent or consumer that reads that directory;
- a binding between a consumer and a root with precedence;
- one discovered copy of a skill;
- the skill that wins after precedence is applied.

The distinction matters when two scope ids resolve to one directory, when a
consumer searches parent and nested project roots, or when two copies have the
same name but different content.

## Proposed vocabulary

### `SkillRoot`

A physical directory that can contain skill instances. A root has a resolved
path identity, scope kind (`global`, `user`, `project`, or `nested-project`),
read/write capability, discovery status, and an observed timestamp.

### `Consumer`

An agent product that discovers and loads skills, such as Claude Code, Cursor,
Gemini CLI, OpenCode, Codex, Command Code, or the generic Agent Skills
compatibility consumer.

### `ConsumerRootBinding`

A consumer-specific relationship to a `SkillRoot`. It records precedence,
whether discovery is recursive, how reload occurs, and any client-specific
metadata. A binding is not itself a filesystem directory.

### `SkillInstance`

One discovered skill directory/file under one physical root. It carries the
skill name, source root, enabled/disabled state, content and metadata hashes,
validation findings, and provenance observations.

### `EffectiveSkill`

The winning `SkillInstance` for a `(Consumer, Project, SkillName)` resolution.
It may explain shadowed, divergent, invalid, disabled, unmanaged, or missing
lower-precedence instances without mutating them.

## Invariants

1. Physical root identity is `Path.resolve()` plus a stable, platform-aware path
   comparison; aliases and symlinks do not create a second root for aggregate
   counts or sync planning.
2. A consumer binding owns discovery and precedence facts; a root does not claim
   that every consumer reads it.
3. A skill instance is observed filesystem state, not a new source of truth.
4. Effective resolution is derived and repairable; it is not persisted in the
   current SQLite schema.
5. Unknown consumer metadata survives observation and round trips.
6. Any write must target one resolved physical root exactly once.

## Current compatibility implementation

Until the model receives maintainer approval, the existing `Scope` facade remains
the public API. The safe subset implemented now is:

- Cursor uses the current user root `~/.cursor/skills`.
- Aggregate scope listings deduplicate resolved physical roots while retaining
  scope ids for direct compatibility lookups.
- Default sync expansion and explicit sync targets avoid repeated physical roots.
- Global, user, project, and nested-project semantics are documented but not
  exposed as new runtime entities.
- Compatibility records expose observed instance states (`active`, `disabled`,
  `invalid`, `duplicated`, `divergent`, `unmanaged`) and explicitly return
  `effective_state: unresolved`; `shadowed` is not inferred without precedence.

## Approval required before runtime expansion

Adding consumer bindings, effective resolution, precedence-aware APIs, persisted
hash/provenance state, or new CLI/UI surfaces requires a maintainer-approved
issue/ADR because those changes alter the data model and user-visible contract.
