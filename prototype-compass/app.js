/* Compass prototype. Vanilla JS, no build, no network. All state is in memory. */
(function () {
  "use strict";
  const D = window.COMPASS_DATA;
  const AG = Object.fromEntries(D.agents.map((a) => [a.id, a]));
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (n) => n.toLocaleString("en-US");
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + "s"}`;
  const join = (a) => (a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]);

  /* ---------- Icons ---------- */
  const P = {
    compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2.2 4.8-4.8 2.2 2.2-4.8z"/>',
    stack: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/>',
    lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    ok: '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 3 3 5-6"/>',
    warn: '<path d="M12 3.5 2.8 19.5h18.4L12 3.5Z"/><path d="M12 10v4M12 17v.01"/>',
    bad: '<path d="M8.2 3h7.6L21 8.2v7.6L15.8 21H8.2L3 15.8V8.2Z"/><path d="m9.5 9.5 5 5M14.5 9.5l-5 5"/>',
    off: '<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    old: '<path d="M4 12a8 8 0 1 0 2.3-5.6"/><path d="M4 4v4h4"/><path d="M12 8v4l2.5 2"/>',
    chev: '<path d="m9 6 6 6-6 6"/>',
    left: '<path d="m15 6-6 6 6 6"/>',
    up: '<path d="m6 15 6-6 6 6"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    power: '<path d="M12 3v8"/><path d="M6.4 6.6a8 8 0 1 0 11.2 0"/>',
    trash: '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    sync: '<path d="M4 12a8 8 0 0 1 14-5.3L20 9"/><path d="M20 4v5h-5"/><path d="M20 12a8 8 0 0 1-14 5.3L4 15"/><path d="M4 20v-5h5"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.01"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.5V14M12 17v.01"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    archive: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/>',
    pencil: '<path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
  };
  const ic = (n, c = "") => `<svg class="i ${c}" viewBox="0 0 24 24" aria-hidden="true">${P[n] || ""}</svg>`;

  /* ---------- State ---------- */
  const clone = (x) => JSON.parse(JSON.stringify(x));
  const S = {
    skills: clone(D.skills),
    activity: clone(D.activity),
    filter: "all", sort: "attention", view: "list", query: "",
    selected: new Set(),
    tab: "copies", source: false, readFrom: null, cmpA: null, cmpB: null,
    demo: "normal", scan: 0, scanError: false,
    fixed: [], // {name, label, undo}
  };

  /* ---------- Model helpers ---------- */
  const STATUS = {
    bad: { key: "bad", label: "Can't be read", icon: "bad", rank: 0 },
    warn: { key: "warn", label: "Copies differ", icon: "warn", rank: 1 },
    ok: { key: "ok", label: "Working", icon: "ok", rank: 2 },
    off: { key: "off", label: "Turned off", icon: "off", rank: 3 },
  };
  const visibleCopies = (s) => s.copies.filter((c) => !(S.scanError && c.agent === "cursor"));
  function status(s) {
    const cs = visibleCopies(s);
    if (cs.some((c) => c.state === "broken")) return STATUS.bad;
    if (!cs.some((c) => c.state === "on")) return STATUS.off;
    const vs = new Set(cs.filter((c) => c.state !== "broken").map((c) => c.v));
    return vs.size > 1 ? STATUS.warn : STATUS.ok;
  }
  const newest = (s) => Math.max(...s.copies.filter((c) => c.state !== "broken").map((c) => c.v), 0);
  const sizeWord = (t) => (t < 1000 ? "Small" : t < 3500 ? "Medium" : "Large");
  const words = (t) => fmt(Math.round((t * 0.75) / 10) * 10);
  const find = (n) => S.skills.find((s) => s.name === n);
  const tag = (st) => `<span class="tag ${st.key}">${ic(st.icon)}${st.label}</span>`;
  const chip = (id) => `<span class="chip" style="--h:${AG[id].hue}" aria-hidden="true">${AG[id].initials}</span>`;
  const counts = () => {
    const c = { ok: 0, warn: 0, bad: 0, off: 0 };
    S.skills.forEach((s) => c[status(s).key]++);
    return c;
  };
  const SUGGESTED = 20; // % of reading space we suggest skills stay under (demo policy)
  function load(id) {
    const on = S.skills.filter((s) => s.copies.some((c) => c.agent === id && c.state === "on"));
    const tokens = on.reduce((n, s) => n + s.tokens, 0);
    return { id, on: on.length, total: S.skills.filter((s) => s.copies.some((c) => c.agent === id)).length, tokens, pct: Math.round((tokens / AG[id].limit) * 1000) / 10 };
  }
  function bodyFor(s, v) {
    const vs = D.versions[s.name];
    return (vs && (vs[v] || vs[newest(s)])) || D.genericBody(s);
  }
  const term = (key, text) => `<button type="button" class="term" data-term="${key}" aria-expanded="false">${text}</button>`;

  /* ---------- Tasks for the Overview "To fix" list ---------- */
  function tasks() {
    const out = [];
    S.skills.forEach((s) => {
      const st = status(s);
      if (st.key === "bad") {
        const broken = s.copies.find((c) => c.state === "broken");
        const sole = !s.copies.some((c) => c.state !== "broken");
        out.push({ name: s.name, st, title: sole ? `No agent can find “${s.name}”` : `${AG[broken.agent].name} can't read “${s.name}”`, text: s.problem, action: s.fix, kind: "repair" });
      } else if (st.key === "warn") {
        const nv = newest(s);
        const older = s.copies.filter((c) => c.v < nv && c.state !== "broken").map((c) => AG[c.agent].name);
        out.push({ name: s.name, st, title: `“${s.name}” is different in ${join(older)}`,
          text: `${join(older)} ${older.length === 1 ? "has" : "have"} an older version, so ${older.length === 1 ? "it" : "they"} may give different answers than your other agents.`,
          action: "Review and update", kind: "match" });
      }
    });
    return out.sort((a, b) => a.st.rank - b.st.rank);
  }

  /* ---------- OVERVIEW ---------- */
  function overview() {
    if (S.demo === "first-run") return firstRun("overview");
    if (S.demo === "loading") return loadingView("overview");
    const c = counts();
    const total = S.skills.length;
    const agentsUsed = D.agents.filter((a) => load(a.id).total > 0).length;
    const t = tasks();
    const need = c.bad + c.warn;
    const intro = `You have ${total} ${term("skill", "skills")} in ${agentsUsed} ${term("agent", "agents")}`;
    const sentence = need
      ? `${intro}. <strong>${need} ${need === 1 ? "needs" : "need"} your attention</strong>; the rest are working.`
      : `${intro}, and all of them are working.`;
    const loads = D.agents.filter((a) => a.id !== "library").map((a) => load(a.id)).filter((l) => l.total).sort((a, b) => b.pct - a.pct);
    const scale = Math.max(30, Math.ceil(Math.max(...loads.map((l) => l.pct)) / 10) * 10);

    return `<div class="page">
      <div class="head">
        <div>
          <h1 class="h1" id="h1" tabindex="-1">Overview</h1>
          <p class="sub">${sentence}</p>
        </div>
      </div>

      ${S.scanError ? `<div class="banner bad" role="alert">${ic("bad")}
        <div><div class="banner-t">We couldn't read Cursor's folder</div>
        <p>Skills Manager doesn't have permission to open <code>~/.cursor/skills</code>, so Cursor's skills aren't shown below. Nothing was changed.</p></div>
        <div class="banner-acts"><button class="btn btn-secondary btn-sm" type="button" data-act="retry">${ic("refresh", "i-s")}Try again</button></div></div>` : ""}

      <div class="stats">
        ${[["ok", "Working", c.ok, "Show working skills", "working"], ["warn", "Need attention", need, "Show these", "attention"], ["off", "Turned off", c.off, "Show turned off", "off"]]
          .map(([k, label, n, link, f]) => `<button type="button" class="stat" data-goto-filter="${f}">
            <span class="stat-k"><span class="st ${k === "warn" && c.bad ? "bad" : k}">${ic(k === "warn" && c.bad ? "bad" : k)}</span>${label}</span>
            <span class="stat-v num">${n}</span><span class="stat-l">${link}${ic("chev", "i-s")}</span></button>`).join("")}
      </div>

      <details class="how">
        <summary>${ic("help")}How Skills Manager works${ic("chev")}</summary>
        <div class="how-body">
          <div class="how-step"><b>1. A skill is a set of instructions</b>Your AI coding tools (we call them agents) read skills to learn how to do a task, like reviewing code.</div>
          <div class="how-step"><b>2. Each agent keeps its own copy</b>The same skill can live in several agents. If the copies drift apart, the agents start behaving differently.</div>
          <div class="how-step"><b>3. We show every copy in one place</b>Fix problems with one click. Everything can be undone, and nothing is uploaded.</div>
        </div>
      </details>

      <section class="sec" aria-labelledby="fix-h">
        <div class="sec-h"><div><h2 class="h2" id="fix-h">To fix</h2>
          <p class="sec-sub">Most serious first. Nothing changes until you choose.</p></div></div>
        <div class="panel"><ul class="tasks">
          ${t.length || S.fixed.length ? "" : `<li class="task-empty"><span class="ic">${ic("check")}</span><div><b>Nothing needs your attention</b><p class="sec-sub">Every skill can be read and every copy matches.</p></div></li>`}
          ${t.map((x, i) => `<li class="task">
              <div><div class="task-t">${tag(x.st)}<a href="#/skills/${encodeURIComponent(x.name)}">${esc(x.title)}</a></div>
              <p class="task-d">${esc(x.text)}</p></div>
              <div class="task-acts"><button class="btn ${i === 0 ? "btn-primary" : "btn-secondary"} btn-sm" type="button" data-task="${i}">${esc(x.action)}</button></div>
            </li>`).join("")}
          ${S.fixed.map((f, i) => `<li class="task done">
              <div><div class="task-t"><span class="tag ok">${ic("check")}Fixed</span>${esc(f.label)}</div></div>
              <div class="task-acts"><button class="btn btn-text btn-sm" type="button" data-undo-fix="${i}">Undo</button></div>
            </li>`).join("")}
        </ul></div>
      </section>

      <section class="sec" aria-labelledby="space-h">
        <div class="sec-h"><div><h2 class="h2" id="space-h">${term("space", "Reading space")} used by skills</h2>
          <p class="sec-sub">Skills take up part of what each agent can read at once. Less is better: it leaves more room for your code.</p></div></div>
        <div class="panel space">
          ${loads.map((l) => `<div class="space-row">
              <span class="space-name">${chip(l.id)}<span>${esc(AG[l.id].name)}</span></span>
              <span class="bar" role="img" aria-label="${esc(AG[l.id].name)}: ${l.pct}% used, suggested limit ${SUGGESTED}%">
                <span class="bar-fill ${l.pct > SUGGESTED ? "warn" : ""}" style="width:${Math.max((l.pct / scale) * 100, 0.8)}%"></span>
                <span class="bar-mark" style="left:${(SUGGESTED / scale) * 100}%"></span>
              </span>
              <span class="space-v num"><b>${l.pct}%</b> · ${plural(l.on, "skill")} on${l.pct > SUGGESTED ? `<br><span class="st warn">${ic("warn")}Over suggested limit</span>` : ""}</span>
            </div>`).join("")}
          <div class="space-note"><span><i class="key" aria-hidden="true"></i>Space used</span><span><i class="key mark" aria-hidden="true"></i>Suggested limit (${SUGGESTED}%)</span><span>Sorted from most to least</span></div>
        </div>
      </section>

      <section class="sec" aria-labelledby="act-h">
        <div class="sec-h"><div><h2 class="h2" id="act-h">Recent changes</h2><p class="sec-sub">What changed and when. Each change was backed up first.</p></div></div>
        <ul class="panel feed">
          ${S.activity.slice(0, 6).map((a) => `<li><span class="ic">${ic({ sync: "sync", add: "plus", off: "power", on: "power", trash: "trash", backup: "archive", fix: "check" }[a.kind] || "clock", "i-s")}</span>
            <span>${esc(a.text)}<small>${esc(a.when)}</small></span></li>`).join("")}
        </ul>
      </section>
    </div>`;
  }

  /* ---------- SKILLS ---------- */
  function visible() {
    const q = S.query.trim().toLowerCase();
    const list = S.skills.filter((s) => {
      const k = status(s).key;
      if (S.filter === "attention" && k !== "warn" && k !== "bad") return false;
      if (S.filter === "off" && k !== "off") return false;
      if (S.filter === "working" && k !== "ok") return false;
      if (q && !`${s.name} ${s.description} ${s.category}`.toLowerCase().includes(q)) return false;
      return true;
    });
    const by = {
      attention: (a, b) => status(a).rank - status(b).rank || a.name.localeCompare(b.name),
      az: (a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
      size: (a, b) => b.tokens - a.tokens,
    }[S.sort];
    return list.sort(by);
  }

  function skillsPage() {
    if (S.demo === "first-run") return firstRun("skills");
    const c = counts();
    const list = visible();
    const loading = S.demo === "loading";
    const fbtn = (id, label, n) => `<button type="button" data-filter="${id}" aria-pressed="${S.filter === id}">${label}<span class="n num">${n}</span></button>`;
    const sel = S.selected.size;
    const allSel = list.length && list.every((s) => S.selected.has(s.name));
    const someSel = list.some((s) => S.selected.has(s.name));

    const toolbar = sel ? `<div class="batch" role="region" aria-label="Actions for selected skills">
        <b>${sel} selected</b>
        <button class="btn btn-sm" type="button" data-batch="on">${ic("power", "i-s")}Turn on</button>
        <button class="btn btn-sm" type="button" data-batch="off">${ic("power", "i-s")}Turn off</button>
        <button class="btn btn-sm" type="button" data-batch="trash">${ic("trash", "i-s")}Move to trash</button>
        <span class="grow"></span>
        <button class="btn btn-sm" type="button" data-batch="cancel">Cancel</button></div>`
      : `<div class="filters" role="group" aria-label="Show">${fbtn("all", "All", S.skills.length)}${fbtn("attention", "Need attention", c.bad + c.warn)}${fbtn("off", "Turned off", c.off)}</div>
        <label class="sel-wrap">Sort<select class="sel" id="sort">
          <option value="attention" ${S.sort === "attention" ? "selected" : ""}>Needs attention first</option>
          <option value="az" ${S.sort === "az" ? "selected" : ""}>Name, A to Z</option>
          <option value="size" ${S.sort === "size" ? "selected" : ""}>Largest first</option></select></label>
        <span class="grow"></span>
        <div class="filters" role="group" aria-label="View">
          <button type="button" data-view="list" aria-pressed="${S.view === "list"}">${ic("list", "i-s")}List</button>
          <button type="button" data-view="grid" aria-pressed="${S.view === "grid"}">${ic("grid", "i-s")}By agent</button>
        </div>`;

    let body;
    if (loading) body = skeletonTable();
    else if (!list.length) body = noResults();
    else body = S.view === "grid" ? gridView(list) : listView(list, allSel, someSel);

    return `<div class="page">
      <div class="head">
        <div><h1 class="h1" id="h1" tabindex="-1">Skills</h1>
          <p class="sub">Every ${term("skill", "skill")} on this computer, with all its ${term("copy", "copies")} on one line.</p></div>
        <button class="btn btn-primary" type="button" data-soon="New skill">${ic("plus")}New skill</button>
      </div>
      ${S.scanError ? `<div class="banner bad" role="alert">${ic("bad")}<div><div class="banner-t">Cursor's skills aren't shown</div>
        <p>We couldn't open <code>~/.cursor/skills</code>. Nothing was changed.</p></div>
        <div class="banner-acts"><button class="btn btn-secondary btn-sm" type="button" data-act="retry">${ic("refresh", "i-s")}Try again</button></div></div>` : ""}
      <div class="search" role="search">${ic("search")}
        <label class="sr-only" for="q">Search skills</label>
        <input id="q" type="search" placeholder="Search by name or what it does" value="${esc(S.query)}" autocomplete="off" ${loading ? "disabled" : ""}>
        <span class="kbd" aria-hidden="true">/</span></div>
      <div class="bar-tools">${toolbar}</div>
      ${!loading && list.length ? `<p class="count" style="margin-top:6px">${list.length === S.skills.length ? `${list.length} skills` : `Showing ${list.length} of ${S.skills.length} skills`}</p>` : ""}
      ${body}
    </div>`;
  }

  function listView(list, allSel, someSel) {
    return `<div class="panel table" role="table" aria-label="Skills" aria-rowcount="${list.length + 1}">
      <div class="thead" role="row">
        <span role="columnheader"><span class="cb"><input type="checkbox" id="sel-all" aria-label="Select all shown skills" ${allSel ? "checked" : ""} data-indeterminate="${!allSel && someSel}"></span></span>
        <span role="columnheader">Skill</span><span role="columnheader">Used by</span><span role="columnheader">Status</span><span role="columnheader" class="r">Size</span>
      </div>
      ${list.map((s) => {
        const st = status(s);
        const cs = visibleCopies(s);
        const show = cs.length > 5 ? cs.slice(0, 4) : cs;
        return `<div class="trow ${S.selected.has(s.name) ? "is-sel" : ""}" role="row">
          <span role="cell"><span class="cb"><input type="checkbox" data-sel="${esc(s.name)}" aria-label="Select ${esc(s.name)}" ${S.selected.has(s.name) ? "checked" : ""}></span></span>
          <span role="cell" class="cell-name"><a class="rlink" href="#/skills/${encodeURIComponent(s.name)}">${esc(s.name)}</a><span class="rdesc">${esc(s.description)}</span></span>
          <span role="cell" class="cell-agents" title="${esc(cs.map((c) => AG[c.agent].name).join(", "))}">${show.map((c) => chip(c.agent)).join("")}${cs.length > show.length ? `<span class="more">+${cs.length - show.length}</span>` : ""}<span class="sr-only">${esc(join(cs.map((c) => AG[c.agent].name)))}</span></span>
          <span role="cell"><span class="st ${st.key}">${ic(st.icon)}${st.label}</span></span>
          <span role="cell" class="size r num">${sizeWord(s.tokens)}<small>${fmt(s.tokens)} tokens</small></span>
        </div>`;
      }).join("")}
    </div>`;
  }

  function gridView(list) {
    const ags = D.agents.filter((a) => !(S.scanError && a.id === "cursor"));
    const cell = (s, a) => {
      const c = s.copies.find((x) => x.agent === a.id);
      if (!c) return `<td><span class="sr-only">No copy</span></td>`;
      const nv = newest(s);
      const [k, i, l] = c.state === "broken" ? ["bad", "bad", "Can't be read"] : c.state === "off" ? ["off", "off", "Turned off"] : c.v < nv ? ["old", "old", "Older version"] : ["on", "check", "On, up to date"];
      return `<td><span class="cell ${k}" title="${esc(a.name)}: ${l}">${ic(i)}<span class="sr-only">${l}</span></span></td>`;
    };
    return `<div class="panel grid-wrap"><table class="mx">
      <caption class="sr-only">Each skill and its copy in each agent</caption>
      <thead><tr><th scope="col" style="text-align:left;padding-left:20px">Skill</th>${ags.map((a) => `<th scope="col">${chip(a.id)}${esc(a.short)}</th>`).join("")}</tr></thead>
      <tbody>${list.map((s) => `<tr><th scope="row"><a href="#/skills/${encodeURIComponent(s.name)}">${esc(s.name)}</a></th>${ags.map((a) => cell(s, a)).join("")}</tr>`).join("")}</tbody>
    </table>
    <div class="legend" aria-hidden="true">
      <span><span class="cell on">${ic("check")}</span>On, up to date</span>
      <span><span class="cell old">${ic("old")}</span>Older version</span>
      <span><span class="cell off">${ic("off")}</span>Turned off</span>
      <span><span class="cell bad">${ic("bad")}</span>Can't be read</span>
      <span>Blank: no copy in that agent</span>
    </div></div>`;
  }

  function noResults() {
    const q = S.query.trim();
    return `<div class="panel empty">
      <span class="ic">${ic(q ? "search" : "ok")}</span>
      <h2>${q ? `No skills match “${esc(q)}”` : S.filter === "attention" ? "Nothing needs attention" : "No skills are turned off"}</h2>
      <p>${q ? "Check the spelling, or search for what the skill does, like “tests” or “commit”." : "That's good news. Every skill in this view is working."}</p>
      <div class="acts"><button class="btn btn-secondary" type="button" data-act="clear">${q ? "Clear search" : "Show all skills"}</button></div>
    </div>`;
  }

  function skeletonTable() {
    const row = (w) => `<div class="trow" aria-hidden="true"><span class="cb"><span class="sk" style="width:18px;height:18px"></span></span>
      <span class="cell-name"><span class="sk" style="display:block;width:${w}%;height:14px"></span><span class="sk" style="display:block;width:${w + 25}%;height:11px;margin-top:8px"></span></span>
      <span class="cell-agents"><span class="sk" style="width:84px;height:26px"></span></span><span><span class="sk" style="display:block;width:90px;height:14px"></span></span><span class="r"><span class="sk" style="display:inline-block;width:56px;height:14px"></span></span></div>`;
    return `<div class="panel table" aria-busy="true"><div class="thead" aria-hidden="true"><span></span><span>Skill</span><span>Used by</span><span>Status</span><span class="r">Size</span></div>
      ${[34, 22, 40, 28, 18, 36].map(row).join("")}</div>`;
  }

  /* ---------- First run & loading ---------- */
  function firstRun(where) {
    return `<div class="page">
      <div class="head"><div><h1 class="h1" id="h1" tabindex="-1">${where === "skills" ? "Skills" : "Overview"}</h1></div></div>
      <div class="panel empty" style="margin-top:24px">
        <span class="ic">${ic("stack")}</span>
        <h2>No skills found yet</h2>
        <p>A ${term("skill", "skill")} is a set of written instructions your AI coding tools follow. Once you add one, you'll see it here with every copy, in every ${term("agent", "agent")}.</p>
        <div class="acts">
          <button class="btn btn-primary" type="button" data-soon="Create your first skill">${ic("plus")}Create your first skill</button>
          <button class="btn btn-secondary" type="button" data-soon="Add a folder of skills">${ic("folder")}Add a folder you already have</button>
        </div>
        <ul class="checked" aria-label="Folders we checked">
          ${D.agents.map((a) => `<li>${ic("check", "i-s")}<span>${esc(a.name)} <code>${esc(a.path)}</code>: empty</span></li>`).join("")}
        </ul>
      </div>
    </div>`;
  }

  function loadingView() {
    const steps = D.agents.length;
    const done = Math.min(S.scan, steps);
    const current = D.agents[Math.min(done, steps - 1)];
    return `<div class="page">
      <div class="head"><div><h1 class="h1" id="h1" tabindex="-1">Overview</h1><p class="sub">Looking for skills on this computer…</p></div></div>
      <div class="panel progress" aria-live="polite">
        <div class="progress-t"><span>${done >= steps ? "Finishing up" : `Checking ${esc(current.name)}'s folder`}</span><span class="num">${done} of ${steps} folders</span></div>
        <div class="ptrack" role="progressbar" aria-label="Scanning folders" aria-valuemin="0" aria-valuemax="${steps}" aria-valuenow="${done}"><div class="pfill" style="width:${(done / steps) * 100}%"></div></div>
        <small>Nothing is changed while we look. This usually takes a few seconds.</small>
      </div>
      <div class="stats" aria-hidden="true">${[0, 1, 2].map(() => `<div class="stat"><span class="sk" style="width:110px;height:14px"></span><span class="sk" style="width:48px;height:30px;margin-top:6px"></span></div>`).join("")}</div>
      <div class="sec" aria-hidden="true"><span class="sk" style="display:block;width:90px;height:18px;margin-bottom:14px"></span>
        <div class="panel">${[70, 55, 62].map((w) => `<div class="task"><div><span class="sk" style="display:block;width:${w}%;height:15px"></span><span class="sk" style="display:block;width:${w + 15}%;height:12px;margin-top:10px"></span></div><span class="sk" style="width:130px;height:32px"></span></div>`).join("")}</div></div>
    </div>`;
  }

  /* ---------- SKILL PAGE ---------- */
  function skillPage(name) {
    const s = find(name);
    if (!s) return `<div class="page"><div class="panel empty"><span class="ic">${ic("search")}</span><h2 id="h1" tabindex="-1">This skill isn't here any more</h2>
      <p>It may have been moved to the trash.</p><div class="acts"><a class="btn btn-secondary" href="#/skills">Back to Skills</a></div></div></div>`;
    const st = status(s);
    const list = visible();
    const idx = list.findIndex((x) => x.name === s.name);
    const prev = idx > 0 ? list[idx - 1] : null;
    const next = idx >= 0 && idx < list.length - 1 ? list[idx + 1] : null;
    const cs = visibleCopies(s);
    const nv = newest(s);
    const anyOn = cs.some((c) => c.state === "on");
    const differ = st.key === "warn";
    if (S.tab === "compare" && !differ && !(cs.length > 1)) S.tab = "copies";
    const tabs = [["copies", `Copies <span class="num">(${cs.length})</span>`], ["read", "Read"], ...(cs.length > 1 ? [["compare", `Compare${differ ? '<span class="dot" aria-hidden="true"></span><span class="sr-only"> (copies differ)</span>' : ""}`]] : []), ["history", "History"]];
    const pct = Math.round((s.tokens / 200000) * 1000) / 10;

    return `<div class="page">
      <div class="crumbs">
        <nav aria-label="Breadcrumb"><ol><li><a href="#/skills">Skills</a></li><li aria-hidden="true">${ic("chev", "i-s")}</li><li aria-current="page">${esc(s.name)}</li></ol></nav>
        ${idx >= 0 ? `<div class="stepper"><span class="num">${idx + 1} of ${list.length}</span>
          <a class="icon-btn" ${prev ? `href="#/skills/${encodeURIComponent(prev.name)}"` : 'aria-disabled="true"'} aria-label="Previous skill${prev ? ": " + esc(prev.name) : ""}">${ic("up")}</a>
          <a class="icon-btn" ${next ? `href="#/skills/${encodeURIComponent(next.name)}"` : 'aria-disabled="true"'} aria-label="Next skill${next ? ": " + esc(next.name) : ""}">${ic("down")}</a></div>` : ""}
      </div>

      <div class="detail">
        <div>
          <h1 class="d-title" id="h1" tabindex="-1">${esc(s.name)}</h1>
          <p class="d-desc">${esc(s.description)}</p>
          ${problemBanner(s, st)}
          <div class="d-acts">
            <button class="btn btn-secondary btn-sm" type="button" data-act="share">${ic("copy", "i-s")}Add to another agent</button>
            <button class="btn btn-secondary btn-sm" type="button" data-act="${anyOn ? "all-off" : "all-on"}">${ic("power", "i-s")}${anyOn ? "Turn off everywhere" : "Turn on everywhere"}</button>
            <button class="btn btn-danger btn-sm" type="button" data-act="trash">${ic("trash", "i-s")}Move to trash</button>
          </div>

          <div class="tabs" role="tablist" aria-label="About this skill">
            ${tabs.map(([id, label]) => `<button type="button" class="tab" role="tab" id="t-${id}" aria-controls="tp" aria-selected="${S.tab === id}" tabindex="${S.tab === id ? 0 : -1}" data-tab="${id}">${label}</button>`).join("")}
          </div>
          <div class="tabp" role="tabpanel" id="tp" aria-labelledby="t-${S.tab}">${tabPanel(s, cs, nv)}</div>
        </div>

        <aside class="panel rail" aria-label="Facts">
          <dl>
            <div class="f"><dt>Status</dt><dd><span class="st ${st.key}">${ic(st.icon)}${st.label}</span></dd></div>
            <div class="f"><dt>Used by</dt><dd>${plural(cs.filter((c) => c.state === "on").length, "agent")} <span style="color:var(--muted);font-weight:500">of ${cs.length}</span></dd></div>
            <div class="f"><dt>Size</dt><dd>${sizeWord(s.tokens)} · about ${words(s.tokens)} words
              <span class="bar" role="img" aria-label="Uses ${pct}% of a 200,000-token reading space"><span class="bar-fill" style="width:${Math.max(pct * 10, 2)}%"></span></span>
              <span style="display:block;font-size:12.5px;color:var(--muted);margin-top:4px;font-weight:500">${pct}% of Claude Code's ${term("space", "reading space")}</span></dd></div>
            <div class="f"><dt>Category</dt><dd>${esc(s.category)}</dd></div>
            <div class="f"><dt>Last changed</dt><dd>${esc(s.updated)}</dd></div>
            <div class="f"><dt>Files</dt><dd><details><summary>Show folder locations</summary>${cs.map((c) => `<code>${esc(AG[c.agent].path)}/${esc(s.name)}</code>`).join("")}</details></dd></div>
          </dl>
        </aside>
      </div>
    </div>`;
  }

  function problemBanner(s, st) {
    if (st.key === "bad") return `<div class="banner bad">${ic("bad")}<div><div class="banner-t">One copy can't be read</div><p>${esc(s.problem)}</p></div>
      <div class="banner-acts"><button class="btn btn-primary btn-sm" type="button" data-act="repair">${esc(s.fix)}</button></div></div>`;
    if (st.key === "warn") {
      const nv = newest(s);
      const older = s.copies.filter((c) => c.v < nv && c.state !== "broken").map((c) => AG[c.agent].name);
      return `<div class="banner warn">${ic("warn")}<div><div class="banner-t">The copies don't match</div>
        <p>${esc(join(older))} ${older.length === 1 ? "has" : "have"} an older version. Compare them to see what's different.</p></div>
        <div class="banner-acts"><button class="btn btn-primary btn-sm" type="button" data-tab="compare">Compare copies</button></div></div>`;
    }
    if (st.key === "off") return `<div class="banner off">${ic("off")}<div><div class="banner-t">Turned off</div><p>No agent uses this skill right now. It's kept here so you can turn it back on.</p></div>
      <div class="banner-acts"><button class="btn btn-secondary btn-sm" type="button" data-act="all-on">Turn on everywhere</button></div></div>`;
    return "";
  }

  function tabPanel(s, cs, nv) {
    if (S.tab === "read") {
      const from = S.readFrom && cs.find((c) => c.agent === S.readFrom) ? S.readFrom : (cs.find((c) => c.v === nv) || cs[0]).agent;
      const c = cs.find((x) => x.agent === from);
      const text = bodyFor(s, c.v);
      return `<div class="panel">
        <div class="doc-bar"><label class="sel-wrap">Showing the copy in<select class="sel" id="read-from">${cs.map((x) => `<option value="${x.agent}" ${x.agent === from ? "selected" : ""}>${esc(AG[x.agent].name)}</option>`).join("")}</select></label>
          <label class="switch"><input type="checkbox" id="src-toggle" ${S.source ? "checked" : ""}><span class="tr"></span>Show file text</label></div>
        ${c.state === "broken" ? `<div class="empty"><span class="ic">${ic("bad")}</span><h2>This copy can't be shown</h2><p>${esc(s.problem)}</p></div>`
          : S.source ? `<pre class="src">${esc(`---\nname: ${s.name}\ndescription: ${s.description}\n---\n\n`)}${esc(text)}</pre>` : `<div class="doc">${md(text)}</div>`}
      </div>`;
    }
    if (S.tab === "history") {
      const own = S.activity.filter((a) => a.text.startsWith(s.name + " "));
      return `<ul class="panel hist">${own.map((a) => `<li><time>${esc(a.when)}</time><span>${esc(a.text)}</span></li>`).join("")}
        <li><time>${esc(s.updated)}</time><span>Last edited</span></li><li><time>Earlier</time><span>Added to Skills Manager</span></li></ul>`;
    }
    if (S.tab === "compare") return comparePanel(s, cs, nv);
    // copies
    return `<div class="panel copies">
      ${cs.map((c, i) => {
        const a = AG[c.agent];
        const t = c.state === "broken" ? tag(STATUS.bad) : c.v < nv ? `<span class="tag warn">${ic("old")}Older version</span>` : `<span class="tag ok">${ic("check")}Up to date</span>`;
        return `<div class="crow">${chip(c.agent)}
          <div style="min-width:0"><div class="crow-n">${esc(a.name)}</div><div class="crow-p" title="${esc(a.path)}/${esc(s.name)}"><bdi>${esc(a.path)}/${esc(s.name)}</bdi></div></div>
          ${t}
          <label class="switch"><input type="checkbox" data-toggle="${s.copies.indexOf(c)}" ${c.state === "on" ? "checked" : ""} ${c.state === "broken" ? "disabled" : ""}><span class="tr"></span>${c.state === "on" ? "On" : c.state === "broken" ? "Skipped" : "Off"}<span class="sr-only"> in ${esc(a.name)}</span></label>
        </div>`;
      }).join("")}
      <div class="add-row"><button class="btn btn-text btn-sm" type="button" data-act="share">${ic("plus", "i-s")}Add to another agent</button></div>
    </div>`;
  }

  function comparePanel(s, cs, nv) {
    const usable = cs.filter((c) => c.state !== "broken");
    const A = usable.find((c) => c.agent === S.cmpA) || usable.find((c) => c.v === nv) || usable[0];
    const B = usable.find((c) => c.agent === S.cmpB && c.agent !== A.agent) || usable.find((c) => c.v !== A.v) || usable.find((c) => c.agent !== A.agent);
    if (!B) return `<div class="panel empty"><span class="ic">${ic("info")}</span><h2>Only one readable copy</h2><p>There's nothing to compare it with.</p></div>`;
    const lines = diff(bodyFor(s, B.v).split("\n"), bodyFor(s, A.v).split("\n")).filter((l) => l.x.trim());
    const adds = lines.filter((l) => l.t === "add").length, dels = lines.filter((l) => l.t === "del").length;
    const opt = (sel, other) => usable.map((c) => `<option value="${c.agent}" ${c.agent === sel.agent ? "selected" : ""} ${c.agent === other.agent ? "disabled" : ""}>${esc(AG[c.agent].name)}${c.v === nv ? " (newest)" : ""}</option>`).join("");
    const same = A.v === B.v;
    return `<div class="panel">
      <div class="cmp-pick">
        <label class="sel-wrap">Compare<select class="sel" id="cmp-b">${opt(B, A)}</select></label>
        <label class="sel-wrap">with<select class="sel" id="cmp-a">${opt(A, B)}</select></label>
      </div>
      ${same ? `<div class="empty"><span class="ic">${ic("ok")}</span><h2>These two copies are the same</h2><p>Pick another pair to compare.</p></div>` : `
      <div class="cmp-sum" role="status"><span class="a"><b>+${adds}</b> ${adds === 1 ? "line" : "lines"} only in ${esc(AG[A.agent].name)}</span><span class="d"><b>−${dels}</b> ${dels === 1 ? "line" : "lines"} only in ${esc(AG[B.agent].name)}</span></div>
      <ol class="diff" aria-label="Differences">
        ${lines.map((l) => {
          const h = /^#{1,3}\s/.test(l.x);
          const text = l.x.replace(/^#{1,3}\s+/, "").replace(/^[-*]\s+/, "• ").replace(/^>\s?/, "“").replace(/\*\*(.+?)\*\*/g, "$1") + (/^>/.test(l.x) ? "”" : "");
          return `<li class="${l.t}${h ? " h" : ""}"><span class="m" aria-hidden="true">${l.t === "add" ? "+" : l.t === "del" ? "−" : ""}</span><span>${l.t === "add" ? '<span class="sr-only">Only in ' + esc(AG[A.agent].name) + ": </span>" : l.t === "del" ? '<span class="sr-only">Only in ' + esc(AG[B.agent].name) + ": </span>" : ""}${esc(text)}</span></li>`;
        }).join("")}
      </ol>
      <div class="cmp-foot"><span>${A.v > B.v ? `${esc(AG[A.agent].name)}'s copy is newer.` : `${esc(AG[B.agent].name)}'s copy is newer.`} A backup is saved before anything changes.</span>
        <button class="btn btn-primary btn-sm" type="button" data-act="use-version" data-from="${A.v >= B.v ? A.agent : B.agent}">${ic("sync", "i-s")}Use ${esc(AG[A.v >= B.v ? A.agent : B.agent].name)}'s version everywhere</button></div>`}
    </div>`;
  }

  /* Line diff (LCS) */
  function diff(a, b) {
    const n = a.length, m = b.length, dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const out = []; let i = 0, j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { out.push({ t: "same", x: a[i] }); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ t: "del", x: a[i++] });
      else out.push({ t: "add", x: b[j++] });
    }
    while (i < n) out.push({ t: "del", x: a[i++] });
    while (j < m) out.push({ t: "add", x: b[j++] });
    return out;
  }

  /* Escaped Markdown (headings, lists, quotes, bold, code). */
  function md(src) {
    const inl = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
    const out = []; let list = null;
    const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
    src.split("\n").forEach((line) => {
      let m;
      if ((m = line.match(/^(#{1,3})\s+(.*)/))) { close(); const l = Math.min(m[1].length, 2); out.push(`<h${l}>${inl(m[2])}</h${l}>`); }
      else if ((m = line.match(/^\d+\.\s+(.*)/))) { if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; } out.push(`<li>${inl(m[1])}</li>`); }
      else if ((m = line.match(/^[-*]\s+(.*)/))) { if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inl(m[1])}</li>`); }
      else if ((m = line.match(/^>\s?(.*)/))) { close(); out.push(`<blockquote><p>${inl(m[1])}</p></blockquote>`); }
      else if (line.trim()) { close(); out.push(`<p>${inl(line)}</p>`); }
      else close();
    });
    close();
    return out.join("");
  }

  /* ---------- Dialogs ---------- */
  function dialog({ title, body, cancel, confirm, onConfirm, danger }) {
    const opener = document.activeElement;
    const el = document.createElement("div");
    el.className = "scrim";
    el.innerHTML = `<div class="dlg" role="dialog" aria-modal="true" aria-labelledby="dlg-t" aria-describedby="dlg-b">
      <div class="dlg-h"><h2 id="dlg-t">${title}</h2></div><div class="dlg-b" id="dlg-b">${body}</div>
      <div class="dlg-f"><button class="btn btn-secondary" type="button" data-x>${cancel}</button><button class="btn ${danger ? "btn-danger" : "btn-primary"}" type="button" data-ok>${confirm}</button></div></div>`;
    document.body.appendChild(el);
    $(".app").inert = true;
    const close = () => { el.remove(); $(".app").inert = false; opener && opener.isConnected && opener.focus(); };
    el.addEventListener("click", (e) => {
      if (e.target === el || e.target.closest("[data-x]")) close();
      else if (e.target.closest("[data-ok]")) { const ok = onConfirm(el); close(); if (ok && ok.focus) setTimeout(() => { const f = $(ok.focus); f && f.focus(); }, 0); }
    });
    el.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.stopPropagation(); close(); }
      if (e.key === "Tab") {
        const f = $$("button, input, select", el).filter((x) => !x.disabled);
        if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    });
    $("[data-x]", el).focus(); // the safe choice gets focus first
  }

  function confirmUseVersion(s, fromAgent) {
    const src = s.copies.find((c) => c.agent === fromAgent);
    const targets = s.copies.filter((c) => c.agent !== fromAgent && c.state !== "broken" && c.v !== src.v);
    if (!targets.length) return toast("Every copy already matches");
    const names = targets.map((c) => AG[c.agent].name);
    dialog({
      title: `Update ${plural(targets.length, "copy", "copies")} of “${esc(s.name)}”?`,
      body: `<p>The copy in ${esc(join(names))} will be replaced with the version from <b>${esc(AG[fromAgent].name)}</b>.</p>
        <div class="dlg-note">${ic("archive")}<span>A backup is saved first. You can undo this from the message that appears, or later from Recent changes.</span></div>`,
      cancel: "Keep as is", confirm: `Update ${plural(targets.length, "copy", "copies")}`,
      onConfirm: () => {
        const before = clone(s.copies);
        targets.forEach((c) => (c.v = src.v));
        log(`${s.name} copies were updated to match ${AG[fromAgent].name}`, "sync");
        markFixed(s.name, `“${s.name}” now matches in every agent`, () => { s.copies = before; unfix(s.name); });
        render();
        toast(`Updated ${join(names)}`, () => { s.copies = before; unfix(s.name); render(); });
        return { focus: "#h1" };
      },
    });
  }

  function shareDialog(s) {
    const have = new Set(s.copies.map((c) => c.agent));
    const opts = D.agents.filter((a) => !have.has(a.id));
    if (!opts.length) return toast(`“${s.name}” is already in every agent`);
    dialog({
      title: `Add “${esc(s.name)}” to another agent`,
      body: `<p>We'll copy the newest version. Agents that already have it won't change.</p>
        ${opts.map((a) => `<label class="pick"><input type="checkbox" value="${a.id}">${chip(a.id)}<span>${esc(a.name)}<small>${esc(a.path)}</small></span></label>`).join("")}`,
      cancel: "Cancel", confirm: "Add copies",
      onConfirm: (el) => {
        const picked = $$("input:checked", el).map((i) => i.value);
        if (!picked.length) return;
        const v = newest(s);
        const before = clone(s.copies);
        picked.forEach((id) => s.copies.push({ agent: id, state: "on", v }));
        const names = picked.map((id) => AG[id].name);
        log(`${s.name} was added to ${join(names)}`, "add");
        render();
        toast(`Added to ${join(names)}`, () => { s.copies = before; render(); });
      },
    });
  }

  /* ---------- Toasts, log, live ---------- */
  function toast(text, undo) {
    const t = document.createElement("div");
    t.className = "toast";
    t.innerHTML = `${ic("ok")}<span>${esc(text)}</span>${undo ? '<button type="button">Undo</button>' : ""}`;
    $("#toasts").appendChild(t);
    const kill = () => t.remove();
    if (undo) t.querySelector("button").addEventListener("click", () => { undo(); kill(); toast("Undone"); });
    setTimeout(kill, undo ? 9000 : 4000);
  }
  const announce = (msg) => { const l = $("#live"); l.textContent = ""; setTimeout(() => (l.textContent = msg), 30); };
  const log = (text, kind) => S.activity.unshift({ when: "Just now", text, kind });
  function markFixed(name, label, undo) { S.fixed.unshift({ name, label, undo }); }
  function unfix(name) { S.fixed = S.fixed.filter((f) => f.name !== name); }

  // Repairs a skill in place and returns a function that undoes the repair.
  function repair(s) {
    const before = clone(s.copies), beforeName = s.name;
    const broken = s.copies.find((c) => c.state === "broken");
    const good = s.copies.find((c) => c.state !== "broken");
    if (good) { broken.state = "on"; broken.v = good.v; }
    else { s.name = s.name.toLowerCase().replace(/\s+/g, "-"); broken.state = "on"; }
    log(`${s.name} was repaired in ${AG[broken.agent].name}`, "fix");
    const undo = () => { s.copies = before; s.name = beforeName; unfix(s.name); unfix(beforeName.toLowerCase().replace(/\s+/g, "-")); };
    markFixed(s.name, `“${s.name}” can be read by ${AG[broken.agent].name} again`, undo);
    return undo;
  }

  /* ---------- Glossary popover ---------- */
  let pop = null;
  function closePop(focusBack) {
    if (!pop) return;
    const btn = pop.btn; pop.el.remove(); btn.setAttribute("aria-expanded", "false"); pop = null;
    if (focusBack) btn.focus();
  }
  function openPop(btn) {
    closePop();
    const g = D.glossary[btn.dataset.term];
    const el = document.createElement("div");
    el.className = "pop"; el.id = "pop"; el.setAttribute("role", "dialog"); el.setAttribute("aria-label", g.title);
    el.innerHTML = `<b>${esc(g.title)}</b>${esc(g.text)}`;
    document.body.appendChild(el);
    const r = btn.getBoundingClientRect();
    el.style.left = Math.max(16, Math.min(r.left + window.scrollX, window.scrollX + innerWidth - el.offsetWidth - 16)) + "px";
    el.style.top = r.bottom + window.scrollY + 8 + "px";
    btn.setAttribute("aria-expanded", "true"); btn.setAttribute("aria-controls", "pop");
    pop = { el, btn };
  }

  /* ---------- Router ---------- */
  function route() {
    const h = location.hash.replace(/^#\/?/, "");
    const [p, ...rest] = h.split("/");
    if (p === "skills") return rest.length ? { page: "skill", name: decodeURIComponent(rest.join("/")) } : { page: "skills" };
    return { page: "overview" };
  }
  let last = "";
  function render(opt = {}) {
    closePop();
    const r = route();
    const key = r.page + ":" + (r.name || "");
    const main = $("#main");
    const y = scrollY;
    main.innerHTML = r.page === "skills" ? skillsPage() : r.page === "skill" ? skillPage(r.name) : overview();
    $$("[data-nav]").forEach((a) => (a.dataset.nav === (r.page === "skill" ? "skills" : r.page) ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
    $("#nav-n").textContent = S.demo === "first-run" ? "0" : S.skills.length;
    $$("[data-indeterminate='true']").forEach((cb) => (cb.indeterminate = true));
    document.title = `${r.page === "skill" ? r.name : r.page === "skills" ? "Skills" : "Overview"} · Skills Manager`;
    if (key !== last) { scrollTo(0, 0); const h = $("#h1"); h && h.focus({ preventScroll: true }); }
    else { scrollTo(0, y); if (opt.focus) { const f = $(opt.focus); f && f.focus({ preventScroll: true }); } }
    last = key;
  }
  const go = (h) => (location.hash === h ? render() : (location.hash = h));

  /* ---------- Events ---------- */
  document.addEventListener("click", (e) => {
    const termBtn = e.target.closest("[data-term]");
    if (termBtn) { pop && pop.btn === termBtn ? closePop() : openPop(termBtn); return; }
    if (pop && !e.target.closest(".pop")) closePop();

    const t = e.target.closest("button, a"); if (!t) return;
    const r = route();
    const s = r.page === "skill" ? find(r.name) : null;

    if (t.dataset.gotoFilter) { S.filter = t.dataset.gotoFilter; S.query = ""; S.selected.clear(); return go("#/skills"); }
    if (t.dataset.filter) { S.filter = t.dataset.filter; S.selected.clear(); render({ focus: `[data-filter="${S.filter}"]` }); return announce($(".count") ? $(".count").textContent : "No skills"); }
    if (t.dataset.view) { S.view = t.dataset.view; return render({ focus: `[data-view="${S.view}"]` }); }
    if (t.dataset.soon) return toast(`“${t.dataset.soon}” comes in the next prototype`);
    if (t.dataset.tab) { S.tab = t.dataset.tab; return render({ focus: `[data-tab="${S.tab}"][role="tab"]` }); }

    if (t.dataset.task !== undefined) {
      const task = tasks()[+t.dataset.task];
      const sk = find(task.name);
      if (task.kind === "match") { S.tab = "compare"; S.cmpA = null; S.cmpB = null; return go("#/skills/" + encodeURIComponent(sk.name)); }
      const undo = repair(sk);
      render({ focus: "#fix-h" });
      return toast(`Repaired “${sk.name}”`, () => { undo(); render(); });
    }
    if (t.dataset.undoFix !== undefined) {
      const f = S.fixed[+t.dataset.undoFix];
      if (f.undo) f.undo();
      unfix(f.name);
      render({ focus: "#fix-h" });
      return toast("Undone");
    }

    if (t.dataset.batch) {
      const b = t.dataset.batch;
      if (b === "cancel") { S.selected.clear(); return render({ focus: "#sel-all" }); }
      const names = [...S.selected];
      const before = clone(S.skills);
      if (b === "trash") {
        S.skills = S.skills.filter((x) => !S.selected.has(x.name));
        log(`${plural(names.length, "skill")} moved to the trash`, "trash");
      } else {
        S.skills.forEach((x) => { if (S.selected.has(x.name)) x.copies.forEach((c) => { if (c.state !== "broken") c.state = b; }); });
        log(`${plural(names.length, "skill")} turned ${b}`, b);
      }
      S.selected.clear();
      render({ focus: "#q" });
      return toast(b === "trash" ? `Moved ${plural(names.length, "skill")} to the trash` : `Turned ${b} ${plural(names.length, "skill")}`, () => { S.skills = before; render(); });
    }

    const a = t.dataset.act;
    if (a === "clear") { S.query = ""; S.filter = "all"; return render({ focus: "#q" }); }
    if (a === "retry") { S.scanError = false; $("#demo-state").value = "normal"; S.demo = "normal"; render({ focus: "#h1" }); return toast("Cursor's folder was read. Everything is shown."); }
    if (!s) return;
    if (a === "share") return shareDialog(s);
    if (a === "use-version") return confirmUseVersion(s, t.dataset.from);
    if (a === "repair") {
      const beforeName = s.name;
      const undo = repair(s);
      if (s.name !== beforeName) { history.replaceState(null, "", "#/skills/" + encodeURIComponent(s.name)); last = "skill:" + s.name; }
      render({ focus: "#h1" });
      return toast(`Repaired “${s.name}”`, () => { undo(); go("#/skills/" + encodeURIComponent(beforeName)); });
    }
    if (a === "all-on" || a === "all-off") {
      const before = clone(s.copies);
      const st = a === "all-on" ? "on" : "off";
      s.copies.forEach((c) => { if (c.state !== "broken") c.state = st; });
      log(`${s.name} was turned ${st} everywhere`, st);
      render({ focus: `[data-act="${a === "all-on" ? "all-off" : "all-on"}"]` });
      return toast(`Turned ${st} in every agent`, () => { s.copies = before; render(); });
    }
    if (a === "trash") {
      const i = S.skills.indexOf(s);
      S.skills.splice(i, 1);
      log(`${s.name} was moved to the trash`, "trash");
      go("#/skills");
      return toast(`Moved “${s.name}” to the trash`, () => { S.skills.splice(i, 0, s); go("#/skills/" + encodeURIComponent(s.name)); });
    }
  });

  document.addEventListener("change", (e) => {
    const t = e.target;
    if (t.id === "demo-state") return setDemo(t.value);
    if (t.id === "sort") { S.sort = t.value; return render({ focus: "#sort" }); }
    if (t.id === "read-from") { S.readFrom = t.value; return render({ focus: "#read-from" }); }
    if (t.id === "src-toggle") { S.source = t.checked; return render({ focus: "#src-toggle" }); }
    if (t.id === "cmp-a") { S.cmpA = t.value; S.cmpB = $("#cmp-b").value; return render({ focus: "#cmp-a" }); }
    if (t.id === "cmp-b") { S.cmpB = t.value; S.cmpA = $("#cmp-a").value; return render({ focus: "#cmp-b" }); }
    if (t.id === "sel-all") { visible().forEach((s) => (t.checked ? S.selected.add(s.name) : S.selected.delete(s.name))); render({ focus: S.selected.size ? '[data-batch="on"]' : "#sel-all" }); return announce(`${S.selected.size} selected`); }
    if (t.dataset.sel) { t.checked ? S.selected.add(t.dataset.sel) : S.selected.delete(t.dataset.sel); render({ focus: `[data-sel="${CSS.escape(t.dataset.sel)}"]` }); return announce(`${S.selected.size} selected`); }
    if (t.dataset.toggle !== undefined) {
      const s = find(route().name), c = s.copies[+t.dataset.toggle];
      const prev = c.state;
      c.state = t.checked ? "on" : "off";
      log(`${s.name} was turned ${c.state} in ${AG[c.agent].name}`, c.state);
      render({ focus: `[data-toggle="${t.dataset.toggle}"]` });
      toast(`${t.checked ? "Turned on" : "Turned off"} in ${AG[c.agent].name}`, () => { c.state = prev; render(); });
    }
  });

  let timer;
  document.addEventListener("input", (e) => {
    if (e.target.id !== "q") return;
    clearTimeout(timer);
    const v = e.target.value;
    timer = setTimeout(() => {
      S.query = v; S.selected.clear();
      const pos = e.target.selectionStart;
      render({ focus: "#q" });
      const q = $("#q"); q && q.setSelectionRange(pos, pos);
      announce($(".count") ? $(".count").textContent : `No skills match ${v}`);
    }, 140);
  });

  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName) && document.activeElement.type !== "checkbox";
    if (e.key === "Escape" && pop) { closePop(true); return; }
    if (e.key === "/" && !typing && !$(".scrim")) { const q = $("#q"); if (q) { e.preventDefault(); q.focus(); } }
    if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && document.activeElement.getAttribute("role") === "tab") {
      const tabs = $$('[role="tab"]');
      const i = (tabs.indexOf(document.activeElement) + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
      S.tab = tabs[i].dataset.tab; render({ focus: `[data-tab="${S.tab}"][role="tab"]` });
    }
  });

  /* ---------- Demo states ---------- */
  let scanTimer;
  function setDemo(v) {
    clearInterval(scanTimer);
    S.demo = v; S.scanError = v === "scan-error"; S.selected.clear();
    if (v === "all-good") {
      S.skills.forEach((s) => { const nv = newest(s) || 1; s.copies.forEach((c) => { if (c.state === "broken") c.state = "on"; c.v = nv; }); s.name = s.name.toLowerCase().replace(/\s+/g, "-"); });
    }
    if (v === "normal") { S.skills = clone(D.skills); S.fixed = []; }
    if (v === "loading") {
      S.skills = clone(D.skills); S.fixed = []; S.scan = 0;
      scanTimer = setInterval(() => {
        S.scan++;
        if (S.scan > D.agents.length) { $("#demo-state").value = "normal"; setDemo("normal"); announce("Scan finished"); return; }
        render();
      }, 550);
    }
    last = ""; render();
    announce({ normal: "Showing demo data", loading: "Scanning folders", "first-run": "Showing first run", "scan-error": "Showing a scan error", "all-good": "Showing everything fixed" }[v]);
  }

  /* ---------- Theme ---------- */
  const themeNow = () => document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  function paintTheme() {
    const dark = themeNow() === "dark";
    $$("#theme [data-i], #theme-m [data-i]").forEach((el) => (el.innerHTML = ic(dark ? "sun" : "moon")));
    $("#theme-m").setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    $("#theme .theme-t").textContent = dark ? "Light theme" : "Dark theme";
  }
  $$("#theme, #theme-m").forEach((b) => b.addEventListener("click", () => {
    const n = themeNow() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = n;
    try { localStorage.setItem("compass-theme", n); } catch (e) {}
    paintTheme();
  }));

  $$("[data-i]").forEach((el) => (el.innerHTML = ic(el.dataset.i)));
  paintTheme();
  addEventListener("hashchange", () => render());
  if (!location.hash) history.replaceState(null, "", "#/overview");
  render();
})();
