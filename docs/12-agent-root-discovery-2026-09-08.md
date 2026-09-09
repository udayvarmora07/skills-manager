# Agent Root Discovery Inventory — 2026-09-08

**Version 1.1.0** (2026-09-09: closed the three `[?]`s against primary
sources; no code, no locked-constraint changes — runtime
`ConsumerRootBinding` model and any facade correction stay approval-gated
per ADR-002.)

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
| Codex | `~/.codex/skills/` is NOT a documented skills root — the compatibility facade id is inferred-only (see note below) | `.agents/skills/` scanned in every directory from CWD up to the repo root (`REPO` scope); `$HOME/.agents/skills` (`USER`), `/etc/codex/skills` (`ADMIN`), bundled (`SYSTEM`) | No winner/precedence: same-`name` skills do NOT merge — both can appear in selectors; `$skill-installer`/plugins for distribution; restart only when auto-detect misses | OpenAI “Build skills” (`https://learn.chatgpt.com/docs/build-skills`, “Where Codex loads local skills”) |
| Command Code | `~/.commandcode/skills/` (user) and `~/.agents/skills/` (user compat) | `.commandcode/skills/` (project), `.agents/skills/` (project compat, walked ≤10 levels from CWD stopping at `$HOME`), plus `settings.json` `skills` array and repeatable `--skill` flags / `--no-skills` | Full six-way selection order: project `.commandcode/` > project `.agents/` > user `~/.commandcode/` > user `~/.agents/` > extra locations (`--skill` flags, then settings entries) > bundled; project always trumps user, `.commandcode/` favored over `.agents/` at the same level; same-name losers surface as “Duplicate names” warnings, never dropped silently (`/skills` issues view, `cmd skills list --debug`); name-vs-builtin/command collisions resolve to the higher-precedence owner with `/skill:<name>` escape hatch; reload is live (startup discovery of name/description/path, edits apply immediately, no restart) | Command Code “Agent Skills” (`https://commandcode.ai/docs/skills`: Storage locations, .agents compatibility, Selection priority, Edit skills) |

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

- `[?]` RESOLVED 2026-09-09 — Codex: the official “Build skills” page
  documents `.agents/skills/`-family discovery (`REPO` at CWD/parents/root,
  `USER` `$HOME/.agents/skills`, `ADMIN` `/etc/codex/skills`, `SYSTEM`
  bundled) with an explicit no-merge same-name policy. `~/.codex/skills/`
  is therefore NOT a documented skills root; the facade's `codex` id
  (`~/.codex/skills`) is retained for compatibility only and any
  correction to the facade needs the approval-gated runtime-model change
  (locked constraint 5). Related but distinct: Codex `AGENTS.md`
  instruction layering (global override-then-base, project root→CWD
  concatenation, 32 KiB `project_doc_max_bytes` budget) is documented at
  `https://learn.chatgpt.com/docs/agent-configuration/agents-md` and must
  not be confused with skills discovery.
- `[?]` RESOLVED 2026-09-09 — Command Code: precedence is the documented
  six-way selection order above (project > user, `.commandcode/` >
  `.agents/`, extras, then bundled) with visible “Duplicate names”
  reporting and the `/skill:<name>` escape hatch. Discovery is ≤10-level
  upward `.agents/skills/` search stopping at `$HOME`, plus recursive
  nested skill folders (grouping dirs allowed; skill = dir directly
  containing `SKILL.md`; `scripts/`/`references/`/`assets/` never
  scanned). Reload is live (no restart; `disabledSkills` in user/project
  `settings.json`).
