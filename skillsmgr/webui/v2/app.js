/* Skills Manager v2 — Vue 3 application (no build step).
 * Same transport, same backend and same observed-state vocabulary as the
 * classic interface; only the presentation and the workflow framing differ. */
"use strict";

const Domain = window.SkillManagerDomain;
const Model = window.SkillsV2Model;
if (!Domain || !Model) {
  const failure = document.createElement("div");
  failure.setAttribute("role", "alert");
  failure.style.cssText = "margin:2rem;padding:1rem;border:1px solid #b42318;border-radius:8px;font:15px/1.5 system-ui,sans-serif;color:#b42318;background:#fff;";
  failure.textContent = "Skills Manager could not start: a script did not load. Reload the page; if it persists, the installed files are incomplete.";
  document.body.appendChild(failure);
  throw new Error("v2 scripts missing");
}

const { api } = Domain;
const { createApp, markRaw } = Vue;
const { esc, plural, join, words, titleCase, shortPath, STATUS, BROKEN_WHY, changes, plainLine, renderDoc, stripFrontmatter } = Model;

/* ---------- Icons (constant, trusted markup) ---------- */
const PATHS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  ok: '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 3 3 5-6"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  warn: '<path d="M12 3.5 2.8 19.5h18.4L12 3.5Z"/><path d="M12 10v4M12 17v.01"/>',
  bad: '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
  off: '<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.01"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
  trash: '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/>',
  share: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  home: '<path d="m4 11 8-7 8 7"/><path d="M6 10v10h12V10"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12"/><path d="M4 6h.01M4 12h.01M4 18h.01"/>',
  map: '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Z"/><path d="M9 3v15M15 6v15"/>',
  inbox: '<path d="M4 13h4l2 3h4l2-3h4"/><path d="M5 5h14l1 8v6H4v-6Z"/>',
  tools: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z"/>',
  auto: '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
  pencil: '<path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/>',
};

const CAP = 48;
const FALLBACK_AGENT = { id: "", name: "Unknown", color: "#55585f", initials: "?", path: "" };

