# Product, UX, and Delivery Plan — 2026-09-15

**Version 1.2.0**

**AI manifest**: Implementation-ready planning companion to
@docs/14-competitive-product-business-strategy-2026-09-15.md. It translates
the research into a target information architecture, user journeys, phased
workstreams, acceptance criteria, dependencies, verification, release gates,
experiments, and approval checkpoints. It does not mark proposed work shipped
and does not supersede `ROADMAP.md`, `task.md`, an owning ADR, or source.

## Status and usage

**[SPEC]**

Status: **mixed-status dated delivery plan**. Foundation status is authoritative
only where `task.md` and source corroborate it; comparison-derived follow-ons
remain proposed. Use this plan to cut small, approved milestones; do not
implement it as one batch. For each accepted workstream:

1. confirm the approval classification and decision prerequisites;
2. add a bounded milestone to `task.md`;
3. write red-first contracts for observable behavior;
4. implement through existing surfaces where possible;
5. update owning docs and @docs/06-progress-log.md;
6. run the repository's current verification ladder before completion.

The current worktree contained extensive pre-existing modifications during this
planning pass. This plan itself makes documentation-only changes; current
implementation status is reconciled below rather than inferred from the plan.

### 2026-09-21 Overview slice

**[NOTE]** The Overview row in the target information architecture is now
shipped as a frontend-derived operator surface. It opens by default,
shows observed logical/instance health signals and recent history, and routes
to existing Library, Install, Doctor, and Trash workflows. The first-run state
offers Create, Add folder, Import, and health-check actions. The Library rail
label is now Library while Profiles, Workspaces, and Trash / Recovery remain
available. At this overview milestone, standalone Quality, Backups, Settings,
hybrid Library, and provenance workflows were still proposed task-center work.
The subsequent 2026-09-21 frontend slices shipped Quality, Install/Recovery,
Settings, hybrid Library, and bounded provenance presentation over those seams.
Implementation-agent visual inspection and stateful CDP
automation are complete in
`.specs/evidence/ui-overview-2026-09-21-final/`, with six viewport captures and
`scenarios/` captures for empty, search, form validation, error/success
feedback, divergent detail, destructive confirmation, disabled filtering,
recovery, and dark theme. The probes reported zero console/runtime errors,
failed requests, or page overflow. Human participant/usability and external
communication approval remain open and are not inferred from local evidence.

The acceptance pass corrected union counting for malformed or unaddressable
observations, honest enabled/parsed/addressable active counts, focus-preserving
global search routing, settled readiness and load-error states, form error
associations with first-invalid focus, exclusive detail rendering, race-safe
attention deep links, single-owner modal focus restoration, and stale-detail
clearing for the disabled filter.

### 2026-09-20 status reconciliation

**[NOTE]**

The task records show DEL-00 through DEL-09 foundations shipped, including the
responsive redesign, logical Library, onboarding, organization, adapter/project
observation, source review/apply, registry review/commit, and backup review/apply
seams. DEL-10 is shipped only as a narrow offline integrity/policy foundation;
it is not a team workflow. DEL-11 local evidence is shipped as automated capture
and candidate packets, while external communication review and human usability
evidence remain open. No plan item below should be read as implementation proof
without matching task/source evidence.

## Planning vocabulary and approval classes

**[SPEC]**

| Label | Meaning |
|---|---|
| `DERIVED` | Read-only computation or frontend presentation over current data; no new source of truth |
| `EXISTING` | Uses an existing CLI, REST, or `Store` surface without changing its contract |
| `ASK-CLI` | Adds or materially changes a CLI command/flag; maintainer approval required |
| `ASK-STORE` | Adds a public `Store` method; maintainer approval required |
| `ASK-SCHEMA` | Changes SQLite schema or `SCHEMA_VERSION`; maintainer approval required and disfavored |
| `ASK-CONSTRAINT` | Changes stdlib/no-build/Vue/loopback/filesystem-source-of-truth constraints; maintainer approval required |
| `ADR` | Requires a recorded architecture/product/security decision before implementation |
| `SERVICE` | Requires a separately designed hosted or external coordination system; never infer from local-web authorization |

A workstream can carry several labels. Approval applies before code, not after a
prototype has silently established a public contract.

## Product outcome

**[SPEC]**

The planned product should let a new user answer five questions in order:

1. **What skills do I have?** — a deduplicated logical library.
2. **Where are they deployed?** — consumer and project badges with instance
   details.
3. **What will actually load?** — cited effective state or an honest unknown.
4. **Can I trust this version?** — validation, risk, source, diff, and eval
   evidence.
5. **Can I change it safely?** — preview, controlled deployment, conflict
   handling, snapshots, and rollback.

The shortest successful first-run journey is:

```text
Launch
  -> detect roots and consumers
  -> group physical copies into logical skills
  -> review health/divergence summary
  -> select one skill
  -> validate and explain its consumer state
  -> preview deployment
  -> deploy with recovery available
```

## Target information architecture

**[SPEC]**

