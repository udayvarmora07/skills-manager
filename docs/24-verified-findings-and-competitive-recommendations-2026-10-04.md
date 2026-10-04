# Verified Findings and Competitive Recommendations — skills-manager

**Version 1.0.0**

**AI manifest**: Dated, evidence-backed audit of `skills-manager` combining a live
internal audit (code, tests, gates, CI, packaging, filesystem) with a fresh
external sweep of the AI-agent skills-tooling market. Findings marked
**[VERIFIED]** were reproduced in this repository during the audit; findings
marked **[AGENT]** come from a delegated research pass and are not
independently re-run here. Competitive figures are dated 2026-10-04 and decay
fast. Load this before planning release, positioning, onboarding, architecture,
or UI work. It supersedes nothing — it adds a verification layer the earlier
audits lacked.

## How to read this document

**[SPEC]** Every **[VERIFIED]** item below was reproduced against the working
tree at commit `e5af3d5`. Where a claim is *structurally* confirmed but not
demonstrated at runtime, it says so. Where a delegated claim conflicts with a
direct measurement, the direct measurement wins and the conflict is stated.

**[SPEC]** Severity is impact on a user or on correctness, not effort to fix.
The single most important finding is not a missing feature: **CI has been red
on `main` for every run since 2026-09-16, and that red build has silently
switched off four quality gates, including the one that verifies release
artifacts.**

---

## Executive summary

**[NOTE]** Ten findings, in priority order. Effort is for one competent
engineer already fluent in the codebase.

| # | Finding | Class | Severity | Effort |
|---|---|---|---|---|
| 1 | **The entire registry integration is dead — `--browse`/`--search`/`--curated`/`--fetch` all return HTTP 401 in production** | Verified live | **Critical** | ~2h |
| 2 | CI red on `main` since 2026-09-16; four gates skipped, incl. release-artifact check | Verified | **Critical** | ~1h |
| 3 | `/api/doctor?scope=all` is a **51 s p50** at 5,000 skills — and the fix is one unused argument | Verified (root cause) | **Critical** | ~1h |
| 4 | `AGENTS.md` + `docs/01-architecture.md` state locking is in-process `RLock`; the code uses `flock`/`msvcrt` | Verified | **High** | ~30m |
| 5 | A pre-existing `0775` data dir permanently locks users out, with no remediation message | Verified | **High** | ~1h |
| 6 | Complexity ratchet measures a 160-line adapter; 2,076 LOC of CLI logic is ungated | Verified | **High** | ~2h |
| 7 | Agent-scope `toggle_skill` does check-then-rename with no lock | Verified | **High** | ~1h |
| 8 | Source-update commit and `Store.edit` take disjoint locks → lost-update window | Verified (structural) | **High** | ~2h |
| 9 | 0 GitHub stars, 120 PyPI downloads, no topics, no brew/npm, PyPI-only | Verified | **High** | ~1 day |
| 10 | `list()` re-reads every document: default Library view is a **4.0 s p95** at 3,000 skills | Verified | **High** | ~2–4h |
| 11 | `/api/skills/<name>/raw` leaks a raw codec error as HTTP 400 — the issue-#13 bug class, one call site from being fixed | Verified | **High** | **XS** |
| 12 | `GET /api/export` writes a file; `GET /api/skills` creates the DB; upload silently drops parts | Verified (root cause) | Medium | ~2h |
| 13 | `examples/` is absent from the sdist — the agent-facing skill is uninstallable | Verified | Medium | ~15m |
| 14 | `renderMarkdown`/`esc` have zero committed test coverage (8 no-op stubs) | Verified | Medium | ~2h |
| 15 | Docs are 91% of product LOC; `06-progress-log.md` alone ≈ 45.7k tokens | Verified | Medium | ongoing |

**The strategic read.** The codebase is materially stronger than its adoption:
24.6k LOC of product, a genuinely fail-closed validator, real cross-process
locking, zero-dependency packaging, and a verified-clean XSS surface. The
market, however, has consolidated *around* it. GitHub now ships **`gh skill`
first-party with 48 agent hosts**, covering install, provenance-bearing list,
dry-run update, and publish. One 139k-star superset tool absorbs skills as a tab.
Claude Code ships `/skill-doctor` for context cost and unused detection. The
ecosystem's own CLI runs 26.5M downloads a month. Meanwhile this project has
**0 stars and 120 lifetime downloads**.

That materially narrows the earlier positioning. "Tell me what I have and what
it costs" is now table stakes, and Command Code already reports shadowed
copies. What survives is narrower and harder: **cross-agent effective
resolution** (no tool answers which copy *Codex* will load for *this* consumer
in *this* project — only Zed, Copilot, Cline and Junie answer it for themselves)
and **a reviewable, reversible update** (`gh skill update` is dry-run-only with
no rollback; Claude Code's auto-update silently rewrites files on disk). Those
two assets exist here and nowhere else. Everything else in this document is
either protecting them or fixing a gate that would let them rot silently.

There is also a strategic fact worth stating plainly: the Agent Skills
specification **deliberately declines to define within-scope precedence**. That
is a reason to defend this project's existing refusal to invent a winner — not
a gap to fill.

---

# Part A — Verified defects

## A1. CI is red on `main` and four quality gates are switched off — CRITICAL

**[VERIFIED]** Every `main` push since `2026-09-16` has failed:

```text
35828797051  2026-09-23  feat: execute next-five task plan       FAILURE
35773770784  2026-09-22  feat: add hygiene reporting …           FAILURE
35773428871  2026-09-22  docs: add skill hygiene …               FAILURE
35772833320  2026-09-22  feat: add safe local source update …    FAILURE
35715410414  2026-09-21  docs(ui): record regional formatting …  FAILURE
35711543318  2026-09-21  docs(ui): …                            FAILURE
```

The failing job is `unit (py3.10)` and `unit (py3.11)` only; 3.12/3.13/3.14 are
green. The test is:

```text
tests/test_audit_store_contracts.py:136
RemovePurgeAtomicityTests::test_remove_purge_never_advertises_a_destroyed_skill
AssertionError: Lists differ: ['demo'] != [] : a husk was advertised
```

**Blast radius.** `.github/workflows/ci.yml` declares `needs: unit` on four
further jobs (`ci.yml:58,76,105,135`). Because two matrix legs fail, the whole
`unit` job fails and all four are **skipped**, every run:

```text
browser smoke and frontend syntax      skipped
package + release-artifact check       skipped
docs consistency                      skipped
adversarial security checks           skipped
```

So the browser harness, the adversarial security pass, the docs gate, and —
most importantly — **the package/release-artifact verification that CI performs
before publishing** have not executed on any commit in this release candidate's
lifetime.

**Root cause: the test is filesystem-order-dependent, and the product is fine.**
`Store._purge_skill` (`store.py:1746`) displaces the tree with `os.replace`,
runs `shutil.rmtree`, and on failure chooses between two *both-correct* branches:

- `SKILL.md` already unlinked → drop the index row, park the remnant
  (`store.py:1783`) → `list()` returns `[]`
- `SKILL.md` intact → roll the tree back, keep the row (`store.py:1772-1781`)
  → `list()` returns `['demo']`

Which branch runs depends on the order `shutil.rmtree` enumerates directory
entries. The test's `make_undeletable` chmods a subdirectory to `0o500`, so
`rmtree` hits `PermissionError` at that subdirectory. If the subdirectory is
enumerated *before* `SKILL.md`, the document survives.

Reproduced by holding everything constant and changing only which name sorts
first:

```text
restricted dir = 'scripts'   scandir ['SKILL.md','scripts']   list()==[]       PASS
restricted dir = 'bin'       scandir ['bin','SKILL.md']       list()==['demo']  FAIL
```

Both outcomes are honest — the invariant "a skill is never advertised once its
document is gone" **holds in all six orderings tested**. The test asserts one
specific branch instead of the invariant, so it passes on the author's
filesystem and fails on the CI runner's.

**Recommended fix (assert the invariant, not a branch).** Replace the
branch-specific assertions with:

1. `StoreError` is raised and is not an `OSError`.
2. `("demo" in [r["name"] for r in store.list()]) == (skill_dir / "SKILL.md").is_file()`
   — the advertising invariant.
3. If the skill is still advertised, `get()` succeeds; if not, it raises
   `SkillNotFound`.
4. `doctor()` is honest either way.

**Do not** "fix" this by reordering the test, pinning the order, or skipping it.
Also worth adding: a `check_docs`-style gate asserting that
`complexity-baseline.json` keys resolve (see A4).

## A2. The authoritative docs are wrong about locking — HIGH

**[VERIFIED]** `AGENTS.md` (the always-loaded hot cache) and
`docs/01-architecture.md` — the file `AGENTS.md`'s own router names as
authoritative for the locking model — both state:

```text
Locking is in-process and two-level; it is not a cross-process lock.
The primitive is threading.RLock, so it excludes threads inside one process
only. … that is STORE-11/SEC-12, recorded as OPEN.
```

The code does the opposite. `skillsmgr/atomic_io.py`:

```text
:97   "flock is process-aware on POSIX"
:100  "Windows uses a one-byte msvcrt.locking region"
:176  _fcntl.flock(handle.fileno(), flags)
```

And `docs/13-audit-remediation-status-2026-09-11.md:546,564` records
`SEC-12` and `STORE-11` as **FIXED**.

This is the highest-leverage documentation defect in the repository: the stale
claim is in the file every agent session loads, and it is the single
most safety-relevant statement in the codebase. It also *caused code damage* —
see A5.

**Blast radius is exactly two locations**, which makes the fix unusually cheap.
A repository-wide sweep for the claim confirms `docs/13-audit-remediation-status`,
`task.md`, and `CHANGELOG.md` all correctly record `SEC-12`/`STORE-11` as
`FIXED`; `DEEP-AUDIT-2026-09-11.md` is a findings-only historical record and is
correct as written. Only `AGENTS.md` and `docs/01-architecture.md:151,164`
still carry the stale model.

**Fix.** Correct `docs/01-architecture.md:151,164-166` and the corresponding
`AGENTS.md` paragraph to describe the `flock`/`msvcrt` cross-process advisory
lock and mark `STORE-11`/`SEC-12` FIXED, cross-referencing the audit tracker.
Then sweep the three stale code comments that repeat the same belief
(`store.py:1517-1522`, `templates.py:66-71`, `scopes.py:766-769`).

## A3. Pre-existing `0775` data dir locks users out with no remediation — HIGH

**[VERIFIED — this is live on the development machine right now.]**

`paths.data_dir()` resolves through `path_safety.trusted_root()`, which fails
closed on a group- or world-writable root (SEC-19). `mkdir_private` creates
*missing* components at `0o700` but never repairs an *existing* one's mode.

Any data directory created **before** SEC-19 landed is therefore permanently
unusable. Observed on this machine:

```text
drwxrwxr-x (0775)  ~/.local/share/skills-manager   created 2026-09-07
drwxrwxr-x (0775)  skills/ backups/ templates/ trash/
0700                ~/.local  ~/.local/share      (parents fine)

$ python3 -m skillsmgr list
error: unsafe data root: /home/uday-varmora/.local/share/skills-manager
       is writable by another user

$ python3 -m skillsmgr webui --no-browser
error: unsafe data root: … is writable by another user
```

Acceptance boundary, measured across modes:

| mode | result |
|---|---|
| `0700` | accepted |
| `0755` | accepted |
| **`0775`** | **rejected — "writable by another user"** |
| `0777` | rejected |

Three defects compound here:

1. **No upgrade path.** `mkdir_private` never chmods an existing directory.
2. **No remediation in the error.** It names the condition but not the fix; the
   message does not say who should run `chmod 700 <path>`.
3. **Silent escalation.** The lockout also affects the web UI and every
   subcommand, so a user's existing skills (here: 5 skills, a 94 KB index, trash
   entries) become unreachable with no in-product route back.

