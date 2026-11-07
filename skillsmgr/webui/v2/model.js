/* Skills Manager v2 — pure data model (no DOM, no network).
 *
 * Turns the API's observations into the vocabulary the new interface speaks:
 * agents, skills, copies, status, problems. Nothing here asserts more than the
 * filesystem reported: there is no "newest" version (the tool has no version
 * order), so a skill whose copies differ is "Copies differ" and the reference
 * copy is the one most places hold, never an elected winner.
 */
"use strict";

(function () {
  const D = window.SkillManagerDomain;

  /* ---------- Small helpers ---------- */
  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ESC[c]);
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + "s"}`;
  const join = (a) => (a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]);
  const words = (tokens) => Math.round((tokens * 0.75) / 10) * 10;

  /* ---------- Agents ---------- */
  const BRAND = {
    "claude-code": ["CC", "#d97757"], codex: ["CX", "#2f6f5e"], cursor: ["CU", "#1b1d22"],
    gemini: ["GE", "#3d7be0"], opencode: ["OC", "#b04a7a"], commandcode: ["CM", "#7a5ad6"],
    agents: ["SF", "#55585f"], global: ["LB", "#55585f"],
  };
  const PALETTE = ["#d97757", "#2f6f5e", "#3d7be0", "#b04a7a", "#7a5ad6", "#a2510a", "#0e7490", "#1c7a47"];
  function hash(s) { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0; return h; }
  function initialsOf(label) {
    const parts = String(label || "?").split(/[\s_-]+/).filter(Boolean);
    return ((parts[0] || "?")[0] + (parts[1] ? parts[1][0] : (parts[0] || "?")[1] || "")).toUpperCase();
  }
  /* The reading window the share is measured against. The tool cannot know the
   * model behind an agent, so this is a stated assumption, not an observation. */
  const WINDOW_BY_CONSUMER = { codex: 400000, "claude-code": 1000000, gemini: 1000000 };
  const DEFAULT_WINDOW = 1000000;

  function shortPath(p) {
    const home = String(p || "").match(/^\/home\/[^/]+|^\/Users\/[^/]+/);
    return home ? "~" + p.slice(home[0].length) : p;
  }

  function buildAgents(scopes) {
    const out = [];
    for (const s of Array.isArray(scopes) ? scopes : []) {
      const kind = String(s.kind || "");
      if (s.exists === false || (kind !== "agent" && kind !== "global" && kind !== "project")) continue;
      const brand = BRAND[s.id] || [initialsOf(s.label || s.id), PALETTE[hash(String(s.id)) % PALETTE.length]];
      out.push({
        id: s.id, name: kind === "global" ? "Your library" : s.id === "agents" ? "Shared skills folder" : (s.label || s.id), kind,
        initials: brand[0], color: brand[1], path: shortPath(s.path || ""),
        limit: WINDOW_BY_CONSUMER[s.consumer || s.id] || DEFAULT_WINDOW,
        library: kind === "global", writable: s.writable !== false && s.availability !== "read-only",
      });
    }
    return out;
  }

  /* ---------- Copies and skills ---------- */
  const BROKEN_WHY = {
    linked: ["Linked outside its folder", "This is a shortcut to a folder outside the agent's skills folder. The app does not follow it, so a write could never land somewhere unexpected.", "Copy the real folder into the skills folder instead of linking it."],
    unaddressable: ["Unusual folder name", "The app cannot address this entry using its supported skill names. Agent loading is not checked.", "Rename the folder to lowercase words joined by hyphens."],
    invalid: ["Damaged file", "The app cannot parse this skill's document. Agent loading is not checked.", "Replace it with a working copy, or repair the first lines by hand."],
    undecodable: ["Not readable text", "The file is not saved as UTF-8 text. This screen offers manual repair because text Undo cannot restore its original bytes.", "Keep a copy of the original file, then open it in a text editor and save it as UTF-8."],
    malformed: ["Damaged file", "The app cannot parse this skill's document. Agent loading is not checked.", "Replace it with a working copy, or repair the first lines by hand."],
  };

  function copyOf(record) {
    /* observedStateFor() ranks `invalid` above `linked`, but the classic Library
     * badges a refused symlink first (observedStateKeys); follow that reading so
     * the two interfaces never disagree about the same record. */
    const obs = D.observeRecord(record);
    const undecodable = /utf-?8|codec|decode/i.test(String(record.decode_error || ""));
    const state = obs.linkEscape ? "linked" : obs.notAddressable ? "unaddressable" : undecodable ? "undecodable" : D.observedStateFor(record);
    /* A refused symlink is not a damaged skill. This tool will not follow it;
     * the target and agent loading remain unobserved. */
    const broken = state === "invalid" || state === "malformed" || state === "unaddressable" || state === "undecodable";
    const linked = state === "linked";
    /* SCOPE-2: a link into another managed scope root is read read-only. It is
     * a readable copy in another managed root; effective loading is unknown. It is
     * not the agent's own copy, so nothing here may toggle or edit it. */
    const readOnly = !!obs.linkFollowed;
    /* The list request omits document bodies, so an absent `body` key means
     * "not loaded yet", never "empty document". Keep the two apart. */
    const bodyLoaded = Object.prototype.hasOwnProperty.call(record, "body") && typeof record.body === "string";
    return {
      name: String(record.name || ""),
      scope: record.scope, label: record.scope_label || record.scope,
      state: broken ? "broken" : linked ? "link" : state === "disabled" ? "off" : "on",
      kind: broken || linked ? state : "", hash: broken || linked ? "" : String(record.content_hash || ""),
      tokens: record.tokens || 0, path: record.physical_path || record.path || "",
      /* Where a followed link's document actually lives, and the fact that it
       * must not be written through this scope. */
      readOnly, linkFrom: readOnly ? String(record.link_target_root || "") : "",
      linkedTo: readOnly ? String(record.linked_to || "") : "",
      body: bodyLoaded ? record.body : "", bodyLoaded,
      description: record.description || "", record,
    };
  }

  /* Reference = the content most readable copies hold. A tie is reported as
   * ambiguous so the interface asks instead of guessing. Physical aliases are
   * separate scope views, but one physical document gets one vote. */
  function reference(copies, agentOrder) {
    const physical = new Map();
    for (const copy of copies) {
      if (copy.state === "broken" || !copy.hash) continue;
      const key = String(copy.path || copy.record.physical_path || copy.record.path || copy.scope);
      const existing = physical.get(key);
      if (!existing || (existing.readOnly && !copy.readOnly) ||
          (existing.readOnly === copy.readOnly && agentOrder(copy.scope) < agentOrder(existing.scope))) {
        physical.set(key, copy);
      }
    }
    const readable = [...physical.values()];
    const tally = new Map();
    for (const c of readable) tally.set(c.hash, (tally.get(c.hash) || []).concat(c));
    const groups = [...tally.values()].sort((a, b) => b.length - a.length || agentOrder(a[0].scope) - agentOrder(b[0].scope));
    if (!groups.length) return { hash: "", holders: [], ambiguous: false, groups: [] };
    const ambiguous = groups.length > 1 && groups[0].length === groups[1].length;
    return { hash: groups[0][0].hash, holders: groups[0], ambiguous, groups };
  }

  /* A dot-prefixed or file-like entry (".system", "README.md") in a skills folder
   * is not a skill; agents ignore it, so it is a note, never an error. */
  const NOT_A_SKILL = /^\.|\.[A-Za-z0-9]{1,5}$/;

  const STATUS = {
    bad: { key: "bad", label: "Can't be read", icon: "bad", rank: 0 },
    warn: { key: "warn", label: "Copies differ", icon: "warn", rank: 1 },
    ok: { key: "ok", label: "Working", icon: "ok", rank: 2 },
    linked: { key: "linked", label: "Linked elsewhere", icon: "info", rank: 2 },
    note: { key: "note", label: "Not a skill", icon: "info", rank: 2 },
    off: { key: "off", label: "Turned off", icon: "off", rank: 3 },
  };

  function buildSkills(records, agents) {
    const order = new Map(agents.map((a, i) => [a.id, i]));
    const rank = (id) => (order.has(id) ? order.get(id) : 99);
    const byName = new Map();
    const seen = new Map();
    for (const r of Array.isArray(records) ? records : []) {
      const name = String(r.name || "");
      if (!name) continue;
      const key = name + "\u0000" + String(r.physical_path || r.path || r.scope);
      const copy = copyOf(r);
      const previous = seen.get(key) || [];
      const sameScope = previous.find((item) => item.copy.scope === copy.scope);
      if (sameScope) {
        if (sameScope.copy.readOnly && !copy.readOnly) {
          byName.get(name)[sameScope.index] = copy;
          sameScope.copy = copy;
        }
        continue;
      }
      /* Preserve one followed link row per agent so that agent-specific views
       * reflect what that consumer loads. Ordinary duplicate-root observations
       * still collapse, and a real row is retained beside any link aliases. */
      if (previous.length && !copy.readOnly && previous.some((item) => !item.copy.readOnly)) continue;
      if (!byName.has(name)) byName.set(name, []);
      const copies = byName.get(name);
      previous.push({ index: copies.length, copy });
      seen.set(key, previous);
      copies.push(copy);
    }
    const skills = [];
    for (const [name, copies] of byName) {
      copies.sort((a, b) => rank(a.scope) - rank(b.scope));
      const ref = reference(copies, rank);
      const fileLike = NOT_A_SKILL.test(name) && copies.every((c) => c.state === "broken" && D.observeRecord(c.record).notAddressable);
      const status = fileLike ? STATUS.note : copies.some((c) => c.state === "broken") ? STATUS.bad
        : !copies.some((c) => c.state === "on" || c.state === "link") ? STATUS.off
        : ref.groups.length > 1 ? STATUS.warn
        : copies.some((c) => c.state === "link") ? STATUS.linked : STATUS.ok;
      /* Name each distinct text: A is the one most places hold. This answers the
       * question users ask most, "which copy does each agent have". */
      const versionByHash = new Map();
      ref.groups.forEach((g, i) => {
        const version = String.fromCharCode(65 + Math.min(i, 25));
        versionByHash.set(g[0].hash, version);
        for (const c of g) c.version = version;
      });
      for (const c of copies) if (!c.version && versionByHash.has(c.hash)) c.version = versionByHash.get(c.hash);
      const pick = (ref.holders[0] || copies.find((c) => c.state !== "broken" && !c.readOnly) || copies[0]);
      const category = (copies.map((c) => c.record.category).find((c) => c && c !== "uncategorized")) || "";
      skills.push({
        name, copies, status, ref, category,
        description: (pick.description || copies.map((c) => c.description).find(Boolean) || ""),
        tokens: pick.tokens || 0, primary: pick,
        differing: ref.hash ? copies.filter((c) => c.state !== "broken" && c.hash && c.hash !== ref.hash) : [],
        broken: copies.filter((c) => c.state === "broken"),
        tools: copies.filter((c) => !agents.find((a) => a.id === c.scope && a.library)),
      });
    }
    skills.sort((a, b) => a.name.localeCompare(b.name));
    return skills;
  }

  /* ---------- Per-agent summary ---------- */
  function agentInfo(agent, skills, suggested) {
    const mine = skills.filter((s) => s.status !== STATUS.note && s.copies.some((c) => c.scope === agent.id));
    const copyIn = (s) => s.copies.find((c) => c.scope === agent.id);
    const on = mine.filter((s) => copyIn(s).state === "on");
    const tokens = on.reduce((n, s) => n + (copyIn(s).tokens || 0), 0);
    const differing = mine.filter((s) => s.differing.some((c) => c.scope === agent.id));
    const broken = mine.filter((s) => copyIn(s).state === "broken" && s.status === STATUS.bad);
    const pct = agent.limit ? Math.round((tokens / agent.limit) * 1000) / 10 : 0;
    const links = mine.filter((s) => copyIn(s).state === "link");
    const key = broken.length ? "bad" : differing.length ? "warn" : "ok";
    return { id: agent.id, agent, mine, on, tokens, differing, broken, links, pct, key, over: pct > suggested };
  }

  /* ---------- Problems (the Inbox) ---------- */
  function problems(skills, agents, infos, suggested) {
    const name = (id) => (agents.find((a) => a.id === id) || { name: id }).name;
    const out = [];
    for (const s of skills) {
      if (s.status === STATUS.note) {
        out.push({ id: "note:" + s.name, key: "info", skill: s.name, agents: s.broken.map((c) => c.scope), noteOnly: true,
          title: `“${s.name}” looks like a file or system folder, not a skill`, short: "Not a skill",
          text: "Agents ignore entries like this, so nothing is broken. You can leave it where it is.", action: "Got it" });
      } else if (s.status.key === "bad") {
        const repairable = (c) => c.kind === "invalid" || c.kind === "malformed";
        const b = s.broken.find((c) => !repairable(c)) || s.broken[0];
        const why = BROKEN_WHY[b.kind] || BROKEN_WHY.invalid;
        const good = s.copies.find((c) => !c.readOnly && c.hash && (c.state === "on" || c.state === "off"))
          || s.copies.find((c) => c.hash && (c.state === "on" || c.state === "off"));
        const fixable = !!good && s.broken.every(repairable);
        const sole = !good;
        out.push({
          id: "bad:" + s.name, key: "bad", skill: s.name, agents: s.broken.map((c) => c.scope), kind: b.kind,
          title: sole ? `No agent can read “${s.name}”` : `${name(b.scope)} can't read “${s.name}”`,
          short: why[0], text: why[1], how: why[2],
          /* Only a damaged document can be replaced from a working copy; the
           * other kinds need a change on disk the app does not make. */
          fixable, source: good ? good.scope : "",
          action: fixable ? `Replace with ${name(good.scope)}'s copy` : "Show me how",
        });
      } else if (s.status.key === "warn") {
        const targets = s.differing.filter((c) => !c.readOnly).map((c) => c.scope);
        const names = targets.map(name);
        out.push({
          id: "warn:" + s.name, key: "warn", skill: s.name, agents: targets, ambiguous: s.ref.ambiguous,
          title: `${join(names)} ${names.length === 1 ? "has a different copy" : "have different copies"} of “${s.name}”`,
          short: "Copies differ",
          text: `Your agents hold different versions of this skill, so they may behave differently until the copies match.`,
          action: `Make ${names.length === 1 ? names[0] + "'s copy" : names.length + " copies"} match`,
        });
      }
    }
    for (const inf of infos) {
      if (inf.agent.library || !inf.over || !inf.on.length) continue;
      out.push({
        id: "space:" + inf.id, key: "info", agent: inf.id, space: true,
        title: `${inf.agent.name}'s skills would fill ${inf.pct}% of a reading window`,
        short: "Suggestion",
        text: `If every skill were read in full, that leaves little room for your code. Turning off skills you rarely use in ${inf.agent.name} frees space.`,
        action: "Done",
      });
    }
    for (const inf of infos) {
      if (inf.agent.library || !inf.links.length) continue;
      out.push({
        id: "link:" + inf.id, key: "info", agent: inf.id, linkAgent: true,
        title: `${inf.agent.name} has ${plural(inf.links.length, "skill")} linked from outside its folder`,
        short: "For your information",
        text: "These are shortcuts to folders elsewhere. This app does not follow them, so their contents and agent loading are unobserved; it cannot compare or edit them.",
        action: "Got it",
      });
    }
    const rank = { bad: 0, warn: 1, info: 2 };
    return out.sort((a, b) => rank[a.key] - rank[b.key] || a.title.localeCompare(b.title));
  }

  function build(records, scopes, opts) {
    const suggested = (opts && opts.suggested) || 100;
    const agents = buildAgents(scopes);
    const skills = buildSkills(records, agents);
    const infos = agents.map((a) => agentInfo(a, skills, suggested));
    const real = infos.filter((i) => !i.agent.library && i.mine.length);
    return {
      agents, skills, infos, suggested,
      rooms: real, problems: problems(skills, agents, infos, suggested),
      byName: new Map(skills.map((s) => [s.name, s])),
      agent: (id) => agents.find((a) => a.id === id),
      info: (id) => infos.find((i) => i.id === id),
    };
  }

  /* ---------- Line diff (LCS) ---------- */
  const MAX_DIFF_CELLS = 4000000;
  function diffLines(a, b) {
    const n = a.length, m = b.length;
    if (n * m > MAX_DIFF_CELLS) { return [...a.map((x) => ({ t: "del", x })), ...b.map((x) => ({ t: "add", x }))].filter((l) => l.x.trim()); }
    const dp = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
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
  const plainLine = (l) => String(l).replace(/^#{1,3}\s+/, "").replace(/^[-*]\s+/, "").replace(/^>\s?/, "").replace(/\*\*(.+?)\*\*/g, "$1");
  /* Only changed lines, plus one line of context before each change. */
  function changes(fromBody, toBody) {
    const d = diffLines(String(fromBody).split("\n"), String(toBody).split("\n"));
    return d.filter((l, i) => l.t !== "same" || (d[i + 1] && d[i + 1].t !== "same" && (!d[i - 1] || d[i - 1].t === "same")));
  }

  /* ---------- Escaped Markdown (with optional highlighted lines) ---------- */
  function stripFrontmatter(text) {
    const m = String(text).match(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/);
    return m ? String(text).slice(m[0].length) : String(text);
  }
  function renderDoc(src, marks) {
    const set = marks || new Set();
    /* Links are shown as text plus their address, never as live anchors: a
     * skill body is untrusted, and a reader should see where a link points. */
    const inline = (t) => esc(t)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\*)/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, "$1 <code>$2</code>");
    const wrap = (raw, html) => (set.has(raw.trim()) ? `<mark>${html}</mark>` : html);
    const out = []; let list = null; let fence = false;
    const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
    for (const line of String(src).split("\n")) {
      let m;
      if (/^```/.test(line)) { close(); out.push(fence ? "</pre>" : "<pre>"); fence = !fence; }
      else if (fence) out.push(esc(line) + "\n");
      else if ((m = line.match(/^#{1,3}\s+(.*)/))) { close(); out.push(`<h2>${inline(m[1])}</h2>`); }
      else if ((m = line.match(/^\d+\.\s+(.*)/))) { if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; } out.push(`<li>${wrap(line, inline(m[1]))}</li>`); }
      else if ((m = line.match(/^[-*]\s+(.*)/))) { if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; } out.push(`<li>${wrap(line, inline(m[1]))}</li>`); }
      else if ((m = line.match(/^>\s?(.*)/))) { close(); out.push(`<blockquote>${wrap(line, inline(m[1]))}</blockquote>`); }
      else if (line.trim()) { close(); out.push(`<p>${wrap(line, inline(line))}</p>`); }
      else close();
    }
    close();
    if (fence) out.push("</pre>");
    return out.join("");
  }

  const ACRONYMS = { sql: "SQL", api: "API", pr: "PR", k8s: "K8s", a11y: "Accessibility", ui: "UI", ux: "UX", css: "CSS", ci: "CI", cd: "CD", aws: "AWS" };
  const titleCase = (n) => String(n).split("-").map((w, i) => ACRONYMS[w.toLowerCase()] || (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w)).join(" ");

  window.SkillsV2Model = Object.freeze({
    esc, plural, join, words, titleCase, shortPath, build, STATUS, BROKEN_WHY,
    diffLines, changes, plainLine, renderDoc, stripFrontmatter,
  });
})();
