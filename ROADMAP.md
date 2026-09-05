# Roadmap

Public direction for `skills-manager`. Items move from Proposed → Accepted → Building → Shipped. Anything touching the [locked constraints](README.md#contributing) needs maintainer approval first.

## Next (v1.1)

- [x] **Spec-lint+** (shipped 2026-09-05): name regex rejects `--`; `description_score()` use-context/filler scoring + warnings; body line + token (>5000) warnings; `scripts/`/`references/`/`assets/` layout checks — mapped to the official [best practices](https://agentskills.io/skill-creation/best-practices).
- [x] **Cross-scope dedup**: same-name skills across scopes detected (`doctor --scope all`, doctor modal), diff via descriptions-differ flag, converge with existing `sync`.
- [x] **Token budget view**: per-skill/per-scope startup footprint in CLI (`tokens --scope all`) + UI (budget bar, `?window=` selector).
- [ ] **Rollback**: snapshot on edit/sync (`history` exists) + `restore --snapshot`.
- [ ] **One-command migration**: full-library export/import (skills + trash + templates) for new machines.
- [x] **Zip-import support** (shipped 2026-09-05 as part of M5): `.zip` accepted (magic-byte detection, traversal guards, manifest-less `skills/` scan).
- [x] **Tar-fallback hardening** (shipped 2026-09-05 as part of M5): per-member allowlist instead of refusal — refusal would break supported 3.10/3.11 (threat-model R-1).
- [x] **Link-escape errors** (shipped 2026-09-05 as part of M5): out-of-root link targets are validation errors; missing-file stays a warning (threat-model R-4).
- [x] **Preview editor + shortcut cheatsheet** (shipped 2026-09-05 as part of M5): Write/Preview tabs (XSS-safe render), `?` modal.
- [x] **Desktop entry** (shipped 2026-09-05 as part of M5): zero-dep `assets/skills-manager.desktop` instead of a `pywebview` wrapper (stdlib-only is a feature).

## Then (v1.2+)

- [ ] **Registry bridge**: browse `skills.sh` → install into chosen scope; publish local skills upstream.
- [ ] **Eval harness**: per-skill before/after prompt tests (per official evaluating-skills guidance).
- [ ] **VS Code extension**: thin wrapper over the existing REST API.
- [ ] **Team sharing**: signed bundles, internal index, draft → review → publish stages.
- [ ] **Refuse unsafe tar fallback** on Python < 3.12 (threat-model R-1). Superseded: per-member allowlist shipped instead (refusal would break supported 3.10/3.11).
- [x] **Zip-import support** (shipped 2026-09-05, M5).

## Ambitious (exploring)

- Skill recommendations mined from shell history / repeated sessions.
- Skill-vs-MCP-vs-subagent guidance; future auto-convert.
- `pywebview` desktop wrapper around the existing web UI. Superseded: zero-dep `.desktop` launcher shipped instead (M5).

## Non-goals

- Becoming a skill *library* (we manage; registries publish).
- Remote hosting / multi-user server (local-first forever).
- New runtime dependencies (stdlib-only is a feature).
