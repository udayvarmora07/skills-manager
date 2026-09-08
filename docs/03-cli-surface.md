# CLI Surface — Skills Manager

**Version 0.3.0**

**AI manifest**: Authoritative inventory of every command, alias, flag, and exit code of the `skills-mgr` CLI. Facts verified against `cli.py` on 2026-08-16. The web UI must mirror this surface exactly (see @docs/08-web-ui.md). Do not add commands or flags without updating this doc and @docs/02-modules.md.

**[SPEC]** Invocation: `python3 -m skillsmgr` (or `skills-mgr` once installed). argparse `prog="skills-mgr"`. Command count: **26 top-level commands + 7 subcommands (trash/templates/db) + 3 aliases (`ls`, `rm`, `gui`) = 40 invocable names**. The `gui` alias is a pure alias of `webui` (the GTK GUI is gone).

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
- `--color auto|always|never` — color output; default auto (TTY detect, honors `NO_COLOR`/`FORCE_COLOR`).
- `--scope SCOPE` — scope selector on `list`, `view`, `search`, `doctor`, `stats`. Values: `global` (default; the Store + DB), `all` (merge every scope), or an agent scope id (`claude-code`, `codex`, `cursor`, `opencode`, `gemini`, `commandcode`, `agents`). `agents` is the Command Code skills dir (`~/.agents/skills`).

**[NOTE]** The scope flag is a **per-command flag**, not a global flag — each scope-aware command declares its own `--scope`. `tokens` and `install` also accept `--scope` with their own semantics (see below).

## Commands

**[NOTE]** `ls` and `rm` are aliases of `list` and `remove` — they are NOT separate commands. `gui` is an alias of `webui`.

### `init [--json]`
Create the data directory layout and initialize the SQLite index.

### `list` / `ls [--json] [--disabled] [--category CAT] [--scope SCOPE]`
List skills in the scope (default global, enabled only). `--disabled` shows disabled; `--category` filters; `--scope all` merges every scope and adds a SCOPE column.

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

### `validate [NAMES...] [--all] [--path DIR] [--json]`
Validate skills by name, all (`--all`), or a directory (`--path`). Prints issues.

### `search TERM [--limit N] [--json] [--scope SCOPE]`
Search with scoring (see @docs/02-modules.md); `--limit` caps results. `--scope all` searches every scope.

### `import ARCHIVE [--force] [--json]`
Import a `.tar.gz`/`.tgz`/`.tar` archive of skills into the global store (tar-only; `tarfile.open(archive, "r:*")` — `.zip` is NOT supported). `--force` overwrites existing names.

### `export [--dest PATH] [--json]`
Export all skills (global scope only) to an archive (default `backups/`). Alias: `backup`.

### `backup [--dest PATH] [--json]`
Alias of `export` (identical behavior).

### `restore NAME [--json]`
Restore a skill from the trash.

### `doctor [--json] [--scope SCOPE]`
Health check: data dir, DB, skill files, consistency between FS and index. With a scope, checks that scope's dir. With `--scope all`, also lists per-scope counts and same-name duplicates (`scopes.find_duplicates()`: name, scopes, descriptions-differ flag — converge with `sync`); `--json` adds a `duplicates` key.

### `stats [--json] [--scope SCOPE]`
Counts and summary (skills, disabled, trash, categories, sizes). With `--scope all`, also lists per-scope counts.

### `trash list [--json] | trash restore NAME [--json] | trash purge [--json]`
Manage the trash: list, restore one, purge all.

### `templates list [--json] | templates new NAME [--body TEXT] [--json]`
List templates; create a skill from a template.

### `history [NAME] [--limit N] [--json]`
Show history (default limit 50). With `NAME`, filtered to that skill.

### `db rebuild [--json] | db resync [--json]`
`rebuild` drops and re-creates the index from the filesystem; `resync` syncs the index with FS without dropping. Both leave the filesystem untouched.

### `sync NAME [--from SCOPE] [--to SCOPE ...] [--force] [--json]`
Copy a skill from one scope to others. Default: `--from global` → every writable existing agent scope. `--to` is repeatable (target scope ids); `--force` overwrites existing names.

### `scopes [--json] [--no-tokens]`
List known skill scopes and their counts (id, label, path, kind, exists, count, tokens). `--no-tokens` skips token totals for speed. Scope ids: `global`, `claude-code`, `codex`, `cursor`, `opencode`, `gemini`, `commandcode`, `agents`, plus project-local scopes when present.

### `tokens [NAME] [--scope SCOPE] [--text TEXT] [--window WINDOW] [--json]`
Estimate token/context usage. `NAME` = a skill; omit to aggregate over `--scope` (default `all`). `--text` estimates raw text instead (`@path` reads a file). `--window` selects the context window (claude 1M, claude-haiku 200k, gpt-5.6 1.05M, gpt-5 400k, gpt-4o 128k, gemini 1M, gemini-2m 2M). Uses tiktoken when installed, else chars/4 heuristic.

### `install SOURCE [--runner RUNNER] [--scope SCOPE] [--agent AGENT ...] [--skill SKILL ...] [--copy] [--list-only] [--dry-run] [--json]`
Install skills from the open skills ecosystem via the `skills` npm package (npx/pnpm/yarn/bunx). `SOURCE` like `vercel-labs/agent-skills` or `owner/repo@skill`. `--scope global` passes `-g`; `--agent` targets agent install dirs; `--skill` filters names; `--copy` copies instead of symlinking; `--list-only` lists available skills; `--dry-run` prints the command without running. `uvx` is rejected (it's an npm package).

### `webui [--host H] [--port P] [--no-browser]` (alias: `gui`)
Launch the local web UI (see @docs/08-web-ui.md). Defaults: `127.0.0.1:8765`, opens browser unless `--no-browser`.

## Flags cheat sheet

**[NOTE]** Multi-word values (descriptions, bodies, metadata) must be quoted or passed via `--body-file`/`--metadata KEY=VALUE`. All mutation commands print human-readable confirmation unless `--json`. Scope ids are lowercase; `--scope all` merges scopes for list/search/stats/tokens.

## Stale-fact note

**[NOTE]** The `gui` command previously launched a GTK4 desktop GUI; since 2026-08-14 it is an alias for `webui` (the GTK GUI was replaced by the local web UI — see @docs/08-web-ui.md). The `scopes`/`sync`/`tokens`/`install` commands and the `--scope` flag were added after the 2026-08-14 doc version.
