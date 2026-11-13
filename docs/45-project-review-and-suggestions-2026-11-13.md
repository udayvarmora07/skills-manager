# Project Review and Suggestions — 2026-11-13

**Version 0.1.0**

**AI manifest**: Ranked suggestions from a whole-project review on 2026-11-13: a read of the docs, a first-time-user run of the CLI and web UI in an isolated home, and five research passes (competitors, agent-vendor changes, user voice, security and quality research, distribution). Proposals only. Nothing here is approved or implemented, and every item that touches a locked constraint is flagged. It extends @docs/28-project-review-and-recommendations-2026-11-06.md and @docs/29-user-demand-and-competitor-analysis-2026-11-06.md; where it repeats them, the newer measurement stands.

## 1. Method and limits

**[NOTE]** Three inputs.

- **Docs and code.** The hot and warm docs, `task.md`, and targeted `grep` checks of `skillsmgr/`. The code was not audited line by line.
- **Hands-on run.** The CLI and the v2 web UI were run on this tree with an isolated `HOME` and `SKILLS_MANAGER_DATA` and two drifting copies of one skill.
- **Research.** Five Sonnet subagents, read-only, using `gh api`, web search and page fetches on 2026-11-13.

**[SPEC] What was verified directly here:** the PyPI version and download count, the GitHub star counts, the commit count since `v1.0.2`, and every hands-on finding in section 3.

**[?] What was not:** the vendor-doc, security and distribution findings come from the subagents and were only spot-checked. Reddit, X, V2EX and Linux.do were unreachable in this pass, so user quotes come from Hacker News, GitHub issues and dev.to. No non-developer or Windows-user evidence was found.

## 2. Main finding: the bottleneck is shipping and distribution

**[SPEC]** Measured 2026-11-13:

| Fact | Value |
|---|---|
| Latest version on PyPI | 1.0.1 (published 2026-09-10) |
| Commits on this branch after the `v1.0.2` tag | 149 |
| PyPI downloads, last month (pypistats) | 23 |
| GitHub stars | 1 |
| vercel-labs/skills stars / npm downloads per month | 39,228 / about 19.5M |
| xingkongliang/skills-manager stars | 7,486 |
| microsoft/apm stars | 4,360 |

**[NOTE]** The v2 interface, AI assist, the hygiene rounds and the installers are all unpublished. `install.sh` installs from PyPI by default, so a new user gets the September tool while the README describes the November one.

Suggestions, in order:

1. **Release 1.1.0.** Approve the pending release or cut a new tag from `main`, so the README, the installer and PyPI describe one product. This is a human decision.
2. **Make the names match.** The repository is `skills-manager`, the PyPI distribution `skill-control-plane`, the import package `skillsmgr` and the command `skills-mgr`. With 23 downloads a month, renaming the distribution to match the command costs little and makes `uvx skills-mgr` work with no install. Keep the old name as a stub that depends on the new one. **Needs the maintainer.**
3. **Lead with a measured claim.** The launch posts that did well on Hacker News in 2026 had one number or one concrete job in the title. "N of your skills are invisible to Claude Code or Codex", taken from the listing-budget check, fits better than "manage skills".
4. **Use the cheap channels.** A Claude Code plugin whose skill wraps the CLI; a "validate skills" GitHub Action built on @docs/36-skill-ci-recipe-2026-11-08.md; the awesome-lists. Homebrew is lower priority. **[?]** Whether the awesome-lists accept tools (not skills) was not confirmed.

**[NOTE]** Nobody in any channel read said they would pay for a skills manager. The services-first reading in docs/27 stays the only supported revenue path.

## 3. First-run problems found hands-on

**[SPEC]** Each was observed on this tree in an isolated home.

