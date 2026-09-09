# Loop-Engineering Findings — skills-manager

**Report date:** 2026-09-08/09 (campaign runs; last verification 2026-09-09)
**Baseline commit (clean tree):** `87e7b9c` — 208 unit tests OK, both smoke scripts PASS,
compile/`node --check`/docs/complexity gates PASS, package-data gate honestly
`UNAVAILABLE` (this environment lacks the optional `build` module).
**Status legend:** `FIXED` = corrected in the current working tree with a hermetic
regression test (changes are uncommitted); `OBS` = observed behavior/limitation to decide
on; `DOC` = documentation-only fix already applied. (`OPEN` was the in-progress label
used during the campaign; no OPEN items remain — former OPEN-1…OPEN-6 are recorded
as FIX-8 (extended), FIX-10, FIX-11, ratchet-resolution, FIX-12, FIX-13.)

> **[SPEC]** Scope of this report: bugs and issues found by the deep loop-engineering
> testing campaign (differential/state-machine loops, round-trip and hostile fuzz,
> CLI adversarial matrix, REST fuzz, concurrency stress, failure injection, archive
> grammar/boundary fuzz, scope sync differential checks). Items marked `FIXED` are
> corrected in the working tree with red-first regression tests; the former OPEN
> queue (OPEN-1…OPEN-6) is fully resolved as recorded in §8.

---

## 1. Verification snapshot (evidence for everything below)

| Gate | Baseline (before campaign) | Current working tree |
|---|---|---|
| `python3 -m unittest discover -s tests` | 208 PASS | **222 PASS** (14 loop regressions, each written red first) |
| `smoke_store.py` | ALL STORE SMOKE TESTS PASSED | ALL STORE SMOKE TESTS PASSED |
| `smoke_web.py` | ALL WEB SMOKE TESTS PASSED | ALL WEB SMOKE TESTS PASSED |
| `check_docs.py` | PASSED | PASSED |
| `check_complexity.py` | PASSED (168 functions) | **PASSED** (181 functions; fixes refactored into small helpers, no baseline inflation) |
| `py_compile` / `node --check app.js` / `git diff --check` | PASS | PASS |
| `check_package_data.py` | UNAVAILABLE (no `build` module) | UNAVAILABLE (unchanged) |

Working-tree diff vs baseline: `skillsmgr/{store,archive,atomic_io,cli,frontmatter,scopes}.py`,
`tests/{test_store_contracts,test_frontmatter_contracts,test_cli_contract,test_concurrency_contracts,test_web_scopes}.py`,
`docs/{02-modules,03-cli-surface}.md`, `loop-engineering-findings.md`.

---

## 2. Findings summary table

