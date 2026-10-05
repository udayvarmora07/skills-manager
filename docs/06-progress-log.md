# Progress Log — Skills Manager

**Version 0.4.0**

**AI manifest**: Dated record of changes, decisions, and bugs for skills-manager,
newest entry on top. **Since 2026-10-05 this file is a digest plus the entries
dated 2026-09-23 and later; everything older lives verbatim in
@docs/archive/README.md.** Read the digest below first — it is the part a session
actually needs. Facts flagged stale here are corrected in the owning doc.

## Digest — read this before the entries

**[SPEC] This file is now a digest plus a resident window.** It measured
313,968 characters / 40,906 words / 4,004 lines on 2026-10-05, and it was being
injected into the context window of every session at roughly 14.5% of a 1M-token
budget *before any work started* — larger than this repository's entire MCP tool
surface. `docs/24` §C1 calls this repository "the pathological case its own
hygiene report diagnoses".

**The rule, and the date it was chosen.** An entry stays resident **if and only
if its dated heading is 2026-09-23 or later**; everything dated 2026-09-22 or
earlier moved to `docs/archive/`, byte-for-byte. 2026-09-23 is the boundary
because the DEL-07…DEL-11 series from 2026-09-19 onward is the construction
record for the modules that ship today — `source_lock.py`, `backup_sync.py`,
`bundles.py`, `registry.py`, `catalog.py`, `adapters.py` — and 2026-09-23 is
where that series gives way to the current open queue.

**Where the full record is.** @docs/archive/README.md indexes the two archive
files: @docs/archive/06-progress-log-2026-09.md (2026-09-04 … 2026-09-22, 160
entries) and @docs/archive/06-progress-log-2026-08.md (2026-08-13 …
2026-08-16, 10 entries plus two undated trailing checklists). Archived text was
verified byte-identical to the source file at the moment of the cut.

**This is a move, not a deletion.** Every archived entry describing a decision
has a surviving owning doc: the ADR set,
@docs/19-safe-local-source-update-implementation-plan.md,
@docs/20-skill-hygiene-report-implementation-plan.md,
@docs/21-p0-trust-gate-and-release-metadata-hardening-plan.md, and — for the
2026-09-11 audit batches — the per-finding dispositions in
@docs/13-audit-remediation-status-2026-09-11.md. If an archived entry disagrees
with an owning doc, the owning doc wins.

## Current state (measured 2026-10-05 on `docs-context-budget`, base `522b81f`)

**[SPEC]** Every number below was produced by running the gate on this tree.

- `python3 -m unittest discover -s tests` — **1,102 tests, OK** (152.7 s).
- `python3 check_complexity.py` — **683 functions across 16 files**, new-function
  budget ≤ 15, no ratchet increase.
- `python3 check_docs.py` — **PASSED**. `python3 smoke_store.py` and
  `python3 smoke_web.py` — green on this base commit.
- Python 3.10–3.14 are the supported matrix and CI proves all five. **A green run
  on the default interpreter is not evidence about the other four** — two of the
  three 2026-10-05 CI failures were invisible locally, and one was a real product
  bug. `docs/SESSION-CONTEXT.md` records the loop.

**[SPEC] What ships today.** A stdlib-only CLI (28 top-level commands + 10
subcommands + 3 aliases) and a stdlib-backed local web UI with vendored Vue and
no build step. Agent-scope tracking across claude-code, codex, cursor, opencode,
gemini, commandcode and `agents`. Registry browse/search/fetch against the public
skills.sh routes with review-first commit and a credential-free provenance
sidecar. Safe local source update with snapshots and previewed rollback. A
read-only Skill Hygiene Report. `doctor --explain` for effective-resolution
evidence. Exact surfaces: @docs/03-cli-surface.md, @docs/04-store-api.md,
@docs/08-web-ui.md.

**[NOTE] Locked constraints — ASK before deviating.** Filesystem is the source of
truth (SQLite is a rebuildable index, `SCHEMA_VERSION = "1"`); CLI stays
stdlib-only; the web UI stays stdlib + no build step + loopback bind; **no new
CLI commands or Store methods** without approval.

**[SPEC] Decisions that still bind.** Recorded here because they outlive the log
entries that introduced them:

- SQLite is an index, never authority; never hand-edit the DB.
- The `03-cli-surface.md` → `08-web-ui.md` mirror is exact in both directions.
- `--json` and `view --raw` deliberately emit stored bytes unsanitised; every
  other display path sanitises. Do not "fix" that.
- Advisory risk findings (`risk_scan`, hygiene) are never enforcement evidence.
- Eval scores are workspace files; they never gate an install or an edit.
- Archive-only history and `@docs/archive/*` files carry no current claims.
- Publishing 1.0.2, consented participant sessions, and external screenshots
  require a human decision and are **not** represented as complete.
- The D1 lazy-observations question (making `malformed` / `decode_error` /
  `addressable` lazy) was explicitly deferred by the maintainer on 2026-10-05: it
  is a public-contract change, and adding a fetch-on-demand path would be a new
  `Store` method, which is locked-constraint 5.

## Resident entry index (2026-09-23 … 2026-10-05)

**[NOTE]** 21 dated entries; full text follows.

| Date | Entry |
|---|---|
| 2026-10-05 | CI went red on `main`; two failures, one of them a real product bug |
| 2026-10-05 | A `git add -A` broke a documented policy; corrected before push |
| 2026-10-05 | The frontend had five copies of one predicate, not three |
| 2026-10-05 | Two parallel branches merged; the complexity ratchet had a hole |
| 2026-10-05 | The progress log is bigger than the audit said, by ~78% |
| 2026-10-05 | Four worktrees, four independent tasks, one owner per file |
| 2026-10-05 | D3-6, D3-7, D3-12: the last three error-contract gaps |
| 2026-10-05 | D3-9: `/api/skills` has a real paging contract |
| 2026-10-05 | D3-8: a parameter that cannot be used is a 400 |
| 2026-10-05 | A generic agent manual arrived; one part was adopted, the rest was not |
| 2026-10-05 | D3-5: an unsafe upload part no longer vanishes |
| 2026-10-05 | D3-4: a read no longer creates, repairs, or hides |
| 2026-10-04 | D1: the primary read path, measured before and after |
| 2026-10-04 | Audit remediation day 1 and week 1 (docs/24) |
| 2026-09-23 | Final next-five candidate verification |
| 2026-09-23 | First-scan journey and management-skill example |
| 2026-09-23 | Package release candidate selected |
| 2026-09-23 | Full-inventory baseline refresh |
| 2026-09-23 | Dependabot Actions PR triage |
| 2026-09-23 | Next five audit-derived tasks planned |
| 2026-09-23 | Public onboarding copy and current-build image |

## 2026-10-05 — `task.md` reconciled against the tree; five closed items were missing entirely

**[SPEC]** Six items were verified done and marked so. Every one was checked by
**reading the source and, where it was cheap, by probing a live loopback
server** — not by trusting the audit that recorded it:

| Item | Claim | How it was verified |
|---|---|---|
| D2 | `/api/doctor?scope=all` walked every scope root twice | `scopes.list_all()` invoked **exactly once** per request, counted by wrapping the function |
| D3-1 / D3-2 | codec text reached the client as 400; unreadable document → raw 500 | corrupt `SKILL.md`: raw route → **404** `{"error": …, "code": "not_found"}`, list route → **200** |
| D3-3 | every export left an archive behind | three downloads: `backups/` empty before and after, **0** staging directories left |
| D3-10 | `Sec-Fetch-Site` compared without trimming | four whitespace/case variants of `cross-site` → **403**; `same-origin` → **200** |
| D3-11 | import content-type matched case-sensitively | three case variants → **200** |

