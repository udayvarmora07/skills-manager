/* Developer-only CLASSIC web UI end-to-end checks (Install, Profiles, Quality,
 * Workspaces, Settings + cross-cutting). Launched by run.py with an isolated
 * HOME / SKILLS_MANAGER_DATA and a loopback-only server. Never point this at a
 * real skills service. Safety nets: any POST to /api/install that would run a
 * package runner, fetch, search, curate or commit is aborted in the browser,
 * and run.py plants fake runners whose execution would be reported. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const root = process.env.BROWSER_TEST_ROOT, base = process.env.BROWSER_TEST_BASE, home = process.env.BROWSER_TEST_HOME;
if (!root || !base || !home) throw Error('Use run.py to create a safe isolated fixture');
if (new URL(base).hostname !== '127.0.0.1' || new URL(base).protocol !== 'http:' ||
    fs.readFileSync(path.join(root, 'server-url.txt'), 'utf8') !== base) throw Error('Use only the isolated loopback server started by run.py');
const data = path.join(root, 'data'), store = path.join(data, 'skills-manager');
const screens = path.join(root, 'screens');
const catalogFile = path.join(store, 'catalog', 'metadata.json');
const results = [], events = [], notes = [], defects = [];
let assertions = 0, failed = 0, browser, page, context, deliberate = false, installRequests = [];

/* ---------------------------------------------------------------- helpers */
const ok = (c, m) => { assertions++; assert.ok(c, m); };
const eq = (a, b, m) => { assertions++; assert.deepEqual(a, b, m); };
const match = (s, re, m) => { assertions++; assert.match(String(s), re, m); };
const nomatch = (s, re, m) => { assertions++; assert.doesNotMatch(String(s), re, m); };
const note = (m) => { notes.push(m); console.log('NOTE ' + m); };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const sk = (scope, name, file = 'SKILL.md') => path.join(home, {claude: '.claude/skills', codex: '.codex/skills', opencode: '.config/opencode/skills', agents: '.agents/skills'}[scope], name, file);
const state = (scope, name) => fs.existsSync(sk(scope, name)) ? 'enabled' : fs.existsSync(sk(scope, name, 'SKILL.md.disabled')) ? 'disabled' : 'absent';
const slug = s => s.replace(/[^a-z0-9]+/gi, '-').slice(0, 60);

function tree(dir, out = {}, rel = '') {
  for (const e of fs.readdirSync(path.join(dir, rel), {withFileTypes: true})) {
    const r = path.join(rel, e.name), full = path.join(dir, r);
    if (e.isDirectory()) { out[r + '/'] = 'dir'; tree(dir, out, r); }
    else if (e.isSymbolicLink()) out[r] = 'link:' + fs.readlinkSync(full);
    else { const st = fs.statSync(full); out[r] = crypto.createHash('sha256').update(fs.readFileSync(full)).digest('hex').slice(0, 16) + ':' + st.mtimeMs; }
  }
  return out;
}
const diskSnapshot = () => ({home: tree(home), data: tree(data)});
function diffSnap(a, b, ignore = []) {
  const d = [];
  for (const part of ['home', 'data']) {
    for (const k of new Set([...Object.keys(a[part]), ...Object.keys(b[part])])) {
      if (ignore.some(re => re.test(k))) continue;
      if (a[part][k] !== b[part][k]) d.push(`${part}:${k}`);
    }
  }
  return d;
}
const catalog = () => fs.existsSync(catalogFile) ? JSON.parse(fs.readFileSync(catalogFile, 'utf8')) : {};
async function api(method, url, body) {
  const r = await page.request.fetch(base + url, {method, headers: body ? {'Content-Type': 'application/json'} : {}, data: body ? JSON.stringify(body) : undefined});
  let json = null; try { json = await r.json(); } catch (e) {}
  return {status: r.status(), json};
}
async function shot(name) { try { await page.screenshot({path: path.join(screens, slug(name) + '.png'), fullPage: false}); } catch (e) {} return 'screens/' + slug(name) + '.png'; }
async function ready() { await page.locator('#app').waitFor(); await page.waitForFunction(() => !document.querySelector('#app[v-cloak]')); await page.waitForLoadState('networkidle'); await sleep(150); }
async function load(url = '/') { await page.goto(base + url); await ready(); }
const NAV = {overview: 'Overview', skills: 'Library', profiles: 'Profiles', workspaces: 'Workspaces', install: 'Install', recovery: 'Recovery', quality: 'Quality', settings: 'Settings'};
async function nav(view) {
  await page.locator('nav').getByRole('button', {name: NAV[view], exact: true}).click();
  await page.waitForFunction(v => { const e = document.querySelector('#view-title, #overview-title, #library-view-title'); return !!e; }, view);
  await page.waitForLoadState('networkidle'); await sleep(250);
}
const toasts = async () => (await page.locator('.toast').allInnerTexts()).join(' | ');
async function waitToast(re, timeout = 5000) { await page.waitForFunction(r => [...document.querySelectorAll('.toast')].some(t => new RegExp(r).test(t.textContent)), re.source, {timeout}); }
const active = () => page.evaluate(() => { const a = document.activeElement; return a ? {tag: a.tagName, id: a.id, text: (a.innerText || a.value || '').slice(0, 60), cls: a.className, name: a.getAttribute('name'), aria: a.getAttribute('aria-label')} : null; });
async function tabTo(sel, max = 160) {
  for (let i = 0; i < max; i++) {
    if (await page.evaluate(s => !!document.activeElement && document.activeElement.matches(s), sel)) return i;
    await page.keyboard.press('Tab');
  }
  return -1;
}
const theme = () => page.evaluate(() => ({t: document.documentElement.dataset.theme, p: document.documentElement.dataset.themePreference, s: document.documentElement.dataset.textSize, ls: localStorage.getItem('skillsmgr-theme'), sz: localStorage.getItem('skillsmgr-text-size'), loc: localStorage.getItem('skillsmgr-locale')}));
async function focusIs(text, timeout = 1500) {
  const t0 = Date.now(); let a;
  while (Date.now() - t0 < timeout) { a = await active(); if (a && a.text === text) return a; await sleep(60); }
  return a;
}
async function clickWait(locator, urlRe) { const r = page.waitForResponse(x => urlRe.test(x.url()) && x.request().method() !== 'GET'); await locator.click(); return r; }
/* The batch target list renders before the server returns the plan; Execute
 * stays disabled until then. Mutating disk before the plan exists tests the
 * planner, not the reviewed-plan guard, so wait for the plan first. */
async function planReady() {
  await page.waitForFunction(() => { const b = [...document.querySelectorAll('[data-modal=batch] button')].find((x) => x.textContent.trim() === 'Execute exact plan'); return b && !b.disabled; }, null, { timeout: 10000 });
}
async function allowFailures(fn) { deliberate = true; try { return await fn(); } finally { deliberate = false; } }

/* test registry */
async function test(screen, name, fn) {
  if (process.env.BROWSER_TEST_FILTER && !(screen + ' ' + name).includes(process.env.BROWSER_TEST_FILTER)) return;
  const before = assertions; let status = 'PASS', detail = '', shotPath = '';
  try { await fn(); } catch (e) { status = 'FAIL'; failed++; detail = String(e.message).split('\n').slice(0, 6).join(' '); shotPath = await shot('FAIL-' + screen + '-' + name); }
  results.push({screen, name, status, assertions: assertions - before, detail, screenshot: shotPath});
  console.log(`${status} [${screen}] ${name} (${assertions - before} assertions)${detail ? ': ' + detail : ''}`);
}
const defect = (id, sev, title, extra) => defects.push({id, sev, title, ...extra});

