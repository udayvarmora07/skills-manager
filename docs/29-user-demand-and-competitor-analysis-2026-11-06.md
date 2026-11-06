# User Demand and Competitor Analysis — skills-manager

**Version 0.2.0**

**AI manifest**: Evidence-led analysis dated 2026-11-06 of what users of AI coding-agent skills ask for, what competing tools ship, and what skills-manager should do about it. It merges four research passes (GitHub issue trackers, community channels, a competitor feature matrix, a spec and security review) with the earlier user-research and monetization notes (docs/26 and docs/27, which exist only in the main checkout and are cited in prose). Proposals only: nothing here is approved, and every item that touches a locked constraint is flagged for the maintainer. Evidence and opinion are labelled separately.

## Status and how to read this

**[NOTE]** This document changes no code, CLI command, Store method, schema or dependency. It extends @docs/28-project-review-and-recommendations-2026-11-06.md (which covers the repository's own health) with the demand side. Where it disagrees with @docs/14-competitive-product-business-strategy-2026-09-15.md, that document still stands until the maintainer decides.

Conventions: **[SPEC]** marks a measured or sourced fact, **[NOTE]** context or opinion, **[?]** unverified or single-source. Reaction counts are thumbs-up on GitHub issues at read time. "Today" is skills-mgr as documented in the README, @docs/03-cli-surface.md and @docs/08-web-ui.md, not re-run for this document.

## 1. Executive summary

1. **[SPEC] The pain is real and is mostly about visibility, not toggling.** Users report skills that never fire because the agent's listing budget silently drops descriptions, and they have no way to see which skills the model can actually see. Evidence: HN thread 46871173 (six commenters), a Vercel eval quoted in HN 46809708 (skill never invoked in 56% of cases), claude-code #9716 (75 thumbs-up, 69 comments), and the Reddit threads recorded in docs/26.
2. **[SPEC] The loudest single request is one canonical skills folder.** claude-code #31005 ("Support AGENTS.md and .agents/skills/") has 447 thumbs-up and 37 comments and is still open. vercel-labs/skills #744 and #693 show installers writing to `~/.agents/skills` where Claude Code cannot see them. skills-mgr already has an `agents` scope; it does not bridge or explain the gap.
3. **[SPEC] A real defect is still open.** No code in `skillsmgr/` reads any agent's native enable/disable switch (Claude Code `skillOverrides`, Codex `[[skills.config]]`, OpenCode `permission.skill`). The tool can show Active for a skill the agent has turned off. For a product that sells trustworthy observed state, this outranks every new feature. It is latent on the maintainer's machine, not live.
4. **[SPEC] Lock files are the de-facto reproducibility story, and skills-mgr reads none.** Vercel's `skills-lock.json` and Microsoft APM's `apm.lock.yaml` carry the community's "restore my setup" demand (vercel #549, 49 thumbs-up; #283, 58). A read-only declared-versus-present-versus-enabled view fits the tool's evidence model and avoids inventing a format.
5. **[NOTE] The durable differentiator is trust, not breadth.** Competitors leak or crash: the Vercel CLI reads credentials through `gh auth token` (#523, 33 thumbs-up), the desktop leader has black-screen and cold-start reports, and asm's own scanner follows symlinks and prints secrets. A local, stdlib-only, loopback-only, no-telemetry tool with recovery can say things they cannot. It cannot win on the number of agents (about 79 for Vercel's CLI against 7 agent scopes here).
6. **[NOTE] Platform risk is concentrated in single-agent users.** Native switches, `/skill-doctor`, org provisioning and the AGENTS.md fallback all erase single-agent demand over time. The multi-agent power user, who needs a cross-agent view and recovery, is the defensible segment.
7. **[NOTE] Willingness to pay is unproven.** The strongest category leader is funded by a tip jar, and no tracker issue asks to pay. The services-first stance in docs/27 stays the sensible reading of the evidence; this document adds no new pricing claim.

## 2. Evidence base and its limits

**[SPEC] Channels read.**

| Channel | What was read | Strength |
|---|---|---|
| GitHub issues | Reaction-sorted and title-scoped searches on claude-code, vercel-labs/skills, openai/codex, opencode, microsoft/apm, agentskills, ruler, rulesync, xingkongliang/skills-manager; about 12 issue bodies in full | Strongest quantitative evidence; counts are comparable across trackers |
| Hacker News | About 12 threads, roughly 1,000 comments scanned by keyword | Medium; qualitative, skews to experienced developers |
| Reddit and X | Read only in the 2026-10-30 pass (14 Reddit threads in full; 387 to 475 tweets, depending on the pass) and recorded in docs/26 and docs/27 | Medium; small threads, X ranking favours viral posts |
| YouTube | Comments on 3 videos | Weak |
| Competitor READMEs and docs | Feature matrix for 10 tools | Medium; documentation claims, not run locally |
| Spec and agent docs | agentskills.io specification, per-agent skill docs | Strong for what agents document; silent on runtime behaviour |

**[SPEC] Channels blocked or not read.**

- **Reddit and X were not re-read in this pass.** Reddit blocks the search tool and its JSON endpoints, and the browser bridge was disconnected. For both, docs/26 and docs/27 remain the only evidence.
- **Instagram was not attempted.** Facebook groups and Discord were not read in either pass.
- **Chinese forums returned nothing indexed.** V2EX, Juejin and Zhihu produced no posts. The Chinese evidence is Chinese-language GitHub issues plus one article derived from Linux.do. docs/27 reports Chinese-language X posts that recommend skills managers; that is a signal, not a measurement.
- **Product Hunt gave listings only,** no comment text.

**[NOTE] How this biases the conclusions.**

- Developers who file GitHub issues and post on HN over-represent power users and under-represent non-coders. The non-coder segment is effectively unmeasured here.
- Thumbs-up counts measure agreement on a public tracker, not purchase intent. Willingness to pay stays [?].
- Claude Code dominates the evidence because its tracker is the busiest. Needs of Codex, Gemini and Cursor users are likely under-counted.
- Competitor feature cells say "not documented", not "absent". A tool may ship a feature its README omits.
- Vendor figures (NVIDIA, Snyk, Koi, OWASP pages) are the vendor's own claims and were not re-verified.

## 3. Demand map

**[SPEC]** Ranked by evidence strength first, then by fit. Evidence labels: strong means 40 or more thumbs-up on at least one tracker issue, or three or more independent channels; medium means 10 to 39 or two channels; weak means a single source or fewer than 10. "Fit" is against the locked constraints in AGENTS.md (filesystem authority, schema unchanged, stdlib-only CLI, stdlib web UI with no build step, no new CLI commands or Store methods without approval). URLs are abbreviated: `cc` is github.com/anthropics/claude-code/issues, `vs` is github.com/vercel-labs/skills/issues.

| # | Need | Segment | Evidence | skills-mgr today | Fit | Effort | Approval |
|---|---|---|---|---|---|---|---|
| 1 | One canonical `.agents/skills` folder that every agent reads | Multi-agent | Strong: cc/31005 447 up; vs/744 38 up; vs/693 25 up; HN 46871173 | Partial: `agents` scope exists, no bridge or explanation | Fits as read-only explanation; a bridge writes symlinks (filesystem, allowed) | M | Yes if a new command; no if inside sync or doctor |
| 2 | See which skills the model actually sees, and which are silently dropped | Solo, multi-agent | Strong: cc/9716 75 up; HN 46871173; 56% non-invocation in HN 46809708; Reddit per docs/26 | Partial: token meter, `doctor --explain`; no listing-budget model | Fits (extends hygiene and tokens) | M | No |
| 3 | Read the agent's own off switch (observed state matches reality) | Multi-agent | Strong as defect: docs/26 section 4b; strong as demand: opencode/34498 70 up, codex 29989 58 up | None | Fits as read-only; Codex TOML needs `tomllib` (3.11+) or a small extractor | M | Yes for raising the Python floor; no for a read-only extractor |
| 4 | Restore a setup from a lock file | Team, multi-agent | Strong: vs/283 58 up; vs/549 49 up; vs/155 35 up | Partial: source-lock sidecar, no restore | Reading is fine; restoring needs a new command | M | Yes |
| 5 | Symlinked skill directories that work | Multi-agent | Strong: cc/14836 53 up; codex 8369 45 up; vs/744 38 up | Detects "linked outside root" (301 of 1,962 instances on the maintainer's machine); no fix | Fits as preview-first copy or register-root action; containment policy is open | M | Yes (changes the containment model) |
| 6 | Non-destructive off switch per skill and per project | Solo, multi-agent | Strong: cc/14920 100 up; vs/634 25 up; cc/26838 44 up | Partial: global rename only | Fits for rename; native writes are a separate step | M | Yes for writing native settings |
| 7 | Usage data: which skills were invoked | Team, enterprise | Strong: cc/35319 43 up ("67 to 183 skills in under a month"); opencode/7533 19 up; Reddit mod in docs/26 | None | Read-only transcript parsing fits; it adds surface | L | Yes (new command or Store method) |
| 8 | Org or team skill source from a Git repo, versioned | Team, enterprise | Strong: cc/28729 99 up, 39 comments; vs/381 82 up (closed); HN 49169640 | Partial: `backup_sync` Git seam, local review only | Fits via existing credential delegation | L | Yes |
| 9 | Skill versions and pinning | Team, author | Medium: vs/11 30 up; agentskills/110; HN verdverm | Partial: source-lock hashes, no pin semantics | Fits (extends `source_lock`) | S | No |
| 10 | Sync Claude Desktop and CLI skills | Non-coder, solo | Strong: cc/20697 162 up, 49 comments | None | Unclear: Desktop storage not examined [?] | M | Unknown |
| 11 | Recursive and monorepo discovery | Multi-agent | Strong: cc/10238 168 up; cc/18192 63 up; cc/26489 50 up | Partial: recursive scopes | Fits | S | No |
| 12 | Listing budget visible and configurable per agent | Multi-agent | Medium: codex/19679 40 up; codex/31088 14 up | Partial: window selector, no per-agent budget | Fits | S | No |
| 13 | Agent-specific frontmatter honoured or flagged (for example `disable-model-invocation`) | Multi-agent | Strong: opencode/34498 70 up; codex 29989 58 up; HN 46871173 | None: key not surfaced, validator ignores per-agent keys | Fits as lint or explain finding | S | No |
| 14 | Fewer, leaner skills with token numbers before and after | Solo | Medium: HN nullstyle and zuzululu; YouTube video with 137k views; Reddit 1xhn8az per docs/26 | Partial: `tokens`, meter, hygiene | Fits; before and after on every toggle is frontend-only | S | No |
| 15 | Capability disclosure and hidden-Unicode scan on installed skills | Enterprise, multi-agent | Medium: HN 49169640; vs/523 33 up; Reddit and X per docs/26; OWASP AST09 | Partial: `risk_scan` is advisory; no Unicode scan | Fits (stdlib `unicodedata`) | S | No |
| 16 | Safe recovery from a bad cleanup | All | Medium: HN y-curious on deleting later; viral delete-unused prompt in docs/26 | Covered: trash, snapshots, review-first update | Fits | none | No |
| 17 | Declared-versus-present drift across machines | Multi-agent, team | Medium: dev.to opensite and dotwee posts; cc/36693; vs/542 (two lock files) | Partial: duplicate and divergent detection within one machine | Read-only compare fits; cross-machine needs Git sync | L | Yes |
| 18 | Test or evaluate a skill before trusting it | Author, team | Medium: HN SkillsBench (364 points) and agent-skills-eval; HackerNoon post | Partial: advisory eval harness | Fits | S | No |
| 19 | Update or check non-GitHub and private sources | Team | Medium: vs/386 18 up; vs/162 15 up; vs/418 11 up | Partial: update preview from folder or snapshot | Fits via `backup_sync` seam | M | Yes |
| 20 | Plugin skills visible and selectable | Multi-agent | Strong: cc/18949 74 up; cc/17271 44 up; cc/15178 33 up | None: plugin skills not read [?] | Read-only inventory plausible; plugin layout varies | M | No |
| 21 | Same-name collision handling | Multi-agent | Weak: apm/1120 6 up; cc marketplace collision 3 up; cline/9885 | Covered: duplicate and divergent detection; "overwrite on sync" not flagged | Fits | S | No |
| 22 | Cross-tool format conversion of frontmatter | Multi-agent | Weak: apm/581 8; ruler/198 9; rulesync/422 3 | Partial: sync copies verbatim | Fits as per-target warnings, not rewrite | M | No |
| 23 | MCP, AGENTS.md and rules managed beside skills | Multi-agent, team | Medium: xingkongliang #266, #465, #55; docs/27 reports it as the most-cited drift; @theo poll 2,013 likes | None | Widens scope; needs an ADR | L | Yes (maintainer question MON-Q2) |
| 24 | Windows install reliability | Windows users | Weak: openskills #43, #28; asm #138; xingkongliang crash reports | Unknown; Windows legs exist in CI | Fits | S | No |
| 25 | Skill CI headless checks on pull requests | Author, team | Weak: rulesync/552 2; agentskills/114 6 up | Partial: `validate`, JSON output | Fits as a documented recipe; an Action is distribution work | S | No |

**[NOTE]** Rows 1, 2, 3 and 13 share one underlying need: "what will this agent really load, from where, and is it switched off". The tool already has the machinery (`doctor --explain`, scopes, hygiene). The demand map suggests presenting it as a single question the user can ask, which is what section 6 proposes.

## 4. Perspectives

### 4.1 Solo developer, one agent

- **[SPEC]** The need is fewer skills and proof of savings. The top reply to a "switched off every built-in skill" thread asked how many tokens it saved (Reddit 1xhn8az, via docs/26). A before-and-after number on every toggle answers it and is frontend-only.
- **[NOTE]** This segment is the most exposed to platform absorption. Claude Code ships `/skills`, per-project `skillOverrides` and `/skill-doctor`. Do not build for this user alone.
- **[SPEC]** A counter-voice exists: HN 48015397 warns of the "perfect productivity stack" trap, and others say to try a fresh session without skills. Honest copy ("remove what you do not need") fits the tool better than "manage more".
- **[NOTE]** First-run should work with zero configuration and show a result in one screen. The existing first-scan guide already does this; keep it.

### 4.2 Multi-agent power user (core target)

- **[SPEC]** This user runs several agents and several machines. docs/27 quotes one who runs six agents on two machines and calls keeping MCP, skills and AGENTS.md in sync "the most annoying part".
- **[SPEC]** Three pains recur: the same skill copied into several folders and diverging, installers that write where one agent cannot see (vs/744, cc/31005), and per-agent off switches that all differ (HN likium: three mechanisms).
- **[NOTE]** The product answer is a cross-agent view of "what each agent loads", with the reason and the recovery path. No researched competitor combines cross-agent inventory, effective-load explanation, review-first change and recovery.
- **[NOTE]** Add the missing consumers (Copilot, Windsurf/Devin, Amp, Kiro, Roo, Cline, Zed, Antigravity) only with cited precedence rows. The existing rule stands: never elect a winner that cannot be cited.
- **[?]** Whether this user wants a GUI at all or only the CLI and CI is not measured.

### 4.3 Team lead

- **[SPEC]** Asks: a shared, versioned skill set from a private repository, with pinning (vs/381 82 up, closed; vs/549; cc/28729). docs/26 notes that one HN commenter built an org plugin with semver auto-update.
- **[NOTE]** Platforms are moving here: Claude org provisioning, managed settings, Microsoft's `apm.yml` with policy files. A tool that defines yet another team format loses. A tool that reads `apm.yml`, `apm.lock.yaml` and `skills-lock.json` and reports drift against what is actually present adds value to all of them.
- **[SPEC]** Team setups drift with model versions (HN j45, TomGarden). A "what changed since the lock" report is useful before any distribution feature exists.
- **[NOTE]** Do not build hosted sharing first. The Git seam in `backup_sync` with credential-helper delegation already avoids storing secrets.

### 4.4 Enterprise, admin and security

- **[SPEC]** Security is the loudest topic in docs/27's X pass (malicious skills on marketplaces, vendor scans). Trail of Bits reported that marketplace scanners marked hand-built malicious skills as safe. Auditors also disagree on the same skill on skills.sh pages (secondary source).
- **[NOTE]** Position: verdict-free capability disclosure, exact provenance, and drift evidence. Do not publish a safe/unsafe label. The existing advisory stance is correct.
- **[SPEC]** "Scan what you already installed" is a stated need (docs/27 quotes a post making it). The tool already holds the inventory, so a retroactive scan plus a hidden-Unicode check (Microsoft APM does this at install) is a low-effort addition.
- **[SPEC]** Governance gaps: no central policy, no allowlist, no audit trail across machines. A local tool cannot provide these; say so plainly rather than imply it.
- **[?]** OWASP AST09 "No Governance" and the Backslash and Speakeasy write-ups are vendor-authored.

### 4.5 Non-coder and Desktop user

- **[SPEC]** Evidence is thin. The visible items are Desktop and CLI skill sync (cc/20697, 162 up) and one tweet from a non-developer who felt the "too many skills" cliff.
- **[NOTE]** The current UI assumes folders and `SKILL.md`. The new `/v2/` interface uses plainer language ("Linked elsewhere", "Not a skill"), which helps. A real non-coder segment would need install without a terminal, and the tool does not offer that.
- **[?]** Treat this segment as unproven. A cheap test is to watch three non-developers use `/v2/` with the first-scan guide.

### 4.6 Skill author and publisher

- **[SPEC]** Authors want to test a skill before shipping (HackerNoon: typos break triggers) and to know it validates. The validator already follows the specification; the spec reference validator `skills-ref` is a free differential oracle for tests.
- **[SPEC]** The 1,536-character description cap, `when_to_use` handling, and the unquoted-colon failure (a YAML colon silently breaking frontmatter, per a Reddit thread in docs/26) are not linted. These are cheap, concrete wins.
- **[NOTE]** Publishing is the registry's job. The tool's role is pre-publish checks and a documented CI recipe.
- **[SPEC]** On the maintainer's machine, 249 of 289 validation errors come from one third-party pack writing `compatibility` as a mapping. Authors need the explanation (the spec requires a string; agents ignore it; uploads reject it), not a weaker validator.

### 4.7 Agent vendors (platform risk)

- **[SPEC]** Already shipped natively: Claude Code per-project `skillOverrides` and `/skill-doctor`, Claude org provisioning, an AGENTS.md fallback (HN 49760187, Claude Code 2.1.277), Codex `[[skills.config]]`, Gemini `skills disable`, OpenCode `permission.skill`, and `skill_activated` OpenTelemetry events (per docs/27).
- **[SPEC]** Open and possibly next: skills-directory parity for `.agents/skills` in Claude Code (cc/31005), usage dashboards, and Microsoft's APM covering declared config across nine agents.
- **[NOTE]** What each would erase: native `.agents/skills` support removes the bridge need; native org distribution removes team sharing for Claude-only teams; `/skill-doctor` removes basic diagnosis for single-agent users.
- **[NOTE]** What none would erase: a view across vendors that each vendor has no incentive to build, local recovery, and neutrality (docs/27 quotes a user objecting that a harness vendor's skill manager creates lock-in).
- **[?]** The "Agent Plugins 1.0" specification and its steering committee come from secondary blogs with conflicting dates. Check the primary specification before building on it.

### 4.8 Open-source contributor

- **[SPEC]** The repository has 1 star against 38,279 for the Vercel CLI and 7,300 for the desktop leader (2026-11-06). A contributor will find a 1,234-test suite, a complexity ratchet and strict gates, which is a strength but also a high bar.
- **[NOTE]** Lower the entry cost: label a few S-effort issues (row 9, 11, 12, 13, 15, 18 in the demand map), and keep the locked-constraints list short and visible. Contributors will otherwise propose dependencies the tool refuses.
- **[NOTE]** Housekeeping signals matter to newcomers: five Dependabot PRs open since 2026-09-16, 11 outstanding worktrees and branches, and large root files are recorded in @docs/28-project-review-and-recommendations-2026-11-06.md.

### 4.9 Business and monetization

- **[SPEC]** docs/27 concludes that the leader is funded by a tip jar, platforms absorb the toggle, and money moves to services and security. It recommends a fixed-price Agent Setup Audit first, Skill CI only after three paid audits, and team profiles only after two requests. It proposes starting prices to test; this document does not repeat or add any.
- **[NOTE]** The demand map supports that order. The audit's content (resident token cost, skills that cannot fire, conflicts, capability findings) maps to rows 2, 12, 14, 15 and 21, all of which are S or M and none of which needs a locked-constraint change.
- **[NOTE]** Demand for team features (rows 4, 8, 17, 19) is real on trackers but nobody there states a price. Build them only if audits surface the same request twice, as docs/27 already says.
- **[?]** No buyer has been interviewed.

### 4.10 UX and accessibility

- **[SPEC]** Competitors' desktop apps are reported to show black screens on preview, fail to start after updates, and show a wrong "synced" state (xingkongliang #144, #69, #111, #412, #384). A localhost web app with honest labels avoids the first two classes.
- **[NOTE]** The `/v2/` rule "no newer or older claims, because no version order exists" is the right instinct. Carry it into every new view: show observed facts, never inferred winners.
- **[SPEC]** Users asked twice whether a toggle takes effect in the current session (docs/26). Every state change should say when it takes effect per agent (Codex reloads live; Claude Code usually needs a new session, per replies recorded in docs/26).
- **[?]** Human perceptual review, screen reader, forced-colors and zoom coverage remain open from earlier passes. Any new view inherits the same gap.

### 4.11 Reliability and trust

- **[SPEC]** Competitor failures that skills-mgr can avoid or detect: two lock files with different schemas where `update` ignores the project lock (vs/542); `update <skill>` adding every other skill from the repo (vs/915, 44 up); absolute paths written into lock files (vs/561); credential harvesting through `gh auth token` (vs/523); telemetry leaking private-repository metadata (vs/699); asm's scanner following symlinks outside the skill and printing secrets (asm #795, #791).
- **[NOTE]** Say so, carefully. A "no credentials, no telemetry, loopback only" statement in the README is a differentiator, but only for what has been verified. The GitHub research notes that zero outbound calls beyond the registry was not verified; verify before claiming.
- **[SPEC]** Own-house caveat: @docs/28-project-review-and-recommendations-2026-11-06.md records two MEDIUM findings (tar import memory exhaustion; forged provenance sidecars accepted) and one LOW-MEDIUM (lock files depend on `TMPDIR`). A trust pitch is only as good as those fixes. Ship them before the pitch.

### 4.12 Distribution and discoverability

- **[SPEC]** Measured 2026-10-30: 1 star, 121 PyPI downloads last month. 2026-11-06 stars: 38,279 (Vercel CLI), 7,300 (desktop leader), 4,246 (Microsoft APM), 966 (asm).
- **[NOTE] Why the gap (opinion, partly evidenced).** Skills arrive through one-line `npx skills add` posts (docs/27 lists installs in the tens of thousands for single skills); the leader sits inside that channel and a Python tool does not. The desktop leader has a download button; this tool asks for `pip` and a localhost URL. The README leads with a feature list, not a result.
- **[NOTE] What would change it:** a published data report on the most-installed public skills (docs/27 recommendation, pending decision MON-Q3); a one-command "see what your agents load" demo that prints a result in under a minute; presence in the registries people already search (PyPI exists; consider the Homebrew route the Windows/macOS competitor uses); and answering the live threads (cc/31005, vs/549) with a working, honest tool rather than self-promotion.
- **[?]** None of these is tested. Distribution is likely to depend on the services-first work in docs/27 more than on features.

## 5. Competitor lessons

**[SPEC]** Matrix highlights (documentation-based, "not documented" is not "absent"): lockfile support is present in Vercel's CLI, Microsoft APM and ai-rulez, and absent here; security scanning is present in APM, asm and ai-rulez, partial here; native-disable reading is documented by none of the ten; token or context view is present only in asm and here; local web GUI exists only here (others are desktop or TUI); JSON output and headless use are common; MCP and rules management is covered by APM, rulesync, ruler and ai-rulez.

**What to copy**

- **Read, do not invent, lock formats** (Vercel, APM). Report declared versus present versus hash-matched.
- **Hidden-Unicode, bidi and tag-character scan** (APM install scan). Small, stdlib, advisory.
- **Audit by rebuild** (APM `audit`): rebuild the expected state and diff it with the working tree, matching the tool's evidence habit.
- **Residency audit** (asm): rank skills to demote to name-only. It is the usable form of "which skills cost the most for the least use".
- **Overlap audit with an explanation** (asm): extend the existing near-duplicate Jaccard evidence.
- **Windows fallback chain** (jiweiyeah/Skills-Manager: symlink, then junction, then tracked copy with a source sidecar) if a bridge is built.
- **Curator-style stale and archive with snapshots, pin and dry-run** (Hermes Agent, per docs/26) layered on the existing trash and snapshots.
- **`generate --check` style CI drift check** (ai-rulez) as a documented recipe over `validate` and `doctor`.

**What to avoid**

- Auto-applying changes without a preview; users said they lost track of what was loaded.
- Full-repository clones for installs (xingkongliang #614; Vercel clone timeouts).
- Absolute paths in persisted state, empty hashes for private sources, and any credential harvesting.
- Counting agents as a goal. Add a consumer only with a cited precedence row.
- A verdict label from an in-house scanner.

**Where skills-mgr is genuinely differentiated** (evidence: feature matrix and README)

- Review-first update with a staged candidate, hash checks and complete-tree snapshots; competitors mostly overwrite.
- Trash, history and snapshot recovery; the matrix marks backup or undo as absent or partial for most tools.
- Observed-state vocabulary that separates active, disabled, malformed, linked and divergent, and refuses to claim an effective winner it cannot cite (`doctor --explain`).
- Local-only by construction: stdlib runtime, loopback bind, request policy on every verb, no telemetry in the product (to be verified before claiming broadly).

## 6. Recommended roadmap

**[NOTE]** Opinion built on the evidence above. "Approval" follows AGENTS.md judgment boundaries; anything marked yes waits for the maintainer.

### Horizon 1: next two weeks (fix, verify, then explain)

| Item | Evidence it rests on | Approval |
|---|---|---|
| Fix the two MEDIUM security findings (streamed tar caps; strip forged sidecars at intake) and the lock-file location | @docs/28-project-review-and-recommendations-2026-11-06.md S1 to S3 | No |
| Read native off switches into observed state, read-only (Claude Code `skillOverrides`, OpenCode `permission.skill`; Codex only if a small extractor or the 3.11 floor is accepted) | Open defect; rows 3, 6, 13 | Yes for the floor, no for an extractor |
| Surface per-agent ignored frontmatter (for example `disable-model-invocation`) as a finding | opencode/34498 70 up, codex 29989 58 up | No |
| Dedupe the `compatibility` error by physical identity, explain it, and add the unknown-key warning | 249 of 289 errors from one pack | No |
| Lint the 1,536-character description cap and the unquoted-colon failure | Reddit threads per docs/26; spec | No |
| Make the body-less list projection decision (22.7 MB payload) before `/v2/` becomes default | @docs/28-project-review-and-recommendations-2026-11-06.md R3 | Yes if the public list contract changes |
| README: add a "what it will not do" and a verified privacy statement | Sections 4.11 and 4.12 | No |

**UI implications (`/v2/`).** The detail view for a skill gains an "Invocation and visibility" panel per consumer: present, enabled or switched off natively, listed, name-only or dropped, with the reason and "takes effect in a new session". The Home view's agent rooms gain a native-switch badge. Neither needs a new endpoint if the data arrives through existing observation fields.

### Horizon 2: next quarter

| Item | Evidence it rests on | Approval |
|---|---|---|
| Listing-budget model per agent (1% for Claude Code, 2% for Codex per docs/26) with "will lose its description" marking | Rows 2, 12; cc/9716; codex/19679 | No |
| Before-and-after token saving on every toggle (frontend) | Row 14; Reddit 1xhn8az | No |
| `.agents/skills` to `.claude/skills` bridge with symlink-safety and a preview; explain-only first | Row 1; cc/31005 447 up; vs/744 | Yes if it becomes a new command |
| Symlink handling: "copy into scope" or "register the target root" with preview | Row 5; cc/14836 53 up; 301 of 1,962 instances on the maintainer's machine | Yes (containment model) |
| Lock-file reader: declared versus present versus hash match for `skills-lock.json` and `apm.lock.yaml`; orphan and unlinked-install detection | Rows 4, 17; vs/549, vs/577, vs/744 | Yes unless folded into `doctor` |
| Hidden-Unicode scan and retroactive scan of installed skills | Row 15; APM; docs/27 X pass | No |
| Residency and overlap reports | Row 14; asm | No |
| Add consumer rows (Amp, Roo first, where full orders are documented) | Spec and agent-docs pass | No |
| A documented Skill CI recipe over existing commands | Row 25 | No |

**UI implications.** A lockfile panel in Recovery or Sync map ("Declared / Present / Enabled", three columns, no inferred winner); a residency list ("cost most, used least" only if usage data exists, otherwise "cost most"); a bridge preview dialog that shows the exact links it would create and how to undo them.

### Horizon 3: later

- Usage analytics from local transcripts (row 7; cc/35319), read-only, per agent. **Approval: yes.** Highest-evidence large item, and the one most exposed to native features.
- Private and non-GitHub update checks through the existing Git seam (rows 8, 19). **Approval: yes.**
- Curator-style stale and archive pass with pin and dry-run, built on trash and snapshots.
- MCP and AGENTS.md drift views (row 23). **Approval: yes; needs an ADR first** (MON-Q2 in docs/27).
- CycloneDX or SPDX export from source-lock data. **Approval: yes** (new command).
- NFKC Unicode names per the specification. **Approval: yes** (locked name rule).
- zh-CN interface (MON-Q4 in docs/27). **Approval: yes** (reverses `lang="en"`).

## 7. Bets not to make

- **Competing on registry scanning verdicts.** Funded vendors scan (docs/27 cites AIR, Upwind, Snyk and others), auditors disagree, and Trail of Bits showed marketplace scanners passing malicious skills. Integrate or call external scanners as advisory evidence instead.
- **A desktop shell.** The leader's reliability issues are partly desktop-shell issues, the tool is deliberately stdlib with no build step, and @docs/08-web-ui.md records the decision to keep the browser (with an optional unbundled launcher).
- **Another marketplace or a skill pack.** Supply is free and mostly poor; docs/27 counts at least eight marketplaces.
- **Chasing agent count.** Vercel's CLI lists about 79; adding unsourced precedence rows breaks the "never elect an uncited winner" rule.
- **Paywalling local features.** The code is MIT; a paywall invites a fork (docs/27).
- **A new lock format.** Interoperate with the two existing ones.
- **Auto-disable without a preview.** It conflicts with the review-first model and with what users said.
- **Hosted sync.** Git with the user's own credential helper covers the need without a service to secure.

## 8. Open questions for the maintainer

**[?]** Decisions only the maintainer can make.

| ID | Question | Why it matters |
|---|---|---|
| D-1 | Raise `requires-python` to 3.11 so `tomllib` can read Codex config, or write a small read-only extractor? | Decides how the native-switch fix is built |
| D-2 | Should a directory symlinked to a shared store be accepted, copied in, or still refused? | Containment model; blocks rows 1 and 5 |
| D-3 | Is a read-only lock reader allowed inside `doctor`, or does it need its own command? | Locked constraint 5 |
| D-4 | Is the target user the multi-agent power user, with Claude-only users left to the platform? | Sets what to cut and what to build first |
| D-5 | Widen scope to MCP and AGENTS.md (MON-Q2 in docs/27)? | Users name all three; needs an ADR |
| D-6 | Publish a public data report on popular skills (MON-Q3)? | Best-evidenced distribution lever; needs careful wording |
| D-7 | Make `/v2/` the default route after the list-payload decision? | Affects first paint and the classic UI's future |
| D-8 | Is usage analytics from transcripts acceptable as a new read-only surface? | Highest demand among large items; new surface |
| D-9 | Is a zh-CN interface wanted (MON-Q4)? | Reverses an explicit decision; weak but non-zero evidence |
| D-10 | Is the services-first year accepted (MON-Q1)? | Orders every product item above |

## 9. Method and limits

**[NOTE]** Four research passes on 2026-11-05 and 2026-11-06 supplied this document: GitHub issue mining (reaction-sorted and title-scoped), a community pass (Hacker News, YouTube, blogs), a feature matrix from competitor READMEs and docs, and a specification and security review. The earlier docs/26 and docs/27 supplied Reddit, X and monetization evidence and were not re-verified. Gaps: Reddit, X, Instagram and Chinese forums were not read in this pass; competitor claims were not run locally; thumbs-up counts were read at one moment; "coverage today" for skills-mgr comes from documentation and was not re-executed; several secondary sources are marked [?]. No number in this document is a forecast.

## 10. Addendum: Reddit, X and Chinese communities (2026-11-06, second pass)

**[NOTE] Channels.** Reddit was read through the maintainer's signed-in Chrome
profile via `opencli browser`, read-only (about 24 pages). X via `opencli
twitter search` (about 14 queries, mostly promotional results). V2EX public API
and search, Juejin, Zhihu and Tencent Security via Exa and Jina Reader, and the
Bilibili public search API. XiaoHongShu timed out and Instagram pages returned
no content, so both remain gaps. Counts are threads read, not platform totals.

**[SPEC] What this pass changes.**

1. **The user framing of the folder problem is "which copy does the agent load".**
   Eight threads (Reddit r/ClaudeCode 1ubdz8g, r/claudeskills 1xd3ql5, r/codex
   1x2wkid; V2EX t/1239048, t/1228460, t/1236972, t/1247023) describe several
   copies on disk with no way to tell which is stale or which is loaded. One
   V2EX user: five copies on disk, three stale, unknown which loads. This is
   exactly the `/v2/` "Copies differ" view plus `doctor --explain`; the gap is
   joining them into one answer per skill.
2. **Leaner skills deserves "strong", not "medium".** V2EX t/1200628 alone has
   56 replies arguing fewer skills choose better; Reddit r/ClaudeCode 1xl8klo
   blames skills for token burn. New detail: Codex prints that skill
   descriptions were shortened to fit its 2% budget, and users work around it
   with one router skill.
3. **Security demand is for re-checking, not only pre-install.** Nine threads,
   including Reddit r/codex 1w2e1wy (an injected "ignore all previous
   instructions" line in a copied `SKILL.md`), Juejin 7683443642279084047 and
   Tencent Zhuque Lab's scan of 50,000+ ClawHub skills. Users want a skill that
   was fine yesterday flagged if it changed. Users also ask for a clear
   yes/no; this document still advises evidence over a verdict label, and that
   tension is now an open question for the maintainer.
4. **Many users write their own skills and avoid third-party ones**
   (r/ClaudeAI 1xltysk, V2EX t/1200628). That shrinks the audience for
   install-centred features and enlarges it for authoring, linting and drift.
5. **Bundles that need hooks are a named fear** (V2EX t/1228460, t/1236972):
   installing a suite that also needs hooks, then removing it cleanly.
6. **Chinese-language users bring regional agents and generic sync.** Trae,
   CodeBuddy and WorkBuddy appear alongside Claude Code and Codex; sync through
   OneDrive, Dropbox or GitHub is common, with reported conflicts. Skill
   managers are a crowded V2EX genre: at least eight were posted Jan–Oct 2026.
7. **Recovery (row 16) found no direct demand** in these channels. Users ask
   "which copy is stale" and "delete cleanly", not "roll back". Recovery stays
   valuable as safety, but it is not a headline.

**[?] Unverified claims seen in this pass:** that Claude Code `/doctor` now
audits skills for stale rules (r/ClaudeAI 1v5mhhl), and that Claude Code 2.1.277
auto-loads AGENTS.md. Either would overlap this tool and should be checked
against primary release notes before planning around it.
