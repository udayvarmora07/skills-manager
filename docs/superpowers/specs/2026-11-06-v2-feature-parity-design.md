# V2 Feature Parity — UI/UX Review Design

**Version 0.1.0**

**AI manifest:** Design proposal and source-backed parity inventory for the
remaining classic-interface features. Companion mockups live in
[prototype-v2-parity](../../../prototype-v2-parity/README.md). This is a review
artifact, not evidence that the production v2 interface implements these flows.

## Status and intent

**[NOTE]** The user requested all remaining v1 features in v2 and explicitly
approved clickable, demo-only mockups before implementation on 2026-11-06.
They delegated design and tooling decisions and requested a considered,
product-specific interface. The Tools-hub navigation is the designer's
recommendation, not a recorded user choice. Visual approval remains pending.

**[NOTE]** Later in the same conversation, the user explicitly directed
production integration into the existing v2 frontend and default promotion
after verification. The [implementation plan](../plans/2026-11-06-v2-feature-parity.md)
records that expanded scope. The original inventory below is the inspected
pre-migration baseline, not a description of the in-progress working tree.

The inspected production baseline was `3b05ae6`. Classic is served at `/` and
v2 at `/v2/`. The production v2 implementation and its boundaries are now recorded in
[the web UI specification](../../08-web-ui.md). The original proposal kept default promotion separate; the user subsequently
authorized implementation and promotion. Classic remains available at `/classic/`.

The user should be able to finish a task without discovering halfway through
that its last step requires the other interface. Preserve the selected v2
visual language while giving every remaining operation a clear location,
honest scope, review step when appropriate, and useful failure state.

## Constraints and design contract

**[SPEC]** Production constraints remain those in [AGENTS.md](../../../AGENTS.md):
filesystem authority, unchanged SQLite schema, Python stdlib backend,
vendored Vue, no build step or new runtime dependencies. This design does not
approve new CLI commands, public Store methods or additional mutation contracts.

**[NOTE]** The selected v2 style is defined by the shipped
[v2 stylesheet](../../../skillsmgr/webui/v2/styles.css) and the
[original final prototype](../../../prototype-final/README.md). The repository
root `DESIGN.md` describes classic's earlier cool-paper/Plex system; its
palette must not silently replace the selected v2 palette.

Preserve warm paper `#f7f5f0`, white working surfaces, ink `#1b1d22`, sparing
terracotta `#b8492a`, Jakarta UI text, Newsreader headings/document text and
IBM Plex Mono paths. Reuse the shipped dark tokens when implementing. Keep
state words beside colour. Prefer rows for comparisons, forms for choices,
and document space for evidence. The content, rather than a dashboard template,
should determine each screen's composition.

Avoid invented health scores, growth charts, decorative metric cards, ambient
animation, gradient panels, tool logos as repeated ornament and marketing copy.
Any sample content in the prototype is visibly labelled as such. No mockup
reads the user's skill files, calls an application API, runs a package manager
or modifies production preferences.

## Approaches considered

**[NOTE]** These were presented during the design discussion. The user then
delegated design judgement and approved clickable mockups; no option is
represented here as an explicit user selection.

| Approach | Benefit | Cost | Disposition |
|---|---|---|---|
| Preserve main navigation; add Tools hub and contextual entry points | Keeps established daily tasks stable; provides a browsable home for secondary tasks | Secondary screens require one additional navigation step | Recommended and used for the review prototype |
| Replace primary navigation with a full sidebar | Makes every area continuously visible; offers room for future growth | Changes the existing v2 composition and reduces working width | Alternative if tool-switching proves frequent in review |
| Put remaining screens in a More menu | Smallest change to the existing shell | Hides the breadth of available work and gives little explanation | Less suitable for onboarding and feature discovery |

## Parity inventory

**[SPEC]** This inventory describes inspected source, not a claim of completed
migration. Read the classic [template](../../../skillsmgr/webui/index.html)
with its [handlers](../../../skillsmgr/webui/app.js), and the
[v2 template](../../../skillsmgr/webui/v2/index.html) with its
[handlers](../../../skillsmgr/webui/v2/app.js). Symbols below are durable
navigation hints rather than copied line numbers.