| # | Observation | Suggested change | Approval |
|---|---|---|---|
| F1 | `skills-mgr list` prints "no skills installed" while `~/.claude/skills` and `~/.agents/skills` hold skills, because the default scope is `global` | When the global store is empty and agent scopes are not, print a one-line hint naming `--scope all` and the counts; or change the default | Hint: no. Default change: yes (documented behaviour) |
| F2 | `doctor` on a fresh, empty data directory reports "issues found" and tells the user to rebuild the index | Treat "no index and no skills" as a clean first run | No |
| F3 | The hygiene report says "use the existing diff/update or sync workflow", but there is no CLI way to diff two copies; only the web UI and `update preview --from` show one | Add a diff to an existing command (for example `view NAME --scope A --diff-scope B`), or reword the follow-up to name `update preview` | Yes if a new command or flag |
| F4 | A data directory created with plain `mkdir` under a default Ubuntu umask (mode 0775) is refused with "writable by another user" and no remedy | Name the exact `chmod 700` command in the message, as the pre-existing-root path already does | No |
| F5 | "1 name-only candidates" is printed when the listing uses 42 of about 40,000 characters | Print candidates only when the estimate is over, or near, the budget | No |
| F6 | Long absolute paths are printed in full in `scopes`, `doctor` and hygiene text | Shorten paths under the home directory to `~/…` in text output (not in `--json`) | No |
| F7 | v2 Home shows "If read in full N%" per agent, but not the listing budget | Show the listing-budget estimate on Home for Claude Code and Codex, since that is the reported pain | No |
| F8 | No shell completion and no "did you mean" for a mistyped command | A static completion script shipped as package data; argparse `suggest_on_error` on Python 3.14 | Completion command: yes |

**[NOTE]** The v2 Home page itself read well on first run: the drifting copy was the one thing flagged, with a plain explanation and a fix button.

## 4. The agent model is going stale

**[?]** From vendor docs read by a subagent on 2026-11-13; each needs a primary-source check and a row in @docs/12-agent-root-discovery-2026-09-08.md before any code changes.

