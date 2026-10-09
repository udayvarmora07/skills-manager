#!/usr/bin/env python3
"""Screen bodies for the Instrument prototype. Imported by build.py."""

from build import btn, IC_GEAR, IC_PLUS, IC_CHART

# ── 02 LIBRARY ──────────────────────────────────────────────────────────────

_LIBRARY_ROWS = """
        <button class="row" aria-selected="true">
          <span class="row-rail"></span>
          <span class="row-main">
            <span class="row-title"><span class="row-name">pdf-processing</span>
              <span class="mark warn"><i></i>divergent</span></span>
            <span class="row-sub">Extract, split and merge PDFs, fill forms, OCR scanned pages and redact.</span>
            <span class="ids">
              <span class="idchip bad">codex · 3.1k</span>
              <span class="idchip warn">opencode · 4.4k</span>
              <span class="idchip same">5 agree at 4.2k</span>
            </span>
          </span>
          <span class="row-meta"><span class="row-tok">4,208 tok</span><span class="mark mute"><i></i>7 copies</span></span>
        </button>

        <button class="row">
          <span class="row-rail" style="background:var(--mute)"></span>
          <span class="row-main">
            <span class="row-title"><span class="row-name">api-conventions</span>
              <span class="mark ok"><i></i>agreed</span></span>
            <span class="row-sub">House rules for REST endpoints: plural nouns, kebab-case URLs, uniform error envelopes.</span>
            <span class="ids">
              <span class="idchip ok">7 scopes · identical</span>
            </span>
          </span>
          <span class="row-meta"><span class="row-tok">2,140 tok</span></span>
        </button>

        <button class="row">
          <span class="row-rail" style="background:var(--bad)"></span>
          <span class="row-main">
            <span class="row-title"><span class="row-name">incident-postmortem</span>
              <span class="mark bad"><i></i>malformed</span></span>
            <span class="row-sub">Frontmatter has a duplicate <code class="mono">category</code> key, so it cannot be parsed.</span>
            <span class="ids">
              <span class="idchip bad">opencode · malformed</span>
              <span class="idchip same">absent from 6 roots</span>
            </span>
          </span>
          <span class="row-meta"><span class="row-tok">—</span></span>
        </button>

        <button class="row">
          <span class="row-rail" style="background:var(--mute)"></span>
          <span class="row-main">
            <span class="row-title"><span class="row-name">design-tokens</span>
              <span class="mark mute"><i></i>disabled</span></span>
            <span class="row-sub">Colour, type and spacing scales. Disabled everywhere it is installed.</span>
            <span class="ids">
              <span class="idchip mute">disabled in 4 roots</span>
              <span class="idchip same">active in 3</span>
            </span>
          </span>
          <span class="row-meta"><span class="row-tok">6,930 tok</span></span>
        </button>

        <button class="row">
          <span class="row-rail" style="background:var(--signal)"></span>
          <span class="row-main">
            <span class="row-title"><span class="row-name">skills-manager-management</span>
              <span class="mark info"><i></i>linked</span></span>
            <span class="row-sub">How an agent drives this tool safely. Installed as a package-data copy.</span>
            <span class="ids">
              <span class="idchip bad">codex · linked out of root</span>
              <span class="idchip same">2 real copies</span>
            </span>
          </span>
          <span class="row-meta"><span class="row-tok">3,318 tok</span></span>
        </button>

        <button class="row">
          <span class="row-rail" style="background:var(--mute)"></span>
          <span class="row-main">
            <span class="row-title"><span class="row-name">graphql-schema-review</span></span>
            <span class="row-sub">Breaking-change detection for GraphQL schemas, with a migration plan per field.</span>
            <span class="ids"><span class="idchip ok">1 root · single copy</span></span>
          </span>
          <span class="row-meta"><span class="row-tok">1,884 tok</span></span>
        </button>

        <button class="row">
          <span class="row-rail" style="background:var(--mute)"></span>
          <span class="row-main">
            <span class="row-title"><span class="row-name">secure-review-skill</span></span>
            <span class="row-sub">Adversarial review of AI-generated code for hardcoded secrets and injection sinks.</span>
            <span class="ids"><span class="idchip warn">registry · 55 days old</span></span>
          </span>
          <span class="row-meta"><span class="row-tok">9,120 tok</span></span>
        </button>

        <button class="row">
          <span class="row-rail" style="background:var(--mute)"></span>
          <span class="row-main">
            <span class="row-title"><span class="row-name">web-perf-budget</span></span>
            <span class="row-sub">Core Web Vitals budgets per route, enforced in CI.</span>
            <span class="ids"><span class="idchip ok">2 roots · identical</span></span>
          </span>
          <span class="row-meta"><span class="row-tok">3,010 tok</span></span>
        </button>
"""

