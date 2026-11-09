# Codebase Untangling — Decisions and Continuation

**Version 0.1.0**

**AI manifest**: Decision log for the 2026-11-09 untangle-codebase session,
continued from Claude in Codex. Read this before changing its shared module
boundaries or declaring the refactor complete.

## Scope and checkpoint

**[SPEC]** Preserve intended CLI, HTTP and documented Python API behavior;
filesystem authority, schema, public Store methods, dependencies and UI
framework stay unchanged. The previous user answer was “do the best”; the
session selected Comments and Tests. Keep comments recording external policy
and regression tests that exercise behavior.

**[NOTE]** Work continues in `.claude/worktrees/untangle-codebase-48bb34`.
Claude stopped after eight commits at `2ccf26b`, leaving five frontend files
dirty. Its session was idle before Codex edits. The primary checkout is dirty
with unrelated work and is untouched. Pending files and the original decision
log were backed up outside the checkout; the non-destructive checkpoint is
`refs/wip/untangle-before-codex-20261109`.

## Continuation findings and planned fixes

- Restore documented Python API boundaries while implementation stays with
  its domain owner.
  - `insights.py` and its contract tests were deleted despite documented,
    exported advisory helpers and ADR consumers.
  - `cli.py` lost its explicitly exported handlers and `COMMANDS`.
  - Shared installer guards differ from the strict original insights API.
- Preserve transport-specific presentation around shared execution.
  - Installer timeout changed HTTP 500 plus command/executed evidence to a
    generic 504. CLI JSON output also grew from 4,000 to 8,000 characters.
- Validate the requested eval input at the CLI file boundary.
  - Explicit runs files with absent/null `runs` now become read-only reports.
- Use the same managed-link policy for scope doctor and scope listing.
  - Doctor's direct loader call omits managed peer roots; an unreadable root
    can look clean. Preserve grouping directories in recursive scope scans.
  - CLI doctor names need existing terminal sanitization.
- Finish the interrupted tool-page inventory consolidation and verify it via
  the actual JS modules, including optional module loading in test harnesses.

- Move read coalescing into a shared, dependency-free read module.
  - `scopes.py` still imports `store._coalesced_read`; per-request sharing
    has no SQLite or Store dependency and changes independently of storage.

- Share descriptor-based bounded file acquisition, retaining caller policies.
  - Native JSON/TOML readers duplicate acquisition; eval and lock readers
    stat a path and then read it without a byte cap. Concurrent growth defeats
    the advertised limits. Parsing, error presentation and final-link policies
    remain distinct in their owners.
- Bind the viewport harness through `context.bound_store`.
  - The full browser ladder found its remaining call to the removed
    `scopes.set_global_store` convenience alias.

## Original inventory and redesign

**[NOTE]** The following inventory is preserved from the previous session.
Its proposals are hypotheses, checked against public contracts during
continuation; the final disposition below supersedes unsupported deletion
claims (especially the documented insights API).

Additions chosen: Comments + Tests (user: "do the best").

### Raw findings — my own
- webapp.py:123 imports cli_handlers._prepare_registry_skill/_commit_registry_review (front-end -> front-end).
- webapp.py:1980,2072 import cli_handlers.validated_install_source/value.
- insights.py: 10 of 17 public helpers have no production caller (consumer_view, diff_skills, diff_three_way, ownership_states, update_preview, quarantine_plan, registry_preview, eval_plan, eval_score, bundle_policy).
- insights.py is grouped by milestone, not domain: risk_scan (used by source_lock, registry install), install_argv (CLI+web), registry_reference (registry.py lazy import).
- insights._INSTALL_VALUE_RE duplicates cli_handlers._SAFE_SOURCE_RE; runners list duplicated.
- _prepare_registry_skill and _commit_registry_review_unlocked duplicate staging+validate+risk_scan+inspection dict.
- _fetch_registry_skill: compatibility adapter.
- cli.py: 18 private alias re-exports, only 4 used (by a compatibility test).
- webapp.py:452-630 batch planning + another tree hash (_batch_tree_hash) lives in the HTTP layer.
- graph: validator<->loader cycle, path_safety->validator, sidecar_binding->scopes, loader->registry, effective->scopes, templates->store, atomic_io->paths/path_safety lazy.

