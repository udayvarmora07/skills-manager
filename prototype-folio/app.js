/* ==========================================================================
   Folio app: preferences, actions, events, init
   ========================================================================== */

/* --------------------------------------------------------------------------
   Preferences
   -------------------------------------------------------------------------- */

function resolvedTheme() {
  if (state.theme === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return state.theme === "dark" ? "dark" : "light";
}

function applyPreferences() {
  const theme = resolvedTheme();
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.textSize = state.textSize;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#0c0e0b" : "#eff0ec");
}

function updateMasthead() {
  const theme = resolvedTheme();
  const iconMount = document.getElementById("theme-icon");
  if (iconMount) iconMount.innerHTML = icon(theme === "dark" ? "sun" : "moon");
  const toggle = document.getElementById("theme-toggle");
  if (toggle) toggle.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
  const drawer = document.getElementById("drawer-toggle");
  if (drawer) drawer.setAttribute("aria-expanded", String(state.railOpen));
}

function render() {
  applyPreferences();
  document.body.classList.toggle("mobile-detail", state.mobileDetail && state.view === "library");
  document.body.classList.toggle("rail-open", state.railOpen);
  updateMasthead();
  renderRail();
  renderStage();
  renderStatus();
  renderOverlay();
  renderToasts();
}

/* --------------------------------------------------------------------------
   Navigation
   -------------------------------------------------------------------------- */

function go(view, options = {}) {
  if (!["overview", "library", "context", "quality", "profiles", "install", "recovery", "settings"].includes(view)) return;
  state.view = view;
  state.mobileDetail = false;
  state.railOpen = false;
  state.palette = false;
  state.modal = null;
  if (view === "library") {
    state.limit = 60;
    state.scrollSelected = true;
  }
  render();
  const main = document.getElementById("main");
  if (main) main.scrollTop = 0;
  if (options.focus) {
    requestAnimationFrame(() => {
      const heading = document.querySelector("#stage h1");
      if (heading) {
        heading.setAttribute("tabindex", "-1");
        heading.focus({ preventScroll: true });
      }
    });
  }
}

function selectSkill(name, options = {}) {
  const skill = findSkill(name);
  if (!skill) return;
  state.selected = name;
  state.detailTab = "document";
  const mobile = window.innerWidth <= 820;
  state.mobileDetail = mobile;
  state.scrollSelected = true;
  state.focusKey = options.focus === false ? "" : mobile ? "doc-back" : `skill:${name}`;
  if (state.view !== "library") state.view = "library";
  render();
}

function alignSelectionToFilter() {
  const list = filteredSkills();
  if (!list.length) return;
  if (!list.some((skill) => skill.name === state.selected)) {
    state.selected = list[0].name;
    state.detailTab = "document";
  }
}

function setScope(scope) {
  state.scope = scope;
  state.view = "library";
  state.limit = 60;
  state.mobileDetail = false;
  state.railOpen = false;
  alignSelectionToFilter();
  state.scrollSelected = true;
  state.focusKey = "scope-select";
  render();
}

function setStatus(status) {
  state.status = status;
  state.limit = 60;
  alignSelectionToFilter();
  state.scrollSelected = true;
  state.focusKey = `status:${status}`;
  render();
}

function clearFilters() {
  state.query = "";
  state.status = "all";
  state.scope = "all";
  state.sort = "name";
  state.limit = 60;
  state.focusKey = "library-query";
  render();
}

function moveSelection(delta) {
  const visible = filteredSkills();
  if (!visible.length) return;
  const index = visible.findIndex((skill) => skill.name === state.selected);
  const next = Math.max(0, Math.min(visible.length - 1, (index < 0 ? 0 : index + delta)));
  state.selected = visible[next].name;
  state.detailTab = "document";
  state.scrollSelected = true;
  state.focusKey = `skill:${state.selected}`;
  render();
}

function toggleRail() {
  state.railOpen = !state.railOpen;
  document.body.classList.toggle("rail-open", state.railOpen);
  const drawer = document.getElementById("drawer-toggle");
  if (drawer) drawer.setAttribute("aria-expanded", String(state.railOpen));
}

function closeRail() {
  state.railOpen = false;
  document.body.classList.remove("rail-open");
  const drawer = document.getElementById("drawer-toggle");
  if (drawer) drawer.setAttribute("aria-expanded", "false");
}

/* --------------------------------------------------------------------------
   Overlays
   -------------------------------------------------------------------------- */

function restoreFocus() {
  const last = state.lastFocus;
  state.lastFocus = null;
  if (last && document.contains(last)) {
    try {
      last.focus({ preventScroll: true });
    } catch (error) {
      /* The trigger may have been replaced by a render. */
    }
  }
}

function openPalette() {
  if (state.modal) return;
  state.lastFocus = document.activeElement;
  state.palette = true;
  state.paletteQuery = "";
  state.paletteIndex = 0;
  renderOverlay();
}

function closePalette() {
  state.palette = false;
  state.paletteQuery = "";
  state.paletteIndex = 0;
  renderOverlay();
  restoreFocus();
}

function openModal(modal) {
  state.palette = false;
  state.lastFocus = document.activeElement;
  state.modal = modal;
  renderOverlay();
}

function closeOverlay() {
  if (state.palette) {
    closePalette();
    return;
  }
  state.modal = null;
  renderOverlay();
  restoreFocus();
}

function runPalette(index) {
  const item = paletteItems()[index];
  if (!item) return;
  state.palette = false;
  state.paletteQuery = "";
  state.paletteIndex = 0;
  renderOverlay();
  if (item.action) item.action();
}

function trapFocus(event) {
  const scope = state.palette ? document.querySelector(".palette") : document.querySelector(".overlay-card");
  if (!scope) return;
  const focusable = Array.from(
    scope.querySelectorAll(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
    )
  ).filter((element) => element.offsetParent !== null);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  if (!scope.contains(document.activeElement)) {
    event.preventDefault();
    first.focus();
    return;
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

/* --------------------------------------------------------------------------
   Actions
   -------------------------------------------------------------------------- */

function toggleTheme() {
  const current = resolvedTheme();
  state.theme = current === "dark" ? "light" : "dark";
  store.set("folio-theme", state.theme);
  render();
}

function openCreate() {
  openModal({ type: "create", edit: false });
}

function openEdit() {
  const skill = selectedSkill();
  if (!skill) return;
  if (skill.addressable === false) {
    toast("This directory cannot be addressed by name. Rename it first.");
    return;
  }
  openModal({ type: "create", edit: true });
}

function openHelp() {
  openModal({ type: "help" });
}

function openAbout() {
  openModal({ type: "about" });
}

function openSync() {
  const skill = selectedSkill();
  if (!skill) return;
  if (skill.addressable === false) {
    toast("This directory cannot be addressed by name. Rename it first.");
    return;
  }
  state.syncTargets = new Set(
    F.SCOPES.filter((scope) => scope.writable && !skill.instances.some((instance) => instance.scope === scope.id)).map(
      (scope) => scope.id
    )
  );
  openModal({ type: "sync" });
}

function applySync() {
  const skill = selectedSkill();
  if (!skill) return;
  const targets = Array.from(state.syncTargets);
  if (!targets.length) return;
  const now = new Date().toISOString();
  targets.forEach((scope) => {
    skill.instances.push(F.makeInstance(skill.name, scope, "active", skill.tokens, { modified: now }));
  });
  skill.copies = skill.instances.length;
  skill.scopes = Array.from(new Set(skill.instances.map((instance) => instance.scope)));
  skill.state = F.stateOf(skill);
  skill.updated = now;
  skill.totalTokens = skill.instances.reduce((sum, instance) => sum + instance.tokens, 0);
  skill.history.unshift({ action: "synced in prototype", at: now, note: `${targets.length} new targets.` });
  closeOverlay();
  state.focusKey = `skill:${skill.name}`;
  render();
  toast(`Copied to ${targets.length} ${targets.length === 1 ? "root" : "roots"}. Existing copies were skipped.`);
}

function toggleSelected() {
  const skill = selectedSkill();
  if (!skill) return;
  if (skill.addressable === false) {
    toast("This directory cannot be addressed by name. Rename it first.");
    return;
  }
  const allDisabled = skill.instances.every((instance) => instance.state === "disabled");
  const target = allDisabled
    ? skill.instances.find((instance) => instance.state === "disabled")
    : skill.instances.find((instance) => instance.state === "active" || instance.state === "mixed");
  if (!target) {
    toast("No copy can change state in this sample record.");
    return;
  }
  const before = target.state;
  target.state = allDisabled ? "active" : "disabled";
  skill.state = F.stateOf(skill);
  skill.updated = new Date().toISOString();
  skill.history.unshift({
    action: allDisabled ? "enabled in prototype" : "disabled in prototype",
    at: skill.updated,
    note: `${scopeLabel(target.scope)}. Memory only.`,
  });
  state.focusKey = "doc-toggle";
  render();
  toast(`${allDisabled ? "Enabled" : "Disabled"} ${scopeLabel(target.scope)}.`, {
    actionLabel: "Undo",
    action: () => {
      target.state = before;
      skill.state = F.stateOf(skill);
      render();
      toast("Reverted the state change.");
    },
  });
}

function openCompare(scopeId) {
  const skill = selectedSkill();
  if (!skill) return;
  const canonical = skill.instances.find((instance) => instance.state === "active") || skill.instances[0];
  if (!canonical) return;
  state.diffMode = "split";
  openModal({
    type: "diff",
    skill: skill.name,
    leftScope: canonical.scope,
    rightScope: scopeId,
  });
}

function openFinding(id) {
  openModal({ type: "finding", id });
}

function openRollback(id) {
  openModal({ type: "rollback", id });
}

function openProfilePlan() {
  openModal({ type: "profile-plan" });
}

function applyProfile() {
  const profile = selectedProfile();
  let enabled = 0;
  profile.members.forEach((member) => {
    if (member.state === "disabled") {
      member.state = "observed";
      enabled += 1;
    }
  });
  closeOverlay();
  render();
  toast(
    `Enable plan applied to ${enabled} disabled ${enabled === 1 ? "copy" : "copies"}. Missing and divergent members were left unchanged.`
  );
}

function openPurge() {
  openModal({ type: "purge" });
}

function purgeTrash() {
  const count = F.TRASH.length;
  F.TRASH.length = 0;
  state.modal = null;
  renderOverlay();
  render();
  const heading = document.querySelector("#stage h1");
  if (heading) {
    heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
  }
  toast(`Purged ${count} ${count === 1 ? "item" : "items"}. This cannot be undone.`);
}

function restoreTrash(id) {
  const index = F.TRASH.findIndex((item) => item.id === id);
  if (index < 0) return;
  const item = F.TRASH[index];
  F.TRASH.splice(index, 1);

  const body = F.bodyFor(item.name, "Restored from the sample trash.", "Recovered");
  const tokens = Math.max(120, Math.round(body.length / 4));
  const now = new Date().toISOString();
  const restored = {
    name: item.name,
    description: "Restored from the sample trash.",
    category: "Recovered",
    version: "0.1.0",
    license: "MIT",
    allowedTools: "Read",
    malformed: false,
    addressable: true,
    body,
    variantBody: null,
    validation: { valid: true, issues: [] },
    history: [{ action: "restored from trash", at: now, note: "Memory only." }],
    instances: [F.makeInstance(item.name, "global", "active", tokens, { modified: now })],
  };
  restored.state = "active";
  restored.tokens = tokens;
  restored.totalTokens = tokens;
  restored.copies = 1;
  restored.updated = now;
  restored.scopes = ["global"];
  skills.unshift(restored);
  render();
  toast(`Restored ${item.name} to the global store.`, {
    actionLabel: "Undo",
    action: () => {
      skills = skills.filter((skill) => skill !== restored);
      F.TRASH.splice(index, 0, item);
      render();
      toast("Moved the item back to the trash.");
    },
  });
}

function installRegistry() {
  const item = selectedRegistryItem();
  if (!item || !state.installTrusted) return;
  if (item.validation.errors > 0) {
    toast("This snapshot has a validation error. A commit is blocked until it is fixed.");
    return;
  }
  if (state.installed.has(item.id)) return;
  if (findSkill(item.name)) {
    toast(`${item.name} is already in the catalogue. The prototype does not overwrite a copy.`);
    return;
  }

  const body = F.bodyFor(item.name, item.description, item.category);
  const tokens = Math.max(160, Math.round(body.length / 4));
  const now = new Date().toISOString();
  const skill = {
    name: item.name,
    description: item.description,
    category: item.category,
    version: "1.0.0",
    license: "MIT",
    allowedTools: "Read, Grep",
    malformed: false,
    addressable: true,
    body,
    variantBody: null,
    validation: { valid: item.validation.errors === 0, issues: [] },
    history: [
      {
        action: "added from registry",
        at: now,
        note: `${item.source}. ${item.files} files, review confirmed in the prototype.`,
      },
    ],
    instances: [F.makeInstance(item.name, "global", "active", tokens, { modified: now })],
  };
  skill.state = "active";
  skill.tokens = tokens;
  skill.totalTokens = tokens;
  skill.copies = 1;
  skill.updated = now;
  skill.scopes = ["global"];
  skills.unshift(skill);
  state.installed.add(item.id);
  state.installTrusted = false;
  state.focusKey = "install-success";
  render();
  toast(`Added ${item.name} to the global store. The prototype wrote to memory only.`);
}

function resetInstall(id) {
  const item = F.REGISTRY.find((entry) => entry.id === id);
  if (!item) return;
  skills = skills.filter((skill) => skill.name !== item.name);
  state.installed.delete(id);
  state.installTrusted = false;
  render();
  toast("Removed the sample copy. No file was touched.");
}

function copyText(text, label) {
  if (!text) return;
  const done = () => toast(`${label} copied.`);
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
    } else {
      fallbackCopy(text, done);
    }
  } catch (error) {
    fallbackCopy(text, done);
  }
}

function fallbackCopy(text, done) {
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  try {
    document.execCommand("copy");
    done();
  } catch (error) {
    toast("Copy is not available in this browser.");
  }
  area.remove();
}

function refreshScan() {
  state.scanAt = new Date().toISOString();
  render();
  toast(`Scan complete. ${fmtNum(F.TOTAL_INSTANCES)} instances across ${F.SCOPES.length} roots.`);
}

/* --------------------------------------------------------------------------
   Toast
   -------------------------------------------------------------------------- */

function toast(message, options = {}) {
  clearTimeout(state.toastTimer);
  state.toast = {
    message,
    actionLabel: options.actionLabel || "",
    action: options.action || null,
  };
  renderToasts();
  state.toastTimer = setTimeout(() => {
    state.toast = null;
    renderToasts();
  }, options.duration || 5200);
}

function renderToasts() {
  const root = document.getElementById("toast-root");
  if (!root) return;
  if (!state.toast) {
    root.innerHTML = "";
    return;
  }
  const current = state.toast;
  root.innerHTML = `<div class="toast" role="status">
    <span class="toast-message">${esc(current.message)}</span>
    ${current.actionLabel ? `<button class="toast-action" type="button" data-action="toast-run">${esc(current.actionLabel)}</button>` : ""}
    <button class="toast-close" type="button" data-action="toast-close" aria-label="Dismiss">×</button>
  </div>`;
}

/* --------------------------------------------------------------------------
   Incremental updates
   -------------------------------------------------------------------------- */

function updateLibraryResults() {
  const visible = filteredSkills();
  const selected = visible.find((skill) => skill.name === state.selected) || visible[0] || null;
  const list = document.getElementById("skill-list");
  if (list) list.innerHTML = renderSkillListInner(visible, selected);
  const count = document.getElementById("library-count");
  if (count) count.textContent = `${fmtNum(visible.length)} of ${fmtNum(skills.length)}`;
}

function updateQualityResults() {
  const findings = qualityFindings();
  const list = document.getElementById("finding-list");
  if (list) {
    list.innerHTML = findings.length
      ? findings.map(renderFindingRow).join("")
      : `<div class="empty" style="border-top:0;padding:34px 16px"><div class="empty-mark">${icon(
          "checkCircle"
        )}</div><h2>No findings match this view.</h2><p>Clear the severity filter or search a different term. The ledger still holds ${fmtNum(
          F.QUALITY.length
        )} findings.</p></div>`;
  }
  const count = document.getElementById("quality-count");
  if (count) count.textContent = `${fmtNum(findings.length)} findings`;
}

function updateInstallResults() {
  const previous = state.installSelected;
  const list = registryItems();
  const item = list.find((entry) => entry.id === state.installSelected) || list[0] || null;
  if (item) state.installSelected = item.id;
  if (state.installSelected !== previous) state.installTrusted = false;

  const container = document.getElementById("registry-list");
  if (container) {
    container.innerHTML = list.length
      ? list.map((entry) => renderRegistryRow(entry, item)).join("")
      : `<div class="empty" style="border-top:0;padding:32px 16px"><div class="empty-mark">${icon(
          "search"
        )}</div><h2>No registry entries match this view.</h2><p>Try another source or a broader search. The prototype ships a fixed snapshot.</p></div>`;
  }
  const panel = document.getElementById("trust-panel");
  if (panel) panel.innerHTML = renderTrustPanel(item);
  const count = document.getElementById("registry-count");
  if (count) count.textContent = `${fmtNum(list.length)} sources`;
}

/* --------------------------------------------------------------------------
   Create / edit submit
   -------------------------------------------------------------------------- */

function submitCreate(form) {
  const name = form.querySelector("#create-name").value.trim();
  const description = form.querySelector("#create-description").value.trim();
  const category = form.querySelector("#create-category").value;
  const body = form.querySelector("#create-body").value;
  const editing = Boolean(state.modal && state.modal.edit);

  const clearErrors = () => {
    ["name", "description", "body"].forEach((key) => {
      const error = document.getElementById(`create-${key}-error`);
      const input = document.getElementById(`create-${key}`);
      if (error) {
        error.textContent = "";
        error.hidden = true;
      }
      if (input) {
        input.removeAttribute("aria-invalid");
        input.setAttribute("aria-describedby", `create-${key}-hint`);
      }
    });
  };

  const fail = (message, key) => {
    const error = document.getElementById(`create-${key}-error`);
    const input = document.getElementById(`create-${key}`);
    if (error) {
      error.textContent = message;
      error.hidden = false;
    }
    if (input) {
      input.setAttribute("aria-invalid", "true");
      input.setAttribute("aria-describedby", `create-${key}-hint create-${key}-error`);
      input.focus();
    }
  };

  clearErrors();

  if (!F.NAME_RE.test(name)) {
    fail("Use lowercase letters, numbers, and single hyphens. Leading, trailing, and doubled hyphens are not allowed.", "name");
    return;
  }
  if (name.length > 64) {
    fail("The name must be 64 characters or fewer.", "name");
    return;
  }
  if (!editing && findSkill(name)) {
    fail("A skill with that name is already in the catalogue. Open it and edit the document instead.", "name");
    return;
  }
  if (!description) {
    fail("Add one sentence that names the moment to use the skill.", "description");
    return;
  }
  if (description.length > 1024) {
    fail("Keep the description under 1,024 characters.", "description");
    return;
  }
  if (!body.trim()) {
    fail("The document cannot be empty.", "body");
    return;
  }

  const now = new Date().toISOString();
  if (editing) {
    const skill = selectedSkill();
    if (!skill) return;
    skill.description = description;
    skill.category = category;
    skill.body = body;
    skill.tokens = Math.max(120, Math.round(body.length / 4));
    if (skill.instances[0]) skill.instances[0].tokens = skill.tokens;
    skill.totalTokens = skill.instances.reduce((sum, instance) => sum + instance.tokens, 0);
    skill.updated = now;
    skill.history.unshift({ action: "edited in prototype", at: now, note: "Memory only. No file was written." });
    closeOverlay();
    state.focusKey = window.innerWidth <= 820 ? "doc-back" : `skill:${skill.name}`;
    render();
    toast("Document updated in the prototype. No file was written.");
    return;
  }

  let documentBody = body.replace(/\r\n/g, "\n");
  const placeholder = "Describe the moment a reader should load this skill.";
  if (documentBody.includes(placeholder)) {
    documentBody = documentBody.replace(placeholder, () => description);
  }
  const tokens = Math.max(120, Math.round(documentBody.length / 4));
  const skill = {
    name,
    description,
    category,
    version: "0.1.0",
    license: "MIT",
    allowedTools: "Read, Grep",
    malformed: false,
    addressable: true,
    body: documentBody,
    variantBody: null,
    validation: { valid: true, issues: [] },
    history: [{ action: "created in prototype", at: now, note: "Memory only. No file was written." }],
    instances: [F.makeInstance(name, "global", "active", tokens, { modified: now })],
  };
  skill.state = "active";
  skill.tokens = tokens;
  skill.totalTokens = tokens;
  skill.copies = 1;
  skill.updated = now;
  skill.scopes = ["global"];
  skills.unshift(skill);
  state.selected = name;
  state.detailTab = "document";
  state.view = "library";
  state.status = "all";
  state.scope = "all";
  state.query = "";
  state.sort = "name";
  state.limit = skills.length;
  state.mobileDetail = window.innerWidth <= 820;
  state.scrollSelected = true;
  state.focusKey = window.innerWidth <= 820 ? "doc-back" : `skill:${name}`;
  closeOverlay();
  render();
  toast("Skill created in the global store. The record lives in memory.");
}

/* --------------------------------------------------------------------------
   Event: click
   -------------------------------------------------------------------------- */

function onClick(event) {
  if (event.target.classList.contains("rail-backdrop")) {
    closeRail();
    return;
  }
  if (event.target.classList.contains("overlay")) {
    closeOverlay();
    return;
  }

  const target = event.target.closest(
    "[data-action], [data-go], [data-skill], [data-scope], [data-tab], [data-status], [data-quality-severity], [data-window], [data-source], [data-theme-choice], [data-size-choice], [data-demo], [data-registry], [data-profile]"
  );
  if (!target) return;

  if (target.dataset.go) {
    go(target.dataset.go, { focus: true });
    return;
  }

  if (target.dataset.action) {
    handleAction(target);
    return;
  }

  if (target.dataset.skill) {
    selectSkill(target.dataset.skill, { focus: true });
    return;
  }

  if (target.dataset.scope) {
    setScope(target.dataset.scope);
    return;
  }

  if (target.dataset.tab) {
    state.detailTab = target.dataset.tab;
    state.focusKey = `tab:${state.detailTab}`;
    render();
    return;
  }

  if (target.dataset.status) {
    setStatus(target.dataset.status);
    return;
  }

  if (target.dataset.qualitySeverity) {
    state.qualitySeverity = target.dataset.qualitySeverity;
    state.focusKey = `qsev:${state.qualitySeverity}`;
    render();
    return;
  }

  if (target.dataset.window) {
    state.window = target.dataset.window;
    state.focusKey = `window:${state.window}`;
    render();
    return;
  }

  if (target.dataset.source) {
    state.installSource = target.dataset.source;
    state.installTrusted = false;
    state.installSelected = "";
    state.focusKey = `source:${state.installSource}`;
    render();
    return;
  }

  if (target.dataset.themeChoice) {
    state.theme = target.dataset.themeChoice;
    store.set("folio-theme", state.theme);
    state.focusKey = `theme:${state.theme}`;
    render();
    return;
  }

  if (target.dataset.sizeChoice) {
    state.textSize = target.dataset.sizeChoice;
    store.set("folio-size", state.textSize);
    state.focusKey = `size:${state.textSize}`;
    render();
    return;
  }

  if (target.dataset.demo) {
    state.demo = target.dataset.demo;
    state.focusKey = `demo:${state.demo}`;
    render();
    if (state.demo === "live") {
      requestAnimationFrame(() => {
        const heading = document.querySelector("#stage h1");
        if (heading) {
          heading.setAttribute("tabindex", "-1");
          heading.focus({ preventScroll: true });
        }
      });
    }
    return;
  }

  if (target.dataset.registry) {
    state.installSelected = target.dataset.registry;
    state.installTrusted = false;
    state.focusKey = `registry:${state.installSelected}`;
    render();
    if (window.innerWidth <= 900) {
      requestAnimationFrame(() => {
        const panel = document.getElementById("trust-panel");
        if (panel) {
          const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          panel.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
        }
      });
    }
    return;
  }

  if (target.dataset.profile) {
    state.selectedProfile = target.dataset.profile;
    state.focusKey = `profile:${state.selectedProfile}`;
    render();
  }
}

function handleAction(element) {
  const action = element.dataset.action;
  switch (action) {
    case "toggle-rail":
      toggleRail();
      break;
    case "close-rail":
      closeRail();
      break;
    case "palette":
      openPalette();
      break;
    case "palette-run":
      runPalette(Number(element.dataset.index));
      break;
    case "close-overlay":
      closeOverlay();
      break;
    case "theme":
      toggleTheme();
      break;

    case "attention-all": {
      state.status = "attention";
      state.scope = "all";
      state.query = "";
      state.limit = 60;
      state.view = "library";
      state.mobileDetail = false;
      alignSelectionToFilter();
      state.scrollSelected = true;
      state.focusKey = "status:attention";
      render();
      break;
    }
    case "help":
      openHelp();
      break;
    case "about":
      openAbout();
      break;
    case "create":
      openCreate();
      break;
    case "edit":
      openEdit();
      break;
    case "toggle":
      toggleSelected();
      break;
    case "sync":
      openSync();
      break;
    case "sync-apply":
      applySync();
      break;
    case "compare":
      openCompare(element.dataset.scope);
      break;
    case "validate":
      state.focusKey = "validate";
      render();
      toast("Validation complete. The sample document keeps its existing issues; no new ones were invented.");
      break;
    case "copy-path":
      copyText(element.dataset.path, "Path");
      break;
    case "copy-hash":
      copyText(element.dataset.hash, "Hash");
      break;
    case "refresh-scan":
      refreshScan();
      break;
    case "refresh-hygiene":
      state.scanAt = new Date().toISOString();
      render();
      toast("Hygiene report refreshed. 14 findings, no files changed.");
      break;
    case "add-folder":
      toast("Folder upload belongs to the backend. This prototype keeps its sample inventory.");
      break;
    case "run-scan":
      state.demo = "live";
      state.scanAt = new Date().toISOString();
      render();
      toast("Scan complete. 642 logical skills in 8 roots. Nothing was written.");
      break;
    case "retry-demo":
      state.demo = "live";
      render();
      toast("Retry complete. The sample inventory is available again.");
      break;
    case "clear-demo":
      state.demo = "live";
      render();
      toast("Live sample data restored.");
      break;
    case "clear-filters":
      clearFilters();
      break;
    case "all-roots":
      setScope("all");
      break;
    case "scope-to-library":
      setScope(element.dataset.scope);
      break;
    case "load-more":
      state.limit += 60;
      render();
      break;
    case "mobile-back":
      state.mobileDetail = false;
      state.focusKey = `skill:${state.selected}`;
      render();
      break;
    case "finding-open":
      openFinding(element.dataset.finding);
      break;
    case "finding-skill":
      closeOverlay();
      selectSkill(element.dataset.skill, { focus: true });
      break;
    case "diff-mode":
      state.diffMode = element.dataset.mode;
      renderOverlay();
      requestAnimationFrame(() => {
        const button = document.querySelector(`[data-focus-key="diff:${state.diffMode}"]`);
        if (button) button.focus();
      });
      break;
    case "install-add":
      installRegistry();
      break;
    case "install-reset":
      resetInstall(element.dataset.id);
      break;
    case "view-installed": {
      const item = selectedRegistryItem();
      if (!item) break;
      state.query = "";
      state.status = "all";
      state.scope = "all";
      state.sort = "name";
      go("library");
      selectSkill(item.name, { focus: true });
      break;
    }
    case "restore-trash":
      restoreTrash(element.dataset.id);
      break;
    case "purge-open":
      openPurge();
      break;
    case "purge-confirm":
      purgeTrash();
      break;
    case "rollback":
      openRollback(element.dataset.id);
      break;
    case "rollback-confirm":
      closeOverlay();
      toast("Rollback review created. Apply it from Recovery when you have read the preview.");
      break;
    case "profile-plan":
      openProfilePlan();
      break;
    case "profile-apply":
      applyProfile();
      break;
    case "reset-sample":
      window.location.reload();
      break;
    case "rebuild":
      toast("Index rebuild simulated. The filesystem was not touched.");
      break;
    case "resync":
      toast("Index resync simulated. The filesystem was not touched.");
      break;
    case "export":
      toast("Slim export prepared as a sample archive. No file was written.");
      break;
    case "export-full":
      toast("Full migration export prepared as a sample archive. No file was written.");
      break;
    case "import":
      toast("Archive import is a backend action. The prototype does not read files.");
      break;
    case "toast-run": {
      const current = state.toast;
      state.toast = null;
      clearTimeout(state.toastTimer);
      renderToasts();
      if (current && current.action) current.action();
      break;
    }
    case "toast-close":
      state.toast = null;
      clearTimeout(state.toastTimer);
      renderToasts();
      break;
    default:
      break;
  }
}

/* --------------------------------------------------------------------------
   Event: input, change, submit
   -------------------------------------------------------------------------- */

function onInput(event) {
  const input = event.target.closest("[data-input]");
  if (!input) return;
  const kind = input.dataset.input;
  if (kind === "library-query") {
    state.query = input.value;
    state.limit = 60;
    updateLibraryResults();
  } else if (kind === "palette") {
    state.paletteQuery = input.value;
    state.paletteIndex = 0;
    updatePaletteResults();
  } else if (kind === "quality-query") {
    state.qualityQuery = input.value;
    updateQualityResults();
  } else if (kind === "install-query") {
    state.installQuery = input.value;
    updateInstallResults();
  }
}

function onChange(event) {
  const control = event.target.closest("[data-change]");
  if (!control) return;
  const kind = control.dataset.change;
  if (kind === "scope") {
    setScope(control.value);
  } else if (kind === "sort") {
    state.sort = control.value;
    state.focusKey = "sort-select";
    render();
  } else if (kind === "quality-scope") {
    state.qualityScope = control.value;
    state.focusKey = "quality-scope";
    render();
  } else if (kind === "locale") {
    state.locale = control.value;
    store.set("folio-locale", state.locale);
    state.focusKey = "locale-select";
    render();
  } else if (kind === "trust") {
    state.installTrusted = control.checked;
    const item = selectedRegistryItem();
    const button = document.querySelector('[data-action="install-add"]');
    if (button) button.disabled = !state.installTrusted || !item || item.validation.errors > 0;
  } else if (kind === "sync-target") {
    if (control.checked) state.syncTargets.add(control.value);
    else state.syncTargets.delete(control.value);
    updateSyncPreview();
  }
}

function onSubmit(event) {
  const form = event.target.closest('[data-form="create"]');
  if (!form) return;
  event.preventDefault();
  submitCreate(form);
}

/* --------------------------------------------------------------------------
   Event: keyboard
   -------------------------------------------------------------------------- */

function onKeydown(event) {
  const key = event.key;
  const target = event.target;
  const typing =
    target &&
    target.matches &&
    target.matches('input, textarea, select, [contenteditable="true"]');

  if ((event.metaKey || event.ctrlKey) && key.toLowerCase() === "k") {
    event.preventDefault();
    if (state.palette) closePalette();
    else if (!state.modal) openPalette();
    return;
  }

  if (state.palette) {
    if (key === "Escape") {
      event.preventDefault();
      closePalette();
      return;
    }
    if (key === "Tab") {
      trapFocus(event);
      return;
    }
    if (key === "ArrowDown" || key === "ArrowUp") {
      event.preventDefault();
      const items = paletteItems();
      if (!items.length) return;
      const delta = key === "ArrowDown" ? 1 : -1;
      state.paletteIndex = (state.paletteIndex + delta + items.length) % items.length;
      const selected = document.getElementById(`palette-item-${state.paletteIndex}`);
      if (selected) selected.scrollIntoView({ block: "nearest" });
      $$(".palette-item").forEach((item, index) => item.setAttribute("aria-selected", String(index === state.paletteIndex)));
      const input = document.getElementById("palette-input");
      if (input) input.setAttribute("aria-activedescendant", `palette-item-${state.paletteIndex}`);
      return;
    }
    if (key === "Enter") {
      event.preventDefault();
      runPalette(state.paletteIndex);
      return;
    }
    return;
  }

  if (state.modal) {
    if (key === "Escape") {
      event.preventDefault();
      closeOverlay();
      return;
    }
    if (key === "Tab") {
      trapFocus(event);
      return;
    }
    return;
  }

  if (typing) return;

  if (target && target.classList && target.classList.contains("doc-tab") && (key === "ArrowLeft" || key === "ArrowRight")) {
    event.preventDefault();
    const tabs = Array.from(document.querySelectorAll(".doc-tab"));
    const index = tabs.indexOf(target);
    if (index !== -1) {
      const next = tabs[(index + (key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
      if (next) next.click();
    }
    return;
  }

  if (key === "Escape") {
    if (state.railOpen) {
      closeRail();
      return;
    }
    if (state.mobileDetail) {
      state.mobileDetail = false;
      state.focusKey = `skill:${state.selected}`;
      render();
      return;
    }
    return;
  }

  if (state.gPending) {
    state.gPending = false;
    clearTimeout(state.gTimer);
    const destinations = {
      o: "overview",
      l: "library",
      c: "context",
      q: "quality",
      p: "profiles",
      i: "install",
      r: "recovery",
      s: "settings",
    };
    if (destinations[key]) {
      event.preventDefault();
      go(destinations[key], { focus: true });
      return;
    }
  }

  if (key === "g") {
    state.gPending = true;
    clearTimeout(state.gTimer);
    state.gTimer = setTimeout(() => {
      state.gPending = false;
    }, 900);
    return;
  }

  if (key === "?") {
    event.preventDefault();
    openHelp();
    return;
  }

  if (key === "/") {
    event.preventDefault();
    openPalette();
    return;
  }

  if (key === "n") {
    event.preventDefault();
    openCreate();
    return;
  }

  if (key === "t") {
    event.preventDefault();
    toggleTheme();
    return;
  }

  if (state.view === "library" && (key === "j" || key === "k")) {
    event.preventDefault();
    moveSelection(key === "j" ? 1 : -1);
  }
}

/* --------------------------------------------------------------------------
   Init
   -------------------------------------------------------------------------- */

function init() {
  applyPreferences();
  render();
  const main = document.getElementById("main");
  if (main) main.scrollTop = 0;

  document.addEventListener("click", onClick);
  document.addEventListener("input", onInput);
  document.addEventListener("change", onChange);
  document.addEventListener("submit", onSubmit);
  document.addEventListener("keydown", onKeydown);

  const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  if (darkQuery.addEventListener) {
    darkQuery.addEventListener("change", () => {
      if (state.theme === "system") render();
    });
  }

  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (motionQuery.addEventListener) {
    motionQuery.addEventListener("change", () => {
      if (state.view === "settings") render();
    });
  }
}

init();
