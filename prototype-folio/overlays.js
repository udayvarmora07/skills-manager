/* ==========================================================================
   Folio overlays: command palette, dialogs, diff
   ========================================================================== */

const COMMANDS = [
  { group: "Go", label: "Overview", hint: "g o", icon: "home", action: () => go("overview", { focus: true }) },
  { group: "Go", label: "Catalogue", hint: "g l", icon: "book", action: () => go("library", { focus: true }) },
  { group: "Go", label: "Context", hint: "g c", icon: "gauge", action: () => go("context", { focus: true }) },
  { group: "Go", label: "Quality", hint: "g q", icon: "checkCircle", action: () => go("quality", { focus: true }) },
  { group: "Go", label: "Profiles", hint: "g p", icon: "users", action: () => go("profiles", { focus: true }) },
  { group: "Go", label: "Install", hint: "g i", icon: "download", action: () => go("install", { focus: true }) },
  { group: "Go", label: "Recovery", hint: "g r", icon: "undo", action: () => go("recovery", { focus: true }) },
  { group: "Go", label: "Settings", hint: "g s", icon: "settings", action: () => go("settings", { focus: true }) },
  { group: "Act", label: "New skill", hint: "n", icon: "plus", action: () => openCreate() },
  { group: "Act", label: "Add a folder", hint: "", icon: "folder", action: () => toast("Folder upload belongs to the backend. This prototype keeps sample data.") },
  { group: "Act", label: "Import an archive", hint: "", icon: "upload", action: () => toast("Archive import is a backend action. The prototype does not read files.") },
  { group: "Act", label: "Export the library", hint: "", icon: "download", action: () => toast("Export prepared as a sample archive. No file was written.") },
  { group: "Act", label: "Toggle theme", hint: "t", icon: "moon", action: () => toggleTheme() },
  { group: "Act", label: "Keyboard shortcuts", hint: "?", icon: "keyboard", action: () => openHelp() },
  { group: "Act", label: "About Folio", hint: "", icon: "info", action: () => openAbout() },
];

function paletteItems() {
  const query = state.paletteQuery.trim().toLowerCase();
  const commands = COMMANDS.filter((command) => {
    if (!query) return true;
    return `${command.label} ${command.group}`.toLowerCase().includes(query);
  });

  if (!query) {
    const recent = F.RECENT.slice(0, 3)
      .map((entry) => {
        const skill = findSkill(entry.name);
        if (!skill) return null;
        return {
          group: "Recent",
          label: skill.name,
          hint: `${skill.copies} ${skill.copies === 1 ? "copy" : "copies"}`,
          icon: "clock",
          action: () => {
            closePaletteNow();
            selectSkill(skill.name, { focus: true });
          },
        };
      })
      .filter(Boolean);
    return [...commands, ...recent];
  }

  const matches = skills
    .filter((skill) => `${skill.name} ${skill.description}`.toLowerCase().includes(query))
    .slice(0, 6)
    .map((skill) => ({
      group: "Skills",
      label: skill.name,
      hint: `${skill.copies} ${skill.copies === 1 ? "copy" : "copies"}`,
      icon: "file",
      action: () => {
        closePaletteNow();
        selectSkill(skill.name, { focus: true });
      },
    }));

  return [...commands, ...matches];
}

function renderOverlay() {
  const root = document.getElementById("overlay-root");
  const app = document.getElementById("app");
  if (!root || !app) return;

  if (state.palette) {
    root.innerHTML = renderPalette();
    app.setAttribute("inert", "");
    app.setAttribute("aria-hidden", "true");
    requestAnimationFrame(() => {
      const input = document.getElementById("palette-input");
      if (input) {
        input.focus();
        const length = input.value.length;
        input.setSelectionRange(length, length);
      }
    });
    return;
  }

  if (state.modal) {
    root.innerHTML = renderModal();
    app.setAttribute("inert", "");
    app.setAttribute("aria-hidden", "true");
    requestAnimationFrame(() => {
      const scope = document.querySelector(".overlay-card");
      if (!scope) return;
      const preferred = scope.querySelector("[data-autofocus]");
      if (preferred) {
        preferred.focus();
        return;
      }
      const first = scope.querySelector(
        "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href]"
      );
      if (first) first.focus();
    });
    return;
  }

  root.innerHTML = "";
  app.removeAttribute("inert");
  app.removeAttribute("aria-hidden");
}

