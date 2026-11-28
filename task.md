# Task Checklist — Skills Manager

**Version 0.13.2**

**AI manifest**: Live work and the remaining gated/deferred queue. `[ ]` means
pending, `[/]` in progress, `[x]` completed. Historical milestones, including
older duplicates of this queue, are archived at
@docs/archive/task-history-through-2026-11-17.md. Archive checkboxes are dated
records, not additional live work.

## Redesign build (2026-11-27)

Spec: @docs/61-redesign-build-spec-2026-11-27.md (detail in
`docs/redesign-build/`). Phases land on `main` green, one at a time.

- [x] Write the build spec from design system v13, canvas v58
  (`designs/final/`) and the briefs, checked against the current code.
- [x] Blocking questions Q1, Q3, Q4 and Q8 decided (recommended answers,
  2026-11-27); design sources committed.
- [x] Refresh `project-status.md` and `project-status.html` against the approved
  design sources and build spec (2026-11-27). The latest board points to
  Phase 3, starting with the Skill page.
- [x] Apply the fix-now changes in @docs/62-redesign-review-2026-11-28.md:
  disclosure chevrons, first launch, classic-view redirects, Doctor and Why
  findings, and feedback scoped to the current visit.
- [x] Apply the before-launch review fixes to the shipped screens and record
  what could be reproduced in @docs/62-redesign-review-2026-11-28.md.
- [x] Restore the browser smoke checks on the Paper Skills table.
- [x] Restore the selected-copy tools under Advanced and verify linked-copy
  guards, tag and profile changes, and reviewed removal with Undo.
- [x] Keep confirmations through navigation triggered by their own actions.
- [x] Fix the remaining Paper recovery, copy and layout findings. Record the
  follow-up decisions and coverage in @docs/62-redesign-review-2026-11-28.md.
- [x] Polish Advanced Skill copies wording, duplicate-profile feedback and phone targets, including the review dialog. Five focused comparison runs under CPU load passed; the earlier full-suite attempt was interrupted after a unittest process encountered malformed inherited Git configuration.
- [ ] Maintainer review of S9. Confirm any future change to the approved page
  widths during design acceptance.
- [ ] Remaining open questions Q6–Q7, Q9–Q11 in
  @docs/redesign-build/09-open-questions-and-risks.md.
- [x] Phase 0 implementation and local checks · Foundations: tokens pipeline, `system.css`, fonts + OFL, logo,
  agent marks, rewritten token gate, `var()` reference test, `DESIGN.md`; the
  whole app changes look in one commit.
- [x] Integrate Phase 0 and verify CI before Phase 1. Commit `c3087ec` passed
  all 17 GitHub CI jobs. See @build-progress.md.
- [x] Phase 1 implementation · Shell: router + legacy redirects, `state.js`, header and tab
  bar, Undo bar, notices, search and palette (S12), Not found (S13).
- [x] Verify Phase 1 locally on Python 3.11–3.14 and Chromium. See @build-progress.md.
- [x] Integrate Phase 1 and verify CI before starting Phase 2. Commit
  `72401c7` passed all 17 jobs. See @build-progress.md.
- [x] Phase 2 · Hero: Skills table S1 + side panel S2 with square states,
  first launch, tracking doorways and guarded Undo. Local review against the
  Claude canvas and design-system exports is recorded in @build-progress.md.
- [x] Apply the four-artifact review corrections to shipped behavior, including
  status evidence, tracking revisions and recovery, copy previews, tablet
  focus, Undo timing, the small favicon and acceptance coverage.
- [x] Phase 3 · Everyday jobs. The Skill page, Editor, New skill and diagnosis
  screens are implemented. The Skill page now reads the selected
  folder’s live document and shows file and listing estimates. The Editor
  now saves to empty writable places with guarded Undo. The maintainer
  approved the Editor, and commit `614bc4b` passed all 17 GitHub CI jobs.
  See @build-progress.md.
- [x] Phase 4 · Upkeep: S7 Needs attention and S8 Trash & backups approved.
  Trash & backups uses a merged Trash list, library archives and checked
  archive previews. Commit `382364b` passed all 17 GitHub CI jobs.
- [/] Phase 5 · Advanced S9 passed local verification and is ready for
  screen review. Tool pages S10, Settings S11, and What to track S14–S19
  follow.
- [ ] Phase 6 · Phone layouts.
- [ ] Phase 7 · Remove the old UI code and aliases; rewrite web UI docs.
- [ ] Phase 8 · Acceptance: ladder, accessibility, visual check against the
  boards, maintainer's 20-minute test, `/ux-review`.

## Jackfield name and brand mark (2026-11-26)

- [x] Naming research and scoring; owner shortlist; Jackfield recommended.
- [x] Logo kit for the chosen mark (B7 Quiet soft J) in `branding/jackfield/kit/`.
- [x] New mark wired into `skillsmgr/webui/logo.svg` (favicon, README) and the
  header mark in `index.html` / `styles.css`.
- [x] Rename user-facing names to Jackfield: `jackfield` CLI (alias
  `skills-mgr`), web UI, docs, management skill, `JACKFIELD_*` variables with
  legacy fallback, new installs in `~/.local/share/jackfield` (an existing
  `skills-manager` library used in place).
- [x] GitHub repository renamed to `udayvarmora07/jackfield` (old URLs redirect);
  checkout moved to `~/jackfield` with `~/skills-manager` left as a symlink and
  all worktrees repaired (2026-11-27).
