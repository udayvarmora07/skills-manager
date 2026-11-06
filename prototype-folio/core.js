/* ==========================================================================
   Folio core: state, formatting, icons, marks, derived data
   ========================================================================== */

const F = window.FOLIO;

const TODAY = Date.UTC(2026, 9, 25, 23, 59, 0);

const clone = (value) =>
  typeof structuredClone === "function" ? structuredClone(value) : JSON.parse(JSON.stringify(value));

const store = {
  get(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value === null ? fallback : value;
    } catch (error) {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (error) {
      /* localStorage can be unavailable on file://. The prototype still works. */
    }
  },
};

const state = {
  view: "overview",
  query: "",
  scope: "all",
  status: "all",
  sort: "name",
  limit: 60,
  selected: "agent-browser",
  detailTab: "document",
  palette: false,
  paletteQuery: "",
  paletteIndex: 0,
  modal: null,
  help: false,
  about: false,
  toast: null,
  toastTimer: null,
  theme: (() => {
    const value = store.get("folio-theme", "system");
    return ["light", "dark", "system"].includes(value) ? value : "system";
  })(),
  textSize: store.get("folio-size", "standard") === "large" ? "large" : "standard",
  locale: (() => {
    const value = store.get("folio-locale", "system");
    return ["system", "en-US", "en-GB", "en-IN"].includes(value) ? value : "system";
  })(),
  window: "claude",
  demo: "live",
  qualitySeverity: "all",
  qualityQuery: "",
  qualityScope: "all",
  installQuery: "",
  installSource: "all",
  installSelected: "r1",
  installTrusted: false,
  installed: new Set(),
  selectedProfile: "frontend",
  syncTargets: new Set(),
  diffMode: "split",
  mobileDetail: false,
  railOpen: false,
  lastFocus: null,
  focusKey: "",
  scrollSelected: true,
  gPending: false,
  gTimer: null,
  scanAt: "2026-10-25T11:58:00Z",
};

let skills = clone(F.SKILLS);

/* --------------------------------------------------------------------------
   DOM and formatting
   -------------------------------------------------------------------------- */

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function esc(value) {
  return String(value === null || value === undefined ? "" : value).replace(/[&<>"']/g, (character) => {
    switch (character) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });
}

function localeCode() {
  if (state.locale === "system") return navigator.language || "en-US";
  return state.locale;
}

function numberFormat() {
  try {
    return new Intl.NumberFormat(localeCode());
  } catch (error) {
    return new Intl.NumberFormat("en-US");
  }
}

function fmtNum(value) {
  return numberFormat().format(value);
}

