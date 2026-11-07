# Agent Root Discovery Inventory — 2026-09-08

**Version 1.3.0** (2026-11-07: added Cline, Kiro, Amp, Roo Code, Zed, GitHub
Copilot and Windsurf/Devin rows, and corrected OpenCode's precedence from "not
documented" to the order its own page states. Every new row cites the vendor
page read on 2026-11-07 and recorded in
@docs/34-agent-skill-loading-research-2026-11-07.md. Prior, 2026-09-11: this
inventory is *used* by shipped code. The read-only
`doctor --explain CONSUMER --project DIR` diagnostic derives per-consumer
precedence from these rows at read time; the runtime `ConsumerRootBinding`
model and any facade correction remain approval-gated per ADR-002. Prior,
2026-09-09: closed the three `[?]`s against primary sources; no code, no
locked-constraint changes.)

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
| OpenCode | `~/.config/opencode/skills/`, compatibility `~/.claude/skills/`, `~/.agents/skills/` | `.opencode/skills/`, compatibility `.claude/skills/`, `.agents/skills/`, searched from current directory upward, plus explicit `skills` config | Registered lowest → highest: built-in < `.claude/skills` < `.agents/skills` < `~/.config/opencode/skills` < project `.opencode/skills` < explicit `skills` config; a later source overrides an earlier one with the same ID (**corrected 2026-11-07** — the earlier “no documented order” row was wrong) | OpenCode “Skills” (`https://opencode.ai/docs/skills/`) |
| Codex | `~/.codex/skills/` is NOT a documented skills root — the compatibility facade id is inferred-only (see note below) | `.agents/skills/` scanned in every directory from CWD up to the repo root (`REPO` scope); `$HOME/.agents/skills` (`USER`), `/etc/codex/skills` (`ADMIN`), bundled (`SYSTEM`) | No winner/precedence: same-`name` skills do NOT merge — both can appear in selectors; `$skill-installer`/plugins for distribution; restart only when auto-detect misses | OpenAI “Build skills” (`https://learn.chatgpt.com/docs/build-skills`, “Where Codex loads local skills”) |
| Command Code | `~/.commandcode/skills/` (user) and `~/.agents/skills/` (user compat) | `.commandcode/skills/` (project), `.agents/skills/` (project compat, walked ≤10 levels from CWD stopping at `$HOME`), plus `settings.json` `skills` array and repeatable `--skill` flags / `--no-skills` | Full six-way selection order: project `.commandcode/` > project `.agents/` > user `~/.commandcode/` > user `~/.agents/` > extra locations (`--skill` flags, then settings entries) > bundled; project always trumps user, `.commandcode/` favored over `.agents/` at the same level; same-name losers surface as “Duplicate names” warnings, never dropped silently (`/skills` issues view, `cmd skills list --debug`); name-vs-builtin/command collisions resolve to the higher-precedence owner with `/skill:<name>` escape hatch; reload is live (startup discovery of name/description/path, edits apply immediately, no restart) | Command Code “Agent Skills” (`https://commandcode.ai/docs/skills`: Storage locations, .agents compatibility, Selection priority, Edit skills) |
| Cline | `~/.cline/skills/` | project `.cline/skills/`, `.clinerules/skills/`, `.claude/skills/` | “The global skill takes precedence” over a project skill; the order among the three project dirs is not documented | Cline “Skills” (`https://docs.cline.bot/features/skills`) |
| Kiro | `~/.kiro/skills/` | workspace `.kiro/skills/` | “Workspace skills take priority over global skills” | Kiro “Skills” (`https://kiro.dev/docs/skills/`) |
| Amp | `~/.config/agents/skills/`, `~/.agents/skills/`, `~/.config/amp/skills/`, `~/.claude/skills/`, `~/.claude/plugins/cache` (recursive, five levels) | project and parents `.agents/skills/`, project `.claude/skills/` | “Amp uses the first skill with a given frontmatter `name`”, in that search order | Amp “Skills” (`https://ampcode.com/docs/customize/skills`) |
| Roo Code | `~/.roo/skills/` and `~/.agents/skills/`, each mode-specific (`skills-<mode>`) or generic | project `.roo/skills/` and `.agents/skills/`, each mode-specific or generic | Project > global; `.roo` > `.agents`; mode-specific > generic (eight tiers) | Roo Code “Skills” (`https://roocodeinc.github.io/Roo-Code/features/skills`) |
| Zed | `~/.agents/skills/` | `<worktree>/.agents/skills/` (direct children only) | “The project-local skill takes precedence” | Zed “Skills” (`https://zed.dev/docs/ai/skills`) |
| GitHub Copilot | `~/.copilot/skills/`, `~/.agents/skills/` | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | Not documented | GitHub Copilot “About agent skills” (`https://docs.github.com/en/copilot/concepts/agents/about-agent-skills`) |
| Windsurf / Devin | `~/.config/devin/skills/`, `~/.agents/skills/` | `.devin/skills/`, `.agents/skills/`, legacy `.windsurf/skills/` | Not documented | Devin “Cascade skills” (`https://docs.devin.ai/desktop/cascade/skills`) |