- [ ] At the next release: publish as `jackfield` on PyPI (trusted publisher for
  the new project, installers' `DIST`/`COMMAND`, `tools/verify_published.py`,
  README badge) and a final `skill-control-plane` that points to it.
  [?] 2026-11-27: `jackfield` is still unclaimed on PyPI and TestPyPI, and a
  pending publisher does not reserve a name. The GitHub repository was renamed,
  so the existing `skill-control-plane` trusted publisher very likely still
  names `skills-manager` and must be updated before that final release
  (not checked: needs the maintainer's PyPI account).
- [x] Seven-day session audit, cleanup of merged worktrees/branches (tips kept
  in `refs/wip/branches/*`) and suite isolation from the checkout's own
  project skills (2026-11-27; see the progress log).
- [x] Brand working files in `branding/jackfield/` and `project-status.md`
  committed; `handoff/` stays untracked per Q8 (2026-11-27).
- [ ] Trademark (USPTO/EUIPO) and domain check for "Jackfield".

## Agent tracking (2026-11-26)

Approved design: `design-brief.md` / `ux-brief.md` "Feature: Agent tracking"
(flows T1–T9, screens S14–S19, signed-off backend contract), canvas rows
`ATA-01`…`ATA-09` / `ATD-01`…`ATD-09` (version 52).

- [x] Backend per the contract: `skillsmgr/tracking.py` owns
  `<data>/tracking.json` (atomic, 0600, revision-checked, broken file copied
  aside); `GET`/`PUT /api/tracking` (409 when stale) and
  `POST /api/tracking/check-folder`. Web-only scope overlay
  (`context.SCOPE_OVERLAY`) so every existing route filters or refuses on the
  server; CLI and `--scope` unchanged. `tests/test_tracking.py`.
- [x] Web UI, mapped onto the shipped UI (option A, chosen by the
  maintainer: "A: fit shipped UI"): What to track (`#/settings/tracking`), Add
  other agent / Edit, Add project folder; Sync map column ▾ menus with the
  confirm in its side panel; Skills project picker, Manage agents, Found-agent,
  broken-file and missing-project notices, "No agents are tracked." empty
  state; Tools hides switched-off groups (Settings stays), a switched-off tool
  page offers Turn it on, Tools → Settings gets a "What to track" row; command
  palette entries. Every change saves at once with Undo; stop-tracking confirms
  show the mini table preview and "Nothing on disk changes".
- [x] Browser e2e (`tools/e2e_v2`): stop tracking with Undo (Sync map menu and
  panel confirm), add a custom agent with live folder checks, then Remove it
  with its folder unchanged; What to track pages join the width/theme overflow
  sweep.

## Project-local AI Tooltip skills (2026-11-24)

- [x] Install `uxui-workflow` and the 12 skills from `ai-tooltip-skill-set` in
  `.agents/skills/` for Codex and compatible agents, and `.claude/skills/` for
  Claude Code. Retain upstream supporting files and MIT notices.

## One interface, desktop-first UI pass (2026-11-23)

- [x] Repeat the audit on 2026-11-24. Keep Sync map actions within their side
  panel and dismiss idle dialogs from the previous page on browser navigation.
- [x] Clarify first-run and filtered states, keep reader
  comparisons available at laptop and narrow widths, make the editor toolbar
  and save controls easier to use, and expose the command palette in the header.
- [x] Fix stale reader history and global search filters, shortcut handling on
  focused controls, and AI estimate callbacks that outlive their input values.
  Align Trigger test choices with simulation eligibility.
- [x] Remove the classic interface (`webui/index.html`, `app.js`, `styles.css`,
  `tools/e2e_classic`, 131 classic-only tests); move the interface out of
  `webui/v2/` so it is served at `/`; `/v2/` and `/classic/` redirect (307).
- [x] Replace the cream, serif and terracotta look with the documented
  `DESIGN.md` system (cool bone ground, IBM Plex Sans + Plex Mono identifiers,
  one teal signal ink, cool dark palette); rewrite `DESIGN.md` and port
  `check_design_tokens.py` to the current tokens.
- [x] Desktop-first layout fixes from two audits and seven five-pass screenshot
  reports (182 captures at 1366/1440/1920, dark, 390): Home agent cards, Skills header above
  the 768px fold, reader title and description fold, Sync map at 1280px,
  Recovery grid, Tools frame and sidebar, Quality paging, filterable copy
  pickers, command palette, header search results, disabled buttons, focus and
  current-tab states, AI-off pages, copy fixes.
- [x] Port the browser harness and E2E contracts to the root interface. Recover
  the interrupted dark and laptop reviews and verify the missing Help, diagnosis
  and add-to-agent states.
- [x] Fix dark-mode selections, multiline creation fields, concealed copy
  paths, narrow-window Tools navigation and Quality disclosures. Restore install
  preview evidence and guard against duplicate workspace inspection requests.
- [x] Run Porting notes and Explain risk findings without a connected model.
  Bind explicit model sends to the previewed prompt and destination.

## Skill Markdown reader (2026-11-23)

- [x] Use one offline Markdown renderer for both skill readers and editor
  previews. Display structured tables and nested content, and give wide tables
  a keyboard accessible scroll region.
- [x] Preserve each reader's link policy, keep HTML and images inert, and cover
  formatting, comparison highlights, and the vendored files with regressions.

## AI authoring and skill lifecycle research (2026-11-22)

- [x] Review public user reports, comparable products, evaluation research, and
  current AI code. Record the recommended authoring and testing sequence and
  later maintenance options in @docs/58-ai-authoring-and-skill-lifecycle-research-2026-11-22.md.
- [x] Integrate AI drafting and text editing into the v2 create and edit entry
  points. Bind confirmed requests to the previewed inputs and model destination,
  and use exact-copy source review and snapshots for edits.
- [x] Compare reviewed versions and optionally a second model. Connect a failed
  request to discovery checks, simulation, saved regression cases and edit review.
- [x] Surface AI maintenance from the reader, compare upstream candidates and
  explain Sync map and Inbox excerpts. Let users download comparison evidence.
- [ ] Extend attended native-agent validation beyond the existing evidence and
  verify support before adding more native trace formats. See the gated fidelity
  study below. The research report also tracks capture automation, executable
  bundles, and managed publishing as separate follow-ons.

## AI across every feature: second research pass (2026-11-22)

- [x] Research user demand, competitors, literature and AI UX patterns beyond
  the shipped authoring flow. Map every product surface to current and proposed
  AI support in @docs/59-ai-everywhere-research-2026-11-22.md.
- [x] Slice 1: repeated trials with paired lift, a 95% bootstrap interval and
  an inconclusive verdict for AI evals and current-vs-proposed comparisons;
  token-regression and non-discriminating-assertion flags; per-hunk accept for
  AI edits (`/api/ai/edit-select`); AI provenance on Recovery snapshots. AI
  evals had no CLI command, so no CLI flag was needed.
- [x] Run a three-round research loop across Reddit, X, YouTube, GitHub, HN,
  Bilibili, V2EX, Quora, Instagram, products and literature, fact-check 30
  claims, and consolidate proposals G1–G15 in
  @docs/60-ai-features-research-loop-2026-11-22.md.
- [x] Slice 2, approved 2026-11-22: `ai ablate` (G1: remove a skill or
  section, replay saved cases, propose removal when not worse, staged review or
  demotion ladder), `ai conflicts` (G2: heuristic contradiction candidates
  between instruction files and skills, optional AI judge with file quotes),
  and per-skill description cuts for Claude Code and Codex in the listing
  report (G3). v2 tool pages "Does it earn its place?" and "Contradiction check".
- [ ] Remaining approval items: `ai health` and `ai recheck`, new agent scopes,
  team-export scope, and per-excerpt consent for sending transcript content to a
  model.
- [x] Round 4 research through the user's own browser (Reddit, X, Instagram,
  Quora), reports 15–17 in @docs/research/2026-11-22-ai-loop/.
