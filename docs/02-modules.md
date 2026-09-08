# Modules — Skills Manager

**Version 0.3.0**

**AI manifest**: Module-by-module inventory of `skillsmgr/`. Facts verified against source 2026-08-16. Keep this doc updated when module internals change.

## `__init__.py`

`__version__ = "1.0.0"`. No other code.

## `__main__.py`

Entry point for `python3 -m skillsmgr`; delegates to `cli.main()`.

## `cli.py`

argparse-based CLI, `prog="skills-mgr"`, 27 top-level commands + 7 subcommands (trash/templates/db) + 3 aliases (`ls`, `rm`, `gui`) = 37 invocable names (see @docs/03-cli-surface.md). Key helpers: `_print_json(data)` (indent=2), `_err(msg)`, `_truncate(text, n)`, `_render_table(rows, headers)`. Exit codes: 0 ok / 1 error / 2 usage / 130 interrupt. `--json` on data commands. `--scope` (per-command flag) on `list`/`view`/`search`/`doctor`/`stats`, plus scope-aware `sync`/`scopes`/`tokens`/`install`. `cmd_gui` launches the local web UI via `webapp.run(...)`. The parser and command handlers remain together for now; focused contract tests protect parser/output compatibility while a larger split remains future work.

## `webapp.py`

Stdlib web backend for the web UI: `WebAppHandler` (routes under `/api/`, static files from `webui/`), `WebAppServer` (ThreadingHTTPServer, 127.0.0.1), `run()` entry (browser open, Ctrl+C handling). Internal policy modules keep request security (`web_security.py`), JSON serialization/body parsing (`web_serialization.py`), and multipart folder upload staging (`web_upload.py`) behind compatibility adapters in `webapp.py`. Scope-aware endpoints (`?scope=` on skills/search, `/api/scopes`, `/api/sync`, `/api/install`). Full endpoint table: @docs/08-web-ui.md.

## `webui/` (frontend)

`index.html` (Vue templates for all screens/modals), `styles.css` (design tokens + components), `app.js` (Vue app: state, actions, markdown renderer, toasts), `static/vendor/vue.global.prod.js` (Vue 3.5.13 vendored, no build step). Scope switcher in the topbar (`activeScope` persisted to localStorage), scope-aware create/edit/remove/disable/sync. Full map: @docs/08-web-ui.md.

## `store.py`

`Store` class (FS + SQLite index), exceptions `StoreError`, `SkillNotFound`. Public API and schema: @docs/04-store-api.md. **Return-type traps**: `export()`/`backup()` return a `Path`; `db_rebuild()` returns `{"added", "updated", "removed"}`. Filesystem paths derived from names go through the shared canonical-name and resolved-root guards. Text mutations use private atomic sibling-temp writes, fsync, replacement, and same-process per-document locks; `doctor()` reports transaction artifacts, temporary files, stale snapshots, and FS/index drift. Archive imports preflight tar members into a private temporary directory, enforce compressed/expanded/member/path/nesting/ratio budgets, reject duplicate/path/special members, validate the strict versioned manifest and extracted frontmatter names, reject ZIP content, verify optional content hashes, and use `tarfile.data_filter` when available with a guarded fallback otherwise. Per-skill commits are staged and failures are reported in `skipped`. Internals: `_connect()` (sqlite3.Row, foreign_keys=ON), `_init_db()`, `_history()`, `_load_skill()`, `_upsert_entry()`, `_scan_dir()`.

## `scopes.py`

Scope model + operations for per-agent skill dirs. `Scope` dataclass (id, label, base, kind, writable, recursive, supported, consumer). `known_scopes()` (global + claude-code, codex, cursor, opencode, gemini, commandcode, agents + project-local). `list_scopes()` exposes root availability and discovery metadata; `list_all()` deduplicates resolved physical roots for aggregate views; direct ids remain addressable. Scope records expose observed instance states; precedence-based `shadowed`/effective resolution remains approval-gated. `find_duplicates()` (same-name cross-scope groups with scopes/descriptions-differ/records; read-only over `list_all()`), `get_skill()`, `get_raw()`, `create_skill()`, `edit_skill()`, `remove_skill()` (trash at `<scope-base>/../trash`), `toggle_skill()`, `sync_skill()` (skips duplicate physical target roots), and `search_all()`. `search_all()` builds global ranking records through the public `Store.list()`/`Store.get()` seams so body matches are retained; callers such as CLI may pass their requested Store, while omitted stores retain the injectable adapter behavior. It converts bounded wildcard `ValueError`s to the scope layer's `StoreError` contract. Agent-scope writes go straight to the agent dir (no DB). Global scope delegates to `Store()`.

## `loader.py`