| Capability | Production v2 today | Proposed v2 home | Classic source evidence |
|---|---|---|---|
| Registry inventory, browse, search, curated sources, stale-cache choice | Classic link only | Install: Registry | `filteredRegistryInventory`, `runRegistry`, `openInstallCenter` |
| Reviewed registry artifact, provenance, validation, risk, expiry and explicit trust | Absent | Install: artifact review | `runRegistry`, `commitRegistryReview` |
| Package-manager runner and generated command | Absent | Install: CLI runner | `openInstall`, `runInstall` |
| New skill from local folder | Absent | Install: Local folder; Skills add action | Classic new/import-folder controls |
| Exact-target local source update and cancellation | Absent | Exact instance: Review update | `prepareUpdateReview`, `applyUpdateReview`, update-review template |
| Retained whole-tree source snapshots and reviewed rollback | Absent | Recovery: Source snapshots | `loadRecoverySnapshots`, `prepareSnapshotReview`, `openRollbackReview` |
| Profile create, describe, preview, delete | Absent | Profiles | `saveProfile`, `previewProfile`, `deleteProfile` |
| Enable-only profile apply over observed exact instances | Absent | Profiles: review enable plan | `openProfileBatch`, `prepareBatch`, `executeBatch` |
| Tags, untagged filter, add/remove tags | Absent | Skills filters and selected-name actions | `setTagFilter`, `updateBatchTags`, `groupTags` |
| Logical Library versus physical Instances view | No explicit instance-table mode | Skills: Cards / Instances | Classic library/instance controls and selected targets |
| Library list/grid preference | Shelf cards only | Skills view preference | Classic library-layout controls |
| Exact-instance batch enable, disable, sync and soft remove | No general batch toolbar | Skills selection and batch review | `openBatch`, `prepareBatch`, `executeBatch` |
| Rich create/edit metadata | V2 create exposes a smaller form | New skill and Edit details | Classic create/edit fields |
| Template list, view, create, use in creation | Absent; new body is hardcoded | Templates; New skill template choice | `openTemplates`, `openNewTemplate`, `saveTemplate` |
| Hygiene severity/search/evidence and instance inspection | Inbox inventory issues only | Quality: Hygiene | `loadQualityHygiene`, `filteredQualityHygieneFindings`, `inspectHygieneInstance` |
| Separate validity, divergence, provenance and size evidence | Some copy evidence in detail/Inbox | Quality: report sections | Classic Quality template and `showQualityReport` |
| Validate selected skill | No dedicated validation action | Skill instance; Quality | Classic validate control/handler |
| Doctor and Stats | No full diagnostic screens | Quality: Diagnostics / Statistics | `openDoctor`, `openStats` |
| Read-only adapters and project resolution | Absent | Workspaces | `loadWorkspaces`, project-explain controls |
| Theme preference | Present as quick cycle | Settings and existing quick control | Classic Settings; v2 `cycleTheme` |
| Text-size and format-locale controls; preference evidence | Text-size CSS exists, settings controls absent; `fmt` uses en-US | Settings | Classic Settings and shared `preferences.js` |
| Rebuild/resync index | Absent | Settings: Index maintenance | Classic command palette and maintenance handlers |
| Global trash restore and empty | Present | Recovery: Trash, with explicit read states | Classic recovery controls; v2 `loadTrash` |
| Persistent history filters and text-snapshot rollback | Read-only recent history only | Recovery: History; skill history link | `openHistory`, `loadHistory`, `rollbackSnapshot` |
| Regular archive export/import | Present | Recovery: Backups | `openImport`, `doImport`; v2 `doImport` |
| Full migration import incl. trash/templates/catalog | Full export exists; import always sends full=0 | Recovery: Backups, explicit archive mode | Classic `openImport(full)`, `doImport` |
| Keyboard command palette and action discovery | Shortcut list only | Shared command palette | Classic command-palette actions |
| First-run explanation and refresh | Home empty guidance; automatic refresh | Home contextual setup; explicit refresh action | Classic scan guide and overview controls |
| Context-window choice, estimator disclosure, largest-scope navigation | Fixed suggested reading-window model | Quality: Statistics; existing Home meter details | Classic scope-budget bars and token-stat controls |

**[NOTE]** Shared features such as document reading, editing, file toggles,
copy comparison, Sync map, Inbox, global trash and ordinary import should be
extended where needed, rather than rebuilt as duplicate screens. A functional
counterpart can use a different layout while preserving the user's capability.

## Proposed information architecture

**[NOTE]** Keep Home, Skills, Sync map, Inbox and Recovery as the established
primary tasks. Replace the generic classic escape hatch with a clearly named
Tools entry. Tools is an index of actions, not another dashboard.