### Raw findings — store/loader/scopes agent (verified grep)
- toggle written twice: store.py:2108-2166, scopes.py:1232-1272.
- SKILL.md / SKILL.md.disabled literals in ~15 modules; loader._ACTIVE/_DISABLED_DOCUMENT private.
- both-documents check: loader.conflicting_documents, archive.has_skill_document (489), loader._probe_document, source_update:404, lockfiles:430.
- trash timestamp format in 4 places (store._trash_timestamp, _TRASH_TS_RE, scopes:978/993, _TRASH_TAIL_RE, _SNAPSHOT_ID_RE).
- UTC iso format repeated in 7+ modules; store.now_iso canonical.
- trash-move collision loop dup (store:1936, scopes:975, store._unique_dest, _write_snapshot_bytes).
- lock helpers: _with_skill_lock/_with_index_lock/_with_scan_lock same body.
- scopes imports store._write_snapshot_bytes, _coalesced_read, _atomic_write_text, _mutation_lock.
- sidecar_binding reads scopes._GLOBAL_STORE and atomic_io._LOCK_ROOTS.
- templates imports store._atomic_write_text/_mutation_lock.
- store wrappers: _safe_skill_path*, _observed_skill_path, _tree_content_hash, _atomic_write_text, _mutation_lock, _reject_both_documents, _load_skill.
- store.py:726-900 nine archive adapters translating ArchiveError->StoreError (one dead: _normalize_archive_member_name).
- 8 lazy loader imports in store probably unnecessary.
- dead: path_safety.realpath_or_none, paths.find_skill_dir, store._move_within_tree.
- root_discovery wrapped by 4 trivial scopes wrappers.
- templates.TEMPLATE_NAME_RE alias.
- scopes: 11 `if scope_id == "global"` forks.
- scopes:537,713,743 except Exception swallow token enrichment; sidecar_binding:160,172 except Exception.
- webapp calls scopes._scope_by_id, _safe_scope_skill_path; cli imports _bound_global_store.

### Raw findings — registry/update/sync agent
- tree walk+hash in 7 places: source_lock.local_manifest(89), source_update._manifest/_reject_unsafe_tree(319-352), atomic_io.tree_content_hash(380), registry._local_file_manifest(1058), registry.snapshot_hash/registry_snapshot_hash(209-239), lockfiles(196), backup_sync(137), webapp._batch_tree_hash.
- source_lock.local_manifest and risk_file_listing: two rglob passes with own skip sets.
- sidecar filename constants defined 3x (registry:56, source_lock:34, source_update:48).
- bind-or-unlink dup: registry._bind_provenance(1120), source_lock._bind_source_lock(308).
- source_lock uses sidecar_binding._record_path; source_update imports store._index_lock_path; cli_handlers imports registry._review_path.
- 24h TTL x3, 16MiB x2; hex64 check 5 ways; _iso x5; _json_bytes x2.
- credential wrappers x2.
- env scrubbing: allow-list (external_scan) vs deny-list (backup_sync).
- source_lock imports insights (risk_scan); risk_file_listing lives in source_lock.
- registry lazy-imports insights.registry_reference.
- backup_sync.py, bundles.py: zero production callers (ADR-004/ADR-009 seams). DEFER to maintainer — product decision.
- source_update.py:111-122 dead py3.10 fallback.
- source_update._stage_candidate: manifest computed 3x.
- sidecar_binding.binding_state except Exception x2 (verdict depends on line).
- insights._record_invalid except Exception -> False (fail-open).
- review_artifacts Fail-callable plumbing exists because 3 error classes.