LIBRARY = """
    <div class="lib">
      <section class="lib-list">
        <div class="filterbar">
          <div class="filter-row">
            <div class="seg">
              <button aria-pressed="true">All</button>
              <button aria-pressed="false">Active</button>
              <button aria-pressed="false">Attention</button>
            </div>
            <span class="filter-spacer"></span>
            <span class="count">638 of 638</span>
          </div>
          <div class="filter-row">
            <select class="select" style="height:28px;font-size:12px;width:auto;flex:0 1 auto">
              <option>All 7 roots</option><option>Opencode</option>
              <option>Codex</option><option>Claude Code</option>
            </select>
            <div class="seg ml-auto">
              <button aria-pressed="true">Logical</button>
              <button aria-pressed="false">1,163 copies</button>
            </div>
          </div>
        </div>
        <div class="rows">
__ROWS__
        </div>
      </section>

      <section class="detail">
        <div class="detail-inner">
          <div class="detail-head">
            <div class="micro">Codex · ~/.codex/skills/pdf-processing</div>
            <h1>pdf-processing</h1>
            <p class="detail-desc">Extract, split and merge PDFs, fill forms, OCR scanned pages and redact.</p>
            <div class="row-flex gap-3" style="margin-top:14px">
              <span class="mark warn"><i></i>divergent</span>
              <span class="mark mute"><i></i>7 copies</span>
              <span class="mark info"><i></i>registry-sourced</span>
              <span class="mark ok"><i></i>valid</span>
            </div>
          </div>

          <div class="dl">
            <dt>Token estimate</dt><dd>4,208 · 0.42% of a Claude 1M window</dd>
            <dt>Last observed</dt><dd>2026-10-08T09:42:11Z</dd>
            <dt>Content hash</dt><dd>a91f4c02e8b7…</dd>
            <dt>Installed from</dt><dd>github.com/vercel-labs/agent-skills</dd>
            <dt>Licence</dt><dd>MIT</dd>
            <dt>Version</dt><dd>1.4.0</dd>
          </div>

          <div class="callout" style="margin-top:var(--s7)">
            <i></i>
            <div class="in">
              <h4>This exact copy is not the one your Codex loads first</h4>
              <p>Seven copies exist and three carry different content. Precedence is a
                 per-consumer question, so the tool will not elect a winner for you —
                 <code>doctor --explain codex</code> reports the documented no-merge policy instead.</p>
            </div>
          </div>

          <div class="row-flex" style="margin-top:var(--s7);margin-bottom:var(--s4)">
            <h2 class="h-head">All observed copies</h2>
            <span class="micro ml-auto">3 of 7 disagree</span>
          </div>
          <table class="tbl">
            <thead><tr><th>Scope</th><th>State</th><th class="n">Tokens</th><th>Path</th></tr></thead>
            <tbody>
              <tr><td><b>Codex</b></td><td><span class="mark bad"><i></i>stale copy</span></td><td class="n">3,102</td><td class="mono">~/.codex/skills/pdf-processing</td></tr>
              <tr><td><b>Opencode</b></td><td><span class="mark warn"><i></i>drifted</span></td><td class="n">4,404</td><td class="mono">~/.config/opencode/skills/pdf-processing</td></tr>
              <tr><td><b>Gemini</b></td><td><span class="mark ok"><i></i>agreed</span></td><td class="n">4,208</td><td class="mono">~/.gemini/skills/pdf-processing</td></tr>
              <tr><td><b>Claude Code</b></td><td><span class="mark ok"><i></i>agreed</span></td><td class="n">4,208</td><td class="mono">~/.claude/skills/pdf-processing</td></tr>
              <tr><td><b>Agents</b></td><td><span class="mark ok"><i></i>agreed</span></td><td class="n">4,208</td><td class="mono">~/.agents/skills/pdf-processing</td></tr>
              <tr><td><b>Command Code</b></td><td><span class="mark mute"><i></i>disabled</span></td><td class="n">4,208</td><td class="mono">~/.commandcode/skills/pdf-processing</td></tr>
            </tbody>
          </table>

          <div class="row-flex gap-3" style="margin-top:var(--s7)">
            <button class="btn btn-primary">Update from folder</button>
            <button class="btn btn-secondary">Sync to all scopes</button>
            <button class="btn btn-ghost">Reveal path</button>
            <span class="ml-auto"></span>
            <button class="btn btn-danger">Remove</button>
          </div>
        </div>
      </section>
    </div>
"""

# ── 03 DOCUMENT READER ──────────────────────────────────────────────────────

DOCUMENT = """
    <div class="view">
      <div class="view-pad">
        <div class="stack stack-6" style="max-width:900px">

          <div class="row-flex gap-2" style="margin-bottom:var(--s2)">
            <button class="btn btn-ghost btn-sm">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
              Back to Library
            </button>
            <span class="micro ml-auto">Gemini · ~/.gemini/skills/pdf-processing/SKILL.md</span>
          </div>

          <div>
            <h1 class="h-display" style="font-family:var(--ff-mono);font-size:32px">pdf-processing</h1>
            <p class="lead" style="margin-top:10px;max-width:64ch">Extract, split and merge PDFs,
              fill forms, OCR scanned pages and redact.</p>
            <div class="row-flex gap-3" style="margin-top:16px">
              <span class="mark ok"><i></i>valid · no errors</span>
              <span class="mark info"><i></i>registry · vercel-labs/agent-skills</span>
              <span class="mark mute"><i></i>4,208 tokens</span>
            </div>
          </div>

          <div class="rule-top" style="margin-top:var(--s6)">
            <div class="row-flex" style="margin-bottom:var(--s5)">
              <div class="seg">
                <button aria-pressed="true">Document</button>
                <button aria-pressed="false">Frontmatter</button>
                <button aria-pressed="false">Files 4</button>
                <button aria-pressed="false">History</button>
              </div>
              <span class="ml-auto"></span>
              <button class="btn btn-secondary btn-sm">Open in editor</button>
              <button class="btn btn-secondary btn-sm">Copy raw</button>
            </div>

            <div class="sheet" style="padding:0;overflow:hidden">
              <div style="padding:var(--s6) var(--s7);border-bottom:1px solid var(--rule-soft)">
                <pre style="margin:0;font-family:var(--ff-mono);font-size:12px;line-height:1.75;color:var(--ink-2)"><span style="color:var(--ink-4)">---</span>
<span style="color:var(--signal)">name</span>: pdf-processing
<span style="color:var(--signal)">description</span>: Extract, split and merge PDFs, fill forms, OCR scanned pages and redact.
<span style="color:var(--signal)">license</span>: MIT
<span style="color:var(--signal)">version</span>: 1.4.0
<span style="color:var(--signal)">allowed-tools</span>: Read, Write, Bash
<span style="color:var(--ink-4)">---</span></pre>
              </div>
              <div class="prose" style="padding:var(--s6) var(--s7)">
                <h2 class="h-head" style="margin-bottom:10px">When to use this</h2>
                <p>Reach for this skill the moment a task mentions a <code class="mono">.pdf</code>,
                  a scanned document, or a form that has to be filled and returned. Do not
                  hand-roll a parser: <code class="mono">pdfplumber</code> and
                  <code class="mono">tesseract</code> cover the cases below and fail loudly
                  where a naive parser fails silently.</p>

                <h2 class="h-head" style="margin:26px 0 10px">Extract text</h2>
                <p>Prefer <code class="mono">pdfplumber</code> for anything with a text layer.
                  It preserves reading order, which matters for multi-column academic PDFs
                  where <code class="mono">pypdf</code> silently interleaves columns.</p>

                <div class="codeblock">
                  <pre><code><span class="kw">import</span> pdfplumber

with pdfplumber.open(<span style="color:var(--signal)">"report.pdf"</span>) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or <span style="color:var(--signal)">""</span>
        print(<span style="color:var(--signal)">f"--- page {i + 1} ---"</span>)
        print(text)</code></pre>
                </div>

                <h2 class="h-head" style="margin:26px 0 10px">OCR a scanned page</h2>
                <p>Only reach for OCR when there is no text layer at all. If a page returns
                  fewer than 40 characters it is almost certainly scanned, and a fast check
                  is cheaper than a bad extraction you have to notice later.</p>

                <h2 class="h-head" style="margin:26px 0 10px">Redaction</h2>
                <p>Redaction must remove content, not cover it. Drawing a filled rectangle
                  leaves the text in the file; the only reliable redaction is removing the
                  glyph run from the content stream. Verify afterwards by extracting the
                  text again and searching for the string you removed.</p>
              </div>
            </div>
          </div>

          <div class="callout">
            <i></i>
            <div class="in">
              <h4>Rendered, never injected</h4>
              <p>A <code class="mono">SKILL.md</code> body is attacker-authored text from an
                 archive or another tool. Every character above is escaped before it reaches
                 the DOM; the renderer emits no raw HTML at all, so a body containing
                 <code>&lt;script&gt;</code> is shown as text and never executed.</p>
            </div>
          </div>

        </div>
      </div>
    </div>
"""

