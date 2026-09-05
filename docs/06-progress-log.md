# Progress Log — Skills Manager

**Version 0.1.0**

**AI manifest**: Dated, append-only record of changes, decisions, and bugs for skills-manager. Read before/after every session (docs/README.md reading order). Newest entry on top. Facts flagged stale here are corrected in the owning doc.

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