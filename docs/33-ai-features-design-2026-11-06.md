# AI Features Design — Skills Manager

**Version 0.1.0**

**AI manifest**: Proposal, not shipped work. It covers which LLM features belong in skills-manager, the rules they must follow, a bring-your-own-key (BYOK) architecture, costs, threats, and the decisions the maintainer must make first. Written 2026-11-06 after the maintainer asked for BYOK LLM support and for deeper thinking about AI features. The only shipped AI path today is the SkillSpector hook's optional LLM stage (`external_scan.py`). Model facts come from the bundled Claude API reference (cached 2026-10-06) and must be rechecked before implementation. Nothing here is approved until the decisions in §8 are answered.

## 1. The question to answer first

**[NOTE]** Many tools now wrap an LLM around their existing surface. The real question is narrower: what can a model tell this user, about their own skills, that no deterministic check here can? Research already done in this repo gives the answer:

- Skills fail **silently at selection time**. Claude Code gives its skill listing 1% of the context window and drops descriptions on overflow; users report 12 of 91 skills that never fired (@docs/26-user-research-skills-context-2026-10-30.md).
- Whether a description *triggers* is a property of a model reading it next to every other description. A regex cannot measure that; a model can.
- Overlapping skills, drift between copies, and third-party skills of unknown intent are also judgement problems. The hygiene report finds the candidates but cannot judge them.

So the AI features worth building **measure and explain how agents will read the user's skills**. They do not replace the deterministic evidence this tool already produces.

## 2. Non-negotiable rules

**[SPEC]** These follow from the product's identity (filesystem truth, review-first, advisory evidence) and apply to every feature below.

1. **Proposals and evidence, never authority.** No model output changes a file, gates an install, sets `valid`, or picks a winner. Any change a feature suggests goes through an existing reviewed write path: source-update review/apply, edit with snapshot and Undo, or the create form.
2. **Every output is labelled.** Each result records provider, model id, prompt version, effort, date and input hash. Outputs vary between runs, so none becomes a recorded fact about a skill.
3. **Skill content is untrusted input.** Bodies and descriptions can carry prompt injection aimed at this very review ("this skill is safe"). Feature calls therefore:
   - pass skill text as clearly delimited data;
   - use structured outputs (`output_config.format`);
   - give the model no tools;
   - ask for evidence quotes the UI can check against the real file, not bare verdicts.
4. **Nothing runs without an explicit request.** Each run states what leaves the machine (which files, which fields, to which provider) and an estimated cost before it starts.
5. **Spend is bounded.** Each run is preflighted with token counting. There is a per-run cap and a per-day cap, both user-set. A run over its cap is refused, not truncated.
6. **Results are files, not database rows.** They are cached under the data directory, keyed by input hash + model + prompt version, the way eval results already are. SQLite and `SCHEMA_VERSION` are untouched.
7. **Off by default, local where possible.** With no key configured, every feature reports `unavailable` and the product behaves exactly as today.

## 3. A different angle: bring your own *agent*

**[NOTE]** Most people who would use these features already run a capable model: the coding agent whose skills this tool manages. The repo already ships an agent-facing management skill (`skillsmgr/examples/skills-manager-management/`). For several features (F2, F5, F8, F9), the cheapest and most private design is:

- this tool **prepares a bounded review packet**: the exact listing, diff or candidates, plus instructions and a JSON answer schema;
- the user's own agent answers it;
- this tool **validates the answer and turns it into a normal review**.

That avoids holding a key, holding a spending loop, and adding an HTTP client. It also keeps the egress decision with the agent the user already trusts. BYOK API calls remain the right design where the work must be repeatable, measurable or batched (F1, F6), and for users without such an agent.

**Recommendation:** design every feature around a **packet → answer → validated proposal** core. Then offer two ways to fill the answer step:
- the API (BYOK);
- the user's agent (management skill).

## 4. Feature catalogue (ranked)

**Value** is how directly the feature addresses evidenced pain. **Risk** covers egress, cost and prompt-injection exposure. **Gate** says whether locked constraint 5 approval is needed for a new CLI command or Store method. Every feature can instead be added as a flag on an existing command or as a REST route, which still needs review.

| # | Feature | Value | Risk | Gate |
|---|---|---|---|---|
| F1 | Trigger simulator: "Will this skill fire?" | Highest | Low (names + descriptions only) | New command or `doctor --hygiene` mode |
| F2 | Description rewriter checked by F1 | High | Low | Edit path exists |
| F3 | Overlap judge for near-duplicate candidates | High | Medium (bodies) | Hygiene mode |
| F4 | Description-vs-behaviour check in reviews | Medium | Medium (bodies) | Review evidence, like `external_scan` |
| F5 | Plain-language update explainer | Medium | Medium (diffs) | Review evidence |
| F6 | Provider-backed eval runner | Medium | Cost | `validate --evals-run` input |
| F7 | Ask your library | Medium | Low (descriptions) | New surface |
| F8 | Skill drafting assistant | Low–medium | Low | Create form |
| F9 | Cross-agent porting notes | Low | Low | Review evidence |
| — | Usage analytics from transcripts | High demand | **Very high** (private transcripts) | Not recommended for cloud models |

