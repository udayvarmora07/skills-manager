---
name: skills-manager-management
description: Use when asked to inspect, validate, explain, preview, or explicitly manage AI coding-agent skills with the installed skills-mgr CLI; require approval for every managed-file mutation.
---

# Manage skills with `skills-mgr`

Use this workflow when the user asks you to inspect or manage skills stored by
Skills Manager. The CLI is the control surface. Read its current contract in
the repository's `docs/03-cli-surface.md` before using an unfamiliar command.

## Boundaries

- Require Python 3.10 or newer and an installed `skills-mgr` command, or use
  `python3 -m skillsmgr` from a checkout. If neither is available, stop and
  tell the user what is missing. Never install the package or this example on
  the user's behalf.
- Work only in the data directory and exact skill scope the user names. The
  filesystem is the source of truth; SQLite is a rebuildable index. Never edit
  the database directly.
- Start with read-only inventory and diagnostics. Do not read or print raw
  skill bodies, secrets, tokens, environment values, or credentials. JSON may
  contain descriptions and local paths: inspect it locally, report only the
  minimum names/scopes/states needed, and redact paths unless the user needs
  them to confirm an exact target.
- Treat `active` or an enabled file as an observed on-disk state only. The
  ordinary `effective_state` is `unresolved`; a listed file does not prove an
  agent loaded it. Use `doctor --explain` only for its named consumer and
  project. Accept `undocumented-precedence`, `unknown-consumer`, missing roots,
  and unresolved results as unknowns; never guess a winner.
- A scan that returns an error, unavailable evidence, or any non-empty
  `degraded` list is incomplete for the affected question. You may report what
  was observed, but stop before mutations that depend on the missing evidence.

## Read-only inventory first

Run these commands before proposing an action:

```sh
skills-mgr list --scope all --json
skills-mgr doctor --scope all --hygiene --json
```

Parse JSON as data; do not copy the complete output into the conversation.
Group observations by exact `name`, then keep every `scope` and physical
instance distinct. If a name appears more than once, if an instance reports a
`divergent` state, or if Doctor/Hygiene reports degraded or unavailable
evidence, do not choose a copy or prepare a write automatically. Ask the user
which exact scope and instance they intend.

If a consumer-resolution question is part of the request, use its exact
consumer id and a user-provided project directory:

```sh
skills-mgr doctor --explain codex --project ./project --json
```

The explain command is read-only. Its output may contain local paths; keep
those private. For Cursor or OpenCode, report `undocumented-precedence` when
returned. For Codex, `no-merge` means no single winner is elected. Do not
translate either result into a guessed effective state.

After identifying one instance, validate that exact directory (the path is
read locally from the inventory and should not be pasted into the conversation
unless needed to confirm the target):

```sh
SKILL_DIR='/exact/observed/skill-directory'
skills-mgr validate --path "$SKILL_DIR" --json
```

## Safe previews

`install --dry-run` only renders the external runner command. Use a source the
user supplied; this command makes no network request and does not install:

```sh
SOURCE='owner/repo' # replace with the exact source the user requested
skills-mgr install "$SOURCE" --scope global --dry-run --json
```

The output must say `"executed": false`. Do not drop `--dry-run` or run the
printed command unless the user separately approves that exact installation.

For a local folder update, first identify one exact existing instance from the
inventory and use the candidate directory supplied by the user:

```sh
SKILL_DIR='/exact/observed/skill-directory'
TARGET_PATH="$SKILL_DIR"
skills-mgr update preview example-skill --from ./candidate \
  --scope agents --target-path "$TARGET_PATH" --json
```

Use the real `NAME`, `SCOPE`, candidate directory, and exact physical target;
the values above are placeholders. Recursive roots or duplicate names require
`--target-path`. This preview stages a private, expiring review inside the
manager data directory, but leaves the managed target and candidate unchanged.
Inspect `review_state`, target identity, hashes, file-level comparison,
validation, advisory risk findings, and recovery policy. Continue only when
the review is `pending`, the exact target matches the user's request, no
required evidence is degraded/unavailable, and the candidate has not changed.

Stop if the scope is unknown, the name is missing, the target path is missing
or ambiguous, same-name copies are divergent, any required scan is degraded,
or the review is blocked, expired, stale, or no longer matches its returned
id. Do not fall back to another scope or target. Re-run a fresh preview only
after the user confirms the intended candidate and target.

## Approval before a write

Never apply a preview based only on an earlier request to inspect or prepare
it. Before `update apply`, show the user the exact skill name, scope, target,
candidate summary, validation/risk evidence, and recovery plan, then obtain
explicit approval for that exact operation. If approved, apply only the
returned review id and exact target:

```sh
skills-mgr update apply example-skill REVIEW_ID --scope agents \
  --target-path ./skills/example-skill --yes --json
```

After success, re-read the exact scope and run Doctor again. Report whether the
target changed, the returned recovery snapshot id, and any warning. For
rollback, inspect the snapshot and create a separate
`skills-mgr update preview NAME --snapshot SNAPSHOT_ID --scope SCOPE --json`
review; require separate explicit approval before applying it.

`sync` has no dry-run flag and changes agent scope files directly. Do not
describe a sync preview, invent `sync --dry-run`, or use sync to resolve a
conflict. It requires the user's exact source scope, destination scopes, and
separate approval before any invocation.

## Manual opt-in installation

This example is not installed by the package or by this workflow. Only when
the user asks to install it into the shared Agents/Command Code scope, ask them
to review the destination and run these commands themselves from the repository
root:

```sh
mkdir -p "$HOME/.agents/skills/skills-manager-management"
cp examples/skills-manager-management/SKILL.md \
  "$HOME/.agents/skills/skills-manager-management/SKILL.md"
```

To remove that one manually installed file later:

```sh
rm "$HOME/.agents/skills/skills-manager-management/SKILL.md"
rmdir "$HOME/.agents/skills/skills-manager-management"
```

Do not copy this file to another agent scope unless the user names that exact
scope. This repository example proves only that the instructions and examples
validate locally; it does not claim agent-runtime integration.
