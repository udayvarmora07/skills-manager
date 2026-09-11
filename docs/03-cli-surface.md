# CLI Surface — Skills Manager

**Version 0.3.0**

**AI manifest**: Authoritative inventory of every command, alias, flag, and exit code of the `skills-mgr` CLI. Facts verified against `cli.py` and import behavior on 2026-09-10. The web UI must mirror this surface exactly (see @docs/08-web-ui.md). Do not add commands or flags without updating this doc and @docs/02-modules.md.

**[SPEC]** Invocation: `python3 -m skillsmgr` (or `skills-mgr` once installed). argparse `prog="skills-mgr"`. Command count: **27 top-level commands + 7 subcommands (trash/templates/db) + 3 aliases (`ls`, `rm`, `gui`) = 37 invocable names**. The `gui` alias is a pure alias of `webui` (the GTK GUI is gone).

## Exit codes

**[SPEC]**

| Code | Meaning | Raised when |
|---|---|---|
| 0 | OK | `args.func(args, store)` returns None/0 |
| 1 | Error | `StoreError`, `ValueError`, or `OSError`; message printed via `_err` |
| 2 | Usage | No subcommand given (help shown); argparse usage errors |
| 130 | Interrupted | `KeyboardInterrupt`; prints `interrupted` |

`__main__.py` wraps `cli.main()` in `sys.exit(...)`, so exit codes propagate to the shell.

Before Store construction and command dispatch, skill-name arguments are checked
against the canonical `NAME_RE` contract. Invalid names, path fragments, and
encoded traversal-style values therefore fail with exit code 1 without creating
or mutating the data directory.

## Global flags

**[SPEC]**

- `--json` — machine-readable output on all data commands; `_print_json(data)` with indent=2.
- `--color` — force color output.
- `--no-color` — disable color output. The default is automatic terminal detection.
- `--scope SCOPE` — scope selector on `list`, `view`, `search`, `doctor`, `stats`. Values: `global` (default; the Store + DB), `all` (merge every scope), or an agent scope id (`claude-code`, `codex`, `cursor`, `opencode`, `gemini`, `commandcode`, `agents`). `agents` is the Command Code skills dir (`~/.agents/skills`).

**[NOTE]** The scope flag is a **per-command flag**, not a global flag — each scope-aware command declares its own `--scope`. `tokens` and `install` also accept `--scope` with their own semantics (see below).

## Commands

**[NOTE]** `ls` and `rm` are aliases of `list` and `remove` — they are NOT separate commands. `gui` is an alias of `webui`.

### `init [--json]`
Create the data directory layout and initialize the SQLite index.

### `list` / `ls [--json] [--disabled] [--category CAT] [--scope SCOPE]`
List skills in the scope (default global) with a STATUS column (`active`/`disabled`); disabled skills are shown marked and `--disabled` narrows the list to disabled skills only. `--category` filters; `--scope all` merges every scope and adds a SCOPE column.

### `create NAME [-d/--description TEXT] [--license LIC] [--category CAT] [--compatibility SPEC] [--version VER] [--allowed-tools TOOLS] [--body TEXT] [--body-file PATH] [--json]`
Create a skill in the global store. Name must match `NAME_RE`; description required. `--body` and `--body-file` are mutually exclusive.

**[NOTE]** `create` is global-only in the CLI — agent-scope creates go through the web UI (`POST /api/skills?scope=`) or `scopes.create_skill()`.

### `add PATH [--name NAME] [--json]`
Add an existing skill directory (or SKILL.md file) from `PATH` (optional `--name` override) to the global store.

### `view NAME [--raw|--json] [--scope SCOPE]`
Print a skill. `--raw` prints the full `SKILL.md` file (frontmatter + body, not body-only); `--json` shows structured data (incl. `tokens` estimate and scope fields).

### `edit NAME [-d TEXT] [--license LIC] [--category CAT] [--compatibility SPEC] [--version VER] [--allowed-tools TOOLS] [--metadata KEY=VALUE] [--body TEXT] [--body-file PATH] [--json]`
Edit a skill in the global store. All fields optional; partial update. Repeated `--metadata` appends.

### `open NAME`
Open the skill file in `$EDITOR` (falls back if unset). Global store only.