- [x] Literature deep dive (report 18). Applied: cases-only bootstrap,
  minimum detectable effect, `untested` ablation decision, two-order judge.
- [x] Literature batch 2: thin-description flags in the listing report,
  `ai ablate --placebo`, directive density and stale project references in
  `ai conflicts`.
- [x] Literature batch 3: held-out gap and selection note for description
  rewrites, `--votes 3` for the contradiction judge, reason counts per
  instruction file, conditional and prohibitive wording counts, and
  planted-instruction tests for the judge.
- [x] Resume batch 3 QA and cover the confirmed regressions in ablation
  statistics and history, Markdown section and directive parsing, Windows
  source labels, model response validation, and held-out rewrite evidence.
- [ ] Remaining literature proposals in @docs/60-ai-features-research-loop-2026-11-22.md
  "Round 4": real-runtime trigger checks, a predictive-value estimate for the
  contradiction judge, and action assertions.

## V2 Tools, Quality and Recovery usability (2026-11-21)

- [x] Audit the existing layouts with agent-browser and agent-desktop. Consult
  Awwwards, Godly/Recent Design and Inspo MCP references.
- [x] Add a searchable tool directory and a visible All tools link at narrow
  widths. Keep the grouped desktop sidebar.
- [x] Add keyboard-accessible section shortcuts in Quality and Recovery,
  clarify backup modes, and cover tool search and shortcut focus in browser tests.
- [x] Complete the deeper product and gallery reference study with rationale,
  live walkthroughs, current v2 measurements and proposed usability tasks.
  See @docs/55-v2-ui-reference-study-2026-11-21.md.
- [x] Build and verify an editable reference board in a tool that opens local
  files without account authentication.
- [x] Reopen the reference selection after feedback. Screen new live products
  and reference libraries, walk through shortlisted tasks, verify frontend
  source on GitHub, and deliver a revised editable board.
  See @docs/56-v2-reference-selection-loop-2026-11-21.md.
- [x] Inspect anonymous Mobbin collections and free resources, test two
  open-source diff demos at phone widths, and update the shortlist for
  exact-copy comparison and recovery evidence. Verify the editable Draw.io
  board opens without an account.
  See @docs/57-v2-mobbin-and-comparison-references-2026-11-21.md.
- [x] Apply the reference research to v2. Carry a name search into Sync map,
  compare exact document copies at desktop and phone widths, and review the
  saved folder before restoring an agent trash entry. See @docs/08-web-ui.md.

## Claude Code recovery hardening handoff (2026-11-20)

- [x] Complete forced-Sync companion preservation and show affected v2 Inbox
  targets before overwrite. Report exact Recovery and retained backup paths.
- [x] Add CLI-only transcript consent, cached aggregate reports and manual
  refresh for supported structured agent events.
- [x] Validate cached usage summaries and day buckets before using them as
  archive evidence. Keep valid counts visible when only a scan summary is damaged.
- [x] Read project locks v1/v2, verify installed trees offline, and support
  reviewed v2 writes and guarded undo.
- [x] Add native project CLI preview/apply/undo for supported JSON settings,
  and read-only Codex launch and Command Code patch handoffs.
- [x] Add lifecycle evidence and reversible pins.
- [x] Keep pin undo recoverable after interrupted replacement, and refuse
  stale receipts and damaged preimages.
- [x] Recover interrupted native settings and project lock replacements
  through existing undo commands with exact file checks.
- [x] Honor project lockfile write protection during apply and undo.
- [x] Report primary document modification evidence in `archive candidates`
  using one UTC date window for modifications and cached usage events.
- [x] Add reviewed, explicit archive apply and restore for one manager-library
  copy. Staleness-based selection remains unavailable pending independent
  evidence of continuous coverage, consumers, edits and installs.
