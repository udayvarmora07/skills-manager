/* ==========================================================================
   Folio views: shell, overview, catalogue, document room, context
   ========================================================================== */

const NAV_GROUPS = [
  {
    label: "Room",
    items: [
      { view: "overview", label: "Overview", icon: "home" },
      { view: "library", label: "Catalogue", icon: "book", count: () => skills.length },
      { view: "context", label: "Context", icon: "gauge" },
    ],
  },
  {
    label: "Operate",
    items: [
      { view: "quality", label: "Quality", icon: "checkCircle", count: () => F.QUALITY.length },
      { view: "profiles", label: "Profiles", icon: "users", count: () => F.PROFILES.length },
      { view: "install", label: "Install", icon: "download" },
      { view: "recovery", label: "Recovery", icon: "undo", count: () => F.TRASH.length },
    ],
  },
  {
    label: "Setup",
    items: [{ view: "settings", label: "Settings", icon: "settings" }],
  },
];

function renderRail() {
  const nav = $("#rail-nav");
  if (!nav) return;
  nav.innerHTML = NAV_GROUPS.map(
    (group) => `<div class="rail-group">
      <div class="rail-group-label">${esc(group.label)}</div>
      ${group.items
        .map((item) => {
          const count = item.count ? item.count() : null;
          return `<button class="rail-link" type="button" data-go="${item.view}" data-focus-key="rail:${item.view}" ${
            state.view === item.view ? 'aria-current="page"' : ""
          }>
            ${icon(item.icon)}
            <span>${esc(item.label)}</span>
            ${count !== null ? `<span class="count">${fmtNum(count)}</span>` : ""}
          </button>`;
        })
        .join("")}
    </div>`
  ).join("");

  const scopes = $("#rail-scopes");
  if (!scopes) return;
  const maxTokens = Math.max(...F.SCOPES.map((scope) => scope.tokens));
  scopes.innerHTML = `<div class="rail-separator"></div>
    <div class="rail-scopes-title"><span>Roots</span><button type="button" data-action="all-roots">All roots</button></div>
    ${F.SCOPES.map((scope) => {
      return `<button class="scope-link" type="button" data-action="scope-to-library" data-scope="${scope.id}" data-focus-key="rail-scope:${scope.id}" aria-pressed="${
        state.scope === scope.id
      }" title="${esc(scope.label)} · ${esc(scope.path)}">
        <span class="scope-name">${esc(scope.label)}</span>
        <span class="scope-count">${fmtNum(scope.count)}</span>
        <span class="scope-track" aria-hidden="true"><i style="transform:scaleX(${(scope.tokens / maxTokens).toFixed(3)})"></i></span>
      </button>`;
    }).join("")}`;

  const foot = $("#rail-foot");
  if (foot) {
    foot.innerHTML = `<strong>${fmtNum(F.TOTAL_INSTANCES)} observed instances</strong>
      ${fmtNum(F.TOTAL_TOKENS)} tokens · ${fmtNum(skills.length)} logical skills<br>
      sample inventory · no backend`;
  }
}

function renderStage() {
  const main = $("#main");
  const mount = $("#stage");
  if (!main || !mount) return;
  const fixed = state.view === "library" && (state.demo === "live" || state.demo === "loading");
  main.className = fixed ? "stage stage-fixed" : "stage";
  const demoLabels = { empty: "Empty inventory", loading: "Loading", error: "Read error" };
  const preview = demoLabels[state.demo]
    ? `<div class="preview-bar" role="status">
        <span class="preview-icon">${icon("eye")}</span>
        <span class="preview-copy"><strong>Preview state: ${demoLabels[state.demo]}.</strong> The sample data stays in memory behind this view.</span>
        <button class="button button-sm" type="button" data-demo="live">${icon("play")}Return to live</button>
      </div>`
    : "";
  mount.innerHTML = preview + renderView();

  if (state.scrollSelected) {
    const row = $('.skill-row[aria-current="true"]');
    if (row) row.scrollIntoView({ block: "nearest" });
    state.scrollSelected = false;
  }

  if (state.focusKey) {
    const target = document.querySelector(`[data-focus-key="${CSS.escape(state.focusKey)}"]`);
    state.focusKey = "";
    if (target) target.focus({ preventScroll: true });
  }
}

function renderStatus() {
  const bar = $("#statusbar");
  if (!bar) return;
  bar.innerHTML = `<div class="status-left">
      <span><b>Local only</b></span>
      <span>Files are the source of truth</span>
      <span>${fmtNum(skills.length)} logical skills</span>
      <span>${fmtTokens(F.TOTAL_TOKENS)} tokens</span>
    </div>
    <div class="status-right">
      <span>Sample inventory · no backend</span>
      <span><kbd>?</kbd> shortcuts</span>
    </div>`;
}

