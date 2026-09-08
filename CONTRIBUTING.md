# Contributing to skills-manager

Thanks for considering a contribution. This project is intentionally small and dependency-free — please read this before opening a PR.

## Ways to contribute

- Bug reports with reproduction steps (data-dir layout, command, expected vs actual).
- Skill-scope support for new agents (new entry in `skillsmgr/scopes.py` + docs).
- Validation rules aligned with the [Agent Skills spec](https://agentskills.io/specification).
- Frontend polish in `skillsmgr/webui/` (no build step, no new runtime deps).
- Tests: `tests/` uses stdlib `unittest` only (no third-party deps, no network); smoke scripts stay as the E2E layer.

## Locked constraints (non-negotiable without maintainer approval)

1. Filesystem stays the source of truth; SQLite is a rebuildable index only.
2. SQLite schema / `SCHEMA_VERSION` unchanged.
3. CLI stays stdlib-only.
4. Web UI: stdlib backend, no build step, no new runtime deps, Vue vendored, binds `127.0.0.1`.
5. **No new CLI commands or Store methods without approval** — open an issue first.

## Development setup

```bash
git clone https://github.com/udayvarmora07/skills-manager
cd skills-manager
python3 -m unittest discover -s tests   # no extra deps needed
```

Isolated throwaway runs (never touch your real skills):

```bash
export SKILLS_MANAGER_DATA=$(mktemp -d)
python3 -m skillsmgr init
python3 -m skillsmgr create demo -d "Demo skill"
python3 -m skillsmgr webui --no-browser
```

## Checks (all must pass)

```bash
python3 -m py_compile skillsmgr/*.py smoke_*.py tests/*.py check_complexity.py check_docs.py
python3 check_complexity.py
python3 check_docs.py
python3 check_package_data.py   # reports UNAVAILABLE when optional build tooling is absent
python3 -m unittest discover -s tests
python3 smoke_store.py
python3 smoke_web.py
node --check skillsmgr/webui/app.js   # if node is available
```

## Style

- Surgical changes: touch only what the task needs; no drive-by refactors.
- Errors surface as clean messages (`StoreError`/`SkillNotFound`), never raw tracebacks to users.
- Frontend: never render raw HTML from skill bodies (XSS) — escape first.
- Update the owning doc under `docs/` when behavior changes, plus `task.md` and `docs/06-progress-log.md` for larger work.

## PR process

1. Open an issue first for anything beyond a trivial fix.
2. Keep PRs focused; include the verification output (compile + unittest + smokes).
3. Update `CHANGELOG.md` under `Unreleased`.