### Raw findings — diagnostics/validator agent
- consumer layout in 4+ tables: effective.CONSUMERS, scopes.known_scopes, root_discovery.project_scope_specs, adapters project roots tuple; plus native_state paths, key_support, hygiene._KEY_SCOPE_CONSUMERS, adapters._RELOAD. Labels/source URLs duplicated (key_support vs effective).
- 1536 cap: validator.MAX_COMBINED_DESCRIPTION vs native_state.DEFAULT_LISTING_MAX_DESC_CHARS; hygiene.MAX_DESCRIPTION_CHARS=1024 vs validator.MAX_DESCRIPTION.
- bounded file reader x4 (native_state._load/_load_toml identical, lockfiles.read_lock, evals.load_cases) +webapp:475.
- hygiene._bounded == lockfiles._bounded; MAX_STRING x2.
- redaction schemes x3 (hygiene ~, effective <redacted>, adapters own copy); adapters._under_any == effective._under_any (swapped), evals._is_within x2.
- native_state uses Path.home() (SCOPE-17 latent bug) vs paths.home_dir().
- evals slug regex vs NAME_RE.
- validator name rule checked 4x.
- scopes.create vs store.create duplicate field validation; unused NAME_RE/MAX_NAME imports in scopes, store.
- window pct calc x4 (webapp x3, cli x1); unknown-window check x2; webapp:1621 200_000 fallback wrong vs 1M; cli_parser help hardcodes windows.
- hygiene WINDOWS.get dup.
- effective lazily imports scopes to map scope id->path.
- 14 lazy tokens imports with aliases _est2/_agg2/_WW2.
- webapp imports tokens._HAS_TIKTOKEN; cli_handlers uses evals._workspace_is_managed (check runs twice).
- dead: key_support.documents_anywhere, known_consumers, tokens.estimate_skill_text; search.score_match internal only.
- search.compile_wildcard vs native_state._glob_match: two wildcard dialects.
- native_state: 9 consumer-id if-branches.
- hygiene 4x except Exception degraded shape; tokens except Exception on import.
- evals:557 except BaseException swallow.
- hygiene _home_prefix failure -> no redaction (fail-open).
- native_state tomllib ImportError guard dead (floor 3.11).

### Raw findings — frontend agent
- esc x2 (domain.js:67, v2/model.js:15); markdown renderer x2 (domain renderMarkdown vs v2 renderDoc); frontmatter parsers x2.
- theme resolution in 4 places; v2 theme listener never removed.
- locale option list x3 with drifting labels; number/date formatting x3 (tool-center bypasses Intl cache).
- explicit Content-Type JSON repeated ~20x although domain.withJsonType adds it.
- scope query string built ad hoc everywhere.
- doSync x2; blob-download boilerplate x2; coalescing x3; focus-trap selector x2.
- dead: app.js openInstallCenter, openRecoveryCenter, updateReviewIsBlocked, setTextSize; v2/library-tools logicalNames; app.js unused destructure observedStateKeys, deriveLogicalSkillIdentity method.
- localStorage keys repeated; classic unguarded localStorage.
- v2 tool route allowlist x3; state labels drift across files; v2/model 'undecodable' classifier bypasses domain.observedStateFor.