function fmtTokens(value) {
  const n = Number(value) || 0;
  if (n >= 1000000) return `${(n / 1000000).toFixed(n >= 10000000 ? 0 : 1).replace(/\.0$/, "")}m`;
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, "")}k`;
  return String(n);
}

function fmtDate(iso, options = { day: "numeric", month: "short" }) {
  try {
    return new Intl.DateTimeFormat(localeCode(), { timeZone: "UTC", ...options }).format(new Date(iso));
  } catch (error) {
    return String(iso).slice(0, 10);
  }
}

function fmtRelative(iso) {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "unknown";
  const days = Math.floor((TODAY - then) / 86400000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  if (months === 1) return "one month ago";
  if (months < 12) return `${months} months ago`;
  const years = Math.floor(months / 12);
  return years === 1 ? "one year ago" : `${years} years ago`;
}

function titleCase(value) {
  return String(value)
    .split(/[\s-]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/* --------------------------------------------------------------------------
   Derived data
   -------------------------------------------------------------------------- */

function findSkill(name) {
  return skills.find((skill) => skill.name === name) || null;
}

function scopeById(id) {
  return F.SCOPES.find((scope) => scope.id === id) || null;
}

function scopeLabel(id) {
  const scope = F.SCOPES.find((item) => item.id === id);
  return scope ? scope.label : id;
}

function scopeShort(id) {
  const scope = F.SCOPES.find((item) => item.id === id);
  return scope ? scope.short : id;
}

function totalTokens() {
  return F.TOTAL_TOKENS;
}

function windowDef() {
  return F.WINDOWS.find((item) => item.id === state.window) || F.WINDOWS[0];
}

function windowSize() {
  return windowDef().size;
}

function pctOfWindow(tokens) {
  return ((Number(tokens) || 0) / windowSize()) * 100;
}

function largestRoot() {
  return [...F.SCOPES].sort((a, b) => b.tokens - a.tokens)[0];
}

function stateMeta(key) {
  return F.STATE_META[key] || F.STATE_META.active;
}

function statusCounts() {
  const counts = { all: skills.length, active: 0, attention: 0, disabled: 0 };
  skills.forEach((skill) => {
    if (skill.state === "active" || skill.state === "mixed") counts.active += 1;
    if (["divergent", "malformed", "linked", "unaddressable"].includes(skill.state)) counts.attention += 1;
    if (skill.state === "disabled" || skill.state === "mixed") counts.disabled += 1;
  });
  return counts;
}

function filteredSkills() {
  const query = state.query.trim().toLowerCase();
  let list = skills.slice();

  if (state.scope !== "all") {
    list = list.filter((skill) => skill.instances.some((instance) => instance.scope === state.scope));
  }

  if (state.status === "attention") {
    list = list.filter((skill) => ["divergent", "malformed", "linked", "unaddressable"].includes(skill.state));
  } else if (state.status === "active") {
    list = list.filter((skill) => skill.state === "active" || skill.state === "mixed");
  } else if (state.status === "disabled") {
    list = list.filter((skill) => skill.state === "disabled" || skill.state === "mixed");
  }

  if (query) {
    list = list.filter((skill) => {
      const haystack = `${skill.name} ${skill.description} ${skill.category} ${skill.instances
        .map((instance) => instance.path)
        .join(" ")}`;
      return haystack.toLowerCase().includes(query);
    });
  }

  if (state.sort === "updated") {
    list.sort((a, b) => String(b.updated).localeCompare(String(a.updated)));
  } else if (state.sort === "largest") {
    list.sort((a, b) => b.tokens - a.tokens);
  } else if (state.sort === "copies") {
    list.sort((a, b) => b.copies - a.copies);
  } else {
    list.sort((a, b) => a.name.localeCompare(b.name));
  }

  return list;
}

function selectedSkill() {
  return findSkill(state.selected);
}

function selectedProfile() {
  return F.PROFILES.find((profile) => profile.id === state.selectedProfile) || F.PROFILES[0];
}

function qualityFindings() {
  const query = state.qualityQuery.trim().toLowerCase();
  return F.QUALITY.filter((finding) => {
    if (state.qualitySeverity !== "all" && finding.severity !== state.qualitySeverity) return false;
    if (state.qualityScope !== "all" && finding.scope !== state.qualityScope && finding.scope !== "multiple") return false;
    if (query) {
      const haystack = `${finding.title} ${finding.evidence} ${finding.category} ${finding.skills.join(" ")}`.toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    return true;
  });
}

function registryItems() {
  const query = state.installQuery.trim().toLowerCase();
  return F.REGISTRY.filter((item) => {
    if (state.installSource !== "all" && !item.source.startsWith(state.installSource)) return false;
    if (!query) return true;
    return `${item.name} ${item.source} ${item.description} ${item.category}`.toLowerCase().includes(query);
  });
}

function selectedRegistryItem() {
  const list = registryItems();
  return list.find((item) => item.id === state.installSelected) || list[0] || null;
}

function variantFor(skill) {
  if (skill.variantBody) return skill.variantBody;
  return skill.body.replace("## Checks", "## Checks\n\n- This copy uses a different checklist from the canonical copy.");
}

/* --------------------------------------------------------------------------
   Icons
   -------------------------------------------------------------------------- */

const ICON_PATHS = {
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  chevronRight: '<path d="m9 5 7 7-7 7"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  arrowLeft: '<path d="M19 12H5m0 0 6-6m-6 6 6 6"/>',
  arrowUpRight: '<path d="M7 17 17 7M8 7h9v9"/>',
  home: '<path d="m4 11 8-7 8 7"/><path d="M6.5 9.5V20h11V9.5"/><path d="M10 20v-5h4v5"/>',
  book: '<path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M8 4v16M5 17h14"/>',
  gauge: '<path d="M4 14a8 8 0 1 1 16 0"/><path d="m12 14 3.5-3.5"/><circle cx="12" cy="14" r="1"/>',
  checkCircle: '<circle cx="12" cy="12" r="8.5"/><path d="m8 12 2.5 2.5L16 9"/>',
  shield: '<path d="M12 3l7 3v5c0 4.2-2.8 7.4-7 9-4.2-1.6-7-4.8-7-9V6z"/><path d="m9 12 2 2 4-4"/>',
  settings: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  users: '<circle cx="9" cy="8" r="3"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0M16 11a3 3 0 1 0 0-6M16 14a5 5 0 0 1 4.5 5"/>',
  download: '<path d="M12 3v12m0 0 4-4m-4 4-4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
  upload: '<path d="M12 15V3m0 0 4 4m-4-4-4 4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
  refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.7L20 8.5"/><path d="M20 4v4.5h-4.5"/>',
  trash: '<path d="M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/>',
  folder: '<path d="M3.5 7.5h6l2 2h9v9h-17z"/><path d="M3.5 7.5V5.5h5l2 2"/>',
  file: '<path d="M6 3.5h8l4 4v13H6z"/><path d="M14 3.5v4h4"/>',
  filePlus: '<path d="M6 3.5h8l4 4v13H6z"/><path d="M14 3.5v4h4"/><path d="M12 11v6M9 14h6"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
  grid: '<rect x="4" y="4" width="6" height="6"/><rect x="14" y="4" width="6" height="6"/><rect x="4" y="14" width="6" height="6"/><rect x="14" y="14" width="6" height="6"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12"/><path d="M4 6h.01M4 12h.01M4 18h.01"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.5 4.5l1.4 1.4m12.2 12.2 1.4 1.4M2 12h2m16 0h2M4.5 19.5l1.4-1.4M18.1 5.9l1.4-1.4"/>',
  keyboard: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="1"/><path d="M16 8V5H4v12h3"/>',
  diff: '<path d="M6 4v16M18 4v16"/><path d="M9 8h6M9 16h6"/>',
  external: '<path d="M14 4h6v6"/><path d="m20 4-8 8"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
  undo: '<path d="M9 7 4 12l5 5"/><path d="M4 12h9a6 6 0 0 1 6 6v1"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/>',
  alert: '<path d="M12 3 2.5 20h19z"/><path d="M12 9v5M12 17h.01"/>',
  terminal: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/>',
  package: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="m4 7.5 8 4.5 8-4.5M12 21v-9"/>',
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  lock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  filter: '<path d="M4 6h16l-6 7v5l-4 2v-7z"/>',
  eye: '<path d="M2.5 12S6 6 12 6s9.5 6 9.5 6S18 18 12 18 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.5"/>',
  link: '<path d="M10 13a4 4 0 0 0 5.7 0l2.8-2.8a4 4 0 0 0-5.7-5.7L11 6.3"/><path d="M14 11a4 4 0 0 0-5.7 0l-2.8 2.8a4 4 0 0 0 5.7 5.7l1.8-1.8"/>',
  play: '<path d="m9 6 9 6-9 6z"/>',
  pause: '<path d="M8 6v12M16 6v12"/>',
  sort: '<path d="M7 4v16m0 0-3-3m3 3 3-3M17 20V4m0 0-3 3m3-3 3 3"/>',
  command: '<rect x="4" y="6" width="16" height="12" rx="2"/><path d="M8 10h.01M12 10h.01M16 10h.01M8 14h8"/>',
};

function icon(name, className = "") {
  const body = ICON_PATHS[name] || ICON_PATHS.chevronRight;
  return `<svg${className ? ` class="${className}"` : ""} aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
}