| Navigation | User question | Primary content | Existing foundation |
|---|---|---|---|
| Overview | Is my setup healthy and what needs attention? | onboarding/resume, consumers, divergent/invalid/unverified counts, recent recovery | scopes, stats, doctor, history |
| Library | What skills do I own or observe? | logical skills, filters, badges, authoring, instance drill-down | list/search/create/edit/sync |
| Workspaces | What is deployed to this agent or project? | consumer/project matrix, effective state, drift, deploy preview | scopes, project discovery, doctor explain |
| Install | Where can I safely obtain or update a skill? | local/archive/Git/registry source, provenance, trust and staged preview | import/add/install preview |
| Quality | Is this skill valid, safe, useful, and appropriately sized? | validation, risk, diffs, provenance, token views, eval evidence | validate, insights, tokens, evals |
| Backups | Can I recover or move my state? | snapshots, trash, exports, restore, future remote backup | history/trash/export/backup/restore |
| Settings | How does this installation behave? | roots, consumers, appearance, accessibility, future update/privacy settings | scope info, theme |

On narrow screens, navigation becomes a top-level screen selector or bottom
navigation. It must not leave the list and detail panes squeezed into one
scrolling column. Library list and skill detail are separate mobile screens,
with an explicit Back action that preserves filters and scroll position.

## Target conceptual model

**[SPEC]**

This is a presentation/domain model, not approval to add database tables. It
extends the vocabulary in @docs/ADR-002-root-consumer-effective-state.md.

| Concept | Definition | Persistence rule |
|---|---|---|
| Logical skill | Same canonical skill identity grouped across physical roots | Derive from observed instances initially |
| Skill instance | One active/disabled/malformed document in one resolved root | Filesystem observation; never becomes authority |
| Deployment | Relationship between a logical skill instance and consumer/project target | Derive from root bindings until an ADR approves more |
| Effective result | Winning, ambiguous, also-loaded, skipped, or unknown instance for consumer/project/name | Read-time only; never persist guessed state |
| Source record | Where an instance came from and the observed source revision/hash | Filesystem sidecar only after ADR; otherwise observation/report |
| Profile | Named desired set of logical skills and target consumers/projects | New persistent concept; requires ADR and import/export contract |
| Policy | Reviewable rules for validation, provenance, risk, versions, or deployment | File-based candidate; Team design decision required |
| Review evidence | Validation, risk, diff, eval, reviewer, and timestamp attached to a content digest | Portable artifact/sidecar candidate; not SQLite authority |

Initial grouping should use the existing canonical skill name and resolved-root
deduplication. Same-name instances with unequal content must appear as one
logical row with a prominent **divergent** status; grouping must never imply
that their content is equal.

## UX behavior specification

### Overview

**[SPEC]**

The empty/new state starts with a guided checklist:

1. detect available consumer roots;
2. scan skills;
3. review duplicates, divergence, invalid files, and unknown precedence;
4. choose an existing library or create a first skill;
5. preview deployment to one target.

Returning users see action-oriented findings, not raw aggregate counts. Each
finding links to a filtered Library, Workspace, or Quality view. “Everything is
healthy” is permitted only when the exact checks behind it are listed.

### Library

**[SPEC]**

Default list unit: one logical skill. Each row/card includes:

- name and short description;
- validation state;
- active/disabled/divergent/unknown indicators;
- agent/project deployment badges;
- provenance state (`local`, source known, source missing, unverified);
- update state only when source comparison is available;
- most relevant next action.

Opening a logical skill reveals tabs or sections for Content, Instances,
Quality, Source, and History. Instance rows expose the resolved scope label,
path, content equality/divergence, enabled state, effective role, and safe
actions. The user can switch to an expert **Instances** view, but the application
must remember that choice rather than making it the first-run default.

Filters should eventually include consumer, project, validation state, source,
tag, enabled state, divergence, update availability, and untagged state. Filter
chips must show a visible clear-all action and persist only deliberate user
choices.

### Workspaces

**[SPEC]**

Use two levels: Consumers and Projects. A workspace detail shows desired versus
observed deployments, known precedence, ambiguous/unknown results, drift, and a
previewable action plan. It must cite the discovery evidence used by
`doctor --explain`; unsupported consumers retain `undocumented-precedence`.

Do not imply that a root and a consumer are the same entity. One resolved root
can serve multiple compatibility scope ids, and one consumer can inspect several
roots in precedence order.

### Install and updates

**[SPEC]**

Every install/update follows this state sequence:

```text
source entered
  -> source normalized
  -> trust/provenance displayed
  -> contents staged or command previewed
  -> validation/risk/diff shown
  -> targets selected
  -> mutation confirmed
  -> result and rollback path shown
```

An update button is unavailable when the source is missing, cannot be
authenticated, or has no comparable upstream reference. Line-ending-only changes
should be normalized for display while raw-byte changes remain inspectable.

### Quality and token semantics

**[SPEC]**

Never collapse evidence into one unexplained score. Quality shows independent
panels for:

- specification validity and warnings;
- structural/layout and link findings;
- risk scan findings;
- provenance and content digest;
- local/upstream or instance-to-instance diff;
- advisory eval results and with/without delta;
- size/token estimates.