function parseRoute() {
  const h = location.hash.replace(/^#\/?/, "");
  const [p, ...rest] = h.split("/");
  if (p === "skill" && rest.length) { try { return { page: "skill", name: decodeURIComponent(rest.join("/")) }; } catch (e) { return { page: "skills" }; } }
  if (p === "tools") return { page: "tools", tool: ["install", "profiles", "quality", "workspaces", "templates", "settings", "source-update"].includes(rest[0]) ? rest[0] : "tools" };
  return ["skills", "map", "inbox", "recovery"].includes(p) ? { page: p } : { page: "home" };
}
const TITLES = { home: "Home", skills: "Skills", map: "Sync map", inbox: "Inbox", recovery: "Recovery", tools: "Tools" };
const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const THEMES = ["system", "light", "dark"];
function savedPreference(key, choices, fallback) {try{const value=localStorage.getItem(key);return choices.includes(value)?value:fallback;}catch(e){return fallback;}}

const app = createApp({
  data() {
    return {
      route: parseRoute(), m: null, loading: true, loadError: "", history: [], busy: false,
      records: [], scopes: [], catalog: {tags:{}, profiles:{}}, catalogError: "", tagFilter: "", libraryView: savedPreference("skillsmgr-v2-library-view",["shelf","instances"],"shelf"), toolTarget: null, readCopyPath: "",
      historyError: "", skillHistoryError: "", trashError: "", trashLoading: false, importFull: false, importResult: null, createTemplates: [], commandQuery: "",
      query: "", filter: "all", agentFilter: "all", extra: {}, sortBy: "name",
      front: null, skipped: [], dismissed: [], done: 0, srcChoice: "",
      bodies: {}, bodyInflight: {}, bodyErrors: {},
      treeQuery: "", edit: null, highlight: true, compareWith: "",
      mapSelId: "", mapPicked: [], peek: null,
      trash: [], importFile: null, importForce: false,
      theme: savedPreference("skillsmgr-theme",THEMES,"system"),formatLocale:savedPreference("skillsmgr-locale",["system","en-US","en-GB","en-IN"],"system"),
      dialog: null, toasts: [], live: "", toastSeq: 0, skillHistory: [], opener: null,
    };
  },
  computed: {
    inboxCount() { return this.m ? this.queue.length : 0; },
    agentInfos() { return this.m ? this.m.infos.filter((i) => !i.agent.library) : []; },
    sharedSkills() { return this.m ? [...this.m.skills].sort((a, b) => b.tools.length - a.tools.length || a.name.localeCompare(b.name)).slice(0, 3) : []; },
    /* Categories only help when the skills actually carry them; otherwise the
     * shelf falls back to an alphabet, which is what people can scan. */
    grouping() { return this.m && new Set(this.m.skills.map((s) => s.category).filter(Boolean)).size > 1 ? "category" : "letter"; },
    filterChoices() {
      const sk = this.m ? this.m.skills : [];
      return [
        { id: "all", label: "All", n: sk.filter((s) => s.status.key !== "note").length },
        { id: "care", label: "Needs care", n: this.careCount },
        { id: "off", label: "Turned off", n: sk.filter((s) => s.status.key === "off").length },
      ];
    },
    shelfTotal() { return this.m ? this.m.skills.filter((s) => s.status.key !== "note").length : 0; },
    careCount() { return this.m ? this.m.skills.filter((s) => s.status.key === "warn" || s.status.key === "bad").length : 0; },
    catalogTags() { return [...new Set(Object.values(this.catalog.tags || {}).flat())].sort(); },
    visibleNames() { return this.visible.map(s => s.name); },
    commandChoices() {const items=[{label:"New skill",action:"create"},{label:"Refresh files",action:"refresh"},...[['Skills','#/skills'],['Install','#/tools/install'],['Profiles','#/tools/profiles'],['Quality and validation','#/tools/quality'],['Workspaces','#/tools/workspaces'],['Templates','#/tools/templates'],['Settings and index maintenance','#/tools/settings'],['Recovery and history','#/recovery']].map(([label,path])=>({label,path}))];return items.filter(item=>item.label.toLowerCase().includes(this.commandQuery.toLowerCase()));},
    visible() {
      if (!this.m) return [];
      const q = this.query.trim().toLowerCase();
      return this.m.skills.filter((s) => {
        const k = s.status.key;
        if (k === "note") return false; /* not a skill: listed in the Inbox only */
        if (this.filter === "care" && k !== "warn" && k !== "bad") return false;
        if (this.filter === "off" && k !== "off") return false;
        if (this.agentFilter !== "all" && !s.copies.some((c) => c.scope === this.agentFilter)) return false;
        const tags = (this.catalog.tags || {})[s.name] || [];
        if (this.tagFilter === "__untagged" && tags.length) return false;
        if (this.tagFilter && this.tagFilter !== "__untagged" && !tags.includes(this.tagFilter)) return false;
        return !q || `${s.name} ${s.description} ${s.category}`.toLowerCase().includes(q);
      });
    },
    groups() {
      if (this.sortBy !== "name") {
        const key = this.sortBy === "size" ? (s) => -s.tokens : (s) => -s.tools.length;
        const items = [...this.visible].sort((a, b) => key(a) - key(b) || a.name.localeCompare(b.name));
        const id = this.sortBy === "size" ? "Largest first" : "In the most tools";
        return items.length ? [{ id, key: "sorted", items, shown: items.slice(0, CAP + (this.extra[id] || 0)) }] : [];
      }
      const by = new Map();
      for (const s of this.visible) {
        const id = this.grouping === "category" ? (s.category || "Other") : (/[a-z]/i.test(s.name[0]) ? s.name[0].toUpperCase() : "#");
        if (!by.has(id)) by.set(id, []);
        by.get(id).push(s);
      }
      return [...by.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([id, items]) => ({
        id, key: id.replace(/\W/g, "") || "other", items, shown: items.slice(0, CAP + (this.extra[id] || 0)),
      }));
    },
    skill() { return this.m && this.route.page === "skill" ? this.m.byName.get(this.route.name) || null : null; },
    treeAll() {
      if (!this.m) return [];
      const q = this.treeQuery.trim().toLowerCase();
      return q ? this.m.skills.filter((s) => s.name.toLowerCase().includes(q)) : this.m.skills;
    },
    treeList() {
      const list = this.treeAll.slice(0, 200);
      if (this.skill && !list.includes(this.skill) && !this.treeQuery) list.unshift(this.skill);
      return list;
    },
    treeHidden() { return Math.max(0, this.treeAll.length - 200); },
    cmp() {
      const s = this.skill;
      if (!s || !s.differing.length) return null;
      return s.differing.find((c) => c.scope === this.compareWith) || s.differing[0];
    },
    refCopy() { const s = this.skill; return s ? (s.copies.find(c=>c.path===this.readCopyPath) || s.ref.holders[0] || s.primary) : null; },
    docHtml() {
      const s = this.skill;
      if (!s) return "";
      const text = stripFrontmatter(this.bodyOf(this.refCopy));
      let marks = new Set();
      if (this.cmp && this.highlight && this.bodyReady(this.cmp)) {
        const theirs = new Set(stripFrontmatter(this.bodyOf(this.cmp)).split("\n").map((l) => l.trim()));
        marks = new Set(text.split("\n").map((l) => l.trim()).filter((l) => l && !theirs.has(l)));
      }
      return renderDoc(text, marks);
    },
    docPending() { return !!this.skill && !this.bodyReady(this.refCopy); },
    docError() { return this.bodyErrorOf(this.refCopy); },
    editable() { return !!this.skill && this.skill.copies.some((c) => c.state !== "broken"); },
    editTargets() { return this.skill ? this.skill.copies.filter((c) => c.state !== "broken") : []; },
    editError() {
      if (!this.edit) return "";
      if (!this.edit.desc.trim()) return "Add a short description so agents know when to use this skill.";
      if (this.edit.desc.length > 1024) return "Keep the description under 1024 characters.";
      return "";
    },
    editDirty() { return !!this.edit && (this.edit.desc !== this.edit.baseDesc || this.edit.body !== this.edit.baseBody || JSON.stringify(this.edit.metadata)!==JSON.stringify(this.edit.baseMetadata)); },
    shareTargets() {
      if (!this.skill || !this.m) return [];
      const have = new Set(this.skill.copies.map((c) => c.scope));
      return this.m.agents.filter((a) => !a.library && a.writable && !have.has(a.id));
    },
    lengthPct() {
      const c = this.skill && this.skill.primary;
      const a = c && this.agentOf(c.scope);
      return a && a.limit ? Math.round((this.skill.tokens / a.limit) * 1000) / 10 : 0;
    },
    brokenText() { const b = this.skill && this.skill.broken[0]; return b ? (BROKEN_WHY[b.kind] || BROKEN_WHY.invalid)[1] : ""; },
    brokenAction() { const p = this.m && this.skill ? this.m.problems.find((x) => x.id === "bad:" + this.skill.name) : null; return p ? p.action : "Show me how"; },
    matchLabel() {
      const n = this.skill ? this.skill.differing.length : 0;
      return n === 1 ? `Make ${this.agentOf(this.skill.differing[0].scope).name}'s copy match` : `Make ${n} copies match`;
    },
    mapBad() { return this.agentInfos.filter((i) => i.key !== "ok").length; },
    slots() {
      /* Agents sit on an ellipse around the hub, starting just right of top. */
      const n = this.agentInfos.length;
      return this.agentInfos.map((_, i) => {
        const ang = (Math.PI * 2 * (i + 0.5)) / n - Math.PI / 2;
        return [Math.round(50 + 34 * Math.cos(ang)), Math.round(Math.min(90, Math.max(34, 60 + 30 * Math.sin(ang))))];
      });
    },
    mapSel() {
      const infos = this.agentInfos;
      if (!infos.length) return null;
      return infos.find((i) => i.id === this.mapSelId) || infos.find((i) => i.key === "bad") || infos.find((i) => i.key === "warn") || infos[0];
    },
    peekLines() {
      if (!this.peek || !this.mapSel) return null;
      const s = this.m.byName.get(this.peek);
      const mine = s && s.copies.find((c) => c.scope === this.mapSel.id);
      const ref = s && s.ref.holders[0];
      if (!mine || !ref || !this.bodyReady(mine) || !this.bodyReady(ref)) return null;
      return changes(stripFrontmatter(this.bodyOf(mine)), stripFrontmatter(this.bodyOf(ref))).slice(0, 80);
    },
    queue() {
      if (!this.m) return [];
      const all = this.m.problems.filter((p) => !this.dismissed.includes(p.id));
      const rest = all.filter((p) => !this.skipped.includes(p.id));
      const sk = this.skipped.map((id) => all.find((p) => p.id === id)).filter(Boolean);
      const list = [...rest, ...sk];
      const i = list.findIndex((p) => p.id === this.front);
      if (i > 0) list.unshift(...list.splice(i, 1));
      return list;
    },
    cur() { return this.queue[0] || null; },
    curSkill() { return this.cur && this.cur.skill && this.m ? this.m.byName.get(this.cur.skill) : null; },
    curChanges() {
      const s = this.curSkill;
      if (!s || !this.cur || this.cur.key !== "warn") return null;
      const src = s.copies.find((c) => c.scope === (this.srcChoice || (s.ref.holders[0] || {}).scope));
      const tgt = s.copies.find((c) => c.scope === this.cur.agents[0] && c !== src) || s.differing[0];
      if (!src || !tgt || !this.bodyReady(src) || !this.bodyReady(tgt)) return null;
      return changes(stripFrontmatter(this.bodyOf(tgt)), stripFrontmatter(this.bodyOf(src))).slice(0, 60);
    },
    curBig() {
      if (!this.cur || this.cur.key !== "info" || !this.m) return [];
      const inf = this.m.info(this.cur.agent);
      return inf ? [...inf.on].sort((a, b) => b.tokens - a.tokens).slice(0, 4) : [];
    },
    themeLabel() { return { system: "follows your computer", light: "light", dark: "dark" }[this.theme]; },
    themeIcon() { return PATHS[{ system: "auto", light: "sun", dark: "moon" }[this.theme]]; },
    createTargets() { return this.m ? this.m.agents.filter((x) => x.writable) : []; },
    formErrors() {
      const f = this.dialog && this.dialog.form;
      if (!f) return {};
      const e = {};
      const n = f.name.trim();
      if (n && (!NAME_RE.test(n) || n.length > 64)) e.name = "Use lowercase letters, numbers and single hyphens, up to 64 characters.";
      else if (n && this.m && (this.m.byName.get(n) || { copies: [] }).copies.some((c) => c.scope === f.scope)) e.name = "A skill with this name already exists there.";
      if (f.desc.length > 1024) e.desc = "Keep the description under 1024 characters.";
      return e;
    },
    formInvalid() {
      const f = this.dialog && this.dialog.form;
      return !f || !f.name.trim() || !f.desc.trim() || !!this.formErrors.name || !!this.formErrors.desc;
    },
    progressBars() { return Math.min(this.done + this.queue.length, 12); },
  },
  watch: {
    libraryView(value) {try{localStorage.setItem("skillsmgr-v2-library-view",value);}catch(e){}},
    cur: { immediate: true, handler(c) { this.srcChoice = c && c.key === "warn" && this.m && this.m.byName.get(c.skill) ? (this.m.byName.get(c.skill).ref.ambiguous ? "" : (this.m.byName.get(c.skill).ref.holders[0] || {}).scope || "") : ""; if (c && c.key === "warn" && this.curSkill) this.ensureBodies(this.curSkill.copies); } },
    "route.name"() { this.compareWith = ""; this.loadSkillHistory(); this.primeBodies(); },
    skill(s) { if (!s && this.edit) this.edit = null; if (s) this.ensureBodies(s.copies); },
    mapSel() { this.ensureMapBodies(); },
  },
  methods: {
    enc: encodeURIComponent, plural, join, words, titleCase, shortPath, plainLine, renderDoc,
    fmt(n) {return Domain.numberFormatter(this.formatLocale==="system"?undefined:this.formatLocale).format(Number(n));},
    fmtDate(value) {const date=new Date(value);return Number.isNaN(date.getTime())?String(value||"Date unavailable"):Domain.dateFormatter(this.formatLocale==="system"?undefined:this.formatLocale,{dateStyle:"medium",timeStyle:"short"}).format(date);},
    preferencesChanged() {this.theme=savedPreference("skillsmgr-theme",THEMES,"system");this.formatLocale=savedPreference("skillsmgr-locale",["system","en-US","en-GB","en-IN"],"system");document.documentElement.dataset.textSize=savedPreference("skillsmgr-text-size",["standard","large"],"standard");this.applyTheme(); },
    skillTags(name) {return (this.catalog.tags || {})[name] || [];},
    openSource(record) { this.toolTarget=markRaw(record);location.hash="#/tools/source-update"; },
    inspectRecord(record) { this.query=record.name;this.filter="all";this.tagFilter="";this.agentFilter=record.scope||"all";this.libraryView="instances";location.hash="#/skills"; },
    openRecord(record) {this.toolTarget=markRaw(record);this.readCopyPath=record.physical_path||record.path||"";location.hash="#/skill/"+encodeURIComponent(record.name);},
    openCommands() {this.commandQuery="";this.openDialog({title:"Find a tool or action",commands:true,cancel:"Close"}); },
    commandGo(item) {const opener=this.opener;this.closeDialog();if(item.action==="create"){this.openCreate();this.opener=opener;}else if(item.action==="refresh")this.refresh();else location.hash=item.path;},
    agentOf(id) { return (this.m && this.m.agent(id)) || { ...FALLBACK_AGENT, name: id || "Unknown" }; },

    /* ----- loading ----- */
    async refresh() {
      this.loading = true; this.loadError = "";
      try {
        const [scopes, records, history] = await Promise.all([
          api("/api/scopes"), api("/api/skills?scope=all&body=0"), api("/api/history?limit=8").then(r=>{this.historyError="";return r;}).catch(e => {this.historyError=this.friendly(e.message);return []; }),
        ]);
        this.scopes=markRaw(scopes);this.records=markRaw(records);
        this.m = markRaw(Model.build(records, scopes, { suggested: 100 }));
        /* A reload produces fresh copies, so nothing is carried over from the
         * previous list: a body is re-read only where a view needs one. */
        this.bodies = {}; this.bodyInflight = {}; this.bodyErrors = {};
        this.history = Array.isArray(history) ? history : (history && history.history) || [];
        this.loadTrash();
        this.loadCatalog();
        this.primeBodies();
      } catch (e) {
        this.loadError = this.friendly(e.message || "The skills could not be read.");
      } finally { this.loading = false; }
    },
    async loadSkillHistory() {
      this.skillHistory = [];this.skillHistoryError="";
      if (this.route.page !== "skill") return;
      try {
        const rows = await api("/api/history?limit=20&name=" + encodeURIComponent(this.route.name));
        this.skillHistory = (Array.isArray(rows) ? rows : []).slice(0, 3);
      } catch (e) { this.skillHistoryError=this.friendly(e.message); }
    },
    async loadCatalog() { try {this.catalog=await api("/api/catalog");this.catalogError="";} catch(e){this.catalogError=this.friendly(e.message);} },

    /* ----- documents (fetched only where a view needs one) -----
     * The list request omits document bodies; this fetches one lazily. The
     * cache key includes the observed content hash, so a changed document
     * always refetches, and two callers asking for the same copy share one
     * request. A body is never assumed loaded: `bodyLoaded` tells an empty
     * document from one that has not been read yet. */
    bodyKey(c) { return `${c && c.scope ? c.scope : ""}\u0000${(c && c.name) || ""}\u0000${(c && c.hash) || ""}`; },
    bodyReady(c) { if (!c) return false; return !!c.bodyLoaded || Object.prototype.hasOwnProperty.call(this.bodies, this.bodyKey(c)); },
    bodyOf(c) { if (!c) return ""; if (c.bodyLoaded) return c.body || ""; const key = this.bodyKey(c); return Object.prototype.hasOwnProperty.call(this.bodies, key) ? this.bodies[key] : ""; },
    bodyErrorOf(c) { return c ? this.bodyErrors[this.bodyKey(c)] || "" : ""; },
    applyBody(c, body) { c.body = body; c.bodyLoaded = true; this.bodyErrors[this.bodyKey(c)] = ""; },
    async ensureBodies(copies) {
      /* A linked entry is deliberately not followed and an unaddressable name
       * cannot be fetched by name, so neither is requested. */
      const list = (Array.isArray(copies) ? copies : [copies])
        .filter((c) => c && !c.bodyLoaded && c.name && c.scope && c.state !== "link" && (!c.record || c.record.addressable !== false));
      await Promise.all(list.map(async (c) => {
        const key = this.bodyKey(c);
        try {
          let request = this.bodyInflight[key];
          if (!request) {
            request = api(`/api/skills/${encodeURIComponent(c.name)}?scope=${encodeURIComponent(c.scope)}`)
              .then((record) => (record && typeof record.body === "string" ? record.body : ""));
            this.bodyInflight[key] = request;
            request.then((body) => { this.bodies[key] = body; delete this.bodyErrors[key]; })
              .catch(() => { /* the caller reports the failure next to its own view */ })
              .finally(() => { if (this.bodyInflight[key] === request) delete this.bodyInflight[key]; });
          }
          this.applyBody(c, await request);
        } catch (e) { this.bodyErrors[key] = this.friendly(e && e.message ? e.message : "The document could not be read."); }
      }));
    },
    primeBodies() {
      if (!this.m) return;
      const page = this.route && this.route.page;
      if (page === "skill" && this.skill) return this.ensureBodies(this.skill.copies);
      if (page === "inbox" && this.curSkill) return this.ensureBodies(this.curSkill.copies);
      if (page === "map") return this.ensureMapBodies();
      return undefined;
    },
    /* The map computes line counts per visible row; load exactly the pairs it
     * compares instead of every copy of every skill. */
    ensureMapBodies() {
      const sel = this.mapSel;
      if (!sel) return undefined;
      const copies = [];
      for (const s of sel.differing.slice(0, 12)) {
        const mine = s.copies.find((c) => c.scope === sel.id), ref = s.ref.holders[0];
        if (mine) copies.push(mine);
        if (ref && ref !== mine) copies.push(ref);
      }
      return this.ensureBodies(copies);
    },

    /* ----- search / filter ----- */
    searchInput(v) { this.query = v; if (this.route.page !== "skills" && v.trim()) location.hash = "#/skills"; this.extra = {}; },
    searchSubmit() { if (this.route.page !== "skills") location.hash = "#/skills"; },
    capReset() { this.extra = {}; },
    showMore(id) { this.extra = { ...this.extra, [id]: (this.extra[id] || 0) + 96 }; },
    clearFilters() { this.query = ""; this.filter = "all"; this.agentFilter = "all"; this.tagFilter="";this.extra = {}; this.$nextTick(() => { const q = document.getElementById("q"); if (q) q.focus(); }); },
    pickAgent(id) { this.agentFilter = id; this.filter = "all"; this.query = ""; this.extra = {}; },
    skipToContent() { const h = document.getElementById("h1") || this.$refs.main; if (h) h.focus(); },
    focusH1() { this.$nextTick(() => { const h = document.getElementById("h1"); if (h) h.focus({ preventScroll: true }); }); },

    /* ----- toasts & dialogs ----- */
    friendly(msg) {
      let s = String(msg || "Something went wrong.");
      if (/invalid archive|not a gzip|ReadError|zipfile/i.test(s)) return "That file is not a backup archive. Choose a .tar.gz, .tar or .zip file made by Skills Manager.";
      if (/not valid UTF-8/i.test(s)) return "One of the copies is not saved as UTF-8 text. Keep a copy of the original file, then open it in a text editor and save it as UTF-8 before editing it here.";
      if (/traceback|(?:UnicodeDecode|Recursion|Permission|FileNotFound|Operational)Error|\[Errno \d+\]/i.test(s)) return "The operation could not be completed. Refresh and try again; check that the skill files are readable and writable.";
      return s.replace(/(?:\/[^\s'":]+)+\/([^\s'":/]+)/g, "$1").replace(/\s*\(byte 0x[0-9a-f]+ at offset \d+\)/i, "");
    },
    toast(text, opts = {}) {
      if (opts.err) text = this.friendly(text);
      const t = { id: ++this.toastSeq, text, err: !!opts.err, undo: opts.undo || null, onUndo: opts.onUndo || null };
      this.toasts.push(t); this.live = text + (t.undo ? " Undo is available." : "");
      this.armToast(t, t.undo ? 20000 : (t.err ? 7000 : 4000));
    },
    /* WCAG 2.2.1: a toast with an action never times out while the reader is
     * on it; it waits until focus and pointer leave, then gets its time again. */
    armToast(t, ms) {
      clearTimeout(t.timer);
      t.ms = ms;
      t.timer = setTimeout(() => { if (!t.held) this.toasts = this.toasts.filter((x) => x.id !== t.id); }, ms);
    },
    holdToast(t, held) {
      t.held = held;
      if (!held) this.armToast(t, Math.max(t.ms || 4000, 6000));
    },
    async runUndo(t) {
      this.toasts = this.toasts.filter((x) => x.id !== t.id);
      this.busy = true;
      try { await t.undo(); await this.refresh(); if (t.onUndo) t.onUndo(); this.toast("Undone"); } catch (e) { await this.refresh(); if (t.onUndo) t.onUndo(); this.toast("Couldn't undo: " + e.message, { err: true }); } finally { this.busy = false; }
    },
    openDialog(d) { this.opener = document.activeElement; this.dialog = { cancel: "Cancel", ...d }; this.$nextTick(() => { const d = this.$refs.dlg; const b = d && (d.querySelector("input:not(.sr-only), select") || d.querySelector("button:not(.sr-only)")); if (b) b.focus(); }); },
    closeDialog() { if(this.busy)return;this.dialog = null; this.$nextTick(() => { if (this.opener && this.opener.isConnected) this.opener.focus(); }); },
    async confirmDialog() {
      if(this.busy || this.dialog?.templateLoading)return;
      if (this.dialog && this.dialog.form && this.formInvalid) {
        const f = this.dialog.form;
        this.live = this.formErrors.name || this.formErrors.desc || (!f.name.trim() ? "Add a name." : "Add a description.");
        return;
      } const d = this.dialog; if(!d?.form)this.dialog = null; if (d && d.onConfirm) await d.onConfirm(d); this.$nextTick(() => { if (!this.dialog && this.opener && this.opener.isConnected) this.opener.focus(); }); },
    dialogKeys(e) {
      if (e.key === "Escape") { e.stopPropagation(); this.closeDialog(); return; }
      if (e.key !== "Tab") return;
      const f = [...this.$refs.dlg.querySelectorAll("button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]")].filter(el=>el.offsetParent!==null);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    },

    /* ----- writes (every one goes through the existing REST routes) ----- */
    async snapshotIds(name, scope) {
      const r = await api(`/api/history?name=${encodeURIComponent(name)}&scope=${encodeURIComponent(scope)}&snapshots=1`);
      if (!r || !Array.isArray(r.snapshots)) throw new Error("Recovery snapshots could not be read. Refresh and try again.");
      return r.snapshots;
    },
    /* Copy `from` over each target. The previous text of each target is
     * snapshotted by the backend, which is what makes Undo possible. */
    async doSync(name, from, tos) {
      const before = {}, prior = {};
      for (const t of tos) {
        before[t] = new Set(await this.snapshotIds(name, t));
        prior[t] = await api(`/api/skills/${encodeURIComponent(name)}?scope=${encodeURIComponent(t)}`).catch(() => null);
      }
      const res = await api("/api/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, from_scope: from, to_scopes: tos, force: true }) });
      const synced = res.synced || [];
      const undo = []; let manualRecovery = false;
      for (const t of synced) {
        let after;
        try { after = await this.snapshotIds(name, t); } catch (e) { manualRecovery = true; continue; }
        const fresh = after.filter((id) => !before[t].has(id));
        if (fresh.length === 1 && prior[t] && !prior[t].decode_error) undo.push([t, fresh[0], !!prior[t].disabled]);
        else manualRecovery = true;
      }
      return { synced, skipped: res.skipped || [], undo, manualRecovery };
    },
    async restoreSyncText(name, scope, snapshot, wasDisabled) {
      const target = `/api/skills/${encodeURIComponent(name)}`;
      const query = `?scope=${encodeURIComponent(scope)}`;
      const current = await api(target + query), initiallyDisabled = !!current.disabled;
      let restored = false;
      try {
        if (initiallyDisabled) await api(target + "/enable" + query, { method: "POST" });
        await api(`/api/trash/${encodeURIComponent(name)}?snapshot=${encodeURIComponent(snapshot)}&scope=${encodeURIComponent(scope)}`, { method: "POST" });
        restored = true;
      } finally {
        const disabled = restored ? wasDisabled : initiallyDisabled;
        const latest = await api(target + query);
        if (!!latest.disabled !== disabled) await api(target + (disabled ? "/disable" : "/enable") + query, { method: "POST" });
      }
    },
    undoFor(name, entries) {
      if (entries.some((e) => e.manualRecovery)) return null;
      const list = entries.flatMap((e) => e.undo.map(([scope, snap, off]) => [e.name || name, scope, snap, off]));
      if (!list.length) return null;
      return async () => { for (const [n, scope, snap, off] of list) await this.restoreSyncText(n, scope, snap, off); };
    },
    skipText(skipped) { return skipped.length ? ` ${skipped.length} could not be changed: ${skipped.map((s) => this.friendly(s.reason)).slice(0, 2).join("; ")}.` : ""; },
    /* A copy's observed token count is what its agent would spend on it; say so
     * when a switch changes that, and stay silent when the count is unknown. */
    tokenClause(tokens, turning) {
      const n = Number(tokens) || 0;
      if (n <= 0) return "";
      return turning === "off" ? ` — frees about ${this.fmt(n)} tokens of that agent's budget` : ` — uses about ${this.fmt(n)} tokens`;
    },

    async syncDiffering() {
      const s = this.skill;
      if (!s || s.ref.ambiguous) return;
      const from = s.ref.holders[0].scope;
      await this.runSync(s.name, from, s.differing.map((c) => c.scope), `${s.name} now matches in`);
    },
    async runSync(name, from, tos, label, onUndo) {
      this.busy = true;
      try {
        const r = await this.doSync(name, from, tos);
        const undo = this.undoFor(name, [r]);
        await this.refresh();
        this.toast(r.synced.length ? `${label} ${join(r.synced.map((id) => this.agentOf(id).name))}.${this.skipText(r.skipped)}${r.manualRecovery ? ' Undo is unavailable for this sync; recovery needs your backup or retained snapshots.' : ''}` : "Nothing was changed." + this.skipText(r.skipped), { err: !r.synced.length, undo: r.synced.length ? undo : null, onUndo });
        return r.synced.length ? r : null;
      } catch (e) { this.toast(e.message, { err: true }); return null; } finally { this.busy = false; }
    },
    async toggleCopy(c) {
      const name = this.skill.name, to = c.state === "on" ? "disable" : "enable";
      const clause = this.tokenClause(c.tokens, to === "disable" ? "off" : "on");
      this.busy = true;
      try {
        await api(`/api/skills/${encodeURIComponent(name)}/${to}?scope=${encodeURIComponent(c.scope)}`, { method: "POST" });
        await this.refresh();
        const back = to === "disable" ? "enable" : "disable";
        this.toast(`${name} turned ${to === "disable" ? "off" : "on"} in ${this.agentOf(c.scope).name}.${clause}`, { undo: async () => { await api(`/api/skills/${encodeURIComponent(name)}/${back}?scope=${encodeURIComponent(c.scope)}`, { method: "POST" }); } });
      } catch (e) { this.toast(e.message, { err: true }); await this.refresh(); } finally { this.busy = false; }
    },
    async allOn() {
      const s = this.skill; this.busy = true; const turned = [];
      const gained = s.copies.filter((x) => x.state === "off").reduce((n, x) => n + (Number(x.tokens) || 0), 0);
      try {
        for (const c of s.copies.filter((x) => x.state === "off")) { await api(`/api/skills/${encodeURIComponent(s.name)}/enable?scope=${encodeURIComponent(c.scope)}`, { method: "POST" }); turned.push(c.scope); }
        await this.refresh();
        const clause = gained > 0 ? ` — uses about ${this.fmt(gained)} tokens across ${plural(turned.length, "agent")}` : "";
        this.toast(`${s.name} turned on everywhere.${clause}`, { undo: async () => { for (const sc of turned) await api(`/api/skills/${encodeURIComponent(s.name)}/disable?scope=${encodeURIComponent(sc)}`, { method: "POST" }); } });
      } catch (e) { this.toast(e.message, { err: true }); await this.refresh(); } finally { this.busy = false; }
    },
    async turnOffIn(s, scope) {
      this.busy = true; const name = s.name;
      const c = s.copies.find((x) => x.scope === scope);
      const clause = this.tokenClause(c && c.tokens, "off");
      try {
        await api(`/api/skills/${encodeURIComponent(name)}/disable?scope=${encodeURIComponent(scope)}`, { method: "POST" });
        await this.refresh();
        this.toast(`${name} turned off in ${this.agentOf(scope).name}.${clause}`, { undo: async () => { await api(`/api/skills/${encodeURIComponent(name)}/enable?scope=${encodeURIComponent(scope)}`, { method: "POST" }); } });
      } catch (e) { this.toast(e.message, { err: true }); } finally { this.busy = false; }
    },
    fixSkillBad() {
      const p = this.m.problems.find((x) => x.id === "bad:" + this.skill.name);
      if (p) this.fixBad(p);
    },
    fixBad(p, undoHook) {
      if (p.fixable) return this.runSync(p.skill, p.source, p.agents, `${p.skill} was replaced in`, undoHook);
      const s = this.m.byName.get(p.skill);
      this.openDialog({ title: p.title, lines: [p.text], how: p.how, paths: s.broken.map((c) => shortPath(c.path)), cancel: "Close" });
      return null;
    },
    openShare() {
      const s = this.skill, from = this.refCopy.scope;
      this.openDialog({
        title: `Add “${s.name}” to another agent`, lines: ["Choose where to copy it. The copy comes from " + this.agentOf(from).name + ". Its file enabled or disabled state and companion files are copied too."],
        picks: this.shareTargets.map((a) => ({ id: a.id, label: a.name, path: a.path })), chosen: this.shareTargets.length === 1 ? [this.shareTargets[0].id] : [], confirm: "Add",
        onConfirm: (d) => this.runSync(s.name, from, d.chosen, `${s.name} was added to`),
      });
    },
    openTrash() {
      const s = this.skill;
      this.openDialog({
        title: `Move “${s.name}” to the trash?`, danger: true, confirm: "Move to trash",
        lines: ["Choose the places to remove it from. Each agent keeps its own trash folder, so restoring from inside the app only works for your library."],
        picks: s.copies.map((c) => ({ id: c.scope, label: this.agentOf(c.scope).name, path: shortPath(c.path) })), chosen: s.copies.length === 1 ? [s.copies[0].scope] : [],
        onConfirm: async (d) => {
          this.busy = true;
          try {
            for (const sc of d.chosen) await api(`/api/skills/${encodeURIComponent(s.name)}?scope=${encodeURIComponent(sc)}&purge=0`, { method: "DELETE" });
            await this.refresh();
            this.toast(`${s.name} moved to the trash in ${join(d.chosen.map((id) => this.agentOf(id).name))}.`);
            if (!this.m.byName.get(s.name)) location.hash = "#/skills";
          } catch (e) { this.toast(e.message, { err: true }); await this.refresh(); } finally { this.busy = false; }
        },
      });
    },
    openPermanentDelete() {const skill=this.skill;if(!skill)return;this.openDialog({title:`Permanently delete “${skill.name}”?`,danger:true,confirm:"Delete permanently",lines:["This removes the selected copies without moving them to trash. There is no Undo or trash restore for this action."],picks:skill.copies.filter(c=>c.record.addressable!==false&&c.state!=="link"&&this.agentOf(c.scope).writable).map(c=>({id:c.scope,label:this.agentOf(c.scope).name,path:shortPath(c.path)})),chosen:[],onConfirm:async d=>{this.busy=true;try{for(const scope of d.chosen)await api(`/api/skills/${encodeURIComponent(skill.name)}?scope=${encodeURIComponent(scope)}&purge=1`,{method:"DELETE"});await this.refresh();this.toast("Selected copies permanently deleted.");if(!this.m.byName.get(skill.name))location.hash="#/skills";}catch(e){await this.refresh();this.toast(e.message,{err:true});}finally{this.busy=false;}}});},

    /* ----- create, recovery, theme, help ----- */
    openCreate() {
      const first = this.createTargets.find((x) => !x.library) || this.createTargets[0];
      this.openDialog({
        title: "New skill", form: { name: "", desc: "", scope: first ? first.id : "global", category:"",version:"",license:"",compatibility:"",allowed_tools:"",body:"## When to use\n\nDescribe the situations where an agent should use this skill.\n\n## Steps\n\n1. \n",template:"" }, confirm: "Create skill",
        onConfirm: async (d) => {
          const f = d.form; this.busy = true;
          try {
            await api("/api/skills?scope=" + encodeURIComponent(f.scope), { method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ name: f.name.trim(), description: f.desc.trim(), category:f.category,version:f.version,license:f.license,compatibility:f.compatibility,allowed_tools:f.allowed_tools,body:f.body.replaceAll("{name}",f.name.trim()) }) });
            this.dialog=null;
            await this.refresh();
            this.toast(`${f.name.trim()} created in ${this.agentOf(f.scope).name}.`);
            location.hash = "#/skill/" + encodeURIComponent(f.name.trim());
          } catch (e) { d.error=this.friendly(e.message);this.live=d.error; } finally { this.busy = false; }
        },
      });
      const dialog=this.dialog;
      api("/api/templates").then(r=>{if(this.dialog===dialog)this.createTemplates=r.templates||[];}).catch(e=>{if(this.dialog===dialog)dialog.error="Templates unavailable: "+this.friendly(e.message);});
    },
    async loadCreateTemplate() {const d=this.dialog;if(!d?.form?.template)return;const name=d.form.template;d.templateLoading=true;try{const t=await api("/api/templates/"+encodeURIComponent(name));if(this.dialog===d&&d.form.template===name)d.form.body=stripFrontmatter(t.body||"");}catch(e){if(this.dialog===d)d.error=this.friendly(e.message);}finally{if(this.dialog===d)d.templateLoading=false;}},
    async loadTrash() { this.trashLoading=true;try { this.trash = await api("/api/trash");this.trashError=""; } catch (e) { this.trashError=this.friendly(e.message); } finally {this.trashLoading=false;} },
    async restoreTrash(t) {
      this.busy = true;
      try { await api("/api/trash/" + encodeURIComponent(t.name), { method: "POST" }); await this.refresh(); this.toast(`${t.name} restored to your library.`); }
      catch (e) { this.toast(e.message, { err: true }); } finally { this.busy = false; }
    },
    openPurge() {
      this.openDialog({ title: "Empty the trash?", danger: true, confirm: "Delete forever", lines: [`${plural(this.trash.length, "skill")} will be deleted permanently. This cannot be undone.`],
        onConfirm: async () => { this.busy = true; try { await api("/api/trash/purge", { method: "POST" }); await this.loadTrash(); this.toast("The trash was emptied."); } catch (e) { this.toast(e.message, { err: true }); } finally { this.busy = false; } } });
    },
    async exportBackup(full) {
      this.busy = true;
      try {
        const { blob, filename } = await Domain.apiBlob("/api/export" + (full ? "?full=1" : ""));
        const url = URL.createObjectURL(blob), a = document.createElement("a");
        a.href = url; a.download = filename || "skills-backup.tar.gz"; document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 2000);
        this.toast("Backup downloaded.");
      } catch (e) { this.toast(e.message, { err: true }); } finally { this.busy = false; }
    },
    async doImport() {
      const f = this.importFile; if (!f || this.busy) return;
      this.busy = true;
      try {
        const r = await api(`/api/import?filename=${encodeURIComponent(f.name)}&force=${this.importForce ? 1 : 0}&full=${this.importFull ? 1 : 0}`, { method: "PUT", body: f });
        this.importResult=r;
        await this.refresh(); this.importFile = null;
        const input = document.getElementById("imp-file"); if (input) input.value = "";
        const n = (r.imported || []).length, k = (r.skipped || []).length;
        this.toast(`${plural(n, "skill")} loaded.${k ? " " + plural(k, "was", "were") + " already there and kept." : ""}`, { err: !n && !k });
      } catch (e) { this.toast(e.message, { err: true }); } finally { this.busy = false; }
    },
    applyTheme() {
      const root = document.documentElement;
      const dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.dataset.themePreference = this.theme;
      root.dataset.theme = this.theme === "system" ? (dark ? "dark" : "light") : this.theme;
    },
    cycleTheme() {
      this.theme = THEMES[(THEMES.indexOf(this.theme) + 1) % THEMES.length];
      try { localStorage.setItem("skillsmgr-theme", this.theme); } catch (e) { /* storage may be blocked */ }
      this.applyTheme(); this.live = "Theme: " + this.themeLabel;
    },
    openHelp() {
      this.openDialog({ title: "Keyboard shortcuts", cancel: "Close", keys: [
        [["/"], "Find a skill"], [["?"], "Show this list"], [["Esc"], "Close a dialog"],
        [["Ctrl/Cmd", "K"], "Find tools and actions"],
        [["Ctrl", "S"], "Save while editing"], [["Enter"], "Fix the item in the Inbox"], [["S"], "Skip it for now"],
      ] });
    },

    /* ----- editing ----- */
    async startEdit() {
      const s = this.skill, c = this.refCopy;
      if (!s || !c) return;
      /* The editor must never open on a body that has not loaded: read it
       * first, and abandon silently if the reader navigated away meanwhile. */
      await this.ensureBodies([c]);
      if (this.skill !== s || this.route.page !== "skill" || this.refCopy !== c) return;
      if (!this.bodyReady(c)) { this.toast(this.bodyErrorOf(c) || "The document could not be read. Try again.", { err: true }); return; }
      const body = stripFrontmatter(this.bodyOf(c));
      const metadata={category:c.record.category||"",version:c.record.version||"",license:c.record.license||"",compatibility:Domain.formatCompat(c.record.compatibility),allowed_tools:Domain.formatTools(c.record.allowed_tools)};
      this.edit = { name: s.name, desc: c.description, baseDesc: c.description, body, baseBody: body, metadata,baseMetadata:{...metadata},tab: "write", targets: this.readCopyPath ? [c.scope] : this.editTargets.map((x) => x.scope) };
      this.$nextTick(() => { this.growArea(); const d = document.getElementById("ed-desc"); if (d) d.focus(); });
    },
    async cancelEdit() {
      if (this.editDirty) return this.openDialog({ title: "Discard your changes?", lines: [`You have unsaved changes to “${this.edit.name}”.`], cancel: "Keep editing", confirm: "Discard changes", danger: true, onConfirm: () => { this.edit = null; } });
      this.edit = null; return null;
    },
    async saveEdit() {
      const e = this.edit; if (!e || this.editError) return;
      this.busy = true; const saved = [];
      try {
        const fields = {};
        if(e.desc!==e.baseDesc)fields.description=e.desc;
        if(e.body!==e.baseBody)fields.body=e.body;
        for(const key of Object.keys(e.metadata))if(e.metadata[key]!==e.baseMetadata[key])fields[key]=e.metadata[key];
        const snaps = {};
        for (const sc of e.targets) snaps[sc] = new Set(await this.snapshotIds(e.name, sc));
        for (const sc of e.targets) {
          await api(`/api/skills/${encodeURIComponent(e.name)}?scope=${encodeURIComponent(sc)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields) });
          const fresh = (await this.snapshotIds(e.name, sc)).find((id) => !snaps[sc].has(id));
          if (fresh) saved.push([sc, fresh]);
        }
        this.edit = null;
        await this.refresh();
        const undo = saved.length ? async () => { for (const [sc, snap] of saved) await api(`/api/trash/${encodeURIComponent(e.name)}?snapshot=${encodeURIComponent(snap)}&scope=${encodeURIComponent(sc)}`, { method: "POST" }); } : null;
        this.toast(`${e.name} saved to ${plural(e.targets.length, "place")}.`, { undo });
      } catch (err) { this.toast(err.message, { err: true }); await this.refresh(); } finally { this.busy = false; }
    },
    growArea() { const a = this.$refs.edbody; if (a) { a.style.height = "auto"; a.style.height = Math.max(420, a.scrollHeight + 4) + "px"; } },
    insertText(prefix) {
      const a = this.$refs.edbody; if (!a) return;
      const at = a.selectionStart, ls = this.edit.body.lastIndexOf("\n", at - 1) + 1;
      this.edit.body = this.edit.body.slice(0, ls) + prefix + this.edit.body.slice(ls);
      this.$nextTick(() => { a.focus(); a.setSelectionRange(at + prefix.length, at + prefix.length); });
    },
    wrapText(mark) {
      const a = this.$refs.edbody; if (!a) return;
      const s = a.selectionStart, e2 = a.selectionEnd, b = this.edit.body;
      this.edit.body = b.slice(0, s) + mark + b.slice(s, e2) + mark + b.slice(e2);
      this.$nextTick(() => { a.focus(); a.setSelectionRange(s + mark.length, e2 + mark.length); });
    },

    /* ----- sync map ----- */
    wireColor(k) { return { ok: "#22a05a", warn: "#d97706", bad: "#dc2626" }[k]; },
    mid(i, _axis, dir) {
      const [x, y] = this.slots[i], mx = (x + 50) / 2, my = (y + 56) / 2;
      return [mx + dir * (x - 50) * 0.08, my + dir * (y - 56) * 0.08];
    },
    tagFor(inf, plain) {
      return inf.key === "bad" ? `${plural(inf.broken.length, "skill")} can't be read` : inf.key === "warn" ? `${plural(inf.differing.length, "copy", "copies")} ${inf.differing.length === 1 ? "differs" : "differ"}` : "matches";
    },
    selectMap(id) { this.mapSelId = id; this.mapPicked = this.mapDefaults(id); this.peek = null; },
    mapDefaults(id) { const i = this.m.info(id); return i ? i.differing.filter((s) => !s.ref.ambiguous).map((s) => s.name) : []; },
    togglePick(n) { this.mapPicked = this.mapPicked.includes(n) ? this.mapPicked.filter((x) => x !== n) : [...this.mapPicked, n]; },
    togglePeek(s) { const next = this.peek === s.name ? null : s.name; this.peek = next; if (next) { const mine = s.copies.find((c) => c.scope === this.mapSel.id); return this.ensureBodies([mine, s.ref.holders[0]]); } return undefined; },
    diffCount(s, scope) {
      const mine = s.copies.find((c) => c.scope === scope), ref = s.ref.holders[0];
      if (!mine || !ref || !this.bodyReady(mine) || !this.bodyReady(ref)) return null;
      return changes(stripFrontmatter(this.bodyOf(mine)), stripFrontmatter(this.bodyOf(ref))).filter((l) => l.t !== "same").length;
    },
    brokenShort(s, scope) { const c = s.copies.find((x) => x.scope === scope); return (BROKEN_WHY[c && c.kind] || BROKEN_WHY.invalid)[0]; },
    async syncPicked() {
      const inf = this.mapSel, picked = this.mapPicked.filter((n) => inf.differing.some((s) => s.name === n));
      if (!picked.length) return;
      this.busy = true; const results = [];
      try {
        for (const n of picked) { const s = this.m.byName.get(n); const r = await this.doSync(n, s.ref.holders[0].scope, [inf.id]); r.name = n; results.push(r); }
        const undo = this.undoFor("", results);
        await this.refresh(); this.mapPicked = this.mapDefaults(inf.id);
        const ok = results.filter((r) => r.synced.length).length;
        this.toast(`${plural(ok, "skill")} now ${ok === 1 ? "matches" : "match"} in ${inf.agent.name}.${results.some((r) => r.manualRecovery) ? ' Undo is unavailable for this sync; recovery needs your backup or retained snapshots.' : ''}`, { undo });
      } catch (e) { this.toast(e.message, { err: true }); await this.refresh(); } finally { this.busy = false; }
    },

    /* ----- inbox ----- */
    async fixCurrent() {
      const p = this.cur; if (!p || this.busy) return null;
      if (p.key === "warn" && !this.srcChoice) return null; /* nothing chosen yet: same as the disabled button */
      /* Undo of a fix puts the item back in the queue, since the file is back. */
      const back = () => { if (!this.m.problems.some((item) => item.id === p.id)) return; this.dismissed = this.dismissed.filter((id) => id !== p.id); this.done = Math.max(0, this.done - 1); };
      let ok = false;
      if (p.key === "warn") {
        const s = this.curSkill, src = this.srcChoice;
        const srcHash = (s.copies.find((c) => c.scope === src) || {}).hash;
        const tos = s.copies.filter((c) => c.state !== "broken" && c.hash && c.hash !== srcHash).map((c) => c.scope);
        ok = !!(await this.runSync(p.skill, src, tos, `${p.skill} now matches in`, back));
      } else if (p.key === "bad") {
        if (!p.fixable) return this.fixBad(p);
        ok = !!(await this.fixBad(p, back));
      } else {
        /* A note acknowledged is not a fix: it leaves the queue without counting. */
        this.dismissed.push(p.id); this.skipped = this.skipped.filter((id) => id !== p.id); if (this.front === p.id) this.front = null;
        this.toast("Hidden until you reload."); return null;
      }
      if (ok) { this.dismissed.push(p.id); this.skipped = this.skipped.filter((id) => id !== p.id); if (this.front === p.id) this.front = null; this.done++; }
      return null;
    },
    skipCurrent() { if (!this.cur) return; const id = this.cur.id; this.skipped = [...this.skipped.filter((x) => x !== id), id]; this.front = null; this.focusH1(); },
  },
  mounted() {
    this.refresh();
    window.addEventListener("hashchange", () => {
      const next = parseRoute();
      if (this.edit && this.editDirty && !(next.page === "skill" && next.name === this.edit.name)) {
        const target = location.hash;
        location.hash = "#/skill/" + encodeURIComponent(this.edit.name);
        return this.openDialog({ title: "Discard your changes?", lines: [`You have unsaved changes to “${this.edit.name}”.`], cancel: "Keep editing", confirm: "Discard changes", danger: true,
          onConfirm: () => { this.edit = null; location.hash = target; } });
      }
      this.route = next; if (next.page !== "skill") this.edit = null;
      this.primeBodies();
      document.title = (next.page === "skill" ? next.name : TITLES[next.page]) + " · Skills Manager";
      window.scrollTo(0, 0); this.focusH1();
    });
    window.addEventListener("beforeunload", (e) => { if (this.editDirty) { e.preventDefault(); e.returnValue = ""; } });
    document.addEventListener("keydown", (e) => {
      const t = e.target, typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
      if(document.querySelector("dialog[open]"))return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase()==="k" && !this.dialog && !document.querySelector("dialog[open]")) {e.preventDefault();this.openCommands();}
      if (e.key === "?" && !typing && !this.dialog) { e.preventDefault(); this.openHelp(); }
      if (e.key === "/" && !typing && !this.dialog && !e.ctrlKey && !e.metaKey) { e.preventDefault(); this.$refs.gsearch.focus(); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && this.edit) { e.preventDefault(); this.saveEdit(); }
      if (this.route.page === "inbox" && this.cur && !typing && !this.dialog && !e.ctrlKey && !e.metaKey && !e.altKey) {
        /* Shortcuts never fire from a link, button or field: Enter on "Open
         * skill" must open the skill, not run the fix (screen-reader E2E SR-1). */
        const onControl = t && t.closest && t.closest("a, button, input, select, textarea, summary, [role=button], [contenteditable]");
        const inScope = !t || t === document.body || (t.closest && t.closest("#main"));
        if (!onControl && inScope) {
          if (e.key === "s" || e.key === "S") { e.preventDefault(); this.skipCurrent(); }
          else if (e.key === "Enter") { e.preventDefault(); this.fixCurrent(); }
        }
      }
    });
    document.title = (this.route.page === "skill" ? this.route.name : TITLES[this.route.page]) + " · Skills Manager";
    window.addEventListener("storage",event=>{if(["skillsmgr-theme","skillsmgr-text-size","skillsmgr-locale"].includes(event.key))this.preferencesChanged();});
    this.loadSkillHistory();
    this.applyTheme();
    /* The filesystem is the source of truth and other tools edit it, so re-read
     * it whenever the tab comes back into view (at most every 15 s, never
     * while an edit is open so a refresh cannot disturb unsaved work). */
    let lastLoad = Date.now();
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState !== "visible" || this.edit || this.busy || Date.now() - lastLoad < 15000) return;
      lastLoad = Date.now(); this.refresh();
    });
    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const on = () => { if (this.theme === "system") this.applyTheme(); };
      if (mq.addEventListener) mq.addEventListener("change", on); else if (mq.addListener) mq.addListener(on);
    }
  },
  updated() { if (this.edit && this.edit.tab === "write") this.growArea(); },
});

app.component("ic", {
  props: { name: String, cls: { type: String, default: "" } },
  computed: { path() { return PATHS[this.name] || PATHS.info; } },
  template: '<svg :class="[\'i\', cls]" viewBox="0 0 24 24" aria-hidden="true" v-html="path"></svg>',
});
app.component("logo", {
  props: { agent: Object, size: { type: String, default: "" } },
  template: '<span :class="[\'logo\', size]" :style="{ background: agent.color }" aria-hidden="true">{{ agent.initials }}</span>',
});

app.component("library-tools", window.SkillsV2LibraryTools);
app.component("tool-center", window.SkillsV2ToolCenter);

app.mount("#app");
