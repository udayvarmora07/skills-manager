# User Research — Skills, Context Cost, and What Users Want

**Version 1.1.0**

**AI manifest**: Market and user research gathered 2026-10-30 to answer "why
would people use skills-manager, and what should it do next?". Sources: the
official Claude Code skills docs, Codex/Gemini CLI/OpenCode skill-toggle docs,
`anthropics/claude-code`, `vercel-labs/skills` and competitor issue trackers
(reaction counts), Reddit r/ClaudeAI and r/ClaudeCode and X/Twitter (both read
through the OpenCLI browser bridge on a logged-in session), GitHub competitor
repos (star/issue counts via `gh`), security research (Snyk, arXiv), and dev
blogs. v1.1.0 adds §4b (every agent's native switch, and a defect in this app),
§9 (X/Twitter), and revises the competitor table and recommendations.
Every number is quoted from its source on the date above; nothing here is a
product claim. Recommendations are proposals — several touch locked constraints
(new CLI commands / Store methods) and need maintainer approval per `AGENTS.md`.

## 1. The problem you set out to solve is real — with one correction

**[SPEC] Confirmed by the official docs** (code.claude.com/docs/en/skills):

- Every installed skill's `name` + `description` is injected into **every**
  session. The listing budget is **1% of the context window**
  (`skillListingBudgetFraction`, override `SLASH_COMMAND_TOOL_CHAR_BUDGET`).
- On overflow, Claude Code **silently drops descriptions**, least-used skills
  first. The skill still exists and `/name` still works, but the model can no
  longer choose it on its own. A warning goes only to the `--debug` log.
- Each description + `when_to_use` is capped at 1,536 chars
  (`skillListingMaxDescChars`).

**[SPEC] The correction — the always-on cost is often small; the bigger costs
are elsewhere.** Users repeatedly split the cost into two buckets:

| Bucket | Cost | Who reports it |
|---|---|---|
| Resident listing (descriptions, every turn) | low thousands → ~10–13k tokens at 40–90 skills | r/ClaudeCode "Stop messing your Claude with Skills" (41 skills); claude-code #43816 (47 skills ≈ 10k tokens/turn) |
| **Silent invisibility** (skills that never fire) | 12 of 91 skills never ran — all 12 had their description dropped | r/ClaudeAI "found out why 12 of my skills never fired" |
| **Wrong-skill activation** (a heavy skill body loads for a small task) | "30–50k tokens gone on the first prompt" | r/ClaudeCode 1ve5dc7, 1vjsblv ("bypass skills for small tasks") |
| **Conflicting / overlapping skills** | "some are contradicting and you can't figure it out" | r/ClaudeCode 1t4cy2y; r/ClaudeAI 1uhzgtm ("race condition") |

**So the pitch is not only "disable to save tokens".** The stronger pitch:
*"See which of your skills Claude can't actually see, which ones collide, and
which ones are too heavy — then fix it per project."*

## 2. What users say, in their words (Reddit, past 12 months)

**[NOTE]** Scores are Reddit points at read time; threads are small but
consistent. ~40 relevant threads found; 14 read in full with top comments.

- **"Around skill #30 I'd built a system I didn't want to use… I'd lost track of
  what was even loaded. When something went sideways, I had no idea which skill
  was responsible."** — *I deleted most of my Claude skills* (r/ClaudeAI 1sw6rss).
  → Users need **visibility and attribution**, not just toggles.
- **"Had 91 skills, 12 had never run once… turns out Claude never saw them. No
  warning anywhere… a colon in a plain YAML description can break the whole
  frontmatter without any error."** (r/ClaudeAI 1wwgsw7) → **Budget overflow +
  silent frontmatter breakage** is the single most concrete pain. Fix used:
  shorten the 27 longest descriptions to ~350 chars → 101 skills at 7.7k tokens.
- **"Ignoring some of them, even when useful / some too large / some
  contradicting."** (r/ClaudeCode 1t4cy2y)
- **"I don't want to miss important ones, but I also don't want my setup to
  become bloated."** (r/ClaudeCode 1s0k1vj) → fear of missing out + bloat.
- **"I switched off every built-in skill I never use"** — 12 pts, 22 comments,
  top reply asked *"So what was the context before and after? How much did this
  save?"* (r/ClaudeCode 1xhn8az) → **Show before/after token savings.** People
  won't trust a toggle without a number.
- **"With 200+ skills I lost track of which ones I use, and updating them by hand
  got annoying."** — author of a Claude Code mod that shows **usage count + last
  used** from transcripts and checks GitHub for updates (r/ClaudeCode 1xgpa06).
- **"Every skill you install wholesale brings its author's opinions into your
  codebase… Decisions persist forever."** — *Skills Curator* (r/ClaudeAI 1tc1o81):
  stack-aware recommendations, a pre-install scan, and stored keep/reject verdicts.
- **"70% carry at least one capability worth knowing: shell (50%), file writes
  (31%), network (31%), credentials (13%)… 59% of skills that fill `allowed-tools`
  understate what they can do… 99% leave a dependency unpinned… more popular
  skills tended to do more."** — scan of 6,309 public skills (r/ClaudeAI 1xb2eyh,
  arXiv 2610.19264). → **Capability disclosure** beats a binary "safe/unsafe".