The shipped Quality center implements the bounded subset currently evidenced by
the REST payloads: observed specification/addressability state, physical-copy
state and divergence, provenance fields when present, and content/token
estimates. Risk, eval/usefulness, trust, and effective-load signals are shown
as unavailable when the current APIs do not provide them; no verdict is
inferred and no single score is rendered.

Replace the current ambiguous aggregate token presentation with four named
measurements:

1. **Unique library text** — deduplicated content bytes/token estimate.
2. **Deployed disk copies** — count and storage estimate across roots.
3. **Selected consumer candidates** — documents the chosen consumer may inspect,
   based on cited discovery.
4. **Estimated effective load** — only where precedence/load behavior is known;
   otherwise show unavailable/unknown.

No token estimate should imply exact model tokenizer behavior when the fallback
estimator is in use.

### Responsive and accessibility behavior

**[SPEC]**

- At 320–400 px, the Library screen must show a skill row or a true empty state
  without scope chips or metrics consuming the entire list region.
- List and detail are separate narrow-screen routes/states; focus moves to the
  detail heading and returns to the invoking row.
- Dialogs fit within the visual viewport, keep their title/actions reachable,
  and scroll their body rather than the whole page.
- All actions are keyboard reachable with visible focus; icon-only actions have
  names; status is not communicated by color alone.
- Reduced-motion behavior remains honored; text zoom does not hide actions.
- Loading, empty, permission-denied, malformed, partial-failure, and offline
  states have explicit copy and recovery actions.

## Delivery overview

**[SPEC]**

```text
DEL-00 Stabilize current tree
  -> DEL-01 Baseline UX/performance evidence
    -> DEL-02 Logical Library + target navigation
      -> DEL-03 Responsive shell + progressive loading
        -> DEL-04 First-run onboarding
          -> DEL-05 Organization: tags, selection, profiles
            -> DEL-06 Workspaces/projects + adapter catalog
              -> DEL-07 Provenance and update preview
                -> DEL-08 Trust-first discovery
                  -> DEL-09 Backup/sync alpha
                    -> DEL-10 Team governance pilot

DEL-02 -> DEL-11 Positioning, docs, screenshots, distribution improvements
DEL-07 -> DEL-10
DEL-05 -> DEL-10
```

DEL-11 can progress alongside product work after the logical-library language is
stable. DEL-09 and DEL-10 require separate security/service decisions and are
not implied by the local implementation phases.

## Phase 0 — stabilize and establish evidence (days 0–14)

### DEL-00 — Current-tree release checkpoint

**[SPEC]**

Priority: blocking. Labels: `EXISTING`.

Scope:

- identify ownership of every current uncommitted batch;
- finish, split, or non-destructively checkpoint work without overwriting other
  sessions;
- rerun the full verification ladder on the actual candidate tree;
- record release state and avoid mixing strategy implementation into the
  existing remediation batch.

Acceptance criteria:

- each modified/untracked file has an understood owner/purpose;
- no concurrent session is writing the same files during a batch;
- current tests, smokes, docs, complexity, package-data behavior, frontend
  syntax, CLI help, and diff checks have recorded results;
- any failure is attributed and resolved or explicitly blocks the next phase;
- a recoverable checkpoint exists before UI restructuring.

### DEL-01 — Product baseline and research harness

**[SPEC]**

Priority: must. Labels: `DERIVED`, `EXISTING`.

Scope:

- codify benchmark fixtures for empty, small, divergent, malformed, and about
  2,000-instance libraries without using private user content;
- record number/timing of startup REST calls and scans;
- capture 320/400/640/900/1280 px states with the existing browser harness;
- run five task-based usability sessions across novice and expert users;
- define consent-safe measurement for activation and errors.

Acceptance criteria:

- baseline captures time to first visible skill row, time to interactive, scan
  count, API failure behavior, overflow, focus order, and mobile reachability;
- fixtures include identical copies and same-name divergent content;
- screenshots and results record environment/date and are reproducible;
- no telemetry or user-content collection is introduced by the baseline;
- target values are set only after measurement, with rationale.

### DEL-02 — Logical Library and navigation foundation

**[SPEC]**

Priority: must. Labels: `DERIVED`, `EXISTING` initially.

Scope:

- group existing physical rows by canonical name and resolved-root identity;
- expose equality/divergence and per-consumer badges;
- introduce the target navigation shell using existing endpoints;
- preserve an expert Instances view and direct scope selection;
- move token totals from the list choke point into Quality/Overview.

Acceptance criteria:

- identical same-name copies render as one logical row with N instance badges;
- divergent same-name copies render as one row with an unmistakable divergence
  action and never merge content;
- a physical root exposed by aliases is counted once in aggregate grouping;
- active, disabled, malformed, and unaddressable copies remain distinguishable;
- URLs/local UI state can reopen a logical skill and selected instance;
- create/edit/delete/sync/restore behavior still targets an explicit physical
  instance and retains existing confirmations/recovery;
- default first launch is Library or Overview, not raw all-scope instances;
- existing CLI/REST contracts remain compatible in the first slice.

Verification:

