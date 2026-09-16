# Docs Index — Skills Manager

**Version 0.3.0**

**AI manifest**: Entry point to the project docs. Every doc **in this tree** follows HADS: H1 title, version line, AI manifest, then `[SPEC]`/`[NOTE]`/`[?]` block markers on their own bold lines — and `check_docs.py` now enforces those three header facts for every `docs/*.md`, plus valid local links/anchors, table integrity, and the surface-parity checks below. Project files that live at the repository root (`README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `SECURITY.md`, `TODO.md`, `PLAN.md`, the threat model, the security report) carry their own header conventions and are deliberately outside the HADS contract. The index was refreshed on 2026-09-15; flag stale facts in `06-progress-log.md`.

## Document map

| Doc | Covers | Load when |
|---|---|---|
| @docs/01-architecture.md | Data model, data-dir layout, FS vs SQLite roles | Any task touching data or paths |
| @docs/02-modules.md | Module-by-module inventory, constants, key behavior | Any edit to `skillsmgr/` internals |
| @docs/03-cli-surface.md | Every command, alias, flag, exit code | Web UI work (must mirror CLI) or CLI QA |
| @docs/04-store-api.md | `Store` public API + SQLite schema | Any UI/store integration |
| @docs/08-web-ui.md | Web UI architecture, REST API, frontend map | Any web UI build or testing |
| @docs/09-baseline-evidence-2026-09-07.md | Dated baseline checks and P0 reproductions | Before P0 hardening or branch integration |
| @docs/10-worktree-integration-comparison-2026-09-08.md | File-by-file comparison of unmerged worktrees and replay order | Before integrating candidate branches |
| @docs/11-integration-status-2026-09-08.md | Selective replay map, first-ten task status, artifact decision, and acceptance evidence | Before merging roadmap work |
| @docs/PRE-MERGE-CHECKLIST.md | Source, provenance, security, verification, and documentation gates | Before committing or merging changes |
| @docs/ADR-001-localhost-mutation-token.md | Decision not to add a per-process mutation token | Any localhost request-boundary change |
| @docs/12-agent-root-discovery-2026-09-08.md | Official discovery-root inventory, precedence/reload notes, and explicit uncertainties | Before changing supported consumer roots |
| @docs/13-audit-remediation-status-2026-09-11.md | Per-finding disposition (`FIXED`/`PARTIAL`/`OPEN`) for every ID in `DEEP-AUDIT-2026-09-11.md`, plus the remaining-work grouping and provenance | Before starting or resuming any deep-audit remediation work |
| @docs/14-competitive-product-business-strategy-2026-09-15.md | Dated competitor research, positioning, customer segments, monetization, GTM, metrics, and strategic decisions | Before changing product positioning, packaging, or business model |
| @docs/15-product-ux-delivery-plan-2026-09-15.md | Target IA and UX, phased workstreams, acceptance criteria, experiments, dependencies, and approval gates | Before cutting a product/UX/business roadmap milestone |
| @docs/ADR-002-root-consumer-effective-state.md | Proposed root/consumer/instance/effective-state vocabulary and approval boundary | Any scope architecture or discovery-model change |
| @docs/ADR-003-registry-bridge-and-eval-harness.md | Offline registry bridge + file-based eval harness: decisions, surfaces, deferred halves | Any registry, install-preview, or eval-harness change |
| @docs/ADR-004-team-sharing-signed-bundles.md | Team sharing (signed bundles, draft → review → publish): trust model, format sketch, blocking decisions — design only | Any bundle-signing, team-distribution, or review-workflow change |
| @docs/06-progress-log.md | Dated log of changes, decisions, bugs | Before/after any session; keep updated |
| @docs/07-context-strategy.md | Hot/warm/cold loading model, compaction anchors | Long sessions, context management |
| @docs/SESSION-CONTEXT.md | Fast re-anchor cache: current state, common tasks, gotchas | Start of any session (preferred over re-reading source) |

## Reading order

1. `AGENTS.md` (root, hot cache — 5 min).
2. `docs/README.md` (this file).
3. Topic docs just-in-time per the map above — never all at once.
4. `docs/06-progress-log.md` to sync on recent changes, then update it when done.

## HADS conventions used here

- Version line within first 20 lines of each doc.
- AI manifest block before the first content section.
- `[SPEC]` = authoritative contract; `[NOTE]` = context/history; `[?]` = open question — resolve or remove it, never leave silently.
- Machine-checked by `check_docs.py`: header facts, links and anchors, table cell
  counts, CLI/REST/`Store` surface parity, and the session-context file inventory.

## Open questions

- `[?]` None for this index. Product, pricing, persistence, hosted-service, and
  distribution questions are owned by
  @docs/14-competitive-product-business-strategy-2026-09-15.md and
  @docs/15-product-ux-delivery-plan-2026-09-15.md. Architecture-specific
  questions remain in their ADRs. Resolved questions are recorded in
  06-progress-log.md.