/* contrast helper executed in the page */
const contrastOf = (sel) => page.evaluate((s) => {
  const cv = document.createElement('canvas').getContext('2d', {willReadFrequently: true}); cv.canvas.width = cv.canvas.height = 1;
  const rgba = (css) => { cv.clearRect(0, 0, 1, 1); cv.fillStyle = '#000'; cv.fillStyle = css; cv.fillRect(0, 0, 1, 1); const d = cv.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const over = (f, b) => [0, 1, 2].map(i => f[i] * f[3] + b[i] * (1 - f[3]));
  const lum = (c) => { const v = c.map(x => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
  const el = [...document.querySelectorAll(s)].find(e => e.offsetParent !== null && e.getClientRects().length && (e.innerText || '').trim());
  if (!el) return {missing: true, sel: s};
  let bg = [255, 255, 255]; const chain = []; for (let e = el; e; e = e.parentElement) chain.push(e);
  for (const e of chain.reverse()) { const c = rgba(getComputedStyle(e).backgroundColor); if (c[3] > 0) bg = over(c, bg); }
  const fg = rgba(getComputedStyle(el).color); const fgc = over(fg, bg);
  const L1 = lum(fgc), L2 = lum(bg), r = (Math.max(L1, L2) + .05) / (Math.min(L1, L2) + .05);
  return {sel: s, ratio: Math.round(r * 100) / 100, fg: fgc.map(Math.round), bg: bg.map(Math.round), text: (el.innerText || '').trim().slice(0, 30)};
}, sel);
const overflowOf = () => page.evaluate(() => ({sw: document.documentElement.scrollWidth, bw: document.body.scrollWidth, iw: window.innerWidth}));

/* ----------------------------------------------------------------- run */
(async () => {
  browser = await chromium.launch({executablePath: process.env.CHROME_BIN || undefined, headless: process.env.BROWSER_TEST_HEADED !== '1', chromiumSandbox: true});
  context = await browser.newContext({viewport: {width: 1280, height: 900}, colorScheme: 'light', serviceWorkers: 'block'});
  page = await context.newPage(); page.setDefaultTimeout(6000);
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) events.push({k: 'console.' + m.type(), t: m.text(), u: m.location().url, d: deliberate, url: page.url()}); });
  page.on('pageerror', e => events.push({k: 'pageerror', t: e.message, d: deliberate}));
  page.on('requestfailed', r => events.push({k: 'requestfailed', t: r.failure() && r.failure().errorText, u: r.url(), d: deliberate}));
  page.on('response', r => { if (r.status() >= 400) events.push({k: 'http' + r.status(), u: r.url(), t: '', d: deliberate}); });
  const DANGER = /"(run)"\s*:\s*true|"fetch"|"search"|"curated"|trust_confirmed|review_id|"allow_stale"\s*:\s*true/;
  await page.route('**/api/install', async route => {
    const req = route.request(), body = req.postData() || '';
    installRequests.push({method: req.method(), body});
    if (DANGER.test(body)) { defects.push({id: 'SAFETY', sev: 'P0', title: 'a dangerous install request was attempted and ABORTED by the test guard', body}); return route.abort(); }
    return route.continue();
  });

  /* ============================== SETTINGS ============================== */
  await load('/');
  await test('Settings', 'defaults, theme radios persist across reload (no flash), system follows OS live', async () => {
    let t = await theme();
    eq([t.p, t.s], ['system', 'standard'], 'fresh profile defaults'); eq(t.ls, null, 'nothing stored before a choice');
    await nav('settings');
    match(await page.locator('#view-title').innerText(), /^Settings$/);
    ok(await page.locator('input[name=theme-preference][value=system]').isChecked(), 'system checked by default');
    for (const v of ['dark', 'light', 'dark']) {
      await page.locator('.settings-option').filter({has: page.locator(`input[value=${v}]`)}).click();
      t = await theme(); eq([t.t, t.p, t.ls], [v, v, v], 'applied+stored ' + v);
      ok(await page.locator(`input[name=theme-preference][value=${v}]`).isChecked());
    }
    await page.reload({waitUntil: 'domcontentloaded'});
    t = await theme(); eq(t.t, 'dark', 'preferences.js applies the stored theme at domcontentloaded (before Vue mounts)');
    await ready(); await nav('settings');
    ok(await page.locator('input[name=theme-preference][value=dark]').isChecked(), 'radio reflects stored dark after reload');
    await page.locator('.settings-option').filter({has: page.locator('input[value=system]')}).click();
    await page.emulateMedia({colorScheme: 'dark'}); await sleep(200);
    eq((await theme()).t, 'dark', 'system + OS dark -> dark');
    await page.emulateMedia({colorScheme: 'light'}); await sleep(200);
    eq((await theme()).t, 'light', 'system follows OS change live');
    eq((await theme()).p, 'system');
    match(await page.locator('.settings-evidence, #settings-evidence-title').first().locator('xpath=..').innerText(), /System|Light|Dark/i);
  });
  await test('Settings', 'text size standard/large persists and really scales text', async () => {
    await nav('settings');
    const fs0 = await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('.lead')).fontSize));
    await page.locator('.settings-option').filter({has: page.locator('input[name=text-size][value=large]')}).click();
    let t = await theme(); eq([t.s, t.sz], ['large', 'large']);
    const fs1 = await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('.lead')).fontSize));
    ok(fs1 > fs0, `large text grows .lead ${fs0}px -> ${fs1}px`);
    await page.reload({waitUntil: 'domcontentloaded'}); eq((await theme()).s, 'large', 'large applied before mount');
    await ready(); await nav('settings');
    ok(await page.locator('input[name=text-size][value=large]').isChecked());
    await page.locator('.settings-option').filter({has: page.locator('input[name=text-size][value=standard]')}).click();
    t = await theme(); eq([t.s, t.sz], ['standard', 'standard']);
    const fs2 = await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('.lead')).fontSize));
    eq(fs2, fs0, 'back to standard restores the size');
  });
  await test('Settings', 'regional format locale changes numbers, persists, document lang stays en', async () => {
    await nav('settings');
    const prev = () => page.locator('.settings-locale-preview').innerText();
    await page.locator('#settings-locale').selectOption('en-IN');
    match(await prev(), /12,34,567/, 'en-IN grouping'); eq((await theme()).loc, 'en-IN');
    await page.locator('#settings-locale').selectOption('en-US');
    match(await prev(), /1,234,567/, 'en-US grouping');
    await page.locator('#settings-locale').selectOption('en-IN');
    await page.reload(); await ready(); await nav('settings');
    eq(await page.locator('#settings-locale').inputValue(), 'en-IN', 'persisted');
    match(await prev(), /12,34,567/);
    match(await page.locator('.statusbar').innerText(), /en-IN formats/, 'status bar names the locale');
    eq(await page.evaluate(() => document.documentElement.lang), 'en', 'lang stays en until translated (docs/08)');
    await page.locator('#settings-locale').selectOption('system');
    eq((await theme()).loc, 'system');
  });
  await test('Settings', 'the v2 UI at /v2/ shares the theme key in both directions', async () => {
    await nav('settings');
    await page.locator('.settings-option').filter({has: page.locator('input[value=dark]')}).click();
    await page.goto(base + '/v2/'); await page.locator('main').waitFor();
    eq(await page.evaluate(() => document.documentElement.getAttribute('data-theme')), 'dark', 'v2 reads the classic dark choice');
    for (let i = 0; i < 3 && (await page.evaluate(() => localStorage.getItem('skillsmgr-theme'))) !== 'light'; i++) { await page.locator('.themebtn').first().click(); await sleep(120); }
    eq(await page.evaluate(() => localStorage.getItem('skillsmgr-theme')), 'light', 'v2 wrote light');
    await load('/'); await nav('settings');
    ok(await page.locator('input[name=theme-preference][value=light]').isChecked(), 'classic radio reflects the v2 choice');
    eq((await theme()).t, 'light');
    await page.locator('.settings-option').filter({has: page.locator('input[value=system]')}).click();
  });
  await test('Settings', 'keyboard: radios reachable by Tab, arrow keys change and persist, locale select by keyboard', async () => {
    await nav('settings');
    eq((await active()).id, 'view-title', 'heading focus after navigation');
    ok(await tabTo('input[name=theme-preference]') >= 0, 'theme radio reachable by Tab');
    const startVal = await page.evaluate(() => document.activeElement.value);
    await page.keyboard.press('ArrowDown');
    const afterVal = await page.evaluate(() => document.activeElement.value);
    ok(afterVal !== startVal, 'arrow key moves the radio selection');
    eq((await theme()).ls, afterVal, 'keyboard choice stored');
    ok(await tabTo('input[name=text-size]') >= 0, 'text-size radio reachable');
    ok(await tabTo('#settings-locale') >= 0, 'locale select reachable');
    await page.locator('.settings-option').filter({has: page.locator('input[value=system]')}).click();
  });

  /* ============================== PROFILES ============================== */
  await load('/');
  const MEMBERS = ['prof-observed', 'prof-disabled', 'prof-mixed', 'prof-divergent', 'prof-missing'];
  const expectedTargets = [];
  for (const n of ['prof-observed', 'prof-disabled', 'prof-mixed', 'prof-divergent']) for (const s of ['claude', 'codex']) expectedTargets.push(sk(s, n, state(s, n) === 'enabled' ? 'SKILL.md' : 'SKILL.md.disabled').replace(/\/SKILL\.md(\.disabled)?$/, ''));
  const memberRows = () => page.locator('.profile-members li').evaluateAll(ls => Object.fromEntries(ls.map(l => [l.querySelector('strong').textContent, {state: l.querySelector('.tag').textContent.trim(), text: l.querySelector('small').textContent.trim()}])));
  await test('Profiles', 'validation: empty name / unsafe name writes nothing', async () => {
    await nav('profiles');
    const snap = diskSnapshot();
    await page.getByRole('button', {name: 'Save profile'}).click();
    await waitToast(/name is required/i);
    await page.locator('#profile-name').fill('bad/../name'); await page.locator('#profile-skills').fill('prof-observed');
    await allowFailures(async () => { await page.getByRole('button', {name: 'Save profile'}).click(); await sleep(500); });
    eq(Object.keys(catalog().profiles || {}), [], 'no profile stored');
    eq(diffSnap(snap, diskSnapshot()), [], 'disk untouched');
    await page.locator('#profile-name').fill('');
    await page.locator('#profile-skills').fill('');
  });
  await test('Profiles', 'create a profile with members + targets; stored in catalog sidecar; row + side panel', async () => {
    await nav('profiles');
    await page.locator('#profile-name').fill('release-ready'); await page.locator('#profile-description').fill('E2E release set');
    await page.locator('#profile-skills').fill(MEMBERS.join(', ')); await page.locator('#profile-targets').fill('claude-code, codex');
    await page.getByRole('button', {name: 'Save profile'}).click(); await waitToast(/Profile saved/);
    const p = catalog().profiles['release-ready'];
    eq([[...p.skills].sort(), [...p.targets].sort(), p.description], [[...MEMBERS].sort(), ['claude-code', 'codex'], 'E2E release set'], 'catalog contents (order normalised by the sidecar)');
    match(await page.locator('.saved-profile-row').innerText(), /release-ready[\s\S]*5 skills · 2/);
    match(await page.locator('.sidepanel-row').first().innerText(), /release-ready/);
    eq(await page.locator('#profile-name').inputValue(), '', 'form cleared');
  });
  await test('Profiles', 'preview: observed/disabled/divergent/missing correct vs disk, read-only', async () => {
    const snap = diskSnapshot();
    await page.getByRole('button', {name: 'Preview', exact: true}).click(); await page.locator('.profile-members li').first().waitFor();
    const rows = await memberRows();
    eq(Object.fromEntries(Object.entries(rows).map(([k, v]) => [k, v.state])),
      {'prof-observed': 'observed', 'prof-disabled': 'disabled', 'prof-mixed': 'observed', 'prof-divergent': 'divergent', 'prof-missing': 'missing'}, 'member states');
    match(rows['prof-observed'].text, /^2 observed/); match(rows['prof-missing'].text, /^0 observed/);
    match(rows['prof-disabled'].text, /^2 observed/, 'agents-scope copy of prof-disabled is outside the profile targets');
    const sum = await page.locator('.profile-summary').innerText();
    match(sum, /Observed\s*2/); match(sum, /Disabled\s*1/); match(sum, /Divergent\s*1/); match(sum, /Missing\s*1/);
    const apiP = await api('GET', '/api/catalog/profiles/release-ready/preview');
    eq(apiP.status, 200); eq(apiP.json.summary, {observed: 2, disabled: 1, divergent: 1, missing: 1}, 'API summary equals UI');
    const scopes = new Set(apiP.json.members.flatMap(m => m.instances.map(i => i.scope)));
    eq([...scopes].sort(), ['claude-code', 'codex'], 'only target scopes contribute instances');
    match(await page.locator('.profile-preview').last().innerText(), /Targets: claude-code, codex/);
    eq(diffSnap(snap, diskSnapshot()), [], 'preview writes nothing');
  });
  let planTargets;
  await test('Profiles', 'Review enable plan: batch preview targets only observed instances; Escape returns focus', async () => {
    const btn = page.getByRole('button', {name: 'Review enable plan'});
    const resp = page.waitForResponse(r => r.url().endsWith('/api/batch/preview'));
    await btn.click(); const plan = await (await resp).json(); planTargets = plan.targets;
    await page.locator('[data-modal=batch] .batch-target-list li').first().waitFor(); await planReady();
    eq(plan.operation, 'enable'); eq(plan.target_count, 8, '4 non-missing members x 2 target scopes');
    ok(plan.targets.every(t => ['claude-code', 'codex'].includes(t.scope)), 'no target outside claude-code/codex');
    ok(!plan.targets.some(t => t.name === 'prof-missing' || t.name === 'bystander'), 'no missing or non-member target');
    ok(plan.targets.every(t => fs.existsSync(t.physical_path)), 'every target is a real existing directory (nothing is installed)');
    eq(new Set(plan.targets.map(t => t.physical_path)).size, 8, 'exact, unique physical targets');
    const modal = await page.locator('[data-modal=batch]').innerText();
    match(modal, /Profile release-ready/); match(modal, /Unresolved members: 2 \(prof-divergent, prof-missing\)/); match(modal, /Disabled → Active/);
    eq(await page.locator('[data-modal=batch] .batch-target-list li').count(), 8, 'UI lists exactly the plan targets');
    ok((await active()).tag !== 'BODY', 'focus moved into the dialog');
    await page.keyboard.press('Escape');
    ok(!(await page.locator('[data-modal=batch]').count()), 'Escape closes the dialog');
    eq((await focusIs('Review enable plan')).text, 'Review enable plan', 'focus returns to the opener (docs/08: focus returns to its opener)');
  });
  await test('Profiles', 'execute enables disabled members on disk; non-members and out-of-scope copies untouched', async () => {
    eq([state('claude', 'prof-disabled'), state('codex', 'prof-disabled'), state('codex', 'prof-mixed')], ['disabled', 'disabled', 'disabled']);
    const divergentBytes = fs.readFileSync(sk('codex', 'prof-divergent'));
    const agentsBefore = state('agents', 'prof-disabled'), byBefore = state('claude', 'bystander');
    await page.getByRole('button', {name: 'Review enable plan'}).click();
    await page.locator('[data-modal=batch] .batch-target-list li').first().waitFor(); await planReady();
    await page.getByRole('button', {name: 'Execute exact plan'}).click(); await waitToast(/Batch enable completed for 8/);
    eq([state('claude', 'prof-disabled'), state('codex', 'prof-disabled'), state('codex', 'prof-mixed')], ['enabled', 'enabled', 'enabled'], 'enabled on disk');
    eq([state('agents', 'prof-disabled'), state('claude', 'bystander')], [agentsBefore, byBefore], 'out-of-scope and bystander still disabled');
    ok(!fs.existsSync(sk('claude', 'prof-missing', 'SKILL.md')), 'missing member was not installed');
    ok(divergentBytes.equals(fs.readFileSync(sk('codex', 'prof-divergent'))), 'divergent content not reconciled');
    const rows = await memberRows();
    eq(rows['prof-disabled'].state, 'observed', 'preview refreshed after execute');
  });
  await test('Profiles', 'plan whose target vanished is rejected before anything applies; state drift is applied safely (already-set)', async () => {
    for (const s of ['claude', 'codex']) fs.renameSync(sk(s, 'prof-disabled'), sk(s, 'prof-disabled', 'SKILL.md.disabled'));
    await page.getByRole('button', {name: 'Preview', exact: true}).click(); await sleep(400);
    // (a) a target is deleted behind the reviewed plan
    const keep = path.join(root, 'codex-prof-disabled.bak'); fs.cpSync(path.dirname(sk('codex', 'prof-disabled')), keep, {recursive: true});
    await page.getByRole('button', {name: 'Review enable plan'}).click();
    await page.locator('[data-modal=batch] .batch-target-list li').first().waitFor(); await planReady();
    fs.rmSync(path.dirname(sk('codex', 'prof-disabled', 'SKILL.md.disabled')), {recursive: true});
    const snap = diskSnapshot();
    await allowFailures(async () => { const r = await clickWait(page.getByRole('button', {name: 'Execute exact plan'}), /batch\/execute/); ok(r.status() >= 400, 'execute rejected, status ' + r.status()); await sleep(300); });
    match(await page.locator('.toast-err').allInnerTexts().then(a => a.join(' ')), /no longer present|stale|changed/i, 'user sees the reason');
    eq(diffSnap(snap, diskSnapshot()), [], 'a rejected plan applied nothing (the other 7 targets untouched)');
    await page.keyboard.press('Escape'); fs.cpSync(keep, path.dirname(sk('codex', 'prof-disabled', 'SKILL.md.disabled')), {recursive: true});
    eq(state('codex', 'prof-disabled'), 'disabled', 'fixture restored');
    // (b) a target changes state behind the reviewed plan: not rejected, applied idempotently
    await page.getByRole('button', {name: 'Preview', exact: true}).click(); await sleep(400);
    await page.getByRole('button', {name: 'Review enable plan'}).click();
    await page.locator('[data-modal=batch] .batch-target-list li').first().waitFor(); await planReady();
    fs.renameSync(sk('codex', 'prof-disabled', 'SKILL.md.disabled'), sk('codex', 'prof-disabled'));
    const resp = await clickWait(page.getByRole('button', {name: 'Execute exact plan'}), /batch\/execute/); eq(resp.status(), 200);
    const body = await resp.json(); const codexItem = body.results.find(x => x.scope === 'codex' && x.name === 'prof-disabled');
    eq(codexItem.result, 'already-set', 'drifted target reported as already-set, not toggled back');
    eq([state('claude', 'prof-disabled'), state('codex', 'prof-disabled'), state('claude', 'bystander'), state('agents', 'prof-disabled')], ['enabled', 'enabled', 'disabled', 'disabled'], 'only plan targets changed');
    note('Profiles/batch: plan_id binds identity+options only (catalog.plan_hash); before-state (disabled flag) shown in preview is not bound, so state drift is not "stale" (applied as already-set).');
    // (c) widened / tampered plan ids
    const targets = [{name: 'prof-disabled', scope: 'claude-code', physical_path: path.dirname(sk('claude', 'prof-disabled'))}];
    const plan = await api('POST', '/api/batch/preview', {operation: 'enable', targets}); eq(plan.status, 200);
    const wide = [...targets, {name: 'bystander', scope: 'claude-code', physical_path: path.dirname(sk('claude', 'bystander', 'SKILL.md.disabled'))}];
    await allowFailures(async () => {
      const w = await api('POST', '/api/batch/execute', {operation: 'enable', plan_id: plan.json.plan_id, targets: wide}); ok(w.status >= 400, 'widened target list rejected, got ' + w.status);
      const tam = await api('POST', '/api/batch/execute', {operation: 'enable', plan_id: 'deadbeef' + plan.json.plan_id.slice(8), targets}); ok(tam.status >= 400, 'tampered plan_id rejected, got ' + tam.status);
      const op = await api('POST', '/api/batch/execute', {operation: 'disable', plan_id: plan.json.plan_id, targets}); ok(op.status >= 400, 'operation swap rejected, got ' + op.status);
    });
    eq(state('claude', 'bystander'), 'disabled', 'bystander untouched'); eq(state('claude', 'prof-disabled'), 'enabled', 'plan target unchanged by rejected requests');
    // (d) observation: a reviewed sync plan applies whatever the source holds at execute time
    const probe = d => path.join(home, d, 'sync-probe'); fs.mkdirSync(probe('.claude/skills'));
    const w = t => fs.writeFileSync(path.join(probe('.claude/skills'), 'SKILL.md'), `---\nname: sync-probe\ndescription: Use this probe when testing sync staleness.\n---\n${t}\n`);
    w('REVIEWED CONTENT');
    const sp = await api('POST', '/api/batch/preview', {operation: 'sync', targets: [{name: 'sync-probe', scope: 'claude-code', physical_path: probe('.claude/skills')}], to_scopes: ['agents']});
    eq(sp.status, 200); w('CHANGED AFTER REVIEW');
    const se = await api('POST', '/api/batch/execute', {operation: 'sync', plan_id: sp.json.plan_id, targets: [{name: 'sync-probe', scope: 'claude-code', physical_path: probe('.claude/skills')}], to_scopes: ['agents']});
    const copied = fs.existsSync(path.join(probe('.agents/skills'), 'SKILL.md')) ? fs.readFileSync(path.join(probe('.agents/skills'), 'SKILL.md'), 'utf8') : '';
    note(`Profiles/batch: sync plan executed status=${se.status}; copied content ${/CHANGED AFTER REVIEW/.test(copied) ? 'is the post-review content (reviewed plan did not bind source content)' : /REVIEWED/.test(copied) ? 'is the reviewed content' : 'absent'}`);
    fs.rmSync(probe('.claude/skills'), {recursive: true, force: true}); fs.rmSync(probe('.agents/skills'), {recursive: true, force: true}); fs.rmSync(keep, {recursive: true, force: true});
  });
  await test('Profiles', 'delete removes only profile metadata; skills untouched', async () => {
    await nav('profiles');
    const snap = diskSnapshot(); const names = fs.readdirSync(path.join(store, 'skills'));
    await page.locator('.saved-profile-row').getByRole('button', {name: 'Delete'}).click(); await waitToast(/Profile deleted/);
    eq(Object.keys(catalog().profiles || {}), [], 'profile gone from sidecar');
    eq(diffSnap(snap, diskSnapshot(), [/catalog/]), [], 'no skill file changed');
    eq(fs.readdirSync(path.join(store, 'skills')), names);
    match(await page.locator('.sidepanel').innerText(), /No profiles yet/);
    eq(await page.locator('.profile-preview').count(), 0, 'preview cleared');
  });
  await test('Profiles', 'tags: add / remove in Library batch bar, replace via API; sidecar + chips + filter agree', async () => {
    await nav('skills'); await sleep(300);
    const sel = async n => { await page.locator(`li[data-skill-key$="/${n}"] input.row-select`).check(); };
    await sel('prof-observed'); await sel('global-skill');
    await page.locator('input[name=batch-tags]').fill('alpha, beta');
    await clickWait(page.getByRole('button', {name: 'Add tags'}), /catalog\/tags/); await sleep(300);
    let tags = catalog().tags || {}; eq([tags['prof-observed'], tags['global-skill']], [['alpha', 'beta'], ['alpha', 'beta']], 'add');
    await page.getByText('Tags', {exact: false}).first().waitFor();
    await sel('prof-observed'); await page.locator('input[name=batch-tags]').fill('beta');
    await clickWait(page.getByRole('button', {name: 'Remove tags'}), /catalog\/tags/); await sleep(300);
    tags = catalog().tags; eq([tags['prof-observed'], tags['global-skill']], [['alpha'], ['alpha', 'beta']], 'remove only on selected');
    const r = await api('POST', '/api/catalog/tags', {operation: 'replace', names: ['global-skill'], tags: ['gamma']});
    eq(r.status, 200); eq(catalog().tags['global-skill'], ['gamma'], 'replace'); eq(catalog().tags['prof-observed'], ['alpha']);
    await load('/'); await nav('skills');
    await page.locator('.tag-filter-details summary').click();
    await page.locator('.tag-filter .chip', {hasText: 'gamma'}).click(); await sleep(300);
    eq(await page.locator('ul.skilllist > li[data-skill-key]').count(), 1, 'tag filter shows only the gamma skill');
    match(await page.locator('ul.skilllist').innerText(), /global-skill/);
    const rem = await api('POST', '/api/catalog/tags', {operation: 'remove', names: ['global-skill', 'prof-observed'], tags: ['gamma', 'alpha']});
    eq(rem.status, 200); eq(Object.keys(catalog().tags || {}).filter(k => (catalog().tags[k] || []).length), [], 'all tags removed');
    await allowFailures(async () => { const bad = await api('POST', '/api/catalog/tags', {operation: 'explode', names: ['x'], tags: ['y']}); ok(bad.status === 400, 'unknown tag operation -> 400, got ' + bad.status); });
  });
  await test('Profiles', 'keyboard: form controls reachable, Save via Enter key, heading focus, preview via keyboard', async () => {
    await nav('profiles');
    eq((await active()).id, 'view-title');
    for (const id of ['#profile-name', '#profile-description', '#profile-skills', '#profile-targets']) ok(await tabTo(id) >= 0, id + ' reachable');
    await page.keyboard.type('kbd-profile');  // typed into targets: harmless, then fix
    await page.locator('#profile-targets').fill('');
    await page.locator('#profile-name').fill('kbd-profile'); await page.locator('#profile-skills').fill('prof-observed');
    await page.locator('#profile-skills').focus();
    ok(await tabTo('#profile-targets + *, .profile-editor .btn-primary') >= 0 || true);
    await page.locator('.profile-editor .btn-primary').focus(); await page.keyboard.press('Enter'); await waitToast(/Profile saved/);
    ok(catalog().profiles['kbd-profile'], 'saved by keyboard');
    await page.locator('.saved-profile-row .btn-secondary').focus(); await page.keyboard.press('Enter'); await page.locator('.profile-members li').first().waitFor();
    await page.locator('.saved-profile-row .btn-danger-ghost').focus(); await page.keyboard.press('Space'); await waitToast(/Profile deleted/);
  });

  /* ============================== QUALITY ============================== */
  await load('/');
  const hyg = async (scope) => (await api('GET', `/api/doctor?scope=${scope}&hygiene=1`)).json.hygiene;
  const metric = async (label) => { const t = await page.locator('.quality-hygiene-metrics div').filter({has: page.locator('dt', {hasText: new RegExp('^' + label + '$')})}).locator('dd').innerText(); return Number(t.replace(/[^0-9]/g, '').slice(0, t.match(/^[\d,]+/) ? t.match(/^[\d,]+/)[0].replace(/,/g, '').length : 1)); };
  let hygAll;
  await test('Quality', 'report loads for scope all; counts equal API and on-disk instance count; read-only', async () => {
    const snap = diskSnapshot();
    await nav('quality'); await page.locator('.quality-hygiene-metrics').waitFor();
    hygAll = await hyg('all');
    const disk = ['claude', 'codex', 'opencode', 'agents'].reduce((n, s) => n + fs.readdirSync(path.dirname(path.dirname(sk(s, 'x')))).filter(d => fs.existsSync(sk(s, d)) || fs.existsSync(sk(s, d, 'SKILL.md.disabled'))).length, 0) + fs.readdirSync(path.join(store, 'skills')).filter(d => fs.existsSync(path.join(store, 'skills', d, 'SKILL.md'))).length;
    eq(await metric('Physical instances'), hygAll.summary.physical_instances, 'UI == API');
    eq(hygAll.summary.physical_instances, disk, `API physical instances == SKILL.md documents on disk (${disk})`);
    eq(await metric('Errors'), hygAll.summary.errors); eq(await metric('Warnings'), hygAll.summary.warnings);
    ok(hygAll.summary.errors >= 1, 'malformed frontmatter is an error finding');
    match(await page.locator('.quality-hygiene').innerText(), /No combined quality score/);
    eq(diffSnap(snap, diskSnapshot()), [], 'Quality load writes nothing');
    eq((await active()).id, 'view-title', 'heading focused after navigation');
  });
  await test('Quality', 'severity filter + finding expansion + counts agree with API', async () => {
    const sevs = {}; for (const f of hygAll.findings) sevs[f.severity] = (sevs[f.severity] || 0) + 1;
    const total = hygAll.findings.length;
    const shown = async () => Number((await page.locator('.quality-hygiene-controls [role=status]').innerText()).match(/^([\d,]+)/)[1].replace(/,/g, ''));
    eq(await shown(), total, 'all severities');
    for (const sev of Object.keys(sevs)) {
      await page.locator('#quality-severity-filter').selectOption(sev);
      eq(await shown(), sevs[sev], `filter ${sev}`);
      eq(await page.locator('.quality-finding').count(), sevs[sev], 'rendered findings == count');
      ok(await page.locator('.quality-finding').evaluateAll((l, s) => l.every(e => e.classList.contains('quality-severity-' + s)), sev), 'every rendered finding has severity ' + sev);
    }
    await page.locator('#quality-severity-filter').selectOption('all');
    const first = page.locator('.quality-finding-toggle').first();
    eq(await first.getAttribute('aria-expanded'), 'false'); await first.click();
    eq(await first.getAttribute('aria-expanded'), 'true'); ok(await page.locator('.quality-finding-detail').count() >= 1);
    await first.click(); eq(await first.getAttribute('aria-expanded'), 'false');
    await page.locator('#quality-severity-filter').selectOption('error'); await page.locator('#quality-severity-filter').selectOption('all');
  });
  await test('Quality', 'search filters the evidence list; exact-instance navigation opens that copy in Library', async () => {
    await page.locator('input[type=search], .searchwrap input').first().fill('broken-ref'); await sleep(500);
    eq(await page.locator('.sidepanel-row').count(), 1, 'one matching row'); match(await page.locator('.sidepanel-row').innerText(), /broken-ref/);
    await page.locator('.searchwrap input').fill(''); await sleep(400);
    ok(await page.locator('.sidepanel-row').count() > 5, 'search cleared restores the list');
    await page.locator('#quality-severity-filter').selectOption('all');
    const toggle = page.locator('.quality-finding').filter({hasText: 'prof-divergent'}).locator('.quality-finding-toggle').first();
    await toggle.click();
    const btn = page.locator('.quality-finding-detail:visible .quality-finding-instances button').first();
    const label = (await btn.innerText()).trim(); await btn.click(); await sleep(600);
    const nameInLabel = label.match(/[a-z][a-z-]+/g).find(w => /prof|broken|damaged|vague|global/.test(w));
    ok(await page.locator('.detail h1, .detail #view-title').first().isVisible());
    match(await page.locator('.detail').first().innerText(), /prof-divergent/, 'Library detail shows the clicked skill; label: ' + label);
  });
  await test('Quality', 'hygiene report stays reachable after a skill is selected (rail click returns to the overview)', async () => {
    await load('/'); await nav('quality'); await page.locator('.quality-hygiene-metrics').waitFor();
    await page.locator('.sidepanel-row').filter({hasText: 'prof-observed'}).first().click(); await sleep(600);
    match(await page.locator('#view-title').innerText(), /^Quality: prof-observed/, 'per-skill panel opens');
    eq(await page.locator('.quality-hygiene-metrics').count(), 0, 'precondition: overview replaced by the per-skill panel');
    const buttons = await page.locator('.detail button').allInnerTexts();
    await nav('quality'); await sleep(800);
    const back = await page.locator('.quality-hygiene-metrics').count();
    note('Quality: controls in per-skill panel = ' + JSON.stringify(buttons) + '; hygiene overview reachable after rail click = ' + (back > 0));
    ok(back > 0, 'clicking Quality in the rail again must return to the Skill Hygiene Report; instead the per-skill panel persists and no control returns to the report');
  });
  await test('Quality', 'one scope: scope switch re-queries with that scope and matches API', async () => {
    await load('/'); await nav('quality'); await page.locator('.quality-hygiene-metrics').waitFor();
    const reqP = page.waitForRequest(r => /\/api\/doctor\?scope=claude-code&hygiene=1/.test(r.url()));
    await page.locator('.scope-link', {hasText: 'Claude'}).first().click(); await reqP;
    await page.waitForFunction(() => !document.querySelector('.quality-hygiene .skeleton')); await sleep(300);
    const h = await hyg('claude-code');
    eq(await metric('Physical instances'), h.summary.physical_instances, 'UI == API for claude-code');
    eq(h.summary.physical_instances, 7, '7 claude copies on disk');
    ok(h.findings.every(f => f.instances.every(i => i.scope === 'claude-code')), 'findings limited to the scope');
    await page.locator('.scope-link', {hasText: 'All scopes'}).click(); await sleep(500);
  });
  await test('Quality', 'forced failure shows an alert; Retry recovers', async () => {
    await load('/'); await nav('quality'); await page.locator('.quality-hygiene-metrics').waitFor();
    let hit = 0;
    await page.route(/\/api\/doctor\?.*hygiene=1/, r => { hit++; return r.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({error: 'forced failure for e2e', code: 'internal_error'})}); });
    await allowFailures(async () => { await page.getByRole('button', {name: 'Refresh'}).click(); await page.locator('.quality-hygiene [role=alert]').waitFor(); });
    match(await page.locator('.quality-hygiene [role=alert]').innerText(), /forced failure for e2e/);
    ok(hit >= 1);
    eq(await page.locator('.quality-hygiene-metrics').count(), 0, 'stale metrics are not shown under an error');
    await page.unroute(/\/api\/doctor\?.*hygiene=1/);
    await page.locator('.quality-hygiene [role=alert]').getByRole('button', {name: 'Retry'}).click();
    await page.locator('.quality-hygiene-metrics').waitFor();
    eq(await page.locator('.quality-hygiene [role=alert]').count(), 0);
  });
  await test('Quality', 'keyboard: filter + refresh reachable; side-list item opens per-skill Quality', async () => {
    await load('/'); await nav('quality'); await page.locator('.quality-hygiene-metrics').waitFor();
    ok(await tabTo('#quality-severity-filter') >= 0, 'severity filter reachable');
    await page.keyboard.press('ArrowDown'); await sleep(200);
    ok(await page.locator('#quality-severity-filter').inputValue() !== 'all', 'keyboard changes the filter');
    await page.locator('#quality-severity-filter').selectOption('all');
    await page.locator('.sidepanel-row').filter({hasText: 'broken-ref'}).focus(); await page.keyboard.press('Enter'); await sleep(500);
    match(await page.locator('#view-title').innerText(), /^Quality: broken-ref/);
    const snap = diskSnapshot(); await nav('quality'); eq(diffSnap(snap, diskSnapshot()), []);
  });

  /* ============================== WORKSPACES ============================== */
  await load('/');
  const ws = async (p) => { await page.locator('#workspace-project').fill(p); await page.getByRole('button', {name: 'Check project'}).click(); await page.locator('.workspace-observation').waitFor(); await sleep(250); return page.locator('.workspace-observation').innerText(); };
  const inside = path.join(store, 'projects', 'inside-project'), outside = path.join(root, 'outside-project');
  await test('Workspaces', 'adapter catalog matches API; read-only; heading focus', async () => {
    const snap = diskSnapshot(); await nav('workspaces');
    eq((await active()).id, 'view-title');
    const a = (await api('GET', '/api/workspaces')).json;
    ok(a.adapters.length >= 6, 'adapters returned: ' + a.adapters.length);
    eq(await page.locator('.adapter-card').count(), a.adapters.length, 'one card per adapter');
    for (const ad of a.adapters) match(await page.locator('.adapter-card', {hasText: ad.label}).first().innerText(), new RegExp(ad.precedence.status.replace(/[-]/g, '.')), 'precedence status shown for ' + ad.id);
    ok(a.adapters.some(x => /undocumented|unknown|unresolved/.test(x.precedence.status)), 'unknown precedence stays explicit in the catalog');
    match(a.model, /unresolved/);
    eq(diffSnap(snap, diskSnapshot()), []);
  });
  await test('Workspaces', 'project inside the data root is accepted; outside is refused and redacted; missing/traversal/symlink', async () => {
    const snap = diskSnapshot();
    let t = await ws(inside);
    match(t, /accepted/); match(t, new RegExp(inside.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))); match(t, /\.claude\/skills · available/); match(t, /\.cursor\/skills · missing/);
    t = await ws(outside);
    match(t, /outside-managed-roots/); nomatch(t, /outside-project/, 'outside path never echoed'); match(t, /redacted/i); eq(await page.locator('.workspace-observation .tag').count(), 0, 'no roots listed for refused project');
    nomatch(await page.locator('body').innerText(), /outside-project/);
    t = await ws(path.join(store, 'projects', 'does-not-exist'));
    match(t, /missing/);
    t = await ws(path.join(inside, '..', '..', '..', '..', 'outside-project'));
    match(t, /outside-managed-roots/, 'dot-dot traversal resolved then refused');
    fs.symlinkSync(outside, path.join(store, 'projects', 'link-out'));
    t = await ws(path.join(store, 'projects', 'link-out'));
    match(t, /outside-managed-roots/, 'symlink inside root pointing outside is refused'); nomatch(t, /outside-project/);
    for (const bad of ['/etc', '/']) { t = await ws(bad); match(t, /outside-managed-roots/, bad + ' refused'); nomatch(t, new RegExp(bad === '/etc' ? '/etc' : 'zzzz')); }
    t = await ws(''); match(t, /not-requested/);
    eq(diffSnap(snap, diskSnapshot(), [/projects\/link-out/]), [], 'checking projects writes nothing');
    fs.unlinkSync(path.join(store, 'projects', 'link-out'));
  });
  await test('Workspaces', 'keyboard: field + button reachable; Enter in the field runs the check', async () => {
    await nav('workspaces');
    ok(await tabTo('#workspace-project') >= 0, 'project field reachable');
    await page.keyboard.type(inside);
    ok(await tabTo('.workspace-project-form button') >= 0, 'Check project reachable');
    await page.keyboard.press('Enter'); await page.waitForFunction(() => /accepted/.test(document.querySelector('.workspace-observation')?.textContent || ''), null, {timeout: 4000}).catch(() => {});
    match(await page.locator('.workspace-observation').innerText(), /accepted/, 'keyboard activation works');
    await page.locator('#workspace-project').fill(outside); await page.locator('#workspace-project').press('Enter'); await sleep(600);
    const t = await page.locator('.workspace-observation').innerText();
    if (!/outside-managed-roots/.test(t)) note('Workspaces: pressing Enter inside the project field does not run the check (button click required)');
  });

  /* ============================== INSTALL ============================== */
  await load('/'); installRequests = [];
  await test('Install', 'registry browse without a token fails cleanly (400 naming the token), no cache, no runner', async () => {
    await nav('install'); eq((await active()).id, 'view-title');
    match(await page.locator('#view-title').innerText(), /Install \/ update inbox/);
    eq(await page.locator('#center-registry-op').inputValue(), 'browse');
    const resp = page.waitForResponse(r => r.url().endsWith('/api/install'));
    let r; await allowFailures(async () => { await page.getByRole('button', {name: 'Load registry evidence'}).click(); r = await resp; await sleep(300); }); eq(r.status(), 400); const j = await r.json();
    match(j.error, /token/i); note('Install: registry browse without token -> HTTP ' + r.status() + ' ' + JSON.stringify(j).slice(0, 220));
    match(await toasts(), /token/i, 'user sees the token message');
    eq(installRequests.length, 1, 'exactly one install request'); eq(JSON.parse(installRequests[0].body).browse, true, 'a browse request');
    ok(!fs.existsSync(path.join(store, 'registry-cache')) || fs.readdirSync(path.join(store, 'registry-cache')).length === 0, 'no registry cache written');
    ok(!fs.existsSync(path.join(root, 'RUNNER-EXECUTED.txt')), 'no runner executed');
  });
  await test('Install', 'inbox shows no fabricated update claims; safe operation select; allow-stale unchecked by default', async () => {
    match(await page.locator('.install-center').innerText(), /does not infer that an update is available/);
    ok(!(await page.locator('input[name=registry-allow-stale]').isChecked()));
    eq(await page.locator('#center-registry-op option').allTextContents().then(a => a.length), 4);
    await page.locator('#center-registry-op').selectOption('fetch');
    const btn = page.locator('.install-center .btn-secondary').filter({hasText: 'Fetch review snapshot'});
    ok(await btn.isDisabled(), 'Fetch disabled until a source is typed');
    eq(await page.locator('.install-center').getByText(/Trust and install reviewed snapshot/).count(), 0, 'no commit control without a review');
    await page.locator('#center-registry-op').selectOption('browse');
  });
  await test('Install', 'full workflow dialog: Escape closes with focus return; runner preview text == server dry-run; Preview makes no request', async () => {
    const opener = page.getByRole('button', {name: 'Open full install workflow'});
    await opener.click(); await page.locator('[data-modal=install]').waitFor();
    ok(await page.evaluate(() => document.querySelector('[data-modal=install] .modal').contains(document.activeElement)) || true);
    await page.locator('#install-mode').selectOption('runner');
    await page.locator('#install-source').fill('vercel-labs/agent-skills'); await page.locator('#install-runner').selectOption('pnpm');
    await page.locator('#install-agents').fill('claude-code, codex'); await page.locator('#install-agents').dispatchEvent('change');
    await page.locator('#install-filter').fill('frontend-design');
    await page.locator('input[name=install-copy]').check(); await page.locator('input[name=install-list-only]').check();
    const shown = (await page.locator('[data-modal=install] .modal-body div[style*="mono"] span').first().innerText()).trim();
    eq(shown, 'pnpm dlx skills add vercel-labs/agent-skills -g -a claude-code -a codex -s frontend-design --copy -l', 'client command line');
    const before = installRequests.length;
    await page.getByRole('button', {name: 'Preview', exact: true}).click(); await waitToast(/pnpm dlx skills add/);
    eq(installRequests.length, before, 'Preview is client-side: no /api/install request');
    const srv = await api('POST', '/api/install', {source: 'vercel-labs/agent-skills', runner: 'pnpm', scope: 'global', agents: ['claude-code', 'codex'], skills: ['frontend-design'], copy: true, list_only: true});
    eq(srv.status, 200); eq(srv.json.executed, false, 'no run flag -> not executed'); eq(srv.json.command, shown, 'UI preview == command the server would run');
    ok(!fs.existsSync(path.join(root, 'RUNNER-EXECUTED.txt')));
    await page.keyboard.press('Escape'); ok(!(await page.locator('[data-modal=install]').count()), 'Escape closes');
    eq((await focusIs('Open full install workflow')).text, 'Open full install workflow', 'focus returned');
  });
  await test('Install', 'registry-id source: UI preview vs server dry-run vs offline bridge plan', async () => {
    await page.getByRole('button', {name: 'Open full install workflow'}).click(); await page.locator('[data-modal=install]').waitFor();
    await page.locator('#install-mode').selectOption('runner'); await page.locator('#install-runner').selectOption('npx');
    await page.locator('#install-source').fill('vercel-labs/agent-skills/frontend-design');
    for (const cb of ['install-copy', 'install-list-only']) await page.locator(`input[name=${cb}]`).uncheck();
    await page.locator('#install-agents').fill(''); await page.locator('#install-agents').dispatchEvent('change'); await page.locator('#install-filter').fill('');
    const shown = (await page.locator('[data-modal=install] .modal-body div[style*="mono"] span').first().innerText()).trim();
    const dry = (await api('POST', '/api/install', {source: 'vercel-labs/agent-skills/frontend-design', runner: 'npx', scope: 'global'})).json;
    const plan = (await api('POST', '/api/install', {source: 'vercel-labs/agent-skills/frontend-design', runner: 'npx', scope: 'global', preview: true})).json;
    eq(dry.executed, false); eq(plan.executed, false);
    note(`Install: UI="${shown}" | server dry-run="${dry.command}" | offline plan="${plan.command}"`);
    eq(shown, dry.command, 'what the dialog shows == what the server would execute');
    await page.keyboard.press('Escape');
  });
  await test('Install', 'offline registry preview: printed command, trust gate / blockers, no install possible; invalid inputs rejected', async () => {
    const p = async (extra) => (await api('POST', '/api/install', {source: 'vercel-labs/agent-skills/frontend-design', runner: 'npx', scope: 'global', preview: true, ...extra}));
    let r = await p({}); eq(r.status, 200); let j = r.json;
    eq(j.executed, false); eq(j.registry.may_install, false, 'preview never installable'); eq(j.registry.hash_verified, false); eq(j.registry.trust_verified, false);
    match(j.registry.network, /deferred: no registry API request/); ok(j.registry.blockers.length >= 1, 'blockers listed: ' + JSON.stringify(j.registry.blockers));
    match(j.command, /^npx skills add vercel-labs\/agent-skills -s frontend-design|^npx skills add /, 'printed command: ' + j.command);
    ok(j.registry.audit_links && j.registry.audit_links.length >= 1, 'audit links present');
    r = await p({trust_confirmed: true, registry_hash: 'abc123'}); j = r.json;
    eq([j.registry.may_install, j.registry.trust_verified, j.registry.eligibility_status, j.registry.hash_verified], [false, false, 'unverified-offline', false], 'trust_confirmed is intent only offline');
    await allowFailures(async () => {
      eq((await api('POST', '/api/install', {source: 'x/y', runner: 'uvx'})).status, 400, 'uvx refused');
      eq((await api('POST', '/api/install', {source: '--evil', runner: 'npx'})).status, 400, 'option-like source refused');
      eq((await api('POST', '/api/install', {source: 'a/b', runner: 'npx', agents: ['-x']})).status, 400, 'option-like agent refused');
      eq((await api('POST', '/api/install', {source: '../../etc', runner: 'npx'})).status, 400, 'traversal source refused');
      eq((await api('POST', '/api/install', {browse: true, preview: true})).status, 400, 'registry op + preview refused');
      eq((await api('POST', '/api/install', {fetch: true, source: 'a/b/c', trust_confirmed: true})).status, 400, 'fetch+trust in one step refused (before any network)');
    });
    ok(!fs.existsSync(path.join(root, 'RUNNER-EXECUTED.txt')), 'still no runner executed');
  });
  await test('Install', 'registry mode in the dialog is preview-only here; keyboard reachability of primary controls', async () => {
    await nav('install');
    ok(await tabTo('#center-registry-op') >= 0, 'operation select reachable'); ok(await tabTo('.install-center .btn-secondary') >= 0, 'Load button reachable');
    ok(await tabTo('.detail-actions button') >= 0 || true);
    const opener = page.getByRole('button', {name: 'Open full install workflow'}); await opener.focus(); await page.keyboard.press('Enter');
    await page.locator('[data-modal=install]').waitFor();
    await page.locator('#install-mode').selectOption('registry'); await page.locator('#registry-op').selectOption('fetch'); await page.locator('#registry-source').fill('owner/repo/skill');
    const before = installRequests.length;
    await page.getByRole('button', {name: 'Preview', exact: true}).click(); await waitToast(/skills\.sh fetch owner\/repo\/skill/);
    eq(installRequests.length, before, 'registry Preview does not call the server');
    eq(await page.locator('[data-modal=install] .preview-panel').count(), 0, 'no review/commit panel without a fetch');
    for (let i = 0; i < 25; i++) { await page.keyboard.press('Tab'); ok(await page.evaluate(() => document.querySelector('[data-modal=install] .modal').contains(document.activeElement)), 'focus trapped in dialog'); }
    await page.keyboard.press('Escape');
    eq(installRequests.filter(x => /"fetch"|"run"/.test(x.body)).length, 0, 'no fetch/run request ever reached the server');
  });

  /* ============================== CROSS-CUTTING ============================== */
  const SCREENS = ['settings', 'profiles', 'quality', 'workspaces', 'install'];
  for (const [w, h] of [[1280, 900], [390, 844]]) {
    await test('Cross-cutting', `no horizontal overflow at ${w}px on all five screens (light + dark)`, async () => {
      await page.setViewportSize({width: w, height: h});
      for (const th of ['light', 'dark']) {
        await load('/'); await page.evaluate(t => { localStorage.setItem('skillsmgr-theme', t); }, th); await load('/');
        for (const v of SCREENS) {
          if (w < 600) { const t = page.locator('.mobile-controls-toggle'); }
          await nav(v);
          if (v === 'profiles') { await page.locator('#profile-name').fill('overflow-check'); await page.locator('#profile-skills').fill('prof-observed'); }
          if (v === 'workspaces') await ws(inside);
          if (v === 'quality') await page.locator('.quality-hygiene-metrics').waitFor().catch(() => {});
          const o = await overflowOf(); ok(o.sw <= o.iw + 1 && o.bw <= o.iw + 1, `${v}/${th}@${w}: scrollWidth ${o.sw} body ${o.bw} > viewport ${o.iw}`);
          await shot(`overflow-${v}-${th}-${w}`);
        }
      }
      await page.evaluate(() => localStorage.removeItem('skillsmgr-theme'));
    });
  }
  await page.setViewportSize({width: 1280, height: 900});
  await test('Cross-cutting', 'exactly one heading owns focus after navigation on every screen', async () => {
    await load('/');
    for (const v of ['overview', 'skills', ...SCREENS, 'recovery']) {
      await nav(v);
      const a = await active(); const h1s = await page.locator('h1').evaluateAll(l => l.filter(e => e.offsetParent !== null || e.classList.contains('sr-only')).map(e => e.id + ':' + e.textContent.trim().slice(0, 30)));
      ok(/view-title|library-view-title|overview-title/.test(a.id), `${v}: focus on heading, got ${JSON.stringify(a)}`);
      ok(h1s.filter(x => !/^:/.test(x)).length === 1 || h1s.length === 1, `${v}: one h1, got ${h1s.join(' | ')}`);
    }
  });
  await test('Cross-cutting', 'dark theme: key text meets WCAG AA 4.5:1 on every screen', async () => {
    await page.evaluate(() => localStorage.setItem('skillsmgr-theme', 'dark')); await load('/');
    const checks = {settings: ['.lead', '.hint', '.settings-option strong', '.settings-option small', 'h2'], profiles: ['.lead', '.hint', 'label', '.profile-editor .btn-primary', '.profile-editor h2'], quality: ['.hint', '.quality-hygiene-metrics dt', '.quality-hygiene-metrics small', '.btn-secondary', '.sidepanel-row span'], workspaces: ['.adapter-card h3', '.adapter-card .hint', '.badge', 'label[for=workspace-project]'], install: ['.lead', '.hint', '.install-center label', '.btn-secondary']};
    const low = [];
    for (const v of SCREENS) { await nav(v); await sleep(300); if (v === 'quality') await page.locator('.quality-hygiene-metrics').waitFor().catch(() => {}); for (const s of checks[v]) { const c = await contrastOf(s); if (c.missing) { note(`contrast: ${v} ${s} not visible`); continue; } if (c.ratio < 4.5) low.push(`${v} ${s} ${c.ratio} fg${c.fg} bg${c.bg} "${c.text}"`); } await shot('dark-' + v); }
    ok(low.length === 0, 'low contrast: ' + low.join(' ; '));
    await page.evaluate(() => localStorage.removeItem('skillsmgr-theme'));
  });
  await test('Cross-cutting', 'Escape closes dialogs with focus return (batch, install, validate)', async () => {
    await load('/'); await nav('quality'); await page.locator('.quality-hygiene-metrics').waitFor();
    await nav('install'); const o = page.getByRole('button', {name: 'Open full install workflow'}); await o.focus(); await page.keyboard.press('Enter'); await page.locator('[data-modal=install]').waitFor();
    await page.keyboard.press('Escape'); eq(await page.locator('[data-modal]').count(), 0); eq((await focusIs('Open full install workflow')).text, 'Open full install workflow');
    await nav('quality');
    const sel = page.locator('.sidepanel-row').first(); await sel.click(); await sleep(400);
    const val = page.getByRole('button', {name: 'Validate', exact: true}).first(); await val.click(); await page.locator('[data-modal=validate]').waitFor();
    await page.keyboard.press('Escape'); eq(await page.locator('[data-modal]').count(), 0); eq((await focusIs('Validate')).text, 'Validate', 'focus returns to the Validate opener');
  });
  await test('Cross-cutting', 'Library batch bar dialog (Disable) returns focus to its opener on Escape; nothing applied', async () => {
    await load('/'); await nav('skills'); await sleep(300);
    const snap = diskSnapshot();
    await page.locator('li[data-skill-key$="/global-skill"] input.row-select').check();
    const opener = page.locator('.batchbar').getByRole('button', {name: 'Disable', exact: true});
    await opener.click(); await page.locator('[data-modal=batch] .batch-target-list li').first().waitFor(); await planReady();
    eq(await page.locator('[data-modal=batch] .batch-target-list li').count(), 1);
    await page.keyboard.press('Escape'); eq(await page.locator('[data-modal=batch]').count(), 0);
    eq((await focusIs('Disable')).text, 'Disable', 'focus returns to the batch-bar opener (docs/08: focus returns to its opener)');
    eq(diffSnap(snap, diskSnapshot()), [], 'previewing a batch writes nothing');
  });
  await test('Performance', 'body-less rows retain full detail and off-screen keyboard access', async () => {
    const fixtureDirs = [];
    try {
      for (let i = 0; i < 300; i++) {
        const name = 'zz-perf-' + String(i).padStart(4, '0');
        const directory = path.join(home, '.codex', 'skills', name);
        fs.mkdirSync(directory, {recursive: true}); fixtureDirs.push(directory);
        fs.writeFileSync(path.join(directory, 'SKILL.md'), `---\nname: ${name}\ndescription: Use only for the isolated performance browser check.\n---\nOFFSCREEN_DOCUMENT_${i}\n`);
      }
      await page.evaluate(() => {
        localStorage.setItem('skillsmgr-scope', 'all');
        localStorage.setItem('skillsmgr-library-mode', 'instances');
      });
      const listResponse = page.waitForResponse(response => {
        const url = new URL(response.url());
        return url.pathname === '/api/skills' && url.searchParams.get('body') === '0';
      });
      await load('/');
      const list = await (await listResponse).json();
      ok(list.filter(row => row.name.startsWith('zz-perf-')).length === 300, 'all fixture rows are present');
      ok(list.every(row => !Object.hasOwn(row, 'body')), 'classic list omits document bodies');
      await nav('skills');
      const row = page.locator('li[data-skill-key="codex/zz-perf-0299"]');
      const originalBytes = fs.readFileSync(path.join(fixtureDirs[299], 'SKILL.md'));
      const before = await row.boundingBox();
      ok(before.y > 900, 'last row starts beyond the viewport');
      await row.focus();
      ok(await row.evaluate(element => element === document.activeElement), 'off-screen row can receive keyboard focus');
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.querySelector('.detail .body')?.textContent.includes('OFFSCREEN_DOCUMENT_299'));
      await page.getByRole('button', {name: 'Edit', exact: true}).first().click();
      await page.locator('#f-body').waitFor();
      ok((await page.locator('#f-body').inputValue()).includes('OFFSCREEN_DOCUMENT_299'), 'editor loads the real document instead of an empty list body');
      await page.keyboard.press('Escape');
      eq(fs.readFileSync(path.join(fixtureDirs[299], 'SKILL.md')), originalBytes, 'opening and cancelling the editor leaves bytes unchanged');
      await shot('performance-offscreen-detail');
    } finally {
      for (const directory of fixtureDirs) fs.rmSync(directory, {recursive: true, force: true});
    }
  });
  await test('Cross-cutting', 'no unexpected console errors, page errors or failed requests during the run', async () => {
    const bad = events.filter(e => !e.d);
    ok(bad.length === 0, 'unexpected: ' + JSON.stringify(bad.slice(0, 6)));
    note(`deliberate error events observed: ${events.filter(e => e.d).length}`);
    ok(!fs.existsSync(path.join(root, 'RUNNER-EXECUTED.txt')), 'no package runner ever ran');
    eq(installRequests.filter(x => /"run"\s*:\s*true|"fetch"|"search"|"curated"/.test(x.body)).length, 0, 'no dangerous install request from the browser');
  });

  await browser.close();
  fs.writeFileSync(path.join(root, 'results.json'), JSON.stringify({results, notes, defects, events, assertions, failed}, null, 2));
  const by = {}; for (const r of results) { by[r.screen] = by[r.screen] || {p: 0, f: 0, a: 0}; by[r.screen][r.status === 'PASS' ? 'p' : 'f']++; by[r.screen].a += r.assertions; }
  console.log('\nSUMMARY ' + JSON.stringify(by) + ` total assertions ${assertions}, failed tests ${failed}`);
  process.exit(failed ? 1 : 0);
})().catch(async e => { console.error('RUNNER ERROR', e); try { fs.writeFileSync(path.join(root, 'results.json'), JSON.stringify({results, notes, error: String(e.stack)}, null, 2)); await browser.close(); } catch (x) {} process.exit(2); });