function renderView() {
  switch (state.view) {
    case "library":
      return renderLibrary();
    case "context":
      return renderContext();
    case "quality":
      return renderQuality();
    case "profiles":
      return renderProfiles();
    case "install":
      return renderInstall();
    case "recovery":
      return renderRecovery();
    case "settings":
      return renderSettings();
    default:
      return renderOverview();
  }
}

function pageHead(options) {
  return `<header class="page-head${options.compact ? " page-head-compact" : ""}">
    <div class="page-kicker"><span class="kicker-mark" aria-hidden="true"></span>${esc(options.kicker)}</div>
    <div class="page-head-row">
      <h1>${options.title}</h1>
      <div class="page-actions">${options.actions || ""}</div>
    </div>
    ${options.lede ? `<p class="page-lede">${options.lede}</p>` : ""}
  </header>`;
}

/* --------------------------------------------------------------------------
   Overview
   -------------------------------------------------------------------------- */

function renderOverview() {
  if (state.demo === "loading") return renderLoadingView("overview");
  if (state.demo === "error") {
    return renderErrorView(
      "Overview",
      "The inventory could not be read.",
      "The scan stopped before the first root. The last good scan was 14 seconds ago. Nothing was repaired.",
      "overview"
    );
  }
  if (state.demo === "empty") return renderFirstRun();

  const pct = pctOfWindow(totalTokens());
  const headroom = windowSize() - totalTokens();
  const largest = largestRoot();
  const counts = statusCounts();

  const attention = [
    {
      name: ".system",
      meta: "Parse failure · Codex",
      copy: "The document cannot be parsed, and the directory name fails the skill name rule. It is listed, not repaired.",
    },
    {
      name: "accessibility-compliance",
      meta: "Divergence · Gemini",
      copy: "Two copies disagree on the keyboard review. 14 lines differ from the canonical document.",
    },
    {
      name: "add-task",
      meta: "Containment · Claude Code",
      copy: "One copy is a symlink to a path outside the Claude root. The loader reports it and does not follow it.",
    },
  ];

  const attentionHtml = attention
    .map((item) => {
      const skill = findSkill(item.name);
      if (!skill) return "";
      return `<button class="brief-item" type="button" data-skill="${esc(skill.name)}" data-focus-key="brief:${esc(skill.name)}" aria-label="Open ${esc(
        skill.name
      )}, ${esc(stateMeta(skill.state).label)}">
        ${mark(skill.state)}
        <span>
          <span class="brief-meta"><span>${esc(item.meta)}</span><span>${skill.copies} ${skill.copies === 1 ? "copy" : "copies"}</span></span>
          <span class="brief-title">${esc(skill.name)}</span>
          <span class="brief-copy">${esc(item.copy)}</span>
        </span>
        <span class="brief-arrow" aria-hidden="true">${icon("arrowUpRight")}</span>
      </button>`;
    })
    .join("");

  return `<div class="page">
    ${pageHead({
      kicker: `Sunday, 25 October 2026 · scanned ${fmtRelative(state.scanAt)}`,
      title: "Three things need a look.",
      lede: `Your agents read <strong>${fmtNum(F.TOTAL_INSTANCES)} skill instances</strong> from ${F.SCOPES.length} roots. The library holds <strong>${fmtNum(
        skills.length
      )} logical skills</strong>. <strong>${fmtNum(counts.attention)}</strong> items need attention; these three are the most consequential.`,
      actions: `<button class="button" type="button" data-action="refresh-scan" data-focus-key="refresh-scan">${icon("refresh")}Rescan</button>
        <button class="button" type="button" data-go="quality">${icon("checkCircle")}Open evidence</button>`,
    })}

    <div class="overview-grid">
      <section aria-labelledby="attention-title">
        <div class="section-head"><h2 id="attention-title">Attention queue</h2><button class="quiet-link" type="button" data-action="attention-all">All ${fmtNum(counts.attention)}</button></div>
        <div class="brief-list">${attentionHtml}</div>
        <p class="hint" style="margin-top:10px">Ordered by severity: a parse failure, then content that disagrees, then a link the tool refuses to follow.</p>
      </section>

      <aside class="budget-card" aria-labelledby="budget-title">
        <div class="budget-card-top">
          <div>
            <div class="budget-kicker" id="budget-title">Context budget · ${esc(windowDef().label)} ${esc(windowDef().note)}</div>
            <div class="budget-number">${pct.toFixed(1)}<small>%</small></div>
          </div>
          <button class="button button-sm button-ghost" type="button" data-go="context">Open budget</button>
        </div>
        <p class="budget-sub">${fmtNum(totalTokens())} tokens across ${F.SCOPES.length} roots. ${
          headroom >= 0 ? `${fmtNum(headroom)} tokens remain before the 100% mark.` : `${fmtNum(-headroom)} tokens are over the window.`
        }</p>
        ${ruler(pct, { label: `Context budget: ${pct.toFixed(1)} percent of a ${windowDef().label} window` })}
        <div class="budget-foot">
          <span>Largest root <strong>${esc(largest.label)} ${fmtTokens(largest.tokens)}</strong></span>
          <span>${fmtNum(F.TOTAL_INSTANCES)} instances</span>
        </div>
      </aside>
    </div>

    <section class="section" aria-labelledby="roots-title">
      <div class="section-head">
        <h2 id="roots-title">Where the documents live</h2>
        <span class="section-meta">${F.SCOPES.length} roots · ${fmtNum(F.TOTAL_INSTANCES)} instances</span>
      </div>
      <div class="state-legend" style="margin-bottom:8px">
        ${["active", "disabled", "divergent", "malformed", "linked"]
          .map((key) => `<span>${mark(key)} ${esc(F.STATE_META[key].label)}</span>`)
          .join("")}
      </div>
      <div class="table-wrap">
        <table class="state-table">
          <thead><tr><th>Root</th><th class="num">Instances</th><th>Context</th><th>State composition</th><th></th></tr></thead>
          <tbody>
            ${F.SCOPES.map((scope) => {
              const max = Math.max(...F.SCOPES.map((item) => item.tokens));
              return `<tr data-action="scope-to-library" data-scope="${scope.id}" title="Open ${esc(scope.label)} in the catalogue">
                <td>
                  <button class="text-button root-name" type="button" data-action="scope-to-library" data-scope="${scope.id}">${esc(scope.label)}</button>
                  <span class="root-path">${esc(scope.path)}</span>
                </td>
                <td class="num">${fmtNum(scope.count)}</td>
                <td>
                  <span class="scope-track" style="margin-top:0" aria-hidden="true"><i style="transform:scaleX(${(scope.tokens / max).toFixed(3)})"></i></span>
                  <span class="mono" style="display:block;margin-top:2px;font-size:8.5px;color:var(--ink-3)">${fmtTokens(scope.tokens)}</span>
                </td>
                <td>${stateBar(scope)}</td>
                <td class="num" aria-hidden="true">${icon("chevronRight")}</td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
    </section>

    <div class="overview-notes">
      <section aria-labelledby="recent-title">
        <div class="section-head"><h2 id="recent-title">Recently touched</h2><button class="section-link" type="button" data-go="recovery">Open recovery</button></div>
        <ul class="recent-list">
          ${F.RECENT.map((entry) => {
            const skill = findSkill(entry.name);
            return `<li>
              <span class="recent-mark" aria-hidden="true">${icon("clock")}</span>
              <span><strong>${esc(entry.name)}</strong><span>${esc(entry.action)}</span></span>
              <time datetime="${entry.at}">${fmtRelative(entry.at)}</time>
            </li>`;
          }).join("")}
        </ul>
      </section>

      <section aria-labelledby="knows-title">
        <div class="section-head"><h2 id="knows-title">What this room knows</h2><span class="section-meta">read-only</span></div>
        <div class="note-panel">
          <strong>Observed, not inferred.</strong>
          The room reports parser failures, divergent content, disabled copies, and links it refuses to follow. It does not produce a single quality score, elect a winner between consumers, or claim model usage.
        </div>
        <div class="note-panel" style="margin-top:10px">
          <strong>Files are the source of truth.</strong>
          The index is a rebuildable cache. Every row names the physical path it observed, and a read never creates or repairs a directory.
          <div style="margin-top:8px"><button class="text-button" type="button" data-go="quality">Open the evidence ledger</button></div>
        </div>
      </section>
    </div>
  </div>`;
}

/* --------------------------------------------------------------------------
   Catalogue
   -------------------------------------------------------------------------- */

function renderLibrary() {
  if (state.demo === "loading") return renderLoadingView("library");
  if (state.demo === "error") {
    return renderErrorView(
      "Catalogue",
      "The catalogue could not be read.",
      "The scan returned no rows. The last good scan is still visible in the status bar. Nothing was changed.",
      "library"
    );
  }
  if (state.demo === "empty") return renderFirstRun();

  const visible = filteredSkills();
  const selected = selectedSkill() || visible[0] || null;
  const counts = statusCounts();

  return `<div class="page library-view">
    ${pageHead({
      kicker: `Catalogue · ${fmtNum(F.TOTAL_INSTANCES)} observed instances`,
      title: "The catalogue.",
      lede: `${fmtNum(skills.length)} logical skills across ${F.SCOPES.length} roots. One name can be several files; the document room keeps every physical copy addressable.`,
      actions: `<button class="button" type="button" data-action="add-folder">${icon("folder")}Add folder</button>
        <button class="button" type="button" data-action="import">${icon("upload")}Import</button>`,
      compact: true,
    })}

    <div class="library-bar" role="search">
      <span class="segmented" role="group" aria-label="Filter by state">
        ${[
          ["all", "All", counts.all],
          ["active", "Active", counts.active],
          ["attention", "Needs attention", counts.attention],
          ["disabled", "Has disabled", counts.disabled],
        ]
          .map(
            ([value, label, count]) =>
              `<button type="button" data-status="${value}" data-focus-key="status:${value}" aria-pressed="${state.status === value}">${esc(
                label
              )}<span class="seg-count">${fmtNum(count)}</span></button>`
          )
          .join("")}
      </span>

      <label class="library-search">
        <span class="sr-only">Search the catalogue</span>
        ${icon("search")}
        <input type="search" value="${esc(state.query)}" placeholder="Search names, paths, descriptions" autocomplete="off" spellcheck="false" data-input="library-query" data-focus-key="library-query">
      </label>

      <select class="select" data-change="scope" data-focus-key="scope-select" aria-label="Filter by root" style="width:auto;height:29px;padding:0 26px 0 8px;font-size:11px">
        <option value="all"${state.scope === "all" ? " selected" : ""}>All roots</option>
        ${F.SCOPES.map((scope) => `<option value="${scope.id}"${state.scope === scope.id ? " selected" : ""}>${esc(scope.label)}</option>`).join("")}
      </select>

      <select class="select" data-change="sort" data-focus-key="sort-select" aria-label="Sort the catalogue" style="width:auto;height:29px;padding:0 26px 0 8px;font-size:11px">
        <option value="name"${state.sort === "name" ? " selected" : ""}>Name A-Z</option>
        <option value="updated"${state.sort === "updated" ? " selected" : ""}>Recently changed</option>
        <option value="largest"${state.sort === "largest" ? " selected" : ""}>Largest first</option>
        <option value="copies"${state.sort === "copies" ? " selected" : ""}>Most copies</option>
      </select>

      ${state.query || state.status !== "all" || state.scope !== "all" ? `<button class="button button-sm button-ghost" type="button" data-action="clear-filters">${icon("close")}Clear</button>` : ""}
      <span class="spacer"></span>
      <span class="library-count" id="library-count">${fmtNum(visible.length)} of ${fmtNum(skills.length)}</span>
    </div>

    <div class="library-split">
      <div class="skill-list" id="skill-list" aria-label="Skills">
        ${renderSkillListInner(visible, selected)}
      </div>
      ${selected ? renderDocumentRoom(selected) : renderLibraryEmpty()}
    </div>
  </div>`;
}

function renderSkillListInner(visible, selected) {
  const rows = visible.slice(0, state.limit);
  const foot =
    visible.length > rows.length
      ? `<div class="skill-list-foot">Showing ${fmtNum(rows.length)} of ${fmtNum(visible.length)}. Narrow the search or load more.<br><button class="button button-sm" type="button" data-action="load-more">${icon("chevronDown")}Show 60 more</button></div>`
      : `<div class="skill-list-foot">${fmtNum(visible.length)} skill${visible.length === 1 ? "" : "s"} in this view. Every row is a logical name, not a file.</div>`;

  if (!visible.length) {
    return `<div class="skill-list-head"><span>Skill</span><span>Tokens</span></div>
      <div class="skill-list-foot" style="padding-top:22px">No skills match this view. Clear the filters or try a broader search.</div>`;
  }

  return `<div class="skill-list-head"><span>Skill</span><span>Tokens</span></div>
    ${rows.map((skill) => renderSkillRow(skill, selected)).join("")}
    ${foot}`;
}

function renderSkillRow(skill, selected) {
  const meta = stateMeta(skill.state);
  const chips = skill.instances
    .slice(0, 2)
    .map(
      (instance) =>
        `<span class="chip" title="${esc(scopeLabel(instance.scope))} · ${esc(instance.path)}">${esc(scopeShort(instance.scope))} ${markSvg(
          instance.state
        )}</span>`
    )
    .join("");
  const more = skill.instances.length > 2 ? `<span class="chip chip-mono">+${skill.instances.length - 2}</span>` : "";
  const isSelected = selected && selected.name === skill.name;

  return `<button class="skill-row" type="button" data-skill="${esc(skill.name)}" data-focus-key="skill:${esc(skill.name)}" aria-current="${
    isSelected ? "true" : "false"
  }" aria-label="${esc(skill.name)}, ${skill.copies} ${skill.copies === 1 ? "copy" : "copies"}, ${esc(meta.label)}. ${esc(skill.description)}">
    ${mark(skill.state)}
    <span class="skill-main">
      <span class="skill-name-line"><span class="skill-name">${esc(skill.name)}</span><span class="skill-copies">${skill.copies} ${
        skill.copies === 1 ? "copy" : "copies"
      }</span></span>
      <span class="skill-desc">${esc(skill.description)}</span>
      <span class="skill-meta-line">${stateChip(skill.state)}${chips}${more}</span>
    </span>
    <span class="skill-tokens">${fmtTokens(skill.tokens)}<br>tokens</span>
  </button>`;
}

function renderLibraryEmpty() {
  return `<div class="document-room"><div class="empty" style="border-top:0">
    <div class="empty-mark">${icon("search")}</div>
    <h2>No skills match this view.</h2>
    <p>The catalogue still holds ${fmtNum(skills.length)} logical skills. Clear the state filter, choose another root, or search for a path.</p>
    <div class="empty-actions"><button class="button" type="button" data-action="clear-filters">${icon("refresh")}Clear filters</button></div>
  </div></div>`;
}

function renderDocumentRoom(skill) {
  if (!skill) return "";
  const tabs = [
    ["document", "Document", null],
    ["copies", "Copies", skill.copies],
    ["validation", "Validation", skill.validation.issues.length || null],
    ["history", "History", skill.history.length || null],
  ];
  const enabled = skill.state === "disabled";
  const addressable = skill.addressable !== false;

  return `<article class="document-room" aria-label="${esc(skill.name)} document room">
    <div class="doc-top">
      <div class="doc-breadcrumb">
        <button class="button button-sm button-ghost mobile-back" type="button" data-action="mobile-back" data-focus-key="doc-back">${icon("arrowLeft")}Catalogue</button>
        <button class="doc-crumb-link" type="button" data-go="library">Catalogue</button>
        <span class="doc-crumb-sep" aria-hidden="true">/</span>
        <span class="doc-crumb-name">${esc(skill.name)}</span>
      </div>
    </div>

    <div class="doc-title-row">
      <div class="doc-heading">
        <h2 class="doc-title">${esc(skill.name)}</h2>
        <p class="doc-sub">${esc(skill.description)}</p>
      </div>
      <div class="doc-actions">
        ${stateBadge(skill.state, false)}
        <button class="button button-sm" type="button" data-action="edit" ${addressable ? "" : "disabled"}>${icon("file")}Edit</button>
        <button class="button button-sm" type="button" data-action="toggle" data-focus-key="doc-toggle" ${addressable ? "" : "disabled"}>${icon(
          enabled ? "play" : "pause"
        )}${enabled ? "Enable" : "Disable"}</button>
        <button class="button button-sm" type="button" data-action="sync" ${addressable ? "" : "disabled"}>${icon("layers")}Sync</button>
      </div>
    </div>

    <div class="doc-tabs" role="tablist" aria-label="Document views">
      ${tabs
        .map(
          ([key, label, count]) =>
            `<button class="doc-tab" type="button" role="tab" aria-selected="${state.detailTab === key}" data-tab="${key}" data-focus-key="tab:${key}">${esc(
              label
            )}${count !== null ? `<span class="count">${fmtNum(count)}</span>` : ""}</button>`
        )
        .join("")}
    </div>

    <div class="doc-body" role="tabpanel">
      ${
        state.detailTab === "copies"
          ? renderCopiesTab(skill)
          : state.detailTab === "validation"
          ? renderValidationTab(skill)
          : state.detailTab === "history"
          ? renderHistoryTab(skill)
          : renderDocumentTab(skill)
      }
    </div>
  </article>`;
}

function renderDocumentTab(skill) {
  if (skill.malformed) {
    const message = skill.validation.issues[0] ? skill.validation.issues[0].message : "The document cannot be parsed.";
    return `<div class="validation-banner is-err">
        ${mark("malformed")}
        <div><h3>This document cannot be parsed.</h3><p>${esc(message)} The raw bytes are shown below. Nothing was repaired, and the directory cannot be opened by name.</p></div>
      </div>
      <div class="doc-sheet" style="margin-top:12px"><pre class="raw-excerpt">${esc(skill.body)}</pre></div>`;
  }

  const primary = skill.instances.find((instance) => instance.state === "active") || skill.instances[0] || {};
  const body = skill.body.replace(/^#\s+.*\n+/, "");

  const notes = [
    ["Observed state", stateBadge(skill.state, true)],
    ["Copies", `${skill.copies} physical ${skill.copies === 1 ? "file" : "files"}`],
    ["Tokens", `<span class="mono">${fmtNum(skill.tokens)}</span>`],
    ["Modified", fmtDate(skill.updated, { day: "numeric", month: "short", year: "numeric" })],
    ["Content hash", `<code>${esc(String(primary.hash || "").slice(0, 28))}…</code>`],
    ["Path", `<code>${esc(primary.path || "")}</code><br><button class="note-action" type="button" data-action="copy-path" data-path="${esc(
      primary.path || ""
    )}">Copy path</button>`],
  ]
    .map(([label, value]) => `<div class="margin-note"><dt>${esc(label)}</dt><dd>${value}</dd></div>`)
    .join("");

  return `<div class="doc-sheet">
    <dl class="frontmatter">
      <dt>name</dt><dd>${esc(skill.name)}</dd>
      <dt>description</dt><dd>${esc(skill.description)}</dd>
      <dt>category</dt><dd>${esc(skill.category)}</dd>
      <dt>version</dt><dd>${esc(skill.version)}</dd>
      <dt>license</dt><dd>${esc(skill.license)}</dd>
      <dt>allowed tools</dt><dd>${esc(skill.allowedTools)}</dd>
    </dl>
    <div class="doc-grid">
      <div class="doc-prose">${renderMarkdown(body)}</div>
      <dl class="margin-notes">${notes}</dl>
    </div>
  </div>`;
}