- [x] Show pins from every equivalent scope when the archive preview coalesces
  copies under a shared root.
- [x] Make opted-in usage reflect persisted OpenCode 2.3.2 activations, report
  the requested UTC date window, and recover from interrupted bounded scans.
- [x] Read OpenCode's configured database and explicit activations, keep cached
  evidence tied to its consented root, and show documented reader gaps in
  archive previews.
- [x] Report incomplete inventory, shared roots and project reader hints in
  archive previews. Distinguish name-matched usage from document activity.
- [x] Include project Gemini and Command Code folders in scoped inventory,
  Workspaces and archive previews, with grouped Command Code discovery.
- [x] Observe standalone Gemini documents in read-only discovery and surface
  their presence in archive inventory diagnostics.
- [x] Preserve grouped and recursive archive inventory across shared roots,
  including project aliases. Report relative folders, partial observations of
  unaddressable skill names, and reader hints from selected root aliases.
- [x] Add developer HTTP regression contracts and a shared JUnit failure
  summary for Hurl and exported Keploy reports.
- [x] Run hash-pinned Hurl contracts in CI, verify scoped Recovery preserves
  unrelated trash, and retain actionable JUnit failure reports.
- [x] Pin the Hurl job to an Ubuntu image that provides its libxml2 runtime
  and check binary startup before running the HTTP contracts.
- [x] Compare portable backup timestamps on Windows and close legacy
  installer metadata before PowerShell uninstalls the environment.
- [x] Verify the native open-source Keploy export against a synthetic saved
  run, including the cgroup startup warning before JUnit XML.
- [x] Rehearse the upgrade from published 1.0.2 and restore its full backup
  into the 1.1.0 candidate using synthetic active, disabled and trashed skills.
- [x] Automate the pinned-wheel upgrade, full restore and downgrade rehearsal
  on the release artifacts. Add a manual cross-platform build and verification
  run, with publishing gated by a matching version tag.
- [x] Use the resolved Python interpreter to bootstrap clean installs in both
  release verifiers when Python is invoked through a launcher symlink.
- [x] Guard POSIX installer upgrade and uninstall with virtual environment
  ownership checks. Preserve foreign launchers and existing environments.
- [x] Guard Windows installer upgrade and uninstall with ownership checks.
  Preserve linked prefixes and unmarked custom environments, and exercise
  those checks under Windows PowerShell 5.1 in the hosted workflow.
- [x] Make the README quickstart start with a read-only inventory and use a
  temporary manager library for recovery practice. Resolve repository links
  and images from PyPI and check them in the documentation gate.
- [x] Protect managed consent and recovery receipts from backup destinations.
  Use the checked output directory if its symlink changes during export.
- [x] Refuse to publish a backup when a concurrent Trash or Restore action
  changes the inventory or a supporting file changes during capture.
- [x] Surface a retryable backup conflict in v2 and classic Recovery and
  verify a retry downloads the full archive.
- [x] Verify recorded skill checksums before a full restore can replace
  library, trash, templates or catalog data.
- [x] Refuse to publish slim or full backups when a supporting folder cannot
  be read during capture or verification. Preserve the previous archive.
