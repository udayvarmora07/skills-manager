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
annex) govern these — verdict first, then the roadmap line. ZIP import is
shipped; the remaining lines below are future or rejected directions:

- [ ] **Registry bridge** — verdict: DEFER network browse/fetch (OIDC-gated API; staged offline→passthrough). Offline half shipped 2026-09-10: `install --preview` / `POST /api/install {preview: true}` parse a registry reference (`owner/repo`, `owner/repo/slug`, skills.sh page URL, GitHub URL), map a skill id onto the exact `npx skills add … -s <slug>` command, gate on explicit trust, and surface linkable `/security/{provider}` audit pages plus a content-hash slot. Still open for the item to close: browsing the catalog, fetching/caching files, auth, and provenance persistence (issue #3, @docs/ADR-003-registry-bridge-and-eval-harness.md).
- [ ] **Eval harness** — verdict: ADVISORY-ONLY stays, file-based, never blocking. File contract shipped 2026-09-10: `evals/evals.json` cases with deterministic assertions, `validate --evals` / `--evals-run` and `POST /api/validate {evals|runs}`, recording `outputs/`, `grading.json`, `timing.json`, and a per-iteration `benchmark.json` with the `with_skill` − `without_skill` delta. Still open: any provider abstraction, credentials, isolation model, or runtime backend (issue #4, @docs/ADR-003-registry-bridge-and-eval-harness.md).
- [ ] **VS Code extension** — verdict: separate-repo spike, no backend changes here: thin wrapper over the existing REST API.
- [ ] **Team sharing** — verdict: DEFERRED pending trust/key-distribution ADR + threat-model delta: signed bundles, internal index, draft → review → publish stages.
- [ ] **Refuse unsafe tar fallback** on Python < 3.12 (threat-model R-1) — verdict: REJECT refusal (keep feature-detect + guarded manual extractor).
- [x] **Zip-import support** (shipped 2026-09-10): scoped extension of `import` with bounded preflight, safe manual extraction, and malicious-ZIP regressions; no new command.

## Release

- **`v1.0.1` published successfully (2026-09-10).** The existing release
  workflow built and verified the exact `skill_control_plane-1.0.1` wheel and
  sdist, attested provenance, published to TestPyPI and PyPI, created the
  GitHub Release, and passed post-publish install/CRUD verification. The
  distribution is available at [PyPI](https://pypi.org/project/skill-control-plane/).
  No publication action is performed by this documentation cleanup.

- **HISTORICAL/SUPERSEDED — v1.0.0 gate holds, publication blocked externally
  (2026-09-10):** fresh wheel
  + sdist were built from the current tree and pass the exact-artifact
  package-data gate, and the wheel clean-installs with working CLI CRUD and
  vendored web assets. Publishing was then tag-triggered and blocked by missing
  release configuration; the subsequent `v1.0.1` workflow run completed
  successfully, so this pre-publish record is retained only as history. The CI
  prerequisite was met: CI was green across all 15 jobs, and the workflow's
  build + verify half was rehearsed against a candidate version (tag/version
  gate, build once, exact-artifact gate, tests, docs, complexity, clean wheel
  install — all PASS).

## Ambitious (exploring)

- Skill recommendations mined from shell history / repeated sessions.
- Skill-vs-MCP-vs-subagent guidance; future auto-convert.
- `pywebview` desktop wrapper around the existing web UI — verdict: REJECT as a product direction (browser canonical; issue #9).

## Non-goals

- Becoming a skill *library* (we manage; registries publish).
- Remote hosting / multi-user server (local-first forever).
- New runtime dependencies (stdlib-only is a feature).
