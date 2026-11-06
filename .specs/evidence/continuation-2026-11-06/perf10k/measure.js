const { chromium } = require('$HOME/node_modules/playwright');
const { execSync } = require('child_process');
const fs = require('fs');
const [,, SIZE, PORT, OUT, REPS = '3', ONLY = ''] = process.argv;
const BASE = `http://127.0.0.1:${PORT}`;

const INIT = `
(() => {
  window.__lt = [];
  try { new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push([e.startTime, e.duration]); }).observe({type:'longtask', buffered:true}); } catch(e){}
  // heartbeat: largest gap between 50ms timer ticks = longest main-thread stall
  window.__hb = {last: performance.now(), max: 0};
  setInterval(() => { const n = performance.now(); const g = n - window.__hb.last - 50; if (g > window.__hb.max) window.__hb.max = g; window.__hb.last = n; }, 50);
  window.__il = [];
  document.addEventListener('input', e => { const t0 = e.timeStamp; requestAnimationFrame(() => requestAnimationFrame(() => window.__il.push(performance.now() - t0))); }, true);
  window.__errs = [];
  addEventListener('error', e => window.__errs.push('error: ' + e.message));
  addEventListener('unhandledrejection', e => window.__errs.push('rejection: ' + e.reason));
  // time an action until a UI signature changes and settles
  window.__time = (actionSrc, sigSrc, timeout, quiet) => new Promise(res => {
    const action = new Function('return (' + actionSrc + ')')();
    const sig = new Function('return (' + sigSrc + ')')();
    const pre = sig(); let first = null, last = null, cur = pre, pending = false;
    const t0 = performance.now();
    const check = () => { pending = false; const s = sig(); if (s !== cur) { cur = s; const t = performance.now(); if (first === null) first = t - t0; last = t - t0; } };
    const mo = new MutationObserver(() => { if (!pending) { pending = true; requestAnimationFrame(() => requestAnimationFrame(check)); } });
    mo.observe(document.body, {subtree:true, childList:true, characterData:true, attributes:true});
    action();
    const tick = () => {
      const now = performance.now() - t0;
      if ((last !== null && now - last > quiet) || now > timeout) { mo.disconnect(); res({first, last, changed: last !== null, timedOut: last === null || now > timeout}); }
      else setTimeout(tick, 50);
    };
    setTimeout(tick, 50);
  });
})();`;

const V2 = {
  home:  { url: '/v2/#/home',  ready: `(() => { const h=document.querySelector('h1#h1'); return h && h.textContent.trim()==='Your agents' && !!document.querySelector('.room'); })()` },
  skills:{ url: '/v2/#/skills',ready: `(() => { const h=document.querySelector('h1#h1'); return h && h.textContent.trim()==='Skills' && !!document.querySelector('a.sk'); })()` },
  skill: { url: '/v2/#/skill/@NAME', ready: `(() => !!document.querySelector('h1#h1.doc-title') && !!document.querySelector('.use'))()` },
  map:   { url: '/v2/#/map',   ready: `(() => { const h=document.querySelector('h1#h1'); return h && h.textContent.trim()==='Sync map' && !!document.querySelector('.mrow'); })()` },
  inbox: { url: '/v2/#/inbox', ready: `(() => { const h=document.querySelector('h1#h1'); return h && h.textContent.trim()==='Next up' && !!document.querySelector('.card.focus'); })()` },
};
const V2_SIG = `() => { const c=document.querySelector('.count'); return (c?c.textContent:'')+'|'+document.querySelectorAll('a.sk').length+'|'+((document.querySelector('a.sk')||{}).href||''); }`;
const CL_SIG = `() => { const l=document.querySelectorAll('li[data-skill-key]'); return l.length+'|'+(l[0]?l[0].dataset.skillKey:''); }`;
const SETQ = (sel, v) => `() => { const i=document.querySelector(${JSON.stringify(sel)}); i.focus(); const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; set.call(i, ${JSON.stringify(v)}); i.dispatchEvent(new Event('input',{bubbles:true})); }`;

function rssTree(pid) {
  try {
    const rows = execSync('ps -eo pid=,ppid=').toString().trim().split('\n').map(l => l.trim().split(/\s+/).map(Number));
    const kids = new Map(); for (const [p, pp] of rows) { (kids.get(pp) || kids.set(pp, []).get(pp)).push(p); }
    let sum = 0;
    const walk = (p) => { try { const t = fs.readFileSync('/proc/' + p + '/smaps_rollup', 'utf8').match(/Pss:\s+(\d+)/); if (t) sum += +t[1]; } catch (e) {} for (const c of (kids.get(p) || [])) walk(c); };
    walk(pid); return Math.round(sum / 1024);
  } catch (e) { return null; }
}

