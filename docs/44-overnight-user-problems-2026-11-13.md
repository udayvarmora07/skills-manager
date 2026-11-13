# Overnight User Problems — 2026-11-13

**Version 0.4.0**

**AI manifest**: Ranked research record from three unattended improvement rounds on 2026-11-13: which real skill-management problems reported since 2026-10-01 this tool can detect locally, which three were fixed, and what is left for later rounds. Evidence is GitHub issues read on 2026-11-13; reaction counts on recent issues are small, so the ranking is judgment, not votes.

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
| 5 | `disable-model-invocation` ignored by some agents | opencode #53172, claude-code #98898 | Partly; OpenCode honours it since v2.0.23, and disagreeing switches are flagged **in round 4** |
| 6 | Skills under `~/.agents/skills` invisible to some agents | claude-code #31005 (619 reactions), opencode #41213 | Partly; Claude Code covered by `agents_bridge` |
| 7 | Duplicate copies across agent folders break `npx skills update` | vercel-labs/skills #2406, #2574 | Mostly existing (duplicates, lockfile evidence) |
| 8 | Very large `SKILL.md` tails truncated by OpenCode at 2,000 lines / 50 KiB | opencode #62718 | Yes — **fixed in round 2** |
| 9 | A skill inside a Claude Code skills-dir plugin folder loses its plugin when copied alone | vercel-labs/skills #2609 | Yes — **fixed in round 4** |

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

## 5. Round 3 (same day)

**[SPEC]** A6, the last planned AI catalogue item: a demote-only explainer for
risk findings on an installed skill (`ai_explain.py`,
`POST /api/ai/explain-findings`, v2 Tools → Explain risk findings). The
pattern scanner over-reports warning text: a line telling the reader never to
pipe `curl` into `sh` still produces a `high` `script` finding. The explainer
lets the user's model say so, but its opinion sits beside the finding and
cannot change the severity, and a false-positive opinion needs a quote that
occurs in the named file.

**[?]** A hostile skill can steer the model, for example by including text
that calls itself safe, and the model can then quote that text. The quote
check proves only that the words exist in the file, not that the reasoning is
sound. That is why an opinion never changes or hides a finding.

**[NOTE]** The OpenCode `disable-model-invocation` candidate (opencode #53172)
was dropped: upstream fixed it in #52747 and the issue is closed as completed.

## 6. Round 4 (same day)

**[SPEC]** Two read-only hygiene additions, pinned by 13 tests in
`tests/test_round3_plugin_and_autoinvoke.py` (6 of the first 10 fail on
`f4d136f`; the rest are guards, and 3 hostile-input tests were added during
self-review):

1. **Skills-dir plugins (vercel-labs/skills#2609).** Claude Code's skills page
   (read 2026-11-13) documents "Skill folder as a plugin": a skills-directory
   folder with `.claude-plugin/plugin.json` loads as `<name>@skills-dir`, and
   its plugin-loading page names the manifest `name` as `<name>`. A skill at
   `<folder>/skills/<skill>/` beside such a manifest gets a
   `plugin-member-skill` finding, since copying the skill alone drops the
   plugin. The `skills_dir_plugins` section lists `~/.claude/skills` plugin
   folders, including ones with no root `SKILL.md`, which this tool's
   non-recursive Claude Code scan does not list as skills.
2. **OpenCode autoinvoke conflict (opencode#53172 → PR #52747).** The PR,
   merged 2026-10-02, maps `disable-model-invocation` onto `autoinvoke`,
   accepts `true/yes/on/1` and `false/no/off/0`, and lets
   `opencode/autoinvoke` win when both are set. The maintainer bot's reply on
   #53172 says it shipped in v2.0.23, and tag `v2.0.23` exists. So the round-1
   premise ("ignored by OpenCode") is out of date; what remains detectable is
   two switches that disagree, now an `opencode-autoinvoke-conflict` warning
   (round 3 had dropped this candidate as fixed upstream).

**[NOTE]** On the maintainer's machine (read-only, `--scope all`): one
skills-dir plugin (`humanizer`, with a root `SKILL.md`), no plugin-member
skills, no autoinvoke conflicts.

**[?]** Whether Claude Code follows a *symlinked* plugin folder is not
documented; such folders are not listed. Plugin skills are not added to the
`claude_listing` estimate.

## 7. Candidates for later rounds

- A per-agent visibility table generalising `agents_bridge` (problem 6).
- Warn inside `sync` itself (not only in hygiene) when the source is a
  plugin member; needs a decision, because sync is a write path.
- Lockfile `skillPath` ambiguity and nested skills shadowed by a root
  `SKILL.md` (vercel-labs/skills #2406, #2574).
