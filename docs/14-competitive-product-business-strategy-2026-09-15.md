# Competitive Product and Business Strategy — 2026-09-15

**Version 1.1.0**

**AI manifest**: Dated competitive analysis and product/business strategy for
Skills Manager. It compares the current repository with
`xingkongliang/skills-manager` at a recorded revision, separates evidence from
recommendations and hypotheses, and defines positioning, target customers,
packaging, monetization, go-to-market, metrics, risks, and decision gates. Read
with @docs/15-product-ux-delivery-plan-2026-09-15.md before prioritizing product
work. This document is planning, not proof that a proposed feature has shipped.

## Status and authority

**[SPEC]**

This document is the strategy baseline produced from the 2026-09-15 research and
refreshed on 2026-09-20. The original observation remains historical; the
refresh below is the current comparison snapshot.
The repository root `ROADMAP.md` remains the public delivery-status authority;
`task.md` remains the execution checklist; source and the owning technical docs
remain authoritative for current behavior.

Recommendations here do not approve a new CLI command, `Store` method, SQLite
schema change, dependency, hosted service, framework change, or non-loopback
bind. Those changes retain the approval boundaries in `AGENTS.md`.

## Executive decision

**[SPEC]**

Skills Manager should not compete as another broad desktop skill installer. Its
strongest position is:

> **The local-first control plane that tells developers and teams which AI-agent
> skills will load, whether those skills are valid and safe, how they differ,
> and how to distribute approved versions without losing control.**

The compared project is substantially ahead in consumer packaging, discovery,
deployment ergonomics, and visual information architecture. This project is
substantially ahead in validation depth, effective-resolution diagnostics,
recoverability, adversarial hardening, migration safety, and advisory quality
evaluation. The product plan should borrow the competitor's understandable
workflows while preserving this project's governance and trust moat.

The highest-leverage mental-model change identified in the original comparison
is now shipped: the UI leads with a logical library and reveals physical copies
on demand, with responsive foundations and onboarding around it. The current
highest-leverage work is task-oriented Overview/Install/Quality/Backups/Settings
information architecture and direct access to the existing evidence, review,
apply, snapshot, and recovery seams.

### 2026-09-20 comparison refresh

**[NOTE]**

