# Modules — Skills Manager

**Version 0.3.0**

**AI manifest**: Module-by-module inventory of `skillsmgr/`. Facts verified against source 2026-09-10 (CLI 27+7+3=37 via `check_docs._command_inventory` + live parser; insights 57 via test count; archive row refreshed for ZIP import and transactional full-import restore). Keep this doc updated when module internals change.

## `__init__.py`

`__version__ = "1.0.1"`. No other code.

## `__main__.py`

Entry point for `python3 -m skillsmgr`; delegates to `cli.main()`.

## `cli.py`, `cli_parser.py`, `cli_handlers.py`

The stable `cli.py` adapter exposes `main()`, `build_parser()`, command handler names, exit constants, and historical private helper aliases. `cli_parser.py` owns argparse construction (`prog="skills-mgr"`): 27 top-level commands + 7 subcommands (trash/templates/db) + 3 aliases (`ls`, `rm`, `gui`) = 37 invocable names (see @docs/03-cli-surface.md). `cli_handlers.py` owns command behavior and validates names/data before filesystem work; `cli_output.py` owns JSON/errors/table rendering. Exit codes: 0 ok / 1 error / 2 usage / 130 interrupt. Public parser/handler adapters preserve existing imports and contract tests.

## `webapp.py`

Stdlib web backend for the web UI: `WebAppHandler` (routes under `/api/`, static files from `webui/`), `WebAppServer` (ThreadingHTTPServer, 127.0.0.1), `run()` entry (browser open, Ctrl+C handling). Internal policy modules keep request security (`web_security.py`), JSON serialization/body parsing (`web_serialization.py`), and multipart folder upload staging (`web_upload.py`) behind compatibility adapters in `webapp.py`. Scope-aware endpoints (`?scope=` on skills/search, `/api/scopes`, `/api/sync`, `/api/install`). Full endpoint table: @docs/08-web-ui.md.

## `webui/` (frontend)

`index.html` (Vue templates for all screens/modals), `styles.css` (design tokens + components), `domain.js` (transport, formatting, frontmatter, escaped Markdown renderer), `app.js` (Vue state, actions, dialogs, focus/keyboard lifecycle, and toasts), `static/vendor/vue.global.prod.js` (Vue 3.5.13 vendored, no build step). Scope switcher in the topbar (`activeScope` persisted to localStorage), scope-aware create/edit/remove/disable/sync. Full map: @docs/08-web-ui.md.

## `store.py`

`Store` class (FS + SQLite index), exceptions `StoreError`, `SkillNotFound`. Public API and schema: @docs/04-store-api.md. **Return-type traps**: `export()`/`backup()` return a `Path`; `db_rebuild()` returns `{"added", "updated", "removed"}`. Filesystem paths derived from names go through the shared canonical-name and resolved-root guards. Live skill directories are always recorded `status='active'` (stale `'trashed'` rows are reactivated via `_upsert_entry`/`resync`, including a post-sync resync when sync commits into the global scope). Text mutations use atomic sibling-temp writes, fsync, replacement, and the same-process per-skill lock shared by `create`/`edit`/`remove`/`disable`/`enable`/`restore` (`_with_skill_lock`); `doctor()` reports transaction artifacts, temporary files, stale snapshots, and FS/index drift. Archive imports preflight tar or ZIP members into a private temporary directory, enforce compressed/expanded/member/path/nesting/ratio budgets, reject duplicate/path/special members, validate the strict versioned manifest and extracted frontmatter names, fail malformed streams as clean `StoreError`, preserve the original destination when commit staging fails, verify optional content hashes, and use `tarfile.data_filter` when available with a guarded fallback otherwise. ZIP extraction uses explicit contained paths and rejects symlink-bit entries because ZIP has no equivalent safe extraction filter, and the compression-ratio budget is enforced per member as well as per archive. Per-skill commits are staged and failures are reported in `skipped`; a failed staging copy never removes the user's existing skill directory. A `--full` import validates every trash/template payload before any mutation, then installs them as one all-or-nothing transaction (`archive.restore_full_payload`) and reconciles the restored trash names into the index, so failures surface as `StoreError` with the previous state intact. `purge_trash` wraps filesystem failures as `StoreError`. Internals: `_connect()` (sqlite3.Row, foreign_keys=ON), `_init_db()`, `_history()`, `_load_skill()`, `_upsert_entry()`, `_scan_dir()`.

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