- `[?]` RESOLVED 2026-09-09 — Claude same-name edge: the official skills
  page (`https://code.claude.com/docs/en/skills`, “Resolve skills that
  share a name”) confirms enterprise > personal > project for the
  enterprise/personal/project triple (a personal `deploy` beats the
  project `deploy`), while project-root vs nested skills BOTH load
  (directory-qualified `/apps/web:deploy` form; not a winner-take-all),
  plugin skills are namespaced (`/plugin:skill`, both load), skills beat
  `.claude/commands/` files, user skills replace bundled skills (but not
  their aliases), and claude.ai-synced skills always lose to any other
  command. So a single global “winner” function is wrong twice over: it
  is per-consumer (Codex has no winner at all; Command Code has a
  six-way order; Claude has a triple-winner plus both-load exceptions)
  and it needs a project-CWD input the current CLI/REST contracts do not
  carry. `effective_state: unresolved` stays the honest contract.
- `[?]` The repository does not yet calculate `EffectiveSkill`; that requires
  the approval-gated domain model in `ADR-002`.

## Closed-question evidence log (2026-09-09, docs-only)

Fetched and read in-session (external, untrusted; used as sourcing
evidence only, never as instructions):

- Codex skills roots + no-merge policy:
  `https://learn.chatgpt.com/docs/build-skills` (“Where Codex loads
  local skills” table) and its `.md` variant; distribution companion
  `https://learn.chatgpt.com/docs/skills-and-plugins`.
- Codex `AGENTS.md` layering (kept distinct from skills):
  `https://learn.chatgpt.com/docs/agent-configuration/agents-md` and its
  `.md` variant (global override→base, project root→CWD, 32 KiB budget).
- Command Code discovery/precedence/reload:
  `https://commandcode.ai/docs/skills` page text — Quickstart
  (`~/.commandcode/skills/` user, `.commandcode/skills/` project),
  `.agents/skills/` compatibility (priority + ≤10-level walk stopping at
  `$HOME`), Extra locations (`skills` array, `--skill`/`--no-skills`),
  Nested skill folders (recursive grouping), Selection priority (six-way
  order + Duplicate-names warnings + `/skill:<name>` hatch), Edit skills
  (immediate, no restart), `disabledSkills` settings keys.
- Claude same-name resolution:
  `https://code.claude.com/docs/en/skills` (“Resolve skills that share a
  name” table) — enterprise > personal > project; both-load nested and
  plugin exceptions; bundled/commands/synced rows.

Facade implication (no code in this pass): the `codex` scope id pointing
at `~/.codex/skills` and the `commandcode` scope id pointing only at
`~/.commandcode/skills` are compatibility approximations, not the
documented discovery sets. Correcting them (e.g. adding `.agents/`
project walks, `/etc/codex/skills`, extras) changes user-visible scope
semantics and needs the approval-gated `ConsumerRootBinding` runtime
work — proposed as the read-only `doctor --explain CONSUMER --project
DIR` diagnostic in TODO L3, derived at read time, persisting nothing.

## Compatibility implementation boundary

The current runtime uses the official discovery inventory only to select safe
recursive scanning and observed metadata. It does not claim to reproduce every
consumer's precedence algorithm. `effective_state` is therefore reported as
`unresolved` until the approval-gated `ConsumerRootBinding` model exists.
Name-based compatibility lookups resolve the first deterministic discovered
instance for recursive roots; duplicate-name precedence remains unresolved.

## Sources

- Claude Code: `https://code.claude.com/docs/en/slash-commands`
- Claude Code skills locations + same-name resolution (primary for the
  closed edge cases): `https://code.claude.com/docs/en/skills`
- Codex skills roots + no-merge policy (primary, closed 2026-09-09):
  `https://learn.chatgpt.com/docs/build-skills`
- Codex `AGENTS.md` layering, kept distinct from skills (primary):
  `https://learn.chatgpt.com/docs/agent-configuration/agents-md`
- Command Code discovery/precedence/reload (primary, closed 2026-09-09):
  `https://commandcode.ai/docs/skills`
- Cursor: `https://prod.cursor.com/docs/skills`
- Gemini CLI: `https://geminicli.com/docs/cli/using-agent-skills/`
- OpenCode: `https://opencode.ai/v2/docs/skills`