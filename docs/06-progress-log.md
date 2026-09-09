# Progress Log — Skills Manager

**Version 0.1.0**

**AI manifest**: Dated, append-only record of changes, decisions, and bugs for skills-manager. Read before/after every session (docs/README.md reading order). Newest entry on top. Facts flagged stale here are corrected in the owning doc.

## 2026-09-09 — CI/contracts/migration re-verification campaign, round 5 (12 probes green, zero code)

- Hermetic probes (stdlib only, scripts in `/tmp/r5_*.py`, outside the repo; zero product-code changes): T2 CI/release structure (unit 3.10–3.14 matrix, adversarial/package/docs/xplat-3OS×3.10-3.14/browser jobs, least-privilege `contents:read`, build-once + `--dist-dir` gate, release tag/version gate + attestation + TestPyPI→`release` env + GitHub Release + post-publish CRUD/asset checks); T3 package-data offline (exact wheel+sdist accept with 5 webui members, vue-missing reject, `--require-build` exit 2); T4 docs links (all `@docs/` resolve modulo the `...` shorthand, module paths exist, `Store.*` refs exist); T5 frontend (9 domain exports present, 19 menuDo actions dispatched, `/`/`?`/Esc + `trapModalFocus`, 13 modals `role=dialog`); T6 live headers (CSP with `frame-ancestors 'none'`, nosniff, DENY, no-referrer, same-origin CORP, no-store on `/`, `/api/*`, `/app.js`); T7 threat-model/ADR file:line refs all resolve in-range; T8 complexity gate green (151 functions, budget ≤ 15, no drift); T9 full migration (skip-by-default respected — same-tree `--full` import skips live names; wiped-tree `--full --force` restores `m-a` live + `m-b` trash + `tpl-a.md` template); T10 snapshots (7 edits → newest 5 kept `...-Z-5..-Z-1`, byte-accurate `--snapshot` restore); T11 cross-process CLI (2 procs × 10 edits all rc 0, doctor consistent); T12 versions aligned `1.0.0`, `dist/`/egg-info/pycache ignored.
- Flake note: the opening full-suite run failed once in `test_remove_and_edit_race_leaves_no_residue_or_raw_errors` (one churn thread alive after the 10s join — scheduling slowness, not a contract break: no raw errors, doctor clean). The file passes 3/3 standalone and the full suite passes on rerun (301 OK). Not a product change; recorded here per the never-guess rule.
- T13/T15: harness `"passed": true` (5 viewports, exit 0) + fresh-tmp lifecycle OK; final ladder below.

## 2026-09-09 — Round-5 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Recovery/contract re-verification campaign, round 4 (10 probes green, zero code)

- Hermetic probes (stdlib only, scripts in `/tmp/r4_*.py`, outside the repo; zero product-code changes): T2 failure injection (dropped-table edit raises while FS content survives + stderr-only `edit rollback failed` diagnostic, `db_rebuild` heals, row-delete drift flagged then `resync` heals); T3 upload bounds (oversize/bad `Content-Length` → 400, 250-part multipart → 400 on the real `PUT /api/import` route, valid folder → 200); T4 history clamp (5/0/huge/missing) + stats keys + tokens estimate/aggregate + long-search `ValueError`; T5 full backup/restore verified by `content_hash` + file bytes (not row counts) + template dup/bad-name guards; T6 doctor (real `.skillsmgr-tmp`/`.skillsmgr-stage` shapes flagged, orphan dir flagged then resynced, stale snapshot flagged); T7 CLI two-data-dir isolation (each dir finds only its own) + REST `test_search_contracts` 11/11 incl. two-server isolation; T9 concurrent same-skill writes 4×25 zero errors, doctor clean, no stranded temps, 101 history rows; T10 insights E2E over a live Store world (view unresolved, ownership, diff/3-way, preview, quarantine `stage-only`/`activated:false`, risk script+link, registry trust-gate, eval 1/1, bundle deferred, store hash unchanged).
- Probe-vs-contract notes (no product change): DB lives at `<data>/skills-manager.db` (not `<data>/skills-manager/`); `dump_frontmatter(data)` takes the mapping only; import tars need the exact versioned manifest; `aggregate()` wants `total_tokens`; `list()` rows carry `content_hash` (path via `get()`); doctor temp/stage detection matches `.skillsmgr-tmp`/`.tmp`/`.skillsmgr-stage` shapes only; upload route is `PUT /api/import`; `quarantine_plan` uses `action:"stage-only"`; `consumer_view` keys on `consumer`.
- T11/T12/T15: harness `"passed": true` file-verified across 5 viewports (an earlier `"passed": false` tail was a shell-pipe JSON-splitting artifact — rerun to file shows `passed:true`, exit 0); fresh-tmp lifecycle all OK; final ladder below.

## 2026-09-09 — Round-4 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.

## 2026-09-09 — Loop-engineering re-verification campaign, round 3 (9 probes green, zero code)

- Hermetic probes (stdlib only, scripts in `/tmp/r3_*.py`, outside the repo; zero product-code changes): T2 store burst (600+ ops incl. honest `SkillNotFound` double-remove, same-second trash cycle, doctor ok); T3 frontmatter 1200 round-trips + 8 hostile inputs (dup/deep/huge/no-close → clean `FrontmatterError`; nested-flow/large-body accepted without crash); T4 search (7 adversarial patterns fast or clean `ValueError`) + validator link matrix 8/8 exact; T5 archive (8 hostile tar classes + garbage + truncated → `StoreError`; ZIP rejection-only; valid manifest tar round-trips `['ok']`); T6 scopes (404 rows, dup flagged, isolation, sync converges); T7 concurrency (8×100 zero errors) + perf (100k-line 0.03s, 20k views 0.10s); T8 REST fuzz (655 requests, 0 fail-opens — purge takes no body by contract, no-CT probe covers `/api/skills`); T9 CLI matrix (81 checks, 0 fail-opens); T10 insights (degenerate/purity/determinism/concurrency clean; `eval_score` missing-`expect` tolerant by design, `eval_plan` strict).
- Probe-vs-contract notes (no product change): `dump_frontmatter(data)` takes the mapping only (body appended by caller); valid import tars need the exact `{"app","version":__version__,"created":"...+Z","skills":[{"name"}]}` manifest; `consumer_view` matches on `consumer` (not `scope`); purge reads no body so the JSON-CT gate applies to body-taking routes.
- Docs hygiene: dropped the #10 Deferred close-record line (retention pass elapsed); L3 now references filed issue #12; `task.md` Milestone 34 (this round).
- T15 final ladder below.

## 2026-09-09 — Round-3 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK. Harness + fresh-tmp recorded in the round-3 entry above.

## 2026-09-09 — Milestone 11 round 2: docs truth, diagnostic proposal, re-verification (15 tasks, zero code)