**[NOTE]** The Cline, Kiro, Amp, Roo, Zed, Copilot and Devin rows, and the
corrected OpenCode order, were read from each vendor's page on 2026-11-07 and
recorded in @docs/34-agent-skill-loading-research-2026-11-07.md before they were
added to `effective.py`. `docs.windsurf.com` redirected to `docs.devin.ai`, so
the Windsurf row is the Devin page's own statement.

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

Aggregate operations now deduplicate these roots by resolved physical path
(`root_discovery.resolved_root()` = `Path.resolve()`;
`unique_physical_scopes()` keeps the first descriptor). The first stable
descriptor wins for aggregate display; direct lookup by an existing scope id
remains compatible. The same identity rule is what stops
`effective.explain` from reporting one physical file as two candidates or as its
own `shadowed` copy when two scope ids point at one directory (SCOPE-7).

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
  the approval-gated domain model in `ADR-002`. What ships instead is the
  read-only `effective.explain` diagnostic (below), which *reports* a winning
  instance per consumer without creating the entity, persisting anything, or
  changing `effective_state: unresolved`.

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

Facade implication: the `codex` scope id pointing at `~/.codex/skills` and the
`commandcode` scope id pointing only at `~/.commandcode/skills` are compatibility
approximations, not the documented discovery sets. Correcting them (e.g. adding
`.agents/` project walks, `/etc/codex/skills`, extras) changes user-visible scope
semantics and still needs the approval-gated `ConsumerRootBinding` runtime work.
The read-only half **shipped 2026-09-11** as `doctor --explain CONSUMER
[--project DIR] [--skill NAME]` (`skillsmgr/effective.py`, also
`GET /api/doctor?explain=…`): it derives the winner per consumer at read time
from the rows recorded above, persists nothing, and reports a *separate* read
surface rather than changing the facade. Correction of the adapters themselves
stays out of scope for it.

## Compatibility implementation boundary

The scope layer still uses the official discovery inventory only to select safe
recursive scanning and observed metadata, and it does not claim to reproduce every
consumer's precedence algorithm; `effective_state` is therefore reported as
`unresolved` on every compatibility record until the approval-gated
`ConsumerRootBinding` model exists. Name-based compatibility lookups resolve the
first deterministic discovered instance for recursive roots.

One surface is deliberately narrower and stronger than that: `effective.explain`
(`skillsmgr/effective.py`) *does* apply a precedence rule — but only for the
consumers with a recorded row in this document's table above, only for one
`(consumer, project, skill)` triple, only at read time, and it returns
`undocumented-precedence` for `cursor`, `copilot` and `devin` (whose same-name
order is documented nowhere) and `unknown-consumer` for anything unrecorded
rather than guessing. A consumer may be added to it only together with a
primary-source row here. `opencode` was **corrected** on 2026-11-07: its page
does document an order (see the table above), so it now resolves under
`policy: "ordered"`; its explicit `skills` config remains an unobservable tier,
so a lower-tier win stays provisional.

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
- OpenCode: `https://opencode.ai/docs/skills/` (refreshed 2026-11-07; the
  earlier `https://opencode.ai/v2/docs/skills` row said no order was documented,
  which the current page contradicts)
