/* ==========================================================================
   Folio views: quality, profiles, install, recovery, settings, empty states
   ========================================================================== */

/* --------------------------------------------------------------------------
   Quality
   -------------------------------------------------------------------------- */

function renderQuality() {
  const findings = qualityFindings();
  const counts = {
    all: F.QUALITY.length,
    error: F.QUALITY.filter((finding) => finding.severity === "error").length,
    warn: F.QUALITY.filter((finding) => finding.severity === "warn").length,
    info: F.QUALITY.filter((finding) => finding.severity === "info").length,
  };

  return `<div class="page">
    ${pageHead({
      kicker: "Quality · evidence ledger",
      title: "What is actually wrong.",
      lede: `Fourteen independent findings across parser state, content, containment, context, and recovery. No combined score, no safety verdict, no invented winner.`,
      actions: `<button class="button" type="button" data-action="refresh-hygiene">${icon("refresh")}Run again</button>`,
    })}

    <div class="library-bar" role="search">
      <span class="segmented" role="group" aria-label="Filter by severity">
        ${[
          ["all", "All", counts.all],
          ["error", "Errors", counts.error],
          ["warn", "Warnings", counts.warn],
          ["info", "Information", counts.info],
        ]
          .map(
            ([value, label, count]) =>
              `<button type="button" data-quality-severity="${value}" data-focus-key="qsev:${value}" aria-pressed="${
                state.qualitySeverity === value
              }">${esc(label)}<span class="seg-count">${fmtNum(count)}</span></button>`
          )
          .join("")}
      </span>

      <label class="library-search">
        <span class="sr-only">Search findings</span>
        ${icon("search")}
        <input type="search" value="${esc(state.qualityQuery)}" placeholder="Search evidence" autocomplete="off" spellcheck="false" data-input="quality-query" data-focus-key="quality-query">
      </label>

      <select class="select" data-change="quality-scope" data-focus-key="quality-scope" aria-label="Filter findings by root" style="width:auto;height:29px;padding:0 26px 0 8px;font-size:11px">
        <option value="all"${state.qualityScope === "all" ? " selected" : ""}>All roots</option>
        ${F.SCOPES.map((scope) => `<option value="${scope.id}"${state.qualityScope === scope.id ? " selected" : ""}>${esc(scope.label)}</option>`).join("")}
        <option value="multiple"${state.qualityScope === "multiple" ? " selected" : ""}>Multiple roots</option>
      </select>

      <span class="spacer"></span>
      <span class="library-count" id="quality-count">${fmtNum(findings.length)} findings</span>
    </div>

    <div class="quality-grid">
      <section aria-labelledby="finding-list-title">
        <div class="section-head"><h2 id="finding-list-title">Findings</h2><span class="section-meta">severity first</span></div>
        <div class="finding-list" id="finding-list">
          ${findings.length ? findings.map(renderFindingRow).join("") : `<div class="empty" style="border-top:0;padding:34px 16px"><div class="empty-mark">${icon("checkCircle")}</div><h2>No findings match this view.</h2><p>Clear the severity filter or search a different term. The ledger still holds ${fmtNum(F.QUALITY.length)} findings.</p></div>`}
        </div>
      </section>

      <aside class="quality-side">
        <div class="side-panel">
          <h3>What this ledger can show</h3>
          <p>Parser and addressability flags, physical copies and their state, content hashes, validator issues, source-lock evidence, and context size. Every finding names the file it came from.</p>
        </div>
        <div class="side-panel">
          <h3>Unavailable signals</h3>
          <ul class="availability-list">
            <li>${mark("unaddressable")}<span><strong>Usage</strong><span>No consumer telemetry is read. The room cannot know which skill was loaded for a task.</span></span></li>
            <li>${mark("unaddressable")}<span><strong>Freshness</strong><span>A modification time is not a statement about relevance.</span></span></li>
            <li>${mark("unaddressable")}<span><strong>Trust</strong><span>A registry hash is evidence of identity, not a safety certification.</span></span></li>
            <li>${mark("unaddressable")}<span><strong>Usefulness</strong><span>No score is invented from file size or wording.</span></span></li>
          </ul>
        </div>
        <div class="side-panel">
          <h3>Last scan</h3>
          <p>${fmtRelative(state.scanAt)}. Findings are derived from the observed inventory; a re-scan does not mutate a document.</p>
        </div>
      </aside>
    </div>
  </div>`;
}

function renderFindingRow(finding) {
  return `<button class="finding-row" type="button" data-action="finding-open" data-finding="${finding.id}" data-focus-key="finding:${finding.id}" aria-label="${esc(
    finding.title
  )}, ${esc(finding.severity)}">
    ${severityMark(finding.severity)}
    <span>
      <span class="finding-headline"><span class="finding-title">${esc(finding.title)}</span>${severityBadge(finding.severity)}</span>
      <span class="finding-evidence">${esc(finding.evidence)}</span>
      <span class="finding-foot">
        ${finding.skills.slice(0, 3).map((name) => `<span class="chip chip-mono">${esc(name)}</span>`).join("")}
        <span class="finding-count">${fmtNum(finding.count)} ${finding.count === 1 ? "instance" : "instances"}</span>
        <span class="finding-count">· ${esc(finding.scope)}</span>
      </span>
    </span>
    <span class="finding-count" aria-hidden="true">${icon("chevronRight")}</span>
  </button>`;
}

/* --------------------------------------------------------------------------
   Profiles
   -------------------------------------------------------------------------- */

function renderProfiles() {
  const profile = selectedProfile();
  const counts = { observed: 0, disabled: 0, divergent: 0, missing: 0 };
  profile.members.forEach((member) => {
    counts[member.state] = (counts[member.state] || 0) + 1;
  });
  const observed = counts.observed;

  return `<div class="page">
    ${pageHead({
      kicker: "Profiles · saved plans",
      title: "A few skills, one decision.",
      lede: "A profile is a saved membership list and a set of target roots. It previews what is observed before it changes anything, and it never installs a missing member.",
    })}

    <div class="profiles-grid">
      <div class="profile-list" aria-label="Saved profiles">
        ${F.PROFILES.map(
          (item) => `<button class="profile-row" type="button" data-profile="${item.id}" data-focus-key="profile:${item.id}" aria-current="${
            item.id === profile.id ? "true" : "false"
          }">
            <span class="profile-name">${esc(item.name)}</span>
            <span class="profile-meta">${item.members.length} members · ${item.targets.length} targets</span>
          </button>`
        ).join("")}
      </div>

      <div class="profile-detail">
        <div class="profile-detail-head">
          <div>
            <h2>${esc(profile.name)}</h2>
            <p class="profile-desc">${esc(profile.description)}</p>
          </div>
          <div class="doc-actions">
            <button class="button button-sm button-primary" type="button" data-action="profile-plan">${icon("play")}Review enable plan</button>
          </div>
        </div>

        <div class="profile-counts">
          ${[
            ["Observed", counts.observed],
            ["Disabled", counts.disabled],
            ["Divergent", counts.divergent],
            ["Missing", counts.missing],
          ]
            .map(
              ([label, value]) => `<div class="profile-count"><span class="label">${label}</span><span class="value">${fmtNum(value)}</span></div>`
            )
            .join("")}
        </div>

        <div class="section-head"><h3 style="margin:0;font-size:12.5px">Members</h3><span class="section-meta">${profile.targets
          .map((id) => scopeShort(id))
          .join(" · ")}</span></div>
        <ul class="profile-member-list">
          ${profile.members
            .map((member) => {
              const skill = findSkill(member.name);
              const memberKey = member.state === "missing" ? "unaddressable" : member.state === "observed" ? "active" : member.state;
              const memberTone = member.state === "divergent" ? "warn" : member.state === "observed" ? "ok" : "muted";
              return `<li>
                ${member.state === "missing" ? missingMark() : mark(memberKey)}
                <span><span class="member-name">${esc(member.name)}</span><span class="member-state is-${memberTone}">${
                  member.state === "missing" ? "No observed copy" : esc(stateMeta(memberKey).label)
                }</span></span>
                ${
                  skill
                    ? `<button class="button button-sm button-ghost" type="button" data-skill="${esc(member.name)}">Open</button>`
                    : `<span class="member-state">Not installed</span>`
                }
              </li>`;
            })
            .join("")}
        </ul>

        <div class="plan-box">
          <h3>What the plan will do</h3>
          <p>It enables the observed physical copies on the target roots. It does not install missing members, overwrite divergent content, or disable anything outside the profile.</p>
          <ul>
            <li>Disabled to active: ${fmtNum(counts.disabled)} ${counts.disabled === 1 ? "copy" : "copies"}.</li>
            <li>Observed and active: no state change.</li>
            <li>Divergent and missing: reported, left unchanged.</li>
          </ul>
        </div>
      </div>
    </div>
  </div>`;
}

/* --------------------------------------------------------------------------
   Install
   -------------------------------------------------------------------------- */

function renderInstall() {
  const item = selectedRegistryItem();
  const list = registryItems();
  const sources = [
    ["all", "All sources"],
    ["vercel-labs", "Vercel Labs"],
    ["anthropics", "Anthropic"],
    ["obra", "Obra"],
    ["microsoft", "Microsoft"],
    ["community", "Community"],
  ];

  return `<div class="page">
    ${pageHead({
      kicker: "Install · registry bridge",
      title: "The registry shelf.",
      lede: "Browse a bounded snapshot, read the validation and advisory risk evidence, then confirm. The trust gate is explicit, and a hash is identity, not a safety claim.",
      actions: `<button class="button" type="button" data-go="library">${icon("book")}Open catalogue</button>`,
    })}

    <div class="library-bar" role="search">
      <label class="library-search">
        <span class="sr-only">Search the registry</span>
        ${icon("search")}
        <input type="search" value="${esc(state.installQuery)}" placeholder="Search sources or skill names" autocomplete="off" spellcheck="false" data-input="install-query" data-focus-key="install-query">
      </label>
      <span class="segmented" role="group" aria-label="Filter by source">
        ${sources
          .map(
            ([value, label]) =>
              `<button type="button" data-source="${value}" data-focus-key="source:${value}" aria-pressed="${state.installSource === value}">${esc(
                label
              )}</button>`
          )
          .join("")}
      </span>
      <span class="spacer"></span>
      <span class="library-count" id="registry-count">${fmtNum(list.length)} sources</span>
    </div>

    <div class="install-grid">
      <section aria-labelledby="registry-title">
        <div class="section-head"><h2 id="registry-title">Skills.sh snapshot</h2><span class="section-meta">read-only until confirmed</span></div>
        <div class="registry-list" id="registry-list">
          ${
            list.length
              ? list.map((entry) => renderRegistryRow(entry, item)).join("")
              : `<div class="empty" style="border-top:0;padding:32px 16px"><div class="empty-mark">${icon("search")}</div><h2>No registry entries match this view.</h2><p>Try another source or a broader search. The prototype ships a fixed snapshot.</p></div>`
          }
        </div>
        <p class="hint" style="margin-top:10px">A fetched snapshot is validated in a private staging tree before the store is touched. This prototype never makes a network request.</p>
      </section>

      <aside id="trust-panel" style="min-width:0">${renderTrustPanel(item)}</aside>
    </div>
  </div>`;
}

function renderRegistryRow(entry, selected) {
  const installed = state.installed.has(entry.id);
  return `<button class="registry-row" type="button" data-registry="${entry.id}" data-focus-key="registry:${entry.id}" aria-current="${
    selected && selected.id === entry.id ? "true" : "false"
  }" aria-label="${esc(entry.name)} from ${esc(entry.source)}. ${esc(entry.description)}">
    <span class="registry-mark" aria-hidden="true">${esc(entry.source.charAt(0).toUpperCase())}</span>
    <span>
      <span class="registry-source">${esc(entry.source)}</span>
      <span class="registry-name">${esc(entry.name)}</span>
      <span class="registry-desc">${esc(entry.description)}</span>
      <span class="registry-foot">
        <span class="registry-stat">${esc(entry.installs)} installs</span>
        <span class="registry-stat">· ${entry.files} files</span>
        <span class="registry-stat">· ${esc(entry.updated)}</span>
        ${installed ? `<span class="badge badge-ok">Installed</span>` : riskBadge(entry.risk)}
      </span>
    </span>
    <span class="finding-count" aria-hidden="true">${icon("chevronRight")}</span>
  </button>`;
}

function renderTrustPanel(item) {
  if (!item) {
    return `<div class="trust-panel"><div class="empty" style="border-top:0;padding:24px 8px"><div class="empty-mark">${icon("package")}</div><h2 style="font-size:15px">Nothing selected.</h2><p>Choose a source from the shelf to read its evidence.</p></div></div>`;
  }

  if (state.installed.has(item.id)) {
    return `<div class="trust-panel">
      <div class="trust-success">
        <strong>${esc(item.name)} is in the global store.</strong>
        <span>One active copy was added. The prototype wrote to memory only.</span>
      </div>
      <div class="trust-section">
        <h3>What happened</h3>
        <div class="evidence-row"><span>Target</span><strong>global store</strong></div>
        <div class="evidence-row"><span>Files</span><strong>${item.files}</strong></div>
        <div class="evidence-row"><span>Validation</span><strong>${item.validation.errors} errors · ${item.validation.warnings} warnings</strong></div>
        <div class="evidence-row"><span>Risk</span><strong>${esc(titleCase(item.risk))} · advisory</strong></div>
      </div>
      <div class="trust-actions">
        <button class="button button-primary" type="button" data-action="view-installed">${icon("book")}Open in catalogue</button>
        <button class="button" type="button" data-action="install-reset" data-id="${item.id}">${icon("undo")}Remove sample copy</button>
      </div>
    </div>`;
  }

  return `<div class="trust-panel">
    <div class="trust-head">
      <div>
        <div class="budget-kicker">${esc(item.source)}</div>
        <h2>${esc(item.name)}</h2>
      </div>
      ${riskBadge(item.risk)}
    </div>
    <p class="trust-desc">${esc(item.description)}</p>

    <div class="trust-section">
      <h3>Snapshot evidence</h3>
      <div class="evidence-row"><span>Files</span><strong>${item.files} · text only</strong></div>
      <div class="evidence-row"><span>Updated</span><strong>${esc(item.updated)}</strong></div>
      <div class="evidence-row"><span>Validation</span><strong>${item.validation.errors} errors · ${item.validation.warnings} warnings</strong></div>
      <div class="evidence-row"><span>Snapshot hash</span><strong title="${esc(item.hash)}">${esc(item.hash.slice(0, 22))}…</strong></div>
      <button class="note-action" type="button" data-action="copy-hash" data-hash="${esc(item.hash)}">Copy hash</button>
    </div>

    <div class="trust-section">
      <h3>Advisory risk findings</h3>
      <ul class="risk-list">
        ${item.riskFindings
          .map(
            (finding) =>
              `<li>${mark(item.risk === "high" ? "malformed" : item.risk === "medium" ? "divergent" : "active")}<span>${esc(
                finding
              )}</span></li>`
          )
          .join("")}
      </ul>
      <p class="hint" style="margin-top:6px">Risk findings are advisory and heuristic. They are never enforcement evidence or a safety certification.</p>
    </div>

    <div class="trust-actions">
      <label class="checkbox-row">
        <input type="checkbox" data-change="trust" ${state.installTrusted ? "checked" : ""}>
        <span>I reviewed the source, the files, the validation, and the advisory risk findings.</span>
      </label>
      <button class="button button-primary" type="button" data-action="install-add" ${
        state.installTrusted && item.validation.errors === 0 ? "" : "disabled"
      }>${icon("download")}Add to global store</button>
      <span class="hint">${
        item.validation.errors > 0
          ? "One validation error blocks the commit. The prototype will not install an invalid snapshot."
          : "The commit is global-store-only. A review id is single use, and this prototype keeps it in memory."
      }</span>
    </div>
  </div>`;
}

/* --------------------------------------------------------------------------
   Recovery
   -------------------------------------------------------------------------- */

function renderRecovery() {
  return `<div class="page">
    ${pageHead({
      kicker: "Recovery · local and reversible",
      title: "Undo, restore, rebuild.",
      lede: "Nothing is purged without a confirmation. A snapshot is applied through a new review, never by a blind restore. The trash is global; agent scopes keep their own.",
      actions: `<button class="button" type="button" data-go="library">${icon("book")}Back to catalogue</button>`,
    })}

    <div class="recovery-grid">
      <section class="recovery-panel" aria-labelledby="trash-title">
        <div class="section-head"><h2 id="trash-title">Trash</h2><span class="section-meta">${F.TRASH.length} items · global only</span></div>
        ${
          F.TRASH.length
            ? `<ul class="trash-list">${F.TRASH.map(
                (item) => `<li class="trash-row">
                  <span><span class="trash-name">${esc(item.name)}</span><span class="trash-meta">${fmtDate(item.date, {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })} · ${esc(item.size)}</span></span>
                  <span class="trash-actions"><button class="button button-sm" type="button" data-action="restore-trash" data-id="${item.id}">${icon(
                    "undo"
                  )}Restore</button></span>
                </li>`
              ).join("")}</ul>`
            : `<div class="empty" style="border-top:0;padding:32px 16px"><div class="empty-mark">${icon("trash")}</div><h2>The trash is empty.</h2><p>Removed skills appear here with an undo path.</p></div>`
        }
        <div class="danger-zone">
          <h3>Purge the trash</h3>
          <p>Permanent removal. This cannot be undone and leaves no snapshot.</p>
          <button class="button button-sm button-danger" type="button" data-action="purge-open" ${F.TRASH.length ? "" : "disabled"}>${icon(
            "trash"
          )}Purge ${F.TRASH.length} items</button>
        </div>
      </section>

      <section class="recovery-panel" aria-labelledby="snapshots-title">
        <div class="section-head"><h2 id="snapshots-title">Retained snapshots</h2><span class="section-meta">newest five per target</span></div>
        <ul class="snapshot-list">
          ${F.SNAPSHOTS.map(
            (snapshot) => `<li class="snapshot-row">
              <span class="snapshot-mark" aria-hidden="true">${icon("clock")}</span>
              <span>
                <span class="snapshot-title">${esc(snapshot.name)} · ${esc(snapshot.action)}</span>
                <span class="snapshot-meta"><span>${esc(scopeLabel(snapshot.scope))}</span><span>·</span><span>${snapshot.files} files</span><span>·</span><span>${fmtDate(
              snapshot.at,
              { day: "numeric", month: "short", year: "numeric" }
            )}</span></span>
              </span>
              <button class="button button-sm button-ghost" type="button" data-action="rollback" data-id="${snapshot.id}">Review</button>
            </li>`
          ).join("")}
        </ul>
        <p class="hint" style="margin-top:8px">A snapshot is a complete tree, not a diff. A rollback previews the change and must be applied as a separate review.</p>

        <div class="section-head" style="margin-top:24px"><h2>Transfer</h2><span class="section-meta">offline archive</span></div>
        <div class="transfer-row">
          <span class="transfer-copy"><strong>Export the library</strong><span>Skills only, or the full migration with trash and templates.</span></span>
          <span class="trash-actions"><button class="button button-sm" type="button" data-action="export">${icon("download")}Export</button><button class="button button-sm" type="button" data-action="export-full">Full</button></span>
        </div>
        <div class="transfer-row">
          <span class="transfer-copy"><strong>Import an archive</strong><span>Content is sniffed. Unsafe members reject the whole upload.</span></span>
          <button class="button button-sm" type="button" data-action="import">${icon("upload")}Import</button>
        </div>
      </section>
    </div>

    <div class="method-note" style="margin-top:26px"><strong>One rule.</strong> A recovery action is not a shortcut for a decision. Restore returns the bytes; it does not reconcile a divergent copy or a stale index. Rebuild the index after the filesystem change.</div>
  </div>`;
}

/* --------------------------------------------------------------------------
   Settings
   -------------------------------------------------------------------------- */

function renderSettings() {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const demos = [
    ["live", "Live"],
    ["loading", "Loading"],
    ["empty", "Empty"],
    ["error", "Error"],
  ];

  return `<div class="page settings-layout">
    ${pageHead({
      kicker: "Settings · local only",
      title: "How this room behaves.",
      lede: "Preferences are local to this browser. They never modify an operating-system setting or a skill document.",
    })}

    <section class="settings-section" aria-labelledby="appearance-title">
      <div><h2 id="appearance-title">Appearance</h2><p>Theme, text size, and regional format are stored in this browser only.</p></div>
      <div class="settings-controls">
        <div class="setting-row">
          <span class="setting-copy"><strong>Theme</strong><span>System follows the operating system and updates live.</span></span>
          <span class="segmented setting-control" role="group" aria-label="Theme">
            ${[
              ["light", "Light"],
              ["dark", "Dark"],
              ["system", "System"],
            ]
              .map(
                ([value, label]) =>
                  `<button type="button" data-theme-choice="${value}" data-focus-key="theme:${value}" aria-pressed="${state.theme === value}">${label}</button>`
              )
              .join("")}
          </span>
        </div>
        <div class="setting-row">
          <span class="setting-copy"><strong>Text size</strong><span>Raises the interface and reading measure together.</span></span>
          <span class="segmented setting-control" role="group" aria-label="Text size">
            ${[
              ["standard", "Standard"],
              ["large", "Large"],
            ]
              .map(
                ([value, label]) =>
                  `<button type="button" data-size-choice="${value}" data-focus-key="size:${value}" aria-pressed="${state.textSize === value}">${label}</button>`
              )
              .join("")}
          </span>
        </div>
        <div class="setting-row">
          <span class="setting-copy"><strong>Regional format</strong><span>Numbers and dates only. The interface copy stays English.</span></span>
          <select class="select setting-control" data-change="locale" data-focus-key="locale-select" style="width:auto;min-width:130px;font-size:11px">
            <option value="system"${state.locale === "system" ? " selected" : ""}>System</option>
            <option value="en-US"${state.locale === "en-US" ? " selected" : ""}>en-US</option>
            <option value="en-GB"${state.locale === "en-GB" ? " selected" : ""}>en-GB</option>
            <option value="en-IN"${state.locale === "en-IN" ? " selected" : ""}>en-IN</option>
          </select>
        </div>
        <div class="setting-row">
          <span class="setting-copy"><strong>Palette</strong><span>A cool bone ground, one chartreuse signal, four status colours.</span></span>
          <span class="swatch-row setting-control" aria-hidden="true"><span class="swatch swatch-paper"></span><span class="swatch swatch-sheet"></span><span class="swatch swatch-ink"></span><span class="swatch swatch-signal"></span></span>
        </div>
      </div>
    </section>

    <section class="settings-section" aria-labelledby="motion-title">
      <div><h2 id="motion-title">Motion and access</h2><p>Motion is short and functional. The operating system preference is the authority.</p></div>
      <div class="settings-controls">
        <div class="setting-row">
          <span class="setting-copy"><strong>Reduced motion</strong><span>Read from the operating system; this page does not change it.</span></span>
          <span class="badge ${reducedMotion ? "badge-warn" : "badge-ok"}">${reducedMotion ? "Reduced" : "Standard"}</span>
        </div>
        <div class="setting-row">
          <span class="setting-copy"><strong>Focus ring</strong><span>A 2px ink outline, a chartreuse halo, and a visible offset on every control.</span></span>
          <span class="badge badge-ok">Always visible</span>
        </div>
        <div class="setting-row">
          <span class="setting-copy"><strong>Keyboard</strong><span>Open the shortcut sheet with <kbd class="kbd">?</kbd>. The catalogue supports <kbd class="kbd">j</kbd> and <kbd class="kbd">k</kbd>.</span></span>
          <button class="button button-sm setting-control" type="button" data-action="help">${icon("keyboard")}Shortcuts</button>
        </div>
      </div>
    </section>

    <section class="settings-section" aria-labelledby="data-title">
      <div><h2 id="data-title">Data</h2><p>The filesystem is the source of truth. The index is a rebuildable cache.</p></div>
      <div class="settings-controls">
        <div class="setting-row">
          <span class="setting-copy"><strong>Data root</strong><span>Sample path for this prototype. Nothing is read from it.</span></span>
          <code class="setting-control mono" style="font-size:9.5px;color:var(--ink-3)">~/.local/share/skills-manager</code>
        </div>
        <div class="setting-row">
          <span class="setting-copy"><strong>Index</strong><span>Schema 1. Rebuilds are safe; the documents are untouched.</span></span>
          <span class="badge badge-ok">Healthy · ${fmtNum(skills.length)} rows</span>
        </div>
        <div class="setting-row">
          <span class="setting-copy"><strong>Maintenance</strong><span>These actions are simulated in the prototype.</span></span>
          <span class="trash-actions setting-control"><button class="button button-sm" type="button" data-action="rebuild">${icon("refresh")}Rebuild</button><button class="button button-sm" type="button" data-action="resync">${icon("undo")}Resync</button></span>
        </div>
      </div>
    </section>

    <section class="settings-section" aria-labelledby="prototype-title">
      <div><h2 id="prototype-title">Prototype</h2><p>Use these states to inspect the layout without a backend.</p></div>
      <div class="settings-controls">
        <div class="setting-row">
          <span class="setting-copy"><strong>Demo state</strong><span>Affects Overview and Catalogue. Other views stay live.</span></span>
          <span class="segmented setting-control" role="group" aria-label="Demo state">
            ${demos
              .map(
                ([value, label]) =>
                  `<button type="button" data-demo="${value}" data-focus-key="demo:${value}" aria-pressed="${state.demo === value}">${label}</button>`
              )
              .join("")}
          </span>
        </div>
        <div class="setting-row">
          <span class="setting-copy"><strong>Sample inventory</strong><span>${fmtNum(F.TOTAL_INSTANCES)} instances, ${fmtNum(
    skills.length
  )} logical skills, generated in the page.</span></span>
          <button class="button button-sm setting-control" type="button" data-action="reset-sample">${icon("refresh")}Reset</button>
        </div>
        <div class="setting-row">
          <span class="setting-copy"><strong>About</strong><span>Concept, constraints, and the design contract.</span></span>
          <button class="button button-sm setting-control" type="button" data-action="about">${icon("info")}About Folio</button>
        </div>
      </div>
    </section>

    <section class="settings-section" aria-labelledby="about-title">
      <div><h2 id="about-title">About this build</h2><p>Folio is a frontend-only concept for Skills Manager.</p></div>
      <div class="about-block">
        <p><strong>Frontend only.</strong> No Python server, no SQLite index, no file access. Every name, path, hash, and count on these screens is sample data.</p>
        <p><strong>One command surface.</strong> The catalogue, budget, evidence ledger, and recovery screens describe the same observed inventory from different angles. None of them is a separate source of truth.</p>
        <p><strong>Built with</strong> semantic HTML, hand-written CSS, and vanilla JavaScript. Fonts are vendored locally. No build step, no CDN, no runtime dependency.</p>
        <p><strong>Version</strong> <code>folio-0.1</code> · <code>2026-10-25</code></p>
        <div style="margin-top:10px;display:flex;gap:7px;flex-wrap:wrap"><button class="button button-sm" type="button" data-action="help">${icon(
          "keyboard"
        )}Shortcuts</button><button class="button button-sm" type="button" data-action="about">${icon("info")}About</button></div>
      </div>
    </section>
  </div>`;
}

/* --------------------------------------------------------------------------
   Loading, empty, error
   -------------------------------------------------------------------------- */

function renderLoadingView(view) {
  if (view === "library") {
    return `<div class="page library-view">
      <header class="page-head page-head-compact">
        <div class="skeleton skeleton-row" style="width:120px;height:10px"></div>
        <div class="skeleton skeleton-title"></div>
        <div class="skeleton skeleton-copy" style="width:48%"></div>
      </header>
      <div class="library-bar"><div class="skeleton" style="width:300px;height:29px"></div><div class="skeleton" style="width:150px;height:29px"></div><div class="skeleton" style="width:120px;height:29px"></div></div>
      <div class="library-split">
        <div class="skill-list">${Array.from({ length: 9 })
          .map(
            () => `<div class="skill-row" style="pointer-events:none"><span class="skeleton" style="width:10px;height:10px;margin-top:3px"></span><span><div class="skeleton skeleton-row" style="width:52%"></div><div class="skeleton skeleton-row" style="width:86%"></div><div class="skeleton skeleton-row" style="width:38%"></div></span><span class="skeleton" style="width:32px;height:9px"></span></div>`
          )
          .join("")}</div>
        <div class="document-room"><div class="skeleton-sheet"><div class="skeleton skeleton-row" style="width:130px;height:10px"></div><div class="skeleton skeleton-title" style="width:58%;height:24px"></div><div class="skeleton skeleton-row" style="width:92%"></div><div class="skeleton skeleton-row" style="width:88%"></div><div class="skeleton skeleton-row" style="width:94%"></div><div class="skeleton skeleton-row" style="width:64%"></div></div></div>
      </div>
    </div>`;
  }

  return `<div class="page">
    <header class="page-head"><div class="skeleton skeleton-row" style="width:160px;height:10px"></div><div class="skeleton skeleton-title" style="width:52%"></div><div class="skeleton skeleton-copy"></div></header>
    <div class="overview-grid">
      <div>${Array.from({ length: 3 })
        .map(
          () => `<div class="skeleton-sheet" style="margin-bottom:10px"><div class="skeleton skeleton-row" style="width:30%"></div><div class="skeleton skeleton-row" style="width:70%"></div><div class="skeleton skeleton-row" style="width:56%"></div></div>`
        )
        .join("")}</div>
      <div class="skeleton-sheet"><div class="skeleton skeleton-row" style="width:40%"></div><div class="skeleton" style="height:44px;margin:14px 0"></div><div class="skeleton skeleton-row" style="width:90%"></div><div class="skeleton skeleton-row" style="width:74%"></div></div>
    </div>
    <div class="skeleton-sheet" style="margin-top:26px"><div class="skeleton skeleton-row" style="width:28%"></div>${Array.from({ length: 5 })
      .map(() => `<div class="skeleton skeleton-row" style="width:96%"></div>`)
      .join("")}</div>
  </div>`;
}

function renderFirstRun() {
  return `<div class="page">
    ${pageHead({
      kicker: "First scan · nothing configured",
      title: "Start with one folder.",
      lede: "The room has not observed a skill root yet. Point it at the directory your agent already reads, run one scan, and the catalogue will show every copy it can see.",
      actions: "",
    })}
    <div class="empty" style="border-top:1px solid var(--rule-2)">
      <div class="empty-mark">${icon("book")}</div>
      <h2>A name is not a file.</h2>
      <p>One logical skill can live in several roots. Folio starts by showing the roots, the copies, and the state of each document. It does not write until you ask it to.</p>
      <div class="empty-steps">
        <div class="empty-step"><span class="step-num">1</span><strong>Point at a root</strong><span>Use a directory an agent already reads, such as ~/.claude/skills.</span></div>
        <div class="empty-step"><span class="step-num">2</span><strong>Run one scan</strong><span>The scan is read-only. It reports what it can read and what it refuses to follow.</span></div>
        <div class="empty-step"><span class="step-num">3</span><strong>Read the answer</strong><span>Start with the attention queue, then the context budget, then the catalogue.</span></div>
      </div>
      <div class="empty-actions">
        <button class="button" type="button" data-action="add-folder">${icon("folder")}Add a folder</button>
        <button class="button button-primary" type="button" data-action="run-scan">${icon("search")}Run the first scan</button>
      </div>
      <p class="hint" style="margin-top:14px">The first scan never writes to a root.</p>
    </div>
  </div>`;
}

function renderErrorView(viewName, title, body, viewKey) {
  return `<div class="page">
    ${pageHead({
      kicker: `${viewName} · read error`,
      title: "The room could not finish the read.",
      lede: "The error is scoped to this view. Nothing was repaired, and the last good data is still on disk.",
      actions: "",
    })}
    <div class="banner" role="alert">
      ${mark("malformed")}
      <div>
        <h2>${esc(title)}</h2>
        <p>${esc(body)}</p>
        <div class="banner-actions">
          <button class="button button-sm" type="button" data-action="retry-demo" data-view="${viewKey}">${icon("refresh")}Retry this view</button>
          <button class="button button-sm button-ghost" type="button" data-action="clear-demo">${icon("close")}Use sample data</button>
        </div>
      </div>
    </div>
    <div class="empty" style="margin-top:14px">
      <div class="empty-mark">${icon("alert")}</div>
      <h2>No rows were changed.</h2>
      <p>A failed read is not an empty library. The two states are kept apart on purpose, so a broken index never looks like a clean root.</p>
    </div>
  </div>`;
}