**[SPEC] The finding is sharper than "the checklist is stale": D2, D3-1, D3-2,
D3-10 and D3-11 were not unchecked in `task.md` — they were absent from it.**
Only D3-3 appeared, marked `[ ]`. For a file whose stated job is to be the
single source of truth for remaining work, a missing item is worse than a wrong
one: a wrong one gets re-done, a missing one gets nobody.

**[NOTE] Cause and prevention, stated without overclaiming.** Work landed in
branches that recorded the finding id in code and in this log but never touched
`task.md`. The parallel-worktree pattern makes that likely rather than
accidental — a branch owning `skillsmgr/**` has no reason to edit it, and
`AGENTS.md` asks each session to update `task.md` without naming an owner.
**`check_docs.py` cannot catch this class**: it checks documentation against
*source surfaces* (CLI commands, REST routes, `Store` methods), and none of these
items has a source surface to drift from. A gate was deliberately **not** added
for it. The fix that would work is ownership — a finding id closed in a commit
closes its `task.md` line in the same commit, or the commit says why not — and
that is a rule for a person to enforce, not a check to add.

**[NOTE] Two smaller corrections in the same pass.** The `§D1 (agent scopes)`
line was `[x]` while the `D1 (agent scopes)` line above it was `[ ]`, which read
as a contradiction: `282cf2a` landed and merged (`0439fb5`) but it removed
re-derived validation, not the document re-read, so the two are different items
and the lines now say so. And a 2026-09-22 section was still headed
"authoritative" while a newer 2026-10-04 section sat above it.

**[?]** D2's original 51 s wall-clock was **not** re-measured. Only the
mechanism that caused it was, because the 1,965-skill tree that produced that
figure is not available here. The 51 s number stays a dated audit measurement.

## 2026-10-05 — The progress log was archived; this file is now a digest

**[SPEC]** This file measured 313,968 characters / 40,906 words / 4,004 lines
before the split and measures **64,666 characters / 9,478 words / 1,091 lines**
after it — 79% fewer characters and 77% fewer words. The 170 older dated
entries and the two undated trailing checklists moved verbatim into
@docs/archive/README.md.

**[NOTE] The reduction is only real if the older text stays out of the context
window, so the resident window must not grow back.** The 2026-10-05 entry
"The progress log is bigger than the audit said, by ~78%" below recorded a
measurement of this file at 38,729 words; that figure is now historical and is
corrected by the numbers above. Its lesson — *one interpreter is not a test
matrix, and a gate that reports PASS about a path it cannot see is not a gate* —
is unaffected, and is why this entry reports measured numbers rather than
adjectives.

**[SPEC] Two defects were found while splitting, and both are recorded rather
than silently corrected.**

1. A bad merge had doubled an H2 on one line
   (`## 2026-10-05 — The frontend had five copies of one predicate, not
   three## 2026-10-05 — …`). Corrected in place; no other resident entry text
   was altered.
2. **The first boundary chosen was wrong.** The initial split was taken at the
   *start* of the 2026-09-23 entry rather than at the start of the first entry
   to be archived, which would have put a dated entry on the wrong side of the
   stated rule. It was caught by re-deriving the first and last dated heading of
   each slice and comparing them against the rule — not by inspection. The slices
   are now verified by reconstructing the original body from the header plus the
   three slices and asserting the result is character-identical.

**[NOTE] `check_docs.py` did not need changing, and the gate was proved to be
watching the new path.** `check_house_style` enforces HADS headers with
`(root / "docs").glob("*.md")`, which is **non-recursive**, so
`docs/archive/*.md` is deliberately outside the header contract and the
archive's own index carries those header facts by hand. `_all_markdown()` *does*
walk `docs/` recursively, so archived files remain held to the
trailing-newline, table-integrity, `@docs/` pointer and markdown-anchor rules.

Because a gate that reports PASS about a path it cannot see is not a gate — this
repository's own documented failure mode — that split was **measured, not
assumed**. Four defects were injected into
`docs/archive/06-progress-log-2026-09.md` one at a time; all four were caught,
and the file was restored sha256-identical each time:

| Injected defect | Gate result |
|---|---|
| trailing newline removed | `file does not end with a newline` |
| an `@docs/` pointer to a document that does not exist | `broken @docs/…` |
| a relative markdown link to a missing file | `dead markdown link -> …` |
| a table row of 3 cells under a 2-cell header | `final table has inconsistent cell counts [2, 3]` |

The injected payloads are described rather than quoted, because quoting them
verbatim in this entry made the gate red against *this* file — a small
demonstration that the gate reads prose, not just structure.

The non-recursive half was proved the same way: removing the H1 from
`docs/archive/README.md` leaves the gate **green**, while removing the H1 from
`docs/README.md` turns it **red** — so the header check is live and its scope is
exactly `docs/*.md`.

The gate also caught a real defect in this change unprompted: the first draft of
`docs/archive/README.md` was written without a trailing newline, and
`check_docs.py` failed on it before the split was called done.
## 2026-10-05 — CI went red on `main`; two failures, one of them a real product bug

**[SPEC]** The push landed and CI ran it — and **`main` was red**, failing
`unit (py3.10)`, `unit (py3.11)`, `unit (py3.14)` and both Windows
cross-platform legs. Because four jobs declare `needs: unit`, that silently
switched off **adversarial security checks**, **browser smoke and frontend
syntax**, **package + release-artifact check** and **docs consistency** — the
same coupling that let CI sit red for seven days in §A1. Exactly one local
interpreter had ever run this tree, and it was not one of the failing ones.

Reproduced locally before touching anything (`uv` supplied 3.11/3.13/3.14).
The two failures were unrelated:

**1. A test that asserted a mechanism, not a property — on Python < 3.12.**
`test_a_flat_scan_does_not_recompute_relative_parts_per_candidate` patches
`pathlib.Path.relative_to` and asserts it is never called. But
`contained_entry_under` calls `target.is_relative_to(...)`, and **on Python up
to 3.13 `Path.is_relative_to()` is implemented *as* `self.relative_to(...)`** —
in 3.14 it was reimplemented to compare parts directly. So the patch counted a
**stdlib internal** as if it were our walk:

```text
py3.11  rows=3  relative_to=3   <-- all three from pathlib, none from us
py3.12  rows=3  relative_to=0
py3.14  rows=3  relative_to=0
```

The product never called `relative_to` in a flat scan on any version. The
counter is now frame-scoped — `only_project_frames=True` counts a call only
when the *immediate caller* is our code — so it measures what it claims to.
This is the **second time this repository has shipped that exact class of
defect**: §A1's purge test asserted one branch of a two-branch function and
passed on the author's filesystem while failing on the runner's. Both were
"assert the mechanism, not the invariant".

**2. A genuine cross-version product bug.** `test_an_unreadable_document_is_still_reported_as_drift`
failed on 3.14 only, and it was telling the truth. `loader._probe_document`
decided existence with `Path.is_file()`, which **raised** `PermissionError` for
a document inside an unreadable directory up to 3.13 and **returns False** in
3.14. So the same store reported drift on one version and raised
`SkillNotFound` on another — issue #13's and SCOPE-4's contract, silently
split by the interpreter. Existence is now decided with `os.stat`, telling
"absent" apart from "cannot be read" directly, on every supported version.

**Lesson recorded rather than learned for the first time:** one interpreter is
not a test matrix. This repository supports 3.10-3.14 and CI proves it, but
nothing in the local loop did — a green local run said nothing about the two
versions that failed. `docs/SESSION-CONTEXT.md` now records that the local
gate must include every interpreter `uv` can supply, not just the default one.