| ID | Area | Severity | Status | One-line description |
|---|---|---|---|---|
| FIX-1 | store | High | FIXED | `create`/`add` over a trashed name leaves the index row `trashed` — new skill invisible to `list()`; resync cannot heal |
| FIX-2 | store | High | FIXED | Same-second trash collisions write `name-<ts>-N` entries the trash reader cannot recognize — invisible, unrestorable, unpurgeable copies |
| FIX-3 | store | Medium | FIXED | Second `remove()` of a trashed skill silently "succeeds" with a bogus `trash_path` |
| FIX-4 | archive | High | FIXED | Import failure during the "move original → backup" step **deleted the original skill directory** (data-loss window) |
| FIX-5 | archive | Medium | FIXED | Truncated/corrupt gzip archives leak raw `EOFError`/`BadGzipFile` instead of a clean `StoreError` |
| FIX-6 | cli | Medium | FIXED | First-run mutation commands die with `no such table: skills` — the CLI never bootstrapped the index schema |
| FIX-7 | cli | Medium | FIXED | `install` accepted malformed `SOURCE`/`--agent`/`--skill` values (no parity with REST route) |
| FIX-8 | frontmatter | Medium | FIXED | Dumper emits unquoted flow-list items containing `, " [ ] { } ' #` and unquoted keys containing quotes → its own output unparseable |
| FIX-9 | docs | Low | DOC | `list` semantics doc said "enabled only"; implementation shows disabled skills with a STATUS column |
| FIX-10 | frontmatter | Medium | FIXED | **Mappings and empty collections nested inside lists** were silently `str()`-ified or became `None` (semantic corruption) → mappings now emit as nested block sequences (flow lists stay scalar/nested-list-only; empty `{}`/`[]` stay inline so they parse back empty) |
| FIX-11 | scopes/store | Medium | FIXED | `sync_skill(...)` into the **global scope writes the filesystem directly** — a `trashed` row could stay `trashed` while the dir is live → sync now reconciles the global index via `resync()`; `resync` treats any live dir as `active` |
| FIX-12 | store concurrency | High | FIXED | `remove`/`disable`/`enable`/trash-`restore` move files **without the per-skill mutation lock** → racing `create`/`edit` strands `.skillsmgr-tmp` files inside trash copies and leaks raw `FileNotFoundError` |
| FIX-13 | store | Low | FIXED | `purge_trash()` propagates raw `OSError` on a mid-purge filesystem failure → wraps as `StoreError` |
| OBS-1 | frontmatter | Info | OBS | Duplicate frontmatter keys resolve **last-wins silently** (no error, no `malformed` flag) |
| OBS-2 | frontmatter | Info | OBS | Numeric scalars are not coerced (str/bool/None only by design); integers handed to the dumper come back as strings on parse |
| OBS-3 | store | Info | OBS | `purge_trash()["purged"]` may repeat a name when two trash copies exist |
| OBS-4 | web | Info | OBS | One `GET /api/tokens` timeout observed under sustained fuzz load (single occurrence, server survived; environment-correlated) |

---

## 3. Fixed findings (detail)

### FIX-1 — create/add over a trashed name leaves the index row `trashed`
- **Area:** `skillsmgr/store.py` (`_upsert_entry`, `create`, `add`, import commit path).
- **Reproduction (minimal):**
  ```python
  store.create("alpha", "one"); store.remove("alpha")   # row -> status 'trashed'
  store.create("alpha", "two")                          # succeeds; dir created
  store.list()      # -> []     (skill invisible)
  store.stats()     # active 0, trashed 1
  store.doctor()    # ok False (orphan dir); resync() does NOT heal
  ```
- **Root cause:** `remove(trash)` keeps the row and marks `status='trashed'`.
  `_upsert_entry` only ever set `status='active'` on the INSERT branch; the
  UPDATE branch refreshed content but never the status, and `resync` also never
  flips status. Only `db rebuild` healed the state.
- **Impact:** the UI/CLI `list` hides a skill that `create` just reported as
  created; doctor reports an orphan dir; silent FS/index disagreement produced
  by public API calls alone.
- **Fix:** `_upsert_entry` now treats any live skill directory as `active` —
  the UPDATE branch includes `status='active'` whenever the row is not already
  active or content/disabled flags changed. This heals `create`, `add`, `edit`,
  `restore`, and archive-import commit paths uniformly.
- **Regression tests:** `test_create_over_trashed_name_reactivates_index_row`,
  `test_add_over_trashed_name_reactivates_index_row`
  (both first written red: `[] != ['demo']`).

### FIX-2 — same-second trash collisions are unrecognizable to the trash reader
- **Area:** `skillsmgr/store.py` (`_TRASH_TS_RE`, `remove()`).
- **Reproduction (forced identical timestamp):** `remove` → `create` → `remove`
  inside one second produces disk entries `alpha-…Z` and `alpha-…Z-1`.
  `trash_list()` showed **1** entry, `restore()` returned the **older** copy
  (`v1` instead of `v2`), and `purge_trash()` reported `purged: []` while the
  newest copy stayed orphaned on disk forever.
- **Root cause:** `remove()`'s collision fallback appends the counter **after**
  the `Z` (`name-<ts>-1`), but `_TRASH_TS_RE` only accepted a counter before an
  optional `Z` — so the reader and its own writer disagreed.