- pure grouping tests in `domain.js` or the smallest existing derived-data seam;
- Python contract fixtures for aggregate rows and alias roots;
- browser-harness checks for list, divergent drill-down, actions, focus, and all
  five viewports;
- Store/Web smokes because existing mutations are exercised, even if their
  backend code is unchanged.

### DEL-03 — Responsive shell and progressive loading

**[SPEC]**

Priority: must. Labels: `DERIVED`, `EXISTING`.

Scope:

- implement distinct narrow-screen list/detail states;
- collapse or move filter/scope controls behind a compact control at small
  widths;
- render the first useful rows without waiting for every secondary statistic;
- eliminate duplicate aggregate scans where existing endpoint composition
  permits;
- handle disconnects and partial failures without noisy raw exceptions.

Acceptance criteria:

- 320 and 400 px screens expose content immediately and never trap the list
  below a capped sidebar;
- Back restores filter, selection, focus, and scroll position;
- no dialog title or primary/secondary action is off-screen at tested widths or
  200% text zoom;
- loading skeleton/status describes what is pending and does not falsely report
  zero skills;
- a failed secondary stats request does not blank a successfully loaded library;
- startup performs no redundant full-root scan identified by DEL-01;
- server-side disconnect errors are cleanly bounded in the tested client-abort
  path.

### DEL-04 — First-run onboarding

**[SPEC]**

Priority: must. Labels: `DERIVED`, `EXISTING`; `ADR` if persistent onboarding
state or new roots are introduced.

Scope:

- detect current supported roots through existing scope information;
- explain filesystem-source-of-truth and local-only operation;
- let the user scan/import, validate, and preview a first deployment;
- offer skip and restart without blocking expert access.

Acceptance criteria:

- a user with existing roots reaches a logical library without entering a path;
- a user with no skills can create or safely import one;
- deployment targets and mutation consequences are explicit;
- errors link to doctor/permissions/help rather than raw traceback text;
- onboarding never uploads data or implies an account is necessary;
- completion can be derived or stored outside skill truth only after its storage
  decision is documented.

## Phase 1 — organize, deploy, and update (days 15–90)

### DEL-05 — Tags, multi-select, batch plans, and profiles

**[SPEC]**

Priority: should. Labels: `ADR`, likely `ASK-STORE`; `ASK-SCHEMA` must be avoided
unless explicitly approved.

Design before implementation:

- distinguish **template** (authoring starter) from **profile** (desired set of
  existing skills and targets);
- decide whether tags/profiles are portable filesystem sidecars, a dedicated
  config tree, or derived from skill metadata;
- specify import/export, rename, delete, disabled, missing, conflict, and
  rebuild behavior;
- define a batch plan as previewable independent operations with partial/atomic
  semantics stated per action.

Acceptance criteria:

- users can filter by tags/untagged and apply tag changes to a selection;
- select-all is scoped to the visible filter and reports the exact target count;
- batch enable/disable/sync/remove never silently widens beyond the preview;
- destructive batches retain per-item recovery and a useful partial-failure
  report;
- a profile can preview desired versus observed deployment without writing;
- missing or divergent profile members are explicit;
- metadata survives full export/import and filesystem-index rebuild according to
  the approved ADR;
- template behavior remains unchanged.

### DEL-06 — Workspaces, projects, and adapter catalog

**[SPEC]**

Priority: should. Labels: `ADR`, potentially `ASK-STORE`, `ASK-CLI`.

Scope:

- present Consumers and Projects using ADR-002 vocabulary;
- create a declarative adapter record with id, label, candidate roots,
  precedence evidence, recursion, reload guidance, platform support, status, and
  last verification date;
- assign adapters to **verified**, **experimental**, or **custom** tiers;
- support explicit project roots only after containment, precedence, and
  lifecycle rules are approved.

Acceptance criteria:

- every verified adapter cites a primary discovery source and has hermetic path
  and precedence fixtures;
- undocumented precedence remains visible as unknown;
- aliases to one resolved root do not duplicate writes or counts;
- a custom root is validated, permission-checked, reversible, and never assumed
  to belong to every consumer;
- project removal from the manager never deletes the project or its skills;
- deployment preview identifies copy/symlink strategy and exact filesystem
  targets;
- platform-specific unavailable roots degrade cleanly.

### DEL-07 — Provenance, source lock, diff, and update preview

**[SPEC]**

Priority: should. Labels: `ADR`, likely `ASK-STORE`; `SERVICE` only for monitored
updates.

Scope:

- define source identity for local path, Git remote/revision, archive digest, and
  registry reference;
- observe/store content digest and last compared source revision;
- show whole-directory diff, not only `SKILL.md`;
- stage candidate updates outside managed roots;
- validate, risk-scan, diff, and require explicit target confirmation;
- snapshot before commit and show rollback.

Acceptance criteria:

- provenance state distinguishes known/verified, known/unverified, local-only,
  missing, changed, and inaccessible;
- content is never marked current from a source URL alone;
- source credentials never enter exports, logs, skill files, or the rebuildable
  index;