**3. A Windows-only teardown failure, in a test this session added.**
`test_dist_dir_install_receives_absolute_artifact_paths` `os.chdir`'d into its
`TemporaryDirectory` and restored the cwd with `addCleanup`, which runs *after*
the `with` block exits — so the temp directory was removed while it was still
the process cwd. **Linux allows removing the cwd; Windows refuses with
`WinError 32`.** It passed locally and failed on every Windows leg. The restore
is now a `finally` *inside* the `with`, and an AST sweep confirms no other test
has the shape.

**Verified on all four locally available interpreters**, full 1,102-test suite
each: **py3.11 OK, py3.12 OK, py3.13 OK, py3.14 OK**, plus
`check_complexity.py`, `check_docs.py`, both smokes, both `node --check`, and
`git diff --check`.

## 2026-10-05 — A `git add -A` broke a documented policy; corrected before push

**[NOTE]** Caught while answering "is everything pushed?", which is the first
moment the working tree was inspected rather than assumed. A `git add -A` used
to stage the frontend documentation swept in two files that were untracked at
the start of this session:

- **`.autogit`** — a 3-byte local tooling marker that this log records as
  *"untracked by policy"* in at least two dated entries. Staging it violated a
  rule the repository states about itself, and nothing about the file made that
  worth it.
- **`.specs/audit-2026-10-04/UI-UX-AGENT-RESOURCE-LIST.md`** — 56 KB from the
  audit's working directory.

**[SPEC] Both were caught before anything was pushed**, so no history rewrite
was needed. `.autogit` is untracked again and added to `.gitignore` so it
cannot recur; the file itself is untouched on disk. `.specs/audit-2026-10-04/`
is left tracked, because the rest of `.specs/` already is and singling one
subdirectory out would be the inconsistency.

**[NOTE] The lesson is about the command, not the two files.** `git add -A`
stages whatever *exists*, which includes things a repository deliberately does
not track. This one has no `.gitignore` entry for `.autogit` or `.specs/`, so
nothing would have stopped it, and the resulting commit was green through
every gate — `check_docs.py`, the complexity ratchet and 1,102 tests all
passed with a policy violation inside the tree. **A gate cannot catch a policy
it does not know about**, which is the same lesson as §A4's stale baseline and
§F3's "fail loudly when the assertion stops applying".

## 2026-10-05 — The frontend had five copies of one predicate, not three

**[SPEC]** Fourth and last parallel branch merged. §C2/§C4 also corrected
upward: the audit counted **three** divergent observed-state predicates and
there were **five** (four in `app.js`, one in `domain.js`).

- **One source for the observed state.** All five now call
  `domain.observeRecord()` / `observedStateFor()` / `observedStateKeys()`, and
  `invalid` was added to `OBSERVED_STATE_LABELS` — it had been missing, which is
  exactly the failure the audit predicted: a state added to the seam silently
  never appeared in Quality.
- **One Escape rule.** The old 16-way ladder hand-copied the `data()` key
  order that `activeModal` derives, and the two **disagreed**: the ladder closed
  `commands` first while `data()` lists it last, so with Commands plus another
  dialog open, focus and Escape named different dialogs. Escape now closes
  `activeModal`.
- **One transport.** Five raw `fetch()` calls bypassed `domain.api` (verified
  exactly five). They now route through `api()` / `apiText()` / `apiBlob()`.
  **Identical in-flight GETs share one request; a completed read is never
  cached and a mutation is never shared** — the filesystem stays authoritative.
- **Request amplification (§G6) measured before and after:** 17 requests across
  10 navigations → **9**, with `/api/skills/<name>` and `/api/skills/<name>/raw`
  each dropping from 4 to **0**.
- **`domain.js` is guarded.** A load failure now renders an explicit message
  instead of a blank page, because the destructure at the top of `app.js` had no
  existence check.

**Red-first:** `tests/test_frontend_seam_contracts.py`, 29 tests, **17 failing**
(9 failures + 8 errors) against the pre-fix sources.

**[NOTE] One new test pins a collision nobody had noticed.**
`observations.document_observations()` hashes the document *text*, and an
unreadable row is built with `text=""` — so **every unreadable version of a skill
shares `sha256("")`**. Once a skill is already malformed, a *different* unreadable
version compares equal and the body is not re-fetched. That is harmless only
because the differing `decode_error` is carried across; a reuse decision keyed on
`content_hash` alone would show a stale repair instruction. Recorded as a
`SESSION-CONTEXT.md` gotcha and pinned by a test.

**[NOTE] One item verified and deliberately not done.** The non-reactive handles
(`themeMediaQuery`, `searchTimer`, `modalFocusTimer`, and the `listSeq` /
`detailSeq` / `toastSeq` counters) really do live in reactive `data()` and get
proxied — but moving them changes reactivity, and those counters are compared in
`finally` blocks and watcher callbacks. A non-reactive counter read through a
stale closure is precisely the stale-response class this repository has already
been bitten by. It needs its own proof, not a drive-by inside a de-duplication
diff.

## 2026-10-05 — Two parallel branches merged; the complexity ratchet had a hole

