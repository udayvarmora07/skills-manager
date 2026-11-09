# Codex Handoff — Remaining Work

**Version 0.1.0**

**AI manifest**: Self-contained handoff for a Codex (or any agent) session picking up skills-manager after 2026-11-09. It lists every remaining task from `task.md` and @docs/39-ai-features-research-and-catalogue-2026-11-09.md, split into work an agent can do now, work that needs a maintainer decision first, and work only a human can do. §1 is a paste-ready prompt; §3 has one prompt per task. State verified on `main` at `b78ee32` (CI 15/15 green, 1,801 tests on Python 3.11–3.14).

## 1. Paste this into Codex to start

```text
You are working in the skills-manager repository (local skill manager for AI coding
agents: stdlib Python CLI + loopback web UI with vendored Vue, no build step).

Read first, in this order:
1. AGENTS.md (operating manual and locked constraints)
2. docs/SESSION-CONTEXT.md (fast re-anchor and gotchas)
3. docs/40-codex-handoff-2026-11-09.md (this handoff: task list and acceptance criteria)
4. docs/39-ai-features-research-and-catalogue-2026-11-09.md (AI feature rules)

Then pick the first unchecked task in section 3 of docs/40 that has no
"needs decision" or "human only" label, and complete it end to end:
- write a failing test first, then the change;
- keep every new function at complexity <= 15 (python3 check_complexity.py);
- never raise an existing complexity-baseline entry; extract helpers instead;
- update docs/02-modules.md, docs/08-web-ui.md (every /api route must be listed),
  docs/39, task.md and the top of docs/06-progress-log.md;
- run the full verification ladder in section 2 on every Python version available;
- commit with a descriptive message, then continue with the next task.

Hard rules:
- Filesystem is the source of truth; never change the SQLite schema or SCHEMA_VERSION.
- No new CLI command, Store method or runtime dependency without maintainer approval.
- AI features: model output is never applied without an explicit user action through an
  existing reviewed write path; skill text is untrusted input (wrap with
  ai.untrusted_block); every run has an estimate step that sends nothing; keys are
  never returned, logged or written outside <data>/ai/settings.json.
- The web server's loopback binding is its only security boundary; never forward,
  tunnel or publish its port.
- Do not do anything in section 5 (human only). Stop and ask on section 4 items.
- Do not touch the dirty primary checkout at ~/skills-manager (branch
  feat/v2-feature-parity) or the redesign/ui-v2 worktree; work in your own branch
  or worktree based on origin/main.
```

## 2. Verification ladder

**[SPEC]** Run all of it before every commit; a green run on one interpreter says nothing about the others.

```bash
for v in 3.11 3.12 3.13 3.14; do py="$(uv python find $v)"; PYTHONDONTWRITEBYTECODE=1 "$py" -m unittest discover -s tests 2>&1 | grep -E '^(OK|FAILED|Ran )'; done
PYTHONDONTWRITEBYTECODE=1 python3 smoke_store.py
PYTHONDONTWRITEBYTECODE=1 python3 smoke_web.py
PYTHONDONTWRITEBYTECODE=1 python3 check_docs.py
PYTHONDONTWRITEBYTECODE=1 python3 check_complexity.py
python3 check_design_tokens.py
for f in skillsmgr/webui/v2/*.js skillsmgr/webui/*.js; do node --check "$f"; done
```

UI changes also need a browser check. The pattern used for the AI pages: run a fake OpenAI-compatible provider on 127.0.0.1 (`tests/test_ai_features.py::FakeProvider`) and the web server with an isolated `HOME` and `SKILLS_MANAGER_DATA`, then drive `/v2/#/tools/<page>`.

## 3. Tasks an agent can do now

Ordered by value. Each task is independent unless it says otherwise.

### 3.1 AI hardening follow-ups (do first, small)

```text
Harden the shipped AI features in skillsmgr/ai*.py and skillsmgr/webui/v2/ai-center.js:
1. <data>/ai/usage.jsonl grows forever and usage_summary() reads all of it on every
   settings request. Keep only the last 90 days (rewrite atomically when the file
   passes 1 MiB) and test 0, 1 and 100,000 lines.
2. A browser that disconnects mid-run keeps spending until the run ends. Between
   model calls, stop the run when the client socket is closed (webapp handler) and
   record a partial run; test with a fake provider that counts calls.
3. Add a "Past runs" list to the AI pages using the existing GET /api/ai/runs and
   GET /api/ai/runs/<id>, rendered as text only.
4. Saved regression prompts: add view and delete (POST /api/ai/prompt-sets with
   replace:true already exists; add per-prompt removal in the UI).
Acceptance: red-first tests for 1 and 2; UI checked in a browser against the fake
provider; docs/08 and docs/39 updated.
```

### 3.2 A11 verified drafting