Shared SKILL.md loader + directory scanner (`load_skill`, `scan_dir`) used by both Store and scopes — keeps FS parsing consistent (frontmatter parse, token estimate, disabled detection, derived observations, and recursive discovery).

## `observations.py`

Pure, non-persisted document observations: portable versus client-extension
frontmatter partitions, content/metadata SHA-256 hashes, observed timestamp, and
scope/consumer provenance.

## `web_security.py`, `web_serialization.py`, `web_upload.py`

Private stdlib-only web policy modules. They own loopback mutation validation, JSON body/response helpers, multipart parsing, bounded upload staging, and per-skill upload results. `webapp.py` retains compatibility wrappers and route ownership.

## `diagnostics.py`

Private stderr-only diagnostics for recovery and optional-enrichment failures; it does not change public return values or REST/CLI schemas.

## `check_complexity.py`

Repository-only AST complexity ratchet for the web, CLI, store, and frontmatter hotspots. `complexity-baseline.json` records existing violations and fails on new over-budget functions or metric increases.

## `atomic_io.py`, `archive.py`, `path_safety.py`, `root_discovery.py`

Internal policy modules extracted from the former Store/scopes hotspots. They
own atomic text writes and tree hashes, archive preflight/extraction/staged
commit behavior, resolved root-containment, and physical-root/capability/
instance-state observations. `paths.py` remains a compatibility adapter for the
existing containment function names.

## `tokens.py`

Token/context estimation. `WINDOWS` dict (claude 1M, claude-haiku 200k, gpt-5.6 1.05M, gpt-5 400k, gpt-4o 128k, gemini 1M, gemini-2m 2M), `DEFAULT_WINDOW = "claude"`. Uses tiktoken when installed, else chars/4 heuristic. `estimate(text)`, `aggregate(records)`.

## `paths.py`

`data_dir()`, `db_path()` (see @docs/01-architecture.md). Subdirs resolved relative to data dir: `skills/`, `trash/`, `templates/`, `backups/`. `contained_path()` resolves and rejects paths outside a managed root; `safe_skill_path()` combines it with `validator.validate_skill_name()`.

## `frontmatter.py`

SKILL.md frontmatter (YAML-ish, delimited by `_DOC_MARKER`): `parse_frontmatter(text)` -> (frontmatter dict, body), `dump_frontmatter(frontmatter, body)`; bool/None/str coercion; raises `FrontmatterError` on malformed input.

## `validator.py`

Name rule: `NAME_RE = ^[a-z0-9]+(-[a-z0-9]+)*$` (rejects `--`, leading/trailing hyphens); limits: `MAX_NAME=64`, `MAX_DESCRIPTION=1024`, `MAX_COMPATIBILITY=500`, `MAX_BODY_LINES=500`, `MAX_BODY_TOKENS=5000`. `validate_skill_name(name)` is the authoritative fail-closed primitive used by Store, scopes, CLI, and REST-adjacent path handling. `Issue` dataclass (level, message, key). `validate_skill(name, skill_dir)` -> `ValidationResult` (`.valid`, `.errors`, `.warnings`, `.issues`). `description_score(text)` -> `{has_use_context, filler_hits, word_count}`. Validators cover: name format, frontmatter name vs directory name, description length + use-context/filler warnings, compatibility length, body line count + token warning, `scripts/`/`references/`/`assets/` layout mentions, relative link targets.

## `search.py`

Pattern `*` -> `.*`, `?` -> `.`, case-insensitive; repeated stars collapse, queries are limited to 200 characters and 10 effective stars, and invalid complexity raises `ValueError`. Scoring: 100 exact name, 90 fullmatch, 80 prefix, 70 name regex, 60 name substring, 40 description/body regex, 30 category regex, 25 description/body substring, 0 no match. `rank_results(records, term)` returns (record, score) tuples.

## `templates.py`

Templates are `<data>/templates/*.md`; `TEMPLATE_NAME_RE`; `DEFAULT_TEMPLATE` string. `list_templates(dir)`, `read_template(dir, name)`, `create_template(dir, name, body=None)` (raises `ValueError` on bad name, `FileExistsError` on dup).

## `colors.py`

TTY auto-detect; honors `NO_COLOR` and `FORCE_COLOR`; `color(text, code)` and styled helpers.

## Smoke tests

- `smoke_store.py` — exercises the Store API (init, add, list, get, search, disable, enable, trash, restore, purge, export, import round-trip, stats, history, resync, db_rebuild). Must pass after any `store.py` change.
- `smoke_web.py` — starts `WebAppServer` on an ephemeral port and hits every REST endpoint (static, CRUD, search, validate, toggle, stats/doctor/history, templates, export→import, trash/restore/purge, rebuild/resync, multipart upload, error paths). Must pass after any `webapp.py` change.
