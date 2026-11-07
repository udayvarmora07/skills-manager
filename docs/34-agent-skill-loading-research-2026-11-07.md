# Agent Skill Loading Research — 2026-11-07

**Version 1.0.0**

**AI manifest**: Primary-source facts, read on 2026-11-07, about where nine agents load `SKILL.md` skills from, which wins on a same-name clash, and which frontmatter keys each documents. Feeds R12 (new `effective.py` consumer rows), the OpenCode precedence correction, and the docs/29 H1 "ignored frontmatter" finding. Every row cites the vendor's own page. A blank means the page does not say; it is never filled with a guess.

## Method

**[NOTE]** Each page was fetched directly on 2026-11-07. Redirects were followed only to the vendor's own documented destination: `developers.openai.com/codex/skills` → `learn.chatgpt.com/docs/build-skills`, `docs.windsurf.com` → `docs.devin.ai`, `docs.roocode.com` → `roocodeinc.github.io/Roo-Code`. Vendor docs change; re-verify a row before relying on it for anything other than the dated observation it is.

## Same-name precedence

**[SPEC]** "Documented" means the page states the rule. Anything else is undocumented, and `doctor --explain` must not elect a winner for it.

| Agent | Locations (as documented) | Same-name rule | Source |
|---|---|---|---|
| Claude Code | enterprise managed dir, `~/.claude/skills`, `.claude/skills`, nested `<subdir>/.claude/skills`, `--add-dir`, plugins | enterprise > personal > project; nested and root both load; plugins are namespaced | [code.claude.com/docs/en/skills](https://code.claude.com/docs/en/skills) |
| Codex | `$CWD/.agents/skills` up to `$REPO_ROOT`, `$HOME/.agents/skills`, `/etc/codex/skills`, bundled | "Codex doesn't merge them; both can appear in skill selectors" (no winner) | [learn.chatgpt.com/docs/build-skills](https://learn.chatgpt.com/docs/build-skills) |
| Gemini CLI | built-in, extensions, `~/.gemini/skills` / `~/.agents/skills`, `.gemini/skills` / `.agents/skills` | built-in < extension < user < workspace; within a tier `.agents/skills` > `.gemini/skills` | [geminicli.com/docs/cli/skills](https://geminicli.com/docs/cli/skills/) |
| OpenCode | built-in, `.claude/skills`, `.agents/skills`, `~/.config/opencode/skills`, project `.opencode/skills`, explicit `skills` config (also `~/.claude/skills`, `~/.agents/skills`) | registered lowest → highest in that order, so a later source overrides an earlier one with the same ID. **This corrects the earlier "no documented order" row.** | [opencode.ai/docs/skills](https://opencode.ai/docs/skills/) |
| Cline | project `.cline/skills`, `.clinerules/skills`, `.claude/skills`; global `~/.cline/skills` | "the global skill takes precedence" over a project skill; order among the three project dirs is not documented | [docs.cline.bot/features/skills](https://docs.cline.bot/features/skills) |
| Kiro | `.kiro/skills`, `~/.kiro/skills` | "workspace skills take priority over global skills" | [kiro.dev/docs/skills](https://kiro.dev/docs/skills/) |
| Amp | `~/.config/agents/skills`, `~/.agents/skills`, `~/.config/amp/skills`, project+parents `.agents/skills`, then `.claude/skills`, `~/.claude/skills`, `~/.claude/plugins/cache` (recursive, five levels) | "Amp uses the first skill with a given frontmatter `name`", in that search order | [ampcode.com/docs/customize/skills](https://ampcode.com/docs/customize/skills) |
| Roo Code | project/global × `.roo`/`.agents` × mode-specific/generic | project > global; `.roo` > `.agents`; mode-specific > generic (8 tiers) | [roocodeinc.github.io/Roo-Code/features/skills](https://roocodeinc.github.io/Roo-Code/features/skills) |
| Zed | `~/.agents/skills`, `<worktree>/.agents/skills` (direct children only) | "the project-local skill takes precedence" | [zed.dev/docs/ai/skills](https://zed.dev/docs/ai/skills) |
| GitHub Copilot | `.github/skills`, `.claude/skills`, `.agents/skills`; `~/.copilot/skills`, `~/.agents/skills` | not documented | [docs.github.com … about-agent-skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) |
| Windsurf / Devin | `.devin/skills`, `.agents/skills`, legacy `.windsurf/skills`; `~/.config/devin/skills`, `~/.agents/skills` | not documented | [docs.devin.ai/desktop/cascade/skills](https://docs.devin.ai/desktop/cascade/skills) |

## Documented frontmatter keys

**[SPEC]** A key that an agent does not document is reported as "no documented effect in that agent". That is different from "rejected". Only the claude.ai upload and Skills API surfaces are documented to reject unknown keys.

| Agent | Keys the page documents | Unknown keys |
|---|---|---|
| Claude Code | `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths`, `shell`, `metadata`, `license`, `compatibility` | "ignores unrecognized keys without reporting an error" |
| claude.ai / Skills API | `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` | "Other keys cause a hard error" |
| Codex | `name`, `description`; implicit invocation is set in `agents/openai.yaml` → `policy.allow_implicit_invocation` | not stated |
| Gemini CLI | `name`, `description` (as "skill metadata") | not stated |
| OpenCode | `name`, `description`, `metadata.opencode/autoinvoke`, `disable-model-invocation`; `license`/`compatibility` "accepted … not interpreted" | not stated |
| Cline | `name`, `description` | not stated |
| Kiro | `name`, `description`; optional `license`, `compatibility`, `metadata` | not stated |
| Amp | `name`, `description`, `mcpServers` (list stated as incomplete) | not stated |
| Roo Code | `name`, `description` | not stated |
| Zed | `name`, `description`, `disable-model-invocation` | "planned but not yet supported" for other spec fields |

## Consequences for this repository

- **[SPEC]** `effective.py`'s `opencode` row must move from `undocumented-precedence` to the documented order above.
- **[SPEC]** New consumer rows with a documented order: `cline`, `kiro`, `amp`, `roo`, `zed`. `copilot` and `devin` are recorded with roots but `undocumented-precedence`.
- **[NOTE]** The most consequential ignored key is `disable-model-invocation`. It hides a skill from the model in Claude Code, OpenCode and Zed, but Codex, Gemini, Cline, Kiro, Amp and Roo document no such key. A user who relies on it to keep a skill out of the model's context gets that effect only in some agents. Codex has its own switch in `agents/openai.yaml`.

## Claude Code skill listing budget

**[SPEC]** From the "Skill descriptions are cut short" section of
[code.claude.com/docs/en/skills](https://code.claude.com/docs/en/skills), read 2026-11-07:

- The listing always contains every skill name. Descriptions are dropped to fit
  a character budget that "scales at 1% of the model's context window".
- On overflow, descriptions are dropped "starting with the skills you invoke
  least". Invocation counts are not observable from the filesystem, so this
  tool cannot predict *which* descriptions are dropped. It can report only that
  the estimate exceeds the budget.
- Budget controls: the `skillListingBudgetFraction` setting (for example `0.02`)
  and the `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment variable (a fixed
  character count). The per-entry cap of 1,536 characters for `description` plus
  `when_to_use` is configurable with `skillListingMaxDescChars`.
- `skillOverrides` set to `"name-only"` lists a skill without its description,
  which frees budget for the others.

**[?]** The page calls it a *character* budget but scales it from a context
window measured in tokens. The conversion it uses is not stated, so any
over-budget figure computed here is an estimate and must say which conversion
it assumed.