**Recommended fix.** Keep failing closed — the control is correct — but:

- Append the exact remediation to the error: the offending path, why it was
  rejected, and `chmod 700 <path>`.
- Offer a guarded repair: when the directory is owner-owned, its parent chain is
  private, and its contents are recognisably this tool's (`skills/`, `trash/`,
  `skills-manager.db`), tighten the mode to `0o700` and say so. Otherwise
  refuse with instructions.
- Add the missing regression: SEC-19 currently pins *rejection* but nothing
  pins the **upgrade path**, which is why a whole release can ship without
  anyone noticing the lockout.

## A4. The complexity ratchet measures a file that no longer contains the logic — HIGH

**[VERIFIED experimentally.]** `check_complexity.py:25-30` declares:

```python
TARGET_FILES = ("skillsmgr/webapp.py", "skillsmgr/cli.py",
                "skillsmgr/store.py", "skillsmgr/frontmatter.py")
```

On 2026-09-09 the CLI was split behind `cli.py` into `cli_parser.py` (316 LOC),
`cli_handlers.py` (1,760 LOC) and `cli_output.py` (93 LOC). `cli.py` is now a
**160-line adapter** whose only functions are `main` and `build_parser`.
`complexity-baseline.json` was not regenerated: **43 of its 169 entries (25%)
no longer resolve to a measured `FunctionDef` — 42 in `cli.py`, 1 in
`webapp.py`.**

The gate still reports `COMPLEXITY CHECK PASSED: 261 functions across 4 files`.

Demonstration — the *same* function appended to two files:

```text
skillsmgr/store.py         (tracked)   → ERROR: new violation: complexity 65 exceeds budget
skillsmgr/cli_handlers.py  (untracked) → COMPLEXITY CHECK PASSED
```

So 2,076 LOC of CLI logic can grow to arbitrary complexity without the gate
noticing. The delegated audit additionally measured that **39 of the 47
over-budget functions in the codebase (83%) sit outside the ratchet**
(`[AGENT]`; this is consistent with, and explained by, the disjoint target list).

Current hotspots for context: `_route_get` cx 96, `_route_post` cx 80,
`Store.import_` cx 34; outside the ratchet, `validate_cli_combinations` cx 68
and `_validate_provenance` cx 70 (`[AGENT]`).

**Recommended fix.**

1. Append `cli_handlers.py`, `cli_parser.py`, `scopes.py`, `registry.py`,
   `effective.py`, `validator.py`, `hygiene.py`, `source_lock.py` to
   `TARGET_FILES`, then regenerate the baseline from live measurements.
2. Make the gate **fail on baseline keys that no longer resolve** rather than
   silently treating them as improvements. That converts this whole defect class
   from silent to loud.
3. Refactor `_route_get`/`_route_post` after the target list is corrected, so
   the ratchet then guides the work rather than missing it.

## A5. Agent-scope `toggle_skill` performs check-then-rename with no lock — HIGH

**[VERIFIED]** `skillsmgr/scopes.py:745-780` checks `src.is_file()`, checks
`dst.is_file()`, then calls `src.rename(dst)` — **no `_mutation_lock` at all**,
while the sibling operations `scopes.edit_skill` (`scopes.py:708`) and
`scopes.restore_snapshot` (`scopes.py:921`) both take `_mutation_lock`. Only the
agent-scope path is affected; `global` delegates to `Store.enable/disable`,
which does lock.

The inline comment at `scopes.py:766-769` reads:

```text
# STORE-11: the lock is process-local, so a second process (CLI + Web UI on one
# data dir) can move the document between the checks above and this rename.
```

That comment repeats the **stale claim from A2**. The lock is no longer
process-local — which is precisely why the missing lock was tolerated rather
than fixed. This is the clearest evidence that the doc drift in A2 is not
cosmetic.

**Recommended fix.** Wrap the body in `with _mutation_lock(src)` to match
`scopes.py:708`, then update the comment to cite the cross-process lock. Add a
scope-path concurrency regression mirroring `tests/test_concurrency_contracts.py`
— the scope path currently has none.

## A6. Source-update and `Store.edit` take disjoint locks — HIGH

**[VERIFIED structurally; not reproduced as a live race.]** The lock keys do not
intersect:

| path | locks taken | site |
|---|---|---|
| `source_update.commit_update_review` | `mutation_lock(directory / ".review.lock")` | `source_update.py:746` |
| `source_lock.commit_local_update` | `mutation_lock(current)` — the **target tree path** | `source_lock.py:603` |
| `Store.edit` / `create` / `remove` | index lock + `<skill>/SKILL.md` | `store.py:146-155` |

`commit_update_review` revalidates the candidate hash (`source_update.py:760`)
and the current target hash (`:762`) and then swaps (`:768`). A `Store.edit` on
the same skill takes only index + `SKILL.md`, so it can land between `:762` and
`:768` and be silently overwritten by the atomic tree replacement.

**Recommended fix.** Acquire the index lock (index-first, matching
`_skill_and_index_locks` ordering) *around* the `commit_local_update` call, and
extend the index lock to cover the revalidate→swap window rather than only the
post-hoc `resync`. Then add a deterministic test that interleaves an edit
between revalidation and swap.

## A7. `renderMarkdown`/`esc` are never executed by any test — MEDIUM

**[VERIFIED]** The Markdown renderer is the XSS-critical path: it renders
attacker-authored `SKILL.md` bodies. In `tests/test_webui_contracts.py` it is
stubbed as a **no-op at 8 sites** (lines 104, 376, 469, 523, 560, 895, 926,
1066). No committed test executes it.

The property is nonetheless **correct today**. Running 12 hostile payloads
through the real `domain.js` in a Node `vm` produced fully escaped output in
every case, and the delegated audit independently reports 14 payloads with zero
surviving `<`/`>`. The link pattern matches only `https?://`, so `javascript:`
URLs are unmatchable, and `esc` is deliberately not exported, so there is no
bypass path.