- [x] Record the 1.1.0 candidate's hosted macOS and Windows rehearsal results.
  Both runners installed the exact wheel and source distribution, upgraded
  from 1.0.2, restored its full backup, and reopened the original library
  after reinstalling 1.0.2.
  [Hosted rehearsal](https://github.com/udayvarmora07/skills-manager/actions/runs/44903486924)
- [x] Resume budgeted JSONL refreshes across an unfinished append and retain
  partial coverage when a record was skipped.
- [x] Count the complete records that fit each bounded JSONL refresh. Keep
  evidence from interrupted OpenCode reads and scan newly inserted rows first.
- [x] Read JSONL session files larger than one refresh can handle, keeping
  oversized records skipped when their tails fall in later refreshes and
  applying the same budget when an agent selection is repeated.
- [x] Resume capped text-transcript walks across projects and retain files
  already counted when discovery reaches its deadline.
- [x] Rotate the starting agent after a refresh exhausts the shared budget
  and preserve the saved position of agents deferred to the next refresh.
- [x] Close AI provider and registry HTTP error responses before returning
  an error or retrying.
- [x] Validate links to repository Markdown when the documentation checker
  cannot use Git, with coverage for links through external symlinks.
- [x] Connect native settings previews to optional off lists in manager-saved
  profiles while keeping the browser enable-only action separate.

See @docs/54-usage-lifecycle-lock-native-profiles-2026-11-20.md.

## Sync map and Recovery continuation (2026-11-20)

- [x] Add a Sync map review filter that combines with name search and covers
  differing, unreadable, duplicate and uninspected copies in displayed scopes.
- [x] Clear repair selections when opening another copy, including in the
  same scope. Count only currently eligible selections in the sync action.
- [x] Restore exact global trash entries from both interfaces and Undo.
  Separate scoped restore of a skill named `purge` from emptying global trash.
- [x] Discard superseded v2 history, trash and catalog responses.
- [x] Finish the current-tree verification ladder and record the results in
  @docs/06-progress-log.md.
- [x] Correct the Windows lockfile mode, binary-read and Codex usage failures
  seen in GitHub CI, and cover the Chrome profile cleanup race. Both Windows
  runners passed on `80f1dd8`.
- [x] Replay the full v2 suite in Firefox and enable repeatable Firefox runs
  for the classic suite. Verify classic in both browser engines.
- [x] Capture and label seven screenshots from the current v2 build with
  synthetic skills. Package them for review before external use.
- [x] Verify fresh Recovery addresses for same-second removals in global and
  agent trash, including restores from older builds' timestamped directories.
- [x] Verify that global Recovery rolls back the selected trash tree when
  its index/history transaction fails.
- [x] Accept trash paths returned through a linked global trash folder, and
  make restore and rollback work across volumes (EXDEV: copy, verify, retire
  the original; withdraw the copy and keep the original if retiring fails).
- [x] Agent-scope Recovery restores across volumes with the same staged,
  verified copy; the global default restore follows trash stamp and serial
  rather than directory mtime; a trash entry that vanishes mid-selection is
  skipped instead of escaping as a raw error.
- [x] `POST /api/trash/purge` empties the trash only as a bare request; a JSON
  body or `scope`/`snapshot` parameter makes it a restore of `purge`.
- [x] Roll back full-backup trash, templates and catalog metadata when a file
  fails to install, a rename is interrupted, or trash index reconciliation
  fails. Keep blocked rollback copies across retries.
- [x] Restore the catalog metadata file without replacing companion files.
- [x] Keep original skill folders through a blocked import rollback, index
  resync and retry. Refuse forced imports through a linked alias.
- [x] Restore larger TAR backups, validate their import budgets before
  publication, and restore large template sets with a fixed lock count.
- [x] Export hardlinked companion bytes and omit install evidence. Read
  legacy archives whose valid full-tree hashes included that evidence.
- [x] Prevent concurrent default backups from overwriting each other. Detect
  file and directory collisions and Windows filename aliases before extraction.
- [x] Preserve the previous backup when a skill disappears or its primary
  document cannot be restored. Refuse output paths in managed data and
  report metadata decoding errors before installing archive contents.
- [x] Preflight incompatible full-import destinations before replacing skills.
  Roll back a skill and its index row when import history cannot be written.
- [x] Show full archive import results and skip reasons in both interfaces.
- [x] Preserve active skills when full archive metadata restoration fails.
  Reject duplicate trash and template entries in an archive manifest.
- [x] Remove three timing races from the suite (fidelity descendant state,
  simulator timeout, skill CI recipe signal before trap) and make the
  corrupt-artifact package test check its reason on both archive readers.

## All-scope list request speed (2026-11-19)

- [x] Profile `GET /api/skills?scope=all&body=0` on 1,000 and 10,000-record
  synthetic fixtures; land only measured, behavior-preserving changes with a
  pinned equivalence test; reject gzip with evidence
  (@docs/52-list-request-performance-2026-11-19.md).

## Size, performance and Rust assessment (2026-11-17)

- [x] Research current primary sources and inspect this app using agent-reach,
  OpenCLI, OpenCLI Browser and Vercel agent-browser, as requested.
- [x] Measure package/runtime size and representative startup, scan and hygiene
  workloads; separate application bytes from shared interpreter/browser costs.
- [x] Keep only verified size/performance improvements with unchanged behavior:
  deduplicate identical font resources and test one-request Doctor scan reuse.
- [x] Record a source-backed Rust/native/hybrid/full-rewrite decision, including
  portability, security, maintenance, rollout and measured limitations.

The maintainer permits a stack/language migration if research justifies it.
Research does not itself select or ship a replacement. No skill data or native
consumer configuration may be sacrificed for a timing or package-size claim.

Verified outcome: the clean wheel is 14.32% smaller (1,069,942 → 916,682
bytes). Three paired synthetic warm-cache CLI samples show median reductions
of 18.7% at 1,000 skills and 25.6% at 10,000 for single-agent Doctor/hygiene.
All 2,172 tests pass on each supported Python version, both smokes and artifact
install probes pass. Rust/full migration remains an evidence-gated future
option; the assessment recommends the optimized Python/Vue shipping reference.
No language/framework/schema/runtime dependency changed. Full evidence:
@docs/50-rust-size-and-performance-assessment-2026-11-17.md.

## Second five-task continuation (2026-11-17)

- [x] Observe grouped personal Claude skill folders without asserting native discovery.
- [x] Observe supplied-project Codex skill declarations without applying native state.
- [x] Separate plugin manual-only intent from historical invocation compatibility reports.
- [x] Report lock-name collisions and unverified source-path declarations.
- [x] Archive completed tracker/progress history losslessly and preserve the open queue.

Verification, commit and normal push to `main` are authorized. No new CLI
command, Store method, schema or runtime dependency is planned. Native sessions,
human sign-offs, owner decisions and publication retain their separate gates.

Verification: 2,164 tests pass on each Python 3.11–3.14, with optional skips
of 5/5/5/4 respectively; both smokes, repository gates and exact package/install
probes pass. All 235 original task/progress sections survive byte-for-byte in
either their original file or indexed archives. Normal main integration is
authorized. The original 15 gated/deferred entries remain open.

## Additional maintainer request (2026-11-17)

- [x] Record research-first tool/setup authorization and Terra/Luna subagent
  preferences in `AGENTS.md`, preserving specific product and release gates.

## Continuation (2026-11-18)

- [x] Recheck the public release status and the cancelled macOS CI leg.
- [x] Exercise v2 in Firefox and retain a repeatable browser runner.
- [x] Report the presence of regular APM project manifests and locks in v2 Quality.
- [x] Verify OpenCode skill-load evidence with a synthetic local provider.
- [x] Capture dated local screenshots for the design-partner pilot review.
- [x] Stabilize the subprocess cleanup and browser sync/Undo assertions.
- [x] Recover and publish the original attested `v1.0.2` wheel and sdist.
- [x] Verify both public artifacts and a clean PyPI install, then remove the
  one-time recovery workflow.

Evidence and remaining decisions are recorded in @docs/06-progress-log.md.

## Agent context hygiene (2026-11-18)

- [x] Verify the research behind the video and record its limits.
- [x] Share task-scoping and context rules between Codex and Claude Code.
- [x] Add an evidence-only context sweep with explicit invocation.
- [x] Verify and correct stale guidance in the current session entry points.

## Autonomous review and improvement loops (2026-11-19)

The maintainer asked for an in-depth review, then repeated improve/evaluate
loops while away. Locked constraints and ASK gates still apply; items that
need a decision are listed under "Open for the maintainer" instead of being
done.

- [x] Loop 1 — review: backend, web security boundary, v2 UI (live), lint.
- [x] v2 nav: fade the tab strip only while tabs are actually clipped.
- [x] v2 skill page: library-only skills say "only in your library", not "in 0 places".
- [x] v2 Markdown: a link address with parentheses is shown whole.
- [x] Static gate: Ruff selects all of pyflakes (`F`); 40 dead imports/variables removed.
- [x] Remove unreferenced prototype/design-concept folders and generated build output.
- [x] Loop 2 — evaluate as a user with Lighthouse and axe-core (agent-browser `a11y`).
- [x] v2: turned-off cards keep AA contrast (dashed edge, muted tokens; no opacity).
- [x] v2: Claude/Gemini badge fills darkened to clear 4.5:1 under white initials; test added.
- [x] Every v2 page passes axe WCAG 2.2 AA in light and dark; Lighthouse a11y 100.
- [x] Brand: hand-drawn SVG mark (a skill page carrying a switch), v2 favicon,
  theme-token header mark and README logo; flat palette, no gradients or glyph tropes.
- [x] Loop 3 — phone width (375 px): no horizontal overflow on any v2 route.
- [x] Loop 3 — read-only REST fuzz: 3,528 malformed GET requests, zero 5xx.
- [x] Classic: the first-scan root list is a focusable, named scroll region (axe clean).
- [x] v2: text fields show the same 2 px focus outline as every other control.
- [x] Logo restart (owner rejected the page-and-switch mark): researched studio
  process and 2024–26 clichés, installed the vetted MIT `logo-designer` skill,
  drew five concepts in parallel, chose "the switchboard" by scale, 1-bit and
  distinctiveness tests; applied to favicon, header and README.
- [x] Real agent marks (Claude Code, Codex, Cursor, Gemini, OpenCode) replace
  initials badges across v2, vendored from Simple Icons (CC0) and theSVG (MIT);
  Command Code and the shared folder keep badges (no open mark exists).
- [x] Scope label "Opencode" corrected to the project's own "OpenCode".
- [x] Missing marks filled: Command Code's official ⌘ symbol and the Agent Skills
  hexagon (both from the Apache-2.0 agentskills/agentskills repo), and the
  Skills Manager mark for "Your library"; README shows the agent row.
- [x] v2: keyboard-shortcut help ("?") is reachable at tablet widths (601–900 px).
- [x] CLI: typo hints for commands (all supported Pythons) and library skill names.
- [x] Security review (subagent, each finding reproduced, then fixed):
  environment API keys follow only the provider's default endpoint (operator
  opt-in `SKILLS_MANAGER_AI_ENV_KEY_ENDPOINT`); `untrusted_block` labels and
  case-variant tags cannot end the data region; source manifests and tree
  hashes are size-bounded and skip FIFOs; `validate --path` output sanitized;
  `git_fetch` pins `--upload-pack` and the pager.