- **Impact:** silent data-visibility loss: the newest trashed content could
  never be restored or purged (purge lied "nothing purged").
- **Fix:** the regex now accepts the counter on either side of the optional `Z`
  (writer-format canonical), so every entry `remove()` produces stays
  recognizable by list/restore/purge/doctor.
- **Regression test:** `test_same_second_trash_counter_entries_are_listed_restored_and_purged`
  (red: `1 != 2`).

### FIX-3 — double `remove()` silently succeeds with a made-up `trash_path`
- **Area:** `skillsmgr/store.py` (`remove`).
- **Reproduction:** `remove("x")` twice — second call returned
  `{"action": "trashed", "trash_path": "<path that does not exist>"}` with
  exit code 0.
- **Root cause:** when the skill dir was already gone, `remove()` only raised
  when the DB row was also missing; a trashed row made it fall through to a
  fake success.
- **Fix:** `remove()` now requires the skill directory to exist and raises
  `SkillNotFound` otherwise; trash copies are managed by
  `restore()`/`purge_trash()`.
- **Regression test:** `test_second_remove_of_trashed_skill_raises_not_found`.

### FIX-4 — import recovery deleted the original skill on backup-move failure
- **Area:** `skillsmgr/archive.py` (`commit_staged_skill` exception path).
- **Reproduction (failure injection):** force every `shutil.move` inside
  `Store.import_(archive, force=True)` to raise `OSError`; the original
  `skills/<name>` directory was **deleted** and `get(name)` failed afterwards.
- **Root cause:** the `except` block ran
  `if dest.exists() and (moved_original or not backup.exists()): rmtree(dest)`
  — when the initial "original → backup" move failed, `dest` *is* the user's
  original and the guard deleted it.
- **Impact:** real data loss on an unlucky I/O failure during forced import
  (ENOSPC/EACCES/EXDEV class).
- **Fix:** exception recovery is now state-explicit: if the original was never
  moved, `dest` is never touched (only the staging copy is cleaned); if it was
  moved, any partial `dest` is discarded and the backup is moved back.
- **Regression test:** `test_import_backup_move_failure_preserves_original_destination`
  (red before fix: original dir gone).

### FIX-5 — truncated/corrupt archives leak raw decompressor exceptions
- **Area:** `skillsmgr/store.py` (`import_` preflight).
- **Reproduction:** a gzip archive truncated to ⅓ leaks
  `EOFError: Compressed file ended before the end-of-stream marker was
  reached`; a random-byte `.tar.gz` leaks `gzip.BadGzipFile`.
- **Fix:** the tar preflight catch set now includes `EOFError`, `zlib.error`,
  and `gzip.BadGzipFile` (all malformed-stream classes tarfile itself does not
  wrap) → clean `StoreError("invalid archive: …")`.
- **Regression test:** `test_import_truncated_gzip_archive_is_clean_store_error`.

### FIX-6 — first-run CLI mutation commands die with `no such table`
- **Area:** `skillsmgr/cli.py` (`_make_store`).
- **Reproduction:** brand-new `SKILLS_MANAGER_DATA`; `python3 -m skillsmgr
  create x -d y` → exit 1, stderr
  `error: unexpected error: no such table: skills` plus a rollback diagnostic.
- **Root cause:** only `init` and read commands auto-initialized the schema;
  mutation commands assumed the DB existed.
- **Fix:** `_make_store()` calls idempotent `store.init_db()` after name
  validation (invalid names still fail before any filesystem mutation — kept
  and asserted).
- **Regression test:** `test_mutation_commands_work_on_fresh_data_dir_without_init`
  (also strengthened the invalid-name test to check the real DB path).

### FIX-7 — `install` accepts malformed sources/agents (REST parity)
- **Area:** `skillsmgr/cli.py` (`cmd_install`).
- **Reproduction:** `install "we ird !" --dry-run` exited 0 and printed the
  runner command; the REST `/api/install` route rejects the same input.
