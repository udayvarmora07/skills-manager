# CLI Surface — Skills Manager

**Version 0.5.0**

**AI manifest**: Authoritative inventory of every command, alias, flag, and exit code of the `skills-mgr` CLI. Facts verified against the parser/handler modules (`cli_parser.py`, `cli_handlers.py`, `cli_output.py` behind the stable `cli.py` adapter) plus live invocations on 2026-09-20. The web UI must mirror this surface exactly (see @docs/08-web-ui.md). Do not add commands or flags without updating this doc and @docs/02-modules.md.

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
List skills in the scope (default global) with a STATUS column (`active`/`disabled`); disabled skills are shown marked and `--disabled` narrows the list to disabled skills only. `--category` filters; `--scope all` merges every scope and adds a SCOPE column. DESCRIPTION/CATEGORY cells are sanitized before printing (see *Untrusted display text*).

### `create NAME [-d/--description TEXT] [--license LIC] [--category CAT] [--compatibility SPEC] [--version VER] [--allowed-tools TOOLS] [--body TEXT] [--body-file PATH] [--json]`
Create a skill in the global store. Name must match `NAME_RE`; description required. `--body` and `--body-file` are mutually exclusive.

**[NOTE]** `create` is global-only in the CLI — agent-scope creates go through the web UI (`POST /api/skills?scope=`) or `scopes.create_skill()`.

### `add PATH [--name NAME] [--json]`
Add an existing skill directory (or SKILL.md file) from `PATH` (optional `--name` override) to the global store.

### `view NAME [--raw|--json] [--scope SCOPE]`
Print a skill. `--raw` prints the full `SKILL.md` file (frontmatter + body, not body-only, and verbatim — `--raw` is deliberately unsanitized); `--json` shows structured data (incl. `tokens` estimate and scope fields). The output modes are incompatible: passing both `--raw` and `--json` is rejected with a clean exit-1 `StoreError`; neither mode silently overrides the other. In the default text form every field value is sanitized (see *Untrusted display text*); `--json` and `--raw` emit the stored bytes unchanged, so pipe JSON through a formatter rather than to a raw terminal.

### `edit NAME [-d TEXT] [--license LIC] [--category CAT] [--compatibility SPEC] [--version VER] [--allowed-tools TOOLS] [--metadata KEY=VALUE] [--body TEXT] [--body-file PATH] [--json]`
Edit a skill in the global store. All fields optional; partial update. Repeated `--metadata` appends.

**[SPEC]** `--metadata` **rejects a key containing a control character** (a newline above all) with `error: metadata key must not contain a control character, got '...'` and exit 1, before anything is written. It used to write a `SKILL.md` the tool could not parse, exit 0, and let a later `edit` append a *second* frontmatter block (CLI-2). The dumper's own guard (`frontmatter.dump_frontmatter`) independently raises on a key it cannot render, so a bad key fails loudly rather than emitting junk (FM-9, partial).

**[SPEC]** `edit` also **fails closed on an unparseable document**: when the existing frontmatter is malformed the command prints `error: cannot safely edit skill '<name>': its frontmatter is malformed (<reason>); repair it by hand first` and exits 1 with the file left byte-for-byte untouched. It no longer treats "no frontmatter parsed" as "no frontmatter present" and rewrite the document into a second block, which had silently discarded the original metadata (CLI-2, SCOPE-12). The same guard protects agent-scope edits through `scopes.edit_skill`.

### `open NAME`
Open the skill file in `$EDITOR` (falls back if unset). Global store only.

### `remove` / `rm NAME [--purge|--trash] [--json]`
Delete a skill from the global store. Default moves to trash; `--purge` deletes permanently.

### `disable NAME [--json]` / `enable NAME [--json]`
Toggle enabled state in the global store (renames `SKILL.md` <-> `SKILL.md.disabled`).

### `validate [NAMES...] [--all] [--path DIR] [--evals] [--evals-run FILE] [--workspace DIR] [--json]`
Validate skills by name, all (`--all`), or a directory (`--path`). Prints issues.
Target selectors are mutually exclusive; `--workspace` is valid only with
`--evals` or `--evals-run`, and ignored combinations fail with a clean exit-1
error rather than silently discarding an argument.

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
Health check: data dir, DB, skill files, consistency between FS and index, content drift, incomplete transaction artifacts, temporary files, and stale snapshots. `global` (the default) runs the Store/DB doctor; an agent scope scans that scope's filesystem directly and reports malformed documents; unknown scope ids are clean errors with exit 1. With `--scope all`, the global Store report also lists per-scope counts and same-name duplicates (`scopes.find_duplicates()`: name, scopes, descriptions-differ flag — converge with `sync`); `--json` adds a `duplicates` key.

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
Counts and summary (skills, disabled, trash, categories, sizes). With `--scope all`, also lists per-scope counts. Category names are sanitized before printing (see *Untrusted display text*).