/* --------------------------------------------------------------------------
   Command palette
   -------------------------------------------------------------------------- */

function renderPalette() {
  const items = paletteItems();
  return `<div class="overlay" data-overlay="palette" role="presentation">
    <div class="palette" role="dialog" aria-modal="true" aria-label="Command palette">
      <div class="palette-input-row">
        ${icon("search")}
        <input id="palette-input" class="palette-input" type="text" placeholder="Search skills, paths, commands" autocomplete="off" spellcheck="false"
          role="combobox" aria-expanded="true" aria-controls="palette-results"
          aria-activedescendant="${items[state.paletteIndex] ? `palette-item-${state.paletteIndex}` : ""}"
          data-input="palette" value="${esc(state.paletteQuery)}">
        <kbd class="kbd">Esc</kbd>
      </div>
      <div class="palette-results" id="palette-results" role="listbox" aria-label="Commands and skills">${renderPaletteResults(items)}</div>
      <div class="palette-foot"><span><span class="kbd">↑</span> <span class="kbd">↓</span> move</span><span><span class="kbd">Enter</span> run</span><span><span class="kbd">Esc</span> close</span></div>
    </div>
  </div>`;
}

function renderPaletteResults(items) {
  if (!items.length) {
    return `<div class="palette-empty">No command or skill matches “${esc(state.paletteQuery)}”.</div>`;
  }
  const groups = [];
  items.forEach((item, index) => {
    let group = groups.find((entry) => entry.name === item.group);
    if (!group) {
      group = { name: item.group, items: [] };
      groups.push(group);
    }
    group.items.push({ ...item, index });
  });

  return groups
    .map(
      (group) => `<div class="palette-group">${esc(group.name)}</div>${group.items
        .map(
          (item) => `<button class="palette-item" type="button" role="option" id="palette-item-${item.index}" aria-selected="${
            item.index === state.paletteIndex
          }" data-action="palette-run" data-index="${item.index}" data-focus-key="palette-item-${item.index}">
            ${icon(item.icon || "chevronRight")}
            <span class="palette-label">${esc(item.label)}</span>
            <span class="palette-hint">${esc(item.hint || "")}</span>
          </button>`
        )
        .join("")}`
    )
    .join("");
}

function updatePaletteResults() {
  const container = document.getElementById("palette-results");
  if (!container) return;
  const items = paletteItems();
  state.paletteIndex = Math.min(state.paletteIndex, Math.max(0, items.length - 1));
  container.innerHTML = renderPaletteResults(items);
  const input = document.getElementById("palette-input");
  if (input) {
    input.setAttribute(
      "aria-activedescendant",
      items[state.paletteIndex] ? `palette-item-${state.paletteIndex}` : ""
    );
  }
  const selected = document.getElementById(`palette-item-${state.paletteIndex}`);
  if (selected) selected.scrollIntoView({ block: "nearest" });
}

function closePaletteNow() {
  state.palette = false;
  state.paletteQuery = "";
  state.paletteIndex = 0;
  renderOverlay();
}

/* --------------------------------------------------------------------------
   Dialog shell
   -------------------------------------------------------------------------- */

function overlayShell(options) {
  return `<div class="overlay" data-overlay="modal" role="presentation">
    <div class="overlay-card${options.wide ? " overlay-card-wide" : ""}${options.narrow ? " overlay-card-narrow" : ""}" role="dialog" aria-modal="true" aria-labelledby="overlay-title">
      <div class="overlay-head">
        <div>
          <div class="overlay-kicker">${esc(options.kicker)}</div>
          <h2 class="overlay-title" id="overlay-title">${options.title}</h2>
          ${options.sub ? `<p class="overlay-sub">${options.sub}</p>` : ""}
        </div>
        <button class="icon-button overlay-close" type="button" data-action="close-overlay" aria-label="Close">${icon("close")}</button>
      </div>
      <div class="overlay-body">${options.body}</div>
      ${options.foot ? `<div class="overlay-foot">${options.foot}</div>` : ""}
    </div>
  </div>`;
}

