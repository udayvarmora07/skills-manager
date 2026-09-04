# PLAN — skills-manager (new-chat starter)

> Copy everything below the line into a fresh chat. It carries full context so the
> agent can start executing `TODO.md` immediately.

---

# Continue skills-manager — OSS publish + v1.1

## Repo
- Path: `/home/uday-varmora/skills-manager` (CWD in VS Code)
- `skills-mgr`: Python stdlib-only CLI + local web UI (stdlib `ThreadingHTTPServer`
  on `127.0.0.1:8765`, Vue 3.5.13 vendored, no build step)
- Data model: filesystem is source of truth (`<data>/skills/<name>/SKILL.md`,
  disabled = `SKILL.md.disabled`); SQLite at
  `<data>/skills-manager/skills-manager.db` is a rebuildable index only,
  `SCHEMA_VERSION = "1"`. Never hand-edit the DB.
- Key files: `skillsmgr/store.py`, `cli.py`, `webapp.py`, `scopes.py`,
  `loader.py`, `validator.py`, `frontmatter.py`, `tokens.py`, `search.py`,
  `webui/app.js` + `index.html` + `styles.css`
- Docs: `AGENTS.md` (hot cache — read first), `docs/SESSION-CONTEXT.md`
  (fast re-anchor), `docs/01-architecture.md`, `02-modules.md`,
  `03-cli-surface.md`, `04-store-api.md`, `08-web-ui.md`, `task.md`
  (checklist, Milestones 1–4 + 6 done), `docs/06-progress-log.md`
- Toolchain: `python3 -m skillsmgr`, `python3 smoke_store.py`,
  `python3 smoke_web.py`, `python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py`
- Locked constraints (ASK before deviating):
  1) FS is source of truth 2) SQLite schema unchanged 3) CLI stdlib-only
  4) web UI stdlib backend, no new runtime deps, Vue vendored, bind 127.0.0.1
  5) no new CLI commands / Store methods without approval

## Status: launch kit COMPLETE, not yet published
- All todos done (10/10 in session table). Last verification: compile OK,
  38 stdlib-`unittest` OK (`python3 -m unittest discover -s tests`),
  both smokes PASS, `node --check webui/app.js` OK, `--help` OK,
  `list --scope agents --json` OK.
- Real bug found + fixed in this cycle: `Store.restore()` prefix collision
  (`demo` grabbed `demo-x`); now exact `_strip_trash_suffix` match.
  Reports: `security_best_practices_report.md` (no criticals),
  `skills-manager-threat-model.md` v1.0 (T-1…T-10, R-1…R-5).

## Critical environment facts (do not re-learn)
- **No network for pip** (PEP 668 + offline). Tests are stdlib `unittest` ONLY —
  `tests/test_store.py` (22), `tests/test_webapp.py` (3, `serve_forever` thread,
  `shutdown`+`join`+`server_close` in teardown), `tests/test_web_scopes.py` (13,
  hermetic `HOME`+`SKILLS_MANAGER_DATA` override). Never reintroduce pytest.
- `Store()` requires `store.init_db()` after construction in tests.
- `list()` takes NO args; disabled rows carry `disabled` column (1/0).
- `rank_results` returns `list[tuple[dict, int]]`; loader sets `malformed` flag;
  validator `Issue` has `level/message/key`; `dump_frontmatter` takes a dict only.
- Smoke tests seed their own tmp dirs; `smoke_web.py` uses an ephemeral port.

## Work order (see TODO.md)
1. **Pre-publish blockers first**: replace `YOUR-USER` (`README.md` ×3,
   `pyproject.toml` ×5, `CONTRIBUTING.md` ×1) and `security@example.com`
   (`SECURITY.md`); re-run full verification; `git init`, first commit,
   `git tag v1.0.0`, push, PyPI (`python3 -m build && twine upload dist/*`),
   confirm CI green. Ask me for the GitHub username + security email if unsure —
   do not invent them.
2. Then v1.1 items top-down. Anything touching locked constraint 5
   (new command/flag/Store method, behavior change) → open a GitHub issue first
   and wait for my approval before coding.
3. After each change: targeted verification (compile + unittest + both smokes),
   then update `task.md` + `docs/06-progress-log.md` + `CHANGELOG.md`.

## Skills
Use `karpathy-guidelines` (surgical changes, verify with tests),
`security-best-practices`, `security-threat-model` when touching intake/auth.
`find-skills` only if a capability is missing, then remove it after.

Start by confirming the pre-publish placeholders are still present
(`grep -rn YOUR-USER README.md pyproject.toml CONTRIBUTING.md`),
then ask me for the real username + security email.