- a candidate update cannot mutate live skill files before review;
- symlink and archive members retain existing containment/budget protections;
- CRLF/LF-only changes are explained without hiding raw content changes;
- stale/missing source disables one-click update and offers relink/inspect;
- successful update creates a recoverable snapshot and records source/content
  digests in the approved filesystem-owned format.

### DEL-08 — Trust-first discovery and install

**[SPEC]**

Priority: should after DEL-07. Labels: `ADR`, `SERVICE`, possibly `ASK-STORE` and
`ASK-CLI`.

Scope:

- extend the shipped offline registry preview only after authentication,
  caching, integrity, and failure behavior are designed;
- rank/filter on compatibility and trust evidence before popularity;
- stage and inspect content before deployment;
- preserve manual Git/path/archive installation.

Acceptance criteria:

- search result cards show source owner, immutable revision/digest when
  available, license, last update, compatibility, and audit links;
- popularity is labeled as popularity, never safety;
- private-source credentials use OS/user-approved secure storage outside data
  exports;
- cached metadata/content has bounded size, expiry, integrity, and offline state;
- content inspection, validation, risk, and target preview happen before any
  install command executes;
- command invocation remains list-form/shell-free and retains explicit trust;
- every network and partial-download failure is recoverable and non-mutating.

## Phase 2 — paid coordination and governance (months 3–12)

### DEL-09 — Git/managed backup and multi-device synchronization alpha

**[NOTE]**

Priority: validate before build. Labels: `ADR`, `SERVICE` for hosted storage;
possibly `ASK-STORE`/`ASK-CLI`.

Required design:

- user-controlled Git remote versus managed encrypted storage;
- device identity, credential storage, content encryption, retention, and
  deletion;
- skill-aware three-way conflict semantics;
- keep-mine/use-remote/keep-both behavior for directories and metadata;
- offline edits, force-push, renamed/deleted skills, and interrupted sync;
- recovery snapshot boundaries.

Alpha acceptance criteria:

- dry-run reports exact local, remote, and conflicting changes;
- no credential or plaintext secret appears in logs/exports;
- concurrent edits never silently overwrite either version;
- keep-both produces valid canonical names and preserves provenance;
- an interrupted operation leaves the local filesystem valid and retryable;
- local archive and manual Git backup stay functional without payment;
- destructive remote deletion has an explicit, tested recovery/retention path.

### DEL-10 — Team governance pilot

**[?]**

Priority: design-partner gated. Labels: `ADR`, `SERVICE`, likely new service APIs.
ADR-004 §6 is resolved as HMAC/shared-secret integrity, file-only offline
distribution, and content-only signed metadata; archive/team-governance
implementation remains separate and unshipped.

Pilot workflow:

```text
author draft
  -> local validation/risk/eval evidence
  -> review content digest and diff
  -> approve/sign release
  -> publish to private channel/profile
  -> developer previews and deploys
  -> organization observes drift
  -> rollback/deprecate when needed
```

Pilot acceptance criteria:

- review attaches to an immutable content digest;
- signature wording matches its real identity guarantee;
- policy failures show rule, evidence, owner, and override procedure;
- audit events have actor/source/time/digest while excluding skill bodies and
  secrets;
- developers retain local inspect/export/recovery capability;
- role boundaries cover author, reviewer, publisher, and administrator;
- revoked/deprecated releases remain explainable and recoverable;
- offline/air-gapped requirements are documented before enterprise promises;
- hosted architecture is separate from the loopback local server.

### DEL-11 — Positioning, distribution, and adoption

**[SPEC]**

Priority: parallel after DEL-02. Labels: `EXISTING`; `ASK-CONSTRAINT` for any
packaged-runtime change.

Scope:

- adopt the control-plane category and recommended headline;
- publish current screenshots and short proof-oriented demonstrations;
- document migration from manual roots and competitor-style libraries;
- make PyPI install, launch, and upgrade paths obvious;
- evaluate signed standalone binaries/desktop packaging without changing the
  canonical architecture by default;
- publish privacy, threat-model, and local-data explanations;
- recruit design partners for DEL-10.

Acceptance criteria:

- landing content explains the product in one sentence and differentiates it
  through truth/trust/control/governance;
- all screenshots represent a current build and include logical Library,
  effective state, Quality, and rollback;
- installation reaches the UI with one documented command after Python/package
  setup;
- platform/package claims are verified in CI before publication;
- no installer silently binds publicly, installs credentials, or adds an update
  daemon;
- comparison content uses dated, sourced, respectful claims;
- a design-partner brief defines cohort, pilot workflow, data handling, success,
  and exit conditions.

## Comparison-derived follow-on backlog

**[SPEC]**

These are proposed slices after the 2026-09-20 comparison refresh. Approval
labels describe the likely boundary; none is shipped by this document.

