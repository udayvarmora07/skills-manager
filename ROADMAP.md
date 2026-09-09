# Roadmap

Public direction for `skills-manager`. Items move from Proposed → Accepted → Building → Shipped. Anything touching the [locked constraints](README.md#contributing) needs maintainer approval first.

## Next (v1.1)

- [x] **Spec-lint+** (shipped 2026-09-05): name regex rejects `--`; `description_score()` use-context/filler scoring + warnings; body line + token (>5000) warnings; `scripts/`/`references/`/`assets/` layout checks — mapped to the official [best practices](https://agentskills.io/skill-creation/best-practices).
- [x] **Cross-scope dedup**: same-name skills across scopes detected (`doctor --scope all`, doctor modal), diff via descriptions-differ flag, converge with existing `sync`.
- [x] **Token budget view**: per-skill/per-scope startup footprint in CLI (`tokens --scope all`) + UI (budget bar, `?window=` selector).
- [x] **Rollback**: snapshot on edit/sync (`history` exists) + `restore --snapshot` (shipped 2026-09-08).
- [x] **One-command migration**: full-library export/import (skills + trash + templates) for new machines (shipped 2026-09-08).

## Then (v1.2+)

Research verdicts 2026-09-09 (`TODO.md` Deferred section; `PLAN.md` §11
annex) govern these — verdict first, then the roadmap line:

- [ ] **Registry bridge** — verdict: DEFER network browse/fetch (OIDC-gated API; staged offline→passthrough): browse `skills.sh` → install into chosen scope; publish local skills upstream.
- [ ] **Eval harness** — verdict: ADVISORY-ONLY stays, file-based, never blocking: per-skill before/after prompt tests (per official evaluating-skills guidance).
- [ ] **VS Code extension** — verdict: separate-repo spike, no backend changes here: thin wrapper over the existing REST API.
- [ ] **Team sharing** — verdict: DEFERRED pending trust/key-distribution ADR + threat-model delta: signed bundles, internal index, draft → review → publish stages.
- [ ] **Refuse unsafe tar fallback** on Python < 3.12 (threat-model R-1) — verdict: REJECT refusal (keep feature-detect + guarded manual extractor).
- [ ] **Zip-import support** (`import` is tar-only today) — verdict: APPROVE as a scoped `import` extension (issue #5; red-first malicious-ZIP corpus; no new command).

## Ambitious (exploring)

- Skill recommendations mined from shell history / repeated sessions.
- Skill-vs-MCP-vs-subagent guidance; future auto-convert.
- `pywebview` desktop wrapper around the existing web UI — verdict: REJECT as a product direction (browser canonical; issue #9).

## Non-goals

- Becoming a skill *library* (we manage; registries publish).
- Remote hosting / multi-user server (local-first forever).
- New runtime dependencies (stdlib-only is a feature).
