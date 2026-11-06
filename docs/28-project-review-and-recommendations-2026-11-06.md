# Project Review and Recommendations — skills-manager

**Version 1.0.0**

**AI manifest**: Dated review of `skills-manager` on 2026-11-05/06, combining measured results from the lead reviewer, a security and maintainability read-through, and a competitive, open-source and specification sweep. It lists verified state, prioritised recommendations (with an approval flag for anything touching locked constraints), security findings, the competitive landscape, spec compliance, the status of the new `/v2/` interface, and what was not verified. Competitive figures are dated 2026-11-05 and decay quickly. It adds to, and supersedes nothing in, @docs/24-verified-findings-and-competitive-recommendations-2026-10-04.md.

## Executive summary

- **The tree is healthy.** At `781c1ed` on `design/2026-10-15`, 1,234 tests pass and the complexity, docs, design-token and both smoke gates pass.
- **The largest user-facing cost is payload size.** `GET /api/skills?scope=all` returns 22.7 MB for 2,061 records on the maintainer's machine because bodies are included. Every UI load pays it.
- **A known product defect is still open.** Native agent disable switches (Codex `[[skills.config]]`, Claude Code `skillOverrides`, OpenCode `permission.skill`) are read nowhere in `skillsmgr/`, so a skill an agent has disabled can be shown as Active.
- **Security: two MEDIUM and one LOW-MEDIUM finding.** Tar import can exhaust memory before its caps apply, provenance and source-lock sidecars are accepted unauthenticated from every intake path, and cross-process locks depend on `TMPDIR`. No live Host/Origin bypass was found.
- **The competitive gap is lockfiles and breadth, not features.** Vercel's `skills-lock.json` and Microsoft APM's `apm.lock.yaml` are the de-facto lock formats; this tool reads neither. Its edge remains local inspection, review-first update, and recovery.
- **The `/v2/` interface works on the real API** (read, edit, diff, sync, undo verified against an isolated fixture) but is not yet the default route.
- **Repo hygiene needs a pass:** 85 MB of loose git objects, ~18 MB of untracked prototype directories, large historical root files, 11 outstanding worktrees/branches, five Dependabot PRs open since 2026-09-16.

## Verified state

**[SPEC]** Each item was measured by the lead reviewer on 2026-11-05/06.