| # | Vendor change | State in this tree |
|---|---|---|
| V1 | `.agents/skills` is now read by Cursor, VS Code/Copilot (local sessions), Zed, Windsurf/Devin, OpenCode and Gemini CLI, as well as Codex | The `cursor` row in `effective.py` lists only `.cursor/skills`; Cursor's docs also name `.claude/skills` and `.codex/skills` |
| V2 | Claude Code's skills page now says a skill entry may be a symlink to a directory and is loaded once | The `agents_bridge` remedy still carries the #14836 caveat; that issue is open but last updated 2026-09-15 |
| V3 | Claude Code downloads claude.ai skills into `~/.claude/skills/synced/` and never uploads them | No handling found (`grep synced skillsmgr/*.py`); it should be read-only and never a sync target |
| V4 | Codex added `skills.max_context_tokens` (raises the 2% listing budget) and `[skills.bundled] enabled = false` | Neither is read; `codex_listing` assumes the 2% rule only |
| V5 | Claude Code v2.1.319 and v2.1.321 changed nested-skill loading (Bash sandbox; `~/.claude/plugins`) | Not modelled |
| V6 | Codex v0.169.0 added a "local-only Claude Code skill migration"; users report it drops linked files while reporting success (openai/codex#60955) | A reliable, reviewed `sync` is a selling point here; not yet said anywhere |
| V7 | Claude Code's default listing budget is still 1% of the window | Correct in `native_state.DEFAULT_LISTING_BUDGET_FRACTION`; no change needed |

**[NOTE]** Suggested feature: generalise `agents_bridge` into one "who can see this skill" table per skill, across every consumer with a cited root list. It is already listed as a candidate in @docs/44-overnight-user-problems-2026-11-13.md §8, and V1 raises its value.

## 5. New features, ranked

| # | Feature | Evidence | Approval |
|---|---|---|---|
| N1 | Restore from `skills-lock.json`, preview first | Most-reacted open issue on vercel-labs/skills (#549, 49 reactions); the lock reader already exists | Yes (new command or flag) |
| N2 | Git-backed sync across machines | Repeated ask on Hacker News in November; the desktop leader ships it; `backup_sync.py` exists and nothing calls it | Yes |
| N3 | "Retire skills" advisor | New since 2026-11-04: experienced users report deleting most of their skills | Depends on usage data, a deferred privacy decision (docs/35) |
| N4 | Risk checks on prose, not only scripts | Snyk and Unit 42 report that real malicious skills put the lure in `SKILL.md` and `references/` text; `risk_file_listing` reads script files only | No |
| N5 | "Changed since last scan" alert | Users want a skill that was fine yesterday flagged when it changes; content hashes already exist | No, if it stays inside hygiene |
| N6 | Authoring-smell lints, info level | arXiv 2607.01456 found at least one smell in over 99% of the skills it studied; several are static (no example, no validation step, dated content, reference nesting deeper than one level) | No |
| N7 | Project picker in the v2 UI | Several report sections say "unavailable: no project root"; the desktop competitor shipped project management on 2026-11-12 | No, within the existing confinement rule |
| N8 | MCP server mode | Lets agents drive the tool and qualifies it for MCP registries | Yes (new surface) |
| N9 | Manage MCP servers and AGENTS.md beside skills | The most repeated ask on the desktop competitor's tracker; MON-Q2 in docs/27 | Yes (scope change, needs an ADR) |

**[NOTE] N4 in detail.** Patterns missing today, each advisory: prose that tells the agent to fetch and follow instructions from a URL; token-shaped secrets and "paste your API key" wording; Telegram, Discord and Slack webhook endpoints and paste hosts; bundled hooks, `.mcp.json` and `package.json` install scripts; any binary, archive or file over about 1 MB inside a skill. `grep` on `skillsmgr/risk.py` found none of these.

## 6. What to stop or cut

- **Pause new AI features and hygiene rounds.** Thirteen AI features are shipped and none has been run against a real provider (docs/39, docs/41).
- **Retire the classic UI** once v2 has a human sign-off. `webui/app.js` is 2,808 lines that duplicate v2.
- **Reduce the process weight.** `task.md` is 2,982 lines. The progress log is back to about 199 KB, twice the 100,000-character limit its own digest set. Seven `prototype-*` directories and several root planning files (`PLAN.md`, `TODO.md`, `DEEP-AUDIT-2026-09-11.md`) are the first thing a contributor sees.
- **Run the pending human sessions.** Three to five consented sessions are listed as open in every pass since September and are the one kind of evidence the project has none of.
- **Close the open items:** issue #14 and the open Dependabot PR (#21).

## 7. Questions for the maintainer

| ID | Question |
|---|---|
| Q1 | May the PyPI distribution be renamed to match the `skills-mgr` command? |
| Q2 | Is the target user the multi-agent power user only (docs/29 D-4)? |
| Q3 | Widen scope to MCP servers and AGENTS.md (docs/29 D-5)? |
| Q4 | Which of N1, N2 and N8 may add a command or surface? |

## 8. Sources

**[NOTE]** Read on 2026-11-13 unless stated.

- Competitors: [vercel-labs/skills releases](https://github.com/vercel-labs/skills/releases), [xingkongliang/skills-manager releases](https://github.com/xingkongliang/skills-manager/releases), [microsoft/apm releases](https://github.com/microsoft/apm/releases), [luongnv89/asm](https://github.com/luongnv89/asm), [vercel-labs/skills #549](https://github.com/vercel-labs/skills/issues/549).
- Vendors: [Claude Code skills](https://code.claude.com/docs/en/skills), [Claude Code changelog](https://code.claude.com/docs/en/changelog), [Codex skills](https://learn.chatgpt.com/docs/build-skills), [Gemini CLI skills](https://geminicli.com/docs/cli/skills/), [OpenCode skills](https://opencode.ai/docs/skills/), [Cursor skills](https://cursor.com/docs/context/skills), [VS Code agent skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills), [Zed skills](https://zed.dev/docs/ai/skills), [agentskills.io specification](https://agentskills.io/specification).
- User voice: [HN 50367037](https://news.ycombinator.com/item?id=50367037), [HN 50399447](https://news.ycombinator.com/item?id=50399447), [HN 50450464](https://news.ycombinator.com/item?id=50450464), [claude-code #108554](https://github.com/anthropics/claude-code/issues/108554), [codex #60955](https://github.com/openai/codex/issues/60955).
- Security and quality: [Snyk threat landscape](https://research.snyk.io/blog/agent-skills-threat-landscape/), [Unit 42](https://unit42.paloaltonetworks.com/openclaw-ai-supply-chain/), [arXiv 2605.11418](https://arxiv.org/abs/2605.11418), [arXiv 2607.01456](https://arxiv.org/abs/2607.01456), [Anthropic authoring guide](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).
- Distribution: [pypistats](https://pypistats.org/packages/skill-control-plane), [Python discourse on distribution and import names](https://discuss.python.org/t/any-list-of-well-known-distribution-import-name-mismatches/44733).