const MARK_PATHS = {
  active: '<rect x="1" y="1" width="8" height="8" fill="currentColor"/>',
  disabled:
    '<rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M2.3 5h5.4" stroke="currentColor" stroke-width="1.4"/>',
  mixed:
    '<rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M1 1h4v8H1z" fill="currentColor"/>',
  divergent:
    '<rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M1 9 9 1v8z" fill="currentColor"/>',
  malformed:
    '<rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="m2.8 2.8 4.4 4.4m0-4.4L2.8 7.2" stroke="currentColor" stroke-width="1.4"/>',
  linked:
    '<rect x="1" y="3" width="6" height="6" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M6.5 3.5 9.5.5M7 .5h2.5V3" stroke="currentColor" stroke-width="1.4"/>',
  unaddressable:
    '<rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M1 9 9 1" stroke="currentColor" stroke-width="1.4"/>',
};

function markSvg(key) {
  return `<svg viewBox="0 0 10 10" aria-hidden="true">${MARK_PATHS[key] || MARK_PATHS.active}</svg>`;
}

function mark(key, extraClass = "") {
  const meta = stateMeta(key);
  return `<span class="mark mark-${meta.tone}${extraClass ? ` ${extraClass}` : ""}" aria-hidden="true">${markSvg(meta.mark)}</span>`;
}

