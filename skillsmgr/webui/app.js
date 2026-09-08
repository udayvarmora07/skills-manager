/* Skills Manager web UI — Vue 3 application (no build step). */
"use strict";

/* ------------------------------------------------------------- utilities */

async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  let data = null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) data = await res.json();
  if (!res.ok) throw new Error((data && data.error) || "HTTP " + res.status);
  return data;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function formatBytes(n) {
  if (n === null || n === undefined) return "—";
  if (n < 1024) return n + " B";
  const units = ["KB", "MB", "GB"];
  let v = n, i = -1;
  do { v /= 1024; i++; } while (v >= 1024 && i < units.length - 1);
  return v.toFixed(v >= 100 ? 0 : 1) + " " + units[i];
}

function formatTokens(n) {
  if (n == null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
}

function tokenPctClass(pct) {
  if (pct >= 80) return "pct-bad";
  if (pct >= 50) return "pct-warn";
  return "pct-ok";
}

function tokenBarWidth(pct) {
  return Math.max(2, Math.min(100, pct)).toFixed(1) + "%";
}

/* Minimal, safe markdown renderer: blocks only, everything escaped. */

function inlineMd(s) {
  let out = esc(s);
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return out;
}

function renderMarkdown(md) {
  if (!md || !md.trim()) return '<p style="color:var(--text-muted);">No documentation body.</p>';
  const lines = String(md).split("\n");
  const out = [];
  let i = 0, inList = null, inCode = false, codeBuf = [], codeLang = "", inTable = false;

  const closeList = () => { if (inList) { out.push("</" + inList + ">"); inList = null; } };
  const closeTable = () => { if (inTable) { out.push("</table>"); inTable = false; } };

  while (i < lines.length) {
    const line = lines[i];

    if (inCode) {
      if (/^```/.test(line.trim())) {
        out.push('<pre><code>' + esc(codeBuf.join("\n")) + "</code></pre>");
        inCode = false; codeBuf = [];
      } else codeBuf.push(line);
      i++; continue;
    }
    if (/^```/.test(line.trim())) { inCode = true; codeLang = ""; i++; continue; }

    const blank = !line.trim();
    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    const hr = /^\s*(-{3,}|\*{3,})\s*$/.test(line);
    const ul = /^\s*[-*+]\s+(.*)$/.exec(line);
    const ol = /^\s*\d+\.\s+(.*)$/.exec(line);
    const quote = /^\s*>\s?(.*)$/.exec(line);

    if (blank) { closeList(); closeTable(); i++; continue; }

    const tableRow = /^\s*\|.*\|\s*$/.test(line) && !h;
    if (tableRow) {
      closeList();
      const cells = line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
      const isSep = cells.every((c) => /^:?-{2,}:?$/.test(c));
      if (!isSep) {
        if (!inTable) { out.push("<table>"); inTable = true; }
        out.push("<tr>" + cells.map((c) => "<td>" + inlineMd(c) + "</td>").join("") + "</tr>");
      }
      i++; continue;
    }

    if (h) { closeList(); closeTable(); out.push(`<h${h[1].length}>` + inlineMd(h[2]) + `</h${h[1].length}>`); i++; continue; }
    if (hr) { closeList(); closeTable(); out.push("<hr>"); i++; continue; }
    if (quote) { closeList(); closeTable(); out.push("<blockquote>" + inlineMd(quote[1]) + "</blockquote>"); i++; continue; }
    if (ul || ol) {
      const tag = ul ? "ul" : "ol";
      const text = (ul || ol)[1];
      closeTable();
      if (inList !== tag) { closeList(); out.push("<" + tag + ">"); inList = tag; }
      out.push("<li>" + inlineMd(text) + "</li>");
      i++; continue;
    }

    closeList(); closeTable();
    out.push("<p>" + inlineMd(line) + "</p>");
    i++;
  }

  closeList(); closeTable();
  if (inCode) out.push('<pre><code>' + esc(codeBuf.join("\n")) + "</code></pre>");

  let html = out.join("\n");

  /* table cleanup: drop stray <table> with no rows and wrap rows */
  html = html.replace(/<table>/g, '<div class="tablewrap"><table>');
  html = html.replace(/<\/table>/g, "</table></div>");

  return html;
}

/* Extract compatibility / allowed-tools from raw SKILL.md frontmatter. */
function parseFrontmatter(text) {
  const m = /^---\s*\n([\s\S]*?)\n---/.exec(text || "");
  if (!m) return {};
  const out = {};
  for (const line of m[1].split("\n")) {
    const kv = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line);
    if (!kv) continue;
    if (kv[1] === "compatibility" && kv[2].trim()) out.compatibility = kv[2].trim();
    if (kv[1] === "allowed-tools" && kv[2].trim()) out.allowed_tools = kv[2].trim();
  }
  return out;
}

function formatCompat(v) {
  if (!v) return "";
  if (typeof v === "string") return v;
  if (typeof v === "object") return Object.entries(v).map(([k, val]) => `${k} ${val}`).join(", ");
  return String(v);
}

function formatTools(v) {
  if (!v) return "";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

/* ------------------------------------------------------------------ app */

const { createApp, nextTick } = Vue;

createApp({
  data() {
    return {
      view: "skills",
      filter: "",
      query: "",
      skills: [],
      trashSkills: [],
      selectedName: null,
      selected: null,
      selectedTrash: null,
      dataDir: "",
      scopes: [],
      activeScope: localStorage.getItem("skillsmgr-scope") || "all",
      budget: null,
      budgetWindow: localStorage.getItem("skillsmgr-budget-window") || "claude",
      install: { runner: "npx", source: "", scope: "global", agents: [], skillsFilter: "", copy: false, listOnly: false, lastResult: null },
      theme: localStorage.getItem("skillsmgr-theme") || "light",
      menuOpen: false,
      busy: false,
      banner: null,
      loadingList: false,
      loadingDetail: false,
      loadingTrash: false,
      toasts: [],
      toastSeq: 0,
      searchTimer: null,
      listSeq: 0,
      detailSeq: 0,
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
      },
    };
  },

  computed: {
    filteredSkills() {
      return this.skills.filter((s) => {
        if (this.filter === "active" && s.disabled) return false;
        if (this.filter === "disabled" && !s.disabled) return false;
        return true;
      });
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
  },

  watch: {
    theme(v) {
      document.documentElement.dataset.theme = v;
      localStorage.setItem("skillsmgr-theme", v);
    },
    activeScope(v) {
      localStorage.setItem("skillsmgr-scope", v);
      this.selectedName = null;
      this.selected = null;
      this.loadSkills();
      this.loadStatsTokens();
    },
    budgetWindow(v) {
      localStorage.setItem("skillsmgr-budget-window", v);
      this.loadStatsTokens();
    },
    query() {
      clearTimeout(this.searchTimer);
      this.searchTimer = setTimeout(() => this.applySearch(), 220);
    },
  },

  mounted() {
    document.documentElement.dataset.theme = this.theme;
    document.addEventListener("keydown", this.onKeydown);
    document.addEventListener("mousedown", this.onDocMousedown);
    this.loadScopes();
    this.loadSkills();
    this.loadTrash();
    this.loadDataDir();
    this.loadStatsTokens();
  },

  methods: {
    renderMarkdown,
    formatBytes,
    formatTokens,
    tokenPctClass,
    tokenBarWidth,
    formatCompat,
    formatTools,

    /* ----------------------------------------------------------- data */

    async loadDataDir() {
      try {
        const st = await api("/api/stats");
        this.dataDir = st.dirs && st.dirs.skills
          ? st.dirs.skills.replace(/\/skills$/, "")
          : "";
      } catch (e) { /* non-fatal */ }
    },

    async loadScopes() {
      try {
        this.scopes = await api("/api/scopes");
      } catch (e) { /* non-fatal */ }
    },

    async loadStatsTokens() {
      try {
        const s = await api("/api/stats?window=" + encodeURIComponent(this.budgetWindow || "claude"));
        this.budget = s;
      } catch (e) { /* non-fatal */ }
    },

    installPreview() {
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

    _scopeParam() {
      return this.activeScope && this.activeScope !== "all" ? "?scope=" + encodeURIComponent(this.activeScope) : "";
    },

    _scopeQs(qs) {
      const s = this.activeScope || "all";
      if (!s || s === "global") return qs;
      return qs ? qs + "&scope=" + encodeURIComponent(s) : "?scope=" + encodeURIComponent(s);
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
      if (!q) { this.loadSkills(); return; }
      if (this.view !== "skills") return;
      const mySeq = ++this.listSeq;
      const scopeAtCall = this.activeScope || "all";
      this.loadingList = true;
      this.banner = null;
      try {
        const s = scopeAtCall;
        const rows = await api("/api/search?q=" + encodeURIComponent(q) + "&scope=" + encodeURIComponent(s));
        if (mySeq !== this.listSeq) return;
        this.skills = rows;
      } catch (e) {
        if (mySeq !== this.listSeq) return;
        this.banner = { type: "error", text: "Search failed: " + e.message };
      } finally {
        if (mySeq === this.listSeq) this.loadingList = false;
      }
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
          }
        } catch (e) { /* optional enrichment */ }
        if (mySeq !== this.detailSeq) return;
        this.selected = record;
        this.selectedName = name;
      } catch (e) {
        if (mySeq !== this.detailSeq) return;
        this.toast("Could not load skill: " + e.message, "err");
        this.selected = null;
      } finally {
        if (mySeq === this.detailSeq) this.loadingDetail = false;
      }
    },

    selectSkill(s) {
      if (this.selectedName === s.name) return;
      this.loadDetail(s.name, s.scope);
    },

    selectTrash(t) {
      this.selectedTrash = this.selectedTrash && this.selectedTrash.trash_path === t.trash_path ? null : t;
    },

    switchView(v) {
      this.view = v;
      if (v === "trash") this.loadTrash();
    },

    setFilter(f) {
      this.filter = f;
    },

    /* ---------------------------------------------------------- helpers */

    toast(text, type = "ok", undo = null) {
      const id = ++this.toastSeq;
      this.toasts.push({ id, text, type, undo });
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

    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
    },

    closeModal(key) {
      this.modals[key] = null;
    },

    onKeydown(e) {
      const tag = (e.target.tagName || "").toLowerCase();
      const typing = ["input", "textarea", "select"].includes(tag) || e.target.isContentEditable;
      if (e.key === "/" && !typing) {
        e.preventDefault();
        this.$refs.searchInput && this.$refs.searchInput.focus();
      } else if (e.key === "Escape") {
        if (this.menuOpen) this.menuOpen = false;
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
      }
    },

    onDocMousedown(e) {
      if (this.menuOpen && this.$refs.menuWrap && !this.$refs.menuWrap.contains(e.target)) {
        this.menuOpen = false;
      }
    },

    menuDo(action) {
      this.menuOpen = false;
      const actions = {
        create: this.openCreate,
        add: this.openAdd,
        edit: this.openEdit,
        toggle: this.toggleSelected,
        validate: this.openValidate,
        remove: () => this.selectedName && this.confirmRemove(this.selected),
        sync: this.openSync,
        install: this.openInstall,
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
        refresh: () => { this.loadScopes(); this.loadSkills(); this.loadTrash(); this.loadStatsTokens(); },
      };
      const fn = actions[action];
      if (fn) fn.call(this);
    },

    openInstall() {
      this.modals.install = true;
    },

    /* ----------------------------------------------------- skill actions */

    openCreate() {
      const defScope = (this.activeScope && this.activeScope !== "all") ? this.activeScope : "global";
      this.modals.skill = {
        mode: "create",
        form: { name: "", description: "", category: "", version: "", license: "", compatibility: "", allowed_tools: "", body: "", scope: defScope },
        errors: {},
      };
      nextTick(() => { const el = document.getElementById("f-name"); el && el.focus(); });
    },

    async openEdit() {
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
      if (Object.keys(m.errors).length) return;

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
      if (!record) { this.toast("Select a skill first.", "err"); return; }
      this.modals.remove = { name: record.name, mode: "trash" };
    },

    async doRemove() {
      const m = this.modals.remove;
      if (!m) return;
      this.busy = true;
      try {
        await this.removeSkill(m.name, m.mode === "purge");
        this.closeModal("remove");
      } catch (e) {
        this.toast(e.message, "err");
      } finally {
        this.busy = false;
      }
    },

    async removeSkill(name, purge) {
      const sc = (this.selected && this.selected.scope) ? this.selected.scope : (this.activeScope !== "all" ? this.activeScope : "global");
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
      this.modals.stats = { loading: true, report: null };
      api("/api/stats")
        .then((report) => { if (this.modals.stats) this.modals.stats.report = report; })
        .catch((e) => { this.closeModal("stats"); this.toast(e.message, "err"); })
        .finally(() => { if (this.modals.stats) this.modals.stats.loading = false; });
    },

    openHistory() {
      this.modals.history = { name: "", rows: [], snapshots: [], loading: false };
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
          const scope = (this.selected && this.selected.scope) ? this.selected.scope : "global";
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
        const scope = (this.selected && this.selected.scope) ? this.selected.scope : "global";
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
      this.modals.templates = { loading: true, names: [] };
      api("/api/templates")
        .then((res) => { if (this.modals.templates) this.modals.templates.names = res.templates || []; })
        .catch((e) => { this.closeModal("templates"); this.toast(e.message, "err"); })
        .finally(() => { if (this.modals.templates) this.modals.templates.loading = false; });
    },

    openNewTemplate() {
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

    openImport() {
      this.modals.import = { file: null, force: false, full: false };
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
