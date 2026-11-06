# V2 Feature Parity Implementation Plan

> **For agentic workers:** Use the subagent-driven-development workflow for scoped implementation and independent review. Preserve the user's requested GPT 6 Luna and GPT 6.1 Terra model choices.

**Goal:** Complete the remaining classic workflows inside the existing v2 design, then make v2 the default after parity and regression checks pass.

**Architecture:** Retain the existing v2 shell, model and ordinary skill workflows. Add focused Vue tool components using the existing API and public assets; keep exact-copy bulk work in the library. Preserve classic under an explicit URL when the default changes.

**Tech Stack:** Python stdlib server, vendored Vue 3, plain JavaScript/CSS, no build step or new runtime dependency.

**Spec:** [V2 parity design and inventory](../specs/2026-11-06-v2-feature-parity-design.md), qualified by the user's later instruction to integrate into v2 and switch the default when verified.

## Global constraints

- The existing v2 interface is the visual authority. Reuse its fonts, tokens, buttons, form controls, document rendering and interaction conventions.
- Filesystem remains the source of truth; SQLite schema/SCHEMA_VERSION and Store public API remain unchanged.
- CLI remains stdlib-only; no new application CLI commands.
- Do not delete or modify the maintainer's real skills during development/testing.
- Registry reviewed installs are global-store-only. Profiles/tags are catalog metadata; physical mutations require exact identities. Agent-scope in-app trash restore is unavailable.
- No default-route switch before integrated feature and browser verification. No push or publication is part of this task.

## Review focus

- Offline, partial and missing responses must not render as empty success; retain errors and retry paths.
- Repeated writes, stale review IDs, changed exact targets and ambiguous sync sources must not widen a reviewed operation.
- Template names/paths and hostile document content must stay contained and escaped.
- Profiles, full backups, text rollback and source rollback must state the real API scope and recovery limits.
- Query/hash preservation and relative assets must work at the new default and at classic's explicit path.

## Task 1: Integrated tool center

**Files:** New focused `skillsmgr/webui/v2/tool-*.js` components and `tools.css`.

**Interfaces:** A Vue `tool-center` component receives `page`, `records`, `scopes`, and optional exact `target`; emits `changed` after actual writes and `inspect` with an exact record. Root owns shell registration and routing.

- [x] Implement Install registry browse/search/curated/review/commit, legacy runner and folder upload against real APIs; show returned blockers and review identity.
- [x] Implement profile metadata CRUD, membership preview and exact enable-only plan execution; preserve partial outcomes.
- [x] Implement template list/read/create/use, including structured creation metadata and rendered preview.
- [x] Implement Quality hygiene/validate/Doctor/stats and Workspaces with explicit unavailable/degraded evidence and links to exact instances.
- [x] Implement Settings using shared preferences and scoped maintenance actions.
- [x] Implement source-update and source-snapshot review/apply/cancel, plus history and archive/recovery supplements.
- [x] Verify syntax, meaningful API payloads, focus and state guards; report implementation limits for independent review.

## Task 2: V2 shell and library completion

**Files:** `skillsmgr/webui/v2/app.js`, `index.html`, `styles.css`; focused v2 tests.

**Interfaces:** Root mounts `tool-center`, supplies original records and scope descriptors, and refreshes after writes.

- [x] Add Tools navigation/routes and context links while preserving all existing v2 routes.
- [x] Add logical tag filters/actions and exact Instances selection with bounded rendering and visible hidden-selection counts.
- [x] Implement exact batch preview/execute with fixed targets/options and persistent per-target results.
- [x] Complete rich create/edit metadata, template entry points, persistent command discovery and explicit refresh.
- [x] Preserve missing/failed history and trash states; support full archive import without implying all-agent backup.
- [x] Check existing v2 browser contracts and new flows with isolated fixture data.

## Task 3: Template read seam and default routing

**Files:** `skillsmgr/webapp.py`, web routing/template tests, owning API docs and complexity baseline if a newly extracted handler requires it.

- [x] Add the smallest contained read seam needed to preview/use stored templates, using existing template functions rather than a new Store method.
- [x] Test missing, malformed, traversal and symlink-escape template reads.
- [x] After Tasks 1–2 pass integrated parity review, redirect the default document to `/v2/`, preserving queries and browser fragments.
- [x] Serve classic assets under `/classic/`; test HTML, scripts, styles, fonts, redirects and traversal refusal at both interfaces.
- [x] Run `python3 smoke_web.py` after backend changes.

## Task 4: Current-tree acceptance and records

**Files:** `task.md`, `docs/06-progress-log.md`, `docs/08-web-ui.md`, tests and developer browser fixtures as required.

