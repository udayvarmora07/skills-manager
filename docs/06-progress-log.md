# Progress Log — Skills Manager

**Version 0.6.0**

**AI manifest**: Dated record of changes, decisions, and bugs for skills-manager,
newest entry on top. **Since 2026-10-05 this file is a digest plus the entries
dated 2026-09-23 and later; everything older lives verbatim in
@docs/archive/README.md.** Read the digest below first — it is the part a session
actually needs. Facts flagged stale here are corrected in the owning doc.

## 2026-11-13 — Overnight round 4: skills-dir plugins, OpenCode autoinvoke conflicts

**[SPEC]** Two read-only hygiene additions from
@docs/44-overnight-user-problems-2026-11-13.md §6. No new command, route, Store
method, schema or dependency:

- **`plugin-member-skill` and `skills_dir_plugins`** (vercel-labs/skills#2609).
  Claude Code loads a skills-directory folder holding
  `.claude-plugin/plugin.json` as `<name>@skills-dir` (code.claude.com skills
  and plugin-loading pages, read 2026-11-13). A skill at
  `<folder>/skills/<skill>/` beside such a manifest gets an info finding,
  because copying it alone with `sync` or `npx skills add` drops the plugin.
  For `claude-code`/`all`, a section lists `~/.claude/skills` plugin folders,
  including ones with no root `SKILL.md` that this tool's scan never lists.
  CLI text adds one line.
- **`opencode-autoinvoke-conflict`** (sst/opencode#52747, merged 2026-10-02).
  OpenCode honours `disable-model-invocation`, but an explicit
  `metadata.opencode/autoinvoke` wins. When the two disagree, one agent
  offers the skill and the other hides it, so the report raises a warning.

**[NOTE]** Red-first: 13 new tests; 6 of the first 10 fail on `f4d136f`, and
the rest are guards. Self-review added three hostile-input tests, which caught
two bugs: a 60,000-deep `[` manifest raised `RecursionError` through the
report, and an unresolvable home raised `RuntimeError`. Manifests are read
only as regular files (no symlink, no FIFO, 64 KiB). Real data, read-only: one
plugin (`humanizer`, with a root document), no member skills, no conflicts.
**Not verified:** Claude Code or OpenCode loading the fixtures; whether Claude
Code follows a symlinked plugin folder; plugin skills in the `claude_listing`
estimate; a browser render of v2 Quality (no UI code changed).

**[NOTE] Verification on the rebased tree (on `300e3d7`):** 1,958 tests on each
of Python 3.11, 3.12, 3.13 and 3.14 (two optional oracle skips each); both
smokes, `check_docs`, `check_complexity` (1,295 functions, nothing raised),
`check_design_tokens`, `node --check`, Ruff 0.16.8 (F821/F822/F823) and Bandit
1.9.4 (0 results).

## 2026-11-13 — Overnight round 3: A6 risk-finding explainer

**[SPEC]** A6 shipped (@docs/44-overnight-user-problems-2026-11-13.md §5):
`ai_explain.py`, `POST /api/ai/explain-findings` and v2 Tools → Explain risk
findings. `risk_scan` runs first without AI over one installed skill and its
bounded file listing; the model then gives one opinion per finding. Opinions
sit beside unchanged findings. A false-positive opinion must quote text found
in the named file or it becomes `unclear`; opinions on unknown or repeated
indexes are dropped. No findings means no call; estimate sends nothing; skill
text goes through `ai.untrusted_block`. No CLI command, Store method, schema
or dependency was added. The OpenCode `disable-model-invocation` candidate
was dropped because upstream fixed it (opencode #52747).

**[NOTE]** Red-first: the 3 new or changed tests in `tests/test_ai_features.py`
fail on `f4d136f`. Browser, isolated HOME, fake provider: estimate then send
showed the cited opinion, the uncited claim as "No clear opinion", the `high`
finding unchanged, no overflow at 390 px and no console errors.
`ai_explain.py` joined the complexity targets (1,285 functions, nothing
raised). **Not verified:** any real provider; a hostile skill can steer the
opinion, and the quote check only proves the text exists.

**[NOTE] Verification on this tree:** 1,945 tests on each Python 3.11, 3.12,
3.13 and 3.14 (two optional oracle skips each); both smokes, `check_docs`,
`check_complexity`, `check_design_tokens`, frontend syntax, Ruff 0.16.8
(F821/F822/F823) and Bandit 1.9.4 (0 results).

## 2026-11-13 — Overnight round 2: Codex listing budget, OpenCode truncation

**[SPEC]** Two read-only hygiene additions from
@docs/44-overnight-user-problems-2026-11-13.md, no new command, route, Store
method, schema or dependency:

- **`codex_listing`** (openai/codex#19679). Codex's renderer was read in
  `codex-rs/ext/skills/src/render.rs`: 2% of the window in tokens, lines
  `- name: description (file: path)`, descriptions cut at 1,024 characters,
  `ceil(bytes / 4)` tokens per line. Applied to enabled `~/.agents/skills`
  instances (file- and config-disabled excluded); one `codex-listing-budget`
  info finding when over. A non-GPT report window becomes an assumed `gpt-5.6`
  window and the basis says so. CLI prints one summary line.
- **`opencode-output-truncation`** (sst/opencode#62718). OpenCode keeps only
  the first 2,000 lines / 50 KiB of a tool result. Enabled instances in
  `opencode`, `agents` or `claude-code` scopes over either limit get one
  warning. Only near-limit documents are opened, through
  `file_reads.read_regular_file` (8 MiB bound), so a FIFO named `SKILL.md`
  cannot block the report; self-review caught the first draft using plain
  `open()`.

**[NOTE]** Red-first: 11 new tests, 10 fail on `d189f66` (the other is a
guard). Real data, read-only: 153 skills ≈ 14,640 Codex tokens (within the
assumed 21,000; over 8,000 at a 400k window); one 57 KiB skill flagged for
OpenCode. **Not verified:** Codex or OpenCode reading the fixtures; Codex's
project/admin/bundled roots and a configured token budget are unread, so the
estimate is `partial`; the v2 Quality page was not re-rendered (the findings
use its generic finding layout).

**[NOTE] Verification on this tree:** 1,943 tests on each Python 3.11, 3.12,
3.13 and 3.14 (two optional oracle skips each); both smokes, `check_docs`,
`check_complexity` (1,277 functions, nothing raised), `check_design_tokens`,
frontend syntax, Ruff 0.16.8 (F821/F822/F823) and Bandit 1.9.4 (0 results).

## 2026-11-13 — Overnight round 1: problems users hit that a local check can name

**[NOTE]** An unattended round researched skill-management problems reported
since 2026-10-01 (GitHub issues across six agent repositories; HN fetch failed,
search rate-limited). Ranked record and later-round candidates:
@docs/44-overnight-user-problems-2026-11-13.md.

**[SPEC]** Shipped, all read-only or transport-only, no new command, Store
method, schema or dependency:

- **Byte-order mark lint** (openai/codex#13918). Codex skips a document whose
  `---` follows U+FEFF; this tool's parser strips it, so the skill looked
  valid here. One advisory `frontmatter` warning now says so.
- **`agent-parse-risk` hygiene finding.** The hygiene report surfaced only
  validator errors, so the empty-block, unquoted-colon and BOM warnings never
  reached Doctor or Quality. They now do, one warning per instance.
- **Codex dead `[[skills.config]]` path entries** (openai/codex#51044). A
  `path` naming the skill folder, a missing file or a non-`SKILL.md` file
  matches nothing, so the user's "disabled" never applies. A `codex_config`
  section and `codex-config-dead-entry` warning (scopes `codex`/`all`) name
  each entry and the `SKILL.md` path to use; CLI text and v2 Quality list them.
- **OpenRouter caching for Claude.** `anthropic/` models on OpenRouter now
  get the listing prefix as a `cache_control` block (OpenRouter caches Claude
  only with explicit breakpoints); other models are unchanged.

**[NOTE]** Red-first: 19 new tests (10 Codex config incl. CLI text, 4 BOM,
3 OpenRouter, 2 parse-risk); 14 fail on `302caf2` and all pass now, the other
5 are guards that pass on both. Complexity: new functions only, one +1 restored by extracting
`_warn_byte_order_mark`; no baseline raised. Browser: v2 Quality against an
isolated HOME showed the Codex entry with its suggested path and the BOM
skill's parse-risk warning, no console errors. **Not verified:** any live
OpenRouter call (whether `prompt_tokens` includes cached tokens is inferred
from its docs' example), Codex itself reading the fixtures, macOS/Windows.

**[NOTE] Verification on this tree:** 1,932 tests on each Python 3.11, 3.12, 3.13 and 3.14 (two optional oracle skips each); both smokes,
`check_docs`, `check_complexity` (1,269 functions, nothing raised),
`check_design_tokens`, frontend syntax, Ruff 0.16.8 (F821/F822/F823) and
Bandit 1.9.4 (0 results).

## 2026-11-13 — AI transport: retries, prompt caching, thinking room, day-cap reservations

**[SPEC]** Reviewing every shipped AI feature on `main` found that the shared
client in `skillsmgr/ai.py` had four gaps under all of them. Recorded in
@docs/39-ai-features-research-and-catalogue-2026-11-09.md §17:

- **No retries.** One 529/429/5xx ended a long run and wasted its spend. Now
  bounded retries (max 2, `retry-after` up to 20 s). Quota and spend-limit codes
  are final, per Anthropic's and OpenAI's error docs. A client disconnect during
  a wait stops the run.
- **No prompt caching.** Every routing batch re-sent the full listing (up to
  600 skills). Multi-batch passes now mark it as an Anthropic cache
  breakpoint. Anthropic's `input_tokens` excludes cached tokens, so the caps
  now add cache reads and writes back. Without that, caching would have made
  the caps undercount.
- **Thinking models could run out of answer room.** The suggested Claude 5.5
  models think by default, and that thinking counts against the same
  `max_tokens` as the answer, which is about 500 per routing batch. Recognised
  Claude and OpenAI reasoning models now get low effort plus 4,096 tokens.
  Others are sent exactly as before.
- **Concurrent runs could jointly exceed the day cap**, the gap docs/42
  recorded. Per-call reservations under the ledger lock close it. Stale entries
  expire, and a reservation that cannot be written refuses the call.

**[NOTE]** Tests came first. 23 tests are in `tests/test_ai_transport.py`, and
the fake Anthropic provider in `test_ai_features.py` now accepts block content.
Five mutations were each caught: reservations ignored, cache tokens dropped,
quota retried, no headroom, no breakpoint. The complexity ratchet only went
down, through six lowered entries; three functions were split rather than any
budget raised. The trigger-test result also shows cached tokens and retries.
**Not verified:** any live provider call, and a browser render of that one
template line (v2 contract tests and the syntax check passed). Request text and
input hashes are unchanged, so A14 fingerprints still compare.

**[NOTE] Verification on this tree:** 1,913 tests on each Python 3.11, 3.12,
3.13 and 3.14 (two optional oracle skips each); both smokes, `check_docs`,
`check_complexity` (1,264 functions, nothing raised), `check_design_tokens`,
frontend syntax, Ruff 0.16.8 (F821/F822/F823) and Bandit 1.9.4 (0 findings).

## 2026-11-12 — Health-check browser startup publication race

**[NOTE]** A fresh functional check found the classic browser launcher reading
an empty `server-url.txt` between creation and its first write, then passing `/`
to `urlopen`. A forced reader/writer interleaving reproduced the same defect
in both optional launchers. They now publish the URL with the existing
`atomic_write_text` helper; deterministic regressions failed before the change
and pass after it. Installed application behavior and runtime dependencies are
unchanged. Extended browser and full-suite verification passed as recorded below.

**[NOTE]** Default AI settings remain absent, so real product HTTP-provider
calls are unverified. Retained synthetic native evidence and fake-provider
checks remain distinct. Hosted CI for the previous main commit completed 14
jobs successfully; its macOS/Python 3.14 job was cancelled without executing
after GitHub could not acquire a runner (capacity-constraint annotations).

**[NOTE]** Verification on the changed tree: 1,891 tests on each Python
3.11–3.14, no skips with the separate reference oracle; 83 focused AI tests;
classic browser 38 scenarios / 342 assertions and v2 browser 37 scenarios with
no failures; six-viewport smoke; both Store/web smokes; compilation, all
frontend JavaScript syntax, Ruff 0.16.8, Bandit 1.9.4, docs, design contrast,
and unchanged complexity budgets. Fresh wheel/sdist from the hash-verified
build environment passed package checks and the exact installed-wheel AI
probe. Evidence is retained under the worktree Git metadata's
`codex-verification/ai-2026-11-12/health-check/` directory.

**[NOTE]** The default-data Doctor check found two filesystem/index differences.
After a SQLite backup, supported `db resync` updated two index rows; Doctor
reports healthy with database integrity `ok`. Before/after hashes prove skill
files unchanged. This repaired the derived index only. Self-review covered
partial URL publication, isolated concurrent fixture roots, startup failure
cleanup, and reuse of the atomic helper's temporary-file cleanup. No new
command, Store method, schema change, or runtime dependency was introduced.

## 2026-11-12 — Interrupted-session verification resumed

**[NOTE]** The task branch and all AI/automation changes survived the interrupted
session. Temporary verification logs did not, so final gates were rerun
against the current tree with evidence under this worktree's Git metadata
(`codex-verification/ai-2026-11-12`). No additional paid agent measurement is
needed to verify the retained synthetic study. Hosted CI and publication remain
separate from local verification.

**[NOTE] Final current-tree verification.** Python 3.11–3.14 each passed
1,889 tests with no skips, using the separate `skills-ref==0.1.1` oracle
environment. The shared AI runner passed 83 focused tests and retained-evidence
checks. Both Store/web smokes, Python compilation, frontend JavaScript syntax,
docs, design tokens, pinned Ruff 0.16.8 and Bandit 1.9.4 passed. Complexity:
1,233 measured functions across 45 files; no original budget or threshold raised.
The hash-locked build produced wheel and sdist, both passed package-data checks,
and the shared isolated installed-wheel probe passed. Exact wheel Python sources
match this tree; developer tools and study evidence are excluded from artifacts.

**[NOTE]** Hostile review was repeated against the final diff, including bounded
Unicode artifacts, missing/corrupt/incomplete observations, snapshot consistency,
credential isolation and subprocess cleanup. The inherited cross-run daily-cap
reservation gap remains documented. No broader native-fidelity claim, macOS or
Windows execution, hosted CI run, remote update, merge or release is claimed.
The native measurement remains the recorded two-case synthetic smoke study.

## 2026-11-10 — Repeat AI verification automation

**[SPEC]** `python3 tools/verify_ai.py` repeats the free AI contracts and verifies
the retained study's exact hashes, joins and agreement accounting. `--artifact
WHEEL` installs the exact wheel offline in a temporary virtual environment and
checks the installed CLI's estimate, baseline, failed regression and absence of
SQLite initialization using a fake provider. The subprocess environment excludes
ambient credentials, HOME is temporary, imports must come from the venv, and
process groups have time/output bounds and cleanup. Guide:
@docs/43-ai-verification-automation-2026-11-10.md.

**[SPEC]** Existing CI jobs share this runner: the unit matrix checks saved
evidence/no-send behavior; the package job probes the exact wheel before upload;
the pinned Ruff gate includes the new tools. Manual workflow dispatch is enabled,
superseded PR runs are cancelled, and unit/package jobs have explicit deadlines.
Read-only permissions, full-SHA action pins and hash-locked build tools remain.
No new job duplicates the full matrix. Paid native-agent runs stay attended;
ordinary CI uses fake providers/executables and no provider credentials.

**[NOTE]** The shared local command passed 83 focused tests and evidence checks;
46 CI/docs contracts passed. New fake-process regressions prove failure and
diagnostic propagation, credential isolation and timeout descendant cleanup.
Final full-matrix/artifact results are recorded in the 2026-11-12 entry above.

## 2026-11-09 — Approved A14 CLI/CI and attended fidelity smoke study

**[SPEC]** The maintainer instructed starting both remaining AI tasks, approving
the proposed minimal CLI surface under locked constraint 5. `ai trigger-test
--saved` defaults to an estimate; only `--run` sends. The JSON envelope is
versioned, listing/prompt/endpoint fingerprints and listing snapshots are saved,
and seed controls listing order rather than provider determinism. A gated run
requires complete matching baseline evidence before sending and uses that same
prompt/listing/configuration snapshot for the actual run. Comparisons recompute
integer hits/answers, include near-miss losses, and reject missing, partial,
legacy or incompatible baselines. No Store method, schema or runtime dependency
was added. Contract and CI recipe: @docs/42-ai-cli-ci-2026-11-09.md.

**[NOTE]** Review found a preflight/send race, permissive linked prompt reads,
unbounded history reads and corrupt-history fallback. Red-first regressions
now cover these; artifact reads are bounded regular files, private AI directory
links are refused, and malformed automatic-baseline candidates fail closed.
Complexity helpers reduce existing budgets; none are raised. Full-matrix checks
also updated the intentional command-inventory assertion for the approved
surface and exposed Linux returning ESRCH, as well as ENOENT, when the fake
descendant is reaped during a `/proc` status read. Both mean the process is gone;
the live-child assertion is unchanged.

**[NOTE]** Boundary review reproduced a self-produced unreadable artifact when
500 prompts or 600 full descriptions contain non-BMP Unicode: ASCII-escaped
JSON exceeds the initial 2 MiB read bound. The 16 MiB bound covers those
supported limits, rejects oversize files before allocation and caps descriptor
reads against concurrent growth. A real serialization round trip covers both
maxima. The fidelity harness also verifies new A14 listing fingerprints while
still marking the uncaptured native listing as unknown.

**[NOTE]** A present-maintainer Claude CLI smoke study observed successful Skill
events matching the simulator in both synthetic cases (2/2, no inconclusive or
multiple-load cases). It used existing native login and a CLI simulator adapter,
with project-only settings and approximate $0.10 per-call caps. It did not use
the product HTTP transport. The tiny sample does not establish normal-agent
fidelity. Method, costs, reproducible guarded script and sanitized evidence:
@docs/41-ai-fidelity-study-2026-11-09.md. Verification is recorded in this entry
and the newest automation entry.

## 2026-11-09 — Pre-push fidelity cleanup test race

**[NOTE]** The fresh Python 3.11 suite exposed a check-then-read race in the
fake-descendant cleanup test: Linux reaped the child between `exists()` and
reading `/proc/<pid>/status`. A controlled probe reproduced the failure. The
test now reads once and accepts `FileNotFoundError` as completed cleanup;
an entry that still exists must report a zombie. Production cleanup is unchanged.

## 2026-11-09 — Handoff 3.6: chore dispositions and decision handoff

**[NOTE]** Read-only GitHub/source review found Dependabot #16/#18 already
closed unmerged and superseded by merged #20. Accepted full SHA pins and node24
runtimes match fetched main and contract expectations; #20's exact head has
16 green recorded checks. Old PR heads were inspected, not rerun. No GitHub
comment/review, new hosted CI run, remote branch mutation, merge or release was
performed. Current disposition: @docs/23-github-actions-dependency-pr-review-2026-09-23.md.

**[NOTE]** Milestone-5's remaining value is historical research/test evidence;
its code is superseded, so no cherry-pick is recommended. Its remote branch
and archive tag, the backup branch with 29 commits absent fetched main, and
both old stashes were inventoried and preserved. Exact SHAs and rationale:
@docs/40-codex-handoff-2026-11-09.md. No stash was popped or archive deleted.

**[NOTE]** Section 3 agent implementation/preparation is now recorded in the
handoff. The live fidelity study still needs the present maintainer; section 5
was left untouched. A concrete minimal AI CLI/CI proposal is prepared in
section 4, without implementation, pending approval under locked constraint 5.

## 2026-11-09 — Handoff 3.5: developer fidelity harness, study pending

**[SPEC]** `tools/ai_fidelity/run.py` prepares a comparison between an existing
saved trigger simulation and successful native-agent Skill events. It defaults
to a no-subprocess dry-run; actual execution requires a present maintainer and
two explicit flags. Complete exact input matching and untied choices are
required. Failed, malformed, incomplete or resource-limited observations are
inconclusive. First-successful-choice agreement is labelled explicitly and
multiple loads disclosed; model prose is not evidence.

**[SPEC]** Time/output/case limits, POSIX process-group cleanup and approximate
native per-call budgets bound the attended operation. Raw prompts, transcripts
and stderr are omitted from reports. Native hooks/configuration can still have
side effects; this tool is not a sandbox, and missing historical listing
snapshots/restricted tool context limit any fidelity conclusion. Distribution
excludes the development harness. No real agent/provider was run, and docs/39's
unmeasured-fidelity uncertainty remains. No product CLI command, Store method,
runtime dependency or schema changed.

**[NOTE]** Thirteen fake-executable tests and a separate real script-entrypoint
dry-run passed; the latter used a nonexistent agent path and reported no
conclusive cases or measured agreement. Review added deep-JSON and malformed,
unknown, terminal-only/truncated stream guards, successful tool-result pairing,
auxiliary EndConversation handling, first-choice/multiple-load labels and
timeout/output/process-group tests. Complexity: 1,187 functions across 42
files, no baseline raised.

**[NOTE]** A temporary virtualenv installed the exact hash-locked build tools.
The pinned no-isolation build produced wheel and sdist; both passed package-data
checks, and direct archive inspection confirmed the harness is absent from
each. The wheel also passed an offline clean-install/resource probe. Nothing
was published. Native-agent hooks, source-listing equivalence and billing are
not certified by these fake-only checks.

## 2026-11-09 — Handoff 3.4: contained metadata-only profile suggestions

**[SPEC]** A12 adds `ai_profiles.py` and `POST /api/ai/suggest-profile`.
Existing project observation and server-owned managed roots precede bounded
descriptor-based enumeration. Outside paths are redacted/refused; accepted
projects contribute extension counts, known manifest names and top-level
directory names, never file contents or project paths. Readable disabled
skills can be selected; path-like description tokens are redacted, invented
names dropped and duplicates merged. Estimate mode sends nothing.

**[SPEC]** V2 shows signals/truncation and an editable named profile. Saving
fetches current catalog metadata and requires confirmation, warning explicitly
about an existing name, before using the existing catalog POST. Suggestions
never save or apply a profile automatically. No native settings, CLI commands,
Store methods, runtime dependencies or SQLite schema changed. Safe scanning
requires POSIX descriptor support; unsupported platforms receive clean errors.

**[NOTE]** Fourteen red-first tests cover root confinement over HTTP, outside
rejection before enumeration/provider calls, symlink escapes/swaps, 0/1/10,000
entries, per-directory bounds, root defaults, filesystem-only discovery,
disabled skills, 600/601 skills, no content/path leakage, malformed model
output and estimates. Browser fixture checks verified redacted outside-root
errors, no-send estimates, metadata-only provider input, dropped invented
names, confirmation dismissal preserving the old profile, explicit overwrite,
and the disabled skill staying disabled. The 390px flow had no overflow or
unexpected console errors; the intentional outside-root probe produced its
expected HTTP 403 console entry. Self-review fixed a computed-property call
and scoped inventory checks to the selected scope. Complexity: 1,162 functions
across 41 files; no baseline increased. No real provider was called.

## 2026-11-09 — Handoff 3.3: conciseness proposals through whole-tree review

**[SPEC]** A13 adds `ai_concise.py` and `POST /api/ai/concise`. Section token
counts are deterministic; model output proposes a shorter primary document
and reference files. Frontmatter and companions are preserved. Bounds,
reference paths, links and collisions are checked; the captured tree content
hash prevents a proposal from silently reverting content edits made during
model latency. Shared JSON decoding also preserves Markdown fences inside
model-returned strings, fixing corruption of code examples in AI drafts.

**[SPEC]** The v2 advisor shows computed before/after counts and counting
method, then transfers the exact target and pending review to the existing
source-update UI. Explicit reviewed commit preserves the whole-tree snapshot
and atomic update path. Generation writes no installed source; estimate mode
sends nothing and stages no review. No CLI command, Store method, runtime
dependency or schema changed.

**[NOTE]** Fourteen red-first regressions cover the fake provider, a real
source-update apply/snapshot, binary and mode preservation, disabled targets,
bounded enumeration, path/link/collision/size rejection, source-change and
cleanup failures, no-send HTTP estimate, computed counts and Markdown fence
integrity. Chromium against isolated fixture data verified estimate with no
usage/review, proposal without live changes, exact review handoff and explicit
apply (reference created, binary preserved, snapshot present), and in-app
abandonment cancellation. The 390px proposal/review flow had no observed
overflow or console warnings/errors. Complexity: 1,149 functions across 40
files; no baseline increased.

**[NOTE]** Capture needs POSIX descriptor/no-follow support and fails cleanly
where unavailable. Existing source-update live-manifest path reads and
post-review mode/empty-directory changes remain outside its proven guarantees;
the advisor rechecks captured bytes, modes and directories through staging,
but does not certify the inherited helper against hostile path swaps. No real
provider or human-only sign-off was used.

## 2026-11-09 — Handoff 3.2: verified skill drafting

**[SPEC]** A11 adds `ai_draft.py` and `POST /api/ai/draft-skill`: draft from an
untrusted brief, validate the document and limits, then measure A1 routing with
the draft added to the scope's listing. Existing-skill prompts are tested
before and after adding the draft to identify prompts it steals; the report
discloses sampled coverage. Invalid or incompletely measured drafts cannot be
used. Empty scopes are supported. Estimate mode contacts no provider.

**[SPEC]** V2 Tools → Draft a skill displays draft text, validation issues and
routing evidence. Use this draft prefills the existing New skill form and
saves nothing until its ordinary Create skill action. No CLI command, Store
method, runtime dependency or SQLite schema changed.

**[NOTE]** Seven red-first fake-provider tests cover valid and stealing drafts,
invalid names and name shapes, oversized bodies, missing routing/near-miss
coverage, empty scopes, collisions (including disabled skills, husks and
dangling links), and no-send estimates over HTTP. Browser checks against an
isolated fake provider covered valid/invalid/unverified results, the stealing
report, estimate with no usage entry, unsaved New skill prefill, and a 390px
viewport with wrapped draft text and no overflow or console warnings/errors.
Complexity: 1,130 functions across 39 measured files, no baseline raised.
Results remain model simulations; no real provider was called.

## 2026-11-09 — Handoff 3.1: AI retention, disconnects and run history

**[SPEC]** Work is isolated in `~/skills-manager-codex` on
`codex/remaining-tasks`, based on fetched `origin/main` (`03b9ad6`). The dirty
primary checkout and redesign worktree were left untouched. Usage-ledger
compaction removes dated rows older than 90 UTC days when the ledger exceeds
1 MiB; compaction and append share a mutation lock. HTTP AI calls stop between
provider requests when the client closes, saving a partial run with usage.
An in-flight provider request is allowed to finish.

**[SPEC]** Every v2 AI page now lists the latest 20 saved runs and opens details
as text. Trigger tests expose saved regression prompts with per-prompt removal.
Replacement preserves 500 entries and checks the previous list under a lock,
returning 409 for stale edits. Disconnected runs do not become regression
baselines. No CLI command, Store method, runtime dependency or schema changed.

**[NOTE]** Red-first regressions cover retention at 0, 1 and 100,000 rows,
corrupt tails, concurrent appends, inclusive UTC cutoff, stale prompt edits and
disconnects through a counting HTTP provider. Full suites: 1,807 tests on each
of Python 3.11–3.14, two optional skips each. Both smoke scripts, docs,
complexity (1,116 functions), design tokens and every shipped JavaScript syntax
check passed. Chromium checks against isolated fake-provider data covered
estimate/run/history, literal HTML-like text, duplicate-text prompts with
different expected skills, last-prompt removal, and a 390px viewport with no
overflow or console warnings/errors. Hostile review also fixed a bad Host
header in the cancellation fixture and registered fixture-local lock roots.
Partial runs intentionally store progress/cost metadata, not intermediate
model answers. No real-provider fidelity or human visual/accessibility
sign-off was performed.

## 2026-11-09 — AI assist: bring your own key, trigger test, verified rewrite

**[NOTE]** The maintainer asked for internet-wide research into BYOK AI features,
then for the best ones to be built in order. Five research passes (communities
via OpenCLI/Exa, competitors, GitHub issues by reactions, BYOK practice,
literature) agree that the pain is skills not being *selected*, and that
unverified AI rewrites or drafts do not help. Catalogue, sources and the
decisions taken for docs/33 §8: @docs/39-ai-features-research-and-catalogue-2026-11-09.md.

**[SPEC]** Shipped A0–A2. `ai.py` is a stdlib client for Anthropic and
OpenAI-compatible endpoints (including Ollama/LM Studio) with an env-first key,
a 0600 settings file, per-run/per-day token caps checked before sending,
refused redirects and a content-free usage ledger. `ai_skills.py` runs the
trigger test over an agent's real listing and proposes description rewrites
that are recommended only when they win without losing on held-out prompts.
REST: `/api/ai/*`; v2: Tools → AI assist. No CLI command, Store method, SQLite
state or dependency was added. New router guards were extracted so existing
complexity entries did not rise; `ai.py`/`ai_skills.py` joined the ratchet with
every function ≤ 15.

**[SPEC]** A3 followed: `ai_overlap.py` judges bounded candidate pairs in both
orders, reports order-dependent verdicts as uncertain, and drops quoted
conflicts that are not verbatim in the files (`POST /api/ai/overlap-judge`, v2
Overlap check). 3 more tests; browser-checked against the fake model.

**[SPEC]** A4 followed: `ai_budget.py` shortens the largest descriptions when a
listing is over budget (Claude Code's measured, others supplied) and marks a
shorter version safe only if its skill still wins as many prompts
(`POST /api/ai/fit-budget`, v2 Fit the listing budget). 3 more tests.

**[SPEC]** A5 followed: `ai_review.py` briefs a pending update or registry
review; claims must quote their file and risk opinions never change a finding
(`POST /api/ai/review-briefing`, *Explain with AI* in both review panels). 2
more tests; the panel was rendered against a real update review.

**[SPEC]** A7 followed: trigger-test prompts can be saved per scope and re-run
with `saved: true`; each skill's hit rate is compared with the previous saved
run and regressions are flagged. 2 more tests; browser-checked.

**[SPEC]** A8 followed: `ai_evals.py` runs a library skill's eval cases with
and without it and records them through the existing harness, graded only by
the case assertions; a skill that passes without itself is flagged
`not-needed`. 3 more tests; browser-checked.

**[SPEC]** A9 followed: `ai_ask.py` answers "which skill fits" from names and
descriptions only and drops invented skills (`POST /api/ai/ask`, v2 Ask your
library). 1 more test; browser-checked.

**[SPEC]** A10 followed: `ai_port.py` finds portability facts without AI and
lets the model explain only those (`POST /api/ai/porting-notes`, v2 Porting
notes). 2 more tests; browser-checked.

**[NOTE] Hostile self-review.** Found and fixed: changing only the endpoint
kept the stored key, so whoever could reach the loopback API could point the
next call, and the key, at another host. A stored key now follows neither a
provider nor an endpoint change (red test added). Checked without change: the
key never reaches a response, the ledger, run files or exports; caps refuse
before sending; responses are bounded; listing, pairs and prompts are capped
(0 skills is a clean error, more than 600 is refused); candidate and eval input
reads are contained and do not follow links; model output is never applied
without an explicit, snapshot-taking edit. Known limit: an abandoned browser
request keeps spending until its run ends, within the caps.

**[NOTE]** Final ladder on the committed tree: 1,801 tests on each of Python
3.11–3.14 (2 optional skips), both smokes, docs, complexity (every AI function
≤ 15; no pre-existing entry raised), design tokens, compilation and frontend
syntax.

**[NOTE]** Verified: 19 new tests against a fake provider; v2 contract tests;
both smokes; docs and complexity gates; a browser run of every page against the
fake model, including applying a proposal (snapshot written). Not verified: any
real provider call, and trigger-test fidelity against a real agent's routing.

## 2026-11-09 — Audited cleanup of already-merged work

**[NOTE]** The maintainer requested in-depth review and removal only after
double-checking integration. Inventory and two Terra reviews distinguish exact
main ancestry from superseded or patch-equivalent work. Dirty and active
checkouts, main and unmerged histories are preserved. A verified all-ref bundle
precedes deletion; complete checkout archives preserve ignored files and release
artifacts. Details and final results: @docs/38-worktree-cleanup-2026-11-09.md.

**[NOTE]** Removed 16 clean inactive worktrees, 2 missing temporary registrations,
21 merged local branches and 5 merged remote heads. Remote deletions used exact
expected-SHA guards and no open PRs existed. All retained/unmerged heads and main
stayed unchanged; fetch also pruned 3 already-absent remote-tracking refs.
Five worktrees and six local branches remain: dirty primary, unmerged redesign,
active shell checkout, dirty design checkout, main, plus the backup branch.
All 47 primary file fingerprints still match.

**[NOTE]** Sixteen complete archives and their manifests were byte-verified.
A reflog-inclusive bundle also preserves 19 reflog-only commits; an independent
bare restore checked all 43 distinct branch/reflog tip objects. No force local
deletion, reset, garbage collection or product-code change was used. Connectivity,
docs checks and the 1,765-test suite pass (2 optional oracle skips). Recovery
records remain private at `/home/uday-varmora/skillsmgr-cleanup-audit-d9orltgn`.

## 2026-11-09 — Main integration of the completed untangle pass

**[NOTE]** The maintainer explicitly requested pushing the completed refactor
into `main`, superseding the preceding local-only stopping point, and requested
Terra-only subagents. Fetched `origin/main` is `f323f16`, the refactor's exact
base, so integration can use a normal fast-forward. The dirty primary checkout
remains on `feat/v2-feature-parity` and is preserved with a content manifest.
Terra's read-only integration audit found no blocker and confirmed that all
new modules and restored compatibility files must be included. Fresh current-tree
verification passes 1,765 Python 3.12 tests (two optional skips), both smokes,
compilation/syntax, docs/design/complexity and pinned Ruff/Bandit checks.
Integration and the normal push are recorded in the integration section of
@docs/37-codebase-untangling-2026-11-09.md.

**[NOTE]** The complete refactor landed as `e4e100b` on `origin/main` through
an ordinary fast-forward push from `f323f16` (eight prior refactor commits plus
the completion commit). `git ls-remote` verified the exact remote SHA. Clean-tree
wheel/sdist builds and package inspection pass; integrated-main Store/HTTP
smokes also pass. All 47 recorded primary-checkout file fingerprints remain
unchanged. The primary stays on `feat/v2-feature-parity`; the recovered task
worktree now holds clean `main`. No release tag or package publication occurred.
GitHub CI is observed separately from this local verification record.

## 2026-11-09 — Codebase untangling, Codex continuation

**[NOTE]** Recovered Claude’s “Codebase untangling” session, its Comments/Tests
scope, eight existing commits and five pending frontend files. Continued in
its worktree, backed up the pending state and preserved the unrelated dirty
primary checkout. Decisions and the original inventory are in
@docs/37-codebase-untangling-2026-11-09.md.

**[SPEC]** Install, document layout, doctor/hygiene, eval recording, reviewed
batches and token-window workflows now have domain owners shared by CLI and
HTTP. Active Store binding, timestamps, read-flight sharing and bounded file
acquisition have leaf modules. V2 tool routing, listing and commands share
model metadata; escaping and JSON headers have one owner. Filesystem authority,
schema, public Store methods, application CLI, dependencies and UI framework
remain unchanged.

**[SPEC]** The continuation restores documented `insights`/CLI/key-support
exports, preserving strict legacy guards. Installer timeout responses and CLI
output limits remain compatible; malformed explicit eval-runs files cannot
silently become read-only reports. Doctor shares managed peer-link policy,
reports root-read degradation and sanitizes names in text output. Shared
regular-file acquisition bounds bytes from the checked descriptor and
preserves each parser's limits, link policy and error shape. Four duplicate
risk checks and implementation-restating comments were removed; public API
behavior coverage was restored.

**[NOTE]** Luna/Terra review found no further worthwhile structural fix.
Runtime export inspection preserves every baseline name in 17 explicit export
lists. The final unit matrix passes 1,765 tests on each Python 3.11–3.14
(two optional oracle skips per run). Both smokes, compilation/syntax, docs,
design, pinned Ruff/Bandit and complexity pass (973 functions, 30 modules;
no original budget raised). Hash-pinned wheel/sdist builds, package-data
inspection and isolated installed CLI/API probes pass. Final browser replay:
classic 38 scenarios / 342 assertions, v2 37 scenarios, zero failures; the
six-viewport harness also passes. Two inherited whitespace defects were removed
with complete AST equivalence checked; artifacts and installed probes were
refreshed. Work remains local, without a new branch commit,
merge, push or release action; the primary checkout is untouched.

## 2026-11-08 — H2 explain-only bridge, Skill CI recipe, checklist reconciliation

**[SPEC] docs/29 H2, explain-only.** `doctor --hygiene --scope all` (and the
same REST report) gains a read-only `agents_bridge` section plus one
`agents-bridge-gap` info finding. They name enabled, readable skills in
`~/.agents/skills` that have no copy or link in `~/.claude/skills`. Claude
Code's documented roots exclude `~/.agents/skills` (docs/34). The remedy given
is the existing `sync` copy. The manual-link remedy carries the open
anthropics/claude-code #14836 caveat; #31005 (`.agents/skills` support) was also
still open on 2026-11-08. Alias records count as present, so a link already
in `~/.claude/skills` closes the gap. On the maintainer's machine: 7 skills. A
link-writing bridge stays deferred: it is a new command and may not work while
#14836 is open. `tests/test_agents_bridge.py`: 9 tests, 8 red before.

**[SPEC] Skill CI recipe.** @docs/36-skill-ci-recipe-2026-11-08.md documents a
pull-request check over the existing `validate --path`. Its marked script block
is executed by `tests/test_skill_ci_recipe.py` (5 tests). Removing
`|| status=1` from the doc turns the suite red, which was checked by mutation.
Its workflow pins must be SHAs this repository's own CI reviewed.

**[NOTE] A pre-existing order dependence.** Running `tests.test_sidecar_binding`
after `test_webapp`, `test_web_client_contracts`, `test_audit_route_table` or
`test_audit_d1_lazy_observations` failed 3 tests on unchanged `a01efdd`: those
modules leave a since-deleted Store bound in the `scopes` context, and sidecar
bindings resolve through it. The fixture now starts unbound and restores the
prior binding. All four pairs pass.

**[NOTE] Checklist reconciliation.** The Codex native-switch defect line now
records the shipped D-1 reader. R7 is closed with its disposition: `git gc`
done and `AGENTS-1.md` removed; the seven `prototype-*` directories and
`.specs/prototypes/` are tracked design history and stay, because deleting them
is the maintainer's call. PyPI still lists 1.0.1, so the 1.0.2 publish is still
waiting on the human `release` approval.

**[NOTE] Independent review (DeepSeek, `max` effort, read-only snapshot).** The
`deepseek-worker` MCP connection dropped mid-session (the bridge doctor passed
every check). The user reconnected it. A first broad review hit the worker's
output limit (exit 137, about 10M input tokens). A narrowed brief at `max`
effort returned five findings, each checked against the code:
- **Fixed:** a scan truncated at `max_instances` could name a skill as missing
  when its Claude copy lay past the limit. It now reports `state: partial` and
  names nothing (red test).
- **Fixed, narrower than proposed:** unquoted `$mgr` was also glob-expanded.
  The script now uses `read -r -a`; a glob-character test is red on the old
  form. A command path containing a space cannot coexist with multi-word
  `SKILLS_MGR` values, so it is documented rather than "fixed".
- **Not a defect, pinned:** "SIGTERM leaves the temp dir". Bash runs the `EXIT`
  trap when an untrapped SIGTERM kills it; a test sends SIGTERM mid-run and
  asserts cleanup.
- **Not a defect:** "the finding carries 100 raw records". `_finding` publishes
  the same bounded `_public_instance` projection every finding uses.
- **Not a defect:** "alias-level disabled state". Aliases collapse by physical
  identity, so their document state is identical by construction.

**[NOTE] A time bomb found by the ladder.** `tests/test_agent_scope_trash.py`
asserted `trashed_at` started with `2026-11-07` and failed on every interpreter
the next day, on `main` as well. It now checks the parsed timestamp falls
between UTC instants taken around the removal. No other hardcoded-date
assertion exists in `tests/`.

**[NOTE] Verification on the committed tree (`095becd`).** 1,741 tests on each of
Python 3.11, 3.12, 3.13 and 3.14, with the 2 optional reference-oracle skips. v2
browser suite: 36 scenarios, no failures and no uncaught page errors. Classic
suite: 38 scenarios / 342 assertions, no failures. Also passed: both smokes,
compilation, `check_docs`, `check_complexity` (899 functions, nothing raised),
`check_design_tokens`, Ruff 0.16.8 (F821/F822/F823) and Bandit 1.9.4. Not
claimed: a human visual or spoken screen-reader review, live registry
execution, and the PyPI release approval.

## 2026-11-07 — Resume the interrupted remaining-tasks sub-session

**[NOTE]** Recovered the named Claude sub-session and both completed worker
snapshots. Continued in its worktree and preserved the unrelated dirty primary
checkout. The maintainer's previous delegated decisions are recorded in
@docs/35-open-decisions-resolved-2026-11-07.md; the untracked decision record is
now included with the implementation.

**[SPEC]** R15 now shares review mechanics across registry, source-update and
backup-sync modules without merging their storage, expiry, error or locking
contracts. The 23 characterization tests passed against the pre-refactor code.
Review caught and fixed normalization of backup paths before symlink checks,
lost temporary-file cleanup after a moved directory, and a descriptor leak on
registry writer setup failure. Existing executable/data-root trust policies
were retained; worker changes aimed only at sandbox quirks were excluded.

**[SPEC]** SCOPE-2 allows read-only inspection of directory links contained in
another known managed agent root. Unmanaged links and global-store scans keep
the old refusal. Scope mutations remain refused with a target-folder message.
The new link tests failed on the old tree before integration. Review also
caught a v2 physical-deduplication bug that hid the writable owning copy; the
owner now survives regardless of row order.

**[SPEC]** Review of the preceding commits found three additional defects:
batch approval did not bind companion files, a failed source swap could replace
the prior sidecar trust binding, and a linked agent-trash root could redirect
restore. Batch plans now include bounded whole-tree hashes for affected trees;
source updates roll back the tree and its prior binding together; agent trash
checks refuse linked roots and recheck the selected entry inside the lock.
Sidecar lookup also uses the requesting Store context rather than the last
unrelated Store registered in the process. Compound rollback failures preserve
the exact saved binding and tree evidence for recovery; private recovery paths
stay in diagnostic logs rather than public exception text.

**[NOTE]** The pinned Bandit audit also exposed four unsuppressed sites from
previous work: one scanner subprocess import, a token-estimate prose constant,
and two Git object SHA-1 calls. Reviewed the existing scanner subprocess call
(trusted executable, argv list, scrubbed environment) and added the narrow
B404 import rationale required by docs/21. Renamed the explanatory constant
without changing its output, and marked Git-format hashes
`usedforsecurity=False`; SHA-256 trust/binding digests are unchanged.

**[NOTE]** Full verification exposed a native-state test that inherited the
runner's real `CODEX_HOME`; it now points to the private fixture. Classic's
browser checks also still expected the old unbound-plan behavior. They now
assert stale rejection before writes and successful execution only after a new
preview. All four Python versions passed the corrected backend tree. Final
verification is repeated after the peer-alias UI integration below.

**[SPEC]** Followed aliases retain per-agent visibility, counts and disabled
mutation controls while the writable owner remains editable. Physical aliases
are counted once for majority/reference comparison, rather than gaining extra
votes from their scope views.
Human visual, spoken screen-reader and usability acceptance remain unclaimed;
PyPI publishing remains a separate human release gate.

**[NOTE] Final verification on the frozen product/test/browser tree.**
- Python 3.11, 3.12, 3.13 and 3.14: **1,724 cases per interpreter, no failures**;
  the two optional reference-oracle cases skip in the stdlib matrix and both
  pass when run separately with the existing `skills-ref` interpreter.
- Full v2 browser suite: **36 scenarios, zero failures**. Full classic suite:
  **38 scenarios / 342 assertions, zero failures**. The peer-link browser case
  checks Claude filtering, disabled alias selection/update/toggle controls and
  editing the owner; agent Recovery covers both Undo and card restore.
- Six-viewport smoke harness, both Store/web smokes, Python compilation, all
  frontend syntax, documentation/design gates, Ruff 0.16.8 and Bandit 1.9.4
  passed. Bandit has zero unsuppressed findings. The complexity ratchet tracks
  **894 functions across 21 files**, with no existing allowance increased and
  every new function at most 15.
- Hash-verified build tools produced wheel and sdist; package-data checks and
  isolated installations of both artifacts passed both smokes. Synthetic
  0/1/10,000-entry tree probes confirm the batch tree bound refuses the large
  case. Source fingerprints confirm no product/test/browser edit landed during
  the final ladder.

**[NOTE]** Final comment review clarified that review-directory permissions
apply to the directory itself, that the filesystem owns global skill truth,
and that reading a peer link does not prove effective agent loading. Python
executable ASTs were unchanged by these wording corrections; focused contracts,
syntax and documentation gates were repeated.

**[NOTE] Hostile-review disposition.** Checked linked paths before hashing,
read-only write refusal, physical alias voting, stale approvals, duplicate
attempts, corrupt/missing evidence, descriptor/temp cleanup and both single-
and compound-failure rollback. Advisory locks do not prevent unrelated tools
from writing after validation; that limit is explicit. The tests run on Linux
and Chromium locally; human perceptual/spoken screen-reader acceptance, live
registry/runner execution, and PyPI release approval remain unclaimed. The
unrelated primary checkout's tracked diff and status are unchanged.

## 2026-11-07 — Second pass: what review and real data changed

**[NOTE]** Lead plus DeepSeek workers again, with one new step. A read-only
code-reviewer agent reviewed every worker-written diff before it shipped. The
entries below record each feature; this one records what only the cross-checks
found.

**[SPEC] Found by a real browser, not by tests.** v2's lazy body loading kept
the skill page's Edit button disabled forever, because
`Object.prototype.hasOwnProperty.call` on a reactive object is not tracked by
Vue. The sandboxed unit tests passed. The Playwright suite failed. Fixed and
pinned.

**[SPEC] Found by real data.**
- On the real 131-entry global lock, 58 of 70 "differs" results were skills this
  tool had disabled by renaming `SKILL.md`. They are now compared under their
  enabled name, which gives 114 exact tree matches.
- Phase B's first `credential-path` check rated 192 bare `.env`/`.ssh` mentions
  high across 1,764 instances. Only the lines that act on the path stay high
  now, which leaves 18.

**[SPEC] Found by the independent review.** Every finding was reproduced,
fixed with a red-first test, and merged:
- an earlier harmless mention could hide a later exfiltration line;
- hostile Python crashed the `ast` check;
- one hygiene request could hash about 32 GB;
- a credential could leak through the lockfile source fallback;
- linked copies showed "Loading document…" forever;
- same-name duplicates all showed one body;
- Phase B's file and description checks were never called by any production
  path.

The review also confirmed two areas with no defect: the `home` root
confinement in `effective.py` and the `errors.py` move.

**[NOTE] Facts are cited, not remembered.**
@docs/34-agent-skill-loading-research-2026-11-07.md records primary-source
precedence and frontmatter facts for 11 agents, Claude Code's listing budget,
and Gemini's `skills.disabled` UNION merge from gemini-cli source. It also
corrects the earlier "OpenCode documents no order".

**[?] Still open.**
- Codex TOML (D-1) and shared review plumbing (R15 remainder).
- Every maintainer decision, and every human sign-off.

## 2026-11-07 — Gemini CLI native skill switch (R4, read-only)

**[SPEC]** `observe_native_states('gemini', …)` now reads the four documented
settings files lowest to highest: system defaults
(`/etc/gemini-cli/system-defaults.json`, overridable with
`GEMINI_CLI_SYSTEM_DEFAULTS_PATH`), `~/.gemini/settings.json`,
`<cwd>/.gemini/settings.json` (reported `unobserved` when the caller supplied no
project), and system overrides (`/etc/gemini-cli/settings.json`, overridable
with `GEMINI_CLI_SYSTEM_SETTINGS_PATH`). Files go through the existing `_load`
bounds, so duplicate keys, FIFOs/non-regular files, bad JSON and files above
1 MiB fail cleanly, and each file is read once per scope batch. `skills.disabled`
is a `UNION` name list, so any readable file that lists the exact name is enough
for `observed_setting: "disabled"` (case sensitivity is not documented, so
matching is exact only); `skills.enabled` and `admin.skills.enabled` resolve
last-declaration-wins and `false` disables every skill. A wrong type is that
source's `invalid` declaration under `invalid_keys`, never an exception; the
list is bounded at 1,000 names and 512 characters per name. The two system paths
are documented for Linux only, so other platforms report them `unavailable`
with a reason instead of guessing. `partial` stays true and `effective_state`
stays `unknown` because environment variables and CLI arguments outrank every
file and are not observed. Wired for the `gemini` scope only through the
existing `scope.consumer` dispatch; Codex TOML stays deferred under D-1.

**[NOTE]** Verified on this tree: 16 new tests in
`tests/test_native_state_gemini.py`; the full suite runs **1,589 tests** with
only the four already-recorded environmental failures (`backup_sync`
trusted-git, `localhost` bind DNS, and the two HOME/data-root permission tests).
`check_docs.py` and `check_complexity.py` pass — `native_state.py` is not a
ratchet target, so the baseline is unchanged. No Store method, CLI command,
REST route, SQLite state, dependency or write was added.

## 2026-11-07 — Phase B: nine stdlib checks in `risk_scan()` with a warning-context rule

**[SPEC]** Implemented Phase B of
@docs/superpowers/plans/2026-11-06-external-skill-scanner.md as nine
single-purpose checks added to `insights.risk_scan()`, written fresh with this
project's own kind names and wording (nothing copied from SkillSpector's
Apache-2.0 patterns or ids): `remote-exec`, `decoded-exec`, `credential-path`,
`suppression`, `persistence`, `bytecode`, `padding`, `broad-trigger` and
`dynamic-code`. Every finding keeps the existing `kind`/`severity`/`evidence`/
`why`/`confidence` shape, is `advisory` with `authority: "advisory"`, and
evidence is control-escaped and length-bounded.

Inputs are the record's `name`, `description`, `body` and an optional `files`
listing of `{path, contents}` entries — the registry snapshot shape. No
filesystem read, import, execution or new dependency was added, and no CLI
command, route or Store method changed. Bundled `.py` sources are parsed with
stdlib `ast` (at most 50 files, 256 KiB each);
`SyntaxError`, oversize and count-limit skips each become one counted
`low` note so an unanalyzed file is never silent. The new findings are capped
at `MAX_RISK_FINDINGS = 200` with an omitted note; a match is
`itertools.islice`-bounded per pattern so a hostile 12 MB file cannot turn the
scan into an unbounded loop.

**[SPEC] The warning-context rule is the false-positive guard the plan asked
for.** A match whose containing line says `do not`, `don't`, `never`, `avoid`,
`instead of` or `unsafe` is still reported, but at `low` with that reason in
`why`. The matched text is removed before the guard test, so a suppression
phrase such as `never refuse` is not mistaken for the warning word `never` that
would otherwise downgrade it. Fenced code blocks are not exempt: a fenced
`bash` block containing `curl … | bash` is reported normally.

**[NOTE] Verification.** New tests are `tests/test_risk_scan_phase_b.py`
(37 tests: one positive and one benign negative per check, the 1-5
warning-context guard, AST syntax-error/oversize skips, the truncation bound,
JSON serializability and the finding shape). Red-first against the unchanged
`insights.py`: **21 failures + 3 errors = 24 of 37 failed**; 37/37 pass after.
`tests/test_insights_contracts.py` (60) still passes, including its 5 s budget
on a 200,000-line body. Full suite: **1,549 tests, 2 failures + 2 errors**, the
four already-recorded environmental failures (`backup_sync` trusted-git,
`localhost` bind DNS, and the two HOME/data-root permission tests) — none touch
these modules. `check_docs.py` and `check_complexity.py` pass (810 functions
across 20 files; no baseline change; every new function is ≤ 9 against the
budget of 15). `insights.py` is not a complexity target, so the ratchet was
measured for the budget but not re-baselined.

**[?] The plan's measured-noise step is unavailable in this sandbox.** It asks
for a `risk_scan()` run over a real library before and after; `HOME` here is an
isolated `/sandbox-home` with no skill roots and `scopes.list_all()` returns 0
records, so there is no number to report. Recorded in `task.md` rather than
claimed.

## 2026-11-07 — R12 consumer rows and the ignored-frontmatter finding

**[SPEC]** Docs/34 (vendor pages read 2026-11-07) drove two changes with no new
CLI command, REST route, Store method, SQLite state, cache, network request or
runtime dependency.

`effective.explain` gained a `home` root spec (resolved through
`paths.home_dir()` at read time and redacted over HTTP exactly like an absolute
`path` root), corrected `opencode` from `undocumented-precedence` to the
documented lowest→highest order (built-in < `.claude/skills` < `.agents/skills`
< `~/.config/opencode/skills` < project `.opencode/skills` < explicit `skills`
config), and added `cline`, `kiro`, `amp`, `roo`, `zed` (ordered) plus
`copilot` and `devin` (roots published, no precedence). `shadowed` entries now
carry the winning tier as `shadowed_by`, which docs/02 already documented but
the code did not emit. The three documented-mode tiers Roo cannot read without
a mode slug, OpenCode's config tier and Amp's configured locations are
`path_known: False` and produce a provisional-lower-win warning. No order was
invented where docs/34 is silent.

New `skillsmgr/key_support.py` is a pure table of the frontmatter keys each
consumer's page documents (claude-code, claude.ai-api, codex, gemini, opencode,
cline, kiro, amp, roo, zed) with its source URL. `hygiene.py` uses it to emit
one advisory `ignored-frontmatter` finding per behavioural key that an
instance's scope consumer(s) do not document. The `agents` scope names the six
consumers that read `~/.agents/skills`; scopes with no recorded key list
(`global`, `commandcode`, `cursor`, project scopes) add a
`frontmatter-key-support` unavailable signal instead. The finding never claims a
key was rejected — only the claude.ai/Skills API surfaces document that — and
`disable-model-invocation` in a codex-read scope carries Codex's own
`agents/openai.yaml` implicit-invocation switch.

**[NOTE]** Verification on this tree: **1,510 tests** in the full suite, of
which the four already-recorded environmental failures reproduce unchanged
(`backup_sync` trusted-git, `localhost` bind DNS, and the two HOME/data-root
permission tests); both smokes, compilation, `check_docs.py` and
`check_complexity.py` (810 functions across 20 files, 0 existing metric raised,
15 added) pass. No browser or packaged-artifact claim is made here. Test
expectations changed or added: `tests/test_effective_new_consumers.py` (18)
and `tests/test_key_support.py` (12). No existing test asserted OpenCode was
undocumented, so nothing was deleted; the new `opencode` tests assert the
documented order instead.

## 2026-11-07 — R11: read-only `skills` CLI lockfile evidence in the hygiene report

**[SPEC]** New `skillsmgr/lockfiles.py` parses the project `skills-lock.json`
(version 1) and global `.skill-lock.json` (version 3) written by
vercel-labs/skills, compares every declared skill with
`<root>/.agents/skills/<sanitizeName>` and adds a `lockfiles` section to the
existing `doctor --hygiene` / `GET /api/doctor?scope=…&hygiene=1` report. No new
CLI command, REST route, Store method, SQLite state, cache, network request, or
write was added. Malformed JSON, a symlinked/oversized lockfile, a wrong version
or a non-dict entry is reported `invalid` with a reason and never raises; at most
500 entries per lock carry an `omitted` count, and each skill hash shares a
2,000-file / 64 MiB budget (`too_large` above it).

`computedHash` is implemented twice (plain codepoint order and a case-insensitive
approximation) because upstream sorts with JavaScript `localeCompare`, which the
standard library cannot reproduce; a match under either order is `match`, and
neither is `mismatch_or_unverifiable` with that explanation, never "modified".
`skillFolderHash` is the git tree object SHA-1 with blob/tree headers, git's
byte-order entry sort, executable and symlink modes, and `.git` skipped; the test
compares it against a real `git write-tree` for nested dirs, an executable file
and a symlink. A mismatch is `differs_from_recorded_tree` and is worded as
"differs from the recorded upstream tree", not tampering. Source URLs lose
userinfo/query, `~/.agents/skills` entries missing from the global lock are
listed as bounded `undeclared` names, and an existing `apm.lock.yaml` is an
unavailable signal (YAML parsing is not in the standard library) and is never
parsed. The CLI human output gains one bounded summary line.

**[NOTE] Verification.** 27 new tests in `tests/test_lockfiles.py`; the four
remaining full-suite failures (`backup_sync` trusted-git, `localhost` bind DNS,
two HOME/data-root permission tests) reproduce on unmodified `HEAD` in this
sandbox and are environmental. `check_docs.py` passes; `lockfiles.py` joined the
complexity targets and the regenerated baseline raised no existing entry
(29 added, all ≤ 11 against a budget of 15).

## 2026-11-07 — Remaining approval-free tasks, lead + DeepSeek workers

**[NOTE]** The maintainer asked for every remaining task to be done and granted
decision authority. Claude acted as lead and reviewer; DeepSeek workers
(`deepseek_worker`, isolated worktrees, sandboxed verification) wrote four
changes. Every worker diff was read and every red-first claim re-checked here
before merging. Human sign-offs and maintainer decisions were not touched.

**[SPEC] Shipped.**

- **R16 / S5** — `backup_sync._run_git` pins `core.sshCommand`,
  `core.fsmonitor`, `core.hooksPath`, `core.askPass`, `core.gitProxy`,
  `diff.external`, `uploadpack.packObjectsHook` and the `ext`/`file` protocols
  with `-c`, sets `GIT_SSH_COMMAND=ssh` and `GIT_CONFIG_NOSYSTEM=1`, and drops
  inherited `GIT_SSH`/proxy/askpass variables. Credential helpers stay the
  delegation path. 3/3 tests fail on the old code, including a real-git test in
  which a hostile repository's `core.sshCommand` actually executed.
- **Silent-failure lint** — warnings for an empty delimited frontmatter block
  and for an unquoted `: ` inside a top-level plain scalar, both of which strict
  YAML parsers drop silently. Warning-only; the value is never echoed.
- **Order-dependent test leak** — `WebAppServer` bound its Store into the
  `scopes` ContextVar and never unbound it, so a later in-process `cli.main` on
  another `--data-dir` resolved `global` through a stale Store. `cli.main` now
  binds its own Store per command and restores the prior binding. That is a
  product fix, not a test-fixture patch.
- **Classic P3s** — Enter in the Workspaces project field runs the check; the
  Install Preview requests the backend's offline plan and renders its blockers,
  `may_install` and https-only audit links as escaped text.
- **R15 (part)** — the web route renders its `skills add` argv through
  `insights.install_argv`. A 22-case HTTP characterization was confirmed to pass
  against the *original* `webapp.py`; only its source assertion failed there.
- **README** — "What it will not do, and what leaves your machine", verified
  against the source. It found one undisclosed egress: with optional `tiktoken`
  installed, `tokens.py` calls `get_encoding("cl100k_base")` at import, which
  downloads that file on first use.
- **Hermetic Chrome test** — `test_chrome_launch_retries_before_giving_up`
  asserted 0 == 3 on any machine without Chrome, because `_chrome()` raised
  before the first launch. It now stubs the resolver.
- **R7 (part)** — `AGENTS-1.md` removed; `git gc` (pack 67.6 → 63.3 MiB).
- **SkillSpector trust** — group write removed from the uv tool path; the
  unchanged policy now accepts the install and the real-tool test runs.

**[NOTE] Worker tooling fixed on the way.** The worker's verification output
was cut at 6,000 characters keeping 70% head, so a long gate listing hid the
test verdict. It now keeps 80% tail within 12,000 characters (worker suite
50/50). Its sandbox has no Chrome and a private `HOME`, so host-dependent tests
can report FAIL for an environment reason. One such FAIL here was a product-test
defect (the Chrome test above), and the rest re-ran green on the host.

**[?] Still open, by design.** Human perceptual/screen-reader sign-offs,
consented sessions, every `Decide:` item, R12 (needs cited primary sources per
agent), R13, R17–R19, Phase B, the rest of R15, and the Dependabot pin update,
which was then done the same day as #20 with a passing release dry run
(see @docs/23-github-actions-dependency-pr-review-2026-09-23.md).

## 2026-11-07 — The default-interface redirect broke CI on Python 3.10

**[SPEC]** CI `unit (py3.10)` failed on `main` at `61355a2`. Because the security,
browser, docs and package jobs depend on it, they were skipped. The cause:
`/` and `/index.html` answered `308`, and Python 3.10's `HTTPRedirectHandler`
follows only 301/302/303/307. Every urllib client on 3.10 therefore raised at
`/`, including `smoke_fixtures.start_server`. That accounts for all 15 failures,
and the same failures reproduce on an unchanged `HEAD` export. The local ladder
for that commit did not run 3.10, which is the lesson already recorded in
SESSION-CONTEXT about testing one interpreter only.

**Fix:** the default-interface redirect is now a temporary `307`, which is also
the right semantics: which interface opens is a product choice a browser must
not cache forever. Trailing-slash canonicalization (`/v2`, `/classic`) stays
`308`. A new test asserts the entry redirect uses a status 3.10 follows. It
failed on 3.12 before the fix, so it does not depend on having 3.10 to go red.

## 2026-11-06 — SkillSpector hook shipped (Phase A) with bring-your-own-key LLM mode

**[SPEC]** New `skillsmgr/external_scan.py` runs an installed SkillSpector on a
private copy of the staged candidate during registry fetch and source-update
reviews, only when asked (`--external-scan`, `--external-scan-llm`, REST
`external_scan`, v2 Settings). It is never imported. A trusted PATH match is run
as an argv list with a scrubbed environment. LLM mode passes only an allowlist
of provider variables, so a user's own key reaches the tool only on request and
is never stored or returned. Output is bounded and whitelisted, and the
evidence is advisory. Commit and apply never re-run it.

19 new tests, red-first. They use a fake tool that records argv, environment and
input, and cover timeout, error, oversized output, hostile text and an unsafe
PATH. Real v2.12.0 output was parsed through the hook (AR1/PE3/SC2, score 66).
The optional real-tool test is skipped here because the uv tool directory is
group-writable and the unchanged trust policy refuses it.

The complexity ratchet flagged +1 on three existing functions; each was
restored by extracting a helper. `external_scan.py` joined the ratchet targets
(752 functions, 17 files, nothing raised). Full suite: 1,404 tests, Python 3.12.

**[NOTE]** A pre-existing order-dependent failure was found and **not** fixed:
running `tests.test_registry_integration_contracts` before
`tests.test_cli_contract` fails the `--scope all` doctor test on unchanged
`HEAD` as well. Also, port 8791 belonged to another session's server showing
real data. It was only viewed, nothing was changed, and verification moved to
an isolated fixture on 8817.

The maintainer then asked for broader AI features. The proposal, with seven
open decisions, is @docs/33-ai-features-design-2026-11-06.md. Nothing in it is
approved or implemented.

## 2026-11-06 — Plan: optional SkillSpector hook, then stdlib risk patterns

**[NOTE]** Plan only; no source changed. NVIDIA SkillSpector cannot be merged
(about 20 runtime dependencies, Python >= 3.12, LLM/OSV egress, and a
DO_NOT_INSTALL verdict that conflicts with the advisory-only rule), so the plan
runs an installed copy as an optional external program in the two existing
review chokepoints and later rewrites a few static checks with the stdlib.
Verified locally on v2.12.0: `--format json --no-llm` reported AR1/PE3/SC2 on a
hostile fixture. SC4 still contacts `api.osv.dev` under `--no-llm`, with no
offline switch. See the
[plan](superpowers/plans/2026-11-06-external-skill-scanner.md).

## 2026-11-06 — `task.md` reconciled with `main` and the research roadmap

**[NOTE]** Checklist-only correction; no source changed. Four lines still
described the v2 parity work as uncommitted or undecided although `61355a2`
is on `origin/main`; they are now checked off. The R4 native-switch defect and
the silent-failure lint are marked partial with what remains (Codex TOML via
D-1; empty-frontmatter and unquoted-colon lint). Ten docs/28 R-items and four
docs/29 roadmap items were **absent** from the checklist and are now listed —
the same missing-not-unchecked failure recorded on 2026-10-05.

## 2026-11-06 — Redesign the v2 tool pages to the Home/Skills standard

**[NOTE]** Continued the uncommitted Codex parity work in a separate worktree
(the original checkout was not edited). A rendered review on an isolated
fixture found the new tool pages read as stacked admin forms: dropdown-driven
registry actions, a raw page-number field, comma-separated skill entry,
undifferentiated finding rows, raw API slugs and ISO timestamps, colliding
headings, and a Tools entry hidden below 1200px beside a duplicate search
button. The tool-center template and `tools.css` were rewritten on v2's own
components; data flow, review gates and API calls are unchanged (see the
@docs/08-web-ui.md design rules). Profiles now pick observed skills from a
filterable list and add absent names explicitly. Two suspected defects were
checked and are not defects: the Skill page sidebar is sticky at viewport
height (a full-page capture artifact), and categories come from
`metadata.category`, so the test fixture was wrong, not the model.

**[SPEC] Verified on this tree:** 1,386 unit tests (Python 3.12); v2 test
modules on 3.11/3.13/3.14 (3.10 not installed locally); 34/34 v2 browser
scenarios including all tool routes at 320/768/1280 in both themes; header fit
measured at 14 widths from 320 to 1920 px; both smokes, docs and complexity
gates. Browser assertions pinned to replaced labels were updated to the new
labels, not removed. Classic browser suite and packaging were not re-run (no
classic or packaged-path change beyond the shared CSS file selector).

## 2026-11-06 — Complete v2 feature parity and promote the default

**[NOTE]** The maintainer first approved clickable mockups, then explicitly
requested production integration using the existing v2 design and default
promotion after verification. Work is local on `feat/v2-feature-parity`.
The [design inventory](superpowers/specs/2026-11-06-v2-feature-parity-design.md)
records the source baseline; the
[implementation plan](superpowers/plans/2026-11-06-v2-feature-parity.md)
records acceptance evidence. The
[earlier mockup](../prototype-v2-parity/README.md) remains an isolated design aid.

V2 now contains the remaining classic workflows: registry/runner/folder install,
profiles, templates, hygiene/validation/diagnostics, workspaces, preferences and
index maintenance, exact-copy source update/whole-tree rollback, logical tags,
reviewed batch operations, rich metadata editing, persistent scoped history and
full archive recovery. `/` and `/index.html` redirect to `/v2/`, preserving
query/hash; classic remains at `/classic/`. Existing v2 fonts, colours, document
reader, daily navigation and dark theme remain the visual authority. Inspo's
configured HTTPS MCP endpoint supplied recommendations/searches and three
archived captures; it was not enabled globally. UI/UX Craft, Design Taste
Frontend, Better Accessibility and Frontend UI Engineering informed the work.

The backend additions are contained template reads and explicit PATCH optional
field/body clears. Omission preserves values; empty descriptions are rejected.
The shared field guard's complexity budget tightened from 7 to 6. No public
Store method, application CLI command, schema or runtime dependency changed.
Luna/Terra reviews found races and copy-identity problems; fixes bind folder
approval to File identities, use the selected copy's description/scope, send
only changed editor fields and isolate independent read results. Behavioral
and real-HTTP regressions cover these cases. The final narrow Terra review
reported no unresolved defects in those fixes.

All write checks use temporary HOME/data roots. The classic browser suite
passed 38 scenarios / 318 assertions; the expanded v2 suite passed 34 scenarios,
including real template/profile operations, retry and 320/768/1280 layouts in
both themes. The six-viewport classic smoke harness also passed after moving
its probes to `/classic/`. The final current-tree suite passed 1,386 tests on Python 3.12; both smokes,
syntax/compilation, docs, design tokens, complexity, Ruff and the medium/high
Bandit scan passed. The final v2 browser repeat again passed all 34 scenarios. Packaging with the pinned hash-checked
toolchain includes all three new v2 assets in wheel and sdist. Live registry
fetch/commit, actual external runner execution and human screen-reader sign-off
are not claimed. Agent-scope trash has no in-app restore, and the interface
states that limit. No personal skills were changed; no commit or push was made.

## 2026-11-06 — Integrate the verified performance work into main

**[NOTE]** The maintainer authorized main integration after the performance
session's verification completed. The canonical checkout was clean apart from
the existing untracked `.claude/` directory; main fast-forwarded from `d00cb78`
to the verified performance tip `68e50f0`. This follow-up updates the integration
record only; it makes no runtime changes. The performance entry below records
the earlier branch-only state and its full Python/browser/package evidence.
The exact pushed commit's CI result is verified separately from those local
checks.

## 2026-11-06 — Complete the performance session's missing verification

**[SPEC]** Continued `claude/project-perf-ux-review-4da40d` with its WIP
performance commit preserved, including the previously uncommitted `/v2`
redirect. Current main `d00cb78` was merged into the performance branch; no
performance work was integrated into main or pushed. The initial three
targeted failures were the uncontended-copy expectation, a startup source
assertion and an incomplete locale-test stub. Tests now exercise parallel
startup and real domain/Vue behavior rather than pinning the old source shape.

The body-less list option preserves existing default fields and full detail
reads; body search and pagination run before projection. Repeated body flags
now fail before scanning. `/v2` redirects to the local `/v2/` directory while
preserving queries and browser hash navigation. Editor guards wait for a full
body and reject missing or superseded selections; Edit during a detail load
shows a wait message and keeps the editor closed. Scope summaries
reuse merged agent rows but scan the global root separately: the initial
optimization missed unindexed global documents, and red-first tests now cover
that case and unchanged counts with a missing/corrupt index. Snapshots stay isolated per caller;
the hygiene memo is per report and resets even on failure. New regressions live
in `tests/test_performance_backend.py`, `tests/test_performance_http.py` and
`tests/test_performance_frontend.py`. Private helper extraction keeps every
existing complexity budget unchanged or lower; two stale-high hygiene budgets
were tightened instead of raised.

The first full matrix exposed a G8 test context missing the new row helper;
it now binds the actual app methods. A deliberately reordered subset also
exposed an existing Store-context leak in the review fixture (reproduced on
unchanged main); the fixture now binds and restores its own Store context.

**[NOTE]** The original Claude session's timings were single local browser
captures, not repeated benchmarks: classic startup 5.3 → 2.55 s, list transfer
22.7 → 4.2 MB, Library opening 846 → 288 ms, and v2 startup 5.35 → 2.54 s.
They are historical observations, not new measurements from this completion.
v2 still requests full document bodies; lazy v2 loading remains deferred.
The six-viewport browser smoke and a 300-row off-screen keyboard/detail/editor
probe have passed. Final verification: **1,363 tests on each Python 3.10.20,
3.11.15, 3.12.3, 3.13.13 and 3.14.3**; both smokes, compilation, docs, design
tokens, complexity (730 functions), Ruff 0.16.8 and Bandit 1.9.4; pinned,
hash-verified wheel/sdist builds with all 25 UI assets and both example files.
Browser results: **38 classic scenarios / 318 assertions**, **28 v2
scenarios** (including query/hash-preserving redirects), and the six-viewport
smoke harness all pass, with no unexpected console errors, failed requests
or horizontal overflow. The deliberately reordered fixture subset also passes.
These are Linux/Chromium checks; non-Chromium engines, newer Python patch
releases and human spoken screen-reader sign-off are not claimed here.

## 2026-11-06 — Refuse oversized tar metadata before chunked reads

**[NOTE]** CI on `5a2f0ce` failed the oversized-PAX memory regression on Python
3.13.18 and 3.14.10. Their tarfile module accumulates extension payloads through
chunked `_safe_read` calls, so the per-read guard admitted roughly 24 MiB before
refusing the next chunk. Loading the upstream 3.13.18 module under local Python
3.13.13 reproduced a 25,348,158-byte peak; the unchanged test budget is 12 MiB.
Source: [CPython 3.13.18 tarfile](https://github.com/python/cpython/blob/v3.13.18/Lib/tarfile.py).

**[SPEC]** `open_tar` now supplies a `TarInfo` subclass that checks the declared
PAX/GNU extension end, including block padding, against the existing absolute
decompressed-stream limit before dispatching to the stdlib parser. This covers
recursively parsed extensions without replacing the stdlib parser. Stream,
member and regression-memory limits are unchanged. Existing `finally` cleanup
closes the reader on initial-open and iteration failures.

**[NOTE]** All 37 streamed-tar and archive contracts pass with the upstream
3.13.18 and 3.14.10 tarfile modules loaded under local 3.13.13 and 3.14.3,
respectively; these are parser-compatibility probes, not runs of the newer
interpreters. The fixed oversized-PAX peak with the 3.13.18 module measured
328,169 bytes. New regressions cover all five extension types initially and
recursively, reader closure, and successful PAX/GNU Unicode long-name imports.
Full local verification passed: **1,339 tests on each Python 3.10.20,
3.11.15, 3.12.3, 3.13.13 and 3.14.3**; both smokes, compilation, complexity
(722 functions), docs, design tokens, Ruff 0.16.8 and Bandit 1.9.4; pinned,
hash-verified wheel/sdist builds and all 25 UI assets in both artifacts.
CI independently covers newer interpreter patch versions and non-Linux hosts.

## 2026-11-06 — Classic screens, 10,000-instance scale and screen-reader checks closed three gaps

**[SPEC]** Three gaps left by @docs/31-combined-e2e-verification-2026-11-06.md
are closed in @docs/32-continuation-verification-2026-11-06.md, all on
isolated fixtures. The classic-only screens now have an end-to-end runner
(`tools/e2e_classic`), passing 312 assertions twice after fixing two defects:
the batch dialog lost its focus return, and Quality's hygiene report became
unreachable once a skill was selected. A 10,000-instance run found no crash or
stall and measured where time goes: a 56.7 MB list payload, a token-counting
`/api/scopes` rescan, and a classic Library that renders all 55,765 nodes.
Orca 46 transcripts plus a CDP audit found a P0: Enter on the Inbox "Open
skill" link ran the fix instead of navigating. It and twelve other findings
are fixed and pinned by four new browser checks (v2 suite 27/27 twice).

**[?] Open.** No person has heard the screen-reader output; the docs/32
walkthrough is the requested next step. The payload, scopes-rescan and classic
row-cap fixes are maintainer decisions, not silent changes.

## 2026-11-06 — Combined frontend/backend integration and browser verification

- Normally merged completed backend `fbe8ec2` into frontend `7d225dc` without
  conflicts; retained the frontend JSON transport required by R9.
- Show partial native settings separately from file toggles in v2 detail;
  loading remains unknown. Corrected binary-repair guidance to explain the
  text Undo limitation instead of denying the new force-sync capability.
- Sanitize initial-load errors and traceback/library failures alongside toasts.
- Red-first model probes found mixed text/binary repair and refused-link source
  bugs. Automatic repair now requires every target to support text Undo and a
  readable source. Sync Undo restores prior file enabled state and refreshes
  after failure; companion-file rollback is explicitly outside text Undo.
- Actual 400% Chrome zoom exposed Recovery’s fixed 320px grid minimum. Its
  tracks and controls now fit the available width; browser zoom is checked
  through isolated X11 input and measured device-pixel ratio.
- The rejected-upload test now observes its own staging allocation rather than
  other suites’ temporary directories; invalid parts still allocate nothing.
- Current tree: **1,337 tests OK on each Python 3.10–3.14**, 24 browser
  assertion groups (both UI transports; desktop/phone, both themes; actual
  200%/400% browser zoom), classic six-width harness, both smokes, docs,
  complexity (721 functions), design tokens, compilation, Ruff and Bandit pass.
- Pinned wheel/sdist build, archives and clean wheel install pass. Automatic
  sdist install remains unavailable without setuptools; a separate clean
  install seeded with pinned build tools passed all 27 asset identity checks.
- Durable D1–D14 dispositions, the new Recovery zoom finding, evidence hashes
  and remaining limits: @docs/31-combined-e2e-verification-2026-11-06.md.
  Screen-reader validation, Markdown table/nested-list rendering and the
  maintainer decisions remain open. Original design checkout, main, releases
  and remotes remain untouched.

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

**[NOTE] The resident window grows with active work, and that is a standing
pressure worth watching.** After the cut the file measured 64,666 characters /
9,478 words / 1,091 lines. Adding the four 2026-10-06 entries brought it to
**78,050 / 11,470 / 1,307** — **+21% in one session**. That is still 75% smaller
than the 313,968-character pre-split figure, and every added entry satisfies the
rule above, so nothing is misfiled. But the rule is date-based, not size-based,
and several consecutive active days of substantive work will push this back
toward the problem @docs/24 §C1 diagnosed. **If it passes roughly 100,000
characters, the cut-off date is the wrong lever and the next boundary should be
size-driven instead** — with the resident digest kept at its current length and
everything above it moved to `docs/archive/`. Recording the trend here is cheaper
than rediscovering it later.

**This is a move, not a deletion.** Every archived entry describing a decision
has a surviving owning doc: the ADR set,
@docs/19-safe-local-source-update-implementation-plan.md,
@docs/20-skill-hygiene-report-implementation-plan.md,
@docs/21-p0-trust-gate-and-release-metadata-hardening-plan.md, and — for the
2026-09-11 audit batches — the per-finding dispositions in
@docs/13-audit-remediation-status-2026-09-11.md. If an archived entry disagrees
with an owning doc, the owning doc wins.

## Current state (measured 2026-11-06 on backend continuation)

**[SPEC]** On the final backend source tree, all **1,324 tests** pass on each
of **Python 3.10, 3.11, 3.12, 3.13 and 3.14**. Complexity: **721 functions
across 16 files**, passed with no ratchet increase. Compilation, docs, design
tokens, both smokes, Ruff and Bandit passed. Pinned wheel/sdist builds and
archive inspection passed; wheel clean install passed, and a separate fresh
sdist environment seeded with pinned build tools passed the full asset probe.
The automated sdist clean-install gate still reports unavailable because its
fresh environment lacks setuptools. No combined frontend or Windows execution
is claimed. Full findings, commits, limits and parent integration checks:
@docs/30-backend-continuation-2026-11-06.md.

## Historical state (measured 2026-10-08 on the UI redesign pass)

**[SPEC]** Every number below was produced by running the gate on this tree.

- `python3 -m unittest discover -s tests` — **1,232 tests, OK** (~99 s), and
  re-verified on **Python 3.11, 3.12, 3.13 and 3.14** — every interpreter CI runs.
- `python3 check_complexity.py` — **689 functions across 16 files**, new-function
  budget ≤ 15, no ratchet increase.
- `python3 check_docs.py` — **PASSED**. `python3 smoke_store.py` and
  `python3 smoke_web.py` — both green. `python3 check_design_tokens.py` — **PASSED**
  (new: re-derives every contrast ratio in `styles.css` from the WCAG formula).
  `browser_harness.py` — green at 320/400/640/900/1280/1440, zero console
  errors, zero failed requests, no overflow. Bandit 0 issues; Ruff clean.
- **1.0.2 is tagged at `ef9bfd6`; TestPyPI has shipped it and PyPI is waiting on
  the maintainer.** The external TestPyPI outage that blocked this has cleared
  (its `/_/oidc/audience` endpoint answers 200 again), the failed job was
  re-run, and `publish to TestPyPI` **succeeded**. `publish to PyPI` is
  `waiting` on the `release` environment's required reviewer — it did not
  proceed unattended. pypi.org still reports v1.0.1 as latest until that
  approval is given. **The hashes recorded for this release were wrong** (three
  sets exist, none of them the artifact that shipped); see the 2026-10-06 entry
  above, which verifies the published bytes against the tag instead.
- The five Dependabot action PRs are still open and all still **request
  changes** (re-verified 2026-10-06).
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
- **Agent-scope document reuse is keyed on the content hash, never on
  `(mtime_ns, size)`, and switches itself off above its bound.** An
  `(mtime_ns, size)` key is blind by construction to a same-size edit inside the
  filesystem's mtime granularity, and this repository has macOS and Windows legs.
- **A cache hit re-stamps `observed_at`; it does not serve a stale one.** A hit
  is still a real observation, and `observed_at` is surfaced by
  `insights.provenance_summary()` for a tool whose pitch is trustworthy
  provenance.
- **Registry provenance is never reused.** A provenance sidecar is a filesystem
  fact, not a fact about `SKILL.md`'s bytes; re-probing keeps a stale sidecar
  visible as drift.
- **A gate that reports PASS about a path it cannot see is not a gate.** Two such
  instances are now on the record: BUG-13/SEC-13 (the sdist member inspector) and
  `b50ca1e` (the action-pin gates, blind to 9 of 29 sites). Prove a gate by
  mutation, not by inspection.
- **The 1.0.2 artifact hashes of record are those built from `522b81f`.** The
  `6733da9` hashes remain only inside the superseded 2026-09-23 entry.

## Resident entry index (2026-09-23 … 2026-11-07)

**[NOTE]** 40 indexed entries; full text follows.

| Date | Entry |
|---|---|
| 2026-11-07 | Phase B: nine stdlib checks in `risk_scan()` with a warning-context rule |
| 2026-11-07 | R12 consumer rows and the ignored-frontmatter finding |
| 2026-11-07 | R11: read-only `skills` CLI lockfile evidence in the hygiene report |
| 2026-11-06 | Integrate the verified performance work into main |
| 2026-11-06 | Complete the performance session's missing verification |
| 2026-11-06 | Refuse oversized tar metadata before chunked reads |
| 2026-11-06 | Classic screens, 10,000-instance scale and screen-reader checks closed three gaps |
| 2026-11-06 | Research-roadmap backend items (docs/28, docs/29) |
| 2026-11-06 | The prototype-final design shipped as a v2 interface on real data |
| 2026-10-30 | Monetization: sell the outcome, not the manager |
| 2026-10-30 | User research: the real pain is skills the model cannot see |
| 2026-10-08 | The UI was redesigned against a contract, and the redesign found a product defect |
| 2026-10-06 | TestPyPI recovered, 1.0.2 shipped, and the recorded hashes were wrong |
| 2026-10-06 | A search body cost one document read per row, to compute nothing |
| 2026-10-06 | G8 shipped inside the tagged 1.0.2, and five records still said it had not |
| 2026-10-06 | The action-pin gates were blind to half the workflow |
| 2026-10-06 | The default Library view stopped re-deriving an unchanged document |
| 2026-10-06 | Dark-theme panes had no boundary, only a 1px border |
| 2026-10-06 | The 1.0.2 artifacts were rebuilt and independently verified |
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

## 2026-11-06 — Continuation verified and prepared for parent integration

**[SPEC]** Seven coherent implementation commits complete R14/R6/R4/R10 and
the reproduced parent backend fixes; the source tree passes 1,324 tests on
each supported Python version, the repository ladder and static checks. The
handoff at @docs/30-backend-continuation-2026-11-06.md lists every fixed,
doc-clarified and unconfirmed finding, actual packaging evidence, remaining
approval decisions and exact combined-tree retests. No frontend tree, original
dirty checkout, remote branch or release was mutated. Both writers are idle;
parent should merge normally and retest both interfaces with frontend R9
header commit `fe46552` present.

## 2026-11-06 — Continuation: prompt HTTP rejection and parameter errors

**[SPEC]** An over-limit declared Content-Length now returns 413 without
waiting for the sender to finish, and closes the connection so unread bytes
cannot be reused as a request. History zero limits and blank context windows
are clean 400s instead of silent defaults. Live socket regressions and existing
parameter contracts pass; the previous drain assertion was updated to require
closure without reading. API docs now distinguish independent template listing
from routes that depend on a broken skills layout. Final full suite: 1,324
tests on Python 3.10–3.14; complexity lowered/removed stale entries only, both
smokes, docs, design tokens and static checks passed.

## 2026-11-06 — Continuation: CLI findings and precise contracts

**[SPEC]** Reproduced CLI search aborts on a refused link and doctor encoding
misclassification now have per-entry handling and explicit decode evidence.
Bare `db` requires an action, ports are range-checked before bootstrap, `@file`
token input must be readable UTF-8, and no-tokens also applies to JSON totals.
Directory export destinations return a clean error; explicit file replacement
remains supported. Docs correct exact-scope view, command-local JSON flags,
add-name matching, global-view token fields, archive preflight and doctor's
limited aggregate headline/project behavior. Seven new CLI tests pass along
with the 1,324-test suite on each supported interpreter; no command, Store
method, dependency, Python-floor or schema change was added.

## 2026-11-06 — Continuation: scoped mutation and damaged-copy recovery

**[SPEC]** The reproduced edit/toggle race now serializes read/validation/write,
toggle, restore and sync destinations on one canonical document lock. Document
symlinks are refused for mutation; contained directory aliases share the key.
Force sync preserves undecodable old bytes before replacement, with manual
binary-snapshot recovery and unchanged source-state semantics. Scoped raw reads
are lossy reports, while rewrites remain strict, and detail no longer logs the
strict decoder's document-byte repr. A cleanup fault no longer rolls back a
successfully installed copy; retained backups survive retries and one refusal
allows other destinations to complete. Thirteen regressions cover processes,
thread storms, aliases, corrupt input, snapshot failure, rollback and partial
cleanup. Full five-version suite: 1,324 tests each; Store and web smokes passed.
Broader source-update/data-root/recursive-identity locking limits remain open.

## 2026-11-06 — Continuation: R4 native JSON observations

**[SPEC]** Scoped list/search/detail adds fresh `native_state` without changing
manager on/off fields. Selected Claude and OpenCode JSON sources are parsed
once per scope batch with explicit missing/invalid/unavailable states, source
order and bounds. Effective state stays unknown because managed/CLI/environment
and other sources are incomplete. Nine helper tests and a real REST regression
cover precedence, wildcard ordering, freshness, corrupt/large/duplicate input,
FIFO refusal, partial evidence and no settings/document mutation. Codex TOML
is deferred without changing Python >=3.10 or dependencies. The final suite
passed all 1,324 tests on each of Python 3.10–3.14.

## 2026-11-06 — Continuation: R10 hidden-Unicode advisory evidence

**[SPEC]** `insights.risk_scan` names format, bidi and tag characters with
escaped code points, Unicode names and occurrence counts. Output is bounded
to 32 field/code-point pairs with omitted counts, remains advisory, and never
rewrites documents or declares them safe. Four red-first tests plus the
insights contracts cover hidden controls, ordinary Unicode, repeated controls,
bounds and read purity. Nested metadata and companion files are outside this
scan. The final five-interpreter suite passed with 1,324 tests each.

## 2026-11-06 — Continuation: R6 portability and physical findings

**[SPEC]** Compatibility mappings remain errors with a string-portability
explanation. The validator warns once for unknown top-level keys (escaped for
display), and lints the combined description/when_to_use 1,536-character cap.
Hygiene retains one finding per physical identity while exposing bounded alias
paths, scopes and supplied state flags; identical separate copies remain
separate. Seven focused tests cover boundary lengths, spec keys, empty input,
physical aliases, distinct copies and truncation. Final source-tree suite:
1,324 tests passed on each of Python 3.10, 3.11, 3.12, 3.13 and 3.14.

## 2026-11-06 — Continuation: R14 malformed request handling

**[SPEC]** JSON decoding now catches recursion failures and rejects containers
deeper than 64 levels before downstream metadata handling. Unknown-user project
expansion was outside the guard in both workspace observation and effective
resolution; both now return a clean 400 without echoing the supplied path.
Red-first route tests reproduced project 500s and accepted deep PATCH metadata;
the same tests now pass across POST/PATCH and both project routes.

## 2026-11-06 — Research-roadmap backend items (docs/28, docs/29)

**[SPEC] R1 / S1 — tar caps now apply while reading.** `archive.validate_members`
called `tar.getmembers()` before any cap, so a 13 KB bz2 of repeated headers
reached 373 MB RSS. Imports now open the tar through `archive.open_tar()`: the
decompressor is chosen by magic bytes and wrapped in `_BoundedReader`, which
refuses any read or seek past `MAX_ARCHIVE_DECOMPRESSED_BYTES` (expanded budget
+ 8 MiB of header slack) *before* delegating, and members are pulled one
`tar.next()` at a time so the 200-member, per-member and expanded caps stop the
walk early. A PAX header declaring 64 MB is refused before it is allocated.
Every decompressor failure (bz2 `OSError`, `LZMAError`, `EOFError`,
`RecursionError` from chained headers) becomes `StoreError`. Red-first: the
many-headers and PAX-bomb tests measured 17.4 MB and 101 MB peak traced memory
on the old code against a 12 MB budget; both pass now, and valid plain/gz/bz2/xz
exports still import.

**[SPEC] R2 / S2 — manager sidecars never survive external intake.**
`.skillsmgr-provenance.json` and `.skillsmgr-source-lock.json` are
unauthenticated; a well-formed forgery needs no secret, and one made `Store.get`
report `registry_provenance` with `hash_verified: true` for a skill that was
never fetched. `Store.add` now copies with `archive.ignore_manager_sidecars`,
archive import strips them from the whole extracted tree (skills and trash), the
multipart upload inherits `Store.add`'s behaviour, and `registry.validate_snapshot`
refuses either name at any depth (it blocked only root provenance before). The
registry commit writes provenance after `Store.add`, into the installed copy, and
purges the install if that write fails. Red-first: all 7 assertions in
`tests/test_audit_r2_intake_sidecars.py` fail on the old code. **Consequence:**
an export → import round trip drops provenance and lock evidence by design.
**Open:** sidecars inside agent scopes are still trusted as read, and
`scopes.sync_skill` copies them between scopes; binding evidence to an install
needs a maintainer decision.

**[SPEC] R5 / S3 — lock files moved under the data root, with a timeout.**
Lock files were in `tempfile.gettempdir()/skillsmgr-locks`, so two processes
with different `TMPDIR` values never excluded each other, the shared directory
had no ownership check, and an unreleased lock blocked forever. They now live in
`<data>/locks/` (owner-only, symlink- and foreign-owner-refused, files opened
`O_NOFOLLOW`), chosen from roots `Store` registers on construction. A blocking
acquisition gives up after `MUTATION_LOCK_TIMEOUT` (60 s) with
`LockTimeoutError` (`StoreError`, 409). Red-first: 6 of 6 tests in
`tests/test_audit_r5_lock_root.py` fail on the old code (with only the new
names shimmed so the module imports). One existing test,
`test_record_runs_never_touches_skill_files_or_the_index`, enumerated every
file under the data root and now excludes `locks/`: those are empty
coordination files, not skill or index data.

**[SPEC] R9 / S4 — every POST declares JSON.** `do_POST` now rejects any POST
whose media type is not `application/json` (415), except the multipart
source-update upload. A `text/plain` purge used to answer 200 and delete data.
Three existing test clients (`smoke_web.py`, `test_audit_route_table`,
`test_webapp`) sent bodyless POSTs without the header and were updated to send
it. **Both web UIs do the same and will get 415 until `domain.js` defaults the
header** — handed to the frontend session, not edited here.

## 2026-11-06 — The prototype-final design shipped as a v2 interface on real data

**[SPEC]** Branch `ui/prototype-final` adds `skillsmgr/webui/v2/` (served at
`/v2/`): Home, Skills, Skill page with edit, Sync map, Inbox, Recovery, New
skill, a dark theme and a shortcut list, all on the existing REST routes. The
classic interface and every existing contract are untouched; see
@docs/08-web-ui.md.

**[NOTE] Real data changed three design decisions.** On the maintainer's machine
all 2,061 records are `uncategorized`, so the category shelf falls back to A–Z.
The prototype's "Can't be read" would have labelled 169 of Claude Code's skills
broken; 168 were refused symlinks the agent reads fine, now "Linked elsewhere".
And the prototype's "older copy" has no basis (no version order exists), so the
reference is the majority content hash and a tie asks the user.

**[SPEC] Verified, not asserted.** Against an isolated fixture in a real browser:
replacing a damaged copy, making copies match, editing and saving to two scopes,
and each Undo all round-tripped on disk. A new contrast test caught the
prototype's muted text at 4.41:1 on the sunken surface; it is now ≥ 4.5:1.

**[?] Open.** v2 is not the default route; the maintainer decides when to flip
it. `GET /api/skills?scope=all` is 22.7 MB on this machine and both interfaces
pay it on every load.
## 2026-10-30 — Monetization: sell the outcome, not the manager

**[NOTE]** Research only; no product source changed. Recorded in
@docs/27-monetization-five-pass-analysis-2026-10-30.md, which challenges the
Pro/Team model in @docs/14-competitive-product-business-strategy-2026-09-15.md.
Measured starting point: 1 GitHub star, 121 PyPI downloads last month, while
the 7,079-star category leader is funded by a tip jar. Platforms now cover the
single-agent on/off job (Claude org provisioning, managed settings,
`skillOverrides`), so the proposal is a services-first year. It starts with a
fixed-price Agent Setup Audit delivered with this tool. Skill CI and team setup
profiles would follow only if paid audits ask for them, with written kill
criteria. Reddit and X evidence (475 tweets, 14 threads) shows users describe
the pain as skills, MCP servers and AGENTS.md drifting across several agents
and machines. Widening scope that way needs maintainer decision MON-Q2.

## 2026-10-30 — User research: the real pain is skills the model cannot see

**[NOTE]** Research only; no product source changed. Recorded in
@docs/26-user-research-skills-context-2026-10-30.md. Key findings: Claude
Code's skill listing gets 1% of the context window and silently drops
descriptions on overflow (users report 12 of 91 skills never firing for that
reason); Claude Code now ships native per-project `skillOverrides`
(`on`/`name-only`/`user-invocable-only`/`off`), so the global
`SKILL.md.disabled` rename is the wrong default for that consumer; the most
upvoted adjacent requests are private skill sources (82 👍), symlinked skill
dirs (53 👍) and a restorable skill lockfile (49 👍). Twelve ranked
recommendations are proposals only — several need approval under locked
constraint 5. A same-day v1.1.0 pass read X on a logged-in session and
found a **defect in this app**: observed state ignores each agent's native
switch, so a skill Codex disabled in `config.toml` would be shown as Active.
Verified latent, not live: this machine's only `[[skills.config]]` entry is
`enabled = true`. Instagram and Hacker News remain
unread and are listed as gaps.

## 2026-10-08 — The UI was redesigned against a contract, and the redesign found a product defect

**Where the design came from.** Three rendered prototypes were produced and
the maintainer selected **A — Warm Instrument** (`.specs/prototypes/`), whose
composition, density and honesty spine were kept. Its **palette was replaced**:
it used parchment `#faf7f1` with copper `#9e4415` and a near-black +
vermilion dark theme, which are the first two entries in every published
AI-tell catalogue, and the mechanical scanner independently flagged the second.
Ground and accent were re-derived from the subject — a cool bone proof sheet
with one reserved ink — and **every replacement value was measured before it
was written**. The first pass had five failures, two of which were thresholds
I had invented for the check itself; those were corrected rather than argued
away.

**The mechanism, not the styling.** `DESIGN.md` at the repository root is the
contract: tokens, their measured ratios, the reasoning, and the refused
defaults a later pass must not slide back into. `check_design_tokens.py`
re-derives every ratio from the shipped stylesheet on each run. It was proved
by mutation, not by inspection: a lightened text token, a lightened control
border, and a font-CDN reference were each injected, and each was caught.

**Two defects the gates could not see, both found by measuring.**

1. **The vendored typeface covered no ASCII.** Six `@font-face` rules
   shipped, 176 KB of woff2 sat in the package, and every "is the font
   vendored" check passed — while every page rendered in the fallback, because
   all six rules carried only the `latin-ext` unicode-range. A probe element
   set in "IBM Plex Sans" measured *the same width* as one set in a face that
   does not exist (310px vs 310px). A correct build measures 339px. This is the
   "declared but never shipped" failure the anti-slop scanner names, one level
   down: the file exists, the declaration exists, and the page still renders
   in the wrong typeface. The test now asserts glyph coverage and that every
   `src` resolves.
2. **The typeface did not ship at all.** `package-data` listed
   `webui/static/vendor/*` but not `webui/static/fonts/*`. Every other gate
   was green; an installed copy would have declared IBM Plex and rendered in
   the fallback, permanently. Found because the build tool was installed and
   the artifacts were built — the gate would have caught it, but nothing was
   running it.

**The product defect the redesign surfaced.** The backend carries a precise
reason in `decode_error`; the UI collapsed every reason into the word
**"Malformed"**. On this machine that mislabelled **301 of 1,962 instances**
and pointed the reader at the wrong remedy. The skill's `SKILL.md` is not
corrupt — it is a symlink whose target sits outside the scope's root, and the
fix is to stop linking or to copy the tree in. That refusal is deliberate and
documented (SCOPE-2 in `loader.py`): a followed link would let a write land
outside the managed root. **Nothing about the security model changed here; only
the name did.** `linked` joined the observed-state vocabulary,
`malformedDocument` stayed true so every existing count and predicate kept
working, Quality gained a bucket rather than letting those rows fall out of
the summary, and the Overview now says *"292 instances are a symlink the tool
refuses to follow because its target sits outside that scope's root"* instead
of counting them as corrupt.

**[SPEC] Three checks in this repository were pinning copy rather than
behaviour, and all three broke when the copy improved.** The G8 template test
asserted the literal `{ 'sr-only': uniformStateLabel }`; the webui contract
asserted `identity.label` and `identity.stateLabel`; and the browser harness
matched an attention-queue item by the exact title "malformed or unaddressable"
— which failed on all six viewports the moment the wording was corrected, with
the product right. Each now asserts the invariant: suppression is a class and
never a removal, the row names what it saw and keeps the full identity
reachable, and the queue item is selected by a stable `data-attention` key.
This repository has now shipped that exact class three times; the fix is the
same each time.

**[NOTE] Rows group their observed identities by state, problems first.**
A logical skill can exist in seven scopes; one chip per scope made every row
three or four lines tall and a 638-row list unscannable. Now the scopes that
agree are one line and the ones that do not are their own line above them,
which is the question this tool exists to answer. Presentation only — it groups
values the seam already returned and asserts nothing the backend did not
report.

**[SPEC] Verified, not asserted.** 1,232 tests pass on **Python 3.11, 3.12,
3.13 and 3.14** (all four interpreters CI runs). `check_complexity` (689
functions), `check_docs`, both smokes, Bandit (**0 issues**) and Ruff
F821/F822/F823 (clean) all pass. The browser harness is green across
320/400/640/900/1280/1440 with zero console errors, zero failed requests and no
overflow. A wheel and an sdist were built with the pinned, hash-verified
toolchain: **19 web UI files** each, fonts present in both, Vue sha256
matching, and a **clean install passes** including the font assertions.

**[?] What is still open.** The **human perceptual review** remains
outstanding, exactly as it did for G8: no non-Chromium engine, no forced-colors
mode, no 200%/400% zoom, no screen reader. The harness renders and measures; it
does not sign off. Separately, whether a skill directory symlinked into a
shared store *should* be refused is a product decision about the containment
model, not a UI one, and it was deliberately not taken here.

## 2026-10-06 — TestPyPI recovered, 1.0.2 shipped, and the recorded hashes were wrong

**[SPEC] The external blocker cleared and the release moved.** The failing call
was `audience retrieval failed: repository at test.pypi.org responded with
unexpected 503` — against
`https://test.pypi.org/_/oidc/audience`, the OIDC trusted-publishing endpoint.
Re-probed later the same day: **200**, three consecutive samples, with
`/simple/`, `/legacy/` and `/pypi/<name>/json` all 200 too. Re-running the
failed job was the whole fix, exactly as the earlier entry said it would be.
`publish to TestPyPI` **succeeded**. `publish to PyPI` is `waiting` on the
`release` environment, whose required reviewer is `udayvarmora07` — so it did
not and cannot proceed unattended. Not worked around by publishing straight to
PyPI: the TestPyPI stage is the gate, and skipping it is the failure mode SEC-7
exists to prevent.

**[SPEC] Verifying the published bytes found that the recorded hashes were
wrong.** Three different hash sets exist for 1.0.2 and **none of them is the
artifact that shipped**:

| source | wheel | sdist |
|---|---|---|
| `task.md` | `efee22f3…` (369,397 B) | `817c46f5…` (348,984 B) |
| this log's 2026-10-06 entry | `032ae368…` (380,909 B) | `fc0f34cb…` (361,035 B) |
| **actually published** | **`db2c07bb…` (380,909 B)** | **`a2962d4a…` (360,164 B)** |

Two sets were recorded for one version. The documented "42/42 checks" and the
"46/46 byte-identical" verifications were real — but they verified *a local
build*, and the release workflow built its own.

**[SPEC] The content is correct, verified against the tag rather than the docs.**
All 46 `skillsmgr/` files are present, none extra, none missing. Exactly two
differ from the working tree — `scopes.py` and `webapp.py` — and both are
byte-identical to their `ef9bfd6` versions, because those are the only two files
changed after the tag. `check_package_data.py --dist-dir` PASSes on the exact
published bytes (6 web UI files, 2 example files, correct Vue sha256, MIT), and
TestPyPI's own recorded digests match the download, so nothing was corrupted in
transit.

**[?]** Why the bytes differ, honestly bounded: this log already records that the
sdist is **not** byte-reproducible (build-generated members get wall-clock
mtimes, and the gzip header MTIME is wall-clock), and that the wheel is
byte-identical across builds **only with `SOURCE_DATE_EPOCH` pinned**. The
release workflow does not pin it, so a CI rebuild can never match a
locally-recorded hash. That is a real reproducibility gap and it is recorded as
such rather than guessed at.

**[NOTE] Why this survived a gate that reports PASS — the repository's fourth
recorded instance of its own lesson.** `verify exact artifacts` verifies the
artifacts it builds in that run; it never compares them against the hashes
written in `task.md`. So the documented hashes were never actually pinned to any
release, and a green `verify` job was consistent with every one of them being
wrong. That is *a gate that reports PASS about a path it cannot see is not a
gate*, after BUG-13/SEC-13 (the sdist member inspector) and the two action-pin
blind spots. Worth noting that three of the four instances were found by
*measuring the artifact* rather than by reading a gate.

## 2026-10-06 — A search body cost one document read per row, to compute nothing

**[SPEC]** The open item recorded a measured cost — 498 ms at 600 skills, 600
cache hits and 600 misses — and a correct explanation: a reuse-cache *hit* still
costs a file read plus the sha256 that forms the key. Two of its three
conclusions were wrong.

**The call site was wrong.** The per-row `Store.get()` was never in
`Store.search()`; it was in `scopes._global_search_records`, which the route
reaches through `search_all()`. And the route's own `Store.search()` call was
**dead code**: `scope = (qs.get("scope", [""])[0] or "global").strip() or "global"`
coerces `""`, `"   "` and an absent parameter all to `"global"`, so the
`if scope in ("all", "")` test could never take its `else`. That branch is
removed, and a source-reading test now fails if a `Store.search` call reappears
in `_route_search_get` — a behavioural test cannot see it, because it is
unreachable.

**The waste was bigger than "a per-row SQLite query".** `Store.get()` returns
`body` **from the index** (`SELECT *`) and spends its document read only filling
`Store._OBSERVED_KEYS`, which does not include `body` and which this caller
discarded entirely. So the old form re-read and re-hashed **every document in
the library to derive metadata nobody looked at**. The reuse cache could not
help: proving the bytes unchanged *is* the file read.

**[SPEC] Fixed with one `SELECT name, body`** over the existing private
`Store._index_rows` read seam — not a new public `Store` method, which is
locked-constraint 5. `scopes` already reached a private `Store` method
(`_check_store_layout`), so this crosses a line that already exists.

Interleaved A/B, hermetic, best-of-5 per arm:

| rows | old (per-row `Store.get`) | new (one `SELECT`) | change |
|---|---|---|---|
| 200 | 100.0 ms | 32.6 ms | **3.07x, −67.4%** |
| 1,000 | 564.7 ms | 183.9 ms | **3.07x, −67.4%** |

Flat across a 5x change in size, because both arms are O(n) and only the per-row
constant moves.

**[NOTE] "Byte-identical" was checked, and was nearly a false claim.** At 300
skills every compared field matched. At 1,000 skills the first run reported the
outputs as *differing* — the only field, across all 1,000 rows, was
`observed_at`, and only because the two arms ran one second apart
(`12:04:52Z` vs `12:04:53Z`). That field records *when the read happened*, so
two runs seconds apart cannot agree. Recorded here rather than smoothed over,
because the same check at a smaller size would have said "identical" and been
wrong at the larger one.

**[SPEC] The body *source* is deliberately unchanged** — still the index,
exactly as `Store.search()` has always used it — so `skills-mgr search` and the
web route keep agreeing on what a body match means. Making this route
filesystem-authoritative would leave the CLI disagreeing with it, which is worse
than the staleness it removes. That is now pinned by a test, so a future
"fix" cannot silently open the split.

**Red-first:** the counting test reports **5 `Store.get()` calls before, 0
after**; the dead-branch test fails against the pre-change `webapp.py`. Two
further tests pin the preserved behaviour (bodies attached, never `None`;
unresynced disk edits not searchable) and pass both before and after, which is
what guard tests are for.

The complexity ratchet caught the dict comprehension as `+1` on
`_global_search_records`; that was **restored by extraction**
(`_indexed_bodies`), not by re-baselining. Removing the dead branch then left
`_route_search_get`'s baseline stale-high at 8 against a measured 7, so the
baseline was refreshed — and the refresh was **audited before committing**:
**0 entries raised, 1 lowered, 1 added, 0 removed**, every other diff line a
`lineno` shift. Refreshing downward is required, because it is the only way the
guard keeps pointing at reality.

No CLI command, public `Store` method, SQLite schema, or dependency changed.
The two doc lines describing the old "public `list()`/`get()` seam" are updated
in the same commit.

## 2026-10-06 — G8 shipped inside the tagged 1.0.2, and five records still said it had not

**[SPEC] This is a documentation-integrity finding, not a UI finding.** The
§G8 structural UI work landed in `6f72f0d` and merged as `f11549a`, both
**inside the tagged `v1.0.2`**. All three recommendations in @docs/24 §G8 are
implemented, pinned by 27 tests in `tests/test_g8_ui_structure_contracts.py`
(`Ran 27 tests ... OK`), and rendered evidence is committed at
`.specs/evidence/ui-g8-release-1.0.2-2026-10-06/` with a sha256 per capture.

**[SPEC] Five records still described it as not done.**

| Record | What it said |
|---|---|
| `task.md` | `- [ ] Structural UI changes (audit G8): rendered review required, not a diff.` Written by `911ca48` at 10:53; the merge landed at 13:04 the same day and **no later commit touched the line.** |
| `docs/06-progress-log.md:1194` | `**[NOTE] Not done, deliberately.** … the structural UI changes (G8) are visual decisions that need rendered review` — written by `a1aceea1`, and **never superseded**, so the log's own last word on G8 was "not done". |
| `docs/SESSION-CONTEXT.md` | **Zero occurrences of "G8".** Its top block is v1.14.0 on base `b50ca1e`, which predates the merge. |
| `CHANGELOG.md` | **Zero occurrences of "G8"**, and none of the attention queue, the overview rework, or the Library density work — in the release that ships all of them. |
| `docs/08-web-ui.md` | §Overview-first shell still pointed its visual evidence at the pre-G8 `.specs/evidence/ui-overview-2026-09-21-final/`. |

**[NOTE] The CHANGELOG one is the sharpest.** `v1.0.2` is tagged and staged; its
publish job fails only on a TestPyPI outage (re-probed this session, still 503
on `/api/v1/`, 200 on `/simple/`). The moment that clears, the release job
publishes an artifact whose changelog never mentions its largest user-visible
change.

**[SPEC] What is genuinely still open, and was left open.** The G8 *review*,
not the G8 *work*: `REVIEW.md` records no human perceptual review, no
non-Chromium engine, no forced-colors mode, no 200%/400% zoom and no screen
reader. The harness renders; it does not sign off. Marking that done from a
green render would be exactly the fabricated-evidence class this repository
keeps refusing, so the line now records the implementation as complete and the
human gate as outstanding.

**[NOTE] The cause is the one already recorded on 2026-10-05**, where five items
turned out to be *missing* from `task.md` rather than merely unchecked: a
finding closed in a commit does not close its checklist line in the same commit.
Two more stale lines surfaced in the same pass — `C4 #4` (shipped in `cf40958`,
still `[ ]`) and a `D1 (lazy observations)` line asking for a decision the
maintainer had already made and a later entry in the same section recorded. All
three are corrected now. The prevention is still ownership, not a gate:
`check_docs.py` cannot catch a checklist claim with no source surface to drift
from.

## 2026-10-06 — The action-pin gates were blind to half the workflow

**[SPEC] This is the security finding of the session.** Both action-pin gates
required a leading `- ` before `uses:`, but a step may equally put `uses:` on the
line after `- name:`. Both forms are used in this repository, and the two-line
form was invisible to **both** gates.

- **20 of 29** `actions/*` sites were checked; **9 were not**: `setup-node`, both
  `upload-artifact`, all five `download-artifact`, and
  `actions/attest-build-provenance` — **the release provenance attestation**.
  The third-party gate had the identical blind spot, and `softprops/action-gh-release`
  (the GitHub Release upload step) is written exactly that way, so it was unchecked
  too.
- `EXPECTED_FIRST_PARTY_SHAS` already carried entries for `upload-artifact`,
  `setup-node`, `download-artifact` and `attest-build-provenance`. **They were
  written expecting enforcement and were never read.**

**[SPEC] Proven red-first rather than argued.** Repinning the release attestation
to a floating `@v2` tag left `test_sec14_every_first_party_action_is_pinned`
**green**; so did repinning it to 40 zeros. Both gates reported PASS about a path
they could not see — the repository's own documented failure mode, and the second
recorded instance of it after BUG-13/SEC-13, where the sdist member inspector
reported PASS about a member it could not see.

Fixed on `main` as `b50ca1e`, **test-only**: both parsers now treat the dash as
optional and four new tests pin it, each mutation-caught. The real tree passes with
the fix, so all nine previously-invisible sites already carried correct reviewed
SHAs — **the gate was blind, not the workflows wrong.** No workflow file, product
source, CLI surface, Store method, schema, or dependency changed.

**[NOTE] A gate limitation found while documenting this.** `check_docs.py`'s
source-symbol check indexes a class's `FunctionDef`/`AsyncFunctionDef` bodies but
not class-level attribute assignments, so a documented reference to a real class
constant is reported as a nonexistent symbol. It fired on `Store`'s
`_OBSERVED_KEYS` tuple while writing the `loader.py` entry. The prose was
reworded to keep the claim rather than weaken it, and the limitation is left
recorded here rather than fixed, because `check_docs.py` and `tests/**` are owned
by another session. Extending the extractor to class attributes is a one-line
change for whoever holds those files.

**[NOTE] What this means for the five open Dependabot PRs.** Before the fix, #19
(the attestation), #18 (`setup-node`) and #17 (`softprops/action-gh-release`) would
**not** have been caught by either gate at all. #15 and #16 write `- uses:` on the
dash line and were always covered. See @docs/23-github-actions-dependency-pr-review-2026-09-23.md.

## 2026-10-06 — The default Library view stopped re-deriving an unchanged document

**[SPEC] §D1's second half.** `scopes.list_all()` — the default Library view —
re-read and re-parsed every document in every agent scope on every request,
measured at 3.7 s over 1,965 real skills. This was the same O(n) full-document-parse
cost the *global* half stopped paying in the 2026-10-04 §D1 pass, and D1's fix did
not touch it: agent-scope rows go through `loader.scan_dir` → `load_skill` per row,
not through `_observe_index_row`.

`loader.py` now holds a bounded, process-local reuse of the derived record.

**[SPEC] The key is the sha256 of the document bytes**, plus the filesystem facts
that are *not* facts about those bytes (`disabled`, `document_conflict`,
`decode_error`) and the document path. The audit had recommended `(mtime_ns, size)`.
**Measurement rejected that**, and the reason is the kind worth keeping: an
`(mtime_ns, size)` key is blind *by construction* to a same-size edit landing inside
the filesystem's mtime granularity — 1 s on HFS+, 2 s on FAT, routinely 1 s on
network mounts — and this repository has macOS and Windows legs. Reading the
document is required to learn the hash anyway, and it is the cheapest part of the
work, so the guarantee is exact rather than statistical.

Three measured findings shaped the design:

- **The audit's "scoped to one request" buys a cold request nothing** —
  instrumented at exactly 1.00 parse per row per request. The win is warm, and warm
  dominates: `webui/app.js` calls `loadSkills()` after ~20 mutation sites and
  deliberately never caches a completed read.
- **A bounded LRU cannot beat a sequential scan larger than itself.** 5,000
  documents through a 1,000-entry bound re-derived 5,001 on the second pass — 0%
  reuse, strictly worse than no cache. `document_reuse_worthwhile()` measures up
  front and switches reuse off above the bound, so the caller keeps exactly its
  pre-reuse behaviour with none of its cost.
- **Registry provenance is deliberately not reused.** A provenance sidecar is a
  filesystem fact, not a fact about `SKILL.md`'s bytes, so it is re-probed on every
  load and a stale or malformed sidecar stays visible as drift.

Interleaved A/B, 9 alternating rounds, hermetic `HOME` and data dir:

| rows | warm pre → post | cold pre → post |
|---|---|---|
| 1,200 | 387.5 → 273.5 ms (**−29.4%**) | 424.9 → 419.7 ms (**−1.2%**) |
| 2,000 | 711.1 → 495.6 ms (**−30.3%**) | 655.0 → 655.6 ms (**+0.1%**) |

**[NOTE] Cold is flat and is reported as flat.** GC churn from retention is the
largest residual, about 6 points of cold cost. A single before/after pair was not
used for this measurement — the 2026-10-04 §D1 entry records that a single pair
showed no change at all where interleaving showed −34%.

**[SPEC] A defect found in review, not by the tests: a cache hit returned a stale
`observed_at`.** That silently changed the field from "when this read happened" to
"when this process first derived these bytes". It is not cosmetic:
`observed_at` is in `Store._OBSERVED_KEYS`, so the **global** path was affected
too, and `insights.provenance_summary()` surfaces it — for a tool whose pitch is
trustworthy provenance, that is the wrong answer. A hit *is* still a real
observation (the bytes were re-read and hashed to prove they are the same bytes),
so the fix re-stamps `observed_at` on **the copy that leaves the cache**; the
stored entry is not mutated and the content-derived fields are not re-stamped.

**Three existing test docstrings had stated as their reason for stripping the field
that it "is stamped with `datetime.now()`".** That reasoning was false for cached
rows between the introduction and the fix. The lesson is the one already written
into this log's own §A1 entry, applied again: **a green subagent report is not a
review.** The suite was green on the tree that carried the defect.

Red-first: 16 mutations, 16 caught. Two guards initially had no teeth and the
*tests* were rewritten rather than the behaviour accepted; the bounding test went
vacuous once the size guard landed and was rewritten to exercise eviction.

No CLI command, Store method, SQLite schema, runtime dependency, or frontend build
step changed. The registry-provenance probe and the containment realpath are both
security contracts and are deliberately retained. See the `loader.py` entry in
@docs/02-modules.md.

## 2026-10-06 — Dark-theme panes had no boundary, only a 1px border

**[SPEC] docs/24 §G2 #7, the half that was still open.** The list and detail panes
measured **1.00:1** against each other in dark theme — identical surfaces — and
were separated only by a 1px border at **1.46:1**. Two regions a user is expected
to read as different things, indistinguishable and without a perceivable edge.

- The divider is now **3.43:1** against the detail pane and **3.96:1** against the
  list pane; the panes themselves are **1.16:1**.
- Two adjacent dark *surfaces* cannot reach 3:1 tastefully — near-black `#06080a`
  against `--surface` is 1.30:1 — so the contrast rides on the boundary, which is
  where WCAG 1.4.11 actually applies.
- The list pane recedes onto `--bg`. Elevating it to `--surface-2` instead would
  have dropped `--border-strong` to **3.01:1** and degraded every form control, so
  that was measured and rejected rather than assumed.
- **Light theme is deliberately untouched.**

**[NOTE] The audit's other half was already satisfied.** Pushing `--border-strong`
toward 3:1 was completed on 2026-10-04; the real defect was that **the pane
divider never used it.** A boundary token existing at a compliant contrast is not
the same as the element that needs the boundary actually referencing it — the same
"present but unwired" class as §A4's stale complexity baseline.

## 2026-10-06 — The 1.0.2 artifacts were rebuilt and independently verified

**[SPEC]** Built from the current tree (`522b81f`) with the pinned hash-verified
toolchain (`setuptools==84.0.0`, `build 1.2.2.post1`, Python 3.12.3),
`--no-isolation`:

| artifact | bytes | sha256 |
|---|---|---|
| `skill_control_plane-1.0.2-py3-none-any.whl` | 380,909 | `032ae3682afb50ebbfc5e252ef40c26fa7e29d9bdb2e91ccfdea158746c86ce8` |
| `skill_control_plane-1.0.2.tar.gz` | 361,035 | `fc0f34cb723774dedc5566a0bdfed267d435c3b13d66ddac14584ca82791982e` |

**[SPEC] These supersede the 2026-09-23 hashes** (`2d7beb9b…` / `3e8aa27a…`, from
commit `6733da9`). That entry is marked as superseded in place rather than left
alongside, so two hash sets never read as equally current in the resident file.

**[SPEC] Verified with a second implementation rather than by trusting the gate**,
because this repository has a recorded incident of a gate reporting PASS about
something it could not see. 42/42 checks: `skillsmgr/examples/skills-manager-management/`
is present in **both** artifacts **and** in an actual `site-packages` install; 46/46
`skillsmgr/` files are byte-identical across the two artifacts and against the
source tree; no `tests/`, `docs/`, `.env`, database or bytecode in either.

**[NOTE]** `check_package_data.py --dist-dir` PASSes on both. `--dist-dir --install`
gives the wheel a clean-install PASS; the **sdist is UNAVAILABLE** through that
path because `venv` no longer seeds `setuptools` on 3.12 and the sdist needs
`--no-build-isolation`. That gap was closed by verifying the pinned
`setuptools-84.0.0` wheel's sha256 against the lock **before** installing it, then
completing the sdist smoke by hand.

**Reproducibility, honestly bounded.** With `SOURCE_DATE_EPOCH` pinned the **wheel
is byte-identical across two builds**. The **sdist is not**: all file payloads
match, but 7 build-generated members get wall-clock mtimes and the gzip header
MTIME is wall-clock. Content-reproducible; container bytes are not.

**[SPEC] Still blocked on maintainer approval.** Nothing was tagged, published, or
pushed.

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

**[NOTE] Both G2 #7 and G8 have since landed** — G2 #7 in the 2026-10-06 dark-theme
entry above, G8 in `6f72f0d`/`f11549a` inside the tagged `v1.0.2`. What remains
for G8 is the *human* perceptual review, not the rendered one. Publishing 1.0.2
still requires maintainer approval, and is additionally blocked on an external
TestPyPI outage. Marked in place rather than left to read as current, following
this file's precedent for the superseded 2026-09-23 artifact hashes.

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

**[NOTE] SUPERSEDED 2026-10-06.** The hashes below were built from commit
`6733da9` and are **not** the current candidate. The current 1.0.2 artifacts,
built from `522b81f`, are `efee22f3…` (wheel, 369,397 bytes) and `817c46f5…`
(sdist, 348,984 bytes) — see the 2026-10-06 entry above. They are retained here
as the dated record of the 2026-09-23 slice, not as the artifact of record.

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

**[NOTE] Re-verified 2026-10-06.** The purge regression is fixed (finding A1) and
`main` is green on all 15 jobs. All five PRs are still open, all five still
recommend **request changes**, and all five recorded SHAs are confirmed exact
against the `uses:` line each PR introduces. **Three of the five reasons changed**:
#17 and #19 need a rebase and (for #19) a different action version, and #18's
actual failure is a missing `Tighten the Node tool cache permissions` step its
branch predates — not the ESM migration this entry predicted. See the
re-verification section at the top of @docs/23-github-actions-dependency-pr-review-2026-09-23.md.

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
