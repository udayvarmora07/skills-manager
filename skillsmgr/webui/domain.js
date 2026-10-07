/* Skills Manager frontend domain utilities (no build step). */
"use strict";

(function () {
/* Keep transport, formatting, parsing, and safe rendering independent from the
 * Vue application. The app consumes this small browser-global interface so the
 * same policy can be exercised without mounting the full UI. */
/* Identical in-flight reads fan in to one request, the same policy the backend
 * already applies to concurrent identical reads. Only *in-flight* work is
 * shared: a completed response is never cached, so the filesystem stays the
 * source of truth and a later read always re-reads it. */
const IN_FLIGHT_READS = new Map();

async function api(url, opts = {}) {
  if (opts.method && opts.method !== "GET") return requestJson(url, opts);
  const inFlight = IN_FLIGHT_READS.get(url);
  if (inFlight) return inFlight;
  const pending = requestJson(url, opts).finally(() => IN_FLIGHT_READS.delete(url));
  IN_FLIGHT_READS.set(url, pending);
  return pending;
}

async function requestJson(url, opts = {}) {
  const res = await fetch(url, opts);
  let data = null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) data = await res.json();
  if (!res.ok) throw new Error((data && data.error) || "HTTP " + res.status);
  return data;
}

/* Non-JSON transfers still belong to this seam: the app must not re-implement
 * error handling or transport inline. These keep the same "throw the server's
 * own error message" contract as api() above. */
async function apiText(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.text();
}

async function apiBlob(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error("HTTP " + res.status);
  return { blob: await res.blob(), filename: filenameFromResponse(res) };
}

function filenameFromResponse(res) {
  const disposition = (res.headers && res.headers.get && res.headers.get("Content-Disposition")) || "";
  const match = /filename="?([^";]+)"?/.exec(disposition);
  return match ? match[1] : "";
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function localizedNumber(value, locale, options = {}) {
  try {
    return new Intl.NumberFormat(locale || undefined, options).format(value);
  } catch (e) {
    return String(value);
  }
}

function formatBytes(n, locale) {
  if (n === null || n === undefined) return "—";
  if (n < 1024) return localizedNumber(n, locale) + " B";
  const units = ["KB", "MB", "GB"];
  let v = n, i = -1;
  do { v /= 1024; i++; } while (v >= 1024 && i < units.length - 1);
  const fractionDigits = v >= 100 ? 0 : 1;
  return localizedNumber(Number(v.toFixed(fractionDigits)), locale, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }) + " " + units[i];
}

function formatTokens(n, locale) {
  if (n == null) return "—";
  if (n >= 1_000_000) {
    return localizedNumber(Number((n / 1_000_000).toFixed(1)), locale, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }) + "M";
  }
  if (n >= 1000) {
    return localizedNumber(Number((n / 1000).toFixed(1)), locale, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }) + "k";
  }
  return localizedNumber(n, locale);
}

function tokenPctClass(pct) {
  if (pct >= 80) return "pct-bad";
  if (pct >= 50) return "pct-warn";
  return "pct-ok";
}

function tokenBarWidth(pct) {
  return Math.max(2, Math.min(100, pct)).toFixed(1) + "%";
}

/* The API gives us observations, not a resolver. Keep the vocabulary here so
 * the Library can name the consumer/workspace and the state it actually saw
 * without implying precedence, deployment, or a desired state. */
const OBSERVED_STATE_LABELS = Object.freeze({
  active: "Active",
  disabled: "Disabled",
  invalid: "Invalid",
  malformed: "Malformed",
  linked: "Linked outside root",
  unaddressable: "Unaddressable",
  divergent: "Divergent",
});

/* One reader for the several shapes the API uses for the same observation:
 * a top-level flag (`malformed`, `decode_error`, `addressable`, `disabled`) and
 * the backend's `instance_states` vocabulary. Every surface that decides what
 * state a record is in must go through here, so a state added to the vocabulary
 * cannot appear in one surface and be missing from another. */
/* The backend's precise reason for an unreadable document. It already carries
 * one; collapsing every reason into the single word "Malformed" throws it away.
 *
 * A symlinked skill directory whose target sits outside its managed root is the
 * common case: the tool deliberately refuses to follow it (SCOPE-2 in
 * loader.py, because `skills-mgr install` symlinks by default and a followed
 * link would let a write land outside the root). The document is not corrupt —
 * it is unreachable on purpose, and the reader's next step is completely
 * different from "repair the frontmatter". */