| Priority | Follow-on | User outcome | Reuse / approval | Acceptance signal |
|---|---|---|---|---|
| Now | Overview/dashboard | See invalid, divergent, pending, and recent work immediately | Frontend-only composition over existing stats/doctor/history; `DERIVED` | A fixture with mixed states produces actionable cards that deep-link to existing surfaces |
| Now | Task-oriented navigation | Find Library, Install, Quality, Recovery, and Settings by job | Frontend-only shell/route presentation; `DERIVED` | Keyboard and mobile navigation expose each task without changing API contracts |
| Now | Hybrid Library grid/list | Browse visually or inspect a precise document view | Frontend-only view mode over logical groups; `DERIVED` | List remains default, grid is optional, and both preserve instance drill-down |
| Now | Agent/workspace identity | Understand where a skill is active, disabled, or observed | Existing scopes/workspaces payloads; `DERIVED` | Each logical card names agent/workspace state without claiming undocumented precedence |
| Next | Profile quick apply/preview | Preview an exact set before applying it | Existing profile and batch preview/apply seams; `EXISTING` | Preview shows targets, diffs, and recovery before any mutation |
| Shipped | Quality evidence center | Inspect independent validity, physical state, provenance, and size evidence | Existing skill/scopes/stats seams; frontend-only | Search and exact drill-down preserve evidence boundaries and label unavailable signals |
| Shipped | Install and update center | Review source, provenance, and pending updates in one task center | Existing registry/source-lock review/apply; frontend-only | No network commit occurs without the current review/trust gates |
| Shipped | Recovery center | Review backups, trash, snapshots, and restore choices together | Existing backup/trash/history/source-lock seams; frontend-only | A recovery fixture can restore or explain every listed artifact without a new truth source |
| Shipped | Settings and accessibility | Change text size and system-theme behavior predictably | Frontend-only preferences; `DERIVED` | Text-size modes and theme preference remain usable at all harness widths |
| Shipped | Command palette | Reach existing actions without hunting through menus | Frontend-only action index; `DERIVED` | Keyboard search exposes only available, permission-safe actions |
| Shipped | Regional formatting foundation | Read counts, sizes, and timestamps in a familiar regional convention | Frontend-only `Intl` formatting preference; `DERIVED` | Settings persists system/en-US/en-GB/en-IN formats, keeps English copy explicit, and remains usable at all harness widths |
| Later | Internationalization | Use the core workflows in additional locales | Frontend-only resource layer after IA stabilizes; `DERIVED` initially | English remains complete and locale expansion has no clipped labels |
| Evidence-gated | Optional packaged desktop experiment | Evaluate installer/tray/keychain/updater value | DEC-09; `ASK-CONSTRAINT`/`ADR` if packaging changes locked runtime assumptions | Design-partner evidence justifies a bounded Tauri/sidecar spike before any packaging rewrite |

### Recommended sequence

**[SPEC]**

1. **A — Shell, dashboard, and navigation:** establish the task-oriented
   Overview and the Library/Install/Quality/Backups/Settings information scent.
2. **B — Library and agent identity:** add optional grid browsing and make
   agent/workspace status legible while preserving logical-first grouping.
3. **C — Task centers:** compose profile preview/apply, Install/update inbox,
   and Recovery around existing review, snapshot, and recovery contracts.
4. **D — Accessibility and localization:** add text-size/system-theme settings
   and command palette polish; i18n follows once IA and labels are stable.
5. **E — Packaging experiment:** only after evidence and DEC-09 approval,
   evaluate an optional packaged desktop path; do not rewrite the canonical app.

## Historical backlog priority matrix

**[SPEC]**

The matrix below is retained as the dated 2026-09-15 sequencing record; the
current proposed backlog and sequence are authoritative for post-refresh work.

| Priority | Work | Why now | Start gate |
|---|---|---|---|
| P0 | DEL-00 current-tree checkpoint | Delivery evidence is unreliable until concurrent/dirty work is controlled | Ownership and current-tree verification |
| P0 | DEL-01 baseline | Prevents design by anecdote and catches mobile/performance regression | Reproducible fixtures |
| P0 | DEL-02 logical Library | Corrects the core mental model and differentiates the product | No new persistence required for first slice |
| P0 | DEL-03 responsive/loading | Current 400 px flow can hide the actual list | DEL-01 baseline and DEL-02 state design |
| P0 | DEL-04 onboarding | Converts deep capability into an understandable first success | Stable navigation and Library |
| P1 | DEL-05 tags/batches/profiles | Necessary for scale and team workflow | Metadata/profile ADR and approval |
| P1 | DEL-06 projects/adapters | Makes multi-agent deployment coherent | ADR-002-compatible model and primary evidence |
| P1 | DEL-07 provenance/updates | Adds recurring individual value and trust moat | Source-record ADR and safe staging design |
| P1 | DEL-08 discovery | Improves acquisition only when trust controls exist | DEL-07 plus network/security decision |
| P2 | DEL-09 multi-device sync | Candidate Pro value | Demand and conflict/security design |
| P2 | DEL-10 team governance | Primary recurring-revenue thesis | Design partners plus a separate service/governance decision; ADR-004 §6 policy is resolved |
| Parallel | DEL-11 positioning/distribution | Improves discovery and validates message | Stable logical-library language |

## Proposed 90-day release slices

**[SPEC]**

### Slice A — “Understand my library” (days 0–30)