```text
Implement docs/39 A11 "verified drafting" in a new module skillsmgr/ai_draft.py with
POST /api/ai/draft-skill {scope, brief, name?, estimate?}.
- The model drafts a SKILL.md (name, description <= 1024 chars, body <= 500 lines) from
  the user's brief. Treat the brief as untrusted.
- Before it can be used: run validator.validate_text on the draft, then run the A1
  trigger test with the draft added to the scope's listing (ai_skills._route with the
  draft as an extra entry) on generated prompts plus near-misses.
- Return the draft, validation issues, its hit rate and which existing skills it
  steals prompts from. Research (SkillsBench) shows unverified drafts do not help,
  so the UI's "Use this draft" button only fills the existing New skill form
  (unsaved) and is disabled while validation errors exist.
- v2: new tool page "Draft a skill" in model.js toolGroups + ai-center.js.
Acceptance: tests with the fake provider (valid draft, invalid draft, a draft that
steals another skill's prompts); browser check; docs updated.
```

### 3.3 A13 conciseness and splitter advisor

```text
Implement docs/39 A13 in skillsmgr/ai_concise.py, POST /api/ai/concise
{scope, name, estimate?}. Claude Code issue #74473 shows a bundled skill injecting
~210k tokens. Deterministic first: token counts per section via tokens.count_tokens.
The model proposes which sections move to references/<file>.md and a shortened
SKILL.md body that links to them. Show token before/after (computed, not claimed).
Applying must go through the existing source-update review (source_update) so the
whole tree change is reviewed and snapshotted; never write files directly.
Acceptance: tests; the proposal round-trips through a real source-update review in a
test; browser check.
```

### 3.4 A12 profile suggester

```text
Implement docs/39 A12 in skillsmgr/ai_profiles.py, POST /api/ai/suggest-profile
{project, scope, estimate?}. Use the existing workspace observation
(adapters.project_observation; the project path must stay contained, outside paths
redacted) to collect repo signals (file extensions, manifest names such as
package.json/pyproject.toml, top-level dirs; no file contents). The model proposes a
named profile of existing skill names; drop names that do not exist. Saving uses the
existing POST /api/catalog/profiles after the user confirms.
Acceptance: tests including a project outside managed roots; browser check.
```

### 3.5 Trigger-test fidelity study (needs the maintainer's key and an agent CLI)

```text
Write tools/ai_fidelity/run.py (dev-only, not packaged): for a saved prompt set,
compare the trigger test's simulated choice with the skill Claude Code actually loads
(headless `claude -p` with a prompt that asks it to report which skill it used, or
parse its JSON stream for Skill tool calls). Report agreement per skill. Do not run it
without the maintainer present: it spends their key and runs their agent.
Record results in docs/39 §5 replacing the [?] about fidelity.
```

### 3.6 Repository chores

```text
- Review the two open Dependabot branches (actions/checkout 7.0.1, actions/setup-node
  7.0.0) against docs/23 rules: pin full SHAs, check Node runtime, run CI. Record a
  disposition in docs/23; merge only if green and approved.
- origin/agents/milestone5-research-user-needs (one commit, c5a7161, 2026-09-05) is
  not in main. Read it, say whether anything is still useful, and ask before deleting.
- Local branch backup/pre-message-rewrite and two old stash entries are archives
  from earlier sessions: list them for the maintainer; do not delete without a yes.
```

## 4. Needs a maintainer decision first (prepare a proposal, do not build)

- **`skills-mgr ai …` CLI surface** for the AI features, and a CI mode (A14, fixed seed, machine-readable output). New CLI commands are locked constraint 5.
- **Per-project profiles** that translate one toggle into each agent's native setting (Codex's switch is user-level only and must say so). See @docs/35-open-decisions-resolved-2026-11-07.md.
- **Microsoft APM `apm.yml` interoperability** instead of a new lockfile.
- **Stale → archive** with pin, restore and dry run (Hermes-Curator style).
- **Transcript-based usage counts** and a **project skill lockfile**. Transcripts are private; any AI use there would be local-model only.
- **Monetization questions MON-Q1…MON-Q5** in @docs/27-monetization-five-pass-analysis-2026-10-30.md.
- **OS keychain storage** for AI keys (D-AI-3 follow-up).

## 5. Human only — an agent must not do these

- **Publish 1.0.2 to PyPI**: approve the `release` environment in GitHub Actions. TestPyPI already shipped.
- **First real-provider run** of the AI features with the maintainer's own key (Tools → AI settings → Test connection, then one small trigger test).
- **Visual sign-off** of the redesigned tool pages and v2 (non-Chromium engine, forced colors, 200%/400% zoom).
- **Spoken screen-reader sign-off** using the @docs/32-continuation-verification-2026-11-06.md walkthrough.
- **Five consented usability sessions** and dated external screenshots.

## 6. Current state to rely on

- `main` = `b78ee32`; CI green on all 15 jobs. Worktrees left on purpose: the dirty primary checkout (`feat/v2-feature-parity`), `~/overnight-ui/worktree` (`redesign/ui-v2`, 142 commits not in main, in progress), and the worktree holding `main`.
- AI features shipped: A0–A10 except A6 standalone (its demote-only opinions ship inside A5). Code: `skillsmgr/ai.py`, `ai_skills.py`, `ai_overlap.py`, `ai_budget.py`, `ai_review.py`, `ai_evals.py`, `ai_ask.py`, `ai_port.py`; UI: `skillsmgr/webui/v2/ai-center.js`; tests: `tests/test_ai_features.py` (36).
- No real AI provider has been called yet; every AI test uses the fake provider.