Tools groups Add and organize (Install, Profiles, Templates), Inspect
(Quality, Workspaces), and Maintain (Recovery, Settings). A compact local
navigation accompanies these pages. Recovery remains directly accessible
from the primary navigation as well. Do not duplicate its state.

Contextual links make common tasks shorter: Skills offers New skill, Add
folder, tags and batch actions; skill detail offers validation and exact-copy
update review; Inbox links to evidence in Quality; Quality opens the exact
instance; Recovery offers a fresh source-snapshot review.

On a phone, use a compact application header and menu, then one local
destination selector or scrollable local navigation. Never fit eleven primary
tabs into the viewport. Browser Back restores list/filter context.

## Screen and interaction shot list

### Tools

**[NOTE]** The question is "Where do I go to finish this task?" Use compact
groups of named destinations with one-sentence descriptions. Keep the
existing skill search distinct from searching tools. Show only actual
capabilities, not a promotional feature grid. A first-time user can reach
Install, Profiles, Quality, Workspaces, Templates and Settings here.

### Install

**[NOTE]** Separate Registry, Local folder and CLI runner by source and
execution model. Registry search shows source identity and review actions;
opening a result does not install it. The review presents destination
scope/path, files or change evidence, validation, advisory risk, artifact hash,
expiry, and any returned blockers. Trust is an explicit choice about this
artifact; risk checks are not a safety certification.

Local folder selection must retain a keyboard-operable file picker alongside
drag/drop. Distinguish installing a new folder from updating an existing exact
instance. Existing targets go through source-update review where supported.

The runner exposes package manager, scope/project, agents, skill filter,
copy/link mode, dry-run and list-only options. Render the resulting command
before the execution action. Runner output is process output, not an app
guarantee that an agent now loads the skill. Copying the command is separate
from running it. Network activity occurs only after an explicit user action
in the eventual production implementation.

Include no search results, offline/unavailable registry, cached results,
blocked artifact, expired artifact, existing destination, pending review,
running and partial-result states. Keep a failed review's evidence visible.

### Profiles

**[NOTE]** Use a profile list and a detail/review panel on desktop, and a
list-to-detail flow on a phone. Show name, description, desired skill names and
target scopes. Members distinguish observed, disabled, missing and differing
copies. Never turn a missing member into an implicit install.

Save profile preserves desired metadata. Apply previews an enable-only plan
for observed exact instances. It does not disable other skills. Deleting a
profile removes metadata only; the confirmation must say skill files remain.
For empty profiles or zero eligible targets, offer editing rather than an
enabled apply button. A partial result lists each target and outcome.

### Skills, tags and exact copies

**[NOTE]** Preserve the current shelf and add an explicit Instances view for
physical operations. A table row carries name, consumer/scope, full accessible
path, file state and an exact-copy action. Scope labels must distinguish
global and project observations, rather than assuming every copy is an agent's
single writable folder.

Selection labels say whether they concern logical skill names or physical
copies. "Select shown" never implies selecting unseen records. If a filter
hides selected items, show the hidden-selection count or clear selection with
an explanation. Bounded rendering must not silently reduce an operation to
the first displayed page.

Tags belong to logical names in the manager's catalog. A tag action over
selected copies deduplicates names and states that the tag applies across
their copies. Tags do not edit frontmatter. The bulk operation toolbar offers
enable, disable, sync and soft remove with reviewed targets and policy; purge
is not a bulk operation.

Creation supports name, description, category, version, license, compatibility,
allowed tools, document body and target scope, plus a template choice. Editing
retains the distinction between document content and manager-owned tags.
Unsaved changes require an explicit leave/discard decision.

### Quality

**[NOTE]** Lead with actionable findings and the report's observed scope and
freshness. Hygiene supports severity and evidence search; expanding a finding
shows the reason, exact location and a link to the affected instance. Keep
validity, divergence, provenance and size as separate facts. No aggregate
quality or trust score, and no automatic repair button for a report that is
read-only.

Validate, Doctor and Statistics are secondary report views. Doctor explains
filesystem/index disagreements and links to index maintenance. Preserve a
clear way back from an inspected skill to the originating report. No findings,
no skills, partial observations and unavailable report are distinct states.

### Workspaces

**[NOTE]** Start with a labelled project-path form that submits with Enter.
Show contained project evidence and the read-only consumer/adapter catalog.
Observed paths, declared native settings and unknown effective loading have
separate labels. A successful path check does not claim that a consumer ran
or loaded a skill. Unsupported consumers and unavailable roots get explicit
explanations. An outside-root or redacted path response cannot offer a
fictional activation action.