- **Fix:** CLI now validates `SOURCE` and `--agent`/`--skill` values against the
  same character class and leading-dash rule as the REST route, before any
  dry-run display or command construction.
- **Note:** this fix initially pushed `cmd_install` complexity over its budget;
  the validation was then extracted into `_validated_install_{runner,value,
  source}` helpers and the ratchet passes against the unchanged baseline
  (see ratchet resolution in §4, former OPEN-4).

### FIX-8 — dumper emits unparseable flow lists (commas/quotes/brackets/`#`)
- **Area:** `skillsmgr/frontmatter.py` (`_dump_flow_scalar`).
- **Reproduction:** `dump_frontmatter({"k": ["5,,CPK…'JK…", "a[b]c", "x # y"]})`
  produced `k: [5,,CPK…, a[b]c, x # y]` which `parse_frontmatter` rejects
  (`unterminated flow collection`) — the dumper could not round-trip its own
  output for any flow item containing `,` `'` `"` `[` `]` `{` `}` `#`.
- **Fix:** flow scalars containing those characters are now single-quoted.
- **Regression test:** `test_flow_list_scalars_with_commas_quotes_and_brackets_round_trip`.
- **Follow-ups folded back in:** quote-character keys and nested mappings/empty
  collections were then fixed as well (former OPEN-1/OPEN-2, recorded as
  FIX-8 extension and FIX-10 in §4).

### FIX-9 — `list` documentation drift (DOC)
- `docs/03-cli-surface.md` claimed "enabled only"; the implementation lists
  active-status skills with a STATUS column and `--disabled` narrows to
  disabled only. Doc corrected; no behavior change (existing users' output is
  unchanged).

---

## 4. Former OPEN findings — now fixed (kept for the record)

> During the campaign these were tracked as OPEN-1…OPEN-6 ("fix deferred").
> All six are resolved in the working tree with red-first hermetic regressions;
> each entry ends with **Resolution** stating the fix. The summary table lists
> them as FIX-8 (extended), FIX-10, FIX-11, ratchet-resolution, FIX-12, FIX-13.

### OPEN-1 — `dump_frontmatter` leaves keys containing `'` or `"` unquoted — FIXED (folded into FIX-8)
- **Area:** `skillsmgr/frontmatter.py` (`_format_key`).
- **Reproduction (minimal):**
  ```python
  dump_frontmatter({"x'y": 1})  # -> "x'y: 1"  (unquoted)
  parse_frontmatter("x'y: 1")   # FrontmatterError: malformed mapping line
  dump_frontmatter({'x"y': 1})  # same failure
  ```
  Found by the round-trip fuzz corpus (0.25 % of generated documents failed at
  seed 20260917, iterations 1196–1198; delta-debugged minima above).
- **Root cause:** `_format_key` only quotes keys that are empty, need stripping,
  contain `:`/`#`, or start with `-`; the parser cannot scan keys containing
  quote characters.
- **Impact:** Store API users passing `metadata_extra` with such keys get a
  clean but surprising failure on create/edit; external frontmatter with such
  keys round-trips to unreadable files after an edit.
- **Resolution:** `FIXED` (extends FIX-8). `_format_key` now quotes keys containing
  `' " [ ] { } ( )` (`_QUOTE_KEY_CHARS`); round-trip regression
  `test_round_trip_keys_containing_quote_characters`.

### OPEN-2 — dicts nested inside flow lists are silently `str()`-ified — FIXED (FIX-10)
- **Area:** `skillsmgr/frontmatter.py` (`_format_flow_list` / `_dump_flow_scalar`).
- **Reproduction:**
  ```python
  doc = {"k": [["a", {"n": 1}]]}
  parse_frontmatter(dump_frontmatter(doc))  # -> {'k': [['a', "{'n': 1}"]]}
  # types silently corrupted: dict -> python-repr string, int -> string
  ```
- **Root cause:** when a *list of lists* (or list inside a flow list) contains
  mapping items, the dumper serializes them with `str(value)` inside the flow
  list; the parser reads the result back as a plain string.