- [x] Independently review against every row of the parity inventory and the hostile-self-review questions in AGENTS.md.
- [x] Run the repository ladder on the current tree: compilation, unittest, both smokes, docs, complexity, design tokens, packaging, JavaScript syntax and CLI help.
- [x] Browser-check the real integrated v2 at desktop/tablet/phone, both themes, keyboard/dialog focus, failure states and representative real filesystem writes in temporary HOME/data roots.
- [x] Record exact evidence and human accessibility limits; mark only verified production capabilities complete.

## Execution ledger

**[NOTE]** The user originally requested design-first work and later explicitly requested production v2 integration followed by default promotion if checks pass. Existing-v2 visual continuity is the binding direction. The mockups remain design evidence, not the implementation. Local implementation will use a task branch and file ownership; no commits or pushes are needed to demonstrate the result.

- Task 1: integrated and independently reviewed; identified defects fixed with regression coverage.
- Task 2: integrated with exact-copy state, bounded rows, logical metadata and reviewed plans.
- Task 3: template read and PATCH clear contracts verified; v2 default and explicit classic routing tested.
- Task 4: final current-tree acceptance complete; evidence and limits follow.

## Acceptance evidence

**[NOTE]** Tests use synthetic data and private temporary HOME/data directories;
real user skill files were not changed. The unauthenticated fixture services
bind only to 127.0.0.1; localhost binding is their only security boundary and
ports must never be forwarded, tunneled or published.

- Final full unittest: **1,386 passed on Python 3.12** (153.285 s),
  `/tmp/skillsmgr-v2-verified-current-tree-unittest.log`.
  The final documentation-only closure also passed the focused docs checks.
- Expanded real Chrome v2 suite: 34 passing scenarios (plus one coverage note),
  including default query/hash redirects, unchanged daily workflows, template
  and profile writes, failed-read retry, settings persistence and all tools at
  320/768/1280 in both themes. The final header was additionally checked at
  16 widths from 320 to 1920px, including breakpoint boundaries. Evidence:
  `/tmp/skillsmgr-v2-final-acceptance-browser/skillsmgr-e2e-gjnb0ipx/results.json`.
- Classic compatibility suite: 38 passing scenarios / 318 assertions. Evidence:
  `/tmp/skillsmgr-v2-acceptance-classic-retry/skillsmgr-classic-fuyvwkac/results.json`.
- Six-viewport classic harness with empty/failed/unavailable fixtures: passed;
  `/tmp/skillsmgr-v2-acceptance-viewport-harness.log`.
- Real isolated API/browser checks additionally exercised logical tags, source
  update commit, retained whole-tree rollback, reviewed local folder import,
  skill/full export-import and diagnostics. The API's outside-managed-roots
  workspace state was rendered correctly; an initial test expected a different
  string and was corrected without changing the product's evidence.
- Both smoke suites, syntax/compilation, CLI help, docs consistency, design-token
  contrast, complexity (733 functions, threshold unchanged), Ruff 0.16.8 and
  Bandit 1.9.4 medium/high scan passed. The one changed baseline tightened 7→6.
- Pinned hash-checked build and wheel/sdist data inspection passed (28 web UI
  assets and 2 bundled skill-example files). Final artifacts are in
  `/tmp/skillsmgr-v2-verified-dist`; inspection is recorded in
  `/tmp/skillsmgr-v2-verified-package.log`.
- [Production screenshot](../../images/v2-tools-2026-11-06.png) shows the
  integrated Tools page with synthetic data, not the historical mockup.

**Review closure.** Folder selection changes cannot reuse pending/completed
approval; exact-copy Edit uses that copy's description and selects its scope;
PATCH explicit clearing works and body-only edits preserve omitted and
non-mapping legacy metadata. Node behavioral and global/codex HTTP roundtrip
tests cover these. Independent Terra re-review found no unresolved defects in
the final fixes.

**Limits.** No live registry fetch/commit or actual external package-runner
execution was performed. Review/transport paths and operation guards are
covered by source/contract tests and fixture browser checks. No human spoken
screen-reader or new real-browser zoom certification is claimed. Source-byte
binding for general batch plans and agent-scope in-app trash restore remain
existing backend limits and are disclosed in the UI. No commit/push or external
publication is part of this task.

**Hostile self-review.** New template paths require canonical names and regular
contained UTF-8 files; untrusted content stays escaped. Empty/missing/failed
responses are distinct, rows/previews are bounded, exact targets/options remain
fixed across preview/apply, double-submit guards cover writes, route/target
changes retire pending source reviews, and errors retain useful recovery paths.
Filesystem authority and index rebuildability remain unchanged. Raw payloads
are secondary details rather than the primary success/error presentation.