- DEL-00 and DEL-01 complete;
- logical Library groups copies and flags divergence;
- Overview routes users to invalid/divergent/unknown items;
- mobile list/detail behavior works at all harness widths;
- token panel uses the four-part semantics or clearly labels unavailable parts;
- landing message and screenshots reflect the shipped slice.

Release exit: a new user can find one logical skill, see its copies, and
understand whether the selected consumer result is known, ambiguous, or unknown.

### Slice B — “Deploy a controlled set” (days 31–60)

- onboarding is complete;
- tags and multi-select ship if their metadata decision is approved;
- profile design is accepted and read-only desired/observed preview exists;
- Consumers/Projects navigation uses verified adapter evidence;
- batch mutations retain exact preview and recovery.

Release exit: a user can define/select a set, preview exact targets, deploy it,
and recover without interpreting raw scope duplicates.

### Slice C — “Update with evidence” (days 61–90)

- source/provenance record decision is accepted;
- directory-wide upstream diff and staged update preview work for at least local
  path and public Git fixtures;
- validation, risk, and provenance appear together without a false aggregate
  badge;
- trust-first registry design is ready; network execution ships only if its
  security gate is separately approved;
- team design-partner pilot specification and recruitment are complete.

Release exit: a user can prove where a supported skill came from, see exactly
what changed, validate the candidate, apply it, and roll back.

## Product experiments

**[?]**

| Experiment | Hypothesis | Method | Decision signal |
|---|---|---|---|
| Logical Library prototype | Users understand one skill with instance badges faster than raw scope copies | Five moderated task sessions using both views | Fewer wrong-copy actions and faster correct explanation |
| Quality decomposition | Separate evidence panels build more trust than a single score | Prototype interviews and comprehension questions | Users can explain each signal's limit |
| Pro backup concept | Individuals pay for managed recovery/update convenience | Problem interviews plus price/concept test; no fake purchase claim | Repeated urgent use case and credible willingness to pay |
| Team policy pilot | Teams pay to distribute approved profiles and detect drift | 5–10 design partners using a manual/service-assisted pilot | Recurring workflow, named budget owner, renewal intent |
| Packaging | Signed desktop/standalone package improves activation | Compare documented install completion in consented tests | Material reduction in install failure/time |
| Trust-first discovery | Provenance/validation drives installs better than popularity-only browse | Usability comparison with staged catalog fixtures | Users select compatible reviewed content and understand risk |

Do not treat positive interview sentiment as purchase evidence. Record current
workarounds, consequences, authority, budget, and an explicit next commitment.

## Decision register

**[?]**

| ID | Blocking decision | Affected work | Required artifact |
|---|---|---|---|
| DEC-01 | Metadata home for tags, profiles, and onboarding state | DEL-04/05 | ADR covering filesystem truth, export/import, rebuild, concurrency |
| DEC-02 | Runtime representation of consumers/projects/bindings | DEL-06 | ADR-002 amendment or new ADR; no persisted effective state by default |
| DEC-03 | Source/provenance lock format and credential boundary | DEL-07/08 | ADR plus threat-model update and migration rules |
| DEC-04 | Network registry authentication, cache, integrity, and availability | DEL-08 | ADR-003 amendment plus threat model |
| DEC-05 | Git-only versus managed backup; encryption and conflict semantics | DEL-09 | ADR-009 local Git/review/apply policy resolved 2026-09-20; hosted/encrypted backup remains separate |
| DEC-06 | HMAC versus asymmetric signatures and bundle versus service distribution | DEL-10 | **Resolved 2026-09-20:** HMAC/shared-secret, file-only offline distribution, content-only signed metadata in ADR-004 §6 |
| DEC-07 | Free/Pro/Team packaging and first price test | DEL-09/10/11 | Interview evidence and pricing experiment brief |
| DEC-08 | Optional analytics scope and consent | All growth work | Data inventory, privacy model, opt-in UX, retention/deletion policy |
| DEC-09 | Desktop/standalone distribution approach | DEL-11 | Packaging ADR if any locked constraint or runtime changes |

## Verification and quality plan

**[SPEC]**

### Per-change ladder

Every accepted slice runs the commands in @docs/SESSION-CONTEXT.md on the
current tree. Additional requirements:

- `store.py` change: `smoke_store.py` is mandatory;
- `webapp.py`/REST change: `smoke_web.py` is mandatory;
- frontend behavior/style change: syntax checks plus `browser_harness.py` at
  320/400/640/900/1280 px and keyboard/focus coverage;
- archive, source, network, credential, signing, or sync change: adversarial
  corpus plus threat-model update;
- public CLI/REST/Store surface change: owning surface doc and parity contract;
- package/distribution change: build with the pinned hash-verified toolchain and
  inspect exact wheel/sdist artifacts.

### Required scenario matrix