- T1 baseline green on the round-1 commit: 301 unittest OK, both smokes PASS, compile/frontend PASS, `check_docs.py` PASS, `check_complexity.py` PASS (151 functions), `git diff --check` PASS.
- T2 docs-truth audit: `docs/01-architecture.md` repo-map was missing the split modules (`cli_parser/handlers/output`, `scopes`/`loader`/`tokens`, `diagnostics`, `web_security/serialization/upload`, `insights`, harness, fixtures, package-data gate) — refreshed. `docs/05-gui-plan.md` confirmed correctly labelled SUPERSEDED with `gui.py`-deleted + alias facts (body stays historical by design). `.commandcode/settings.json` confirmed clean (the `gui.py` compile entry was replaced by `skillsmgr/*.py` in `2ae27bf`; remaining `gui.py` hits are append-only history). CLI 27+7+3=37 re-derived from `check_docs._command_inventory` AST walk + live parser (30 top-level names incl. aliases + 7 nested); insights 57 re-counted (`grep -c "def test"`).
- T3/T4 fixes: `docs/SESSION-CONTEXT.md` v0.3.0 (date, counts, full inventory, insights-57, Milestone 11 status, discovery v1.1.0); `docs/01-architecture.md` repo-map + data-flow diagram; `CHANGELOG.md` Unreleased 52→57 with round breakdown; `task.md` T11 52→57. `check_docs.py` PASS after each edit (one interim fail caught a `nested subcommands` phrasing the gate regex does not accept — fixed to the canonical `subcommands (trash/templates/db)` form).
- T5 L2 still gated: issue #5 OPEN zero comments; `store.py:1221` ZIP rejection-only, no `ZipFile` extraction anywhere in `skillsmgr/`.
- T6 diagnostic proposal filed as issue #12 (`[ASK] Read-only effective-resolution diagnostic (doctor --explain CONSUMER --project DIR)`): read-only, per-winner source citations, no persistence/schema change, hermetic per-consumer fixtures sketched, constraint-5 approval explicitly requested.
- T7 deferred re-verified: #3/#4/#8/#11 all OPEN zero comments; no `urlopen`/`http.client`/`socket`/SDK/model-subprocess code in `skillsmgr/` (`urllib` is URL-parsing only in `webapp.py`/`web_security.py`).
- T8/T9 release dry-run: `pyproject.toml` version == `__version__` == `1.0.0` == tag `v1.0.0`; `release.yml` tag/version gate + least-privilege perms verified; no bump/tag/publish performed. `check_package_data.py` honestly UNAVAILABLE; README PyPI-future claim accurate; live PyPI `skills-manager` JSON still 404.
- T10 worktrees: 5 Carson dirs exist; `git worktree list` heads recorded (`todo-plan-implementation 2bb7280`, `milestone5-research-user-needs c5a7161`, three at `667fabb`); `docs/10` scope is the 2-candidate comparison, not a live 5-dir map — no doc change needed.
- T11/T12 re-verification: `browser_harness.py` `"passed": true` (5 viewports); fresh-tmp lifecycle (create→validate→doctor→search→remove→purge→doctor) all OK.
- T13 docs updated for round 2: `TODO.md` (L6 dry-run note, stale-claim status note), `task.md` Milestones 31-L6 + 33 (this round), `PLAN.md` annex (issue #12 filed), this log.
- T14/T15 below: diff review + commit/push, then the final ladder re-run.

## 2026-09-09 — Milestone 11 round-2 final ladder (T15)

- `check_docs.py` → PASSED; 301 unittest → OK; both smokes → PASSED; `py_compile` → OK; `node --check` (`app.js` + `domain.js`) → OK; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK; `check_package_data.py` → honestly UNAVAILABLE (standing behavior).

## 2026-09-09 — Milestone 11 verdict execution round 1 (L1/L3/L4/L5/L6; docs + GitHub, zero code)

- L1: pinned live-preview + cheatsheet evidence (`skillsmgr/webui/index.html:70,373,756-760`, `skillsmgr/webui/domain.js:60`, `skillsmgr/webui/app.js:6,130`), commented it on issue #10, and CLOSED the issue (`gh issue view 10` = CLOSED). No code.
- L4: recorded all three rejections with file/line evidence and zero code changes — #6 keep `archive.py:133-158` feature-detect + guarded manual extractor (PEP 706; refusal breaks the 3.10/3.11 `requires-python >= 3.10` matrix); #7 keep `validator.py:323-352` warning + `insights.py:342-354` `risk_scan()` (200-target walk: 0 real escapes); #9 browser canonical per locked constraint 4 (`browser_harness.py:28` 320–1280px matrix, zero runtime deps).
- L3: closed all three `[?]`s docs-only in `docs/12-agent-root-discovery-2026-09-08.md` v1.1.0 against primary sources fetched in-session — Codex `.agents/skills/` REPO/USER/ADMIN/SYSTEM roots with explicit no-merge same-name policy (`https://learn.chatgpt.com/docs/build-skills`; facade `~/.codex/skills` flagged compat-only; `AGENTS.md` layering kept distinct via `.../agent-configuration/agents-md`); Command Code six-way selection order (project `.commandcode/` > project `.agents/` > user `~/.commandcode/` > user `~/.agents/` > extras > bundled) with Duplicate-names warnings, `/skill:<name>` hatch, ≤10-level `.agents/` walk stopping at `$HOME`, recursive nested folders, live reload (`https://commandcode.ai/docs/skills`); Claude enterprise > personal > project with both-load nested/plugin, bundled/commands/synced rows (`https://code.claude.com/docs/en/skills`). Proposed read-only `doctor --explain CONSUMER --project DIR` (read-time derivation, per-winner source citation, no persistence, `effective_state: unresolved` elsewhere) — needs its own issue/ADR approval per locked constraint 5. `check_docs.py` PASS after the edit.
- L5: verified the deferred four untouched — issues #3/#4/#8/#11 all OPEN with zero comments; no network (`urllib` only for URL parsing in `webapp.py`/`web_security.py`), backend (eval stays stdlib caller-scored), extension (no TS surface), or signing (`bundle_policy()` = `deferred`) code in `skillsmgr/`; ZIP stays rejection-only (`store.py:1221`).
- L6: verified the release gate without publishing — package `1.0.0` == tag `v1.0.0`; `release.yml` tag/version gate + build-once + `--dist-dir` + attestation + TestPyPI→protected `release` env; README makes no PyPI-install claim; `check_package_data.py` honestly UNAVAILABLE (no `build` module).
- Docs: `TODO.md` L1/L3/L4/L5 marked done with evidence (L2 ZIP stays the only approval-gated code item; #10 Deferred line retained one pass as close record), `task.md` Milestone 31 updated + Milestone 32 (this round) added, `PLAN.md` annex verdicts updated, `docs/12-agent-root-discovery-2026-09-08.md` v1.1.0.
- Verification: T14 ladder re-run recorded in the next entry below (kept separate so commands stay copy-verifiable).

## 2026-09-09 — Milestone 11 round-1 verification ladder (T14)

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → 301 tests OK.
- `python3 smoke_store.py` → ALL STORE SMOKE TESTS PASSED; `python3 smoke_web.py` → ALL WEB SMOKE TESTS PASSED.
- `py_compile` (all tracked `skillsmgr/*.py` + root `*.py`) → OK; `node --check` `app.js` + `domain.js` → OK; `check_docs.py` → PASSED; `check_complexity.py` → PASSED (151 functions, budget ≤ 15); `git diff --check` → OK; `--help` → OK.
- `python3 browser_harness.py` (system Chrome CDP) → `"passed": true` across 320/400/640/900/1280px, zero console errors/warnings/network failures/overflow.
- Fresh-tmp live seam (`SKILLS_MANAGER_DATA=$(mktemp -d)`): create → validate (ok + 2 description warnings) → doctor (consistent) → search (hit) → remove → `trash purge` (`purged ['l3verify']`) → doctor (consistent) → OK.
- `check_package_data.py` → honestly UNAVAILABLE (no `build` module; no `dist/` artifact used as evidence) — unchanged standing behavior, not a regression.

## 2026-09-09 — Loop-engineering research verdicts (probes + 200-source survey)

- Ran 9 hermetic probe scripts (isolated temp dirs, stdlib only, no product-code changes; scripts in `/tmp/probe_*.py`, outside the repo): link matrix (`../`, absolute, deep escape warn; `https://`/`#`/`<angled>` clean; 200-target live walk = 145 external/anchor, 55 in-root, 0 out-of-root); zip (`zipfile` keeps hostile names verbatim; symlink-bit detectable); tar (6/6 hostile classes rejected); search (`*a*a*a*a*` instant, 500-char query clean `ValueError`); frontmatter (dup/huge/flow-bomb all clean `FrontmatterError`); eval/risk/registry/quarantine (9 findings on hostile skill, trust gate `False→True`, stage-only); effective boundary (`consumer_view` + `unresolved`, 3-way sides, preview risks, `unknown` provenance); REST (x-origin 403, no-CT 415, bad install 400, long query 400); signing (HMAC ok, `ed25519` absent).
- Surveyed ~200 web sources in ~30 batches plus 5 primary fetches (agentskills spec/eval, skills.sh CLI/API, Socket×skills.sh, Codex skills doc, Command Code skills, Claude priority explainer) across registry, eval, archive, localhost, signing, discovery, atomicity, and accessibility families.
- Verdicts: CLOSE #10 (already shipped); APPROVE ZIP as a scoped `import` extension (red-first corpus; ~90% of tar policy ports; new = symlink-bit check, zip manual extractor, bomb ratio); REJECT tar-refusal #6 (keep feature-detect + guarded extractor), link-to-error #7 (keep warning + `risk_scan()`), desktop wrapper #9 (browser canonical); DEFER registry network #3 (OIDC-gated API; staged offline→passthrough), eval backend #4 (advisory-only, file-based, never blocking), extension in-repo #8 (separate repo), team sharing #11 (trust ADR + threat-model delta first); keep effective resolution `unresolved` (per-consumer precedence is not global; close 3 `[?]`s, then propose read-only `doctor --explain`).
- Docs-only change recorded in `TODO.md` (v2.1.0: Milestone 4 note, Deferred verdicts, Milestone 11 queue L1–L6), `task.md` (Milestone 5 verdicts, Milestone 31), `PLAN.md` (§9 bullets, §11 annex). No code, no locked-constraint changes.
- Verification: `python3 check_docs.py` PASS; full ladder re-run is the new session's first job (L1–L6 start there).

## 2026-09-09 — Insights audit round 5 (degenerate, fs, perf, docs truth)

- Swept degenerate inputs (empty lists/dicts, `None`/`0` bodies, empty consumer), nested/odd structures (list provenance, dict hashes, falsy flags, nested body values, int names, bool skill, int/None eval fields, unicode), and large inputs (500KB body 0.06s, 10k links 0.03s, 20k-line diff 0.01s, 5k eval cases instant, 10k-record views): all JSON-clean, no raw errors.
- Filesystem audit: dangling/file/deleted/locked paths classify `invalid`; non-string paths skip dir validation (`managed`, documented); locked-file probe confirmed `scopes.get_skill()` itself raises `PermissionError` before insights runs (Store/scopes seam, out of scope); `insights.py` performs no direct `open()`.
- Perf: 8-thread × 150 mixed-helper workload 2.49s zero errors; 200k-line scan 0.06s; 20k-record views under 0.1s. REST/CLI regression clean (validate/search/purge).
- Docs truth: stale "31 tests" claims in SESSION-CONTEXT/task/CHANGELOG corrected to 52. Added 5 round-5 lock tests (57 total in the file).
- Verification: 301 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS, package-data honestly UNAVAILABLE (no `build` module), `browser_harness.py` PASS (`"passed": true`), fresh-tmp validate/purge OK.

## 2026-09-09 — Insights boundary round 4 (deep-copy, callable, strings)

- Probed 7 hypothesized boundaries; all 7 confirmed genuine: `consumer_view()` shallow-copied nested dicts (caller mutation leaked into inputs), `eval_score()` let non-callable scorers raise raw `TypeError`, `quarantine_plan()` accepted non-string sources into JSON output, `update_preview()` accepted non-string snapshot items, `registry_preview()` crashed on non-string descriptions and accepted non-string source/scope, `consumer_view()` accepted non-string consumers.
- Fixed red-first (7 new tests, 52 total in the file; 5 failures + 2 errors before green): `copy.deepcopy` record copies, `callable()` scorer guard, `isinstance(str)` source guard, non-empty-string snapshot items, description non-string becomes a blocker, `_require_optional_str()` for source/scope/content_hash, consumer `isinstance(str)` guard. No locked-constraint changes.
- Verification: 296 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS, package-data honestly UNAVAILABLE (no `build` module), `browser_harness.py` PASS (`"passed": true`), fresh-tmp validate/purge OK.

## 2026-09-09 — Deep E2E audit of all 45 insights tasks (E1–E9)

- Built isolated-tmp E2E worlds (global + cursor scopes, duplicates, disabled, risky, real snapshots): E1 lifecycle OK (4 global incl. disabled, 2 cursor, `find_duplicates` flags `e2e-dup`); E2 views OK (3 vs 2, precedence unresolved) with all-five ownership states and 64-char provenance hashes; E3 diff OK (description+body, 6-line bound) and snapshot rollback byte-accurate; E4 risk OK (script/link/pattern on the hostile skill, clean skill empty), quarantine stage-only, registry trust-gated, eval 1/1, bundle deferred.
- E5 purity proved by SHA-256 tree hash before/after running every helper over every record pair: disk and inputs unchanged. E6: 30× JSON sweep instant, ordering deterministic, 8-thread × 150-iteration concurrency clean, 6000-line diff truncates to 200 in <0.05s. E7: REST matrix (skills/stats/doctor/scopes/search) 200 OK, CLI create/list/search/doctor/purge OK.
- E8 genuine defect (red-first): global `Store.list()` rows lack the loader `malformed` flag, so validator-failing global skills classified `managed`. First fix attempt (re-validating `record["body"]`) was wrong — body-only text always errors without frontmatter — and broke 2 tests. Correct fix: `_record_invalid()` checks the loader flag, else `validator.validate_skill(name, path)` against the record's real skill directory; synthetic no-path records stay non-invalid. 5 permanent E2E tests in `TestInsightsDeepE2E` (45 total in the file).
- Verification: 289 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS, package-data honestly UNAVAILABLE (no `build` module), `browser_harness.py` PASS (`"passed": true`), fresh-tmp CLI validate/purge OK.

## 2026-09-09 — Insights robustness round 3 (strict names, JSON, determinism, hostile data)

- Strict-string name policy: `quarantine_plan()`/`eval_plan()` now reject non-string names (`123`, `True`, lists, dicts) with clean `ValueError` via `_canonical_name()`; padded real strings still trim. Found red-first (1 failure), green after.
- Locked behavior contracts (9 new tests, 40 total in `tests/test_insights_contracts.py`): JSON-serializability of all 11 helper outputs; deterministic consumer-view ordering under shuffle with input-order-preserving ownership; non-string fields (`int` body, `dict` description, list tools/extensions) never raise raw errors; null-byte/100KB/emoji bodies scan in milliseconds and stay JSON-clean; scorer exceptions propagate while malformed plans/misaligned outputs raise `ValueError`; three-way missing keys and registry extra keys locked; 4000-line diffs and 100k-line scans complete under 5s within the 200-line bound; 4-thread × 100-iteration concurrency smoke clean.
- Hygiene refactor: `risk_scan()` decomposed into six single-purpose scanners (peak complexity 19 → 9, all `insights.py` functions ≤ 9 by local audit; file is outside the `check_complexity.py` hotspot set so the CI ratchet is unaffected).
- Verification: 284 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS, package-data honestly UNAVAILABLE (no `build` module), `browser_harness.py` PASS (`"passed": true`), fresh-tmp live-seam OK.

## 2026-09-09 — Insights fail-closed hardening follow-up (T1–T15, second round)

- Hardened `skillsmgr/insights.py` after a 16-probe hostile-input sweep found raw `AttributeError`/`TypeError`/`ValueError` leaks: every record-dict entry point now raises clean `ValueError`; `consumer_view()` skips non-dict list items; `update_preview()` coerces tokens safely (`None` for non-numeric, negatives/bools rejected) and rejects non-list snapshots; `diff_skills()` caps `body_diff` at `MAX_BODY_DIFF_LINES` (200) with `body_diff_truncated`; `eval_plan()` requires dict cases carrying input/expect; `registry_preview()`/`eval_score()` reject non-dict/non-list shapes. No locked-constraint changes.
- Added 11 red-first hardening tests (`tests/test_insights_contracts.py` now 31 tests; 2 failures + 9 errors before the fix, all green after). Re-ran the adversarial sweep: every hostile probe now returns clean `ValueError` or a safe value; 5000-line bodies truncate to 200 lines.
- Reconciled `docs/02-modules.md` (fail-closed policy section), `docs/SESSION-CONTEXT.md` (file inventory gains `insights.py` + tests), and stale "20 tests" claims in `task.md`/`CHANGELOG.md`/progress log.
- Verification: 275 unittest PASS, both smokes PASS, compile/frontend/docs/complexity/diff/help PASS, package-data honestly UNAVAILABLE (no `build` module), `browser_harness.py` PASS (`"passed": true`), fresh-tmp live-seam exercise OK.

## 2026-09-09 — Milestone 9 read-only insight foundation (T1–T15)

- Added `skillsmgr/insights.py`: twelve pure stdlib-only helpers with zero disk mutation and no locked-constraint changes (no new CLI commands/flags, no new `Store` methods, `SCHEMA_VERSION = "1"` unchanged, no network/dependencies). `consumer_view()` lists one consumer's observed instances with precedence explicitly unresolved per ADR-002; `diff_skills()`/`diff_three_way()` preview field/body changes and hold base on conflict; `ownership_states()` classifies `managed`/`unmanaged`/`adopted`/`quarantined`/`invalid`; `provenance_summary()` splits known loader observations from explicit unknowns; `update_preview()` reports changed files, token/body/snapshot risks, and rollback availability; `quarantine_plan()` returns a stage-only plan validated by `validate_skill_name()`; `risk_scan()` explains script/link/tool/pattern findings with why + evidence; `registry_preview()` is an offline dry-run gated on explicit trust; `eval_plan()`/`eval_score()` are provider-neutral, deterministic, and advisory-only; `bundle_policy()` records signatures as `deferred` pending issue #11.
- Added `tests/test_insights_contracts.py` (31 red-first hermetic tests: all failed on missing-module import before the implementation; all pass after). Exercised the helpers against live public seams in an isolated temp dir (`Store.create` + `scopes.list_all`/`get_skill`): consumer view, diff, ownership, provenance, preview, risk, registry gate, eval, bundle, and quarantine plan all behaved as specified.
- Reconciled `docs/02-modules.md` (new `insights.py` section), `TODO.md` Milestone 9 (foundation checked with approval-gated runtime exposure noted), `task.md` Milestone 25 (T1–T15), and `CHANGELOG.md` Unreleased.
- Verification: full ladder below in T14; `git status` shows exactly the intended files (no live skill roots touched).

## 2026-09-09 — Browser UX, accessibility, module seams, and documentation truth

- Split the CLI behind compatibility-preserving seams: `cli_parser.py` owns argparse construction, `cli_handlers.py` owns command behavior, `cli_output.py` owns rendering, and `cli.py` remains the stable adapter (`main`, `build_parser`, handler/private helper names). The parser inventory and CLI contract tests remain green.
- Split the no-build frontend: `webui/domain.js` owns fetch/formatting/frontmatter/escaped-Markdown policy and `app.js` owns Vue state/workflows. `index.html` loads domain before app; package-data uses recursive source discovery and includes the new file.
- Added accessible modal behavior: labelled dialogs, safer initial focus, Tab trap, Escape close, focus restoration, `inert`/`aria-hidden` background, pressed/current state attributes, live announcements, and a `?` keyboard shortcut help dialog. Added escaped editor Markdown preview and pre-sync source/target/overwrite/rollback resolution preview.
- Added `browser_harness.py`, a dev-only stdlib + system Chrome DevTools Protocol probe. It starts a hermetic server, captures console/runtime/network failures and horizontal overflow, and passed 320, 400, 640, 900, and 1280px viewport probes. CSP was corrected to permit the vendored Vue global runtime compiler while retaining the existing localhost security headers.
- Reconciled `AGENTS.md`, `docs/02-modules.md`, `docs/08-web-ui.md`, `docs/SESSION-CONTEXT.md`, `TODO.md`, `task.md`, `CHANGELOG.md`, and current plan/backlog claims. Effective consumer shadowing and native wrapper remain explicitly deferred/approval-gated.
- Verification: targeted web/CLI/docs/package tests PASS, `smoke_web.py` PASS, `node --check` PASS, browser harness PASS. Final ladder also passes: 244 unittest tests, both smoke suites, Python compile, frontend syntax, `check_docs.py`, `check_complexity.py`, CLI help, browser harness (5/5 viewports), and `git diff --check`; fresh package-data verification is unavailable in the base interpreter because the optional `build` module is not installed. Review follow-up also closes release tag/version validation, Windows xplat interpreter selection, least-privilege workflow permissions, and CI browser/domain coverage with contract tests.


## 2026-09-09 — Controlled release engineering (Milestone 8 CI/packaging half)

- Reworked CI into separate `unit` (Python 3.10–3.14 matrix) / `adversarial` / `package` / `docs` / `xplat` (Linux/macOS/Windows × 3.10/3.14) / `browser` jobs with least-privilege `contents: read`, a documented action-pin policy (third-party release actions pinned to reviewed SHAs; first-party `actions/*` on tags with verified SHAs recorded), and a build-once package gate: CI builds one wheel+sdist, uploads `dist`, and `check_package_data.py --dist-dir dist` inspects those exact artifacts, followed by a clean-venv wheel install smoke.
- Added `check_package_data.py --dist-dir DIR` (inspect exactly one wheel + one sdist already in DIR; exit 1 on count mismatch or package-data failure) for the build-once/test-exact-artifacts contract; `pyproject.toml` classifiers extended to 3.13/3.14 to match the tested matrix.
- Closed a genuine cross-platform containment gap found while writing the xplat matrix: neither `contained_path()` nor archive member validation rejected Windows `\` separators or `C:` drive prefixes on POSIX hosts (POSIX `pathlib` treats them as plain characters/relative paths, while Windows resolves them as separators/absolute paths). Both now reject them on every host; red-first hermetic regressions prove it and the pre-existing path/archive/scope/store/CLI suites stayed green.
- Added tag-gated `.github/workflows/release.yml`: validate the tag against the package version before building or publishing; build once → verify exact artifacts (package-data, unit, docs, clean-install CLI smoke) → attest build provenance → TestPyPI (`testpypi` environment) → PyPI (protected `release` environment, OIDC Trusted Publishing, no long-lived token) → GitHub Release with the exact assets → tag/version/web-asset/hermetic-CRUD verification plus a PyPI-install check. Workflow defaults are least-privilege `contents: read`; only publish/release jobs request additional permissions.
- Qualified PyPI claims honestly per the release policy: PyPI badge removed from `README.md`; README states PyPI is a future release and points at source/CI-artifact installs. PyPI `skills-manager` JSON still 404s as of this change (checked 2026-09-09), so no published-install claim is made.
- Locked with `tests/test_ci_release_contracts.py` (red-first): CI matrix/jobs/permissions/artifact assertions, xplat containment + build-once mode assertions, release workflow assertions (tag gate, environments, Trusted Publishing, attestation, TestPyPI/PyPI, GitHub Release, post-publish checks), and PyPI-claim assertions. `TODO.md` Milestone 8 marked accordingly, `task.md` Milestone 23 added, `CHANGELOG.md` Unreleased and `CONTRIBUTING.md` checks updated.
- Verification: full unittest suite PASS; `smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); Python compile PASS; `node --check skillsmgr/webui/app.js` PASS; `check_docs.py` PASS; `check_complexity.py` PASS; both workflow YAML files parse; `git diff --check` PASS. Browser/a11y work is tracked in the newer 2026-09-09 entry above; this entry records the release-engineering checkpoint as it stood before that follow-up, not a current open-status claim. The xplat workflow uses the portable `python` executable so Windows matrix legs invoke the configured interpreter.

## 2026-09-09 — Advanced loop-engineering campaign closeout

- Ran nine deterministic hermetic probe loops (stdlib-only, seeded; probe code kept outside the repo): store-lifecycle burst, frontmatter round-trip/hostile fuzz, failure injection, REST fuzz, concurrency stress, search/validator/loader-templates/CLI-env fuzz, CLI adversarial matrix, archive boundary+grammar fuzz, scope differential loop.
- Fixed 15 genuine defects surgically with red-first hermetic regressions and no locked-constraint changes (no new commands/flags, no new Store public methods, `SCHEMA_VERSION = "1"` unchanged): trashed-row reactivation on create/add (incl. resync of any returned live directory), same-second trash counter recognition, honest double-remove error, import backup-move recovery preserving the original, truncated-gzip clean StoreError, CLI first-run schema bootstrap, install validation parity, flow-scalar and quote-char key quoting, nested-block mapping emission with inline empty collections, post-sync global index reconciliation, shared per-skill lock coverage with stranded-temp cleanup, purge StoreError wrapping, loud duplicate frontmatter-key errors (FIX-14, promoted from OBS-1), and deduped `purged` names (FIX-15, promoted from OBS-3).
- Full findings with repro/root-cause/fix evidence live in `loop-engineering-findings.md`; owning docs updated (`docs/02-modules.md` store/frontmatter behavior incl. duplicate-key rejection, `docs/04-store-api.md` `purged` dedup, `docs/03-cli-surface.md` list semantics) and `task.md` Milestone 22 closed.
- Verification: full unittest suite (224 tests) PASS; `smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); Python compile PASS; `node --check skillsmgr/webui/app.js` PASS; `check_docs.py` PASS; `check_complexity.py` PASS (194 functions); `git diff --check` PASS; package-data gate remains honestly `UNAVAILABLE` (no `build` module in this environment; CI installs it).

## 2026-09-08 — REST two-server search isolation regression closeout (18:42 UTC)

- Fixed both REST search routes (`/api/search` and `/api/skills?q=...`) to pass the request handler's `self.store` into global and merged `scopes.search_all()` calls. Agent-scope searches still use filesystem adapters; body-aware ranking, response schemas, and singleton compatibility for non-WebAppServer callers are unchanged.
- Added a hermetic two-server regression in `tests/test_search_contracts.py`: separate Stores are served concurrently, and each server's `scope=global` response contains only its own global skill while `scope=all` contains its own global skill plus the shared agent skill. Both server lifecycles are cleaned up.
- No commands, Store methods, schema, dependencies, or `.autogit` contents were changed.
- Verification: focused search contracts (11 tests) PASS; full unittest suite (208 tests) PASS; `smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); Python compile PASS; `node --check skillsmgr/webui/app.js` PASS; `check_docs.py` PASS; `check_complexity.py` PASS (168 functions); `git diff --check` PASS.