### `remove` / `rm NAME [--purge|--trash] [--json]`
Delete a skill from the global store. Default moves to trash; `--purge` deletes permanently.

### `disable NAME [--json]` / `enable NAME [--json]`
Toggle enabled state in the global store (renames `SKILL.md` <-> `SKILL.md.disabled`).

### `validate [NAMES...] [--all] [--path DIR] [--evals] [--evals-run FILE] [--workspace DIR] [--json]`
Validate skills by name, all (`--all`), or a directory (`--path`). Prints issues.

`--evals` also reports the advisory eval harness status per target
(`evals/evals.json` case count, malformed-content errors, missing input files,
and the run workspace path). Eval findings never change `valid` or the exit
code. `--evals-run FILE` scores runs from a JSON file
(`{iteration, runs:[{case, variant, output, duration_ms?, tokens?}]}`, or a bare
run list) and records `outputs/output.txt`, `grading.json`, `timing.json`, and
`benchmark.json` in the iteration workspace; it requires exactly one target and
a valid case file. `--workspace DIR` overrides the workspace location (default
`<data>/evals/<name>-workspace`; with `--path`, `<DIR>-workspace` only when
`DIR` is outside the store's `skills/` tree, since a sibling workspace inside
`skills/` would be scanned as skill data). Eval
results are workspace files only — never SQLite rows — and never gate installs
or edits. See @docs/ADR-003-registry-bridge-and-eval-harness.md.

### `search TERM [--limit N] [--json] [--scope SCOPE]`
Search with scoring (see @docs/02-modules.md); `--limit` caps results. `--scope all` searches every scope. The global portion always uses the Store selected by `--data-dir`; merged search keeps that same requested global store while agent scopes use their filesystem adapters.

### `import ARCHIVE [--force] [--full] [--json]`
Import a `.tar.gz`/`.tgz`/`.tar` or `.zip` archive of skills into the global
store. Content is sniffed rather than trusted from the filename. Tar and ZIP
imports enforce resource budgets, reject traversal/Windows/special members, and
use a strict versioned `skills-mgr` manifest contract; `--force` overwrites
existing names with staged per-skill recovery.
`--full` restores trash and templates from a full export.

### `export [--dest PATH] [--full] [--json]`
Export all skills (global scope only) to an archive (default `backups/`).
`--full` includes trash and templates. Alias: `backup`.

### `backup [--dest PATH] [--full] [--json]`
Alias of `export` (identical behavior).

### `restore NAME [--snapshot TS] [--scope SCOPE] [--json]`
Restore a skill from the trash, or roll back to a retained snapshot.

### `history [NAME] [--limit N] [--json]`
Show recent history. When `NAME` is supplied, JSON output includes retained
snapshot IDs and text output lists them after the history table.

### `doctor [--json] [--scope SCOPE] [--explain CONSUMER [--project DIR] [--skill NAME]]`
Health check: data dir, DB, skill files, consistency between FS and index, content drift, incomplete transaction artifacts, temporary files, and stale snapshots. With a scope, checks that scope's dir. With `--scope all`, also lists per-scope counts and same-name duplicates (`scopes.find_duplicates()`: name, scopes, descriptions-differ flag — converge with `sync`); `--json` adds a `duplicates` key.