- Counter-voice, worth respecting: *"Just get back to your job… use (or create)
  a skill that replaces your boring routine work."* (7 pts, top comment) and
  *"Just stop using skills."* A large group wants **fewer, curated** skills, not a
  bigger catalog — so "add every registry" is not by itself a selling point.

## 3. Upvoted demand on issue trackers

**[SPEC]** 👍 counts on 2026-10-30.

| 👍 | Issue | What it tells us |
|---|---|---|
| 82 | vercel-labs/skills — official support for **private skills** (closed) | Teams keep private skill repos |
| 53 | claude-code #14836 — `/skills` doesn't find skills in **symlinked directories** | Symlinked installs are common and break |
| 49 | vercel-labs/skills — **restore all skills from `skills-lock.json`** (`npm ci` equivalent) | **Reproducible per-project skill sets** |
| 33 | claude-code #15178 — plugin skills not injected into `<available_skills>` | "Is my skill actually visible?" |
| 31 | claude-code #12633 — **subagent-exclusive skills** (hide from main agent) | Route heavy skills to scoped agents |
| 18 | vercel-labs/skills — `update`/`check` for **non-GitHub sources** | Updates beyond GitHub |
| 13 | vercel-labs/skills — clone timeout on large monorepos | Sparse fetch matters |
| 10 | claude-code #98220 — let `skillOverrides` disable **plugin skills** | Per-skill control everywhere |
| — | claude-code #43816 / #43928 / #30423 — SkillSearch lazy loading, `disabledSkills`, **role-based skill profiles** | Profiles are asked for directly |
| — | claude-code #93318, #91833 — listing has **no source label**; built-in vs custom indistinguishable | Provenance in the UI |

## 4. Platform reality you must build on (changes your design)

**[SPEC] Claude Code now has native per-skill, per-project visibility** —
`skillOverrides` in `.claude/settings.local.json` (written by `/skills`):

| Value | Listed to model | In `/` menu |
|---|---|---|
| `on` | name + description | yes |
| `name-only` | name only | yes |
| `user-invocable-only` | hidden | yes |
| `off` | hidden | hidden |

Also: `disable-model-invocation: true` (frontmatter), `disableBundledSkills`,
`paths:` globs (load only when matching files are touched), `/doctor` (listing
cost + biggest contributors) and `/skill-doctor` (unused skills). Plugin skills
are **not** covered by `skillOverrides`.

