# Roadmap

Public direction for `skills-manager`. Items move from Proposed → Accepted → Building → Shipped. Anything touching the [locked constraints](README.md#contributing) needs maintainer approval first.

## Next (v1.1)

- [ ] **Spec-lint+**: name regex incl. no-consecutive-hyphens, description keyword/use-context scoring, body length + token warnings, `scripts/`/`references/` layout checks — mapped to the official [best practices](https://agentskills.io/skill-creation/best-practices).
- [ ] **Cross-scope dedup**: detect same-name/similar-description skills across agents, diff, one-command converge.
- [ ] **Token budget view**: per-skill/per-scope startup footprint in CLI + UI.
- [ ] **Rollback**: snapshot on edit/sync (`history` exists) + `restore --snapshot`.
- [ ] **One-command migration**: full-library export/import (skills + trash + templates) for new machines.

## Then (v1.2+)

- [ ] **Registry bridge**: browse `skills.sh` → install into chosen scope; publish local skills upstream.
- [ ] **Eval harness**: per-skill before/after prompt tests (per official evaluating-skills guidance).
- [ ] **VS Code extension**: thin wrapper over the existing REST API.
- [ ] **Team sharing**: signed bundles, internal index, draft → review → publish stages.
- [ ] **Refuse unsafe tar fallback** on Python < 3.12 (threat-model R-1).
- [ ] **Zip-import support** (`import` is tar-only today).

## Ambitious (exploring)

- Skill recommendations mined from shell history / repeated sessions.
- Skill-vs-MCP-vs-subagent guidance; future auto-convert.
- `pywebview` desktop wrapper around the existing web UI.

## Non-goals

- Becoming a skill *library* (we manage; registries publish).
- Remote hosting / multi-user server (local-first forever).
- New runtime dependencies (stdlib-only is a feature).