**[SPEC]** Two of the four worktree branches are in: the god-router split
(§C4 #3) and the packaged example (§A8). Both are merged, the ladder is green
on the merged tree (**1,046 tests**), and each is recorded below.

### The god routers are no longer gods — and the ratchet had a hole

| function | before | after | LOC |
|---|---|---|---|
| `_route_get` | **89** | **13** | 311 → 36 |
| `_route_post` | **80** | **11** | 210 → 34 |

Twenty-four per-route guards with a `(parts, qs) -> bool` dispatcher; nothing
went over budget, and two guards were split further rather than parked at
exactly 15. Guarded by `tests/test_audit_route_table.py`: **16 characterisation
tests that passed 16/16 on the pre-refactor tree** and again after, pinning
status, body shape, the stable error `code`, the security header set on
successes *and* errors, and **29 near-miss paths that must keep answering
`unknown_endpoint`**. It went red exactly once — for a real defect the
refactor introduced, a dropped `self.` that turned `/api/tokens?name=` into a
500. A separate 106-observation probe reports byte-identical responses before
and after.

**[SPEC] The audit's numbers for this were wrong again, and in an instructive
way.** It quotes `_route_get` at complexity 96 and "89 branches". **96 is what
`complexity-baseline.json` recorded** — the branch quoted the baseline file
instead of measuring; the code had already fallen to 89. And "89 branches" is
the *complexity* number mislabelled.

**That mistake is not harmless, and finding it exposed a real defect in the
gate itself.** Because the baseline recorded 96 while the code measured 89,
and the ratchet fails only on *increase*, that entry had been carrying **7
points of silent guard headroom** the whole time — and after the refactor it
would have carried 83, letting complexity grow back from 13 to 96 without a
word. The same shape as §A4: a gate that reports PASS about slack nobody is
tracking.

So the baseline was regenerated — and the diff was audited before committing:
**0 entries raised, 8 lowered, 53 added, 0 removed.** Refreshing a baseline
*downward* is now *required*, because it is the only way the guard keeps
pointing at reality.

`slack_baseline_keys()` makes that durable. It is the mirror of the existing
`unresolved_baseline_keys()` (which catches an entry that guards *nothing*):
this one catches an entry that guards *less than it claims*. Red-first proof —
injecting the old `96` makes the gate fail with

```text
ERROR: baseline entry is above the measured metric: …::_route_get: baseline 96 > measured 13
```

and injecting a five-branch bump into the real function now fails with
`complexity 13 -> 18`, which the stale baseline would have waved through.
Three regression tests pin it, including one asserting no real repository entry
is above its measured metric. **Raising a baseline to silence an increase
remains forbidden; this check is what makes the difference visible.**

### The agent-facing skill now ships — and the audit understated why

`examples/skills-manager-management/` is the only artifact that lets an AI
agent drive this tool safely. §A8 said it was missing from the sdist.
Measured with a real build (throwaway venv, pinned hash-verified toolchain,
`--no-isolation`): it was missing from the **sdist and the wheel**, so
`pip install skill-control-plane` gave zero access to it.

Shipped as package data at `skillsmgr/examples/`. Sdist-only would not have
fixed it — PyPI's default for `pip install` is the wheel, and an sdist is
rebuilt into a wheel that drops non-package files. `MANIFEST.in` needed no
change; `skillsmgr/examples/` has no `__init__.py`, so `packages.find` leaves
it inert data that cannot shadow a real `examples` package on a consumer's
import path.

`check_package_data.py` now proves the example is present and readable, and —
the more valuable half — the prohibitions it always had (`tests/`, `docs/`,
`.env`, a database, bytecode, the vendored Vue sha256, PEP 639 MIT metadata)
finally have **offline coverage that fires against a real artifact**. The old
gate happily accepted an archive that silently dropped the agent entry point.

**[NOTE] The remaining gap is a decision, not a defect.** Nothing *offers* the
example: no CLI command can, without locked-constraint-5 approval.
`skills-mgr init --with-management-skill` is the follow-up to decide, and
until then the docs must describe the manual path.

## 2026-10-05 — The progress log is bigger than the audit said, by ~78%

**[SPEC]** docs/24 §C1 flags `docs/06-progress-log.md` as "the pathological
case its own hygiene report diagnoses" and quotes it at **34,282 words ≈ 45,700
tokens**. Re-measured on the current tree:

```text
38,729 words   297,773 characters   3,749 lines
~80k tokens at 3.7 chars/token
92.8k tokens as actually loaded (reported by /context for this session)
```

Two errors, not one. The file grew, and the audit's **own arithmetic was
low**: 34,282 words at 45,700 tokens implies ~3 characters per word, which is
below what English prose costs in subword tokens even then. So the figure was
an undercount for the size it measured, not just a stale size.

**Why this is not a documentation nit.** Memory files are injected into every
session's context window. In this session they consumed **145.4k of 1M tokens
(14.5%)**, of which this one file is 92.8k — larger than the entire MCP tool
surface. The audit's recommendation ("archive the progress log by year and
point the compaction anchor at a bounded digest") is right and is roughly
**twice as urgent** as the number it was written against.

**[NOTE] Not done here, deliberately.** The log is append-only by policy and
`check_docs.py` enforces its HADS structure, so pruning it is a decision, not
a cleanup. The smallest change that would recover most of the context is to
move entries older than a fixed date into `docs/archive/` and leave a one-page
digest in its place. Recorded in `task.md` for the maintainer.

## 2026-10-05 — Four worktrees, four independent tasks, one owner per file

**[NOTE]** The remaining audit work was fanned out to four subagents, each in
its own `git worktree` (worktrunk `wt v0.80.0`), with **disjoint file
ownership** — `AGENTS.md`'s "one writer per working tree" rule, satisfied by
never letting two sessions touch the same file:

| worktree | task | files owned |
|---|---|---|
| `skills-manager.d1scopes` | §D1: agent-scope read cost (3.326 s at 1,965 skills) | `scopes.py`, `loader.py` |
| `skills-manager.frontendregistry` | §C2 / §G6: three divergent state registries, the hand-copied Escape ladder, request amplification | `webui/app.js`, `domain.js`, `index.html` |
| `skills-manager.examples-sdist` | §A8: `examples/` is absent from the sdist | `MANIFEST.in`, `pyproject.toml`, `check_package_data.py` |
| `skills-manager.routeget` | §C4 #3: split `_route_get` (complexity 96, budget 15) | `webapp.py` |

This session kept `docs/`, `task.md`, `docs/04-store-api.md`,
`docs/08-web-ui.md` and every merge, so no two sessions edit one document.
Each agent was told to report what needs documenting rather than write it.

**[NOTE] A fifth slot was dropped after the claim failed verification.**
§C4 #4 recommends *"one `@store_error_adapter` replacing 9 identical
adapters; move `_reject_both_documents` to `path_safety.py`"*. Measured:

```text
grep -rn "store_error_adapter" --include=*.py .   -> 0 hits
except StoreError blocks in webapp.py             -> 2   (the audit says 9)
```

**`@store_error_adapter` does not exist in this repository.** The nine
`str(exc)` sites the audit's count came from are three distinct patterns — a
diagnostic payload, a status mapping, and a re-wrap — not nine copies of one
adapter. Spending a parallel slot on refactoring a symbol that does not exist
would have been wasted work.

The recommendation's **second half is real and still open**: the one-document
invariant (`a skill directory must not hold both SKILL.md and
SKILL.md.disabled`) is implemented twice, as `_reject_both_documents` in
`store.py` and inline at `scopes.py:795`, with different wording and nothing
keeping them equivalent. That is exactly the "duplicated guard that drifts"
class the audit was looking for, and it is queued for a session that owns
`scopes.py`.

**[NOTE] Four audit claims have now failed verification** — recorded because
the whole point of this audit pass was to measure rather than trust:

1. **§A2** claimed `AGENTS.md` carried the stale in-process-`RLock` locking
   claim. It does not; only `docs/01-architecture.md` did.
2. **§A9** described the registry `hash` field as usable for verification. It
   is not — ten candidate algorithms were checked against a live payload and
   none matched, so integrity rests on the manager's own framed `snapshot_hash`
   and the upstream value is carried as `upstream_hash_verified: false`.
3. **§G2 #5** ("Show scope controls" → "Filters and scopes") rests on the claim
   that the disclosure holds filters. It does not; that label was reverted.
4. **§C4 #4** names a decorator that does not exist and overstates `2` as `9`.

## 2026-10-05 — D3-6, D3-7, D3-12: the last three error-contract gaps

**[SPEC]** All three reproduced on the live server first. D3-6 was worse than
recorded:

```text
GET /api/skills       -> 200 ['kept']        # the stale row is correctly omitted
GET /api/skills/gone  -> 200 installed=False  body="# gone\n"
```

This is a row whose directory no longer exists — `doctor()` calls it
`stale_rows` and reports `ok: False` — and it was the one route serving the
**stored body of a document the filesystem does not have**.

- **D3-6.** Both `/api/skills/<name>` and `/api/skills/<name>/raw` now answer
  `404 skill_not_found` for a row with no directory. `Store.get()` is
  **unchanged**: STORE-10's `installed: False` / `path: None` signal is a
  documented contract other callers rely on, and `doctor()` still needs to see
  the row. Only the REST route changed, and a test pins that the Store signal
  survives.
- **D3-7.** One error shape everywhere: `{"error", "code"}`. `error` is always
  the message; `code` is the exception's own stable code when it has one (the
  source-update family keeps `review-not-found`, `target-changed`, …) and
  otherwise a status slug. Six existing tests asserted the error body by exact
  equality as `{"error": message}`; they now assert `{"error", "code"}`, which
  is a **stricter** pin, not a looser one.
- **D3-12.** `WebAppServer` validated `normalized_host` and then bound `host`.
  So `'127.0.0.1 '` (trailing space) and `'::1'` passed the loopback policy and
  then raised the interpreter's own `gaierror` out of the constructor. The
  validated value is what binds, and a socket failure becomes a clean
  `StoreError` naming the host.