### Raw findings — web/cli agent
- registry fetch/commit rules x3 (webapp:90-148, cli_handlers:193-212,1448-1483); implementation in CLI.
- install value guard x2 (cli _SAFE_SOURCE_RE, insights _INSTALL_VALUE_RE identical); runner allowlist x3 with drifting uvx text.
- install subprocess run x2 with different truncation (web 8000, cli json 4000/text 8000) and timeout mapping.
- doctor enrichment diverged: CLI double scan; degraded names "scope/duplicates" vs "scopes/duplicates"; web doctor ignores non-global scope.
- hygiene record acquisition copy-pasted webapp:284-333 vs cli:771-815.
- eval run recording dup webapp:167-194 vs cli:556-578.
- token document read x3 (two bare utf-8 reads); token window math x4; window validation x2; dead 200_000 fallbacks.
- web scope=global token lookup differs from CLI.
- search dispatch 3 identical branches webapp:1438-1453; list route fork.
- MAX_QUERY_LEN dup with scopes:1527 hard-coded 200.
- web global/agent forks redundant (scopes already branches) webapp:2098,2301,2324,1583,2154,1466,1496.
- scope-default normalization open-coded 14x; bool parse x6.
- stats aggregation in route body.
- _SKILL_FIELDS dup in store/scopes/cli.
- cli.py: re-exports unused; 16 private aliases (4 used only by compat test); ~90 lines plumbing.
- cli_handlers re-aliases cli_output.
- cli_parser.build_parser(commands dict) indirection.
- webapp private reach-ins: scopes._scope_by_id, _safe_scope_skill_path, tokens._HAS_TIKTOKEN; cli registry._review_path, scopes._bound_global_store.
- webapp _json_bytes/_parse_multipart/_upload_folder forwarders; validate_mutation_request alias unused.
- MAX_UPLOAD_PARTS redefined; MAX_BODY_BYTES == web_upload.MAX_UPLOAD_BYTES.
- dead: WebAppHandler._unquote, _expected_origin, cli_handlers._fetch_registry_skill, Colors.dim/cyan/gray.
- raw route double check of documents.
- PUT /api/import string-match "too large" -> 413; inner except flattens 409 to 400.
- skill_not_found code never emitted (_specific_error_code gets str).
- verb handlers x5 same body; source-update path special case in _require_post_media_type.
- 9 except Exception keep-alive sites; webapp:2488 except around set_global_store.
- batch op allowlist x2.
- web_upload limit checks/staging x2.
- make_store mutates colors.COLORS global.

### Redesign (fixes above the problems they solve)
F1 `install.py` owns installing: ecosystem value/runner guards, argv+display, run with one output policy, registry review prepare/commit (one staged-inspection helper), fetch/commit rules. Both front-ends call it.
  - webapp->cli_handlers edges; install guard x2; runner allowlist x3; run x2; registry rules x3; prepare/commit dup; _fetch_registry_skill; registry._review_path reach-in.
F2 `risk.py` owns advisory risk evidence (risk_scan + risk_file_listing). registry_reference moves into registry.py. insights.py deleted; its 10 caller-less helpers + tests removed.
  - source_lock->insights; registry lazy->insights; insights grab-bag; _record_invalid fail-open (goes with dead ownership_states).
F3 `documents.py` leaf owns the on-disk document layout: names SKILL.md/.disabled, conflict check, strict/lossy read, toggle rename. names rule lives in validator top (no loader import).
  - literals in 15 modules; conflict check x3; toggle x2; validator<->loader cycle.
F4 ArchiveError is a StoreError -> nine store adapters go.
F5 Store stops wrapping atomic_io/loader/path_safety one-liners; templates/scopes use atomic_io directly.
F6 one `now_iso` (clock) used everywhere.
F7 sidecar constants + bind-or-remove live in sidecar_binding.
F8 tokens owns window lookup/report; module-level imports.
F9 front-end shared workflows move to domain (doctor scope enrichment, hygiene records, eval record, stats summary); webapp scope param helper; redundant global forks go; cli.py trimmed to main/build_parser.
F10 frontend: dead code, duplicated esc, redundant JSON headers.
DEFERRED (maintainer): delete backup_sync.py / bundles.py (ADR-backed seams, no prod caller).

## Final disposition

**[SPEC]** The inventory is resolved by the following ownership decisions.
The earlier raw deletion proposals are superseded where public compatibility
or different policies require separate entry points.