- **Impact:** silent semantic corruption of structured metadata on any
  dump→parse cycle (empty dicts become `"{}"` strings; nested ints become
  strings — historical note; the str/bool/None-only coercion contract itself
  is unchanged, see OBS-2).
- **Historical alternative considered:** either teach the parser minimal flow maps /
  empty-flow values, or have the dumper raise a clean `TypeError` for mapping
  items nested inside flow lists (fail loud instead of corrupting).
- **Resolution:** `FIXED` (FIX-10). Mappings nested in lists now emit as nested
  block sequences (`_dump_sequence_element`); flow lists stay scalar/nested-list
  only and still raise `TypeError` for mappings; empty `{}`/`[]` stay inline so
  they parse back empty. Regression `test_dump_serializes_mappings_inside_flow_lists`.

### OPEN-3 — `sync` into the global scope bypasses the index — FIXED (FIX-11)
- **Area:** `skillsmgr/scopes.py` (`sync_skill`).
- **Evidence:** in the hermetic scope differential loop, after
  `scopes.sync_skill(name, "agents", ["global"])` onto a name whose global row
  was `trashed` (dir previously removed), the global **directory is live but
  the row stays `trashed`**: `find_duplicates()` misses the copy (expected
  count 2, reported absent), and `store.resync()` cannot flip the status
  (same limitation family as FIX-1, on the resync side).
- **Root cause:** `sync_skill` commits every target — including the global
  Store-backed root — with raw staged `copytree`/`move` (correct for agent
  directories which have no DB), never reconciling the global row status.
- **Impact:** sync-from-agent flows can leave doctor-inconsistent state and
  duplicate detection blind until `db rebuild`.
- **Suggested fix (not applied, needs design decision):** for targets whose
  resolved root is the global root, route the commit through the Store public
  API (or reconcile the affected row) — note the current locked constraints
  forbid adding a new Store method without approval, which is why this is
  documented rather than fixed. *(Historical note: kept verbatim from the
  campaign log; the constraint-compliant resolution actually applied is
  recorded in **Resolution** just below — no new Store method was added.)*
- **Resolution:** `FIXED` (FIX-11) without any new Store method: `sync_skill`
  calls the existing public `resync()` seam when `"global"` is among the synced
  targets, and `resync` itself now reactivates any live directory whose row is
  still `'trashed'`. Regression `test_sync_into_global_reactivates_stale_trashed_row`.

### OPEN-4 — complexity ratchet RED from the uncommitted fixes — RESOLVED
- At the time the gate reported:
  - `skillsmgr/cli.py::cmd_install` complexity 25 → 34 (FIX-7 validation),
  - `skillsmgr/frontmatter.py::_dump_flow_scalar` complexity 6 → 9 (FIX-8).
- Impact at the time: CI gate failure until the code was refactored (extract
  helpers) or the baseline deliberately re-ratcheted (maintainer decision).
- **Resolution:** `RESOLVED` by refactoring, **no baseline inflation**:
  `_quote_flow_text`, `_validated_install_{runner,value,source}`,
  `_remove/_restore/_disable/_enable_unlocked` sharing `_with_skill_lock`,
  `_purge_entry`, `_resync_row_{changed,update}`. `check_complexity.py` PASSES
  against the unchanged baseline (191 functions; the count grew only through
  new small helpers, each under the budget of 15).

### OPEN-5 — unlocked whole-dir moves race with locked file writes — FIXED (FIX-12)
- **Area:** `skillsmgr/store.py` (`remove`, `disable`, `enable`, trash-branch
  `restore`) vs. per-skill mutation locks in `create`/`edit`.
- **Evidence (concurrency stress, 4 writers × ~25 s on 6 names):**
  ```
  FileNotFoundError: [Errno 2] … '.SKILL.md.<tmp>.skillsmgr-tmp' -> '…/conc-5/SKILL.md'
  doctor: temporary_files = [trash/conc-5-…/.SKILL.md.<tmp>.skillsmgr-tmp, … (7 files)]
  ```
