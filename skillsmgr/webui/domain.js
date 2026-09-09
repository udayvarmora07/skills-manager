/* Skills Manager frontend domain utilities (no build step). */
"use strict";

(function () {
/* Keep transport, formatting, parsing, and safe rendering independent from the
 * Vue application. The app consumes this small browser-global interface so the
 * same policy can be exercised without mounting the full UI. */
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
  esc,
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