| Inventory group | Disposition and reason |
|---|---|
| Registry install rules, runners, argument guards and subprocess execution | `install.py` owns them. CLI and HTTP adapt inputs and presentation. Timeout HTTP evidence and the CLI JSON tail limit remain transport contracts. |
| Risk scan, staged risk listing and registry reference parsing | `risk.py` owns risk evidence; `registry.py` owns reference parsing. `insights` keeps its documented pure/advisory API and delegates moved implementations. |
| Enabled/disabled filenames, reads, conflicts and toggles | `documents.py` owns the layout and byte/text rules. Store and agent scopes retain their different locking/index transactions and contextual error messages. |
| Store, template and path pass-through wrappers | Production callers use `atomic_io`, `archive`, `path_safety` and `loader` directly. `ArchiveError` remains a `StoreError`; redundant translation wrappers are gone. |
| Ambient Store binding, lock-root internals and hidden imports | `context.py` owns active binding; sidecar lookup uses the lock-root accessor. Shared read-flight mechanics are in a leaf module. The viewport harness uses a restoring context binding. |
| Timestamp spellings, hex checks, sidecar filenames and binding | `clock`, `atomic_io.is_sha256_hex` and `sidecar_binding` own these rules. Artifact collision allocation uses `path_safety.unique_child`. |
| Doctor, hygiene records, eval recording, exact batch plans and token windows | `doctor`, `evals`, `batch`, `scopes` and `tokens` own their respective workflows. Frontends perform adaptation. Invalid explicit CLI runs cannot silently become read-only reports. |
| Lookup, ranking, scope defaults, HTTP verb handling and upload staging | Scope lookup/ranking and upload staging each have one owner; routes use shared scope/flag parsing and request serving. Index-backed search body semantics stay as before. |
| Bounded reads and duplicate native JSON/TOML acquisition | `file_reads.py` owns descriptor acquisition, file-type checks, byte bounds and cleanup. Each parser keeps its limits, link policy and error shape. |
| Frontend escaping, JSON headers, names and tool-page inventories | The domain transport owns mutation headers and HTML escaping; v2 shares name validation and tool metadata. Tool routes, index and command palette derive from the same inventory. Unused methods, exports and locals are removed. |
| Documented Python facades | `insights`, public CLI exports and `key_support.documents_anywhere` remain. Legacy insight renderer guards retain strict strings and `ValueError`; production adapters use their domain APIs. Private alias identity tests now target owning behavior. |
| Duplicate risk tests and implementation-restating comments | Four copied risk checks were removed from the newer suite because restored public contracts already exercise the same functions and assertions. Distinct invalid-input, large-input and Phase B regressions remain. Restating comments were removed; external policy, security rationale and concurrency explanations remain. |

### Required distinctions and remaining special cases

**[NOTE]** These are retained requirements, not pending refactor work:

- Global Store mutations coordinate a filesystem tree with a rebuildable index;
  agent roots have no index. Their scope forks and lock order remain explicit.
- Consumer discovery, effective precedence, key support, native switches and
  workspace observations describe different capabilities. Their tables overlap
  in names but cannot be merged into one list without changing root coverage,
  precedence or mutability. Native consumer branches encode actual formats.
- Upstream registry hashes, manager integrity hashes, update manifests and
  batch tree evidence use different framing, files, link rules and limits.
  Their traversal and validation are kept with those protocols. Risk listing
  also has its own bounded advisory scope and is not an integrity manifest.
- Review artifacts retain separate expiry/size policy constants, storage,
  status/error contracts and clocks. Equal current values alone do not make
  registry approval, local update and backup approval the same policy. Common
  review encoding, credential checks and private writes remain shared.
- Global trash/snapshot parsers accept historical artifact spellings; agent
  trash validates the current agent format. Creation shares timestamps and
  collision allocation. Path containment helpers distinguish already-resolved
  roots from named entries; these semantics are used by the hot scan paths.
- Home-relative redaction, HTTP confinement redaction and adapter projection
  serve different audiences. Wildcard and native permission matching also have
  different documented dialects. They remain separate.
- Classic and v2 have distinct document presentation, modal/focus lifecycles
  and sync/Undo workflows. Domain transport/escaping is shared; presentation
  renderers, preference bootstrap and live Vue listeners remain at their
  lifecycles. List-body fetch coalescing and report sequence guards prevent
  different races and cannot substitute for transport request sharing.
