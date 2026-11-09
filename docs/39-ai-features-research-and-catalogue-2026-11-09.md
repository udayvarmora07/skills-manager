# AI Features — Research and Catalogue

**Version 0.1.0**

**AI manifest**: Research record and ranked catalogue of bring-your-own-key (BYOK) AI features for skills-manager, written 2026-11-09. It extends @docs/33-ai-features-design-2026-11-06.md with community, competitor, GitHub, BYOK-practice and literature research, records the decisions taken to start building, and tracks which features are shipped. Shipped surfaces: `skillsmgr/ai.py`, `skillsmgr/ai_skills.py`, `/api/ai/*` (see @docs/08-web-ui.md) and the v2 *AI assist* tool pages. Unshipped ideas are proposals. Figures quoted from vendors, READMEs or single papers are not independently verified and are marked as such.

## 1. How this was researched

**[NOTE]** Five parallel research passes on 2026-11-09, each writing a sourced report:

| Pass | Sources | Access notes |
|---|---|---|
| Communities | Reddit (r/ClaudeAI, r/ClaudeCode, r/codex, r/cursor), X, Hacker News, V2EX, dev blogs | Reddit read through an OpenCLI browser session (its API adapter is login-walled); X through `opencli twitter search`; others through Exa and the HN Algolia API |
| Competitors | skill managers/registries, prompt managers, scanners, BYOK desktop tools | Product pages via Jina Reader and `gh api` |
| GitHub demand | anthropics/claude-code, anthropics/skills, openai/codex, anomalyco/opencode, google-gemini/gemini-cli, vercel-labs/skills | Issues ranked by reactions through the REST search API |
| BYOK practice | Zed, Continue, Cline, aider, simonw/llm, Ollama, LM Studio, Raycast | Key storage, cost control and loopback-server threats |
| Literature | arXiv, Anthropic engineering, Hamel Husain, Eugene Yan, conference talks | Some items were read from abstracts only |

All fetched text was treated as data. Nothing was posted, liked or logged into.

## 2. What the evidence says

**[NOTE]** The findings converge strongly.