function renderModal() {
  if (!state.modal) return "";
  switch (state.modal.type) {
    case "create":
      return renderCreateModal();
    case "sync":
      return renderSyncModal();
    case "diff":
      return renderDiffModal();
    case "help":
      return renderHelpModal();
    case "about":
      return renderAboutModal();
    case "purge":
      return renderPurgeModal();
    case "finding":
      return renderFindingModal();
    case "rollback":
      return renderRollbackModal();
    case "profile-plan":
      return renderProfilePlanModal();
    default:
      return "";
  }
}

/* --------------------------------------------------------------------------
   Create / edit
   -------------------------------------------------------------------------- */

function defaultBody(name, description) {
  const title = titleCase(name);
  return `# ${title}

${description || "Describe the moment a reader should load this skill."}

## When to use

Use this skill when the task matches the description above and the answer has to be checked against the files in the repository.

## Workflow

1. Read the current state.
2. Make the smallest change that solves the task.
3. Run the check. Fix what fails before you report done.

## Done when

The result is observable in the files, not only in the summary.`;
}

function renderCreateModal() {
  const editing = Boolean(state.modal.edit);
  const skill = editing ? selectedSkill() : null;
  if (editing && !skill) return "";
  const categories = ["General", ...Array.from(new Set(skills.map((item) => item.category))).filter((category) => category !== "General").sort()];
  if (skill && !categories.includes(skill.category)) categories.push(skill.category);
  const name = skill ? skill.name : "";
  const description = skill ? skill.description : "";
  const body = skill ? skill.body : defaultBody("new-skill", "");

  return overlayShell({
    kicker: editing ? "Edit document · memory only" : "New skill · global store",
    title: editing ? "Edit the document." : "Start a new skill.",
    sub: editing
      ? "The prototype updates its in-memory record. No file is written and the name cannot be changed here."
      : "A skill is a small document with a trigger, a workflow, and a check. This prototype keeps the record in memory.",
    body: `<form id="create-form" data-form="create" novalidate>
      <div class="settings-controls">
        <div class="field">
          <label for="create-name">Name</label>
          <input class="input" id="create-name" name="name" value="${esc(
            name
          )}" placeholder="e.g. release-notes" autocomplete="off" spellcheck="false" aria-describedby="create-name-hint" ${editing ? "readonly" : "data-autofocus"}>
          <span class="hint" id="create-name-hint">Lowercase letters, numbers, and single hyphens. The directory name must match.</span>
          <span class="field-error" id="create-name-error" hidden></span>
        </div>
        <div class="field">
          <label for="create-description">Description</label>
          <input class="input" id="create-description" name="description" value="${esc(
            description
          )}" placeholder="One sentence that names the moment to use the skill." autocomplete="off" aria-describedby="create-description-hint" ${editing ? "data-autofocus" : ""}>
          <span class="hint" id="create-description-hint">The catalogue shows two lines. The document keeps the full sentence.</span>
          <span class="field-error" id="create-description-error" hidden></span>
        </div>
        <div class="field">
          <label for="create-category">Category</label>
          <select class="select" id="create-category" name="category">
            ${categories.map((category) => `<option value="${esc(category)}"${skill && skill.category === category ? " selected" : ""}>${esc(category)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label for="create-body">Document</label>
          <textarea class="textarea" id="create-body" name="body" spellcheck="false" aria-describedby="create-body-hint">${esc(body)}</textarea>
          <span class="hint" id="create-body-hint">Markdown. The preview in the document room is escaped and read-only.</span>
          <span class="field-error" id="create-body-error" hidden></span>
        </div>
      </div>
    </form>`,
    foot: `<span class="foot-note">${editing ? "The name stays fixed." : "The record is local to this page."}</span>
      <button class="button" type="button" data-action="close-overlay">Cancel</button>
      <button class="button button-primary" type="submit" form="create-form">${editing ? "Save document" : "Create skill"}</button>`,
  });
}

/* --------------------------------------------------------------------------
   Sync
   -------------------------------------------------------------------------- */

function renderSyncModal() {
  const skill = selectedSkill();
  if (!skill) return "";
  const writable = F.SCOPES.filter((scope) => scope.writable);
  return overlayShell({
    kicker: "Sync · exact targets",
    title: "Copy to other roots.",
    sub: `Copy <strong>${esc(skill.name)}</strong> to another root. Existing copies are skipped, not overwritten. The prototype changes memory only.`,
    body: `<div style="border-top:1px solid var(--rule)">
      ${writable
        .map((scope) => {
          const existing = skill.instances.some((instance) => instance.scope === scope.id);
          const checked = state.syncTargets.has(scope.id);
          return `<label style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--rule);cursor:${
            existing ? "not-allowed" : "pointer"
          };opacity:${existing ? ".58" : "1"}">
            <span style="display:flex;align-items:flex-start;gap:9px">
              <input type="checkbox" data-change="sync-target" value="${scope.id}" ${existing ? "disabled" : ""} ${
            checked ? "checked" : ""
          } style="margin-top:2px;accent-color:var(--ink)">
              <span><span class="mono" style="font-size:10.5px">${esc(scope.label)}</span><span class="hint" style="display:block">${esc(
            scope.path
          )}</span></span>
            </span>
            <span class="badge ${existing ? "badge-muted" : "badge-ok"}">${existing ? "Already present" : "New copy"}</span>
          </label>`;
        })
        .join("")}
    </div>
    <div class="note-panel" id="sync-preview" style="margin-top:14px">${syncPreview()}</div>`,
    foot: `<span class="foot-note">Existing copies are reported, never replaced.</span>
      <button class="button" type="button" data-action="close-overlay">Cancel</button>
      <button class="button button-primary" type="button" data-action="sync-apply" id="sync-apply">${syncButtonLabel()}</button>`,
  });
}

function syncPreview() {
  const skill = selectedSkill();
  if (!skill) return "";
  const targets = Array.from(state.syncTargets);
  const existing = skill.instances.length;
  return `<strong>Preview</strong>
    <span>${targets.length} target${targets.length === 1 ? "" : "s"} selected. ${targets.length} new ${
    targets.length === 1 ? "copy" : "copies"
  } will be written. ${existing} existing cop${existing === 1 ? "y is" : "ies are"} reported and will not be replaced.</span>`;
}

function syncButtonLabel() {
  const count = state.syncTargets.size;
  return `Copy to ${count} ${count === 1 ? "root" : "roots"}`;
}

function updateSyncPreview() {
  const preview = document.getElementById("sync-preview");
  if (preview) preview.innerHTML = syncPreview();
  const button = document.getElementById("sync-apply");
  if (button) {
    button.textContent = syncButtonLabel();
    button.disabled = state.syncTargets.size === 0;
  }
}

/* --------------------------------------------------------------------------
   Diff
   -------------------------------------------------------------------------- */

function lineDiff(left, right) {
  const A = String(left).replace(/\r\n/g, "\n").split("\n");
  const B = String(right).replace(/\r\n/g, "\n").split("\n");
  const n = A.length;
  const m = B.length;

  if (n * m > 300000) {
    let start = 0;
    while (start < n && start < m && A[start] === B[start]) start += 1;
    let endA = n - 1;
    let endB = m - 1;
    while (endA >= start && endB >= start && A[endA] === B[endB]) {
      endA -= 1;
      endB -= 1;
    }
    const rows = A.slice(0, start).map((line, index) => ({
      type: "same",
      left: line,
      right: B[index],
      leftNo: index + 1,
      rightNo: index + 1,
    }));
    A.slice(start, endA + 1).forEach((line, index) =>
      rows.push({ type: "del", left: line, right: "", leftNo: start + index + 1, rightNo: "" })
    );
    B.slice(start, endB + 1).forEach((line, index) =>
      rows.push({ type: "add", left: "", right: line, leftNo: "", rightNo: start + index + 1 })
    );
    for (let k = endA + 1, r = endB + 1; k < n; k += 1, r += 1) {
      rows.push({ type: "same", left: A[k], right: B[r], leftNo: k + 1, rightNo: r + 1 });
    }
    return rows;
  }

  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const rows = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) {
      rows.push({ type: "same", left: A[i], right: B[j], leftNo: i + 1, rightNo: j + 1 });
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      rows.push({ type: "del", left: A[i], right: "", leftNo: i + 1, rightNo: "" });
      i += 1;
    } else {
      rows.push({ type: "add", left: "", right: B[j], leftNo: "", rightNo: j + 1 });
      j += 1;
    }
  }
  while (i < n) {
    rows.push({ type: "del", left: A[i], right: "", leftNo: i + 1, rightNo: "" });
    i += 1;
  }
  while (j < m) {
    rows.push({ type: "add", left: "", right: B[j], leftNo: "", rightNo: j + 1 });
    j += 1;
  }
  return rows;
}

function renderDiffModal() {
  const skill = findSkill(state.modal.skill);
  if (!skill) return "";
  const leftBody = skill.body;
  const rightBody = variantFor(skill);
  const rows = lineDiff(leftBody, rightBody);
  const adds = rows.filter((row) => row.type === "add").length;
  const dels = rows.filter((row) => row.type === "del").length;
  const same = rows.filter((row) => row.type === "same").length;
  const leftLines = rows.filter((row) => row.type !== "add").length;
  const rightLines = rows.filter((row) => row.type !== "del").length;
  const mode = state.diffMode;

  return overlayShell({
    kicker: "Compare copies · line evidence",
    title: esc(skill.name),
    sub: `${esc(scopeLabel(state.modal.leftScope))} against ${esc(scopeLabel(state.modal.rightScope))}`,
    wide: true,
    body: `<div class="diff-toolbar">
        <span class="diff-stats"><span>${fmtNum(same)} unchanged</span><span class="add">+${fmtNum(adds)}</span><span class="del">−${fmtNum(dels)}</span></div>
        <span class="segmented" role="group" aria-label="Diff layout">
          <button type="button" data-action="diff-mode" data-mode="split" aria-pressed="${mode === "split"}" data-focus-key="diff:split">Split</button>
          <button type="button" data-action="diff-mode" data-mode="unified" aria-pressed="${mode === "unified"}" data-focus-key="diff:unified">Unified</button>
        </span>
      </div>
      <div class="diff ${mode === "unified" ? "diff-unified" : ""}">
        <div class="diff-head"><div>${esc(scopeLabel(state.modal.leftScope))} · ${fmtNum(leftLines)} lines</div><div>${esc(
      scopeLabel(state.modal.rightScope)
    )} · ${fmtNum(rightLines)} lines</div></div>
        <div class="diff-body">${renderDiffRows(rows, mode)}</div>
      </div>`,
    foot: `<span class="foot-note">The prototype does not choose a winner. The copy you sync is the decision.</span>
      <button class="button" type="button" data-action="close-overlay">Close</button>`,
  });
}

function renderDiffRows(rows, mode) {
  return rows
    .map((row) => {
      const isAdd = row.type === "add";
      const isDel = row.type === "del";
      const leftCell = mode === "unified" && isAdd ? row.right : row.left;
      const leftNo = mode === "unified" && isAdd ? row.rightNo : row.leftNo;
      const empty = mode === "split" && isAdd ? " is-empty" : "";
      return `<div class="diff-row${isAdd ? " is-add" : isDel ? " is-del" : ""}${empty}">
        <span class="ln left">${leftNo || ""}</span><span class="cell left">${esc(leftCell)}</span>
        <span class="ln right">${row.rightNo || ""}</span><span class="cell right">${esc(row.right)}</span>
      </div>`;
    })
    .join("");
}

/* --------------------------------------------------------------------------
   Help
   -------------------------------------------------------------------------- */

function renderHelpModal() {
  const groups = [
    [
      "Global",
      [
        ["Open the command palette", "Ctrl / ⌘ K"],
        ["Open the command palette", "/"],
        ["Open this sheet", "?"],
        ["New skill", "n"],
        ["Toggle theme", "t"],
        ["Close an overlay or return to the list", "Esc"],
      ],
    ],
    [
      "Catalogue",
      [
        ["Move down the list", "j"],
        ["Move up the list", "k"],
        ["Open the selected skill", "Enter"],
      ],
    ],
    [
      "Navigation",
      [
        ["Overview", "g then o"],
        ["Catalogue", "g then l"],
        ["Context", "g then c"],
        ["Quality", "g then q"],
        ["Profiles", "g then p"],
        ["Install", "g then i"],
        ["Recovery", "g then r"],
        ["Settings", "g then s"],
      ],
    ],
  ];

  return overlayShell({
    kicker: "Keyboard · the room at speed",
    title: "Shortcuts.",
    sub: "The catalogue, palette, dialogs, and tabs all work from the keyboard. Focus returns to where it started.",
    body: `<table class="shortcut-table">
      ${groups
        .map(
          ([group, shortcuts]) => `<tbody>
            <tr class="shortcut-group"><th colspan="2">${esc(group)}</th></tr>
            ${shortcuts
              .map(
                ([action, keys]) =>
                  `<tr><td>${esc(action)}</td><td class="shortcut-keys"><span class="kbd">${esc(keys)}</span></td></tr>`
              )
              .join("")}
          </tbody>`
        )
        .join("")}
    </table>
    <p class="hint" style="margin-top:12px">A shortcut never fires while you are typing in a field. <span class="kbd">Esc</span> always closes the top layer.</p>`,
    foot: `<button class="button" type="button" data-action="close-overlay">Close</button>`,
  });
}

/* --------------------------------------------------------------------------
   About
   -------------------------------------------------------------------------- */

function renderAboutModal() {
  return overlayShell({
    kicker: "About · folio-0.1",
    title: "A reading room, not a dashboard.",
    sub: "A frontend-only concept for the local control plane that manages AI coding-agent skill documents.",
    body: `<div class="about-block">
      <p><strong>The premise.</strong> A skill is a markdown file that gets concatenated into a model's context window. When two agents behave differently, the cause is often a document, a copy, or a broken link. Folio treats those documents as an archive to be read, compared, and measured, rather than as rows to be administered.</p>
      <p><strong>The composition.</strong> One index rail, one page, one focal answer. The catalogue is a list beside a document sheet, not a card grid. The context budget is a ruler with a labelled 100% mark, not a progress pill. The quality view is an evidence ledger, not a score.</p>
      <p><strong>The palette.</strong> A cool bone ground, one chartreuse signal for selection and focus, four status colours that always pair with a word and a glyph. Instrument Sans for the instrument, Newsreader for the document, JetBrains Mono for every identifier and number.</p>
      <p><strong>The constraints.</strong> No build step, no runtime dependency, no network request, no file access. Fonts are vendored. Every observation in this prototype is sample data generated in the page.</p>
      <p><strong>What is not claimed.</strong> This prototype does not read your skill files, write to them, or verify a registry package. It shows the interface and the state model a real implementation would expose.</p>
      <p><strong>Open the shortcuts</strong> to move without a pointer, or close this panel and start with the attention queue.</p>
    </div>`,
    foot: `<button class="button" type="button" data-action="help">${icon("keyboard")}Shortcuts</button><button class="button button-primary" type="button" data-action="close-overlay">Close</button>`,
  });
}

/* --------------------------------------------------------------------------
   Purge
   -------------------------------------------------------------------------- */

function renderPurgeModal() {
  return overlayShell({
    kicker: "Recovery · irreversible",
    title: "Purge the trash?",
    sub: `${F.TRASH.length} items will be removed permanently. There is no snapshot and no undo for this action.`,
    narrow: true,
    body: `<div class="note-panel" style="border-left-color:var(--err)"><strong>The prototype will clear its in-memory list.</strong> In a real store, this deletes the trash directory. Restore or export first if any item might be needed.</div>`,
    foot: `<button class="button" type="button" data-action="close-overlay">Cancel</button><button class="button button-danger" type="button" data-action="purge-confirm">${icon(
      "trash"
    )}Purge ${F.TRASH.length} items</button>`,
  });
}

/* --------------------------------------------------------------------------
   Finding
   -------------------------------------------------------------------------- */

function renderFindingModal() {
  const finding = F.QUALITY.find((item) => item.id === state.modal.id);
  if (!finding) return "";
  return overlayShell({
    kicker: `${titleCase(finding.category)} · ${finding.scope}`,
    title: esc(finding.title),
    sub: "Read-only evidence. The finding names the scope and the files it came from.",
    body: `<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">${severityBadge(finding.severity)}<span class="finding-count">${
      finding.count
    } ${finding.count === 1 ? "instance" : "instances"}</span></div>
      <dl class="detail-grid">
        <dt>Evidence</dt><dd>${esc(finding.evidence)}</dd>
        <dt>Why it matters</dt><dd>${esc(finding.detail)}</dd>
        <dt>Scope</dt><dd><code>${esc(finding.scope)}</code></dd>
        <dt>Affected skills</dt><dd>${finding.skills.length ? finding.skills.map((name) => esc(name)).join(", ") : "No single skill. This is a root-level observation."}</dd>
      </dl>
      <p class="hint" style="margin-top:12px">Advisory evidence is not enforcement. A malformed document is a fact; a risk finding is a lead.</p>`,
    foot: `<button class="button" type="button" data-action="close-overlay">Close</button>${
      finding.skills.length
        ? `<button class="button button-primary" type="button" data-action="finding-skill" data-skill="${esc(finding.skills[0])}">Open ${esc(
            finding.skills[0]
          )}</button>`
        : ""
    }`,
  });
}

/* --------------------------------------------------------------------------
   Rollback
   -------------------------------------------------------------------------- */

function renderRollbackModal() {
  const snapshot = F.SNAPSHOTS.find((item) => item.id === state.modal.id);
  if (!snapshot) return "";
  return overlayShell({
    kicker: "Recovery · snapshot review",
    title: "Create a rollback review.",
    sub: `${esc(snapshot.name)} on ${esc(scopeLabel(snapshot.scope))}, captured ${fmtDate(snapshot.at, {
      day: "numeric",
      month: "short",
      year: "numeric",
    })}.`,
    body: `<dl class="detail-grid">
        <dt>Snapshot</dt><dd><code>${esc(snapshot.hash)}</code></dd>
        <dt>Files</dt><dd>${snapshot.files}</dd>
        <dt>Source</dt><dd>${esc(snapshot.action)}</dd>
        <dt>State</dt><dd>${esc(snapshot.state)}</dd>
      </dl>
      <div class="note-panel" style="margin-top:14px"><strong>A rollback is a new review.</strong> It previews the candidate tree, validates it, and requires a separate approval. The prototype will not apply it.</div>`,
    foot: `<button class="button" type="button" data-action="close-overlay">Cancel</button><button class="button button-primary" type="button" data-action="rollback-confirm">${icon(
      "undo"
    )}Create review</button>`,
  });
}

/* --------------------------------------------------------------------------
   Profile plan
   -------------------------------------------------------------------------- */

function copyCount(count, singular, plural) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function renderProfilePlanModal() {
  const profile = selectedProfile();
  const counts = { observed: 0, disabled: 0, divergent: 0, missing: 0 };
  profile.members.forEach((member) => {
    counts[member.state] = (counts[member.state] || 0) + 1;
  });
  return overlayShell({
    kicker: "Profiles · enable plan",
    title: "Preview the enable plan.",
    sub: `${esc(profile.name)} on ${profile.targets.map((id) => esc(scopeLabel(id))).join(", ")}.`,
    body: `<div class="profile-counts" style="margin-top:0">
        ${[
          ["Observed", counts.observed],
          ["Disabled", counts.disabled],
          ["Divergent", counts.divergent],
          ["Missing", counts.missing],
        ]
          .map(([label, value]) => `<div class="profile-count"><span class="label">${label}</span><span class="value">${value}</span></div>`)
          .join("")}
      </div>
      <ul class="issue-list">
        <li>${mark("active")}<span><span class="issue-title">${copyCount(counts.observed, "observed copy", "observed copies")}</span><span class="issue-message">Already active. No state change.</span></span><span class="issue-key">no-op</span></li>
        <li>${mark("disabled")}<span><span class="issue-title">${copyCount(counts.disabled, "disabled copy", "disabled copies")}</span><span class="issue-message">Renamed back to SKILL.md on the target root.</span></span><span class="issue-key">enable</span></li>
        <li>${mark("divergent")}<span><span class="issue-title">${copyCount(counts.divergent, "divergent copy", "divergent copies")}</span><span class="issue-message">Reported, left unchanged. The profile does not choose a winner.</span></span><span class="issue-key">skip</span></li>
        <li>${missingMark()}<span><span class="issue-title">${copyCount(counts.missing, "missing member", "missing members")}</span><span class="issue-message">Not installed. A profile is a plan, not a package manager.</span></span><span class="issue-key">skip</span></li>
      </ul>
      <p class="hint" style="margin-top:10px">The prototype applies the plan to memory and reports the same skip rules.</p>`,
    foot: `<button class="button" type="button" data-action="close-overlay">Cancel</button><button class="button button-primary" type="button" data-action="profile-apply" ${
      counts.disabled === 0 ? "disabled" : ""
    }>${icon("play")}${counts.disabled === 0 ? "No changes to apply" : "Apply the plan"}</button>`,
  });
}