- **Root cause:** `create`/`edit` serialize on
  `_mutation_lock(skill_dir/"SKILL.md")` but `remove`/`disable`/`enable` and
  the trash-`restore` move the whole directory (or rename the file) **without
  taking that lock**. A writer mid-atomic-write loses its parent directory; the
  stranded temp file then travels inside the trash copy (doctor finds it
  forever), and the raw `FileNotFoundError` escapes instead of a clean error.
  Reachable from the threaded web server when two requests touch the same
  skill.
- **Suggested fix (not applied):** take the same per-skill mutation lock in
  `remove`, `disable`, `enable`, `restore` (both branches), and make the
  atomic-write cleanup resilient when the parent dir has moved. *(Historical
  note: this is exactly what was then applied — see **Resolution** below.)*
- **Resolution:** `FIXED` (FIX-12). All six mutations share `_with_skill_lock`
  around the per-skill path; `atomic_write_text` also sweeps a moved temp file
  by name. Threaded race regression
  `test_remove_and_edit_race_leaves_no_residue_or_raw_errors`.

### OPEN-6 — `purge_trash()` raw `OSError` on mid-purge filesystem failure — FIXED (FIX-13)
- Failure injection forcing `shutil.rmtree` to fail on the second trash entry
  propagates a raw `OSError` out of the Store API (CLI maps it to a clean
  exit-1 message; the remaining entries stay listed and purge can be retried).
- Severity low; decide whether Store methods should wrap disk failures into
  `StoreError` for a uniform contract.
- **Resolution:** `FIXED` (FIX-13). `_purge_entry` raises
  `StoreError("could not purge trash: …")`; unvisited entries stay purgeable.
  Regression `test_purge_trash_wraps_filesystem_failures_as_store_error`.

---

## 5. Observations (design notes, no immediate action)

- **OBS-1 — duplicate keys:** `k: 1\nk: 2` parses silently to `{'k': '2'}`
  (last-wins, `malformed: False`). Tolerated by common YAML tooling; a
  duplicate `name:`/`description:` can hide authoring mistakes. Consider a
  parser error or a `malformed`/warning signal later.
- **OBS-2 — numeric fidelity:** block scalars are never coerced to numbers and
  booleans/None are; ints/floats handed to the dumper come back as strings
  after parse (visible when `metadata_extra` carries numbers; in the
  doc-subset contract this is "str/bool/None only" — no doc claims numeric
  support). The historical OPEN-2 corruption class (mappings str()-ified in
  flow lists) is separately fixed as FIX-10 above.
- **OBS-3 — `purged` duplicates:** purging two trash copies of the same name
  yields `purged: ["x", "x"]`; cosmetic, could be deduped.
- **OBS-4 — `/api/tokens` latency:** one 15 s client timeout while the REST
  fuzz hammered the server; server stayed alive and healthy afterwards.
  Environment/load-correlated; no handler bug reproduced.

---

## 6. Campaign method, probes, and coverage evidence

All probes are deterministic (seeded) and hermetic (temporary data dirs, no
network, stdlib only). Probe code lives **outside the repo**
(`~/sm-probes/{probes.py,probes2.py}`); no probe file was added to the
repository.