const LINK_ESCAPE_RE = /escapes managed root|outside the managed root/i;

function observeRecord(record) {
  const source = record || {};
  const raw = source.instance_states || source.states;
  const states = Array.isArray(raw) ? raw : [];
  const has = (key) => states.some((state) => String(state).toLowerCase() === key);
  const decodeError = String(source.decode_error || "");
  return {
    states,
    /* The backend reports an unreadable document as the `invalid` state; a
     * document that cannot be decoded is the same observation, so both fold
     * into one key here and `invalid` stays available as its own label. */
    invalid: has("invalid"),
    /* A refused symlink is still an unreadable document, so `malformedDocument`
     * stays true and every existing count and predicate keeps working. This is
     * a strictly finer reading of the same observation, not a new one. */
    malformedDocument: !!(source.malformed || source.decode_error) || has("invalid") || has("malformed"),
    linkEscape: LINK_ESCAPE_RE.test(decodeError),
    notAddressable: source.addressable === false || has("unaddressable"),
    isDisabled: !!source.disabled || has("disabled"),
  };
}

/* The single classification every state predicate reads. Order is
 * most-specific-first; `invalid` is reported separately from `malformed`
 * because Quality counts them separately. */
function observedStateFor(record) {
  const observed = observeRecord(record);
  if (observed.invalid) return "invalid";
  if (observed.linkEscape) return "linked";
  if (observed.malformedDocument) return "malformed";
  if (observed.notAddressable) return "unaddressable";
  if (observed.isDisabled) return "disabled";
  return "active";
}

/* The badges a Library row shows. The backend's `invalid` and a malformed or
 * undecodable document are one observation to a reader, so both render as
 * "Malformed" here; Quality keeps the finer distinction via observedStateFor.
 * A refused symlink gets its own badge because it has a different remedy. */
function observedStateKeys(record, options = {}) {
  const observed = observeRecord(record);
  const out = [];
  if (observed.linkEscape) out.push("linked");
  else if (observed.malformedDocument) out.push("malformed");
  if (observed.notAddressable) out.push("unaddressable");
  if (observed.isDisabled) out.push("disabled");
  if (!out.length) out.push("active");
  if (options.divergent && !out.includes("divergent")) out.push("divergent");
  return out;
}

function scopeDescriptorFor(record, scopes) {
  const scopeId = String((record && record.scope) || "");
  return (Array.isArray(scopes) ? scopes : []).find((scope) => String(scope && scope.id || "") === scopeId) || null;
}

function observedIdentity(record, scopes, options = {}) {
  const descriptor = scopeDescriptorFor(record, scopes);
  const scopeId = String((record && record.scope) || (descriptor && descriptor.id) || "");
  const scopeLabel = String((record && record.scope_label) || (descriptor && descriptor.label) || scopeId || "Unknown scope");
  const kind = String((record && record.kind) || (descriptor && descriptor.kind) || "unknown");
  const consumer = String((record && record.consumer) || (descriptor && descriptor.consumer) || "").trim();
  const consumerLabel = consumer || "Unknown consumer";
  const kindLabel = kind === "project" ? "workspace" : kind === "agent" ? "agent" : kind === "global" ? "" : kind;
  const identityLabel = !kindLabel || kindLabel === "unknown"
    ? scopeLabel
    : `${scopeLabel} ${kindLabel}`;
  const baseStates = observedStateKeys(record || {});
  if (options.divergent && !baseStates.includes("divergent")) baseStates.push("divergent");
  const stateLabels = baseStates.map((state) => OBSERVED_STATE_LABELS[state] || state);
  return {
    key: [scopeId || scopeLabel, consumerLabel, kind, baseStates.join(",")].join("|"),
    scope: scopeId,
    scopeLabel,
    kind,
    kindLabel,
    consumer: consumer || null,
    consumerLabel,
    identityLabel,
    label: `${identityLabel} · consumer: ${consumerLabel}`,
    /* The long form above is the accessible identity and the tooltip. It is
     * too wide to print on a row: "Claude Code agent · consumer: claude-code"
     * is ~44 characters, and a logical skill can have seven of them, so the
     * list pane wrapped to five or six lines per skill and stopped being
     * scannable. The visible form is the scope name; the full identity stays
     * in the title attribute and in the accessibility tree. */
    shortLabel: scopeLabel,
    stateKeys: baseStates,
    stateLabels,
    stateLabel: stateLabels.join(" · "),
    problem: baseStates.some((state) => state !== "active"),
  };
}

