# ADR-003 — Registry Bridge (offline) and Eval Harness (file-based)

**Version 1.0.0**

**AI manifest:** Decision record for the two TODO items that were blocked on a
surface: the registry bridge (issue #3) and the eval harness (issue #4). It
records why only the offline/file-based halves ship, which existing surfaces
carry them, and what remains deferred.

## Status

Accepted — September 10, 2026, for the offline/file-based scope only. Network
fetch, registry caching and authentication, eval provider abstraction, and team
signing remain deferred under issues #3, #4, and #11.

## Context

Both items already existed as pure helpers with **no reachable surface**: no CLI
command, flag, REST route, or UI path called `skillsmgr/insights.py`.

Their research verdicts are unchanged and still binding:

- **Registry bridge (#3): DEFERRED network browse/fetch.** The skills.sh catalog
  API is real (`/api/v1/skills`, `/api/v1/skills/{source}/{skill}`,
  `/api/v1/skills/audit/{source}/{skill}`) but authenticated reads need a Vercel
  OIDC bearer token (600 req/min per team+project), which needs `vercel link` and
  a credential lifecycle — unsuitable for a local-first stdlib tool. Install is
  already delegated to the ecosystem runner, and the third-party audit surface
  (Socket/Snyk/Trust Hub) is linkable, not proxyable. The ToxicSkills audit
  (13.4% of 3,984 skills critical; 76 confirmed malicious payloads) hardens the
  deferral.
- **Eval harness (#4): ADVISORY-ONLY.** The official guide prescribes
  `evals/evals.json` plus `with_skill`/`without_skill` baselines and
  `iteration-N/eval-*/` workspaces; deterministic assertions are the stdlib-safe
  subset, and model-graded judging is measurably biased. Nothing may gate an
  install or an edit.

Locked constraints (`AGENTS.md`) still apply: stdlib only, no runtime
dependency, filesystem as the source of truth, SQLite schema frozen, and no new
CLI command or `Store` method without approval.

## Decision

### 1. Registry bridge ships the offline half only

`insights.registry_reference()` parses a registry reference offline:
`owner/repo`, `owner/repo/slug`, `https://skills.sh/{source}/{slug}`, and the
documented `installUrl` form `https://github.com/owner/repo`. Nothing is
fetched, cached, or credentialed — there is no registry request at all, and one
test pins that the bridge modules import no network client.

`insights.registry_bridge_plan()` turns that reference into the exact command
the existing `install` surface would run (adding `-s <slug>` for a skill id),
plus the linkable per-skill audit pages (`/owner/repo/skill/security/{provider}`)
and a `content_hash` slot whose documented use is detecting upstream change
without re-fetching files. Trust is an explicit gate: without
`trust_confirmed`, the plan reports a blocker and `may_install: false`.

Absent registry metadata is reported honestly rather than invented:
`description_status` and `provenance_note` say that description/installs need an
authenticated catalog read or manual entry.

### 2. Both items are surfaced by extending existing surfaces

No new CLI command and no new `Store` method:

| Item | CLI | REST |
|---|---|---|
| Registry bridge | `install --preview` (+ `--trust-confirmed`, `--registry-hash`) | `POST /api/install` with `"preview": true` |
| Eval harness | `validate --evals`, `validate --evals-run FILE` (+ `--workspace DIR`) | `POST /api/validate` with `"evals": true` and/or `"runs": [...]` |

`install` keeps its existing behavior — runner allowlist, dry-run-first,
delegation to `npx/pnpm/yarn/bunx skills add`. The preview is informational and
executes nothing. `validate` keeps its existing exit-code contract; eval
findings are advisory and never change `valid`.

### 3. The eval harness implements the official file contract

Cases live in `evals/evals.json` inside the skill directory
(`skill_name`, `evals[]` with `id`/`prompt`/`expected_output`/`files`, plus an
optional `slug` and optional deterministic `assertions`). Assertions are the
deterministic subset: `equals`, `contains`, `not_contains`, `regex`, `is_json`.
A case without assertions is recorded as ungraded — never as a pass or a fail.

Results are files, never rows:

```text
<workspace>/iteration-N/eval-<slug>/{with_skill,without_skill}/
    outputs/output.txt
    grading.json
    timing.json
<workspace>/iteration-N/benchmark.json
```

Workspace placement:

- installed skills default to `<data>/evals/<name>-workspace`, deliberately
  **outside** `skills/` so the skill scan, `doctor` orphan detection, archive
  export, and the SQLite index never see run data;
- `validate --path DIR` uses the guide's authoring layout (`<DIR>-workspace`)
  when `DIR` is outside the store's `skills/` tree — and falls back to
  `<data>/evals/<name>-workspace` when it is inside it, so a `--path` recording
  can never plant a sibling directory in the managed skills root;
- `--workspace DIR` overrides on the CLI only — REST never accepts a
  client-supplied path, so a mutating request cannot choose where files land.

### 4. One renderer for install commands

`insights.install_argv()` / `install_command_line()` are the single source for
the printed dry-run text, the executed argv, and the bridge plan, so the
preview and the real command cannot drift.

## Consequences

- Both TODO items are now usable end to end without network access, a
  third-party runtime, a schema change, or a new command.
- Eval scores are advisory by construction: no code path reads them before an
  install or an edit, and no score is persisted in SQLite.
- Registry provenance stays incomplete until an authenticated read or manual
  entry supplies it; the plan says so instead of guessing.
- Still open and requiring their own ADR/approval: registry API/caching/auth and
  provenance persistence, an eval provider abstraction with credentials and
  isolation, and signed team bundles (#11).
- `Store`, the SQLite schema, and `SCHEMA_VERSION = "1"` are untouched.

## Verification

- `tests/test_registry_bridge_contracts.py` — reference parsing, audit links,
  argv parity with the historical renderer, injection rejection, plan gates,
  no-network-import pin, `install --preview` CLI (human + JSON, clean errors,
  unchanged `--dry-run`), and the REST preview payload and legacy shape.
- `tests/test_eval_harness_contracts.py` — case loading and error reporting,
  assertion semantics, slug derivation, containment, workspace placement
  (including the store-`skills/` fallback), scoring and benchmark deltas,
  recording layout and atomicity, no skill/index mutation, the `validate` CLI
  paths, and the REST read-only/recorded shapes.
