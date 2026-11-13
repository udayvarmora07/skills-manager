# Modules — Skills Manager

**Version 0.11.0**

**AI manifest**: Module-by-module inventory of `skillsmgr/`. The 2026-11-09
module boundaries are recorded in @docs/37-codebase-untangling-2026-11-09.md.
 Facts verified against source 2026-10-06 (CLI 28+10+3=41 via `check_docs._command_inventory` + live parser; safe local source-update review/apply/snapshot orchestration is filesystem-owned; `loader.py` holds a bounded process-local derived-record reuse keyed on the sha256 of the document bytes, with a thrash-cliff guard and an `observed_at` re-stamp; launcher executable discovery rejects unsafe PATH matches; environment data roots are validated; validator references are URL-aware; full-import rollback diagnostics, narrow undefined-name CI checks, reviewed Bandit suppressions, deterministic Markdown discovery, PEP 639 artifact metadata, and package-data/workflow security gates are pinned). Keep this doc updated when module internals change.

## `__init__.py`

`__version__ = "1.0.2"`. No other code.

## `__main__.py`

Entry point for `python3 -m skillsmgr`; delegates to `cli.main()`.

## `cli.py`, `cli_parser.py`, `cli_handlers.py`

The stable `cli.py` adapter exposes `main()`, `build_parser()`, the public `COMMANDS` table, command handler names, and exit constants. `cli_parser.py` owns argparse construction (`prog="skills-mgr"`): 29 top-level commands + 11 subcommands (7 trash/templates/db actions, 3 update actions and 1 AI action) + 3 aliases (`ls`, `rm`, `gui`) = 43 invocable names (see @docs/03-cli-surface.md). `cli_handlers.py` owns command behavior and validates names/data before filesystem work (it also rejects a `--metadata` key containing a control character with a clean exit 1, and both edit paths fail closed on an unparseable document); `cli_output.py` owns JSON/errors/table rendering plus `sanitize_text()`/`truncate()`/`render_table()`, which strip C0/C1/DEL, Unicode line separators, format characters, and lone surrogates from untrusted display fields (`--json` and `view --raw` are deliberately exempt). Exit codes: 0 ok / 1 error / 2 usage / 130 interrupt. Public parser/handler adapters preserve existing imports and contract tests.

## `cli_ai.py`

**[SPEC] Approved A14 CLI/CI.** `cmd_ai` implements the `ai trigger-test --saved`
handler behind the stable CLI adapter. It defaults to no-send estimation and
uses `ai_skills.trigger_test` with a baseline preflight over the same captured
inputs/configuration used for sending. It emits schema-versioned JSON or
sanitized human text and recomputes complete integer routing counts for a
conservative, optional regression gate. Prompt, model/endpoint, seed/repeats
and routing-version mismatches cannot pass; listing changes are disclosed.
It writes no skill or SQLite state. Contract: @docs/42-ai-cli-ci-2026-11-09.md.

## `webapp.py`

Stdlib web backend for the web UI: `WebAppHandler` (routes under `/api/`, static files from `webui/`), `WebAppServer` (ThreadingHTTPServer, 127.0.0.1), `run()` entry (trusted optional browser open, Ctrl+C handling). Internal policy modules keep request security (`web_security.py`), JSON serialization/body parsing (`web_serialization.py`), and multipart folder upload staging (`web_upload.py`) in their owning modules. Scope-aware endpoints (`?scope=` on skills/search, `/api/scopes`, `/api/sync`, `/api/install`). Full endpoint table: @docs/08-web-ui.md.

## `webui/` (frontend)

**[NOTE] 2026-11-06 v2 default.** `/` redirects to `/v2/`; the classic frontend
below remains at `/classic/`. V2's `app.js` owns the shell and ordinary skill
flows, `model.js` derived state/document rendering, `library-tools.js` exact-copy
selection and reviewed batches, and `tool-center.js` the remaining secondary
workflows. The tool-page groups and IDs are defined in `model.js`; the tool
index, hash router and command palette derive their lists from it.
`tools.css` extends the selected v2 tokens. Stored-template reads and
PATCH explicit optional/body clears live in `webapp.py`; omitted fields are
preserved. See @docs/08-web-ui.md for the current route and workflow map.


`index.html` (Vue templates for all screens/modals), `styles.css` (design tokens + components), `domain.js` (transport, formatting, frontmatter, escaped Markdown renderer), `app.js` (Vue state, actions, dialogs, focus/keyboard lifecycle, and toasts), `static/vendor/vue.global.prod.js` (Vue 3.5.13 vendored, no build step). Scope switcher in the topbar (`activeScope` persisted to localStorage), scope-aware create/edit/remove/disable/sync. Full map: @docs/08-web-ui.md.

## `errors.py`

Leaf module holding the exception hierarchy: `StoreError`, `SkillNotFound`,
`LockTimeoutError` (`status = 409`) and `StoreLayoutError` (`status = 404`). It
imports nothing from `skillsmgr`, so modules that only need to raise or catch
these errors do not import the whole Store and the import cycle is broken.
`store.py` re-exports all four, so `from skillsmgr.store import StoreError`
keeps working and both paths name the same class (R15).

## `store.py`

`Store` class (FS + SQLite index); the exception classes it uses are re-exported from `errors.py`. Public API and schema: @docs/04-store-api.md. **Return-type traps**: `export()`/`backup()` return a `Path`; `db_rebuild()` returns `{"added", "updated", "removed"}`. Filesystem paths derived from names go through the shared canonical-name and resolved-root guards. Live skill directories are always recorded `status='active'` (stale `'trashed'` rows are reactivated via `_upsert_entry`/`resync`, including a post-sync resync when sync commits into the global scope). Text mutations use atomic sibling-temp writes, fsync, replacement, and the same-process per-skill lock shared by `create`/`edit`/`remove`/`disable`/`enable`/`restore` (`_with_skill_lock`); every mutation also takes the library-wide index lock at `<data>/skills/.skillsmgr-index-lock` (`index_lock_path`) so a whole-tree scan cannot interleave, and `restore`/`purge_trash` additionally serialize on `<data>/trash/.trash-lock`; `doctor()` reports transaction artifacts, temporary files, stale snapshots, and FS/index drift. Archive imports preflight tar or ZIP members into a private temporary directory, enforce compressed/expanded/member/path/nesting/ratio budgets, reject duplicate/path/special members, validate the strict versioned manifest and extracted frontmatter names, fail malformed streams as clean `StoreError`, preserve the original destination when commit staging fails, verify optional content hashes, and use `tarfile.data_filter` when available with a guarded fallback otherwise. ZIP extraction uses explicit contained paths and rejects symlink-bit entries because ZIP has no equivalent safe extraction filter, and the compression-ratio budget is enforced per member as well as per archive. Per-skill commits are staged and failures are reported in `skipped`; a failed staging copy never removes the user's existing skill directory. A `--full` import validates every trash/template/catalog payload before any mutation, then installs them as one all-or-nothing transaction (`archive.restore_full_payload`) and reconciles the restored trash names into the index; if a later payload fails and its old destination cannot be restored, the diagnostic names the surviving dotted backup while the original `StoreError` remains the public failure. `purge_trash` wraps filesystem failures as `StoreError`. Internals: `_connect()` (sqlite3.Row, foreign_keys=ON), `_init_db()`, `loader.load_skill()`, `_upsert_entry()`, `_scan_dir()`.

## `catalog.py`