function deriveLogicalSkillIdentity(records, scopes, options = {}) {
  const source = Array.isArray(records) ? records.filter(Boolean) : [];
  const divergent = !!options.divergent;
  const byKey = new Map();
  for (const record of source) {
    const identity = observedIdentity(record, scopes, { divergent });
    const prior = byKey.get(identity.key);
    if (prior) {
      prior.count += 1;
      continue;
    }
    byKey.set(identity.key, { ...identity, count: 1 });
  }
  const identities = [...byKey.values()].sort((a, b) =>
    a.label.localeCompare(b.label) || a.stateLabel.localeCompare(b.stateLabel)
  );
  const stateKeys = [...new Set(identities.flatMap((item) => item.stateKeys))];
  return {
    identities,
    stateKeys,
    stateLabels: stateKeys.map((state) => OBSERVED_STATE_LABELS[state] || state),
  };
}

/* Derive the product's logical-library rows without creating a new source of
 * truth. The API supplies physical_path so aliases to one resolved document
 * collapse once, while different copies retain their own instance records. */
function groupLogicalSkills(records, scopes) {
  const groups = new Map();
  for (const record of (Array.isArray(records) ? records : [])) {
    const name = String(record.name || "");
    if (!name) continue;
    if (!groups.has(name)) groups.set(name, { name, instances: [], records: [], _seen: new Set() });
    const group = groups.get(name);
    /* Keep every API observation for identity display, including aliases that
     * intentionally collapse to one physical instance below. */
    group.records.push(record);
    const identity = String(record.physical_path || record.path || `${record.scope || ""}/${name}`);
    if (group._seen.has(identity)) continue;
    group._seen.add(identity);
    group.instances.push(record);
  }
  return [...groups.values()].map((group) => {
    const instances = group.instances.slice().sort((a, b) =>
      String(a.scope_label || a.scope || "").localeCompare(String(b.scope_label || b.scope || ""))
    );
    const states = new Set();
    const hashes = new Set();
    const scopeLabels = [];
    const badges = [];
    for (const instance of group.records) {
      for (const state of observedStateKeys(instance)) states.add(state);
      const explicit = Array.isArray(instance.instance_states) ? instance.instance_states : [];
      if (explicit.includes("divergent")) states.add("divergent");
      if (instance.content_hash) hashes.add(String(instance.content_hash));
      const scope = String(instance.scope_label || instance.scope || "");
      if (scope && !scopeLabels.includes(scope)) scopeLabels.push(scope);
    }
    for (const instance of instances) {
      const scope = String(instance.scope_label || instance.scope || "");
      if (scope && !badges.includes(scope)) badges.push(scope);
    }
    const divergent = hashes.size > 1 || states.has("divergent");
    if (divergent) states.add("divergent");
    const identity = deriveLogicalSkillIdentity(group.records, scopes, { divergent });
    return {
      name: group.name,
      description: instances.find((item) => item.description)?.description || "",
      category: instances.find((item) => item.category)?.category || "",
      instances,
      instanceCount: instances.length,
      scopes: scopeLabels,
      badges,
      states: [...states],
      stateLabels: [...states].map((state) => OBSERVED_STATE_LABELS[state] || state),
      identities: identity.identities,
      divergent,
      identical: instances.length > 1 && !divergent,
      primary: instances[0] || null,
    };
  }).sort((a, b) => a.name.localeCompare(b.name));
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
  const lines = String(md).replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  let i = 0, inList = null, inCode = false, codeBuf = [], inTable = false;

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
    if (/^```/.test(line.trim())) { inCode = true; i++; continue; }

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
    closeList(); closeTable(); out.push("<p>" + inlineMd(line) + "</p>");
    i++;
  }

  closeList(); closeTable();
  if (inCode) out.push('<pre><code>' + esc(codeBuf.join("\n")) + "</code></pre>");
  let html = out.join("\n");
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
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object") return Object.entries(v).map(([k, val]) => `${k} ${val}`).join(", ");
  return String(v);
}

function formatTools(v) {
  if (!v) return "";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

window.SkillManagerDomain = Object.freeze({
  api,
  apiText,
  apiBlob,
  OBSERVED_STATE_LABELS,
  observeRecord,
  observedStateFor,
  observedStateKeys,
  groupLogicalSkills,
  deriveLogicalSkillIdentity,
  observedIdentity,
  formatBytes,
  formatTokens,
  tokenPctClass,
  tokenBarWidth,
  renderMarkdown,
  parseFrontmatter,
  formatCompat,
  formatTools,
});
}());