# ── 04 QUALITY ──────────────────────────────────────────────────────────────

QUALITY = """
    <div class="view">
      <div class="view-pad">
        <div class="stack stack-6" style="max-width:1080px">

          <div>
            <h1 class="h-display">Quality</h1>
            <p class="lead" style="margin-top:8px;max-width:70ch">Independent observations for every
              copy on disk. These panels never collapse into a score, and they never infer safety,
              trust or effective load.</p>
          </div>

          <div class="callout">
            <i></i>
            <div class="in">
              <h4>Why there is no score</h4>
              <p>A composite number would average a document you cannot decode with one that is
                merely linked from outside its root, and then hide which of the two you should fix.
                Every panel below reports one thing and names the evidence for it.</p>
            </div>
          </div>

          <section>
            <div class="row-flex" style="margin-bottom:var(--s4)">
              <h2 class="h-title">Document validity</h2>
              <span class="mark bad ml-auto"><i></i>4 malformed</span>
            </div>
            <table class="tbl">
              <thead><tr><th>Skill</th><th>Scope</th><th>Finding</th><th>Remedy</th><th class="n">Files</th></tr></thead>
              <tbody>
                <tr><td class="mono">incident-postmortem</td><td>Opencode</td>
                    <td><span class="mark bad"><i></i>duplicate key</span> <span class="mono faint">category</span></td>
                    <td class="muted">Repair by hand — never rewritten automatically</td><td class="n">1</td></tr>
                <tr><td class="mono">legacy-deploy</td><td>Codex</td>
                    <td><span class="mark bad"><i></i>undecodable</span> <span class="faint">not UTF-8</span></td>
                    <td class="muted">Re-encode from source; the original bytes are untouched</td><td class="n">1</td></tr>
                <tr><td class="mono">batch-import-v2</td><td>Gemini</td>
                    <td><span class="mark bad"><i></i>no frontmatter</span></td>
                    <td class="muted">Add name and description, or delete the directory</td><td class="n">3</td></tr>
                <tr><td class="mono">Webhook-signing</td><td>Agents</td>
                    <td><span class="mark bad"><i></i>name mismatch</span> <span class="faint">dir ≠ frontmatter</span></td>
                    <td class="muted">Rename the directory or the field to match</td><td class="n">1</td></tr>
              </tbody>
            </table>
          </section>

          <section>
            <div class="row-flex" style="margin-bottom:var(--s4)">
              <h2 class="h-title">Duplication</h2>
              <span class="micro ml-auto">286 same-name groups · 41 byte-identical</span>
            </div>
            <div class="card">
              <div class="queue">
                <div class="queue-item">
                  <div class="queue-glyph info"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h10"/></svg></div>
                  <div class="queue-body">
                    <h3><span class="mono">pdf-processing</span> — 7 copies, 3 disagree</h3>
                    <p>Gemini, Claude Code, Agents and Command Code hold byte-identical content.
                       Codex is three versions behind; Opencode has drifted by 196 tokens.</p>
                    <span class="fig">spread <b>1,106 tok</b> · worst pair <b>opencode / codex</b></span>
                  </div>
                  <div class="queue-act"><button class="btn btn-secondary">Compare</button></div>
                </div>
                <div class="queue-item">
                  <div class="queue-glyph warn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 4v16M12 4l-8 8M12 4l8 8"/></svg></div>
                  <div class="queue-body">
                    <h3><span class="mono">api-conventions</span> — 7 copies, 1 disagree</h3>
                    <p>One Command Code copy predates the uniform-error-envelope rule and will
                       teach an agent the older convention.</p>
                    <span class="fig">spread <b>214 tok</b> · oldest <b>2026-06-02</b></span>
                  </div>
                  <div class="queue-act"><button class="btn btn-secondary">Compare</button></div>
                </div>
                <div class="queue-item">
                  <div class="queue-glyph mute"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg></div>
                  <div class="queue-body">
                    <h3>41 near-duplicate candidates</h3>
                    <p>Bounded inverted-index features with weighted Jaccard scores. A
                       heuristic, and it is labelled as one — similarity is not a claim.</p>
                    <span class="fig">threshold <b>0.82</b> · bounded at <b>200</b> candidates</span>
                  </div>
                  <div class="queue-act"><button class="btn btn-secondary">Review</button></div>
                </div>
              </div>
            </div>
          </section>

          <section>
            <div class="row-flex" style="margin-bottom:var(--s4)">
              <h2 class="h-title">Context hotspots</h2>
              <span class="micro ml-auto">Top 5 by token weight, all 1,163 copies</span>
            </div>
            <table class="tbl">
              <thead><tr><th>Skill</th><th>Scope</th><th class="n">Tokens</th><th class="n">% of window</th><th>Position</th></tr></thead>
              <tbody>
                <tr><td class="mono">secure-review-skill</td><td>Codex</td><td class="n">61,840</td><td class="n">6.2%</td>
                    <td style="width:34%"><div class="budget-track"><div class="budget-fill over" style="width:49%"></div></div></td></tr>
                <tr><td class="mono">full-repository-review</td><td>Opencode</td><td class="n">48,102</td><td class="n">4.8%</td>
                    <td><div class="budget-track"><div class="budget-fill over" style="width:38%"></div></div></td></tr>
                <tr><td class="mono">ui-ux-pro-max</td><td>Codex</td><td class="n">38,940</td><td class="n">3.9%</td>
                    <td><div class="budget-track"><div class="budget-fill over" style="width:31%"></div></div></td></tr>
                <tr><td class="mono">design-tokens</td><td>Claude Code</td><td class="n">6,930</td><td class="n">0.7%</td>
                    <td><div class="budget-track"><div class="budget-fill" style="width:5.5%"></div></div></td></tr>
                <tr><td class="mono">web-perf-budget</td><td>Opencode</td><td class="n">3,010</td><td class="n">0.3%</td>
                    <td><div class="budget-track"><div class="budget-fill" style="width:2.4%"></div></div></td></tr>
              </tbody>
            </table>
          </section>

          <section>
            <div class="row-flex" style="margin-bottom:var(--s4)">
              <h2 class="h-title">Signals this tool cannot observe</h2>
            </div>
            <div class="card" style="padding:var(--s6)">
              <div class="row-flex gap-3" style="flex-wrap:wrap">
                <span class="mark mute"><i></i>usage frequency</span>
                <span class="mark mute"><i></i>freshness against upstream</span>
                <span class="mark mute"><i></i>trust worthiness</span>
                <span class="mark mute"><i></i>usefulness</span>
                <span class="mark mute"><i></i>which copy a consumer loads</span>
              </div>
              <p class="small muted" style="margin-top:14px;max-width:74ch">Each of these would require
                observing an agent at inference time. This tool is a filesystem index, so it reports
                them as unavailable rather than guessing — and an unavailable signal is shown, not omitted.</p>
            </div>
          </section>

        </div>
      </div>
    </div>
"""