1. **The pain is selection, not storage.** Skills that are installed and listed are still not chosen.
   - GitHub: claude-code [#9716](https://github.com/anthropics/claude-code/issues/9716) (75 reactions) and [#30387](https://github.com/anthropics/claude-code/issues/30387): listed, not invoked.
   - Budget truncation: codex [#19679](https://github.com/openai/codex/issues/19679) (40), [#19090](https://github.com/openai/codex/issues/19090) (9 of 60 skills never reach the model), claude-code [#56710](https://github.com/anthropics/claude-code/issues/56710) (122 descriptions dropped).
   - Literature: arXiv 2605.24050 reports up to a 21% pass-rate drop at 202 skills driven by wrong-skill selection; arXiv 2610.18522 reports loaded-skill recall falling from 73.6% to 27.4% with 1,000 distractors.
2. **Nobody can tell whether a description is good, and wording matters a lot.** A community measurement of 20 skills over 1,000 labelled prompts found 46.3% recall, raised to 67.3% by one added sentence per description (single source, unverified).
3. **Rewriting works in one pass, but only if verified.** arXiv 2606.30775: one rewrite informed by false positives and false negatives matched manual tuning (79.2% vs 79.4% F1); further iterations moved F1 under 0.5%. A large train/validation gap signals genuinely overlapping scope.
4. **Unverified AI-written skills do not help.** SkillsBench / SkillAxe (arXiv 2606.10546): self-generated skills scored about −1.3 points against +16.2 for curated ones. Drafting must be gated by measurement.
5. **The existing verification tooling is unreliable.** Anthropic's own skill-creator trigger loop has six open 0%-recall issues (e.g. anthropics/skills [#1169](https://github.com/anthropics/skills/issues/1169)). Static linters are crowded (skillcheck, skilldoctor, skill-distill); verified outcomes are scarce (SkillForge, ai-shakespii).
6. **Libraries are growing past what people can audit.** claude-code [#35319](https://github.com/anthropics/claude-code/issues/35319): one organisation went from 67 to 183 skills in a month with no usage evidence.
7. **Security of third-party skills is a live concern.** Snyk ToxicSkills reports 13.4% of skills with a critical issue; Skill-Inject (arXiv 2602.20156) reports up to 80% attack success and argues filtering will not fix it; arXiv 2610.19264 finds 59% of declaring skills understate their bundle's capabilities.
8. **Users distrust AI in tools for cost, privacy and quality.** They count dormant-skill tokens, note that BYOK is not private when a vendor proxies requests, and want to see what is sent before it is sent.

## 3. Ranked catalogue

**[SPEC]** Ranking is by evidence strength × fit with this tool's identity (filesystem truth, review-first, advisory evidence). "Shipped" means implemented, tested and documented on this branch.

| # | Feature | Evidence | Status |
|---|---|---|---|
| A0 | **BYOK foundation**: Anthropic + OpenAI-compatible + local endpoints, env-first key, run/day token caps, egress statement, usage ledger | All passes | **Shipped** |
| A1 | **Trigger test (library arena)**: the agent's own listing with every other skill as a distractor; never-fires / unreliable / lost-to / near-miss false triggers; repeated, order-shuffled | §2.1–2.2; gap no competitor fills | **Shipped** |
| A2 | **Verified description rewrite**: candidates from failures, re-tested; recommended only if better overall and not worse on held-out prompts | §2.3, skill-creator split, GEPA | **Shipped** |
| A3 | Collision / overlap judge: candidate pairs from the near-duplicate heuristic, a description-word prefilter and user picks; judged in both orders; verbatim-checked conflicts; boundary sentences and merge idea | #35319, #27721, #10238; Cisco overlap check | **Shipped** |
| A4 | Listing-budget fitter: shorten the largest descriptions to fit the agent's budget, each verified by A1 | #56710, #19679, #19090; existing `claude_listing` estimate | **Shipped** |
| A5 | Review briefing for registry fetch and update review: plain-language diff, description-vs-behaviour, new capabilities/URLs; every claim cites a hunk | vercel-labs/skills #11; Snyk, arXiv 2610.19264 | **Shipped** (includes A6's demote-only opinions) |
| A6 | Demote-only finding explainer for `risk_scan` hits: may lower severity with a cited reason, never raise or hide | Cisco `--adjudicate`; false-positive complaints | Planned |
| A7 | Regression pack: saved prompt sets per skill, re-run after an edit, sync or model change, with history files | r/ClaudeAI versioning threads; skill-creator post | **Shipped** |
| A8 | Eval runner with and without the skill (feeds existing `evals.py`), plus "still needed?" capability-uplift flag | SkillForge, Anthropic guidance, SkillsBench | **Shipped** |
| A9 | Ask your library, answers validated against real names/paths | opencode #7846 (120) | **Shipped** |
| A10 | Porting notes per consumer, facts from `key_support`, model writes prose only | opencode #34498 (70), codex #29989 (62), claude-code #31005 (613) | **Shipped** |
| A11 | Verified drafting: draft a SKILL.md from a brief, then A1 + validate before it can be saved | §2.4 | **Shipped** |
| A12 | Profile suggester from repo signals | codex #9799, claude-code #30355 | Idea |
| A13 | Conciseness / splitter advisor (move bulk to `references/`) | claude-code #74473 (210k tokens) | **Shipped** |
| A14 | CI mode: fixed-seed trigger test with machine-readable output | Sanity on X; skill-linter SARIF | Idea; needs CLI approval |
| — | Transcript mining with a cloud model | Weak demand; very high privacy cost | **Not recommended**; local-model-only if ever |
| — | Auto-applying any model output | Every pass | **Never** |

## 4. Decisions taken to start (answers to docs/33 §8)

**[SPEC]** Taken on 2026-11-09 under the maintainer's instruction to build the best features end to end; each is reversible.

- **D-AI-1 transport:** stdlib `urllib`, no SDK, no new dependency (locked constraint 3). Two request shapes cover every listed provider. Redirects are refused so a key cannot follow one.
- **D-AI-2 providers:** Anthropic, OpenAI, OpenRouter, Gemini (OpenAI-compatible endpoint), Ollama, LM Studio and any custom OpenAI-compatible base URL. Plain `http` only to loopback.
- **D-AI-3 key storage:** the provider's environment variable wins; otherwise a key typed in the UI is stored in `<data>/ai/settings.json` (0600, directory 0700). It is never returned, logged, exported or written to the ledger; changing the provider **or the endpoint** forgets it, so redirecting the endpoint cannot carry an old key to a new host. No OS keychain yet.
- **D-AI-4 web routes that spend:** allowed, because the user asked to enter keys in the UI. The loopback binding is the only boundary, stated on the settings page: any local process can reach the server and spend up to the caps. The caps are the mitigation; a per-launch token was judged not to stop a same-user process that can read the page.
- **D-AI-5 first slice:** A0 + A1 + A2, web UI first. **No CLI command was added** (locked constraint 5); a `skills-mgr ai …` surface awaits approval.
- **D-AI-6 budgets:** defaults 300,000 input tokens per run and 2,000,000 per UTC day, user-adjustable (1,000 to 50,000,000). Preflight uses `tokens.count_tokens`; a run over its cap is refused before anything is sent.
- **D-AI-7 default model:** none. The user chooses; Anthropic suggestions are listed. The result labels name the model, so results from different models are never confused.

## 5. How A1 and A2 work

**[SPEC]**

- **Listing.** `ai_skills.build_listing(scope)` takes the scope's enabled, readable, addressable skills, skipping `disable-model-invocation: true`, and caps each `description` + `when_to_use` at 1,536 characters as Claude Code does. At most 600 skills.
- **Routing pass.** Prompts go in batches of 10 with the full listing; the model returns `{id, skill, runner_up}`. Names it invents count as invalid answers and are reported. Each repeat shuffles listing order with a fixed seed (position-bias control).
- **Prompts.** User-written (`text => skill` or `=> none`) or generated per chosen skill, with optional near-miss prompts that should load none of them.
- **Report.** Per skill: hit rate, verdict (`fires` ≥ 67%, `unreliable`, `never-fires`), the skills that won its prompts. Overall recall, near-miss false-trigger rate, invalid and missing answers.
- **Rewrite.** Prompts are split alternately into train and held-out per expected skill. The model sees only train failures, the skill's description, the first 4,000 body characters and rival descriptions. Each candidate is re-routed on every prompt; it is `recommended` only when its overall score beats the current description, its held-out score is not lower, and its recall is not lower.
- **Applying** a candidate uses the existing `PATCH /api/skills/<name>?scope=` route, so the edit takes a snapshot and is undoable from Recovery.
- **Untrusted input.** Skill text and prompts are wrapped in `<untrusted>` blocks with a standing instruction to treat them as data; the model has no tools; output must be JSON and is validated against real names.
- **Files.** Finished runs are saved as `<data>/ai/runs/<kind>-<UTC>-<hex>.json` (newest 50). Calls are logged to `<data>/ai/usage.jsonl` with counts and an input hash only.
- **Retention and disconnects (handoff 3.1).** When the usage ledger exceeds
  1 MiB and contains dated rows older than 90 UTC days, those rows are removed
  by atomic replacement coordinated with appends. Malformed rows do not break
  today's counts. HTTP runs check for a closed client between calls and save
  a partial run with `status: disconnected` and completed-call usage. An
  already-running provider request finishes; no next call is started after
  closure is detected. Past runs on every AI page lists the latest 20 saved
  runs and opens their full contents as text.

**[?]** The trigger test is a *simulation by the configured model*, not the agent's real router; results are labelled as estimates. Fidelity against a real agent's choices has not been measured.

## 6. Verification

**[NOTE]** `tests/test_ai_features.py` (19 tests) runs against a fake provider on 127.0.0.1 that speaks both request shapes. It covers key privacy (header only, never in body, settings, ledger or responses), env precedence, clearing, plain-http refusal, redirect refusal, caps refusing before any request, estimate mode sending nothing, never-fires detection, held-out-verified recommendation, read-only behaviour and the HTTP routes. The v2 pages were exercised in a browser against the same fake model: settings save, connection test, trigger test, improve and apply (the edit left a snapshot). No real provider was called.

## 7. A3 overlap judge

**[SPEC]** `ai_overlap.overlap_judge` gathers at most 12 candidate pairs without AI: the existing near-duplicate heuristic, a description-word Jaccard prefilter (≥ 0.18 after stop-words, which catches differently named skills doing the same job) and pairs the user names. Each pair goes to the model twice, A-then-B and B-then-A. If the relation differs between orders it is reported as `uncertain`; if the recommendation differs it becomes `review`. A conflict survives only when both quotes, whitespace-normalised, occur in the skill they are attributed to; others are dropped and counted. Boundary sentences link to Improve, which still has to prove a measured gain before recommending anything.

## 8. A4 listing-budget fitter

**[SPEC]** `ai_budget.fit_budget` takes Claude Code's budget from the existing `claude_listing` estimate (settings-aware) or a caller-supplied `budget_chars` for other agents. Within budget it returns without any model call. Otherwise it picks the largest descriptions (at most 10) until shortening each to about 45% (never below 120 characters) could cover the overflow, asks for shorter versions, generates three prompts per chosen skill and routes them once with the current descriptions and once with all shorter versions together. A shorter version is `safe` only when its skill wins at least as many prompts as before. `fits` says whether the safe savings cover the overflow; when they do not, the page points to turning skills off or name-only.

## 9. A5 review briefing

**[SPEC]** `ai_review.review_briefing` reads a pending review without changing it: for an update, each changed file's bounded unified diff plus the full text of added files from the staged candidate; for a registry fetch, the snapshot's files. At most 25 files and 40,000 characters are sent with the advisory risk findings. Claims, capabilities (network, shell, credentials, file-write, persistence) and description mismatches are kept only when their quote, whitespace-normalised and with diff markers removed, occurs in the file they name. The summary is shown but labelled unchecked. Each risk finding may receive an opinion (`likely-real`, `likely-false-positive`, `unclear`), shown beside the original, which keeps its severity. The v2 review panels embed the briefing as an opt-in *Explain with AI* step with the usual estimate-then-send.

## 10. A7 regression pack

**[SPEC]** Any trigger-test result can be saved as the scope's regression prompts (`<data>/ai/prompt-sets/<scope>.json`; duplicates merged; at most 20 per skill and 500 per scope). A trigger test with `saved: true` re-runs them (skipping prompts whose skill is no longer listed) and compares every skill's hit rate with the most recent earlier saved-prompt run for that scope, listing each change and flagging regressions. The comparison spans whatever changed in between, edits or a different model; the run labels say which model answered each.

The trigger page also lists saved prompts and removes one exact text/expected
pair at a time after confirmation. Replacement preserves up to 500 entries;
an `expected_prompts` precondition rejects stale tabs with HTTP 409. Partial
disconnected runs are excluded from regression baselines.

## 11. A8 eval runner

**[SPEC]** `ai_evals.run_evals` takes a library skill's `evals/evals.json` (at most 20 cases per run; input files are read with containment and bounded at 8,000 characters each). Every case runs twice: with the whole `SKILL.md` as system instructions, and with only a neutral agent instruction. Outputs (at most 1,500 output tokens, possibly cut off) are passed to the existing `evals.record_runs`, which grades them with the case's deterministic assertions and writes the next `iteration-N` atomically. No model grades anything, so cases without assertions are reported as ungraded. `not-needed` means every graded case passed both with and without the skill: the skill may add nothing for this model. It is a prompt, not a deletion.

## 12. A9 ask your library

**[SPEC]** `ai_ask.ask_library` sends the question with skill names, the scopes holding them and the first 300 description characters, never bodies. Above 300 skills it narrows by word overlap with the question first. Suggested names that are not real skills are dropped and counted, so every link in the answer opens a skill that exists.

## 13. A10 porting notes

**[SPEC]** `ai_port.porting_notes` lists, without AI, every frontmatter key (other than `name` and `description`) the target consumer's documentation does not list, and fixed-pattern references to one agent's conventions (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `$ARGUMENTS`, `${CLAUDE_*}`, `~/.claude` and `~/.codex` paths, `mcp__` tool names, Claude Code tool names, subagents) with the line they occur on. Only when facts exist is the model asked to explain them; each note must name a listed fact or it is dropped. "Not documented" means the target's own page does not list the key, not that the key is rejected.

## 14. A11 verified drafting

**[SPEC]** `ai_draft.draft_skill` treats the brief as untrusted data and
produces a SKILL.md containing name, description and body. The draft passes
`validator.validate_text` plus explicit limits of 1,024 description characters
and 500 body lines. A name already installed in the scope, including a hidden
or disabled skill, cannot be reused. Unsupported frontmatter is rejected so
the New skill form can preserve the draft's fields.

Valid drafts are measured using A1 with the full scope listing as distractors.
Generated prompts include the draft, near misses and a bounded sample of
existing skills; the report discloses how many existing skills were sampled.
A stolen prompt is one the baseline routes to its expected existing skill
but the augmented listing routes to the draft. Missing or invalid answers are
reported; incomplete measurement cannot enable use. These are simulations by
the configured model, not evidence of the real agent's routing fidelity.

Estimate mode budgets the drafting and verification calls without contacting
the provider. V2 Tools → Draft a skill shows the draft and evidence as text.
Use this draft fills the existing New skill form, unsaved, and is disabled for
validation errors or an unmeasured result. The user reviews that form and
explicitly creates the skill through the existing scope-aware write path.

## 15. A13 conciseness and splitter advisor

**[SPEC]** `ai_concise` counts tokens per section before contacting a model,
ignoring Markdown headings inside fenced code. The selected primary document
is untrusted input. The proposal contains a shorter body linking to new
`references/*.md` files; the existing frontmatter and companion files are
preserved. Reference paths, duplicates, collisions, links and size limits are
validated. Counts before and after are computed with `tokens.count_tokens`,
including the new references separately and identifying the counting method.
These counts measure the primary document and added references, not a claim
of lower total library usage or equivalent behavior.

The captured tree is bounded and tied to the installed source content hash across
generation. Concurrent content changes refuse the proposal. A private
candidate goes through `source_update.prepare_local_update`; the v2 page
hands the resulting review to the existing Update from folder review UI.
Only its explicit approval/commit path applies the full tree and keeps a
snapshot. Pending UI reviews are cancelled on input or in-app route changes
unless ownership has transferred to the source-update page. Estimate mode
sends no request and creates no candidate or review. No installed skill is
changed by generation.

**[NOTE]** Safe capture currently requires POSIX directory-descriptor and
no-follow support; unsupported platforms return a clean error. The existing
source-update helper still reads its live manifest through filesystem paths;
this change does not certify that helper against hostile concurrent path
swaps. Commit hashes cover file names and bytes, not mode or empty-directory
changes made after review. The advisor rechecks those attributes through
staging; the existing commit contract remains unchanged.

## 16. Not yet built

- **A12** profile suggester.
- **A14 CI mode**: needs a CLI surface, which needs maintainer approval (locked constraint 5).
- **Fidelity**: measure the trigger simulation against a real agent's choices before treating its numbers as more than estimates.