| probe | what it hammers | last result |
|---|---|---|
| store-lifecycle burst | 600-op create/edit/disable/enable/remove/restore/resync storm incl. same-second trash cycles; fs-vs-DB invariants every step | **0 findings** |
| frontmatter round-trip + hostile fuzz | 1,200 generated docs (dump→parse equality), hostile corpus, budget boundary checks | **0 findings** (after FIX-8/FIX-10 incl. empty-collection and nested-mapping fixes) |
| failure injection | edit mid-write, snapshot-restore write, import commit move, db-lock failures; residue + doctor checks | **0 findings** (FIX-13 contract wrap; original-preservation recovery stands) |
| REST fuzz | 700 hostile requests + origin policy battery + traversal + oversized bodies + multipart; survival cycles | surface clean (2 probe-artifact rows: 415 oversized-body rejection, survival-cycle count reset); hostile origins never mutated state; headers present |
| concurrency stress | 4 writers + 2 readers; torn-frame atomicity; doctor after storm | **0 findings** (after FIX-12 lock coverage) |
| search fuzz | 400+ adversarial terms; bounds; `a**b ≡ a*b` collapse; exact-hit sanity | 0 findings |
| validator fuzz | 120 hostile skill dirs; odd scan roots | 0 findings |
| loader/templates fuzz | empty/both-files/broken-frontmatter dirs, symlink dirs, template-name battery | 0 findings |
| CLI env matrix | env/color/unicode/empty-args/json-parse batteries | 0 findings |
| CLI adversarial matrix (earlier campaign) | 182 checks: help for every command, invalid names/args, exit codes, JSON shapes, zip/archive rejection, scope battery | 0 findings (after FIX-3/6/7; exit-code expectations aligned with implementation) |
| archive boundary + grammar fuzz (earlier campaign) | 450 randomized archives + empirical boundary probes (member count, nesting, path length, 8 MiB members, expanded monsters, zip/garbage/truncated) | 0 findings (after FIX-4/5); no residue, no leaks, canonical-only imports |
| scope differential loop (earlier campaign) | 1,200 ops across global + agents incl. sync both directions, duplicate detection | **0 findings** (after FIX-11 post-sync reconciliation) |

**Sensitivity control:** the store-lifecycle probe detects deliberate injected
corruption immediately ("row 'a' active but dir missing"), confirming the
invariant checks are not vacuous.

---

## 7. What was *not* covered (limitations)

- **Browser/UI click-through:** no browser tooling in this environment; the web
  UI frontend was validated only by `node --check`, the static/route surface,
  the REST API loops, and the repo's own smoke suite. Earlier deep UI QA
  history is documented in `docs/06-progress-log.md` (2026-08-14 entry).
- **Package-data gate:** `check_package_data.py` reports `UNAVAILABLE` because
  the optional `build` module is not installed here; CI installs it and runs
  `--require-build`.
- **Cross-process concurrency:** same-store multi-*process* behavior is by
  design atomic-replace plus `doctor`/`db resync` recovery (no lock files);
  this campaign stressed same-process threads, not multi-process locks.
- **Performance:** adversarial probes are timing-bounded per input but no
  formal benchmark suite was run.

---

## 8. Repair status (was: recommended next steps)

All former OPEN items are resolved in the working tree:

1. OPEN-1 (quote-char keys) → FIX-8 extended: `_format_key` now quotes keys
   containing `' " [ ] { } ( )`, with round-trip regressions.
2. OPEN-2 (mappings str()-ified in lists) → FIX-10: nested block-sequence
   emission for mappings in lists; empty `{}`/`[]` stay inline so they parse
   back empty.
3. OPEN-5 (unlocked moves race writes) → FIX-12: `_with_skill_lock` shared by
   `create`/`edit`/`remove`/`disable`/`enable`/trash-`restore` (public methods
   hold the lock briefly and delegate to private `_unlocked` bodies, so no
   method grew past its checked-in complexity), plus stranded-temp cleanup in
   `atomic_io` and a threaded race regression.
4. OPEN-3 (sync bypasses index) → FIX-11: post-sync `resync()` when the global
   scope was committed, and `resync` reactivates any live dir.
5. OPEN-4 (complexity ratchet) → resolved by extracting `_quote_flow_text`,
   `_validated_install_{runner,value,source}`, `_remove/_restore/_disable/
   _enable_unlocked` sharing `_with_skill_lock`, `_purge_entry`, and
   `_resync_row_{changed,update}` helpers: `check_complexity.py` PASSES
   against the **unchanged checked-in baseline** (191 functions; the count
   grew only through new small helpers, each under the budget of 15).
6. OPEN-6 (raw purge OSError) → FIX-13: `purge_trash` wraps as `StoreError`,
   remaining entries stay purgeable.

Remaining work: write `task.md` and `docs/06-progress-log.md` entries for this
campaign and commit the change set.
