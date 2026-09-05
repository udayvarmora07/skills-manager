# Task Checklist — Skills Manager

**Version 0.3.0**

**AI manifest**: Single source of truth for remaining work on skills-manager. Update after every step. Notation: `[ ]` unstarted, `[/]` in progress, `[x]` done. Milestones: (1) docs layer, (2) GUI, (3) zero-error iteration loop.

## Milestone 1 — Docs layer (2026-08-13)

- [x] Confirm repo layout and module inventory
- [x] Verify CLI command surface (29 commands + 2 aliases, 31 invocable names) via grep of `skillsmgr/cli.py`
- [x] Verify Store public API via grep of `skillsmgr/store.py`
- [x] Verify GUI toolkit availability (GTK4 4.14 selected, GTK3 3.24 fallback)
- [x] Capture AGENTS.md research takeaways (Red Hat article + context-engineering / agent-legibility skills)
- [x] Create `docs/` directory
- [x] Write `task.md` (this file)
- [x] Write `AGENTS.md` (hot cache, router, <=150 lines)
- [x] Write `docs/README.md` (docs index, hot/warm/cold map)
- [x] Write `docs/01-architecture.md` (data model, data-dir layout)
- [x] Write `docs/02-modules.md` (module-by-module facts)
- [x] Write `docs/03-cli-surface.md` (command table, exit codes)
- [x] Write `docs/04-store-api.md` (public API + SQLite schema)
- [x] Write `docs/06-progress-log.md` (dated log entries)
- [x] Write `docs/07-context-strategy.md` (hot/warm/cold model for sessions)
- [x] QA docs: every @docs/ pointer resolves, HADS format valid, no stale facts

## Milestone 2 — GUI (local web UI, replaced GTK4 on 2026-08-14)

- [x] Scaffold `skillsmgr/gui.py` + `__main__` integration (GTK4, later deleted)
- [x] Main window: skill list (mirror `list` output, status columns)
- [x] Detail view: view skill metadata + body (mirror `view`)
- [x] Actions: create, add, edit, disable, enable, remove (trash/purge), restore
- [x] Search bar (mirror `search` scoring, live filtering)
- [x] Manage: validate, doctor, stats, history, trash views, templates list/new, db rebuild/resync
- [x] Import/export/backup/restore (import modal + export download + folder upload)
- [x] Error paths: StoreError/SkillNotFound surfaced as dialogs/toasts, never tracebacks
- [x] Launch check: web UI serves on 127.0.0.1 and opens in browser

## Milestone 3 — Zero-error iteration loop

- [x] Run `python3 -m skillsmgr --help` — no CLI regressions
- [x] Run `python3 smoke_store.py` — passes
- [x] Run `python3 smoke_web.py` — passes (all REST endpoints)
- [x] Browser click-through: create/edit/disable/remove+undo/restore/trash/validate/doctor/stats/history/templates/import/export/theme — zero console errors
- [x] Mobile 400px viewport: no topbar overflow
- [x] Fix 4 CLI bugs (export/backup/db rebuild/doctor) found by reproduction
## Milestone 4 — Security + hardening audit (2026-09-04)

- [x] Security audit + bug audit via subagents (P0/P1/P2 triaged with evidence)
- [x] P0 fixes: `validate --all` fs-scan, PATCH name ignored, import traversal/type/empty guards, 25 MB body + Content-Length caps, generic 500 + stderr log, tar `filter="data"`, restore timestamp-regex, purge skips non-timestamp dirs
- [x] P1/P2 fixes: scopes injectable global store (`set_global_store`, wired in `WebAppServer`), `sync_skill` name validation, loader `malformed` flag, frontend `listSeq`/`detailSeq` race guards + scope-aware undo/restore, docs `--scope`/`--raw`/zip corrections, web-UI rule-1 correction
- [x] `smoke_store.py` made hermetic (tmp fixture replaces external opencode path)
- [x] Full CLI E2E matrix on temp data dir (create/list/view/raw/edit/search/limit/disable/enable/validate/stats/doctor/history/export/remove/trash/restore/purge/templates/db/sync/scopes/tokens/install-dry-run + error paths; exit codes 0/1/2 verified)
- [x] Full REST edge matrix (traversal→400, empty→400, zip→400, bad-archive→400, oversize→400, long-query→400, history clamp, PATCH-name-ignored, disable/enable, static `..`→404, unknown→404)
- [x] `node --check` on `webui/app.js`; UI serve check (index + vendored Vue 200)
- [x] `security_best_practices_report.md` (no criticals; H-1 supply-chain note, M-1 tar-fallback, M-2 member allowlist, M-3 path disclosure)
- [x] `skills-manager-threat-model.md` v1.0 (assets A-1..A-4, boundaries B-1..B-5, paths T-1..T-10, risks R-1..R-5)