**Red-first:** `tests/test_audit_d3_error_contract.py`, 15 tests — **7 failures
+ 4 errors** before, 15/15 after.

**Two of my own errors, both worth recording.** `X-Total-Count`-style lessons
aside, here: `_send_error` grew complexity 1 → 5 and `WebAppServer.__init__`
9 → 11, both restored by extraction (`_error_payload`, `_bind_server`) rather
than by re-baselining. And one test asserted that an `::1` bind failure would
mention "loopback" — but `::1` *passes* the loopback policy and fails at the
socket, so the test was demanding the wrong message and was corrected to demand
a clean `StoreError` naming the host.

## 2026-10-05 — D3-9: `/api/skills` has a real paging contract

**[SPEC]** Closed @docs/24 §D3-9. Measured first: `?limit=5`, `?offset=3`,
`?page=2`, `?per_page=2` and `?cursor=abc` on `/api/skills` were **all silently
ignored** — the same full row set came back every time, ~1 MB at 1,000 skills.

**The paging contract is opt-in.** The web UI asks for `/api/skills?scope=all`
with no paging parameters and needs every row for the Library, so an unpaged
request still returns everything. What changed is that a paging parameter
which *is* supplied is honoured, and one which is **not implemented** is
refused rather than ignored — `page`, `per_page`, `cursor`, `before`, `after`,
`start`, `skip` and `first` all answer `400` naming `limit`/`offset`. `limit`
is capped at 500 so one request cannot ask for an unbounded page, `offset`
applies on its own, an out-of-range `offset` is an empty page rather than an
error, and every response carries `X-Total-Count` (the *unpaged* total, so a
client can page without a second request).

**Three defects were mine, and only the tests caught them:**

1. `X-Total-Count` set before `send_response` landed in the header buffer
   *ahead of the status line*, and the client read `X-Total-Count: 12` as the
   HTTP status. Fixed by giving `_send` an explicit extra-header slot rather
   than letting a caller call `send_header` too early.
2. `limit=0` collided with the "unpaged" sentinel and silently meant
   "unpaged" instead of being the bad value it is.
3. `offset` on its own did nothing, because the slice was gated on `limit`.
   A caller asking for "everything after row 10" got everything.

**Red-first:** `tests/test_audit_d3_pagination.py`, 14 tests — **11 failures +
3 errors** before, 14/14 after.

## 2026-10-05 — D3-8: a parameter that cannot be used is a 400

**[SPEC]** Closed @docs/24 §D3-8. Both shapes reproduced on the live server
first, and the scope half was worse than the audit recorded.

**Numerics and windows.** `?limit=abc` answered `200` with 50 rows;
`?window=bogus` answered `200` with Claude's window. A client could not tell
its request had been ignored. `_int_param()` and `_window_param()` now raise a
clean `StoreError` naming the parameter and the valid choices.

One subtlety worth recording: the guard matches `^[0-9]+$` rather than
calling `int()`, because `int(" 5 ")`, `int("1_0")` and `int("١٢٣")` **all
succeed** — accepting them silently is the same defect in smaller clothes.

**A second, quieter defect fell out of writing the test.** `?limit=` was still
answered `200`, and so was `?limit=%20`. The cause was not the validator:
`urllib.parse.parse_qs` **drops blank values by default**, so `?limit=` and an
absent `limit` were literally the same dictionary. All five query-string parse
sites now pass `keep_blank_values=True`. That is a broader change than the fix
itself, which is why it is called out here and why the full 991-test suite was
re-run rather than only the new tests.

**Scopes.** `/api/sync` validated nothing:

```text
to_scopes: [123]     -> 200 {"skipped": [{"scope": 123, "reason": "unknown scope"}]}
to_scopes: "global"  -> 200 {"skipped": [{"scope": "g", ...}, {"scope": "l", ...},
                                         {"scope": "o", ...}, {"scope": "b", ...},
                                         {"scope": "a", ...}, {"scope": "l", ...}]}
```

The second is the one worth remembering: a **string where a list was expected**
was iterated character by character, so a client that sent `"global"` got six
"unknown scope" entries and a success status. `_scope_list()` is now shared by
`/api/sync` and the batch plan. A *well-formed* scope id that does not exist is
still reported in `skipped` — that is an answer, not a malformed request.

**Red-first:** `tests/test_audit_d3_parameter_coercion.py`, 15 tests — **16
failures + 1 error** before, 15/15 after. One of the 15 was my test being wrong
rather than the code: it interpolated raw Arabic-Indic digits into a URL
unencoded, which is a test bug, so the value is now percent-encoded.

## 2026-10-05 — A generic agent manual arrived; one part was adopted, the rest was not

**[NOTE]** `AGENTS-1.md` (repo root) is a **template for a multi-tenant SaaS
product** — TypeScript/Next.js/Postgres/Redis/Kubernetes defaults, a
signup→payment lifecycle, billing/GTM/legal phases, and `<<PLACEHOLDERS>>`
still unfilled. It is not written for this project, and most of it does not
apply. Recorded here so a future session does not helpfully "modernise" this
codebase to match it.

**Adopted** — the parts that are non-conflicting and that this session proved
worth their cost, folded into `AGENTS.md`:

- **§9.3's hostile self-review checklist**, made a standing gate before
  declaring done. This is not decorative: run against `cfdf56a`/`b258c23` it
  found **six** defects in code that had already passed 937 tests and every
  gate — a `GET /api/history` answering HTTP 500 with `no such table: history`,
  a write path still emitting the interpreter text the fix promised to remove,
  two routes answering 200 beside four answering 404, `Path.exists()` making a
  dangling symlink read as an empty library, a `doctor()["repair"]` field with
  no reader, and a `_coalesced_read` that leaked its in-flight entry on
  `KeyboardInterrupt` so one Ctrl-C permanently wedged that endpoint.
- **§4.2's inner build loop with an escalation rule** (max 5 attempts; change
  approach after 2) and **§4.5's stuck protocol**.
- **§1's "you never hide uncertainty"** — already in force; kept explicit.

**Deliberately not adopted**, because each would break something this repo
holds on purpose:

| Template says | This repo | Why |
|---|---|---|
| §7 TypeScript/Next.js/Postgres/Redis, shadcn/ui | stdlib-only Python + SQLite index, vendored Vue, no build step | Locked constraints 3 and 4. §7 itself says "override only via ADR". |
| §6 SaaS lifecycle (billing, orgs, tenancy, RLS) | a single-developer local tool | Not this product. |
| §12 `docs/PROJECT_STATE.md`, `DECISIONS.md`, `ROADMAP.md`, `LESSONS.md` | `AGENTS.md` + `docs/SESSION-CONTEXT.md` + `docs/ADR-*` + `task.md` + `docs/06-progress-log.md` | Equivalent records exist and are enforced by `check_docs.py`; renaming would break every `@docs/` pointer. |
| §8 "never commit to `main` directly" | commits land on `main` | A workflow change is the owner's call, not a side effect of adding a file. |
| §13 command placeholders | the verification loop in @docs/SESSION-CONTEXT.md | The real commands are already written down and true. |

**Not restructured:** `AGENTS.md` is deliberately a small router-style hot cache
— docs/24 §C1 calls this repository "the pathological case its own hygiene
report diagnoses", because `docs/06-progress-log.md` alone is ~45,700 tokens.
The adopted rules went into `AGENTS.md`'s existing "Judgment boundaries"
section rather than replacing it with a 523-line manual.

## 2026-10-05 — D3-5: an unsafe upload part no longer vanishes

**[SPEC]** Closed @docs/24 §D3-5. Reproduced on the live `PUT /api/import`
route first, and the measured behaviour was worse than the audit recorded:

```text
safe + parent-traversal + absolute  -> 200 {"imported": ["good"], "skipped": []}
only unsafe parts                  -> 200 {"imported": [], "skipped": []}
```

Two parts the client sent and the user expected were simply **gone**, and the
payload claimed `skipped: []` — which reads as "everything you sent was
processed". The second shape is silent data loss with a success status: nothing
installed, nothing reported, no route back.

- **An unsafe part rejects the whole upload.** `web_upload._plan_staging()`
  judges every part's path *before* anything is written, so a rejected upload
  installs nothing and leaves no staging tree. Absolute paths, `..` segments,
  backslash separators and NUL bytes each answer `400` naming the part the
  client sent and the reason.
- **One predicate for both upload paths.** `staged_single_skill` (the
  review-first source-update upload) already **raised** for exactly these
  conditions while `upload_folder` skipped the part — the two upload paths had
  drifted into disagreeing about the same input. Both now share
  `_unsafe_part_reason()`, and a test pins that they agree.
- **The SEC-6 name-conflict contract needed care here.** `_stage_path()`
  detects "one name is both a file and a directory" by *looking at the
  filesystem*, so it only worked mid-write. Putting a decision pass in front of
  the writes silently disabled it — the two `test_audit_batch5_contracts`
  regressions caught it, which is exactly what they exist for. The conflict is
  now derived from the upload itself (a staged path is a prefix of, or prefixed
  by, another) so both part orders are rejected before any write, and
  `_stage_path`'s filesystem check remains as a second line.

**Red-first:** `tests/test_audit_d3_upload_safety.py`, 14 tests — **13 failures**
before, 14/14 after. One of those 14 was *my* test being wrong rather than the
code: the error message renders the client-controlled filename with `repr()`, so
a backslash shows doubled, and the assertion now matches that deliberately
rather than the product being weakened to satisfy a test.

## 2026-10-05 — D3-4: a read no longer creates, repairs, or hides

**[SPEC]** Closed the first half of @docs/24 §D3-4. Both halves were
**reproduced before anything was changed**, on a real loopback server with an
isolated data root:

```text
one GET /api/skills on a data directory that did not exist  ->  200 []
  ... which then existed, holding four directories and a 32 KB SQLite file
```

and, with `<data>/skills` replaced by a regular file:

```text
GET /api/skills   -> 400 {"error": "cannot create directory below non-directory …"}
GET /api/stats    -> 400 (same)
GET /api/doctor   -> 400 (same)
GET /api/search   -> 400 (same)
GET /api/scopes   -> 200          <-- the UI was half-broken
GET /api/trash    -> 200          <-- and half of it looked healthy
```

The second shape is the worse one: nothing the caller sent caused it, and the
message was the interpreter's `mkdir_private` text naming an internal path,
with no repair step.

- **Reads create nothing.** `Store.list/get/search/stats/history/doctor` no
  longer call the write path's `_init_db()`. They go through
  `_index_rows()`, one seam that opens the index *without* creating the data
  layout, the database file, or the schema — `sqlite3.connect` writes a file the
  moment it is handed a path that does not exist, so the file is probed first.
  A store with no index reads exactly like a store with no skills, which is what
  the filesystem says too; the next write bootstraps it as it always did.
- **A lost index is reported, not silently repaired.** `doctor()` is where a
  deleted index is *found*, so repairing it there would defeat the tool. It now
  reports `db_integrity: "unindexed"`, `db_rows: 0`, every scanned directory as
  an orphan, `ok: false`, and a `repair` line naming `skills-mgr db rebuild` —
  and notes the skills are still on disk.
- **A damaged layout is named and repairable.** New `StoreLayoutError`
  (a `StoreError` with `status = 404`, routed by the web layer's existing
  status attribute) names the path, what it is instead of, and the exact
  `mv <path> <path>.broken` repair. Every affected route answers the **same**
  404 with the same body, instead of four 400s beside two 200s.

**Red-first:** `tests/test_audit_d3_read_purity.py`, 12 tests. Proved against
the pre-fix tree with **only the new exception name shimmed in** so the module
could import — **6 failures + 6 errors** before, 12/12 after. The failures are
individually meaningful: the read that created the layout, the read that created
the index, the mixed 400/200 status set, and the leaked interpreter text each
fail on their own assertion.

**One existing test asserted the mechanism, not the property.**
`test_concurrent_first_reads_bootstrap_schema_once` pinned
`bootstrap.call_count == 1`. The bug it was written for was real — repeated
schema writes turned a read into a SQLite writer — but "once" was the mechanism.
It now asserts `0` schema bootstraps **and** `0` `_ensure_store_dirs` calls,
which satisfies the same contention concern more strongly and is what D3-4
requires. The fan-in half of that contract is unchanged and still asserted.

**Two test suites were not hermetic, and that made CI red for a wrong reason.**
The first full-suite run after this work reported two errors that passed in
isolation. They were not flaky — they were **non-hermetic**. `WebAppServer`
binds a `Store`, but every scope-aware route still reads the *real* agent scope
roots through `scopes.known_scopes()`:

```text
/home/uday-varmora/.claude/skills      328      ~/.gemini/skills      450
/home/uday-varmora/.codex/skills       177      ~/.commandcode/skills   59
/home/uday-varmora/.config/opencode    519 r    ~/.agents/skills      120 r
                                                     list_all(): 1,965 rows, 3.7 s
```

`r` = recursive. `/api/stats` scans all of it, so on a loaded machine it
exceeded the 10 s client timeout in `urlopen` and the request raised instead of
returning — twice, in two different suites. `tests/test_audit_d3_read_purity.py`
and the pre-existing `tests/test_web_client_contracts.py` now isolate `HOME` as
well as `SKILLS_MANAGER_DATA`; the latter went from a multi-second class to
**15 tests in 0.65 s** and the former to **12 tests in 1.4 s**. This is the same
hazard `smoke_web.py` already documents, fixed per-class.

**[NOTE] The measurement above is itself an open D1 finding.** `scopes.list_all()`
— the default Library view — re-reads and re-parses **every document in every
agent scope** on each request, with no observation reuse at all. 3.7 s at 1,965
real skills is the same O(n) full-document-parse cost the D1 work removed from
the *global* half, and it is untouched by it: agent-scope rows go through
`loader.scan_dir` → `load_skill` per row, not through `_observe_index_row`.
Recorded in `task.md` as the next D1 step rather than started here.

## 2026-10-04 — D1: the primary read path, measured before and after

**[SPEC]** Executed the pure-latency half of @docs/24 §D1. The profile the audit
published was re-measured on this machine first, and it matched: at 1,200
synthetic skills, `Store.list()` spent **81% of its time inside
`_observe_index_row`**, of which the document read was 54%, a per-row
`contained_path` 24%, and a per-row `read_provenance` 21%.

Four costs were removed. **None of them had a behavioural contract behind it**,
and each is pinned by a red-first regression in
`tests/test_audit_d1_read_path.py` (15 tests; against the pre-fix source:
**4 failures + 9 errors**, all 15 green after):

- **The shared-read fan-in copied its result twice.** `_coalesced_read` stored
  `copy.deepcopy(func())` into the flight and then returned
  `copy.deepcopy(result)`. The first copy exists so a *waiting* caller never
  shares objects with the producer; the producer's own return copy is a second
  full traversal of every row that no other caller can reach. One copy now, and
  the "every caller gets an independent copy" property is still tested.