Filesystem-owned manager metadata at `<data>/catalog/metadata.json`: bounded
tags keyed by canonical skill name and saved profiles containing member names
and target scopes/consumers. `load_catalog()`/`save_catalog()` use atomic
writes and a mutation lock; `profile_preview()` derives observed, disabled,
divergent, and missing states from current scope rows. `plan_hash()` binds a
batch preview to exact physical targets and operation options. It does not
write SQLite or change skill documents. Full archive support is implemented in
`archive.py`/`Store.export()`/`Store.import_`; the decision record is
@docs/ADR-006-catalog-metadata-and-batch-plans.md.

## `adapters.py`

Read-only consumer adapter catalog derived from `effective.CONSUMERS` and the
primary root-discovery evidence. It exposes candidate roots, tiered precedence
evidence, reload guidance, verification date, and explicit unknown-precedence
status. A candidate root carries `scope`, `relative_path`, `absolute_path` or
`home_path` (the home-relative spec added 2026-11-07), with `path_known`
distinguishing a documented-but-unreadable tier. `project_observation()`
validates resolved project containment and
redacts outside paths; `workspaces_payload()` combines that observation with
adapter records. No project or consumer binding is persisted. Decision record:
@docs/ADR-007-adapter-catalog-and-project-workspaces.md.

## `scopes.py`

Scope list rows additionally expose derived `physical_root` and
`physical_path` observations for the logical-library UI; aliases to one
resolved document can be grouped once without becoming a new source of truth.

Scope model + operations for per-agent skill dirs. `Scope` dataclass (id, label, base, kind, writable, recursive, supported, consumer). `known_scopes()` (global + claude-code, codex, cursor, opencode, gemini, commandcode, agents + project-local). `list_scopes()` exposes root availability and discovery metadata; `list_all()` deduplicates resolved physical roots for aggregate views while keeping *distinct* instances apart, so two same-name skills inside one recursive scope are both listed and both carry the `duplicated`/`divergent` states; direct ids remain addressable. Scope records expose observed instance states (`active`, `disabled`, `invalid`, `duplicated`, `divergent`, `unmanaged`, and `unaddressable` for a name that fails `NAME_RE`, which is paired with `addressable: false` on the row); precedence-based `shadowed`/effective resolution remains approval-gated. `find_duplicates()` (same-name cross-scope groups with scopes/descriptions-differ/records; read-only over `list_all()`), `get_skill()`, `get_raw()`, `create_skill()`, `edit_skill()`, `remove_skill()` (trash at `<scope-base>/../trash`), `toggle_skill()`, `sync_skill()` (skips duplicate physical target roots), and `search_all()`. `search_all()` builds global ranking records through `Store.list()` and attaches each row's body with a **single** `SELECT name, body` over the existing `Store._index_rows` read seam; callers such as CLI may pass their requested Store, while omitted stores retain the injectable adapter behavior. **[SPEC]** The body *source* is deliberately still the index, exactly as `Store.search()` has always used it, so the CLI and the web route keep agreeing on what a body match means. The previous per-row `Store.get()` was **waste, not authority**: `Store.get()` returns `body` from the index and spends its document read filling `Store._OBSERVED_KEYS`, which this caller discarded entirely — so it re-read and re-hashed every document in the library to derive metadata nobody looked at. The reuse cache could not help, because proving the bytes unchanged *is* the file read. One `_index_rows` call rather than a new public `Store` method, which is locked-constraint 5; `scopes` already reaches a private `Store` method (`_check_store_layout`), so this crosses an existing line rather than drawing a new one. It converts bounded wildcard `ValueError`s to the scope layer's `StoreError` contract. Agent-scope writes go straight to the agent dir (no DB). Global scope delegates to the injected `Store`; that injection is a `ContextVar` (per-thread, rebound per request by the web server), so two in-process servers on different data dirs cannot cross over. `known_scopes()` and `scan_scope("global")` share one identity for the global root: the injected Store's own tree when one is injected, otherwise the environment-derived data dir.

## `documents.py`, `clock.py`, `read_flights.py`, `file_reads.py`

`documents.py` owns enabled/disabled document names, strict and replacement
UTF-8 reads, conflict detection and the locked enable/disable rename. Its
callers own the surrounding Store/index or agent-scope transaction.
`clock.py` owns UTC record and filename timestamp formats. `read_flights.py`
shares only simultaneous reads, publishes errors/interrupts to waiters and
keeps nested results independent; completed reads are never cached.
`file_reads.py` acquires a regular-file descriptor and reads no more than the
caller's byte limit plus one detection byte. Native settings, evals and
lockfiles retain their separate parsers, limits, error shapes and link policies.

## `doctor.py`, `batch.py`

`doctor_report()` composes global/index, agent filesystem and optional hygiene
reports for both frontends. Agent doctor uses the scope scanner's managed-peer
link policy and reports root scan failures as degraded. Recursive discovery
remains best-effort: an inaccessible descendant is not proof of a complete
scan, and a grouping directory without a document is not reported as a skill.
`batch.py` owns exact-target preview/execute, plan bindings, tree evidence and
per-item application; HTTP handles request/response adaptation.

## `insights.py`

The documented advisory API remains available: consumer views, two/three-way
skill diffs, ownership/provenance evidence, update/quarantine plans, registry
previews, provider-neutral eval plans/scores and bundle policy. Shared risk,
registry and install implementations remain in their owning modules; the
compatibility facade preserves strict legacy input rejection and `ValueError`
contracts. It does not import the CLI or HTTP adapter.

## `loader.py`

Shared SKILL.md loader + directory scanner (`load_skill`, `scan_dir`) used by both Store and scopes — keeps FS parsing consistent (frontmatter parse, token estimate, disabled detection, derived observations, and recursive discovery).

**[SPEC] Bounded derived-record reuse.** `load_skill(..., reuse=True)` reuses a
previously derived record instead of re-parsing, re-hashing and re-estimating an
unchanged document. The key is the **sha256 of the document bytes** plus the
filesystem facts that are *not* facts about those bytes — `disabled`,
`document_conflict`, `decode_error` — plus the document path, which leads the key
because the derived record reports it verbatim as `provenance.path` (two callers
spell the same physical file differently and each keeps its own spelling).
`os.path.realpath` was the obvious identity and was measured: one `lstat` per path
component for no gain, since `scan_dir` hands every scope the same resolved root.

The content hash is deliberate and is **not** the `(mtime_ns, size)` key the audit
recommended. An `(mtime_ns, size)` key is blind by construction to a same-size edit
landing inside the filesystem's mtime granularity — 1 s on HFS+, 2 s on FAT,
routinely 1 s on network mounts — and this repository has macOS and Windows legs.
Reading the document is required to learn the hash anyway, and it is the cheapest
part of the work, so the guarantee is exact rather than statistical.

Three measured facts shape the design:

- **Reuse is a process-local warm win, not a per-request one.** The audit's
  "scoped to one request" scoping buys a cold request nothing — instrumented at
  exactly 1.00 parse per row per request. Warm dominates because `webui/app.js`
  calls `loadSkills()` after ~20 mutation sites and deliberately never caches a
  completed read. Interleaved A/B, 9 alternating rounds, hermetic `HOME` and data
  dir: 1,200 rows warm 387.5 → 273.5 ms (−29.4%) / cold 424.9 → 419.7 ms (−1.2%);
  2,000 rows warm 711.1 → 495.6 ms (−30.3%) / cold 655.0 → 655.6 ms (+0.1%). Cold
  is flat and reported as flat; GC churn from retention is the largest residual,
  about 6 points of cold cost.