# ── 05 INSTALL ──────────────────────────────────────────────────────────────

INSTALL = """
    <div class="view">
      <div class="view-pad">
        <div class="stack stack-6" style="max-width:1040px">
          <div>
            <h1 class="h-display">Install</h1>
            <p class="lead" style="margin-top:8px;max-width:70ch">Fetch a snapshot from the
              skills.sh registry, read the validation and advisory risk evidence, then trust that
              exact review. Committing performs no second network request.</p>
          </div>

          <div class="card">
            <div class="card-head">
              <div class="grow">
                <h2>Search the registry</h2>
                <p>Public route · no token required</p>
              </div>
              <button class="btn btn-secondary">Curated</button>
            </div>
            <div class="card-body" style="padding:var(--s5) var(--s6)">
              <div class="search" style="padding-left:11px;height:38px">
                <span class="ph">owner/repo or owner/repo/slug, or plain text…</span>
              </div>
              <table class="tbl" style="margin-top:var(--s5)">
                <thead><tr><th>Skill</th><th>Source</th><th class="n">Downloads</th><th>Signal</th></tr></thead>
                <tbody>
                  <tr><td class="mono">frontend-design</td><td class="muted">anthropics/skills</td><td class="n">184k</td>
                      <td><span class="mark mute"><i></i>newest 2026-09-30</span></td></tr>
                  <tr><td class="mono">web-design-guidelines</td><td class="muted">vercel-labs/agent-skills</td><td class="n">92k</td>
                      <td><span class="mark ok"><i></i>already installed in 5 scopes</span></td></tr>
                  <tr><td class="mono">impeccable</td><td class="muted">pbakaus/impeccable</td><td class="n">61k</td>
                      <td><span class="mark warn"><i></i>advertories: 2</span></td></tr>
                  <tr><td class="mono">avoid-ai-design</td><td class="muted">funboy322/avoid-ai-design</td><td class="n">4.1k</td>
                      <td><span class="mark ok"><i></i>scan clean</span></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="card">
            <div class="card-head">
              <div class="grow">
                <h2>Pending review</h2>
                <p>One snapshot staged privately. Trust is explicit and the review id is single-use.</p>
              </div>
              <span class="mark warn"><i></i>expires in 23h 41m</span>
            </div>
            <div style="padding:var(--s6)">
              <div class="row-flex gap-4" style="align-items:flex-start">
                <div class="grow stack stack-4">
                  <div>
                    <div class="h-head" style="font-family:var(--ff-mono)">pbakaus/impeccable</div>
                    <div class="small muted" style="margin-top:3px">9 files · 4,102 tokens · 118 KB</div>
                  </div>
                  <div class="row-flex gap-2" style="flex-wrap:wrap">
                    <span class="mark ok"><i></i>valid · 0 errors</span>
                    <span class="mark warn"><i></i>3 advisory risk findings</span>
                    <span class="mark mute"><i></i>hash unverified from upstream</span>
                  </div>
                  <div class="sheet" style="margin:0;padding:var(--s5);max-width:none">
                    <div class="micro" style="margin-bottom:8px">Advisory risk findings — heuristic, not enforcement</div>
                    <ul class="stack stack-2 small muted">
                      <li><b class="mono" style="color:var(--warn)">scripts/install.mjs</b> — writes outside the skill directory</li>
                      <li><b class="mono" style="color:var(--warn)">references/hallmark.md</b> — instructs the agent to fetch a remote stylesheet</li>
                      <li><b class="mono" style="color:var(--warn)">SKILL.md</b> — instructs the agent to run <code class="mono">npx</code> without a pinned version</li>
                    </ul>
                  </div>
                  <p class="small muted">Integrity rests on this tool's own framed
                    <code class="mono">snapshot_hash</code>. The upstream <code class="mono">hash</code>
                    field is preserved as <code class="mono">upstream_hash</code> and never claimed as verified.</p>
                </div>
              </div>
              <div class="row-flex gap-3" style="margin-top:var(--s6);padding-top:var(--s5);border-top:1px solid var(--rule-soft)">
                <label class="check" style="flex:1">
                  <span class="box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg></span>
                  <span>I read the validation and the three risk findings. Trusting this review is my decision,
                    not a safety certification.</span>
                </label>
              </div>
              <div class="row-flex gap-3" style="margin-top:var(--s5)">
                <button class="btn btn-primary btn-lg">Trust and install into Global</button>
                <button class="btn btn-secondary btn-lg">Discard</button>
                <span class="ml-auto"></span>
                <span class="small faint mono">review 7c1f…a2</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
"""

# ── 06 RECOVERY ─────────────────────────────────────────────────────────────