- Input guards remain at independently callable Store/scope APIs and at CLI/HTTP
  shape boundaries. Shared format limits come from validator/token owners;
  create, edit and transport acceptance are not interchangeable operations.
- Degradation catches preserve optional evidence while required mutations fail
  closed. Platform lock fallbacks, the lazy CLI web-server import and async
  readiness waits retain external platform or lifecycle reasons. No gate or
  regression was disabled to make the pass succeed.
- `backup_sync` and `bundles` are shipped, ADR-backed APIs even without a current
  CLI/HTTP workflow. They and documented insight functions remain available.
  On 2026-11-09 the maintainer decided to keep `insights`, `backup_sync` and
  `bundles` as compatibility APIs; a later pass should not re-propose removing
  them without a new decision.
- Agent doctor detects an unreadable root and shares managed-peer link policy.
  Recursive discovery remains best-effort; it does not certify inaccessible
  descendants, and document-less grouping folders are not inferred to be skills.

## Verification and review

**[NOTE]** All evidence below belongs to this worktree. The unrelated primary
checkout, `main`, remotes, release approvals and installed user skills are
unchanged. No commit or push was requested for this continuation.

**[NOTE]** Independent GPT 6 Luna and GPT 6.1 Terra reviews found no further
worthwhile structural fix after the compatibility and bounded-reader passes.
The final runtime export audit checked all baseline names in 17 modules with
explicit `__all__` lists: every name remains exported and importable.

| Check | Measured result |
|---|---|
| Full unittest matrix | 1,765 tests each on Python 3.11.15, 3.12.3, 3.13.13 and 3.14.3; all pass, with the same 2 optional oracle skips per interpreter |
| Store and HTTP smoke tests | Both pass against the final implementation |
| Python compilation and first-party JavaScript syntax | All checked files pass |
| Docs, design tokens, complexity, Ruff 0.16.8 and Bandit 1.9.4 | All pass; 973 tracked functions across 30 files, no original function budget raised |
| Import/dependency inspection | No package import cycles or private imports between package modules |
| Pinned wheel and sdist build | Both build with hash-verified `requirements-build.txt`; both pass package-data inspection |
| Isolated installed artifacts | Each installs in a fresh environment and passes CLI create/list/doctor and public compatibility imports; sdist build uses the same pinned toolchain |

**[NOTE]** Final browser replay passes: classic 38 scenarios / 342 assertions,
v2 37 scenarios, both with zero failures; the six-viewport harness also passes.
Evidence is in `verified-browser/` and `verified-viewports/` under the directory
below. The final diff check removed two whitespace defects inherited from the
Claude commits; `whitespace-equivalence.json` proves both complete Python ASTs
are unchanged. Artifacts were rebuilt and installed probes repeated afterward.

**[NOTE]** Evidence and backups are private local files at
`/home/uday-varmora/skillsmgr-untangle-continuation-vj8oqe8v`:
`dist-final/` contains the verified distributions; `verified-source-hashes.json`
binds 184 source/check/test files to the final ladder. Unit logs are
`/tmp/skillsmgr-untangle-verified-py{311,312,313,314}.log`; packaging and installed
probes are in `/tmp/skillsmgr-untangle-package-final.log` and
`/tmp/skillsmgr-untangle-installed-final.log`. Source hashes were checked again
after the matrix. `delivered-source-hashes.json` records the final bytes after
the two AST-identical whitespace fixes; the equivalence record links them to
the tested source. Remaining changes only update documentation/evidence.

### Hostile review against the final diff

**[NOTE]** Reviewed the changes against all seven repository questions:

1. Adversarial inputs: installer strict guards, filesystem confinement and
   escaped rendering remain exercised. Bounded readers check the opened file,
   reject non-regular objects and preserve the caller's final-symlink policy.
2. Empty/single/large inputs: existing behavior suites cover empty and ordinary
   records; the new reader tests cover exact/over-limit, growing/replaced files,
   missing files, directories and FIFOs. This session did not rerun the dated
   10,000-instance performance benchmark or claim a new performance number.