- **The skills root was resolved once per row.** `contained_path` resolves both
  `root` and the candidate, so a scan re-resolved the same root 1,200 times.
  `path_safety.contained_path_under()` / `safe_skill_path_under()` take an
  already-resolved root — the resolved counterpart of the existing
  `contained_entry_under`. `resolve()` was also swapped for `os.path.realpath`,
  which resolves the same links without pathlib rebuilding every component
  first; `contained_entry_under` already resolved that way.
- **The provenance sidecar probe walked the whole ancestry to guard a file that
  was usually absent.** `read_provenance` ran `_reject_symlink_ancestors` — one
  `lstat` per component from the skill directory to `/` — *before* checking
  `lexists`. A library where nothing came from the registry paid that walk for
  every skill, on every read. The existence probe now comes first; **when the
  sidecar is present the guard still runs first and unchanged**, and both
  directions are tested.
- **The default Library view read every global document twice.**
  `scopes.scan_scope("global")` enriched index rows with a token estimate by
  opening `SKILL.md` and re-running `tokens.estimate` — work the row's own
  loader pass had already done for the same bytes and thrown away. The four
  token fields are now carried through the observation pass, and the enrichment
  fallback only runs for a row the loader could not read.

**Measured, interleaved A/B at 1,200 skills** (three alternating post/pre rounds;
a single before/after pair was **not** used — it showed no change at all, and
the interleaved run showed −34%, which is the honest instrument on a noisy
box):

| operation | pre (ms) | post (ms) | change |
|---|---|---|---|
| `Store.list()` | 728.6 | 481.7 | **−33.9%** |
| `scopes.list_all()` *(the default Library view)* | 1279.4 | 771.1 | **−39.7%** |
| `Store.doctor()` | 758.2 | 634.6 | −16.3% |
| `Store.search()` | 35.1 | 21.5 | −38.7% |
| `Store.stats()` | 75.1 | 69.8 | −7.1% |

The complexity ratchet caught my own +1 on `_observe_index_row` and the breach
was **restored by refactoring** (`_mark_unaddressable_row`,
`_observed_skill_path`), not by editing `complexity-baseline.json`. The one
existing test that broke did so for a real reason: the coalescing contract test
pinned the private method's arity, which the hoisted-root parameter changed;
the wrapper now accepts whatever arity it is called with.

**[NOTE] What was deliberately not done.** The audit's D1 item 1 — *make the
observations lazy* — is **not** an optimisation, it is a public-contract change:
the `malformed` / `decode_error` / `addressable` signals that the Overview's
attention queue, Doctor, hygiene and `effective.explain` all read come out of
that document read. Dropping it would silently remove user-visible drift
reporting to buy latency, and adding a way to fetch observations on demand would
be a new `Store` method, which is locked-constraint 5. It is recorded in
`task.md` as a decision for the maintainer, not a silent omission. The measured
headroom that remains is exactly that read: `load_skill` is 57% of the remaining
`list()` cost, and there is no cheaper way to learn whether a document is
malformed than reading it.

## 2026-10-04 — Audit remediation day 1 and week 1 (docs/24)

**[SPEC]** Worked @docs/24-verified-findings-and-competitive-recommendations-2026-10-04.md.
Every claim marked **[VERIFIED]** below was re-measured directly rather than
taken on trust; three places where the delegated claim was wrong are recorded as
such. **`main` is green for the first time since 2026-09-16** — all 15 CI jobs
pass, including the four that had been skipped on every run since the purge test
went red (`browser smoke`, `package + release-artifact check`, `docs
consistency`, `adversarial security checks`).

- **A1 — CI was red on `main` for 7 days and four gates were off.** The purge
  test asserted one of two *both-correct* branches of `_purge_skill`, chosen by
  the order `shutil.rmtree` enumerates entries. Replaced with the invariant
  ("a skill is never advertised once its document is gone") plus branch-consistent
  `get()`/`doctor()` assertions. Verified order-independent by executing the real
  test source under **10** different restricted-directory names, both branches
  exercised. Red-first: with `bin`, the old `== []` assertion fails.
- **A9 — the whole registry integration was returning HTTP 401 in production.**
  skills.sh moved its read API behind Vercel-project OIDC; a binary on a laptop
  cannot mint a token, so `--browse`/`--search`/`--curated` **and the entire
  `--fetch` install path** were dead. Repointed search to the public
  `/api/search` and fetch/detail to the public `/api/download`, and proved the
  full trust-gated cycle works end to end again (fetch → review id → explicit
  commit → 12 files installed → provenance sidecar → replay refused).
  **This extends the audit**: browse and curated have *no* public equivalent, and
  the download route's `hash` does **not** match our `registry_snapshot_hash`
  (10 candidate algorithms checked against a live payload, none match). The
  upstream hash is therefore carried as `upstream_hash` with
  `upstream_hash_verified: false` rather than asserted; integrity rests on the
  manager's own framed `snapshot_hash`.
- **A2 — locking docs were wrong in the authoritative file.** `docs/01-architecture.md`
  still described in-process `threading.RLock` with `STORE-11`/`SEC-12` OPEN; the
  code uses an advisory cross-process `flock`/`msvcrt` lock. Corrected, plus three
  stale code comments. **The audit also claimed `AGENTS.md` carried the same
  stale claim — it does not** (72 lines, no locking section); only
  `docs/01-architecture.md` was affected.
- **A3 — a pre-existing `0775` data root was permanently unusable with no
  remediation.** Added a guarded repair that tightens to `0o700` only when the
  directory is owner-held, has an acceptable parent chain, and is recognisably
  this tool's data, plus an error that names the exact `chmod` command. It can
  only reduce access. Two red-first regressions, including the upgrade path SEC-19
  never pinned.
- **A4 — the complexity ratchet measured a 160-line adapter.** `cli.py` became
  one in the 2026-09-09 CLI split, leaving 2,076 lines of `cli_handlers.py` /
  `cli_parser.py` unguarded and **43 of 169** baseline entries (25%) resolving
  to nothing. Targets now cover 16 modules: **261 → 631 functions,
  4,750 → ~13,000 LOC**. A baseline key that no longer resolves is now a hard
  failure rather than a silently dropped guard (proved by injecting a stale key).
- **A5 — agent-scope `toggle_skill` did check-then-rename with no lock** while
  `edit_skill` and `restore_snapshot` both took `_mutation_lock`. Now wrapped.
- **A6 — the update commit and `Store.edit` took disjoint locks**, so an edit
  landing between the target-hash revalidation and the atomic swap was silently
  overwritten. The index lock is now held across the whole window, outermost and
  index-first. The review's `committed` status write stays *inside* the review
  lock — releasing it first broke single-use, caught by an existing test.