RECOVERY = """
    <div class="view">
      <div class="view-pad">
        <div class="stack stack-6" style="max-width:1040px">
          <div>
            <h1 class="h-display">Recovery</h1>
            <p class="lead" style="margin-top:8px;max-width:70ch">Every write in this tool keeps a
              recovery path. Rollback is never instantaneous — it runs the same diff, validation and
              approval policy as the change that made it.</p>
          </div>

          <div class="callout">
            <i></i>
            <div class="in">
              <h4>A snapshot is not a restore button</h4>
              <p>Selecting a snapshot opens a normal update review against your live copy. You read
                 the diff and approve it, exactly as if you were applying an external change. There
                 is no path in this product that overwrites your files without showing you first.</p>
            </div>
          </div>

          <section>
            <div class="row-flex" style="margin-bottom:var(--s4)">
              <h2 class="h-title">Trash</h2>
              <span class="mark mute ml-auto"><i></i>12 items · global scope only</span>
            </div>
            <table class="tbl">
              <thead><tr><th>Name</th><th>Removed</th><th class="n">Tokens</th><th></th></tr></thead>
              <tbody>
                <tr><td class="mono">legacy-deploy</td><td class="muted">2026-09-28 14:02</td><td class="n">1,880</td>
                    <td class="n"><button class="btn btn-secondary btn-sm">Restore</button></td></tr>
                <tr><td class="mono">batch-import-v2</td><td class="muted">2026-09-24 09:41</td><td class="n">2,204</td>
                    <td class="n"><button class="btn btn-secondary btn-sm">Restore</button></td></tr>
                <tr><td class="mono">old-design-tokens</td><td class="muted">2026-09-11 17:20</td><td class="n">5,410</td>
                    <td class="n"><button class="btn btn-secondary btn-sm">Restore</button></td></tr>
              </tbody>
            </table>
          </section>

          <section>
            <div class="row-flex" style="margin-bottom:var(--s4)">
              <h2 class="h-title">Source snapshots</h2>
              <span class="micro ml-auto">newest five retained per exact target</span>
            </div>
            <table class="tbl">
              <thead><tr><th>Target</th><th>Taken</th><th>Tree hash</th><th>State</th><th></th></tr></thead>
              <tbody>
                <tr><td class="mono">pdf-processing · opencode</td><td class="muted">2026-10-06 08:14</td>
                    <td class="mono">3b81c0f9…</td>
                    <td><span class="mark ok"><i></i>active</span></td>
                    <td class="n"><button class="btn btn-secondary btn-sm">Review rollback</button></td></tr>
                <tr><td class="mono">pdf-processing · codex</td><td class="muted">2026-09-30 11:02</td>
                    <td class="mono">77ac41de…</td>
                    <td><span class="mark ok"><i></i>active</span></td>
                    <td class="n"><button class="btn btn-secondary btn-sm">Review rollback</button></td></tr>
                <tr><td class="mono">api-conventions · agents</td><td class="muted">2026-09-02 16:38</td>
                    <td class="mono">e10b77aa…</td>
                    <td><span class="mark mute"><i></i>no SKILL.md</span></td>
                    <td class="n"><button class="btn btn-secondary btn-sm">Review rollback</button></td></tr>
              </tbody>
            </table>
          </section>

          <section>
            <div class="row-flex" style="margin-bottom:var(--s4)">
              <h2 class="h-title">Archive transfer</h2>
            </div>
            <div class="card" style="padding:var(--s6)">
              <div class="row-flex gap-4" style="flex-wrap:wrap">
                <div class="grow" style="min-width:260px">
                  <h3 class="h-head" style="margin-bottom:5px">Export</h3>
                  <p class="small muted">A versioned manifest with a SHA-256 per skill tree. Archives
                     are staged in a temporary directory and removed after the download — nothing is
                     left in <code class="mono">backups/</code>.</p>
                  <div class="row-flex gap-2" style="margin-top:14px">
                    <button class="btn btn-secondary">Skills only</button>
                    <button class="btn btn-secondary">Full, with trash</button>
                  </div>
                </div>
                <div style="width:1px;background:var(--rule-soft)"></div>
                <div class="grow" style="min-width:260px">
                  <h3 class="h-head" style="margin-bottom:5px">Import</h3>
                  <p class="small muted">Tar or ZIP, sniffed by content rather than by filename.
                     Traversal, absolute paths, Windows separators and special members are rejected
                     <em>before</em> anything is written.</p>
                  <div class="row-flex gap-2" style="margin-top:14px">
                    <button class="btn btn-secondary">Choose archive</button>
                    <button class="btn btn-ghost">Paste from clipboard</button>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
"""

# ── 07 PROFILES ─────────────────────────────────────────────────────────────

PROFILES = """
    <div class="view">
      <div class="view-pad">
        <div class="stack stack-6" style="max-width:1040px">
          <div>
            <h1 class="h-display">Profiles</h1>
            <p class="lead" style="margin-top:8px;max-width:72ch">A profile is a desired set of
              existing skills and targets. Applying one enables the copies that are actually
              observed. It never installs a missing member, never reconciles divergent content,
              and never disables anything outside the profile.</p>
          </div>

          <section>
            <div class="row-flex" style="margin-bottom:var(--s4)">
              <h2 class="h-title">Backend service</h2>
              <span class="micro ml-auto">7 members · 3 targets</span>
            </div>
            <table class="tbl">
              <thead><tr><th>Skill</th><th>Observed instances</th><th>State</th></tr></thead>
              <tbody>
                <tr><td class="mono">api-conventions</td><td><span class="idchip ok">claude-code</span><span class="idchip ok">codex</span><span class="idchip ok">agents</span><span class="idchip ok">+4</span></td>
                    <td><span class="mark ok"><i></i>observed</span></td></tr>
                <tr><td class="mono">database-optimiser</td><td><span class="idchip ok">codex</span><span class="idchip ok">opencode</span></td>
                    <td><span class="mark ok"><i></i>observed</span></td></tr>
                <tr><td class="mono">postgres-schema-review</td><td><span class="idchip warn">claude-code · disabled</span></td>
                    <td><span class="mark warn"><i></i>disabled</span></td></tr>
                <tr><td class="mono">incident-postmortem</td><td><span class="idchip ok">gemini</span><span class="idchip bad">opencode · malformed</span></td>
                    <td><span class="mark bad"><i></i>divergent</span></td></tr>
                <tr><td class="mono">graphql-schema-review</td><td class="faint">none</td>
                    <td><span class="mark mute"><i></i>missing</span></td></tr>
              </tbody>
            </table>
          </section>

          <div class="card" style="padding:var(--s6)">
            <div class="row-flex gap-4">
              <div class="grow">
                <h3 class="h-head">Enable plan · Backend service</h3>
                <p class="small muted" style="margin-top:5px;max-width:70ch">Targets are re-resolved at
                  execution time against exact physical paths. A target that moved is refused rather
                  than applied to whatever now holds the name.</p>
              </div>
              <button class="btn btn-primary">Preview plan</button>
            </div>
            <div class="row-flex gap-3" style="margin-top:var(--s5);padding-top:var(--s5);border-top:1px solid var(--rule-soft)">
              <span class="mark ok"><i></i>2 disabled → active</span>
              <span class="mark mute"><i></i>6 no change</span>
              <span class="mark bad"><i></i>1 unresolved</span>
              <span class="mark mute"><i></i>partial failure keeps the rest</span>
            </div>
          </div>
        </div>
      </div>
    </div>
"""