function renderCopiesTab(skill) {
  const canonical = skill.instances.find((instance) => instance.state === "active") || skill.instances[0];
  const divergent = skill.instances.filter((instance) => instance.state === "divergent");

  return `${
    divergent.length
      ? `<div class="copy-note">${mark("divergent")}<span>${divergent.length} ${
          divergent.length === 1 ? "copy differs" : "copies differ"
        } from the canonical document. The compare view shows the lines that changed.</span></div>`
      : ""
  }
  <div class="table-wrap">
    <table class="copy-table">
      <thead><tr><th>Root</th><th>Path</th><th>State</th><th class="num">Tokens</th><th>Modified</th><th></th></tr></thead>
      <tbody>
        ${skill.instances
          .map(
            (instance) => `<tr class="${instance.state === "divergent" ? "is-divergent" : ""}">
              <td class="scope-cell">${esc(scopeLabel(instance.scope))}${
                canonical && instance.scope === canonical.scope ? '<span class="chip chip-mono" style="margin-left:5px">canonical</span>' : ""
              }</td>
              <td class="path-cell" title="${esc(instance.path)}">${esc(instance.path)}</td>
              <td>${stateBadge(instance.state)}</td>
              <td class="num">${fmtNum(instance.tokens)}</td>
              <td class="num" style="text-align:left">${fmtDate(instance.modified)}</td>
              <td><button class="button button-sm" type="button" data-action="compare" data-scope="${instance.scope}" ${
                instance.state === "divergent" ? "" : "disabled"
              }>${icon("diff")}Compare</button></td>
            </tr>`
          )
          .join("")}
      </tbody>
    </table>
  </div>
  <p class="hint" style="margin-top:10px">${skill.copies} observed ${
    skill.copies === 1 ? "copy" : "copies"
  }. The catalogue groups by name; every physical path stays addressable. Divergence is reported, never resolved silently.</p>`;
}