The renderer is safe **by inspection**, not by test. `docs/08-web-ui.md` locked
rule 4 ("frontend never renders raw HTML") depends entirely on this function,
and nothing would fail if it regressed.

**Recommended fix.** Add the existing Node-`vm` harness payload set as a
committed regression: assert that no payload yields an unescaped `<`, `>`,
`on*=` handler, or `javascript:` URL, and pin the exported-symbol list so a new
raw-HTML sink becomes visible.

## A9. The entire registry integration returns HTTP 401 — CRITICAL, live today

**[VERIFIED live against production, 2026-10-04.]** `skills.sh` moved its
read endpoints behind Vercel-project OIDC authentication. Our client still
targets the pre-auth paths and now gets `401` on every call.

```text
$ curl -s -o /dev/null -w "%{http_code}" https://skills.sh/api/v1/skills
401
$ curl … /api/v1/skills/search?q=pdf          401
$ curl … /api/v1/skills/curated                401
$ curl … /api/v1/skills/audit/anthropics/skills/pdf   200   ← public
$ curl … /api/download/anthropics/skills/pdf           200   ← public
```

Through the shipped CLI, on a clean data dir with no token set:

```text
$ skills-mgr install --browse    → error: registry request failed with HTTP 401
$ skills-mgr install --search pdf → error: registry request failed with HTTP 401
$ skills-mgr install --curated   → error: registry request failed with HTTP 401
$ skills-mgr install --fetch vercel-labs/skills/find-skills
                                 → error: registry request failed with HTTP 401
```

**Four documented features are non-functional in production right now.**
`docs/03-cli-surface.md:180-181` still describes all four as returning
"bounded catalog/review evidence", with no mention of an authentication
requirement. `ADR-005` and `docs/08-web-ui.md`'s Install modal describe the same
paths. `check_docs.py` cannot catch this: it verifies that routes and flags
exist, not that a third-party service still answers them.

The documented auth is a Vercel-project OIDC token (`VERCEL_OIDC_TOKEN`, ~12 h
rotation, minted against `oidc.vercel.com`) at 600 req/min per team/project.
**A binary on a user's laptop cannot mint one.** The `skills` CLI works around
this by using two *undocumented* public routes — `/api/search` and
`/api/download` — both of which answer 200 without credentials.

**Recommended fix, in order:**

1. **Move browse/search/curated to `/api/search`** (the route the ecosystem CLI
   actually uses, public). Reuse the host/redirect/size/response bounds already
   implemented in `registry.py` — they are already correct, only the path
   changes.
2. **Keep the audit endpoint.** `/api/v1/skills/audit/{source}/{skill}` is
   public and returns real Gen Agent Trust Hub / Socket / Snyk / Runlayer /
   ZeroLeaks verdicts. This is a free, high-value addition: surface them as
   **evidence with vendor disagreement and freshness visible, never as a
   verdict** — the live data shows the same file rated `safe` by one vendor and
   `critical` by another, with a five-month freshness gap on a third.
3. **Treat OIDC as optional, not required.** Accept the bearer token if present,
   but never make it the only path — that is what broke this.
4. **Add a live-contract test or a documented, dated probe** so a third-party
   auth change cannot go unnoticed until a user reports it. A `--check-registry`
   style read-only probe would convert a silent outage into a loud one.

Until this is fixed, **the honest move is to state the registry limitation
prominently in the README** rather than implying working browse/search.

## A8. `examples/` is not packaged — MEDIUM

**[VERIFIED]** The sdist contains 61 members and **no `examples/` directory**:

```text
$ tar tzf dist/skill_control_plane-1.0.2.tar.gz | grep -i example
  NOT PRESENT
```

`examples/skills-manager-management/SKILL.md` is the only artifact that lets an
AI agent drive the tool safely (dry-run first, exact-target preview, explicit
approval). It is invisible to anyone who installs from PyPI, and the CHANGELOG
confirms it is "not auto-installed or included in the Python distribution" —
correct, but it means the agent-facing capability is undiscoverable.

**Recommended fix.** Either ship it inside the package (e.g.
`skillsmgr/examples/<name>/SKILL.md`) so `skills-mgr` can offer
`skills-mgr init --with-management-skill`, or publish it as a `SKILL.md` in a
public registry reachable via `npx skills add`. Given the competitive finding in
B5, the headless/scriptable surface is the contested position; do not leave the
agent entry point off-distribution.

---

# Part B — Competitive position

## B1. The market consolidated around the problem

**[AGENT, observed 2026-10-04]** The 2026-09-22 audit in `docs/18` listed eight
competitors. The landscape has since changed materially.

| Project | Lang | Stars | Last push | What it wins on |
|---|---|---|---|---|
| **`gh skill`** (GitHub first-party) | Rust | — | 2026-04-16 | **48 agent hosts**; `install`/`list`/`update --dry-run`/`publish`/`preview`/`search`; provenance per skill |
| `farion1231/cc-switch` | Rust/Tauri | **139,895** | 2026-10-04 | Absorbed skills as one tab of a config superset |
| `vercel-labs/skills` | TS | 33,085 | 2026-10-02 | The ecosystem itself — 26.5M npm downloads in Sept 2026; `.skill-lock.json` with a tree-SHA |
| `numman-ali/openskills` | TS | 10,774 | 2026-01-18 | Universal loader — **stale 8 months** |
| `HKUDS/OpenSpace` | Python | 7,741 | 2026-08-12 | Skill *evolution* + team cloud — stalled on README commits |
| `xingkongliang/skills-manager` | Rust/Tauri | 5,443 | 2026-10-01 | 54 agents, marketplace, signed cross-platform installers |
| `runkids/skillshare` | Go | 2,712 | 2026-10-04 | Broadest resource types + local web dashboard + team sync |
| `luongnv89/asm` | TS | 949 | 2026-10-01 | **Headless, `--json/--yes/--machine` audit CLI** |
| `wanghuan9/skilldock` | Rust/Tauri | 607 | 2026-10-03 | Git semantics for skills: diff-preview, per-hunk revert |
| **this project** | Python | **0** | 2026-09-23 | Stdlib-only, cross-agent effective resolution, review→apply→rollback |

`gh skill` carries no star count because it is first-party tooling rather than a
repository; it is nonetheless the most consequential entry in this table and was
**verified live** on the audit machine via `gh skill --help`.

Two corrections to `docs/18`: `iamzhihuix/skills-manage` **does not exist** (the
GitHub user 404s) and should be dropped from the record; and
`anthropics/skills` (179k★) is a *content collection*, not a manager — it ships
the spec and templates with no CLI, sync, or inventory layer, and should not be
counted as a competitor.

**The market rewards breadth, not depth.** The two tools that scale both lead
with "one app, N tools". `openskills` reached 10.7k stars with zero management
depth. Both pure-hygiene tools that shipped on the token-cost thesis are dead
(`skillctl` 5★, last push 2026-03-17; `egebese/skill-manager` 38★, a single-day
repo). Do not compete on tool count or marketplace size.

## B2. The incumbent behaviour is `npx skills add`, not another tool

**[AGENT]** `npx skills` runs **26,538,005 downloads in September 2026**. The
real baseline a user compares against is tolerating the mess with one CLI
command — not switching managers. Meanwhile `luongnv89/asm` has already
independently shipped duplicate audit, semantic-overlap audit, and token-residency
reporting: the same insights this project's `hygiene.py` produces.

## B3. White space this project already occupies — **revised**

**[AGENT, 2026-10-04]** The earlier framing was too generous. Two facts erode it:

**`gh skill` is first-party GitHub and ships 48 agent hosts.** Announced
2026-04-16 (`gh` ≥ v2.90.0), verified live. It already does `install` (with
`--pin`, `--scope`, `--upstream`), `list --json` returning a **provenance record
per skill** (`sourceURL, version, pinned, path, scope`), `update` with
`--dry-run`, `publish`, `preview`, and `search`. Directory installs inject
source-tracking metadata into `SKILL.md` frontmatter. That is a large fraction
of this project's feature surface, shipped by the platform vendor, free.

**The incumbents now answer "what is installed and what does it cost".**
Claude Code ships `/skill-doctor` (per-skill context cost, never-invoked
detection) and `/plugin` → Stats → "Not used recently". Gemini ships
`/skills list`. **Command Code** ships documented six-way precedence *and*
reports every shadowed copy as a "Duplicate names" issue. So "tell me what I
have and what it costs" is no longer differentiating, and "report shadowed
copies" is no longer unique.

**What is genuinely still open** — and it is a narrower, sharper claim than the
one made on 2026-09-22:

