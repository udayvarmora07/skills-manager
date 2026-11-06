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
  return ["skills", "map", "inbox", "recovery"].includes(p) ? { page: p } : { page: "home" };
}
const TITLES = { home: "Home", skills: "Skills", map: "Sync map", inbox: "Inbox", recovery: "Recovery" };
const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const THEMES = ["system", "light", "dark"];

const app = createApp({
  data() {
    return {
      route: parseRoute(), m: null, loading: true, loadError: "", history: [], busy: false,
      query: "", filter: "all", agentFilter: "all", extra: {},
      front: null, skipped: [], dismissed: [], done: 0, srcChoice: "",
      treeQuery: "", edit: null, highlight: true, compareWith: "",
      mapSelId: "", mapPicked: [], peek: null,
      trash: [], importFile: null, importForce: false,
      theme: THEMES.includes(localStorage.getItem("skillsmgr-theme")) ? localStorage.getItem("skillsmgr-theme") : "system",
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
    careCount() { return this.m ? this.m.skills.filter((s) => s.status.key === "warn" || s.status.key === "bad").length : 0; },
    visible() {
      if (!this.m) return [];
      const q = this.query.trim().toLowerCase();
      return this.m.skills.filter((s) => {
        const k = s.status.key;
        if (k === "note") return false; /* not a skill: listed in the Inbox only */
        if (this.filter === "care" && k !== "warn" && k !== "bad") return false;
        if (this.filter === "off" && k !== "off") return false;
        if (this.agentFilter !== "all" && !s.copies.some((c) => c.scope === this.agentFilter)) return false;
        return !q || `${s.name} ${s.description} ${s.category}`.toLowerCase().includes(q);
      });
    },
    groups() {
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
    refCopy() { const s = this.skill; return s ? (s.ref.holders[0] || s.primary) : null; },
    docHtml() {
      const s = this.skill;
      if (!s) return "";
      const text = stripFrontmatter(this.refCopy.body || "");
      let marks = new Set();
      if (this.cmp && this.highlight) {
        const theirs = new Set(stripFrontmatter(this.cmp.body || "").split("\n").map((l) => l.trim()));
        marks = new Set(text.split("\n").map((l) => l.trim()).filter((l) => l && !theirs.has(l)));
      }
      return renderDoc(text, marks);
    },
    editable() { return !!this.skill && this.skill.copies.some((c) => c.state !== "broken"); },
    editTargets() { return this.skill ? this.skill.copies.filter((c) => c.state !== "broken") : []; },
    editError() {
      if (!this.edit) return "";
      if (!this.edit.desc.trim()) return "Add a short description so agents know when to use this skill.";
      if (this.edit.desc.length > 1024) return "Keep the description under 1024 characters.";
      return "";
    },
    editDirty() { return !!this.edit && (this.edit.desc !== this.edit.baseDesc || this.edit.body !== this.edit.baseBody); },
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
      return mine && ref ? changes(stripFrontmatter(mine.body), stripFrontmatter(ref.body)).slice(0, 80) : null;
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
      return src && tgt ? changes(stripFrontmatter(tgt.body), stripFrontmatter(src.body)).slice(0, 60) : null;
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
    cur: { immediate: true, handler(c) { this.srcChoice = c && c.key === "warn" && this.m && this.m.byName.get(c.skill) ? (this.m.byName.get(c.skill).ref.ambiguous ? "" : (this.m.byName.get(c.skill).ref.holders[0] || {}).scope || "") : ""; } },
    "route.name"() { this.compareWith = ""; this.loadSkillHistory(); },
    skill(s) { if (!s && this.edit) this.edit = null; },
  },
  methods: {
    enc: encodeURIComponent, plural, join, words, titleCase, shortPath, plainLine, renderDoc,
    fmt(n) { return Number(n).toLocaleString("en-US"); },
    agentOf(id) { return (this.m && this.m.agent(id)) || { ...FALLBACK_AGENT, name: id || "Unknown" }; },

    /* ----- loading ----- */
    async refresh() {
      this.loading = true; this.loadError = "";
      try {
        const [scopes, records, history] = await Promise.all([
          api("/api/scopes"), api("/api/skills?scope=all"), api("/api/history?limit=8").catch(() => []),
        ]);
        this.m = markRaw(Model.build(records, scopes, { suggested: 100 }));
        this.history = Array.isArray(history) ? history : (history && history.history) || [];
        this.loadTrash();
      } catch (e) {
        this.loadError = e.message || "The skills could not be read.";
      } finally { this.loading = false; }
    },
    async loadSkillHistory() {
      this.skillHistory = [];
      if (this.route.page !== "skill") return;
      try {
        const rows = await api("/api/history?limit=20&name=" + encodeURIComponent(this.route.name));
        this.skillHistory = (Array.isArray(rows) ? rows : []).slice(0, 3);
      } catch (e) { this.skillHistory = []; }
    },

    /* ----- search / filter ----- */
    searchInput(v) { this.query = v; if (this.route.page !== "skills" && v.trim()) location.hash = "#/skills"; this.extra = {}; },
    searchSubmit() { if (this.route.page !== "skills") location.hash = "#/skills"; },
    capReset() { this.extra = {}; },
    showMore(id) { this.extra = { ...this.extra, [id]: (this.extra[id] || 0) + 96 }; },
    clearFilters() { this.query = ""; this.filter = "all"; this.agentFilter = "all"; this.extra = {}; },
    pickAgent(id) { this.agentFilter = id; this.filter = "all"; this.query = ""; this.extra = {}; },
    focusH1() { this.$nextTick(() => { const h = document.getElementById("h1"); if (h) h.focus({ preventScroll: true }); }); },

    /* ----- toasts & dialogs ----- */
    toast(text, opts = {}) {
      const t = { id: ++this.toastSeq, text, err: !!opts.err, undo: opts.undo || null };
      this.toasts.push(t); this.live = text;
      setTimeout(() => { this.toasts = this.toasts.filter((x) => x.id !== t.id); }, t.undo ? 9000 : (t.err ? 7000 : 4000));
    },
    async runUndo(t) {
      this.toasts = this.toasts.filter((x) => x.id !== t.id);
      this.busy = true;
      try { await t.undo(); await this.refresh(); this.toast("Undone"); } catch (e) { this.toast("Couldn't undo: " + e.message, { err: true }); } finally { this.busy = false; }
    },
    openDialog(d) { this.opener = document.activeElement; this.dialog = { cancel: "Cancel", ...d }; this.$nextTick(() => { const b = this.$refs.dlg && this.$refs.dlg.querySelector("button"); if (b) b.focus(); }); },
    closeDialog() { this.dialog = null; this.$nextTick(() => { if (this.opener && this.opener.isConnected) this.opener.focus(); }); },
    async confirmDialog() { if (this.dialog && this.dialog.form && this.formInvalid) return; const d = this.dialog; this.dialog = null; if (d && d.onConfirm) await d.onConfirm(d); this.$nextTick(() => { if (this.opener && this.opener.isConnected) this.opener.focus(); }); },
    dialogKeys(e) {
      if (e.key === "Escape") { e.stopPropagation(); this.closeDialog(); return; }
      if (e.key !== "Tab") return;
      const f = [...this.$refs.dlg.querySelectorAll("button:not([disabled]), input:not([disabled])")];
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    },

    /* ----- writes (every one goes through the existing REST routes) ----- */
    async snapshotIds(name, scope) {
      try { const r = await api(`/api/history?name=${encodeURIComponent(name)}&scope=${encodeURIComponent(scope)}&snapshots=1`); return (r && r.snapshots) || []; } catch (e) { return []; }
    },
    /* Copy `from` over each target. The previous text of each target is
     * snapshotted by the backend, which is what makes Undo possible. */
    async doSync(name, from, tos) {
      const before = {};
      for (const t of tos) before[t] = new Set(await this.snapshotIds(name, t));
      const res = await api("/api/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, from_scope: from, to_scopes: tos, force: true }) });
      const synced = res.synced || [];
      const undo = [];
      for (const t of synced) {
        const after = await this.snapshotIds(name, t);
        const fresh = after.find((id) => !before[t].has(id));
        if (fresh) undo.push([t, fresh]);
      }
      return { synced, skipped: res.skipped || [], undo };
    },
    undoFor(name, entries) {
      const list = entries.flatMap((e) => e.undo.map(([scope, snap]) => [e.name || name, scope, snap]));
      if (!list.length) return null;
      return async () => { for (const [n, scope, snap] of list) await api(`/api/trash/${encodeURIComponent(n)}?snapshot=${encodeURIComponent(snap)}&scope=${encodeURIComponent(scope)}`, { method: "POST" }); };
    },
    skipText(skipped) { return skipped.length ? ` ${skipped.length} could not be changed: ${skipped.map((s) => s.reason).slice(0, 2).join("; ")}.` : ""; },

    async syncDiffering() {
      const s = this.skill;
      if (!s || s.ref.ambiguous) return;
      const from = s.ref.holders[0].scope;
      await this.runSync(s.name, from, s.differing.map((c) => c.scope), `${s.name} now matches in`);
    },
    async runSync(name, from, tos, label) {
      this.busy = true;
      try {
        const r = await this.doSync(name, from, tos);
        const undo = this.undoFor(name, [r]);
        await this.refresh();
        this.toast(r.synced.length ? `${label} ${join(r.synced.map((id) => this.agentOf(id).name))}.${this.skipText(r.skipped)}` : "Nothing was changed." + this.skipText(r.skipped), { err: !r.synced.length, undo: r.synced.length ? undo : null });
        return r;
      } catch (e) { this.toast(e.message, { err: true }); return null; } finally { this.busy = false; }
    },
    async toggleCopy(c) {
      const name = this.skill.name, to = c.state === "on" ? "disable" : "enable";
      this.busy = true;
      try {
        await api(`/api/skills/${encodeURIComponent(name)}/${to}?scope=${encodeURIComponent(c.scope)}`, { method: "POST" });
        await this.refresh();
        const back = to === "disable" ? "enable" : "disable";
        this.toast(`${name} turned ${to === "disable" ? "off" : "on"} in ${this.agentOf(c.scope).name}.`, { undo: async () => { await api(`/api/skills/${encodeURIComponent(name)}/${back}?scope=${encodeURIComponent(c.scope)}`, { method: "POST" }); } });
      } catch (e) { this.toast(e.message, { err: true }); await this.refresh(); } finally { this.busy = false; }
    },
    async allOn() {
      const s = this.skill; this.busy = true; const turned = [];
      try {
        for (const c of s.copies.filter((x) => x.state === "off")) { await api(`/api/skills/${encodeURIComponent(s.name)}/enable?scope=${encodeURIComponent(c.scope)}`, { method: "POST" }); turned.push(c.scope); }
        await this.refresh();
        this.toast(`${s.name} turned on everywhere.`, { undo: async () => { for (const sc of turned) await api(`/api/skills/${encodeURIComponent(s.name)}/disable?scope=${encodeURIComponent(sc)}`, { method: "POST" }); } });
      } catch (e) { this.toast(e.message, { err: true }); await this.refresh(); } finally { this.busy = false; }
    },
    async turnOffIn(s, scope) {
      this.busy = true; const name = s.name;
      try {
        await api(`/api/skills/${encodeURIComponent(name)}/disable?scope=${encodeURIComponent(scope)}`, { method: "POST" });
        await this.refresh();
        this.toast(`${name} turned off in ${this.agentOf(scope).name}.`, { undo: async () => { await api(`/api/skills/${encodeURIComponent(name)}/enable?scope=${encodeURIComponent(scope)}`, { method: "POST" }); } });
      } catch (e) { this.toast(e.message, { err: true }); } finally { this.busy = false; }
    },
    fixSkillBad() {
      const p = this.m.problems.find((x) => x.id === "bad:" + this.skill.name);
      if (p) this.fixBad(p);
    },
    fixBad(p) {
      if (p.fixable) return this.runSync(p.skill, p.source, p.agents, `${p.skill} was replaced in`);
      const s = this.m.byName.get(p.skill);
      this.openDialog({ title: p.title, lines: [p.text], how: p.how, paths: s.broken.map((c) => shortPath(c.path)), cancel: "Close" });
      return null;
    },
    openShare() {
      const s = this.skill, from = this.refCopy.scope;
      this.openDialog({
        title: `Add “${s.name}” to another agent`, lines: ["Choose where it should also be available. The copy comes from " + this.agentOf(from).name + "."],
        picks: this.shareTargets.map((a) => ({ id: a.id, label: a.name, path: a.path })), chosen: [], confirm: "Add",
        onConfirm: (d) => this.runSync(s.name, from, d.chosen, `${s.name} was added to`),
      });
    },
    openTrash() {
      const s = this.skill;
      this.openDialog({
        title: `Move “${s.name}” to the trash?`, danger: true, confirm: "Move to trash",
        lines: ["Choose the places to remove it from. Each agent keeps its own trash folder, so restoring from inside the app only works for your library."],
        picks: s.copies.map((c) => ({ id: c.scope, label: this.agentOf(c.scope).name, path: shortPath(c.path) })), chosen: [],
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

    /* ----- create, recovery, theme, help ----- */
    openCreate() {
      const first = this.createTargets.find((x) => !x.library) || this.createTargets[0];
      this.openDialog({
        title: "New skill", form: { name: "", desc: "", scope: first ? first.id : "global" }, confirm: "Create skill",
        onConfirm: async (d) => {
          const f = d.form; this.busy = true;
          try {
            await api("/api/skills?scope=" + encodeURIComponent(f.scope), { method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ name: f.name.trim(), description: f.desc.trim(), body: "## When to use\n\nDescribe the situations where an agent should use this skill.\n\n## Steps\n\n1. \n" }) });
            await this.refresh();
            this.toast(`${f.name.trim()} created in ${this.agentOf(f.scope).name}.`);
            location.hash = "#/skill/" + encodeURIComponent(f.name.trim());
          } catch (e) { this.toast(e.message, { err: true }); } finally { this.busy = false; }
        },
      });
    },
    async loadTrash() { try { this.trash = await api("/api/trash"); } catch (e) { this.trash = []; } },
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
      const f = this.importFile; if (!f) return;
      this.busy = true;
      try {
        const r = await api(`/api/import?filename=${encodeURIComponent(f.name)}&force=${this.importForce ? 1 : 0}&full=0`, { method: "PUT", body: f });
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
        [["Ctrl", "S"], "Save while editing"], [["Enter"], "Fix the item in the Inbox"], [["S"], "Skip it for now"],
      ] });
    },

    /* ----- editing ----- */
    startEdit() {
      const s = this.skill, c = this.refCopy;
      const body = stripFrontmatter(c.body || "");
      this.edit = { name: s.name, desc: s.description, baseDesc: s.description, body, baseBody: body, tab: "write", targets: this.editTargets.map((x) => x.scope) };
      this.$nextTick(() => this.growArea());
    },
    async cancelEdit() {
      if (this.editDirty) return this.openDialog({ title: "Discard your changes?", lines: [`You have unsaved changes to “${this.edit.name}”.`], cancel: "Keep editing", confirm: "Discard changes", danger: true, onConfirm: () => { this.edit = null; } });
      this.edit = null; return null;
    },
    async saveEdit() {
      const e = this.edit; if (!e || this.editError) return;
      this.busy = true; const saved = [];
      try {
        const snaps = {};
        for (const sc of e.targets) snaps[sc] = new Set(await this.snapshotIds(e.name, sc));
        for (const sc of e.targets) {
          await api(`/api/skills/${encodeURIComponent(e.name)}?scope=${encodeURIComponent(sc)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ description: e.desc, body: e.body }) });
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
      return inf.key === "bad" ? `${plural(inf.broken.length, "skill")} can't be read` : inf.key === "warn" ? `${plural(inf.differing.length, "copy", "copies")} differ` : "matches";
    },
    selectMap(id) { this.mapSelId = id; this.mapPicked = this.mapDefaults(id); this.peek = null; },
    mapDefaults(id) { const i = this.m.info(id); return i ? i.differing.filter((s) => !s.ref.ambiguous).map((s) => s.name) : []; },
    togglePick(n) { this.mapPicked = this.mapPicked.includes(n) ? this.mapPicked.filter((x) => x !== n) : [...this.mapPicked, n]; },
    diffCount(s, scope) { const mine = s.copies.find((c) => c.scope === scope), ref = s.ref.holders[0]; return mine && ref ? changes(stripFrontmatter(mine.body), stripFrontmatter(ref.body)).filter((l) => l.t !== "same").length : 0; },
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
        this.toast(`${plural(ok, "skill")} now ${ok === 1 ? "matches" : "match"} in ${inf.agent.name}.`, { undo });
      } catch (e) { this.toast(e.message, { err: true }); await this.refresh(); } finally { this.busy = false; }
    },

    /* ----- inbox ----- */
    async fixCurrent() {
      const p = this.cur; if (!p || this.busy) return;
      let ok = false;
      if (p.key === "warn") {
        const s = this.curSkill, src = this.srcChoice;
        const srcHash = (s.copies.find((c) => c.scope === src) || {}).hash;
        const tos = s.copies.filter((c) => c.state !== "broken" && c.hash && c.hash !== srcHash).map((c) => c.scope);
        ok = !!(await this.runSync(p.skill, src, tos, `${p.skill} now matches in`));
      } else if (p.key === "bad") {
        if (!p.fixable) return this.fixBad(p);
        ok = !!(await this.fixBad(p));
      } else { ok = true; this.toast("Marked done for this session."); }
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
        location.hash = "#/skill/" + encodeURIComponent(this.edit.name);
        return this.cancelEdit();
      }
      this.route = next; if (next.page !== "skill") this.edit = null;
      document.title = (next.page === "skill" ? next.name : TITLES[next.page]) + " · Skills Manager";
      window.scrollTo(0, 0); this.focusH1();
    });
    window.addEventListener("beforeunload", (e) => { if (this.editDirty) { e.preventDefault(); e.returnValue = ""; } });
    document.addEventListener("keydown", (e) => {
      const t = e.target, typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
      if (e.key === "?" && !typing && !this.dialog) { e.preventDefault(); this.openHelp(); }
      if (e.key === "/" && !typing && !this.dialog && !e.ctrlKey && !e.metaKey) { e.preventDefault(); this.$refs.gsearch.focus(); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && this.edit) { e.preventDefault(); this.saveEdit(); }
      if (this.route.page === "inbox" && this.cur && !typing && !this.dialog && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (e.key === "s" || e.key === "S") { e.preventDefault(); this.skipCurrent(); }
        else if (e.key === "Enter" && !(t && t.tagName === "BUTTON")) { e.preventDefault(); this.fixCurrent(); }
      }
    });
    document.title = (this.route.page === "skill" ? this.route.name : TITLES[this.route.page]) + " · Skills Manager";
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

app.mount("#app");