# ── 08 WORKSPACES ───────────────────────────────────────────────────────────

WORKSPACES = """
    <div class="view">
      <div class="view-pad">
        <div class="stack stack-6" style="max-width:1040px">
          <div>
            <h1 class="h-display">Consumers &amp; projects</h1>
            <p class="lead" style="margin-top:8px;max-width:72ch">Which roots each coding agent
              reads, and what this project can observe about them. Read-only: nothing here is a
              binding, and nothing is persisted.</p>
          </div>

          <div class="callout">
            <i></i>
            <div class="in">
              <h4>An unknown order stays unknown</h4>
              <p>Two of these consumers document no same-name order at all. Rather than inventing a
                winner, the tool reports <code class="mono">undocumented-precedence</code> and shows
                you every copy. A guess that looks confident is worse than an admission.</p>
            </div>
          </div>

          <section>
            <div class="row-flex" style="margin-bottom:var(--s4)">
              <h2 class="h-title">Consumer roots</h2>
              <span class="micro ml-auto">observed · precedence cited from the published docs</span>
            </div>
            <table class="tbl">
              <thead><tr><th>Consumer</th><th>Roots read</th><th>Documented order</th><th>Winnable</th></tr></thead>
              <tbody>
                <tr><td><b>Claude Code</b></td><td class="muted">personal, project, enterprise</td><td class="muted">personal &gt; project</td><td><span class="mark ok"><i></i>yes</span></td></tr>
                <tr><td><b>Codex</b></td><td class="muted">project, personal, SYSTEM</td><td class="muted">no-merge — every copy loads</td><td><span class="mark mute"><i></i>no winner</span></td></tr>
                <tr><td><b>Command Code</b></td><td class="muted">six tiers</td><td class="muted">project .commandcode &gt; .agents &gt; user &gt; extras &gt; bundled</td><td><span class="mark ok"><i></i>yes</span></td></tr>
                <tr><td><b>Gemini</b></td><td class="muted">built-in, extension, user, workspace</td><td class="muted">built-in &lt; extension &lt; user &lt; workspace</td><td><span class="mark warn"><i></i>ties are ambiguous</span></td></tr>
                <tr><td><b>Cursor</b></td><td class="muted">one project root</td><td class="faint">not documented</td><td><span class="mark mute"><i></i>unknown</span></td></tr>
                <tr><td><b>Opencode</b></td><td class="muted">recursive config root</td><td class="faint">not documented</td><td><span class="mark mute"><i></i>unknown</span></td></tr>
              </tbody>
            </table>
          </section>

          <section>
            <div class="row-flex" style="margin-bottom:var(--s4)">
              <h2 class="h-title">This project</h2>
              <span class="mark ok ml-auto"><i></i>inside managed roots</span>
            </div>
            <div class="card" style="padding:var(--s6)">
              <div class="dl" style="margin-top:0">
                <dt>Project root</dt><dd>~/skills-manager</dd>
                <dt>Project scopes found</dt><dd>.claude/skills (9) · .codex/skills (3) · .commandcode/skills (1)</dd>
                <dt>Resolution for a name</dt><dd>personal &gt; project, reported per skill</dd>
                <dt>Effective state</dt><dd><span class="mark mute"><i></i>unresolved — approval-gated</span></dd>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
"""

# ── 09 SETTINGS ─────────────────────────────────────────────────────────────

SETTINGS = """
    <div class="view">
      <div class="view-pad">
        <div class="stack stack-6" style="max-width:760px">
          <div>
            <h1 class="h-display">Settings</h1>
            <p class="lead" style="margin-top:8px;max-width:64ch">These change how this window reads
              on this device. Nothing here changes an OS setting or touches another tool.</p>
          </div>

          <section class="card" style="padding:var(--s6)">
            <h2 class="h-title" style="margin-bottom:var(--s5)">Appearance</h2>
            <div class="stack stack-5">
              <div>
                <div class="field" style="margin-bottom:9px"><label>Theme</label></div>
                <div class="seg">
                  <button aria-pressed="false">System</button>
                  <button aria-pressed="true">Light</button>
                  <button aria-pressed="false">Dark</button>
                </div>
              </div>
              <div>
                <div class="field" style="margin-bottom:9px"><label>Text size</label></div>
                <div class="seg">
                  <button aria-pressed="true">Standard</button>
                  <button aria-pressed="false">Large</button>
                </div>
              </div>
              <div>
                <div class="field" style="margin-bottom:9px"><label>Regional format</label>
                  <span class="hint">Numbers and dates only. The interface stays English until translated resources exist.</span></div>
                <select class="select" style="max-width:280px"><option>System</option><option>en-US</option><option>en-GB</option><option>en-IN</option></select>
              </div>
            </div>
          </section>

          <section class="card" style="padding:var(--s6)">
            <h2 class="h-title" style="margin-bottom:var(--s3)">Reading</h2>
            <p class="small muted" style="margin-bottom:var(--s5);max-width:60ch">Default context
              window for every percentage in this tool.</p>
            <select class="select" style="max-width:280px">
              <option>Claude 1M — 1,000,000 tokens</option>
              <option>Claude Haiku — 200,000</option>
              <option>GPT-5.6 — 1,050,000</option>
              <option>GPT-5 — 400,000</option>
              <option>Gemini 2M — 2,000,000</option>
            </select>
          </section>

          <section class="card" style="padding:var(--s6)">
            <h2 class="h-title" style="margin-bottom:var(--s5)">Safety</h2>
            <div class="stack stack-5">
              <button class="switch" aria-pressed="true">
                <span class="track"><span class="knob"></span></span>
                <span>Refuse to follow a <span class="mono">SKILL.md</span> symlink out of its root</span>
              </button>
              <p class="small faint" style="margin-top:-8px;max-width:64ch">On. This is why 292 instances
                read as <em>linked</em> rather than <em>malformed</em>: the document is fine, the link
                is refused, and the fix is to copy the tree in.</p>
              <button class="switch" aria-pressed="true">
                <span class="track"><span class="knob"></span></span>
                <span>Bind the server to loopback only</span>
              </button>
              <p class="small faint" style="margin-top:-8px;max-width:64ch">On, and not configurable.
                There is no authentication, so the binding is the entire security boundary — every
                request validates its <span class="mono">Host</span>, including reads.</p>
            </div>
          </section>
        </div>
      </div>
    </div>
"""

# ── 10 TRASH ────────────────────────────────────────────────────────────────