- **A bounded LRU cannot beat a sequential scan larger than itself.**
  `document_reuse_worthwhile(document_count)` measures up front and returns
  `False` above `MAX_DOCUMENT_CACHE = 4096`, and `scan_dir` then passes
  `reuse=False` — the caller keeps exactly its pre-reuse behaviour with none of
  its cost. Measured at 5,000 documents through a 1,000-entry bound, the second
  pass re-derived 5,001 documents: 0% reuse, strictly worse than no cache.
- **A hit re-stamps `observed_at` on the copy that leaves the cache.** A hit is
  still a real observation — the bytes were re-read and hashed to prove they are
  the same bytes — so `observed_at` must say when *this read* happened. The stored
  entry is not mutated and no content-derived field is re-stamped. This matters
  beyond the agent-scope path: `observed_at` is listed in the `Store` class's
  `_OBSERVED_KEYS` tuple, so the global path is affected too.

Registry provenance is deliberately **not** reused. A provenance sidecar is a
filesystem fact rather than a fact about `SKILL.md`'s bytes, so it is re-probed on
every load and a stale or malformed sidecar stays visible as drift. The
containment realpath is likewise retained as a security contract. Every value
leaving the cache is an independent copy (`isolated_record`, bounded depth
`_COPY_MAX_DEPTH = 12`), so no caller and the cache never share an object.

## `observations.py`

Pure, non-persisted document observations: portable versus client-extension
frontmatter partitions, content/metadata SHA-256 hashes, observed timestamp, and
scope/consumer provenance.

## `hygiene.py`

Read-only deterministic synthesis over observed scope records. `hygiene_report()`
deduplicates resolved physical instances, reuses `validator.validate_skill()`,
`validator.description_score()`, token estimates, and `source_lock_status()` to
report structural/validation evidence, exact duplicate groups, same-name drift,
bounded near-duplicate candidates, broken references, activation-description
guidance, context limits, source-lock state, largest instances, degraded scans,
an advisory ignored-frontmatter section, and explicitly unavailable signals.
The ignored-frontmatter findings use the pure `key_support` table below: a
top-level key with a documented behavioural effect in Claude Code is reported
(`info`) when a consumer reading that scope documents no such effect — grouped
one finding per key, naming which consumers document it and which do not, and
never claiming the key is rejected. Scopes without a documented key list
(`global`, `commandcode`, `cursor`, project scopes) produce a
`frontmatter-key-support` unavailable signal instead.
`normalize_instruction_body()` owns the
narrow exact-instruction comparison normalization; `near_duplicate_candidates()`
uses bounded inverted-index features and weighted Jaccard scores. The module
does not write files, SQLite, caches, history, or network state and exposes no
Store method. Physical findings retain bounded alias `observations` (scope,
path and supplied state flags), with explicit total/truncation above 100
observations. Validation keeps mapping-valued compatibility as an error with
portability guidance, warns once for non-spec top-level keys, and warns when
description plus `when_to_use` exceeds 1,536 characters.

**[SPEC] `claude_listing` — the "what the model sees" estimate (R13).** One
read-only section estimates Claude Code's skill listing from the instances in
the `claude-code` scope, plus project `.claude/skills` instances only when the
caller supplied a `project_root` (otherwise `project_skills.state` is
`unavailable` and says so). Entries are one per listed skill: a `skillOverrides`
state of `off` is excluded, `name-only` contributes its name only, and every
other listed skill contributes its name plus
`min(len(description + when_to_use), cap)`. The cap is
`skillListingMaxDescChars` from the same settings sources `native_state` reads,
defaulting to 1,536; `SKILL.md.disabled` instances are never listed.
`listing_chars` sums the entries, `listing_tokens_estimate` comes from
`tokens.count_tokens()` with its method reported, and the budget is the
`SLASH_COMMAND_TOOL_CHAR_BUDGET` value when it is a positive integer, otherwise
`skillListingBudgetFraction` (default 0.01) times `WINDOWS[window]` with
`budget_chars_estimate = tokens x 4` and the conversion stated as an
assumption. `status` is `within_budget`, `over_budget_estimate`, or `unknown`
when a settings source exists but could not be parsed (`confidence: "partial"`;
the numbers are still computed). It also reports `chars_to_free`, an
`over_cap` count and names, and `name_only_candidates` (R13): listed skills
sorted by description size, bounded to 25 with `total`/`omitted`, each with a
home-redacted path and the `freed_chars` switching to name-only would save.
Those candidates are ordered **by size only** — Claude Code drops descriptions
starting with the least-invoked skills, which this tool cannot observe, so it
never claims which descriptions are actually dropped. One advisory `info`
finding appears under `claude-listing-budget` when the estimate is over
budget. `hygiene_report()` accepts an optional `window` (default
`tokens.DEFAULT_WINDOW`; an unknown value is a clean `HygieneError`). No CLI
command, REST route, Store method, SQLite state, write, or network request is
added.

**[SPEC] `agents_bridge` — explain-only H2 (2026-11-08).** With `scope=all`,
`hygiene_report()` lists enabled, readable instances whose scopes (aliases
included) contain `agents` but not `claude-code` and whose name has no `claude-
code` copy, bounded by `MAX_BRIDGE_NAMES = 50`. It cites Claude Code's
documented roots, offers the existing `sync` copy and a caveated manual link as
remedies, emits one `agents-bridge-gap` info finding, and writes nothing. Other
scopes report `state: unavailable`; a truncated scan reports `state: partial`
and names nothing, because the missing copy could be past the limit.

**[SPEC] `agent-parse-risk` (2026-11-13).** Validator warnings in
`validator.SILENT_FAILURE_MESSAGES` (empty frontmatter block, unquoted `: `,
byte-order mark before `---`) become one `agent-parse-risk` warning per
instance; previously the report surfaced only validator errors.

**[SPEC] `codex_config` (2026-11-13).** For the `codex` and `all` scopes the
report adds a home-redacted `codex_config` section from
`native_state.codex_config_dead_entries()` and one `codex-config-dead-entry`
warning when any entry matches no skill; other scopes report it
`unavailable`. Nothing is written.

**[SPEC] `codex_listing` (2026-11-13, round 2).** Estimates Codex's skill
listing from enabled, readable `agents`-scope instances (Codex's documented
USER root), excluding `SKILL.md.disabled` and `[[skills.config]]`-disabled
skills. Each line is `- name: description (file: path)` with the description
cut at 1,024 characters and costed `ceil(utf-8 bytes / 4)` tokens; the budget
is 2% of the report window, replaced by an assumed `gpt-5.6` window (and
said so) when the window is not a GPT model. Project, admin and bundled roots
and a configured token budget are unread, so `confidence` is `partial`. One
`codex-listing-budget` info finding when over budget (codex#19679,
codex-rs/ext/skills/src/render.rs).