async function run(ui, screen, name, rep) {
  const rec = { size: +SIZE, ui, screen, rep, ok: false };
  const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', headless: true, chromiumSandbox: true, args: ['--disable-dev-shm-usage'] });
  const bpid = process.pid;
  try {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await ctx.addInitScript(INIT);
    const page = await ctx.newPage();
    const consoleErrs = []; const failed = [];
    page.on('console', m => { if (m.type() === 'error') consoleErrs.push(m.text().slice(0, 200)); });
    page.on('pageerror', e => consoleErrs.push('pageerror: ' + String(e).slice(0, 200)));
    page.on('requestfailed', r => failed.push(r.url().slice(0, 120) + ' ' + (r.failure() || {}).errorText));
    page.on('crash', () => { rec.crashed = true; });
    const cdp = await ctx.newCDPSession(page);
    await cdp.send('Performance.enable');
    let url, ready;
    if (ui === 'v2') { url = V2[screen].url.replace('@NAME', encodeURIComponent(name)); ready = V2[screen].ready; }
    else { url = '/'; ready = `(() => !!document.querySelector('#overview-title') && !document.querySelector('.skeleton'))()`; }
    await page.goto(BASE + url, { waitUntil: 'commit', timeout: 60000 });
    let t;
    try {
      const h = await page.waitForFunction(ready + ' && performance.now()', null, { polling: 'raf', timeout: 90000 });
      t = await h.jsonValue(); rec.ready_ms = Math.round(t);
    } catch (e) { rec.ready_ms = null; rec.ready_error = String(e).split('\n')[0]; }
    let libMs = null;
    if (ui === 'classic') {
      rec.landing_ms = rec.ready_ms;
      if (rec.ready_ms != null) {
        const r = await page.evaluate(async () => {
          const btn = [...document.querySelectorAll('nav button')].find(b => /Library|Skills/.test(b.textContent));
          const t0 = performance.now(); btn.click();
          return await new Promise(res => {
            const tick = () => { const li = document.querySelector('li[data-skill-key]'); if (li && li.offsetParent !== null) res(performance.now()); else requestAnimationFrame(tick); };
            tick(); setTimeout(() => res(null), 90000);
          }).then(t1 => ({ t0, t1, abs: t1 }));
        });
        rec.library_switch_ms = r.t1 == null ? null : Math.round(r.t1 - r.t0);
        rec.ready_ms = r.t1 == null ? null : Math.round(r.abs); // absolute time since navigation start incl. landing
        rec.ready_note = 'classic ready_ms = navigationStart -> first library row visible (landing + click)';
      }
    }
    await page.waitForTimeout(2000);
    const info = await page.evaluate(() => {
      const res = performance.getEntriesByType('resource');
      const sk = res.find(r => /\/api\/skills\?scope=all/.test(r.name));
      const sum = (f) => res.reduce((a, r) => a + (r[f] || 0), 0);
      return {
        api_skills_ms: sk ? Math.round(sk.duration) : null, api_skills_bytes: sk ? sk.encodedBodySize : null,
        api_skills_ttfb_ms: sk ? Math.round(sk.responseStart - sk.startTime) : null,
        requests: res.length, transfer_bytes: sum('transferSize'),
        dom_nodes: document.getElementsByTagName('*').length,
        heap_pre_gc_mb: performance.memory ? +(performance.memory.usedJSHeapSize / 1048576).toFixed(1) : null,
        longtasks: window.__lt, hb_max: Math.round(window.__hb.max), errs: window.__errs,
      };
    });
    await cdp.send('HeapProfiler.enable'); await cdp.send('HeapProfiler.collectGarbage');
    const mets = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(m => [m.name, m.value]));
    const lt = info.longtasks;
    Object.assign(rec, {
      api_skills_ms: info.api_skills_ms, api_skills_bytes: info.api_skills_bytes, api_skills_ttfb_ms: info.api_skills_ttfb_ms,
      requests: info.requests, transfer_mb: +(info.transfer_bytes / 1048576).toFixed(1),
      dom_nodes: info.dom_nodes, cdp_nodes: mets.Nodes, heap_mb: +(mets.JSHeapUsedSize / 1048576).toFixed(1), heap_pre_gc_mb: info.heap_pre_gc_mb,
      heap_total_mb: +(mets.JSHeapTotalSize / 1048576).toFixed(1),
      longtask_n: lt.length, longtask_total_ms: Math.round(lt.reduce((a, x) => a + x[1], 0)), longtask_max_ms: Math.round(lt.reduce((a, x) => Math.max(a, x[1]), 0)),
      stall_max_ms: info.hb_max, tree_pss_mb: rssTree(bpid),
      script_ms: Math.round((mets.ScriptDuration || 0) * 1000), layout_ms: Math.round((mets.LayoutDuration || 0) * 1000), style_ms: Math.round((mets.RecalcStyleDuration || 0) * 1000),
    });
    // interactions
    const inter = {};
    if ((ui === 'v2' && screen === 'skills') || (ui === 'classic' && rec.ready_ms != null)) {
      const sel = ui === 'v2' ? '#q' : 'input[name=skill-search]';
      const sig = ui === 'v2' ? V2_SIG : CL_SIG;
      const T = (act, to = 20000) => page.evaluate(([a, s, to]) => window.__time(a, s, to, 400), [act, sig, to]);
      inter.search_single_event = await T(SETQ(sel, 'audit'));
      inter.search_clear = await T(SETQ(sel, ''));
      await page.waitForTimeout(500);
      await page.evaluate(() => { window.__il = []; });
      await page.focus(sel);
      await page.keyboard.type('audit', { delay: 150 });
      await page.waitForTimeout(1500);
      const il = await page.evaluate(() => window.__il.map(x => Math.round(x)));
      inter.typing_input_to_paint_ms = il;
      inter.search_clear2 = await T(SETQ(sel, ''));
      if (ui === 'v2') {
        inter.filter_on = await T(`() => { const b=document.querySelectorAll('.seg button'); b[b.length>1?1:0].click(); }`);
        inter.filter_off = await T(`() => { document.querySelectorAll('.seg button')[0].click(); }`);
      } else {
        inter.filter_on = await T(`() => { [...document.querySelectorAll('button.chip')].find(b=>b.textContent.trim()==='Disabled').click(); }`);
        inter.filter_off = await T(`() => { [...document.querySelectorAll('button.chip')].find(b=>b.textContent.trim()==='All').click(); }`);
      }
      const after = await page.evaluate(() => ({ lt: window.__lt.length, hb: Math.round(window.__hb.max), lmax: window.__lt.reduce((a, x) => Math.max(a, x[1]), 0) }));
      inter.after = after;
    }
    rec.interaction = inter;
    rec.console_errors = consoleErrs.slice(0, 5); rec.console_error_n = consoleErrs.length + info.errs.length; rec.failed_requests = failed.slice(0, 3);
    rec.ok = true;
  } catch (e) {
    rec.error = String(e).split('\n').slice(0, 2).join(' | ');
  } finally {
    try { await browser.close(); } catch (e) {}
  }
  return rec;
}

