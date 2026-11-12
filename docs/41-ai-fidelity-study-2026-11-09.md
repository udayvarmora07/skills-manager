# Trigger simulation fidelity study — 2026-11-09

**Version 0.2.0**

**AI manifest**: Dated evidence and limits for a small synthetic comparison of the trigger simulator with Claude Code Skill events. The preserved fixture and sanitized results are in @tools/ai_fidelity/evidence/2026-11-09/.

**[NOTE] A two-case smoke study found 2/2 first-skill agreement.** Both cases
were conclusive; neither had multiple skill calls. This tiny, intentionally
obvious synthetic sample is not an estimate of general routing fidelity. The
native context was restricted and the simulator used a Claude CLI adapter,
not the product's HTTP provider transport.

| Request | Simulator first choice | First successful native Skill call |
|---|---|---|
| Write a haiku about autumn leaves. | `haiku-poem` | `haiku-poem` |
| Convert 12 meters to feet. | `unit-conversion` | `unit-conversion` |

## Method

**[NOTE]** Claude Code `2.1.319` was signed in with a first-party account.
We requested `haiku`; the simulator reported `claude-haiku-5-5` in its model
usage, and both native stream initializations reported that model. The default
Skills Manager data directory had no AI settings, Claude prompt set or saved
simulation. Instead, a private temporary project contained exactly two
handwritten project skills, with no executable content:

- `haiku-poem`: “Use when asked to compose a haiku poem, especially about nature or seasons.”
- `unit-conversion`: “Use when asked to convert a quantity between measurement units such as meters and feet.”

Their bodies respectively instructed writing a haiku and calculating the
conversion. The simulator listing used these same descriptions. We passed the
two requests in the table to `ai_skills.normalize_prompts` and `_route` with
seed 0 and one pass. A temporary in-process `ask_json` adapter sent `_route`'s
actual system and user prompts through `claude -p`, with tools disabled and an
empty strict MCP config. It parsed the returned JSON; it did not use `AiRun`,
the product's provider HTTP transport, ledger, token caps or saved-run path.
A harness-compatible simulation JSON was assembled from those model answers;
its provenance label was `claude-cli-adapter`, and it was not a product-saved
run. The prompt set and simulation were joined and passed to
`tools/ai_fidelity/run.py` for two native calls in saved order. Agreement uses
successful Skill tool events and results, never model prose.

All three calls used `--setting-sources project`, an empty strict MCP config,
no session persistence, `--permission-prompts none`, and a nominal $0.10
per-call limit. Project settings requested `disableAllHooks`,
`disableBundledSkills`, and `disableSkillShellExecution`; the temporary
project had no plugin or hook configuration. The simulator used no built-in
tools and one turn; the native observations used the harness's Skill-only
tool selection and two-turn limit, with 90-second per-call timeout. Official
[skills documentation](https://code.claude.com/docs/en/skills) says omitting
`user` from setting sources suppresses account skill sync, and the
[hooks reference](https://code.claude.com/docs/en/hooks) documents
`disableAllHooks` and its managed-policy limitation. Managed policy was not
independently audited; the setup is not a sandbox. Native user settings contain
hooks and plugins, but user settings were excluded. No authentication tokens
were read or copied and no local server was started.

The simulator CLI reported $0.0002198; the harness does not retain native
call costs, so actual total cost is unknown. Client budgets are approximate
and may be exceeded. The simulation start was `2026-11-09T18:22:50Z`;
prompt-set SHA-256 `689478e1307680ec906bb7b3c66dc706975f364dba9775cb7dd942f7d493ab7a`,
simulation SHA-256 `d883349c691d62185f9965bb68c210daddfd591ec9e45f38bae1d1788c45a42b`.
These hashes identify the preserved synthetic inputs, whose schema includes timestamps;
they do not make predictable prompts anonymous. The harness does not capture
the native listing, so its equality with the simulator listing is not proven.

## Interpretation

**[?]** No inference about normal interactive Claude Code, a real library with
competitors, negative cases, other models, repeat variability, or the product's
HTTP provider implementation follows from these two obvious cases. The test
provides a successful end-to-end smoke observation of the comparison method,
not a validated general fidelity rate. A larger, consented study should include
near misses and overlapping distractors, repeated/shuffled cases, captured
listing and configuration provenance, and explicit cost accounting.

## Reproduction and evidence

**[NOTE]** Sanitized prompt, simulation and native comparison JSON are retained
in @tools/ai_fidelity/evidence/2026-11-09/. No raw transcript or credentials
are included. `tools/ai_fidelity/study_fixture.py` reconstructs the trusted
fixture in a private temporary directory and runs the CLI adapter and harness
with the same restrictions. Its default is a no-send dry run. An attended
reproduction with a signed-in Claude CLI is explicitly invoked as:

```sh
python3 tools/ai_fidelity/study_fixture.py --run-agent --maintainer-present
```

This starts three provider calls; results, model availability and costs can
differ. The simulator and native calls use separate processes, and its CLI
adapter sends the `_route` prompt but does not impose the product HTTP
transport's output-token limit. Inspect local managed settings before running.