**[SPEC] `opencode-output-truncation` (2026-11-13, round 2).** An enabled
instance in a scope OpenCode reads (`opencode`, `agents`, `claude-code`)
whose `SKILL.md` exceeds 2,000 lines or 50 KiB gets one warning: OpenCode
keeps only the head of a tool result (opencode#62718). Only documents whose
body is near either limit are opened (bounded at 8 MiB); nothing is written.

## `key_support.py`

Pure, stdlib-only table of the frontmatter keys each consumer documents, copied
from @docs/34-agent-skill-loading-research-2026-11-07.md: `claude-code`,
`claude.ai-api`, `codex`, `gemini`, `opencode`, `cline`, `kiro`, `amp`, `roo`
and `zed`, each with its source URL. `BEHAVIOURAL_KEYS` is the Claude Code set
that the hygiene finding cares about. `documents(consumer, key)` answers the
one question the finding asks (a dotted entry such as
`metadata.opencode/autoinvoke` documents its top-level key), and `documents_anywhere(key)` checks across the recorded consumers.
`known_consumers()`, `label()`, `source()` and `documented_keys()` expose the
recorded evidence.
Nothing here reads the filesystem, writes, caches, or makes a network request,
and no `Store`/REST/CLI surface is added.

## `registry.py`

Stdlib-only skills.sh network boundary used by the existing install surfaces.
`RegistryClient` implements bounded browse/search/curated reads and snapshot
fetches, optional bearer authentication, private auth-scope-isolated cache
entries, explicit stale-cache fallback, and clean response/redirect errors.
`validate_snapshot()` checks canonical text-file paths, resource limits, the
upstream-compatible registry hash, and the manager's framed local
`snapshot_hash()`. `materialize_snapshot()` performs symlink-safe atomic
staging. `provenance_for_snapshot()`, `write_provenance()`, and
`read_provenance()` maintain and reconcile the credential-free
`.skillsmgr-provenance.json` sidecar; loader observations expose valid
provenance or a fail-closed error. No network request occurs at import time,
SQLite is not used, and no `Store` method is added. Full decisions:
@docs/ADR-005-registry-network-and-provenance.md.

## `source_lock.py`

DEL-07's filesystem-owned evidence and review seam. `source_identity()` accepts
bounded local, Git, archive, and registry identifiers without credentials;
`local_manifest()` hashes a bounded regular-file tree without following
symlinks; and `preview_local_update()` compares every file, distinguishes
missing from inaccessible sources, explains CRLF/LF-only changes, validates the
candidate, and attaches advisory `risk_scan()` findings. `review_local_update()`
creates a stale-detecting review id; `commit_local_update()` requires explicit
approval and a snapshot root before atomically replacing the target; and
`restore_source_snapshot()` provides an explicit rollback seam. The
`.skillsmgr-source-lock.json` sidecar is bounded, atomic, owner-only, and
excluded from content hashes. `MAX_TOTAL_DIFF_LINES` adds a deterministic
whole-preview budget while preserving per-file bounds and binary-safe evidence.
`risk_file_listing()` gives `risk_scan()` a bounded `{path, contents?}` listing of a staged candidate (symlinks skipped, `SKILL.md` and sidecars left out, at most 50 script files of 256 KiB read as UTF-8, everything else listed by path only); the registry fetch/commit and source-update reviews pass it together with the description, so the bundled-script, bytecode, `ast` and description checks run on real reviews. The caller-facing review/apply workflow lives in `source_update.py`; it adds no
Store method, SQLite state, network, or runtime dependency. Decision record:
@docs/ADR-008-source-lock-and-update-preview.md.

## `source_update.py`

Filesystem-owned orchestration for the approved safe local update workflow.
`prepare_local_update()` and `prepare_snapshot_update()` resolve one observed
physical scope instance, normalize a private candidate, persist bounded
expiring review evidence, and return validation, advisory-risk, diff, identity,
activation, and recovery evidence. `commit_update_review()` applies only the
unchanged staged candidate through `source_lock.commit_local_update()`, marks
the review single-use, reconciles the global index after filesystem success,
and retains opaque whole-tree snapshots. `read_update_review()`,
`cancel_update_review()`, and `list_update_snapshots()` are module functions,
not Store methods. Review artifacts live below private
`source-update-reviews/`; snapshots live below
`source-update-snapshots/`. Stable `SourceUpdateError.code` values are mapped
by the CLI and REST adapters; no staged private path or credential-bearing
source identity is returned.

## `review_artifacts.py`

**[SPEC]** Shared review mechanics for registry installs, source updates and
backup sync: id/header/status checks, expiry interpretation, JSON encoding,
credential-key rejection, size checks and private registry writes. The callers
retain storage layouts, TTL/size policies, JSON framing, public projections,
exception classes/codes, locks and cleanup. Backup sync preserves unnormalized
symlink ancestry checks; source updates and sync retain `atomic_write_text` and
its directory-move failure cleanup. The module is covered by the complexity
ratchet and `tests/test_review_plumbing_characterization.py` plus
`tests/test_review_artifact_failures.py`.

## `backup_sync.py`

DEL-09 review-first planning and integration seam. `build_manifest()`
normalizes bounded, sorted skill/file digests with credential-free source
labels; `dry_run()` reports exact local and remote changes plus three-way
conflicts; `three_way_plan()` keeps the default conflict action at review and
reports explicit keep-mine, use-remote, or keep-both choices; and
`interrupted_sync()` exposes completed/pending work and a retryable snapshot
handle. `git_remote_info()` and `git_fetch()` use a trusted Git executable,
delegate auth to configured Git helpers/SSH agents, and reject credential-
bearing remote URLs. Every Git invocation pins program-executing configuration (`core.sshCommand`, `core.fsmonitor`, `core.hooksPath`, `core.askPass`, `core.gitProxy`, `diff.external`, `uploadpack.packObjectsHook`, `ext`/`file` protocols) with `-c`, sets `GIT_SSH_COMMAND=ssh` and `GIT_CONFIG_NOSYSTEM=1`, and drops inherited `GIT_SSH`/proxy/askpass variables, so a hostile repository's local config cannot run a program (R16). `prepare_sync_review()`/`read_sync_review()` persist and
inspect private expiring manifests and plans; `commit_sync_review()` rechecks
the candidate and applies only through the existing source-lock snapshot,
atomic replacement, and rollback seam. No CLI command, Store method, or
SQLite state is added. Decision record:
@docs/ADR-009-backup-sync-dry-run-planner.md.

## Sidecar bindings and agent recovery

**[SPEC]** `sidecar_binding.py` records physical install path and sidecar-byte
digest under the private manager data root. Copied, edited or preexisting
unrecorded provenance/source-lock files do not become trusted declarations.
`scopes.scope_trash_list()` and `restore_trashed()` provide bounded agent-scope
trash discovery and exact-copy restore; the existing REST trash endpoints
select the requested scope. `loader.scan_dir(link_roots=...)` and scope reads
can inspect directory links contained in another known agent root, mark them
`read_only`/`link_followed`, and retain their physical alias identity. Writes
continue to use the original containment path; the global store never opts in.

## `bundles.py`

Pure DEL-10 integrity foundation. `canonical_manifest()` accepts a bounded
version-1 member manifest and produces deterministic bytes; `bundle_digest()`
hashes those bytes; `sign_manifest()` and `verify_manifest()` provide detached
HMAC-SHA256 evidence with key fingerprints, tamper/wrong-key/revocation
reasons, and the explicit limitation that this is shared-secret group
integrity only. The module never reads keys from the environment, creates an
archive, transports a key, publishes, imports, writes, or adds CLI/REST/Store/
SQLite behavior. The crypto/distribution/metadata policy and the unimplemented
archive boundary remain in @docs/ADR-004-team-sharing-signed-bundles.md.

## `web_security.py`, `web_serialization.py`, `web_upload.py`

Private stdlib-only web policy modules. They own loopback **request** validation (`web_security.validate_request` runs for `GET`/`HEAD` as well as the mutating verbs; `validate_mutation_request` is kept only as an alias), JSON body/response helpers, multipart parsing, bounded upload staging, and per-skill upload results. Upload staging decides each destination path before writing (`web_upload._stage_path`), so a filename that is both a file and a directory in one upload — in either part order — is a clean `400` naming the conflict rather than a raw `IsADirectoryError` HTTP 500, and no raw exception text becomes the client's error message (SEC-6). `webapp.py` retains compatibility wrappers and route ownership.

## `diagnostics.py`

Private stderr-only diagnostics for recovery and optional-enrichment failures; it does not change public return values or REST/CLI schemas. CLI Doctor adds a bounded `degraded` entry when JSON enrichment is incomplete, while human output retains the base result and points to stderr diagnostics.

## `launcher_security.py`

`trusted_executable()` is the shared resolver for the dev-only browser harness
and optional desktop launcher. It checks that a PATH candidate resolves to a
regular executable, skips unsafe earlier matches, and on POSIX requires the
file and its parent directories to be owned by the current user/root and not
writable by other users (with the standard sticky-directory exception for
temporary roots). The browser harness keeps Chrome's sandbox enabled and pins
its ephemeral DevTools listener to `127.0.0.1`.

## `check_complexity.py`

Repository-only AST complexity ratchet for the web, CLI, store, and frontmatter hotspots. `complexity-baseline.json` records existing violations and fails on new over-budget functions or metric increases.

## `atomic_io.py`, `archive.py`, `path_safety.py`, `root_discovery.py`

Internal policy modules extracted from the former Store/scopes hotspots. They
own atomic text writes and tree hashes, archive preflight/extraction/staged
commit behavior, trusted data-root validation, resolved root-containment, and
physical-root/capability/instance-state observations. `archive.open_tar()`
reads a tar through a position-capped decompressed view (`_BoundedReader`,
`MAX_ARCHIVE_DECOMPRESSED_BYTES`) and validation walks members one header at a
time, so no cap waits for a full `getmembers()` listing (R1). `paths.py` remains a
compatibility adapter for the existing containment function names.

## `effective.py`

Read-only effective-resolution diagnostic behind `doctor --explain CONSUMER
[--project DIR] [--skill NAME]` and `GET /api/doctor?explain=…` (issue #12).
`explain()` derives, at read time, which instance of a skill a consumer would
load for one `(consumer, project-CWD, skill)` triple, and returns a
JSON-serialisable report: `resolution`, `policy`, per-skill `winner`,
`shadowed` (each entry carries the winning tier as `shadowed_by`), `also_loads`,
the `tiers` actually read with their `instances`/`skipped` detail, `warnings`,
`unobservable_tiers`, and the cited `source` URL. A root spec is one of
`scope` (a facade root), `rel` (project-relative), `path` (absolute), or
`home` (resolved against `paths.home_dir()` at read time). A `home` root is
confined and redacted exactly like a `path` root: it is never inside the
manager data directory, so the HTTP boundary replaces it with the redaction
marker. Every precedence row lives in `CONSUMERS` and is sourced from
@docs/12-agent-root-discovery-2026-09-08.md, refreshed from
@docs/34-agent-skill-loading-research-2026-11-07.md: `commandcode` documents a
six-way order (project `.commandcode/` > project `.agents/` > user
`~/.commandcode/` > user `~/.agents/` > extras > bundled), `codex` an explicit
no-merge policy (so `policy: "no-merge"` elects no winner and reports every
copy), `claude-code` personal > project with nested copies both loading,
`gemini` built-in < extension < user < workspace, and `opencode` built-in <
`.claude/skills` < `.agents/skills` < `~/.config/opencode/skills` < project
`.opencode/skills` < explicit `skills` config (its config tier is unobservable,
so a lower win is provisional; the earlier "no documented order" row was
corrected on 2026-11-07). The ordered additions are `cline` (global > project;
its three project roots tie as `ambiguous`), `kiro` (workspace > global), `amp`
(first `name` in its documented search order), `roo` (project > global,
`.roo` > `.agents`, mode-specific > generic, with four unobservable
mode-specific tiers), and `zed` (project > user). `cursor`, `copilot` and
`devin` publish roots but no same-name order, so they stay
`undocumented-precedence`. Consumers therefore never get an invented winner: an
unrecorded order yields `undocumented-precedence`, and an unknown consumer
yields `unknown-consumer` with the known list. A missing project directory yields
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
`read_only`/`persists_nothing`. The top-level `resolution` is derived from the
per-skill entries rather than asserted from the policy: `no-instances` when no
skill holds one, `partially-resolved` when some do and others do not, and
`both-load-only` when the only loadable copies are nested ones reachable through
a documented both-load rule (whose entry then lists them as `candidates` instead
of claiming no instance exists). Reads are also deduplicated by *physical*
identity: a root reached through a symlink is recorded per tier as an `alias` and
not read twice, so one file is never reported as two candidates or as its own
shadowed copy (ADR-002 invariant 1).

## `install.py`

**[SPEC] One owner for installing (2026-11-09).** Both front-ends call it, so
neither imports the other. It holds the ecosystem runner allowlist
(`install_runner()`, `uvx` refused), the guard on every value forwarded to a
runner (`install_value()`/`install_source()`: the shared character class, at
most 256 characters, no leading `-`, no absolute, traversal or drive-prefixed
shape), the single argv renderer (`install_argv()`/`install_command_line()`),
`run_install()` (120 s timeout as `InstallTimeoutError`, a `StoreError`,
and the last 8,000 characters of each stream), the offline `registry_bridge_plan()` with its
never-verified trust gate, and the two-step registry install:
`registry_fetch()` enforces fetch-then-commit, trust only on commit, and the
global-only target; `prepare_registry_review()` stages, validates and
risk-scans a snapshot and writes the private review; `commit_registry_review()`
re-validates under `registry.registry_review_lock()`, calls `Store.add`, and
writes provenance into the installed copy or purges it. The HTTP adapter
preserves its timeout response (HTTP 500 with command and execution evidence);
the CLI keeps its 4,000-character JSON stream tails and 8,000-character text tails.

## `risk.py`

`risk_scan()` returns explainable, advisory-only findings (script/link/tool/
pattern checks, bounded hidden-Unicode/bidi/tag code points, and the nine
Phase B checks described below); it never returns a safety verdict or rewrites
input, and a non-dict record raises `ValueError`. `risk_file_listing()` turns a
staged tree into its bounded `{path, contents?}` input. Registry reference
parsing (`registry_reference()`, `owner/repo`, `owner/repo/slug`,
`https://skills.sh/{source}/{slug}`, `https://github.com/owner/repo`; segments
capped at `MAX_REGISTRY_SEGMENT = 96`, other hosts refused) lives in
`registry.py`.

## `context.py`

The `ContextVar` naming the Store that `global` means for the current thread
(`active_store()`, `set_active_store()`, `bound_store()`). It is a leaf so that
`scopes`, `sidecar_binding` and both front-ends share it without importing one
another (SCOPE-10).

## `external_scan.py`

Optional, advisory evidence from an installed NVIDIA SkillSpector. The program is
never imported; `skillspector_evidence()` runs a trusted PATH match
(`launcher_security.trusted_executable`) as an argv list without a shell, on a
private 0700 copy of the staged candidate (a disabled `SKILL.md.disabled` is
renamed in the copy only), with `--format json --output` and, in static mode,
`--no-llm`. It never passes `--transitive`, `--use-shipped-baseline`,
`--recursive` or `--baseline`. The child environment is scrubbed to
`PATH/HOME/LANG/LC_ALL/TMPDIR`; LLM mode adds only the documented provider
variables (`_LLM_ENV`), so a bring-your-own key reaches the tool only when asked
and is never stored or returned. Bounds: 120 s static / 600 s LLM (process group
killed on timeout), 4 MiB report, 200 findings with an `omitted` count, 500
characters per string; `code_snippet` is dropped. Statuses: `completed`,
`incomplete`, `unavailable` (with the reason, including an untrusted
group-writable install), `timeout`, `error`. `scan_options()` normalises the
opt-in (`true`/`"static"`/`"llm"`/`{"llm": bool}`; empty means off) and raises
`StoreError` otherwise. Wired into `install.prepare_registry_review` and
`source_update._prepare_from_source` only; commit and apply never re-run it.
No Store method, SQLite state or runtime dependency.

## `lockfiles.py`

Read-only evidence for lockfiles written by the open-source `skills` CLI
(vercel-labs/skills). `read_lock(path, kind=...)` parses one bounded lockfile and
returns a JSON-safe record; a missing file is `missing`, and malformed JSON, a
non-object root, an unsupported version, a non-dict skill entry, a symlink, or a
file above `MAX_LOCK_BYTES` (4 MiB) is `invalid` with a reason -- it never
raises. Project locks must be version 1 and global locks version 3. At most
`MAX_LOCK_ENTRIES` (500) entries are kept with an `omitted` count.
`sanitize_name()` reproduces the CLI's directory-name rule (lowercase, each run
of characters outside `[a-z0-9._]` becomes `-`, strip leading/trailing `.`/`-`,
truncate to 255, empty becomes `unnamed-skill`). `safe_source_url()` removes
userinfo, query, and fragment from a `sourceUrl` so no credential is echoed.
`computed_folder_hash(dir, order)` reproduces the project lock's `computedHash`
(relative path bytes followed by file bytes, no separators, under a plain
codepoint or case-insensitive ordering; `.git` and `node_modules` are skipped
and symlinks are not files). `skill_folder_tree_sha(dir)` computes the git tree
object SHA-1 used by the global lock's `skillFolderHash`, with blob/tree
headers, git's byte-order entry sort (directories compared with a trailing
`/`), executable/symlink modes, and `.git` skipped. Both hashers share a
per-skill budget of `MAX_HASH_FILES` (2,000 files) and `MAX_HASH_BYTES` (64 MiB)
and raise `LockfileTooLarge` above it. `lockfile_evidence(home,
project_root=None, xdg_state_home=None)` compares each declared skill with its
installed copy (`<root>/.agents/skills/<sanitize_name>`), reports
present/disabled/hash status and summary counts, lists undeclared global
installs (bounded), and returns the project lock as `unavailable` when no
project root context exists. A global `skillFolderHash` mismatch is
`differs_from_recorded_tree`; a project `computedHash` outcome that matches
neither ordering is `mismatch_or_unverifiable` with the ICU-collation
explanation. An `apm.lock.yaml` is reported as an unavailable signal and is
never parsed. `hygiene_report()` folds the section under `lockfiles`; no Store
method, SQLite state, cache, network request, or write is added.

