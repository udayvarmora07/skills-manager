/* Skills Manager — final prototype. Vanilla JS, no build, no network.
   All state lives in memory; nothing is read from or written to disk. */
(function () {
  "use strict";
  const D = window.SM_DATA;
  const AG = Object.fromEntries([D.library, ...D.agents].map((a) => [a.id, a]));
  const CAT = Object.fromEntries(D.categories.map((c) => [c.id, c]));
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (n) => n.toLocaleString("en-US");
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + "s"}`;
  const join = (a) => (a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]);
  const clone = (x) => JSON.parse(JSON.stringify(x));
  const enc = encodeURIComponent;

  /* ---------- Icons ---------- */
  const P = {
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    ok: '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 3 3 5-6"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    warn: '<path d="M12 3.5 2.8 19.5h18.4L12 3.5Z"/><path d="M12 10v4M12 17v.01"/>',
    bad: '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/>',
    off: '<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.01"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    left: '<path d="m15 6-6 6 6 6"/>',
    undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    trash: '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/>',
    share: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    pencil: '<path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    lens: '<circle cx="11" cy="11" r="6"/><path d="m20 20-4.5-4.5M8.5 11h5M11 8.5v5"/>',
    flask: '<path d="M9 3h6M10 3v6L5 19a1.5 1.5 0 0 0 1.3 2h11.4a1.5 1.5 0 0 0 1.3-2L14 9V3"/><path d="M7 15h10"/>',
    bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3Z"/>',
    steps: '<path d="M4 7h10M4 12h16M4 17h7"/><path d="m16 15 3 3-3 3"/>',
    gauge: '<path d="M4 18a9 9 0 1 1 16 0"/><path d="m12 13 4-4"/>',
    plug: '<path d="M9 2v5M15 2v5M6 7h12v4a6 6 0 0 1-12 0Z"/><path d="M12 17v5"/>',
    brackets: '<path d="M8 4H5v16h3M16 4h3v16h-3"/><path d="M10 12h4"/>',
    eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    pen: '<path d="M12 19l7-7 3 3-7 7-3-3Z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18Z"/>',
    db: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
    cube: '<path d="M12 2 3 7v10l9 5 9-5V7Z"/><path d="m3 7 9 5 9-5M12 12v10"/>',
    list: '<path d="M4 7h16M4 12h16M4 17h10"/><path d="m17 15 2 2 3-3"/>',
    box: '<rect x="3" y="9" width="18" height="10" rx="2"/><path d="M7 9V5h4v4M13 9V6h4v3"/>',
    doc: '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5Z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    quote: '<path d="M7 7h4v6a4 4 0 0 1-4 4M13 7h4v6a4 4 0 0 1-4 4"/>',
    map: '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Z"/><path d="M9 3v15M15 6v15"/>',
    commit: '<circle cx="12" cy="12" r="3.5"/><path d="M3 12h5.5M15.5 12H21"/>',
    merge: '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="15" r="2"/><path d="M6 7v10M6 9a6 6 0 0 0 6 6h4"/>',
    shield: '<path d="M12 3 4.5 6v5.5c0 4.5 3.2 8.2 7.5 9.5 4.3-1.3 7.5-5 7.5-9.5V6L12 3Z"/><path d="m9 12 2 2 4-4"/>',
  };
  const ic = (n, c = "") => `<svg class="i ${c}" viewBox="0 0 24 24" aria-hidden="true">${P[n] || P.doc}</svg>`;

  /* ---------- State ---------- */
  const S = {
    skills: clone(D.skills),
    texts: clone(D.texts),
    activity: clone(D.activity),
    // shelf
    filter: "all", agent: "all", query: "",
    // map
    mapAgent: null, mapPicked: null, peek: null,
    // inbox
    skipped: [], dismissed: new Set(), done: 0, front: null,
    // notebook
    highlight: true, compareWith: null, edit: null,
  };

  /* ---------- Model ---------- */
  const find = (n) => S.skills.find((s) => s.name === n);
  const newest = (s) => Math.max(0, ...s.copies.filter((c) => c.state !== "broken").map((c) => c.v));
  const STATUS = {
    bad: { key: "bad", label: "Can't be read", icon: "bad", rank: 0 },
    warn: { key: "warn", label: "Copies differ", icon: "warn", rank: 1 },
    ok: { key: "ok", label: "Working", icon: "ok", rank: 2 },
    off: { key: "off", label: "Turned off", icon: "off", rank: 3 },
  };
  function status(s) {
    if (s.copies.some((c) => c.state === "broken")) return STATUS.bad;
    if (!s.copies.some((c) => c.state === "on")) return STATUS.off;
    return new Set(s.copies.filter((c) => c.state !== "broken").map((c) => c.v)).size > 1 ? STATUS.warn : STATUS.ok;
  }
  const older = (s) => { const nv = newest(s); return s.copies.filter((c) => c.state !== "broken" && c.v < nv); };
  function textOf(s, v) {
    const t = S.texts[s.name];
    return (t && (t[v] || t[newest(s)])) || D.genericText(s);
  }
  function agentInfo(id) {
    const mine = S.skills.filter((s) => s.copies.some((c) => c.agent === id));
    const on = mine.filter((s) => s.copies.some((c) => c.agent === id && c.state === "on"));
    const tokens = on.reduce((n, s) => n + s.tokens, 0);
    const old = mine.filter((s) => { const c = s.copies.find((x) => x.agent === id); return c.state !== "broken" && c.v < newest(s); });
    const broken = mine.filter((s) => s.copies.some((c) => c.agent === id && c.state === "broken"));
    const pct = AG[id].limit ? Math.round((tokens / AG[id].limit) * 1000) / 10 : 0;
    const key = broken.length ? "bad" : old.length ? "warn" : "ok";
    return { id, mine, on, tokens, old, broken, pct, key };
  }
  const ACRONYMS = { sql: "SQL", api: "API", pr: "PR", k8s: "K8s", a11y: "Accessibility" };
  const titleCase = (n) => n.split("-").map((w, i) => ACRONYMS[w.toLowerCase()] || (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w)).join(" ");
  const words = (t) => fmt(Math.round((t * 0.75) / 10) * 10);

  /* Everything that needs the user's attention, most serious first. */
  function problems() {
    const out = [];
    S.skills.forEach((s) => {
      const st = status(s);
      if (st.key === "bad") {
        const b = s.copies.find((c) => c.state === "broken");
        const sole = !s.copies.some((c) => c.state !== "broken");
        out.push({ id: "bad:" + s.name, key: "bad", skill: s.name, agents: [b.agent],
          title: sole ? `No agent can find “${s.name}”` : `${AG[b.agent].name} can't read “${s.name}”`,
          short: sole ? "Unusual folder name" : "Damaged file", text: s.problem, action: s.fix });
      } else if (st.key === "warn") {
        const ol = older(s);
        const names = ol.map((c) => AG[c.agent].name);
        out.push({ id: "warn:" + s.name, key: "warn", skill: s.name, agents: ol.map((c) => c.agent),
          title: `${join(names)} ${ol.length === 1 ? "has" : "have"} an older copy of “${s.name}”`, short: "Out of date",
          text: `Your other agents use a newer version, so ${ol.length === 1 ? "it" : "they"} may behave differently until updated.`,
          action: `Update ${names.length === 1 ? names[0] + "'s copy" : names.length + " copies"}` });
      }
    });
    D.agents.forEach((a) => {
      const inf = agentInfo(a.id);
      if (inf.pct > D.suggestedSpace) out.push({ id: "space:" + a.id, key: "info", agent: a.id,
        title: `${a.name}'s skills use ${inf.pct}% of its reading space`, short: "Suggestion",
        text: `That leaves less room for your code and conversation. Turning off skills you rarely use in ${a.name} frees up space.`, action: "Done" });
    });
    const rank = { bad: 0, warn: 1, info: 2 };
    return out.filter((p) => !S.dismissed.has(p.id)).sort((a, b) => rank[a.key] - rank[b.key]);
  }

  /* ---------- Shared fragments ---------- */
  const logo = (id, cls = "") => `<span class="logo ${cls}" style="background:${AG[id].color}" aria-hidden="true">${AG[id].initials}</span>`;
  const pill = (st) => `<span class="pill ${st.key}">${ic(st.icon)}${st.label}</span>`;
  const dot = (k) => ({ bad: ic("bad"), warn: ic("warn"), info: ic("info") }[k]);

  /* ========== HOME (Agent rooms) ========== */
  function home() {
    const probs = problems();
    const agents = D.agents.map((a) => agentInfo(a.id));
    const shared = [...S.skills].sort((a, b) => b.copies.length - a.copies.length).slice(0, 3);
    const healthLabel = (inf) => inf.broken.length ? `${ic("bad")}${plural(inf.broken.length, "skill")} can't be read`
      : inf.old.length ? `${ic("warn")}${plural(inf.old.length, "skill is", "skills are")} out of date`
      : `${ic("ok")}All ${plural(inf.mine.length, "skill")} working`;
    return `<div class="page">
      <h1 class="h1" id="h1" tabindex="-1">Your agents</h1>
      <p class="lede">Each AI tool on this computer and the skills it knows. ${probs.length ? `<b>${plural(probs.length, "thing needs", "things need")} a look.</b>` : "<b>Everything is working.</b>"}</p>
      <div class="home">
        <section aria-label="Agents" class="rooms">
          ${agents.map((inf) => {
            const a = AG[inf.id];
            const names = inf.mine.map((s) => s.name);
            return `<a class="card room" href="#/skills" data-agent-link="${a.id}" aria-label="${esc(a.name)}: ${plural(inf.mine.length, "skill")}, open its skills">
              <div class="room-h">${logo(a.id)}<div style="min-width:0"><div class="room-n">${esc(a.name)}</div><div class="room-p">${esc(a.path)}</div></div></div>
              <span class="pill ${inf.key}">${healthLabel(inf)}</span>
              <div class="chips">${names.slice(0, 4).map((n) => `<span>${esc(n)}</span>`).join("")}${names.length > 4 ? `<span class="more">+${names.length - 4} more</span>` : ""}</div>
              <div class="meter"><div class="ml"><span>Reading space used</span><b class="num">${inf.pct}%</b></div>
                <div class="track" role="img" aria-label="${inf.pct}% used, suggested limit ${D.suggestedSpace}%"><i class="${inf.pct > D.suggestedSpace ? "warn" : ""}" style="width:${Math.max(inf.pct * 2.5, 1.5)}%"></i><span class="lim" style="left:${D.suggestedSpace * 2.5}%"></span></div></div>
            </a>`;
          }).join("")}
          <button type="button" class="card room add" data-soon="Connecting another agent"><div><div class="plus">${ic("plus")}</div><b>Connect another agent</b>Point us at its skills folder</div></button>
        </section>
        <aside class="side">
          <div class="card">
            <h2>Needs a look</h2><p class="sub">${probs.length ? `${plural(probs.length, "thing")}, most important first` : "Nothing right now"}</p>
            ${probs.length ? probs.slice(0, 3).map((p, i) => `<div class="look"><span class="look-ic ${p.key} ${p.key}">${dot(p.key)}</span>
              <div><b>${esc(p.title)}</b><p>${esc(p.text)}</p><a class="btn btn-sm ${i === 0 ? "btn-ink" : "btn-soft"}" href="#/inbox" data-inbox-to="${p.id}">${p.key === "info" ? "Review" : "Fix it"}</a></div></div>`).join("")
              : `<div class="look"><span class="look-ic" style="background:var(--ok-bg);color:var(--ok)">${ic("check")}</span><div><b>All clear</b><p>Every skill can be read and every copy matches.</p></div></div>`}
            ${probs.length > 3 ? `<a class="see-all" href="#/inbox">Open inbox (${probs.length}) ${ic("arrow", "i-s")}</a>` : ""}
          </div>
          <div class="card">
            <h2>Shared by most agents</h2><p class="sub">Your most-used skills</p>
            ${shared.map((s) => `<a class="shared-row" href="#/skill/${enc(s.name)}"><span>${esc(s.name)}</span><span class="faces">${s.copies.filter((c) => c.agent !== "library").map((c) => logo(c.agent, "xs")).join("")}</span></a>`).join("")}
          </div>
          <div class="card">
            <h2>Recent changes</h2>
            <ul class="hist" style="margin-top:12px">${S.activity.slice(0, 4).map((a) => `<li>${esc(a.text)}<small>${esc(a.when)}</small></li>`).join("")}</ul>
          </div>
        </aside>
      </div>
    </div>`;
  }

  /* ========== SKILLS (Shelf, grouped by category) ========== */
  function visibleSkills() {
    const q = S.query.trim().toLowerCase();
    return S.skills.filter((s) => {
      const k = status(s).key;
      if (S.filter === "care" && k !== "warn" && k !== "bad") return false;
      if (S.filter === "off" && k !== "off") return false;
      if (S.agent !== "all" && !s.copies.some((c) => c.agent === S.agent)) return false;
      if (q && !`${s.name} ${s.description} ${s.category}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }
  function shelf() {
    const list = visibleSkills();
    const care = S.skills.filter((s) => ["warn", "bad"].includes(status(s).key));
    const offN = S.skills.filter((s) => status(s).key === "off").length;
    const fb = (id, label, n) => `<button type="button" data-filter="${id}" aria-pressed="${S.filter === id}">${label}<span class="n num">${n}</span></button>`;
    const groups = D.categories.map((c) => ({ c, items: list.filter((s) => s.category === c.id) })).filter((g) => g.items.length);
    return `<div class="page">
      <div class="shelf-head">
        <div><h1 class="h1" id="h1" tabindex="-1">Your skills, <em>grouped by what they're for.</em></h1>
          <p class="lede">${S.skills.length} skills shared across ${D.agents.length} AI tools. Pick one to read it, change it or share it.</p></div>
        <button type="button" class="btn btn-ink" data-act="new">${ic("plus")}New skill</button>
      </div>
      <div class="tools">
        <div class="searchf">${ic("search")}<label class="sr-only" for="q">Search skills</label><input class="field" id="q" type="search" placeholder="Search by name or what it does" value="${esc(S.query)}" autocomplete="off"></div>
        <div class="seg" role="group" aria-label="Show">${fb("all", "All", S.skills.length)}${fb("care", "Needs care", care.length)}${fb("off", "Turned off", offN)}</div>
        <label class="sr-only" for="agent-f">Agent</label>
        <select class="field" id="agent-f"><option value="all">All agents</option>${D.agents.map((a) => `<option value="${a.id}" ${S.agent === a.id ? "selected" : ""}>Only ${esc(a.name)}</option>`).join("")}</select>
        <span class="count" aria-live="polite">${list.length === S.skills.length ? `${list.length} skills` : `Showing ${list.length} of ${S.skills.length}`}</span>
      </div>
      ${care.length && S.filter !== "care" ? `<div class="ribbon">${ic("warn")}<span><b>${plural(care.length, "skill needs", "skills need")} a little care.</b> Cards with a badge have a problem.</span><a class="btn btn-ink btn-sm" href="#/inbox">Fix them in Inbox</a></div>` : ""}
      ${groups.length ? groups.map(({ c, items }) => `<section class="cat" aria-labelledby="cat-${c.id.replace(/\W/g, "")}">
          <div class="cat-h"><h2 class="h2" id="cat-${c.id.replace(/\W/g, "")}">${esc(c.id)}</h2><span>${plural(items.length, "skill")}</span></div>
          <div class="shelf">${items.map(card).join("")}</div>
        </section>`).join("")
        : `<div class="card empty" style="margin-top:28px"><span class="ic" style="background:var(--sunken);color:var(--ink-2)">${ic("search")}</span>
          <h2>${S.query ? `No skills match “${esc(S.query)}”` : S.filter === "care" ? "Nothing needs care" : "Nothing here"}</h2>
          <p>${S.query ? "Check the spelling, or search for what the skill does, like “tests” or “commit”." : "Every skill in this view is working."}</p>
          <button type="button" class="btn btn-line" data-act="clear">Show all skills</button></div>`}
    </div>`;
  }
  function card(s) {
    const st = status(s);
    const c = CAT[s.category];
    const tools = s.copies.filter((x) => x.agent !== "library");
    return `<a class="card sk ${st.key === "off" ? "faded" : ""}" href="#/skill/${enc(s.name)}" aria-label="${esc(s.name)}. ${st.label}. ${esc(s.description)}">
      <div class="cover" style="background:${c.tint};color:${c.ink}">${ic(s.icon)}${st.key !== "ok" ? `<span class="pill ${st.key}">${ic(st.icon)}${st.label}</span>` : ""}</div>
      <div class="sk-b"><b>${esc(s.name)}</b><p>${esc(s.description)}</p>
        <div class="sk-f"><span class="dots">${tools.map((x) => `<i class="${x.state === "off" ? "is-off" : x.state === "broken" ? "is-bad" : ""}" style="background:${AG[x.agent].color}" title="${esc(AG[x.agent].name)}"></i>`).join("")}</span>
        <small>${st.key === "off" ? "Off everywhere" : plural(tools.length, "tool")}</small></div></div>
    </a>`;
  }

  /* ========== SKILL (Notebook: read & edit) ========== */
  function notebook(name) {
    const s = find(name);
    if (!s) return `<div class="page"><div class="card empty"><span class="ic" style="background:var(--sunken);color:var(--ink-2)">${ic("search")}</span><h2 id="h1" tabindex="-1">This skill isn't here any more</h2><p>It may have been moved to the trash.</p><a class="btn btn-line" href="#/skills">Back to skills</a></div></div>`;
    const editing = S.edit && S.edit.name === s.name;
    const groups = D.categories.map((c) => ({ c, items: S.skills.filter((x) => x.category === c.id) })).filter((g) => g.items.length);
    return `<div class="nb">
      <nav class="tree" aria-label="All skills">
        <div class="tree-find"><label class="sr-only" for="tree-q">Filter skills</label><input id="tree-q" type="search" placeholder="Filter skills" autocomplete="off"></div>
        ${groups.map(({ c, items }) => `<div class="tree-g">${esc(c.id)}</div>${items.map((x) => `<a href="#/skill/${enc(x.name)}" data-tree="${esc(x.name.toLowerCase())}" ${x.name === s.name ? 'aria-current="page"' : ""}>${esc(x.name)}<i class="d ${status(x).key}" aria-label="${status(x).label}"></i></a>`).join("")}`).join("")}
      </nav>
      <div class="nb-main">
        <div class="nb-bar"><a href="#/skills">Skills</a><span aria-hidden="true">/</span><span>${esc(s.category)}</span><span aria-hidden="true">/</span><b>${esc(s.name)}</b>
          <span class="acts">${editing ? "" : `<button type="button" class="btn btn-line btn-sm" data-act="share">${ic("share", "i-s")}Add to agent</button>
          <button type="button" class="btn btn-ink btn-sm" data-act="edit">${ic("pencil", "i-s")}Edit</button>`}</span></div>
        ${editing ? editView(s) : readView(s)}
      </div>
    </div>`;
  }

  function readView(s) {
    const st = status(s);
    const nv = newest(s);
    const ol = older(s);
    const cmp = ol.find((c) => c.agent === S.compareWith) || ol[0];
    let marks = new Set();
    if (cmp && S.highlight) {
      const theirs = new Set(textOf(s, cmp.v).split("\n").map((l) => l.trim()));
      marks = new Set(textOf(s, nv).split("\n").map((l) => l.trim()).filter((l) => l && !theirs.has(l)));
    }
    const claude = AG["claude-code"];
    const pct = Math.round((s.tokens / claude.limit) * 1000) / 10;
    return `<div class="sheet">
      <article>
        <p class="meta">${esc(s.category)} · Edited ${esc(s.updated)}</p>
        <h1 class="doc-title" id="h1" tabindex="-1">${esc(titleCase(s.name))}</h1>
        <p class="doc-lead">${esc(s.description)}</p>
        ${st.key === "bad" ? `<div class="inline-note bad"><b>Problem:</b> ${esc(s.problem)}<br><button type="button" class="btn btn-ink btn-sm" data-act="repair">${esc(s.fix)}</button></div>` : ""}
        ${st.key === "warn" && cmp ? `<div class="inline-note warn"><b>${esc(AG[cmp.agent].name)} has an older copy.</b> The highlighted lines are missing from it.<br><button type="button" class="btn btn-ink btn-sm" data-act="update-older">Update ${ol.length === 1 ? esc(AG[ol[0].agent].name) : plural(ol.length, "copy", "copies")}</button></div>` : ""}
        <div class="doc">${md(textOf(s, nv), marks)}</div>
      </article>
      <aside class="margin" aria-label="About this skill">
        ${st.key === "warn" && cmp ? `<div class="note warn"><b>Note</b>
            <p>${S.highlight ? "The highlighted lines are missing from" : "Some lines are missing from"} ${esc(AG[cmp.agent].name)}'s copy, so it may skip these steps.</p>
            ${ol.length > 1 ? `<label class="hl">Compare with <select class="field" style="height:32px;font-size:13px" id="cmp-with">${ol.map((c) => `<option value="${c.agent}" ${c.agent === cmp.agent ? "selected" : ""}>${esc(AG[c.agent].name)}</option>`).join("")}</select></label>` : ""}
            <label class="hl"><input type="checkbox" id="hl-toggle" ${S.highlight ? "checked" : ""}> Highlight what's missing</label>
            <button type="button" class="btn btn-ink btn-sm" data-act="update-older">Update ${ol.length === 1 ? esc(AG[ol[0].agent].name) : plural(ol.length, "copy", "copies")}</button></div>` : ""}
        ${st.key === "bad" ? `<div class="note bad"><b>Problem</b><p>${esc(s.problem)}</p><button type="button" class="btn btn-ink btn-sm" data-act="repair">${esc(s.fix)}</button></div>` : ""}
        ${st.key === "off" ? `<div class="note"><b>Turned off</b><p>No agent uses this skill right now.</p><button type="button" class="btn btn-ink btn-sm" data-act="all-on">Turn on everywhere</button></div>` : ""}
        ${st.key === "ok" ? `<div class="note ok"><b>Status</b><p>Working. Every copy matches.</p></div>` : ""}
        <div class="note"><b>Used by</b><div class="uses">
          ${s.copies.map((c, i) => `<div class="use">${logo(c.agent, "xs")}<span>${esc(AG[c.agent].name)}${c.state === "broken" ? '<small class="bad">Can\'t be read</small>' : c.v < nv ? '<small class="warn">Older copy</small>' : ""}</span>
            <label class="switch" title="${c.state === "on" ? "On" : "Off"} in ${esc(AG[c.agent].name)}"><input type="checkbox" data-toggle="${i}" ${c.state === "on" ? "checked" : ""} ${c.state === "broken" ? "disabled" : ""}><span class="tr"></span><span class="sr-only">Use in ${esc(AG[c.agent].name)}</span></label></div>`).join("")}
        </div></div>
        <div class="note"><b>Length</b><p>About ${words(s.tokens)} words · ${pct}% of Claude Code's reading space</p></div>
        <div class="note"><b>History</b><ul class="hist">${S.activity.filter((a) => a.text.startsWith(s.name + " ")).slice(0, 3).map((a) => `<li>${esc(a.text.slice(s.name.length + 1))}<small>${esc(a.when)}</small></li>`).join("")}<li>Last edited<small>${esc(s.updated)}</small></li></ul></div>
        <div class="note"><details class="paths"><summary>Folder locations</summary>${s.copies.map((c) => `<code>${esc(AG[c.agent].path)}/${esc(s.name)}</code>`).join("")}</details></div>
        <div><button type="button" class="btn btn-danger btn-sm" data-act="trash">${ic("trash", "i-s")}Move to trash</button></div>
      </aside>
    </div>`;
  }

  function editView(s) {
    const e = S.edit;
    const err = !e.desc.trim() ? "Add a short description so agents know when to use this skill." : e.desc.length > 300 ? "Keep the description under 300 characters." : "";
    const targets = s.copies.filter((c) => c.state !== "broken");
    return `<div class="sheet" style="grid-template-columns:minmax(0,760px)">
      <article>
        <p class="meta">Editing · Changes are saved as a new version, and the old one is kept</p>
        <h1 class="doc-title" id="h1" tabindex="-1">${esc(titleCase(s.name))}</h1>
        <label class="ed-label" for="ed-desc">Description <span style="font-weight:600;color:var(--muted)">(when should an agent use this?)</span></label>
        <input class="ed-input" id="ed-desc" value="${esc(e.desc)}" ${err ? 'aria-invalid="true" aria-describedby="ed-err"' : ""}>
        ${err ? `<p class="ed-err" id="ed-err">${ic("bad", "i-s")}${err}</p>` : `<p class="ed-hint num">${e.desc.length} / 300</p>`}
        <div class="ed-tabs" role="tablist" aria-label="Editor">
          <button type="button" role="tab" aria-selected="${e.tab === "write"}" data-etab="write">Write</button>
          <button type="button" role="tab" aria-selected="${e.tab === "preview"}" data-etab="preview">Preview</button>
          ${e.tab === "write" ? `<span class="ed-tools" aria-label="Formatting"><button type="button" data-ins="## " title="Heading">H</button><button type="button" data-ins="- " title="Bullet list">• List</button><button type="button" data-ins="1. " title="Numbered list">1. List</button><button type="button" data-wrap="**" title="Bold"><b>B</b></button></span>` : ""}
        </div>
        ${e.tab === "write" ? `<label class="sr-only" for="ed-body">Instructions</label><textarea class="ed-area" id="ed-body" spellcheck="true">${esc(e.body)}</textarea>`
          : `<div class="doc" style="margin-top:20px">${md(e.body, new Set())}</div>`}
      </article>
    </div>
    <div class="savebar" role="region" aria-label="Save changes">
      ${e.dirty ? `<span class="dirty">● Unsaved changes</span>` : ""}
      <span class="to">Save to:
        ${targets.map((c) => `<label><input type="checkbox" data-target="${c.agent}" ${e.targets.includes(c.agent) ? "checked" : ""}>${esc(AG[c.agent].name)}</label>`).join("")}
      </span>
      <span class="sp"><button type="button" class="btn btn-soft" data-act="cancel-edit">Cancel</button>
      <button type="button" class="btn btn-ink" data-act="save" ${err || !e.targets.length ? "disabled" : ""}>Save ${e.targets.length ? "to " + plural(e.targets.length, "place") : ""}</button></span>
    </div>`;
  }

  /* Escaped Markdown renderer, with optional line highlighting. */
  function md(src, marks) {
    const inl = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
    const wrap = (raw, html) => (marks.has(raw.trim()) ? `<mark>${html}</mark>` : html);
    const out = []; let list = null;
    const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
    src.split("\n").forEach((line) => {
      let m;
      if ((m = line.match(/^#{1,3}\s+(.*)/))) { close(); out.push(`<h2>${inl(m[1])}</h2>`); }
      else if ((m = line.match(/^\d+\.\s+(.*)/))) { if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; } out.push(`<li>${wrap(line, inl(m[1]))}</li>`); }
      else if ((m = line.match(/^[-*]\s+(.*)/))) { if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; } out.push(`<li>${wrap(line, inl(m[1]))}</li>`); }
      else if ((m = line.match(/^>\s?(.*)/))) { close(); out.push(`<blockquote>${wrap(line, inl(m[1]))}</blockquote>`); }
      else if (line.trim()) { close(); out.push(`<p>${wrap(line, inl(line))}</p>`); }
      else close();
    });
    close();
    return out.join("");
  }

  /* Line diff (LCS) for comparisons. */
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
    return out.filter((l) => l.x.trim());
  }
  const plain = (l) => l.replace(/^#{1,3}\s+/, "").replace(/^[-*]\s+/, "").replace(/^>\s?/, "").replace(/\*\*(.+?)\*\*/g, "$1");
  /* Only the changed lines, plus one line of context before each change. */
  function changes(s, olderV) {
    const d = diff(textOf(s, olderV).split("\n"), textOf(s, newest(s)).split("\n"));
    return d.filter((l, i) => l.t !== "same" || (d[i + 1] && d[i + 1].t !== "same" && (!d[i - 1] || d[i - 1].t === "same")));
  }

  /* ========== SYNC MAP ========== */
  const SLOTS = [[22, 31], [78, 31], [17, 70], [83, 72], [50, 92]];
  function mapPage() {
    const infos = D.agents.map((a) => agentInfo(a.id));
    const sel = S.mapAgent || (infos.find((x) => x.key === "bad") || infos.find((x) => x.key === "warn") || infos[0]).id;
    S.mapAgent = sel;
    const bad = infos.filter((x) => x.key !== "ok").length;
    const HX = 50, HY = 56;
    const tagFor = (inf) => inf.key === "bad" ? `✕ ${inf.broken.length} can't be read` : inf.key === "warn" ? `${inf.old.length} older` : "✓ in sync";
    const line = (inf, i) => {
      const [x, y] = SLOTS[i];
      const stroke = { ok: "var(--ok-line)", warn: "var(--warn-line)", bad: "var(--bad-line)" }[inf.key];
      const dash = inf.key === "warn" ? 'stroke-dasharray="10 8"' : "";
      const mx = (x + HX) / 2, my = (y + HY) / 2;
      const seg = inf.key === "bad"
        ? `<line x1="${HX}" y1="${HY}" x2="${mx - (x - HX) * .08}" y2="${my - (y - HY) * .08}" stroke="${stroke}" stroke-width="4" vector-effect="non-scaling-stroke"/><line x1="${mx + (x - HX) * .08}" y1="${my + (y - HY) * .08}" x2="${x}" y2="${y}" stroke="${stroke}" stroke-width="4" vector-effect="non-scaling-stroke"/>`
        : `<line x1="${HX}" y1="${HY}" x2="${x}" y2="${y}" stroke="${stroke}" stroke-width="4" ${dash} vector-effect="non-scaling-stroke"/>`;
      return seg;
    };
    return `<div class="mapwrap">
      <section class="canvas" aria-label="Sync map">
        <div class="intro">
          <div><h1 class="h1" id="h1" tabindex="-1">Everything is connected to your library</h1>
          <p class="lede">${D.agents.length - bad} agents are in sync. ${bad ? `<b class="warn">${plural(bad, "connection needs", "connections need")} fixing.</b> Click an agent to see why.` : "<b>Nothing needs fixing.</b>"}</p></div>
          <div class="legend" aria-hidden="true">
            <span><svg viewBox="0 0 28 8"><path d="M0 4h28" stroke="#22a05a" stroke-width="3"/></svg>In sync</span>
            <span><svg viewBox="0 0 28 8"><path d="M0 4h28" stroke="#d97706" stroke-width="3" stroke-dasharray="5 4"/></svg>Out of date</span>
            <span><svg viewBox="0 0 28 8"><path d="M0 4h10M18 4h10" stroke="#dc2626" stroke-width="3"/></svg>Broken</span>
          </div>
        </div>
        <svg class="wires" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">${infos.map(line).join("")}</svg>
        <a class="hub" href="#/skills" aria-label="Your library: ${S.skills.length} skills"><b class="num">${S.skills.length}</b><span>skills in your library</span><em>the master copies</em></a>
        ${infos.map((inf, i) => `<span class="tagw ${inf.key} ${inf.key}" style="left:${(SLOTS[i][0] + HX) / 2}%;top:${(SLOTS[i][1] + HY) / 2}%">${tagFor(inf)}</span>`).join("")}
        ${infos.map((inf, i) => `<button type="button" class="node" style="left:${SLOTS[i][0]}%;top:${SLOTS[i][1]}%" data-map="${inf.id}" aria-pressed="${inf.id === sel}" aria-label="${esc(AG[inf.id].name)}: ${tagFor(inf).replace("✕ ", "").replace("✓ ", "")}">${logo(inf.id, "sm")}<span><b>${esc(AG[inf.id].name)}</b><small>${plural(inf.mine.length, "skill")}</small></span></button>`).join("")}
      </section>
      <div class="maplist">
        <h1 class="h1" style="font-size:30px">Sync map</h1>
        <div class="mlist" style="margin-top:16px">${infos.map((inf) => `<button type="button" class="mrow" style="width:100%;background:${inf.id === sel ? "var(--sunken)" : "#fff"};border-left:0;border-right:0;border-bottom:0;text-align:left" data-map="${inf.id}">${logo(inf.id, "xs")}<span><b>${esc(AG[inf.id].name)}</b><small>${plural(inf.mine.length, "skill")}</small></span><span class="pill ${inf.key}">${tagFor(inf)}</span></button>`).join("")}</div>
      </div>
      <aside class="mpanel" aria-live="polite">${mapPanel(agentInfo(sel))}</aside>
    </div>`;
  }
  function mapPanel(inf) {
    const a = AG[inf.id];
    const flow = `<div class="flow">${logo("library", "xs")}Library<span class="ar ${inf.key}"></span>${logo(a.id, "xs")}${esc(a.name)}</div>`;
    if (inf.key === "ok") return `<span class="crumb">Library → ${esc(a.name)}</span>
      <div><h2>${esc(a.name)} is in sync</h2><p class="sub" style="font-size:15px">All ${plural(inf.mine.length, "skill")} match your library.</p></div>${flow}
      <div class="meter"><div class="ml"><span>Reading space used</span><b>${inf.pct}%</b></div><div class="track"><i class="${inf.pct > D.suggestedSpace ? "warn" : ""}" style="width:${Math.min(inf.pct * 2.5, 100)}%"></i><span class="lim" style="left:${D.suggestedSpace * 2.5}%"></span></div></div>
      <div class="cta"><a class="btn btn-line" href="#/skills" data-agent-link="${a.id}" style="flex:1">See ${esc(a.name)}'s skills</a></div>`;
    const picked = S.mapPicked && S.mapPicked.agent === a.id ? S.mapPicked.names : inf.old.map((s) => s.name);
    const peekS = inf.old.find((s) => s.name === S.peek) || null;
    const peekC = peekS && peekS.copies.find((c) => c.agent === a.id);
    return `<span class="crumb">Library → ${esc(a.name)}</span>
      <div><h2>${inf.broken.length ? `${esc(a.name)} can't read ${plural(inf.broken.length, "skill")}` : `${esc(a.name)} has ${plural(inf.old.length, "older skill")}`}</h2>
      <p class="sub" style="font-size:15px">${esc(a.name)} will behave differently from your other agents until these are fixed.</p></div>
      ${flow}
      ${inf.broken.length ? `<div class="mlist">${inf.broken.map((s) => `<div class="mrow"><span class="bad">${ic("bad")}</span><span><b>${esc(s.name)}</b><small>${esc(s.problem)}</small></span><button type="button" class="btn btn-ink btn-sm" data-repair="${esc(s.name)}">Fix</button></div>`).join("")}</div>` : ""}
      ${inf.old.length ? `<div class="mlist">${inf.old.map((s) => {
        const n = changes(s, s.copies.find((c) => c.agent === a.id).v).filter((l) => l.t !== "same").length;
        return `<div class="mrow"><input type="checkbox" data-pick="${esc(s.name)}" ${picked.includes(s.name) ? "checked" : ""} aria-label="Update ${esc(s.name)}"><span><b>${esc(s.name)}</b><small>${plural(n, "line")} different from your library</small></span><button type="button" class="peek" data-peek="${esc(s.name)}" aria-pressed="${S.peek === s.name}">${S.peek === s.name ? "Hide" : "Peek"}</button></div>`;
      }).join("")}</div>
      ${peekS ? `<div class="minidiff" aria-label="Differences in ${esc(peekS.name)}"><div class="h">${esc(peekS.name)}: what will change in ${esc(a.name)}</div>${changes(peekS, peekC.v).map((l) => `<div class="${l.t}">${l.t === "add" ? '<span class="sr-only">Added: </span>' : l.t === "del" ? '<span class="sr-only">Removed: </span>' : ""}${esc(plain(l.x))}</div>`).join("")}</div>` : ""}
      <p class="backup">${ic("undo", "i-s")}A backup is saved first, and you can undo.</p>
      <div class="cta"><button type="button" class="btn btn-ink btn-lg" data-sync="${a.id}" ${picked.length ? "" : "disabled"}>Update ${plural(picked.length, "skill")} in ${esc(a.name)}</button></div>` : ""}`;
  }

  /* ========== INBOX ========== */
  function orderedProblems() {
    const all = problems();
    const rest = all.filter((p) => !S.skipped.includes(p.id));
    const skipped = S.skipped.map((id) => all.find((p) => p.id === id)).filter(Boolean);
    const list = [...rest, ...skipped];
    const i = list.findIndex((p) => p.id === S.front);
    if (i > 0) list.unshift(...list.splice(i, 1));
    return list;
  }
  function inbox() {
    const items = orderedProblems();
    const total = S.done + items.length;
    if (!items.length) return `<div class="inbox"><div class="card empty" style="padding:72px 24px">
      <span class="ic">${ic("check")}</span><h2 id="h1" tabindex="-1">All done</h2>
      <p>${S.done ? `You fixed ${plural(S.done, "thing")}. ` : ""}Every skill can be read, and every copy matches.</p>
      <div style="display:flex;gap:8px;margin-top:8px"><a class="btn btn-ink" href="#/home">Go to Home</a><a class="btn btn-line" href="#/skills">Browse skills</a></div></div></div>`;
    const cur = items[0];
    return `<div class="inbox">
      <div class="prog"><span class="bars" aria-hidden="true">${Array.from({ length: total }, (_, i) => `<i class="${i < S.done ? "done" : i === S.done ? "now" : ""}"></i>`).join("")}</span><span>${S.done} of ${total} done</span></div>
      <h1 class="label" id="h1" tabindex="-1">Next up</h1>
      <article class="card focus" aria-labelledby="focus-t">${focusCard(cur)}</article>
      ${items.length > 1 ? `<h2 class="label">Still to do</h2><div class="queue">${items.slice(1).map((p) => `<button type="button" class="qi ${S.skipped.includes(p.id) ? "skipped" : ""}" data-jump="${p.id}"><span class="k ${p.key} ${p.key}">${dot(p.key)}</span><b>${esc(p.title)}</b><small>${S.skipped.includes(p.id) ? "Skipped" : p.short}</small></button>`).join("")}</div>` : ""}
      <p style="margin-top:24px;color:var(--ok);font-weight:700;display:flex;gap:8px;align-items:center">${ic("check", "i-s")}When this list is empty, everything is working.</p>
    </div>`;
  }
  function focusCard(p) {
    const keys = `<span class="keys"><span><kbd>Enter</kbd> ${p.key === "info" ? "Done" : "Fix"}</span><span><kbd>S</kbd> Skip</span></span>`;
    const skip = `<button type="button" class="btn btn-soft btn-lg" data-skip="${p.id}">Skip for now</button>`;
    if (p.key === "warn") {
      const s = find(p.skill);
      const c = s.copies.find((x) => x.agent === p.agents[0]);
      const ch = changes(s, c.v);
      return `<span class="pill warn">${ic("warn")}Out of date</span>
        <h2 id="focus-t"><span class="who">${esc(join(p.agents.map((id) => AG[id].name)))}</span> ${p.agents.length === 1 ? "has" : "have"} an older copy of ${esc(s.name)}</h2>
        <p class="why">${esc(p.text)}</p>
        <div class="vs">
          <div class="ver"><header>${logo(c.agent, "xs")}${esc(AG[c.agent].name)}'s copy<small>older</small></header>${ch.filter((l) => l.t !== "add").map((l) => `<p class="${l.t}">${esc(plain(l.x))}</p>`).join("")}</div>
          <div class="ver"><header>${logo("library", "xs")}Newest version<small>used by the others</small></header>${ch.filter((l) => l.t !== "del").map((l) => `<p class="${l.t}">${esc(plain(l.x))}</p>`).join("")}</div>
        </div>
        <div class="f-acts"><button type="button" class="btn btn-ink btn-lg" data-primary data-fix="${p.id}">${esc(p.action)}</button>${skip}<a class="link" href="#/skill/${enc(s.name)}">Open skill</a>${keys}</div>`;
    }
    if (p.key === "bad") {
      const s = find(p.skill);
      return `<span class="pill bad">${ic("bad")}Can't be read</span>
        <h2 id="focus-t">${esc(p.title)}</h2>
        <p class="why">${esc(p.text)}</p>
        <div class="f-acts"><button type="button" class="btn btn-ink btn-lg" data-primary data-fix="${p.id}">${esc(p.action)}</button>${skip}<a class="link" href="#/skill/${enc(s.name)}">Open skill</a>${keys}</div>`;
    }
    const inf = agentInfo(p.agent);
    const big = [...inf.on].sort((a, b) => b.tokens - a.tokens).slice(0, 4);
    return `<span class="pill" style="background:var(--sunken);color:var(--ink-2)">${ic("info")}Suggestion</span>
      <h2 id="focus-t">${esc(p.title)}</h2>
      <p class="why">${esc(p.text)} Here are its largest skills:</p>
      <div class="big-list">${big.map((s) => `<div class="big-row"><span><b>${esc(s.name)}</b><small>About ${words(s.tokens)} words · ${Math.round((s.tokens / AG[p.agent].limit) * 1000) / 10}%</small></span>
        <a class="link" href="#/skill/${enc(s.name)}">Open</a><button type="button" class="btn btn-line btn-sm" data-off-in="${esc(s.name)}|${p.agent}">Turn off in ${esc(AG[p.agent].name)}</button></div>`).join("")}</div>
      <div class="f-acts"><button type="button" class="btn btn-ink btn-lg" data-primary data-fix="${p.id}">Done</button>${skip}${keys}</div>`;
  }

  /* ---------- Actions ---------- */
  const log = (text) => S.activity.unshift({ when: "Just now", text });
  function withUndo(label, fn, after) {
    const snap = { skills: clone(S.skills), texts: clone(S.texts), done: S.done, dismissed: new Set(S.dismissed), skipped: [...S.skipped], front: S.front, activity: clone(S.activity) };
    fn();
    render(after);
    toast(label, () => { Object.assign(S, snap); render(); });
  }
  function updateOlder(s, agents) {
    const nv = newest(s);
    s.copies.forEach((c) => { if (c.state !== "broken" && (!agents || agents.includes(c.agent)) && c.v < nv) c.v = nv; });
  }
  function repair(s) {
    const b = s.copies.find((c) => c.state === "broken");
    const good = s.copies.find((c) => c.state !== "broken");
    if (good) { b.state = "on"; b.v = good.v; log(`${s.name} was repaired in ${AG[b.agent].name}`); return null; }
    const old = s.name;
    s.name = s.name.toLowerCase().replace(/\s+/g, "-"); b.state = "on";
    log(`${s.name} was renamed from “${old}”`);
    return s.name;
  }
  function fixProblem(p) {
    if (p.key === "warn") { const s = find(p.skill); updateOlder(s, p.agents); log(`${s.name} was updated in ${join(p.agents.map((id) => AG[id].name))}`); }
    else if (p.key === "bad") repair(find(p.skill));
    else S.dismissed.add(p.id);
    S.skipped = S.skipped.filter((id) => id !== p.id);
    if (S.front === p.id) S.front = null;
    S.done++;
  }

  /* ---------- Dialogs & toasts ---------- */
  function dialog({ title, body, cancel, confirm, onConfirm, danger }) {
    const opener = document.activeElement;
    const el = document.createElement("div");
    el.className = "scrim";
    el.innerHTML = `<div class="dlg" role="dialog" aria-modal="true" aria-labelledby="dlg-t"><div class="dlg-h"><h2 id="dlg-t">${title}</h2></div>
      <div class="dlg-b">${body}</div><div class="dlg-f"><button type="button" class="btn btn-line" data-x>${cancel}</button><button type="button" class="btn ${danger ? "btn-danger" : "btn-ink"}" data-ok>${confirm}</button></div></div>`;
    document.body.appendChild(el);
    $("#main").inert = true; $(".top").inert = true;
    const close = () => { el.remove(); $("#main").inert = false; $(".top").inert = false; if (opener && opener.isConnected) opener.focus(); };
    el.addEventListener("click", (e) => {
      if (e.target === el || e.target.closest("[data-x]")) close();
      else if (e.target.closest("[data-ok]")) { close(); onConfirm(el); }
    });
    el.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.stopPropagation(); close(); }
      if (e.key === "Tab") {
        const f = $$("button, input", el); const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    });
    $("[data-x]", el).focus();
    return el;
  }
  function toast(text, undo) {
    const t = document.createElement("div");
    t.className = "toast"; t.setAttribute("role", "status");
    t.innerHTML = `${ic("ok")}<span>${esc(text)}</span>${undo ? '<button type="button">Undo</button>' : ""}`;
    $("#toasts").appendChild(t);
    if (undo) t.querySelector("button").addEventListener("click", () => { undo(); t.remove(); toast("Undone"); });
    setTimeout(() => t.remove(), undo ? 9000 : 4000);
  }
  const announce = (m) => { const l = $("#live"); l.textContent = ""; setTimeout(() => (l.textContent = m), 30); };

  /* ---------- Router ---------- */
  function route() {
    const h = location.hash.replace(/^#\/?/, "");
    const [p, ...rest] = h.split("/");
    if (p === "skill" && rest.length) return { page: "skill", name: decodeURIComponent(rest.join("/")) };
    if (["skills", "map", "inbox"].includes(p)) return { page: p };
    return { page: "home" };
  }
  let last = "";
  function render(opt = {}) {
    const r = route();
    const key = r.page + ":" + (r.name || "");
    const y = scrollY;
    const html = { home, skills: shelf, map: mapPage, inbox, skill: () => notebook(r.name) }[r.page]();
    $("#main").innerHTML = html;
    $$("[data-nav]").forEach((a) => (a.dataset.nav === (r.page === "skill" ? "skills" : r.page) ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
    const n = problems().length;
    $("#inbox-n").textContent = n || "";
    $("#inbox-n").setAttribute("aria-label", `${n} items`);
    document.title = `${{ home: "Home", skills: "Skills", map: "Sync map", inbox: "Inbox", skill: r.name }[r.page]} · Skills Manager`;
    if (key !== last) { scrollTo(0, 0); const h = $("#h1"); h && h.focus({ preventScroll: true }); }
    else { scrollTo(0, y); if (opt.focus) { const f = $(opt.focus); f && f.focus({ preventScroll: true }); } }
    last = key;
    const area = $("#ed-body"); if (area) { area.style.height = "auto"; area.style.height = Math.max(420, area.scrollHeight + 4) + "px"; }
  }
  function go(h) {
    if (S.edit && S.edit.dirty && !h.startsWith("#/skill/" + enc(S.edit.name))) {
      dialog({ title: "Discard your changes?", body: `<p>You have unsaved changes to “${esc(S.edit.name)}”.</p>`, cancel: "Keep editing", confirm: "Discard changes", danger: true,
        onConfirm: () => { S.edit = null; location.hash = h; } });
      return;
    }
    if (location.hash === h) render(); else location.hash = h;
  }

  /* ---------- Events ---------- */
  document.addEventListener("click", (e) => {
    const t = e.target.closest("a, button");
    if (!t) return;
    // Guard navigation away from unsaved edits.
    if (t.tagName === "A" && t.getAttribute("href") && t.getAttribute("href").startsWith("#") && S.edit && S.edit.dirty) {
      e.preventDefault(); return go(t.getAttribute("href"));
    }
    if (t.dataset.agentLink) { S.agent = t.dataset.agentLink; S.filter = "all"; S.query = ""; }
    if (t.dataset.inboxTo) S.front = t.dataset.inboxTo;
    if (t.dataset.soon) return toast(`${t.dataset.soon} comes in a later version`);
    if (t.dataset.filter) { S.filter = t.dataset.filter; return render({ focus: `[data-filter="${S.filter}"]` }); }

    // Map
    if (t.dataset.map) { S.mapAgent = t.dataset.map; S.mapPicked = null; S.peek = null; return render({ focus: `.node[data-map="${t.dataset.map}"]` }); }
    if (t.dataset.peek) { S.peek = S.peek === t.dataset.peek ? null : t.dataset.peek; return render({ focus: `[data-peek="${CSS.escape(t.dataset.peek)}"]` }); }
    if (t.dataset.sync) {
      const id = t.dataset.sync, inf = agentInfo(id);
      const names = S.mapPicked && S.mapPicked.agent === id ? S.mapPicked.names : inf.old.map((s) => s.name);
      return withUndo(`Updated ${plural(names.length, "skill")} in ${AG[id].name}`, () => {
        names.forEach((n) => updateOlder(find(n), [id]));
        log(`${join(names)} ${names.length === 1 ? "was" : "were"} updated in ${AG[id].name}`);
        S.mapPicked = null; S.peek = null;
      }, { focus: `.node[data-map="${id}"]` });
    }
    if (t.dataset.repair) { const s = find(t.dataset.repair); return withUndo(`Fixed “${s.name}”`, () => repair(s)); }

    // Inbox
    if (t.dataset.fix) { const p = problems().find((x) => x.id === t.dataset.fix); return withUndo(p.key === "info" ? "Marked as done" : "Fixed. On to the next one", () => fixProblem(p), { focus: "#h1" }); }
    if (t.dataset.skip) { if (S.front === t.dataset.skip) S.front = null; S.skipped = S.skipped.filter((id) => id !== t.dataset.skip); S.skipped.push(t.dataset.skip); render({ focus: "#h1" }); return announce("Skipped. Showing the next item."); }
    if (t.dataset.jump) { S.front = t.dataset.jump; return render({ focus: "#focus-t" }); }
    if (t.dataset.offIn) { const [n, id] = t.dataset.offIn.split("|"); const s = find(n); return withUndo(`Turned off ${n} in ${AG[id].name}`, () => { s.copies.find((c) => c.agent === id).state = "off"; log(`${n} was turned off in ${AG[id].name}`); }); }

    // Editor helpers
    if (t.dataset.etab) { syncEditFields(); S.edit.tab = t.dataset.etab; return render({ focus: `[data-etab="${t.dataset.etab}"]` }); }
    if (t.dataset.ins !== undefined || t.dataset.wrap) return insertFormat(t.dataset.ins, t.dataset.wrap);

    const a = t.dataset.act;
    if (!a) return;
    if (a === "clear") { S.query = ""; S.filter = "all"; S.agent = "all"; return render({ focus: "#q" }); }
    if (a === "new") return toast("Creating a skill comes in a later version");
    const s = route().name && find(route().name);
    if (!s) return;
    if (a === "edit") { S.edit = { name: s.name, desc: s.description, body: textOf(s, newest(s)), tab: "write", dirty: false, targets: s.copies.filter((c) => c.state !== "broken").map((c) => c.agent) }; return render({ focus: "#ed-body" }); }
    if (a === "cancel-edit") {
      if (!S.edit.dirty) { S.edit = null; return render({ focus: '[data-act="edit"]' }); }
      return dialog({ title: "Discard your changes?", body: "<p>Your edits haven't been saved yet.</p>", cancel: "Keep editing", confirm: "Discard changes", danger: true, onConfirm: () => { S.edit = null; render({ focus: '[data-act="edit"]' }); } });
    }
    if (a === "save") { syncEditFields(); return save(s); }
    if (a === "update-older") return withUndo(`Updated ${join(older(s).map((c) => AG[c.agent].name))}`, () => { const names = older(s).map((c) => AG[c.agent].name); updateOlder(s); log(`${s.name} was updated in ${join(names)}`); });
    if (a === "repair") { let nn = null; withUndo(`Fixed “${s.name}”`, () => { nn = repair(s); if (nn) history.replaceState(null, "", "#/skill/" + enc(nn)); last = "skill:" + s.name; }); return; }
    if (a === "all-on") return withUndo("Turned on everywhere", () => { s.copies.forEach((c) => { if (c.state === "off") c.state = "on"; }); log(`${s.name} was turned on everywhere`); });
    if (a === "share") return shareDialog(s);
    if (a === "trash") {
      const i = S.skills.indexOf(s);
      S.skills.splice(i, 1); log(`${s.name} was moved to the trash`);
      location.hash = "#/skills";
      return toast(`Moved “${s.name}” to the trash`, () => { S.skills.splice(i, 0, s); location.hash = "#/skill/" + enc(s.name); });
    }
  });

  function syncEditFields() {
    if (!S.edit) return;
    const d = $("#ed-desc"), b = $("#ed-body");
    if (d) S.edit.desc = d.value;
    if (b) S.edit.body = b.value;
  }
  function insertFormat(prefix, wrapWith) {
    const ta = $("#ed-body"); if (!ta) return;
    const [a, b] = [ta.selectionStart, ta.selectionEnd];
    const v = ta.value;
    if (wrapWith) { ta.value = v.slice(0, a) + wrapWith + (v.slice(a, b) || "bold text") + wrapWith + v.slice(b); }
    else { const ls = v.lastIndexOf("\n", a - 1) + 1; ta.value = v.slice(0, ls) + prefix + v.slice(ls); }
    S.edit.body = ta.value; S.edit.dirty = true;
    ta.focus();
    const bar = $(".dirty"); if (!bar) render({ focus: "#ed-body" });
  }
  function save(s) {
    const e = S.edit;
    const before = { skills: clone(S.skills), texts: clone(S.texts), activity: clone(S.activity) };
    const nv = newest(s) + 1;
    S.texts[s.name] = S.texts[s.name] || {};
    S.texts[s.name][nv] = e.body;
    s.description = e.desc.trim();
    s.tokens = Math.max(200, Math.round((e.body.length + e.desc.length) / 4));
    s.updated = "Just now";
    s.copies.forEach((c) => { if (e.targets.includes(c.agent)) c.v = nv; });
    const names = e.targets.map((id) => AG[id].name);
    log(`${s.name} was edited and saved to ${join(names)}`);
    S.edit = null;
    render({ focus: '[data-act="edit"]' });
    const left = s.copies.filter((c) => c.state !== "broken" && !e.targets.includes(c.agent)).length;
    toast(left ? `Saved. ${plural(left, "copy was", "copies were")} left as before.` : `Saved to ${plural(names.length, "place")}`, () => { Object.assign(S, before); render(); });
  }
  function shareDialog(s) {
    const have = new Set(s.copies.map((c) => c.agent));
    const opts = D.agents.filter((a) => !have.has(a.id));
    if (!opts.length) return toast(`“${s.name}” is already in every agent`);
    dialog({ title: `Add “${esc(s.name)}” to another agent`,
      body: `<p>We'll copy the newest version. Agents that already have it won't change.</p>${opts.map((a) => `<label class="pick"><input type="checkbox" value="${a.id}">${logo(a.id, "xs")}<span>${esc(a.name)}<small>${esc(a.path)}</small></span></label>`).join("")}`,
      cancel: "Cancel", confirm: "Add copies",
      onConfirm: (el) => {
        const ids = $$("input:checked", el).map((i) => i.value);
        if (!ids.length) return;
        withUndo(`Added to ${join(ids.map((id) => AG[id].name))}`, () => { const v = newest(s); ids.forEach((id) => s.copies.push({ agent: id, state: "on", v })); log(`${s.name} was added to ${join(ids.map((id) => AG[id].name))}`); });
      } });
  }

  document.addEventListener("change", (e) => {
    const t = e.target;
    if (t.id === "agent-f") { S.agent = t.value; return render({ focus: "#agent-f" }); }
    if (t.id === "hl-toggle") { S.highlight = t.checked; return render({ focus: "#hl-toggle" }); }
    if (t.id === "cmp-with") { S.compareWith = t.value; return render({ focus: "#cmp-with" }); }
    if (t.dataset.pick) {
      const inf = agentInfo(S.mapAgent);
      const cur = S.mapPicked && S.mapPicked.agent === S.mapAgent ? S.mapPicked.names : inf.old.map((s) => s.name);
      const names = t.checked ? [...cur, t.dataset.pick] : cur.filter((n) => n !== t.dataset.pick);
      S.mapPicked = { agent: S.mapAgent, names };
      return render({ focus: `[data-pick="${CSS.escape(t.dataset.pick)}"]` });
    }
    if (t.dataset.target) { syncEditFields(); S.edit.targets = t.checked ? [...S.edit.targets, t.dataset.target] : S.edit.targets.filter((x) => x !== t.dataset.target); return render({ focus: `[data-target="${t.dataset.target}"]` }); }
    if (t.dataset.toggle !== undefined) {
      const s = find(route().name), c = s.copies[+t.dataset.toggle];
      return withUndo(`${t.checked ? "Turned on" : "Turned off"} in ${AG[c.agent].name}`, () => { c.state = t.checked ? "on" : "off"; log(`${s.name} was turned ${c.state} in ${AG[c.agent].name}`); }, { focus: `[data-toggle="${t.dataset.toggle}"]` });
    }
  });

  let qTimer;
  document.addEventListener("input", (e) => {
    const t = e.target;
    if (t.id === "q") {
      clearTimeout(qTimer);
      qTimer = setTimeout(() => { S.query = t.value; const p = t.selectionStart; render({ focus: "#q" }); const q = $("#q"); q && q.setSelectionRange(p, p); announce($(".count").textContent); }, 140);
    }
    if (t.id === "tree-q") { const v = t.value.trim().toLowerCase(); $$(".tree a").forEach((a) => (a.hidden = v && !a.dataset.tree.includes(v))); }
    if (t.id === "ed-desc" || t.id === "ed-body") {
      const wasDirty = S.edit.dirty;
      syncEditFields(); S.edit.dirty = true;
      if (t.id === "ed-body") { t.style.height = "auto"; t.style.height = Math.max(420, t.scrollHeight + 4) + "px"; }
      const errNow = !S.edit.desc.trim() || S.edit.desc.length > 300;
      const errShown = !!$("#ed-err");
      if (!wasDirty || (t.id === "ed-desc" && errNow !== errShown)) { const p = t.selectionStart; render({ focus: "#" + t.id }); const f = $("#" + t.id); f && f.setSelectionRange(p, p); }
      else if (t.id === "ed-desc") { const h = $(".ed-hint"); if (h) h.textContent = `${S.edit.desc.length} / 300`; }
    }
  });

  $("#gsearch").addEventListener("submit", (e) => { e.preventDefault(); S.query = $("#gq").value; S.filter = "all"; S.agent = "all"; $("#gq").value = ""; go("#/skills"); });

  document.addEventListener("keydown", (e) => {
    const el = document.activeElement;
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) && el.type !== "checkbox";
    if (e.key === "/" && !typing && !$(".scrim")) { e.preventDefault(); ($("#q") || $("#gq")).focus(); return; }
    if (route().page === "inbox" && !typing && !$(".scrim") && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (e.key === "Enter" && !el.closest("button, a, label")) { const b = $("[data-primary]"); if (b) { e.preventDefault(); b.click(); } }
      if (e.key.toLowerCase() === "s") { const b = $("[data-skip]"); if (b) { e.preventDefault(); b.click(); } }
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && S.edit) { e.preventDefault(); const b = $('[data-act="save"]'); if (b && !b.disabled) b.click(); }
  });
  addEventListener("beforeunload", (e) => { if (S.edit && S.edit.dirty) { e.preventDefault(); e.returnValue = ""; } });

  addEventListener("hashchange", () => {
    if (S.edit && !location.hash.startsWith("#/skill/" + enc(S.edit.name))) S.edit = null;
    render();
  });
  if (!location.hash) history.replaceState(null, "", "#/home");
  render();
})();