| Area | Minimum scenarios |
|---|---|
| Logical grouping | identical copies, divergent copies, alias roots, disabled, malformed, unaddressable, deleted-between-scan |
| Workspaces | known precedence, undocumented precedence, same-tier ambiguity, missing project, external/out-of-boundary project |
| Batch actions | empty selection, filtered select-all, mixed writable/read-only, partial failure, interruption, undo/restore |
| Provenance/update | missing source, private auth failure, changed revision, line-ending-only diff, symlink, malicious archive, rollback |
| Backup/sync | first push/pull, concurrent edit, rename/delete, keep-both, offline, interrupted operation, credential redaction |
| Team governance | wrong/revoked key, tampered member, stale approval digest, unauthorized publish, policy override, audit export |
| Responsive UI | empty/small/2,000-instance data, dialog, long path/name, 200% zoom, keyboard only, reduced motion, aborted request |

### Release evidence

A release note must state:

- what user outcome changed;
- what remains proposed or unsupported;
- whether a command, Store method, schema, dependency, bind, or framework changed;
- migration and rollback behavior;
- exact current-tree verification results;
- screenshots/docs version and any known accessibility/performance limits.

## Security and privacy gates

**[SPEC]**

- Filesystem remains authoritative; indexes, hosted metadata, and caches are
  discardable/repairable observations unless an ADR explicitly defines a new
  file artifact.
- Never send skill content, paths, prompts, eval output, credentials, or system
  inventory to a service by default.
- Network installs and updates must stage before mutation and preserve all
  existing archive/path/resource limits.
- Credentials use platform/user-approved secret storage and are excluded from
  archives, logs, diagnostics, crash reports, and URLs.
- Signing proves only what its cryptographic/identity design actually proves;
  transport integrity never implies content safety.
- Hosted coordination requires its own authentication, authorization,
  isolation, retention, abuse, availability, and incident-response threat model.
- The local loopback application does not become a multi-user server through a
  configuration toggle.

## Documentation ownership

**[SPEC]**

| Change area | Owning document to update |
|---|---|
| Product strategy, segment, packaging | @docs/14-competitive-product-business-strategy-2026-09-15.md |
| Public shipped/proposed delivery status | root `ROADMAP.md` |
| Active execution checklist | root `task.md` |
| Architecture/data model | @docs/01-architecture.md and relevant ADR |
| Modules/source inventory | @docs/02-modules.md |
| CLI contract | @docs/03-cli-surface.md |
| Store contract/schema | @docs/04-store-api.md |
| Web/REST/frontend | @docs/08-web-ui.md |
| Discovery/precedence | @docs/12-agent-root-discovery-2026-09-08.md and ADR-002 |
| Registry/evals | ADR-003 |
| Team distribution/signing | ADR-004 |
| Security disposition | threat model and audit tracker |
| Every completed change | @docs/06-progress-log.md and `task.md` |

## Definition of ready

**[SPEC]**

A milestone is ready only when:

- the user problem and excluded scope are explicit;
- current behavior is reproduced with a fixture/test;
- approval labels and required decisions are resolved;
- file ownership is clear and no concurrent writer overlaps the batch;
- UI/error/empty/loading/partial-failure behavior is specified;
- data ownership, migration, concurrency, and rollback are specified;
- security/privacy impact and verification commands are listed;
- acceptance criteria are observable and do not depend on internal
  implementation wording.

## Definition of done

**[SPEC]**

A milestone is done only when:

- all accepted criteria pass on the current working tree;
- no locked constraint moved without recorded approval;
- failures surface as clean errors/dialogs rather than tracebacks;
- docs, tests, smokes, browser checks, and package gates appropriate to the
  change have current evidence;
- `task.md`, @docs/06-progress-log.md, public roadmap, and owning docs agree;
- migration/recovery are exercised, not merely described;
- proposed/unknown work remains labeled and is not marketed as shipped.

## Planning risks specific to execution

**[SPEC]**

1. **Overlarge UI rewrite:** cut DEL-02 into derived grouping, navigation shell,
   detail drill-down, then action migration; keep mutations explicit throughout.
2. **Accidental second source of truth:** do not put profiles/provenance/team
   state in SQLite merely because querying is easy; decide portable file
   ownership first.
3. **Backend expansion disguised as UI:** if the frontend needs a new mutation or
   domain entity, stop at the approval gate.
4. **Performance optimization without evidence:** measure scans, payloads, and
   rendering separately; retain correctness fixtures at large scale.
5. **Marketplace before trust:** DEL-08 cannot leapfrog DEL-07.
6. **SaaS assumptions leaking local:** paid coordination stays separable and
   local capabilities remain complete offline.
7. **Adapter claim drift:** verified status expires into needs-review when its
   primary source or fixture is stale; the UI must degrade honestly.
8. **Metrics violating trust:** no default content telemetry; use opt-in counts
   and research until a privacy decision is accepted.

## Next action

**[SPEC]**

DEL-00 through DEL-09 foundations are recorded as shipped, the Overview and
task-oriented navigation slice is now shipped in the current tree, DEL-10
remains a narrow integrity/policy foundation, and DEL-11 remains human-gated
beyond local evidence. The next action is to continue evidence-gated refinement
of the shipped Library, Quality, Install/Recovery, and Settings centers. Human
visual/usability validation of the shipped Overview remains open. Do not infer backend, schema, CLI, dependency, hosted,
or packaging authorization from this plan; retain the existing approval labels
and gate any optional desktop experiment through DEC-09.