## Milestone 6 — OSS launch kit (2026-09-05)

- [x] Packaging: `pyproject.toml` (`skills-manager`, `requires-python >=3.10`, `skills-mgr` entry, stdlib-only, no dev deps), `.gitignore`, `LICENSE` (MIT)
- [x] Docs: `README.md` (badges, quickstart, scopes table, web UI, data model), `CONTRIBUTING.md` (stdlib-unittest, locked constraints), `SECURITY.md` (72h ack / 14d fix, localhost scope notes), `CHANGELOG.md` (Keep a Changelog, Unreleased + 1.0.0), `ROADMAP.md` (v1.1 / v1.2+ / non-goals)
- [x] Reports: `security_best_practices_report.md`, `skills-manager-threat-model.md` (T-1…T-10, R-1…R-5)
- [x] Tests: `tests/test_store.py` (22), `tests/test_webapp.py` (3, serve_forever thread + shutdown/join/close), `tests/test_web_scopes.py` (13, hermetic HOME+DATA override) — 38 total, all OK via `python3 -m unittest discover -s tests`
- [x] CI: `.github/workflows/ci.yml` (3.10/3.11/3.12, py_compile + unittest + both smokes + node --check), bug/feature templates, PR template
- [x] Fixes in this pass: test `_skill_body` helper (dump_frontmatter takes dict only, body appended separately); real `Store.restore()` prefix-collision bug (now `_strip_trash_suffix(p.name) == name`); README cursor path (`~/.cursor/skills-cursor`); pytest→unittest everywhere (offline env)
- [x] Verified: compile OK, 38 unittest OK, both smokes pass, `node --check` OK, `--help` OK, `--scope agents` OK (empty — no ~/.agents on this box)
- [x] Published: `udayvarmora07/skills-manager` created via `gh`, `main` + `v1.0.0` pushed, CI green (run 33914953774); PyPI name `skills-manager` confirmed free, `dist/` built (sdist+wheel) — upload blocked pending PyPI API token (`/tmp/buildenv/bin/python -m twine upload dist/*`)

## Milestone 7 — v1.1 spec-lint+ (in progress, 2026-09-05)

- [x] Spec-lint+ in `validator.py` (no new commands/Store methods): name regex already rejects `--` (`^[a-z0-9]+(-[a-z0-9]+)*$`, verified); `description_score()` (use-context detection + vague-filler hits); description warnings (missing use-context, filler words); body token warning (>5000 tokens, progressive-disclosure guidance); `scripts/`/`references/`/`assets/` layout check (dangling mentions)
- [x] Tests: 5 new `unittest` cases (43 total OK) + `smoke_store.py` spec-lint section
- [x] Cross-scope dedup (same-name detect + descriptions-differ flag + converge via existing sync): `scopes.find_duplicates()` read-only over `list_all()`; surfaced in `doctor --scope all` (text + `duplicates` JSON key), `/api/doctor?scope=all` (`duplicates` + `scopes` keys), doctor modal section with Sync… converge buttons; 4 hermetic tests (47 total OK) + `smoke_web.py` shape assertion
- [x] Token budget view in CLI + UI (verified already complete, no new code needed): `tokens --scope all` aggregate (`total/avg/max`, `largest[]`, `pct_window`), `/api/stats?window=` (`all_tokens/all_avg/all_pct`, top-5 `largest`), `/api/tokens`, frontend budget bar + window selector + per-row tokens + sync-mirror cost hint
- [x] Rollback snapshots + one-command migration (constraint-5 ASK → issues #1 + #2 opened via `gh`, no code until approved)

## Milestone 5 — Proposed ideas (approved via plan; implemented 2026-09-05)

- [x] Native window wrapper → DEFERRED; shipped zero-dep `assets/skills-manager.desktop` launcher instead (browser-first is the accepted local pattern; wrapper would violate constraint 4)
- [x] Skill-body editor with live markdown preview (Write/Preview tabs, XSS-safe `renderMarkdown`)
- [x] Keyboard-shortcut cheatsheet modal (`?` key; `/` + `Esc` documented)
- [x] Real pytest suite → DONE differently: 51 stdlib `unittest` + CI (offline env forbids pip/pytest)
- [x] CI workflow → DONE: `.github/workflows/ci.yml` green on 3.10/3.11/3.12
- [x] Zip-import support (stdlib `zipfile`, magic-byte detection, traversal guards; manifest-less archives scan bare `skills/`)
- [x] Tar-fallback allowlist on Python < 3.12 (threat-model R-1: per-member guards, NOT refusal — refusal would break supported 3.10/3.11)
- [x] Out-of-root link escapes → validation error (threat-model R-4; missing-file stays a warning)