**Consequence for skills-manager.** Today `disable` renames `SKILL.md` →
`SKILL.md.disabled`. That is **global and all-or-nothing**: disabling
`video-editing` for your coding repo also disables it for your video project.
Users asked for exactly the opposite (profiles per project). The native knob is
better on three counts: per-project, reversible without touching the skill, and
it has a **middle state** (`name-only`) that saves almost all the description
cost while keeping `/name` working. Renaming should become the fallback for
agents that have no native knob (Codex, Cursor, Gemini, OpenCode), not the
default for Claude Code.

## 4b. Every agent has its own native switch — and this app reads none of them

**[SPEC]** Verified from each tool's docs/issues on 2026-10-30:

| Agent | Native switch | Per project? | Middle state | Description budget |
|---|---|---|---|---|
| Claude Code | `skillOverrides` in `.claude/settings.local.json` (also `/skills` UI) | yes | `name-only`, `user-invocable-only` | 1% of window |
| Codex | `[[skills.config]] path=… enabled=false` in `~/.codex/config.toml` | **no** — a project `.codex/config.toml` is ignored for skills (openai/codex #20210); path selectors are canonicalized | none (`allow_implicit_invocation=false` only stops auto-use) | 2% of window, 8,000-char fallback |
| Gemini CLI | `gemini skills disable <name> --scope user\|workspace`, `/skills disable` | yes | none found | [?] |
| OpenCode | `permission.skill` patterns in `opencode.json` (`allow`/`deny`/`ask`, wildcards) | yes | `ask`; frontmatter `disable-model-invocation` | [?] |
| Hermes Agent | `hermes skills config` + background Curator | — | stale → archived | — |
| Cursor | none found | — | — | — |

**[SPEC] A defect in this app, found by this research.** `grep` over
`skillsmgr/` finds no reference to `config.toml` or `skillOverrides`. So the
"observed state" the UI reports is the *presence* layer only. A competitor's
issue tracker documents exactly what goes wrong for Codex
(xingkongliang/skills-manager, "Codex skills.config enablement is invisible"):

- the manager shows a skill **Active** while Codex has it disabled in
  `config.toml`. **Checked on this machine:** the one `[[skills.config]]`
  entry in `~/.codex/config.toml` is `path = "~/.agents/skills"`,
  `enabled = true`, so no skill is mis-reported *today* — the gap is latent,
  and appears the first time a user runs Codex's own `/skills` disable;
- conversely, re-deploying a skill from a different canonical path silently
  **re-enables** something the user turned off, because the rule no longer matches.

For a tool whose pitch is "trustworthy observed state", that latent gap is
the most important finding in this document. The minimum fix is read-only: read each
agent's native switch and show `Disabled by Codex config` / `Hidden by
skillOverrides` as an observed state. Writing those files is a separate,
approval-gated step.

## 5. Competitive landscape (GitHub, 2026-10-30)

| ⭐ | Project | Positioning | Gap you can own |
|---|---|---|---|
| 37,201 | vercel-labs/skills (`npx skills`, skills.sh) | installer + registry, 1,209 open issues | no context/visibility analysis |
| 10,813 | numman-ali/openskills | universal loader | last push Jan 2026; maintenance question open |
| 7,063 | xingkongliang/skills-manager | desktop app, 50+ tools, presets, 261 open issues | slow with big libraries (90 s cold start), updates break |
| 1,844 | qufei1993/skills-hub | "install once, sync everywhere" | sync only |
| 1,048 | jiweiyeah/Skills-Manager (`skm`) | symlink sync to 32 tools | sync only |
| 960 | luongnv89/asm | CLI: `stats --tokens` (resident vs body cost), **residency audit**, overlap audit, security audit, bundles, registry | closest competitor on context; CLI/TUI only |
| 4,151 | **microsoft/apm** (Agent Package Manager) | `apm.yml` + `apm.lock.yaml` across 9 agents; skills, prompts, plugins **and MCP**; any git host; hash-pinned, hidden-Unicode scan | owns *declared* config; no view of what is actually loaded or disabled |
| 461 | yibie/skills-manager | native macOS app, many agents | — |
| 334 | alvinunreal/lazyskills | TUI discover/install/manage | — |
| — | **Claude Code `/skill-doctor`** (built-in) | per-skill context cost + never-used skills, Claude Code only | went viral in ≥6 languages (@midudev 1,433❤, @dani_avila7 599❤) — the *diagnosis* is now native; the *cross-agent action with recovery* is not |
| — | **Hermes Agent Curator** (built-in) | stale after 30 d, archive after 90 d, snapshot before every pass, `pin`, `restore`, dry-run | the best design reference found for safe pruning |
| — | @camsoft2000 "Skill Manager" (macOS, launched 2026-09-30, 253❤) | menu-bar toggles, AI auto-grouping, broken-skill scan | replies asked for per-project sets and multi-machine sync |
| 0–30 | skillswitch, skill-manager (mrdenox109, edgar-montano, singme163), skillsbar, SkillsBar, Chops, SkillsGate, Skills Curator, claude-forge mod | per-project profiles, auto-disable, usage counts, menu-bar browsing | ~20 near-identical tools; fragmented, mostly single-agent |

**[NOTE] Only five managers have traction** (xingkongliang 7.1k, skills-hub
1.8k, skm 1.0k, asm 960, yibie 461); the rest of the 20+ sit at 0–30 stars.
There is no category winner, and the two platform players (Claude Code's
`/skill-doctor`, Microsoft APM) each cover one slice.

**[NOTE] The category is crowded on *sync* and *install*.** Nobody combines
(a) cross-agent inventory, (b) *what the model actually sees* per project,
(c) evidence-first safety, and (d) recovery. skills-manager already has (a),
(c) and (d) — `doctor --explain`, hygiene, risk scan, snapshots, trash, review-
first updates — which is the moat. Competing on "number of registries" is the
weakest position.

## 6. Recommendations, ranked by evidence × fit

Legend — **Fit**: uses existing surfaces (✓) or needs approval for a new CLI
command / Store method (⚠ locked constraint 5).

### Tier 0 — fix first (correctness of what the app already claims)

0. **Read every agent's native switch into observed state.** ✓ read-only
   (scopes/loader observation; no new command). Show `Disabled by Codex
   config.toml`, `Hidden by skillOverrides (name-only/off)`, `Denied by
   opencode.json`, `Disabled in Gemini (user/workspace)`. Without it the app's
   "Active" becomes wrong for Codex the moment a user disables a skill
   through Codex itself — see §4b. Also show **"takes effect in a
   new session"** per agent: two separate repliers to the Skill Manager launch
   asked exactly that (Codex reloads live; Claude Code usually needs a new
   session).

### Tier 1 — the core of your idea, done right

1. **Per-project skill profiles that write native settings.** ⚠
   One action, translated per agent: `skillOverrides` for Claude Code,
   `[[skills.config]]` for Codex (user-level only — the UI must say "this also
   affects your other Codex projects"), `gemini skills disable --scope
   workspace`, `permission.skill` for OpenCode, rename/symlink fallback for
   Cursor. Nobody found does this translation layer. Evidence: "per-project
   skill sets, so two agents in different repos can each have their own active
   group" (@_luisFilipePT on the Skill Manager launch), plus everything below.
   "Coding profile" = a saved set of on / name-only / off per skill, applied to a
   *project* by writing `skillOverrides` into `<project>/.claude/settings.local.json`
   (Claude Code) and falling back to rename/symlink for agents without a native
   knob. Profiles already exist in `catalog.py`; this extends their *apply* step.
   Evidence: claude-code #30423, #43928, asm/skillswitch/xingkongliang presets,
   every "too many skills" thread.
2. **"What the model sees" budget view per project.** ✓ (extends hygiene/tokens)
   Compute the resident listing exactly as Claude Code does: sum of description
   + `when_to_use` (capped at 1,536), against 1% of the selected window, and mark
   which skills **will lose their description** (least-used first). Show it as
   the existing context-budget meter. This is the "12 skills never fired" fix,
   and nobody's GUI does it.
3. **Before/after savings on every toggle.** ✓ (frontend)
   "Turning these 14 off saves ~6,800 resident tokens (0.7% of 1M); 3 skills
   regain their descriptions." Directly answers the top reply in 1xhn8az.
4. **Suggested profile from the project's stack.** ⚠ (read-only first)
   Read `package.json` / `pyproject.toml` / `go.mod` / `CLAUDE.md` and file
   types, and propose "keep frontend + testing, set marketing / video /
   finance to off". Output is a **preview the user approves** — never auto-apply
   (matches your review-first model). Evidence: Skills Curator, the
   mrdenox109 auto-disable tool, claude-code #39854.

### Tier 2 — high-signal problems you already half-solve

5. **Silent-failure lint.** ✓ (validator/hygiene)
   Flag: unquoted colons and other YAML that parses to empty metadata,
   descriptions over the 1,536 cap, descriptions likely to be dropped, missing
   "when to use" phrasing. Add "suggest a shorter description" (≤350 chars,
   what / when / not-for) as an editable proposal.
6. **Overlap / collision report** ✓ — hygiene's near-duplicate detection,
   reframed as "these 3 skills will compete for the same prompts" with
   description similarity. Evidence: 1t4cy2y, 1uhzgtm, asm `audit overlap`.
7. **Usage analytics from transcripts.** ⚠
   Count real invocations per skill from `~/.claude/projects/*/*.jsonl` (local,
   read-only): uses, last used, never used. Turns "disable unused" from
   guesswork into data. Evidence: claude-forge mod (200+ skills), `/skill-doctor`.
8. **Capability disclosure instead of a safety verdict.** ✓ (risk_scan)
   Per skill: runs shell / writes files / network / reads credentials /
   unpinned deps / `allowed-tools` understates actual capability. Show it on
   registry results *before* install. Evidence: 6,309-skill scan, Snyk
   ToxicSkills (36% prompt injection, 1,467 malicious payloads across ~4k
   skills), ClawHavoc (341 malicious skills).
8b. **Retroactive scan of everything already installed, across all agents.** ✓
   (hygiene + risk_scan over the existing inventory). Add two checks the X
   evidence names: **hidden Unicode / invisible instructions** (bidi, zero-width,
   tag characters, HTML comments) and **capability drift since install** (a
   source-locked skill whose scripts changed). Optionally *detect and call* an
   already-installed external scanner such as SkillSpector as advisory
   evidence — never a new runtime dependency (locked constraint 4), and never
   labelled "safe" (Trail of Bits beat three marketplace scanners).
9. **Symlink-aware handling.** ✓
   Your own UI found 301 of 1,962 instances as "Linked outside root", and
   claude-code #14836 (53 👍) shows users hit the same wall. Offer "copy into
   scope" or "register the target root" with a preview — the containment
   decision is already flagged as open in the progress log.

### Tier 3 — teams and reproducibility

10. **Project skill set — interoperate with `apm.yml`, don't invent a format.** ⚠
    The 49 👍 `npm ci` request is real, but Microsoft APM (4.1k ⭐) already
    defines `apm.yml` / `apm.lock.yaml` across 9 agents. Read it to show
    "declared vs actually present vs actually enabled" drift — the view APM
    lacks — and export a profile as `apm.yml`. Your `source_lock.py` hashes are
    the evidence layer.
10b. **Curator-style stale/archive, reversible.** ⚠ Borrow Hermes' design:
    mark stale after N unused days, archive (never delete) after M, snapshot
    before every pass, `pin` to exempt, one-click restore, dry-run by default.
    Your trash + snapshot model already provides the recovery half. This is the
    safe answer to the viral "run skill-doctor, then delete every skill it
    reports as unused" prompt (@dani_avila7), which deletes with no undo.
10c. **Sync across machines via a private Git repo.** ⚠ Asked under the Skill
    Manager launch (@kassamkhojaa) and in competitor trackers ("sync which skills
    are on/off across devices"); laptop-migration pain (@stephentonyyy). Your
    `backup_sync.py` Git seam with credential-helper delegation fits.
11. **Private registries / Git sources** ⚠ — private GitHub/GitLab/self-hosted
    Git as install sources (the 82 👍 request); `backup_sync.git_fetch` already
    delegates credentials safely.
12. **Kept/rejected decision memory** ✓ — store "I evaluated X, rejected because
    Y" in the catalog sidecar, so a skill that keeps resurfacing in registry
    search shows your past verdict (Skills Curator's best idea).

### Registries — yes, but differentiated

**[NOTE]** Adding more registries is fine, but every competitor already
searches skills.sh. Make registry results useful instead: show **resident token
cost**, **capability disclosure**, **overlap with what you already have**, and
**"fits this project's stack"** next to each result. That is the gap between a
catalog and a curator.

### What not to build (evidence says low value)

- An auto-disable that acts without a preview — conflicts with your trust model
  and with users who said they lost track of what was loaded.
- A huge bundled skill pack — the loudest voices say fewer, sharper skills.
- Raising the listing budget as the main fix — the docs themselves recommend
  trimming and `name-only` first.

## 7. Positioning line (proposal)

> **Your agent can't use a skill it can't see.** skills-manager shows exactly
> which skills each project's agent sees, which ones are silently dropped or
> colliding, and lets you switch per-project profiles with a preview, the
> token saving, and one-click recovery — across Claude Code, Codex, Cursor,
> Gemini, and OpenCode.

## 8. Method and coverage gaps

**[NOTE]** What was done: official docs fetched in full; `gh` API for stars,
issues, and reaction-sorted issue search; Reddit read through the OpenCLI
browser bridge (`opencli browser` on reddit.com, same-origin fetch of thread
JSON, top comments ≥2 points); web search for blogs/security research.

**[?] Not covered — do not treat as researched:**

- **X/Twitter**: read on a logged-in session in v1.1.0 (see §9). Searches are
  rate-limited (HTTP 429 after ~7 queries); queries that never returned are
  listed in §9 rather than silently dropped. Likes are X's count at read time;
  X's ranking favours viral threads, so the low-like replies were read too.
- **Instagram, Facebook groups, Discord**: not attempted; low expected signal
  for a developer CLI, but unverified.
- **Hacker News**: Algolia API probe returned no parsed hits; no HN threads read.
- **r/cursor, r/codex**: searched only through combined queries that Reddit
  does not support; not read individually.
- **Sample size**: Reddit threads are small (0–12 points, 4–28 comments). Treat
  them as qualitative signal; the issue-tracker 👍 counts are the stronger
  quantitative evidence.
- Competitor feature claims come from their READMEs and were not run locally.

## 9. X/Twitter — what builders say (v1.1.0)

**[NOTE]** 387 unique tweets from 16 searches plus four full reply threads,
2026-01 → 2026-10. Most high-like hits are generic "skills are amazing" listicles;
the signal below is what is specific to this product.

**The problem, from the people who build the agents.**

- **Boris Cherny (creator of Claude Code)**, as reported by @om_patel5 (427❤):
  *"people have way too many skills and agents inflating their context usage…
  be selective."* The platform owner names the problem this tool solves.
- **@dillon_mulroy (874❤):** *"I think skills are a mistake and the wrong
  abstraction. I almost never want my agent auto invoking them and I have built
  custom tooling to 'toggle' them on/off to prevent them from always being
  present in my context window."* Replies split — "only the description lives
  in context" vs "activating and deactivating is such a pain" (@rhoml) — and
  @ClaytonFarr names the real need: *"being able to quickly enable/disable
  skills for a given project or convo would help."*
- **@pseudokid (129❤):** trimmed OpenCode's system prompt from ~30k to 4–5k
  tokens by disabling skills — then: *"this is not the way. It makes the agent
  lame."* Users want the saving **without** losing capability → `name-only`
  and per-project sets, not mass deletion.
- **@thatroblennon, @p_rabtsevich, @davekiss, @IAenBruto** independently explain
  the 1%/2% budget: *"Why Claude/Codex CAN'T SEE and WON'T USE your skills."*
  The silent-truncation story is spreading on its own.
- **@evielync:** natural-language skill invocation *"doesn't seem to work as well.
  Maybe I have too many skills now."* — a non-developer feeling the same cliff.
- **@KingBootoshi (172❤):** *"too many harnesses. too many skills. too many
  mcps. JUST TOO MANY."* · **@gendev01:** "~/.claude and ~/.codex have way too
  many files which don't make sense."

**Skill Manager launch thread (@camsoft2000, 2026-09-30) — a free requirements list.**

| Reply | Need |
|---|---|
| "per-project skill sets, so two agents working in different repos at the same time can each have their own active group, instead of one global switch" | per-project, concurrent |
| "Any plans to support sync across multiple machines? … private GitHub repo" | multi-machine sync |
| "does toggling a skill off remove it from the current session's context?" (asked twice) | say when a change takes effect |
| "The grouping is the useful part… twenty overlapping instructions can quietly pull the agent in different directions" | conflict/overlap view |
| "Half the skills never fire and they still burn context every turn" | dead-skill detection |
| "the real bottleneck isn't loading, it's selection — the more skills, the more the model picks wrong" | routing quality, not just counts |
| "built a manager for the skills your agent can't manage on its own, we are three layers deep now" | keep the tool itself lightweight |

**Trust and provenance.** NVIDIA's "Verified Agent Skills" (1,765❤) ships a skill
card with origin, risks and modification state. Replies ask: *"Are skills signed
to ensure they haven't been modified?"*, *"who shipped it, what it can reach,
how it was checked, and when to pull it back"*, and warn *"'transparency' is a
dashboard, not a guarantee."* NVIDIA also reports verified skills improved task
correctness by 41 points in their own benchmark (vendor claim, not
re-verified). This matches the app's existing source-lock + risk-scan evidence
model and its refusal to call a scan a safety certification.

**Volume is the driver.** Viral posts celebrate packs of 286 skills / 68
subagents (ECC), "970 skills and 273 agents for $0", OpenMontage's 500+ video
skills, and an 817-skill security pack; Hermes advertises a hub of 88,000+
skills; one user "installed 145 claude skills at once to see what happens".
Each pack lands every description in every session — exactly the
coding-project-loading-video-skills case this project started from.

**Security is the loudest single topic on X.**

- *"The #1 most downloaded skill on OpenClaw marketplace was MALWARE… stole your
  SSH keys, crypto wallets, browser cookies, and opened a reverse shell… 1,184
  malicious skills found, one attacker uploaded 677 packages alone"*
  (@chiefofautism, 7,286❤). Independent counts: 341 of 2,857 ClawHub skills
  (11.9%, @aakashgupta 571❤ / Koi); Zscaler ThreatLabz traced Remcos RAT and
  GhostLoader payloads delivered through a skill.
- NVIDIA's open-source **SkillSpector** (71 attack patterns, 17 categories):
  across 31,132 skills, **26.1% had vulnerabilities and 5.2% looked malicious**
  (@RoundtableSpace 651❤ and several reposts; vendor figures, not re-verified).
- **Trail of Bits** built four malicious skills — *"Three took less than an hour…
  ClawHub, Cisco, and Vercel's skills.sh marked them as safe"* (280❤). A green
  scanner is not a safety verdict, which is the app's existing advisory stance.
- **Hidden instructions** humans don't see in a rendered skill (@ZackKorman 560❤);
  Microsoft APM scans for hidden Unicode on every install for this reason.
- **EvoMal** (@omarsar0 87❤): a malicious skill in a shared library spreads
  **without ever being invoked** — the agent copies it as a template when
  authoring a new skill. Installed-but-idle is not harmless.
- *"You scan AI skills before you install them. Now scan the ones you've
  already installed."* (@RoundtableSpace) — a retroactive inventory scan is a
  stated need, and the app already holds the inventory.
- [?] Several posts say Anthropic moved Agent Skills to the Linux Foundation
  and "70+ platforms" adopted it; not verified from a primary source here.

**How skills actually arrive: one viral `npx skills add` at a time.** The top
`skills.sh` / `npx skills` posts are install one-liners — a UI skill "installed
more than 30,000 times" (@jakubkrehel, 6,896❤), design (Hallmark 5,489❤,
TasteSkill, scandinavian-design), motion/Lottie/transitions, App Store
screenshots, **marketing** (Marketing Skills v2.0, 1,398❤), an APK
reverse-engineering/modding skill (2,232❤), and a viral "Find Skills" skill that
picks skills for a goal (1,505❤). The resulting library is mixed-domain by
construction — the coding-project-carrying-marketing-and-video-skills case this
project began from. Two consequences: (1) the `skills` CLI's lock file is the
most common record of *where a skill came from*, so reading it is the cheapest
route to update checks (the claude-forge mod can only update skills installed
that way); (2) the one-liner path installs a script-bearing skill with no review
step, which is the gap the app's review-first registry fetch already fills.

**Platform direction.** Anthropic's 2026-10-22 guide (widely shared) says one
agent with skills, loaded **only when needed**, beats stacks of subagents.
Claude Code's own `/skill-doctor` went viral in English, Spanish, Japanese,
Korean, Arabic and Chinese. Diagnosis is becoming a platform feature; acting on
it safely across agents is not.

**[NOTE] Query coverage.** 16 distinct X queries ran in three paced batches
because of HTTP 429 rate limits; all 16 eventually returned results. Raw
results: `/tmp/sm-research/x/` (not committed).

## Sources

- Claude Code skills docs — https://code.claude.com/docs/en/skills
- claude-code issues: #43816 (SkillSearch), #43928 (`disabledSkills`), #14836,
  #15178, #12633, #98220, #93318, #30423 — https://github.com/anthropics/claude-code/issues
- vercel-labs/skills issues — https://github.com/vercel-labs/skills/issues
- Reddit: r/ClaudeAI 1sw6rss, 1wwgsw7, 1xb2eyh, 1tc1o81, 1xj49xc, 1uhzgtm;
  r/ClaudeCode 1t4cy2y, 1s0k1vj, 1xhn8az, 1xgpa06, 1ucjf62, 1r08xbf, 1vjsblv, 1ve5dc7
- Snyk ToxicSkills — https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/
- 6,309-skill capability study — https://arxiv.org/abs/2610.19264
- Agent skill security survey — https://arxiv.org/pdf/2607.13987
- asm — https://github.com/luongnv89/asm
- xingkongliang/skills-manager — https://github.com/xingkongliang/skills-manager
- Skill listing budget write-ups — https://blog.fsck.com/2025/12/17/claude-code-skills-not-triggering/ ,
  https://rzailabs.com/blog/claude-code-skills-listing-budget
- Codex skill config — https://developers.openai.com/codex/config-reference ,
  https://github.com/openai/codex/issues/20210 , https://github.com/openai/codex/issues/14316
- Gemini CLI commands — https://geminicli.com/docs/reference/commands/
- OpenCode skills — https://opencode.ai/docs/skills.md
- Hermes Curator — https://hermes-agent.nousresearch.com/docs/user-guide/features/curator
- Microsoft APM — https://github.com/microsoft/apm
- Codex enablement gap in a competitor — https://github.com/xingkongliang/skills-manager/issues
- X: https://x.com/i/status/2105284674947833956 (Skill Manager launch + replies),
  https://x.com/i/status/2052778906516619569 (@dillon_mulroy),
  https://x.com/i/status/2043885581533577686 (Boris Cherny, via @om_patel5),
  https://x.com/i/status/2057496919425900834 (NVIDIA Verified Skills),
  https://x.com/i/status/2106038403733098713 (@midudev `/skill-doctor`)