## `effective.py`

Read-only effective-resolution diagnostic behind `doctor --explain CONSUMER
[--project DIR] [--skill NAME]` and `GET /api/doctor?explain=…` (issue #12).
`explain()` derives, at read time, which instance of a skill a consumer would
load for one `(consumer, project-CWD, skill)` triple, and returns a
JSON-serialisable report: `resolution`, `policy`, per-skill `winner`,
`shadowed` (with the winning tier as `shadowed_by`), `also_loads`, the `tiers`
actually read with their `instances`/`skipped` detail, `warnings`,
`unobservable_tiers`, and the cited `source` URL. Every precedence row lives in
`CONSUMERS` and is sourced from
@docs/12-agent-root-discovery-2026-09-08.md: `commandcode` documents a six-way
order (project `.commandcode/` > project `.agents/` > user `~/.commandcode/` >
user `~/.agents/` > extras > bundled), `codex` documents an explicit no-merge
policy (so `policy: "no-merge"` elects no winner and reports every copy),
`claude-code` documents personal > project for the conflict pair with
project-root/nested copies both loading, `gemini` documents built-in <
extension < user < workspace, and `cursor`/`opencode` document no same-name
order at all. Consumers therefore never get an invented winner: an unrecorded
order yields `undocumented-precedence`, and an unknown consumer yields
`unknown-consumer` with the known list. A missing project directory yields
`missing-project`; a documented tier whose path this tool cannot read
(`path_known: False`, e.g. Claude's enterprise tier, Codex `SYSTEM`, Command
Code `extras`/`bundled`) is reported as unobservable with a warning that a
lower-tier win is provisional. Observed-state vocabulary is reused: `disabled`
(`SKILL.md.disabled` is not loadable as `SKILL.md`) and `invalid` (malformed or
undecodable) instances are reported under `skipped` with a reason and can never
win; a skill with only skipped copies resolves to `no-instances`. Nothing is
persisted — no filesystem write, no SQLite access, no cache, no `Store` method
— and `effective_state` stays `unresolved` (ADR-002). Reads are bounded by
`MAX_ROOTS`/`MAX_INSTANCES`, and the report always carries
`read_only`/`persists_nothing`.

## `insights.py`

Read-only Milestone 9 insight helpers (pure, stdlib-only, zero disk
mutation): `consumer_view()` (per-consumer observed instances, precedence
explicitly unresolved per ADR-002), `diff_skills()`/`diff_three_way()`
(two-way field/body diff, three-way merge preview holding base on conflict),
`ownership_states()` (`managed`/`unmanaged`/`adopted`/`quarantined`/`invalid`),
`provenance_summary()` (known/unknown split over loader observations),
`update_preview()` (changed files, token/body/snapshot risks, rollback flag),
`quarantine_plan()` (stage-only plan validated by `validate_skill_name`),
`risk_scan()` (explainable script/link/tool/pattern findings with why +
evidence), `registry_preview()` (offline dry-run gated on explicit trust),
`registry_reference()` (offline parse of `owner/repo`, `owner/repo/slug`,
`https://skills.sh/{source}/{slug}`, and `https://github.com/owner/repo` into
`{form, source, slug, registry_id, page_url, audit_links}` — no request, cache,
or credential), `registry_bridge_plan()` (that reference mapped onto the exact
`npx skills add` command via `install_argv()`, with the explicit trust gate as
`blockers`/`may_install`, linkable `/security/{provider}` audit pages, and a
`content_hash` slot for change detection), `install_argv()`/
`install_command_line()` (single renderer behind both the printed dry-run text
and the executed argv), `eval_plan()`/`eval_score()` (provider-neutral
deterministic cases, advisory only), `bundle_policy()` (signatures deferred
pending issue #11 review).
Fail-closed input policy: non-dict records raise `ValueError` (never raw
`AttributeError`/`TypeError`); `consumer_view()` skips non-dict list items;
`update_preview()` coerces tokens safely (`None` for non-numeric) and
rejects non-list snapshots; `diff_skills()` caps `body_diff` at
`MAX_BODY_DIFF_LINES` (200) with a `body_diff_truncated` flag;
`eval_plan()` requires dict cases with input/expect keys; name entry
points (`quarantine_plan`/`eval_plan`) require real strings via
`_canonical_name()`; all outputs are JSON-serializable; consumer views
sort deterministically; `ownership_states()` treats a record as
`invalid` on the loader `malformed` flag or `validator.validate_skill`
errors against its real skill directory (body-only text is never
revalidated as a document); `consumer_view()` deep-copies records;
`eval_score()` requires a callable scorer; snapshot items and
quarantine sources must be strings; non-string registry descriptions
become install blockers; registry source/scope/hash must be strings
when present; registry reference segments are length-capped
(`MAX_REGISTRY_SEGMENT = 96`) and reject traversal, separators, absolute
paths, and any host outside `skills.sh`/`github.com`; install sources and
`-a`/`-s` values must match the ecosystem value allowlist and must not start
with `-`.

## `evals.py`

File-based, advisory-only eval harness implementing the official
evaluating-skills contract with the standard library only (no network, no SDK,
no SQLite, no `Store` method). `evals_file()` locates `evals/evals.json` inside
a skill directory; `load_cases()` reads and normalizes it (`skill_name`, cases
with `id`/`prompt`/`expected_output`/`files`, plus optional `slug` and optional
deterministic `assertions`), reporting malformed content as `issues` instead of
raising, and warning (never failing) on missing input files; `normalize_case()`
validates one case; `case_slugs()` derives the guide's `eval-<slug>` directory
name; `workspace_for()`/`workspace_beside()` resolve the run workspace
(`<data>/evals/<name>-workspace` for installed skills — deliberately outside
`skills/` — or `<skill-dir>-workspace` in authoring layout);
`iteration_dir()`/`case_dir()`/`variant_dir()` compose the contained
`iteration-N/eval-<slug>/{with_skill,without_skill}` paths;
`grade_output()` evaluates the deterministic assertion subset (`equals`,
`contains`, `not_contains`, `regex`, `is_json`) and marks a case with no
assertions `graded: false` rather than passed; `normalize_runs()`/
`score_runs()`/`benchmark()` grade caller-supplied runs and aggregate a
per-variant case pass rate plus the `with_skill` − `without_skill` delta;
`record_runs()` writes `outputs/output.txt`, `grading.json`, `timing.json` per
variant and a per-iteration `benchmark.json` through atomic sibling-temp
writes. Bounds: `MAX_CASES = 100`, `MAX_EVALS_FILE_BYTES = 1_000_000`,
`MAX_CASE_TEXT = 20000`, `MAX_OUTPUT_TEXT = 200000`, `MAX_RUNS = 400`,
`MAX_PATTERN_LENGTH = 200`, `MAX_REGEX_INPUT = 50000`. `EVAL_POLICY` records
the standing rule: results are workspace files, never SQLite rows, and never
gate installs or edits.
sort deterministically; `risk_scan()` is six single-purpose scanners.
Operates on records the existing `scopes`/`loader`/`Store.history` seams
already return; no new CLI/Store surfaces, no schema change.

## `tokens.py`

Token/context estimation. `WINDOWS` dict (claude 1M, claude-haiku 200k, gpt-5.6 1.05M, gpt-5 400k, gpt-4o 128k, gemini 1M, gemini-2m 2M), `DEFAULT_WINDOW = "claude"`. Uses tiktoken when installed, else chars/4 heuristic. `estimate(text)`, `aggregate(records)`.

## `paths.py`

`data_dir()`, `db_path()` (see @docs/01-architecture.md). Subdirs resolved relative to data dir: `skills/`, `trash/`, `templates/`, `backups/`. `contained_path()` resolves and rejects paths outside a managed root; `safe_skill_path()` combines it with `validator.validate_skill_name()`.

## `frontmatter.py`

SKILL.md frontmatter (YAML-ish, delimited by `_DOC_MARKER`): `parse_frontmatter(text)` -> (frontmatter dict, body), `dump_frontmatter(frontmatter, body)`; bool/None/str coercion; raises `FrontmatterError` on malformed input. Duplicate keys are rejected as clean `FrontmatterError` in every mapping form (block, inline `- key:`, continuation, flow maps) instead of resolving last-wins. The dumper round-trips its own output (flow items with special characters and keys with quotes are quoted) and raises `TypeError` for mappings nested inside flow lists, which the parser grammar cannot express.

## `validator.py`

Name rule: `NAME_RE = ^[a-z0-9]+(-[a-z0-9]+)*$` (rejects `--`, leading/trailing hyphens); limits: `MAX_NAME=64`, `MAX_DESCRIPTION=1024`, `MAX_COMPATIBILITY=500`, `MAX_BODY_LINES=500`, `MAX_BODY_TOKENS=5000`. `validate_skill_name(name)` is the authoritative fail-closed primitive used by Store, scopes, CLI, and REST-adjacent path handling. `Issue` dataclass (level, message, key). `validate_skill(name, skill_dir)` -> `ValidationResult` (`.valid`, `.errors`, `.warnings`, `.issues`). `description_score(text)` -> `{has_use_context, filler_hits, word_count}`. Validators cover: name format, frontmatter name vs directory name, description length + use-context/filler warnings, compatibility length, body line count + token warning, `scripts/`/`references/`/`assets/` layout mentions, relative link targets.

## `search.py`

Pattern `*` -> `.*`, `?` -> `.`, case-insensitive; repeated stars collapse, queries are limited to 200 characters and 10 effective stars, and invalid complexity raises `ValueError`. Scoring: 100 exact name, 90 fullmatch, 80 prefix, 70 name regex, 60 name substring, 40 description/body regex, 30 category regex, 25 description/body substring, 0 no match. `rank_results(records, term)` returns (record, score) tuples.

## `templates.py`

Templates are `<data>/templates/*.md`; `TEMPLATE_NAME_RE`; `DEFAULT_TEMPLATE` string. `list_templates(dir)`, `read_template(dir, name)`, `create_template(dir, name, body=None)` (raises `ValueError` on bad name, `FileExistsError` on dup).

## `colors.py`

TTY auto-detect; honors `NO_COLOR` and `FORCE_COLOR`; `color(text, code)` and styled helpers.

## Smoke tests

- `check_package_data.py` — verifies the complete web UI inside the built wheel and sdist; `--dist-dir` inspects the exact artifacts CI publishes and, with `--install`, also installs them into fresh temporary venvs. `browser_harness.py` — dev-only system-Chrome CDP probe (ports chosen by the OS via `DevToolsActivePort`).
- `smoke_store.py` — exercises the Store API (init, add, list, get, search, disable, enable, trash, restore, purge, export, import round-trip, stats, history, resync, db_rebuild). Must pass after any `store.py` change.
- `smoke_web.py` — starts `WebAppServer` on an ephemeral port and hits every REST endpoint (static, CRUD, search, validate, toggle, stats/doctor/history, templates, export→import, trash/restore/purge, rebuild/resync, multipart upload, error paths). Must pass after any `webapp.py` change.