- Cline, Kiro, Amp, Roo Code, Zed, GitHub Copilot, Windsurf/Devin (read
  2026-11-07): @docs/34-agent-skill-loading-research-2026-11-07.md lists each
  vendor URL beside its row.

## Native settings observations (R4, 2026-11-06)

**[SPEC]** Scoped list, search and detail records add `native_state`, derived
from selected JSON files on each read. Each scope batch reads each source at
most once; no setting is persisted or written. Existing `disabled`, `status`,
instance states and effective-resolution fields retain their meanings.

- Claude Code sources are low-to-high priority: `~/.claude/settings.json`,
  `<cwd>/.claude/settings.json`, `<cwd>/.claude/settings.local.json`.
  `skillOverrides` maps an exact skill name to `on`, `name-only`,
  `user-invocable-only`, or `off`. `sources` lists each observed declaration;
  `observed_setting`, when available, is the highest declaration among these
  files, not a claim about runtime visibility. Missing keys do not manufacture
  an `on` observation. Invalid/unavailable sources suppress that aggregate.
- OpenCode sources are the standard user
  `~/.config/opencode/opencode.json` followed by `<cwd>/opencode.json`.
  `permission.skill` accepts `allow`, `ask`, `deny`, or a pattern map. `*` and
  `?` match skill names; the last matching rule within each file is reported.
  Cross-file rule ordering is not inferred, so there is no aggregate setting.
- Gemini CLI sources, lowest to highest priority, are the system defaults file
  (`GEMINI_CLI_SYSTEM_DEFAULTS_PATH`, otherwise
  `/etc/gemini-cli/system-defaults.json`), `~/.gemini/settings.json`,
  `<cwd>/.gemini/settings.json`, and the system overrides file
  (`GEMINI_CLI_SYSTEM_SETTINGS_PATH`, otherwise `/etc/gemini-cli/settings.json`).
  Those two documented system paths are Linux-only, and other platforms report
  them `unavailable` instead of guessing a path. `skills.disabled` is a name
  list merged with `UNION`, so a readable file that lists the exact name is
  enough for `observed_setting: "disabled"`; `skills.enabled: false` and
  `admin.skills.enabled: false` disable every skill, and each boolean resolves
  to the last file that declares it. Case sensitivity is not documented, so
  matching is exact only. Environment variables and CLI arguments outrank the
  files and are not observed, so `partial` is always true. When nothing
  readable disables a name the observation says
  `"not disabled by the files read"`. Primary source: the "Gemini CLI native
  skill switch" section of @docs/34-agent-skill-loading-research-2026-11-07.md.
- `sources[].status` distinguishes `ok`, `missing`, `unobserved`, `invalid`
  schema and `unavailable` input. Reads are bounded to 1 MiB per file; duplicate
  JSON keys, non-regular files and bad JSON/encoding fail cleanly. Claude maps
  are capped at 10,000 rules, OpenCode at 256, Gemini's disabled list at 1,000
  names with 512 characters per name, and patterns at 512 characters.
  Other settings and raw errors are never included in the observation.
- The context is the manager process's current directory, including when a
  user-scope skill is being inspected. Parent-directory discovery, managed,
  CLI, environment, remote, plugin and additional config-directory sources are
  incomplete. Every observation says `partial: true` and
  `effective_state: unknown`. This evidence does not prove discovery, loading
  or invocation. Unsupported consumers are explicit; Codex TOML is deferred.

**[NOTE] Primary source check (2026-11-06, Gemini row added 2026-11-07):**
[Claude skill visibility](https://code.claude.com/docs/en/skills#override-skill-visibility-from-settings),
[Claude settings precedence](https://code.claude.com/docs/en/settings),
[OpenCode permissions](https://opencode.ai/docs/permissions/),
[OpenCode configuration](https://opencode.ai/docs/config/), and the Gemini CLI
[skills](https://geminicli.com/docs/cli/skills/) page as recorded in the
"Gemini CLI native skill switch" section of
@docs/34-agent-skill-loading-research-2026-11-07.md.
The omitted config sources are why observed declarations are kept separate
from an effective runtime claim.
