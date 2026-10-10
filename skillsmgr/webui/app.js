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
  failure.textContent = "Skills Manager could not start: domain.js did not load. "
    + "Reload the page; if it persists, the served frontend files are incomplete.";
  document.body.appendChild(failure);
  throw new Error("SkillManagerDomain missing");
}

const {
  api, apiText, apiBlob,
  formatBytes, formatTokens, tokenPctClass, tokenBarWidth,
  renderMarkdown, parseFrontmatter, formatCompat, formatTools,
  groupLogicalSkills, deriveLogicalSkillIdentity, observedIdentity,
  observeRecord, observedStateFor, observedStateKeys,
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
createApp({
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
      skills: [],
      allSkills: [],
      trashSkills: [],
      catalog: { version: 1, tags: {}, profiles: {} },
      tagFilter: "",
      selectedKeys: [],
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
      firstScanGuideDismissed: false,
      guideExplainConsumer: "codex",
      guideExplainResult: null,
      guideExplainError: null,
      guideExplainLoading: false,
      guideExplainRequest: 0,
      scopeScanFailed: false,
      budget: null,
      budgetWindow: localStorage.getItem("skillsmgr-budget-window") || "claude",
      install: { mode: "runner", registryOp: "browse", runner: "npx", source: "", scope: "global", agents: [], skillsFilter: "", copy: false, listOnly: false, page: 0, perPage: 25, view: "all-time", allowStale: false, lastResult: null, review_id: null, review: null },
      theme: ["light", "dark", "system"].includes(savedTheme) ? savedTheme : "system",
      resolvedTheme: "light",
      systemTheme: "light",
      textSize: localStorage.getItem("skillsmgr-text-size") === "large" ? "large" : "standard",
      localeOptions,
      locale: localeValues.includes(savedLocale) ? savedLocale : "system",
      resolvedLocale: "en-US",
      prefersReducedMotion: false,
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
      loadingRecoverySnapshots: false,
      recoverySnapshots: [],
      loadingHistory: true,
      overviewHistory: [],
      loadingWorkspaces: false,
      workspaces: null,
      workspaceProject: "",
      qualityHygiene: null,
      qualityHygieneLoading: false,
      qualityHygieneError: null,
      qualitySeverityFilter: "all",
      qualityExpandedFindings: [],
      profileForm: { name: "", description: "", skills: "", targets: "" },
      profilePreview: null,
      mobileDetailOpen: false,
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
        install: null,
        batch: null,
        update: null,
        help: null,
        commands: null,
      },
    };
  },

  computed: {
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

    selectedLogical() {
      return groupLogicalSkills(this.skills, this.scopes).find((skill) => skill.name === this.selectedName) || null;
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
      return this.skills.filter((record) => wanted.has(this.targetKey(record)));
    },
    selectedCount() { return this.selectedTargets.length; },
    profileObservedCount() {
      return (this.profilePreview && this.profilePreview.members || [])
        .reduce((count, member) => count + (member.instances || []).length, 0);
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
      return this.view === "overview" && !this.firstScanGuideDismissed;
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
        { id: "nav-install", label: "Install", title: "Open Install", category: "Navigation", keywords: "workflow registry", action: "switchView", args: ["install"], focusDestination: true },
        { id: "nav-recovery", label: "Recovery", title: "Open Recovery", category: "Navigation", keywords: "trash restore backups", action: "switchView", args: ["recovery"], focusDestination: true },
        { id: "nav-workspaces", label: "Workspaces", title: "Open Workspaces", category: "Navigation", keywords: "projects adapters", action: "switchView", args: ["workspaces"], focusDestination: true },
        { id: "nav-quality", label: "Quality", title: "Open Quality", category: "Navigation", keywords: "evidence health", action: "switchView", args: ["quality"], focusDestination: true },
        { id: "nav-settings", label: "Settings", title: "Open Settings", category: "Navigation", keywords: "preferences accessibility theme", action: "switchView", args: ["settings"], focusDestination: true },
        { id: "create-skill", label: "Create skill", title: "Create a new skill", category: "Skill actions", keywords: "new add author", action: "openCreate", focusDestination: true },
        { id: "add-folder", label: "Add folder", title: "Add skills from a folder", category: "Skill actions", keywords: "import directory upload", action: "openAdd" },
        { id: "install-workflow", label: "Install workflow", title: "Install via a runner or registry", category: "Transfer", keywords: "install npx pnpm bunx registry", action: "openInstall", focusDestination: true },
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
        : this.commandPaletteCommands.filter((command) => [command.label, command.title, command.category, command.keywords]
          .join(" ").toLowerCase().includes(needle));
      /* Group order is applied HERE, once, so there is exactly one ordering in
         the app. Grouping the results afterwards instead would make the drawn
         order differ from the order ArrowDown walks — a palette that highlights
         a row the reader cannot see is worse than an ungrouped one, and the
         bug would only appear for a query that matched rows in two groups. */
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

    activeScopeOption() {
      return this.scopeOptions.find((o) => o.id === this.activeScope) || this.scopeOptions[0];
    },

    activeScopeLabel() {
      return this.activeScopeOption.label;
    },

    activeScopeAvailable() {
      return this.activeScopeOption.exists;
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
      this.selectedKeys = [];
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
      this.commandPaletteActiveIndex = 0;
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
    this.prefersReducedMotion = this.readReducedMotion();
    this.setupThemeListener();
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
     * against the *current* viewport rather than a remembered one. */
    positionScopeMenu() {
      const menu = this.$refs.scopeMenuWrap && this.$refs.scopeMenuWrap.querySelector("#scope-menu");
      if (!menu) return;
      const gap = 6;
      const roomBelow = window.innerHeight - menu.getBoundingClientRect().top + gap;
      const roomAbove = menu.getBoundingClientRect().bottom + gap;
      this.scopeMenuFlip = roomBelow < menu.offsetHeight && roomAbove > roomBelow;
    },

    closeScopeMenu(restoreFocus = false) {
      this.scopeMenuOpen = false;
      this.scopeMenuFlip = false;
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
    rowBadgeItems(s) {
      if (!s) return [];
      if (this.libraryMode === "library") {
        const tags = this.groupTags(s);
        return (s.instanceCount > 1 ? [{ key: "copies", text: s.instanceCount + " copies", scope: true }] : [])
          .concat(tags.map((tag) => ({ key: "tag:" + tag, text: "#" + tag })));
      }
      const tags = s.tags || [];
      return (s.category ? [{ key: "category", text: s.category }] : [])
        .concat(tags.map((tag) => ({ key: "tag:" + tag, text: "#" + tag })));
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
      for (const instance of instances) {
        const key = this.targetKey(instance);
        if (checked) keys.add(key); else keys.delete(key);
      }
      this.selectedKeys = [...keys];
    },

    toggleSelectAll() {
      const keys = new Set(this.selectedKeys);
      if (this.allVisibleSelected) this.visibleTargetKeys.forEach((key) => keys.delete(key));
      else this.visibleTargetKeys.forEach((key) => keys.add(key));
      this.selectedKeys = [...keys];
    },

    skipOnboarding() {
      this.onboardingDismissed = true;
    },

    dismissFirstScanGuide() {
      this.firstScanGuideDismissed = true;
    },

    restartFirstScanGuide() {
      this.firstScanGuideDismissed = false;
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

    updateReviewIsBlocked(review) {
      return !!(review && (review.review_state === "blocked"
        || review.review_state === "no-change"
        || (review.validation && review.validation.valid === false)));
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
        this.toast(`Update applied to ${modal.target.name}; recovery snapshot ${modal.snapshotId || "created"}.`, "ok");
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
        return;
      }
      this.closeModal("update");
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
      } catch (e) {
        this.recoverySnapshots = [];
        this.toast("Could not load source snapshots: " + e.message, "err");
      } finally {
        this.loadingRecoverySnapshots = false;
      }
    },

    async loadWorkspaces() {
      this.loadingWorkspaces = true;
      try {
        const suffix = this.workspaceProject.trim() ? "?project=" + encodeURIComponent(this.workspaceProject.trim()) : "";
        this.workspaces = await api("/api/workspaces" + suffix);
      } catch (e) {
        this.toast("Could not load workspace evidence: " + e.message, "err");
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
      this.install.lastResult = null;
      this.busy = true;
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
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
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
        this.install.lastResult = res;
        this.install.review_id = null;
        this.install.review = null;
        this.toast(`Installed ${res.name} from the reviewed registry snapshot.`, "ok");
        await this.loadScopes();
        await this.loadSkills();
      } catch (e) {
        this.toast(e.message, "err");
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

    async loadQualityHygiene() {
      const scopeAtCall = this.activeScope || "all";
      this.qualityHygieneLoading = true;
      this.qualityHygieneError = null;
      try {
        const report = await api("/api/doctor?scope=" + encodeURIComponent(scopeAtCall) + "&hygiene=1");
        if ((this.activeScope || "all") !== scopeAtCall) return;
        this.qualityHygiene = report.hygiene || null;
        if (!this.qualityHygiene) this.qualityHygieneError = "The server returned no hygiene report.";
        this.liveAnnouncement = "Skill hygiene evidence refreshed.";
      } catch (e) {
        this.qualityHygieneError = e.message;
        this.liveAnnouncement = "Skill hygiene evidence could not be loaded.";
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
      } catch (e) {
        this.toast("Could not load trash: " + e.message, "err");
      } finally {
        this.loadingTrash = false;
      }
    },

    async loadOverviewHistory() {
      this.loadingHistory = true;
      try {
        this.overviewHistory = await api("/api/history?limit=8");
      } catch (e) {
        this.overviewHistory = [];
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
      this.loadDetail(s.name, s.scope);
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
      else if (v === "install") this.loadSkills();
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
          : document.querySelector("#view-title, #overview-title");
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

    qualityCategoryCount(category) {
      return Number((this.qualityHygiene && this.qualityHygiene.category_counts || {})[category] || 0);
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
        this.selectedKeys = [];
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
        this.selectedKeys = [];
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
        this.profileForm = { name: "", description: "", skills: "", targets: "" };
        this.toast("Profile saved.");
      } catch (e) { this.toast(e.message, "err"); }
      finally { this.busy = false; }
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

    async deleteProfile(name) {
      this.busy = true;
      try {
        this.catalog = await api("/api/catalog/profiles/" + encodeURIComponent(name), { method: "DELETE" });
        if (this.profilePreview && this.profilePreview.name === name) this.profilePreview = null;
        this.toast("Profile deleted.");
      } catch (e) { this.toast(e.message, "err"); }
      finally { this.busy = false; }
    },

    /* ---------------------------------------------------------- helpers */

    /* One place decides whether a message is announced, and it announces it
     * ONCE. `liveAnnouncement` is cleared on the next tick after the toast is
     * added, because a live region only speaks when its text CHANGES -- two
     * identical consecutive failures ("Could not load skills: ...") would
     * otherwise be silent the second time, which is precisely when a
     * repeating failure matters most. */
    toast(text, type = "ok", undo = null) {
      const id = ++this.toastSeq;
      const life = undo ? TOAST_UNDO_MS : TOAST_MS;
      /* Cap the stack. A burst is exactly when a reader needs the surface:
       * capping drops the OLDEST, because the newest describes the condition
       * that produced the rest. */
      this.toasts = [...this.toasts, { id, text, type, undo, life }].slice(-TOAST_MAX);
      this.liveAnnouncement = text;
      this.$nextTick(() => { if (this.liveAnnouncement === text) this.liveAnnouncement = ""; });
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

    readReducedMotion() {
      return typeof window !== "undefined"
        && typeof window.matchMedia === "function"
        && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
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
      if (e.key === "/" && !typing && !this.activeModal) {
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
        else if (this.activeModal === "update") this.requestCloseUpdate();
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
        install: this.openInstall,
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

    openInstall() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals.install = true;
    },

    /* ----------------------------------------------------- skill actions */

    openCreate() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      const defScope = (this.activeScope && this.activeScope !== "all") ? this.activeScope : "global";
      this.modals.skill = {
        mode: "create",
        form: { name: "", description: "", category: "", version: "", license: "", compatibility: "", allowed_tools: "", body: "", scope: defScope },
        errors: {},
      };
      nextTick(() => { const el = document.getElementById("f-name"); (el || this.modalElement())?.focus(); });
    },

    async openEdit() {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      if (!this.selectedName) { this.toast("Select a skill first.", "err"); return; }
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
        },
        errors: {},
      };
      try {
        const sc = (this.selected && this.selected.scope) ? this.selected.scope : (this.activeScope !== "all" ? this.activeScope : "global");
        const qp = "?scope=" + encodeURIComponent(sc);
        const text = await apiText("/api/skills/" + encodeURIComponent(this.selectedName) + "/raw" + qp);
        const fm = parseFrontmatter(text);
        if (!this.modals.skill) return;
        if (fm.compatibility && !this.modals.skill.form.compatibility) this.modals.skill.form.compatibility = fm.compatibility;
        if (fm.allowed_tools && !this.modals.skill.form.allowed_tools) this.modals.skill.form.allowed_tools = fm.allowed_tools;
      } catch (e) { /* optional */ }
    },

    async saveSkill() {
      const m = this.modals.skill;
      if (!m) return;
      m.errors = {};
      if (!m.form.name) m.errors.name = "Name is required.";
      if (!m.form.description) m.errors.description = "Description is required.";
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

    async toggleSelected() {
      if (!this.selectedName) { this.toast("Select a skill first.", "err"); return; }
      const name = this.selectedName;
      const sc = (this.selected && this.selected.scope) ? this.selected.scope : (this.activeScope !== "all" ? this.activeScope : "global");
      const qp = "?scope=" + encodeURIComponent(sc);
      this.busy = true;
      try {
        const action = this.selectedDisabled ? "enable" : "disable";
        await api("/api/skills/" + encodeURIComponent(name) + "/" + action + qp, { method: "POST" });
        this.toast('Skill "' + name + '" ' + action + "d in " + sc + ".");
        await this.loadScopes();
        await this.loadSkills();
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
        this.toast("Purged " + (res.purged || []).length + " skill(s) from trash.");
        this.selectedTrash = null;
        await this.loadTrash();
        await this.loadSkills();
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    async restoreTrash() {
      if (!this.selectedTrash) return;
      const name = this.selectedTrash.name;
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

    openHistory(scopeOverride = null) {
      if (!(this.commandPaletteTransfer && this.modalRestoreFocus)) this.modalRestoreFocus = document.activeElement;
      this.modals.history = { name: "", rows: [], snapshots: [], loading: false, scope: scopeOverride || "" };
      this.loadHistory();
    },

    async loadHistory() {
      const m = this.modals.history;
      if (!m) return;
      m.loading = true;
      try {
        const name = m.name ? "&name=" + encodeURIComponent(m.name) : "";
        m.rows = await api("/api/history?limit=200" + name);
        m.snapshots = [];
        if (m.name) {
          const scope = m.scope || ((this.selected && this.selected.scope) ? this.selected.scope : "global");
          const snapshotResult = await api("/api/history?name=" + encodeURIComponent(m.name) + "&scope=" + encodeURIComponent(scope) + "&snapshots=1");
          m.snapshots = snapshotResult.snapshots || [];
        }
      } catch (e) {
        this.toast(e.message, "err");
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

    async doSync() {
      const m = this.modals.sync;
      if (!m) return;
      const to = Object.keys(m.picked).filter((k) => m.picked[k]);
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
}).mount("#app");
