/* Clear prototype — vanilla JS, no build, no network. All state is in memory. */
(function () {
  "use strict";
  const D = window.CLEAR_DATA;
  const AG = Object.fromEntries(D.agents.map((a) => [a.id, a]));

  /* ---------- Icons (inline SVG, 24px grid) ---------- */
  const P = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/>',
    layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/>',
    download: '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>',
    undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    checkCircle: '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 3 3 5-6"/>',
    alert: '<path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 10v4M12 17.5v.01"/>',
    xCircle: '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
    power: '<path d="M12 3v8"/><path d="M6.4 6.6a8 8 0 1 0 11.2 0"/>',
    trash: '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    sync: '<path d="M4 12a8 8 0 0 1 14-5.3L20 9"/><path d="M20 4v5h-5"/><path d="M20 12a8 8 0 0 1-14 5.3L4 15"/><path d="M4 20v-5h5"/>',
    chevron: '<path d="m9 6 6 6-6 6"/>',
    left: '<path d="m15 6-6 6 6 6"/>',
    close: '<path d="M6 6l12 12M18 6 6 18"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    upload: '<path d="M12 20V9"/><path d="m7 14 5-5 5 5"/><path d="M5 4h14"/>',
    shield: '<path d="M12 3 4.5 6v5.5c0 4.5 3.2 8.2 7.5 9.5 4.3-1.3 7.5-5 7.5-9.5V6L12 3Z"/><path d="m9 12 2 2 4-4"/>',
    gauge: '<path d="M4 18a9 9 0 1 1 16 0"/><path d="m12 13 4-4"/>',
    book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5Z"/><path d="M19 19v2H6"/>',
    file: '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5Z"/><path d="M14 3v5h5"/>',
    pencil: '<path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.01"/>',
    archive: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    sparkle: '<path d="M12 4v4M12 16v4M4 12h4M16 12h4"/><circle cx="12" cy="12" r="1.5"/>',
  };
  const icon = (n, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[n] || ""}</svg>`;
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (n) => n.toLocaleString("en-US");
  const $ = (sel, root = document) => root.querySelector(sel);

  /* ---------- State ---------- */
  const state = {
    skills: D.skills.map((s) => ({ ...s, copies: s.copies.map(([agent, st, v]) => ({ agent, state: st, v })) })),
    filter: "all",       // all | attention | off
    agent: "any",
    query: "",
    tab: "where",
    tipHidden: false,
    history: D.activity.slice(),
  };

  /* ---------- Derived status, in plain language ---------- */
  function statusOf(s) {
    if (s.copies.some((c) => c.state === "broken")) return { key: "bad", label: "Can't be read", icon: "xCircle" };
    const on = s.copies.filter((c) => c.state === "on");
    if (!on.length) return { key: "off", label: "Turned off", icon: "power" };
    if (new Set(s.copies.filter((c) => c.state !== "broken").map((c) => c.v)).size > 1) return { key: "warn", label: "Copies differ", icon: "alert" };
    return { key: "ok", label: "Working", icon: "checkCircle" };
  }
  const sizeOf = (t) => (t < 1000 ? "Small" : t < 3500 ? "Medium" : "Large");
  const words = (t) => fmt(Math.round((t * 0.75) / 10) * 10);
  const find = (name) => state.skills.find((s) => s.name === name);
  const counts = () => {
    const c = { ok: 0, warn: 0, bad: 0, off: 0 };
    state.skills.forEach((s) => c[statusOf(s).key]++);
    return c;
  };
  function agentLoad(id) {
    const on = state.skills.filter((s) => s.copies.some((c) => c.agent === id && c.state === "on"));
    const tokens = on.reduce((n, s) => n + s.tokens, 0);
    const a = AG[id];
    return { count: state.skills.filter((s) => s.copies.some((c) => c.agent === id)).length, active: on.length, tokens, pct: Math.round((tokens / a.window) * 100) };
  }

  /* ---------- Shared fragments ---------- */
  const tile = (id, extra = "") => {
    const a = AG[id];
    return `<span class="mono-tile ${extra}" style="--h:${a.hue}" title="${esc(a.name)}" aria-hidden="true">${a.short}</span>`;
  };
  const statusPill = (st) => `<span class="status ${st.key}">${icon(st.icon)}${st.label}</span>`;
  const greeting = () => {
    const h = new Date().getHours();
    return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  };

  /* ---------- HOME ---------- */
  function attentionItems() {
    const items = [];
    state.skills.forEach((s) => {
      const st = statusOf(s);
      if (st.key === "warn") {
        const newest = Math.max(...s.copies.map((c) => c.v));
        const odd = s.copies.filter((c) => c.v !== newest && c.state !== "broken").map((c) => AG[c.agent].name);
        items.push({ tone: "warn", icon: "alert", title: `“${s.name}” is different in some agents`,
          why: `${listJoin(odd)} ${odd.length === 1 ? "has" : "have"} an older copy, so ${odd.length === 1 ? "it" : "they"} may behave differently.`, cta: "Compare copies", go: s.name });
      }
      if (st.key === "bad") {
        items.push({ tone: "bad", icon: "xCircle", title: `“${s.name}” can't be read`,
          why: s.problem || "One copy is damaged, so the agent skips it.", cta: "See the problem", go: s.name });
      }
    });
    D.agents.forEach((a) => {
      const l = agentLoad(a.id);
      if (l.pct >= 20) items.push({ tone: "info", icon: "gauge", title: `${a.name}'s skills are getting large`,
        why: `They fill ${l.pct}% of what ${a.name} can read at once. Turning off unused skills leaves more room for your code.`, cta: "See largest skills", filterAgent: a.id });
    });
    items.sort((a, b) => ({ bad: 0, warn: 1, info: 2, off: 3 }[a.tone] - { bad: 0, warn: 1, info: 2, off: 3 }[b.tone]));
    if (D.trash) items.push({ tone: "off", icon: "trash", title: `${D.trash} skills are in the trash`, why: "They are not used by any agent. You can bring them back or empty the trash.", cta: "Review trash", soon: true });
    return items;
  }
  const listJoin = (arr) => (arr.length < 2 ? arr.join("") : arr.slice(0, -1).join(", ") + " and " + arr[arr.length - 1]);

  function renderHome() {
    const c = counts();
    const total = state.skills.length;
    const agentsWith = D.agents.filter((a) => agentLoad(a.id).count > 0).length;
    const todo = attentionItems();
    const needs = c.warn + c.bad;

    const healthCard = (key, ico, label, n, hint, filter) => `
      <button class="health-card" type="button" data-go-filter="${filter}">
        <span class="health-top"><span class="health-ico ${key}">${icon(ico)}</span>${label}</span>
        <span class="health-num">${n}</span>
        <span class="health-hint">${hint} ${icon("chevron", "i-sm")}</span>
      </button>`;

    return `
    <div class="page">
      <header>
        <div class="eyebrow">${greeting()}</div>
        <h1 class="title" tabindex="-1" id="page-title">Your skills at a glance</h1>
        <p class="lede">You have <strong>${total} skills</strong> across <strong>${agentsWith} agents</strong>.
          ${needs ? `<strong>${needs} ${needs === 1 ? "needs" : "need"} a quick look</strong> — everything else is working.` : "Everything is working."}</p>
      </header>

      <form class="big-search" style="margin-top:24px" role="search" data-home-search>
        ${icon("search", "i-lg")}
        <label class="sr-only" for="home-q">Find a skill</label>
        <input id="home-q" type="search" placeholder="Find a skill by name or what it does…" autocomplete="off">
        <span class="kbd" aria-hidden="true">/</span>
        <button class="btn btn-primary" type="submit">Search</button>
      </form>

      ${state.tipHidden ? "" : `
      <section class="tip" aria-labelledby="tip-title" style="position:relative">
        <span class="tip-ico">${icon("book")}</span>
        <div>
          <div class="tip-title" id="tip-title">New here? A skill is a set of instructions for your AI agent.</div>
          <p>Each agent (like Claude Code or Cursor) keeps its own copy. Skills Manager shows you every copy in one place, so you can keep them the same.</p>
          <div class="tip-steps"><span><b>1</b>Check what needs a look</span><span><b>2</b>Open a skill to see its copies</span><span><b>3</b>Fix with one click — you can always undo</span></div>
        </div>
        <button class="icon-btn" type="button" data-hide-tip aria-label="Hide this tip">${icon("close")}</button>
      </section>`}

      <div class="health" role="list">
        ${healthCard("ok", "checkCircle", "Working", c.ok, "See working skills", "working")}
        ${healthCard("warn", "alert", "Needs a look", c.warn + c.bad, "Review these", "attention")}
        ${healthCard("off", "power", "Turned off", c.off, "See turned off", "off")}
      </div>
      <div class="health-bar" role="img" aria-label="${c.ok} working, ${c.warn + c.bad} need a look, ${c.off} turned off">
        <span class="ok" style="flex:${c.ok}"></span><span class="warn" style="flex:${c.warn + c.bad}"></span><span class="off" style="flex:${c.off}"></span>
      </div>

      <section class="section" aria-labelledby="todo-h">
        <div class="section-head">
          <div><h2 class="section-title" id="todo-h">What needs your attention</h2>
          <div class="section-sub">Sorted by what matters most. Nothing changes until you choose to.</div></div>
        </div>
        <div class="card todo">
          ${todo.length ? todo.slice(0, state.showAllTodo ? 99 : 4).map((t, i) => `
            <div class="todo-item">
              <span class="todo-ico ${t.tone}">${icon(t.icon)}</span>
              <div><div class="todo-title">${esc(t.title)}</div><div class="todo-why">${esc(t.why)}</div></div>
              <button class="btn btn-quiet btn-sm" type="button" data-todo="${i}">${esc(t.cta)} ${icon("chevron", "i-sm")}</button>
            </div>`).join("") + (todo.length > 4 ? `<div class="more-row"><button class="link-btn" type="button" data-more-todo>${state.showAllTodo ? "Show less" : `Show ${todo.length - 4} more`}</button></div>` : "") : `
            <div class="all-good"><span class="todo-ico info">${icon("check")}</span><div><div class="todo-title">All clear</div><div class="todo-why">Every skill is working and all copies match.</div></div></div>`}
        </div>
      </section>

      <div class="split section">
        <section aria-labelledby="agents-h">
          <div class="section-head"><div><h2 class="section-title" id="agents-h">Your agents</h2>
            <div class="section-sub">How much of each agent's reading space your skills use.</div></div></div>
          <div class="agents">
            ${D.agents.map((a) => {
              const l = agentLoad(a.id);
              const tone = l.pct >= 20 ? "warn" : "";
              return `<button type="button" class="card agent-card" data-agent="${a.id}" style="text-align:left">
                <span class="agent-row">${tile(a.id)}<span><span class="agent-name">${esc(a.name)}</span><br><span class="agent-meta">${l.active} on · ${l.count - l.active} off</span></span>
                  <span class="agent-count">${l.count}<small>skills</small></span></span>
                <span class="meter">
                  <span class="meter-label"><span>Reading space used</span><b>${l.pct}%</b></span>
                  <span class="meter-track"><span class="meter-fill ${tone}" style="width:${Math.max(l.pct, 1)}%"></span></span>
                </span>
              </button>`;
            }).join("")}
          </div>
        </section>

        <section aria-labelledby="act-h">
          <div class="section-head"><div><h2 class="section-title" id="act-h">Recent changes</h2>
            <div class="section-sub">Everything here can be undone.</div></div></div>
          <ul class="card activity">
            ${state.history.slice(0, 6).map((a) => `<li><span class="act-ico">${icon(actIcon(a.kind), "i-sm")}</span>
              <span><span class="act-what">${esc(a.what)}</span><br><span class="act-when">${esc(a.when)}</span></span></li>`).join("")}
          </ul>
        </section>
      </div>

      <section class="section" aria-labelledby="quick-h">
        <div class="section-head"><h2 class="section-title" id="quick-h">Quick actions</h2></div>
        <div class="quick">
          ${[["plus", "Create a skill", "Start from a simple template"], ["upload", "Add from a folder", "Bring in skills you already have"],
             ["download", "Get new skills", "Browse trusted skills to install"], ["shield", "Run a health check", "Look for problems in every agent"]]
            .map(([i, t, s]) => `<button type="button" class="quick-btn" data-soon="${t}">${icon(i, "i-lg")}<span><span class="quick-title">${t}</span><br><span class="quick-sub">${s}</span></span></button>`).join("")}
        </div>
      </section>
    </div>`;
  }
  const actIcon = (k) => ({ sync: "sync", add: "plus", off: "power", trash: "trash", backup: "archive", on: "power" }[k] || "clock");

  /* ---------- SKILLS ---------- */
  function visibleSkills() {
    const q = state.query.trim().toLowerCase();
    return state.skills.filter((s) => {
      const k = statusOf(s).key;
      if (state.filter === "attention" && !(k === "warn" || k === "bad")) return false;
      if (state.filter === "off" && k !== "off") return false;
      if (state.filter === "working" && k !== "ok") return false;
      if (state.agent !== "any" && !s.copies.some((c) => c.agent === state.agent)) return false;
      if (q && !(s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q) || s.category.toLowerCase().includes(q))) return false;
      return true;
    }).sort((a, b) => {
      if (state.agent !== "any" && state.filter === "all") return b.tokens - a.tokens;
      const rank = { bad: 0, warn: 1, ok: 2, off: 3 };
      return rank[statusOf(a).key] - rank[statusOf(b).key] || a.name.localeCompare(b.name);
    });
  }

  function renderSkills(selectedName) {
    const c = counts();
    const list = visibleSkills();
    const sel = selectedName ? find(selectedName) : null;
    const chip = (id, label, n) => `<button type="button" class="chip" data-filter="${id}" aria-pressed="${state.filter === id}">${label}<span class="n">${n}</span></button>`;

    return `
    <div class="skills-layout ${sel ? "has-detail" : ""}">
      <div class="page">
        <div class="page-head" style="margin-bottom:20px">
          <div>
            <h1 class="title" tabindex="-1" id="page-title">Skills</h1>
            <p class="lede" style="font-size:16px">Every skill your agents can use, with all its copies in one row.</p>
          </div>
          <button class="btn btn-primary" type="button" data-soon="Create a skill">${icon("plus")}New skill</button>
        </div>

        <div class="big-search" role="search">
          ${icon("search", "i-lg")}
          <label class="sr-only" for="skills-q">Search skills</label>
          <input id="skills-q" type="search" placeholder="Search by name, purpose or category…" value="${esc(state.query)}" autocomplete="off">
          <span class="kbd" aria-hidden="true">/</span>
        </div>

        <div class="toolbar">
          <div class="chips" role="group" aria-label="Show">
            ${chip("all", "All", state.skills.length)}
            ${chip("attention", "Needs a look", c.warn + c.bad)}
            ${chip("off", "Turned off", c.off)}
          </div>
          <label class="sr-only" for="agent-sel">Agent</label>
          <select class="select" id="agent-sel">
            <option value="any">All agents</option>
            ${D.agents.map((a) => `<option value="${a.id}" ${state.agent === a.id ? "selected" : ""}>${esc(a.name)}</option>`).join("")}
          </select>
          <span class="spacer"></span>
          <span class="result-count" aria-live="polite">${list.length === state.skills.length ? `${list.length} skills` : `Showing ${list.length} of ${state.skills.length}`}</span>
        </div>

        <div class="card list" role="list" aria-label="Skills">
          ${list.length ? `<div class="list-head" aria-hidden="true"><span>Skill</span><span class="col-agents">Used by</span><span>Status</span><span class="col-size" style="text-align:right">Size</span></div>` : ""}
          ${list.length ? list.map((s) => rowHtml(s, sel)).join("") : emptyHtml()}
        </div>
      </div>
      ${sel ? detailHtml(sel) : ""}
    </div>`;
  }

  function rowHtml(s, sel) {
    const st = statusOf(s);
    const shown = s.copies.length > 4 ? s.copies.slice(0, 3) : s.copies;
    const usedBy = s.copies.map((c) => AG[c.agent].name + (c.state === "off" ? " (off)" : c.state === "broken" ? " (can't be read)" : "")).join(", ");
    return `<div role="listitem"><button type="button" class="row" data-skill="${esc(s.name)}" aria-current="${sel && sel.name === s.name}"
        aria-label="${esc(s.name)}. ${st.label}. Used by ${esc(usedBy)}. ${sizeOf(s.tokens)} size.">
      <span style="min-width:0"><span class="row-name">${esc(s.name)}</span><span class="row-desc">${esc(s.description)}</span></span>
      <span class="stack col-agents">${shown.map((c) => tile(c.agent, c.state === "off" ? "is-off" : c.state === "broken" ? "is-broken" : "")).join("")}${s.copies.length > shown.length ? `<span class="more">+${s.copies.length - shown.length}</span>` : ""}</span>
      <span>${statusPill(st)}</span>
      <span class="row-size col-size">${sizeOf(s.tokens)}<small>${fmt(s.tokens)} tokens</small></span>
    </button></div>`;
  }

  function emptyHtml() {
    const searching = state.query.trim();
    return `<div class="empty">
      <span class="empty-ico">${icon(searching ? "search" : "checkCircle", "i-lg")}</span>
      <h3>${searching ? `No skills match “${esc(searching)}”` : state.filter === "attention" ? "Nothing needs a look" : "Nothing here yet"}</h3>
      <p>${searching ? "Try a shorter word, or search for what the skill does (for example “tests” or “commit”)." : "Every skill in this view is working. Nice."}</p>
      <button class="btn btn-quiet" type="button" data-clear>Show all skills</button>
    </div>`;
  }

  function explainHtml(s) {
    const st = statusOf(s);
    if (st.key === "ok") {
      const n = s.copies.filter((c) => c.state === "on").length;
      return `<div class="explain ok">${icon("checkCircle")}<div><div class="explain-title">Working everywhere</div>
        <p>${n === 1 ? "There is one copy and it's turned on." : `All ${n} copies are the same and turned on.`}</p></div></div>`;
    }
    if (st.key === "warn") {
      const groups = {};
      s.copies.forEach((c) => (groups[c.v] = groups[c.v] || []).push(AG[c.agent].name));
      const newest = Math.max(...s.copies.map((c) => c.v));
      const odd = Object.entries(groups).filter(([v]) => +v !== newest).flatMap(([, n]) => n);
      return `<div class="explain warn">${icon("alert")}<div><div class="explain-title">The copies don't match</div>
        <p>${esc(listJoin(odd))} ${odd.length === 1 ? "has" : "have"} an older version. Your agents may answer differently.</p>
        <button class="btn btn-primary btn-sm" type="button" data-action="match">${icon("sync", "i-sm")}Make all copies match</button></div></div>`;
    }
    if (st.key === "bad") {
      return `<div class="explain bad">${icon("xCircle")}<div><div class="explain-title">One copy can't be read</div>
        <p>${esc(s.problem || "The file is damaged, so the agent skips it.")}</p>
        <button class="btn btn-quiet btn-sm" type="button" data-soon="Fix the file">${icon("pencil", "i-sm")}Open the file to fix it</button></div></div>`;
    }
    return `<div class="explain off">${icon("power")}<div><div class="explain-title">Turned off</div>
      <p>No agent uses this skill right now. It's kept so you can turn it back on later.</p>
      <button class="btn btn-quiet btn-sm" type="button" data-action="all-on">${icon("power", "i-sm")}Turn on everywhere</button></div></div>`;
  }

  function detailHtml(s) {
    const st = statusOf(s);
    const anyOn = s.copies.some((c) => c.state === "on");
    const tabs = [["where", "Where it lives"], ["read", "Read it"], ["history", "History"]];
    return `<aside class="detail" aria-labelledby="detail-name">
      <div class="detail-top">
        <button class="btn btn-ghost btn-sm back-btn" type="button" data-close>${icon("left", "i-sm")}All skills</button>
        <span class="detail-crumb">${esc(s.category)}</span>
        <button class="icon-btn detail-close" type="button" data-close aria-label="Close details">${icon("close")}</button>
      </div>
      <div class="detail-head">
        <h2 class="detail-name" id="detail-name" tabindex="-1">${esc(s.name)}</h2>
        <p class="detail-desc">${esc(s.description)}</p>
        <div class="detail-facts">
          ${statusPill(st)}
          <span class="fact">${s.copies.length} ${s.copies.length === 1 ? "copy" : "copies"}</span>
          <span class="fact" title="${fmt(s.tokens)} tokens">${sizeOf(s.tokens)} · about ${words(s.tokens)} words</span>
          <span class="fact">Changed ${esc(s.updated)}</span>
        </div>
        <div class="detail-actions">
          <button class="btn btn-quiet btn-sm" type="button" data-action="share">${icon("copy", "i-sm")}Add to another agent</button>
          <button class="btn btn-quiet btn-sm" type="button" data-action="${anyOn ? "all-off" : "all-on"}">${icon("power", "i-sm")}${anyOn ? "Turn off" : "Turn on"}</button>
          <button class="btn btn-danger btn-sm" type="button" data-action="trash">${icon("trash", "i-sm")}Move to trash</button>
        </div>
      </div>
      ${explainHtml(s)}
      <div class="tabs" role="tablist" aria-label="Skill details">
        ${tabs.map(([id, label]) => `<button class="tab" role="tab" id="tab-${id}" aria-controls="panel" aria-selected="${state.tab === id}" tabindex="${state.tab === id ? 0 : -1}" data-tab="${id}">${label}</button>`).join("")}
      </div>
      <div class="tab-panel" role="tabpanel" id="panel" aria-labelledby="tab-${state.tab}">${tabPanel(s)}</div>
    </aside>`;
  }

  function tabPanel(s) {
    if (state.tab === "read") {
      return `<div class="doc-note">${icon("file", "i-sm")}This is what the agent reads. Shown from ${esc(AG[s.copies[0].agent].name)}.</div>
        <div class="doc">${md(D.bodies[s.name] || D.defaultBody(s))}</div>`;
    }
    if (state.tab === "history") {
      const items = state.history.filter((h) => h.what.startsWith(s.name + " "));
      const rows = items.length ? items : [{ when: s.updated, what: `${s.name} was last changed` }];
      return `<ul class="history">${rows.map((h) => `<li><time>${esc(h.when)}</time><span>${esc(h.what)}</span></li>`).join("")}
        <li><time>Earlier</time><span>${esc(s.name)} was added to Skills Manager</span></li></ul>`;
    }
    const newest = Math.max(...s.copies.map((c) => c.v));
    return `<div class="copies">
      ${s.copies.map((c, i) => {
        const a = AG[c.agent];
        const tag = c.state === "broken" ? `<span class="tag bad">Can't be read</span>` : c.v < newest ? `<span class="tag warn">Older version</span>` : "";
        return `<div class="copy">
          ${tile(c.agent)}
          <div style="min-width:0"><div class="copy-name">${esc(a.name)} ${tag}</div>
            <div class="copy-path"><span title="${esc(a.path)}/${esc(s.name)}"><bdi>${esc(a.path)}/${esc(s.name)}</bdi></span><button type="button" data-copy-path="${esc(a.path + "/" + s.name)}" aria-label="Copy folder path for ${esc(a.name)}">${icon("copy", "i-sm")}</button></div></div>
          <label class="switch"><input type="checkbox" data-toggle="${i}" ${c.state === "on" ? "checked" : ""} ${c.state === "broken" ? "disabled" : ""}><span class="track"></span><span>${c.state === "on" ? "On" : c.state === "broken" ? "Skipped" : "Off"}</span><span class="sr-only"> for ${esc(a.name)}</span></label>
        </div>`;
      }).join("")}
      <button class="btn btn-ghost btn-sm add-copy" type="button" data-action="share">${icon("plus", "i-sm")}Add to another agent</button>
    </div>`;
  }

  /* Tiny, fully escaped Markdown renderer (headings, lists, quotes, bold, code). */
  function md(src) {
    const inline = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
    const out = []; let list = null;
    const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
    src.split("\n").forEach((line) => {
      let m;
      if ((m = line.match(/^(#{1,3})\s+(.*)/))) { close(); const l = Math.min(m[1].length, 2); out.push(`<h${l}>${inline(m[2])}</h${l}>`); }
      else if ((m = line.match(/^\d+\.\s+(.*)/))) { if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; } out.push(`<li>${inline(m[1])}</li>`); }
      else if ((m = line.match(/^[-*]\s+(.*)/))) { if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inline(m[1])}</li>`); }
      else if ((m = line.match(/^>\s?(.*)/))) { close(); out.push(`<blockquote><p>${inline(m[1])}</p></blockquote>`); }
      else if (line.trim()) { close(); out.push(`<p>${inline(line)}</p>`); }
      else close();
    });
    close();
    return out.join("");
  }

  /* ---------- Dialogs ---------- */
  let lastFocus = null;
  function openDialog(html, onConfirm) {
    lastFocus = document.activeElement;
    const ov = document.createElement("div");
    ov.className = "overlay";
    ov.innerHTML = `<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="dlg-title">${html}</div>`;
    document.body.appendChild(ov);
    $("#main").inert = true; $(".sidebar").inert = true;
    const close = () => { ov.remove(); $("#main").inert = false; $(".sidebar").inert = false; lastFocus && lastFocus.focus && lastFocus.focus(); };
    ov.addEventListener("click", (e) => {
      if (e.target === ov || e.target.closest("[data-dlg-cancel]")) close();
      if (e.target.closest("[data-dlg-ok]")) { onConfirm(ov); close(); }
    });
    ov.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.stopPropagation(); close(); }
      if (e.key === "Tab") {
        const f = [...ov.querySelectorAll("button, input")].filter((x) => !x.disabled);
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    });
    (ov.querySelector("[data-dlg-cancel]") || ov.querySelector("button")).focus();
  }

  function shareDialog(s) {
    const have = new Set(s.copies.map((c) => c.agent));
    const options = D.agents.filter((a) => !have.has(a.id));
    if (!options.length) return toast(`“${s.name}” is already in every agent.`);
    openDialog(`
      <div class="dialog-head"><h2 id="dlg-title">Add “${esc(s.name)}” to another agent</h2>
        <p>We'll copy the newest version. The agents that already have it won't change.</p></div>
      <div class="dialog-body">
        ${options.map((a) => `<label class="pick"><input type="checkbox" value="${a.id}">${tile(a.id)}<span><b>${esc(a.name)}</b><br><span class="pick-note">${esc(a.path)}</span></span></label>`).join("")}
      </div>
      <div class="dialog-foot"><button class="btn btn-ghost" data-dlg-cancel>Cancel</button><button class="btn btn-primary" data-dlg-ok>Add copies</button></div>`,
      (ov) => {
        const picked = [...ov.querySelectorAll("input:checked")].map((i) => i.value);
        if (!picked.length) return;
        const v = Math.max(...s.copies.map((c) => c.v));
        const before = s.copies.slice();
        picked.forEach((id) => s.copies.push({ agent: id, state: "on", v }));
        log(`${s.name} was added to ${listJoin(picked.map((id) => AG[id].name))}`, "add");
        render();
        toast(`Added to ${listJoin(picked.map((id) => AG[id].name))}`, () => { s.copies = before; render(); });
      });
  }

  function matchDialog(s) {
    const newest = Math.max(...s.copies.map((c) => c.v));
    const src = s.copies.find((c) => c.v === newest);
    const odd = s.copies.filter((c) => c.v !== newest && c.state !== "broken");
    openDialog(`
      <div class="dialog-head"><h2 id="dlg-title">Make all copies match</h2>
        <p>The newest version will replace the older ones. A backup is saved first, so you can undo this.</p></div>
      <div class="dialog-body">
        <div class="preview-box"><b>Use the version from:</b> ${esc(AG[src.agent].name)} (newest)</div>
        <div class="preview-box"><b>Will be updated:</b> ${esc(listJoin(odd.map((c) => AG[c.agent].name)))}</div>
      </div>
      <div class="dialog-foot"><button class="btn btn-ghost" data-dlg-cancel>Cancel</button><button class="btn btn-primary" data-dlg-ok>${icon("sync", "i-sm")}Update ${odd.length} ${odd.length === 1 ? "copy" : "copies"}</button></div>`,
      () => {
        const before = s.copies.map((c) => ({ ...c }));
        odd.forEach((c) => (c.v = newest));
        log(`${s.name} copies were made to match`, "sync");
        render();
        toast("All copies now match", () => { s.copies = before; render(); });
      });
  }

  /* ---------- Toasts & log ---------- */
  function toast(text, undo) {
    const t = document.createElement("div");
    t.className = "toast";
    t.innerHTML = `${icon("checkCircle")}<span>${esc(text)}</span>${undo ? '<button type="button">Undo</button>' : ""}`;
    $("#toasts").appendChild(t);
    const kill = () => t.remove();
    if (undo) t.querySelector("button").addEventListener("click", () => { undo(); kill(); toast("Undone"); });
    setTimeout(kill, undo ? 8000 : 3500);
  }
  function log(what, kind) { state.history.unshift({ when: "Just now", what, kind }); }

  /* ---------- Router & render ---------- */
  function route() {
    const h = location.hash.replace(/^#\/?/, "");
    const [page, ...rest] = h.split("/");
    return { page: page === "skills" ? "skills" : "home", skill: rest.length ? decodeURIComponent(rest.join("/")) : null };
  }

  let lastPage = null, lastSkill = null;
  function render(opts = {}) {
    const r = route();
    const main = $("#main");
    const keepScroll = window.scrollY;
    main.innerHTML = r.page === "skills" ? renderSkills(r.skill && find(r.skill) ? r.skill : null) : renderHome();
    document.querySelectorAll("[data-route]").forEach((a) => { if (a.dataset.route === r.page) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    const nav = $("#nav-skill-count"); if (nav) nav.textContent = state.skills.length;
    document.title = (r.page === "skills" ? (r.skill ? r.skill + " · Skills" : "Skills") : "Home") + " · Skills Manager";

    if (r.page !== lastPage) { window.scrollTo(0, 0); $("#page-title") && $("#page-title").focus({ preventScroll: true }); }
    else if (r.skill && r.skill !== lastSkill) { $("#detail-name") && $("#detail-name").focus({ preventScroll: true }); if (matchMedia("(max-width: 960px)").matches) window.scrollTo(0, 0); }
    else if (opts.focus) { const el = $(opts.focus); el && el.focus(); window.scrollTo(0, keepScroll); }
    else window.scrollTo(0, keepScroll);
    lastPage = r.page; lastSkill = r.skill;
  }

  const go = (hash) => { if (location.hash === hash) render(); else location.hash = hash; };

  /* ---------- Events ---------- */
  document.addEventListener("click", (e) => {
    const t = e.target.closest("button, a"); if (!t) return;
    const r = route();
    const s = r.skill && find(r.skill);

    if (t.dataset.goFilter) { state.filter = t.dataset.goFilter; state.agent = "any"; state.query = ""; return go("#/skills"); }
    if (t.dataset.agent) { state.agent = t.dataset.agent; state.filter = "all"; state.query = ""; return go("#/skills"); }
    if (t.hasAttribute("data-more-todo")) { state.showAllTodo = !state.showAllTodo; return render({ focus: "[data-more-todo]" }); }
    if (t.hasAttribute("data-hide-tip")) { state.tipHidden = true; render({ focus: "#home-q" }); return; }
    if (t.dataset.todo !== undefined) {
      const item = attentionItems()[+t.dataset.todo];
      if (item.soon) return toast("Trash & backups comes in the next prototype");
      if (item.filterAgent) { state.agent = item.filterAgent; state.filter = "all"; state.query = ""; return go("#/skills"); }
      state.filter = "all"; state.agent = "any"; state.query = ""; state.tab = "where";
      return go("#/skills/" + encodeURIComponent(item.go));
    }
    if (t.dataset.soon) return toast(`“${t.dataset.soon}” is part of the next prototype`);
    if (t.dataset.filter) { state.filter = t.dataset.filter; return render({ focus: `[data-filter="${t.dataset.filter}"]` }); }
    if (t.dataset.skill) { state.tab = state.tab || "where"; return go("#/skills/" + encodeURIComponent(t.dataset.skill)); }
    if (t.hasAttribute("data-close")) { const n = r.skill; go("#/skills"); setTimeout(() => { const row = document.querySelector(`[data-skill="${CSS.escape(n)}"]`); row && row.focus(); }, 0); return; }
    if (t.hasAttribute("data-clear")) { state.query = ""; state.filter = "all"; state.agent = "any"; return render({ focus: "#skills-q" }); }
    if (t.dataset.tab) { state.tab = t.dataset.tab; return render({ focus: `[data-tab="${t.dataset.tab}"]` }); }
    if (t.dataset.copyPath) { navigator.clipboard && navigator.clipboard.writeText(t.dataset.copyPath).catch(() => {}); return toast("Folder path copied"); }

    if (t.dataset.action && s) {
      const a = t.dataset.action;
      if (a === "share") return shareDialog(s);
      if (a === "match") return matchDialog(s);
      if (a === "all-off" || a === "all-on") {
        const before = s.copies.map((c) => ({ ...c }));
        s.copies.forEach((c) => { if (c.state !== "broken") c.state = a === "all-on" ? "on" : "off"; });
        log(`${s.name} was turned ${a === "all-on" ? "on" : "off"}`, a === "all-on" ? "on" : "off");
        render({ focus: `[data-action="${a === "all-on" ? "all-off" : "all-on"}"]` });
        return toast(`Turned ${a === "all-on" ? "on" : "off"} in every agent`, () => { s.copies = before; render(); });
      }
      if (a === "trash") {
        const idx = state.skills.indexOf(s);
        state.skills.splice(idx, 1);
        log(`${s.name} was moved to the trash`, "trash");
        go("#/skills");
        return toast(`Moved “${s.name}” to the trash`, () => { state.skills.splice(idx, 0, s); go("#/skills/" + encodeURIComponent(s.name)); });
      }
    }
  });

  document.addEventListener("change", (e) => {
    const t = e.target;
    if (t.id === "agent-sel") { state.agent = t.value; return render({ focus: "#agent-sel" }); }
    if (t.dataset.toggle !== undefined) {
      const s = find(route().skill); const c = s.copies[+t.dataset.toggle];
      c.state = t.checked ? "on" : "off";
      log(`${s.name} was turned ${c.state} in ${AG[c.agent].name}`, c.state);
      render({ focus: `[data-toggle="${t.dataset.toggle}"]` });
      toast(`${t.checked ? "Turned on" : "Turned off"} in ${AG[c.agent].name}`, () => { c.state = t.checked ? "off" : "on"; render(); });
    }
  });

  let searchTimer;
  document.addEventListener("input", (e) => {
    if (e.target.id !== "skills-q") return;
    clearTimeout(searchTimer);
    const v = e.target.value;
    searchTimer = setTimeout(() => { state.query = v; const pos = e.target.selectionStart; render({ focus: "#skills-q" }); const i = $("#skills-q"); i && i.setSelectionRange(pos, pos); }, 120);
  });

  document.addEventListener("submit", (e) => {
    if (!e.target.matches("[data-home-search]")) return;
    e.preventDefault();
    state.query = $("#home-q").value; state.filter = "all"; state.agent = "any";
    go("#/skills");
  });

  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (e.key === "/" && !typing && !document.querySelector(".overlay")) {
      e.preventDefault(); ($("#skills-q") || $("#home-q")).focus();
    }
    if (e.key === "Escape" && !document.querySelector(".overlay")) {
      if (typing && document.activeElement.value) return;
      if (route().skill) { const n = route().skill; go("#/skills"); setTimeout(() => { const row = document.querySelector(`[data-skill="${CSS.escape(n)}"]`); row && row.focus(); }, 0); }
    }
    // Arrow keys move between rows; between tabs.
    if ((e.key === "ArrowDown" || e.key === "ArrowUp") && document.activeElement.classList.contains("row")) {
      e.preventDefault();
      const rows = [...document.querySelectorAll(".row")];
      const i = rows.indexOf(document.activeElement) + (e.key === "ArrowDown" ? 1 : -1);
      rows[Math.max(0, Math.min(rows.length - 1, i))].focus();
    }
    if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && document.activeElement.classList.contains("tab")) {
      const tabs = [...document.querySelectorAll(".tab")];
      const i = (tabs.indexOf(document.activeElement) + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
      state.tab = tabs[i].dataset.tab; render({ focus: `[data-tab="${state.tab}"]` });
    }
  });

  /* Theme */
  function themeNow() {
    const set = document.documentElement.dataset.theme;
    return set || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }
  function paintThemeBtns() {
    const dark = themeNow() === "dark";
    document.querySelectorAll("#theme-btn, #tab-theme").forEach((b) => {
      b.querySelector("[data-icon]").innerHTML = icon(dark ? "sun" : "moon");
      b.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
      const l = b.querySelector(".theme-label"); if (l) l.textContent = dark ? "Light mode" : "Dark mode";
    });
  }
  document.querySelectorAll("#theme-btn, #tab-theme").forEach((b) => b.addEventListener("click", () => {
    const next = themeNow() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("clear-theme", next); } catch (e) {}
    paintThemeBtns();
  }));

  // Static icons in the shell
  document.querySelectorAll("[data-icon]").forEach((el) => (el.innerHTML = icon(el.dataset.icon)));
  paintThemeBtns();
  window.addEventListener("hashchange", () => render());
  if (!location.hash) history.replaceState(null, "", "#/home");
  render();
})();
