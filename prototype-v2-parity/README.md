# Skills Manager — remaining v2 feature designs

An isolated, clickable design study for the classic-to-v2 migration.
The production workflows are now integrated in `skillsmgr/webui/v2/`; this
folder preserves the earlier demo-only review aid. All skills, paths, findings and outcomes are sample data. It does not
call the Skills Manager API, execute commands or read/write your skills.

## Open the preview

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 prototype-v2-parity/preview.py
```

Open the full URL printed by the script, including `/prototype-v2-parity/`.
The port is selected by the OS. The server exposes only the preview files and
the existing public fonts/Vue assets, with no directory listing or application
API. It has no authentication: **the localhost binding is the only security
boundary**. Never forward, tunnel or publish the port. Stop with Ctrl+C.

No installation or build is needed. Fonts and Vue come from the repository.

## What to review

Start at Tools, then inspect Install, Profiles, Quality, Workspaces, Templates
and Settings. Skills covers exact-copy selection, tags and batch actions;
Recovery covers trash, history, source snapshots and archive modes. Preview
state controls expose examples of failures and blocked actions. Existing
Home/Sync map/Inbox screens are contextual navigation, not replacement designs.

The [design specification](../docs/superpowers/specs/2026-11-06-v2-feature-parity-design.md)
contains the source-backed parity matrix, the screen/flow requirements,
research provenance and implementation boundaries. The user subsequently directed production integration using the existing v2
design. The implementation and default-route contract are documented in
[the web UI specification](../docs/08-web-ui.md#default-v2-interface-v2).

## Limits

This preview demonstrates proposed interactions, not backend integration or
race-safety guarantees. Refresh resets in-memory examples. A simulated import
does not read an archive, and a simulated command does not execute a process.
Agent-scope trash restore remains unavailable in the real backend. Whole-tree
source-snapshot review and older text-snapshot rollback are different flows.

The production acceptance evidence is recorded in the migration plan and
progress log. This historical mockup is not the production app and makes no
claim of human visual approval or screen-reader certification.
