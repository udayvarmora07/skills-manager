# Open Decisions Resolved — 2026-11-07

**Version 1.1.0**

**AI manifest**: The maintainer delegated every open product and locked-rule decision on 2026-11-07 ("think harder, do in-depth research and choose the best solution"). This file records each choice, the evidence behind it, and what was built. A decision here supersedes the matching `Decide:` line in `task.md`. Items marked *deferred* or *declined* are decisions too, with the reason; none was skipped silently.

## How the choices were made

**[SPEC]** Three rules, applied to every item:

1. Prefer the option that removes a measured defect with the smallest new surface.
2. Never trade away a security property (containment, review-before-write, loopback-only) for convenience. Where an option did that, look for a narrower variant that keeps the property.
3. Product-direction and business questions (who the user is, revenue, scope widening) are the owner's, not an agent's. Without new evidence they stay proposals, and the reason is written down.

## Built

| Item | Decision | Evidence | Where |
|---|---|---|---|
| D-1 Codex TOML | **Require Python ≥ 3.11** and read `[[skills.config]]` with stdlib `tomllib` | 3.10 reached end of life on 2026-10-01 and 3.10.22 was its final security release ([PEP 619](https://peps.python.org/pep-0619/)). Keeping an EOL interpreter only to avoid `tomllib` would mean a vendored or hand-written TOML parser, which is new attack surface to maintain. | `native_state.observe_codex_states`; facts in @docs/34-agent-skill-loading-research-2026-11-07.md |
| Batch plan binding (P3) | **Bind** the plan id to each target's `content_hash`, `disabled` state and bounded whole-tree hashes, plus the observed destination copies for `sync` | A preview stayed valid after the reviewed document was rewritten or toggled, or after the copy a forced sync would overwrite changed. The user approved one set of bytes and the batch acted on another. 4 of 5 new tests failed on the old code. | `webapp._resolve_batch_target`, `catalog.plan_hash` |
| R2 follow-up: sidecar binding | **Recorded physical path plus content digest**, kept in the manager's private data directory. HMAC was rejected. | A per-install HMAC needs a key file, so it adds key creation, rotation and loss handling, and it protects against nothing a 0700 data directory does not already protect against. A record in `<data>/sidecar-bindings/` cannot be written by a skill package, needs no secret, and also catches a sidecar copied to another directory (sync) or edited after writing. Older tool versions are unaffected, because the sidecar files themselves do not change. | `skillsmgr/sidecar_binding.py` |
| Agent-scope trash restore | **Build** it as module functions plus the existing `/api/trash` route with `?scope=` | Agent-scope removals were irreversible from the UI. The same route also ignored `?scope=` and restored from the global trash, which is a latent wrong-target bug. No new CLI command and no new Store method. | `scopes.scope_trash_list`, `scopes.restore_trashed` |
| SCOPE-2 / D-2 symlinked skill dirs | **Follow read-only**, but only when the link lands inside another managed scope root. Writes through the link stay refused. | All 276 links in `~/.claude/skills` on the maintainer's machine point into `~/.agents/skills` (108) or `~/.codex/skills` (168), roots this tool already manages. Refusing them showed 15% of the library as empty without protecting anything. A link into an unmanaged directory keeps the old refusal, so the tool still never reads or writes outside a managed root. | `loader.scan_dir(link_roots=…)` |
| docs/29 H2 bridge (2026-11-08) | **Explain-only, inside `doctor --hygiene`**; a link-writing bridge command stays deferred | Claude Code's documented roots exclude `~/.agents/skills`, and both anthropics/claude-code #31005 (`.agents/skills` support) and #14836 (symlinked skill folders unreliable) were open on 2026-11-08. A written link may therefore not work, and a new command needs approval. The existing `sync` copy is the remedy named. On the maintainer's machine 7 skills sit only in `~/.agents/skills`. | `hygiene._agents_bridge_section` |
| Skill CI (docs/29 row 25, 2026-11-08) | **Documented recipe**, no new command or published Action | It needs no approval, uses the existing `validate --path`, and its script is executed by a test. | @docs/36-skill-ci-recipe-2026-11-08.md |
| R15 remainder | Shared review-artifact plumbing, behaviour-preserving, with characterization tests captured from the old code first | Engineering item; needed no decision | `skillsmgr/review_artifacts.py` |

## Closed without a change

| Item | Decision | Evidence |
|---|---|---|
| `/api/scopes` without token totals | **No change needed** | Measured on 2,062 real rows: `list_scopes(records=…)` over the request's shared scan takes **0.003 s**. The cost the audit saw was the separate rescan, and the performance pass of 2026-11-06 already removed it by sharing the in-flight scan. Dropping the field would break the classic UI's budget arithmetic for no gain. |
| Cap classic Library rows | **Declined** | Classic is no longer the default interface (`/` → `/v2/` since `61355a2`). A cap would break its documented "exact visible-set" selection contract. The 10,000-instance case is served by v2's lazy bodies. |
| R18 NFKC Unicode names | **Declined** — names stay ASCII `^[a-z0-9]+(-[a-z0-9]+)*$` | Skill names become directory names. macOS normalizes file names to NFD while Linux stores bytes as given, so an NFKC name would compare unequal to its own directory on one platform and could collide on another. Confusable characters (Cyrillic `а` vs Latin `a`) would let one skill impersonate another in every listing. Every path guard depends on `NAME_RE`. The `skills-ref` divergence stays pinned in `tests/test_skills_ref_oracle.py`, so the difference is visible, not hidden. |
| R19 CycloneDX/SPDX export | **Deferred** | Needs a new CLI command (locked constraint 5), and no user request or issue asks for it. Source-lock JSON is already machine-readable. Revisit when a consumer of an SBOM appears. |

## Deferred: owner decisions

**[NOTE]** These shape what the product *is* or how it earns money. The evidence in @docs/26-user-research-skills-context-2026-10-30.md, @docs/27-monetization-five-pass-analysis-2026-10-30.md and @docs/29-user-demand-and-competitor-analysis-2026-11-06.md (D-table) does not settle them, and choosing them for the owner would be a guess presented as a decision.

| Item | Status and the next step that would unblock it |
|---|---|
| docs/33 D-AI-1…7 (AI features) | Deferred. D-AI-4 is a hard blocker: the web server is unauthenticated on loopback, so any route that spends an API key can be driven by any local process. A CLI-only first slice (D-AI-5) is the safe start once the owner wants AI features at all. |
| docs/29 D-3 (lockfile reader in `doctor`) | Already answered in practice: R11 shipped the read-only lock reader inside `doctor --hygiene`, with no new command. |
| docs/29 D-4, D-5/MON-Q2, D-6/MON-Q3, D-9/MON-Q4, D-10/MON-Q1, MON-Q5 | Owner's call: target user, scope widening to MCP/AGENTS.md, a public data report, zh-CN, services-first year, pricing tiers. |
| docs/29 D-8, transcript usage counts | Deferred. This needs a privacy decision: it reads conversation transcripts. |
| Per-project profiles (native toggles) | Deferred. It writes to other tools' settings files, which is a step past the read-only native observations shipped so far (R4, D-1). Do the read side for every agent first. |
| Microsoft APM `apm.yml` interop, project skill lockfile | Deferred. The R11 reader already covers the `skills` CLI lockfiles; the APM file is detected and reported as an unavailable signal. |
| Stale → archive (Curator-style) | Deferred. It needs usage evidence (D-8) to define "stale" honestly. |

## Human-only, unchanged

**[NOTE]** Visual sign-off, a spoken screen-reader check, consented usability sessions, and approving the 1.0.2 PyPI publish in the GitHub `release` environment remain with a person.

## Continuation review notes

**[SPEC]** Review-artifact characterization and failure-path regressions retain
the callers' distinct layouts, expiry/error policies and atomic cleanup. The
new shared module is a complexity-ratchet target.

**[SPEC]** Source-update binding changes are transactional with the tree swap:
a refused backup path, failed replacement or failed binding write preserves the
previous installed bytes and trust record. External agent binding records are
selected through the requesting Store context (or the environment data root
for unbound calls), not whichever unrelated Store happened to register last.
A caller using a custom Store for agent-sidecar operations should bind that
Store context. Restoring older snapshot bytes does not automatically establish
trust for their sidecars; without an authenticated matching record they remain
unbound.

**[NOTE]** Batch plans detect changed companion files as well as changed skill
documents between preview and execution validation. Advisory mutation locks do
not prevent changes made by unrelated tools that ignore those locks. Browser
and full-ladder results are recorded in the newest progress-log entry.
