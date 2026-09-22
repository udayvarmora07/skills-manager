/* Skills Manager web UI — Vue 3 application (no build step). */
"use strict";

/* ------------------------------------------------------------- utilities */

const { api, formatBytes, formatTokens, tokenPctClass, tokenBarWidth, renderMarkdown, parseFrontmatter, formatCompat, formatTools, groupLogicalSkills, deriveLogicalSkillIdentity, observedIdentity } = window.SkillManagerDomain;

/* ------------------------------------------------------------------ app */

const { createApp, nextTick } = Vue;

createApp({
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
      scopes: [],
      activeScope: localStorage.getItem("skillsmgr-scope") || "all",
      libraryMode: localStorage.getItem("skillsmgr-library-mode") || "library",
      browseMode: localStorage.getItem("skillsmgr-browse-mode") === "grid" ? "grid" : "list",
      onboardingDismissed: false,
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
      profileForm: { name: "", description: "", skills: "", targets: "" },
      profilePreview: null,
      mobileDetailOpen: false,
      compactControlsOpen: false,
      mobileReturnKey: "",
      toasts: [],
      liveAnnouncement: "",
      toastSeq: 0,
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
      if (!needle) return this.commandPaletteCommands;
      return this.commandPaletteCommands.filter((command) => [command.label, command.title, command.category, command.keywords]
        .join(" ").toLowerCase().includes(needle));
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
      return this.overviewRecords.filter((record) => {
        const states = record.instance_states || record.states || [];
        return !record.disabled
          && !record.malformed
          && !record.decode_error
          && record.addressable !== false
          && !states.some((state) => ["invalid", "malformed", "unaddressable"].includes(state));
      }).length;
    },
    overviewDisabledCount() {
      return this.overviewRecords.filter((record) => !!record.disabled).length;
    },
    overviewDivergentGroups() {
      return this.overviewLogicalSkills.filter((group) => !!group.divergent);
    },
    overviewMalformedCount() {
      return this.overviewRecords.filter((record) => {
        const states = record.instance_states || record.states || [];
        return !!record.malformed || states.includes("malformed");
      }).length;
    },
    overviewUnaddressableCount() {
      return this.overviewRecords.filter((record) => {
        const states = record.instance_states || record.states || [];
        return record.addressable === false || states.includes("unaddressable");
      }).length;
    },
    overviewInvalidRecords() {
      return this.overviewRecords.filter((record) => {
        const states = record.instance_states || record.states || [];
        return !!record.malformed
          || !!record.decode_error
          || record.addressable === false
          || states.some((state) => ["invalid", "malformed", "unaddressable"].includes(state));
      });
    },
    overviewAttention() {
      const items = [];
      if (this.overviewInvalidRecords.length) {
        const count = this.overviewInvalidRecords.length;
        items.push({
          key: "observed-invalid",
          title: "Review malformed or unaddressable entries",
          detail: `${count} observed instance${count === 1 ? " cannot" : "s cannot"} be treated as a normal addressable skill.`,
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
        const states = record.instance_states || record.states || [];
        if (states.includes("invalid")) return "invalid";
        if (record.malformed || record.decode_error || states.includes("malformed")) return "malformed";
        if (record.addressable === false || states.includes("unaddressable")) return "unaddressable";
        if (record.disabled) return "disabled";
        return "observed";
      };
      const validityFlagged = records.filter((record) => {
        const states = record.instance_states || record.states || [];
        return record.malformed
          || record.decode_error
          || record.addressable === false
          || states.some((state) => ["invalid", "malformed", "unaddressable"].includes(state));
      });
      return {
        observed: records.length,
        active: records.filter((record) => stateOf(record) === "observed").length,
        disabled: records.filter((record) => stateOf(record) === "disabled").length,
        malformed: records.filter((record) => stateOf(record) === "malformed").length,
        unaddressable: records.filter((record) => stateOf(record) === "unaddressable").length,
        validityFlagged: validityFlagged.length,
        divergent: logical.filter((group) => !!group.divergent).length,
        provenance: records.filter((record) => record.registry_provenance && typeof record.registry_provenance === "object").length,
      };
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
    this.removeThemeListener();
    document.removeEventListener("keydown", this.onKeydown);
    document.removeEventListener("mousedown", this.onDocMousedown);
  },

  methods: {
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
      const states = (record && (record.instance_states || record.states)) || [];
      if (states.includes("invalid")) return "Invalid observed";
      if (record && (record.malformed || record.decode_error || states.includes("malformed"))) return "Malformed observed";
      if (record && (record.addressable === false || states.includes("unaddressable"))) return "Unaddressable observed";
      if (record && record.disabled) return "Disabled observed";
      return "Observed; not a validation verdict";
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
      } catch (e) { /* non-fatal */ }
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
        this.skills = rows;
        this.allSkills = rows.slice();
        if (this.query.trim() && this.view === "skills") this.applySearch();
        if (this.selectedName) {
          const still = this.skills.find((sk) => sk.name === this.selectedName && (s === "all" || sk.scope === s));
          if (still) this.loadDetail(still.name, still.scope);
          else { this.selectedName = null; this.selected = null; }
        }
      } catch (e) {
        if (mySeq !== this.listSeq) return;
        this.banner = { type: "error", text: "Could not load skills: " + e.message };
      } finally {
        if (mySeq === this.listSeq) this.loadingList = false;
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
          const raw = await fetch("/api/skills/" + encodeURIComponent(name) + "/raw" + qp);
          if (raw.ok) {
            const text = await raw.text();
            Object.assign(record, parseFrontmatter(text));
          } else if (mySeq === this.detailSeq) {
            this.toast("Could not load full metadata (compatibility may be missing).", "err");
          }
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
      if (v === "trash" || v === "recovery") this.loadTrash();
      if (v === "recovery") this.loadRecoverySnapshots();
      else if (v === "install") this.loadSkills();
      else if (v === "workspaces") this.loadWorkspaces();
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
          const states = record.instance_states || record.states || [];
          return !!record.malformed || record.addressable === false || states.includes("malformed") || states.includes("unaddressable");
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

    toast(text, type = "ok", undo = null) {
      const id = ++this.toastSeq;
      this.toasts.push({ id, text, type, undo });
      this.liveAnnouncement = text;
      setTimeout(() => {
        this.toasts = this.toasts.filter((t) => t.id !== id);
      }, undo ? 8000 : 4000);
    },

    async undoToast(t) {
      this.toasts = this.toasts.filter((x) => x.id !== t.id);
      try { await t.undo(); } catch (e) { this.toast("Undo failed: " + e.message, "err"); }
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
        if (this.menuOpen) this.closeActionsMenu(true);
        else if (this.modals.commands) this.closeModal("commands");
        else if (this.modals.remove) this.closeModal("remove");
        else if (this.modals.purge) this.closeModal("purge");
        else if (this.modals.skill) this.closeModal("skill");
        else if (this.modals.validate) this.closeModal("validate");
        else if (this.modals.doctor) this.closeModal("doctor");
        else if (this.modals.stats) this.closeModal("stats");
        else if (this.modals.history) this.closeModal("history");
        else if (this.modals.templates) this.closeModal("templates");
        else if (this.modals.newtemplate) this.closeModal("newtemplate");
        else if (this.modals.import) this.closeModal("import");
        else if (this.modals.sync) this.closeModal("sync");
        else if (this.modals.install) this.closeModal("install");
        else if (this.modals.batch) this.closeModal("batch");
        else if (this.modals.update) this.requestCloseUpdate();
        else if (this.modals.help) this.closeModal("help");
      }
    },

    onDocMousedown(e) {
      if (this.menuOpen && this.$refs.menuWrap && !this.$refs.menuWrap.contains(e.target)) {
        this.menuOpen = false;
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
        const raw = await fetch("/api/skills/" + encodeURIComponent(this.selectedName) + "/raw" + qp);
        if (raw.ok) {
          const text = await raw.text();
          const fm = parseFrontmatter(text);
          if (!this.modals.skill) return;
          if (fm.compatibility && !this.modals.skill.form.compatibility) this.modals.skill.form.compatibility = fm.compatibility;
          if (fm.allowed_tools && !this.modals.skill.form.allowed_tools) this.modals.skill.form.allowed_tools = fm.allowed_tools;
        }
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
          const res = await fetch("/api/import", { method: "PUT", body: form });
          let data = null;
          try { data = await res.json(); } catch (e) { /* ignore */ }
          if (!res.ok) throw new Error((data && data.error) || "HTTP " + res.status);
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
          body: JSON.stringify({ name: m.name }),
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
        const res = await fetch(url, { method: "PUT", body: m.file });
        let data = null;
        try { data = await res.json(); } catch (e) { /* ignore */ }
        if (!res.ok) throw new Error((data && data.error) || "HTTP " + res.status);
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
        const res = await fetch("/api/export" + (full ? "?full=1" : ""));
        if (!res.ok) throw new Error("Export failed (HTTP " + res.status + ")");
        const blob = await res.blob();
        const cd = res.headers.get("Content-Disposition") || "";
        const m = /filename="?([^";]+)"?/.exec(cd);
        const filename = m ? m[1] : "skills-export.tar.gz";
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