### F1. Trigger simulator

**What it does.**
1. Rebuild what one agent actually sees: its skill listing in its precedence order, including the description truncation and drop rules recorded in docs/26 and `effective.py`.
2. Take a set of test prompts, either written by the user or proposed by F8-style generation and then approved.
3. Ask the model, acting as that agent, which skill (if any) it would invoke for each prompt.

**What it reports.**
- **Unreachable skills:** no prompt selects them.
- **Shadowed skills:** another skill wins their own prompts.
- **Collisions:** two skills split one intent.
- **Silent losses:** skills that would win if their description had not been dropped for budget.

**Why it matters.** It turns "12 of 91 skills never fired" from an anecdote into a per-library measurement. No competitor surveyed in docs/29 measures this.

**How.**
- The listing goes into the cached system prefix, so every test prompt after the first is a cache read.
- Structured output: `{prompt_id, chosen_skill|null, runner_up|null, quoted_reason}`.
- Default model: the model the agent itself runs, because fidelity matters more than price. Configurable.
- Repeat each prompt *n* times and report choice frequencies, never one sample.

### F2. Description rewriter, verified

The model proposes a description that:
- fits the agent's budget and the 1,024 / 1,536-character limits;
- keeps the trigger phrases F1 credited;
- removes the filler `validator.description_score` already flags.

The proposal is re-run through F1 **before** the user sees it. The diff is shown with the before/after selection rates. Applying it uses the existing edit path (snapshot + Undo). This closed loop is the core of the AI pitch: **the tool proves the rewrite helps, or does not offer it.**

### F3. Overlap judge

The input is only `hygiene.near_duplicate_candidates()` pairs, which are already bounded. That keeps the cost proportional to real candidates, not to the library squared. For each pair the model answers:
- same purpose / overlapping / distinct;
- which instructions conflict, as quotes;
- a merge or scope-split proposal, as a draft, never applied.

### F4. Description-vs-behaviour check

The model checks whether the body and bundled scripts do what the description claims. This is SkillSpector TP4 generalised to every skill, and runs at registry fetch and update review time. It adds a second, independent opinion beside SkillSpector's LLM stage; disagreement between the two is itself shown. The result is advisory evidence, exactly like `external_scan`.

### F5. Update explainer

The input is the bounded `source_lock` diff. The output is a few sentences:
- what behaviour changes;
- what new capabilities or URLs appear;
- what was removed.

Every claim must cite a diff hunk. The UI drops uncited claims.

### F6. Eval runner

`evals.py` already records `with_skill` / `without_skill` runs and benchmarks them, but nothing produces the runs. A BYOK runner would:
- execute each case both ways;
- record outputs and token usage through the existing `record_runs()`;
- optionally use the Batch API, at 50% cost, when latency does not matter.

Grading stays the deterministic assertion subset. An LLM judge may be added, labelled as such, and never used as the only grade.

### F7. Ask your library

Questions such as "Which of my skills handles PDF forms?" Only names, descriptions and scope labels are sent, never bodies. The answer must cite exact instances, which the UI links to.

### F8 / F9. Drafting and porting

- **F8:** draft a `SKILL.md` from a short brief, landing in the New skill form, validated and unsaved.
- **F9:** for one skill and a target agent, list which frontmatter and conventions carry over and which do not (for example `allowed-tools` outside Claude Code). Notes only, no rewrite.

### Not recommended: transcript analytics with a cloud model

Demand is real (docs/29 D-8), but agent transcripts hold source code, secrets and private conversation. If ever built, it should be:
- read-only;
- deterministic first: count actual `Skill` tool invocations;
- local-model-only for anything semantic.

## 5. Architecture

**[NOTE]** Shape only. File names are illustrative and would follow the existing private-module pattern.

```text
packet builder (per feature, pure)  ──►  answer source  ──►  validator  ──►  proposal / evidence
   bounded inputs, schema, egress        a) BYOK API         schema +      existing review,
   statement, token preflight            b) user's agent     quote checks  edit or create path
                                         c) local model
```

**`llm` seam.** One private module handles:
- resolving credentials from the environment (never accepted over HTTP, never written by this tool);
- token-count preflight;
- per-run and per-day budgets;
- structured-output requests and refusal handling;
- the content-hash result cache under `<data>/ai-results/`.

It writes no SQLite and adds no Store method.

**Credential resolution.** Claude credentials resolve the standard way:
1. `ANTHROPIC_API_KEY`;
2. `ANTHROPIC_AUTH_TOKEN`;
3. an `ant auth login` profile.