function renderValidationTab(skill) {
  const valid = skill.validation.valid;
  const issues = skill.validation.issues || [];
  return `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px">
      <p class="hint" style="margin:0">Local parser, name rule, and authoring guidance. No score.</p>
      <button class="button button-sm" type="button" data-action="validate" data-focus-key="validate">${icon("checkCircle")}Run validation</button>
    </div>
    <div class="validation-banner ${valid ? "" : "is-err"}">
      ${mark(valid ? "active" : "malformed")}
      <div><h3>${valid ? "Valid against the local rules." : "Validation failed."}</h3>
        <p>${valid ? `${issues.length} warning${issues.length === 1 ? "" : "s"}. The document parses, the name matches its directory, and the required fields are present.` : `${issues.filter((issue) => issue.level === "error").length} error(s). A malformed document is reported, never repaired here.`}</p>
      </div>
    </div>
    ${issues.length
      ? `<ul class="issue-list">${issues
          .map(
            (issue) => `<li>
              ${severityMark(issue.level === "error" ? "error" : issue.level === "warn" ? "warn" : "info")}
              <span><span class="issue-title">${esc(issue.key)}</span><span class="issue-message">${esc(issue.message)}</span></span>
              <span class="issue-key">${esc(issue.level)}</span>
            </li>`
          )
          .join("")}</ul>`
      : `<p class="hint" style="margin-top:14px">No findings. Validation checks structure and naming; it does not measure usefulness or safety.</p>`}`;
}