`--explain CONSUMER` switches to the read-only effective-resolution diagnostic
(issue #12): it derives, at read time, which instance of a skill that consumer
would load for `--project DIR` (default: the current directory), reporting the
winner plus the instances it shadows and the primary source behind the decision.
It writes nothing — no file, no SQLite row, no cache — and `effective_state`
stays `unresolved`. Consumers with a recorded precedence row: `commandcode`
(six-way order), `codex` (explicit no-merge, so no winner is elected),
`claude-code` (personal > project for the conflict pair, with nested copies
reported under `also_loads` because they both load), `gemini` (built-in <
extension < user < workspace, same-tier ties reported as `ambiguous`), plus
`cursor`/`opencode`, which document no same-name order and therefore return
`undocumented-precedence` instead of a guess. An unknown consumer returns
`unknown-consumer` and exit 1; a missing `--project` directory returns
`missing-project` and exit 1. Diagnostics that legitimately resolve nothing
(`no-merge`, `undocumented-precedence`, `no-instances`) exit 0. `--skill NAME`
narrows the report to one name. See `effective.py` in @docs/02-modules.md.

### `stats [--json] [--scope SCOPE]`
Counts and summary (skills, disabled, trash, categories, sizes). With `--scope all`, also lists per-scope counts.

### `trash list [--json] | trash restore NAME [--json] | trash purge [--json]`
Manage the trash: list, restore one, purge all.

### `templates list [--json] | templates new NAME [--body TEXT] [--json]`
List templates; create a skill from a template.

### `db rebuild [--json] | db resync [--json]`
`rebuild` drops and re-creates the index from the filesystem; `resync` syncs the index with FS without dropping. Both leave the filesystem untouched.

### `sync NAME [--from SCOPE] [--to SCOPE ...] [--force] [--json]`
Copy a skill from one scope to others. Default: `--from global` → every writable existing agent scope. `--to` is repeatable (target scope ids); `--force` overwrites existing names.

### `scopes [--json] [--no-tokens]`
List known skill scopes and their counts (id, label, path, kind, exists, count, tokens). `--no-tokens` skips token totals for speed. Scope ids: `global`, `claude-code`, `codex`, `cursor`, `opencode`, `gemini`, `commandcode`, `agents`, plus project-local scopes when present.

### `tokens [NAME] [--scope SCOPE] [--text TEXT] [--window WINDOW] [--json]`
Estimate token/context usage. `NAME` = a skill; omit to aggregate over `--scope` (default `all`). `--text` estimates raw text instead (`@path` reads a file). `--window` selects the context window (claude 1M, claude-haiku 200k, gpt-5.6 1.05M, gpt-5 400k, gpt-4o 128k, gemini 1M, gemini-2m 2M). Uses tiktoken when installed, else chars/4 heuristic.

### `install SOURCE [--runner RUNNER] [--scope SCOPE] [--agent AGENT ...] [--skill SKILL ...] [--copy] [--list-only] [--dry-run] [--preview] [--trust-confirmed] [--registry-hash HEX] [--json]`
Install skills from the open skills ecosystem via the `skills` npm package (npx/pnpm/yarn/bunx). `SOURCE` like `vercel-labs/agent-skills` or `owner/repo@skill`. `--scope global` passes `-g`; `--agent` targets agent install dirs; `--skill` filters names; `--copy` copies instead of symlinking; `--list-only` lists available skills; `--dry-run` prints the command without running. `uvx` is rejected (it's an npm package).

`--preview` prints the offline registry bridge preview instead of installing: the parsed registry reference, linkable per-skill audit pages, the `--registry-hash` slot used to detect upstream change, and the exact command this surface would run (`-s <slug>` is added for a registry skill id). It performs no registry request, no cache write, and no execution; without `--trust-confirmed` the plan reports a trust blocker. Registry references accept `owner/repo`, `owner/repo/slug`, `https://skills.sh/{source}/{slug}`, and `https://github.com/owner/repo`; a bare two-segment value is always read as a source (`owner/repo`), so use the skills.sh page URL for a well-known source's skill. Network browse/fetch stays deferred (issue #3). See @docs/ADR-003-registry-bridge-and-eval-harness.md.

### `webui [--host H] [--port P] [--no-browser]` (alias: `gui`)
Launch the local web UI (see @docs/08-web-ui.md). Defaults: `127.0.0.1:8765`, opens browser unless `--no-browser`.

## Flags cheat sheet

**[NOTE]** Multi-word values (descriptions, bodies, metadata) must be quoted or passed via `--body-file`/`--metadata KEY=VALUE`. All mutation commands print human-readable confirmation unless `--json`. Scope ids are lowercase; `--scope all` merges scopes for list/search/stats/tokens.

## Stale-fact note

**[NOTE]** The `gui` command previously launched a GTK4 desktop GUI; since 2026-08-14 it is an alias for `webui` (the GTK GUI was replaced by the local web UI — see @docs/08-web-ui.md). The `scopes`/`sync`/`tokens`/`install` commands and the `--scope` flag were added after the 2026-08-14 doc version.
