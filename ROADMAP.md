# Roadmap

Public direction for `skills-manager`. Items move from Proposed → Accepted → Building → Shipped. Anything touching the [locked constraints](README.md#contributing) needs maintainer approval first. The dated competitive/product/business rationale and implementation-ready proposal live in [docs/14-competitive-product-business-strategy-2026-09-15.md](docs/14-competitive-product-business-strategy-2026-09-15.md) and [docs/15-product-ux-delivery-plan-2026-09-15.md](docs/15-product-ux-delivery-plan-2026-09-15.md); neither marks a proposal shipped.

## Next (v1.1)

The DEL-11 positioning/distribution slice is documented in
@docs/17-adoption-and-distribution.md. It supplies a migration guide,
reproducible proof-story procedure, and a design-partner protocol; it does not
claim screenshots, human sessions, adoption metrics, hosted sync, or team
governance until those have dated evidence and approvals.

## Proposed after the 2026-09-20 comparison refresh

The comparison-derived follow-ons are proposals only; implementation detail and
approval labels live in [docs/15-product-ux-delivery-plan-2026-09-15.md](docs/15-product-ux-delivery-plan-2026-09-15.md),
with strategy and architecture rationale in [docs/14-competitive-product-business-strategy-2026-09-15.md](docs/14-competitive-product-business-strategy-2026-09-15.md).

### Now

- [x] Shipped 2026-09-21: Overview/dashboard for observed invalid, divergent, disabled, recovery, and recent work, with direct routes into existing surfaces. Human visual/usability validation remains pending.
- [x] Shipped 2026-09-21: task-oriented navigation entry points for Overview, Library, Quality, and Settings, with Quality grounded in independent observed evidence rather than a combined score.
- [x] Shipped 2026-09-21: optional hybrid grid/list Library browse mode; list remains the default, grid is a local presentation preference, and both paths retain filters, exact physical selection, keyboard activation, detail drill-down, and mobile list-to-detail behavior.
- [x] Shipped 2026-09-21: logical Library rows and grid cards now show observed agent/consumer/workspace identity with explicit active, disabled, malformed/unaddressable, or divergent state; exact scope-qualified Instances/detail targeting remains unchanged and no precedence/effective-state claim is made.
- [x] Shipped 2026-09-21: profile quick apply with an exact, preview-locked enable plan over currently observed physical instances; missing and divergent members remain visibly unresolved.
- [x] Shipped 2026-09-21: task-oriented Install/update inbox and single Recovery/backups center composed from existing registry review, provenance, trash, history, import, and export seams; registry-backed skill search is evidence-only, registry fetch and trust remain two explicit phases, and Recovery history is global-scoped.
- [x] Shipped 2026-09-21: Settings/accessibility controls with live System/Light/Dark theme resolution, a CSP-safe pre-paint preference bootstrap, Standard/Large rem-scaled UI text, and local-only preferences.
- [x] Shipped 2026-09-21: accessible frontend-only Commands palette with Ctrl/Cmd+K, searchable available navigation and existing actions, selected-record availability filtering, labelled combobox/listbox results, and modal-aware focus transfer.

### Next

- [ ] Proposed: internationalization follows IA stabilization.

### Evidence-gated

- [ ] Proposed: optional packaged desktop experiment through DEC-09 only, if installer/tray/keychain/signed-updater demand is evidenced.

- [x] **Spec-lint+** (shipped 2026-09-05): name regex rejects `--`; `description_score()` use-context/filler scoring + warnings; body line + token (>5000) warnings; `scripts/`/`references/`/`assets/` layout checks — mapped to the official [best practices](https://agentskills.io/skill-creation/best-practices).
- [x] **Cross-scope dedup**: same-name skills across scopes detected (`doctor --scope all`, doctor modal), diff via descriptions-differ flag, converge with existing `sync`.
- [x] **Token budget view**: per-skill/per-scope startup footprint in CLI (`tokens --scope all`) + UI (budget bar, `?window=` selector).
- [x] **Rollback**: snapshot on edit/sync (`history` exists) + `restore --snapshot` (shipped 2026-09-08).
- [x] **One-command migration**: full-library export/import (skills + trash + templates) for new machines (shipped 2026-09-08).

## Then (v1.2+)

Research verdicts 2026-09-09 (`TODO.md` Deferred section; `PLAN.md` §11
annex) govern these — verdict first, then the roadmap line. ZIP import is
shipped; the remaining lines below are future or rejected directions:

- [x] **Optional desktop window** (2026-09-11, issue #9): the bundled `pywebview` direction stays rejected; the allowed artefact ships as `desktop_launcher.py` — unbundled, loopback-only, zero new dependencies, opening the existing UI in a Chromium `--app=` window with a browser fallback (`tests/test_desktop_launcher_contracts.py`).
- [x] **Effective-resolution diagnostic** (shipped 2026-09-11, issue #12): read-only `doctor --explain CONSUMER [--project DIR] [--skill NAME]` and `GET /api/doctor?explain=…` derive the winning instance per consumer from cited per-consumer rules, report shadowed/also-loads/skipped instances, and return `unknown-consumer`/`undocumented-precedence` instead of a guess. Derives at read time and persists nothing; `effective_state` stays `unresolved` (`skillsmgr/effective.py`).
- [x] **Registry bridge** (shipped 2026-09-16): the existing `install`/`POST /api/install` surfaces now browse, search, and list the skills.sh catalog, and fetch a bounded text snapshot after explicit trust confirmation. Requests enforce the skills.sh HTTPS host, optional OIDC bearer auth, private auth-isolated cache, stale-cache opt-in, response/path/resource limits, upstream-compatible hash comparison, atomic materialization, and credential-free per-skill provenance sidecars. The offline `--preview` contract remains unchanged. See @docs/ADR-003-registry-bridge-and-eval-harness.md and @docs/ADR-005-registry-network-and-provenance.md; no new command, Store method, schema, dependency, or bind.
- [ ] **Eval harness** — verdict: ADVISORY-ONLY stays, file-based, never blocking. File contract shipped 2026-09-10: `evals/evals.json` cases with deterministic assertions, `validate --evals` / `--evals-run` and `POST /api/validate {evals|runs}`, recording `outputs/`, `grading.json`, `timing.json`, and a per-iteration `benchmark.json` with the `with_skill` − `without_skill` delta. Still open: any provider abstraction, credentials, isolation model, or runtime backend (issue #4, @docs/ADR-003-registry-bridge-and-eval-harness.md).
- [x] **VS Code extension** — verdict: separate-repo spike, no backend changes here (2026-09-11). Backend sufficiency is pinned by `tests/test_web_client_contracts.py` and the client contract is documented in `docs/08-web-ui.md`; the extension itself lives in its own repo. Two integration limits found while probing are filed as issue #14.
- [x] **Team sharing policy** — verdict: resolved 2026-09-20 as HMAC/shared-secret integrity, file-only offline distribution, and content-only signed metadata. The offline manifest-evidence foundation remains shipped; archive, approval-state, roles, revocation, and key-lifecycle integration remain unimplemented and require a separate implementation review. See `docs/ADR-004-team-sharing-signed-bundles.md` and threat-model T-13/R-6.
- [x] **Refuse unsafe tar fallback** on Python < 3.12 (threat-model R-1) — verdict: REJECT refusal; closed as not-planned 2026-09-11 with the decision pinned by `tests/test_path_safety.py::TarFallbackPolicyPins` (permissive-filter bypass shape, no-filter traversal, both capability branches).
- [x] **Zip-import support** (shipped 2026-09-10): scoped extension of `import` with bounded preflight, safe manual extraction, and malicious-ZIP regressions; no new command.
- [x] **Out-of-root link severity** (2026-09-11, issue #7): promotion to a validation error stays rejected; the warning-only decision and the `risk_scan()` signal that replaced enforcement are pinned by `tests/test_link_severity_contracts.py`.

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