1. **Ladder.** On `design/2026-10-15` at `781c1ed`: 1,234 tests OK; `check_complexity.py`, `check_docs.py`, `check_design_tokens.py`, `smoke_store.py` and `smoke_web.py` all pass.
2. **List payload.** `GET /api/skills?scope=all` returns 22.7 MB (2,061 records, bodies included).
3. **Hygiene on real data.** 2,061 observed records, 1,763 physical instances, 716 logical names. 289 errors, of which 249 are "'compatibility' must be a string" from about 40 third-party skills (one pack) that write `compatibility` as a mapping. Findings are capped and truncated at 2,000.
4. **Categories.** All 2,061 records are `uncategorized`, so category grouping carries no information on this machine.
5. **Native switches.** No code in `skillsmgr/` reads any agent's own enable/disable setting. The defect recorded in the 2026-10-30 user-research entry of @docs/06-progress-log.md is open.
6. **Repository.** `.git` is 85 MB of loose objects (0 packs). About 18 MB of untracked `prototype-*` and `design-concepts` directories sit in the main checkout. The root holds large historical files: `TODO.md` (1,279 lines), `PLAN.md` (837), the deep audit (2,337) and `AGENTS-1.md` (522 lines, a SaaS template the repo's own log says does not apply). 11 worktrees/branches are outstanding. Five Dependabot PRs have been open since 2026-09-16. Issue #14 (a `localhost` Host alias returns 403) is open.

## Recommendations

**[SPEC]** Priority: P0 fix now, P1 next, P2 planned, P3 opportunistic. Effort: S under a day, M a few days, L over a week. "Approval" is yes for anything that adds a CLI command or Store method, changes the schema, adds a dependency, or raises `requires-python` to 3.11 (locked constraints in `AGENTS.md`).

| ID | Priority | Area | Recommendation | Evidence | Effort | Approval |
|---|---|---|---|---|---|---|
| R1 | P0 | Security | Stream tar iteration in `archive.py` and enforce member and decompressed-byte caps while reading, not after `getmembers()` | S1 below: 13 KB bz2 gave 373 MB RSS | M | no |
| R2 | P0 | Security | Strip `.skillsmgr-provenance.json` and `.skillsmgr-source-lock.json` at every external intake (`Store.add`, archive import, upload, registry snapshot) | S2 below | M | no |
| R3 | P1 | Performance | Body-less list projection with lazy body fetch for `/api/skills`, keeping an opt-in for full bodies | 22.7 MB per UI load | M | yes if it changes the public list contract |
| R4 | P1 | Correctness | Read native disable switches (Claude Code `skillOverrides`, OpenCode `permission.skill`, Codex `[[skills.config]]`) into observed state, read-only | Open defect; research sections 3 and 4 | M | yes for Codex TOML via `tomllib` (needs 3.11), unless a tiny read-only extractor is used |
| R5 | P1 | Security | Move lock files under the validated data dir; add an acquire timeout | S3 below | S | no |
| R6 | P1 | Validation | Keep the `compatibility` error but dedupe by physical identity, explain impact, and add one warning for non-spec top-level keys | 249 of 289 errors from one pack | S | no |
| R7 | P1 | Repo hygiene | Run `git gc`; move or delete untracked prototype directories; archive large historical root files; remove `AGENTS-1.md` | 85 MB loose, ~18 MB untracked | S | no (deleting files is the maintainer's call) |
| R8 | P1 | Process | Triage the five Dependabot PRs and the 11 worktrees/branches; decide issue #14 | Open since 2026-09-16 | S | no |
| R9 | P2 | Security | Require `application/json` on bodyless POST routes (`/api/trash/purge`, `/api/rebuild`, enable/disable) | S4 below | S | no |
| R10 | P2 | Security | Add a hidden-Unicode, bidi and tag-character scan using `unicodedata` as an advisory finding | APM does this on install | S | no |
| R11 | P2 | Interop | Read `skills-lock.json` and `apm.lock.yaml` and report declared versus present versus hash match | De-facto lock formats | M | yes (new command) unless folded into `doctor` |
| R12 | P2 | Coverage | Add consumer rows and scopes for Amp, Roo, Cline, Kiro, Copilot, Zed, Windsurf/Devin with cited orders | Research section 3 | M | no |
| R13 | P2 | Residency | Rank skills to demote to name-only, extending hygiene evidence | asm residency audit | S | no |
| R14 | P2 | Reliability | Fix 500s where 400 is documented: deeply nested JSON, `?project=~nouser/x` | S6 below | S | no |
| R15 | P2 | Maintainability | Collapse triplicated install-runner logic onto `insights.install_argv`; share review plumbing across `registry.py`, `source_update.py`, `backup_sync.py`; move `StoreError` to `errors.py` | Security report, maintainability | M | no |
| R16 | P3 | Security | Neutralise git config on fetch in `backup_sync._run_git` before anything calls it | S5 below (latent) | S | no |
| R17 | P3 | Validation | Add `skills-ref` as a dev-only differential oracle in tests; lint the 1,536-character description cap | Research sections 2 and 4 | S | no |
| R18 | P3 | Names | Accept NFKC Unicode lowercase names as the spec does | `NAME_RE` is ASCII-only | S | yes (changes a locked name rule used across Store, scopes, CLI) |
| R19 | P3 | Export | CycloneDX/SPDX export from source-lock data | APM | S | yes (new command) |

## Security findings

**[SPEC]** Each finding was reproduced during the review under an isolated `HOME` and `SKILLS_MANAGER_DATA`. The repro scripts were not retained, so none are committed; treat each as reproduced, not as regression-tested. Severities and file references are from the review.

| ID | Severity | Location | Finding | Fix direction |
|---|---|---|---|---|
| S1 | MEDIUM | `archive.py:130` | `validate_members` calls `tar.getmembers()` before the 200-member and expanded-size caps apply. A 13 KB bz2 of repeated headers took 373 MB RSS and 49 s; an 800k-member gzip took 18 s and 369 MB. Growth is linear, so a 1–25 MB bz2 could exhaust memory. | Iterate as a stream, cap members and decompressed bytes while reading |
| S2 | MEDIUM | `store.py` intake, archive import, upload; `registry.validate_snapshot` | The two sidecars are unauthenticated and copied verbatim. Forged provenance made `Store.get` report `registry_provenance` with `hash_verified: true` for a never-fetched skill; a forged lock showed known-verified with a fake git source. `target.physical_path` is never compared to the real path. `registry.validate_snapshot` blocks only the provenance sidecar, not the lock sidecar. | Strip both at external intake; bind to the install by per-install HMAC or path check |
| S3 | LOW-MEDIUM | `atomic_io.py` | With different `TMPDIR` values the second process acquired the lock after 0.03 s instead of waiting. `/tmp/skillsmgr-locks` has no ownership check: a planted symlink created an empty file at an arbitrary path, and another user could hold a lock forever (no acquire timeout). | Locks under the validated data dir; add a timeout |
| S4 | LOW | `webapp.py` routes | Bodyless POSTs skip the JSON content-type check; `POST /api/trash/purge`, `/api/rebuild` and `/disable` with `text/plain` returned 200 (purge deleted data). Origin and Sec-Fetch-Site still gave 403 cross-site; no live bypass was found. | Enforce content type on every POST |
| S5 | LOW (latent) | `backup_sync._run_git` | A hostile repository's `core.sshCommand` ran during `git_fetch`. Nothing calls `backup_sync` today. | Disable config-driven execution before wiring |
| S6 | LOW | JSON parsing; `adapters.project_observation` | Deeply nested JSON gives `RecursionError` (500); `?project=~nouser/x` gives `RuntimeError` because `expanduser` is outside the `try`. Both should be 400. | Bound depth; move `expanduser` inside the guard |
| S7 | INFO | read routes | Symlink containment is not applied on reads: `/raw` served an outside file linked as `SKILL.md` in an agent scope while the list marks it refused. Local user only. | Apply `contained_entry` on read routes |

**[NOTE]** Verified still fixed by live probes: Host, Origin and Sec-Fetch-Site checks on reads and writes; upload and export fixes; REST frontmatter injection (4 payloads); registry redirect and host checks; `source_update` locking; `launcher_security`; the install allowlist.

## Competitive landscape

**[NOTE]** Stars and last-push dates were read via `gh` on 2026-11-05. Items marked `[?]` come from secondary sources.

| Project | Stars / last push | What it does that skills-manager does not |
|---|---|---|
| vercel-labs/skills | 38.2k / 11-05 | About 60 agent targets; check/update; `use` without install; private repos; experimental frozen lockfile with content hashes |
| microsoft/apm | 4.2k / 11-04 | `apm.yml` plus `apm.lock.yaml` across many agents; hidden-Unicode scan; `apm audit` drift check; CycloneDX/SPDX export; policy governance |
| agentskills/agentskills | 27.0k / 11-04 | The specification and `skills-ref` validator; governance adopted 2026-11-04; no spec-level lockfile yet (#46) |
| gh skill (GitHub CLI) | n/a | `install --pin`, tree-SHA drift, `publish` validation `[?]` |
| luongnv89/asm | 965 / 11-01 | Semantic overlap audit, residency audit, token stats |
| xingkongliang/skills-manager | 7.3k / 11-03 | Desktop app, 50+ tools, presets; the main GUI rival |
| rulesync / ruler / ai-rulez | 1.6k / 3.0k / 166 | Generate per-agent config from one source |
| snyk/agent-scan; cisco skill-scanner | 3.2k; 2.7k | Dedicated skill security scanners; detect and call them rather than clone |

**[NOTE]** Where this tool differs: it is stdlib-only, loopback-only, filesystem-authoritative, and offers review-first update with snapshots and a read-only effective-resolution diagnostic. The positioning in @docs/14-competitive-product-business-strategy-2026-09-15.md still holds; the gap to close is lock-format interop (R11).

## Spec compliance

**[SPEC]** The validator is not too strict on `compatibility`. The specification, `skills-ref`, Claude Code documentation and Kiro all require a string of 1–500 characters. The errors on this machine come from about 40 distinct skills in one third-party pack that write a mapping plus non-spec `version`, `author` and `tags`, copied or symlinked about four times across agent folders. Claude Code and OpenCode ignore extra fields and load these skills; claude.ai upload and the Skills API reject fields outside the spec. Recommended behaviour (R6): keep the error, dedupe by physical identity, say "map; spec wants string; agents ignore it, uploads reject it", and warn once on non-spec top-level keys.

Known gaps against the specification and agent extensions:

- `NAME_RE` is ASCII-only; the spec and `skills-ref` allow NFKC Unicode lowercase alphanumerics (R18).
- No unknown-field check; `allowed-tools` string versus list (spec issue #144) is open.
- Agent-specific fields are not modelled: Claude Code (`when_to_use`, `disable-model-invocation`, `user-invocable`, `paths`, `model`, `hooks` and others), Cursor (`paths`, `icon`, `color`), Amp (`mcpServers`), Codex sidecar `agents/openai.yaml`.
- The 1,536-character description plus `when_to_use` cap is not linted.
- `CONSUMERS` lacks Copilot, Windsurf/Devin, Amp, Goose, Kiro, Roo, Cline, Zed and Antigravity; Amp and Roo document full precedence orders that could be cited (R12).

**[?]** Replacing hand-rolled code. `frontmatter.py` (1,312 lines) cannot adopt PyYAML without breaking the stdlib-only rule; the realistic gains are a test-time oracle and text-patching touched keys to shrink the dumper (needs a spike). Multipart framing is deliberate (SEC-11) and should stay, with property tests against `email` as an oracle (prototype not run). `tomllib` needs Python 3.11 while `requires-python` is `>=3.10`; raising the floor is a maintainer decision.

## v2 interface

**[SPEC]** On this branch (`ui/prototype-final`) the prototype-final design is implemented as `/v2/` on the real API. It provides Home (agent rooms), a Skills shelf, a Skill notebook with read, edit and diff highlight, a Sync map, an Inbox, Recovery (trash, backup, import), New skill, a measured dark theme and keyboard help. Verified in a browser against an isolated fixture: replace-damaged-copy, make-copies-match, and edit-save-to-two-places each round-trip on disk, and Undo works through backend snapshots.

Honesty decisions that should be kept:

- No "newest" or "older" claims, because no version order exists. The reference copy is the majority content hash; ties ask the user.
- Refused symlinks are shown as "Linked elsewhere", not broken. On the real machine this moved Claude Code from "169 can't be read" to 1.
- Dot and file-like entries (`README.md`, `.system`) are "Not a skill" notes.
- The new contrast test caught the prototype's muted text at 4.41:1 on the sunken surface; it was fixed.

**Remaining:**

- `/v2/` is not the default route.
- Install, Profiles, Quality, Workspaces and Settings stay in the classic UI via "All tools & settings".
- Agent-scope trash has no in-app restore.
- The 22.7 MB list load (R3) will dominate v2 first paint until addressed.
- **[?]** Human perceptual review, screen reader, forced-colors and zoom coverage remain open, as for earlier UI passes.

## What was not verified

- The security repro scripts were not retained; findings were reproduced during the review only.
- Frontend JavaScript beyond earlier audits, Windows paths and locking, and real-browser DNS rebinding were not checked.
- Competitive figures are from 2026-11-05 and secondary sources are marked `[?]`.
- The tests were run on one interpreter family as reported; the 3.10–3.14 matrix was not re-run for this review.
- No performance fix was prototyped; R3 savings are unmeasured.
- Dependabot PR heads and the 11 worktrees were counted, not re-reviewed.
- The 2026-10-30 user-research and monetization notes exist as untracked files in the main checkout and were not available to link from this checkout.
