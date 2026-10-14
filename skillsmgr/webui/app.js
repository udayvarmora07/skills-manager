/* Skills Manager web UI — Vue 3 application (no build step). */
"use strict";

/* ------------------------------------------------------------- utilities */

/* domain.js carries the transport, formatting, and state policy. If it failed
 * to load, say so on the page instead of throwing into an empty document —
 * a blank screen with a console trace tells the user nothing. */
const SkillManagerDomain = window.SkillManagerDomain;
if (!SkillManagerDomain) {
  const failure = document.createElement("div");
  failure.setAttribute("role", "alert");
  failure.style.cssText = "margin:2rem;padding:1rem;border:1px solid #a94b20;border-radius:8px;"
    + "font:14px/1.5 system-ui,sans-serif;color:#a94b20;background:#fff;";
  failure.textContent = "skills-manager could not start: domain.js did not load. "
    + "Reload the page; if it persists, the served frontend files are incomplete.";
  document.body.appendChild(failure);
  throw new Error("SkillManagerDomain missing");
}

const {
  api, apiText, apiBlob,
  formatBytes, formatTokens, tokenPctClass, tokenBarWidth,
  renderMarkdown, parseFrontmatter, formatCompat, formatTools,
  groupLogicalSkills, deriveLogicalSkillIdentity, observedIdentity,
  observeRecord, observedStateFor, observedStateKeys, observedSeverity,
} = SkillManagerDomain;

/* ------------------------------------------------------------------ app */

const { createApp, nextTick, h } = Vue;

/* -------------------------------------------------------------- icons

   Icons are a vendored Lucide subset rendered from one inline <symbol>
   sprite (see index.html and static/icons/lucide-sprite.svg).  A symbol
   reference needs an <svg> wrapper, so this renders exactly one: every
   stylesheet rule the old inline icons relied on (`.btn svg`, `.toast svg`,
   `.modal-close svg`, …) keeps matching, and `currentColor` keeps working
   because the sprite has no `stroke` colour of its own.

   `name` is validated against the sprite's own `id` list at registration, so
   a typo renders a visible marker instead of a silently blank box — the
   "declared but never rendered" failure this repository has hit before with a
   vendored font.  */
const ICON_NAMES = Object.freeze(
  Array.from(
    (document.querySelectorAll && document.querySelectorAll(".icon-sprite symbol")) || []
  ).map((s) => s.id.replace(/^i-/, ""))
);
const ICON_SET = new Set(ICON_NAMES);

/* Toast lifetimes. DESIGN-V2 §F says 4s / 8s and these are those numbers, read
 * once so the timer and the markup cannot drift apart.
 *
 * A shrinking countdown hairline was tried here and removed: its 8s duration
 * is not a motion token, and `check_motion()` correctly refuses a finite
 * animation duration that is not one. The control that actually matters for
 * "I could not read that in time" is the dismiss button, which the toast did
 * not have at all. */
const TOAST_MS = 4000;
const TOAST_UNDO_MS = 8000;
const TOAST_MAX = 3;

/* The sentence the toggle reports, for BOTH tenses.
 *
 * It used to be built as `'Skill "' + name + '" ' + action + "d in " + sc` —
 * past tense by concatenation, which holds for exactly two English words and
 * says nothing about the third verb. It also printed `sc`, the wire slug, into
 * a sentence: `disabled in claude-code.` beside a Library row whose chip said
 * `Claude Code`. The record already carries the observed `scope_label`; a
 * record without one falls back to the slug rather than inventing a name,
 * because RULES #12 says the UI states only what was observed.
 */
const TOGGLE_PAST = { disable: "Disabled", enable: "Enabled" };

function toggleOutcome(record, action) {
  const name = (record && record.name) || "";
  const where = String((record && record.scope_label) || (record && record.scope) || "");
  const verb = TOGGLE_PAST[action];
  /* An action with no stated past tense is a NEW verb, and guessing one by
   * appending a letter is how `enable` became `enabled` by luck. Say plainly
   * that it happened rather than ship a malformed word. */
  if (!verb) return 'Skill "' + name + '" ' + action + " in " + where + ".";
  return 'Skill "' + name + '" ' + verb + " in " + where + ".";
}

if (!ICON_NAMES.length) {
  console.error("app-icon: the icon sprite is missing or empty");
}

/* Command-palette group order. DESIGN-V2 §A names Raycast's *grouped* results
   as the reference, so the palette renders headings rather than repeating the
   category on every row — twenty-two rows each carrying the same word
   "Navigation" is a column, not a group.

   The order is declared, not derived, and it is deliberate: what applies to
   what you are looking at comes first (Selected skill), then the verbs that
   change it, then the things you bring in and take out, then diagnostics, and
   Navigation last because it is the one group you can always reach by
   clicking the rail. A category not listed here sorts after the listed ones
   alphabetically, so adding a command can never silently drop it off the end
   of the palette with no heading. */
const COMMAND_GROUP_ORDER = Object.freeze([
  "Selected skill",
  "Skill actions",
  "Transfer",
  "Tools",
  "Navigation",
]);

/* 5.7a — the ONE list of views that render the search field.
   `searchAppliesHere` gates the `/` shortcut AND the keyboard-shortcut
   reference in the help dialog used to hard-code its own four view names.
   Two lists meant the reference could be wrong without anything failing: it
   claimed `/` works "Anywhere" while the key handler deliberately does
   nothing on the five views without a search field (`onKeydown`, below,
   which already said so in a comment nobody reading the dialog would see).

   The guard reads this list and the dialog reads the same list, so adding a
   view to one without the other is now impossible rather than merely
   untested. `searchAppliesHere` keeps its name and its meaning. */
const SEARCH_VIEWS = Object.freeze([
  { id: "skills", label: "Library" },
  { id: "install", label: "Install" },
  { id: "quality", label: "Quality" },
  { id: "trash", label: "Trash" },
]);
const SEARCH_VIEW_IDS = Object.freeze(SEARCH_VIEWS.map((view) => view.id));

/* 5.7b — the subjects on the Settings view, in the order they are shown.
   The side column lists these; each id is the id of the section it jumps to.
   Frozen because it is a constant dressed as component state only so the
   template can `v-for` it. */
const SETTINGS_SECTIONS = Object.freeze([
  { id: "settings-appearance", label: "Theme", hint: "Light, dark, or follow the system" },
  { id: "settings-reading", label: "Text size", hint: "The fixed reading scale" },
  { id: "settings-formats", label: "Regional formats", hint: "Counts, sizes, timestamps" },
  /* 5.7e: the blurb said "The OS signals this app honors", which 5.7c's own
     finding made false — the row below it says the app FOLLOWS the OS and
     cannot change it, and an explicit Light/Dark choice deliberately does not
     honor the OS at all. The blurb now describes the section rather than
     promising the product's behaviour. */
  { id: "settings-accessibility", label: "Accessibility", hint: "The OS settings this app reads" },
  { id: "settings-about", label: "About", hint: "What this app reads, and what it reaches" },
]);

/* 5.8a — every finding `/api/doctor` can report, in one list.
 *
 * The dialog used to read `orphan_dirs` and `stale_rows` by hand, so on the
 * seeded library it said "Issues found." and then showed one orphaned
 * directory while SIX undecodable documents and one conflicting document -
 * the keys that actually explain the word "issues" - were never rendered by
 * anything in the product. A verdict with nothing under it is the honesty
 * failure RULES #12 warns about, and it was invisible because no gate looks
 * at a page's contents.
 *
 * One list, so a key cannot be dropped by omission the way two were: the
 * ledger renders whatever is non-empty and the test asserts this table covers
 * every finding key the REST route can return.
 *
 * `repair` is deliberately NOT here. It is a list of things the backend says
 * it *can* fix, the empty array on the seed says nothing about its item
 * shape, and rendering a guessed row for it would be inventing a capability
 * (API gap, logged in STATE.md).
 */
/* 5.9a — keep the TAIL of a filesystem path, drop the head.
 *
 * A CSS ellipsis keeps the head, which is the half every root on one machine
 * shares: `/tmp/skillsmgr-v2-sandbox/.claude/skills` and
 * `/tmp/skillsmgr-v2-sandbox/.codex/skills` render as the SAME prefix and
 * differ only where the ellipsis eats. The reader is left comparing eight
 * identical strings.
 *
 * A budget, not a segment count: how many characters fit is a fact about the
 * column's width in mono, and `text-overflow: ellipsis` is still there for
 * the case where the tail is too long for whatever width we ended up at. The
 * full value stays on the row's `title`, so nothing is lost - it is moved,
 * not dropped (4.1c's precedent).
 *
 * Returns the input UNCHANGED when it already fits, so a short path is never
 * given an ellipsis it did not need.
 */
const ABOUT_PATH_TAIL_CHARS = 34;
function frontTruncatePath(path) {
  const text = typeof path === "string" ? path : "";
  if (text.length <= ABOUT_PATH_TAIL_CHARS) return text;
  return "…/" + text.slice(-(ABOUT_PATH_TAIL_CHARS - 2));
}

const DOCTOR_FINDINGS = Object.freeze([
  { key: "undecodable_documents", label: "Documents that could not be read", hint: "Skipped when the library is listed" },
  { key: "conflicting_documents", label: "Names claimed by more than one document", hint: "Only the first is indexed" },
  { key: "orphan_dirs", label: "Directories with no skill document", hint: "Not listed as skills" },
  { key: "stale_rows", label: "Index rows with nothing on disk", hint: "Counted by the index, not the library" },
  { key: "filesystem_index_drift", label: "Filesystem and index disagree", hint: "The two are separate sources of truth" },
  { key: "incomplete_transactions", label: "Transactions that did not finish", hint: "Left behind by an interrupted write" },
  { key: "transaction_artifacts", label: "Transaction artifacts", hint: "Written by an interrupted write" },
  { key: "temporary_files", label: "Temporary files left behind", hint: "Not cleaned up by the last run" },
  { key: "stale_snapshots", label: "Snapshots whose source is gone", hint: "A rollback target that cannot be read" },
]);

/* 5.9b — the two remaining wire vocabularies the INVENTORY dialogs painted.
 *
 * `issue.level` and `history.action` are REST values. Printing them meant the
 * Validate dialog showed "error"/"warning" in a badge and the History dialog
 * showed "create"/"trash" in a cell, which is the same defect 5.4c fixed on
 * the Workspaces badge and 5.5 fixed on ten category headings. The wire value
 * is NOT lost: it rides in `data-status`, because here it is the row's
 * identity in a table, not a decorative detail.
 *
 * The keys are the set the store can write (`_history`/`_commit_history`
 * call sites across skillsmgr/), NOT a list observed on one seed, so a run
 * that never produced a `restore` still renders the word. An UNOBSERVED value
 * falls back to the raw string rather than to an invented word (RULES #12).
 */
const HISTORY_ACTIONS = Object.freeze({
  create: "Created",
  add: "Added",
  edit: "Edited",
  update: "Updated",
  disable: "Disabled",
  enable: "Enabled",
  trash: "Trashed",
  restore: "Restored",
  import: "Imported",
});

const VALIDATE_LEVELS = Object.freeze({
  error: "Error",
  warning: "Warning",
  info: "Note",
});

/* An unlisted category sorts after every listed one and ALPHABETICALLY among
   its own kind, so a new command can never fall off the end of the palette
   without a heading. The first version of this returned a numeric rank derived
   from a string hash, and its own comment claimed alphabetical while the code
   produced "Middle, Zebra, Alpha" - a comment describing a behaviour the reader
   could see was different is worse than no comment. `Array#sort` is stable, so
   two commands in the same group keep the order they were declared in. */
function compareCommandGroups(a, b) {
  const ia = COMMAND_GROUP_ORDER.indexOf(a);
  const ib = COMMAND_GROUP_ORDER.indexOf(b);
  if (ia !== -1 && ib !== -1) return ia - ib;
  if (ia !== -1) return -1;
  if (ib !== -1) return 1;
  return String(a || "").localeCompare(String(b || ""));
}

/* How well a command answers a query, best first. 0 means "does not match".
 *
 * WHY RANKING EXISTS AT ALL. The filter used to be one flat `includes()` over
 * label + title + category + keywords, which meant a *prose* sentence could
 * outrank the destination it merely mentions. Typing "library" ran
 * "Export the current skill library" — a download — instead of opening the
 * Library, because that command is declared earlier in the array and Enter
 * always runs the first row. The label is the name the reader typed; the title
 * is a description written for someone who has not typed anything yet. A label
 * match therefore beats a title match, and an exact one beats a prefix one.
 *
 * Ranking happens before grouping, and `Array.prototype.sort` is stable, so a
 * command keeps its declared order inside its own group. */
const COMMAND_MATCH_LABEL_EXACT = 1;
const COMMAND_MATCH_LABEL_PREFIX = 2;
const COMMAND_MATCH_LABEL_CONTAINS = 3;
const COMMAND_MATCH_OTHER = 4;

function commandMatchRank(command, needle) {
  const label = String((command && command.label) || "").toLowerCase();
  if (label === needle) return COMMAND_MATCH_LABEL_EXACT;
  if (label.startsWith(needle)) return COMMAND_MATCH_LABEL_PREFIX;
  if (label.includes(needle)) return COMMAND_MATCH_LABEL_CONTAINS;
  const elsewhere = [command && command.title, command && command.category, command && command.keywords]
    .map((value) => String(value || "").toLowerCase())
    .join(" ");
  return elsewhere.includes(needle) ? COMMAND_MATCH_OTHER : 0;
}

/* Unknown names get a `data-missing-icon` marker instead of a silent blank
   box — an icon that renders as nothing is the failure mode this whole seam
   exists to prevent, so it has to be visible in the DOM and loud in CI. */
const AppIcon = {
  name: "app-icon",
  props: {
    name: { type: String, required: true },
  },
  render() {
    return h("svg", {
      "class": "app-icon",
      viewBox: "0 0 24 24",
      "aria-hidden": "true",
      focusable: "false",
      ...(ICON_SET.has(this.name) ? {} : { "data-missing-icon": this.name }),
    }, this.name ? [h("use", { href: "#i-" + this.name })] : []);
  },
};

/* Registered on the *definition*, never through an `app.component(...)` chain.
   The Node harnesses in tests/ stub `createApp` as `{ mount() {} }` with no
   other methods, so a chained `.component(...)` call would throw a TypeError
   in every one of them the moment the file loads — a regression in five test
   modules to register one component. `components:` is read off the object the
   harness already keeps, so it costs those harnesses nothing. */
/* 5.4 — the one candidate root out of the three shapes `_root_record` accepts.
 * Kept in one place because the previous template inlined this `||` chain in
 * TWO places (the tag soup and the Vue `:key`), where a copy could disagree. */
function rootPath(root) {
  return root.scope || root.relative_path || root.absolute_path || "";
}

/* The evidence link used to read "primary source" for six different vendors —
 * a word that identifies nothing. Show the host it actually points at, and
 * nothing at all when the catalogue recorded no source. */
function adapterSourceHost(url) {
  if (!url) return "";
  try {
    return new URL(url).host;
  } catch (err) {
    return url;
  }
}

function formatCount(n) {
  return typeof n === "number" ? n.toLocaleString("en-US") : String(n);
}