const SHORT_STATE = {
  active: "Active",
  mixed: "Active + disabled",
  disabled: "Disabled",
  divergent: "Divergent",
  malformed: "Malformed",
  linked: "Outside root",
  unaddressable: "Unaddressable",
};

function stateBadge(key, long = false) {
  const meta = stateMeta(key);
  return `<span class="badge badge-${meta.tone}">${markSvg(meta.mark)} ${esc(long ? meta.label : SHORT_STATE[key] || meta.label)}</span>`;
}

function shortStateLabel(key) {
  return SHORT_STATE[key] || stateMeta(key).label;
}

function stateChip(key) {
  const meta = stateMeta(key);
  return `<span class="chip state-chip is-${meta.tone}" title="${esc(meta.label)}">${esc(shortStateLabel(key))}</span>`;
}

function missingMark() {
  return `<span class="mark mark-muted" aria-hidden="true"><svg viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.4" stroke-dasharray="2 1.5"/></svg></span>`;
}

function severityMark(severity) {
  const meta = F.SEVERITY_META[severity] || F.SEVERITY_META.info;
  const shape = severity === "error" ? "malformed" : severity === "warn" ? "divergent" : "active";
  return `<span class="mark mark-${meta.tone}" aria-hidden="true">${markSvg(shape)}</span>`;
}

function severityBadge(severity) {
  const meta = F.SEVERITY_META[severity] || F.SEVERITY_META.info;
  return `<span class="badge badge-${meta.tone}">${esc(meta.label)}</span>`;
}

function riskBadge(risk) {
  const tone = risk === "high" ? "err" : risk === "medium" ? "warn" : "ok";
  return `<span class="badge badge-${tone}">${esc(titleCase(risk))} risk</span>`;
}

function memberBadge(memberState) {
  const map = {
    observed: { tone: "ok", label: "Observed", shape: "active" },
    disabled: { tone: "muted", label: "Disabled", shape: "disabled" },
    divergent: { tone: "warn", label: "Divergent", shape: "divergent" },
    missing: { tone: "muted", label: "Missing", shape: "unaddressable" },
  };
  const meta = map[memberState] || map.missing;
  return `<span class="badge badge-${meta.tone}">${markSvg(meta.shape)} ${esc(meta.label)}</span>`;
}

/* --------------------------------------------------------------------------
   Ruler component
   -------------------------------------------------------------------------- */

function ruler(pct, options = {}) {
  const raw = Number(pct) || 0;
  const value = Math.max(0, Math.min(125, raw));
  const tone = raw > 100 ? "err" : raw >= 80 ? "warn" : "ok";
  const size = options.size === "lg" ? " ruler-lg" : options.size === "sm" ? " ruler-sm" : "";
  const labels =
    options.size === "sm"
      ? ""
      : `<div class="ruler-ticks" aria-hidden="true"></div><div class="ruler-labels" aria-hidden="true">${[0, 25, 50, 75, 100, 125]
          .map((tick) => `<span>${tick}%</span>`)
          .join("")}</div>`;
  const label = options.label || `Context budget: ${raw.toFixed(1)} percent of the window`;
  return `<div class="ruler${size}" style="--pct:${value.toFixed(2)};--tone:var(--${tone})" role="img" aria-label="${esc(label)}">
    <div class="ruler-track"><div class="ruler-fill"></div><div class="ruler-threshold"></div></div>
    ${labels}
  </div>`;
}

function stateBar(scope) {
  const order = ["active", "disabled", "divergent", "malformed", "linked"];
  const total = scope.count || 1;
  return `<span class="state-bar" aria-label="${order
    .map((key) => `${scope.states[key]} ${key}`)
    .join(", ")}">${order
    .map(
      (key) =>
        `<span class="s-${key}" style="width:${((scope.states[key] || 0) / total * 100).toFixed(2)}%" title="${scope.states[key]} ${key}"></span>`
    )
    .join("")}</span>`;
}
