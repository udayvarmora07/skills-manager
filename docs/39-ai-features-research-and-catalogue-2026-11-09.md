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
| A3 | Collision / overlap judge on `near_duplicate_candidates()` pairs, position-swapped, with optional merge draft | #35319, #27721, #10238; Cisco overlap check | Next |
| A4 | Listing-budget fitter: shorten the fewest descriptions to fit the agent's budget, each verified by A1 | #56710, #19679, #19090; existing `claude_listing` estimate | Next |
| A5 | Review briefing for registry fetch and update review: plain-language diff, description-vs-behaviour, new capabilities/URLs; every claim cites a hunk | vercel-labs/skills #11; Snyk, arXiv 2610.19264 | Next |
| A6 | Demote-only finding explainer for `risk_scan` hits: may lower severity with a cited reason, never raise or hide | Cisco `--adjudicate`; false-positive complaints | Planned |
| A7 | Regression pack: saved prompt sets per skill, re-run after an edit, sync or model change, with history files | r/ClaudeAI versioning threads; skill-creator post | Planned |
| A8 | Eval runner with and without the skill (feeds existing `evals.py`), plus "still needed?" capability-uplift flag | SkillForge, Anthropic guidance, SkillsBench | Planned |
| A9 | Ask your library, answers validated against real names/paths | opencode #7846 (120) | Planned |
| A10 | Porting notes per consumer, facts from `key_support`, model writes prose only | opencode #34498 (70), codex #29989 (62), claude-code #31005 (613) | Planned |
| A11 | Verified drafting: draft a SKILL.md from a brief, then A1 + validate before it can be saved | §2.4 | Planned, gated |
| A12 | Profile suggester from repo signals | codex #9799, claude-code #30355 | Idea |
| A13 | Conciseness / splitter advisor (move bulk to `references/`) | claude-code #74473 (210k tokens) | Idea |
| A14 | CI mode: fixed-seed trigger test with machine-readable output | Sanity on X; skill-linter SARIF | Idea; needs CLI approval |
| — | Transcript mining with a cloud model | Weak demand; very high privacy cost | **Not recommended**; local-model-only if ever |
| — | Auto-applying any model output | Every pass | **Never** |

## 4. Decisions taken to start (answers to docs/33 §8)

**[SPEC]** Taken on 2026-11-09 under the maintainer's instruction to build the best features end to end; each is reversible.

- **D-AI-1 transport:** stdlib `urllib`, no SDK, no new dependency (locked constraint 3). Two request shapes cover every listed provider. Redirects are refused so a key cannot follow one.
- **D-AI-2 providers:** Anthropic, OpenAI, OpenRouter, Gemini (OpenAI-compatible endpoint), Ollama, LM Studio and any custom OpenAI-compatible base URL. Plain `http` only to loopback.
- **D-AI-3 key storage:** the provider's environment variable wins; otherwise a key typed in the UI is stored in `<data>/ai/settings.json` (0600, directory 0700). It is never returned, logged, exported or written to the ledger; changing provider forgets it. No OS keychain yet.
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

**[?]** The trigger test is a *simulation by the configured model*, not the agent's real router; results are labelled as estimates. Fidelity against a real agent's choices has not been measured.

## 6. Verification

**[NOTE]** `tests/test_ai_features.py` (19 tests) runs against a fake provider on 127.0.0.1 that speaks both request shapes. It covers key privacy (header only, never in body, settings, ledger or responses), env precedence, clearing, plain-http refusal, redirect refusal, caps refusing before any request, estimate mode sending nothing, never-fires detection, held-out-verified recommendation, read-only behaviour and the HTTP routes. The v2 pages were exercised in a browser against the same fake model: settings save, connection test, trigger test, improve and apply (the edit left a snapshot). No real provider was called.

## 7. Next

A3 overlap judge, A4 budget fitter and A5 review briefing, in that order, each reusing the A0 seam and the A1 router.