TRASH = """
    <div class="view">
      <div class="view-pad">
        <div class="stack stack-6" style="max-width:900px">
          <div>
            <h1 class="h-display">Trash</h1>
            <p class="lead" style="margin-top:8px;max-width:66ch">Global scope only. Agent-scope
              trash lives in that scope's own directory and is not merged here.</p>
          </div>
          <div class="card">
            <div class="queue">
              <div class="queue-item">
                <div class="queue-glyph info"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg></div>
                <div class="queue-body">
                  <h3 class="mono" style="font-size:14px">legacy-deploy</h3>
                  <p>Removed 2026-09-28 · 3 files · 1,880 tokens</p>
                </div>
                <div class="queue-act row-flex gap-2">
                  <button class="btn btn-secondary">Restore</button>
                </div>
              </div>
              <div class="queue-item">
                <div class="queue-glyph info"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg></div>
                <div class="queue-body">
                  <h3 class="mono" style="font-size:14px">batch-import-v2</h3>
                  <p>Removed 2026-09-24 · 6 files · 2,204 tokens · malformed on disk</p>
                </div>
                <div class="queue-act row-flex gap-2">
                  <button class="btn btn-secondary">Restore</button>
                </div>
              </div>
            </div>
          </div>
          <div class="row-flex gap-3">
            <button class="btn btn-danger">Empty trash permanently</button>
            <span class="small faint">Purging is the one action with no undo and no snapshot.</span>
          </div>
        </div>
      </div>
    </div>
"""

# ── 11 COMMAND PALETTE ──────────────────────────────────────────────────────

PALETTE_OVERLAY = """
<div class="scrim">
  <div class="palette">
    <div class="palette-input">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input placeholder="Type a command, or search 638 skills…" value="pdf">
    </div>
    <div class="palette-list">
      <div class="palette-group">Skills</div>
      <button class="palette-item" aria-selected="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 5h16v14H4z"/></svg>
        <span class="txt"><b>pdf-processing</b> — open in Library</span>
        <span class="kbd">↵</span>
      </button>
      <button class="palette-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 5h16v14H4z"/></svg>
        <span class="txt"><b>pdf-report-generator</b> — open in Library</span>
      </button>
      <div class="palette-group">Actions on pdf-processing</div>
      <button class="palette-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v10m0 0l4-4m-4 4l-4-4M4 19h16"/></svg>
        <span class="txt">Sync to all 7 scopes</span>
      </button>
      <button class="palette-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 4v16m8-8H4"/></svg>
        <span class="txt">Update from folder — review required</span>
      </button>
      <button class="palette-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="8"/><path d="M6 12h12"/></svg>
        <span class="txt">Disable in every scope</span>
      </button>
      <div class="palette-group">Go to</div>
      <button class="palette-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3v18h18"/><path d="M7 15l4-5 3 3 5-7"/></svg>
        <span class="txt">Overview</span>
      </button>
      <button class="palette-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>
        <span class="txt">Recovery</span>
      </button>
    </div>
    <div class="palette-foot">
      <span><span class="kbd">↑</span> <span class="kbd">↓</span> navigate</span>
      <span><span class="kbd">↵</span> open</span>
      <span><span class="kbd">esc</span> dismiss</span>
      <span class="ml-auto">Every action in this tool is reachable from here</span>
    </div>
  </div>
</div>
"""

# ── 12 CREATE / EDIT DIALOG ─────────────────────────────────────────────────

CREATE_OVERLAY = """
<div class="scrim">
  <div class="dialog dialog-wide">
    <div class="dialog-head">
      <div class="grow">
        <h2>New skill</h2>
        <p>Written to the Global store. Agent-scope copies are made with <b>sync</b>, never by
           creating the same skill twice.</p>
      </div>
      <button class="btn btn-ghost btn-icon" aria-label="Close">✕</button>
    </div>
    <div class="dialog-body">
      <div class="form-grid">
        <div class="field">
          <label for="n">Name</label>
          <input class="input mono" id="n" value="pdf-report-generator">
          <span class="hint">Lowercase, digits and single hyphens · max 64 characters</span>
        </div>
        <div class="field">
          <label>Category</label>
          <input class="input" value="documents">
        </div>
        <div class="field span2">
          <label for="d">Description</label>
          <textarea class="textarea" id="d" rows="3">Turn a set of source documents into a paginated
brief with a table of contents, a citation per claim, and a one-line summary per section.</textarea>
          <span class="hint">The description is what an agent reads to decide whether to load the
skill, so it says <em>when to use it</em>, not what the skill is proud of.</span>
        </div>
        <div class="field">
          <label>Licence</label>
          <input class="input" value="MIT">
        </div>
        <div class="field">
          <label>Version</label>
          <input class="input mono" value="0.1.0">
        </div>
        <div class="field span2">
          <label>Allowed tools</label>
          <input class="input mono" value="Read, Write, Bash">
          <span class="hint">Comma separated. An agent may only use these while this skill is loaded.</span>
        </div>
        <div class="field span2">
          <label>Body</label>
          <textarea class="textarea mono" rows="7">## When to use this

Reach for this when the task is to turn N documents into one readable artefact.

## Steps

1. Read every source before writing anything.
2. Build the outline from headings, not from document order.
3. Cite the source path for every claim.</textarea>
        </div>
      </div>

      <div class="card" style="margin-top:var(--s6);box-shadow:none">
        <div class="card-head" style="padding:var(--s4) var(--s5)">
          <div class="grow"><h2>Validation</h2></div>
          <span class="mark ok"><i></i>0 errors</span>
        </div>
        <div style="padding:var(--s4) var(--s5)">
          <div class="row-flex gap-3" style="flex-wrap:wrap">
            <span class="mark ok"><i></i>name matches directory</span>
            <span class="mark ok"><i></i>description states a use case</span>
            <span class="mark ok"><i></i>31 lines, under the 500 limit</span>
            <span class="mark ok"><i></i>1,204 tokens estimated</span>
          </div>
        </div>
      </div>
    </div>
    <div class="dialog-foot">
      <span class="small faint">Validation runs before anything is written</span>
      <span class="spacer"></span>
      <button class="btn btn-secondary">Cancel</button>
      <button class="btn btn-primary">Create skill</button>
    </div>
  </div>
</div>
"""

# ── 13 UPDATE REVIEW + DIFF ─────────────────────────────────────────────────