1. **Cross-agent, cross-consumer effective resolution.** No tool answers *"which
   copy of this skill will Codex load for this consumer in this project?"*.
   Claude Code, Gemini, Copilot, Cline and Junie each answer only for
   themselves. Surveying 15 agents, **only Zed, Copilot, Cline and Junie let a
   user ask "which copy loads right now" at all** — and none of them answers it
   across agents. `doctor --explain` does, per consumer, with primary-source
   citations.
2. **A reviewable, reversible update.** `gh skill update` is the closest thing
   that exists and it is `--dry-run` with **no rollback**. Claude Code's
   auto-update does the opposite of review: it rewrites plugin files on disk in
   the background up to ten minutes after your first message, so "the files you
   reviewed can change on disk." `npx skills` has **no signature verification
   at all**. `source_update.py` — revalidate, exact-target apply, whole-tree
   snapshot, rollback — is the missing half, and it is **local**, which no
   registry can be.
3. **Spec *plus* vendor-extension validation.** `gh skill publish` validates the
   6-field spec only. Claude Code reads 22 frontmatter fields; Cursor adds
   `paths`/`icon`/`color`; Roo adds `modeSlugs`; Codex adds
   `agents/openai.yaml`; Windsurf adds `triggers`/`permissions`. Four agents
   have four different recursion depths and none is in the spec.
4. **Cross-agent convergence detection.** Cursor has 8 roots, opencode 10+,
   Roo 8, `gh skill` 48 hosts. **No tool reports where two agents' libraries
   have silently diverged.**

**[AGENT — correcting an overclaim in an earlier draft of this document.]** The
first version of this section said "no competitor ships a reviewable, reversible
update". **That was wrong.** `xingkongliang/skills-manager` does ship diff +
revision-bound approval (a SHA-256 `removal_approval_token`; a mismatch returns
`Held` and changes nothing) and undoable Git snapshots — its own agent-facing
skill file states the rationale: *"only a person can say those files are
expendable."* The defensible ground is narrower and should be stated precisely:

- **No unattended-update code path exists at all.** Not disabled by default —
  *absent*. The Rust competitor ships an opt-in auto-apply scheduler; Gemini
  ships `--consent`; Cursor ships auto-refresh. Ours is the only surveyed tool
  where a machine can never apply a skill update without a human in the loop.
  This is the one axis where we are better **by construction, not by
  configuration**.
- **Snapshots bind to the update transaction**, not to an optional backup
  service. Theirs lives inside the Git-backup flow, so a user who never connects
  a remote has no undo for an update.
- **The diff is a gate, not an inspection tool.** Theirs enforces on *removals*
  only; ours puts the whole diff, validation and a re-checked candidate digest
  behind one review id.
- **Filesystem-authoritative vs lockfile-authoritative.** Both `npx skills` and
  the Rust app track only what *they* installed — `npx skills update` enumerates
  the lockfile alone, so a hand-placed skill is invisible to it. Ours reads the
  real tree.

