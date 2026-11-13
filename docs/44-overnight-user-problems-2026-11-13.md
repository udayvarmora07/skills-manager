# Overnight User Problems — 2026-11-13

**Version 0.2.0**

**AI manifest**: Ranked research record from two unattended improvement rounds on 2026-11-13: which real skill-management problems reported since 2026-10-01 this tool can detect locally, which three were fixed, and what is left for later rounds. Evidence is GitHub issues read on 2026-11-13; reaction counts on recent issues are small, so the ranking is judgment, not votes.

## 1. Method

**[NOTE]** A read-only research pass searched GitHub issues updated since
2026-10-01 in anthropics/claude-code, anthropics/skills, openai/codex,
sst/opencode, google-gemini/gemini-cli and vercel-labs/skills, sorted by
reactions, and read the bodies of the most relevant. The GitHub search rate
limit cut coverage, and the Hacker News query failed, so no HN evidence is
included. Every fetched text was treated as data. OpenRouter's prompt-caching
page was read on the same date for the third item.

## 2. Ranked problems found

**[NOTE]** Ranked by how often a user is silently hurt × whether a local,
deterministic check can catch it before the agent does.

| # | Problem | Evidence | Locally detectable? |
|---|---|---|---|
| 1 | Listing budgets silently truncate descriptions (Claude Code and Codex; Codex uses 2% of the window, fallback 8,000 characters) | claude-code #107255; codex #19679 (40 reactions) | Yes; Claude Code already estimated (`claude_listing`); Codex **fixed in round 2** |
| 2 | A UTF-8 byte-order mark before `---` makes Codex skip the skill ("missing YAML frontmatter delimited by ---") | codex #13918 (updated 2026-10-28) | Yes — **fixed this round** |
| 3 | Frontmatter quirks drop skills in strict parsers | gemini-cli #25693 | Partly — the existing lint now **reaches Doctor and Quality** this round |
| 4 | A Codex `[[skills.config]]` `path` entry naming the skill **folder** silently disables nothing; it must name `SKILL.md` | codex #51044 (2026-10-05), codex #60951 | Yes — **fixed this round** |
| 5 | `disable-model-invocation` ignored by some agents | opencode #53172, claude-code #98898 | Partly; the ignored-frontmatter finding covers the documented part |
| 6 | Skills under `~/.agents/skills` invisible to some agents | claude-code #31005 (619 reactions), opencode #41213 | Partly; Claude Code covered by `agents_bridge` |
| 7 | Duplicate copies across agent folders break `npx skills update` | vercel-labs/skills #2406, #2574 | Mostly existing (duplicates, lockfile evidence) |
| 8 | Very large `SKILL.md` tails truncated by OpenCode at 2,000 lines / 50 KiB | opencode #62718 | Yes — **fixed in round 2** |

## 3. What was fixed, and why these three

**[SPEC]** Each is small, deterministic or transport-only, inside the locked
constraints (no new CLI command, Store method, schema or dependency), and
pinned by tests that fail on the previous commit.

1. **Byte-order mark lint (problem 2).** This tool's own parser strips a BOM,
   so a skill Codex skips looked valid here. `validator` now adds one advisory
   `frontmatter` warning when a document with a frontmatter block starts with
   U+FEFF. `valid` is unchanged. Building it showed that the hygiene report
   surfaced only validator *errors*, so the existing empty-block and
   unquoted-colon warnings never reached Doctor or Quality either. A new
   `agent-parse-risk` warning now carries all three (problem 3).
2. **Codex dead config entries (problem 4).** `native_state.codex_config_dead_entries()`
   lists `path` entries that name a folder (with the `SKILL.md` path to use
   when one exists), a missing file, or a file other than `SKILL.md`. An entry
   behind an unreadable directory is not reported, because Codex might still
   match it. The hygiene report adds a `codex_config` section and one
   `codex-config-dead-entry` warning for the `codex` and `all` scopes; the CLI
   text and the v2 Quality finding list each entry. Nothing is written.
3. **OpenRouter prompt caching for Claude (docs/39 §18).** OpenRouter caches
   Anthropic models only with explicit `cache_control` breakpoints, so a
   multi-batch trigger test through OpenRouter re-paid the full listing on
   every batch. The reused listing prefix now carries a breakpoint when the
   provider is `openrouter` and the model id starts with `anthropic/`. Other
   models keep the plain-text prefix that automatic caching needs.

**[?]** OpenRouter's page does not say outright that `prompt_tokens` includes
cached tokens; its example implies it, and the caps rely on that. Not observed
against a live provider.

## 4. Round 2 (same day)

**[SPEC]** Two read-only hygiene additions, both pinned by tests that fail on
`d189f66`:

1. **Codex listing budget (problem 1).** Codex's renderer
   (`codex-rs/ext/skills/src/render.rs`, read 2026-11-13) reserves 2% of the
   model's context window in tokens (8,000 characters when the window is
   unknown), renders each skill as `- name: description (file: path)`, caps a
   description at 1,024 characters and costs a line `ceil(bytes / 4)` tokens.
   The new `codex_listing` section applies that rule to enabled
   `~/.agents/skills` instances, excluding file- and config-disabled skills,
   and adds one `codex-listing-budget` info finding when over budget. A
   non-GPT report window is replaced by an assumed `gpt-5.6` window, stated in
   the budget basis.
2. **OpenCode tool-output truncation (problem 8).** OpenCode keeps the first
   2,000 lines / 50 KiB of a tool result, so the tail of a larger `SKILL.md`
   never reaches the model. An `opencode-output-truncation` warning names
   enabled instances in the scopes OpenCode reads (`opencode`, `agents`,
   `claude-code`) over either limit.

**[?]** Codex's project `.agents/skills`, `/etc/codex/skills`, bundled system
skills and a configured token budget are not read, so the Codex estimate is
`partial`. Whether OpenCode counts 50 KiB in bytes is inferred from the issue's
"KiB"; bytes are used.

**[NOTE]** On the maintainer's machine (read-only): 153 listed
`~/.agents/skills` skills cost about 14,640 Codex tokens, within the assumed
`gpt-5.6` budget of 21,000 but nearly twice the 8,000 a 400k-token `gpt-5`
window allows; one skill (`do-and-judge`, 57,505 bytes) is over OpenCode's
50 KiB head.

## 5. Candidates for later rounds

- A6 standalone demote-only explainer for risk findings on installed skills.
- A per-agent visibility table generalising `agents_bridge` (problem 6).
- Skill-directory plugin layout check before sync (vercel-labs/skills #2609).
- OpenCode `metadata.opencode/autoinvoke: false` as the working equivalent of
  `disable-model-invocation` in the ignored-frontmatter finding (opencode #53172).
- Lockfile `skillPath` ambiguity and nested skills shadowed by a root
  `SKILL.md` (vercel-labs/skills #2406, #2574).