The upstream comparison was refreshed against commit
[`6ae02e39d9efea0faf75e643b8205f97833a593d`](https://github.com/xingkongliang/skills-manager/commit/6ae02e39d9efea0faf75e643b8205f97833a593d),
observed on 2026-09-20. The competitor reports version `1.40.0`, 4,864 GitHub
stars, 416 forks, 195 issues, and 22 pull requests. These public counters are
volatile adoption signals, not measures of quality. The refreshed inventory is
60 Rust files / 42,640 lines, 63 frontend TypeScript/TSX/CSS files / 19,004
lines, 122 commands, 526 Rust tests, and a package manifest with 22 runtime and
15 development JavaScript dependencies.

The current product truth is materially better than the September baseline in
the user-facing layer: logical-library grouping, onboarding, tags/batches/
profiles, adapter and project observation, registry/provenance review, source
review/apply, backup review/apply, and redesigned responsive UI foundations are
shipped. Remaining gaps are task-oriented Overview/Install/Quality/Backups/
Settings information architecture; stronger visual agent/workspace identity;
unified task centers; source/update inbox UI; consumer installers and OS
integration; and human evidence. The last item remains an evidence gate, not a
feature claim.

### Architecture verdict

**[SPEC]**

Keep the filesystem-authoritative Python backend, loopback API, vendored Vue,
and no-build frontend as the canonical architecture. The existing
`desktop_launcher.py` Chromium app-mode window is the preferred zero-dependency
desktop experience. React is not the advantage to copy; Tauri packaging and OS
integration are the potential advantages. A Tauri/sidecar experiment is only a
future DEC-09 option if installer, tray, keychain, or signed-updater demand is
demonstrated. This refresh does not authorize a React/Rust rewrite.

## Research scope and evidence rules

**[NOTE]**

The comparison covered:

- the external repository at commit
  `b19706df9f993bfbe3b87d9a32a720f3e75506da` on 2026-09-15;
- its README, changelog, releases, package metadata, frontend and Tauri/Rust
  source, public website, GitHub repository metadata, and contributor surface;
- this repository's current working tree, README, public roadmap, product docs,
  CLI and REST surfaces, Python/Vue source, tests, release metadata, and rendered
  local web UI at desktop and 400 px mobile width;
- a point-in-time visual and behavior inspection of the local UI, including its
  default all-scope list and token-budget presentation.

GitHub popularity and issue counts are volatile observations, not quality
scores. Code and test counts are approximate inventory measurements, not
product-value metrics. Pricing below is a proposed experiment, not evidence of
willingness to pay.

## Point-in-time product snapshot

**[NOTE]**

| Dimension | `xingkongliang/skills-manager` | This project |
|---|---|---|
| Product shape | Cross-platform Tauri desktop application plus standalone CLI | Python CLI plus local loopback web UI |
| Public version observed | `1.40.0` (2026-09-20 refresh; `1.39.0` remains the 2026-09-15 historical observation) | Published distribution `skill-control-plane` `1.0.1` |
| License | MIT | MIT |
| Repository signal | 4,864 stars, 416 forks, 195 issues, 22 pull requests (2026-09-20; volatile, not quality) | 0 stars, 0 forks, 1 open issue in the public repository snapshot |
| Runtime stack | React 19, TypeScript, Vite, Tailwind, Tauri 2, Rust, SQLite | Python standard library backend/CLI, vendored Vue 3, SQLite rebuildable index, no frontend build step |
| Distribution | Homebrew, macOS DMG, Windows EXE/MSI, Linux AppImage/DEB/RPM, CLI binaries | PyPI package; browser-canonical UI; unbundled optional desktop launcher |
| Agent reach | 54 built-in agents plus custom tools/paths | Seven named agent filesystem scopes, generic agents scope, global and project-local discovery |
| Primary strength | Discovery, installation, cross-agent deployment, presets, desktop convenience | Validation, resolution explanation, safety, recovery, migrations, eval evidence, low-dependency operation |
| Primary gap | Limited first-party authoring/governance depth visible in the inspected product | Task-oriented Overview/Install/Quality/Backups/Settings IA, stronger agent/workspace identity, unified task centers, source/update inbox, consumer installers/OS integration, and human evidence |

The 2026-09-20 competitor inventory is 60 Rust files / 42,640 lines, 63
frontend TypeScript/TSX/CSS files / 19,004 lines, 122 commands, 526 Rust tests,
and 22 runtime + 15 development JavaScript dependencies. The 2026-09-15
inventory (59 Rust files / 42,294 lines; 62 frontend files / 18,894 lines; 521
Rust tests) remains historical. These figures describe implementation scale
only.

## Competitive product profiles

### External project: consumer desktop skill manager

**[NOTE]**

The external project organizes one central library across many AI tools. Its
important workflows include:

- install from local sources, Git repositories, archives, and skills.sh;
- search/browse a marketplace leaderboard;
- detect, reorder, and configure agents and custom tool paths;
- deploy skills by symlink or copy to global workspaces and explicit projects;
- represent one logical skill with per-agent badges;
- filter by tags, sources, untagged state, and saved presets;
- select many skills for batch operations;
- inspect upstream source, directory-wide diffs, and available updates;
- back up and synchronize through GitHub device flow or arbitrary Git remotes;
- resolve conflicts with keep-mine, use-remote, and keep-both choices;
- preserve undoable snapshots and an activity log;
- offer themes, text sizing, English and Chinese locales, tray controls, and
  application auto-update;
- install a management skill and expose its CLI so AI agents can operate the
  manager itself.

The navigation is task-oriented: Dashboard, Library, Install, Backup, Presets,
Global Workspaces, Projects, and Settings. Cards present logical skills with
deployment badges instead of leading with every filesystem instance.

Its changelog also demonstrates the operating cost of breadth: recent fixes
covered line-ending false positives, off-screen confirmation dialogs,
missing-source state, batch-selection correctness, private Git authentication,
and project deployment behavior. These are useful warnings for this roadmap:
every new adapter, update source, sync path, and responsive dialog creates a
continuing compatibility obligation.

### This project: local trust and governance control plane

**[NOTE]**

The current project already supplies a deeper integrity and authoring layer:

- filesystem source of truth with a rebuildable SQLite index;
- create, edit, live Markdown preview, templates, search, categories, and
  enable/disable flows;
- structural/spec validation, frontmatter and description quality checks,
  resource/link/layout findings, and bounded failure handling;
- scope-aware management for Claude Code, Codex, Cursor, OpenCode, Gemini,
  Command Code, the generic agents root, global data, and project-local roots;
- safe synchronization and cross-scope duplicate/divergence diagnosis;
- `doctor --explain` effective-resolution evidence without guessing undocumented
  precedence;
- token estimates, aggregate statistics, snapshots, history, trash, undo,
  restore, full backup, and guarded tar/ZIP migration;
- offline registry command preview with explicit trust confirmation;
- a file-based advisory eval harness that compares with-skill and without-skill
  results without changing validity;
- path, archive, multipart, origin/host, supply-chain, packaging, and
  cross-process mutation protections;
- stdlib-only operation, vendored frontend runtime, and a comprehensive
  contract/regression suite.

That is a credible foundation for a safety-sensitive control plane. The
2026-09-20 redesign fixes the logical-first and responsive foundations that the
original inspection found lacking. The historical dataset still matters as
motivation: 1,888 scope instances produced mostly repeated copies and a
4.7-million-token aggregate, and at 400 px the old scope chips/token panel could
consume the capped sidebar before a skill row was visible. Those figures are
historical observations, not a current UI claim or universal benchmark. The
remaining product issue is fragmented workflows and actions, not a hidden list.

## Capability comparison and response

**[SPEC]**

| Capability | Competitive read | Strategic response |
|---|---|---|
| Logical library | Competitor presents one skill with agent badges | Shipped as the local default; next improve agent identity and direct paths from logical cards to evidence and instances |
| Desktop installation | Competitor is materially stronger | Improve install/launch convenience incrementally; do not rewrite in Tauri to imitate it |
| Agent breadth | Competitor is broader | Build a declarative verified/experimental/custom adapter catalog before adding many hard-coded roots |
| Authoring | Current project is stronger | Make create/edit/preview/templates a visible differentiator |
| Validation and safety | Current project is stronger | Promote this to primary positioning and Quality navigation |
| Effective resolution | Current project has evidence-based diagnostics | Turn the explanation into understandable UI without persisting guessed state |
| Tags, presets, batches | Competitor remains stronger in ergonomics | Foundations are shipped; next add profile quick apply/preview and task-center access without implying automatic deployment |
| Projects/workspaces | Competitor is stronger in visual identity | Read-only adapter/project observation is shipped; next make agent/workspace status legible without guessing precedence |
| Source/update flow | Competitor is stronger in inbox ergonomics | Review/apply foundations are shipped; next compose a source/update inbox around provenance, diffs, and existing approval gates |
| Marketplace | Competitor is stronger in breadth | Registry browse/review foundations are shipped; next add trust-ranked access and validation, never popularity-as-trust |
| Backup/multi-device | Competitor is stronger in convenience | Local backup review/apply and recovery foundations are shipped; next add a Recovery center, not automatic multi-device sync |
| Evals/governance | Current project is stronger | Make Quality reports and policy evidence the path to Team revenue |
| Localization/accessibility | Competitor has broader settings | Responsive/accessibility foundations are shipped; next add text-size/system-theme settings, then i18n after IA stabilizes |
| Operational simplicity | Current project is stronger | Preserve stdlib, no-build, loopback, filesystem authority, and rebuildable-index constraints as product advantages |

## Ideas to adopt and avoid from the refresh

**[SPEC]**

Adopt selectively: a hybrid list/document library with an optional grid browse
mode; a useful Overview/dashboard; task-oriented navigation; visible agent and
workspace identity/status; preset/profile quick apply with an exact preview;
dedicated Install, Recovery, and Settings surfaces; and a source/update inbox.
Text-size controls and internationalization are later accessibility and reach
work, after the information architecture stabilizes.

Avoid: a fixed 1100px desktop assumption; icon or tag overload; popularity as a
trust proxy; a feature-parity chase; and any new source of truth. Every proposed
surface must reuse the filesystem-authoritative data and existing review/apply
seams unless a separately approved architecture decision says otherwise.

## Strategic positioning

**[SPEC]**

### Category

Use **AI Agent Skill Control Plane** as the category. “Skills manager” remains a
useful descriptive/search term, but by itself it positions the product beside a
larger desktop organizer where breadth and packaging dominate comparison.

### Recommended message

Primary headline:

> **Know exactly which skills every AI agent will load—and whether they are
> valid, current, safe, and approved.**

Supporting statement:

> Author once, validate deeply, explain precedence, deploy across agents, and
> recover every change from a local-first control plane.

### Differentiation pillars

1. **Truth** — show the logical skill, every physical instance, and the effective
   consumer result without inventing undocumented precedence.
2. **Trust** — validate content, provenance, update diffs, risk, and eval
   evidence before deployment.
3. **Control** — local files remain authoritative; users can review, synchronize,
   roll back, export, and rebuild without a service dependency.
4. **Governance** — profiles, approved versions, policy reports, audit history,
   and team distribution build on the same transparent primitives.

### What not to claim

- Do not call a sum of copied document bytes “tokens loaded by the model.”
- Do not claim a skill is safe merely because an archive signature or content
  hash verifies.
- Do not claim effective state where source-backed precedence is unavailable.
- Do not claim cross-device or team collaboration until conflict, identity,
  signing, and distribution semantics exist.
- Do not claim marketplace quality from popularity alone.

## Target customers and jobs

**[SPEC]**

### Segment 1 — multi-agent individual developers

Job: “Keep the same trusted skill library working across several coding agents
without manually copying files or wondering which version loads.”

Core value: logical library, deployment badges, effective-resolution view,
safe sync, updates, backup, and recovery.

### Segment 2 — skill authors and maintainers

Job: “Create a portable skill, validate its structure and usefulness, compare
iterations, and publish it with defensible quality evidence.”

Core value: authoring, spec lint, preview, fixtures/resources, eval comparisons,
provenance, diff, export, and CI-friendly reports.

### Segment 3 — platform and developer-experience teams

Job: “Give developers an approved skill set across tools, detect drift, and
prove what was reviewed without taking control of their local files.”

Core value: policies, profiles, private distribution, signed provenance,
review/publish workflow, audit reports, drift detection, CI gates, and role
controls.

### Beachhead

The first design-partner cohort should be small engineering teams already using
two or more agent products and maintaining internal skill repositories. They
feel both halves of the problem: consumer deployment friction and governance
risk. Broad consumer-marketplace users are useful for adoption but are less
likely to pay for the strongest differentiation.

## Product principles

**[SPEC]**

1. **Logical first, physical on demand.** Default views answer “what skills do I
   have?”; drill-down answers “where are the copies?”
2. **Read before write.** Preview diffs, targets, conflicts, trust, and rollback
   before a mutation.
3. **Explain uncertainty.** Use unknown, unsupported, unverified, or ambiguous
   rather than deriving a reassuring guess.
4. **Local operation must remain complete.** Paid services add coordination and
   convenience; they do not disable local CRUD, validation, backup, or recovery.
5. **Quality is evidence, not a badge.** Validation, risk checks, provenance,
   and evals remain individually inspectable.
6. **Adapter breadth must be maintainable.** Every consumer integration has a
   cited discovery contract, fixtures, status, and an owner/review date.
7. **Progressive disclosure beats expert-only density.** New users get a guided
   path; experts retain filesystem paths, hashes, diagnostics, and raw reports.

## Business model

**[SPEC]**

The open-source product should remain fully useful for local individual work.
Revenue should come from coordinated state and managed trust, not artificial
restrictions on files users already own.

### Community edition — free and MIT

Keep these capabilities free:

- local library, create/edit/search, templates, and preview;
- local agent discovery and deployment/sync;
- validation, risk findings, effective-resolution explanation, and advisory
  eval files;
- local history, snapshots, trash, import/export, and manual backup;
- offline registry preview and inspectable CLI/REST automation;
- all safety fixes and data-portability features.

This edition is the adoption engine, trust proof, and self-hostable escape hatch.

### Pro — individual convenience

**[?]**

Test **USD 8–12 per month or about USD 79 per year** only after at least one
service-grade benefit exists. Candidate benefits:

- encrypted managed multi-device synchronization or hosted private backup;
- monitored source/update notifications;
- longer managed history and easy device recovery;
- signed packaged application/standalone executable convenience;
- priority support and migration assistance.

An alternative one-time desktop-convenience license may fit users who reject
subscriptions. Test willingness to pay before selecting subscription-only
packaging.

### Team — governance and collaboration

**[?]**

Test **USD 15–25 per active user per month with a small team minimum** for:

- private organization registry and approved profiles;
- draft, review, publish, deprecate, and rollback workflows;
- signed provenance and policy enforcement;
- organization drift, audit, and adoption reports;
- GitHub/GitLab integration and CI policy gates;
- role-based access and shared eval evidence;
- managed update channels and support.

The user count, minimum, and whether authors or all recipients are billable must
be discovered in design-partner interviews. No value is selected by this plan.

### Enterprise — deployment assurance

**[?]**

Quote annual contracts for SSO/SCIM, self-hosted or air-gapped coordination,
retention controls, compliance evidence, SLA/support, custom policy packs,
custom consumer adapters, and migration. Enterprise work must not silently turn
the canonical local UI into a publicly bound multi-user server.

### Services — early revenue

Offer paid onboarding, skill-library audits, migration, policy design, internal
skill authoring, custom adapters, and enablement workshops before the hosted
product exists. Services should feed repeatable product requirements instead of
becoming an unrelated consultancy.

## Packaging and entitlement boundary

**[SPEC]**

| Layer | Free/local responsibility | Paid responsibility |
|---|---|---|
| Files and authoring | Always usable without an account | No exclusive file format |
| Validation and security | All local checks and fixes | Managed policy distribution and compliance reporting |
| Backup | Local archives and user-controlled Git remain free | Hosted encrypted storage, monitoring, retention, and recovery service |
| Distribution | Manual/local sync and portable exports | Private organization channels, approvals, rollout, and fleet drift |
| Evals | Local file contract and advisory scoring | Shared result history, policy aggregation, managed runners if separately approved |
| Updates | Local source inspection and manual preview | Monitored notifications, managed channels, staged team rollout |
| Support | Community docs/issues | Response-time commitments, migration, and custom integration |

Because both projects are MIT-licensed, defensibility comes from trusted hosted
coordination, integration quality, policy content, support, brand, and community;
it does not come from hiding a local Boolean entitlement in open source.

## Go-to-market plan

**[SPEC]**

### Product-led acquisition

- Publish a clear comparison page around “organize” versus “control and govern,”
  without disparaging the competitor.
- Replace feature-list screenshots with three proof stories: explain what loads,
  catch an unsafe/divergent skill, and roll back a controlled deployment.
- Provide a five-minute onboarding flow that detects installed agents and turns
  an existing directory into a logical library.
- Publish CI recipes for validation and advisory eval evidence.
- Create migration guides from manual dotfile copies and other skill managers.
- Use the `skills-mgr` CLI and a management skill as developer-native adoption
  channels once their exact security contract is approved.

### Design-partner motion

Recruit 5–10 teams meeting all of these criteria: more than one coding agent,
at least one internal skill repository, and a real review/compliance or drift
problem. Run structured interviews and a time-boxed pilot around one workflow:
approved profile → developer deployment → drift report → rollback.

The pilot outcome is learning, not vanity adoption. Record the buying role,
security objections, current workaround cost, must-have integrations, and the
event that creates urgency.

### Content and community

- “Which skill actually loads?” consumer-resolution guides backed by primary
  discovery sources.
- Skill quality and threat-model checklists.
- Reproducible examples of evals that show improvement and regressions.
- Open adapter catalog contributions with verification fixtures.
- Public roadmap and changelog entries that distinguish shipped, proposed, and
  rejected work.

## Success metrics and measurement

**[SPEC]**

No metric below has a current baseline. Establish baselines before setting a
numerical target. Because local-first operation and lack of telemetry are product
values, collect metrics through explicit opt-in diagnostics, privacy-preserving
event counts, user-exported reports, and interviews. Never collect skill bodies,
prompts, secrets, filesystem paths, or eval outputs by default.

### Product metrics

- **Activation:** a new user detects or imports a skill, validates it, and
  deploys it to at least one consumer.
- **Time to first truth:** elapsed time until the user can see one logical skill,
  its instances, and its effective/unknown consumer status.
- **Governed coverage:** proportion of observed logical skills with valid
  structure, known provenance, and no unresolved divergence.
- **Recovery confidence:** successful rollback/restore outcomes divided by
  attempted recovery operations in opted-in or test data.
- **Update safety:** previewed updates that complete without unexpected drift or
  require a rollback.
- **Retention proxy:** active managed projects or consumers per returning user,
  measured only with consent.

### Business metrics

- free-to-design-partner and free-to-paid conversion;
- number of teams with a recurring approved-profile workflow;
- annual recurring revenue and expansion/contraction;
- support and hosted-infrastructure cost per paid account;
- time to onboard a team and time to restore a failed device;
- sales cycle and reasons for loss;
- services work converted into reusable product capability.

### Quality guardrails

- zero filesystem-source-of-truth regressions;
- zero silent precedence guesses or unsigned-as-signed claims;
- no destructive mutation without preview/recovery where the workflow permits;
- current regression, smoke, documentation, complexity, packaging, and browser
  gates remain green before release;
- adapter claims have primary-source provenance and review dates.

## Strategic risks and mitigations

**[SPEC]**

| Risk | Why it matters | Mitigation |
|---|---|---|
| Feature-parity chase | A smaller project can spend years reproducing 54 adapters and desktop polish | Focus on logical-library UX plus trust/governance differentiation; use adapter data, not bespoke code |
| Product/category confusion | Users may see only another installer | Lead every surface with effective state, validation, provenance, and controlled deployment |
| Local-first versus recurring revenue | Users may reject accounts and subscriptions | Keep local product complete; charge for hosted coordination, monitoring, policy, and support |
| Marketplace supply-chain risk | Discovery increases exposure to malicious skills | Trust-ranked preview, provenance, content diff, explicit confirmation, quarantine, and rollback before broad browse |
| False quality confidence | A signature, validation pass, or eval score can be overinterpreted | Show each evidence type and limitation separately; never collapse to an unexplained green badge |
| Adapter maintenance burden | Consumer paths and precedence change independently | Verification fixtures, primary sources, statuses, review dates, graceful unknown state |
| Hosted scope creep | A local web server is not a secure multi-tenant SaaS | Build hosted coordination as a separately threat-modeled service/client architecture |
| Dirty-tree delivery risk | Large uncommitted batches make attribution and release evidence unreliable | Stabilize and checkpoint current work before starting feature implementation |
| Competitor momentum | Existing distribution and community shorten its feedback loop | Ship a narrow, differentiated onboarding story and recruit governance-focused design partners |

## Decisions made by this strategy

**[SPEC]**

1. Position around control, quality, and governance—not maximum adapter count.
2. Make a deduplicated logical library the default UX.
3. Keep physical instance/scoped diagnostics available as an expert drill-down.
4. Move token information into an explanatory Quality/Insights context and
   distinguish unique library size, deployed copies, and estimated active load.
5. Preserve the local-first, filesystem-authoritative, rebuildable-index,
   loopback, stdlib, vendored-Vue, and no-build constraints until separately
   approved.
6. Keep local core capabilities free; monetize hosted coordination, governance,
   assurance, and support.
7. Validate demand through team design partners before building a broad hosted
   platform.

## Decisions still required

**[?]**

| ID | Question | Evidence needed | Owner decision before |
|---|---|---|---|
| STRAT-Q1 | Is the first paid product Pro sync/backup or Team governance? | Interview urgency, pilot use, willingness-to-pay evidence | Hosted implementation |
| STRAT-Q2 | Subscription, annual-only, or optional one-time desktop convenience? | Pricing interviews and checkout/preorder experiment | Public price page |
| STRAT-Q3 | Which 3–5 consumer adapters form the verified support tier? | Usage interviews plus primary-source discovery stability | Adapter catalog launch |
| STRAT-Q4 | Can profiles/tags/provenance live in filesystem sidecars without creating a second truth source? | ADR and import/export/rebuild prototype | Persistent metadata implementation |
| STRAT-Q5 | Should organization distribution use signed portable bundles, a hosted registry, or both? | ADR-004 decisions, threat model, pilot workflow | Team product build |
| STRAT-Q6 | What privacy-preserving product analytics, if any, will users accept? | Explicit consent research and data inventory | Telemetry addition |
| STRAT-Q7 | Does managed evaluation require provider execution, or only aggregation of user-produced results? | Design-partner security and workflow evidence | Eval service design |

## Explicit non-goals for the next planning horizon

**[SPEC]**

- a Tauri/React rewrite to match the competitor's stack;
- raw parity with all 54 competitor adapters;
- a popularity-first marketplace without provenance and trust controls;
- AI recommendations mined from private shell/prompt history before consent,
  quality, and threat-model questions are settled;
- converting the current loopback web server into a public multi-user server;
- making an account mandatory for local authoring, validation, backup, or
  recovery;
- persisting derived effective state in the current SQLite schema;
- treating telemetry, stars, downloads, or code volume as proof of user value.

## Sources and reproducibility

**[NOTE]**

External sources inspected:

- [competitor repository](https://github.com/xingkongliang/skills-manager)
- [2026-09-20 competitor commit](https://github.com/xingkongliang/skills-manager/commit/6ae02e39d9efea0faf75e643b8205f97833a593d)
- [historical 2026-09-15 competitor tree](https://github.com/xingkongliang/skills-manager/tree/b19706df9f993bfbe3b87d9a32a720f3e75506da)
- [competitor README at refresh](https://github.com/xingkongliang/skills-manager/blob/6ae02e39d9efea0faf75e643b8205f97833a593d/README.md)
- [competitor package manifest](https://github.com/xingkongliang/skills-manager/blob/6ae02e39d9efea0faf75e643b8205f97833a593d/package.json)
- [competitor Rust manifest](https://github.com/xingkongliang/skills-manager/blob/6ae02e39d9efea0faf75e643b8205f97833a593d/src-tauri/Cargo.toml)
- [competitor Tauri configuration](https://github.com/xingkongliang/skills-manager/blob/6ae02e39d9efea0faf75e643b8205f97833a593d/src-tauri/tauri.conf.json)
- [competitor releases](https://github.com/xingkongliang/skills-manager/releases)
- [competitor website](https://skillsmanager.dev/)
- [Tauri sidecar documentation](https://v2.tauri.app/develop/sidecar/)
- [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/)

Local source anchors:

- root `README.md` for the current product promise and installation;
- root `ROADMAP.md` for public delivery status;
- @docs/03-cli-surface.md and @docs/08-web-ui.md for shipped surfaces;
- @docs/12-agent-root-discovery-2026-09-08.md and
  @docs/ADR-002-root-consumer-effective-state.md for discovery and resolution;
- @docs/ADR-003-registry-bridge-and-eval-harness.md for trust-preview and eval
  boundaries;
- @docs/ADR-004-team-sharing-signed-bundles.md for team-distribution decisions;
- @docs/13-audit-remediation-status-2026-09-11.md for remaining audited risk.

Any future refresh must record the competitor revision, observation date, local
commit/working-tree state, and measurement method so changes are comparable.