- [x] `git_fetch` refuses a credential helper set by the repository's own config
  (`git config --show-scope`: local/worktree, includes too); global and system
  helpers keep working (2026-11-20).
- [x] v2 bug review (subagent, each finding verified): Ctrl+S save guard,
  dialog Escape/Tab trap after a click, stale-response guards for refresh and
  skill history, history reload after changes, Test connection keeps unsaved
  AI settings, visible plurals.
- [x] v2 follow-ups: "Compare with" shows the copy being compared; a failed
  re-read is announced on every page; a new import clears the old result; the
  command palette does nothing while busy.
- [x] Merged PR #22: full suite on ubuntu/macOS/Windows plus a headless-Chrome
  e2e job; fixes macOS temp-dir symlinks, Windows fchmod/replace/ordering/
  directory identity.
- [x] v2 interface pass (2026-11-20): type-scale tokens (Large text now scales
  everything), spacing rhythm, axe 0 violations, Home layout, copy (docs/06).
- [x] Resolved design-study proposals. Retain existing type sizes and solid
  palette tokens. The 13 px/500 trial saved no toolbar height or wrapping at
  the measured widths. Corrected skill-reader label contrast and recorded
  the comparison in @docs/53-apm-and-interface-decisions-2026-11-20.md.
- [x] Resolved Microsoft APM scope. Quality reports file presence and links
  to the upstream audit. APM owns YAML validation, resolution and package
  import/export. See @docs/53-apm-and-interface-decisions-2026-11-20.md.
- [x] UI follow-ups from the reference study (`~/design-refs/`): searchable
  skills × agent scopes matrix with a copy and repair panel, plus a remembered
  Comfortable/Compact Skills shelf preference (2026-11-20).
- [x] Scope scan: non-canonical names (`Upper-Case`, `.hidden`) were blanked
  as bogus link escapes with blank descriptions; document-less dot-folders
  are now honest husks ("Not a skill" kept). Toggle-toast punctuation and the
  unconfigured "Shorten a skill" heading fixed (2026-11-20, docs/06).
- [x] Leaked 2026-10-09 test fixtures `agent-only`/`demo` moved to agent trash
  (`~/.agents/trash`, `~/.codex/trash`, `~/.commandcode/trash`; restorable from
  Recovery); the two dangling `~/.claude/skills` links to them
  (`agent-only -> ~/.agents/skills/agent-only`, `demo -> ~/.codex/skills/demo`)
  were removed (2026-11-20).
- [x] Windows residual: concurrent HTTP reads saw a transient 404 during a
  replace. Readers now retry delete-pending documents (≤100 ms); the stress test
  runs on Windows again and passed on py3.11/3.14 (2026-11-20).
