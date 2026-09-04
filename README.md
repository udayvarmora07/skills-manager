# skills-manager

**The local control plane for your AI coding-agent skills.** Create, organize, sync, back up, and quality-check `SKILL.md` skills across every agent you use — from one CLI and one local web UI.

[![CI](https://github.com/udayvarmora07/skills-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/udayvarmora07/skills-manager/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/skills-manager.svg)](https://pypi.org/project/skills-manager/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](pyproject.toml)

> `skills-manager` on GitHub: `udayvarmora07/skills-manager`; on PyPI: `skills-manager` (`skills-mgr` entry point).

## Why this exists

The [Agent Skills](https://agentskills.io) format (`SKILL.md`) is now an open standard supported by Claude Code, Cursor, Gemini CLI, OpenCode, Copilot/VS Code, Goose, Amp, and more. The ecosystem has **skill libraries** ([vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)), **installers** ([skills.sh](https://skills.sh)), and a **spec** — but nobody owns the *management* problem:

- The same skill copy-pasted into `~/.claude/skills`, `~/.codex/skills`, Cursor dirs… edits diverge.
- Vague descriptions cause false activation or misses; oversized bodies eat context.
- No versioning, no safe update/rollback, no backup story, no cross-tool view.

`skills-manager` fills that gap: one store, every scope, full lifecycle.

| | skills-manager | `skills.sh` / `npx skills add` | skill libraries |
|---|---|---|---|
| Install remote skills | ✅ (via `install`) | ✅ | — (source) |
| Create / edit / validate locally | ✅ | — | — |
| Manage across **all** your agents | ✅ (`--scope all`) | single-target | — |
| Sync + dedup between agents | ✅ | — | — |
| Version history + trash/rollback | ✅ | — | — |
| Token-footprint budgeting | ✅ (`tokens`) | — | — |
| Local web UI | ✅ | — | — |

## Install

Requires Python ≥ 3.10. The runtime is **stdlib-only** — no dependencies.

```bash
pipx install skills-manager        # recommended (isolated)
# or
pip install skills-manager
```

Run without installing:

```bash
git clone https://github.com/udayvarmora07/skills-manager
cd skills-manager
python3 -m skillsmgr --help
```

## Quickstart

```bash
# 1. See everything you have, everywhere
skills-mgr list --scope all

# 2. Create a skill once…
skills-mgr create my-workflow -d "Deploys our staging stack. Use when shipping to staging."

# 3. …sync it to every agent you use
skills-mgr sync my-workflow

# 4. Or manage it visually (localhost only, no build step, works offline)
skills-mgr webui
```

More:

```bash
skills-mgr search "deploy" --scope all   # scored search across agents
skills-mgr tokens --scope all            # context-footprint budgeting
skills-mgr validate --all                # spec lint incl. description/body guidance
skills-mgr export                        # timestamped backup tarball
skills-mgr install vercel-labs/agent-skills --dry-run   # preview remote install
```

## Agent scopes

One command surface, per-agent directories underneath:

| Scope | Directory |
|---|---|
| `global` (default) | manager store (`~/.local/share/skills-manager/skills/`) |
| `claude-code` | `~/.claude/skills` |
| `codex` | `~/.codex/skills` |
| `cursor` | `~/.cursor/skills-cursor` |
| `opencode` | `~/.config/opencode/skills` |
| `gemini` | `~/.gemini/skills` |
| `commandcode` | `~/.commandcode/skills` |
| `agents` | `~/.agents/skills` |
| `all` | merged read-only view |

`list`, `view`, `search`, `doctor`, `stats` accept `--scope`; `sync` copies between scopes; `tokens`/`install` have their own scope semantics. Agent-scope writes go straight to the agent dir (no DB) — disable renames `SKILL.md` ⇄ `SKILL.md.disabled` in place, which Claude Code and Command Code both respect.

## Web UI

```bash
skills-mgr webui              # http://127.0.0.1:8765, opens browser
skills-mgr webui --no-browser # server only
skills-mgr webui --port 9000  # custom port
```

Stdlib `ThreadingHTTPServer` backend + vendored Vue 3 (no npm, no CDN, works offline). Scope switcher, live search, trash with undo, validate/doctor/stats/history, templates, import/export, sync modal. Binds loopback only — never expose it; there is no auth (see [Threat model](skills-manager-threat-model.md)).

## Data model

- **Filesystem is the source of truth**: `<data>/skills/<name>/SKILL.md`.
- **SQLite is a rebuildable index only** (`db rebuild` / `db resync` repair any drift; never hand-edit it).
- Data dir: `$SKILLS_MANAGER_DATA` → `$XDG_DATA_HOME` → `~/.local/share`, then `/skills-manager`.

## CLI reference

26 commands + `trash`/`templates`/`db` subcommands + `ls`/`rm`/`gui` aliases. Exit codes: `0` ok · `1` error · `2` usage · `130` interrupt. `--json` on data commands.

Full surface: [`docs/03-cli-surface.md`](docs/03-cli-surface.md).

## Contributing

PRs welcome — start with [`CONTRIBUTING.md`](CONTRIBUTING.md). Locked constraints for any change:

1. Filesystem stays the source of truth.
2. SQLite schema unchanged.
3. CLI stays stdlib-only.
4. Web UI: stdlib backend, no build step, no new runtime deps, loopback bind.
5. No new CLI commands or Store methods without maintainer approval — open an issue first.

## Security

See [`SECURITY.md`](SECURITY.md) for disclosure policy. Design notes: [`security_best_practices_report.md`](security_best_practices_report.md), [`skills-manager-threat-model.md`](skills-manager-threat-model.md).

## Roadmap

Where this is going: [`ROADMAP.md`](ROADMAP.md) (spec-lint+, cross-scope dedup, registry bridge, eval harness, VS Code extension…).

## License

MIT — see [LICENSE](LICENSE).