## 2026-09-08 — CLI data-dir search regression closeout (18:27 UTC)

- Fixed `cmd_search()` to pass the Store created for `--data-dir` into the scope search adapter. Global search and the global portion of merged search now read only the requested data directory; agent-scope records still come from scope filesystem adapters.
- Added a hermetic two-data-dir regression in `tests/test_search_contracts.py` proving global isolation and merged results contain the requested global result plus the agent result, never the other Store's result.
- Preserved body-aware global/merged ranking, historical output shapes, error contracts, and all locked constraints; no commands, Store methods, schema, dependencies, or `.autogit` contents changed.
- Verification: focused search/CLI tests PASS (15 tests); full unittest PASS (207 tests); `smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); Python compile PASS; `node --check skillsmgr/webui/app.js` PASS; `check_docs.py` PASS; `check_complexity.py` PASS (168 functions); `git diff --check` PASS.

## 2026-09-08 — Uncommitted-change review and verification

- Reviewed all tracked and untracked changes except `.autogit`; inspected `AGENTS.md`, owning docs, tests, smoke scripts, CI, and production diffs. The review identified a high-impact CLI `--data-dir` search regression; the subsequent closeout above fixed it and added isolation coverage.
- Applied only permitted surgical changes to tests, docs, smoke scripts, and CI: strengthened smoke history assertions, synchronized fixture server readiness, made concurrency readers prove execution, made secondary smoke cleanup exception-safe, removed brittle package-asset count assumptions, corrected current test/gate guidance and duplicate CLI documentation, and made CI install packaging build tooling before the package-data gate.
- Local package-data verification remains `UNAVAILABLE` because this environment has no `build` module; no stale `dist/` artifacts were used. CI now installs `build==1.2.2.post1` and requires the fresh-build gate.

## 2026-09-08 — Search contract defect closeout (17:51 UTC)

- Fixed scope and merged searches dropping global body-only matches: `scopes.search_all()` now obtains global list rows through `Store.list()` and body content through `Store.get()` before applying the existing bounded scorer. CLI and REST global search paths use this same body-aware public seam, preserving ranking and response shapes.
- Fixed wildcard complexity errors escaping from `scopes.search_all()`: bounded matcher `ValueError`s are translated to `StoreError`, so CLI returns its normal clean exit-1 error and REST returns the standard JSON HTTP 400 error.
- No commands, Store methods, schema, dependencies, or `.autogit` contents were changed. Existing focused regressions in `tests/test_search_contracts.py` remain authoritative; no fixture assumptions required correction.
- Verification: `python3 -m unittest tests.test_search_contracts` — 9 tests PASS; the later CLI and REST isolation closeouts raised the final full suite to 208 passing tests. Final smoke, compile, frontend syntax, docs, complexity, and diff checks are recorded in the newest entries.

## 2026-09-08 — Documentation consistency gate

- Extended `check_docs.py` with offline checks for all local `@docs/*.md` links, explicit documented source paths, qualified `Store.method`/module symbols, current CLI command inventory, current web UI claims, and source/package/documented version alignment.
- Current command counts are derived from `skillsmgr/cli.py` (27 top-level + 7 nested + 3 aliases = 37 invocable names); superseded GTK planning and append-only historical entries remain exempt from current-claim checks.
- Added five focused stdlib tests covering the clean repository gate, broken pointers, missing Store symbols, version mismatch, and parser-derived command inventory.
- Verification: `python3 check_docs.py` PASS; focused docs tests PASS (5 tests). Full suite and smoke verification remain delegated to the parent session.

## 2026-09-08 — Distribution package-data verification

- Added stdlib-only `check_package_data.py`, which builds exactly one wheel and one sdist in a fresh temporary directory via `python -m build`, then checks deterministic `skillsmgr/webui/` contents including vendored Vue.
- Added offline `tests/test_package_data.py` archive fixtures and exact member-set assertions; no network or third-party test dependency is required.
- Optional `--install` probes install each fresh artifact into an isolated temporary venv with `pip --no-index --no-deps`; runtime dependencies and product APIs are unchanged.
- Exact limitation: this environment lacks the optional `build` module (`/usr/bin/python3: No module named build`), so the live check reports `UNAVAILABLE` and does not inspect stale `dist/` artifacts. `--require-build` is available for release CI to make unavailable tooling non-zero.

## 2026-09-08 — Hermetic smoke fixture refactor

- Added `smoke_fixtures.py` with only shared temporary Store setup/cleanup and loopback WebAppServer start/stop lifecycle helpers; refactored both executable smokes to use those helpers without changing their assertions or printed checkpoints.
- Added two stdlib `unittest` regressions covering initialized-store cleanup and ephemeral loopback-server lifecycle.
- Verification: `python3 smoke_store.py` PASS (`ALL STORE SMOKE TESTS PASSED`); `python3 smoke_web.py` PASS (`ALL WEB SMOKE TESTS PASSED`); focused fixture tests PASS (2 tests); `python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py` PASS; `python3 check_complexity.py` PASS (166 functions); `git diff --check` PASS. An intermediate full unittest run covered 202 tests but reported 3 failures plus 1 error in search-contract tests; it was superseded by the later search closeout at the top of this log. An intermediate `check_docs.py` run also reported stale command-inventory mismatches; those docs were corrected before the later passing gate.

## 2026-09-08 — Helper compatibility audit

- Audited the extracted web policy/serialization/upload modules and CLI output helpers against their pre-extraction interfaces and recent history.
- Found no concrete compatibility regression: `webapp._json_bytes`, `webapp._parse_multipart`, `webapp.RequestError`, and CLI output aliases preserve their historical call shapes and behavior.
- Added `tests/test_compatibility.py` to lock those private compatibility seams, including the historically ignored `_json_bytes` status argument and one-argument CLI helper calls.
- Verification: focused compatibility/web/CLI tests passed (29 tests); compile, docs consistency, and complexity checks passed.

## 2026-09-08 — Web policy extraction, contract regressions, and complexity ratchet

- Extracted request security, JSON serialization/body parsing, and bounded multipart upload staging into private stdlib-only modules while retaining `webapp.py` compatibility wrappers.
- Fixed text `scopes` output attempting to access unrelated skill snapshot arguments and fixed raw REST archive import to forward `full=1`.
- Added focused CLI and REST regression tests plus an AST complexity ratchet with a checked-in baseline, contributor instructions, and CI wiring.
- Added stderr-only diagnostics for rollback cleanup failures so recovery problems are visible without changing public schemas.
- Deep verification found malformed JSON field types that leaked as HTTP 500 and a CLI color documentation mismatch; added 4xx validation, integrated CLI output helpers, and corrected the CLI docs.
- Verification: full repository suite passed (128 tests), store/web smoke, docs gate, frontend syntax, compile, CLI color/output probes, and complexity check.

## 2026-09-08 — Atomic recovery, hash verification, and documentation truth

- Completed ten executable backlog tasks: atomic sibling-temp writes with flush/fsync/replace, rollback preservation across filesystem/index failures, same-process per-skill mutation serialization, failure-injection coverage, richer doctor diagnostics, and content-hash backup verification.
- Scope and template writers now use the same atomic document policy; snapshots are also written atomically. Cross-process behavior is explicitly documented as atomic-file replacement plus `doctor`/`db resync` recovery, without adding lock files or public API surface.
- Export manifests now carry optional SHA-256 skill-tree hashes; imports verify hashes during staged and committed copies while preserving the existing per-skill `imported`/`skipped` contract.
- Reconciled current architecture/scope/API/CLI documentation, removed the deleted GUI path from Command Code settings, and added `check_docs.py` as a machine-checkable docs/source gate wired into CI.
- Verification evidence for this slice is recorded after the final full-suite, smoke, frontend, help, docs-gate, and diff checks.

## 2026-09-08 — Root/consumer discovery baseline

- Completed the next five executable Milestone 4 tasks without introducing a new
  public data model, CLI command, Store method, or SQLite field.
- Added ADR-002 for `SkillRoot`, `Consumer`, `ConsumerRootBinding`,
  `SkillInstance`, and `EffectiveSkill`; runtime expansion remains approval-gated.
- Added the official discovery inventory for Claude Code, Cursor, Gemini CLI, and
  OpenCode. Codex and Command Code precedence/reload behavior remain `[?]` until
  primary documentation is available.
- Corrected Cursor's user root to `~/.cursor/skills`. Aggregate scope listings and
  sync target planning now deduplicate resolved physical roots while direct scope
  ids remain compatible.
- Primary-source verification narrowed the Claude Code inventory: discovery and
  live change detection are confirmed, while exact same-name precedence remains
  `[?]` instead of being guessed.

## 2026-09-08 — Root capability and observed instance states

- Completed the next five scope/effective-state tasks as far as the locked
  compatibility boundary permits.
- Recursive scanning is now opt-in per consumer root: Cursor, OpenCode, shared
  agent, and matching project roots recurse; flat roots remain one-level scans.
- Scope descriptors now expose `writable`, `read-only`, `missing`, and
  `unsupported` availability, plus consumer and recursive-discovery metadata.
- Scope records expose observed `active`, `disabled`, `invalid`, `duplicated`,
  `divergent`, and `unmanaged` states. Effective resolution is explicitly
  reported as `unresolved`; `shadowed` classification remains approval-gated
  until ConsumerRootBinding precedence is a runtime model.
- Sync continues to target each resolved physical root once. Added recursive,
  capability, disabled/malformed, divergent, and unresolved-state regressions.

## 2026-09-08 — Observation and hotspot extraction slice

- Preserved unknown/client-specific frontmatter through edits and exposed a
  non-persisted portable/extension partition in loaded records.
- Added non-persisted content hash, metadata hash, observed timestamp, and
  provenance observations without changing SQLite or public Store signatures.
- Extracted atomic I/O, archive policy, and root-discovery helpers into internal
  modules, plus the root-containment primitives into `path_safety.py`, while
  keeping Store/scopes/paths compatibility adapters and existing error contracts.

## 2026-09-08 — Recovery snapshots, migration, and localhost policy slice

- Completed the next five executable backlog tasks after archive hardening.
- ADR-001 records the decision **not** to add a per-process mutation token:
  loopback-only binding, pre-handler browser request checks, no cookies/sessions,
  and supported local non-browser clients provide the simpler correct boundary.
- Added guarded snapshots under `<data>/snapshots/<scope>/<name>/` with canonical
  scope/name/path validation, newest-five retention, automatic pre-edit and
  force-sync-overwrite capture, and global/agent restore. CLI, REST, and web UI
  expose retained snapshot IDs and rollback.
- Added `--full` to existing export/backup/import surfaces. Full archives include
  skills, validated trash, and templates; snapshots and agent scopes remain
  excluded. Full migration uses the current hardened tar/resource/manifest
  pipeline and rejects slim archives when `--full` is requested.
- Added focused tests for snapshot retention/rollback, agent-scope snapshots,
  full migration round trips, slim/full compatibility, REST snapshot routes, and
  staged sync failure preservation.
- Selective replay status: approved candidate worktree code was not merged
  wholesale. Current source retains the hardened archive pipeline and adds only
  the reviewed snapshot/full-migration seams needed by this slice.

## 2026-09-08 — Next-five archive contract and resource-safety slice

- Completed the next five executable archive tasks: resource budgets, strict
  manifest validation, canonical manifestless fallback handling, explicit ZIP
  policy, and per-skill staged/rollback import behavior.
- Tar preflight now enforces compressed-size (25 MiB), expanded-size (16 MiB),
  individual-member (8 MiB), member-count (200), path-length (512), nesting
  depth (16), and compression-ratio (1000:1) limits before extraction.
- Manifests must identify `skills-mgr`, use a supported semantic major version,
  contain a UTC creation timestamp, and list unique canonical skill names whose
  extracted directories and frontmatter agree. Invalid names fail closed.
- ZIP remains intentionally unsupported; content sniffing rejects ZIP bytes even
  when the filename has a tar extension. Each skill is staged independently,
  failed replacements restore the previous destination, and results report
  imported/skipped names.
- Added hermetic tests for all archive limits, strict schema/path/frontmatter
  validation, ZIP rejection, malformed fallback names, forced-destination
  preservation, and injected per-skill copy failure.

## 2026-09-08 — P0 parser, search, and localhost request-safety slice

- Completed ten executable risk-first tasks from the latest `TODO.md` across
  parser bounds, wildcard search, and localhost web request security.
- Frontmatter parsing now enforces document, key, collection, scalar, and nesting
  budgets; deep recursion and malformed bounded structures surface as clean
  `FrontmatterError` values. Valid round trips remain covered.
- Wildcard search collapses repeated stars, caps query length and effective star
  count, preserves body matching, and uses one bounded scorer across Store,
  global/agent/merged scopes, CLI, and REST paths. Adversarial patterns return a
  clean 400 through REST instead of exhausting regex backtracking.
- All state-changing HTTP methods now validate loopback Host/port, reject
  cross-site Fetch Metadata and mismatched Origin/Referer values before route
  handlers, require JSON for JSON mutations, reject non-loopback binds, and add
  CSP/framing/MIME/referrer/cross-origin response headers. Header-absent local
  clients remain supported.
- Added hermetic regressions for hostile browser headers and every mutating
  method, wildcard exhaustion/body matching, parser resource limits, and clean
  error contracts.
- Verified on September 8, 2026: compile PASS, **76 unittest PASS**,
  `smoke_store.py` PASS, `smoke_web.py` PASS, frontend syntax PASS, CLI help
  PASS, focused REST probes PASS, and `git diff --check` PASS.

## 2026-09-08 — Next-five archive and trash safety slice

- Completed the next five executable tasks after the first-ten path-safety
  slice: forced-destination protection, exact trash matching, archive
  preflight, unsafe archive-member rejection, and safe `tarfile.data_filter`
  feature detection.
- `Store.import_()` now validates tar member paths, duplicate names, supported
  regular-file/directory types, manifest structure, canonical skill names,
  and extracted skill documents in a private temporary directory before any
  forced destination deletion or copy. Interpreters without `data_filter` use
  an explicit guarded extractor rather than unfiltered `extractall()`.
- Trash list/restore/purge/doctor now share exact canonical timestamped-entry
  recognition and ignore malformed or symlinked entries consistently.
- Added hermetic regressions for forced invalid names, unsafe members,
  duplicates, symlinks, hard links, FIFOs, no-filter extraction, valid archive
  compatibility, malformed trash entries, and doctor consistency.
- Verified: compile PASS, **65 unittest PASS**, `smoke_store.py` PASS,
  `smoke_web.py` PASS, `node --check` PASS, CLI help PASS, and `git diff
  --check` PASS.

## 2026-09-08 — Close encoded REST raw-read seam

- Added a regression test for an encoded traversal request targeting the global
  `/api/skills/<name>/raw` endpoint. The test first demonstrated the missing
  guard by receiving the wrong 404 behavior for an outside path.
- Fixed the raw-read route to resolve the decoded name through `Store.get()`
  before constructing the file path, preventing disclosure of an outside
  `SKILL.md` while preserving the existing clean HTTP error contract.
- Verified the focused REST safety tests and the full suite: **57 unittest
  tests PASS**. The broader smoke/compile/help/diff checks remain green.

## 2026-09-08 — Selective replay controls and canonical path safety

- Completed the first ten executable tasks selected from the latest `TODO.md`:
  selective replay map, status classification, pre-merge checklist, packaging
  artifact decision, canonical skill-name validation, resolved-root containment,
  Store/scope enforcement, decoded REST validation, and pre-handler CLI
  validation.
- Added `docs/11-integration-status-2026-09-08.md` and
  `docs/PRE-MERGE-CHECKLIST.md`. Candidate worktrees remain classified as
  `worktree-only` or `approved-not-integrated`; no wholesale branch merge was
  performed. `dist/` and `skills_manager.egg-info/` remain ignored local build
  artifacts, not release inputs.
- Added `validate_skill_name()` and `contained_path()`/`safe_skill_path()`.
  Store and agent-scope reads, writes, renames, moves, copies, restores,
  imports, exports, sync destinations, and deletes now validate names and keep
  resolved paths inside their managed roots. Existing symlink escapes and
  absolute path parts are rejected.
- REST path segments are decoded after splitting, so encoded separators reach
  the canonical guard. CLI skill names are rejected before Store construction;
  invalid input does not create a database or touch the filesystem.
- Added hermetic regressions for path/symlink/absolute escapes, Store and scope
  mutation paths, encoded REST deletion, pre-handler CLI rejection, and invalid
  manifestless archive fallback names.
- Verified: compile PASS, **56 unittest PASS**, `smoke_store.py` PASS,
  `smoke_web.py` PASS, `node --check` PASS, CLI help PASS, and `git diff
  --check` PASS.
- Remaining by design: P0-SEC-002 localhost request-origin security,
  P0-SEC-004 wildcard exhaustion, P0-SEC-005 parser resource bounds, the full
  archive preflight/limit policy, recovery/atomicity, UX/accessibility, and
  release packaging. These remain open in `TODO.md`.

## 2026-09-07 — Milestone 0 baseline and P0 reproduction evidence

- **Completed the first two world-class roadmap tasks** from `TODO.md`.
- Captured a reproducible baseline in `docs/09-baseline-evidence-2026-09-07.md` at commit `667fabb7ddb41fcd0db6fb9a58128665bba0190c`: compile PASS, **47 unittest PASS**, `smoke_store.py` PASS, `smoke_web.py` PASS, `node --check` PASS, and CLI help PASS.
- The package-build check was run honestly and returned exit 1 because `/usr/bin/python3: No module named build`; this remains a Milestone 8 release-engineering gap and was not hidden by using existing `dist/` artifacts.
- Reproduced all five current-`main` P0 behaviors in isolated temporary environments before product-code changes: mutation path traversal deletion, cross-origin localhost trash purge, invalid manifestless archive name import, wildcard matcher timeout, and raw frontmatter `RecursionError`.
- Updated `TODO.md`, `task.md`, and `docs/README.md` to point to the evidence report. No source code or `.autogit` was modified.

## 2026-09-08 — Milestone 0 worktree integration comparison

- **Completed the third world-class roadmap task** from `TODO.md`.
- Compared `agents/todo-plan-implementation` (`2bb7280`, 22 changed files, 74 tests) and `agents/milestone5-research-user-needs` (`c5a7161`, 17 changed files, 55 tests) file-by-file against current `main` (`667fabb`). Both candidate worktrees pass their own unit and smoke suites and both diffs pass `git diff --check`.
- Found **13 overlapping files**, with `skillsmgr/store.py` the highest-risk conflict because both branches independently change archive intake. The comparison report requires manual archive-pipeline design rather than a textual merge.
- Classified the security/adversarial branch as the primary P0/recovery source and the Milestone 5 branch as a secondary ZIP/UX source. Defined replay order: tests → P0 security → localhost security → recovery → archive policy → UX → docs.
- Wrote `docs/10-worktree-integration-comparison-2026-09-08.md`. No candidate worktree, product source, test file, or `.autogit` was modified.

## 2026-09-05 — Dedup + token-budget closeout (Milestone 7, v1.1 items 3–4 done)

- **Cross-scope dedup (code, no constraint-5 impact)**: `scopes.find_duplicates()` — read-only grouping over `list_all()`, same-name groups with `scopes`/`count`/`descriptions_differ`/`records`, converge via existing `sync_skill()`. Surfaced in `doctor --scope all` (text lines + `duplicates` JSON key), `/api/doctor?scope=all` (`duplicates` + `scopes` keys), doctor modal section with per-name Sync… buttons (jump into existing sync modal via `syncDupe()`). No new commands/flags/Store methods.
- **Smoke gotcha**: `smoke_web.py` is NOT HOME-hermetic — real `~/.agents/skills` leaks into `/api/doctor?scope=all`, so the new smoke section asserts shape (`isinstance list`), not emptiness. Unit tests stay hermetic (HOME+DATA redirected).
- **Frontend**: `openDoctor()` appends `?scope=all` when `activeScope === "all"`; new `.btn-sm`/`.pill-warn`/`.dupe-list` styles.
- **Token budget (verified complete, no new code)**: `tokens --scope all` aggregate + `largest`, `/api/stats?window=` (`all_tokens/all_avg/all_pct`, top-5 `largest`), `/api/tokens`, frontend budget bar + window selector + per-row tokens + sync cost hint.
- **Verified**: compile OK, **47 unittest OK** (4 new dedup tests), both smokes PASS, `node --check` OK, `--help` OK, live `doctor --scope all` shows dupes in text + JSON.
- **Docs**: task.md M7 dedup+budget [x], TODO.md v1.1 items 3–4 [x], ROADMAP v1.1 dedup+budget [x], CHANGELOG Unreleased entries, 03-cli-surface doctor line, 08-web-ui doctor row, 02-modules scopes line.
- **Remaining**: PyPI upload needs token; rollback/migration ASK issues opened (#1 snapshots, #2 full-migration) — no code until approved.
- **Pushed**: commit `0eeb0ac` (v1.1 dedup + budget), CI green (run 33946982582, 21s); issues #1 + #2 opened via `gh`.

## 2026-09-05 — Publish + v1.1 spec-lint+ (Milestone 7 in progress)

- **Published**: `gh repo create skills-manager --public` → `udayvarmora07/skills-manager`; `main` + `v1.0.0` pushed; CI green (run 33914953774, 20s). Placeholders replaced (YOUR-USER→udayvarmora07; security@example.com→private advisories link). PyPI name `skills-manager` free; `dist/` built (sdist+wheel 1.0.0); upload blocked pending PyPI API token.
- **Spec-lint+ (v1.1, no constraint-5 impact)**: `NAME_RE` already rejects `--` (verified empirically); new `description_score()` (use-context regex + filler-word set); description warnings (missing use-context, vague filler); body token warning (`MAX_BODY_TOKENS=5000` via `tokens.count_tokens`, progressive-disclosure guidance); `scripts/`/`references/`/`assets/` layout check (dangling mentions). Sourced from agentskills.io best-practices + optimizing-descriptions guides.
- **Tests**: 5 new unittest cases → **43 OK**; `smoke_store.py` gains a spec-lint section (vague + oversize + score asserts). Both smokes PASS, `node --check` OK.
- **Docs**: task.md Milestone 7, TODO.md v1.1 items 1–2 [x], ROADMAP spec-lint [x], CHANGELOG Unreleased entry, 02-modules validator line.
- **Remaining**: PyPI upload needs token; cross-scope dedup + token budget view next (code, no ASK); rollback/migration need issue-first ASK.

## 2026-09-05 — OSS launch kit completion (Milestone 6)

- **Packaging/docs verified present**: pyproject.toml, .gitignore, LICENSE (MIT), README.md, CONTRIBUTING.md, SECURITY.md, CHANGELOG.md, ROADMAP.md, both security reports, tests/test_store.py + test_webapp.py, CI + issue/PR templates. Recreated missing `tests/test_web_scopes.py` (13 hermetic scope tests). Deleted `__pycache__/` dirs.
- **Test fixes (2 test bugs, 1 real bug)**: `_skill_body` helper called `dump_frontmatter(dict, body)` but signature is `dump_frontmatter(data, /, *, key_order)` — fixed to append body separately (3 errors). **Real bug**: `Store.restore()` matched `p.name.startswith(name + "-")` + regex on remainder, so restoring `demo` could grab `demo-x-<ts>` (test proved: got "Demo x skill"). Fixed to `_strip_trash_suffix(p.name) == name`.
- **Webapp test hang fixed**: `setUpClass` created `WebAppServer` but never started `serve_forever`; `tearDownClass` referenced nonexistent `server._thread`. Fixed: daemon thread + `server.shutdown()` + join + `server_close()`. Suite: 22 + 3 + 13 = **38 tests OK**.
- **Offline-env decision enforced**: no network for pip (PEP 668 + no dist). CI + CONTRIBUTING + PR template + pyproject switched pytest→stdlib `python3 -m unittest discover -s tests`; dropped `[dependency-groups] dev = pytest`. Also fixed stale README cursor path (`~/.cursor/skills-cursor`) and venv-based setup (no deps to install).
- **Verified**: `py_compile` OK, 38 unittest OK, `smoke_store` PASS, `smoke_web` PASS, `node --check` JS_OK, `--help` OK, `list --scope agents --json` → `[]` (no ~/.agents on this box).
- **Remaining before publish**: replace `YOUR-USER` (README ×3, pyproject ×5, CONTRIBUTING ×1) + `security@example.com` (SECURITY.md). Launch: `git init && git add -A && git commit`, create GitHub repo, push, `git tag v1.0.0`, PyPI via build+twine.
- **task.md**: added Milestone 6 (all [x] except pre-publish placeholders).

## 2026-09-04 — Hardening audit + E2E + security closeout (Milestones 4–5)

- **Security/bug audits** (subagents): P0 confirmed — `validate --all` KeyError, PATCH `name` TypeError 500, import filename traversal, unbounded body DoS. Fixed: fs-scan for `--all`, `name` popped before field filter, basename + tar-type + empty guards, 25 MB cap + Content-Length validation, generic 500 + stderr log, tar `filter="data"`, restore timestamp-regex, purge skips non-timestamp dirs.
- **P1/P2 fixes**: scopes injectable global store (`set_global_store`, wired in `WebAppServer.__init__`); `sync_skill` NAME_RE/MAX_NAME validation; loader `malformed` flag; frontend `listSeq`/`detailSeq` race guards + scope-aware undo/restore; docs `--scope`/`--raw`/zip corrections (03-cli-surface) and rule-1 correction (08-web-ui).
- **smoke_store.py hermetic**: tmp-dir `fixture-skill` replaces external opencode path dependency.
- **E2E matrices green**: full CLI matrix (all commands + trash/templates/db, `--json`, error paths, exits 0/1/2); REST edge matrix 18/18 (traversal→400, empty→400, zip→400, bad-archive→400, oversize→400, long-query→400, history clamp, PATCH-name-ignored, static `..`→404); `node --check` JS_OK; UI serve 200s.
- **Reports**: `security_best_practices_report.md` (no criticals; H-1 install supply-chain, M-1 tar fallback, M-2 member allowlist, M-3 path disclosure) and `skills-manager-threat-model.md` v1.0 (A-1..A-4, B-1..B-5, T-1..T-10, R-1..R-5).
- **Ideas proposed** (task.md Milestone 5, all need ASK): native wrapper, live-preview editor, shortcut cheatsheet, pytest suite, CI, zip-import, tar-fallback refusal, link-warning→error.
- **Verified**: `py_compile` COMPILE_OK, both smokes PASS, `--help` OK, `list --scope agents --json` OK (`[]` in this env — no agent dirs present).
- **Note**: full browser click-through not re-run in this env (no browser tool); last verified 2026-08-14 zero-console-error pass stands; curl-based UI checks (index/Vue/static-jail) green.

## 2026-08-16 — Docs refresh: scopes / commandcode tracking (no code changes)

- **Confirmed live**: tracking the skills the `commandcode` CLI loads is already built in — `--scope agents` reads/writes `~/.agents/skills` directly (verified: lists the 4 live skills find-skills, karpathy-guidelines, kubernetes-skill, security-audit), and the web UI's scope switcher exposes the same **Agents** scope. No symlink created (would have risked the live dir); no code changes needed.
- **Docs were stale** (said 29 commands, no `--scope`, no `sync`/`scopes`/`tokens`/`install`, listed gui.py which is deleted). Refreshed: `docs/03-cli-surface.md` v0.2.0→v0.3.0 (40 invocable names, `--scope` flag, 4 scope-aware commands), `docs/02-modules.md` v0.2.0→v0.3.0 (added scopes.py/loader.py/tokens.py, removed gui.py), `docs/08-web-ui.md` v0.1.0→v0.2.0 (Scopes section, scope-aware API table), `AGENTS.md` v0.2.0→v0.3.0 (scope tracking in What-this-is), `docs/SESSION-CONTEXT.md` v0.1.0→v0.2.0 (scopes router rows, agent-scope gotcha, `--scope agents` in verification loop).
- **Verified**: `python3 -m py_compile skillsmgr/*.py smoke_*.py`, `python3 smoke_store.py`, `python3 smoke_web.py`, `python3 -m skillsmgr --help`, `python3 -m skillsmgr list --scope agents --json` — all pass.

## 2026-08-14 — Deep UI QA loop (agent-browser exploratory testing)

- **Method**: launched the web UI with a 6-skill corpus, attached a console error/warn tracker, and ran an iterative test loop (test → log → fix → re-test) covering every screen, action, modal, import/export, keyboard, theme, and responsive breakpoint (1280/900/640/400px).
- **CRITICAL BUG FOUND AND FIXED** (`webui/app.js` markdown renderer): `renderMarkdown()` referenced undefined `inTableSep` on every table row → `ReferenceError` thrown during any render of a skill body containing a table. Symptom: **completely blank page after reload** when a table skill was selected (Vue render crashed). Removed the dead `if (!inTableSep) {}` line.
- **BUG FOUND AND FIXED** (same renderer): tables rendered as **two separate `<table>` elements** (header row in one, data rows in another) because the separator row is skipped without closing the table. Added `inTable` state + `closeTable()` — header + body rows now render as one table.
- **BUG FOUND AND FIXED** (`webui/index.html`): skills list had **no empty state** for zero results (search no-match or Disabled filter) — bare empty `ul`. Added teaching empty states ("No matching skills", "No disabled skills", "No skills installed") with guidance text.
- **BUG FOUND AND FIXED** (`webui/index.html`): detail-pane empty state said "No skills installed" when a search/filter yielded zero results (misleading; skills existed). Now distinguishes `skills.length === 0 && !query` (truly empty store) from search/filter no-match ("Select a skill").
- **CLI BUG FOUND AND FIXED** (`cli.py:212`): `cmd_edit` checked `result.get("updated")` but `store.edit()` returns `{"name", "changed"}` — every successful edit printed "no changes for X" despite applying the change (history confirmed). Fixed to check `changed`; verified "updated" vs "no changes" behavior.
- **Verified working**: create (validation banner, full form, body via textarea), edit (pre-filled, partial update, compatibility/allowed-tools render), disable/enable, remove→trash→undo toast→restore, remove→purge, trash list/restore/empty-with-confirm, live search (name/description/body), filters, detail metadata + markdown (headings/lists/code/inline/bold/italic/links/quotes/table), validate (valid + empty), doctor, stats, history (skill filter + limit), templates (list + new), import archive (new + duplicate-skip), export (download lands in ~/Downloads), multipart folder upload (alpha/beta via API simulation), rebuild/resync index, Copy path (Clipboard API + execCommand fallback), theme toggle + localStorage persistence, `/` search focus, Esc menu/modal close, responsive stacking at 900px, compact topbar at 640px, no overflow at 400px. **Zero console errors across all flows post-fix.**
- **Re-test after fixes**: fresh browser session — page loads and reloads clean, table renders as one element, empty states correct, `python3 smoke_store.py` and `python3 smoke_web.py` both still ALL PASS.

## 2026-08-14 — Local web UI replaces GTK4 (Milestone 3 complete)

- **Decision**: abandoned the GTK4 GUI (toolkit fights: PyGObject `set_data` unsupported, GTK4/GTK3 Popover/`append` differences). Built a **local web UI** instead — same architecture as Jan / LM Studio / AnythingLLM / Open WebUI. User chose this direction explicitly.
- **Backend**: wrote `skillsmgr/webapp.py` — stdlib `ThreadingHTTPServer` bound to 127.0.0.1, JSON REST API over the Store public API, static file serving from `skillsmgr/webui/`. Hand-rolled `_parse_multipart` for webkitdirectory folder uploads (browser "Add from folder" → `Store.add` per SKILL.md).
- **Frontend**: wrote `skillsmgr/webui/` — Vue 3.5.13 vendored (`static/vendor/vue.global.prod.js`, no build step, works offline), `index.html` (all screens/modals), `styles.css` (design tokens, warm ivory + copper palette, authored dark theme), `app.js` (state, actions, hand-rolled XSS-safe markdown renderer, undo toasts).
- **CLI**: `webui` subcommand added (flags: `--host`, `--port`, `--no-browser`), `gui` kept as alias; `skillsmgr/gui.py` deleted; `cmd_gui` now calls `webapp.run`.
- **CLI bugs fixed** (found by reproducing before touching code): `cmd_export`/`cmd_backup` treated the `Path` return as a dict (`TypeError: 'PosixPath' object is not subscriptable`); `cmd_db_rebuild` used non-existent `result['skills']` key; `cmd_doctor` printed "database integrity check failed: ok" (guard now checks `!= "ok"`).
- **Tests**: wrote `smoke_web.py` — starts the server on an ephemeral port, hits every endpoint (static, CRUD, search, validate, toggle, stats/doctor/history, templates, export→import round-trip, trash/restore/purge, rebuild/resync, multipart folder upload, error paths). ALL WEB SMOKE TESTS PASSED.
- **Browser click-through (agent-browser 0.27 + Chrome)**: exercised create, detail view (real multi-line skill markdown: 333 elements rendered), live search, filters, disable/enable, remove+undo, trash/restore, validate (valid + 3-issue invalid skill), doctor, stats, history, templates, import (new + duplicate), export (download landed in ~/Downloads), theme toggle + persistence, 400px mobile viewport. **Zero console errors** across all flows.
- **BUG FOUND AND FIXED**: mobile topbar overflowed at 400px (`scrollWidth 458 > clientWidth 385`) — added `max-width: 640px` rules hiding brand text + stat pill, tightening padding/buttons. Verified no overflow after fix.
- **BUG FOUND AND FIXED**: webapp static route dropped `parts[2:]` (Vue file 404) — now joins all parts.
- **Docs**: wrote `docs/08-web-ui.md` (authoritative) and `docs/SESSION-CONTEXT.md` (fast re-anchor cache). Updated AGENTS.md v0.2.0 (locked constraints: web UI instead of GTK), docs/README.md, 02-modules v0.2.0, 03-cli-surface v0.2.0, 05-gui-plan marked SUPERSEDED.
- task.md Milestone 2+3 items all `[x]`.

## 2026-08-13 — Manage views (Milestone 2)

- Implemented the Manage section in `skillsmgr/gui.py` (handlers inserted after `_on_refresh_skills`, before `class SkillsManagerApp`), mirroring CLI command shapes via the Store public API only: `_on_validate_skill` (`Store.get` → `validate_skill(name, Path(record["path"]))`, catching `(OSError, ValueError)`; issues rendered via `getattr(issue, 'message', issue)`), `_on_doctor` (`Store.doctor`), `_on_stats` (`Store.stats` via `_format_dict`), `_on_history`/`_on_history_response` (GTK4 DropDown + GTK3 ComboBoxText over `["All skills"] + names` from `Store.list`, limit entry default 50, `int(limit_text)`/ValueError→50, empty → `_notify(self, "No history records.")`, rows `f"{record['at']}  {record['name']}  {record['action']}"`), `_on_trash` (`Store.trash_list`), `_on_purge_trash`/`_on_purge_trash_response` (confirm dialog, Cancel / `_RESPONSE_PURGE=2` → `Store.purge_trash`, `_notify` + `_reload_list()`), `_on_templates` (`list_templates(self._store.templates_dir)`; OSError → plain `_alert`, no `_log_store_error`), `_on_new_template`/`_on_new_template_response` (name entry + body TextView in ScrolledWindow, `create_template(..., body or None)`, empty name → `_alert(self, "Template name is required.")`, `(ValueError, FileExistsError)` → `_alert(self, str(exc))`), `_on_rebuild_index` (`Store.db_rebuild`), `_on_resync` (`Store.resync`, added/updated/removed counts + `_reload_list()`). Shared helpers: `_render_store_output` (single `set_text(f"{title}\n{'-' * len(title)}\n\n{text}")`), `_format_dict` (`@staticmethod`, recursive via `SkillsWindow._format_dict`, dicts indented +2, lists joined ", ").
- Pattern: PyGObject attrs attached to the dialog (`dialog._history_dropdown`, `dialog._template_body`, etc.), read via `getattr` in response handlers; response guard `response != Gtk.ResponseType.OK` → destroy + return (cancel path).
- Verified: `python3 -m py_compile skillsmgr/gui.py` — COMPILE_OK; `DISPLAY=:0 timeout 6 python3 -m skillsmgr gui` exited 124 with no traceback; `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `python3 -m skillsmgr --help` unchanged (no CLI regressions). task.md M2 item 6 `[x]`.

## 2026-08-13 — Search bar (Milestone 2)

- Implemented the search bar in `skillsmgr/gui.py`, mirroring CLI `search` behavior via the Store public API (`Store.search` at store.py:365 — case-insensitive LIKE over name/description/body with wildcard escaping, same row shape as `Store.list`).
- `_search_entry.connect("search-changed", self._on_search_changed)` added at entry build (gui.py:203-206); `_on_search_changed` added after `_reload_list` (gui.py:366).
- Design decisions: no debounce — direct signal connection (fast local SQLite LIKE; KISS). Empty/whitespace term → `_reload_list()` (full list). Otherwise: clear list + selection, reset `_text_buffer` to "Select a skill to view its SKILL.md content.", wrap `Store.search(term)` in `try/except StoreError` → `_log_store_error` + `_alert(self, f"Could not search skills: {exc}")` with "Could not search skills." placeholder (no tracebacks, window stays usable); no matches → "no matching skills" placeholder.
- Verified: `python3 -m py_compile skillsmgr/gui.py` — COMPILE_OK; `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `python3 -m skillsmgr --help` unchanged (no CLI regressions); `DISPLAY=:0 timeout 6 python3 -m skillsmgr gui` exited 124 with no traceback (search bar + live filtering run until timeout). task.md M2 item 5 `[x]`.

## 2026-08-13 — Skill actions (Milestone 2)

- Implemented all action methods in `skillsmgr/gui.py` (methods before `SkillsManagerApp`), mirroring CLI command shapes: `_on_new_skill`/`_on_new_skill_response` (create dialog → `Store.create`), `_on_add_skill`/`_on_add_skill_picked`/`_do_add_skill` (file picker → `Store.add`), `_on_edit_skill`/`_on_edit_skill_response` (edit dialog → `Store.edit`, partial semantics, only non-empty fields sent), `_on_disable_skill`/`_on_enable_skill` (`Store.disable`/`enable`), `_on_remove_skill`/`_on_remove_response` (Cancel / `_RESPONSE_TRASH=1` / `_RESPONSE_PURGE=2` → `Store.remove`), `_on_restore_skill`/`_on_restore_response` (`Store.restore`), `_on_refresh_skills` (`_reload_list`). Menu wired via `Gtk.MenuButton` + `Gtk.Popover` + `_add_menu_item` (8 items: New/Add/Edit/Disable/Enable/Remove/Restore/Refresh).
- **BUG FOUND (PyGObject limitation)**: `set_data`/`get_data` raise `RuntimeError: Data access methods are unsupported. Use normal Python attributes instead`. Converted all 19 sites (14 edit ops) to Python attributes: `obj._attr = value` / `getattr(obj, "_attr", None)`. Sites covered: dialog rows, detail-view selection (GTK4 `SingleSelection` + GTK3 `ListBox` `set_data`), response handlers (`_current_name`, `_dialog`, `_current_item`, `_purge` flags).
- **BUG FOUND (GTK4 API)**: `Gtk.Popover` has no `append`; `_content_add(popover, menu_box)` raised `AttributeError: 'Popover' object has no attribute 'append'`. Fixed `_content_add` to prefer `set_child` when the container has it (Popover), else GTK4 `append` (Box/dialog content areas), else GTK3 `pack_start`.
- Verified: `python3 -m py_compile skillsmgr/gui.py` — COMPILE_OK; `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `python3 -m skillsmgr --help` unchanged (no CLI regressions); `DISPLAY=:0 timeout 6 python3 -m skillsmgr gui` exited 124 with no traceback (window + menu popover launch until timeout). task.md M2 item 4 `[x]`.

## 2026-08-13 — Skill detail view (Milestone 2)

- Implemented the detail view in `skillsmgr/gui.py`, mirroring CLI `view` (`cli.py:172-192`): right pane renders 8 metadata lines (`name`, `status` with `"disabled" if record["disabled"] else "active"` mapping, `category`, `license`, `version`, `description`, `path`, `updated` from `updated_at`; each `or "-"`), a blank line, then the SKILL.md body — all fetched via `Store.get(name)`.
- GTK4 branch: `Gtk.SingleSelection` `"selection-changed"` → `_on_selection_changed` (guards `self._text_buffer is None`, uses `get_selected_item()` → `_SkillItem.name`); GTK3 branch: `Gtk.ListBox` `"row-selected"` → `_on_row_selected` via `row.get_data("skill-name")` (name attached with `box.set_data` at insert time). No selection → placeholder "Select a skill to view its SKILL.md content."
- `_render_detail(name)` wraps `Store.get` in `try/except StoreError` → `_log_store_error(exc)` + `_alert(self, f"Could not load skill '{name}': {exc}")` (no tracebacks; satisfies M2 item 7 constraint early).
- Verified: `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `python3 -m skillsmgr --help` unchanged (no CLI regressions); `timeout 6 python3 -m skillsmgr gui` exited 124 (GUI + detail pane launch on DISPLAY=:0 until timeout). task.md M2 item 3 `[x]`.

## 2026-08-13 — Main window skill list (Milestone 2)

- Implemented the skill list in `skillsmgr/gui.py`, mirroring CLI `list` output: columns NAME/STATUS/CATEGORY/DESCRIPTION via `Store.list()` (active-only, ORDER BY name), rows = bold name + `status · category — description` detail line (description truncated at 60 chars, same `_truncate` semantics as cli.py:38-41).
- GTK4 branch: `Gio.ListStore.new(_SkillItem)` + `Gtk.SingleSelection` + `Gtk.SignalListItemFactory` (`_setup_row`/`_bind_row`) + `Gtk.ListView`; `_SkillItem` is a GObject with str properties (name/status/category/description) and `from_row()` mapping (`"disabled" if row["disabled"] else "active"`, `category or "-"`). `self._model`/`self._selection` kept for the detail view.
- GTK3 fallback: `Gtk.ListBox` with per-row vertical Boxes (`pack_start`, `list_box.insert` — 3.24-safe), same row layout.
- `__init__` now loads the list under `try/except StoreError`: error → `_log_store_error` + `_alert` dialog + "Could not load skill list." label; empty store → "no skills installed" label; `_show(self)` at end of `__init__` (show_all only on GTK3).
- Verified: `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `python3 -m skillsmgr --help` unchanged (no CLI regressions); `timeout 6 python3 -m skillsmgr gui` exited 124 (list renders on DISPLAY=:0 until timeout). task.md M2 item 2 `[x]`.

## 2026-08-13 — GTK4 GUI scaffold (Milestone 2)

- Wrote `skillsmgr/gui.py` (scaffold): GTK4 4.14 → GTK3 3.24 fallback, `SkillsManagerApp`, `SkillsWindow` (HeaderBar with search entry + actions menu, Paned layout 900x600), `_alert` (AlertDialog GTK4 / MessageDialog GTK3), `_log_store_error`, `run()` entry point.
- Wired `gui` subcommand in `skillsmgr/cli.py`: `cmd_gui` (lazy import of the gui module; `ImportError`/`ValueError`/`RuntimeError` → clean `_err` + EXIT_ERROR) plus `gui` subparser; parent `--data-dir` flows through `_make_store`.
- Verified: `python3 -m skillsmgr --help` lists `gui    launch the desktop GUI (GTK4)` with all other commands unchanged (no CLI regressions); `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; `timeout 6 python3 -m skillsmgr gui` exited 124 (GUI launched on DISPLAY=:0 and ran until timeout — GTK init OK).

## 2026-08-13 — Docs layer (Milestone 1)

- Created `docs/` directory; wrote `task.md` (v0.2.0), `AGENTS.md` (v0.1.0), `docs/README.md` (v0.1.0).
- Wrote `docs/01-architecture.md` (v0.1.0): data model, data-dir layout, FS vs SQLite roles.
- Wrote `docs/02-modules.md` (v0.1.0): module inventory, constants, search scoring, exit codes.
- **FACT CORRECTION**: command count corrected from "25" to "29 commands (22 top-level + 7 subcommands) plus 2 aliases (`ls`, `rm`) — 31 invocable names". Fixed in `task.md` and `docs/02-modules.md` line 17. `docs/03-cli-surface.md` records the stale-fact note.
- Wrote `docs/03-cli-surface.md` (v0.1.0): full command/flag/exit-code surface.
- Wrote `docs/04-store-api.md` (v0.1.0): `Store` public API + SQLite schema, verified against `store.py`.
- Toolkit verification: GTK4 4.14 (PyGObject 3.48.2) present; GTK3 3.24 fallback; Wayland session; PySide6/PyQt6/wx absent → GTK confirmed.
- Wrote `docs/05-gui-plan.md` (v0.1.0): GUI blueprint, CLI→view mapping, Milestone 3 iteration loop.
- Wrote `docs/07-context-strategy.md` (v0.1.0): hot/warm/cold loading model.
- Wrote this file (v0.1.0).
- **QA PASSED** (Milestone 1 close-out): `python3 -m skillsmgr --help` runs with no regressions; `python3 smoke_store.py` — ALL STORE SMOKE TESTS PASSED; all 8 `docs/*.md` exist with H1 + version line; every `@docs/` pointer in the repo resolves (no missing files); HADS markers valid. task.md Milestone 1 fully `[x]`.

## Milestone 2 — GTK4 GUI (pending)

- [x] Scaffold `skillsmgr/gui.py` + `__main__` integration
- [ ] Main window, detail view, actions, search, manage, dialogs
- [ ] Launch check on DISPLAY=:0

## Milestone 3 — Zero-error loop (pending)

- [ ] `--help` no-regression, `smoke_store.py` passes
- [ ] Exercise every GUI action; log each iteration here
- [ ] Loop until zero errors/bugs