- [x] Compatibility: archives a Windows build exported before the `/`-separator
  change verify again (`atomic_io.tree_hash_matches` accepts the legacy `\`
  digest only on an exact match; 2026-11-20).
- [x] AI Center: buttons stay disabled until every overlapping request ends
  (an in-flight counter; the old boolean re-enabled paid calls early).
- [x] Merged PR #23 (list request 29–49% faster, response unchanged) after
  reviewing the path-safety shortcuts against `realpath` semantics.
- [x] Docs audit (subagent, each finding re-verified): README data-root fix,
  localhost guidance, doctor drift recipe; CLI surface signatures for `create`,
  `trash restore`, `templates new`; `--scope` help lists `commandcode`.
- [x] CI: the full unit suite runs on ubuntu, macOS and Windows (3.11, 3.14);
  product fixes for macOS temp symlinks and Windows `fchmod`, inode-0 risk scan,
  provenance/tree-hash ordering and separators; precise skips for POSIX-only tests.
- [x] CI: new `e2e` job runs `tools/e2e_v2` and `tools/e2e_classic` headless on
  Ubuntu with Playwright from the hash-verified `tools/e2e_deps` lockfile.
- [x] Windows: readers racing a document replace now retry too (decided and
  implemented 2026-11-20; see docs/06).
- [x] Parallel sessions: all-scope list performance and CI portability merged
  as PRs #23 and #22.

Open for the maintainer:

- [x] Issue #14 F-2: `localhost:<port>` is accepted as a Host alias for a loopback bind (maintainer approved 2026-11-19).
- [x] ADR-001 revisit (2026-11-20): on Linux a connection owned by another OS
  user is refused (kernel socket owner via `/proc/net/tcp`, no token, no client
  change). macOS/Windows unchanged — per-user token file still the option there.
- [x] Keep the tracked `.specs/` evidence and its Git history. Existing docs
  link to it and the package manifest excludes it from distribution.
- [x] `body=0` list rows also omit `portable_frontmatter`/`frontmatter_extensions`
  (896 KB of 4.8 MB on the maintainer's library; detail route unchanged; 2026-11-20).
- [x] Shelf cards: accessible name is the visible text, skill name first (no
  aria-label; CSS order keeps the layout); axe 4.7 clean. Library-only cards say
  "Only in your library" instead of "In 0 tools" (2026-11-20).

## Remaining gated and deferred entries

The delegated release review decisions are recorded below and in the parity
section. Participant research remains in the pilot protocol.

- [x] Select 1.1.0 as the next release and set the working candidate to that
  version. Keep the existing distribution and the tag-triggered publication
  gate. Record product decisions Q1–Q4 in docs/45 §7.
- [x] Check the pinned build toolchain's repeatability and document the
  distinction between identical packaged content and identical archive bytes.
- [x] Verify recovery from clean installs of both exact release artifacts.
  Compare the published PyPI downloads before creating the GitHub release.

- [/] Broader fidelity study with distractors, near misses, repeats and the
  product's configured HTTP transport; the two-case result does not validate it.
  HTTP portion completed 2026-11-17: DeepSeek V4.1 Flash via GOAT matched
  36/36 authored labels, using four skills, 12 prompts and three repeats.
  An offline OpenCode probe confirmed how to observe a successful skill load.
  The retained HTTP artifacts passed an offline checksum recheck, and the
  native harness dry run matched all 12 prompt records to the simulation.
  The repeatable OpenCode probe verifies the model-facing listing, completed
  skill call and follow-up request using a loopback-only fake provider.
  Its saved-corpus replay verifies all 12 prompts, all four listing entries,
  eight scripted skill calls and four scripted no-call cases in OpenCode.
  A fresh OpenCode-scoped simulator preflight matched the replay's fixture and
  budgeted three passes without calling a provider. The attended same-model
  comparison still needs a working provider for one of the permitted models.
  See @docs/48-ai-http-study-2026-11-17.md.

- [x] Review Orca's emitted speech and accept the release evidence for the
  spoken walkthrough. Human listening remains a research activity.
  See @docs/32-continuation-verification-2026-11-06.md.
- [x] Rehearse the v2 walkthrough with keyboard input and Chromium's
  accessibility tree. Fix Inbox names and keep the page skip link outside
  the accessibility tree while a v2 dialog is open.

- [x] Review v2 visually and with keyboard, accessibility-tree and Orca evidence.
  Keep the earlier forced-colors and actual 200%/400% browser-zoom evidence.

- [x] Resolve docs/27 MON-Q1…MON-Q5. Start with a services pilot for multi-agent
  operators. Keep the skills scope and English UI, defer the public catalog
  report, and keep Pro and Team as hypotheses. See docs/27.

- [x] Accept the redesign through the maintainer-delegated review and retain
  the classic interface. Review decisions, scope and limitations are in
  @docs/32-continuation-verification-2026-11-06.md.

- [x] Check the dated pilot screenshot package locally. All seven image
  checksums and viewport labels match the manifest. Review notes are in
  @docs/06-progress-log.md.

- [x] Refresh the pilot package from `d2257c8` and rehearse Sync and Recovery
  with a synthetic divergent copy containing a supporting file.

- [x] Approve the nine synthetic screenshots from `d2257c8` for use as
  dated product illustrations with their commit and viewport labels.

- [x] Provide a fresh synthetic pilot launcher, rehearse Sync and full-folder
  Recovery, and keep the Inbox Sync control clear of fixed navigation.

- [x] Rehearse all six pilot workflows on five fresh synthetic fixtures and
  accept this evidence for the current release review. Future participant
  sessions retain the consent and research protocol in @docs/25-design-partner-pilot-kit.md.

## Earlier completed batch (2026-11-17)

Commit `5ada04a` completed static completion/typo suggestions, per-consumer
discovery evidence, scan degradation, AI simulation wording and unknown Codex
metadata. Its receipt is in @docs/06-progress-log.md. Earlier completed tasks
remain in the archive, rather than being counted again here.

## Historical sections retained for relative links

**[NOTE]** The following sections retain their relative Markdown links.
The tool-page review records the current decision. Earlier delivery steps
remain historical.

## V2 feature parity and default interface (2026-11-06)

- [x] Audit classic and v2; create the [source-backed design and inventory](docs/superpowers/specs/2026-11-06-v2-feature-parity-design.md).
- [x] Use UI/UX Craft, Design Taste Frontend, Better Accessibility and Frontend
  UI Engineering; inspect three archived Inspo captures. Preserve v2's existing
  warm-paper/serif design. Luna/Terra provided scoped implementation and review.
- [x] Build the approved [demo-only mockups](https://github.com/udayvarmora07/skills-manager/blob/515f5be/prototype-v2-parity/README.md), then
  follow the user's expanded instruction to integrate production workflows.
- [x] Integrate Install, Profiles, Templates, Quality, Workspaces, Settings,
  source updates/snapshots, scoped history, full-archive modes, exact-instance
  batch actions, logical tags and rich create/edit into v2.
- [x] Add contained stored-template reads and explicit PATCH field clearing;
  preserve unknown/omitted metadata on ordinary edits. No schema, public Store
  API, application CLI or runtime dependency change.
- [x] Promote `/` and `/index.html` to `/v2/`; retain `/classic/` and query/hash
  behavior. Update classic browser harnesses for the explicit compatibility URL.
- [x] Fix review-discovered stale folder approval, mixed-copy description,
  omitted-metadata overwrite and independent read-state races; add regressions.
- [x] Verify real API/filesystem flows in private HOME/data fixtures, both
  themes, phone/tablet/desktop, keyboard dialogs and retry/error states.
- [x] Finish the final current-tree ladder: 1,386 unittest cases on Python 3.12,
  34 v2 browser scenarios, 38 classic scenarios / 318 assertions, both smokes,
  viewport harness, static/security/design/docs gates and pinned packaging.
  Evidence is in the [implementation plan](docs/superpowers/plans/2026-11-06-v2-feature-parity.md).
- [x] Design pass on the tool pages: Tools becomes a primary tab, duplicate
  header search removed, every tool page rebuilt on v2 components with worded
  status and humanized values; 34/34 v2 browser scenarios and 1,386 tests pass.
- [x] Commit and integrate the combined parity + design work: `61355a2` is on
  `origin/main` (verified 2026-11-06).
- [x] Review the redesigned tool pages at desktop and phone widths. Keep the
  active mobile tool tab visible and accept the layouts through the delegated
  review in @docs/32-continuation-verification-2026-11-06.md.

Agent-scope in-app trash restore now uses the existing scope-aware trash API
and the v2 Recovery card (2026-11-07; see docs/35).
Live registry fetch/commit and actual external runner execution are not exercised
by this task's browser checks. Human screen-reader and spoken usability sign-off
remain unclaimed. The work landed on `main` as `61355a2`.

## External skill scanner — SkillSpector (planned 2026-11-06)

Plan: [external skill scanner](docs/superpowers/plans/2026-11-06-external-skill-scanner.md).
The maintainer chose both phases, hook first.

- [x] Decide D-A and D-B: show SkillSpector's score labelled as its own claim;
  accept OSV egress with a stated warning (maintainer, 2026-11-06). D-C
  (Quality integration) stays deferred.
- [x] Phase A: `skillsmgr/external_scan.py`, wired into registry fetch and
  source-update reviews; `--external-scan`/`--external-scan-llm`, REST
  `external_scan`, v2 Settings + review panels. LLM mode is bring-your-own-key
  from the server/CLI environment only. 19 tests incl. an optional real-tool
  test; real v2.12.0 output verified through the hook.
- [x] Installed SkillSpector under `~/.local/share/uv/tools` was group-writable
  (umask 002). Group write removed from `~/.local/share/uv`, `.../tools` and the
  `skillspector` tree (2026-11-07); `trusted_executable` now accepts it and the
  optional real-tool test runs instead of skipping. Policy unchanged.
- [x] CI `unit (py3.10)` red on `main` at `61355a2`: `/` answered 308, which
  3.10's urllib does not follow. Default-interface redirect is now 307; slash
  canonicalization stays 308; regression test added (2026-11-07).
- [x] Pre-existing test leak (2026-11-07): `WebAppServer` left its Store bound
  in the `scopes` ContextVar, so a later in-process `cli.main` resolved `global`
  through a stale Store. `cli.main` now binds its own Store per command and
  restores the prior binding. `tests/test_cli_store_binding.py`.
- [x] AI features (BYOK): D-AI-1…D-AI-7 answered and A0–A10 shipped on
  2026-11-09; see the top section and @docs/39-ai-features-research-and-catalogue-2026-11-09.md.
- [x] Phase B: stdlib rewrites of SC2/SC3/PE3/AR/RA2/SC8/P9/TR/AST checks in
  `insights.risk_scan()` — nine checks, `tests/test_risk_scan_phase_b.py`,
  2026-11-07.
- [x] Phase B noise measured on the maintainer's real library (1,764
  instances): high `credential-path` findings fell 192 → 18 after the
  mention-vs-access fix; numbers in the external-scanner plan. Independent
  review fixes (severity-downgrade bypass, hostile-AST crashes) and the
  production wiring of files/description into `risk_scan` landed 2026-11-07.

Current implementation evidence is recorded in @docs/06-progress-log.md.