const appOptions = {
  components: { AppIcon },
  data() {
    const savedTheme = localStorage.getItem("skillsmgr-theme");
    const savedLocale = localStorage.getItem("skillsmgr-locale");
    const localeOptions = [
      { value: "en-US", label: "English (United States)" },
      { value: "en-GB", label: "English (United Kingdom)" },
      { value: "en-IN", label: "English (India)" },
    ];
    const localeValues = ["system", ...localeOptions.map((option) => option.value)];
    return {
      view: "overview",
      filter: "",
      query: "",
      /* 5.7c — the OS reduced-motion signal, observed and kept LIVE.
         6.4c deleted this field as a "declared and never read" token. Its test
         grepped `app.js` for the name and did not look at the markup, so it
         deleted the only reader: `index.html`'s Accessibility-evidence row was
         still bound to `prefersReducedMotion`, which then resolved to
         `undefined` and printed "OS has not requested reduced motion" on every
         machine, including the ones that had asked for it. That is RULES #12's
         "a claim about the reader stated as observed", and it survived a green
         gate because no stdlib test renders the template.

         `motionMediaQuery`/`motionMediaHandler` are NOT in `data()` on purpose:
         a MediaQueryList is not reactive state and putting it there would make
         Vue walk it. They are instance fields assigned in `mounted()` and
         cleared in `beforeUnmount()`, mirroring `themeMediaQuery`. */
      prefersReducedMotion: false,
      skills: [],
      allSkills: [],
      trashSkills: [],
      catalog: { version: 1, tags: {}, profiles: {} },
      tagFilter: "",
      selectedKeys: [],
      selectedSnapshot: {},
      batchTagInput: "",
      selectedName: null,
      selected: null,
      selectedTrash: null,
      dataDir: "",
      // Observed, not configured: the authority the page was actually served
      // from. The server binds loopback by default and refuses a non-loopback
      // host, so this is also the address a reader can trust is local. Shown in
      // the status bar so "which server am I talking to" is never a guess.
      serverHost: (typeof location !== "undefined" && location.host) || "unknown",
      scopes: [],
      activeScope: localStorage.getItem("skillsmgr-scope") || "all",
      libraryMode: localStorage.getItem("skillsmgr-library-mode") || "library",
      browseMode: localStorage.getItem("skillsmgr-browse-mode") === "grid" ? "grid" : "list",
      onboardingDismissed: false,
      firstScanGuideDismissed: localStorage.getItem("skillsmgr-first-scan-dismissed") === "1",
      guideExplainConsumer: "codex",
      guideExplainResult: null,
      guideExplainError: null,
      guideExplainLoading: false,
      guideExplainRequest: 0,
      scopeScanFailed: false,
      budget: null,
      budgetWindow: localStorage.getItem("skillsmgr-budget-window") || "claude",
      /* 6.3c — `reading` is the registry panel's OWN flag, and it exists
         because `busy` was the wrong one. `busy` is set by every action in the
         app, so binding the panel's "Reading <source>…" hint to it made this
         panel state something it had not observed: renaming a skill anywhere
         printed "Reading skills.sh…" here (RULES #12 — the UI states observed
         facts). The loading half of the same defect 6.3 fixed for errors. */
      install: { mode: "registry", registryOp: "browse", runner: "npx", source: "", scope: "global", agents: [], skillsFilter: "", copy: false, listOnly: false, page: 0, perPage: 25, view: "all-time", allowStale: false, lastResult: null, review_id: null, review: null, committed: null, error: null, reading: false },
      theme: ["light", "dark", "system"].includes(savedTheme) ? savedTheme : "system",
      resolvedTheme: "light",
      systemTheme: "light",
      textSize: localStorage.getItem("skillsmgr-text-size") === "large" ? "large" : "standard",
      localeOptions,
      locale: localeValues.includes(savedLocale) ? savedLocale : "system",
      /* 5.7b — the settings rail in the side column and the sections it jumps
         to read one list, so a subject cannot be listed and not exist. The
         ids are the section ids in index.html; `jumpToSetting` is the only
         thing that moves focus, and it records the reader's choice in
         `settingsSection` — never a scroll position, which this build cannot
         observe honestly. */
      settingsSections: SETTINGS_SECTIONS,
      settingsSection: SETTINGS_SECTIONS[0].id,
      resolvedLocale: "en-US",
      themeMediaQuery: null,
      themeMediaHandler: null,
      menuOpen: false,
      scopeMenuOpen: false,
      scopeMenuFlip: false,
      busy: false,
      banner: null,
      // Keep the Overview readiness marker absent until the first list
      // request has settled, including the initial render before mounted().
      loadingList: true,
      loadingDetail: false,
      loadingTrash: false,
      /* 6.3 — a read that FAILED is not a read that found nothing. Each of
       * these four used to clear its list in the catch and toast, so the view
       * that owns the list rendered an empty-state sentence making a claim
       * about the disk ("The global trash is empty") that a transport failure
       * cannot support. The error is state, not a transient: it survives until
       * a read actually succeeds, so a reader who looks away does not come
       * back to a page asserting something nobody observed. Same shape
       * `qualityHygieneError` already had. */
      trashError: null,
      loadingRecoverySnapshots: false,
      recoverySnapshots: [],
      recoverySnapshotsError: null,
      loadingHistory: true,
      overviewHistory: [],
      overviewHistoryError: null,
      /* Wall-clock stamp of THIS page's own last settled successful list read.
       * The aggregate /api/skills route carries no server-side observation
       * timestamp (it is stamped per record by Store.get, not by the list), so
       * the age cannot come from the API. Stamped on success only and cleared
       * on failure, so "Scanned 4 min ago" never outlives the read that
       * justified it. */
      lastScanAt: null,
      rescanBusy: false,
      loadingWorkspaces: false,
      workspaces: null,
      workspacesError: null,
      workspaceProject: "",
      qualityHygiene: null,
      qualityHygieneLoading: false,
      qualityHygieneError: null,
      qualitySeverityFilter: "all",
      qualityExpandedFindings: [],
      profileForm: { name: "", description: "", skills: "", targets: "" },
      // 5.3a: which saved profile the form is currently editing, or null for a
      // new one. The backend upserts by name (catalog.save_profile), so editing
      // is a frontend path only — but an editable name field would silently
      // create a SECOND profile and leave the original untouched, which is why
      // the field is locked while this is set.
      profileEditing: null,
      profilePreview: null,
      mobileDetailOpen: false,
      // 4.4: the detail pane is a tab shell. `detailTab` is component state,
      // NOT a route — a reload always lands on Overview, which is the one
      // panel that needs no fetch. `detailHistory.key` is the (scope, name)
      // the rows belong to, so a reader who switches skill mid-flight reads
      // the rows for the skill on screen and not the one they left.
      detailTab: "overview",
      detailHistory: { key: "", rows: [], snapshots: [], loading: false, error: "", loaded: false },
      compactControlsOpen: false,
      // 2.1e2: below 761px the rail IS this drawer (same element, same DOM).
      // `drawerRestoreCompact` remembers what the scope/context disclosure was
      // doing before the drawer opened, so opening the drawer cannot silently
      // change the state 2.1f still owns (`:has(.compact-controls.open)`).
      drawerOpen: false,
      drawerRestoreCompact: false,
      mobileReturnKey: "",
      toasts: [],
      liveAnnouncement: "",
      toastSeq: 0,
      /* Observed, not inferred: the last transport attempt actually failed to
       * reach the server. Set from a real `fetch` rejection and cleared by a
       * successful one -- never from a timer or a route change. */
      offline: false,
      /* id -> timeout handle, so a dismissed toast's pending timer is cleared
       * instead of firing against a list it is no longer in. A leaked timer
       * over a long session is a slow leak with no symptom until the tab dies. */
      toastTimers: {},
      searchTimer: null,
      searchRestore: [],
      listSeq: 0,
      detailSeq: 0,
      modalRestoreFocus: null,
      modalFocusTimer: null,
      commandPaletteTransfer: false,
      commandPaletteQuery: "",
      commandPaletteActiveIndex: 0,
      modals: {
        skill: null,
        remove: null,
        purge: null,
        validate: null,
        doctor: null,
        stats: null,
        history: null,
        templates: null,
        newtemplate: null,
        import: null,
        sync: null,
        batch: null,
        update: null,
        help: null,
        commands: null,
        // 5.3c. Deleting a profile is destructive and irreversible: the four
        // typed fields are the only way back and there is no profile trash.
        // It gets a confirm in the EXISTING vocabulary — the same shape as
        // `modals.remove`, not an `inline confirm()` (RULES #5 bans inline
        // script) and not a second way of asking.
        //
        // The KEY and the `data-modal` attribute must be the SAME STRING.
        // `modalElement()` builds its selector as
        // `[data-modal="' + activeModal + '"]`, and `activeModal` is the key.
        // Naming the attribute `delete-profile` left the dialog fully visible
        // and fully inert: no focus trap, no Escape, focus still on the body.
        // Every other modal in this file has always matched; this one was
        // written by hand and did not, and nothing failed loudly.
        deleteProfile: null,
      },
    };
  },

  computed: {
    /* 5.4 — Workspaces. Every fact below is derived ONCE, here, and the
     * template renders what these return. Three reasons, all measured:
     *
     *  - `tier` and `status` are the SAME boolean twice — adapters.py derives
     *    both from `policy == "ordered"` — so the old rail printed "verified ·
     *    verified" for three of six consumers. One fact, one badge, one word.
     *  - the card grid rendered `candidate_roots`, the FLAT union of `tiers`,
     *    so a root lost the tier that gives it meaning and the tier notes —
     *    the most honest sentences in the payload — were dropped entirely.
     *  - `.tag` caps at 90px, so every candidate path was amputated to
     *    "path unkno…". A path is not a label; truncating it makes the one
     *    fact this view exists to show unreadable.
     */
    workspaceAdapters() {
      return ((this.workspaces && this.workspaces.adapters) || []).filter(Boolean).map((adapter) => {
        const precedence = adapter.precedence || {};
        const documented = precedence.status === "documented";
        const source = precedence.evidence || "";
        return {
          id: adapter.id,
          label: adapter.label || adapter.id,
          documented,
          state: documented ? "documented" : "unknown precedence",
          policy: precedence.policy || "undocumented",
          note: Array.isArray(precedence.notes)
            ? precedence.notes.join(" ")
            : (precedence.notes || ""),
          source,
          sourceHost: adapterSourceHost(source),
          reload: adapter.reload || "reload behavior is undocumented",
          verified: adapter.last_verified || "",
          tiers: (adapter.tiers || []).map((tier, index) => ({
            key: tier.id || tier.label || String(index),
            label: tier.label || tier.id || "Unnamed tier",
            note: tier.note || "",
            roots: (tier.roots || []).map((root, position) => ({
              key: rootPath(root) + "#" + position,
              label: rootPath(root) || "path unknown",
              known: root.path_known !== false && !!rootPath(root),
              recursive: !!root.recursive,
            })),
          })),
        };
      });
    },

    /* "not-requested" is this page's resting state, not a finding. A badge for
     * it (amber, since it is not `accepted`) turned "you have not asked for
     * anything" into a warning the reader has to dismiss. Only an observed
     * state earns a tone; the idle page says one sentence instead. */
    workspaceObservation() {
      const project = (this.workspaces && this.workspaces.project) || {};
      const status = project.status || "not-requested";
      return {
        status,
        requested: status !== "not-requested",
        tone: status === "accepted" ? "badge-ok" : (status === "not-requested" ? "" : "badge-warn"),
        path: project.path || "",
        roots: (project.skills_roots || []).map((root) => ({
          relative: root.relative || root.path || "",
          exists: !!root.exists,
        })),
      };
    },
    /* 5.4c — the badge rendered `{{ workspaceObservation.status }}`, which is
     * the value `adapters.py` names for a MACHINE. Three of the four statuses
     * that can be displayed are already words; `outside-managed-roots` is a
     * compound slug with a hyphen in it, set in a badge where a reader expects
     * a state, next to a sentence that says the same thing in prose.
     *
     * The fallback is the raw value on purpose. This build has observed four
     * statuses; inventing a fifth label for a status it has never seen would be
     * a claim, and RULES #12 says the UI states observed facts. The wire value
     * stays on the badge's `data-status`, so the machine surface a test (or a
     * future reader of the markup) needs never has to be re-derived from text.
     */
    workspaceObservationLabel() {
      const labels = {
        accepted: "accepted",
        missing: "missing",
        inaccessible: "inaccessible",
        "outside-managed-roots": "outside managed roots",
      };
      const status = this.workspaceObservation.status;
      return labels[status] || status;
    },
    workspaceIdleSentence() {
      if (this.loadingWorkspaces && !this.workspaces) return "";
      if (this.workspaceObservation.requested) return "";
      return this.workspaces === null
        ? "Adapter evidence could not be read from this machine."
        : "No project has been observed. Enter a path inside the managed data root to see which skill roots exist there; nothing is read until you do.";
    },
    workspaceObservationSentence() {
      const seen = this.workspaceObservation;
      const here = seen.roots.filter((root) => root.exists).length;
      const parts = {
        accepted: here
          ? here + " of " + formatCount(seen.roots.length) + " candidate roots exist there."
          : "None of the " + seen.roots.length + " candidate roots exist there.",
        missing: "The path does not exist, so nothing under it was read.",
        "outside-managed-roots": "The path is outside the managed data root, so it was not read and its path is withheld.",
        inaccessible: "The path could not be resolved, so its path is withheld.",
      };
      return parts[seen.status] || "";
    },

    filteredSkills() {
      const source = !this.query.trim() && this.skills.length === 0 && this.allSkills.length
        ? this.allSkills
        : this.skills;
      return source.filter((s) => {
        if (this.filter === "active" && s.disabled) return false;
        if (this.filter === "disabled" && !s.disabled) return false;
        if (this.tagFilter === "__untagged" && s.tags && s.tags.length) return false;
        if (this.tagFilter && this.tagFilter !== "__untagged" && !(s.tags || []).includes(this.tagFilter)) return false;
        return true;
      });
    },
    logicalSkills() { return groupLogicalSkills(this.filteredSkills, this.scopes); },
    visibleSkills() { return this.libraryMode === "instances" ? this.filteredSkills : this.logicalSkills; },

    /* The "nothing selected" pane is the widest surface in the app, so it says
     * the thing a reader is actually stuck on: is this an empty library, or a
     * filtered one? Both were previously rendered as the same two sentences,
     * which made a filter that hid every skill indistinguishable from a library
     * that had none. Both branches stay derived from observed state only. */
    paneBlankLede() {
      if (!this.skills.length && !this.query) {
        return "No skill documents are observed on this machine yet. A skill is a folder holding a SKILL.md file.";
      }
      if (this.skills.length && !this.visibleSkills.length) {
        return "Every observed skill in this scope is hidden by the filters below the list. Nothing has been removed.";
      }
      return "Choose a skill in the list to read its document, observed copies and history.";
    },

    /* Every observation the Library rows render, read through the same seam the
     * badges use. The uniform checks below only decide whether a value is
     * *repeated on every row* -- they never re-derive the value itself, and the
     * underlying `malformed` / `decode_error` / `addressable` signals are
     * untouched. When a value is uniform the row keeps it in an `sr-only`
     * span, so suppressing the visual never strips the accessible name.
     *
     * Suppression needs more than one visible row: with a single row every
     * value is trivially "uniform", and hiding that row's only state badge
     * would remove evidence rather than repetition. This is a cached computed,
     * so it costs one pass per list change, not one pass per rendered row. */
    visibleIdentityItems() {
      return this.visibleSkills.length > 1
        ? this.visibleSkills.flatMap((row) => this.identityItems(row))
        : [];
    },

    uniformStateLabel() {
      const items = this.visibleIdentityItems;
      if (!items.length) return null;
      const states = [...new Set(items.map((item) => item.stateLabel))];
      return states.length === 1 && !items.some((item) => item.problem) ? states[0] : null;
    },

    /* A state that is true of every visible row is not per-row information.
     *
     * `uniformStateLabel` already suppressed a uniformly-"Active" list. It
     * deliberately did not suppress a uniformly *problem* state, because
     * hiding a warning is worse than repeating it — but repeating it on 329
     * rows is not the alternative. A badge on 100% of rows is a wall of colour
     * that makes the one row which differs impossible to see, and it trains
     * the reader to stop looking at the badge entirely.
     *
     * So a uniform problem state is suppressed per row and *promoted* to the
     * pane header, where it is stated once with the count. Nothing is lost: the
     * per-row chip stays in the accessibility tree as `sr-only`, exactly as the
     * uniform-active case does.
     *
     * This is a presentation decision and it is deliberately independent of
     * whether the underlying observation is correct. A scope where every skill
     * really is malformed deserves one loud banner; a scope where the
     * observation is wrong also deserves one loud banner — because a reader who
     * sees one banner can act on it, and a reader looking at 329 identical
     * badges cannot.
     */
    uniformProblemLabel() {
      const items = this.visibleIdentityItems;
      if (!items.length) return null;
      if (!items.every((item) => item.problem)) return null;
      const states = [...new Set(items.map((item) => item.stateLabel))];
      return states.length === 1 ? states[0] : null;
    },
    uniformProblemCount() {
      return this.visibleIdentityItems.length;
    },

    /* The promoted banner states the SAME observation as the per-row chip it
     * replaced, so it paints on the same severity ladder. Before this it was
     * hard-wired to the warn ramp, which meant "all four rows are Disabled"
     * still produced an amber alarm box — the task's defect, relocated rather
     * than removed. Derived from the items themselves, never re-classified. */
    uniformSeverity() {
      const items = this.visibleIdentityItems;
      return items.length ? observedSeverity(items.flatMap((item) => item.stateKeys || [])) : "ok";
    },

    selectedLogical() {
      return groupLogicalSkills(this.skills, this.scopes).find((skill) => skill.name === this.selectedName) || null;
    },
    /* 4.4. ONE list, read by three things: the strip renders it, the arrow
       keys index into it, and `selectDetailTab` refuses an id that is not in
       it. A second hand-written list is a second place for the strip and the
       keyboard contract to disagree. The Instances count is the count of what
       the Instances panel will actually render — not the logical total, which
       is the number of rows the reader cannot see from inside a pane. */
    detailTabs() {
      return [
        { id: "overview", label: "Overview" },
        { id: "source", label: "Source" },
        { id: "instances", label: "Instances", count: this.detailInstanceCount },
        { id: "history", label: "History" },
        { id: "quality", label: "Quality" },
      ];
    },
    detailInstances() {
      const logical = this.selectedLogical;
      if (logical && logical.instances && logical.instances.length) return logical.instances;
      return this.selected ? [this.selected] : [];
    },
    detailInstanceCount() {
      return this.detailInstances.length;
    },
    /* Provenance is OPTIONAL and absent for most skills in the seeded library.
       The copy has to name which of the two happened, or a reader reads
       "absent" as "none was recorded" — which is exactly the claim this
       product refuses to make when the server simply did not return it. */
    detailObservation() {
      return this.selected ? observeRecord(this.selected) : {};
    },
    detailProvenance() {
      const p = this.selected && this.selected.registry_provenance;
      if (!p || typeof p !== "object") return "";
      return [p.source, p.slug || p.id].filter(Boolean).join(" · ") || "recorded, with no source or identifier returned";
    },
    tagNames() {
      return [...new Set(Object.values(this.catalog.tags || {}).flat())].sort((a, b) => a.localeCompare(b));
    },
    visibleTargetKeys() {
      const records = this.libraryMode === "library"
        ? this.visibleSkills.flatMap((group) => group.instances || [])
        : this.visibleSkills;
      return records.map((record) => this.targetKey(record));
    },
    selectedTargets() {
      const wanted = new Set(this.selectedKeys);
      /* The record set is NOT stable. `refreshList()` sends a live query to the
         server and REPLACES `this.skills` with the matches, so a key the reader
         had ticked stops resolving — measured: type one character into the
         search box after selecting 3 rows and the bulk bar vanished, taking the
         selection with it, silently and with no undo.

         `selectedSnapshot` is the copy taken at the moment of selection: the
         handful of fields a batch target needs. A selection is a decision the
         reader made about rows they can SEE; narrowing the list afterwards must
         not unmake it. Records that are still loaded win, so the snapshot can
         never serve a staler `disabled` value than the API does. */
      const found = this.skills.filter((record) => wanted.has(this.targetKey(record)));
      if (found.length === wanted.size) return found;
      const seen = new Set(found.map((record) => this.targetKey(record)));
      const restored = this.selectedKeys
        .filter((key) => !seen.has(key))
        .map((key) => this.selectedSnapshot[key])
        .filter(Boolean);
      return found.concat(restored);
    },
    selectedCount() { return this.selectedTargets.length; },
    /* What "Tags" will ACTUALLY write, stated before it writes it.

       The bar counts exact physical instances; `/api/catalog/tags` is keyed by
       LOGICAL NAME (the catalog is one dict of name -> tags, catalog.py
       `update_tags`), so selecting one copy of a three-copy skill writes all
       three. The REST contract is frozen and the catalog has no per-instance
       key to address, so the fix is not a different request -- it is the
       sentence. This counts, per distinct name in the selection, how many
       loaded instances carry it, and the panel renders it. Measured off
       `this.skills`, the same source `selectedTargets` reads, so the two can
       never disagree about which instances exist.

       `widened` is the honest summary: true when the selection spans fewer
       names than it does instances, i.e. pressing Tags does more than the bar
       advertised. */
    batchTagPlan() {
      const counts = new Map();
      for (const record of this.selectedTargets) {
        if (record && record.name) counts.set(record.name, 0);
      }
      for (const record of this.skills) {
        if (record && record.name && counts.has(record.name)) {
          counts.set(record.name, counts.get(record.name) + 1);
        }
      }
      const entries = [...counts.keys()]
        .sort((a, b) => a.localeCompare(b))
        .map((name) => ({ name, copies: counts.get(name) }));
      const instanceCount = this.selectedTargets.length;
      return {
        names: entries.map((entry) => entry.name),
        entries,
        widened: entries.length !== instanceCount,
      };
    },
    /* A target that came from `selectedSnapshot` is a row the reader ticked
       before the list was re-queried and is no longer in the loaded set, so its
       path and `disabled` flag are the values observed AT SELECTION TIME, not
       the filesystem's current answer. Loaded records always win (see
       `selectedTargets`), which bounds this to targets that fell out of the
       loaded set entirely -- but the dialog reviews a plan built from those
       stale fields, so it has to say which rows it cannot re-check.

       A COMPUTED, not a method: the template reads `batchStaleTargets.length`,
       and a method of the same name would answer the number of its own
       parameters -- 0, every time, which renders a false "nothing is stale". */
    batchStaleTargets() {
      const loaded = new Set(this.skills.map((record) => this.targetKey(record)));
      return (this.modals.batch ? this.modals.batch.targets : [])
        .filter((target) => !loaded.has(this.targetKey(target)));
    },
    profileObservedCount() {
      return (this.profilePreview && this.profilePreview.members || [])
        .reduce((count, member) => count + (member.instances || []).length, 0);
    },
    /* 5.3a — the editor's heading and verb follow profileEditing. These are
       computed, not inline template ternaries, so the heading, the primary
       button and the toast cannot disagree about what the form is doing. */
    profileFormTitle() {
      return this.profileEditing ? `Edit ${this.profileEditing}` : "New profile";
    },
    profileSaveLabel() {
      /* 6.5c — §I asks every state to leave one verb-led action, and this
       * label was the reason the Profiles view measured as STRANDED: with no
       * profiles on disk the only control in the view read "Save profile",
       * which is not an action a reader can start and implies something was
       * already saved. The heading beside it already said "New profile", so
       * the form and its own button disagreed about what pressing it does.
       * Nothing about the create path changed — `saveProfile` has always
       * created when `profileEditing` is null; this only names it. */
      return this.profileEditing ? "Save changes" : "Create profile";
    },
    profileSaveOutcome() {
      return this.profileEditing
        ? `Profile ${this.profileEditing} updated.`
        : `Profile ${(this.profileForm.name || "").trim()} saved.`;
    },
    profileUnresolvedMembers() {
      return (this.profilePreview && this.profilePreview.members || [])
        .filter((member) => member.state === "missing" || member.state === "divergent");
    },
    allVisibleSelected() {
      return this.visibleTargetKeys.length > 0 && this.visibleTargetKeys.every((key) => this.selectedKeys.includes(key));
    },
    onboardingVisible() {
      return this.view === "skills"
        && this.activeScope === "all"
        && !this.loadingList
        && this.skills.length === 0
        && !this.query.trim()
        && !this.filter
        && !this.onboardingDismissed;
    },
    onboardingRoots() {
      return (this.scopes || []).filter((scope) => scope.exists);
    },
    firstScanGuideVisible() {
      // An empty library already has a first-run card carrying its own
      // actions; a guide above it would repeat the message and offer a
      // disabled primary. The guide appears once there is something to
      // observe — which is also the only time any of its three marks
      // can carry a non-empty fact.
      return this.view === "overview" && !this.firstScanGuideDismissed
        && this.overviewInstanceCount > 0;
    },
    // Three marks, not three step cards. Nothing the reader can do completes
    // these, so each reports an OBSERVATION with an explicit unknown when the
    // scan could not settle. `unknown` is a first-class state on purpose: the
    // previous version let a failed root read fall through to prose that read
    // like a completed scan.
    firstScanMarks() {
      const n = this.overviewInstanceCount;
      const divergent = this.overviewDivergentGroups.length;
      const roots = this.guideRoots.length;
      const missing = this.guideUnavailableRoots.length;
      const sample = this.guideSampleRecord;
      if (this.loadingList) {
        return [
          { id: "roots", state: "pending", label: "Roots", detail: "pending" },
          { id: "instance", state: "pending", label: "Instance", detail: "pending" },
          { id: "conflicts", state: "pending", label: "Conflicts", detail: "pending" }
        ];
      }
      if (this.banner) {
        return [
          { id: "roots", state: "unknown", label: "Roots", detail: "scan failed" },
          { id: "instance", state: "unknown", label: "Instance", detail: "scan failed" },
          { id: "conflicts", state: "unknown", label: "Conflicts", detail: "scan failed" }
        ];
      }
      return [
        {
          id: "roots",
          state: this.scopeScanFailed ? "unknown" : missing ? "warn" : "ok",
          label: "Roots",
          detail: this.scopeScanFailed
            ? "root details unavailable"
            : `${this.formatNumber(roots)} detected${missing ? `, ${this.formatNumber(missing)} missing` : ""}`
        },
        {
          id: "instance",
          state: sample ? "ok" : "warn",
          label: "Instance",
          detail: sample ? sample.name : "none readable"
        },
        {
          id: "conflicts",
          state: this.scopeScanFailed ? "unknown" : divergent ? "warn" : "ok",
          label: "Conflicts",
          detail: divergent ? `${this.formatNumber(divergent)} divergent` : "none observed"
        }
      ];
    },
    guideRoots() {
      return (this.scopes || []).filter((scope) => scope.exists);
    },
    guideUnavailableRoots() {
      return (this.scopes || []).filter((scope) => ["missing", "unsupported"].includes(scope.availability));
    },
    guideSampleRecord() {
      return this.overviewRecords.find((record) =>
        !record.malformed && !record.decode_error && record.addressable !== false) || this.overviewRecords[0] || null;
    },
    guideSampleIsProject() {
      return !!(this.guideSampleRecord && (this.scopes || []).some((scope) =>
        scope.id === this.guideSampleRecord.scope && scope.kind === "project"));
    },
    guidePreviewRecord() {
      return this.overviewRecords.find((record) =>
        !record.malformed && !record.decode_error && record.addressable !== false
        && record.root_availability === "writable"
        && record.scope && record.scope !== "all"
        && (record.physical_path || record.path) && record.physical_root) || null;
    },
    guideExplainSkill() {
      const name = this.guideSampleRecord && this.guideSampleRecord.name;
      return name && this.guideExplainResult && this.guideExplainResult.skills
        ? this.guideExplainResult.skills[name] || null
        : null;
    },
    filteredTrash() {
      const q = this.query.trim().toLowerCase();
      if (!q) return this.trashSkills;
      return this.trashSkills.filter((t) => t.name.toLowerCase().includes(q));
    },
    totalCount() { return this.skills.length; },
    activeCount() { return this.skills.filter((s) => !s.disabled).length; },
    disabledCount() { return this.skills.filter((s) => s.disabled).length; },
    trashCount() { return this.trashSkills.length; },
    /* 7.4e1 — the view-level back button picked its label from a two-case
     * ternary (`view === 'quality' ? 'Back to Quality' : 'Back to Library'`),
     * and it renders on every view EXCEPT the Library — so on Trash, Recovery,
     * Profiles, Install, Workspaces and Settings, the control that returns the
     * reader to that view's own list claimed to return them to the Library.
     * Below 760px the list and the detail are one screen at a time, so it is
     * the only way back and a wrong label is the whole affordance.
     *
     * The view NAME list already exists: the palette's navigation rows. 5.7a
     * established `SEARCH_VIEWS` as the single list behind the `/` claim for
     * the same reason — the guard and the prose cannot drift. Deriving from the
     * rows means a tenth view cannot arrive with a wrong label by omission.
     * No matching row means we do not invent a destination: "Back", and the
     * stdlib suite fails because a rendered view has no palette row. */
    mobileBackLabel() {
      const row = this.commandPaletteCommands.find(
        (c) => c.action === "switchView" && c.args && c.args[0] === this.view);
      return row ? "Back to " + row.label : "Back";
    },
    /* 7.4e2 — the facts the blank pane states, all derived from the records
     * `/api/trash` returned. `trashSkills` is [] both when the trash is empty
     * and when a read failed, and the error branch in the pane OUTRANKS the
     * empty claim (6.3), so a failed read cannot reach this copy asserting
     * there is nothing to restore. Nothing here is claimed about agent-scope
     * copies: there is no endpoint for them, and `.scope-note` beside this
     * block already says they are not counted. */
    trashBlankLede() {
      if (!this.trashSkills.length) {
        return "Nothing is in the global trash on this machine.";
      }
      if (this.query && !this.filteredTrash.length) {
        return "No trashed skill matches this search, and nothing has been removed. "
          + "Clear it to see all " + this.trashCount + ".";
      }
      if (!this.trashSkills.length) return "";
      return "Choose a trashed skill in the list to see where it was removed to, "
        + "and to restore it.";
    },
    trashTotalBytes() {
      return this.trashSkills.reduce((sum, t) => sum + (Number(t.size_bytes) || 0), 0);
    },
    trashRemovedRange() {
      const times = this.trashSkills
        .map((t) => new Date(t.modified).getTime())
        .filter((n) => Number.isFinite(n));
      if (!times.length) return "";
      const first = this.formatDate(new Date(Math.min(...times)));
      const last = this.formatDate(new Date(Math.max(...times)));
      /* Every removal can share one timestamp -- the seed's do -- and "X \u2013 X"
       * is noise the reader has to decode. A range that spans nothing is one
       * date. 2.1c's rule: a value shared by every row is stated once. */
      return first === last ? first : first + " \u2013 " + last;
    },
    /**
     * 5.6a — `query` is NOT cleared by `switchView` and the search field does
     * not render on this view (`searchAppliesHere` excludes recovery), so a
     * query typed in Library kept narrowing this list with nothing on screen
     * to say so. A value every row shares and the reader cannot see is stated
     * once, here, or not at all (2.1c's rule). `null` when no filter is
     * active, so the sentence costs no space in the common case.
     */
    recoveryTrashFilterNote() {
      const q = (this.query || "").trim();
      if (!q || !this.trashSkills.length) return null;
      if (!this.filteredTrash.length) return null;
      return "Showing " + this.formatNumber(this.filteredTrash.length)
        + " of " + this.formatNumber(this.trashCount)
        + " trashed item" + (this.trashCount === 1 ? "" : "s")
        + " for “" + q + "”.";
    },
    allScopesCount() { return (this.scopes || []).reduce((n, s) => n + (s.count || 0), 0); },

    /* Per-scope share of one context window, largest first.
     *
     * This is the most operationally consequential thing the tool observes: an
     * agent that loads every skill under a root cannot fit them all. Every
     * number here is arithmetic over what `/api/scopes` and `/api/stats`
     * already report — nothing is inferred about which copy an agent would
     * actually load, because the tool deliberately has no resolver.
     *
     * The axis runs to BUDGET_AXIS_MAX rather than 100 so that 111% and 121%
     * render as visibly different bars. On a 0-100% axis both would clamp to a
     * full bar and the chart would hide its own point.
     */
    scopeBudgetRows() {
      const windowTokens = (this.budget && this.budget.window_tokens) || 0;
      const rows = (this.scopes || [])
        .filter(Boolean)
        .map((s) => {
          const tokens = s.tokens || 0;
          const pct = windowTokens > 0 ? (tokens / windowTokens) * 100 : 0;
          return {
            id: s.id,
            label: s.label,
            tokens,
            count: s.count || 0,
            pct,
            // Displayed figures are whole percent. A root at 121.061% and one
            // at 118.996% are the same size bar; three decimals imply a
            // precision the chars/4 estimator does not have.
            pctRounded: Math.round(pct),
            over: pct > 100,
          };
        })
        .sort((a, b) => b.pct - a.pct);
      return rows;
    },
    overBudgetScopeCount() {
      return this.scopeBudgetRows.filter((r) => r.over).length;
    },
    budgetAxisMax() {
      const peak = this.scopeBudgetRows.reduce((m, r) => Math.max(m, r.pct), 0);
      return Math.max(125, Math.ceil(peak / 25) * 25);
    },
    scopeThresholdPos() {
      const max = this.budgetAxisMax || 125;
      return Math.max(0, Math.min(100, (100 / max) * 100)).toFixed(2) + "%";
    },
    selectedDisabled() {
      return this.selected ? !!this.selected.disabled : false;
    },
    updateTargetAvailable() {
      const target = this.selected;
      return !!(target
        && target.name
        && target.scope
        && target.scope !== "all"
        && target.addressable !== false
        && target.root_availability === "writable"
        && (target.physical_path || target.path)
        && target.physical_root);
    },
    activeModal() {
      return Object.keys(this.modals).find((key) => this.modals[key]) || null;
    },
    commandPaletteCommands() {
      const commands = [
        { id: "nav-overview", label: "Overview", title: "Open Overview", category: "Navigation", keywords: "dashboard home", action: "switchView", args: ["overview"], focusDestination: true },
        { id: "nav-library", label: "Library", title: "Open Library", category: "Navigation", keywords: "skills browse", action: "switchView", args: ["skills"], focusDestination: true },
        { id: "nav-profiles", label: "Profiles", title: "Open Profiles", category: "Navigation", keywords: "catalog groups", action: "switchView", args: ["profiles"], focusDestination: true },
        /* 5.2d: the runner keywords live here now. There was a second row,
           `install-workflow` ("Install via a runner or registry", Transfer),
           which since 5.2b deleted the dialog has done exactly what this one
           does — navigate to this page. Two rows for one destination means the
           palette offers the reader a choice that does not exist, and because
           2.2 ranks Transfer first the *Transfer* copy was drawn above the
           Navigation one, so Enter on "install" highlighted a row whose label
           names a thing the product no longer has a separate surface for.
           `openInstall` is the Overview button's name, not a second route. */
        { id: "nav-install", label: "Install", title: "Open Install", category: "Navigation", keywords: "workflow registry runner npx pnpm bunx", action: "switchView", args: ["install"], focusDestination: true },
        { id: "nav-recovery", label: "Recovery", title: "Open Recovery", category: "Navigation", keywords: "backup snapshot rollback archive history", action: "switchView", args: ["recovery"], focusDestination: true },
        /* 7.4c: `nav-recovery` carried the keyword `trash`, which is WHY the
           missing door survived review — typing "trash" in the palette did
           something, so the string was present and the destination was not.
           Now that a Trash view is real it has its own row, and Recovery keeps
           the words that actually name it. Ranking is by the shared
           `_palette_module` scorer, so an exact label match on "Trash" beats a
           keyword hit on "Recovery" without either row needing to know that. */
        { id: "nav-trash", label: "Trash", title: "Open Trash", category: "Navigation", keywords: "deleted removed restore empty purge bin", action: "switchView", args: ["trash"], focusDestination: true },
        { id: "nav-workspaces", label: "Workspaces", title: "Open Workspaces", category: "Navigation", keywords: "projects adapters", action: "switchView", args: ["workspaces"], focusDestination: true },
        { id: "nav-quality", label: "Quality", title: "Open Quality", category: "Navigation", keywords: "evidence health", action: "switchView", args: ["quality"], focusDestination: true },
        { id: "nav-settings", label: "Settings", title: "Open Settings", category: "Navigation", keywords: "preferences accessibility theme", action: "switchView", args: ["settings"], focusDestination: true },
        { id: "create-skill", label: "Create skill", title: "Create a new skill", category: "Skill actions", keywords: "new add author", action: "openCreate", focusDestination: true },
        { id: "add-folder", label: "Add folder", title: "Add skills from a folder", category: "Skill actions", keywords: "import directory upload", action: "openAdd" },
        { id: "import-archive", label: "Import archive", title: "Import a skills archive", category: "Transfer", keywords: "archive tar zip migration", action: "openImport", focusDestination: true },
        { id: "export-archive", label: "Export archive", title: "Export the current skill library", category: "Transfer", keywords: "download backup archive", action: "exportArchive" },
        { id: "full-export", label: "Full migration export", title: "Export skills, trash, and templates", category: "Transfer", keywords: "full backup migration archive", action: "exportArchive", args: [true] },
        { id: "templates", label: "Templates", title: "View templates", category: "Tools", keywords: "starter files", action: "openTemplates", focusDestination: true },
        { id: "new-template", label: "New template", title: "Create a template", category: "Tools", keywords: "starter create", action: "openNewTemplate", focusDestination: true },
        { id: "doctor", label: "Doctor", title: "Inspect filesystem and index health", category: "Tools", keywords: "diagnostic integrity", action: "openDoctor", focusDestination: true },
        { id: "stats", label: "Stats", title: "View skill statistics", category: "Tools", keywords: "metrics tokens", action: "openStats", focusDestination: true },
        { id: "history", label: "History", title: "View skill history", category: "Tools", keywords: "snapshots rollback", action: "openHistory", focusDestination: true },
        { id: "refresh", label: "Refresh", title: "Refresh skills and scope data", category: "Tools", keywords: "reload update", action: "refreshCommand" },
        { id: "rebuild", label: "Rebuild", title: "Rebuild the local index", category: "Tools", keywords: "database index", action: "rebuildIndex" },
        { id: "resync", label: "Resync", title: "Resync the local index", category: "Tools", keywords: "database index", action: "resyncIndex" },
        { id: "shortcuts", label: "Keyboard shortcuts", title: "Show every keyboard shortcut", category: "Tools", keywords: "help keys kbd reference", action: "openShortcutsHelp", focusDestination: true, keys: ["?"] },
        { id: "focus-search", label: "Focus search", title: "Jump to the skill search field", category: "Navigation", keywords: "filter find library", action: "focusLibrarySearch", focusDestination: true, keys: ["/"] },
      ];
      const selectedAvailable = this.view === "skills" && !!this.selectedName && !!this.selected;
      if (selectedAvailable) {
        commands.push(
          { id: "selected-edit", label: "Edit", title: `Edit ${this.selectedName}`, category: "Selected skill", keywords: "modify change", action: "openEdit", focusDestination: true },
          { id: "selected-validate", label: "Validate", title: `Validate ${this.selectedName}`, category: "Selected skill", keywords: "check lint", action: "openValidate", focusDestination: true },
          { id: "selected-toggle", label: this.selectedDisabled ? "Enable" : "Disable", title: `${this.selectedDisabled ? "Enable" : "Disable"} ${this.selectedName}`, category: "Selected skill", keywords: "active disabled toggle", action: "toggleSelected" },
          { id: "selected-sync", label: "Sync", title: `Sync ${this.selectedName} to agents`, category: "Selected skill", keywords: "copy agents scopes", action: "openSync", focusDestination: true },
          ...(this.updateTargetAvailable ? [{ id: "selected-update", label: "Update from folder", title: `Review a local update for ${this.selectedName}`, category: "Selected skill", keywords: "source diff replace review rollback", action: "openUpdate", focusDestination: true }] : []),
          { id: "selected-remove", label: "Remove", title: `Remove ${this.selectedName}`, category: "Selected skill", keywords: "trash delete", action: "removeSelected", focusDestination: true },
        );
      }
      return commands;
    },
    filteredCommandPaletteCommands() {
      const needle = this.commandPaletteQuery.trim().toLowerCase();
      const matches = !needle
        ? this.commandPaletteCommands.slice()
        : this.commandPaletteCommands.filter((command) => commandMatchRank(command, needle) > 0);
      /* Group order is applied HERE, once, so there is exactly one ordering in
         the app. Grouping the results afterwards instead would make the drawn
         order differ from the order ArrowDown walks — a palette that highlights
         a row the reader cannot see is worse than an ungrouped one, and the
         bug would only appear for a query that matched rows in two groups.

         The drawn order is left exactly as 2.2 left it. An earlier attempt also
         ranked the drawn rows by name match; it was measured, found to change no
         observable result for any query in the real command set, and deleted
         rather than shipped as a second ordering that reads as behaviour. What
         was never decided is which row Enter runs — that is
         `bestCommandPaletteIndex` below. */
      return matches.sort((a, b) => compareCommandGroups(a.category, b.category));
    },
    /* Pure presentation over the ordered list above: consecutive runs of the
       same category become one heading each. There is no index math here and
       no second cursor, because there is only one order to present. */
    commandPaletteGroups() {
      const groups = [];
      for (const command of this.filteredCommandPaletteCommands) {
        let group = groups[groups.length - 1];
        if (!group || group.category !== command.category) {
          group = {
            id: "command-group-" + command.category.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
            category: command.category,
            commands: [],
          };
          groups.push(group);
        }
        group.commands.push(command);
      }
      return groups;
    },
    commandPaletteActiveCommand() {
      return this.filteredCommandPaletteCommands[this.commandPaletteActiveIndex] || null;
    },
    /* The row Enter runs when a query is typed.
     *
     * This is deliberately NOT the first drawn row. 2.2 groups the results
     * (Transfer before Navigation, because the rail always offers navigation),
     * so for the query "library" the drawn order is "Export the current skill
     * library" and then "Library" — and Enter ran the download. The reader
     * typed a name; the name is a label; the active row starts on the best
     * label match wherever it is drawn. Group order, the drawn order, Home/End
     * and ArrowDown all behave exactly as they did. */
    bestCommandPaletteIndex() {
      const commands = this.filteredCommandPaletteCommands;
      if (!commands.length) return 0;
      const needle = this.commandPaletteQuery.trim().toLowerCase();
      if (!needle) return 0;
      let best = 0;
      let bestRank = commandMatchRank(commands[0], needle);
      for (let index = 1; index < commands.length; index += 1) {
        const rank = commandMatchRank(commands[index], needle);
        if (rank > 0 && rank < bestRank) { best = index; bestRank = rank; }
      }
      return best;
    },
    commandPaletteStatus() {
      const count = this.filteredCommandPaletteCommands.length;
      return count ? `${count} command${count === 1 ? "" : "s"} available` : "No commands found. Try a different search term.";
    },
    overviewRecords() {
      return this.allSkills.length ? this.allSkills : this.skills;
    },
    overviewLogicalSkills() {
      return groupLogicalSkills(this.overviewRecords, this.scopes);
    },
    overviewLogicalCount() {
      return this.overviewLogicalSkills.length;
    },
    overviewInstanceCount() {
      return this.overviewRecords.length;
    },
    overviewActiveCount() {
      return this.overviewRecords.filter((record) => observedStateFor(record) === "active").length;
    },
    overviewDisabledCount() {
      return this.overviewRecords.filter((record) => observeRecord(record).isDisabled).length;
    },
    overviewDivergentGroups() {
      return this.overviewLogicalSkills.filter((group) => !!group.divergent);
    },
    overviewMalformedCount() {
      return this.overviewRecords.filter((record) => {
        const observed = observeRecord(record);
        /* A refused symlink is reported on its own line; counting it here as
         * "malformed" would both misname it and let the two totals disagree. */
        return observed.malformedDocument && !observed.linkEscape;
      }).length;
    },
    overviewLinkedCount() {
      return this.overviewRecords.filter((record) => observeRecord(record).linkEscape).length;
    },
    overviewUnaddressableCount() {
      return this.overviewRecords.filter((record) => observeRecord(record).notAddressable).length;
    },
    overviewInvalidRecords() {
      return this.overviewRecords.filter((record) => {
        const observed = observeRecord(record);
        return observed.malformedDocument || observed.notAddressable;
      });
    },
    overviewAttention() {
      const items = [];
      if (this.overviewInvalidRecords.length) {
        const records = this.overviewInvalidRecords;
        const linked = records.filter((record) => observeRecord(record).linkEscape).length;
        const other = records.length - linked;
        const parts = [];
        if (linked) {
          parts.push(`${this.formatNumber(linked)} instance${linked === 1 ? " is" : "s are"} a symlink the tool refuses to follow because its target sits outside that scope's root`);
        }
        if (other) {
          parts.push(`${this.formatNumber(other)} instance${other === 1 ? " is" : "s are"} unaddressable or unreadable`);
        }
        items.push({
          key: "observed-invalid",
          /* The title names both observations because they have different
           * remedies, and "malformed" was wrong for a symlink: the document is
           * not corrupt, it is unreachable on purpose. */
          title: linked && !other
            ? "Skills linked outside their scope root"
            : "Review unreadable or unaddressable entries",
          detail: `${parts.join("; ")}.`,
          action: "Review in Library",
        });
      }
      if (this.overviewDivergentGroups.length) {
        items.push({
          key: "divergent",
          title: "Resolve divergent copies",
          detail: `${this.overviewDivergentGroups.length} logical skill${this.overviewDivergentGroups.length === 1 ? " has" : "s have"} unequal observed instances.`,
          action: "Inspect copies",
        });
      }
      if (this.overviewDisabledCount) {
        items.push({
          key: "disabled",
          title: "Review disabled instances",
          detail: `${this.overviewDisabledCount} observed instance${this.overviewDisabledCount === 1 ? " is" : "s are"} disabled and will be skipped by its consumer.`,
          action: "Show disabled",
        });
      }
      if (this.trashCount) {
        items.push({
          key: "recovery",
          title: "Recover removed skills",
          detail: `${this.trashCount} skill${this.trashCount === 1 ? " is" : "s are"} available in global trash.`,
          action: "Open recovery",
        });
      }
      return items;
    },
    overviewAttentionCount() {
      return this.overviewAttention.length;
    },
    scannedAgoLabel() {
      /* Null until a settled successful read exists, so a pending or failed
       * load shows no age at all rather than a stale one. Rounded down to the
       * minute; "just now" covers the first 45s so the label does not churn
       * on every navigation. */
      if (!this.lastScanAt) return null;
      const seconds = Math.floor((Date.now() - this.lastScanAt) / 1000);
      if (seconds < 0) return null;
      if (seconds < 45) return "just now";
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes} min ago`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
      const days = Math.floor(hours / 24);
      return `${days} day${days === 1 ? "" : "s"} ago`;
    },
    themeModeLabel() {
      return this.theme === "system" ? "System" : (this.theme === "dark" ? "Dark" : "Light");
    },
    themeToggleTitle() {
      const next = this.theme === "system" ? "light" : (this.theme === "light" ? "dark" : "system");
      const nextLabel = next === "system" ? "system" : next;
      return `Theme: ${this.themeModeLabel} (currently ${this.resolvedTheme}). Activate to use ${nextLabel} theme.`;
    },
    systemThemeLabel() {
      return this.systemTheme === "dark" ? "dark" : "light";
    },
    /* 5.7c. The two evidence rows used to be pasted into the template:
       `{{ systemThemeLabel }} dark-mode preference` renders "light
       dark-mode preference", which is a label glued to a noun rather than a
       sentence. The value is an OBSERVED OS preference, so the `<dt>` names
       what the value IS and the `<dd>` is the value — the same shape every
       other fact on this branch uses (4.4's `.detail-facts`, 5.9a's About).
       Same reason `prefersReducedMotion` gets a computed of its own: it is
       one OS signal and it now has two readers (the evidence row, and the
       sentence below it that says what the app does about it). */
    reducedMotionLabel() {
      return this.prefersReducedMotion ? "Reduced, honored" : "Off, not requested";
    },
    /* --- 5.1 Install center -------------------------------------------------
       Three READ sources over one `POST /api/install` route. All the machinery
       existed before this view — `install.registryOp`, `runRegistry`,
       `install.lastResult` — and none of it rendered, so a reader who clicked
       Install in the rail saw the global search field promising "Search
       registry sources…" above an empty pane.

       **[NOTE] Rows are read DEFENSIVELY, because the payload is not ours.**
       `RegistryClient.browse`/`curated` validate only that the response carries
       a list under `data` (`_validate_listing`, registry.py:488); every field
       INSIDE a row is whatever the registry chose to send, and `_validate_
       public_search` copies the public route's objects through untouched. So a
       row is normalised here, once, instead of six optional chains in the
       template. */
    installSources() {
      return [
        { id: "curated", label: "Curated" },
        { id: "browse", label: "Browse" },
        { id: "search", label: "Search" },
      ];
    },
    /* 5.1b — the two workflows, which are NOT two more sources. The registry
       half only reads; the installer half only writes. Putting them in one
       source strip would put "Search" and "npx" on the same row, which reads as
       four equivalent ways to get a skill and is not what they are. `mode` is
       the field the dialog's "Workflow" select already wrote — this moves the
       choice to the surface it describes, and deletes that select. */
    installWorkflows() {
      return [
        { id: "registry", label: "Registry" },
        { id: "fetch", label: "Fetch & trust" },
        { id: "runner", label: "Installer" },
      ];
    },
    /* The sentence under the heading is mode-aware because 5.1a's was scoped to
       the registry half: "nothing on this page writes to disk" is true until the
       Installer button is pressed, and a blanket claim like that is the RULES #12
       failure this product is built to avoid. The fetch half has a THIRD claim
       to make: it writes a review under the data dir on the first press and a
       skill into the global store on the second, and it will not do either until
       the reader has seen the first one's evidence. */
    installScopeNote() {
      if (this.install.mode === "runner") {
        return "Runs a package runner on this machine and writes into the agent scope roots it reports. This is the half of this page that changes things on disk.";
      }
      if (this.install.mode === "fetch") {
        return "Fetches one skill from skills.sh into a review under this data directory. Nothing is installed until you read that review and confirm it. The commit targets the global store only.";
      }
      return "Reads the skills.sh registry. Nothing on this page writes to disk — fetching a snapshot for review is a separate, deliberate action.";
    },
    installRunnerReady() {
      return !!(this.install.source && this.install.source.trim());
    },
    /* `runInstall` reads `install.lastResult` for its exit code, and so does the
       outcome sentence — but the REGISTRY half writes the same field, and its
       payload is a listing. `exit_code` is what the install route returns and a
       listing never carries one, so this distinguishes the two by a field the
       response actually has rather than by whichever half asked last. */
    installRunnerResult() {
      const result = this.install.lastResult;
      return result && typeof result.exit_code === "number" ? result : null;
    },
    /* A dry run is not a run. The primary button said "Run" with `-l` already
       ticked, which is the one label in this view that could overstate what the
       press would do. */
    installRunnerActionLabel() {
      return this.install.listOnly ? "List only" : "Run";
    },
    /* The name of the workflow currently on the page, read from the SAME list the
       strip renders rather than typed here. The fetch half's error banner opens
       with it ("Fetch & trust did not complete."), and a hardcoded string there
       would be a fourth place to rename a workflow — the exact drift 4.7 spent a
       night removing from the batch dialog. Falls back to the first entry so it
       is never empty: an error banner that says ". did not complete." is worse
       than no banner. */
    installWorkflowLabel() {
      const current = this.installWorkflows.find((w) => w.id === this.install.mode);
      return (current || this.installWorkflows[0]).label;
    },
    installRunnerOutcome() {
      const result = this.installRunnerResult;
      if (!result) return "";
      if (result.exit_code === 0) return `Exit 0. ${result.runner || this.install.runner || "the runner"} reported success for ${result.source || this.install.source}.`;
      const detail = String(result.stderr || result.stdout || "").trim().split("\n").filter(Boolean).pop() || "The runner printed nothing to explain the exit code.";
      return `Exit ${result.exit_code}. ${detail}`;
    },
    installSource() {
      return this.installSources.find((s) => s.id === this.install.registryOp) || this.installSources[0];
    },
    /* The precondition the BACKEND enforces, not the one the form would
       prefer. `search` rejects anything under two characters
       (registry.py:773) — which is why an empty search box does not fire a
       request at all rather than firing one that is certain to fail. */
    installQueryLength() {
      return this.install.source.trim().length;
    },
    installCanRead() {
      if (this.install.registryOp === "search") return this.installQueryLength >= 2;
      return true;
    },
    installMissingReason() {
      if (this.installCanRead) return "";
      return `The registry search rejects a query shorter than 2 characters. ${this.installQueryLength} entered.`;
    },
    installMeta() {
      const meta = this.install.lastResult && this.install.lastResult._registry;
      return meta && typeof meta === "object" ? meta : null;
    },
    /* `cache_state` is one of miss|fresh|stale|refreshed (registry.py:75) and
       the banner is about `stale`, which is the only one of the four that means
       "this was not asked of the registry just now". Derived from the boolean
       the backend sets rather than from the string, so an unknown state cannot
       quietly read as fresh. */
    installShowingStaleCache() {
      const meta = this.installMeta;
      return !!meta && meta.stale === true;
    },
    installCacheStateLabel() {
      const meta = this.installMeta;
      if (!meta) return "";
      const state = String(meta.cache_state || "");
      if (state === "stale") return "Cached copy";
      if (state === "fresh") return "Cached copy, still inside its lifetime";
      if (state === "refreshed") return "Refreshed from the registry";
      if (state === "miss") return "Fetched from the registry";
      return state;
    },
    installRows() {
      const result = this.install.lastResult;
      if (!result || !Array.isArray(result.data)) return [];
      return result.data
        .filter((row) => row && typeof row === "object")
        .map((row, index) => ({
          key: String(row.id || row.slug || row.name || index),
          name: String(row.name || row.slug || row.id || "Unnamed entry"),
          source: String(row.source || row.owner || ""),
          installs: Number.isFinite(row.installs) ? row.installs : null,
          url: String(row.url || ""),
        }));
    },
    installResultTruncated() {
      return !!(this.install.lastResult && this.install.lastResult.truncated);
    },
    /* --- 5.2 the fetch stepper ---------------------------------------------
       `fetch` is the one registry operation that WRITES: stage 1 puts a private,
       expiring review under the data dir and installs nothing; stage 2 is the
       reader looking at it; stage 3 sends `review_id` + `trust_confirmed` and
       writes the skill into the global store. The backend enforces the split
       (webapp.py:128 refuses a commit without `trust_confirmed`, :130 refuses
       `trust_confirmed` without a `review_id`), so the stepper below is not a
       UI convention layered over a single call — it is the shape of the route.

       **The three states are derived, never declared.** `review` and
       `committed` are whatever the last two responses actually returned, so a
       step cannot advance on a value a reader typed. */
    installFetchSteps() {
      const review = this.install.review;
      const committed = this.install.committed;
      if (committed) {
        return [
          { id: "fetch", label: "Fetched", state: "done", detail: "The snapshot was staged for review." },
          { id: "review", label: "Reviewed", state: "done", detail: "You read the evidence below and confirmed it." },
          { id: "commit", label: "Installed", state: "done", detail: `${committed.name} is in the global store.` },
        ];
      }
      if (review) {
        return [
          { id: "fetch", label: "Fetched", state: "done", detail: `Review ${review.review_id} is held under this data directory.` },
          { id: "review", label: "Read the evidence", state: "current", detail: "The validation, risk signals and hashes are below. Nothing is installed until you confirm." },
          { id: "commit", label: "Trust and install", state: "todo", detail: "Available once you have read the evidence." },
        ];
      }
      return [
        { id: "fetch", label: "Fetch for review", state: "current", detail: "Fetches one skill and stages it for review. Installs nothing." },
        { id: "review", label: "Read the evidence", state: "todo", detail: "Validation, risk signals, hashes and expiry." },
        { id: "commit", label: "Trust and install", state: "todo", detail: "Writes the reviewed snapshot into the global store." },
      ];
    },
    installFetchStepIndex() {
      const steps = this.installFetchSteps;
      const at = steps.findIndex((s) => s.state === "current");
      return at === -1 ? steps.length : at;
    },
    /* One sentence, under the strip, for the step the reader is ON. Three
       sentences competed for one 1280 row, wrapped the strip onto two lines and
       left a separator stranded at the head of the second — so the strip now
       carries labels and this carries the one line that does work. The detail
       of a DONE step is not lost either: the commit outcome banner says it. */
    installFetchDetail() {
      const steps = this.installFetchSteps;
      const current = steps.find((s) => s.state === "current");
      return (current || steps[steps.length - 1]).detail;
    },
    /* `registry` is a dict the backend builds from a snapshot we did not write,
       and `inspection.findings` is a list of heuristic signals whose own policy
       string says they are not a verdict. Both are read defensively and BOTH
       strings are rendered verbatim rather than summarised into a score — the
       product states observed facts only (RULES #12). */
    installFetchFacts() {
      const review = this.install.review || this.install.committed;
      if (!review) return [];
      const registry = (review.registry && typeof review.registry === "object") ? review.registry : {};
      const rows = [
        { label: "Registry id", value: registry.id || registry.slug || registry.source || "the returned source", code: true },
        { label: "Source", value: registry.source || "not recorded by the registry" },
        { label: "Slug", value: registry.slug || "not recorded" },
        { label: "Snapshot hash", value: registry.snapshot_hash || "not recorded", code: true },
        { label: "Registry hash", value: registry.registry_hash || registry.remote_registry_hash || "not recorded", code: true },
        { label: "Hash verified", value: registry.hash_verified === true ? "verified against the registry" : (registry.remote_hash ? "not verified — the registry's own hash is recorded, not confirmed" : "no remote hash was returned") },
        { label: "Cache", value: String(registry.cache_state || "unknown") },
        { label: "Files", value: Number.isFinite(registry.file_count) ? String(registry.file_count) : "not counted" },
      ];
      if (registry.normalization) rows.push({ label: "Normalization", value: String(registry.normalization) });
      return rows;
    },
    installFetchWarnings() {
      const inspection = this.install.review && this.install.review.inspection;
      const list = inspection && inspection.validation && Array.isArray(inspection.validation.warnings) ? inspection.validation.warnings : [];
      return list.filter((w) => w && typeof w === "object").map((w) => ({
        level: String(w.level || "warning"),
        message: String(w.message || "the validator reported a warning with no message"),
      }));
    },
    /* The policy string is the backend's and says out loud that these findings
       are not a safety or trust verdict (cli_handlers.py:1505). Rendering a
       count instead would turn a heuristic into a grade, which is the exact
       failure this product is built not to ship. */
    installFetchRisk() {
      const inspection = this.install.review && this.install.review.inspection;
      const risk = inspection && inspection.risk;
      if (!risk || typeof risk !== "object") return null;
      const findings = Array.isArray(risk.findings) ? risk.findings.filter((f) => f && typeof f === "object") : [];
      return {
        policy: String(risk.policy || "the scan returned no policy statement"),
        findings: findings.map((f) => ({
          kind: String(f.kind || "finding"),
          severity: String(f.severity || "unknown"),
          evidence: String(f.evidence || "no evidence text was returned"),
          why: String(f.why || ""),
        })),
      };
    },
    /* The expiry is the backend's own 24h window (registry.py:68), not a number
       typed here, and it matters: after it passes the commit fails with "review
       is unreadable", so a reader told only "installed" would be told nothing
       about the window they are acting in. */
    installFetchExpiry() {
      const review = this.install.review;
      const value = (review && (review.review_expires_at || review.expires_at)) || "";
      if (!value) return "";
      const when = new Date(value);
      if (Number.isNaN(when.getTime())) return String(value);
      return when.toLocaleString();
    },
    installFetchOutcome() {
      const committed = this.install.committed;
      if (!committed) return "";
      return `installed into the global store at ${committed.path}.`;
    },
    registryInventory() {
      const source = this.allSkills.length ? this.allSkills : this.skills;
      return source.filter((record) => record && record.registry_provenance && typeof record.registry_provenance === "object");
    },
    filteredRegistryInventory() {
      const q = this.query.trim().toLowerCase();
      if (!q) return this.registryInventory;
      return this.registryInventory.filter((record) => {
        const provenance = record.registry_provenance || {};
        return [record.name, provenance.id, provenance.source, provenance.slug]
          .some((value) => String(value || "").toLowerCase().includes(q));
      });
    },
    /* Does `query` filter anything at all on the view in front of the reader?

     * The search field is GLOBAL — one input in the topbar, one `v-model`, one
     * `/` binding — so it renders on every view. That is right: it filters the
     * Library, Trash, Quality evidence and the registry inventory. But `query`
     * is read by exactly four filtered lists, and Recovery is not one of them:
     * its pane is "Source snapshots" for the selected skill, with no list to
     * search. The field still promised "Search recovery…" there, so the UI
     * stated a capability that did not exist (RULES #12).
     *
     * The claim, not the control, is what is wrong. Removing the field on the
     * views that cannot use it is the only way the placeholder can stop being
     * a promise — and `/` must then stop being a promise too, which is why the
     * key handler consults this same list rather than the element. */
    searchAppliesHere() {
      return SEARCH_VIEW_IDS.includes(this.view);
    },
    /* The help dialog's `/` row names these views in prose. Derived from
       SEARCH_VIEWS so the sentence and the guard cannot disagree — this is
       the "one definition, two hosts" shape 5.6a used for the trash ledger.
       "and" before the last item, because a settings page that says
       "Library, Install, Quality, Trash" reads as a list, not a sentence. */
    searchShortcutScope() {
      const labels = SEARCH_VIEWS.map((view) => view.label);
      if (labels.length < 2) return labels.join("");
      return `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
    },
    registryInventoryCount() {
      return this.filteredRegistryInventory.length;
    },
    qualityRecords() {
      return this.allSkills.length ? this.allSkills : this.skills;
    },
    filteredQualitySkills() {
      const q = this.query.trim().toLowerCase();
      if (!q) return this.qualityRecords;
      return this.qualityRecords.filter((record) => {
        const provenance = record.registry_provenance || {};
        return [record.name, record.description, record.category, ...(record.tags || []), provenance.id, provenance.source, provenance.slug]
          .some((value) => String(value || "").toLowerCase().includes(q));
      });
    },
    qualitySummary() {
      const records = this.qualityRecords;
      const logical = groupLogicalSkills(records, this.scopes);
      const stateOf = (record) => {
        // The domain seam owns this classification; "observed" is its "active"
        // bucket under the wording Quality uses, so nothing here restates it.
        const state = observedStateFor(record);
        return state === "active" ? "observed" : state;
      };
      const validityFlagged = records.filter((record) => {
        const observed = observeRecord(record);
        return observed.malformedDocument || observed.notAddressable;
      });
      return {
        observed: records.length,
        active: records.filter((record) => stateOf(record) === "observed").length,
        disabled: records.filter((record) => stateOf(record) === "disabled").length,
        malformed: records.filter((record) => stateOf(record) === "malformed").length,
        /* A refused symlink is its own bucket. Without it these records would
         * fall out of the summary entirely — the seam now classifies them
         * separately, and a summary that silently loses rows is worse than one
         * that names them. */
        linked: records.filter((record) => stateOf(record) === "linked").length,
        unaddressable: records.filter((record) => stateOf(record) === "unaddressable").length,
        validityFlagged: validityFlagged.length,
        divergent: logical.filter((group) => !!group.divergent).length,
        provenance: records.filter((record) => record.registry_provenance && typeof record.registry_provenance === "object").length,
      };
    },
    qualityHygieneFindings() {
      const report = this.qualityHygiene;
      return report && Array.isArray(report.findings) ? report.findings : [];
    },
    filteredQualityHygieneFindings() {
      const query = this.query.trim().toLowerCase();
      return this.qualityHygieneFindings.filter((finding) => {
        if (this.qualitySeverityFilter !== "all" && finding.severity !== this.qualitySeverityFilter) return false;
        if (!query) return true;
        const instances = (finding.instances || []).flatMap((instance) => [instance.name, instance.scope, instance.scope_label, instance.consumer]);
        return [finding.title, finding.explanation, finding.recommendation, finding.category, ...instances]
          .some((value) => String(value || "").toLowerCase().includes(query));
      });
    },
    qualityHygieneGroups() {
      const groups = new Map();
      for (const finding of this.filteredQualityHygieneFindings) {
        if (!groups.has(finding.category)) groups.set(finding.category, []);
        groups.get(finding.category).push(finding);
      }
      return [...groups.entries()].map(([category, findings]) => ({ category, findings }));
    },
    qualityHygieneSummary() {
      return (this.qualityHygiene && this.qualityHygiene.summary) || {};
    },
    /* 5.5 — the report's own severity tally, in the order the server ranks
       them. `unavailable` is a count of CHECKS THAT COULD NOT RUN, not of
       findings: no finding in the list ever carries that severity, which is why
       the severity <select> has no "Unavailable" option and the ledger says
       what the number is instead of pretending it is a finding. */
    qualitySeverityLedger() {
      const summary = this.qualityHygieneSummary;
      return [
        { severity: "error", count: Number(summary.errors || 0), label: "errors — a check that ran and failed" },
        { severity: "warning", count: Number(summary.warnings || 0), label: "warnings — observed evidence to read" },
        { severity: "info", count: Number(summary.informational || 0), label: "informational" },
        { severity: "unavailable", count: Number(summary.unavailable || 0), label: "signals not observed — checks that could not run" },
      ];
    },
    /* One pass over the server's histogram instead of nine `qualityCategoryCount`
       calls in the template, which is how "Exact duplicate groups" came to sum
       three independent category counts and label the total "independent
       groups" while the report's own copy said findings overlap. */
    qualityCategoryLedger() {
      return SkillManagerDomain.hygieneCategoryLedger(
        (this.qualityHygiene && this.qualityHygiene.category_counts) || {}
      );
    },
    /* The scope switcher is a listbox over OBSERVED facts only: a scope the
       server did not discover is reported as "root not detected", never as an
       empty library. `/api/scopes` omits missing roots, so `exists: false` here
       means undiscovered, not empty — the copy says exactly that. */
    scopeOptions() {
      const all = {
        id: "all",
        label: "All scopes",
        path: "every detected root",
        count: this.allScopesCount,
        exists: true,
        over: false,
      };
      const rows = (this.scopes || []).filter(Boolean).map((s) => {
        const budget = this.scopeBudgetFor(s.id);
        return {
          id: s.id,
          label: s.label,
          path: s.path || "",
          count: s.count || 0,
          exists: s.exists !== false,
          over: !!(budget && budget.over),
        };
      });
      return [all].concat(rows);
    },

    /* 5.9a — the roots the About section lists, taken from the SAME
     * `scopeOptions` the rail's switcher renders rather than derived a
     * second time. Two derivations of "which directories is this machine
     * pointed at" would be free to disagree, and the About section's whole
     * claim is that it names what the app actually reads.
     *
     * Element 0 is the synthetic `All scopes` row — `every detected root` is
     * not a directory, so it is dropped rather than rendered as one. Slice,
     * do not filter on `id`: a real scope's id is whatever the backend sent.
     */
    observedRoots() {
      return this.scopeOptions.slice(1).map((root) => Object.assign({}, root, {
        // 2.1b recorded this exact finding on the scope popover and left it as
        // a note: "a front-truncated path computed in JS would be cleaner".
        // This is that. CSS `text-overflow` keeps the HEAD, and on this
        // machine every root shares a head — eight rows rendered
        // `/tmp/skillsmgr-v2-sandbox/…` and the one column that exists to
        // tell them apart was amputated for all eight.
        short: frontTruncatePath(root.path),
      }));
    },

    activeScopeOption() {
      return this.scopeOptions.find((o) => o.id === this.activeScope) || this.scopeOptions[0];
    },

    activeScopeLabel() {
      return this.activeScopeOption.label;
    },

    activeScopeAvailable() {
      return this.activeScopeOption.exists;
    },
    /* --- sync facts -------------------------------------------------------
     *
     * FIVE getters. They must live in `computed`, not `methods`, and that is
     * not a style choice: `syncPickedTargets.length` in a template is 0 when
     * `syncPickedTargets` is a FUNCTION, because a function's `.length` is its
     * arity. That is the 4.3b `batchStaleTargets` defect, and it renders a
     * dialog that confidently states nothing is selected.
     */
    syncPickedTargets() {
      const m = this.modals.sync;
      if (!m || !m.picked) return [];
      return Object.keys(m.picked).filter((k) => m.picked[k]);
    },
    syncPickedCount() { return this.syncPickedTargets.length; },
    syncPickedLabels() {
      const m = this.modals.sync;
      if (!m) return [];
      return this.syncPickedTargets.map((id) => {
        const t = (m.targets || []).find((x) => x && x.id === id);
        return t && t.label ? t.label : id;
      });
    },
    /* The context cost of writing this skill to every picked target. It is an
     * arithmetic multiple of what one copy already costs, NOT a prediction:
     * the tool has no resolver and cannot know which of those copies an agent
     * actually loads. The copy says so on screen. */
    syncProjectedTokens() {
      const tokens = (this.selected && this.selected.tokens) || 0;
      return tokens * this.syncPickedCount;
    },
    syncOutcomeSentence() {
      const n = this.syncPickedCount;
      if (!n) return "Pick at least one target scope.";
      return "Writes 1 copy to " + n + (n === 1 ? " scope" : " scopes") + ".";
    },

    /* 4.7c -- what the purge COVERS, not only what it can show.
     *
     * The backlog row for this task asserted that `/api/trash/purge` is
     * unscoped: it does not cover every scope's trash while the dialog only
     * sees the global list.  Observed on the sandbox, that is the opposite.
     * A scope removal parks a copy at `~/.commandcode/trash/<scope>__<name>-<ts>`
     * and `Store.purge_trash()` walks one directory -- the global
     * `<data>/skills-manager/trash` -- so the purge returned exactly the three
     * names `GET /api/trash` had listed and left the scope copy on disk.
     *
     * The list is therefore complete, which is not the same as the dialog
     * being honest: nothing in the trash view said its list was the GLOBAL
     * trash, so a reader who removed a skill from an agent scope, saw it leave
     * the Library, and opened this view was told nothing was there.  The one
     * sentence that admitted it (`restore from trash view is global-only`) was
     * a toast the reader may have missed by the time they cared.
     *
     * `agentScopeLabels` names the scopes from `/api/scopes`, never from a
     * hardcoded list, so a scope that is not detected is not claimed.
     */
    agentScopeLabels() {
      return (this.scopes || [])
        .filter((s) => s && s.kind === "agent" && s.label)
        .map((s) => s.label);
    },

    /* 5.8a - the Doctor ledger. See DOCTOR_FINDINGS for why it is a list.
     *
     * A computed, because the template reads it as a VALUE (`v-for`). A
     * function called from a template has to live in `methods` instead - Vue
     * unwraps a computed before the template sees it, so
     * `{{ doctorVerdict() }}` on a computed resolves to the string it returns
     * and the render throws. 5.5 recorded that trap; it is recorded again
     * here because the next person will be editing exactly this pair.
     */
    doctorFindings() {
      const report = (this.modals.doctor || {}).report;
      if (!report) return [];
      return DOCTOR_FINDINGS.map((f) => ({
        key: f.key,
        label: f.label,
        hint: f.hint,
        names: Array.isArray(report[f.key]) ? report[f.key] : [],
      })).filter((f) => f.names.length > 0);
    },
    /** 5.8a - a METHOD, because the template calls it inside a `.map()`.
     *  `/api/doctor` puts `scope_label` on every duplicate record and the
     *  dialog was printing `d.scopes.join(", ")` - the wire slug - one object
     *  away from the human name (5.4c, 5.5 and 4.7b all found this once).
     *  It sat in `computed:` in the first draft of this task and its own suite
     *  caught it on the first run: Vue unwraps a computed to its value, so a
     *  template that CALLS one gets a string. `doctorScopeLabel` lives in
     *  `methods:` next to `doctorVerdict`. */
    purgeScopeSentence() {
      const n = this.trashSkills.length;
      return "Permanently delete " + this.formatNumber(n) + " trashed "
        + (n === 1 ? "skill" : "skills") + " from the global trash?";
    },
    purgeScopeNote() {
      const labels = this.agentScopeLabels;
      const where = labels.length
        ? " (" + labels.join(", ") + ")"
        : "";
      return "A skill removed from an agent scope" + where
        + " is trashed beside that scope. This list does not show those copies,"
        + " and emptying the trash does not delete them.";
    },

    /* 4.8 — the exit button says what pressing it will do.
     *
     * It said "Review later", and no path in the product can review later: the
     * review lives server-side with an expiry, nothing lists pending reviews
     * (API gap, RULES #1), and the only two answers to the question the press
     * raises are "keep reviewing here" and a DELETE. A label promising a
     * return the dialog cannot deliver is RULES #12's failure in a button.
     *
     * In `computed`, not `methods`: the template reads the property, and a
     * function's `.length` is its ARITY — as a method this would have printed
     * "0" on every review (4.7's `syncPickedTargets`, 4.3b's
     * `batchStaleTargets`, 2.1 before both).
     */
    updateExitLabel() {
      const modal = this.modals.update;
      if (modal && !modal.success && modal.review && modal.review.review_state === "pending") {
        return "Cancel review…";
      }
      return "Close";
    },

    /* 4.8b — the commit endpoint answers `committed_with_warning` when the
     * BYTES were replaced but index reconciliation or snapshot pruning failed
     * (`_reconcile_after_commit` in source_update.py). The banner said
     * "Update applied successfully." for that payload too, so the one sentence
     * in the response naming what is still outstanding was dropped on the floor
     * and a reader was told a clean success while the counts in the Overview
     * and the rows in the Library were stale. RULES #12: the UI states only
     * observed facts, and "successfully" was an invented one.
     *
     * Both failure modes are covered because the payload states only one of
     * them: `result` can say committed-with-warning with no `warning` string,
     * and `warning` can arrive without `result` saying so. When neither names
     * the outstanding step, the copy says THAT rather than guessing at it.
     *
     * `computed`, not `methods` — the template reads the property, and a
     * function's `.length` is its arity (2.1, 4.3b, 4.7).
     */
    updateApplyOutcome() {
      const success = this.modals.update && this.modals.update.success;
      if (!success) return null;
      const outstanding = success.result === "committed_with_warning" || !!success.warning;
      if (!outstanding) {
        return { ok: true, outstanding: "", title: "Update applied successfully." };
      }
      return {
        ok: false,
        outstanding: success.warning
          || "the response named no outstanding step, so ask before trusting the counts above it.",
        title: "Update applied, with an outstanding step.",
      };
    },

    /* 6.6 — the left pane's LANDMARK name. `aside.sidebar` is a
     * `complementary` landmark, and at 1440 the app had exactly two of them,
     * both unnamed: a screen reader's landmark list offered "complementary"
     * twice with nothing to tell them apart (axe `landmark-unique`, measured on
     * 7 of 8 views). `#nav-drawer` now carries its own label in the markup, so
     * this one names what is actually inside it — the list or context pane —
     * per view. Honest and observed, never invented: a view with no sidepanel
     * of its own falls back to the generic name rather than to a guess.
     *
     * It lives at the END of `computed` on purpose. `tests/
     * test_redesign_install_center.py` reads the `modals:` literal as a fixed
     * 2400-character slice and asserts `install:` is not in it (5.1: the Install
     * view replaced a modal). A computed parked at the TOP pushed this map's
     * `install:` key into that slice and the test read it as a regression that
     * was never made — the eighth recorded instance of a counting assertion
     * being wrong in the direction that makes a check unadoptable.
     *
     * The comment above contains no braces on purpose, either:
     * `_app_options_literal()` walks `app.js` counting them. */
    listPaneLabel() {
      const names = {
        skills: "Skill list and filters",
        profiles: "Saved profiles",
        workspaces: "Candidate roots",
        install: "Install sources",
        recovery: "Trash and snapshots",
        quality: "Skills in this scope",
        settings: "Settings sections",
      };
      return names[this.view] || "Context pane";
    },

  },



  watch: {
    theme(v) {
      this.applyThemePreference(v);
      this.setupThemeListener();
      localStorage.setItem("skillsmgr-theme", this.theme);
    },
    textSize(v) {
      this.applyTextSize(v);
      localStorage.setItem("skillsmgr-text-size", this.textSize);
    },
    locale(v) {
      this.applyLocale(v);
      localStorage.setItem("skillsmgr-locale", this.locale);
    },
    activeScope(v) {
      localStorage.setItem("skillsmgr-scope", v);
      this.selectedName = null;
      this.selected = null;
      this.clearSelection();
      this.mobileDetailOpen = false;
      this.allSkills = [];
      // BUG-4: a live query must keep filtering after the scope changes,
      // otherwise the search box shows a term while the list shows every skill.
      this.refreshList();
      this.loadStatsTokens();
      if (this.view === "quality") this.loadQualityHygiene();
    },
    libraryMode(v) {
      localStorage.setItem("skillsmgr-library-mode", v);
    },
    browseMode(v) {
      localStorage.setItem("skillsmgr-browse-mode", v);
    },
    budgetWindow(v) {
      localStorage.setItem("skillsmgr-budget-window", v);
      this.loadStatsTokens();
    },
    commandPaletteQuery() {
      this.commandPaletteActiveIndex = this.bestCommandPaletteIndex;
    },
    filteredCommandPaletteCommands(commands) {
      const max = commands.length - 1;
      const next = max < 0 ? 0 : Math.min(this.commandPaletteActiveIndex, max);
      if (next !== this.commandPaletteActiveIndex) this.commandPaletteActiveIndex = next;
      this.$nextTick(() => this.scrollActiveCommandIntoView());
    },
    commandPaletteActiveIndex() {
      this.$nextTick(() => this.scrollActiveCommandIntoView());
    },
    query(value, previous) {
      clearTimeout(this.searchTimer);
      if (value.trim() && !String(previous || '').trim() && this.view === "skills") this.searchRestore = this.skills.slice();
      if (!value.trim() && this.searchRestore.length && this.view === "skills") this.skills = this.searchRestore.slice();
      if (value.trim() && !["skills", "trash", "install", "recovery", "quality"].includes(this.view)) {
        // Preserve focus in the persistent search field while making it a
        // useful global entry point from Overview and auxiliary views.
        this.view = "skills";
        this.mobileDetailOpen = false;
        this.compactControlsOpen = false;
      }
      this.searchTimer = setTimeout(() => this.applySearch(), 220);
    },
    activeModal(value) {
      clearTimeout(this.modalFocusTimer);
      if (value) {
        this.modalFocusTimer = setTimeout(() => this.$nextTick(() => this.focusModal()), 0);
      } else {
        this.modalFocusTimer = setTimeout(() => {
          if (this.commandPaletteTransfer) {
            this.commandPaletteTransfer = false;
            return;
          }
          this.restoreModalFocus();
        }, 0);
      }
    },
  },

  mounted() {
    this.applyThemePreference(this.theme);
    this.applyTextSize(this.textSize);
    this.applyLocale(this.locale);
    this.setupThemeListener();
    this.setupMotionListener();
    document.addEventListener("keydown", this.onKeydown);
    document.addEventListener("mousedown", this.onDocMousedown);
      this.loadInitialData();
  },

  beforeUnmount() {
    /* Every pending toast timer is cleared, or each one fires after teardown
     * against a component instance that no longer exists. */
    Object.values(this.toastTimers || {}).forEach((handle) => clearTimeout(handle));
    this.toastTimers = {};
    this.removeThemeListener();
    this.removeMotionListener();
    document.removeEventListener("keydown", this.onKeydown);
    document.removeEventListener("mousedown", this.onDocMousedown);
  },

  methods: {
    /* Bar geometry for the context-budget meter. These are methods, not
     * computeds: they take a percentage and return a CSS width, so a computed
     * would have to be a computed *returning a function*, and unwrapping that
     * inside a template render is exactly where a reactive proxy leaks into
     * arithmetic. */
    scopePctOf(pct) {
      const max = this.budgetAxisMax || 125;
      const v = Number(pct) || 0;
      return Math.max(0, Math.min(100, (v / max) * 100)).toFixed(2) + "%";
    },
    scopePctClass(pct) {
      const v = Number(pct) || 0;
      return v > 100 ? "pct-bad" : v > 70 ? "pct-warn" : "pct-ok";
    },
    /* The rail carries the scope's share of one context window, so the thing
     * that decides whether an agent is silently truncated is visible from every
     * screen rather than only the overview. */
    scopeBudgetFor(id) {
      return this.scopeBudgetRows.find((r) => r.id === id) || null;
    },
    scopePctFor(id) {
      const row = this.scopeBudgetFor(id);
      return row ? row.pctRounded + "%" : "";
    },

    scopeMenuItems() {
      if (!this.$refs.scopeMenuWrap) return [];
      return [...this.$refs.scopeMenuWrap.querySelectorAll('[role="option"]:not([disabled])')];
    },

    focusScopeMenuItem(el) {
      if (el && el.focus) el.focus();
    },

    toggleScopeMenu() {
      if (this.scopeMenuOpen) {
        this.closeScopeMenu(true);
        return;
      }
      this.menuOpen = false;
      this.scopeMenuOpen = true;
      this.scopeMenuFlip = false;
      this.$nextTick(() => {
        this.positionScopeMenu();
        const items = this.scopeMenuItems();
        const current = items.find((el) => el.getAttribute("aria-selected") === "true");
        this.focusScopeMenuItem(current || items[0]);
      });
    },

    /* The trigger sits at the BOTTOM of the rail -- under the scope heading and
     * above the context-budget meter -- so a listbox that always opens downward
     * runs off the bottom of any viewport shorter than trigger + list. Measured
     * at 800px the list is 307px tall and starts at y=676: 183px of it is below
     * the fold, unreachable and un-clickable. Flip above when there is more
     * room above than below, and reset on close so the next open re-measures
     * against the *current* viewport rather than a remembered one.

     * Two things this measured wrong until now, both found by driving it:

     * 1. Room was read off the MENU's own box, which is already clamped by the
     *    stylesheet's `max-height` and therefore already overflowing. The
     *    overflow was fed straight back into the direction decision, so the
     *    "room above" figure was inflated by exactly the amount the list had
     *    failed to fit. Room is a property of the TRIGGER and the window; it
     *    is measured there.
     * 2. Direction is not a guarantee of reachability. A ten-row list needs
     *    435px; a 480px-tall window leaves ~92px above the trigger, so flipping
     *    put 316px of it off the top of the screen -- the same unreachable
     *    rows the flip was added to prevent, mirrored. The list is now bounded
     *    to the room on the side it actually chose and scrolls from there, so
     *    every row is reachable at any window height. */
    positionScopeMenu() {
      const menu = this.$refs.scopeMenuWrap && this.$refs.scopeMenuWrap.querySelector("#scope-menu");
      const trigger = this.$refs.scopeMenuTrigger;
      if (!menu || !trigger) return;
      const gap = 6;
      const box = trigger.getBoundingClientRect();
      const roomBelow = window.innerHeight - box.bottom - gap;
      const roomAbove = box.top - gap;
      /* Clear last run's bound before asking how tall the list really is, or
       * the second open of a short-window list measures its own clamp. */
      menu.style.maxHeight = "";
      const wanted = menu.scrollHeight;
      this.scopeMenuFlip = wanted > roomBelow && roomAbove > roomBelow;
      const room = Math.max(0, this.scopeMenuFlip ? roomAbove : roomBelow);
      menu.style.maxHeight = Math.floor(room) + "px";
    },

    closeScopeMenu(restoreFocus = false) {
      this.scopeMenuOpen = false;
      this.scopeMenuFlip = false;
      const menu = this.$refs.scopeMenuWrap && this.$refs.scopeMenuWrap.querySelector("#scope-menu");
      if (menu) menu.style.maxHeight = "";
      if (restoreFocus) {
        const trigger = this.$refs.scopeMenuTrigger;
        this.$nextTick(() => trigger && trigger.focus());
      }
    },

    chooseScope(id) {
      this.activeScope = id;
      this.closeScopeMenu(true);
    },

    onScopeMenuKeydown(e) {
      const items = this.scopeMenuItems();
      if (!items.length) return;
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        this.closeScopeMenu(true);
        return;
      }
      if (e.key === "Tab") {
        // A listbox is a single tab stop; Tab leaves it rather than walking rows.
        this.closeScopeMenu(false);
        return;
      }
      const index = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const delta = e.key === "ArrowDown" ? 1 : -1;
        items[(index + delta + items.length) % items.length].focus();
      } else if (e.key === "Home") {
        e.preventDefault();
        items[0].focus();
      } else if (e.key === "End") {
        e.preventDefault();
        items[items.length - 1].focus();
      }
    },
    renderMarkdown,
    tokenPctClass,
    tokenBarWidth,
    formatCompat,
    formatTools,
    groupLogicalSkills,
    deriveLogicalSkillIdentity,
    observedIdentity,

    formatBytes(value) {
      return formatBytes(value, this.resolvedLocale);
    },

    formatTokens(value) {
      return formatTokens(value, this.resolvedLocale);
    },

    formatNumber(value, options = {}) {
      if (value === null || value === undefined || value === "") return "—";
      const numeric = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(numeric)) return String(value);
      try {
        return new Intl.NumberFormat(this.resolvedLocale || undefined, options).format(numeric);
      } catch (e) {
        return String(value);
      }
    },

    /* Relative time for a list whose whole question is "what just happened".
       An absolute timestamp answers a different question, and the answer a
       reader actually wants ("was that before or after I last looked?") is not
       recoverable from one at a glance. Absolute time is still reachable: the
       row carries the exact value in `title`/`datetime`, and "7 days ago"
       falls back to the absolute date rather than pretending to be precise.
       `now` is a parameter rather than a hidden `Date.now()` so the formatter
       is testable without freezing the clock. */
    formatRelative(value, now = Date.now()) {
      if (!value) return "—";
      const date = value instanceof Date ? value : new Date(value);
      const ms = now - date.getTime();
      if (Number.isNaN(ms)) return String(value);
      /* A timestamp in the future is clock skew or a bad record, not "0 sec".
       * Saying so is honest; a negative age is not. */
      if (ms < -60000) return this.formatDate(value);
      const seconds = Math.floor(ms / 1000);
      if (seconds < 45) return "just now";
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes} min ago`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
      const days = Math.floor(hours / 24);
      if (days < 7) return `${days} day${days === 1 ? "" : "s"} ago`;
      return this.formatDate(value);
    },

    formatDate(value, options = {}) {
      if (!value) return "—";
      const date = value instanceof Date ? value : new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      const dateOptions = { dateStyle: "medium", timeStyle: "short", ...options };
      try {
        return new Intl.DateTimeFormat(this.resolvedLocale || undefined, dateOptions).format(date);
      } catch (e) {
        return String(value);
      }
    },

    qualityStateLabel(record) {
      // Reads the same seam the Overview counts and the Library badges read, so
      // a state added to the vocabulary cannot appear here and be missing there.
      switch (observedStateFor(record)) {
        case "invalid": return "Invalid observed";
        case "malformed": return "Malformed observed";
        case "unaddressable": return "Unaddressable observed";
        case "disabled": return "Disabled observed";
        default: return "Observed; not a validation verdict";
      }
    },

    inspectQualityInLibrary() {
      const record = this.selected;
      this.query = "";
      this.filter = "";
      this.tagFilter = "";
      this.switchView("skills");
      if (record) this.$nextTick(() => this.selectSkill(record));
    },

    identityItems(item) {
      if (!item) return [];
      return this.libraryMode === "library"
        ? (item.identities || [])
        : [observedIdentity(item, this.scopes)];
    },

    /* Identities grouped by observed state, problems first.
     *
     * A logical skill can exist in seven scopes. Printing one chip per scope
     * made each row three or four lines tall, so a 638-row list showed about
     * eleven entries per screen and could not be scanned. Grouping keeps the
     * list to at most a couple of lines and — more to the point — puts the
     * disagreement first. This tool exists to answer "which of my agents are
     * reading different instructions?", and this is the row that answers it:
     * the scopes that agree are one line, the ones that do not are their own
     * line above them.
     *
     * This is presentation only. It groups values the seam already returned
     * and asserts nothing the backend did not report.
     */
    groupedIdentities(item) {
      const items = this.identityItems(item);
      if (!items.length) return [];
      const groups = new Map();
      const order = [];
      for (const it of items) {
        const key = (it.stateKeys || []).join(",");
        if (!groups.has(key)) {
          groups.set(key, {
            key,
            stateLabel: it.stateLabel,
            problem: !!it.problem,
            /* `problem` still answers "differs from Active" and still sorts;
             * `severity` answers "how loudly to paint it", which is why a
             * Disabled group is a problem and not an alarm. */
            severity: observedSeverity(it.stateKeys),
            names: [],
            full: [],
          });
          order.push(key);
        }
        const group = groups.get(key);
        group.names.push(it.scopeLabel || it.label);
        group.full.push(it.label);
      }
      return order
        .map((key) => groups.get(key))
        .sort((a, b) => Number(b.problem) - Number(a.problem) || a.stateLabel.localeCompare(b.stateLabel));
    },

    /* The disagreement between copies, stated once on the row.
     *
     * `groupedIdentities` reports what each copy IS. Divergence is a different
     * fact — it is about two copies not matching each other — so it cannot be
     * carried by a chip attributed to one scope, and it cannot be carried by
     * the copy count either ("2 copies" is the row's shape, not its problem).
     *
     * Every value here is observed. The group's `divergent` flag is the same
     * one that already drives `identical` and the Detail pane's "Divergent
     * observed" tag; the copy count is `clusterSize`; the scope names are the
     * identities' own `scopeLabel`. Nothing is inferred, and when the copies
     * agree this returns null so the row says nothing at all.
     */
    clusterDisagreement(item) {
      if (!item || this.libraryMode !== "library") return null;
      if (!item.divergent) return null;
      const size = this.clusterSize(item);
      if (size < 2) return null;
      return {
        who: `${this.formatNumber(size)} copies`,
        state: "Divergent",
      };
    },

    setLibraryMode(mode) {
      this.libraryMode = mode === "instances" ? "instances" : "library";
    },

    setBrowseMode(mode) {
      this.browseMode = mode === "grid" ? "grid" : "list";
    },

    selectLogicalSkill(group) {
      if (group && group.primary) this.selectSkill(group.primary);
    },

    targetKey(record) {
      return (record.scope || "") + "/" + record.name + "|" + (record.physical_path || record.path || "");
    },

    isSelected(record) {
      return this.selectedKeys.includes(this.targetKey(record));
    },

    groupSelectionState(group) {
      const instances = group.instances || [];
      const count = instances.filter((record) => this.isSelected(record)).length;
      return count === 0 ? "none" : (count === instances.length ? "all" : "some");
    },

    groupTags(group) {
      return [...new Set((group.instances || []).flatMap((instance) => instance.tags || []))];
    },

    /* The row badge row is omitted entirely when it would be empty, so a list
     * without tags or multi-copy groups does not reserve a blank grid track. */
    /* Tags and category for a row. The "N copies" badge that used to be
     * computed here was removed in the template by a regex matching
     * /^\d+ cop/ on its own text -- so every multi-copy row with no tags
     * rendered an EMPTY `.row-badges` cell (measured: 7 of 96), and two files
     * had to agree on an English word for no visible result. The cluster
     * count is not a badge; it is the row's shape, and `clusterSize` owns it. */
    rowBadgeItems(s) {
      if (!s) return [];
      if (this.libraryMode === "library") {
        return this.groupTags(s).map((tag) => ({ key: "tag:" + tag, text: "#" + tag }));
      }
      const tags = s.tags || [];
      return (s.category ? [{ key: "category", text: s.category }] : [])
        .concat(tags.map((tag) => ({ key: "tag:" + tag, text: "#" + tag })));
    },

    /* How many exact physical instances one Library row stands for.
     *
     * A Library row is one NAME; this is how many on-disk copies back it. It
     * was printed on every row, so 87 of 96 rows in the seeded library read
     * "1 copy" -- a constant restating the row's own shape, in a bordered
     * pill immediately after the name. A cluster is the exception worth
     * marking; a single copy is what every other row already is, so it needs
     * no ink. `identities` leads because aliases collapse to one physical
     * instance and must not be counted twice. */
    clusterSize(item) {
      if (!item) return 0;
      return (item.identities || []).length || (item.instances || []).length || 0;
    },

    profileTargets() {
      const seen = new Set();
      const targets = [];
      for (const member of (this.profilePreview && this.profilePreview.members || [])) {
        for (const instance of (member.instances || [])) {
          const target = {
            name: member.name,
            scope: instance.scope,
            path: instance.path || instance.physical_path || "",
          };
          const key = (target.name || "") + "|" + (target.scope || "") + "|" + target.path;
          if (!target.name || !target.scope || seen.has(key)) continue;
          seen.add(key);
          targets.push(target);
        }
      }
      return targets;
    },

    toggleSelection(record, checked) {
      const instances = record.instances || [record];
      const keys = new Set(this.selectedKeys);
      const snapshot = Object.assign({}, this.selectedSnapshot);
      for (const instance of instances) {
        const key = this.targetKey(instance);
        if (checked) {
          keys.add(key);
          snapshot[key] = Object.freeze({
            name: instance.name,
            scope: instance.scope,
            path: instance.path || instance.physical_path || "",
            physical_path: instance.physical_path || instance.path || "",
            disabled: Number(instance.disabled) || 0,
          });
        } else {
          keys.delete(key);
          delete snapshot[key];
        }
      }
      this.selectedKeys = [...keys];
      this.selectedSnapshot = snapshot;
    },

    toggleSelectAll() {
      const keys = new Set(this.selectedKeys);
      if (this.allVisibleSelected) this.visibleTargetKeys.forEach((key) => keys.delete(key));
      else this.visibleTargetKeys.forEach((key) => keys.add(key));
      this.selectedKeys = [...keys];
      // Prune, so a snapshot entry never outlives the key that justified it.
      const snapshot = Object.assign({}, this.selectedSnapshot);
      for (const key of Object.keys(snapshot)) if (!keys.has(key)) delete snapshot[key];
      this.selectedSnapshot = snapshot;
    },

    /* The bulk bar had no way out that did not depend on the filter.
       `toggleSelectAll` only ever adds or removes VISIBLE keys, so three
       hand-picked rows out of 96 left the reader with "Select visible" — which
       would have added the other 93 — and no control that emptied the
       selection. Changing the filter hid the chosen rows and kept them counted
       forever. One call, and the tag field goes with it because it is an input
       into an action that is about to have no subject. */
    clearSelection() {
      this.selectedKeys = [];
      this.selectedSnapshot = {};
      this.batchTagInput = "";
    },

    skipOnboarding() {
      this.onboardingDismissed = true;
    },

    dismissFirstScanGuide() {
      this.firstScanGuideDismissed = true;
      localStorage.setItem("skillsmgr-first-scan-dismissed", "1");
    },

    restartFirstScanGuide() {
      this.firstScanGuideDismissed = false;
      localStorage.removeItem("skillsmgr-first-scan-dismissed");
      this.view = "overview";
      this.$nextTick(() => {
        const heading = document.querySelector("#first-scan-title");
        if (heading) heading.focus();
      });
    },

    async runGuideExplain() {
      const request = ++this.guideExplainRequest;
      this.guideExplainLoading = true;
      this.guideExplainError = null;
      this.guideExplainResult = null;
      try {
        const report = await api("/api/doctor?explain=" + encodeURIComponent(this.guideExplainConsumer));
        if (request === this.guideExplainRequest) this.guideExplainResult = report.explain || null;
      } catch (e) {
        if (request === this.guideExplainRequest) this.guideExplainError = "Effective-resolution evidence is unavailable. Open Quality or retry the read-only explanation.";
      } finally {
        if (request === this.guideExplainRequest) this.guideExplainLoading = false;
      }
    },

    openGuideLibrary() {
      const record = this.guideSampleRecord;
      if (record) this.openOverviewSkill({ primary: record });
      else this.switchView("skills");
    },

    openGuidePreviewTarget() {
      const record = this.guidePreviewRecord;
      if (record) this.openOverviewSkill({ primary: record });
    },

    restartOnboarding() {
      this.onboardingDismissed = false;
      this.view = "skills";
      this.activeScope = "all";
    },

    modalElement() {
      return this.activeModal ? document.querySelector('[data-modal="' + this.activeModal + '"] .modal') : null;
    },

    focusableInModal() {
      const modal = this.modalElement();
      if (!modal) return [];
      return [...modal.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])')]
        .filter((el) => !el.closest('[hidden], [inert]') && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    },

    focusModal() {
      const modal = this.modalElement();
      if (!modal) return;
      const focusables = this.focusableInModal();
      const preferred = focusables.find((el) => el.matches('button.btn-secondary, input:not([readonly]), textarea, select'));
      (preferred || focusables[0] || modal).focus();
    },

    trapModalFocus(e) {
      if (!this.activeModal) return;
      const focusables = this.focusableInModal();
      if (!focusables.length || e.key !== 'Tab') return;
      const first = focusables[0], last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    },

    /* --------------------------------------------------------- drawer (2.1e2)

    Below 761px the navigation rail is a drawer: same element, same buttons,
    positioned differently.  There is no second copy of the nav to fall out of
    sync, and every destination keeps the markup, the handler and the
    accessible name it had as a rail button.

    The scope/context disclosure travels *into* the drawer rather than keeping
    its own trigger on a 390px screen, so `compactControlsOpen` is forced on
    while the drawer is open and restored to its previous value on close. That
    is deliberate: the Library filter bar's `:has(.compact-controls.open)` gate
    belongs to task 2.1f, and this task must not move it.
    */

    drawerElement() {
      return this.$refs.drawerTrigger ? document.getElementById("nav-drawer") : null;
    },

    focusableInDrawer() {
      const drawer = document.getElementById("nav-drawer");
      if (!drawer) return [];
      return [...drawer.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])')]
        .filter((el) => !el.closest('[hidden], [inert]') && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    },

    openDrawer() {
      if (this.drawerOpen) return;
      this.drawerRestoreCompact = this.compactControlsOpen;
      this.drawerOpen = true;
      this.compactControlsOpen = true;
      this.$nextTick(() => {
        const target = this.focusableInDrawer().find((el) => el.classList.contains("drawer-close"))
          || this.focusableInDrawer()[0];
        if (target) target.focus();
      });
    },

    closeDrawer() {
      if (!this.drawerOpen) return;
      this.drawerOpen = false;
      this.compactControlsOpen = this.drawerRestoreCompact;
      this.drawerRestoreCompact = false;
      this.$nextTick(() => {
        const trigger = this.$refs.drawerTrigger;
        if (trigger) trigger.focus();
      });
    },

    trapDrawerFocus(e) {
      // A dialog is above the drawer and owns its own trap; two traps would
      // fight over the same Tab press.
      if (!this.drawerOpen || this.activeModal) return;
      if (e.key !== "Tab") return;
      const focusables = this.focusableInDrawer();
      if (!focusables.length) return;
      const first = focusables[0], last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    },

    restoreModalFocus() {
      const target = this.modalRestoreFocus;
      this.modalRestoreFocus = null;
      if (target && typeof target.focus === 'function' && document.contains(target)) {
        target.focus();
        return;
      }
      // Menu items disappear when the actions menu closes before its modal
      // opens. Return keyboard users to the stable actions trigger instead.
      const trigger = document.querySelector('[aria-label="Open actions menu"]');
      if (trigger) trigger.focus();
    },

    /* ----------------------------------------------------------- data */

    async loadScopes() {
      try {
        this.scopes = await api("/api/scopes");
        this.scopeScanFailed = false;
      } catch (e) {
        this.scopeScanFailed = true;
      }
    },

    async loadCatalog() {
      try {
        this.catalog = await api("/api/catalog");
        for (const record of this.skills) record.tags = this.catalog.tags[record.name] || record.tags || [];
      } catch (e) { /* non-fatal: skills remain usable without organization metadata */ }
    },

    async loadInitialData() {
      // The list is useful before secondary stats are ready. Keep the first
      // paint independent while fetching each required source once.
      await Promise.all([this.loadScopes(), this.loadSkills(), this.loadTrash()]);
      await this.loadOverviewHistory();
      await this.loadCatalog();
      await this.loadStatsTokens();
    },

    /* Rescan re-reads the same surfaces loadInitialData reads, and keeps the
     * reader where they are. It does not navigate, so a reader who pressed it
     * from the Overview does not silently land in the Library. */
    async rescanOverview() {
      this.rescanBusy = true;
      try {
        await this.loadInitialData();
      } finally {
        this.rescanBusy = false;
      }
    },

    openInstallCenter() {
      this.switchView("install");
    },

    openRecoveryCenter() {
      this.switchView("recovery");
    },

    updateTarget(record = this.selected) {
      if (!record) return null;
      return {
        name: record.name,
        scope: record.scope,
        consumer: record.consumer || observedIdentity(record, this.scopes).consumerLabel,
        physical_path: record.physical_path || record.path,
        physical_root: record.physical_root,
        disabled: !!record.disabled,
        activation_state: record.disabled ? "disabled" : "active",
      };
    },

    openUpdate() {
      if (!this.updateTargetAvailable) {
        this.toast("This exact skill instance is not addressable and writable.", "err");
        return;
      }
      this.openModal("update", {
        mode: "local", target: this.updateTarget(this.selected), files: [], review: null,
        error: null, loading: false, confirmingClose: false, confirmed: false,
        success: null, snapshotId: null,
      });
    },

    updateReviewCanApply(modal = this.modals.update) {
      return !!(modal && modal.review
        && modal.review.review_state === "pending"
        && modal.review.validation && modal.review.validation.valid !== false
        && modal.review.comparison && (modal.review.comparison.changed_files || []).length
        && modal.confirmed && !modal.loading);
    },

    async onUpdateFiles(event) {
      const modal = this.modals.update;
      if (!modal) return;
      const files = [...((event && event.target && event.target.files) || [])];
      modal.files = files;
      modal.review = null;
      modal.error = null;
      modal.confirmed = false;
      if (files.length) await this.prepareUpdateReview();
    },

    async prepareUpdateReview() {
      const modal = this.modals.update;
      if (!modal || !modal.files || !modal.files.length) return;
      modal.loading = true;
      modal.error = null;
      modal.review = null;
      modal.confirmed = false;
      try {
        const form = new FormData();
        form.append("name", modal.target.name);
        form.append("scope", modal.target.scope);
        form.append("target_path", modal.target.physical_path);
        for (const file of modal.files) {
          form.append("files", file, file.webkitRelativePath || file.name);
        }
        modal.review = await api("/api/source-updates/reviews", { method: "POST", body: form });
        this.toast(modal.review.review_state === "pending"
          ? "Private update review ready. Inspect the evidence before applying."
          : `Update review is ${modal.review.review_state}.`, modal.review.review_state === "pending" ? "info" : "err");
      } catch (e) {
        modal.error = e.message;
        this.toast("Could not prepare update review: " + e.message, "err");
      } finally {
        if (this.modals.update === modal) modal.loading = false;
      }
    },

    async prepareSnapshotReview(snapshot) {
      const modal = this.modals.update;
      if (!modal || !snapshot || !snapshot.snapshot_id) return;
      modal.loading = true;
      modal.error = null;
      /* 4.8b — the local path (`prepareUpdateReview`) clears both of these
       * before its await and the snapshot path cleared neither. Measured, not
       * assumed: `openRollbackReview` builds a FRESH modal with
       * `confirmed: false` and prepares once, so the carried-over `true` is
       * unreachable today — this is defence in depth, exactly like the
       * `!scopeMenuOpen` guard 4.2 slice A kept for the same reason. The
       * review IS cleared, though, and that one is not defence: a retry that
       * left a stale review on screen would let `updateReviewCanApply` read
       * changed files and a review_id belonging to the previous candidate. */
      modal.review = null;
      modal.confirmed = false;
      try {
        modal.review = await api("/api/source-updates/reviews/from-snapshot", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: modal.target.name, scope: modal.target.scope,
            target_path: modal.target.physical_path, snapshot_id: snapshot.snapshot_id }),
        });
        this.toast("Rollback review ready. Review the reverse diff before applying.", "info");
      } catch (e) {
        modal.error = e.message;
        this.toast("Could not prepare rollback review: " + e.message, "err");
      } finally {
        if (this.modals.update === modal) modal.loading = false;
      }
    },

    openRollbackReview(snapshot) {
      if (!this.updateTargetAvailable || !snapshot || snapshot.available === false) {
        this.toast("Select an exact writable target with an available snapshot first.", "err");
        return;
      }
      const target = this.updateTarget(this.selected);
      this.openModal("update", {
        mode: "snapshot", snapshot, target, files: [], review: null, error: null,
        loading: false, confirmingClose: false, confirmed: false, success: null, snapshotId: null,
      });
      this.prepareSnapshotReview(snapshot);
    },

    async applyUpdateReview() {
      const modal = this.modals.update;
      if (!this.updateReviewCanApply(modal)) return;
      modal.loading = true;
      modal.error = null;
      try {
        const result = await api("/api/source-updates/reviews/" + encodeURIComponent(modal.review.review_id) + "/commit", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: modal.target.name, scope: modal.target.scope,
            target_path: modal.target.physical_path, approve: true }),
        });
        modal.success = result;
        modal.snapshotId = result.snapshot_id || null;
        /* 4.8b — the toast read "Update applied to X; recovery snapshot Y."
         * for every response, including `committed_with_warning`, where the
         * bytes landed and the index reconciliation did not. Same failure as
         * the banner, in the place a reader sees for eight seconds. The verdict
         * comes from `updateApplyOutcome`, the same computed the banner reads,
         * so the two cannot disagree. */
        const outcome = this.updateApplyOutcome;
        this.toast(outcome.ok
          ? `Update applied to ${modal.target.name}; recovery snapshot ${modal.snapshotId || "created"}.`
          : `Update applied to ${modal.target.name}, with an outstanding step: ${outcome.outstanding}`,
          /* `info`, not `err`: the bytes WERE replaced, so an error tone is a
           * lie in the other direction, and `ok` is the lie being fixed. It is
           * the neutral type this app already ships (`.toast-info`, the `circle`
           * glyph) and it is already read by three other call sites. */
          outcome.ok ? "ok" : "info");
        await Promise.all([this.loadScopes(), this.loadSkills(), this.loadTrash(), this.loadRecoverySnapshots()]);
      } catch (e) {
        modal.error = e.message;
        this.toast("Update was not applied: " + e.message, "err");
      } finally {
        if (this.modals.update === modal) modal.loading = false;
      }
    },

    requestCloseUpdate() {
      const modal = this.modals.update;
      if (!modal) return;
      if (modal.review && modal.review.review_state === "pending" && !modal.success) {
        modal.confirmingClose = true;
        /* 4.8 — this band is the LAST child of the scrolling `.modal-body`,
         * and the evidence above it (target, tree hashes, a per-file diff,
         * validity, risk, recovery policy) is far taller than the body at
         * every width. A reader at the top who presses Escape, mis-clicks the
         * scrim or presses the foot button is therefore asked a question that
         * rendered off-screen, which reads as "nothing happened" — the exact
         * defect 4.5 slice A fixed for the editor's band, and the more likely
         * one here because the foot button is always on screen. */
        this.$nextTick(() => {
          const band = document.querySelector('[data-modal="update"] .update-close-confirm');
          if (band && band.scrollIntoView) band.scrollIntoView({ block: "nearest" });
        });
        return;
      }
      this.closeModal("update");
    },

    /* 4.8b — the DECISION the row asked for, and it is the editor's rule, not
     * this dialog's.
     *
     * `requestCloseUpdate` re-raised the question on every Escape, while the
     * skill editor's `skillEscape` clears it and Escape again re-asks (4.5
     * slice A). The update dialog was wrong about its own affordance, for a
     * reason worth stating: its case for forcing a decision is that a pending
     * review is server-side and expires. That case does not apply to CLEARING
     * the question, because clearing it leaves the reader inside the dialog
     * with the review exactly as pending as it was — nothing is dropped and
     * nothing is decided. What it buys is that Escape means "step back one
     * level" everywhere, and the band IS a level.
     *
     * No exit is lost: Escape again re-asks, and the foot button, the close
     * glyph and the scrim all still go through `requestCloseUpdate`.
     */
    updateEscape() {
      const modal = this.modals.update;
      if (!modal) return;
      if (modal.confirmingClose) { modal.confirmingClose = false; return; }
      this.requestCloseUpdate();
    },

    async cancelUpdateReview() {
      const modal = this.modals.update;
      if (!modal || !modal.review || !modal.review.review_id) {
        this.closeModal("update");
        return;
      }
      try {
        await api("/api/source-updates/reviews/" + encodeURIComponent(modal.review.review_id), { method: "DELETE" });
        this.toast("Pending update review cancelled.", "info");
        this.closeModal("update");
      } catch (e) {
        modal.error = "Review cancellation failed: " + e.message;
        this.toast(modal.error, "err");
      }
    },

    async loadRecoverySnapshots() {
      const target = this.updateTarget(this.selected);
      if (!target || !this.updateTargetAvailable) {
        this.recoverySnapshots = [];
        return;
      }
      this.loadingRecoverySnapshots = true;
      try {
        const query = "?name=" + encodeURIComponent(target.name)
          + "&scope=" + encodeURIComponent(target.scope)
          + "&target_path=" + encodeURIComponent(target.physical_path);
        const result = await api("/api/source-updates/snapshots" + query);
        this.recoverySnapshots = Array.isArray(result) ? result : (result.snapshots || []);
        this.recoverySnapshotsError = null;
      } catch (e) {
        this.recoverySnapshots = [];
        /* 6.3 — the two panes that read this both said "No retained source
         * snapshots for this exact target." after a failure, which is a claim
         * about what is on disk made by a request that never arrived. */
        this.recoverySnapshotsError = "Could not read source snapshots: " + e.message;
        this.toast(this.recoverySnapshotsError, "err");
      } finally {
        this.loadingRecoverySnapshots = false;
      }
    },

    async loadWorkspaces() {
      this.loadingWorkspaces = true;
      try {
        const suffix = this.workspaceProject.trim() ? "?project=" + encodeURIComponent(this.workspaceProject.trim()) : "";
        this.workspaces = await api("/api/workspaces" + suffix);
        this.workspacesError = null;
      } catch (e) {
        /* 6.3 — `workspaces` stays `null` on purpose (never set to `{}`), so
         * `workspaceIdleSentence`'s "could not be read" branch is reachable.
         * What was missing is that the catalogue BELOW it rendered "No adapter
         * evidence is available on this machine." — `!loadingWorkspaces` is
         * true after a failure as well as after an honest empty. */
        this.workspacesError = "Could not read adapter evidence: " + e.message;
        this.toast(this.workspacesError, "err");
      } finally {
        this.loadingWorkspaces = false;
      }
    },

    async loadStatsTokens() {
      try {
        const s = await api("/api/stats?window=" + encodeURIComponent(this.budgetWindow || "claude"));
        this.budget = s;
        this.dataDir = s.dirs && s.dirs.skills
          ? s.dirs.skills.replace(/\/skills$/, "")
          : "";
      } catch (e) { /* non-fatal */ }
    },

    installPreview() {
      if (this.install.mode === "registry") {
        if (this.install.registryOp === "browse") return `skills.sh leaderboard (${this.install.view || "all-time"})`;
        if (this.install.registryOp === "search") return `skills.sh search ${this.install.source || "<query>"}`;
        if (this.install.registryOp === "curated") return "skills.sh curated catalog";
        return `skills.sh fetch ${this.install.source || "<owner/repo/skill>"} → global store`;
      }
      /* 5.2 — the fetch half reads the SOURCE field too, and `install.source`
         is where the runner form keeps its own source. Falling through to the
         runner assembler would print `npx skills add <owner/repo/skill>` for a
         press that does not run npx at all. */
      if (this.install.mode === "fetch") {
        const spec = (this.install.source || "").trim() || "<owner/repo/skill>";
        return this.install.review
          ? `skills.sh commit ${this.install.review.review_id} → global store`
          : `skills.sh fetch ${spec} → review (not the global store)`;
      }
      const r = this.install.runner || "npx";
      const src = (this.install.source || "").trim() || "owner/repo";
      let cmd = r === "npx" ? `npx skills add ${src}` : r === "pnpm" ? `pnpm dlx skills add ${src}` : r === "yarn" ? `yarn dlx skills add ${src}` : `bunx skills add ${src}`;
      if (this.install.scope === "global") cmd += " -g";
      if (this.install.agents && this.install.agents.length) cmd += " " + this.install.agents.map((a) => `-a ${a}`).join(" ");
      if (this.install.skillsFilter) cmd += ` -s ${this.install.skillsFilter}`;
      if (this.install.copy) cmd += " --copy";
      if (this.install.listOnly) cmd += " -l";
      return cmd;
    },

    async runInstall(confirm) {
      if (this.install.mode === "registry") {
        if (confirm) return this.runRegistry();
        this.toast(this.installPreview(), "info");
        return;
      }
      if (!this.install.source || !this.install.source.trim()) { this.toast("Enter a source (e.g. vercel-labs/agent-skills).", "err"); return; }
      if (this.install.runner === "uvx") { this.toast("uvx does not apply to the npm 'skills' package; use npx/pnpm/yarn/bunx.", "err"); return; }
      if (!confirm) {
        // Dry-run: just show command.
        this.toast(this.installPreview(), "info");
        return;
      }
      this.busy = true;
      try {
        const payload = {
          source: this.install.source.trim(),
          runner: this.install.runner,
          scope: this.install.scope || "global",
          agents: this.install.agents && this.install.agents.length ? this.install.agents : undefined,
          skills: this.install.skillsFilter ? [this.install.skillsFilter] : undefined,
          copy: !!this.install.copy,
          list_only: !!this.install.listOnly,
          run: true,
        };
        const res = await api("/api/install", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        this.install.lastResult = res;
        if (res.exit_code === 0) {
          this.toast(`Installed via ${res.runner}: ${res.source}`, "ok");
          await this.loadScopes();
          await this.loadSkills();
        } else {
          this.toast(`Install exited ${res.exit_code}: ${(res.stderr || res.stdout || "").slice(0, 200)}`, "err");
        }
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    registryReady() {
      return this.install.registryOp === "browse" || this.install.registryOp === "curated"
        || !!(this.install.source && this.install.source.trim());
    },

    async runRegistry() {
      if (!this.registryReady()) {
        this.toast("Enter a registry query or skill id first.", "err");
        return;
      }
      // A new request retires the prior review before its response arrives;
      // the commit action can never be mistaken for the new form values.
      this.install.review_id = null;
      this.install.review = null;
      this.install.committed = null;
      this.install.lastResult = null;
      this.busy = true;
      this.install.reading = true;
      this.install.error = null;
      try {
        const op = this.install.registryOp;
        const payload = {
          browse: op === "browse" ? true : undefined,
          search: op === "search" ? this.install.source.trim() : undefined,
          curated: op === "curated" ? true : undefined,
          fetch: op === "fetch" ? true : undefined,
          source: op === "fetch" ? this.install.source.trim() : undefined,
          page: Number(this.install.page) || 0,
          per_page: Number(this.install.perPage) || 25,
          view: this.install.view || "all-time",
          allow_stale: !!this.install.allowStale,
        };
        const res = await api("/api/install", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        this.install.lastResult = res;
        if (op === "fetch") {
          this.install.review_id = res.review_id || null;
          this.install.review = res.review_id ? res : null;
          if (res.review_id) {
            this.toast("Registry snapshot reviewed locally. Inspect the evidence before trusting it.", "info");
          } else {
            this.toast("Registry fetch returned no review id; nothing was installed.", "err");
          }
        } else {
          this.toast(`Registry ${op} loaded (${(res.data || []).length} result groups).`, "ok");
        }
      } catch (e) {
        // A toast is gone in four seconds, and a registry read that failed is
        // the whole content of this page — so the pane states it, in the
        // backend's own words rather than a sentence invented here (RULES #12).
        // The toast stays: it names the failure at the moment it happens,
        // wherever the reader happens to be.
        this.install.error = e && e.message ? e.message : String(e);
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
        /* `reading` clears in the same `finally` as `busy`, and on the failure
           path too: a read that failed leaves the error banner, not a spinner
           that never stops. */
        this.install.reading = false;
      }
    },

    async commitRegistryReview() {
      const review = this.install.review;
      if (!review || !review.review_id) { this.toast("Fetch a registry snapshot for review first.", "err"); return; }
      this.busy = true;
      try {
        const res = await api("/api/install", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fetch: true, review_id: review.review_id, trust_confirmed: true }),
        });
        /* The commit response is KEPT, not written into `lastResult` and read
           back out of it. It has no `exit_code` (so `installRunnerResult` calls
           it a runner failure), no `data` (so `installRows` calls it an empty
           listing) and no `_registry` (so `installMeta` calls it un-cached) —
           three different false readings from one field written by two halves.
           `committed` is its own state, so "installed" cannot be mistaken for a
           listing and the stepper can stay on step three. */
        this.install.committed = res;
        this.install.review_id = null;
        this.install.review = null;
        this.toast(`Installed ${res.name} from the reviewed registry snapshot.`, "ok");
        await this.loadScopes();
        await this.loadSkills();
      } catch (e) {
        /* A failed commit must NOT be swallowed into the pane. The review is
           still pending server-side and still committable, so `review` and
           `committed` are both left exactly as they were — the only thing that
           changes is that the reader is told, on the pane whose whole content
           is this transaction, rather than in a toast that is gone in four
           seconds (5.1's rule). */
        this.install.error = e && e.message ? e.message : String(e);
        this.toast(this.install.error, "err");
      } finally {
        this.busy = false;
      }
    },

    async loadSkills() {
      const mySeq = ++this.listSeq;
      const scopeAtCall = this.activeScope || "all";
      this.loadingList = true;
      this.banner = null;
      try {
        const s = scopeAtCall;
        const rows = await api("/api/skills?scope=" + encodeURIComponent(s));
        if (mySeq !== this.listSeq || (this.activeScope || "all") !== scopeAtCall) return;
        /* A response is proof the server answered. Clear the global banner on
         * the success path only -- never on a timer, so a flapping connection
         * still shows the reader the last moment it worked. */
        this.offline = false;
        this.skills = rows;
        this.allSkills = rows.slice();
        /* Success path only: this read is what makes the page's age claim true. */
        this.lastScanAt = Date.now();
        if (this.query.trim() && this.view === "skills") this.applySearch();
        if (this.selectedName) {
          const still = this.skills.find((sk) => sk.name === this.selectedName && (s === "all" || sk.scope === s));
          if (still) {
            // The list already re-read the filesystem. Only re-read the detail
            // when that row actually changed, so a navigation that refreshes
            // the list does not also re-download the document body and its
            // frontmatter for a skill the reader did not touch.
            if (this.detailIsCurrent(still)) this.selected = { ...this.selected, ...this.detailObservations(still) };
            else this.loadDetail(still.name, still.scope);
          } else { this.selectedName = null; this.selected = null; }
        }
      } catch (e) {
        if (mySeq !== this.listSeq) return;
        /* A `fetch` that rejects before a response is a transport failure: the
         * server did not answer at all. That is a different condition from a
         * 4xx/5xx (which arrive as a real response and become a normal banner
         * message), so it is the one case that raises the global offline
         * banner. Anything else stays a scoped message. */
        const unreachable = e instanceof TypeError;
        if (unreachable) this.offline = true;
        /* A failed read retires the age claim: "Scanned 4 min ago" describes a
         * read that happened, and the page now shows rows it could not
         * refresh. Null is honest; the old stamp would not be. */
        this.lastScanAt = null;
        this.banner = {
          type: unreachable ? "warn" : "error",
          text: unreachable
            ? "The local server did not answer. Start it, then retry — what is shown below is the last observed state."
            : "Could not load skills: " + e.message,
        };
      } finally {
        if (mySeq === this.listSeq) this.loadingList = false;
      }
    },

    /* Identity of the exact physical instance a detail belongs to. Two reads
     * of an unchanged document produce the same signature, which is what lets
     * a list refresh reuse the detail instead of re-fetching it. */
    detailSignature(record) {
      if (!record) return "";
      return [
        record.name, record.scope, record.physical_path || record.path || "",
        record.content_hash || "", record.disabled ? "1" : "0",
        record.malformed ? "1" : "0", record.addressable === false ? "0" : "1",
      ].join("|");
    },

    detailIsCurrent(row) {
      if (!this.selected || this.selected.name !== row.name) return false;
      if ((this.selected.scope || null) !== (row.scope || null)) return false;
      return this.detailSignature(this.selected) === this.detailSignature(row);
    },

    /* List rows carry the observed fields the detail pane shows beside the
     * document; the body and raw frontmatter stay from the last detail read. */
    detailObservations(row) {
      const carried = {};
      for (const key of ["scope", "scope_label", "physical_root", "physical_path",
        "root_availability", "addressable", "consumer", "disabled", "path",
        "malformed", "decode_error", "content_hash", "tokens", "tokens_pct",
        "description", "category", "license", "version", "updated_at", "provenance"]) {
        if (row[key] != null) carried[key] = row[key];
      }
      return carried;
    },

    /* A METHOD, not a computed, and the distinction is load-bearing: Vue's
       render proxy UNWRAPS a computed before the template sees it, so a
       `computed` called as `qualityCategoryLabel(group.category)` resolves to
       the string it returns and the template throws
       "qualityCategoryLabel is not a function" — the whole view's evidence
       section renders nothing at all, silently, with no console-free build. */
    qualityCategoryLabel(category) {
      return SkillManagerDomain.hygieneCategoryLabel(category);
    },

    async loadQualityHygiene() {
      const scopeAtCall = this.activeScope || "all";
      this.qualityHygieneLoading = true;
      this.qualityHygieneError = null;
      try {
        const report = await api("/api/doctor?scope=" + encodeURIComponent(scopeAtCall) + "&hygiene=1");
        if ((this.activeScope || "all") !== scopeAtCall) return;
        this.qualityHygiene = report.hygiene || null;
        if (!this.qualityHygiene) this.qualityHygieneError = "The server returned no hygiene report.";
        this.announce("Skill hygiene evidence refreshed.");
      } catch (e) {
        this.qualityHygieneError = e.message;
        this.announce("Skill hygiene evidence could not be loaded.");
      } finally {
        this.qualityHygieneLoading = false;
      }
    },

    async applySearch() {
      const q = this.query.trim();
      if (!q) {
        // Restore the last complete scope immediately while the authoritative
        // refresh settles. This keeps clearing search responsive even when a
        // local scan takes longer than the debounce window.
        if (this.allSkills.length) this.skills = this.allSkills.slice();
        if (this.view === "skills") this.loadSkills();
        return;
      }
      if (["install", "recovery", "quality"].includes(this.view)) return;
      if (this.view !== "skills" && this.view !== "trash") {
        this.view = "skills";
        this.mobileDetailOpen = false;
        this.compactControlsOpen = false;
      }
      if (this.view === "trash") return;
      // The complete scope snapshot is already local, so filtering it here
      // keeps search and reset deterministic while preserving the server API
      // for clients that still use it directly.
      const needle = q.toLowerCase();
      const source = this.allSkills.length ? this.allSkills : this.skills;
      this.skills = source.filter((record) => [record.name, record.description, record.category, ...(record.tags || [])]
        .some((value) => String(value || "").toLowerCase().includes(needle)));
      this.loadingList = false;
    },

    async loadTrash() {
      this.loadingTrash = true;
      try {
        this.trashSkills = await api("/api/trash");
        /* 6.3 — cleared on the SUCCESS path only, never on a timer: a flapping
         * connection must keep saying what it last failed to do. */
        this.trashError = null;
      } catch (e) {
        this.trashError = "Could not read the global trash: " + e.message;
        this.toast(this.trashError, "err");
      } finally {
        this.loadingTrash = false;
      }
    },

    async loadOverviewHistory() {
      this.loadingHistory = true;
      try {
        this.overviewHistory = await api("/api/history?limit=8");
        this.overviewHistoryError = null;
      } catch (e) {
        /* 6.3 — this catch was completely silent: no toast, no state, and the
         * Overview then said "No history entries yet." about a store it had
         * never successfully read. */
        this.overviewHistory = [];
        this.overviewHistoryError = "Could not read recent activity: " + e.message;
        this.toast(this.overviewHistoryError, "err");
      } finally {
        this.loadingHistory = false;
      }
    },

    async loadDetail(name, scope) {
      const mySeq = ++this.detailSeq;
      const sc = scope || (this.selected && this.selected.scope) || this.activeScope;
      const scopeParam = sc && sc !== "all" ? "?scope=" + encodeURIComponent(sc) : "";
      // When scope is "all", find the skill's scope from the list.
      let effScope = sc;
      if (!effScope || effScope === "all") {
        const hit = this.skills.find((s) => s.name === name);
        effScope = (hit && hit.scope) ? hit.scope : "global";
      }
      const qp = "?scope=" + encodeURIComponent(effScope);
      this.loadingDetail = true;
      try {
        const record = await api("/api/skills/" + encodeURIComponent(name) + qp);
        if (mySeq !== this.detailSeq) return;
        try {
          const text = await apiText("/api/skills/" + encodeURIComponent(name) + "/raw" + qp);
          Object.assign(record, parseFrontmatter(text));
        } catch (e) {
          if (mySeq === this.detailSeq) {
            this.toast("Could not load full metadata (compatibility may be missing).", "err");
          }
        }
        if (mySeq !== this.detailSeq) return;
        const observed = [...(this.skills || []), ...(this.allSkills || [])].find((item) =>
          item && item.name === name && (!effScope || effScope === "all" || item.scope === effScope));
        if (observed) {
          for (const key of ["scope", "scope_label", "physical_root", "physical_path", "root_availability", "addressable", "consumer", "disabled", "path"]) {
            if (record[key] == null && observed[key] != null) record[key] = observed[key];
          }
        }
        this.selected = record;
        this.selectedName = name;
        if (this.view === "recovery") this.loadRecoverySnapshots();
      } catch (e) {
        if (mySeq !== this.detailSeq) return;
        this.toast("Could not load skill: " + e.message, "err");
        this.selected = null;
      } finally {
        if (mySeq === this.detailSeq) this.loadingDetail = false;
      }
    },

    /* ---------------------------------------------------------- row keys */

    /* Move focus between Library rows with j/k (and the arrow keys, which are
     * what a reader who does not know the letters already tries).
     *
     * WHY FOCUS AND NOT SELECTION. Each row already handles Enter and Space on
     * itself, guarded with `.self` so a keypress inside a row's checkbox does
     * not also open the detail. Moving DOM focus therefore composes with what
     * is there instead of adding a second path to the same action -- and the
     * focused row is the one the a11y tree announces, which a "current row"
     * that is only styled is not.
     *
     * WHY IT STOPS AT THE ENDS. The command palette deliberately wraps
     * (2.2): it is a flat set you are hunting through, and wrapping makes the
     * last item reachable from the first without walking back. A list is
     * positional and ordered -- wrapping j from the last row to the first
     * would move focus without the list having changed, so a reader cannot
     * tell whether anything happened. Clamp, and do not pretend otherwise.
     */
    moveRowFocus(delta) {
      // One `<ul>` carries both presentations (`:class="['skilllist', ...]"`),
      // so one selector covers List and Grid. Rows that are not rows -- the
      // batch bar, the selection hint, a skeleton, an empty state -- carry no
      // `data-skill-key` and are excluded by the same query.
      const rows = Array.from(
        document.querySelectorAll(".skilllist > li[data-skill-key]")
      );
      if (!rows.length) return false;
      const current = rows.indexOf(document.activeElement);
      const next = current === -1
        ? (delta > 0 ? 0 : rows.length - 1)
        : Math.min(rows.length - 1, Math.max(0, current + delta));
      const row = rows[next];
      if (!row || row === document.activeElement) return false;
      row.focus();
      if (typeof row.scrollIntoView === "function") {
        row.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
      return true;
    },

    /* ------------------------------------------------------- 5.7b settings rail
       Moves focus to the section the reader chose from the side column. The
       section carries `tabindex="-1"` for exactly this: a keyboard reader who
       presses it lands on the subject instead of being left at the top of the
       document with the screen reader still announcing the side column.

       `settingsSection` is set first and unconditionally, so the marker in the
       rail is true even if the section is missing from the DOM (it cannot be
       — `SETTINGS_SECTIONS` is the list the template renders from — but a
       marker that depends on a successful lookup is a marker that can go
       stale). Focus is guarded because `focus()` throws on some engines when
       the node is not focusable, and a broken rail must not take the view
       down with it. */
    jumpToSetting(id) {
      if (!SETTINGS_SECTIONS.some((entry) => entry.id === id)) return;
      this.settingsSection = id;
      this.$nextTick(() => {
        const target = document.getElementById(id);
        if (!target) return;
        if (typeof target.scrollIntoView === "function") {
          target.scrollIntoView({ block: "nearest" });
        }
        try { target.focus({ preventScroll: true }); } catch (err) { target.focus(); }
      });
    },

    selectSkill(s) {
      // BUG-3: the list keys rows by scope+name and the UI supports the same
      // skill name in several scopes, so comparing the name alone made
      // clicking another scope's copy a no-op that left the detail pane
      // showing the first scope's record.
      if (
        this.selectedName === s.name
        && this.selected
        && this.selected.scope === (s.scope || null)
      ) {
        this.mobileDetailOpen = true;
        return;
      }
      this.mobileReturnKey = (s.scope || "") + "/" + s.name;
      this.mobileDetailOpen = true;
      /* 4.4: a NEW skill starts on Overview. Resetting only when the identity
         changes is the whole point — resetting on every `loadDetail` would
         yank a reader off the History tab when they pressed Enable, which is
         the one action whose result belongs on that tab. */
      this.detailTab = "overview";
      this.loadDetail(s.name, s.scope);
    },

    /* ------------------------------------------------------- 4.4 detail tabs */
    selectDetailTab(id) {
      if (!this.detailTabs.some((tab) => tab.id === id)) return;
      this.detailTab = id;
      /* History is the only panel that needs a fetch, and a pane the reader
         cannot see is a request they did not ask for. Fetched on first open,
         not on selection — a reader who reads the document should not pay
         for a history table they never looked at. */
      if (id === "history") this.ensureDetailHistory();
    },

    /* 5.1. Switching source RETIRES the previous answer rather than letting it
       sit under a tab that does not describe it. `install.lastResult` is the
       only record of what the pane is showing, and a result from Curated left
       up while the reader reads Browse is exactly the "stale sentence beside a
       correct bar" pair 3.3 got wrong. The error goes with it. */
    selectInstallSource(id) {
      if (!this.installSources.some((s) => s.id === id)) return;
      if (this.install.registryOp === id) return;
      this.install.registryOp = id;
      this.install.lastResult = null;
      this.install.error = null;
      /* No request is fired here on purpose: `browse`/`curated` without a token
         and `search` under two characters are all requests the route is certain
         to reject, and a page that fires them to find out is a page that
         produces a red banner for doing nothing. */
    },
    selectInstallWorkflow(id) {
      if (!this.installWorkflows.some((w) => w.id === id)) return;
      if (this.install.mode === id) return;
      this.install.mode = id;
      /* The error belongs to the workflow that failed. Carrying it across the
         switch would name the WRONG workflow in the banner that opens with it
         ("Registry did not complete" for a commit that failed under Fetch &
         trust) — `selectInstallSource` has always cleared it for exactly this
         reason, and `fetch` set `registryOp` without inheriting the habit. */
      this.install.error = null;
      /* `fetch` is a registry operation but it is NOT one of the three READ
         sources the strip owns, so it rides on `registryOp` rather than
         becoming a fourth tab: `runRegistry` already switches on it and the
         route already refuses to combine it with another operation
         (webapp.py:96). Coming back to the read half restores a tab this strip
         can actually show — landing on a tablist with no tab selected is the
         state 5.1b was written to avoid. */
      if (id === "fetch") {
        this.install.registryOp = "fetch";
      } else if (id === "registry" && !this.installSources.some((s) => s.id === this.install.registryOp)) {
        this.install.registryOp = this.installSources[0].id;
      }
    },
    /* The agents list was parsed by an inline `@change` expression in the dialog.
       Two forms cannot each carry their own copy of a comma split — they drift,
       and the drift is invisible until a request sends `-a claude-code` twice.
       One parser, both call sites. */
    syncInstallAgents() {
      this.install.agents = String(this.install.agentsText || "").split(",").map((s) => s.trim()).filter(Boolean);
    },
    onInstallTabKey(event) {
      const ids = this.installSources.map((s) => s.id);
      const at = ids.indexOf(this.install.registryOp);
      let next = null;
      if (event.key === "ArrowRight") next = (at + 1) % ids.length;
      else if (event.key === "ArrowLeft") next = (at - 1 + ids.length) % ids.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = ids.length - 1;
      /* Only these four keys are consumed — the same rule as the detail strip
         above. `/` focuses search, Escape and the palette belong to their own
         handlers, and a three-tab strip has nothing to close. */
      if (next === null) return;
      event.preventDefault();
      this.selectInstallSource(ids[next]);
      const el = event.currentTarget.querySelector('[data-install-tab="' + ids[next] + '"]');
      if (el) el.focus();
    },

    onDetailTabKey(event) {
      const ids = this.detailTabs.map((tab) => tab.id);
      const at = ids.indexOf(this.detailTab);
      let next = null;
      if (event.key === "ArrowRight") next = (at + 1) % ids.length;
      else if (event.key === "ArrowLeft") next = (at - 1 + ids.length) % ids.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = ids.length - 1;
      /* Only these four keys are consumed. Escape, j/k, `/` and the palette
         belong to their own handlers, and a strip that swallowed Escape would
         trap the reader in a five-panel pane. */
      if (next === null) return;
      event.preventDefault();
      this.selectDetailTab(ids[next]);
      /* Focus, not just selection: roving tabindex means the DOM focus has to
         follow the arrow or Tab lands on the button the reader just left. */
      const el = event.currentTarget.querySelector('[data-detail-tab="' + ids[next] + '"]');
      if (el) el.focus();
    },

    async ensureDetailHistory(force = false) {
      const selected = this.selected;
      if (!selected || !selected.name) return;
      const key = (selected.scope || "global") + "/" + selected.name;
      const current = this.detailHistory;
      /* One in-flight request per (scope, name). `force` is the Refresh
         button and `rollbackSnapshot`, both of which mean "ask again". */
      if (!force && current.key === key && (current.loaded || current.loading)) return;
      this.detailHistory = { key, rows: [], snapshots: [], loading: true, error: "", loaded: false };
      try {
        const name = encodeURIComponent(selected.name);
        const rows = await api("/api/history?limit=200&name=" + name);
        const scope = encodeURIComponent(selected.scope || "global");
        const result = await api("/api/history?name=" + name + "&scope=" + scope + "&snapshots=1");
        /* The reader may have switched skill or scope while this was in
           flight. Writing then would land the OLD skill's rows under the NEW
           skill's heading — a table that is confidently wrong, which is the
           failure mode this product treats as worse than an empty one. */
        if (this.detailHistory.key !== key) return;
        this.detailHistory = {
          key, rows: (rows || []).filter(Boolean), snapshots: result.snapshots || [],
          loading: false, error: "", loaded: true,
        };
      } catch (e) {
        if (this.detailHistory.key !== key) return;
        this.detailHistory = { key, rows: [], snapshots: [], loading: false, error: e.message, loaded: true };
      }
    },

    closeMobileDetail() {
      this.mobileDetailOpen = false;
      this.$nextTick(() => {
        const row = [...document.querySelectorAll("[data-skill-key]")]
          .find((el) => el.dataset.skillKey === this.mobileReturnKey);
        if (row) row.focus();
      });
    },

    closeMobileView() {
      this.mobileDetailOpen = false;
      this.$nextTick(() => {
        const label = this.view === "trash" ? "Trash" : this.view.charAt(0).toUpperCase() + this.view.slice(1);
        const tab = [...document.querySelectorAll('.viewtabs button')]
          .find((el) => (el.innerText || '').trim().startsWith(label));
        if (tab) tab.focus();
      });
    },

    selectTrash(t) {
      this.selectedTrash = this.selectedTrash && this.selectedTrash.trash_path === t.trash_path ? null : t;
      this.mobileReturnKey = "trash/" + (t && t.trash_path || "");
      this.mobileDetailOpen = true;
    },

    switchView(v) {
      this.view = v;
      // Keep auxiliary lists visible on phones; a selected item can then move
      // to its detail state and the explicit back action returns to that list.
      this.mobileDetailOpen = false;
      this.compactControlsOpen = false;
      // A destination picked in the drawer closes it, and restores whatever the
      // scope/context disclosure was doing before the drawer opened.
      if (this.drawerOpen) this.closeDrawer();
      if (v === "trash" || v === "recovery") this.loadTrash();
      if (v === "recovery") this.loadRecoverySnapshots();
      else if (v === "install") {
        this.loadSkills();
        /* 5.1b: arriving from the dialog can leave the registry operation on
           `fetch`, which the view's source strip does not own. Same reason,
           different door. 5.2: `fetch` is now a workflow the view DOES own, so
           leaving it selected while the read strip is showing would mean a tab
           list with no tab selected. */
        if (this.install.mode !== "fetch" && !this.installSources.some((s) => s.id === this.install.registryOp)) {
          this.install.registryOp = this.installSources[0].id;
        }
      }
      else if (v === "workspaces") this.loadWorkspaces();
      else if (v === "quality") this.loadQualityHygiene();
      // BUG-4: entering the skills view with a live query must re-apply it, or
      // the list silently disagrees with the search box.
      else if (v === "skills") this.refreshList();
      if (v === "overview") this.loadOverviewHistory();
      this.$nextTick(() => {
        this.scrollActiveViewTab();
        const heading = v === "skills"
          ? document.querySelector("#library-view-title")
          : document.querySelector("#view-title, #overview-title, #install-view-title");
        if (heading) heading.focus();
      });
    },

    scrollActiveViewTab() {
      if (typeof window === "undefined" || !window.matchMedia
        || !window.matchMedia("(max-width: 760px)").matches) return;
      const active = document.querySelector(".navigation-rail .viewtabs button.active");
      if (active && typeof active.scrollIntoView === "function") {
        active.scrollIntoView({ block: "nearest", inline: "center" });
      }
    },

    openOverviewSkill(group) {
      const record = group && (group.primary || (group.instances || [])[0]);
      this.filter = "";
      this.tagFilter = "";
      this.query = "";
      if (record) {
        // Pin the requested identity before switchView refreshes the list. A
        // stale selection here lets the refresh start a competing detail load
        // for the skill that was selected before returning to Overview.
        this.selectedName = record.name;
        this.selected = null;
        this.mobileReturnKey = (record.scope || "") + "/" + record.name;
        this.mobileDetailOpen = true;
      }
      this.switchView("skills");
      if (record) this.$nextTick(() => this.selectSkill(record));
    },

    openOverviewAttention(key) {
      if (key === "recovery") {
        this.switchView("recovery");
        return;
      }
      if (key === "disabled") {
        this.query = "";
        this.tagFilter = "";
        this.filter = "disabled";
        // The filter changes the visible list; clear any prior detail so it
        // cannot contradict the disabled-only result set.
        this.selectedName = null;
        this.selected = null;
        this.switchView("skills");
        return;
      }
      const group = key === "divergent"
        ? this.overviewDivergentGroups[0]
        : this.overviewLogicalSkills.find((item) => (item.instances || []).some((record) => {
          // The same predicate that built the attention item, so the deep link
          // cannot point at a group the queue did not count.
          const observed = observeRecord(record);
          return observed.malformedDocument || observed.notAddressable;
        }));
      this.openOverviewSkill(group);
    },

    /* Refresh the skills list, honouring an active search query (BUG-4). */
    refreshList() {
      if (this.query && this.query.trim() && this.view === "skills") {
        return this.applySearch();
      }
      return this.loadSkills();
    },

    setFilter(f) {
      this.filter = f;
    },

    setTagFilter(tag) {
      this.tagFilter = tag || "";
    },

    qualityFindingIsExpanded(id) {
      return this.qualityExpandedFindings.includes(id);
    },

    toggleQualityFinding(id) {
      const current = new Set(this.qualityExpandedFindings);
      if (current.has(id)) current.delete(id); else current.add(id);
      this.qualityExpandedFindings = [...current];
    },

    inspectHygieneInstance(instance, finding = null) {
      const targetPath = instance && (instance.physical_path || instance.path);
      const record = this.qualityRecords.find((item) => item.name === (instance && instance.name)
        && item.scope === (instance && instance.scope)
        && (!targetPath || (item.physical_path || item.path) === targetPath));
      if (!record) {
        this.toast("That exact observed instance is no longer in the current Library snapshot.", "err");
        return;
      }
      this.query = "";
      this.filter = "";
      this.tagFilter = "";
      this.selectedName = record.name;
      this.selected = record;
      this.switchView("skills");
      this.$nextTick(() => {
        this.selectSkill(record);
        if (finding && finding.category === "broken-reference") this.openValidate();
      });
    },

    retryQualityHygiene() {
      return this.loadQualityHygiene();
    },

    /* 6.3 — one retry for every read whose failure is now state. Each one
     * re-runs the loader that failed, so the error clears only when the same
     * request actually succeeds. A retry control that hid the error without
     * re-reading would be the defect wearing a fix's clothes. */
    retryTrash() { return this.loadTrash(); },
    retryOverviewHistory() { return this.loadOverviewHistory(); },
    retryRecoverySnapshots() { return this.loadRecoverySnapshots(); },
    retryWorkspaces() { return this.loadWorkspaces(); },

    onSearchKeydown(e) {
      // Keep the native select-all shortcut reliable for keyboard and browser
      // automation users before a following Backspace/Delete clears the field.
      // Some embedded Chromium contexts expose the shortcut without applying
      // the selection to a type=search control.
      if ((e.ctrlKey || e.metaKey) && String(e.key || "").toLowerCase() === "a") {
        e.preventDefault();
        e.target.select();
      }
    },

    menuItems() {
      if (!this.$refs.menuWrap) return [];
      return [...this.$refs.menuWrap.querySelectorAll('[role="menuitem"]:not([disabled])')];
    },

    focusFirstMenuItem() {
      const first = this.menuItems()[0];
      if (first) first.focus();
    },

    toggleActionsMenu() {
      if (this.menuOpen) {
        this.closeActionsMenu(true);
        return;
      }
      this.menuOpen = true;
      this.$nextTick(() => this.focusFirstMenuItem());
    },

    closeActionsMenu(restoreFocus = false) {
      this.menuOpen = false;
      if (restoreFocus) {
        const trigger = this.$refs.menuTrigger;
        this.$nextTick(() => trigger && trigger.focus());
      }
    },

    onMenuKeydown(e) {
      const items = this.menuItems();
      if (!items.length) return;
      if (e.key === "Escape") {
        e.preventDefault();
        this.closeActionsMenu(true);
        return;
      }
      const index = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const delta = e.key === "ArrowDown" ? 1 : -1;
        items[(index + delta + items.length) % items.length].focus();
      } else if (e.key === "Home") {
        e.preventDefault();
        items[0].focus();
      } else if (e.key === "End") {
        e.preventDefault();
        items[items.length - 1].focus();
      }
    },

    clearSearch() {
      this.query = "";
      this.$nextTick(() => this.$refs.searchInput && this.$refs.searchInput.focus());
    },

    /* The empty pane's "Clear filters" only clears FILTERS. It deliberately
     * leaves `activeScope` alone: scope is the reader's location, not a filter
     * they applied to a list they were just reading, and silently widening a
     * scope is how a destructive-looking "clear" becomes one. */
    clearLibraryFilters() {
      this.filter = "";
      this.tagFilter = "";
      this.query = "";
    },

    toggleCommandPalette(event) {
      if (this.activeModal && this.activeModal !== "commands") return;
      if (this.modals.commands) {
        this.closeModal("commands");
        return;
      }
      this.openCommandPalette(event && event.currentTarget);
    },

    openCommandPalette(opener = null) {
      if (this.activeModal && this.activeModal !== "commands") return;
      this.menuOpen = false;
      this.commandPaletteQuery = "";
      this.commandPaletteActiveIndex = 0;
      this.openModal("commands", {});
      if (opener && opener.matches && opener.matches(".command-trigger")) {
        this.modalRestoreFocus = opener;
      } else if (document.activeElement === document.body || document.activeElement === document.documentElement) {
        this.modalRestoreFocus = document.querySelector(".command-trigger") || this.modalRestoreFocus;
      }
    },

    scrollActiveCommandIntoView() {
      const active = this.commandPaletteActiveCommand;
      if (!active) return;
      const option = document.getElementById("command-option-" + active.id);
      if (option && typeof option.scrollIntoView === "function") option.scrollIntoView({ block: "nearest" });
    },

    moveCommandPaletteSelection(delta) {
      const count = this.filteredCommandPaletteCommands.length;
      if (!count) return;
      this.commandPaletteActiveIndex = (this.commandPaletteActiveIndex + delta + count) % count;
    },

    onCommandPaletteKeydown(e) {
      const commands = this.filteredCommandPaletteCommands;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        this.moveCommandPaletteSelection(1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        this.moveCommandPaletteSelection(-1);
      } else if (e.key === "Home") {
        e.preventDefault();
        this.commandPaletteActiveIndex = 0;
      } else if (e.key === "End") {
        e.preventDefault();
        this.commandPaletteActiveIndex = Math.max(0, commands.length - 1);
      } else if (e.key === "Enter") {
        e.preventDefault();
        this.executeCommand(this.commandPaletteActiveCommand);
      } else if (e.key === "Escape") {
        e.preventDefault();
        this.closeModal("commands");
      }
    },

    executeCommand(command) {
      if (!command) return;
      const available = this.filteredCommandPaletteCommands.find((item) => item.id === command.id);
      if (!available) return;
      const opener = this.modalRestoreFocus;
      this.commandPaletteTransfer = !!available.focusDestination;
      this.closeModal("commands");
      this.$nextTick(() => {
        // Let Vue remove Commands before invoking the destination. This keeps
        // the destination opener distinct from the palette input and gives
        // navigation commands a stable render to focus.
        this.modalRestoreFocus = opener;
        this.invokeCommand(available);
        if (this.activeModal) {
          // A newly opened dialog owns restoration now, but it must return to
          // the original Commands trigger/opener when it closes.
          this.modalRestoreFocus = opener;
          this.commandPaletteTransfer = false;
        }
      });
    },

    invokeCommand(command) {
      const fn = this[command.action];
      if (typeof fn === "function") fn.apply(this, command.args || []);
    },

    /* The `?` shortcut already opened the reference inline in `onKeydown`.
       Routing both the key and the palette command through one method is the
       point: a shortcut that works from the keyboard but is unreachable from
       the command palette is two code paths, and they drift. */
    openShortcutsHelp() {
      this.openModal("help", {});
    },

    /* `/` focuses the search field only when the Library is the current view —
       the same guard the key handler applies. Navigating to Library first is
       the honest thing: the palette must not claim it moved focus somewhere
       the reader is not looking. */
    focusLibrarySearch() {
      if (this.view !== "skills") this.switchView("skills");
      this.$nextTick(() => this.$refs.searchInput && this.$refs.searchInput.focus());
    },

    refreshCommand() {
      this.loadScopes();
      this.loadSkills();
      this.loadTrash();
      this.loadCatalog();
      this.loadStatsTokens();
    },

    removeSelected() {
      if (this.selectedName && this.selected) this.confirmRemove(this.selected);
    },

    async updateBatchTags(operation) {
      /* 6.3b — 4.7b gave `toggleSelected` BOTH halves of the double-click
       * contract: a `busy` guard before the request AND `:disabled="busy"` on
       * the button. This handler had NEITHER, and it is the one batch verb that
       * writes without a dialog in between — `openBatch` opens a review, this
       * POSTs straight to `/api/catalog/tags`. Measured on arrival: two
       * presses inside one frame produced two requests, and because the
       * handler ends with `clearSelection()` the second one re-reads a
       * selection that no longer exists. A reader who was not sure the first
       * landed is not a second decision — same rule, same reason. */
      if (this.busy) return;
      if (!this.selectedTargets.length) { this.toast("Select at least one skill instance.", "err"); return; }
      const tags = this.batchTagInput.split(",").map((tag) => tag.trim()).filter(Boolean);
      if (!tags.length) { this.toast("Enter at least one tag.", "err"); return; }
      this.busy = true;
      try {
        this.catalog = await api("/api/catalog/tags", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ operation, names: [...new Set(this.selectedTargets.map((record) => record.name))], tags }),
        });
        this.clearSelection();
        this.batchTagInput = "";
        await this.loadSkills();
        this.toast("Tags updated for the selected logical skills.");
      } catch (e) { this.toast(e.message, "err"); }
      finally { this.busy = false; }
    },

    openBatch(operation, explicitTargets = null, context = null) {
      const targets = (explicitTargets || this.selectedTargets).map((target) => Object.freeze({
        name: target.name,
        scope: target.scope,
        path: target.path || target.physical_path || "",
        physical_path: target.physical_path || target.path || "",
      }));
      if (!targets.length) { this.toast("Select at least one skill instance.", "err"); return; }
      const writableScopes = (this.scopes || []).filter((scope) => scope.id !== this.activeScope && scope.writable);
      this.modals.batch = { operation, targets: Object.freeze(targets.slice()), plan: null, context, toScopes: Object.fromEntries(writableScopes.map((scope) => [scope.id, true])), force: false };
      this.prepareBatch();
    },

    /* What this batch will do to THIS target, in the observed-state words the
       rest of the app uses. The dialog only ever printed the transition for
       `enable`, so a `disable`, `remove` or `sync` review listed names and
       paths and said nothing about what it was about to change — three of the
       four operations reviewed a change the reader could only infer.

       `disabled` is the field the backend's own `_execute_batch_post` compares
       against (`target["disabled"] == (not desired)` -> "already-set"), so this
       states the real branch the request will take rather than a guess. */
    batchOutcome(target) {
      const operation = this.modals.batch && this.modals.batch.operation;
      const alreadyDisabled = !!Number(target.disabled);
      if (operation === "enable") return alreadyDisabled ? "Disabled → Active" : "Active · no state change";
      if (operation === "disable") return alreadyDisabled ? "Disabled · no state change" : "Active → Disabled";
      if (operation === "remove") return alreadyDisabled ? "Disabled → Trash" : "Active → Trash";
      const chosen = Object.keys((this.modals.batch && this.modals.batch.toScopes) || {})
        .filter((id) => this.modals.batch.toScopes[id])
        .map((id) => (this.scopes.find((scope) => scope.id === id) || {}).label || id);
      return chosen.length ? `Active → copied to ${chosen.join(", ")}` : "Active · no target scope chosen";
    },

    async prepareBatch() {
      const modal = this.modals.batch;
      if (!modal) return;
      if (modal.operation === "sync") {
        const selectedScopes = Object.keys(modal.toScopes).filter((scope) => modal.toScopes[scope]);
        modal.to_scopes = selectedScopes;
      }
      this.busy = true;
      try {
        modal.plan = await api("/api/batch/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ operation: modal.operation, targets: modal.targets, to_scopes: modal.to_scopes || [], force: !!modal.force }),
        });
      } catch (e) { this.toast(e.message, "err"); }
      finally { this.busy = false; }
    },

    async executeBatch() {
      const modal = this.modals.batch;
      if (!modal || !modal.plan || !modal.plan.plan_id || !modal.targets || !modal.targets.length) return;
      this.busy = true;
      try {
        const result = await api("/api/batch/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ operation: modal.operation, plan_id: modal.plan.plan_id, targets: modal.targets, to_scopes: modal.to_scopes || [], force: !!modal.force }),
        });
        const failed = (result.results || []).filter((item) => item.status === "failed").length;
        this.closeModal("batch");
        this.clearSelection();
        await this.loadScopes();
        await this.loadSkills();
        if (modal.context && modal.context.profileName) await this.previewProfile(modal.context.profileName);
        this.toast(failed ? `Batch completed with ${failed} failure(s). See each item for details.` : `Batch ${modal.operation} completed for ${result.target_count} target(s).`, failed ? "err" : "ok");
      } catch (e) { this.toast(e.message, "err"); }
      finally { this.busy = false; }
    },

    async saveProfile() {
      const form = this.profileForm;
      if (!form.name.trim()) { this.toast("Profile name is required.", "err"); return; }
      // 5.3a: an edit is a save under an UNCHANGED name. If the field was
      // unlocked and retyped, this would post a second profile and leave the
      // original exactly as it was — so the divergence is refused here, where
      // the request is built, and not only by the disabled field in the markup.
      const editing = this.profileEditing;
      if (editing && form.name.trim() !== editing) {
        this.toast(`This editor saves over ${editing}. Cancel it to create a profile under a new name.`, "err");
        return;
      }
      this.busy = true;
      try {
        this.catalog = await api("/api/catalog/profiles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: form.name.trim(),
            description: form.description.trim(),
            skills: form.skills.split(",").map((name) => name.trim()).filter(Boolean),
            targets: form.targets.split(",").map((target) => target.trim()).filter(Boolean),
          }),
        });
        this.profileEditing = null;
        this.profileForm = { name: "", description: "", skills: "", targets: "" };
        this.toast(this.profileSaveOutcome);
      } catch (e) { this.toast(e.message, "err"); }
      finally { this.busy = false; }
    },

    /* 5.3a — the edit path. The backend upserts by name, so there is no
       update verb to discover: load the stored profile into the same form and
       let Save write over it. `skills`/`targets` are stored as arrays and the
       fields are comma-separated, so the join is stated here once. */
    editProfile(name) {
      const profile = (this.catalog.profiles || {})[name];
      if (!profile) return;
      this.profileEditing = name;
      this.profileForm = {
        name,
        description: profile.description || "",
        skills: (profile.skills || []).join(", "),
        targets: (profile.targets || []).join(", "),
      };
      this.$nextTick(() => {
        const field = document.getElementById("profile-description");
        if (!field) return;
        field.focus();
        field.scrollIntoView({ block: "center" });
      });
    },

    cancelProfileEdit() {
      this.profileEditing = null;
      this.profileForm = { name: "", description: "", skills: "", targets: "" };
    },

    /* 5.3b — WHICH profile the detail pane is showing. There used to be two
     * independent answers to this question on screen at once: the saved-row's
     * `aria-pressed` (the one being edited) and the preview heading (the one
     * last previewed), and nothing kept them in step. The mark now lives on the
     * master row and reads ONE function, so the row and the pane cannot
     * disagree. Editing wins over previewing: while `profileEditing` is set the
     * detail pane is literally showing that profile's fields. */
    profileCurrent(name) {
      if (!name) return false;
      if (this.profileEditing) return this.profileEditing === name;
      return !!(this.profilePreview && this.profilePreview.name === name);
    },

    async previewProfile(name) {
      try { this.profilePreview = await api("/api/catalog/profiles/" + encodeURIComponent(name) + "/preview"); }
      catch (e) { this.toast(e.message, "err"); }
    },

    openProfileBatch() {
      const targets = this.profileTargets();
      if (!targets.length) { this.toast("This profile has no observed physical instances to enable.", "err"); return; }
      const unresolved = this.profileUnresolvedMembers;
      this.openBatch("enable", targets, {
        profileName: this.profilePreview && this.profilePreview.name,
        unresolvedCount: unresolved.length,
        unresolvedMembers: unresolved.map((member) => member.name),
      });
    },

    confirmDeleteProfile(name) {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      if (!name) return;
      this.modals.deleteProfile = { name };
    },

    async doDeleteProfile() {
      const m = this.modals.deleteProfile;
      if (!m) return;
      const name = m.name;
      this.busy = true;
      try {
        this.catalog = await api("/api/catalog/profiles/" + encodeURIComponent(name), { method: "DELETE" });
        if (this.profileEditing === name) this.cancelProfileEdit();
        if (this.profilePreview && this.profilePreview.name === name) this.profilePreview = null;
        this.closeModal("deleteProfile");
        // The old toast was the constant string "Profile deleted." — the same
        // shape 4.2b removed from the Library's rows: a message that carries no
        // information about WHICH profile is gone, delivered next to a list
        // that may hold several. Naming it is the whole difference.
        this.toast('Profile "' + name + '" deleted. It is not in the trash.');
      } catch (e) { this.toast(e.message, "err"); }
      finally { this.busy = false; }
    },

    /* ---------------------------------------------------------- helpers */

    /* The ONE place that publishes to the live region, and it announces a
     * message ONCE. A live region only speaks when its text *changes*, so an
     * announcement that is never cleared is announced exactly once ever: two
     * identical consecutive failures ("Could not load skills: ...") would be
     * silent the second time, which is precisely when a repeating failure
     * matters most. Publish, then clear on the next tick, so the next
     * identical write is a change again.

     * This was `toast()` alone, and two hygiene sites wrote
     * `liveAnnouncement` directly with no clear -- so a second hygiene
     * refresh, and a refresh that succeeded and then failed, said nothing.
     * Fixing the toast and leaving two bypasses in place is the "declared but
     * unwired" class this repository keeps finding. */
    announce(text) {
      this.liveAnnouncement = text;
      this.$nextTick(() => { if (this.liveAnnouncement === text) this.liveAnnouncement = ""; });
    },

    toast(text, type = "ok", undo = null) {
      const id = ++this.toastSeq;
      const life = undo ? TOAST_UNDO_MS : TOAST_MS;
      /* Cap the stack. A burst is exactly when a reader needs the surface:
       * capping drops the OLDEST, because the newest describes the condition
       * that produced the rest. */
      this.toasts = [...this.toasts, { id, text, type, undo, life }].slice(-TOAST_MAX);
      this.announce(text);
      this.toastTimers[id] = setTimeout(() => this.dismissToast({ id }), life);
    },

    dismissToast(t) {
      const timer = this.toastTimers[t.id];
      if (timer) { clearTimeout(timer); delete this.toastTimers[t.id]; }
      this.toasts = this.toasts.filter((x) => x.id !== t.id);
    },

    async undoToast(t) {
      this.dismissToast(t);
      try { await t.undo(); } catch (e) { this.toast("Undo failed: " + e.message, "err"); }
    },

    /* Retry is a real request, not a re-render: it re-reads the inventory, the
     * trash and the history, and the banner clears itself only when one of
     * them succeeds. If they all fail, `offline` stays true and the reader is
     * not told a lie. */
    async retryFromOffline() {
      await this.loadSkills();
      await Promise.all([this.loadTrash(), this.loadHistory()]);
    },

    async copy(text) {
      try {
        await navigator.clipboard.writeText(text);
      } catch (e) {
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
      }
      this.toast("Path copied to clipboard.");
    },

    normalizeThemePreference(value) {
      return ["light", "dark", "system"].includes(value) ? value : "system";
    },

    normalizeLocale(value) {
      const supported = ["system", ...this.localeOptions.map((option) => option.value)];
      return supported.includes(value) ? value : "system";
    },

    readSystemLocale() {
      const browserLocale = (typeof navigator !== "undefined" && navigator.language)
        || (typeof window !== "undefined" && window.navigator && window.navigator.language);
      return browserLocale || "en-US";
    },

    applyLocale(value) {
      const preference = this.normalizeLocale(value);
      let resolved = preference === "system" ? this.readSystemLocale() : preference;
      try {
        new Intl.NumberFormat(resolved).format(1234);
      } catch (e) {
        resolved = "en-US";
      }
      this.resolvedLocale = resolved;
      document.documentElement.dataset.locale = resolved;
      document.documentElement.dataset.localePreference = preference;
      // Keep the document language truthful until translated resources exist.
      document.documentElement.lang = "en";
    },

    readSystemTheme() {
      if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      }
      return "light";
    },

    applyThemePreference(value) {
      const preference = this.normalizeThemePreference(value);
      const systemTheme = this.readSystemTheme();
      const resolved = preference === "system" ? systemTheme : preference;
      this.systemTheme = systemTheme;
      this.resolvedTheme = resolved;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.dataset.themePreference = preference;
    },

    setupThemeListener() {
      this.removeThemeListener();
      if (this.theme !== "system" || typeof window === "undefined" || typeof window.matchMedia !== "function") return;
      this.themeMediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      this.themeMediaHandler = () => {
        if (this.theme === "system") this.applyThemePreference("system");
      };
      if (typeof this.themeMediaQuery.addEventListener === "function") {
        this.themeMediaQuery.addEventListener("change", this.themeMediaHandler);
      } else if (typeof this.themeMediaQuery.addListener === "function") {
        this.themeMediaQuery.addListener(this.themeMediaHandler);
      }
    },

    removeThemeListener() {
      if (!this.themeMediaQuery || !this.themeMediaHandler) {
        this.themeMediaQuery = null;
        this.themeMediaHandler = null;
        return;
      }
      if (typeof this.themeMediaQuery.removeEventListener === "function") {
        this.themeMediaQuery.removeEventListener("change", this.themeMediaHandler);
      } else if (typeof this.themeMediaQuery.removeListener === "function") {
        this.themeMediaQuery.removeListener(this.themeMediaHandler);
      }
      this.themeMediaQuery = null;
      this.themeMediaHandler = null;
    },

    /* 5.7c — the reduced-motion signal, subscribed rather than sampled once.
       Sampled once in `mounted()` would be a fact about the machine at load;
       a reader who turns reduced motion on while the app is open would still
       be told the OS has not asked for it. Same shape as the theme pair
       above, deliberately, so there is ONE listener idiom in this file. */
    setupMotionListener() {
      this.removeMotionListener();
      if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
      this.motionMediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      this.prefersReducedMotion = this.motionMediaQuery.matches;
      this.motionMediaHandler = (event) => {
        this.prefersReducedMotion = event.matches;
      };
      if (typeof this.motionMediaQuery.addEventListener === "function") {
        this.motionMediaQuery.addEventListener("change", this.motionMediaHandler);
      } else if (typeof this.motionMediaQuery.addListener === "function") {
        this.motionMediaQuery.addListener(this.motionMediaHandler);
      }
    },

    removeMotionListener() {
      if (!this.motionMediaQuery || !this.motionMediaHandler) {
        this.motionMediaQuery = null;
        this.motionMediaHandler = null;
        return;
      }
      if (typeof this.motionMediaQuery.removeEventListener === "function") {
        this.motionMediaQuery.removeEventListener("change", this.motionMediaHandler);
      } else if (typeof this.motionMediaQuery.removeListener === "function") {
        this.motionMediaQuery.removeListener(this.motionMediaHandler);
      }
      this.motionMediaQuery = null;
      this.motionMediaHandler = null;
    },

    setThemePreference(value) {
      this.theme = this.normalizeThemePreference(value);
    },

    applyTextSize(value) {
      const mode = value === "large" ? "large" : "standard";
      this.textSize = mode;
      document.documentElement.dataset.textSize = mode;
    },

    setTextSize(value) {
      this.textSize = value === "large" ? "large" : "standard";
    },

    toggleTheme() {
      const next = this.theme === "system" ? "light" : (this.theme === "light" ? "dark" : "system");
      this.setThemePreference(next);
    },

    closeModal(key) {
      this.modals[key] = null;
    },

    openModal(key, value = {}) {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals[key] = value;
      this.$nextTick(() => this.focusModal());
    },

    onKeydown(e) {
      this.trapModalFocus(e);
      this.trapDrawerFocus(e);
      const commandShortcut = (e.ctrlKey || e.metaKey) && String(e.key || "").toLowerCase() === "k";
      if (commandShortcut && (!this.activeModal || this.activeModal === "commands")) {
        e.preventDefault();
        this.toggleCommandPalette();
        return;
      }
      const tag = (e.target.tagName || "").toLowerCase();
      const typing = ["input", "textarea", "select"].includes(tag) || e.target.isContentEditable;
      /* Row keys. Library only, never while typing, never inside a dialog or
         the drawer -- the same exclusions `/`, `?` and Cmd-K already honour, so
         no new precedence had to be invented.

         The two menus are excluded too, and that is not tidiness: the scope
         menu and the actions menu both bind ArrowUp/ArrowDown, they open
         WITHOUT `activeModal` being set, and this branch runs before anything
         else would notice. INVENTORY flagged exactly this -- "arrow-key
         handlers do exist but they belong to other widgets".

         `j`/`k` are unconditional within those guards; the ARROWS only take
         over once focus is already on a row. A reader who has not entered the
         list yet is scrolling the pane with ArrowDown, and that first press
         must still scroll it. */
      const onRow = !!(e.target && e.target.closest
        && e.target.closest(".skilllist > li[data-skill-key]"));
      const rowKey = !typing && !this.activeModal && !this.drawerOpen && !this.scopeMenuOpen
        && !this.menuOpen && this.view === "skills"
        && (e.key === "j" || e.key === "k" || (onRow && (e.key === "ArrowDown" || e.key === "ArrowUp")))
        ? (e.key === "j" || e.key === "ArrowDown" ? 1 : -1)
        : 0;
      if (rowKey && this.moveRowFocus(rowKey)) {
        e.preventDefault();
        return;
      }
      if (e.key === "/" && !typing && !this.activeModal) {
        // Only a shortcut that will do something. Recovery and the other
        // filter-less views do not render the field, so swallowing `/` there
        // would be a keypress that visibly does nothing.
        if (!this.searchAppliesHere) return;
        e.preventDefault();
        this.$refs.searchInput && this.$refs.searchInput.focus();
      } else if (e.key === "?" && !typing && !this.activeModal) {
        e.preventDefault();
        this.openModal("help", {});
      } else if (e.key === "Escape") {
        // Topmost surface first. The scope menu can be open *inside* the drawer,
        // and a dialog opened from the drawer sits above it, so the drawer is
        // last — not because it is unimportant, but because it is the deepest.
        if (this.scopeMenuOpen) this.closeScopeMenu(true);
        else if (this.menuOpen) this.closeActionsMenu(true);
        else if (this.activeModal === "update") this.updateEscape();
        else if (this.activeModal === "skill") this.skillEscape();
        else if (this.activeModal) this.closeModal(this.activeModal);
        else if (this.drawerOpen) this.closeDrawer();
      }
    },

    onDocMousedown(e) {
      if (this.menuOpen && this.$refs.menuWrap && !this.$refs.menuWrap.contains(e.target)) {
        this.menuOpen = false;
      }
      if (this.scopeMenuOpen && this.$refs.scopeMenuWrap && !this.$refs.scopeMenuWrap.contains(e.target)) {
        this.scopeMenuOpen = false;
      }
    },

    menuDo(action) {
      this.menuOpen = false;
      const trigger = this.$refs.menuTrigger;
      if (trigger) trigger.focus();
      const actions = {
        create: this.openCreate,
        add: this.openAdd,
        edit: this.openEdit,
        toggle: this.toggleSelected,
        validate: this.openValidate,
        remove: () => this.selectedName && this.confirmRemove(this.selected),
        sync: this.openSync,
        update: this.openUpdate,
        /* 5.2d — `install: this.openInstall` is GONE, deliberately. Every
           command's `action` is looked up in this map, and after 5.2d no
           command names `openInstall` (the palette's Install row is
           `switchView`, the Overview button calls the method directly), so the
           entry was a key with no writer — the "declared and never read" class
           this repo has now found five times. 5.2b kept it and wrote a comment
           claiming two routes were deliberate; there has been one door since
           the dialog went. */
        help: () => this.openModal("help", {}),
        import: this.openImport,
        export: this.exportArchive,
        fullExport: () => this.exportArchive(true),
        templates: this.openTemplates,
        newtemplate: this.openNewTemplate,
        stats: this.openStats,
        doctor: this.openDoctor,
        history: this.openHistory,
        rebuild: this.rebuildIndex,
        resync: this.resyncIndex,
        refresh: () => { this.loadScopes(); this.loadSkills(); this.loadTrash(); this.loadCatalog(); this.loadStatsTokens(); },
      };
      const fn = actions[action];
      if (fn) fn.call(this);
    },

    /* 5.2b — ONE door. This used to raise a modal that carried a SECOND copy
       of the installer's form (operation, view, source, page size, stale
       cache, preview, review-and-trust) over the same `install.*` state. The
       view is the form now, so `openInstall` navigates there instead: the
       Overview button and the rail both land on the same page, and there is no
       second form left to drift. 5.2d: the palette's second Install row went
       too, so `openInstall` is called from markup only — it is not a palette
       action and there is no dispatch-map entry for it. */
    openInstall() {
      this.openInstallCenter();
    },

    /* ----------------------------------------------------- skill actions */

    openCreate() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      const defScope = (this.activeScope && this.activeScope !== "all") ? this.activeScope : "global";
      this.modals.skill = {
        mode: "create",
        form: { name: "", description: "", category: "", version: "", license: "", compatibility: "", allowed_tools: "", body: "", scope: defScope },
        errors: {},
        /* 4.5c — fields the reader has actually typed into. "Required" is only
           said about a field they filled and emptied; tabbing through a form
           you have not started must not scold you for it. */
        touched: {},
        confirmingClose: false,
      };
      this.captureSkillBaseline();
      nextTick(() => { const el = document.getElementById("f-name"); (el || this.modalElement())?.focus(); });
    },

    async openEdit() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      if (!this.selectedName) { this.toast("Select a skill first.", "err"); return; }
      const sc = (this.selected && this.selected.scope) ? this.selected.scope : (this.activeScope !== "all" ? this.activeScope : "global");
      this.modals.skill = {
        mode: this.selectedName,
        form: {
          name: this.selectedName,
          description: this.selected.description || "",
          category: this.selected.category || "",
          version: this.selected.version || "",
          license: this.selected.license || "",
          compatibility: this.selected.compatibility || "",
          allowed_tools: this.selected.allowed_tools || "",
          body: this.selected.body || "",
          // The Scope select is rendered for both modes and `saveSkill` falls
          // back to the selected skill's scope, so leaving it undefined made the
          // control render *blank* in Edit — a scope the reader cannot see and a
          // second vocabulary for "where this lives" that disagreed with the
          // one the Library list already used.
          scope: sc,
        },
        errors: {},
        /* 4.5c — fields the reader has actually typed into. "Required" is only
           said about a field they filled and emptied; tabbing through a form
           you have not started must not scold you for it. */
        touched: {},
        confirmingClose: false,
      };
      this.captureSkillBaseline();
      try {
        const qp = "?scope=" + encodeURIComponent(sc);
        const text = await apiText("/api/skills/" + encodeURIComponent(this.selectedName) + "/raw" + qp);
        const fm = parseFrontmatter(text);
        if (!this.modals.skill) return;
        if (fm.compatibility && !this.modals.skill.form.compatibility) this.modals.skill.form.compatibility = fm.compatibility;
        if (fm.allowed_tools && !this.modals.skill.form.allowed_tools) this.modals.skill.form.allowed_tools = fm.allowed_tools;
      } catch (e) { /* optional */ }
      // Re-baseline once the back-fill has settled -- see the note below.
      this.captureSkillBaseline();
    },

    /* ------------------------------------------------ unsaved changes (4.5)

    The editor could be dismissed four ways -- Cancel, the close glyph, a
    mousedown on the scrim, and Escape -- and all four were a bare
    `this.modals.skill = null`. A reader who spent twenty minutes in a body
    and mis-clicked the scrim lost all of it, with no error and no undo.

    This is the update review's shape, not a second invention:
    `requestCloseUpdate` + `modals.update.confirmingClose` already exists
    (`requestCloseUpdate`), so "you are about to drop something" has one
    vocabulary in the product instead of two.

    **The baseline is captured after `openEdit`'s `/raw` fetch settles.** That
    fetch back-fills `compatibility` and `allowed_tools` from the document on
    disk, so a snapshot taken at open would report the *application's own*
    edit as the reader's typing and ask them to discard a change they never
    made. The re-capture at the end of `openEdit` is that fix; capturing at
    open as well keeps a close-during-fetch honest rather than unguarded. */
    skillBaseline(form) {
      return ["name", "description", "category", "version", "license",
        "compatibility", "allowed_tools", "body", "scope"]
        .map((k) => String((form && form[k]) || ""))
        .join("\u0000");
    },

    captureSkillBaseline() {
      const m = this.modals.skill;
      if (m) m.baseline = this.skillBaseline(m.form);
    },

    skillFormDirty() {
      const m = this.modals.skill;
      if (!m || m.baseline == null) return false;
      return this.skillBaseline(m.form) !== m.baseline;
    },

    requestCloseSkill() {
      const m = this.modals.skill;
      if (!m) return;
      if (this.skillFormDirty()) {
        m.confirmingClose = true;
        /* The band is the first child of the scrolling `.modal-body`, and a
           reader who has scrolled down to the body textarea -- the single
           longest field in the form -- is exactly the one who pressed Escape
           or mis-clicked the scrim. Without this they are asked a question
           that rendered off-screen, which reads as "nothing happened". */
        this.$nextTick(() => {
          const band = document.querySelector('[data-modal="skill"] .banner');
          if (band && band.scrollIntoView) band.scrollIntoView({ block: "nearest" });
        });
        return;
      }
      this.closeModal("skill");
    },

    /* Escape while the confirmation is up clears the confirmation and leaves
       the reader in the editor. Pressing it again re-asks -- which is the
       point: a second Escape that destroyed the work would reintroduce the
       exact failure this task removes. */
    skillEscape() {
      const m = this.modals.skill;
      if (!m) return;
      if (m.confirmingClose) { m.confirmingClose = false; return; }
      this.requestCloseSkill();
    },

    /* 4.5c — ONE validator, read by both the blur handler and `saveSkill`.
       Two copies of a rule is how a form starts accepting what it then
       rejects; extracting it is what lets a test assert the two paths agree.

       The name rule is the SERVER's, not a taste decision: the catalog
       validator is `^[a-z0-9]+(-[a-z0-9]+)*$` over 1-64 characters, and this
       field's hint has always stated it in prose while nothing checked it —
       so the reader met the rule as a 400 and a toast. Saying it on blur is
       the same fact, earlier. In edit mode the name input is `:readonly`, so
       only the "required" branch applies there: an error the reader cannot act
       on is a guard that teaches them to dismiss errors. */
    skillFieldError(field) {
      const m = this.modals.skill;
      if (!m) return "";
      const v = (m.form[field] || "").trim();
      if (field === "name") {
        if (!v) return "Name is required.";
        if (m.mode !== "create") return "";
        if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(v)) {
          /* A VERDICT, not the rule again. The field's hint states the rule and
             sits permanently 12px above this message; the first version of
             this repeated it in different words ("hyphens" above, "single
             hyphens only" below), so the dialog described one rule twice in
             two vocabularies on adjacent lines. Found by reading a capture,
             not by any assertion — every test passed. */
          return "Not a valid name.";
        }
        if (v.length > 64) return "Name is 1-64 characters; this one is " + v.length + ".";
      }
      if (field === "description" && !v) return "Description is required.";
      return "";
    },

    /* Only speaks for a field the reader has finished with, and only says
       "required" about a field they have actually typed into. Measured: the
       first version of this shipped a scolding for every empty field the
       reader tabbed past on the way to the next one, which is 4.5 slice A's
       failure mode pointed at a field instead of a dialog — the learned
       response to a form that talks back spuriously is to dismiss messages
       without reading, and that is how the work it protects gets lost.

       A FORMAT or LENGTH message is different in kind: it implies something was
       typed, so it needs no marker. */
    noteSkillFieldEdited(field) {
      const m = this.modals.skill;
      if (!m) return;
      if (!m.touched) m.touched = {};
      m.touched[field] = true;
    },

    validateSkillField(field) {
      const m = this.modals.skill;
      if (!m) return;
      const touched = !!(m.touched && m.touched[field]);
      const raw = (m.form[field] || "").trim();
      const err = (!touched && raw === "" && /is required\.$/.test(this.skillFieldError(field)))
        ? ""
        : this.skillFieldError(field);
      const next = Object.assign({}, m.errors);
      if (err) next[field] = err; else delete next[field];
      m.errors = next;
    },

    async saveSkill() {
      const m = this.modals.skill;
      if (!m) return;
      m.confirmingClose = false;
      /* Recomputed from the shared validator rather than reset first, so a
         field the reader was already told about keeps its message instead of
         blinking out and back on the frame the button is pressed. */
      m.errors = {};
      for (const f of ["name", "description"]) {
        const err = this.skillFieldError(f);
        if (err) m.errors[f] = err;
      }
      if (Object.keys(m.errors).length) {
        this.$nextTick(() => {
          const firstInvalid = document.querySelector('[data-modal="skill"] .form-field.has-error input, [data-modal="skill"] .form-field.has-error textarea, [data-modal="skill"] .form-field.has-error select');
          if (firstInvalid) firstInvalid.focus();
        });
        return;
      }

      const payload = {};
      const payloadKeys = m.mode === "create"
        ? ["name", "description", "category", "version", "license", "compatibility", "allowed_tools", "body"]
        : ["description", "category", "version", "license", "compatibility", "allowed_tools", "body"];
      for (const k of payloadKeys) {
        const v = (m.form[k] || "").trim();
        if (v) payload[k] = v;
      }

      const effScope = (m.form.scope || this.activeScope || "global");
      const createScope = effScope === "all" ? "global" : effScope;
      const editScope = (this.selected && this.selected.scope) ? this.selected.scope : createScope;
      this.busy = true;
      try {
        if (m.mode === "create") {
          await api("/api/skills?scope=" + encodeURIComponent(createScope), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          this.toast('Skill "' + payload.name + '" created in ' + createScope + '.');
        } else {
          const res = await api("/api/skills/" + encodeURIComponent(m.mode) + "?scope=" + encodeURIComponent(editScope), {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          this.toast(res.changed ? 'Skill "' + m.mode + '" updated.' : 'No changes to "' + m.mode + '".');
        }
        this.closeModal("skill");
        this.query = "";
        await this.loadScopes();
        await this.loadSkills();
        await this.loadTrash();
        if (m.mode === "create") this.selectedName = payload.name;
        this.loadDetail(m.mode === "create" ? payload.name : m.mode, m.mode === "create" ? createScope : editScope);
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    openAdd() {
      const input = document.createElement("input");
      input.type = "file";
      input.webkitdirectory = true;
      input.onchange = async () => {
        if (!input.files || !input.files.length) return;
        const form = new FormData();
        for (const f of input.files) {
          const rel = f.webkitRelativePath || f.name;
          form.append("files", f, rel);
        }
        this.busy = true;
        try {
          const data = await api("/api/import", { method: "PUT", body: form });
          await this.loadSkills();
          if (data.imported && data.imported.length) {
            this.toast("Added skill(s): " + data.imported.join(", ") + ".");
            this.loadDetail(data.imported[0]);
          } else {
            this.toast("Nothing added: " + (data.skipped || []).join(", "), "info");
          }
        } catch (e) {
          this.toast(e.message, "err");
        } finally {
          this.busy = false;
        }
      };
      input.click();
    },

    /* One request, for both the button and its Undo. `toggleSelected` could
     * have closed over itself, but then the undo path would carry its own copy
     * of the POST and its own error handling, and the two would drift — which
     * is exactly how 4.7 shipped a literal `N` in a sentence that measured it.
     * The reader's Undo and the reader's click must send the same request.
     *
     * `toggleSkillState` does NOT touch `busy`. The undo runs from the toast,
     * which is outside the detail row's disabled set, so it has no business
     * claiming the flag; it reports its own outcome instead.
     */
    async toggleSkillState(name, scope, action) {
      const qp = "?scope=" + encodeURIComponent(scope);
      await api("/api/skills/" + encodeURIComponent(name) + "/" + action + qp, { method: "POST" });
      await this.loadScopes();
      await this.loadSkills();
    },

    async toggleSelected() {
      if (!this.selectedName) { this.toast("Select a skill first.", "err"); return; }
      /* A second press while the first is still in flight is a reader who was
       * not sure the first landed — not a second decision. Measured: two
       * dispatches in one tick produced two POSTs, and the backend's own
       * rejection ("skill 'x' is already enabled", lower case, single quotes)
       * reached the screen VERBATIM, in a different voice from every other
       * message in the app and reading as a failure of the tool rather than of
       * the click.
       *
       * `this.busy = true` is set before the first await, so this guard sees
       * the second press; `:disabled="busy"` on the button is what makes it
       * visible. One is not a substitute for the other — the attribute cannot
       * stop two dispatches inside a single frame, and the guard alone leaves
       * the button looking clickable.
       */
      if (this.busy) return;
      const name = this.selectedName;
      const sc = (this.selected && this.selected.scope) ? this.selected.scope : (this.activeScope !== "all" ? this.activeScope : "global");
      this.busy = true;
      try {
        const action = this.selectedDisabled ? "enable" : "disable";
        await this.toggleSkillState(name, sc, action);
        /* The sentence names the scope the way every other surface in the app
         * does. `sc` is the wire slug (`claude-code`, `opencode`, …) and it
         * used to be printed raw, so the toast read `… disabled in
         * claude-code.` beside a Library row whose chip said `Claude Code` and
         * a scope menu whose option said the same. The record already carries
         * the label the backend observed (`scope_label`), and
         * `observedIdentity` is what the rest of the UI reads it through.
         *
         * `action + "d"` built the past tense by concatenation, which is
         * correct for exactly two English words and asserts nothing about the
         * third verb anyone adds later. `toggleOutcome` names both tenses.
         */
        this.toast(toggleOutcome(this.selected || {}, action),
                   "ok",
                   // Undo, not a confirm dialog.
                   //
                   // The decision: disabling is REVERSIBLE and takes one click
                   // on the same button that performed it, so a modal would tax
                   // every reader for a mistake they can already fix. The
                   // confirmation the product does owe is that the reader can
                   // tell what happened AND put it back without finding the row
                   // again — which is what this is.
                   //
                   // It was already built and unreachable: 2.3 shipped
                   // `toast(text, type, undo)` with an 8-second
                   // `TOAST_UNDO_MS` lifetime for exactly this case, an Undo
                   // button in the toast markup, and `undoToast` to run it —
                   // and measured, NO caller in the product has ever passed a
                   // third argument. The 8s window had no occupant. `enable`
                   // gets no Undo: re-enabling is the restore, and offering
                   // "Undo" on it would offer the action the reader just took.
                   action === "disable"
                     ? () => this.toggleSkillState(name, sc, "enable")
                     : null);
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    confirmRemove(record) {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      if (!record) { this.toast("Select a skill first.", "err"); return; }
      // BUG-5: bind the modal to the record it was opened for.  The scope was
      // re-derived from live `this.selected` at confirm time, so a selection
      // change (or a same-name skill in another scope) between opening and
      // confirming removed a different skill than the one the dialog named --
      // irreversibly for the purge path.
      this.modals.remove = {
        name: record.name,
        scope: record.scope || (this.activeScope !== "all" ? this.activeScope : "global"),
        mode: "trash",
      };
    },

    async doRemove() {
      const m = this.modals.remove;
      if (!m) return;
      this.busy = true;
      try {
        await this.removeSkill(m.name, m.mode === "purge", m.scope);
        this.closeModal("remove");
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    async removeSkill(name, purge, scope) {
      const sc = scope
        || (this.selected && this.selected.scope)
        || (this.activeScope !== "all" ? this.activeScope : "global");
      const qp = "?scope=" + encodeURIComponent(sc) + "&purge=" + (purge ? "1" : "0");
      await api("/api/skills/" + encodeURIComponent(name) + qp, { method: "DELETE" });
      if (purge) {
        this.toast('Skill "' + name + '" permanently deleted from ' + sc + '.');
      } else {
        // Undo restores the same scope-trashes only global; agent scopes have
        // their own per-scope trash without a UI restore path yet.
        if (sc === "global") {
          this.toast('Skill "' + name + '" moved to trash.', "ok", async () => {
            await api("/api/trash/" + encodeURIComponent(name), { method: "POST" });
            await this.loadSkills();
            await this.loadTrash();
            this.loadDetail(name, sc);
            this.toast('Skill "' + name + '" restored.');
          });
        } else {
          this.toast('Skill "' + name + '" moved to the ' + sc + ' scope trash (restore from trash view is global-only).', "ok");
        }
      }
      await this.loadScopes();
      await this.loadSkills();
      await this.loadTrash();
      if (this.selectedName === name) { this.selectedName = null; this.selected = null; }
    },

    confirmPurge() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals.purge = {};
    },

    async purgeTrash() {
      this.busy = true;
      try {
        const res = await api("/api/trash/purge", { method: "POST" });
        this.closeModal("purge");
        // The server's count is what it OBSERVED deleting, which is a different
        // fact from the count the dialog predicted; the dialog reads the loaded
        // list, so the two can differ and this must not reuse the dialog's
        // figure.  `skill(s)` was the last ungrammatical string in the four
        // dialogs and it was also the one that never named the scope.
        const purged = res.purged || [];
        this.toast("Purged " + this.formatNumber(purged.length) + " trashed "
          + (purged.length === 1 ? "skill" : "skills") + " from the global trash.");
        this.selectedTrash = null;
        await this.loadTrash();
        await this.loadSkills();
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    /**
     * 5.6a — restore ONE trashed skill.
     *
     * `item` is optional because the Trash view's detail pane still restores
     * through `selectedTrash` (that pane is 5.6b), while Recovery's list
     * restores the row the reader pressed. Two arguments, one request path:
     * a second method would be a second place for the two to drift, which is
     * what 4.7's literal `N` cost.
     */
    async restoreTrash(item) {
      const target = item || this.selectedTrash;
      if (!target) return;
      const name = target.name;
      this.busy = true;
      try {
        await api("/api/trash/" + encodeURIComponent(name), { method: "POST" });
        this.toast('Skill "' + name + '" restored.');
        this.selectedTrash = null;
        await this.loadTrash();
        await this.loadSkills();
        // Trash view is global-only: pass the global scope explicitly so the
        // restored skill resolves even when activeScope is an agent scope.
        this.loadDetail(name, "global");
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    /* --------------------------------------------------------- validate */

    openValidate() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals.validate = {
        name: this.selectedName || "",
        loading: false,
        result: null,
        error: null,
      };
    },

    async runValidate() {
      const m = this.modals.validate;
      if (!m) return;
      m.loading = true;
      m.error = null;
      m.result = null;
      try {
        m.result = await api("/api/validate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: m.name, scope: (this.selected && this.selected.scope) || this.activeScope || "global" }),
        });
      } catch (e) {
        m.error = e.message;
      } finally {
        m.loading = false;
      }
    },

    /* ------------------------------------------------------- maintenance */

    /* 5.8a - a verdict that counts, and a branch that admits it cannot.
     *
     * The banner said "Issues found." on every unhealthy library, whatever
     * was found. The words name no issue, so the sentence was true of a
     * library with one orphaned directory and of one with a hundred broken
     * documents, and the reader had to go looking for which it was.
     *
     * A METHOD, because the template calls it (`{{ doctorVerdict() }}`) and
     * Vue unwraps a computed before the template ever sees it. 5.5's trap.
     *
     * The `!ok` branch matters as much as the count: `report.ok` is the
     * BACKEND's verdict, and if it says unhealthy while `doctorFindings` is
     * empty then this dialog does not hold the key that explains why. Saying
     * "nothing found" there would be the dialog inventing a clean bill of
     * health it was never given.
     */
    /** 5.8b - the Stats tiles are NOT additive, and never were.
     *  `total` is `COUNT(*) FROM skills`, so it includes the trashed rows.
     *  `active` counts `status='active'` names that exist on disk, so it
     *  excludes them. `disabled` counts `disabled=1 AND name IN <active>` -
     *  a SUBSET of `active`, not a sibling. On the seed: 48 / 45 / 2 / 3, and
     *  45 + 2 + 3 = 50. The dialog put the four numbers side by side as equal
     *  tiles and called the first one "Total skills", so the arithmetic every
     *  reader tries is wrong by two and the sentence names the wrong thing -
     *  `db_rows` is the same number as `total`, not a total.
     *
     *  The sentence states the relationship instead of implying it, and it is
     *  a METHOD because the template calls it. 5.5's trap, fifth instance.
     */
    statsPopulationNote() {
      const r = (this.modals.stats || {}).report;
      if (!r) return "";
      return this.formatNumber(r.active) + " installed"
        + (r.disabled ? ", " + this.formatNumber(r.disabled) + " of them disabled" : "")
        + ", and " + this.formatNumber(r.trashed) + " trashed."
        + " The " + this.formatNumber(r.total) + " above is index rows, which is every"
        + " one of those plus " + this.formatNumber(r.total - r.active - r.trashed)
        + " with no directory on disk — the figures do not add up, and should not.";
    },
    /** What a category IS, and which population it covers.
     *  `_live_index_totals` (store.py) groups `status='active'` rows that are
     *  live on disk — the INSTALLED set, disabled included — and the key is
     *  whatever the skill's own frontmatter says, so `uncategorized` arrives
     *  beside seven real ones. The old dialog printed the raw key under a bare
     *  heading and said nothing about either fact. */
    statsCategoryNote() {
      const r = (this.modals.stats || {}).report;
      const cats = (r && r.categories) || {};
      const covered = Object.keys(cats).length;
      const sum = Object.keys(cats).reduce((n, k) => n + (Number(cats[k]) || 0), 0);
      const uncategorized = Number(cats.uncategorized) || 0;
      let s = "One `category:` line per skill. Keys are what each document says,"
        + " not a fixed vocabulary. These " + this.formatNumber(sum)
        + " are the " + this.formatNumber(r.active) + " installed skills; ";
      s += covered
        ? (sum === r.active
            ? "every installed skill has one."
            : this.formatNumber(r.active - sum) + " carry none and are not listed here.")
        : "none of them carries one.";
      if (uncategorized) {
        s += " `" + Object.keys(cats).indexOf("uncategorized") + " · uncategorized` is this app's"
          + " placeholder for a document with no `category:`, not a category anyone chose.";
      }
      return s;
    },
    doctorVerdict() {
      const report = (this.modals.doctor || {}).report;
      if (!report) return "";
      const findings = this.doctorFindings;
      const n = findings.reduce((sum, f) => sum + f.names.length, 0);
      if (!n) {
        return report.ok
          ? "Nothing to repair. The library, the index and the trash agree."
          : "The library is flagged, and no finding explains it below.";
      }
      return this.formatNumber(n)
        + (n === 1 ? " finding" : " findings")
        + " across " + findings.length
        + (findings.length === 1 ? " check." : " checks.");
    },
    /** Scope ids -> the labels this same payload already carries.
     *  A METHOD, because the template calls it inside a `.map()`. */
    doctorScopeLabel(id) {
      const report = (this.modals.doctor || {}).report || {};
      for (const group of report.duplicates || []) {
        for (const rec of group.records || []) {
          if (rec && rec.scope === id && rec.scope_label) return rec.scope_label;
        }
      }
      return id;
    },
    openDoctor() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals.doctor = { loading: true, report: null };
      api("/api/doctor" + (this.activeScope === "all" ? "?scope=all" : ""))
        .then((report) => { if (this.modals.doctor) this.modals.doctor.report = report; })
        .catch((e) => { this.closeModal("doctor"); this.toast(e.message, "err"); })
        .finally(() => { if (this.modals.doctor) this.modals.doctor.loading = false; });
    },

    syncDupe(name, fromScope) {
      this.selectedName = name;
      this.selected = { name, scope: fromScope };
      this.closeModal("doctor");
      this.openSync();
    },

    openStats() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals.stats = { loading: true, report: null };
      api("/api/stats")
        .then((report) => { if (this.modals.stats) this.modals.stats.report = report; })
        .catch((e) => { this.closeModal("stats"); this.toast(e.message, "err"); })
        .finally(() => { if (this.modals.stats) this.modals.stats.loading = false; });
    },

    /* 5.9b: a function CALLED from a template must be a METHOD, never a
     * computed — Vue unwraps a computed to its value before the template
     * sees it, so `{{ historyActionLabel(r.action) }}` would throw during
     * render and the History table would vanish with every gate green. */
    historyActionLabel(action) {
      return HISTORY_ACTIONS[action] || String(action);
    },

    validateLevelLabel(level) {
      return VALIDATE_LEVELS[level] || String(level);
    },

    openHistory(scopeOverride = null) {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals.history = { name: "", loaded: "", rows: [], snapshots: [], loading: false, scope: scopeOverride || "", error: null };
      this.loadHistory();
    },

    async loadHistory() {
      const m = this.modals.history;
      if (!m) return;
      /* 5.9b — the Snapshots block used to hang off `m.name`, which is the
       * <select>'s v-model, so PICKING a skill claimed "No snapshots for this
       * skill" above a table still listing every skill's history — a claim
       * about the disk made by a selection that had not been applied (5.6a's
       * class). `loaded` is the name the data below it was actually fetched
       * for, and it is only set once both requests have settled. */
      const asked = m.name;
      m.loading = true;
      try {
        const name = asked ? "&name=" + encodeURIComponent(asked) : "";
        m.rows = await api("/api/history?limit=200" + name);
        m.snapshots = [];
        if (asked) {
          const scope = m.scope || ((this.selected && this.selected.scope) ? this.selected.scope : "global");
          const snapshotResult = await api("/api/history?name=" + encodeURIComponent(asked) + "&scope=" + encodeURIComponent(scope) + "&snapshots=1");
          m.snapshots = snapshotResult.snapshots || [];
        }
        m.loaded = asked;
        m.error = null;
      } catch (e) {
        /* 6.3 — was `this.toast(e.message, "err")` alone, leaving `rows` at
         * whatever it was and rendering "No history records." under it. */
        m.rows = [];
        m.snapshots = [];
        m.error = "Could not read history: " + e.message;
        this.toast(m.error, "err");
      } finally {
        m.loading = false;
      }
    },

    async rollbackSnapshot(name, snapshot) {
      this.busy = true;
      try {
        const scope = (this.modals.history && this.modals.history.scope)
          || ((this.selected && this.selected.scope) ? this.selected.scope : "global");
        const res = await api("/api/trash/" + encodeURIComponent(name) + "?snapshot=" + encodeURIComponent(snapshot) + "&scope=" + encodeURIComponent(scope), { method: "POST" });
        this.toast(`Rolled back "${res.name}" to snapshot ${snapshot}.`);
        await this.loadSkills();
        await this.loadDetail(name, scope);
        await this.loadHistory();
        /* 4.4: the History dialog's reload does not touch the pane's cache,
           so after a rollback from EITHER surface the pane would keep showing
           the pre-rollback rows until the reader pressed Refresh. */
        await this.ensureDetailHistory(true);
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    async rebuildIndex() {
      this.busy = true;
      try {
        const res = await api("/api/rebuild", { method: "POST" });
        this.toast("Index rebuilt: " + res.added + " added, " + res.updated + " updated, " + res.removed + " removed.");
        await this.loadSkills();
        await this.loadTrash();
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    async resyncIndex() {
      this.busy = true;
      try {
        const res = await api("/api/resync", { method: "POST" });
        this.toast("Store resynced: " + res.added + " added, " + res.updated + " updated, " + res.removed + " removed.");
        await this.loadSkills();
        await this.loadTrash();
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    /* -------------------------------------------------------- templates */

    openTemplates() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals.templates = { loading: true, names: [] };
      api("/api/templates")
        .then((res) => { if (this.modals.templates) this.modals.templates.names = res.templates || []; })
        .catch((e) => { this.closeModal("templates"); this.toast(e.message, "err"); })
        .finally(() => { if (this.modals.templates) this.modals.templates.loading = false; });
    },

    openNewTemplate() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals.newtemplate = { name: "", body: "", error: "" };
    },

    async saveTemplate() {
      const m = this.modals.newtemplate;
      if (!m) return;
      if (!m.name.trim()) { m.error = "Template name is required."; return; }
      this.busy = true;
      try {
        await api("/api/templates", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: m.name.trim(), body: m.body || null }),
        });
        this.closeModal("newtemplate");
        this.toast('Template "' + m.name.trim() + '" created.');
      } catch (e) {
        m.error = e.message;
      } finally {
        this.busy = false;
      }
    },

    /* ------------------------------------------------------ import/export */

    openImport(full = false) {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals.import = { file: null, force: false, full: !!full };
    },

    pickImportFile() {
      this.$refs.importInput && this.$refs.importInput.click();
    },

    onImportPicked(e) {
      const files = e.target.files;
      if (files && files.length) {
        this.modals.import.file = files[0];
      }
      e.target.value = "";
    },

    onDropImport(e) {
      const files = e.dataTransfer.files;
      if (files && files.length) {
        this.modals.import.file = files[0];
      }
    },

    async doImport() {
      const m = this.modals.import;
      if (!m || !m.file) return;
      this.busy = true;
      try {
        const url = "/api/import?filename=" + encodeURIComponent(m.file.name) + "&force=" + (m.force ? "1" : "0") + "&full=" + (m.full ? "1" : "0");
        const data = await api(url, { method: "PUT", body: m.file });
        this.closeModal("import");
        if (data.imported && data.imported.length) {
          this.toast("Imported: " + data.imported.join(", "));
        }
        if (data.skipped && data.skipped.length) {
          this.toast("Skipped (already present): " + data.skipped.join(", "), "info");
        }
        await this.loadSkills();
        await this.loadTrash();
        if (data.imported && data.imported.length) this.loadDetail(data.imported[0]);
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    openSync() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      if (!this.selectedName) { this.toast("Select a skill first.", "err"); return; }
      const from = (this.selected && this.selected.scope) ? this.selected.scope : "global";
      const targets = (this.scopes || []).filter((s) => s.id !== from && s.writable);
      this.modals.sync = { name: this.selectedName, from_scope: from, targets, picked: {}, force: false };
      for (const t of targets) this.modals.sync.picked[t.id] = true;
    },

    /* --------------------------------------------------------- sync facts
     *
     * The sync dialog used to derive its own facts in the template, in three
     * separate expressions, and one of them printed a literal "N" where the
     * target count belongs — "syncing to N agents" — because the sentence was
     * written before the count existed and never filled the hole in. A number
     * no reader can see is worse than no number: the sentence still reads like
     * a measurement.
     *
     * So every figure the dialog states is derived HERE, once, from the same
     * `modals.sync.picked` map `doSync` posts. There is no path by which the
     * dialog can state one count and send another.
     */
    async doSync() {
      const m = this.modals.sync;
      if (!m) return;
      // The SAME list the dialog states in syncOutcomeSentence. Posting a
      // separately-derived list is how a confirm starts naming one thing and
      // doing another, which is the 2.3 lesson (a palette row that ran a
      // different command than the one it drew).
      const to = this.syncPickedTargets;
      if (!to.length) { this.toast("Pick at least one target scope.", "err"); return; }
      this.busy = true;
      try {
        const res = await api("/api/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: m.name, from_scope: m.from_scope, to_scopes: to, force: !!m.force }),
        });
        this.closeModal("sync");
        const ok = (res.synced || []).length;
        const skip = (res.skipped || []).length;
        this.toast(`Synced "${m.name}" to ${ok} scope(s)` + (skip ? `, skipped ${skip}.` : "."), ok ? "ok" : "info");
        await this.loadScopes();
        await this.loadSkills();
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    async exportArchive(full = false) {
      this.busy = true;
      try {
        const { blob, filename: served } = await apiBlob("/api/export" + (full ? "?full=1" : ""));
        const filename = served || "skills-export.tar.gz";
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 4000);
        this.toast("Archive downloaded: " + filename);
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },
  },
};

/* One handle on the mounted instance, for the browser suite.
 *
 * WHY THIS EXISTS. Vue attaches `__vue_app__` to the root element but leaves
 * `_instance` null after mount, so there is no supported way for a Playwright
 * test to reach a method. Without a seam, every assertion about toasts,
 * banners and skeletons would have to click a five-step real flow per message
 * — which pins the FLOW rather than the SURFACE, and 2.3 changed the surface.
 *
 * The alternative considered and rejected: reach through `__vue_app__
 * ._container._vnode.component.proxy`. It works and it is undocumented
 * internals that change between Vue minors, so a Vue bump would break the
 * suite in a way that looks like a product failure.
 *
 * This is a handle and nothing more. It exposes no capability a user does not
 * already have from the console, it adds no behaviour, and it is the same
 * object the component already is. */
window.__skillsManagerApp = createApp(appOptions).mount("#app");