REVIEW_OVERLAY = """
<div class="scrim">
  <div class="dialog dialog-wide" style="max-height:88vh">
    <div class="dialog-head">
      <div class="grow">
        <h2>Update <span class="mono" style="font-weight:500">pdf-processing</span></h2>
        <p>Opencode copy · <span class="mono">~/.config/opencode/skills/pdf-processing</span>. The
           candidate is staged privately and applied only if it is unchanged at commit time.</p>
      </div>
      <span class="mark info">review 7c1f…a2</span>
    </div>
    <div class="dialog-body">
      <div class="row-flex gap-3" style="margin-bottom:var(--s5);flex-wrap:wrap">
        <span class="mark ok"><i></i>valid · 0 errors</span>
        <span class="mark warn"><i></i>196 tokens added</span>
        <span class="mark mute"><i></i>1 file changed</span>
        <span class="mark mute"><i></i>line endings unchanged</span>
        <span class="mark ok"><i></i>stays active</span>
      </div>

      <div class="diff">
        <div class="diff-file">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="width:14px;height:14px"><path d="M4 5h16v14H4z"/></svg>
          <span class="mono">SKILL.md</span>
          <span class="stat"><span style="color:var(--ok)">+14</span> <span style="color:var(--bad)">−2</span></span>
        </div>
        <div class="diff-line"><span class="ln">38</span><span class="txt">## Extract text</span></div>
        <div class="diff-line del"><span class="ln">39</span><span class="txt">- Prefer pdfplumber for anything with a text layer.</span></div>
        <div class="diff-line add"><span class="ln">39</span><span class="txt">+ Prefer `pdfplumber` for anything with a text layer.</span></div>
        <div class="diff-line add"><span class="ln">40</span><span class="txt">+ It preserves reading order, which `pypdf` silently breaks on</span></div>
        <div class="diff-line add"><span class="ln">41</span><span class="txt">+ multi-column layouts — a failure you only notice downstream.</span></div>
        <div class="diff-line"><span class="ln">42</span><span class="txt"> </span></div>
        <div class="diff-line add"><span class="ln">43</span><span class="txt">+ ## OCR a scanned page</span></div>
        <div class="diff-line add"><span class="ln">44</span><span class="txt">+ </span></div>
        <div class="diff-line add"><span class="ln">45</span><span class="txt">+ Only OCR when there is no text layer. A page returning fewer than</span></div>
        <div class="diff-line add"><span class="ln">46</span><span class="txt">+ 40 characters is almost certainly scanned, and that check is far</span></div>
        <div class="diff-line add"><span class="ln">47</span><span class="txt">+ cheaper than a bad extraction discovered three steps later.</span></div>
        <div class="diff-line"><span class="ln">48</span><span class="txt"> </span></div>
        <div class="diff-line add"><span class="ln">49</span><span class="txt">+ ## Redaction</span></div>
        <div class="diff-line add"><span class="ln">50</span><span class="txt">+ </span></div>
        <div class="diff-line add"><span class="ln">51</span><span class="txt">+ Redaction must remove content, not cover it. Drawing a filled</span></div>
        <div class="diff-line add"><span class="ln">52</span><span class="txt">+ rectangle leaves the text in the file. Verify by extracting the text</span></div>
        <div class="diff-line add"><span class="ln">53</span><span class="txt">+ again and searching for the string you removed.</span></div>
      </div>

      <div class="callout" style="margin-top:var(--s6)">
        <i></i>
        <div class="in">
          <h4>What happens when you apply</h4>
          <p>A complete snapshot of the current tree is taken first, the candidate is re-checked
             against the hash you reviewed, and the target is replaced atomically. If the candidate
             moved in the meantime the apply is refused and nothing changes.</p>
        </div>
      </div>

      <label class="check" style="margin-top:var(--s6)">
        <span class="box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg></span>
        <span>I reviewed the target, the file changes, the validation result, and the snapshot policy.</span>
      </label>
    </div>
    <div class="dialog-foot">
      <span class="small faint">A snapshot is kept for rollback — it is never a blind restore</span>
      <span class="spacer"></span>
      <button class="btn btn-secondary">Cancel</button>
      <button class="btn btn-primary">Apply reviewed update</button>
    </div>
  </div>
</div>
"""

SCREENS = [
    dict(name="02-library.html", active="skills", tb_title="Library",
         tb_meta="638 logical skills · 1,163 physical copies",
         actions=[btn("Doctor", "secondary", IC_GEAR), btn("New skill", "primary", IC_PLUS)],
         body=LIBRARY.replace("__ROWS__", _LIBRARY_ROWS)),
    dict(name="03-document.html", active="skills", tb_title="pdf-processing",
         tb_meta="Gemini · 4,208 tokens",
         actions=[btn("Edit", "secondary"), btn("Sync", "secondary"), btn("Remove", "danger")],
         body=DOCUMENT),
    dict(name="04-quality.html", active="quality", tb_title="Quality",
         tb_meta="independent evidence, never a score",
         actions=[btn("Doctor", "secondary", IC_GEAR), btn("Stats", "secondary", IC_CHART)],
         body=QUALITY),
    dict(name="05-install.html", active="install", tb_title="Install",
         tb_meta="skills.sh · public routes, no token",
         actions=[btn("Refresh", "secondary")],
         body=INSTALL),
    dict(name="06-recovery.html", active="recovery", tb_title="Recovery",
         tb_meta="trash, snapshots, archives",
         actions=[btn("Export", "secondary"), btn("Import", "secondary")],
         body=RECOVERY),
    dict(name="07-profiles.html", active="profiles", tb_title="Profiles",
         tb_meta="desired sets of existing skills",
         actions=[btn("New profile", "primary", IC_PLUS)],
         body=PROFILES),
    dict(name="08-workspaces.html", active="workspaces", tb_title="Consumers &amp; projects",
         tb_meta="read-only evidence",
         actions=[btn("Refresh", "secondary")],
         body=WORKSPACES),
    dict(name="09-settings.html", active="", tb_title="Settings",
         tb_meta="this device only",
         actions=[], body=SETTINGS),
    dict(name="10-trash.html", active="", tb_title="Trash",
         tb_meta="12 items · global scope",
         actions=[btn("Empty trash", "danger")], body=TRASH),
    dict(name="11-palette.html", active="skills", tb_title="Library",
         tb_meta="638 logical skills", actions=[], body=LIBRARY.replace("__ROWS__", _LIBRARY_ROWS),
         overlay=PALETTE_OVERLAY),
    dict(name="12-create.html", active="skills", tb_title="Library",
         tb_meta="638 logical skills", actions=[], body=LIBRARY.replace("__ROWS__", _LIBRARY_ROWS),
         overlay=CREATE_OVERLAY),
    dict(name="13-review.html", active="skills", tb_title="Library",
         tb_meta="638 logical skills", actions=[], body=LIBRARY.replace("__ROWS__", _LIBRARY_ROWS),
         overlay=REVIEW_OVERLAY),
]