### Templates

**[NOTE]** List built-in and stored templates with a document preview. Built-in
templates remain read-only; creating a stored template is a separate action.
Use template opens New skill with editable content and an explicit target.
Template creation does not create or activate a skill. Empty, invalid-name,
duplicate-name and unsaved-content states need usable copy.

### Settings

**[NOTE]** Group appearance, reading, regional formats and index maintenance.
Theme offers System/Light/Dark, text size offers Standard/Large, and format
locale offers System/en-US/en-GB/en-IN with a real formatting preview. Regional
formats do not translate the UI. Preferences are shared with classic only in
the eventual implementation; prototype preferences remain isolated.

Show OS dark-mode and reduced-motion observations without implying that the
app can change OS settings. Index maintenance explains rebuild versus resync
and reports results. It does not offer a generic "reset everything" action
or imply a repair of malformed skill documents.

### Source-update review

**[NOTE]** Start from an exact writable instance, carrying its scope and path.
Display candidate tree, changes/diff, validation, advisory risks and recovery
policy before approval. An unavailable, ambiguous or refused-link target must
not become writable merely because its logical name matches another copy.
Cancellation ends the pending review. Expiry, changed target/candidate,
unavailable snapshot and bounded-upload failures retain actionable context.

Whole-tree source rollback starts a fresh validated review. Keep it distinct
from the older text-document snapshot rollback. Do not promise that binary
data, companion files or activation state are restored by a text-only Undo.
The older history action uses a direct rollback endpoint; a confirmation can
explain its scope, but must not claim the source-review guarantees.

### Recovery

**[NOTE]** Use Trash, History, Source snapshots and Backups as local sections.
Trash restore and empty apply to the global manager store. Agent-scope trash
still lacks an in-app restore route: explain the limitation wherever the
user reviews a removal. Never claim that this design supplies that backend.
Only empty-trash purge is part of the current trash surface; no per-item
trash-purge action is introduced.

History filters by skill/scope and shows outcomes, not just success events.
Text snapshots and whole-tree source snapshots have different labels and
recovery disclosures. If history or trash fails to load, show Retry; never
substitute an empty-success message as the current v2 handlers do.

Backups distinguishes ordinary skill archives from a full manager archive.
Full means global skill store, trash, templates and catalog metadata; it is
not a backup of all agent scopes. Import explicitly selects archive mode and
overwrite policy and reports imported/skipped/failed outcomes supported by
the backend. Do not invent an atomic archive preview or all-agent restore.

### Shared search, commands and feedback

**[NOTE]** Retain `/` skill search and `?` help, add a discoverable command
palette for the actions currently exposed by classic, and guard shortcuts
inside forms, links, summaries and dialogs. An action and its destination
must be available through visible UI as well as keyboard shortcuts.

Long-running actions disable duplicate submission and announce progress.
Success identifies what changed; partial success preserves per-target results.
Undo is offered only when the actual operation has a usable recovery artifact.
Actionable errors and recovery links remain available until dismissed.

## Review contracts and awkward scenarios

**[SPEC]** Existing batch and archive contracts are described in
[ADR-006](../../ADR-006-catalog-metadata-and-batch-plans.md); source review is
described in [the source-update plan](../../19-safe-local-source-update-implementation-plan.md)
and [web API specification](../../08-web-ui.md).

| Scenario | Required design behaviour |
|---|---|
| No records, one record, many records | Maintain the screen structure; show one useful next action; bound rendered rows without hiding totals |
| User double-clicks Apply | One pending operation and retained reviewed targets |
| A selection spans scopes or aliases | Review exact resolvable targets and accessible paths; report unresolved/aliased cases |
| File changed after batch preview | Do not claim byte-level binding: current batch hash binds targets/options, not prior bytes or sync source content |
| Source-review target changed | Explain stale review and require a fresh review according to the existing source-review contract |
| A target is already enabled | Report already-set rather than a fabricated new mutation |
| Some batch targets fail | Keep each result, count partial outcomes, and offer only supported retries/recovery |
| User refreshes/disconnects during a write | Do not automatically replay; refresh filesystem evidence and inspect history/snapshots where available |
| A skill name/path contains hostile text | Render as text; never interpret as HTML or instructions; production validation remains server-owned |
| Root, index, history or report is missing/corrupt | Keep unavailable distinct from empty; do not trust SQLite over disk |
| Native setting disagrees with enabled file | Show both facts and unknown effective loading |
| Agent trash cannot be restored in-app | Disclose before remove; no blanket Undo claim |
| Multiple copies tie or differ | Ask which exact copy to use; never call an unversioned copy older/newer |
| Review expired or trust blocked | Disable commit with a visible reason and a refresh/re-review path |