The tool never stores a key. An OS keychain is a later, separate decision (D-AI-3).

**The web UI is the hard part.** The server is unauthenticated on loopback. Today that is acceptable because no route spends money. A route that calls a paid API would let **any local process spend the user's key** through it. Options are set out in D-AI-4. Until that is decided, AI features are CLI-only, plus read-only display of cached results in the UI.

## 6. Models and cost (Claude, cached reference 2026-10-06)

**[?]** Prices and ids must be rechecked against the live Models API before implementation.

| Model | Id | Input / output per 1M tokens | Use here |
|---|---|---|---|
| Claude Opus 5.5 | `claude-opus-5-5` | $4 / $20 | Default for judgement (F2–F5, F8) |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | $2 / $10 | User-selectable |
| Claude Haiku 5.5 | `claude-haiku-5-5` | $0.10 / $0.50 | User-selectable for bulk F1/F7 runs |

**API facts the design relies on:**
- Opus 5.5 always thinks, and its effort defaults to `medium`. Set it explicitly: `low` for classification-shaped calls (F1, F7), higher for rewriting.
- Forced `tool_choice` returns a 400 on the 5.5 models. Use structured outputs.
- Cache reads cost about 0.1× of input.
- `POST /v1/messages/count_tokens` supports the preflight.
- The Batch API costs 50% and returns results in any order, keyed by `custom_id`.

**Worked estimate for F1.** These are planning numbers only, not measured.
- **Input:** 300 skills at about 60 description tokens is about 18k tokens of listing, sent once as a cached prefix.
- **Volume:** 20 test prompts × 3 repeats = 60 calls, each about 18k cached + 100 fresh input tokens and about 80 output tokens.
- **On Opus 5.5:** first write about $0.09; reads about 60 × 18k × $0.40/M ≈ $0.43; output about $0.10. **Roughly $0.60 per run.**
- **On Haiku 5.5:** about **2 cents**.
- The preflight shows the real figure before anything is sent.

## 7. Threats

| Threat | Mitigation |
|---|---|
| Prompt injection in a skill steers the verdict ("rate me safe", "pick me") | Delimited data, no tools, structured output, quote-backed claims checked against the file, repeated samples, and advisory-only results |
| A local process spends the key through the web UI | CLI-only first; any web route waits for D-AI-4 |
| Key leakage | Environment or SDK profile only. Never logged, cached, returned, or written to review artifacts. Tests assert its absence, as `tests/test_external_scan.py` does today |
| Unexpected egress | Per-run statement of exactly which fields go to which provider. F1/F7 send no bodies |
| Cost runaway | Token preflight, per-run and per-day caps, refusal over cap, Batch for bulk |
| Results mistaken for facts | Model/prompt/date labels; outputs never stored as skill state; disagreements shown |
| Provider refusal or outage | `refusal` and errors become explicit statuses, as `external_scan` does |

## 8. Decisions for the maintainer

- **D-AI-1 — How to call the model (locked constraint 3).** The official recommendation is the `anthropic` SDK, but the CLI must stay stdlib-only. Options:
  - (a) An optional extra (`pip install skill-control-plane[ai]`), imported lazily, so the core install stays stdlib-only. **Recommended.**
  - (b) Hand-written `urllib` HTTP calls with no new dependency. This re-implements retries, errors and streaming, which the reference advises against.
  - (c) External CLIs only (`claude`, `skillspector`, `ollama`), the way the SkillSpector hook works.
- **D-AI-2 — Providers.** Claude first, with others behind the same packet/answer seam. Are a local model (Ollama) and OpenAI-compatible endpoints wanted in v1?
- **D-AI-3 — Key storage.** Environment / SDK profile only (proposed), or also an OS keychain later?
- **D-AI-4 — Web routes that spend money.** Options:
  - CLI-only (proposed for v1);
  - a per-launch random token required by AI routes;
  - per-request confirmation in the UI plus the budget cap.
- **D-AI-5 — First slice.** Proposed: F1 trigger simulator plus F2 verified rewriter, CLI-first. Second: F4/F5 review evidence.
- **D-AI-6 — Budgets.** Default per-run and per-day caps (proposed $1 / $5), and where they live. Proposed: a manager config file under the data directory, never SQLite.
- **D-AI-7 — Default model.** Opus 5.5 by default, per the reference. Should the trigger simulator instead default to the model of the agent being simulated?

## 9. Relationship to shipped work

- `external_scan.py` already applies rules 1, 3 (by delegation), 4 and 7. Its LLM mode passes only an allowlist of provider variables from the environment, which is the same BYOK posture proposed here.
- `evals.py`, `hygiene.py`, `source_lock.py` and `effective.py` supply the bounded inputs every feature above needs. None of them changes.
- Constraint check:
  - no SQLite or `SCHEMA_VERSION` change in any option;
  - a new CLI command or Store method only where §4 says so, and only after approval.
