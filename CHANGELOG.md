# Changelog

All notable changes to this project are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- Archive/trash safety hardening: forced imports cannot turn invalid names into
  destructive paths; tar members are preflighted in a private temporary tree;
  duplicate, traversal, unexpected-layout, symlink, hard-link, FIFO, and other
  special members are rejected; tar extraction uses `data_filter` when
  available and a guarded regular-file/directory fallback otherwise; malformed
  trash entries are ignored consistently.
- Spec-lint+ (`validator.py`): `description_score()` (use-context + filler detection), description warnings (missing "Use … when …", vague filler), body token warning (`MAX_BODY_TOKENS=5000`, progressive-disclosure guidance), `scripts/`/`references/`/`assets/` layout check for dangling mentions.
- Cross-scope dedup: `scopes.find_duplicates()` (same-name + descriptions-differ flag), surfaced in `doctor --scope all`, `/api/doctor?scope=all`, and the doctor modal with Sync… converge buttons.
- Token budget view (verified complete): `tokens --scope all` aggregate + `largest`, `/api/stats?window=` + `/api/tokens`, frontend budget bar with window selector.
- Open-source launch kit: `README.md`, `LICENSE` (MIT), `pyproject.toml`, CI workflow, issue/PR templates, `SECURITY.md`, `ROADMAP.md`.

## [1.0.0] — 2026-09-04

### Added

- CLI (`skills-mgr`): 26 commands + `trash`/`templates`/`db` subcommands; `--json` output; exit codes 0/1/2/130.
- Agent scopes: `global`, `claude-code`, `codex`, `cursor`, `opencode`, `gemini`, `commandcode`, `agents`, merged `all` view; `sync` between scopes; scope-aware `list/view/search/doctor/stats/tokens/install`.
- Local web UI (stdlib backend, vendored Vue 3, loopback-only): CRUD, live search, trash with undo, validate/doctor/stats/history, templates, import/export, sync modal, dark theme.
- `tokens`: per-skill/scope token and context-window estimates (tiktoken when available, chars/4 fallback).
- `install`: dry-run-first wrapper over the `skills` npm package with allowlist validation.
- Filesystem-as-source-of-truth model with rebuildable SQLite index (`db rebuild`/`resync`).

### Fixed

- `validate --all` crash, PATCH `name` 500, import traversal/type/empty guards, 25 MB body caps, generic 500s, tar `filter="data"`, restore/purge timestamp handling, frontend race guards, scope-aware undo/restore.

### Security

- No critical findings. See `security_best_practices_report.md` and `skills-manager-threat-model.md`.