## Accessibility and responsive acceptance

**[NOTE]** Review at desktop 1440px, laptop 1280px, tablet 768px and phone
390/320px. On narrow layouts, stack evidence after the choice it explains,
preserve the identity column, and allow horizontal scrolling only within a
diff or table region when required. Keep the page free of sideways scrolling.

Use one h1 per page, native buttons/links/labels/fieldsets, visible keyboard
focus, minimum 44px touch targets where practical, and text beside status
colour. Dialogs trap focus, support Escape and restore the opener. On route
changes, focus the heading; preserve editing and selection context. Inline
field errors identify the field and correction. Loading retains useful labels
and sets busy state. Reduced motion removes travel and decorative animation.

Check actual font loading, contrast of rendered text/control boundaries in
both themes, large text, forced colours and narrow reflow. A browser pass
cannot substitute for a human perceptual or screen-reader review. Actual
200%/400% browser zoom and assistive-technology checks remain separate from
CSS viewport checks.

## Research used and its limits

**[NOTE]** Skills used: UI/UX Craft, Design Taste Frontend's app-screen
guidance, Better Accessibility and Frontend UI Engineering, with Brainstorming
for design review. Luna audited classic; Terra audited v2 and builds the
prototype. The user's optional Graphify suggestion was considered: no existing
graph was present and the targeted template/handler audit answered the parity
question without building a new graph.

The configured Inspo server was disabled in Codex. Its configured HTTPS MCP
endpoint was queried directly with `initialize`, `tools/list`, one `recommend`,
two `search_screens`, then `get_screen` for three retained references. No MCP
configuration was changed. The initial recommendation returned a poorly fitting
Bandcamp page; it was rejected. Three archived desktop captures were downloaded
to a temporary research directory and visually inspected, rather than trusting
their sometimes inconsistent metadata:

| Inspo capture | Actual observation | Design use and limit |
|---|---|---|
| [Linear Docs, captured 2026-05-12](https://0nme3pk5am3urwa9.public.blob.vercel-storage.com/captures/linear-app--docs/hero.1440.webp) | Persistent grouped local navigation and short task descriptions | Secondary-tool navigation; do not import its dark palette or oversized icon-card spaces |
| [Hugging Face Docs, captured 2026-05-13](https://0nme3pk5am3urwa9.public.blob.vercel-storage.com/captures/huggingface-co--docs/hero.1440.webp) | Named tool families, grouped catalog and search | Discoverable Tools directory; do not import its rainbow taxonomy or copy the card grid |
| [daisyUI installation guide, captured 2026-05-13](https://0nme3pk5am3urwa9.public.blob.vercel-storage.com/captures/daisyui-com--docs-install-lit/hero.1440.webp) | Context stays visible while runnable commands are shown in sequence | Separate choices, generated command and execution; no decorative steps or advertising rail |

These are archived references, not claims about today's live products or
their usability metrics. Their screenshots are linked for provenance and
are not copied into the prototype.

[Carbon forms guidance](https://www.carbondesignsystem.com/building-blocks/core/patterns/forms)
supports grouping related inputs and revealing relevant fields as the user
progresses. [Primer's confirmation dialog guidance](https://primer.style/product/components/confirmation-dialog/)
supports explicit confirmation for consequential actions. The product-specific
scope, recovery disclosures and navigation recommendation are designer
judgements derived from this application's contracts.

## Review and implementation boundary

**[NOTE]** The prototype is a design rehearsal with sample state held in
memory. Demonstrated outcomes are simulations. The real API integration,
race handling, filesystem checks and production regression coverage are later
work, after visual/interaction approval.

Use this review to settle navigation, screen density, terminology, exact-copy
selection, review hierarchy, and failure/recovery presentation. Document any
unclickable edge case honestly in the prototype README. Do not mark the
production parity checklist complete because a prototype screen exists.

**[?]** Agent-scope in-app trash restore requires an additional backend
contract; the current UI must retain the limitation. Making v2 the default
route is a separate maintainer decision. Human design and screen-reader
approval have not been obtained.
