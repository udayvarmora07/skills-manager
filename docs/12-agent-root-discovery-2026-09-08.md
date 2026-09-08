# Agent Root Discovery Inventory — 2026-09-08

**Version 1.0.0**

**AI manifest:** Research inventory for the Milestone 4 root/consumer tasks.
Official sources are listed for each supported consumer. Facts not confirmed by
an official source are marked `[?]` and are not implemented as policy.

## Root vocabulary used in this inventory

- **User/global root:** a directory under the user profile, available across
  projects.
- **Project root:** a directory under a repository/workspace.
- **Nested project root:** a project-local root below the repository root or
  current working directory that a consumer scopes to the files below it.
- **Precedence:** the rule used when multiple roots provide the same skill id.
- **Reload:** whether changes are detected live or require a restart/refresh.

## Official discovery facts

| Consumer | User roots | Project/nested roots | Precedence/reload | Source |
|---|---|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` in the starting directory and parents; nested `.claude/skills/` is discovered on demand | Enterprise > personal > project for conflicts; nested skills are directory-qualified; live change detection is documented | Claude Code “Extend Claude with skills” |
| Cursor | `~/.cursor/skills/` and `~/.agents/skills/` | `.cursor/skills/`, `.agents/skills/`, and nested project skill directories; Claude/Codex compatibility roots also load | Nested skills are scoped to files below the directory; startup discovery is documented | Cursor “Agent Skills” |
| Gemini CLI | `~/.gemini/skills/` and `~/.agents/skills/` alias | `.gemini/skills/` and `.agents/skills/` in the workspace | Built-in < extension < user < workspace; `/skills reload` refreshes discovery | Gemini CLI “Managing Agent Skills” |
| OpenCode | `~/.config/opencode/skills/`, compatibility `~/.claude/skills/`, `~/.agents/skills/` | `.opencode/skills/`, compatibility `.claude/skills/`, `.agents/skills/`, searched from current directory upward | Later source wins; project roots are considered from repository root toward current directory; runtime loads winning definition | OpenCode “Skills” |
| Codex | `~/.codex/skills/` in current compatibility facade | `[?]` project discovery and precedence require an official Codex skills reference | `[?]` | No official source was located during this run |
| Command Code | `~/.commandcode/skills/` in this repository’s compatibility facade | `[?]` | `[?]` | Command Code behavior is not documented in this repository |

## Current repository mapping

The compatibility facade currently exposes these ids:

| ID | Current physical root | Kind |
|---|---|---|
| `global` | manager data `<data>/skills/` | manager/global |
| `claude-code` | `~/.claude/skills/` | user/consumer |
| `codex` | `~/.codex/skills/` | user/consumer |
| `cursor` | `~/.cursor/skills/` | user/consumer |
| `opencode` | `~/.config/opencode/skills/` | user/consumer |
| `gemini` | `~/.gemini/skills/` | user/consumer |
| `commandcode` | `~/.commandcode/skills/` | user/consumer |
| `agents` | `~/.agents/skills/` | shared compatibility/user |
| project-local ids | `.agents/skills/`, `.claude/skills/`, `skills/` below CWD | project/nested compatibility |

Aggregate operations now deduplicate these roots by resolved physical path. The
first stable descriptor wins for aggregate display; direct lookup by an existing
scope id remains compatible.

## Explicit uncertainties

- `[?]` Codex official root precedence, nested-project discovery, and reload
  semantics need a primary Codex documentation source before being implemented.
- `[?]` Command Code discovery and precedence are currently inferred only from
  the local `~/.commandcode/skills` contract and should not be generalized.
- `[?]` The repository does not yet calculate `EffectiveSkill`; that requires
  the approval-gated domain model in `ADR-002`.

## Compatibility implementation boundary

The current runtime uses the official discovery inventory only to select safe
recursive scanning and observed metadata. It does not claim to reproduce every
consumer's precedence algorithm. `effective_state` is therefore reported as
`unresolved` until the approval-gated `ConsumerRootBinding` model exists.
Name-based compatibility lookups resolve the first deterministic discovered
instance for recursive roots; duplicate-name precedence remains unresolved.

## Sources

- Claude Code: `https://code.claude.com/docs/en/slash-commands`
- Cursor: `https://prod.cursor.com/docs/skills`
- Gemini CLI: `https://geminicli.com/docs/cli/using-agent-skills/`
- OpenCode: `https://opencode.ai/v2/docs/skills`