3. Repetition/concurrency/order: read-flight bodies are AST-identical to their
   checkpoint implementations apart from the rename, with existing nested-copy,
   error/interrupt and unrelated-key contracts retained. Descriptor identities
   are checked before no-follow fallback reads; bytes come from that descriptor.
4. UI interruptions: the browser suites include delayed double-click, Undo,
   cancellation, stale-toggle and read-retry scenarios. Shared tool metadata
   adds no mutation flow; existing transport/disconnect handling stays in place.
5. Cleanup: descriptors close in `finally`, scope preflight uses a context
   manager, and Store context binding resets its token. Existing staged commit
   and rollback tests remain. New documentation points to current owning code.
6. Missing/corrupt/partial evidence: malformed/undecodable documents and missing
   runs cannot become healthy evidence. Root doctor failures are degraded;
   recursive scan completeness remains explicitly unclaimed.
7. Simplicity: policy differences and shipped public compatibility entry points
   were retained. No replacement framework, new dependency, application command,
   public Store method or schema migration was introduced. Import analysis
   reports no package cycles and no private imports between package modules.

**[NOTE]** Three added regressions were checked against the recovered
checkpoint's actual function bodies in isolated Python processes, without
editing the checkout: installer timeout evidence, invalid explicit eval-runs
input and doctor managed-peer links all fail on the checkpoint behavior.

**[NOTE]** Assumptions and limits: this is local Linux verification. The
`O_NOFOLLOW`-absent identity fallback is exercised through injected platform
flags and replacement races, not a real Windows/macOS run. The optional
`skills_ref` reference-oracle interpreter is not configured; its two tests
remain explicitly skipped. Human visual/spoken screen-reader sign-off and live
external registry/runner execution are outside this structural pass.

## Main integration authorization (2026-11-09)

**[SPEC]** The maintainer subsequently requested pushing this completed task to
`main` and using only GPT 6.1 Terra subagents. This supersedes the earlier
local-only stopping point. No release tag or package publication is requested.

**[NOTE]** Fetched `origin/main` and local `main` both point to `f323f16`, the
base of the eight prior refactor commits. The primary checkout has independent
uncommitted work on `feat/v2-feature-parity`; a content manifest records its
state and integration proceeds from this task worktree. Terra reviewed the
full scope and found no dependency/schema/public-Store/CLI-surface changes,
obvious secrets or generated artifacts. The restored `insights` facade and
its behavior tests, the new shared read modules and the decision record are
included explicitly.

**[NOTE]** Fresh pre-commit verification on the complete tree passes: 1,765
unittest cases on Python 3.12 (two optional oracle skips), compilation,
first-party JS syntax, both smokes, docs/design/complexity, Ruff 0.16.8 and
Bandit 1.9.4. Product/check/test fingerprints match the completed refactor;
only integration records and the changelog were added. A trailing blank line
in the newly staged read-flight module was trimmed with complete AST equivalence
checked. The staged tree includes
all restored compatibility files and shared read modules. The normal main push
and its remote receipt are recorded after integration; GitHub CI remains a
separate check.

### Verified main push receipt

**[NOTE]** `origin/main` was fast-forwarded from `f323f16` to
`e4e100b5af94ea3f786a485c25c01ca7a221a5cc`. The normal push returned success,
and `git ls-remote origin refs/heads/main` returned that same full SHA. The
committed tree matches the staged verified tree; local `main` is clean in this
task worktree. All 47 file fingerprints recorded for the independent primary
checkout still match, and its branch remains `feat/v2-feature-parity`.

**[NOTE]** Clean committed-tree wheel/sdist builds and package-data inspection
passed; SHA-256 records and fresh unit/smoke/static logs are at
`/home/uday-varmora/skillsmgr-main-integration-21iqvlon`. The main tree also
passed Store and HTTP smoke checks after the fast-forward. This receipt is a
documentation follow-up to the pushed code commit. GitHub CI status is checked
and reported separately; no release tag or package publication is part of the
request.