(async () => {
  // choose a skill with the most differing copies for the detail screen
  const recs = await (await fetch(BASE + '/api/skills?scope=all')).json();
  const by = new Map();
  for (const r of recs) { if (r.malformed) continue; (by.get(r.name) || by.set(r.name, []).get(r.name)).push(r); }
  let best = null, bestScore = -1;
  for (const [n, a] of [...by].sort()) { const h = new Set(a.map(x => x.content_hash)); const sc = a.length * 10 + (h.size > 1 ? 5 : 0); if (sc > bestScore) { best = n; bestScore = sc; } }
  const detail = { name: best, copies: by.get(best).length, distinct: new Set(by.get(best).map(x => x.content_hash)).size };
  fs.appendFileSync(OUT, JSON.stringify({ meta: true, size: +SIZE, detail, instances: recs.length }) + '\n');
  const plan = [['v2', 'home'], ['v2', 'skills'], ['v2', 'skill'], ['v2', 'map'], ['v2', 'inbox'], ['classic', 'library']];
  for (const [ui, screen] of plan) {
    if (ONLY && !(ui + ':' + screen).includes(ONLY)) continue;
    for (let rep = 1; rep <= +REPS; rep++) {
      const r = await run(ui, screen, best, rep);
      fs.appendFileSync(OUT, JSON.stringify(r) + '\n');
      console.log(SIZE, ui, screen, rep, r.ok, r.ready_ms, r.error || '');
    }
  }
})();