function renderHistoryTab(skill) {
  if (!skill.history.length) {
    return `<div class="empty" style="border-top:0;padding:34px 16px"><div class="empty-mark">${icon("clock")}</div><h2>No history yet.</h2><p>The prototype records actions in memory only. A real store would keep the file path and the timestamp.</p></div>`;
  }
  return `<p class="hint" style="margin:0 0 12px">Local history. A snapshot is applied through a review, never directly.</p>
    <ul class="timeline">
      ${skill.history
        .map(
          (entry) => `<li>
            <span class="tl-action">${esc(entry.action)}</span>
            <p class="tl-note">${esc(entry.note || "")}</p>
            <time datetime="${entry.at}">${fmtDate(entry.at, { day: "numeric", month: "short", year: "numeric" })} · ${fmtRelative(entry.at)}</time>
          </li>`
        )
        .join("")}
    </ul>`;
}

/* --------------------------------------------------------------------------
   Markdown
   -------------------------------------------------------------------------- */

function inlineMarkdown(text) {
  let value = esc(text);
  const codes = [];
  value = value.replace(/`([^`]+)`/g, (_, code) => {
    codes.push(code);
    return `\u0001${codes.length - 1}\u0001`;
  });
  value = value.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  value = value.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  value = value.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  value = value.replace(/\u0001(\d+)\u0001/g, (_, index) => `<code>${codes[Number(index)]}</code>`);
  return value;
}

function tableCells(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderMarkdown(markdown) {
  const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let index = 0;
  let paragraph = [];

  const flush = () => {
    if (paragraph.length) {
      out.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
      paragraph = [];
    }
  };

  while (index < lines.length) {
    const line = lines[index];

    if (/^```/.test(line)) {
      flush();
      const language = line.slice(3).trim();
      const code = [];
      index += 1;
      while (index < lines.length && !/^```/.test(lines[index])) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1;
      out.push(`<pre><code${language ? ` class="language-${esc(language)}"` : ""}>${esc(code.join("\n"))}</code></pre>`);
      continue;
    }

    if (/^#{1,4}\s+/.test(line)) {
      flush();
      const match = line.match(/^(#{1,4})\s+(.*)$/);
      out.push(`<h${match[1].length}>${inlineMarkdown(match[2])}</h${match[1].length}>`);
      index += 1;
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      flush();
      const items = [];
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
        items.push(`<li>${inlineMarkdown(lines[index].replace(/^\s*[-*]\s+/, ""))}</li>`);
        index += 1;
      }
      out.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      flush();
      const items = [];
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(`<li>${inlineMarkdown(lines[index].replace(/^\s*\d+\.\s+/, ""))}</li>`);
        index += 1;
      }
      out.push(`<ol>${items.join("")}</ol>`);
      continue;
    }

    if (/^>\s?/.test(line)) {
      flush();
      const quote = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^>\s?/, ""));
        index += 1;
      }
      out.push(`<blockquote>${renderMarkdown(quote.join("\n"))}</blockquote>`);
      continue;
    }

    if (/^\|/.test(line) && index + 1 < lines.length && /^\|?[\s:|-]+\|?\s*$/.test(lines[index + 1])) {
      flush();
      const header = tableCells(line);
      index += 2;
      const rows = [];
      while (index < lines.length && /^\|/.test(lines[index])) {
        rows.push(tableCells(lines[index]));
        index += 1;
      }
      out.push(`<table><thead><tr>${header.map((cell) => `<th>${inlineMarkdown(cell)}</th>`).join("")}</tr></thead><tbody>${rows
        .map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkdown(cell)}</td>`).join("")}</tr>`)
        .join("")}</tbody></table>`);
      continue;
    }

    if (/^---+$/.test(line.trim())) {
      flush();
      out.push("<hr>");
      index += 1;
      continue;
    }

    if (!line.trim()) {
      flush();
      index += 1;
      continue;
    }

    paragraph.push(line.trim());
    index += 1;
  }

  flush();
  return out.join("\n");
}

/* --------------------------------------------------------------------------
   Context
   -------------------------------------------------------------------------- */

function renderContext() {
  const window = windowDef();
  const total = totalTokens();
  const pct = pctOfWindow(total);
  const headroom = window.size - total;
  const largest = largestRoot();
  const largestSkills = [...skills].sort((a, b) => b.tokens - a.tokens).slice(0, 7);
  const maxSkillTokens = largestSkills[0] ? largestSkills[0].tokens : 1;

  return `<div class="page">
    ${pageHead({
      kicker: "Context · observed estimate",
      title: "What fits in a window.",
      lede: `One skill is not one file. These are the tokens your agents actually read, measured from the documents on disk and compared with the window you choose.`,
      actions: `<button class="button" type="button" data-go="quality">${icon("checkCircle")}Open evidence</button>`,
    })}

    <div class="window-switch" role="group" aria-label="Context window">
      ${F.WINDOWS.map(
        (item) =>
          `<button class="window-chip" type="button" data-window="${item.id}" data-focus-key="window:${item.id}" aria-pressed="${state.window === item.id}">
            ${esc(item.label)}<span class="wc-size">${esc(item.note)}</span>
          </button>`
      ).join("")}
    </div>

    <section class="budget-hero" aria-labelledby="budget-hero-title">
      <div class="budget-hero-head">
        <div>
          <div class="budget-kicker" id="budget-hero-title">Total observed context · ${esc(window.label)}</div>
          <div class="budget-hero-number">${pct.toFixed(1)}<small>%</small></div>
        </div>
        <p class="budget-hero-copy">${fmtNum(total)} tokens across ${F.SCOPES.length} roots. ${
          headroom >= 0 ? `${fmtNum(headroom)} tokens remain before the threshold.` : `${fmtNum(-headroom)} tokens are over the window.`
        } The mark is an estimate, not a bill.</p>
      </div>
      ${ruler(pct, { size: "lg", label: `Total context: ${pct.toFixed(1)} percent of a ${window.label} window` })}
      <div class="budget-stats">
        <div class="budget-stat"><span class="label">Observed tokens</span><span class="value">${fmtNum(total)}</span><span class="sub">document bytes ÷ 4</span></div>
        <div class="budget-stat"><span class="label">Headroom</span><span class="value">${headroom >= 0 ? fmtNum(headroom) : "−" + fmtNum(-headroom)}</span><span class="sub">${
          headroom >= 0 ? "before the 100% mark" : "over the window"
        }</span></div>
        <div class="budget-stat"><span class="label">Largest root</span><span class="value">${fmtTokens(largest.tokens)}</span><span class="sub">${esc(
          largest.label
        )} · ${fmtNum(largest.count)} instances</span></div>
      </div>
    </section>

    <div class="context-grid">
      <section aria-labelledby="scope-budget-title">
        <div class="section-head"><h2 id="scope-budget-title">Budget by root</h2><span class="section-meta">${esc(window.note)}</span></div>
        <div class="table-wrap">
          <table class="scope-budget">
            <thead><tr><th>Root</th><th class="num">Instances</th><th class="num">Tokens</th><th>Share of window</th><th></th></tr></thead>
            <tbody>
              ${F.SCOPES.map((scope) => {
                const share = (scope.tokens / window.size) * 100;
                const tone = share > 50 ? "err" : share > 30 ? "warn" : "ok";
                const label = share > 50 ? "Over half" : share > 30 ? "Large" : "Within";
                return `<tr>
                  <td><span class="scope-label">${esc(scope.label)}</span><span class="scope-path">${esc(scope.path)}</span></td>
                  <td class="num">${fmtNum(scope.count)}</td>
                  <td class="num">${fmtNum(scope.tokens)}</td>
                  <td>
                    <span class="scope-track" style="margin-top:0" aria-hidden="true"><i style="transform:scaleX(${Math.min(1, scope.tokens / window.size).toFixed(3)})"></i></span>
                    <span class="mono" style="font-size:8.5px;color:var(--ink-3)">${share.toFixed(1)}%</span>
                  </td>
                  <td><span class="badge badge-${tone}">${label}</span></td>
                </tr>`;
              }).join("")}
            </tbody>
          </table>
        </div>
        <p class="method-note"><strong>How this is measured.</strong> The number is the sum of the document bytes divided by four. It is an estimate. It cannot see the consumer's own instructions, tool descriptions, cache hits, or the model's tokenizer. Treat it as a budget, not a bill.</p>
      </section>

      <section aria-labelledby="largest-title">
        <div class="section-head"><h2 id="largest-title">Largest documents</h2><span class="section-meta">single copy</span></div>
        <ol class="largest-list">
          ${largestSkills
            .map(
              (skill, index) => `<li class="largest-row">
                <span class="largest-rank">${index + 1}</span>
                <span>
                  <span class="largest-name">${esc(skill.name)}</span>
                  <span class="largest-meta">${esc(scopeShort(skill.instances[0] ? skill.instances[0].scope : "global"))} · ${skill.copies} ${
                skill.copies === 1 ? "copy" : "copies"
              }</span>
                  <span class="largest-bar" aria-hidden="true"><span style="display:block;height:100%;background:var(--ink-2);transform-origin:left;transform:scaleX(${(
                    skill.tokens / maxSkillTokens
                  ).toFixed(3)})"></span></span>
                </span>
                <span class="largest-tokens">${fmtNum(skill.tokens)}</span>
              </li>`
            )
            .join("")}
        </ol>
        <div class="note-panel" style="margin-top:14px">
          <strong>What the budget cannot see.</strong>
          It measures files on disk. It does not know which documents the consumer loads for a given task, how the model tokenizes them, or whether a cached prefix skips a file.
        </div>
      </section>
    </div>
  </div>`;
}