### `trash list [--json] | trash restore NAME [--json] | trash purge [--json]`
Manage the trash: list, restore one, purge all. Human `trash purge` reports the
number of purged skills; `--json` preserves the structured `purged` name list.

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

### `install [SOURCE] [--runner RUNNER] [--scope SCOPE] [--agent AGENT ...] [--skill SKILL ...] [--copy] [--list-only] [--dry-run] [--preview] [--trust-confirmed] [--registry-hash HEX] [--review REVIEW_ID] [--browse|--search QUERY|--curated|--fetch] [--page N] [--per-page N] [--view VIEW] [--allow-stale] [--json]`
Install skills from the open skills ecosystem via the `skills` npm package (npx/pnpm/yarn/bunx). `SOURCE` like `vercel-labs/agent-skills` or `owner/repo@skill`. `--scope global` passes `-g`; `--agent` targets agent install dirs; `--skill` filters names; `--copy` copies instead of symlinking; `--list-only` executes the runner's list mode and reports its output/exit status; `--dry-run` prints the command without running. Source, agent, and skill values must be non-empty, at most 256 characters, and may not be option-like, traversal-shaped, absolute, or Windows drive-prefixed. `uvx` is rejected (it's an npm package).

`--preview` prints the offline registry bridge preview instead of installing: the parsed registry reference, linkable per-skill audit pages, the `--registry-hash` slot used to detect upstream change, and the exact command this surface would run (`-s <slug>` is added for a registry skill id). It performs no registry request, no cache write, and no execution. `--trust-confirmed` records caller review intent only for the offline plan; that plan still reports `trust_verified: false`, `eligibility_status: "unverified-offline"`, `hash_verified: false`, and `may_install: false` (a supplied hash is `unverified-provided` until an authenticated read and comparison).

The existing install surface also supports the network registry operations
`--browse`, `--search QUERY`, `--curated`, and two-step `--fetch`. Browse/search/
curated and the first `--fetch SOURCE` return bounded catalog/review evidence
and cache metadata without mutating the Store. The second request is
`--fetch --review REVIEW_ID --trust-confirmed`; it is global-store-only,
revalidates the expiring review snapshot and optional `--registry-hash` evidence,
then writes a credential-free `.skillsmgr-provenance.json` sidecar. The commit
request performs no network request and a review id is single-use. `--allow-stale`
opts into an expired cache only when the network is unavailable. Set
`SKILLS_MANAGER_REGISTRY_TOKEN` or `VERCEL_OIDC_TOKEN` for bearer authentication;
tokens are not persisted.
The registry client rejects unsafe hosts/redirects, oversized or malformed
responses, traversal/symlink paths, duplicate files, and resource-limit
violations. See @docs/ADR-003-registry-bridge-and-eval-harness.md and
@docs/ADR-005-registry-network-and-provenance.md.

Before the existing store-add seam is reached, a fetched snapshot is
materialized in a private temporary directory, fully validated, and scanned
with the advisory `risk_scan()` heuristic. Validation errors fail before any
managed-file mutation; warnings and risk findings are returned under the JSON
`inspection` block and are never a safety certification.

### `webui [--host H] [--port P] [--no-browser]` (alias: `gui`)
Launch the local web UI (see @docs/08-web-ui.md). Defaults: `127.0.0.1:8765`, opens browser unless `--no-browser`.

## Flags cheat sheet

**[NOTE]** Multi-word values (descriptions, bodies, metadata) must be quoted or passed via `--body-file`/`--metadata KEY=VALUE`. All mutation commands print human-readable confirmation unless `--json`. Scope ids are lowercase; `--scope all` merges scopes for list/search/stats/tokens.

## Untrusted display text

**[SPEC]** `list`, `view`, and `stats` print strings that an attacker can influence:
a description or category can arrive from an imported archive or from a scope
directory another tool wrote. Every printed cell therefore passes through
`cli_output.sanitize_text()` first — C0 controls, DEL, and C1 controls (ESC
included, so `ESC[2K` is covered), the Unicode line/paragraph separators, Unicode
format characters (a bidi override can reorder a whole line), and lone surrogates
are each replaced with `?`.

The consequence is the contract worth remembering: a hostile `ESC`/CR payload can
no longer erase the real row and print a convincing "verified" one, and can no
longer corrupt column widths, because the escape stops counting towards `len()`.
`render_table()` and `truncate()` sanitize as well, so a value cannot reach the
terminal through a path that skips the seam, and the colors this tool emits itself
are applied *after* sanitizing, so they are unaffected.

The guards cover the `list`, `view`, `stats`, `search`, and `history` text output.
`--json` and `view --raw` are exempt **by design** — they are data, not a rendered
view — so do not pipe either to a live terminal. (CLI-3.)

## Stale-fact note

**[NOTE]** The `gui` command previously launched a GTK4 desktop GUI; since 2026-08-14 it is an alias for `webui` (the GTK GUI was replaced by the local web UI — see @docs/08-web-ui.md). The `scopes`/`sync`/`tokens`/`install` commands and the `--scope` flag were added after the 2026-08-14 doc version.