- **A7 — `renderMarkdown`/`esc` were stubbed at 8 sites and executed by no test.**
  Three tests now run the real renderer over 17 hostile payloads in a Node `vm`,
  asserting on emitted tags rather than substrings (escaped text legitimately
  contains `onerror`; `div` is the renderer's own table wrapper). Two mutations
  confirmed to fail the suite. **The first payload set was itself wrong**: a bare
  `javascript:alert(1)` cannot match a link pattern requiring `//`, so it proved
  nothing.
- **UI (audit §E/G1–G3).** `--s3` was used 13 times and defined *nowhere* — the
  stylesheet's only undefined custom property, so eight components rendered with
  no intended spacing. Reduced motion forced `animation-duration` but not
  `animation-iteration-count`, leaving two `infinite` animations strobing.
  `--border-strong` — the *only* boundary on `.form-field` inputs — measured
  1.62:1 light / 2.06:1 dark, a WCAG 1.4.11 failure in both themes; now 3.26:1 /
  3.43:1. `--border` (88 uses, decorative containers) was deliberately left
  alone. Plus the anchor-colour, `label-content-name-mismatch` (WCAG 2.5.3), and
  trash-purge labelling/placement fixes.
- **CI browser job.** It had been skipped so long that its first real execution
  died at `ZygoteHostImpl::Init()`. Chrome reported "No usable sandbox!"
  (Ubuntu 24.04 AppArmor). Chrome's own message offers `--no-sandbox`, but the
  harness keeps the renderer sandbox on by design (SEC-15, pinned by test), so the
  runner's user namespaces were re-enabled instead. That exposed a second latent
  failure: `setup-node` extracts with mode 0777, which `launcher_security`
  correctly rejects — fixed by tightening the runner, not the policy. The harness
  now reports *which* check rejected an executable.

**[NOTE] One audit recommendation was reverted after measuring it.** G2 #5
("Show scope controls" → "Filters and scopes") rests on the claim that the
disclosure holds filters. It does not: `#compact-controls` contains agent scopes
and the context budget only, while the All/Active/Disabled chips live in a
separate `.filters` block. A pinned test encodes the original label as a
deliberate decision, so the label stands.

**[NOTE] Not done, deliberately.** Dark-theme pane separation (G2 #7) and the
structural UI changes (G8) are visual decisions that need rendered review, not a
diff. Publishing 1.0.2 still requires maintainer approval. The audit's
`[AGENT]`-marked competitive figures were not re-verified.

## 2026-09-23 — Final next-five candidate verification

- The current worktree passed 888 unittest tests, `smoke_store.py`,
  `smoke_web.py`, `check_docs.py`, `check_complexity.py` (261 tracked
  functions), the narrow Ruff 0.16.8 gate, Python compilation, three Node
  syntax checks, package-data checks, and `git diff --check`.
- The six-viewport browser harness and scope-failure, inventory-failure,
  unavailable-root, and empty scenarios passed with no console/runtime errors,
  warnings, failed requests, or overflow. Its populated checks observed both
  malformed/unaddressable and divergent attention items.
- The isolated wheel smoke and artifact metadata checks passed for the exact
  `1.0.2` wheel/sdist hashes recorded below. The candidate is still uncommitted
  and unpublished; the protected release review and maintainer approval are
  not represented as complete.

## 2026-09-23 — First-scan journey and management-skill example

- Added a populated and empty first-scan guide using existing scan, Doctor,
  Quality, Library, and update-preview routes. Six responsive viewports and
  four synthetic failure/empty scenarios passed; the populated fixture also
  asserted malformed/unaddressable and divergent-copy attention evidence.
  Synthetic settled-scan time was 955 ms median. No human usability result
  is claimed.
- Added an opt-in `examples/skills-manager-management/` skill with exact-scope
  evidence handling, read-only inventory, dry-run/preview gates, explicit
  approval before writes, recovery checks, and manual installation/removal
  instructions.
- Added isolated CLI contracts for inventory/validation/explanation,
  install dry-run, non-mutating target/candidate preview, ambiguous and unavailable
  targets, unknown scope, missing target, and stale-review refusal. The
  example validator passed with no errors or warnings.
- Updated `task.md`, @docs/16-product-baseline-2026-09-18.md,
  @docs/22-next-five-task-execution-plan-2026-09-23.md, and CHANGELOG.md. No
  CLI/API/Store surface or database schema changed.

## 2026-09-23 — Package release candidate selected

- Rechecked PyPI and repository tags: published version/tag is `1.0.1` and
  the next unused candidate is `1.0.2`. Updated the project package version
  and confirmed README installation wording reflects the existing PyPI
  distribution.
- The pinned, hash-verified build passed package-data checks. Wheel
  `skill_control_plane-1.0.2-py3-none-any.whl` SHA-256 is
  `2d7beb9ba9545e38384da0ace95f2f64ba3c1ff750a225053fb641ecb7f25de8`; sdist
  `skill_control_plane-1.0.2.tar.gz` SHA-256 is
  `3e8aa27a9a3d3e8b0cda395490a57217bbe598ff6c0c9687cbd73c3a6635311c`. Both
  declare version 1.0.2 and `License-Expression: MIT`. A clean no-dependency
  install passed CLI CRUD/validation and local web asset/API smoke checks.
- The candidate remains an uncommitted worktree based on `6733da9`; no tag,
  upload, GitHub Release, or external publication was performed. The exact
  commit and artifact hashes still require maintainer review and approval.

## 2026-09-23 — Full-inventory baseline refresh

- Extended `baseline_harness.py` with intentionally invoked 100/1,000/10,000
  actual-file inventories, five startup-critical REST routes, cold and warm
  policies, ordered samples, cleanup/size/runtime bounds, and nearest-rank
  p95. A reported p95 now requires 20 successful samples; a request does not
  start unless its full timeout fits inside the remaining runtime budget.
- The 100 and 1,000 runs completed 20 samples per mode and route. The 10,000
  fixture contained exactly 10,000 files, but the 900-second budget ended
  after 20 cold scopes/list/stats samples and 11 cold Doctor samples;
  remaining Doctor/Hygiene and all warm samples are explicitly `not_run`.
- Saved all sample states in `benchmarks/full-inventory-2026-09-23.json` and
  refreshed @docs/16-product-baseline-2026-09-18.md with timings, the route
  bottleneck, a proposed one-hour evidence budget, and its non-SLO status.
  This is synthetic evidence; no human usability result or performance pass
  is claimed.

## 2026-09-23 — Dependabot Actions PR triage

- Refreshed open PR state, exact proposed commits, workflow use sites, release
  metadata, and CI logs for PRs #15–#19. Added the per-PR evidence and
  recommendations in @docs/23-github-actions-dependency-pr-review-2026-09-23.md.
- Recommended request changes for all five. PRs #15–#18 target Node 24 but
  retain stale adjacent version comments; #15/#16 also fail the repository's
  full-SHA contract test. PR #19 points to v2.4.0, whose nested
  `actions/attest` still declares Node 20 on the removal date.
- The current `main` run fails the purge regression on Python 3.10/3.11; the
  local Python 3.11.15 focused run passed and its cause remains unresolved.
  No external review/comment, workflow pin change, or merge was made.

## 2026-09-23 — Next five audit-derived tasks planned

**[NOTE]** Reconciled @docs/18-project-improvement-audit-2026-09-22.md with
`main` at `6733da9` and the existing uncommitted public-onboarding edits.
Registered @docs/22-next-five-task-execution-plan-2026-09-23.md and queued
five bounded tasks: action-update PR triage, a metadata-corrected package
release, 100/1,000/10,000 full-inventory measurements, a guided first-run
scan, and an opt-in agent-facing management skill. Existing P0 code fixes,
local source update, and read-only hygiene are not re-planned. The plan does
not merge a PR, publish a release, or claim participant evidence.
`check_docs.py` and `git diff --check` passed for this planning slice; no
product source, CLI/API contract, or package version changed.

## 2026-09-23 — Public onboarding copy and current-build image

- Replaced the README's unsupported category-ownership and single-target
  comparison with a current, linked description of Vercel's multi-agent
  installer/updater and this project's local inspection, review, and recovery
  workflow. The local-candidate-only update boundary is explicit.
- Captured the README overview image from commit `6733da9` at 1280 × 900 with
  synthetic browser-harness fixtures. The six-viewport harness passed with no
  console errors, failed requests, or horizontal overflow.
- Clarified the contributor issue route and draft-PR fallback while preserving
  maintainer approval for locked changes. GitHub issues were enabled at review
  time; five Dependabot GitHub Actions PRs were open and remain for separate
  review. No package release or participant session is claimed.