## `ai.py`, `ai_skills.py`

**[SPEC] Bring-your-own-key AI (2026-11-09).** `ai.py` is a stdlib-only client
for Anthropic Messages and OpenAI-compatible chat completions (OpenAI,
OpenRouter, Gemini's compatibility endpoint, Ollama, LM Studio, custom).
Settings live in `<data>/ai/settings.json` (0600 in a 0700 directory); the
provider's environment variable takes precedence over a stored key, and
`public_settings()` never returns the key. `AiRun` preflights every call
against per-run and per-day input-token caps, refuses redirects, bounds
responses at 2 MiB, retries transient provider failures (408/409/429/5xx/529 and network errors, at most twice, honouring `retry-after` up to 20 s; spend-limit and quota codes are final), marks a stable request prefix as an Anthropic prompt-cache breakpoint, counts cached input tokens against the caps, asks current Claude and OpenAI reasoning models for low effort with a 4,096-token thinking allowance, admits each call against the day cap with a cross-process reservation in `<data>/ai/reservations.json` (recorded and in-flight usage), appends counts and an input hash to `<data>/ai/usage.jsonl`,
and parses JSON answers with `extract_json()`. Oversized usage ledgers are
atomically compacted to remove dated rows older than 90 days; append and
compaction share a cross-process lock. `AiRun` checks the requesting client's
connection between calls; disconnects save a partial run with completed-call
usage before stopping. The HTTP handler supplies that request-local check.
`ai_skills.py` builds an agent's
listing (`build_listing`), runs the trigger test (`trigger_test`) and the
held-out-verified description rewrite (`improve_description`), and saves runs
under `<data>/ai/runs/`. Saved regression prompts (A7) live in
`<data>/ai/prompt-sets/`; a saved-prompt run is compared per skill with the
previous one (`save_prompt_set`, `read_prompt_set`). Prompt replacement supports
an `expected_prompts` precondition to reject stale edits, and preserves up to
500 prompts. The v2 AI pages show saved runs as text and let users view and
remove individual regression prompts. `ai_overlap.py` (A3) judges bounded candidate
pairs in both orders and keeps only conflicts quoted verbatim from the files.
`ai_budget.py` (A4) shortens the largest descriptions when a listing exceeds
its budget and marks each shorter version safe only if it still triggers.
`ai_review.py` (A5) briefs a pending update or registry review; every claim
must quote its file, and risk opinions never change a finding. `ai_evals.py`
(A8) produces with/without-skill outputs for `evals.record_runs`, which grades
them with the case assertions; no model grading. `AiRun.ask_text` serves
plain-text answers. `ai_ask.py` (A9) answers "which skill fits" from names and
descriptions only and keeps only skills that exist. `ai_port.py` (A10) finds
portability facts without AI (undocumented keys via `key_support`, agent-specific
references) and lets the model explain only those facts. Both are read-only towards skills; no Store method,
CLI command or SQLite state is added. Rules and decisions:
@docs/39-ai-features-research-and-catalogue-2026-11-09.md.

## `ai_explain.py`

**[SPEC] Risk-finding explainer (A6, 2026-11-13).** `explain_findings` runs
`risk.risk_scan` over one installed skill's record plus its bounded
`risk_file_listing` (no AI), then asks the model for one opinion per finding:
`likely-real`, `likely-false-positive` or `unclear`. Opinions are returned
beside the unchanged findings; no severity is changed and no finding is
hidden. A false-positive opinion must quote text found in the file it names
(the document body or a listed script); otherwise it becomes `unclear` and is
counted in `uncited_demoted`. Opinions about unknown or repeated finding
indexes are dropped and counted. Skill text is wrapped with
`ai.untrusted_block`; at most 30 findings, a 20,000-character body and 15
script files of 6,000 characters are sent. No findings means no model call;
estimate mode sends nothing. Read-only; runs are saved like other AI runs.
A hostile skill can steer the opinion and supply its own quote; the quote check
proves only that the text exists, which is why opinions never change a finding.

## `ai_draft.py`

**[SPEC] Verified drafting (A11).** `draft_skill` produces a bounded SKILL.md
from an untrusted brief, validates it with `validator.validate_text`, and
rejects name collisions, unsupported frontmatter, descriptions over 1,024
characters and bodies over 500 lines. Validation errors prevent routing and
use. A valid draft is added to the full scope listing for A1 routing, with
generated draft prompts, near misses and a bounded sample of existing skills.
Baseline-versus-augmented routing identifies prompts taken from existing
skills; sample coverage and missing/invalid answers are reported. Estimate
mode sends nothing. Results live in the existing AI run history. The v2 tool
fills the existing New skill form without saving; ordinary explicit creation
remains the write path.

## `ai_concise.py`

**[SPEC] Conciseness advisor (A13).** Deterministic section counts use
`tokens.count_tokens`; headings inside fenced code do not start sections.
The model proposes a shorter primary document and new `references/*.md`
files. Paths, sizes, links and collisions are checked before staging. A
bounded captured tree preserves companions and binds the proposal to the
observed source content hash across the model call. Changed content invalidates it.
`source_update.prepare_local_update` creates the ordinary whole-tree review;
the existing reviewed commit takes a snapshot and applies it atomically.
Model output is never written directly to the installed skill. The shared
JSON decoder preserves Markdown fences inside model-returned JSON strings.
Estimate mode
sends nothing and creates no review. Computed primary and reference counts
are reported with their counting method; semantic equivalence is not claimed.

## `ai_profiles.py`

**[SPEC] Profile suggestions (A12).** `suggest_profile` first uses
`adapters.project_observation` with server-owned managed roots. Outside or
unavailable projects return redacted errors before project enumeration or
provider calls. Descriptor-anchored scanning collects only extension counts,
known manifest names and top-level directory names, with depth/item limits
and a truncation flag; project files are never opened. The model sees these
signals and bounded skill metadata, with path-like description tokens
redacted. Readable disabled skills are eligible. Invented skill names are
dropped and names are deduplicated. The suggestion writes no catalog entry;
the v2 user confirms a save or overwrite through the existing catalog API.
No native agent settings are changed. Safe scanning requires the same POSIX
descriptor support as conciseness capture.

## `tools/ai_fidelity/run.py`

**[SPEC] Developer-only fidelity preparation.** Consumes a saved prompt set and
its complete saved trigger simulation, validating their exact tuple join and
rejecting tied, missing or invalid choices. Default dry-run starts no child
process. Maintainer-attended execution needs two explicit flags and observes
successful Skill tool calls/results from the agent stream. Failed/incomplete
cases are inconclusive, not no-skill choices. Agreement measures the first
successful skill choice; multiple loads are reported separately. Reports keep
hash provenance and skill/model labels, without raw prompts, transcripts or
stderr. The tool is excluded from distribution artifacts. Its restricted tool
context and absent historical listing snapshot limit what a comparison can
establish. The guarded developer `study_fixture.py` reproduction and sanitized
evidence demonstrate two conclusive synthetic agreements using a native-CLI
simulator adapter; they do not establish general fidelity or validate the
product's HTTP transport. Method: @docs/41-ai-fidelity-study-2026-11-09.md.

## `tools/verify_ai.py`

**[SPEC] Development-only repeat automation.** Runs free AI contracts, verifies
the retained study's exact hashes and recomputed accounting, and optionally
probes an explicitly supplied wheel from an isolated virtual environment with
clean HOME/environment and a fake loopback provider. The existing CI unit matrix
uses its evidence/no-send check and the package job probes the exact built
wheel before upload. No real credential or native agent is needed. Invocation
and limits: @docs/43-ai-verification-automation-2026-11-10.md.

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
`record_runs()` normalizes and scores runs before writing; it rejects duplicate
`(case, variant)` pairs, stages the complete iteration, and atomically replaces
that iteration so failed writes cannot leave partial or stale results. Commit
rollback handles interruptions and preserves an unrecoverable backup for repair.
Workspace checks cover lexical and resolved containment, including symlink
aliases beneath the managed `skills/` tree. It writes `outputs/output.txt`,
`grading.json`, `timing.json` per variant and a per-iteration `benchmark.json`
through atomic sibling-temp writes. Bounds: `MAX_CASES = 100`, `MAX_EVALS_FILE_BYTES = 1_000_000`,
`MAX_CASE_TEXT = 20000`, `MAX_OUTPUT_TEXT = 200000`, `MAX_RUNS = 400`,
`MAX_PATTERN_LENGTH = 200`, `MAX_REGEX_INPUT = 50000`. `EVAL_POLICY` records
the standing rule: results are workspace files, never SQLite rows, and never
gate installs or edits, and results sort deterministically.

**[SPEC] `risk_scan()` also runs nine single-purpose Phase B checks over
caller-supplied data only** (`name`, `description`, `body`, and an optional
`files` listing of `{path, contents}` entries; no filesystem read is added):
remote script piped to a shell (`curl`/`wget … | sh|bash|zsh`, PowerShell
`iex (iwr …)`/`Invoke-Expression (Invoke-WebRequest …)`), decoded payload
executed (`base64 -d | sh`, `eval(atob(…))`, `exec(base64.b64decode(…))`,
`exec(codecs.decode(…))`), credential paths (`~/.ssh/`, `id_rsa`,
`.aws/credentials`, `.netrc`, `.env`, the macOS keychain
`security find-generic-password`, `~/.config/gcloud`, `~/.kube/config`,
`.npmrc`), refusal/disclaimer suppression wording (English only; the finding
policy states that limit), persistence (`crontab`, `systemctl --user`,
`~/.config/systemd/user`, shell-rc append/redirect writes, `LaunchAgents`),
shipped `__pycache__`/`.pyc` from the listing only, whitespace padding (at
least 200 consecutive spaces/tabs or 30 consecutive blank lines, both stated in
the evidence), over-broad description triggers plus exact shadowing of a small
built-in command list, and `exec`/`eval`/`compile`/`__import__`/`os.system`/
`os.popen`/`subprocess.*(shell=True)` in bundled `.py` sources parsed with
stdlib `ast` (never imported or executed; at most 50 files and 256 KiB each,
with `SyntaxError`, oversize and count-limit skips reported as counted notes).
A match that sits in a warning or negation sentence (`do not`, `don't`, `never`,
`avoid`, `instead of`, `unsafe`) is still reported, but at `low` with that
reason in `why`; fenced code blocks are not exempt. Evidence is escaped and
length-bounded, the new findings are capped at `MAX_RISK_FINDINGS` with an
omitted note, and every finding stays advisory.

Operates on records the existing `scopes`/`loader`/`Store.history` seams
already return; no new CLI/Store surfaces, no schema change.

## `tokens.py`

Token/context estimation. `window_name()` validates a requested context, and
`aggregate(records, window)` owns totals and context percentages. `WINDOWS` dict (claude 1M, claude-haiku 200k, gpt-5.6 1.05M, gpt-5 400k, gpt-4o 128k, gemini 1M, gemini-2m 2M), `DEFAULT_WINDOW = "claude"`. Uses tiktoken when installed, else chars/4 heuristic. `estimate(text)`, `aggregate(records)`.

## `paths.py`

`data_dir()`, `db_path()` (see @docs/01-architecture.md). Environment-selected
roots are canonicalized through `path_safety.trusted_root()` and fail closed on
unsafe ownership, permissions, filesystem roots, or non-directories. Subdirs
resolved relative to data dir: `skills/`, `trash/`, `templates/`, `backups/`.
`contained_path()` resolves and rejects paths outside a managed root;
`safe_skill_path()` combines it with `validator.validate_skill_name()`.

## `frontmatter.py`

SKILL.md frontmatter (YAML-ish, delimited by `_DOC_MARKER`): `parse_frontmatter(text)` -> (frontmatter dict, body), `dump_frontmatter(frontmatter, body)`; bool/None/str coercion; raises `FrontmatterError` on malformed input. Duplicate keys are rejected as clean `FrontmatterError` in every mapping form (block, inline `- key:`, continuation, flow maps) instead of resolving last-wins. The dumper round-trips its own output (flow items with special characters and keys with quotes are quoted) and raises `TypeError` for mappings nested inside flow lists, which the parser grammar cannot express.

## `validator.py`

Name rule: `NAME_RE = ^[a-z0-9]+(-[a-z0-9]+)*$` (rejects `--`, leading/trailing hyphens); limits: `MAX_NAME=64`, `MAX_DESCRIPTION=1024`, `MAX_COMPATIBILITY=500`, `MAX_BODY_LINES=500`, `MAX_BODY_TOKENS=5000`. `validate_skill_name(name)` is the authoritative fail-closed primitive used by Store, scopes, CLI, and REST-adjacent path handling. `Issue` dataclass (level, message, key). `validate_skill(name, skill_dir)` -> `ValidationResult` (`.valid`, `.errors`, `.warnings`, `.issues`). `description_score(text)` -> `{has_use_context, filler_hits, word_count}`. Validators cover: name format, frontmatter name vs directory name, description length + use-context/filler warnings, compatibility length, body line count + token warning, `scripts/`/`references/`/`assets/` layout mentions, and relative link targets normalized for URL fragments, queries, percent-encoding, and sentence punctuation. Three advisory warnings cover frontmatter an agent's parser would silently drop: an empty delimited block (`frontmatter` key), an unquoted `: ` inside a top-level plain scalar (that key), and a UTF-8 byte-order mark before `---` (`frontmatter` key; Codex skips such a skill, openai/codex#13918), all read from the raw text and never changing `valid`.

## `search.py`

Pattern `*` -> `.*`, `?` -> `.`, case-insensitive; repeated stars collapse, queries are limited to 200 characters and 10 effective stars, and invalid complexity raises `ValueError`. Scoring: 100 exact name, 90 fullmatch, 80 prefix, 70 name regex, 60 name substring, 40 description/body regex, 30 category regex, 25 description/body substring, 0 no match. `rank_results(records, term)` returns (record, score) tuples.

## `templates.py`

Templates are `<data>/templates/*.md`; `TEMPLATE_NAME_RE`; `DEFAULT_TEMPLATE` string. `list_templates(dir)`, `read_template(dir, name)`, `create_template(dir, name, body=None)` (raises `ValueError` on bad name, `FileExistsError` on dup).

## `colors.py`

TTY auto-detect; honors `NO_COLOR` and `FORCE_COLOR`; `color(text, code)` and styled helpers.

## Smoke tests

- `check_package_data.py` — verifies the complete web UI inside the built wheel and sdist; `--dist-dir` inspects the exact artifacts CI publishes and, with `--install`, also installs them into fresh temporary venvs. It asserts PEP 639 `License-Expression: MIT`, `License-File: LICENSE`, byte-identical license payloads, and no deprecated license classifier, then checks the vendored Vue bundle against the recorded upstream version/sha256/size (SEC-9) — including the copy inside each artifact — and inspects **every** archive member, so a build shipping `tests/`, `docs/`, `.env`, a database or bytecode fails (BUG-13/SEC-13); `MANIFEST.in` prunes `tests` from the sdist. `browser_harness.py` — dev-only system-Chrome CDP probe (sandbox enabled, loopback-only ephemeral port, trusted executable discovery). `desktop_launcher.py` uses the same resolver.
- `smoke_store.py` — exercises the Store API (init, add, list, get, search, disable, enable, trash, restore, purge, export, import round-trip, stats, history, resync, db_rebuild). Must pass after any `store.py` change.
- `smoke_web.py` — starts `WebAppServer` on an ephemeral port and hits every REST endpoint (static, CRUD, search, validate, toggle, stats/doctor/history, templates, export→import, trash/restore/purge, rebuild/resync, multipart upload, error paths). Must pass after any `webapp.py` change.

## `native_state.py`

Read-only bounded JSON observations for Claude Code skill visibility,
OpenCode skill permissions and the Gemini CLI skill switches, plus bounded
TOML observations of Codex `[[skills.config]]` (stdlib `tomllib`, so Python
>= 3.11). `observe_native_entries()` is the per-row seam `scopes` calls:
Codex matches an absolute `SKILL.md` path, so it is observed per row
(`observe_codex_states()`), while every other consumer shares one name batch.
A Codex `path` entry is canonicalized and must name one `SKILL.md`; a `name`
entry matches every same-name skill; the last matching entry wins; an entry
with zero or two selectors or a non-boolean `enabled` is counted under
`invalid_entries` and ignored; at most 1,000 entries are read.
`observe_native_states()` loads each selected source once per scope batch;
`observe_native_state()` serves one name. Nothing is cached across requests or
written. Reports disclose selected declarations with explicit uncertainty, not
effective loading. See @docs/12-agent-root-discovery-2026-09-08.md for file
ordering and parser bounds.

Gemini CLI sources, lowest to highest precedence, are the system defaults file
(`GEMINI_CLI_SYSTEM_DEFAULTS_PATH`, otherwise `/etc/gemini-cli/system-defaults.json`),
`~/.gemini/settings.json`, `<cwd>/.gemini/settings.json`, and the system
overrides file (`GEMINI_CLI_SYSTEM_SETTINGS_PATH`, otherwise
`/etc/gemini-cli/settings.json`). The documented system paths are Linux-only;
on other platforms those two sources report `unavailable` with a reason rather
than an invented path. `skills.disabled` is a name list with `mergeStrategy:
UNION`, so any readable file that lists the exact name (case sensitivity is not
documented, so matching is exact only) is enough for `observed_setting:
"disabled"`; `skills.enabled: false` and `admin.skills.enabled: false` disable
every skill. `skills.enabled`/`admin.skills.enabled` resolve to the last
declaration in precedence order. A wrong type is that source's `invalid`
declaration (reported under `invalid_keys`), never an exception; at most 1,000
disabled names and 512 characters per name are accepted. Environment variables
and CLI arguments rank above every file and are not observed, so `partial` is
always true and `effective_state` stays `unknown`. When nothing readable
disables the name, `observed_setting` says `"not disabled by the files read"`.

`codex_config_dead_entries()` (2026-11-13) lists Codex `[[skills.config]]`
`path` entries that can never match a skill: a folder (with the `SKILL.md`
path to use when one exists), a missing file, or a file not named `SKILL.md`
(openai/codex#51044). Entries behind an unreadable directory are not
reported; at most `MAX_DEAD_ENTRIES` (50) are listed with `total`/`omitted`.
Read-only.

`observe_claude_listing()` reads the two documented listing-budget keys
(`skillListingMaxDescChars`, `skillListingBudgetFraction`) from the same three
Claude settings files, with the same `_load` bounds and typed validation, plus
the `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment variable. It returns ordered
per-file `sources` evidence, an `invalid_keys` list for a declared value that is
not usable, `max_desc_chars`/`budget_fraction` resolved as the last declaration
across `user` -> `project` -> `project-local`, `env_budget` evidence, and
`partial: true` only when a file exists but could not be parsed (a `missing` or
`unobserved` source cannot hide a declaration). It establishes no effective
state and writes nothing.

**[NOTE] `observed_setting` no longer requires a project context.** The rule
observation treats an `unobserved` source (the caller supplied no project) the
same as `missing` when deciding whether the last Claude declaration is worth
reporting; `partial` and `effective_state: "unknown"` are unchanged, because a
project file that was never read could still override it. Without this, no
`skillOverrides` declaration could ever be observed from the CLI or REST paths,
which never pass a project root.