And the honest counterweights: they cover **54 agent roots to our 8**, they have
a shipped desktop app at 5,443★, and they have an **open data-loss bug of
exactly the kind we are built against** —
[xingkongliang#256](https://github.com/xingkongliang/skills-manager/issues/256),
open since 2026-06-29: *"更新skill后，原来skill文件夹中用户自己加的文件没了"* —
after updating a skill, files the user had added inside it are gone. Their own
docs separately warn that *"a file the user edited that the new version also
ships… the update overwrites their edits silently."*

The honest one-sentence claim is therefore narrower than "the only tool that
tells you what loads":

> *Here is exactly which bytes each of your agents will load, for this consumer,
> in this project, what it costs you, and what changed since you last approved
> it — with a rollback for every change.*

## B3a. The ecosystem standard deliberately does not exist — do not fill it

**[AGENT]** This is a constraint, not an opportunity, and it protects an
existing decision. The Agent Skills specification's own client guide says only
*"project-level skills override user-level skills"* and then explicitly
declines to rule within a scope: **"either first-found or last-found is
acceptable — pick one and be consistent."** Meanwhile:

- Codex documents an explicit **no-merge** policy and elects no winner.
- Command Code reports duplicates; Roo Code's settings UI renders the
  *unresolved* map, so users see shadowed duplicates and are never told which is
  effective; Continue shows the same name twice in one tool schema.
- **There is no standard for "this name is ambiguous."** That is precisely the
  thing a manager exists to say.

Versioning (`agentskills#46`) has been open 10 months with 19 comments, having
converged on "versioning belongs in the distribution layer, not `SKILL.md`". The
provenance RFC (`#358`) was **closed with zero comments** — not accepted, just
closed. Dependencies (`#90`) were closed with the maintainer note *"why not
simply reference the other skills in the `SKILL.md` body?"*, which means
relationships are prose-only **by decision**, so nothing can validate them.

This is why `ADR-002`'s `effective_state: unresolved` and the refusal to elect
an uncited winner are the right posture. They should be defended, not relaxed.
A manager's job here is to *report observed divergence faithfully*, never to
standardise what the vendors have declined to standardise.

One structural note for later: `.agents/skills` has become the de-facto
cross-agent project convention — endorsed by the spec's client guide, `gh skill`,
and the `skills` CLI — yet only 14 of 70 `skills`-CLI agent rows use it at
project scope. That gap is worth watching, not betting on yet.

## B4. Distribution is the binding constraint — HIGH

**[VERIFIED]** Adoption today:

```text
GitHub stars          0        PyPI downloads (lifetime)   120
GitHub forks          0        … decaying 81 → 1-2 per day
GitHub topics         []       Homebrew                   absent
Discussions           off      npm                        absent
Watchers              0        Distribution               PyPI only
```

`requires_dist` is `None` (correctly stdlib-only), but a package that is
PyPI-only, has no topics, and shows a red CI badge is invisible to every
discovery mechanism GitHub and the ecosystem provide.

**Recommended, in order:**

1. **Fix the CI badge** (A1). A red badge on a zero-star landing page is the
   most expensive free signal being lost.
2. **Add GitHub topics** (`ai-agents`, `agent-skills`, `skill-management`,
   `claude-code`, `codex`, `cursor`, `cli`, `local-first`, `privacy`). Free,
   instant, and the primary discovery surface for a repo with no stars.
3. **Enable Discussions.** Every competitor has one; issue trackers alone do not
   carry a community.
4. **Publish 1.0.2.** The verified-good candidate in A1 has been sitting
   unpublished while 120 lifetime downloads accrue to 1.0.1.
5. **Add a Homebrew tap** — `xingkongliang` and `skillshare` both ship casks,
   and cask installs are the reflex for a desktop-adjacent CLI on macOS.
6. **Consider a `npx` shim.** `skill-control-plane` has 26M-download-scale
   neighbours; a thin npm wrapper is how users in this ecosystem acquire tools.

## B5. The README hero shows the wrong product

**[VERIFIED]** `docs/images/overview-2026-09-23-1280x900.png` — the first
visual on the landing page — is the **first-run guide**, dominated by
disclaimers: *"This guide summarizes existing observations. It never installs,
syncs, cleans up, or changes a skill."* / *"A discovered file is not proof that
a consumer loaded it."* The headline reads "Keep your local skills ready." and
the observed count is "6 observed instances across 2 detected roots".

The UI itself is genuinely good — clean dark theme, logical rail grouping,
honest states, real density without clutter. But as a *sales* surface it
communicates carefulness rather than capability, and a visitor's honest
question ("so what?") is answered with "6".

The differentiators from B3 are present in the product but absent from the
image: divergent copies, and `doctor --explain` resolving which copy loads.

**Recommended.** Re-shoot the hero as the **Library with a divergent
same-name group plus the effective-resolution explainer open** — the one
screenshot that shows what no competitor does. Keep the first-run guide as a
second image, where it belongs.

---

# Part C — Architecture and code quality

## C1. Quantified shape

**[VERIFIED where marked; `[AGENT]` for the delegated measurements.]**

| Metric | Value | Source |
|---|---|---|
| Product Python | 18,482 LOC / 38 modules | VERIFIED |
| Frontend | 6,155 LOC / 5 files | VERIFIED |
| **Product total** | **24,637 LOC** | VERIFIED |
| Tests | 15,773 LOC / 888 tests | VERIFIED |
| Docs + Markdown prose | 22,417 lines / 50 files = **91% of product LOC** | VERIFIED |
| `docs/06-progress-log.md` alone | 34,282 words ≈ **45,700 tokens** | VERIFIED |
| Gates + smokes + harnesses | ≈3,110 LOC | VERIFIED |
| `app.js` | 153 methods, 49 computed, one root component, 0 sub-components | VERIFIED |
| XSS sinks (`innerHTML`/`eval`/`new Function`) | **0**; 2 `v-html`, both via `inlineMd` | VERIFIED |
| Over-budget functions (cx > 15) | 47 of 707; **8 inside the ratchet, 39 outside** | AGENT |
| Import cycles | 10, all resolving via lazy back-edges | AGENT |
| `except Exception` in `skillsmgr/` | 44 — all rollback/diagnostic/fan-in; zero silent `pass` | AGENT |

**The self-referential finding.** This project builds a tool that reports
"context hotspots" and "skills installed but never loaded". Its own
`docs/06-progress-log.md` is ~45,700 tokens and its `docs/07-context-strategy.md`
tells every agent to re-read that file after compaction. The repository is the
pathological case its own hygiene report diagnoses. Consider archiving the
progress log by year and pointing the compaction anchor at a bounded digest.

## C2. Frontend structure

**[VERIFIED/AGENT]** `app.js` is a single root component with 153 methods, 74
`data()` keys and 16 modal state objects managed as flat booleans. Notable
defects, all cheap to fix:

- **`renderMarkdown`/`esc` untested** (A7).
- **Three divergent copies of the observed-state predicate**
  (`domain.js:82-99`, `app.js:414-421`, `app.js:603-610`). `invalid` exists in
  the app copies but not in `domain.OBSERVED_STATE_LABELS`, so a state added to
  the domain seam silently never appears in Quality.
- **The 16-way Escape ladder hand-copies the `data()` key order** that
  `activeModal` derives (`app.js:1904-1920` vs `app.js:99-116`). A modal added
  to one and not the other is un-closable by Escape.
- **No modal stack** — opening a modal from a modal destroys the opener, so
  every nested flow manually tears down its parent.
- **5 raw `fetch()` calls bypass `domain.api`**, re-implementing transport
  inline against the seam's stated purpose.
- `app.js:6` destructures `window.SkillManagerDomain` with no existence guard,
  so a `domain.js` load failure yields a blank page with no message.
- Non-reactive handles (`MediaQueryList`, timers, sequence counters) are stored
  in reactive `data()` and get wrapped in Proxies.

These are the *same defect class* as the backend's flat routers: a dispatch
table hand-copied in N places with no shared source of truth.

## C3. Concurrency map

**[VERIFIED]** Beyond A5 and A6:

- `purge_trash` takes the trash lock only, while `restore` takes
  index → trash → skill (`store.py:1993` vs `1837-1855`). Not a deadlock, but
  purge is weakly excluded from index-scoped writers.
- `atomic_io.py:84-90` creates the predictable `/tmp/skillsmgr-locks`
  directory outside the guarded block; another uid owning it at `0700` yields a
  raw `PermissionError` from every mutation. Contrast `paths.trusted_root()`,
  which checks ownership.
- `_reject_both_documents` exists in `store.py` (3 call sites) and is
  re-implemented inline in `scopes.py:761-766` with different wording — the
  confirmed instance of the "duplicated guard that drifts" bug class this audit
  was looking for. Currently equivalent; nothing keeps it that way.

## C4. Top 5 refactors by impact/risk

| # | Refactor | Risk | Why first |
|---|---|---|---|
| 1 | Correct `TARGET_FILES`; regenerate baseline; fail on unresolved keys (A4) | near-zero | Prerequisite — makes 2,076 LOC visible and forces the router work to be guided |
| 2 | Fix `toggle_skill` locking (A5) + close the update/edit lock gap (A6) | low | Highest severity, small diff; lock order is already index-first so no new deadlock |
| 3 | Split `_route_get`/`_route_post` into a route table | moderate | 327+210 LOC, cx 96/80, 89 branches. Move one route at a time, gated by `smoke_web.py` |
| 4 | One `@store_error_adapter` replacing 9 identical adapters; move `_reject_both_documents` to `path_safety.py` | low | Mechanical; makes the drift class impossible rather than merely absent |
| 5 | Single declarative modal/state registry consumed by `activeModal`, the Escape ladder, and the predicates (C2) | low | Closes four findings together |

---

# Part D — Backend, data, and performance

## D1. The primary read path re-reads every document — HIGH for scale

**[VERIFIED — measured, not estimated.]** A hermetic store of 3,000 synthetic
skills, `SKILLS_MANAGER_DATA` isolated, median of 7 timed runs after warm-up:

| Operation | median | p95 |
|---|---|---|
| `Store.list()` | **2,532.7 ms** | 2,586.9 ms |
| `scopes.list_all()` *(= `GET /api/skills?scope=all`)* | **3,326.3 ms** | **4,008.3 ms** |
| `Store.doctor()` | 2,793.1 ms | 2,811.9 ms |
| `Store.stats()` | 246.6 ms | 278.6 ms |
| `Store.search('skill')` | 130.6 ms | 134.1 ms |

`scopes.list_all()` is the web UI's **default Library view**. A 4-second p95
there is the product's most-experienced moment.

**Root cause.** `Store.list()` is not an index read. Profiling 1,200 skills:

```text
2.464 s total   Store.list
  └─ 2.076 s  _list_uncached
       └─ 2.033 s  _observe_index_row   (1,200 calls — 82% of total)
            ├─ 1.399 s  loader.load_skill      read + parse every SKILL.md
            ├─ 0.560 s  path_safety.contained_path   one resolve() per row
            ├─ 0.431 s  registry.read_provenance      sidecar check per row
            └─ 0.385 s  copy.deepcopy          112,802 calls
```

The SQLite index is read, then every row is re-read from disk, re-parsed,
re-hashed, re-path-resolved and deep-copied to attach the derived observations
(content hash, metadata hash, frontmatter partition, provenance, tokens). The
`docs/16-product-baseline` claim of 10,000-skill support is not supported by
this: 3,000 already costs 4 seconds on the default view.

Note the design tension: the non-persisted observations are a *deliberate*
choice that keeps the filesystem authoritative and avoids a schema change. The
cost is that the primary read path is O(n) full document parses. The
`_coalesced_read` fan-in (`store.py:178`) already collapses identical
concurrent reads, which is the right instinct — but a single sequential `list()`
still pays the full price.

**Recommended fix, in constraint-preserving order.**

1. **Make observations lazy.** Return index rows without hashes/provenance and
   compute them when a row is opened or when Quality/Doctor needs them. This
   alone should take `list()` to a pure index read. No schema change, no Store
   method added — the records already carry the fields, populated on access.
2. **Hoist `contained_path`'s per-row `resolve()`.** Resolve the skills root
   once per scan and join names onto it; re-validate containment once. Saves
   ~0.56 s per 1,200 rows.
3. **Skip the provenance sidecar probe** when the file does not exist — a single
   `os.path.isfile` is already cheaper than the current 0.43 s.
4. Only then consider a short-lived observation cache keyed on
   `(path, mtime_ns, size)` scoped to one request. That preserves filesystem
   authority — a changed mtime invalidates — while removing repeat parses
   inside a single scan.

Items 1–3 are pure latency work with no behavioural change and no schema
movement. **Do not** introduce a persisted observation cache; that would
reintroduce the stale-index class the project deliberately avoids.

## D2. `/api/doctor?scope=all` is a 51-second request — CRITICAL

**[AGENT measured; root cause VERIFIED directly.]** Real `WebAppServer` on an
ephemeral port, `HOME` and `SKILLS_MANAGER_DATA` isolated, ~1,000 requests
across three fixture sizes and four concurrency levels.

| fixture | route | conc | p50 | p95 |
|---|---|---|---|---|
| 1,000 | `/api/doctor?scope=all` | 1 | 1.84 s | 2.13 s |
| 1,000 | `/api/doctor?scope=all` | 10 | 8.23 s | 13.68 s |
| 5,000 | `/api/doctor?scope=all` | 1 | 14.30 s | 21.95 s |
| 5,000 | `/api/doctor?scope=all` | 10 | 64.40 s | **85.48 s** |
| 5,000 | `/api/doctor?scope=all` | 25 | **51.15 s** | 51.27 s |

**Every request returned HTTP 200. Zero non-200s, zero exceptions, zero lock
errors, zero `database is locked`, across the whole run.** That is a genuinely
excellent concurrency result and it should not be buried — see D4.

51 seconds is not a latency, it is an outage. The cause is verified in source
and the fix is already written:

```text
webapp.py:929   _list_scopes(records=records)   ← /api/stats uses the seam
webapp.py:744   _list_scopes()                  ← no seam
scopes.py:226   list_scopes(*, records=None)    ← documented request-level seam
scopes.py:425   find_duplicates() → list_all()  ← unconditional fresh scan
```

`list_scopes()` accepts a `records=` parameter documented at `scopes.py:230` as
*"an internal request-level seam … the Web UI stats route"*. `/api/stats` uses
it. **`_doctor_scope_enrichment` does not** — it calls `list_scopes()` and
`find_duplicates()` back to back, and `find_duplicates()` starts yet another
`list_all()`. Each `list_all()` is uncached, O(N) file reads plus SHA-256.

**Fix:** pass `records=` in `_doctor_scope_enrichment` (one argument), then
extend `_coalesced_read` from `store.list()` to `scopes.list_all()`. The seam
exists; the neighbouring route proves the pattern; one call site does not use it.

## D3. Error-contract gaps

**[AGENT, VERIFIED directly on the highest-value one.]**

| ID | Gap | Evidence | Fix |
|---|---|---|---|
| **D3-1** | **Raw codec text reaches the client as HTTP 400** | `webapp.py:861` is a bare `skill_file.read_text(encoding="utf-8")` with no guard. `UnicodeDecodeError` subclasses `ValueError`, so `_handle_exception` returns **400 with the interpreter's own message**: `"'utf-8' codec can't decode byte 0xe9 in position 46…"`. The same file already has the correct helper — `_skill_text()` at `webapp.py:317` catches `(OSError, UnicodeError)`. | Route through `_skill_text()`, or `loader.read_skill_text()`. **One-line change.** |
| **D3-2** | **Raw 500 on an unreadable document** | Same line: `chmod 000 SKILL.md` → `500 internal error` + stderr `PermissionError`. The client is safe but the request is an *unhandled* exception, and `GET /api/skills/<name>` on the same file correctly returns 200. | Same helper. |
| **D3-3** | `GET /api/export` **writes a file** | `store.export(dest=None)` creates `<data>/backups/export-<ts>.tar.gz` on every call — unpruned, and `docs/08-web-ui.md:262` documents only the download. Violates RFC 9110 §9.3.1: a prefetch or retry grows the directory permanently. Contrast `snapshots/`, which has `SNAPSHOT_KEEP = 5`. | Stream to a temp file and unlink after send, or document and prune. |
| **D3-4** | `GET /api/skills` **mutates the filesystem** | `_init_db()` → `_ensure_store_dirs()` runs on the read path: one GET on an empty data dir creates four directories and a 32 KB SQLite file. It can also *fail* — replacing `<data>/skills` with a regular file turns `/api/skills`, `/api/stats` and `/api/doctor` into 400s. | Read paths must not ensure the layout; 404 with a repair hint instead. |
| **D3-5** | Multipart upload **silently discards unsafe parts** | `web_upload.py:181` `continue`s on absolute/`..`/backslash paths, returning `200 {"imported":[],"skipped":[]}`. The sibling `staged_single_skill` (`:243`) *raises* for the same condition. A user uploading a folder gets success and loses data with no indication. | Reject the whole upload with 400, matching the sibling. |
| **D3-6** | `get()` and `list()` **disagree** | After deleting a skill's directory, `list()` omits it but `GET /api/skills/<name>` returns 200 with `installed:false` and the now-unbacked stored body. `doctor()` flags it as `stale_rows`. | `get()` → 404 when not installed; keep the field for CLI consumers. |
| **D3-7** | Two error-body shapes | 39 routes emit `{"error": …}`; the source-update family emits `{"code", "error"}` (`source_update.py:67`). A client cannot branch on one key. | Standardise, ideally with a code on every route. |
| **D3-8** | Invalid numeric params **silently coerced** | `?limit=abc` → 50 rows; `?window=bogus` → Claude's window. And the same bad `to_scopes` input gives 400 on `/api/batch/preview` but 200 on `/api/sync`. | 400 on unparseable numerics; share one scope-coercion validator. |
| **D3-9** | No pagination anywhere | `?limit=5`, `?offset=5`, `?page=2`, `?per_page=5`, `?cursor=abc` on `/api/skills` — **all silently ignored**, 1,000 rows returned every time. `/api/skills` is 0.992 MB at 1,000 skills. | Add `limit`/`offset` with `X-Total-Count`; reject unknown paging params instead of ignoring them. |
| **D3-10** | `Sec-Fetch-Site` compared without trimming | `web_security.py:52` — `'cross-site'` → 403, `'cross-site '` → **200**. The `email` parser strips leading, not trailing whitespace. Not browser-exploitable, but a policy predicate accepting a value it is documented to reject. | `.strip().lower()`. |
| **D3-11** | `PUT /api/import` content-type match is case-sensitive | `webapp.py:1469` uses `ctype.startswith(...)`; `:1167` correctly uses `.lower().startswith(...)`. `Multipart/Form-Data` is therefore mis-parsed as a raw archive. Exactly the "sibling of an already-fixed bug" class. | `.lower().startswith(...)`. |
| **D3-12** | Non-loopback-looking host raises raw `gaierror` | `webapp.py:1563` binds the **unstripped** `host` while the policy check uses the normalised one, so `'127.0.0.1 '` and `'::1'` pass validation then fail with raw interpreter text. | Bind the validated value; translate `OSError` to `StoreError`. |

## D4. What is genuinely excellent about this backend

**[AGENT, stated plainly]** This backend has been adversarially audited before
and it shows:

1. **The browser boundary is sound and honestly documented.** DNS rebinding,
   two-`Host`-header smuggling, `Sec-Fetch-Site` variants, hostile `Origin`
   (`null`, credential-embedded, authority-swap), relative `Referer`,
   cross-origin `DELETE`/`POST`/`PATCH`/`PUT`, `OPTIONS`/`TRACE` verb
   fallthrough, static traversal (`/../webapp.py`, `/static/../../../etc/passwd`,
   `/%2e%2e/webapp.py`), encoded path traversal, and non-loopback binds were all
   rejected with the correct status. **`SECURITY.md` and the threat model make
   no claim that could be falsified.**
2. **Zero errors under load** — see D4. The `flock` + bounded-registry lock with
   a correct `_is_owned()` check, the deterministic index-first lock ordering,
   and the one-time schema bootstrap under that lock are a properly solved
   concurrency problem, arrived at by fixing real races rather than luck.
3. **`_coalesced_read` is the right optimisation** — in-flight fan-in,
   explicitly *not* a result cache, per-caller `deepcopy` because callers
   annotate rows. It fixes the thundering herd without breaking
   filesystem-as-source-of-truth. That is the hardest thing to get right here.
4. **Lock files live outside managed trees**, so a lock key can never
   materialise a fake skill directory — a subtle trap most implementations fall
   into.
5. **Review-first mutations are a real architectural strength**:
   `/api/batch/preview`→`execute` with a plan hash binding exact physical targets
   and options, and the source-update review/commit/rollback lifecycle with
   single-use review ids and explicit `approve: true`. **These are the two most
   mature parts of the API and should be treated as the template for the rest.**
6. **Archive intake is genuinely thorough** — tar *and* ZIP, content-sniffed,
   with independent pre-validation *plus* capability detection on
   `tarfile.data_filter` (so a bypassed filter cannot weaken the import),
   per-member and whole-archive ratio budgets, ZIP symlink-bit rejection, and
   all-or-nothing full-import rollback.
7. **The codebase documents its own failures**, including "verified but
   deliberately not changed" and `[?]` markers. That is rarer and more valuable
   than green tests.

**[NOTE]** A parallel REST/security review was commissioned and had not returned
at the time of writing. Three specific checks it was asked to perform are
**not** covered by this document and should be run before acting on any
`webapp.py` refactor (C4 #3):

1. Route-by-route REST parity and status-code correctness across all `/api/*`.
2. `EXPLAIN QUERY PLAN` timings on the actual hot queries at 5,000+ skills
   (D1 established *where* the time goes; it did not benchmark SQLite itself).
3. Live loopback-boundary probing — hostile `Host`, `Sec-Fetch-Site`,
   `Origin`/`Referer`, and multipart abuse against a running server.

The static parts of that assessment **are** covered and are favourable (D3), and
`smoke_web.py` passes in the 888-test suite, but a passing smoke test is not a
boundary probe.

## D5. Index design is sound

**[VERIFIED]** The hot query uses the index rather than scanning:

```text
EXPLAIN QUERY PLAN SELECT … FROM skills WHERE status='active'
  → SEARCH skills USING INDEX idx_skills_status (status=?)
```

`SCHEMA_VERSION = "1"`, three tables, `Store` exposes 21 public methods. The
schema is not the bottleneck — the read-time observation layer described in D1
is. No schema change is recommended.

## D6. Security posture

**[VERIFIED]** The loopback boundary is the strongest part of the codebase:

- 0 occurrences of `innerHTML`, `outerHTML`, `insertAdjacentHTML`,
  `document.write`, `eval`, or `new Function` across `app.js`, `domain.js`,
  `index.html`. The entire HTML-injection surface is 2 `v-html` bindings, both
  routed through `inlineMd`, which calls `esc()` *before* any regex, and whose
  link pattern matches only `https?://`.
- `script-src 'unsafe-eval'` is documented as an accepted trade-off with its
  cost stated and pinned by `tests/test_audit_batch5_contracts.py`. Correct.
  See F1 for the cost being *unrecorded*.
- Host/Origin/Referer/Fetch-Metadata validation runs on every routed verb,
  including reads.
- Terminal output sanitisation (`cli_output.sanitize_text`) covers C0/C1/DEL,
  separators, format characters and lone surrogates.

The one integrity gap is A7: this posture is asserted by documentation and by
review, but the single function that makes it true is never executed by a test.

---

# Part E — UI/UX and design system

**[AGENT, live-rendered]** The UI audit ran the real app on loopback against a
seeded fixture (26 global skills, 3 agent-scope copies including one divergent
duplicate, plus disabled/malformed/unaddressable/trash/history rows) and a
second empty instance. **29 screenshots were captured and viewed.** The headline:

> **The backend discipline is excellent and the visual layer has drifted behind
> it** — the tool has stopped inventing facts but has started padding space, and
> the padding now occupies more room than the data.

Accessibility baseline is strong: **Lighthouse 100 / 100 / 100 / 100**, one
fixable failure, logical tab order, a real skip link, consistent 2 px focus
rings, screen-reader names on icon-only controls, and textbook form validation
(per-field errors plus focus moved to the first invalid field).

## G1. A spacing token is used 13 times and defined nowhere — 5-minute bug

**[VERIFIED directly]** `styles.css` uses `var(--s3)` **13 times**. It is
defined **nowhere**, and it is the *only* undefined custom property in the
entire stylesheet:

```text
defined tokens:  --s1:  --s2:  --s4:  --s9:
undefined used:  --s3   (13 uses)
```

An undefined custom property makes `var(--s3)` invalid at computed-value time,
so the declaration is dropped and the property falls back to its initial value.
The affected rules include `.quality-warning`, `.quality-observations`,
`.quality-hygiene-controls`, `.quality-finding-toggle`, `.profile-summary`,
`.recovery-actions`, `.result-block`, and `.notice-list` — all rendering with
**no intended spacing**. Visibly: "Signals not observed" rows sit flush against
their dividers and the divergence banner is glued to the table above it.

**Fix:** add `--s3: 12px;` to `:root`. The documented spacing rhythm in
`docs/08-web-ui.md` is 4/8/12/16/24/32, so 12px is the intended value. This is
the single highest-value change in the entire document relative to effort.

## G2. Ship-first quick wins — under an hour, no design debate

| # | Change | Effort | Why |
|---|---|---|---|
| 1 | Add `--s3: 12px` to `:root` | 5 min | G1 |
| 2 | Add `animation-iteration-count: 1 !important` to the reduced-motion block | 5 min | The block sets `animation-duration: 0.01ms !important` but **two animations are `infinite`** (`.btn.is-busy svg`, `.skel-row`), so the save/create/import busy spinner strobes for reduced-motion users at ~100 kHz |
| 3 | `aria-label` → `"Update from folder for this exact skill instance"` | 5 min | The one Lighthouse failure: `label-content-name-mismatch`, WCAG 2.5.3 Level A |
| 4 | Global `a { color: var(--accent-text); }` | 15 min | Adapter-catalog links render in default browser blue `rgb(0,0,238)` while every document link uses copper |
| 5 | "Show scope controls" → "Filters and scopes" | 10 min | The disclosure also holds All/Active/Disabled, List/Grid, mode and tags. A user hunting "Active only" will not open a control called *scope* |
| 6 | "Empty global trash" → "Purge all 3 items permanently", moved **below** the list | 30 min | It is the **purge button**, not a status, it is the only red control there, and it sits directly above the 3 items it destroys |
| 7 | Dark theme: separate the list and detail pane surfaces; push `--border-strong` toward 3:1 | 1 h | Measured **1.0:1** between the two panes (legible only via a 1.46:1 border) |

## G3. Contrast: every text pair passes, every border fails

**[AGENT, measured at runtime in dark theme]**

| Pair | Ratio | Result |
|---|---|---|
| `#edf0f5` on content surface | 13.46:1 | PASS |
| `#edf0f5` on rail | 14.45:1 | PASS |
| `#a5afbd` muted on content | 6.93:1 | PASS |
| `#e7a06f` copper on content | 7.07:1 | PASS |
| `#37404c` border on content | **1.46:1** | **FAIL** (3:1) |
| `#4a5665` border-strong on content | **2.06:1** | **FAIL** |
| list pane vs detail pane (dark) | **1.00:1** | **FAIL** |

Light-theme borders were computed from token values (not re-measured) and also
fail, at 1.17–1.62:1. **This is WCAG 1.4.11 (Non-text Contrast, Level AA)** and
it is currently violated in both themes. The worst case is `.form-field input`,
whose *only* visual boundary is a 1.62:1 border. Fixing `--border` and
`--border-strong` is the highest-value contrast change and costs nothing
visually.

## G4. Information architecture — chrome is crowding out the data

Three structural findings, each with a measured or observed basis:

- **Overview: the hero consumes 250 of 900 px for zero information**, then a
  *second* generic headline appears below it, then metric tiles
  (`28 / 26 / 1 / 3` at 28 px — the loudest thing on the page, but not
  actionable), then finally the attention queue. Meanwhile the "Observed state"
  panel duplicates the queue's own counts (divergent groups, malformed entries
  appear in both). The queue is already the best-designed surface in the app
  and it is buried.
- **Library: ~330 px of chrome before the first row**, yielding **5.5 visible
  rows** at 1440×900. Every row additionally repeats
  `Global · consumer: skills-manager` at 11 px plus an `Active` badge — uniform
  across all 28 rows, i.e. pure noise. The row type ramp is
  14 / 12.5 / 11 / **10** px; the 10 px `identity-state` badge is below every
  legibility floor and appears on every row.
- **Detail: 66 % chrome / 34 % document.** Title, badges, four actions,
  description, Instances panel and Skill-details disclosure occupy 547 px before
  any document content; the document gets 270 px. The document's own H1 (22 px)
  renders *larger* than the "Skill document" section label (19 px) directly
  above it — inverted hierarchy. Absolute filesystem paths are the largest and
  most colourful text in the Instances panel and the Quality copies table.

**Recurring theme: absolute paths are the primary visual in every list, row and
card.** The design brief says metadata should not become the story, and it
currently does in four places.

## G5. Mobile: correct skeleton, starved information

**[AGENT]** Nothing overflows at any width and the list→detail flow with an
explicit "← Back to Library" works and returns focus. The skeleton is right.

The information is not. At **320×740 the entire first screen is apparatus** —
brand row, search row, tab strip, disclosure bar, scope list, context budget
with five truncated chips (`context-bu…`, `code-revie…`, `prompt-inj…`), filter
chips — and **zero skill rows are visible**. Five unreadable chips are worse
than no chips. At 900 px the search input collapses to ~40 px while the
`29 skills` count pill keeps full width: priority inverted.

## G6. Request amplification

**[AGENT, network panel]** Across 9 navigations: `/api/skills?scope=all`
fetched **6×**, `/api/skills/<name>?scope=agents` **5×**, `/api/skills/<name>/raw`
**5×**, `/api/trash` **3×** — 33 requests where ~10 would do. All returned 200
and there were zero console errors, so this is waste rather than breakage, but
it compounds directly with D1: each redundant `scope=all` fetch pays the
2.5-second observation cost again.

## G7. Design-system debt

**[AGENT]** Spacing tokens cover only 4/8/16/32 — **12 and 24 have no token**, so
two of the six documented rhythm steps can only be written literally. 83 % of
box-geometry declarations are hardcoded, with 18 distinct off-rhythm values.
There are **no `font-size` tokens at all** (144 hardcoded, 26 distinct sizes
including a 10→11→11.5→12→12.5→13→13.5 sub-ramp). Off-contract radii of
4/5/7/12 px sit alongside the contracted 6/8/10/16, with `.scope-link` and
`.rail-action` at 7 px violating the "8 px buttons" rule. Note this interacts
directly with G1: `--s3` is missing precisely because the token set was never
completed.

## G8. The three highest-impact UI changes

1. **Kill the Overview hero; lead with the attention queue** (~1 day). Replace
   the hero with a single status line (`28 skills · 26 active · 4 need
   attention`), promote the queue to first block, delete the duplicate
   "Observed state" panel, and move first-run guidance *below* the queue — a new
   user currently scrolls ~900 px of read-only guidance before reaching
   "Create your first skill".
2. **Raise Library density and suppress uniform values** (~2 days). Collapse the
   filter stack into one 40 px bar; omit scope when every visible row shares it
   and omit the state badge when every row is `Active`; floor type at 11 px and
   tighten rows to ~56 px for **12–13 visible rows** instead of 5.5.
3. **Demote filesystem paths to a disclosure** (~1 day). Primary line becomes
   scope + state; full paths move into the existing Skill-details disclosure
   with a Copy button; delete the `Largest:` chip row from the context-budget
   card on all viewports.

## G9. What is genuinely working

**[AGENT]** Stated plainly, because it is a real asset:

- **The honesty discipline is the best thing about this product.** "Observed
  evidence, not a single score", "not a validation verdict", "unavailable",
  "Signals not observed". It refuses to synthesise a score, refuses to claim an
  effective state, and says *unavailable* rather than inventing one. For a
  supply-chain-adjacent tool that is exactly right, and it is unusual.
- **The colour system is genuinely well made and authored, not generated.** Dark
  mode inverts the primary button to peach `#e7a06f` on near-black at 8.18:1
  rather than dimming the light-theme copper, and it does not read as an
  inversion.
- **The Markdown renderer is good** — escaped, bordered tables, real list
  numbering, copper blockquote caps, warm code blocks, ~75ch measure. It reads
  like a document reader.
- **The New skill modal is the best-composed screen in the app.**
- **The divergent-copy treatment is excellent** — grid mode shows both
  instances stacked inside one card with their own state badges, treating the
  physical root as the unit of truth without pretending to know which loads.
- **The FIRST RUN empty state is the best onboarding in the app**, and the
  adapter catalog resists inventing an answer where none is documented.

**One correction to the delegated finding count:** the agent initially reported
"Empty global trash" as a contradiction with 3 listed items; DOM inspection
showed it is the purge *button*, and the defect is the label and placement
(G2 #6), not a state contradiction. Recorded so it is not re-raised.

---

# Part F — The five locked constraints

**[SPEC]** Recommendations above assume all five hold. Three observations where
the constraints are demonstrably *costing* something, presented for a decision
rather than a change.

## F1. The no-build-step constraint costs 58 KB per install and buys `unsafe-eval`

**[VERIFIED]** The vendored bundle is Vue's **runtime + compiler** build:

```text
vendored  vue.global.prod.js          157,924 bytes
runtime-only vue.runtime.global.prod.js  100,041 bytes
                                   → ~58 KB shipped to every user
```

That extra compiler is exactly why `script-src 'unsafe-eval'` is unavoidable:
`app.js` passes no `template:`/`render:`, so Vue compiles `index.html`'s in-DOM
markup at start-up with `Function(code)()`. The trade-off is documented and
pinned by `tests/test_audit_batch5_contracts.py`, which is correct engineering.
But the constraint has a cost that is currently unrecorded anywhere: **37% of the
frontend payload exists only to avoid a build step.**

The unlock is small and honest: author the Vue app as render functions produced
once at development time and committed, then vendor the runtime-only build.
That is *not* a build step in CI — it is a committed artifact. This would remove
`unsafe-eval`, cut 58 KB, and shrink the XSS blast radius. It should be treated
as an ADR, not a refactor.

## F2. Frozen schema is currently costing nothing

**[VERIFIED]** `SCHEMA_VERSION = "1"` with three tables, `Store` exposing 21
public methods. The delegated audit found no pressure point here — every
derived observation (hashes, provenance, instance state, health) is computed at
read time and deliberately not persisted. **No relaxation recommended.**

## F3. `check_docs.py` is a genuine asset — extend it, do not relax it

**[VERIFIED]** It already enforces HADS headers, link *and anchor* validity,
table cell-count integrity, CLI/REST/Store surface parity in both directions,
and file-inventory parity. The A4 recommendation is to apply the same
"fail loudly when the assertion stops applying" principle to the complexity
baseline. The class of defect this repo has already suffered once — a gate that
reported PASS about a path it could not see — has simply reappeared in a
different gate. That argues for more of this discipline, not less.

---

# Part G — Recommended sequence

**[NOTE]** Ordered so each step makes the next one visible or safe. Steps 1–3
are the whole of the "unblock the release" work and total roughly half a day.

### Day 1 — restore trust in the build

0. **Repair the registry client** (A9). Move browse/search/curated to the public
   `/api/search` route, keep the public audit endpoint as a bonus evidence
   source, and stop making a Vercel OIDC token the only path. **Four documented
   features are returning HTTP 401 in production right now** — this is the
   highest-severity item in this document and it needs no code review to
   confirm.
1. **Fix the purge test to assert the invariant, not a branch** (A1). Verify by
   running it with a restricted directory that sorts both before and after
   `SKILL.md`. This alone turns `main` green.
2. **Re-run CI and confirm all four previously-skipped jobs execute** —
   `browser smoke`, `package + release-artifact check`, `docs consistency`,
   `adversarial security checks`. Do not treat "unit is green" as done.
3. **Correct the locking model in `AGENTS.md` and `docs/01-architecture.md`**
   (A2), then sweep the three stale code comments. Add a `check_docs` assertion
   so `STORE-11`/`SEC-12` cannot silently regress to "OPEN" again.
4. **Fix the data-dir remediation path** (A3) and add the missing upgrade-path
   regression.
5. **Publish 1.0.2**, regenerating the artifact hashes in the progress log from
   `e5af3d5` rather than reusing the `6733da9` values.

### Week 1 — fix the gates that lie

6. **Re-aim the complexity ratchet** (A4): extend `TARGET_FILES`, regenerate the
   baseline, and make unresolved baseline keys a hard failure.
7. **Fix the two concurrency gaps** (A5, A6), each with a regression.
8. **Commit the Markdown-renderer payload set** as a real test (A7).
9. **Apply the seven UI quick wins** (E2) — under an hour, no design debate.
   Start with `--s3: 12px`, which is a five-minute fix for thirteen broken
   declarations in eight components (E1). Then the reduced-motion
   `animation-iteration-count`, the `aria-label` WCAG 2.5.3 fix, the global
   anchor colour, the "Filters and scopes" rename, the "Purge all 3 items
   permanently" rename-and-relocate, and the dark-theme pane separation.

### Weeks 2–3 — the work the gates will then demand

10. **Pass `records=` in `_doctor_scope_enrichment`** (D2). One argument; the
    seam already exists at `scopes.py:226` and `/api/stats` already uses it.
    Then extend `_coalesced_read` to `scopes.list_all()`.
11. **Fix the error-contract gaps** (D3) — starting with D3-1, which is a
    one-line swap to `_skill_text()`, the correct helper already in the same
    file at `webapp.py:317`.
12. **Make observations lazy** (D1). This is the single largest user-visible
    latency win available and the profile says it is mechanical.
13. **Split the two god-routers** (C4 #3), one route at a time, gated by
    `smoke_web.py`. Now visible to the ratchet from step 6.
14. **Collapse the frontend's three divergent state registries** (C2), and fix
    the request amplification (E6).
15. **Fix the border contrast** (E3) — `--border`/`--border-strong` toward 3:1.
    WCAG 1.4.11 is currently violated in both themes.
16. **The three structural UI changes** (E8): kill the Overview hero, raise
    Library density, demote filesystem paths.
17. **Add pagination** (D3-9). Everything is O(N) in both time and bytes with no
    ceiling; at 5,000 skills `/api/skills` is ~5 MB per request.

### Adoption, in parallel and independent of the above

12. Add GitHub topics; enable Discussions (B4).
13. Re-shoot the README hero on the divergent-copies + effective-resolution
    view (B5).
14. Ship `examples/skills-manager-management` inside the package or to a
    registry (A8) — it is the agent entry point and it is currently
    undistributable.

---

# Verification evidence

**[VERIFIED]** All of the following was run against `e5af3d5` during this audit.

```text
unittest discover -s tests                        888 tests, OK  (61.0s)
same suite on python3.11.15                       888 tests, OK  (65.4s)
check_complexity.py                               PASSED (261 fns / 4 files)
check_docs.py                                     PASSED
check_package_data.py (source)                    Vue sha256 PASS; build UNAVAILABLE
smoke_store.py / smoke_web.py                     run via the 888-test suite

clean worktree + pinned hash-verified toolchain:
  uv pip install --require-hashes -r requirements-build.txt   setuptools 84.0.0
  python -m build --no-isolation --wheel --sdist             BOTH BUILT
  check_package_data.py --dist-dir dist                       BOTH PASS
    wheel skill_control_plane-1.0.2-py3-none-any.whl  (6 web UI files, Vue 157,924 B, MIT)
    sdist skill_control_plane-1.0.2.tar.gz           (6 web UI files, Vue 157,924 B, MIT)
  wheel clean-install (--no-index --no-deps)                imports and --help OK
```

The release candidate is **sound**; the blocker is that CI has never been able
to prove it (§A1).

Note: the SHA-256 values recorded in `docs/06-progress-log.md` for the 1.0.2
artifacts describe a candidate based on `6733da9`. Rebuilt from `e5af3d5` they
differ, as expected. Regenerate before tagging.

## What was deliberately not done

**[SPEC]** This was an audit. No project file was modified, no commit was made,
and nothing was published. Scratch worktrees and probe scripts were removed.
One out-of-repository change was made and is disclosed: `chmod 700` on
`~/.local/share/skills-manager`, which was required to confirm A3's remediation
and left the five existing skills intact and reachable.






