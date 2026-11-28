/* Optional developer-only browser checks; launched by run.py with isolated HOME/data. */
const {chromium, firefox} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = process.env.BROWSER_TEST_ROOT, base = process.env.BROWSER_TEST_BASE;
if (!root || !base) throw Error('Use run.py to create a safe isolated fixture');
if (new URL(base).hostname!=='127.0.0.1' || new URL(base).protocol!=='http:' || fs.readFileSync(path.join(root,'server-url.txt'),'utf8')!==base) throw Error('Use only the isolated loopback server started by run.py');
const home = process.env.BROWSER_TEST_HOME, results = [], exceptions = [];
const engine = process.env.BROWSER_TEST_ENGINE;
const headed = process.env.BROWSER_TEST_HEADED === '1';
let failed = 0, browser;
function record(name, status, detail='') { results.push({name, status, detail}); console.log(`${status} ${name}${detail ? ': '+detail : ''}`); }
async function test(name, fn) { if(process.env.BROWSER_TEST_FILTER && !name.includes(process.env.BROWSER_TEST_FILTER)) return; try { await fn(); record(name, 'PASS'); } catch (e) { failed++; record(name, 'FAIL', String(e.message)); } }
(async () => {
  if (engine === 'firefox') {
    browser = await firefox.launch({headless: !headed});
  } else if (engine === 'chromium') {
    browser = await chromium.launch({executablePath: process.env.CHROME_BIN, headless: !headed,
      args: headed ? ['--ozone-platform=x11'] : [], chromiumSandbox: true});
  } else {
    throw Error('Use run.py to select a browser engine');
  }
  const browserVersion = browser.version();
  console.log(`Browser: ${engine} ${browserVersion}`);
  const context = await browser.newContext({viewport:{width:1280,height:900}});
  const page = await context.newPage(); page.setDefaultTimeout(5000);
  page.on('pageerror', e => exceptions.push(e.message));
  let navigation = 0;
  async function go(route, target = page) {
    await target.goto(base + '/?fixture-step=' + (++navigation) + '#/' + route);
    await target.locator('main').waitFor();
    await target.waitForLoadState('networkidle');
    if (route.startsWith('skill/')) await target.locator('.jf-reader-heading').waitFor();
  }
  async function theme(t) { for (let i=0;i<3 && await page.locator('html').getAttribute('data-theme')!==t;i++) { const button = page.locator('.themebtn:visible').first(); if (await button.count()) await button.click(); else { await page.keyboard.press('Control+k'); await page.getByRole('combobox', {name:'Search skills, actions and pages'}).fill('Switch theme'); await page.getByRole('option', {name:/Switch theme/}).click(); } } assert.equal(await page.locator('html').getAttribute('data-theme'),t); }
  const file=(scope,name='same-everywhere')=>path.join(home,scope,'skills',name,'SKILL.md');
  const libraryFile = name => path.join(root, 'data', 'jackfield', 'skills', name, 'SKILL.md');
  const trashScreen = page.locator('.jf-trash-screen');
  const trashList = trashScreen.locator('section[aria-labelledby="rec-trash"]');
  const restoreButton = (name, place, copy = '') => trashList.getByRole('button', {
    name:`Review restore for ${name} in ${place}${copy ? ', ' + copy : ''}`, exact:true,
  });
  const attention = page.locator('.jf-attention');
  const attentionHeading = attention.locator('#attention-detail-heading');
  const attentionItem = id => attention.locator(`[data-attention-id=${JSON.stringify(id)}]`);
  const attentionNav = page.locator('.tabs a[href="#/attention"]');
  const attentionWrites = request => request.method() === 'POST' &&
    ['/api/sync', '/api/batch/execute'].includes(new URL(request.url()).pathname);
  async function openAttention(id) {
    await go(id ? 'attention?item=' + encodeURIComponent(id) : 'attention');
    await attention.getByRole('heading', {name:'Needs attention', exact:true}).waitFor();
    if (id) await attentionHeading.waitFor();
  }
  async function expectAttentionCount(count) {
    if (count) await attention.getByRole('heading', {name:`To fix · ${count}`, exact:true}).waitFor();
    assert.equal(await attentionNav.getAttribute('aria-label'), count ? `Needs attention, ${count} ${count === 1 ? 'item' : 'items'}` : null);
  }
  async function turnOffCodexFromReader() {
    await page.getByRole('button', {name:'same-everywhere in Codex: On'}).click();
    await page.locator('.jf-panel').getByRole('button', {name:/^Turn off/}).click();
  }
  await test('Geometry Doctor chevron', async () => {
    await go('advanced/doctor');
    await page.getByRole('button', {name:'Run Doctor', exact:true}).click();
    const report = page.locator('.tp-more > summary').filter({hasText:'Full report'});
    await report.waitFor();
    assert.equal(await report.evaluate(e => getComputedStyle(e).display), 'flex');
    const icon = await report.evaluate(e => { const s=getComputedStyle(e, '::before'); return {content:s.content, mask:s.maskImage, width:s.width, height:s.height}; });
    assert.notEqual(icon.content, 'none'); assert.notEqual(icon.mask, 'none');
    assert.equal(icon.width, '14px'); assert.equal(icon.height, '14px');
    await page.setViewportSize({width:390,height:900});
    assert((await report.boundingBox()).height >= 44);
    await report.click();
    await page.waitForFunction(e => getComputedStyle(e, '::before').transform === 'matrix(0, 1, -1, 0, 0, 0)', await report.elementHandle());
    await page.setViewportSize({width:1280,height:900});
  });
  await test('Geometry New AI doorway', async () => {
    await go('new');
    const ai = page.getByRole('button', {name:'Create with AI or add metadata'});
    await ai.waitFor(); assert(await ai.locator('svg.jf-chevron').isVisible());
    const dialog = page.locator('[role="dialog"]');
    await ai.click();
    await dialog.waitFor();
    await page.keyboard.press('Escape');
    await dialog.waitFor({state:'hidden'});
  });
  await test('Geometry phone checkbox row', async () => {
    await go('skills');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    for (const width of [390, 600]) {
      await page.setViewportSize({width, height:900});
      const row = page.locator('.jf-grid tbody tr').first(); await row.waitFor();
      const checkbox = row.locator('.jf-grid-checkbox'), name = row.locator('.jf-grid-skill > button');
      const cb = await checkbox.boundingBox(), nb = await name.boundingBox();
      assert(cb.width >= 44 && cb.height >= 44); assert(Math.abs(cb.y - nb.y) < 8, 'checkbox and skill name must share a row');
      assert(cb.x + cb.width <= nb.x + 1, 'checkbox and name touch areas overlap');
      const input=checkbox.locator('input'), before=await input.isChecked(); await checkbox.click({position:{x:5,y:5}}); assert.notEqual(await input.isChecked(),before);
    }
    await page.setViewportSize({width:1280,height:900});
  });
  await test('Geometry phone skill targets', async () => {
    const viewport = page.viewportSize();
    const sites = [
      ['skill/same-everywhere', page.locator('.jf-reader-details summary, .jf-reader-actions button, .jf-reader-details a[href="#/trash"]').filter({visible:true})],
      ['skill/split-even', page.getByRole('button', {name:'Review a different copy', exact:true})],
      ['skills/same-everywhere/why', page.getByRole('button', {name:'Check again', exact:true})],
    ];
    try {
      for (const [route, targets] of sites) {
        await go(route);
        for (const width of [390, 600]) {
          await page.setViewportSize({width, height:900});
          await targets.first().waitFor();
          for (const target of await targets.all()) {
            const box = await target.boundingBox();
            assert(box.height >= 44 && box.width >= 44, `small target at ${width}px: ${await target.innerText()}`);
          }
        }
      }
    } finally {
      await page.setViewportSize(viewport);
    }
  });
  await test('Geometry Skill panel disclosures align', async () => {
    await go('skill/same-everywhere');
    const details=page.locator('.jf-reader-details'); await details.waitFor();
    const headings=details.locator('summary');
    const boxes=await Promise.all((await headings.all()).map(el=>el.boundingBox()));
    assert(boxes.length >= 3); assert(boxes.every(box => Math.abs(box.x-boxes[0].x) < 1), 'details summaries have different left edges');
  });
  await test('Geometry welcome columns align', async () => {
    for (const width of [390, 1440]) {
      const first=await browser.newContext({viewport:{width,height:900}}), welcome=await first.newPage();
      try {
        await welcome.goto(base+'/#/skills'); await welcome.locator('.jf-welcome-agent').first().waitFor();
        const rows=welcome.locator('.jf-welcome-agent'); assert((await rows.count()) >= 2);
        const coords=await rows.evaluateAll(items=>items.map(row=>{const a=row.children[1].getBoundingClientRect(), b=row.children[2].getBoundingClientRect();return {count:a.x,path:b.x,pathWidth:b.width,rowWidth:row.getBoundingClientRect().width};}));
        assert(coords.every(item=>Math.abs(item.count-coords[0].count)<1 && Math.abs(item.path-coords[0].path)<1), 'welcome columns differ');
        if (width === 390) assert(coords.every(item=>item.pathWidth >= item.rowWidth - 1), 'phone paths need a full row');
        assert.equal(await welcome.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      } finally { await first.close(); }
    }
  });
  await test('Paper disclosure chevrons keep their size, rotation and reduced motion', async () => {
    const checkDisclosure = async (summary, reduced) => {
      await summary.waitFor();
      if (await summary.evaluate(element => element.parentElement.open)) {
        await summary.click();
        await page.waitForFunction(element => getComputedStyle(element, '::before').transform === 'none', await summary.elementHandle());
      }
      const style = () => summary.evaluate(element => {
        const {width, height, transform, transitionDuration, maskImage} = getComputedStyle(element, '::before');
        return {width, height, transform, transitionDuration, maskImage};
      });
      const closed = await style();
      assert.equal(closed.width, '14px');
      assert.equal(closed.height, '14px');
      assert.equal(closed.transform, 'none');
      assert.notEqual(closed.maskImage, 'none');
      const duration = Number.parseFloat(closed.transitionDuration);
      if (reduced) assert(duration < 0.001);
      else assert.equal(duration, 0.12);
      await summary.click();
      await page.waitForFunction(element => getComputedStyle(element, '::before').transform === 'matrix(0, 1, -1, 0, 0, 0)', await summary.elementHandle());
    };
    const checkPreferences = async (check) => {
      for (const mode of ['light', 'dark']) {
        for (const reduced of [false, true]) {
          await page.emulateMedia({colorScheme:mode, reducedMotion:reduced ? 'reduce' : 'no-preference'});
          await theme(mode);
          await check(reduced);
        }
      }
    };
    try {
      await go('skill/same-everywhere');
      await checkPreferences(reduced => checkDisclosure(page.locator('.native-settings > summary'), reduced));
      await page.getByRole('button', {name:'Edit', exact:true}).click();
      await checkPreferences(reduced => checkDisclosure(page.locator('.instance-metadata > summary:visible'), reduced));
      await go('trash');
      await checkPreferences(reduced => checkDisclosure(page.locator('summary').filter({hasText:'History and text snapshots'}), reduced));
      await go('tools/quality');
      await checkPreferences(async reduced => {
        const finding = page.locator('.tp-findings > li > details > summary').first();
        await finding.waitFor();
        assert.equal(await finding.evaluate(element => getComputedStyle(element, '::before').content), 'none');
        await checkDisclosure(page.locator('.v2-tool-nav-group > summary').last(), reduced);
      });
      await go('settings');
      await checkPreferences(reduced => checkDisclosure(page.locator('.v2-tool-nav-group > summary').first(), reduced));
    } finally {
      await page.emulateMedia({colorScheme:null, reducedMotion:null});
      await theme('light');
    }
  });
  await test('Paper first launch shows the scanning state, agent folders and next action (F9)', async () => {
    for (const colorScheme of ['light', 'dark']) {
      const first = await browser.newContext({colorScheme});
      const welcome = await first.newPage();
      let release;
      const pending = new Promise(resolve => { release = resolve; });
      await welcome.route('**/api/scopes', async route => { await pending; await route.continue(); });
      try {
        welcome.on('pageerror', error => exceptions.push(error.message));
        await welcome.goto(base + '/#/skills');
        await welcome.getByRole('heading', {name:'Looking for your agents…'}).waitFor({timeout:5000});
        release();
        await welcome.getByRole('heading', {name:/Found 4 agents and \d+ skills/}).waitFor({timeout:5000});
        const paths = await welcome.locator('.jf-welcome-path').allTextContents();
        assert.equal(paths.length, 4);
        assert(paths.every(path => path.trim().length > 0));
        assert(paths.some(path => path.endsWith('.codex/skills')));
        await welcome.getByText(/^Tip:/).waitFor();
        const show = welcome.getByRole('button', {name:'Show my skills', exact:true});
        assert(await show.evaluate(element => element.classList.contains('sm-btn--accent')));
        await show.click();
        await welcome.getByRole('grid', {name:'Skills table'}).waitFor();
      } finally {
        release();
        await first.close();
      }
    }
  });
  await test('Default entry serves the interface at / with query and hash intact',async()=>{await page.goto(base+'/?window=claude#/skills');await page.waitForLoadState('networkidle');assert.equal(page.url(),base+'/?window=claude#/skills');const show=page.getByRole('button',{name:'Show my skills'});if(await show.isVisible())await show.click();assert(await page.getByRole('grid',{name:'Skills table'}).locator('tbody tr').count()>0);});
  await test('Retired overview and map links replace history with the Skills table', async () => {
    for (const old of ['#/home', '#/map', '#/skills?view=agents', '#/skills?view=map']) {
      await go('trash');
      await page.evaluate(hash => { location.hash = hash; }, old);
      await page.waitForURL(url => url.hash === '#/skills');
      const welcome = page.getByRole('button', {name:'Show my skills'});
      if (await welcome.isVisible()) await welcome.click();
      await page.getByRole('grid', {name:'Skills table'}).waitFor();
      await page.goBack();
      await page.waitForURL(url => url.hash === '#/trash');
    }
    await page.goto(base+'/?fixture-step='+(++navigation)+'#/skills?view=map&q=sole-copy');
    await page.waitForURL(url => url.hash === '#/skills?q=sole-copy');
    assert.equal(await page.getByRole('searchbox', {name:'Filter skills'}).inputValue(), 'sole-copy');
  });
  await test('Paper follow-up uses one project name and mark across screens', async () => {
    const workspace = path.join(home, 'workspace');
    const project = path.join(workspace, '.claude');
    const folder = path.join(project, 'skills', 'majority-minor');
    const viewport = page.viewportSize();
    const tracking = base + '/api/tracking';
    const readTracking = async () => (await page.request.get(tracking)).json();
    const saveTracking = async (settings) => {
      const response = await page.request.put(tracking, {headers:{Origin:base}, data:settings});
      assert.equal(response.status(), 200, await response.text());
    };
    const previous = (await readTracking()).settings;
    let showingProject = false;
    fs.mkdirSync(folder, {recursive:true});
    fs.copyFileSync(file('.codex', 'majority-minor'), path.join(folder, 'SKILL.md'));
    try {
      await saveTracking({...previous, projects:{
        folders:[...new Set([...previous.projects.folders, workspace])], showing:workspace,
      }});
      showingProject = true;
      await go('skills?q=majority-minor');
      const column = page.getByRole('columnheader', {name:/This project/});
      await column.locator('[data-a="PJ"]').waitFor();
      await go('skill/majority-minor');
      const picker = page.locator('.jf-reader-source select');
      await picker.waitFor();
      const options = await picker.locator('option').allTextContents();
      assert(options.some(option => option.startsWith('This project — ') && option.endsWith(folder)), JSON.stringify(options));
      for (const width of [390, 1440]) {
        await page.setViewportSize({width, height:900});
        assert(await picker.evaluate(select => select.getBoundingClientRect().right <=
          select.closest('article').getBoundingClientRect().right + 1), `copy picker exceeds the document at ${width}px`);
      }
      await page.setViewportSize(viewport);
      await page.locator('.jf-reader-places .jf-agent').filter({hasText:'This project'}).locator('[data-a="PJ"]').waitFor();
      await go('skills/majority-minor/why');
      await page.locator('.jf-why-grid .jf-agent').filter({hasText:'This project'}).locator('[data-a="PJ"]').waitFor();
      await go('new');
      await page.locator('.jf-editor-place').filter({hasText:'This project'}).locator('[data-a="PJ"]').waitFor();
      await openAttention('majority-minor:project:different');
      await attention.locator('.jf-attention-detail .jf-agent').filter({hasText:'This project'}).locator('[data-a="PJ"]').waitFor();
    } finally {
      await page.setViewportSize(viewport);
      fs.rmSync(folder, {recursive:true, force:true});
      fs.rmdirSync(path.join(project, 'skills'));
      fs.rmdirSync(project);
      if (showingProject) await saveTracking({...previous, revision:(await readTracking()).revision});
    }
  });
  await test('Global search opens a library skill when no agent is available', async () => {
    await page.route('**/api/scopes', route => route.fulfill({json:[]}));
    try {
      await go('skills');
      const welcome = page.getByRole('button', {name:'Show my skills'});
      if (await welcome.isVisible()) await welcome.click();
      await page.getByRole('heading', {name:/No agents are tracked|No agent skills found yet/}).waitFor();
      await page.getByRole('button', {name:'Search skills, actions and pages'}).click();
      await page.getByRole('combobox', {name:'Search skills, actions and pages'}).fill('library-fixture');
      await page.getByRole('option', {name:/library-fixture/}).first().click();
      await page.waitForURL(url => url.hash === '#/skills/library-fixture');
      await page.locator('.jf-reader-heading').waitFor();
    } finally { await page.unrouteAll({behavior:'wait'}); }
  });
  await test('Skills place and sort controls handle unknown places and popup focus', async () => {
    const endpoint = '**/api/tracking';
    await page.route(endpoint, async route => {
      const response = await route.fetch();
      const data = await response.json();
      data.projects = [{path:home + '/workspace', status:'ok'}];
      await route.fulfill({response, json:data});
    });
    try {
      await page.setViewportSize({width:1280,height:900});
      await go('skills?agent=missing-place');
      const welcome=page.getByRole('button',{name:'Show my skills'});
      if (await welcome.isVisible()) await welcome.click();
      const grid=page.getByRole('grid',{name:'Skills table'});
      assert((await grid.locator('thead th').count()) > 2);
      const place=page.getByText('All places',{exact:true}).first();
      await place.click();
      await page.getByRole('group',{name:'Place'}).getByRole('button',{name:'Codex',exact:true}).click();
      assert.equal(await grid.locator('thead th').count(), 2);
      assert((await page.url()).includes('agent=codex'));
      await page.getByLabel('Place: Codex').click();
      await page.getByRole('group',{name:'Place'}).getByRole('button',{name:'All places'}).click();
      if (await welcome.isVisible()) await welcome.click();
      const sort=page.locator('.jf-toolbar-picker').nth(1).locator('summary');
      await sort.click();
      await page.getByRole('group',{name:'Sort'}).getByRole('button',{name:'Largest first'}).click();
      assert(await sort.isVisible());
      assert(await sort.evaluate(el=>el===document.activeElement));
      await sort.press('Enter');
      await page.keyboard.press('Escape');
      assert(!(await page.locator('.jf-toolbar-picker[open]').count()));
      await sort.press('Enter');
      await page.keyboard.press('Tab');
      const alphabetical = page.getByRole('group',{name:'Sort'}).getByRole('button',{name:'A to Z'});
      assert(await alphabetical.evaluate(button => button === document.activeElement));
      await page.keyboard.press('Enter');
      assert.equal(await sort.getAttribute('aria-label'), 'Sort: A to Z');
      const options=page.getByRole('button',{name:'Codex options'});
      await options.click();
      const choice=page.getByRole('button',{name:'Stop tracking Codex…'});
      await choice.waitFor();
      await choice.evaluate(el => el.dispatchEvent(new FocusEvent('focusout',{bubbles:true,relatedTarget:null})));
      assert(await choice.isVisible());
      await page.getByRole('button',{name:'OpenCode options'}).focus();
      assert.equal(await choice.count(),0);
      await options.click();
      await options.focus();
      await options.press('Escape');
      assert.equal(await choice.count(),0);
      await options.click();
      await page.getByRole('searchbox',{name:'Filter skills'}).click();
      assert.equal(await choice.count(),0);
      const picker=page.locator('.jf-project-picker');
      await picker.locator('summary').click();
      const none=picker.getByRole('button',{name:'None',exact:true});
      await none.evaluate(el => el.dispatchEvent(new FocusEvent('focusout',{bubbles:true,relatedTarget:null})));
      assert(await none.isVisible());
      await page.getByRole('searchbox',{name:'Filter skills'}).click();
      assert.equal(await picker.getAttribute('open'),null);
      await page.setViewportSize({width:390,height:844});
      await go('skills?agent=missing-place');
      assert(await page.getByRole('combobox',{name:'Showing place'}).inputValue());
      assert.equal(await page.locator('.jf-grid tbody tr').first().locator('td').count(),1);
      await page.getByRole('button',{name:'Filter and sort'}).click();
      const phoneSort=page.locator('.jf-sort-picker summary');
      await phoneSort.click();
      assert(await page.getByRole('group',{name:'Sort'}).evaluate(el => {
        const rect=el.getBoundingClientRect(); return rect.left>=0 && rect.right<=innerWidth;
      }));
    } finally {
      await page.unroute(endpoint);
      await page.setViewportSize({width:1280,height:900});
    }
  });
  await test('Four primary places navigate and identify the current page', async () => {
    try {
      for (const width of [1280, 390]) {
        await page.setViewportSize({width, height:900});
        await go('skills');
        const nav = page.locator(width === 1280 ? '.tabs' : '.bottomnav');
        const places = [['Skills', '#/skills'], ['Needs attention', '#/attention'],
          ['Trash & backups', '#/trash'], ['Advanced', '#/advanced']];
        assert.equal(await nav.locator('a').count(), places.length);
        for (const [name, hash] of places) {
          const link = nav.locator(`a[href="${hash}"]`);
          assert.match(await link.innerText(), new RegExp(name));
          await link.click();
          await page.waitForURL(url => url.hash === hash);
          await page.waitForFunction(selector => document.querySelector(selector)?.getAttribute('aria-current') === 'page',
            `${width === 1280 ? '.tabs' : '.bottomnav'} a[href="${hash}"]`);
        }
      }
    } finally { await page.setViewportSize({width:1280, height:900}); }
  });
  await test('Skills notices an external file change and highlights the refreshed row (F8)', async () => {
    const name = 'phase-four-disk-change';
    const active = file('.claude', name), disabled = active + '.disabled';
    const folder = path.dirname(active);
    const document = `---\nname: ${name}\ndescription: Exercise a disk change in the browser.\n---\n# Original instructions\n`;
    assert(!fs.existsSync(folder));
    const view = await browser.newContext({viewport:{width:1440, height:900}});
    try {
      fs.mkdirSync(folder);
      fs.writeFileSync(active, document);
      const watcher = await view.newPage();
      watcher.setDefaultTimeout(5000);
      watcher.on('pageerror', error => exceptions.push(error.message));
      await watcher.clock.install();
      await watcher.goto(base + '/#/skills');
      const welcome = watcher.getByRole('button', {name:'Show my skills', exact:true});
      const on = watcher.getByRole('button', {name:`${name} in Claude Code: On`, exact:true});
      await welcome.or(on).first().waitFor();
      if (await welcome.isVisible()) await welcome.click();
      await on.waitFor();

      fs.renameSync(active, disabled);
      await watcher.bringToFront();
      await watcher.clock.fastForward(15_001);
      await watcher.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
      const notice = watcher.getByRole('region', {name:/^1 skill changed on disk/});
      await notice.waitFor();
      assert(await on.isVisible());
      await notice.getByRole('button', {name:'Refresh', exact:true}).click();
      const off = watcher.getByRole('button', {name:`${name} in Claude Code: Off`, exact:true});
      await off.waitFor();
      const highlight = watcher.locator('tr.is-changed').filter({has:off});
      await highlight.waitFor();
      await notice.waitFor({state:'hidden'});
      await watcher.clock.fastForward(3501);
      await highlight.waitFor({state:'hidden'});
      assert(await off.isVisible());
      assert.equal(fs.readFileSync(disabled, 'utf8'), document);
    } finally {
      await view.close();
      fs.rmSync(folder, {recursive:true, force:true});
    }
  });
  await test('Canonical routes replace legacy history and retain query strings', async () => {
    await go('skills');
    await page.evaluate(() => { location.hash = '#/home?fixture=kept'; });
    await page.waitForURL(url => url.hash === '#/skills?fixture=kept');
    await page.goBack();
    await page.waitForURL(url => url.hash === '#/skills');
    await page.evaluate(() => { location.hash = '#/skill/sole-copy?view=file'; });
    await page.waitForURL(url => url.hash === '#/skills/sole-copy?view=file');
    await page.locator('#h1').getByText('sole-copy').waitFor();
    await page.evaluate(() => { location.hash = '#/new'; });
    await page.getByRole('heading', {name:'New skill', exact:true}).waitFor();
    await page.getByRole('button', {name:'Cancel', exact:true}).click();
  });
  await test('Direct editor route survives reload', async () => {
    await page.goto(base + '/#/skills/sole-copy/edit');
    await page.locator('.ed-area').waitFor();
    await page.reload();
    await page.locator('.ed-area').waitFor();
    assert.equal(new URL(page.url()).hash, '#/skills/sole-copy/edit');
    assert.match(await page.locator('.ed-area').inputValue(), /single fixture copy/);
  });
  await test('Editor leaves differing copies unchecked and stops on an external change (F5)', async () => {
    const name = 'majority-minor';
    const codex = file('.codex', name), claude = file('.claude', name);
    const originalCodex = fs.readFileSync(codex), originalClaude = fs.readFileSync(claude);
    try {
      await go('skill/' + name);
      await page.getByRole('button', {name:'Edit', exact:true}).click();
      const places = page.getByRole('complementary', {name:'Save to'});
      const codexRow = places.getByRole('checkbox', {name:/Codex/});
      assert.equal(await codexRow.isChecked(), false);
      assert.match(await codexRow.locator('..').innerText(), /Different copy/);
      for (const row of await places.getByRole('checkbox').all()) {
        if (await row.isChecked()) await row.uncheck();
      }
      await codexRow.check();
      await page.locator('#ed-desc').fill('A newly reviewed description.');
      await page.locator('#ed-desc').press('Control+s');
      await page.locator('.jf-reader-heading').getByRole('button',{name:'File text'}).waitFor();
      assert.match(fs.readFileSync(codex, 'utf8'), /A newly reviewed description[\s\S]*Majority text/);
      assert.deepEqual(fs.readFileSync(claude), originalClaude);
      await page.getByRole('button',{name:'Undo',exact:true}).click();
      await page.locator('.toast').getByText('Undone',{exact:true}).waitFor();
      assert.deepEqual(fs.readFileSync(codex), originalCodex);

      await page.getByRole('button', {name:'Edit', exact:true}).click();
      await page.locator('#ed-desc').fill('Preserve this draft.');
      const target = url => url.pathname === '/api/skills/' + name && url.searchParams.get('scope') === 'claude-code';
      const editBeforeWrite = route => {
        if (route.request().method() === 'PATCH') {
          fs.writeFileSync(claude, Buffer.concat([originalClaude, Buffer.from('External edit.\n')]));
        }
        return route.continue();
      };
      await page.route(target, editBeforeWrite);
      try {
        await page.locator('#ed-desc').press('Control+s');
        await page.locator('.jf-editor').getByRole('alert').getByText(/changed on disk/i).waitFor();
      } finally { await page.unroute(target, editBeforeWrite); }
      assert.equal(await page.locator('#ed-desc').inputValue(), 'Preserve this draft.');
      assert.match(fs.readFileSync(claude, 'utf8'), /External edit/);
      await page.getByRole('button', {name:'Cancel', exact:true}).click();
      await page.getByRole('button', {name:'Discard changes', exact:true}).click();
    } finally {
      fs.writeFileSync(codex, originalCodex);
      fs.writeFileSync(claude, originalClaude);
    }
  });
  for (const changeAfterSave of [false, true]) {
    const outcome = changeAfterSave ? 'Undo preserves a changed supporting file' : 'Undo restores the source and removes the added copy';
    await test('Editor adds a missing copy and ' + outcome, async () => {
      const name = changeAfterSave ? 'phase-three-editor-guard' : 'phase-three-editor-add';
      const source = file('.claude', name), target = file('.codex', name);
      const companion = 'references/café.txt';
      const sourceCompanion = path.join(path.dirname(source), companion);
      const targetCompanion = path.join(path.dirname(target), companion);
      const original = Buffer.from(`---\nname: ${name}\ndescription: Original description.\n---\n# Original instructions\n`);
      const notes = Buffer.from('Original companion notes\r\n');
      const newDescription = 'Use this skill to review an edited draft.';
      const newBody = '# Revised instructions\n\nReview the draft before publishing.\n';
      assert(!fs.existsSync(path.dirname(source)) && !fs.existsSync(path.dirname(target)));
      try {
        fs.mkdirSync(path.dirname(sourceCompanion), {recursive:true});
        fs.writeFileSync(source, original);
        fs.writeFileSync(sourceCompanion, notes);
        await go('skill/' + name);
        await page.getByRole('button', {name:'Edit', exact:true}).click();
        const places = page.getByRole('complementary', {name:'Save to'});
        const codex = places.getByRole('checkbox', {name:/Codex/});
        assert(await places.getByRole('checkbox', {name:/Claude Code/}).isChecked());
        assert.equal(await codex.isChecked(), false);
        await codex.locator('..').getByText('Not here', {exact:true}).waitFor();
        await codex.locator('..').getByText(/No copy here/).waitFor();
        const editor = page.locator('.jf-editor');
        await editor.getByLabel('Description', {exact:true}).fill(newDescription);
        await editor.getByLabel('Instructions', {exact:true}).fill(newBody);
        await editor.getByRole('button', {name:'Save to 1 place', exact:true}).waitFor();
        await codex.check();
        await codex.locator('..').getByText('A new copy will be added here.', {exact:true}).waitFor();
        assert(!fs.existsSync(path.dirname(target)), 'selecting a place should not create the copy');
        await editor.getByRole('button', {name:'Save to 2 places', exact:true}).click();
        const notice = page.locator('.toast').filter({hasText:`${name} saved to 2 places.`});
        const undo = notice.getByRole('button', {name:'Undo', exact:true});
        await undo.waitFor();
        const saved = fs.readFileSync(source);
        assert(saved.includes(newDescription) && saved.includes(newBody.trim()));
        assert.deepEqual(fs.readFileSync(target), saved);
        assert.deepEqual(fs.readFileSync(sourceCompanion), notes);
        assert.deepEqual(fs.readFileSync(targetCompanion), notes);
        assert(!fs.existsSync(file('.config/opencode', name)), 'unselected place should remain empty');

        const changedNotes = Buffer.from('Edited outside Jackfield after Save.\n');
        if (changeAfterSave) fs.writeFileSync(targetCompanion, changedNotes);
        await undo.click();
        if (changeAfterSave) {
          await page.locator('.toast').getByText(/couldn.t undo/i).waitFor();
          assert.deepEqual(fs.readFileSync(target), saved);
          assert.deepEqual(fs.readFileSync(targetCompanion), changedNotes);
        } else {
          await page.locator('.toast').getByText('Undone', {exact:true}).waitFor();
          assert(!fs.existsSync(path.dirname(target)), 'Undo should remove the added folder from the place');
          const trash = await page.request.get(base + '/api/trash?scope=codex');
          assert(trash.ok());
          const moved = (await trash.json()).find(entry => entry.name === name)?.trash_path;
          assert(moved, 'Undo should move the added folder to Trash');
          assert.deepEqual(fs.readFileSync(path.join(moved, companion)), notes);
        }
        assert.deepEqual(fs.readFileSync(source), original);
        assert.deepEqual(fs.readFileSync(sourceCompanion), notes);
      } finally {
        fs.rmSync(path.dirname(source), {recursive:true, force:true});
        fs.rmSync(path.dirname(target), {recursive:true, force:true});
      }
    });
  }
  await test('New skill draft survives Back, Keep editing and explicit Cancel', async () => {
    await go('skills');
    await page.evaluate(() => { location.hash = '#/new'; });
    const create = page.locator('.jf-create');
    await create.getByLabel('Name', {exact:true}).fill('draft-browser-test');
    await create.getByLabel('Instructions', {exact:true}).fill('Draft instructions retained.');
    await page.goBack();
    const discard = page.getByRole('dialog', {name:/Discard/});
    await discard.waitFor();
    await discard.getByRole('button', {name:'Keep editing'}).click();
    await create.waitFor();
    assert.equal(await create.getByLabel('Name', {exact:true}).inputValue(), 'draft-browser-test');
    assert.equal(await create.getByLabel('Instructions', {exact:true}).inputValue(), 'Draft instructions retained.');
    await create.getByLabel('Instructions', {exact:true}).fill('Still editable after Back.');
    await create.getByRole('button', {name:'Cancel', exact:true}).click();
    await discard.waitFor();
    await discard.getByRole('button', {name:'Keep editing'}).click();
    assert.equal(await create.getByLabel('Instructions', {exact:true}).inputValue(), 'Still editable after Back.');
    await create.getByRole('button', {name:'Cancel', exact:true}).click();
    await discard.getByRole('button', {name:/Discard/}).click();
    await page.waitForURL(url => url.hash === '#/skills');
    await create.waitFor({state:'hidden'});
  });
  await test('Batch 2 New skill protects instructions and formats errors', async () => {
    const list = url => url.pathname === '/api/templates';
    const detail = url => url.pathname === '/api/templates/fixture';
    const listHandler = route => route.fulfill({json:{templates:['fixture']}});
    const detailHandler = route => route.fulfill({json:{body:'# Stored fixture'}});
    await page.route(list, listHandler); await page.route(detail, detailHandler);
    try {
      await go('new');
      const create = page.locator('.jf-create'), body = create.getByLabel('Instructions', {exact:true});
      await create.getByRole('button', {name:'Checklist', exact:true}).click();
      assert.match(await body.inputValue(), /Checklist/);
      await body.fill('Keep my instructions');
      await create.getByRole('button', {name:'Blank', exact:true}).click();
      let guard = create.getByRole('group', {name:'Replace instructions?'});
      await guard.getByRole('button', {name:'Keep editing'}).click();
      assert.equal(await body.inputValue(), 'Keep my instructions');
      const select = create.getByLabel('Stored template');
      await select.selectOption('fixture');
      await guard.getByRole('button', {name:'Keep editing'}).click();
      assert.equal(await select.inputValue(), '');
      await select.selectOption('fixture');
      await guard.getByRole('button', {name:'Replace instructions'}).click();
      await page.waitForFunction(() => document.querySelector('#nf-body').value === '# Stored fixture');
      await body.fill('Changed again');
      await create.getByRole('button', {name:'Blank', exact:true}).click();
      await guard.getByRole('button', {name:'Replace instructions'}).click();
      assert.equal(await body.inputValue(), '# {name}\n');
      const preview = url => url.pathname === '/api/skills' && url.searchParams.has('preview');
      const fail = route => route.fulfill({status:500,json:{error:'PermissionError /private/fixture/secret'}});
      await page.route(preview, fail);
      try {
        await create.getByLabel('Name', {exact:true}).fill('error-test');
        await create.getByLabel('What it does and when to use it').fill('Use to test errors.');
        await create.getByText(/The operation could not be completed/).waitFor();
        assert.doesNotMatch(await create.innerText(), /PermissionError|\/private\/fixture/);
      } finally { await page.unroute(preview, fail); }
      await create.getByRole('button', {name:'Retry preview'}).click();
      const button = create.getByRole('button', {name:'Create in 1 place'});
      await page.waitForFunction(el => !el.disabled, await button.elementHandle());
      const write = url => url.pathname === '/api/skills' && url.searchParams.has('scope');
      const failWrite = route => route.request().method() === 'POST' ? fail(route) : route.continue();
      await page.route(write, failWrite);
      try {
        await button.click();
        await create.getByRole('group', {name:'Add it to'}).getByText(/The operation could not be completed/).waitFor();
        assert.doesNotMatch(await create.innerText(), /PermissionError|\/private\/fixture/);
      } finally { await page.unroute(write, failWrite); }
    } finally { await page.unroute(list, listHandler); await page.unroute(detail, detailHandler); }
  });
  await test('Batch 2 starter selection cancels an earlier pending template', async () => {
    const list = url => url.pathname === '/api/templates';
    const detail = url => url.pathname === '/api/templates/slow-fixture';
    let release, started;
    const gate = new Promise(resolve => { release = resolve; });
    const requested = new Promise(resolve => { started = resolve; });
    const listHandler = route => route.fulfill({json:{templates:['slow-fixture']}});
    const detailHandler = async route => { started(); await gate; await route.fulfill({json:{body:'# Late template'}}); };
    await page.route(list, listHandler); await page.route(detail, detailHandler);
    try {
      await go('new');
      const create = page.locator('.jf-create'), body = create.getByLabel('Instructions', {exact:true});
      await body.fill('Keep this draft');
      await create.getByLabel('Stored template').selectOption('slow-fixture');
      const guard = create.getByRole('group', {name:'Replace instructions?'});
      await guard.getByRole('button', {name:'Replace instructions'}).click();
      await requested;
      await create.getByRole('button', {name:'Checklist', exact:true}).click();
      await guard.getByRole('button', {name:'Keep editing'}).click();
      release();
      await page.waitForResponse(r => new URL(r.url()).pathname === '/api/templates/slow-fixture');
      assert.equal(await body.inputValue(), 'Keep this draft');
      assert(await body.isEnabled());
      assert.equal(await create.getByLabel('Stored template').inputValue(), '');
    } finally { release(); await page.unroute(list, listHandler); await page.unroute(detail, detailHandler); }
  });
  await test('Batch 2 default template and failed replacement preserve the draft', async () => {
    const list = url => url.pathname === '/api/templates';
    const detail = url => url.pathname.startsWith('/api/templates/');
    const listHandler = route => route.fulfill({json:{templates:['default-fixture','failed-fixture']}});
    const detailHandler = route => new URL(route.request().url()).pathname.endsWith('/default-fixture')
      ? route.fulfill({json:{body:'# Default template'}})
      : route.fulfill({status:500,json:{error:'Fixture read failed'}});
    await page.route(list, listHandler); await page.route(detail, detailHandler);
    try {
      await go('new?template=default-fixture');
      const create = page.locator('.jf-create'), body = create.getByLabel('Instructions', {exact:true});
      await page.waitForFunction(() => document.querySelector('#nf-body').value === '# Default template');
      await body.fill('Keep after failure');
      const select = create.getByLabel('Stored template');
      await select.selectOption('failed-fixture');
      await create.getByRole('button', {name:'Replace instructions'}).click();
      await create.getByText('This template couldn’t be read.').waitFor();
      assert.equal(await body.inputValue(), 'Keep after failure');
      assert.equal(await select.inputValue(), 'default-fixture');
      assert(await body.isEnabled());
    } finally { await page.unroute(list, listHandler); await page.unroute(detail, detailHandler); }
  });
  await test('Batch 2 editor touch targets and place rows remain usable', async () => {
    for (const width of [390, 600]) {
      await page.setViewportSize({width, height:900});
      await go('new');
      const place = page.locator('.jf-create .jf-editor-place').nth(1);
      await place.waitFor();
      const checkbox = await place.locator('input').boundingBox(), mark = await place.locator('.jf-agent-mark').boundingBox(), name = await place.locator('.jf-agent-name').boundingBox();
      assert(Math.abs(checkbox.y - name.y) < 12 && Math.abs(mark.y - name.y) < 12, 'place controls must align with the name');
      assert.equal(await place.locator('.jf-agent-path').evaluate(e => getComputedStyle(e).whiteSpace), 'nowrap');
      await go('skills/sole-copy/edit');
      const editor = page.locator('.jf-editor');
      await editor.getByRole('heading', {name:'Save to'}).waitFor();
      for (const element of await editor.locator('.jf-reader-title nav a, .ed-toolbar button').all()) {
        const box = await element.boundingBox(); assert(box.width >= 44 && box.height >= 44, `small target: ${await element.innerText()}`);
      }
      const row = editor.locator('.jf-editor-place').filter({hasText:'Not here'}).first();
      const agent = await row.locator('.jf-agent').boundingBox(), status = await row.locator('.jf-status').boundingBox();
      assert(status.x >= agent.x + agent.width || status.y >= agent.y + agent.height, 'status overlaps agent');
      const check = row.getByRole('checkbox'); const before = await check.isChecked();
      await row.click({position:{x:10,y:10}});
      assert.notEqual(await check.isChecked(), before);
      await go('skills');
      const welcome = page.getByRole('button', {name:'Show my skills'});
      if (await welcome.isVisible()) await welcome.click();
      const checkLabel = page.locator('.jf-grid-checkbox').first();
      await checkLabel.waitFor();
      const targetBox = await checkLabel.boundingBox();
      assert(targetBox.width >= 44 && targetBox.height >= 44);
      const rowCheck = checkLabel.getByRole('checkbox');
      const checked = await rowCheck.isChecked();
      await checkLabel.click({position:{x:5,y:5}});
      assert.notEqual(await rowCheck.isChecked(), checked);
      await go('skills/sole-copy/why');
      for (const link of await page.locator('.jf-why-breadcrumb a').all()) {
        const box = await link.boundingBox(); assert(box.width >= 44 && box.height >= 44);
      }
    }
    await page.setViewportSize({width:1280, height:900});
  });
  await test('New skill previews exact file bytes for two selected places (F4)', async () => {
    const name = 'phase-three-create';
    const paths = [file('.claude',name), file('.codex',name)];
    await go('new');
    const create = page.locator('.jf-create');
    await create.getByLabel('Name', {exact:true}).fill(' Phase THREE Create ');
    await create.getByRole('button', {name:'Use phase-three-create'}).click();
    await create.getByLabel('What it does and when to use it').fill('Use this: review café. # preserve this\nA second line.');
    await create.getByRole('button', {name:'Checklist', exact:true}).click();
    await create.getByRole('checkbox', {name:/Codex/}).check();
    const preview = create.getByRole('complementary', {name:'What will be created'}).locator('pre');
    await preview.waitFor();
    const before = await preview.textContent();
    assert.match(before, /## Checklist/);
    assert.match(before, /A second line/);
    assert(paths.every(path => !fs.existsSync(path)), 'preview did not create any file');
    await create.getByRole('button', {name:'Create in 2 places'}).click();
    await page.waitForURL(url => url.hash === '#/skills/' + name);
    for (const path of paths) assert.deepEqual(fs.readFileSync(path), Buffer.from(before));
    assert(!fs.existsSync(file('.config/opencode',name)));
  });
  await test('New skill reports a partial create and keeps confirmed files', async () => {
    const name = 'phase-three-partial';
    const codex = url => url.pathname === '/api/skills' && url.searchParams.get('scope') === 'codex';
    let rejected = 0;
    const fail = route => { rejected++; return route.fulfill({status:409, json:{error:'Fixture write refused'}}); };
    await page.route(codex, fail);
    try {
      await go('new');
      const create = page.locator('.jf-create');
      await create.getByLabel('Name', {exact:true}).fill(name);
      await create.getByLabel('What it does and when to use it').fill('Use for a partial creation fixture.');
      await create.getByRole('checkbox', {name:/Codex/}).check();
      await create.getByRole('button', {name:'Create in 2 places'}).click();
      await create.getByText(/Some places couldn.t be confirmed/).waitFor();
      assert.equal(rejected, 1);
      assert(fs.existsSync(file('.claude', name)));
      assert(!fs.existsSync(file('.codex', name)));
      assert(await create.getByRole('checkbox', {name:/Codex/}).isDisabled());
      await create.getByRole('link', {name:'Open it'}).click();
      await page.waitForURL(url => url.hash === '#/skills/' + name);
    } finally { await page.unroute(codex, fail); }
  });
  await test('New skill restores a place after permissions recover on a new visit', async () => {
    const name = 'recover-create-permission';
    let readOnly = false;
    const scopes = url => url.pathname === '/api/scopes';
    const scopeHandler = async route => {
      const response = await route.fetch(), rows = await response.json();
      if (readOnly) Object.assign(rows.find(row => row.id === 'codex'), {writable:false, availability:'read-only'});
      await route.fulfill({response, json:rows});
    };
    const write = url => url.pathname === '/api/skills' && url.searchParams.get('scope') === 'codex';
    const refuse = route => { readOnly = true; return route.fulfill({status:409, json:{error:'Fixture write refused'}}); };
    await page.route(scopes, scopeHandler);
    await page.route(write, refuse);
    try {
      await go('new');
      const create = page.locator('.jf-create');
      await create.getByLabel('Name', {exact:true}).fill(name);
      await create.getByLabel('What it does and when to use it').fill('Use for permission recovery.');
      await create.getByRole('checkbox', {name:/Codex/}).check();
      await create.getByRole('button', {name:'Create in 2 places'}).click();
      await create.getByText(/Some places couldn.t be confirmed/).waitFor();
      await create.getByRole('checkbox', {name:/Codex/}).waitFor({state:'hidden'});
      assert(fs.existsSync(file('.claude', name)));
      readOnly = false;
      await create.getByRole('link', {name:'Open it'}).click();
      await page.getByRole('button', {name:'Edit', exact:true}).waitFor();
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.getByRole('link', {name:'New skill', exact:true}).first().click();
      await create.getByRole('checkbox', {name:/Codex/}).waitFor();
      assert(await create.getByRole('checkbox', {name:/Codex/}).isEnabled());
    } finally {
      await page.unroute(scopes, scopeHandler);
      await page.unroute(write, refuse);
      await page.request.delete(`${base}/api/skills/${name}?scope=claude-code&purge=1`);
    }
  });
  await test('New skill reports an inventory error and retries without losing the draft', async () => {
    const scopes = url => url.pathname === '/api/scopes';
    let reject = true;
    const scopeHandler = route => reject ? route.fulfill({status:503, json:{error:'Fixture inventory unavailable'}}) : route.continue();
    await go('skills');
    await page.route(scopes, scopeHandler);
    try {
      await page.getByRole('link', {name:'New skill', exact:true}).first().click();
      const create = page.locator('.jf-create');
      await create.getByLabel('Name', {exact:true}).fill('inventory-retry-fixture');
      await create.getByLabel('What it does and when to use it').fill('Use to check inventory retry.');
      await create.getByRole('alert').getByText(/inventory unavailable/i).waitFor();
      assert(await create.getByRole('button', {name:/^Create in/}).isDisabled());
      const ai = create.getByRole('button', {name:'Create with AI or add metadata'});
      assert(await ai.isDisabled());
      await ai.evaluate(button => button.dispatchEvent(new MouseEvent('click', {bubbles:true})));
      assert.equal(await page.getByRole('dialog').count(), 0);
      reject = false;
      await create.getByRole('button', {name:'Try again', exact:true}).click();
      await create.getByRole('alert').waitFor({state:'hidden'});
      await page.waitForFunction(() => !document.querySelector('.jf-create button[form="jf-create-form"]')?.disabled);
      assert(await create.getByRole('button', {name:/^Create in/}).isEnabled());
      assert(await ai.isEnabled());
      assert.equal(await create.getByLabel('Name', {exact:true}).inputValue(), 'inventory-retry-fixture');
      assert.equal(await create.getByLabel('What it does and when to use it').inputValue(), 'Use to check inventory retry.');
    } finally { await page.unroute(scopes, scopeHandler); }
  });
  await test('New skill can target the library before it has a folder', async () => {
    const scopes = url => url.pathname === '/api/scopes';
    const records = url => url.pathname === '/api/skills' && url.searchParams.get('scope') === 'all';
    const library = path.join(root, 'data/jackfield/skills');
    const absent = route => route.fulfill({json:[{id:'global', kind:'global', label:'Global', path:library,
      exists:false, writable:true, availability:'missing'}]});
    const empty = route => route.fulfill({json:[]});
    await page.route(scopes, absent);
    await page.route(records, empty);
    try {
      await go('new');
      const create = page.locator('.jf-create');
      assert(await create.getByRole('checkbox', {name:/Your library/}).isChecked());
      await create.getByLabel('Name', {exact:true}).fill('phase-three-library');
      await create.getByLabel('What it does and when to use it').fill('Use for the empty library fixture.');
    } finally {
      await page.unroute(scopes, absent);
      await page.unroute(records, empty);
    }
    await page.getByRole('button', {name:'Create in 1 place', exact:true}).click();
    await page.waitForURL(url => url.hash === '#/skills/phase-three-library');
    assert(fs.existsSync(path.join(library, 'phase-three-library/SKILL.md')));
  });
  await test('Delayed initial template lookup preserves new skill input', async () => {
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    const matches = url => url.pathname === '/api/templates';
    const handler = async route => { await gate; await route.fulfill({json:{templates:['delayed-fixture']}}); };
    const detail = url => url.pathname === '/api/templates/delayed-fixture';
    let detailReads = 0;
    const detailHandler = route => { detailReads++; return route.fulfill({json:{body:'# Different stored template body'}}); };
    await page.route(matches, handler);
    await page.route(detail, detailHandler);
    try {
      await go('skills');
      await page.evaluate(() => { location.hash = '#/new?template=delayed-fixture'; });
      const create = page.locator('.jf-create');
      await create.getByLabel('Instructions', {exact:true}).fill('Typed before template lookup finished.');
      const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/templates');
      release();
      await response;
      await page.waitForTimeout(200);
      assert.equal(detailReads, 0, 'a delayed lookup must not apply a template over typed instructions');
      assert.equal(await create.getByLabel('Instructions', {exact:true}).inputValue(), 'Typed before template lookup finished.');
      await create.getByRole('button', {name:'Cancel', exact:true}).click();
      await page.getByRole('dialog', {name:'Discard this skill draft?'}).getByRole('button', {name:'Discard draft'}).click();
      await page.waitForURL(url => url.hash === '#/skills');
    } finally { release(); await page.unroute(matches, handler); await page.unroute(detail, detailHandler); }
  });
  await test('Tracking draft survives a query-only route change', async () => {
    await go('settings/tracking/add-agent');
    await page.locator('#trk-name').fill('Unfinished agent');
    await page.evaluate(() => { location.hash = '#/settings/tracking/add-agent?source=fixture'; });
    await page.waitForURL(url => url.hash === '#/settings/tracking/add-agent?source=fixture');
    await page.waitForTimeout(200);
    assert.equal(await page.locator('#trk-name').inputValue(), 'Unfinished agent');
    await page.locator('.trk-form').getByRole('button', {name:'Cancel'}).click();
    await page.getByRole('dialog', {name:/Discard/}).getByRole('button', {name:'Discard'}).click();
    await page.waitForURL(url => url.hash === '#/settings/tracking');
  });
  await test('Direct editor recovers after a failed document read and retry', async () => {
    let failures = 0;
    const matches = url => url.pathname === '/api/skills/sole-copy' && url.searchParams.get('scope') === 'claude-code';
    const handler = route => failures++ === 0
      ? route.fulfill({status:503, json:{error:'Fixture body unavailable'}}) : route.continue();
    await page.route(matches, handler);
    try {
      await page.goto(base + '/#/skills/sole-copy/edit');
      await page.getByRole('button', {name:'Retry document'}).click();
      await page.locator('.ed-area').waitFor();
      assert.match(await page.locator('.ed-area').inputValue(), /single fixture copy/);
      assert.equal(new URL(page.url()).hash, '#/skills/sole-copy/edit');
      assert(failures >= 2);
    } finally { await page.unroute(matches, handler); }
  });
  await test('Unknown page and missing skill offer recovery and a close name (S13)', async () => {
    await go('unknown-fixture');
    await page.getByRole('heading', {name:'Page not found'}).waitFor();
    assert(await page.getByRole('link', {name:'Go to Skills'}).isVisible());
    assert(await page.getByRole('link', {name:'Look in Trash'}).isVisible());
    await page.evaluate(() => { location.hash = '#/skills/sole-cop'; });
    await page.getByText('Did you mean', {exact:true}).waitFor();
    await page.getByRole('link', {name:'sole-copy', exact:true}).click();
    await page.waitForURL(url => url.hash === '#/skills/sole-copy');
    await page.locator('.jf-reader-heading').waitFor();
  });
  await test('Quality lists observed Claude Code evidence and recovers from a failed read', async () => {
    await go('tools/quality');
    const card = page.getByRole('region', {name:'What Claude Code sees', exact:true});
    const report = await (await context.request.get(base+'/api/doctor?scope=all&hygiene=1')).json();
    const listing = report.hygiene.claude_listing;
    const format = new Intl.NumberFormat().format;
    await card.getByText(`${format(listing.listing_chars)} of ~${format(listing.budget.budget_chars_estimate)} characters`, {exact:true}).waitFor();
    assert.equal(await card.getByText('Partial', {exact:true}).count() > 0, listing.confidence === 'partial');
    for (const width of [1280, 320]) for (const mode of ['dark', 'light']) {
      await page.setViewportSize({width,height:900});
      await theme(mode);
      await card.scrollIntoViewIfNeeded();
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await card.screenshot({path:path.join(root,`listing-budget-${mode}-${width}.png`)});
    }
    await page.setViewportSize({width:1280,height:900});
    const matches = url => url.pathname==='/api/doctor' && url.searchParams.get('hygiene')==='1';
    let attempts = 0;
    const handler = route => attempts++===0 ? route.fulfill({status:503,contentType:'application/json',body:'{"error":"fixture unavailable"}'}) : route.continue();
    await page.route(matches, handler);
    try {
      await go('tools/quality');
      await page.getByText('Hygiene evidence is unavailable.', {exact:false}).waitFor();
      assert.equal(await card.count(), 0);
      await page.getByRole('button', {name:'Retry', exact:true}).focus();
      await page.keyboard.press('Enter');
      await card.waitFor();
      assert.equal(await page.getByText('Hygiene evidence is unavailable.', {exact:false}).count(), 0);
    } finally { await page.unroute(matches, handler); }
  });
  await test('Unmodified shortcuts leave focused controls alone', async () => {
    await go('skills');
    for (const control of [page.getByRole('button', {name:'Keyboard shortcuts'}), page.getByRole('link', {name:'Skills', exact:true})]) {
      await control.focus();
      // Dispatch to the page so Firefox's own quick-find shortcut cannot take focus.
      for (const key of ['/', '?']) {
        await control.dispatchEvent('keydown', {key, bubbles:true, cancelable:true});
        assert(await control.evaluate(el => document.activeElement === el));
        assert.equal(await page.getByRole('dialog', {name:'Keyboard shortcuts'}).count(), 0);
      }
    }
    await page.locator('#h1').focus();
    await page.keyboard.press('/');
    assert(await page.getByRole('combobox', {name:'Search skills, actions and pages'}).evaluate(el => document.activeElement === el));
  });
  await test('Skill page opens from search and shows the exact file bytes for the chosen copy (F1)', async () => {
    const codexFile = file('.codex', 'majority-minor'), original = fs.readFileSync(codexFile);
    const exact = Buffer.from('\ufeff' + original.toString('utf8').replace(/\n/g, '\r\n'));
    fs.writeFileSync(codexFile, exact);
    try {
      await go('skills');
      await page.getByRole('button', {name:'Search skills, actions and pages'}).click();
      const search = page.getByRole('combobox', {name:'Search skills, actions and pages'});
      await search.fill('majority-minor');
      await page.getByRole('option', {name:/^majority-minor/}).waitFor();
      await search.press('Enter');
      await page.waitForURL(url => url.hash === '#/skills/majority-minor');
      await page.locator('#h1').getByText('majority-minor', {exact:true}).waitFor();
      await page.getByRole('button', {name:'File text', exact:true}).click();
      const text = page.locator('.jf-file-text');
      await text.waitFor();
      assert.match(await text.textContent(), /Majority text/);
      await page.getByLabel('Read copy').selectOption({label:'Codex'});
      await page.waitForFunction(expected => document.querySelector('.jf-file-text')?.textContent === expected, exact.toString('utf8'));
      assert.equal(await text.textContent(), exact.toString('utf8'));
      await page.reload();
      await text.waitFor();
      assert.equal(await text.textContent(), exact.toString('utf8'));
      await page.getByRole('button', {name:'Read', exact:true}).click();
      assert.match(await page.getByRole('article', {name:'Skill document'}).locator('.doc').innerText(), /Different text/);
    } finally { fs.writeFileSync(codexFile, original); }
  });
  await test('Skill page reads exact instances within one recursive scope (S3)', async () => {
    const name = 'reader-exact-instance';
    const fixture = fs.mkdtempSync(path.join(home, '.config/opencode/skills/reader-fixture-'));
    const notes = 'references/notes & checks.md';
    const copies = [
      {branch:'alpha', body:'Read the first OpenCode copy.', notes:'First line\n', lines:'1 line'},
      {branch:'beta', body:'Read the second OpenCode copy.', notes:'One\r\nTwo\r\nThree', lines:'3 lines'},
    ];
    try {
      for (const copy of copies) {
        const folder = path.join(fixture, copy.branch, name);
        fs.mkdirSync(path.join(folder, 'references'), {recursive:true});
        copy.path = fs.realpathSync(folder);
        copy.label = 'OpenCode — ' + copy.path;
        copy.raw = `---\nname: ${name}\ndescription: Use this fixture for exact reader checks.\n---\n\n${copy.body}\n`;
        fs.writeFileSync(path.join(folder, 'SKILL.md'), copy.raw);
        fs.writeFileSync(path.join(folder, notes), copy.notes);
        if (copy.branch === 'beta') {
          fs.writeFileSync(path.join(folder, 'references/binary.bin'), Buffer.from([0xff, 0xfe]));
        }
      }
      await go('skill/' + name);
      const picker = page.getByLabel('Read copy');
      const document = page.getByRole('article', {name:'Skill document'});
      const raw = document.locator('.jf-file-text');
      const files = page.getByRole('complementary', {name:'Details'}).locator('section')
        .filter({has:page.getByRole('heading', {name:'Files', exact:true})});
      for (const copy of [...copies].reverse()) {
        await picker.selectOption({label:copy.label});
        await document.locator('.doc').getByText(copy.body, {exact:true}).waitFor();
        await files.getByText(notes, {exact:true}).locator('..').getByText(copy.lines, {exact:true}).waitFor();
        const binary = files.getByText('references/binary.bin', {exact:true});
        if (copy.branch === 'beta') {
          await binary.locator('..').getByText('Line count unavailable', {exact:true}).waitFor();
        } else {
          assert.equal(await binary.count(), 0);
        }
        await page.getByRole('button', {name:'File text', exact:true}).click();
        await raw.waitFor();
        assert.equal(await raw.textContent(), copy.raw);
        await page.getByRole('button', {name:'Read', exact:true}).click();
      }
      const exact = copies[1];
      const qualityRequest = url => url.pathname === '/api/doctor' && url.searchParams.get('hygiene') === '1';
      const mockQuality = route => route.fulfill({json:{hygiene:{findings:[{
        title:'Fixture exact copy', severity:'warning', instances:[{name, scope:'opencode', path:exact.path}],
      }]}}});
      await page.route(qualityRequest, mockQuality);
      try {
        await go('tools/quality');
        const finding = page.locator('.tp-findings > li > details').filter({hasText:'Fixture exact copy'});
        await finding.locator(':scope > summary').click();
        await finding.getByRole('button', {name:'Open', exact:true}).click();
        await document.locator('.doc').getByText(exact.body, {exact:true}).waitFor();
        assert.equal(new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('copy'), exact.path);
        await page.reload();
        await document.locator('.doc').getByText(exact.body, {exact:true}).waitFor();
      } finally { await page.unroute(qualityRequest, mockQuality); }
    } finally {
      fs.rmSync(fixture, {recursive:true, force:true});
    }
  });
  await test('Skill page describes Claude Code list space in plain language', async () => {
    await go('skill/sole-copy');
    const details = page.getByRole('complementary', {name:'Details'});
    await details.getByText('This estimate covers personal skills in Claude Code.', {exact:true}).waitFor();
    assert.match(await details.innerText(), /estimated skill list space/);
    assert.doesNotMatch(await details.innerText(), /tokens|skillListingBudgetFraction/);
  });
  await test('Skill page square uses the shared panel and restores phone focus', async () => {
    await page.setViewportSize({width:390,height:844});
    try {
      await go('skill/same-everywhere');
      const square = page.getByRole('button', {name:'same-everywhere in Codex: On'});
      await square.focus();
      await square.press('Enter');
      const panel = page.getByRole('dialog', {name:'same-everywhere'});
      await panel.getByRole('button', {name:/^Turn off/}).waitFor();
      await page.keyboard.press('Escape');
      await panel.waitFor({state:'hidden'});
      assert(await square.evaluate(el => el === document.activeElement));
      assert(!fs.existsSync(file('.codex') + '.disabled'));
      await page.getByLabel('Read copy').selectOption({label:'Codex'});
      const details = page.getByRole('complementary', {name:'Details'});
      await details.getByText('SKILL.md', {exact:true}).waitFor();
      await turnOffCodexFromReader();
      await panel.waitFor({state:'hidden'});
      const undo = page.getByRole('button', {name:'Undo', exact:true});
      await undo.waitFor();
      assert(fs.existsSync(file('.codex') + '.disabled'));
      await details.getByText('SKILL.md.disabled', {exact:true}).waitFor();
      await undo.click();
      await square.waitFor();
      assert(fs.existsSync(file('.codex')));
      await details.getByText('SKILL.md', {exact:true}).waitFor();
      await go('skills?sel=same-everywhere%3Acodex');
      await panel.waitFor();
      await page.keyboard.press('Escape');
      await panel.waitFor({state:'hidden'});
      assert(await page.getByRole('link', {name:'Jackfield home'}).isVisible());
    } finally { await page.setViewportSize({width:1280,height:900}); }
  });
  await test('Skill history follows navigation and ignores an older response', async () => {
    await go('skill/same-everywhere');
    let release;
    const delayed = new Promise(resolve => { release = resolve; });
    const matches = url => url.pathname === '/api/history' && url.searchParams.has('name') && !url.searchParams.has('snapshots');
    const handler = async route => {
      const name = new URL(route.request().url()).searchParams.get('name');
      if (name === 'sole-copy') await delayed;
      await route.fulfill({status:200, contentType:'application/json', body:JSON.stringify([{action:'fixture-'+name, timestamp:'2026-01-01T00:00:00Z'}])});
    };
    await page.route(matches, handler);
    try {
      await Promise.all([
        page.waitForRequest(request => request.url().includes('/api/history?limit=20&name=sole-copy')),
        page.evaluate(() => { location.hash = '#/skills/sole-copy'; }),
      ]);
      await Promise.all([
        page.waitForResponse(response => response.url().includes('/api/history?limit=20&name=same-everywhere')),
        page.evaluate(() => { location.hash = '#/skills/same-everywhere'; }),
      ]);
      const older = page.waitForResponse(response => response.url().includes('/api/history?limit=20&name=sole-copy'));
      release();
      await older;
      await page.waitForTimeout(200);
      assert.match(await page.getByRole('complementary', {name:'Details'}).innerText(), /fixture-same-everywhere/);
      assert.doesNotMatch(await page.getByRole('complementary', {name:'Details'}).innerText(), /fixture-sole-copy/);
    } finally { release(); await page.unroute(matches, handler); }
  });
  await test('Retired /v2 and /classic addresses open the interface at / keeping query and hash', async () => {
    await page.goto(base + '/classic/?window=claude#/skills');
    await page.getByRole('heading',{name:'Skills',exact:true}).waitFor();
    assert.equal(page.url(), base + '/?window=claude#/skills');
    await page.goto(base + '/v2?window=claude#/skills');
    await page.getByRole('heading',{name:'Skills',exact:true}).waitFor();
    assert.equal(page.url(), base + '/?window=claude#/skills');
    assert(await page.getByRole('heading',{name:'Skills',exact:true}).isVisible());
  });
  await test('Needs attention gives manual guidance and preserves unreadable bytes', async () => {
    const target = file('.codex', 'damaged-one'), before = fs.readFileSync(target);
    const writes = [];
    const observe = req => { if (attentionWrites(req)) writes.push(req.url()); };
    page.on('request', observe);
    try {
      await openAttention('damaged-one:codex:unreadable');
      assert.match(await attentionHeading.innerText(), /damaged-one/);
      assert.match(await attention.innerText(), /cannot be read as text|by hand|manually/i);
      assert.equal(await attention.getByRole('button', {name:'Replace with the readable copy'}).count(), 0);
      await attentionHeading.focus();
      await page.keyboard.press('f');
      assert.deepEqual(writes, []);
      assert.deepEqual(fs.readFileSync(target), before);
    } finally { page.off('request', observe); }
  });
  await test('Needs attention requires an explicit version before fixing a tied copy', async () => {
    const target = file('.codex', 'split-even'), before = fs.readFileSync(target);
    const writes = [];
    const observe = req => { if (attentionWrites(req)) writes.push(req.url()); };
    page.on('request', observe);
    try {
      await go('inbox?item=warn%3Asplit-even');
      await page.waitForURL(url => url.hash.startsWith('#/attention?'));
      await attentionHeading.waitFor();
      assert.match(await attentionHeading.innerText(), /split-even/);
      for (const name of ['Version 1', 'Version 2']) {
        const choice = attention.getByRole('button', {name:new RegExp('^' + name)});
        assert.equal(await choice.getAttribute('aria-pressed'), 'false');
      }
      assert(await attention.getByRole('button', {name:'Choose a version first', exact:true}).isDisabled());
      await attentionHeading.focus();
      await page.keyboard.press('Enter');
      await page.keyboard.press('f');
      assert.deepEqual(writes, []);
      assert.deepEqual(fs.readFileSync(target), before);
    } finally { page.off('request', observe); }
  });
  await test('Needs attention Open skill follows Enter without fixing (SR-1)', async () => {
    const target = file('.codex', 'damaged-fm'), before = fs.readFileSync(target);
    const writes = [];
    const observe = req => { if (attentionWrites(req)) writes.push(req.url()); };
    page.on('request', observe);
    try {
      await openAttention('damaged-fm:codex:unreadable');
      const open = attention.getByRole('link', {name:'Open skill', exact:true});
      await open.focus();
      await page.keyboard.press('f');
      await page.keyboard.press('Enter');
      await page.waitForURL(url => url.hash.startsWith('#/skills/damaged-fm'));
      assert.deepEqual(writes, []);
      assert.deepEqual(fs.readFileSync(target), before);
    } finally { page.off('request', observe); }
  });
  await test('Needs attention Check again counts two problems on one skill (F7)', async () => {
    const name = 'majority-minor';
    const damaged = file('.agents', name), original = fs.readFileSync(damaged);
    const endpoint = url => url.pathname === '/api/skills' && url.searchParams.get('scope') === 'all' && url.searchParams.get('body') === '0';
    let includeProblems = false;
    const restrictInventory = async route => {
      const response = await route.fetch();
      const records = await response.json();
      const names = ['sole-copy', 'same-everywhere', '.system'];
      if (includeProblems) names.push(name);
      await route.fulfill({response, json:records.filter(record => names.includes(record.name))});
    };
    await page.route(endpoint, restrictInventory);
    try {
      await openAttention();
      await attention.getByRole('heading', {name:'Nothing left to fix', exact:true}).waitFor();
      assert.match(await attention.innerText(), /We checked .* skills in .* places/);
      await attention.getByText(/^Last checked /).waitFor();
      await expectAttentionCount(0);
      fs.writeFileSync(damaged, Buffer.from([0xff, 0xfe]));
      includeProblems = true;
      await attention.getByRole('button', {name:'Check again', exact:true}).click();
      await expectAttentionCount(2);
      const issues = attention.getByRole('region', {name:'To fix · 2', exact:true});
      assert.equal(await issues.locator('[data-attention-id]').count(), 2);
      await issues.locator('[data-attention-id="majority-minor:codex:different"]').waitFor();
      await issues.locator('[data-attention-id="majority-minor:agents:unreadable"]').waitFor();
    } finally {
      fs.writeFileSync(damaged, original);
      await page.unroute(endpoint, restrictInventory);
    }
  });
  await test('Needs attention keyboard navigation, Skip and Undo preserve the issue group (F7)', async () => {
    const name = 'majority-minor', id = `${name}:codex:different`;
    const target = file('.codex', name), original = fs.readFileSync(target);
    const writes = [];
    const observe = req => { if (attentionWrites(req)) writes.push(req.postDataJSON().operation); };
    page.on('request', observe);
    try {
      await openAttention(id);
      const count = Number(await attentionNav.locator('.sm-nav__count').innerText());
      await expectAttentionCount(count);
      const ids = await attention.getByRole('region', {name:`To fix · ${count}`, exact:true})
        .locator('[data-attention-id]').evaluateAll(items => items.map(item => item.dataset.attentionId));
      const index = ids.indexOf(id);
      assert(index >= 0 && ids.length > 1);
      const forward = index < ids.length - 1;
      const adjacent = ids[index + (forward ? 1 : -1)];
      await attentionHeading.focus();
      await page.keyboard.press(forward ? 'j' : 'k');
      await page.waitForURL(url => new URLSearchParams(url.hash.split('?')[1]).get('item') === adjacent);
      await page.keyboard.press(forward ? 'k' : 'j');
      await page.waitForURL(url => new URLSearchParams(url.hash.split('?')[1]).get('item') === id);
      await attention.getByRole('button', {name:'Skip for now', exact:true}).click();
      const skipped = attention.getByRole('region', {name:'Skipped · 1', exact:true});
      const skippedItem = skipped.locator(`[data-attention-id="${id}"]`);
      await skippedItem.waitFor();
      await expectAttentionCount(count - 1);
      assert.deepEqual(writes, []);
      assert.deepEqual(fs.readFileSync(target), original);
      await skippedItem.click();
      await attention.getByRole('button', {name:'The shared version', exact:true}).click();
      await attention.locator('[data-primary]:enabled').waitFor();
      await attentionHeading.focus();
      await page.keyboard.press('f');
      const undo = page.locator('.toast').getByRole('button', {name:'Undo', exact:true});
      await undo.waitFor();
      await attention.getByRole('region', {name:'Fixed · 1', exact:true}).locator(`[data-attention-id="${id}"]`).waitFor();
      assert.deepEqual(writes, ['remove', 'sync']);
      assert.deepEqual(fs.readFileSync(target), fs.readFileSync(file('.claude', name)));
      await expectAttentionCount(count - 1);
      await undo.click();
      await page.locator('.toast').getByText(/^Undone/).waitFor();
      await skippedItem.waitFor();
      await expectAttentionCount(count - 1);
      assert.deepEqual(fs.readFileSync(target), original);
    } finally {
      page.off('request', observe);
      fs.mkdirSync(path.dirname(target), {recursive:true});
      fs.writeFileSync(target, original);
    }
  });
  await test('Skip link keeps the current page and focuses its heading (SR-2)',async()=>{await go('skill/same-everywhere');await page.locator('a.skip').focus();await page.keyboard.press('Enter');await page.waitForTimeout(200);assert(page.url().endsWith('#/skills/same-everywhere'),page.url());assert.equal(await page.evaluate(()=>document.activeElement&&document.activeElement.id),'h1');});
  await test('Navigation names the Needs attention count and stays outside the dialog tab order', async () => {
    await go('skills');
    const badge = page.locator('.tabs a[href="#/attention"] .sm-nav__count');
    const count = Number(await badge.innerText());
    assert(count > 1, 'fixture includes multiple problems');
    const review = page.getByRole('link', {name: `Needs attention, ${count} items`, exact: true});
    const skipLink = page.getByRole('link', {name: 'Skip to content', exact: true});
    try {
      for (const width of [1280, 390]) {
        await page.setViewportSize({width, height: 900});
        await review.waitFor();
        assert.equal(await review.count(), 1);
      }
    } finally {
      await page.setViewportSize({width: 1280, height: 900});
    }
    const shortcuts = page.getByRole('button', {name: 'Keyboard shortcuts', exact: true});
    await shortcuts.click();
    await page.getByRole('dialog', {name: 'Keyboard shortcuts'}).waitFor();
    assert(await page.locator('.toasts').evaluate(element => element.inert));
    assert(await page.locator('a.skip').evaluate(element => {
      const focused = document.activeElement;
      element.focus();
      return element.inert && document.activeElement === focused;
    }));
    await page.keyboard.press('Escape');
    assert(!(await page.locator('.toasts').evaluate(element => element.inert)));
    assert.equal(await skipLink.count(), 1);
    assert(await shortcuts.evaluate(element => document.activeElement === element));
  });
  await test('Search accepts typing, keyboard navigation and returns all matches', async () => {
    await go('skill/sole-copy');
    await page.getByRole('button', {name:'Search skills, actions and pages'}).click();
    const search = page.getByRole('combobox', {name:'Search skills, actions and pages'});
    await page.waitForFunction(() => document.activeElement?.id === 'command-q');
    await search.pressSequentially('same');
    assert.equal(await search.inputValue(), 'same', 'the palette retains the typed query');
    const option = page.getByRole('option', {name:/same-everywhere/});
    await option.waitFor();
    await search.press('ArrowDown');
    assert.notEqual(await search.getAttribute('aria-activedescendant'), null);
    await page.getByRole('option', {name:'Show 1 match in Skills'}).click();
    await page.waitForURL(url => url.hash === '#/skills?q=same');
    await page.waitForFunction(() => document.querySelector('.jf-skills-filter input')?.value === 'same');
  });
  await test('New skill shows multiple lines of instructions and cancels cleanly', async () => {
    await go('skills');
    await page.getByRole('link', {name:'New skill', exact:true}).click();
    const dialog = page.locator('.jf-create');
    const instructions = dialog.getByLabel('Instructions', {exact:true});
    assert(await instructions.evaluate(element => element.clientHeight > 100));
    await dialog.getByRole('button', {name:'Cancel', exact:true}).click();
    await dialog.waitFor({state:'hidden'});
  });
  await test('Search includes skills despite prior Skills filters and excludes observations', async () => {
    await go('skills?agent=codex&only=problems');
    await page.getByRole('button', {name:'Show only these', exact:true}).waitFor();
    assert.equal(await page.getByRole('button', {name:'sole-copy',exact:true}).count(), 0);
    await page.getByRole('button', {name:'Search skills, actions and pages'}).click();
    const search = page.getByRole('combobox', {name:'Search skills, actions and pages'});
    await search.fill('sole-copy');
    await page.getByRole('option', {name:'Show 1 match in Skills'}).click();
    await page.waitForURL(url => url.hash === '#/skills?q=sole-copy');
    await page.waitForFunction(() => document.querySelector('.jf-skills-filter input')?.value === 'sole-copy');
    await page.getByRole('button', {name:/sole-copy in Claude Code/}).waitFor();
    await go('skill/sole-copy');
    assert.equal(await page.locator('.tree a').filter({hasText:'.system'}).count(), 0);
    await page.getByRole('button', {name:'Search skills, actions and pages'}).click();
    await search.fill('.system');
    assert.equal(await page.locator('#command-list [role="option"]').count(), 0);
    await page.keyboard.press('Escape');
    await openAttention();
    assert.equal(await attention.locator('[data-attention-id]').filter({hasText:'.system'}).count(), 0);
  });
  await test('Command palette has a desktop pointer entry and restores focus', async () => {
    await page.setViewportSize({width:1366,height:768});
    try {
      await go('skills');
      const launcher = page.getByRole('button', {name:'Search skills, actions and pages'});
      await launcher.click();
      const dialog = page.getByRole('dialog', {name:'Search skills, actions and pages'});
      assert(await dialog.isVisible());
      await page.keyboard.press('Escape');
      assert(await launcher.evaluate(el => el === document.activeElement));
    } finally {
      await page.setViewportSize({width:1280,height:900});
    }
  });
  await test('Browser Back leaves a pristine New skill page and focuses the destination', async () => {
    await go('advanced');
    await page.locator('.tabs').getByRole('link', {name:'Skills', exact:true}).click();
    await page.getByRole('link', {name:'New skill', exact:true}).click();
    const dialog = page.locator('.jf-create');
    await dialog.waitFor();
    await page.goBack();
    await dialog.waitFor({state:'hidden'});
    const heading = page.getByRole('heading', {level:1, name:'Skills', exact:true});
    await heading.waitFor();
    assert(await heading.evaluate(el => el === document.activeElement));
  });
  await test('Skills panel actions fit at phone and desktop widths for tied copies', async () => {
    const endpoint = /[/]api[/]skills[?]scope=all(?:&body=0)?$/;
    const inventory = await (await page.request.get(base + '/api/skills?scope=all')).json();
    await page.route(endpoint, route => route.fulfill({json:inventory.filter(record => record.name === 'split-even')}));
    try {
      for (const width of [1366, 1024, 320]) {
        await page.setViewportSize({width,height:768});
        await go('skills?q=split-even');
        await page.getByRole('button', {name:/^split-even in Claude Code: Version/}).click();
        const action = page.getByRole('button', {name:'Compare the two versions', exact:true});
        await action.scrollIntoViewIfNeeded();
        assert(await action.evaluate(el => {
          const panel = el.closest('.jf-panel');
          const bounds = el.getBoundingClientRect();
          return bounds.left >= 0 && bounds.right <= innerWidth && panel.scrollWidth <= panel.clientWidth + 1;
        }), `Compare action clips at ${width}px`);
      }
    } finally {
      await page.unrouteAll({behavior:'wait'});
      await page.setViewportSize({width:1280,height:900});
    }
  });
  await test('Accessible names distinguish the brand, review items and comparison squares (SR-4/6/7/11)', async () => {
    await page.setViewportSize({width:390,height:844});
    try {
      await openAttention();
      assert.equal(await page.locator('a.brand').getAttribute('aria-label'), 'Jackfield home');
      const issues = await attention.getByRole('navigation', {name:'Problems'}).getByRole('button').allTextContents();
      assert(issues.length > 1);
      assert.equal(new Set(issues).size, issues.length);
    } finally { await page.setViewportSize({width:1280,height:900}); }
    await go('skill/majority-minor');
    assert(await page.getByRole('button', {name:'majority-minor in Codex: Different'}).isVisible());
    await go('skills?q=majority-minor');
    const squares = await page.getByRole('button', {name:/^majority-minor in /}).evaluateAll(buttons => buttons.map(button => button.getAttribute('aria-label')));
    assert(squares.length > 1);
    assert.equal(new Set(squares).size, squares.length);
  });
  await test('Needs attention keeps the selected repair visible and shows large groups in pages', async () => {
    const inventory = await (await page.request.get(base + '/api/skills?scope=all&body=0')).json();
    const sample = inventory.filter(record => record.name === 'majority-minor');
    const rows = Array.from({length:74}, (_, index) => {
      const name = 'many-problems-' + String(index).padStart(2, '0');
      return sample.map(record => ({...record, name,
        path:record.path?.replace('majority-minor', name),
        physical_path:record.physical_path?.replace('majority-minor', name),
      }));
    }).flat();
    const matches = url => url.pathname === '/api/skills' && url.searchParams.get('scope') === 'all';
    const inventoryFixture = route => route.fulfill({json:rows});
    await page.route(matches, inventoryFixture);
    try {
      await openAttention('many-problems-73:codex:different');
      const group = attention.getByRole('region', {name:'To fix · 74', exact:true});
      const selected = group.locator('[aria-current="true"]');
      assert.match(await selected.innerText(), /many-problems-73/);
      assert.equal(await group.getByRole('listitem').count(), 51);
      await group.getByRole('button', {name:'Show more in To fix', exact:true}).press('Enter');
      assert.equal(await group.getByRole('listitem').count(), 74);
      assert.equal(await selected.count(), 1);
      assert(await group.getByRole('button', {name:/many-problems-50/}).evaluate(button => button === document.activeElement));
    } finally { await page.unroute(matches, inventoryFixture); }
  });
  await test('An Undo toast stays while focused (SR-3)',async()=>{await go('skill/same-everywhere');await turnOffCodexFromReader();const undo=page.locator('.toast button').filter({hasText:'Undo'}).last();await undo.waitFor();await undo.focus();const held=await page.evaluate(()=>!!document.activeElement.closest('.toast'));assert(held);await undo.click();await page.waitForTimeout(700);assert(fs.existsSync(file('.codex')));});
  await test('Reader replacement previews before writing and ignores a repeated confirmation', async () => {
    await go('skill/majority-minor');
    const review = page.getByRole('region', {name:'Copies differ'}).getByRole('button', {name:'Review a different copy'});
    const target = file('.codex', 'majority-minor'), before = fs.readFileSync(target);
    await review.click();
    const panel = page.locator('.jf-panel');
    await panel.getByRole('button', {name:'Compare the two versions'}).click();
    assert.deepEqual(fs.readFileSync(target), before);
    await panel.getByRole('button', {name:/Keep Claude Code/}).click();
    const confirm = panel.getByRole('button', {name:/^(Make|Replace)/});
    await confirm.evaluate(el => { el.click(); el.click(); });
    const undo = page.getByRole('button', {name:'Undo', exact:true});
    await undo.waitFor();
    assert.notDeepEqual(fs.readFileSync(target), before);
    await undo.click();
    await page.locator('.toast').getByText('Undone', {exact:true}).waitFor();
    assert.deepEqual(fs.readFileSync(target), before);
  });
  await test('Reader comparison controls stay available at laptop and narrow widths', async () => {
    try {
      for (const width of [1366, 1024, 320]) {
        await page.setViewportSize({width, height:768});
        await go('skill/split-even');
        const comparison = page.getByRole('region', {name:'Copies differ'});
        const target = comparison.getByRole('combobox', {name:'Compare with'});
        const highlight = comparison.getByRole('checkbox', {name:"Highlight what's missing"});
        assert(await target.isVisible());
        await target.selectOption({index:1});
        await highlight.check();
        assert(await highlight.isChecked());
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        await comparison.getByRole('link', {name:'Choose a version in Needs attention', exact:true}).click();
        await page.waitForURL(url => url.hash.startsWith('#/attention?') &&
          new URLSearchParams(url.hash.split('?')[1]).get('item') === 'split-even:split');
        await attentionHeading.waitFor();
        assert.match(await attentionHeading.innerText(), /split-even/);
      }
    } finally {
      await page.setViewportSize({width:1280,height:900});
    }
  });
  await test('Needs attention review follows the chosen version and shows affected locations', async () => {
    await openAttention('majority-minor:codex:different');
    const shared = attention.getByRole('button', {name:/^The shared version/});
    const codex = attention.getByRole('button', {name:/^Codex’s version/});
    assert.equal(await shared.getAttribute('aria-pressed'), 'false');
    assert.equal(await codex.getAttribute('aria-pressed'), 'false');
    await shared.click();
    const targets = attention.getByRole('list', {name:'Copies that will be overwritten'});
    assert.match(await targets.innerText(), /Codex/);
    assert((await targets.innerText()).includes(path.dirname(file('.codex', 'majority-minor'))));
    await codex.click();
    const comparison = attention.getByRole('region', {name:'Document comparison'});
    await comparison.locator('.compare-identities > div').last().getByText('Codex', {exact:true}).waitFor();
    const apply = attention.getByRole('button', {name:'Use Codex’s version everywhere', exact:true});
    await apply.waitFor();
    assert.equal(await targets.locator('li').count(), 3);
    assert.doesNotMatch(await targets.innerText(), /Codex/);
    const exactRead = url => url.pathname === '/api/skills/majority-minor' && url.searchParams.get('scope') === 'agents';
    let release;
    const pending = new Promise(resolve => { release = resolve; });
    const delay = async route => { await pending; await route.continue(); };
    await page.route(exactRead, delay);
    try {
      await attention.getByLabel('Compare target').selectOption('agents');
      assert.match(await comparison.locator('.compare-identities > div').first().innerText(), /Shared folder/);
      assert(await apply.isDisabled());
      release();
      await attention.locator('[data-primary]:enabled').waitFor();
      await comparison.getByText(/Supporting files haven’t been compared here/).waitFor();
    } finally {
      release();
      await page.unroute(exactRead, delay);
    }
  });
  await test('Needs attention Fix stays clear of navigation after scrolling', async () => {
    try {
      for (const [width, block] of [[1280, 'start'], [390, 'end']]) {
        await page.setViewportSize({width, height:577});
        await openAttention('majority-minor:codex:different');
        await attention.getByRole('button', {name:/^The shared version/}).click();
        const visible = await attention.getByRole('button', {name:'Use the shared version in Codex', exact:true}).evaluate((button, block) => {
          button.focus({preventScroll:true});
          button.scrollIntoView({block, behavior:'instant'});
          const rect = button.getBoundingClientRect();
          const header = document.querySelector('.top').getBoundingClientRect();
          const footer = document.querySelector('.bottomnav').getBoundingClientRect();
          const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
          return document.activeElement === button && button.contains(hit) &&
            rect.top >= header.bottom && rect.bottom <= (footer.height ? footer.top : innerHeight);
        }, block);
        assert(visible, `Needs attention Fix is obscured at ${width}px`);
      }
    } finally {
      await page.setViewportSize({width:1280, height:900});
    }
  });
  await test('Needs attention runs one delayed Fix and Undo restores the exact folder and count (F7)', async () => {
    const name = 'majority-minor', id = `${name}:codex:different`;
    const target = file('.codex', name), before = fs.readFileSync(target);
    const companion = path.join(path.dirname(target), 'target-only.txt');
    fs.writeFileSync(companion, 'previous copy only');
    const operations = [];
    const endpoint = '**/api/batch/execute';
    const delay = async route => {
      operations.push(route.request().postDataJSON().operation);
      await new Promise(resolve => setTimeout(resolve, 400));
      await route.continue();
    };
    await page.route(endpoint, delay);
    try {
      await openAttention(id);
      const count = Number(await attentionNav.locator('.sm-nav__count').innerText());
      await expectAttentionCount(count);
      await attention.getByRole('button', {name:/^The shared version/}).click();
      await attention.locator('.jf-attention-what').getByText(/The replacement comes from Claude Code/).waitFor();
      const apply = attention.getByRole('button', {name:'Use the shared version in Codex', exact:true});
      await attention.locator('[data-primary]:enabled').waitFor();
      const removed = page.waitForResponse(r => attentionWrites(r.request()) &&
        r.request().postDataJSON().operation === 'remove');
      await apply.evaluate(button => { button.click(); button.click(); });
      const response = await removed;
      assert(response.ok());
      const removedCopy = (await response.json()).results[0];
      const retained = removedCopy.trash_path;
      assert.equal(path.dirname(retained), path.join(home, '.codex', 'trash'));
      assert.equal(fs.readFileSync(path.join(retained, 'target-only.txt'), 'utf8'), 'previous copy only');
      const undo = page.locator('.toast').getByRole('button', {name:'Undo', exact:true});
      await undo.waitFor();
      assert.deepEqual(operations, ['remove', 'sync']);
      await expectAttentionCount(count - 1);
      await attention.getByRole('heading', {name:'Fixed · 1', exact:true}).waitFor();
      assert.deepEqual(fs.readFileSync(target), fs.readFileSync(file('.claude', name)));
      await undo.click();
      await page.locator('.toast').getByText(/^Undone/).waitFor();
      assert.deepEqual(fs.readFileSync(target), before);
      assert.equal(fs.readFileSync(companion, 'utf8'), 'previous copy only');
      assert(!fs.existsSync(retained));
      await expectAttentionCount(count);
      await attentionItem(id).waitFor();
      await attention.getByRole('heading', {name:/^Fixed ·/}).waitFor({state:'hidden'});
    } finally {
      await page.unroute(endpoint, delay);
      fs.mkdirSync(path.dirname(target), {recursive:true});
      fs.writeFileSync(target, before);
      fs.rmSync(companion, {force:true});
    }
  });
  await test('Needs attention clears failed review controls on a return visit', async () => {
    const endpoint = '**/api/batch/execute';
    let attempts = 0;
    const refuse = route => {
      attempts++;
      return route.fulfill({status:409, json:{error:'Fixture refused the write'}});
    };
    await page.route(endpoint, refuse);
    try {
      await openAttention('majority-minor:codex:different');
      await attention.getByRole('button', {name:/^The shared version/}).click();
      await attention.locator('[data-primary]:enabled').click();
      const retry = attention.getByRole('button', {name:'Check again', exact:true});
      await retry.waitFor();
      await attentionHeading.focus();
      await page.keyboard.press('f');
      await page.waitForTimeout(250);
      assert.equal(attempts, 1);
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.waitForURL(url => url.hash === '#/skills');
      await attentionNav.click();
      await attentionHeading.waitFor();
      await retry.waitFor({state:'hidden'});
      await attention.locator('.jf-attention-detail[aria-busy="false"]').waitFor();
      assert(await attention.getByRole('button', {name:'Skip for now', exact:true}).isEnabled());
    } finally { await page.unroute(endpoint, refuse); }
  });
  await test('Needs attention restores fix choices when permissions recover on return', async () => {
    let readOnly = false;
    const scopes = url => url.pathname === '/api/scopes';
    const scopeHandler = async route => {
      const response = await route.fetch(), rows = await response.json();
      if (readOnly) Object.assign(rows.find(row => row.id === 'codex'), {writable:false, availability:'read-only'});
      await route.fulfill({response, json:rows});
    };
    const endpoint = '**/api/batch/execute';
    const refuse = route => { readOnly = true; return route.fulfill({status:409, json:{error:'Fixture write refused'}}); };
    await page.route(scopes, scopeHandler);
    await page.route(endpoint, refuse);
    try {
      await openAttention('majority-minor:codex:different');
      await attention.getByRole('button', {name:/^The shared version/}).click();
      await attention.locator('[data-primary]:enabled').click();
      await attention.getByText(/can.t safely identify the folders/).waitFor();
      readOnly = false;
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.waitForURL(url => url.hash === '#/skills');
      await attentionNav.click();
      await attentionHeading.waitFor();
      await attentionItem('majority-minor:codex:different').click();
      await attention.getByRole('button', {name:/^The shared version/}).waitFor();
    } finally {
      await page.unroute(scopes, scopeHandler);
      await page.unroute(endpoint, refuse);
    }
  });
  await test('A delayed write failure is announced without restoring the old review state', async () => {
    const endpoint = '**/api/batch/execute';
    let release;
    const pending = new Promise(resolve => { release = resolve; });
    const delayed = async route => {
      await pending;
      await route.fulfill({status:409, json:{error:'Fixture write did not complete'}});
    };
    await page.route(endpoint, delayed);
    try {
      await openAttention('majority-minor:codex:different');
      await attention.getByRole('button', {name:/^The shared version/}).click();
      const requested = page.waitForRequest(attentionWrites);
      await attention.locator('[data-primary]:enabled').click();
      await requested;
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.locator('.jf-skills-screen').waitFor();
      release();
      await page.locator('.toast').getByText(/couldn’t confirm which folders changed/).waitFor();
      await attentionNav.click();
      await attentionHeading.waitFor();
      assert.equal(await attention.getByRole('button', {name:'Check again', exact:true}).count(), 0);
    } finally {
      release();
      await page.unroute(endpoint, delayed);
    }
  });
  await test('A completed change does not carry its Undo to a different screen', async () => {
    const active = file('.codex'), disabled = active + '.disabled';
    try {
      await go('skill/same-everywhere');
      await turnOffCodexFromReader();
      const undo = page.locator('.toast').getByRole('button', {name:'Undo', exact:true});
      await undo.waitFor();
      const edit = page.getByRole('button', {name:'Edit', exact:true});
      await edit.click();
      await page.locator('#ed-desc').waitFor();
      await undo.waitFor({state:'hidden'});
      assert.equal(await page.locator('#app > .sr-only[aria-live]').textContent(), '');
      assert(fs.existsSync(disabled));
    } finally { if (fs.existsSync(disabled) && !fs.existsSync(active)) fs.renameSync(disabled, active); }
  });
  await test('Stale file toggle reports error without resurrecting fixture',async()=>{await go('skill/same-everywhere');const f=file('.codex'),old=fs.readFileSync(f);fs.unlinkSync(f);try{await turnOffCodexFromReader();await page.waitForTimeout(600);assert(!fs.existsSync(f));assert(!fs.existsSync(f+'.disabled'));await page.locator('.jf-panel').getByRole('alert').waitFor();}finally{fs.writeFileSync(f,old);}});
  await test('Native setting evidence is partial and file switch Undo preserves files',async()=>{await go('skill/same-everywhere');await page.locator('.native-settings summary').click();let t=await page.locator('.native-settings').innerText();assert.match(t,/partial/i);assert.match(t,/loading is unknown/i);assert.match(t,/Declared setting: off/);assert.match(t,/Declared setting: deny/);const f=file('.codex');await turnOffCodexFromReader();await page.waitForTimeout(500);assert(fs.existsSync(f+'.disabled'));await page.locator('.toast button').filter({hasText:'Undo'}).last().click();await page.waitForTimeout(600);assert(fs.existsSync(f));assert(!fs.existsSync(f+'.disabled'));});
  await test('Native invalid and unavailable settings render without exposing values',async()=>{let config=path.join(home,'.config/opencode/opencode.json'),saved=fs.readFileSync(config),claude=path.join(home,'.claude/settings.json'),oldClaude=fs.readFileSync(claude);fs.writeFileSync(config,'{"private":"fixture-secret",');fs.writeFileSync(claude,JSON.stringify({skillOverrides:{'majority-minor':'invalid-fixture-value'}}));try{await go('skill/majority-minor');await page.locator('.native-settings summary').click();let t=await page.locator('.native-settings').innerText();assert.match(t,/invalid/);assert.match(t,/unavailable/);assert.doesNotMatch(t,/fixture-secret|invalid-fixture-value/);}finally{fs.writeFileSync(config,saved);fs.writeFileSync(claude,oldClaude);}});
  await test('Discard navigation, dialog focus trap and cancellation',async()=>{await go('skill/same-everywhere');await page.getByRole('button',{name:'Edit',exact:true}).click();assert(await page.locator('#ed-desc').evaluate(e=>e===document.activeElement));await page.locator('.ed-area').fill('Unsaved browser fixture');await page.locator('.tabs a').filter({hasText:'Skills'}).click();await page.locator('.dlg').waitFor();for(let i=0;i<10;i++){await page.keyboard.press('Tab');assert(await page.evaluate(()=>document.querySelector('.dlg').contains(document.activeElement)));}await page.getByRole('button',{name:'Keep editing'}).click();assert(await page.locator('.ed-area').isVisible());await page.locator('.tabs a').filter({hasText:'Skills'}).click();await page.getByRole('button',{name:'Discard changes'}).click();await page.waitForTimeout(300);assert(page.url().endsWith('#/skills'));});
  await test('Trash & backups restores a library folder from the merged list', async () => {
    const target = libraryFile('library-fixture'), original = fs.readFileSync(target);
    await go('skill/library-fixture');
    await page.getByRole('button', {name:'Move to Trash', exact:true}).click();
    assert.equal(await page.locator('.pick input:checked').count(), 1);
    await page.locator('.dlg-f .btn-danger').click();
    await page.waitForURL(url => url.hash === '#/skills');
    assert(!fs.existsSync(target));
    await go('recovery');
    assert.equal(new URL(page.url()).hash, '#/trash');
    const restore = restoreButton('library-fixture', 'Your library');
    await restore.click();
    const review = page.getByRole('dialog', {name:'Restore library-fixture?', exact:true});
    assert(!fs.existsSync(target));
    await review.getByRole('button', {name:'Restore folder', exact:true}).click();
    await restore.waitFor({state:'hidden'});
    assert.deepEqual(fs.readFileSync(target), original);
    const restored = trashList.getByRole('link', {name:'Show restored copy', exact:true});
    await restored.waitFor();
    assert.match(await restored.getAttribute('href'), /scope=global/);
    await page.locator('.tabs a[href="#/skills"]').click();
    await page.waitForURL(url => url.hash === '#/skills');
    await page.locator('.tabs a[href="#/trash"]').click();
    await trashScreen.getByRole('heading', {name:'Trash & backups', exact:true}).waitFor();
    assert.equal(await restored.count(), 0);
  });
  await test('Trash & backups restores the exact library copy of a skill named purge', async () => {
    const trashed = [];
    const installed = path.dirname(libraryFile('purge'));
    try {
      for (const [i, body] of ['Older content.', 'Newer content.'].entries()) {
        const created = await page.request.post(base+'/api/skills', {data:{name:'purge', description:'Recovery test fixture.', body}});
        assert.equal(created.status(), 201);
        const removed = await page.request.delete(base+'/api/skills/purge?scope=global');
        assert.equal(removed.status(), 200);
        trashed.push((await removed.json()).trash_path);
        fs.utimesSync(trashed[i], 1700000000 + i * 60, 1700000000 + i * 60);
      }
      await go('trash');
      await restoreButton('purge', 'Your library', 'copy 1 of 2').waitFor();
      await restoreButton('purge', 'Your library', 'copy 2 of 2').click();
      const review = page.getByRole('dialog', {name:'Restore purge?', exact:true});
      const restoring = page.waitForResponse(r => {
        const url = new URL(r.url());
        return r.request().method() === 'POST' && url.pathname === '/api/trash/purge' && url.searchParams.get('scope') === 'global';
      });
      await review.getByRole('button', {name:'Restore folder', exact:true}).click();
      const response = await restoring;
      assert(response.ok());
      assert.equal(response.request().postDataJSON().trash_path, trashed[0]);
      await review.waitFor({state:'hidden'});
      assert.match(fs.readFileSync(libraryFile('purge'), 'utf8'), /Older content\./);
      assert(!fs.existsSync(trashed[0]));
      assert(fs.existsSync(trashed[1]));
    } finally {
      for (const dir of [installed, ...trashed]) fs.rmSync(dir, {recursive:true, force:true});
    }
  });
  for (const [name,sourceDisabled,targetDisabled] of [['target-disabled',false,true],['source-disabled',true,false]]) {
    await test(`Needs attention Undo restores ${name} bytes and disabled state`, async () => {
      const target = file('.codex', name), prior = target + (targetDisabled ? '.disabled' : '');
      const installed = target + (sourceDisabled ? '.disabled' : '');
      const source = file('.claude', name) + (sourceDisabled ? '.disabled' : '');
      const old = fs.readFileSync(prior), sourceBytes = fs.readFileSync(source);
      try {
        await openAttention(name + ':split');
        await attention.getByRole('button', {name:/^Version [12]$/}).filter({hasText:'claude original text'}).click();
        await attention.locator('[data-primary]:enabled').click();
        const undo = page.locator('.toast').getByRole('button', {name:'Undo', exact:true});
        await undo.waitFor();
        assert.deepEqual(fs.readFileSync(installed), sourceBytes);
        assert(!fs.existsSync(prior), 'fix should install the chosen copy’s disabled state');
        await undo.click();
        await page.locator('.toast').getByText(/^Undone/).waitFor();
        assert(!fs.existsSync(installed));
        assert.deepEqual(fs.readFileSync(prior), old);
      } finally {
        fs.rmSync(installed, {force:true});
        fs.mkdirSync(path.dirname(prior), {recursive:true});
        fs.writeFileSync(prior, old);
      }
    });
  }
  await test('Needs attention repairs malformed text and Undo brings its problem back', async () => {
    const name = 'damaged-fm', id = `${name}:codex:unreadable`;
    const target = file('.codex', name), before = fs.readFileSync(target);
    try {
      await openAttention(id);
      await attention.getByRole('button', {name:'Replace with the readable copy', exact:true}).click();
      const undo = page.locator('.toast').getByRole('button', {name:'Undo', exact:true});
      await undo.waitFor();
      await attention.getByRole('region', {name:'Fixed · 1', exact:true}).locator('[data-attention-id]').waitFor();
      assert.deepEqual(fs.readFileSync(target), fs.readFileSync(file('.claude', name)));
      await undo.click();
      await page.locator('.toast').getByText(/^Undone/).waitFor();
      await attentionItem(id).waitFor();
      assert.deepEqual(fs.readFileSync(target), before);
      await attention.getByRole('heading', {name:/^Fixed ·/}).waitFor({state:'hidden'});
    } finally {
      fs.mkdirSync(path.dirname(target), {recursive:true});
      fs.writeFileSync(target, before);
    }
  });
  await test('Create, editor focus, safe Markdown, save and Undo',async()=>{
    await go('skills');
    await page.getByRole('link',{name:'New skill',exact:true}).first().click();
    const name=page.getByLabel('Name', {exact:true});
    assert(await name.evaluate(e=>e===document.activeElement));
    await name.fill('created-browser');

    await page.locator('#nf-desc').fill('Use this fixture to verify browser creation.');
    await page.getByRole('button',{name:'Create in 1 place',exact:true}).click();
    await page.getByRole('button',{name:'Edit',exact:true}).waitFor();
    const createdToast = page.locator('.toast').getByText('created-browser created in 1 place.', {exact:true});
    await createdToast.waitFor();
    const live = page.locator('#app > .sr-only[aria-live]');
    assert.equal(await live.textContent(), 'created-browser created in 1 place.');
    const f=file('.claude','created-browser'), original=fs.readFileSync(f);
    await page.getByRole('button',{name:'Edit',exact:true}).click();
    await createdToast.waitFor({state:'hidden'});
    assert.equal(await live.textContent(), '');
    assert(await page.locator('#ed-desc').evaluate(e=>e===document.activeElement));
    await page.locator('#ed-body').fill('Name | Result\n--- | ---\n*italic* | [docs](https://example.test/a)\n\n<img src=x onerror="window.fixtureAttack=1">');
    await page.getByRole('button',{name:'Preview',exact:true}).click();
    assert.equal(await page.locator('.doc th').count(),2);
    assert.equal(await page.locator('.doc em').innerText(),'italic');
    assert.equal(await page.locator('.doc a,.doc img,.doc script').count(),0);
    assert.equal(await page.evaluate(()=>window.fixtureAttack),undefined);
    await page.locator('.savebar button').filter({hasText:'Save to'}).click();
    const undo = page.locator('.toast').filter({hasText:'created-browser saved to 1 place.'})
      .getByRole('button',{name:'Undo',exact:true});
    await undo.waitFor();
    assert.notDeepEqual(fs.readFileSync(f),original);
    const restore = page.waitForResponse(response => {
      const url = new URL(response.url());
      return response.request().method() === 'POST' && url.pathname === '/api/trash/created-browser'
        && url.searchParams.has('snapshot');
    });
    await undo.click();
    assert((await restore).ok());
    assert.deepEqual(fs.readFileSync(f),original);
  });
  await test('Leaving while creation refresh is pending does not show stale success', async () => {
    const name = 'pending-create-feedback';
    await go('skills');
    await page.getByRole('link', {name:'New skill', exact:true}).first().click();
    await page.getByLabel('Name', {exact:true}).fill(name);
    await page.locator('#nf-desc').fill('Use this fixture to verify navigation during refresh.');
    let release;
    const pending = new Promise(resolve => { release = resolve; });
    let requestSeen;
    const seen = new Promise(resolve => { requestSeen = resolve; });
    const endpoint = '**/api/skills?scope=all&body=0';
    const delay = async route => { requestSeen(); await pending; await route.continue(); };
    await page.route(endpoint, delay);
    try {
      await page.getByRole('button', {name:'Create in 1 place', exact:true}).click();
      await seen;
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.waitForURL(url => url.hash === '#/skills');
      const refreshed = page.waitForResponse(response => response.url().includes('/api/skills?scope=all&body=0'));
      release();
      await refreshed;
      await page.waitForTimeout(250);
      assert.equal(new URL(page.url()).hash, '#/skills');
      assert.equal(await page.locator('.toast').getByText(name + ' created in 1 place.', {exact:true}).count(), 0);
      assert.equal(await page.locator('#app > .sr-only[aria-live]').textContent(), '');
    } finally {
      release();
      await page.unroute(endpoint, delay);
      await page.request.delete(`${base}/api/skills/${name}?scope=claude-code&purge=1`);
    }
  });
  await test('Permanent deletion confirms on the Skills screen', async () => {
    const name = 'permanent-feedback-browser';
    const created = await page.request.post(base + '/api/skills?scope=claude-code', {
      data:{name, description:'Use this fixture to verify deletion feedback.', body:'Fixture body.'},
    });
    assert.equal(created.status(), 201);
    try {
      await go('skill/' + name);
      await page.getByText('Permanent removal', {exact:true}).click();
      await page.getByRole('button', {name:'Delete permanently', exact:true}).click();
      const dialog = page.getByRole('dialog', {name:/Permanently delete/});
      await dialog.locator('input[type=checkbox]').check();
      await dialog.getByRole('button', {name:'Delete permanently', exact:true}).click();
      await page.waitForURL(url => url.hash === '#/skills');
      await page.locator('.toast').getByText('Selected copies permanently deleted.', {exact:true}).waitFor();
      assert.equal(await page.locator('#app > .sr-only[aria-live]').textContent(), 'Selected copies permanently deleted.');
    } finally {
      await page.request.delete(`${base}/api/skills/${name}?scope=claude-code&purge=1`);
    }
  });
  await test('Markdown readers render tables, nested lists and safe content',async()=>{
    try {
      for (const width of [320, 768, 1024, 1440]) {
        await page.setViewportSize({width,height:900});
        await go('skill/markdown-reader');
        const table = page.locator('.doc').getByRole('table');
        await table.waitFor();
        assert.equal(await table.getByRole('columnheader').count(),6);
        assert.equal(await table.locator('tbody td code').first().innerText(),'a|b');
        assert.equal(await table.locator('tbody td').nth(1).evaluate(e=>getComputedStyle(e).textAlign),'right');
        assert.equal(await page.locator('.doc ul li ul li').innerText(),'Nested detail');
        assert(await page.locator('.doc').getByRole('checkbox',{name:'Completed'}).isChecked());
        assert.match(await page.locator('.doc pre').innerText(),/<tag>/);
        assert.equal(await page.locator('.doc :is(a,img,script)').count(),0);
        const overflow = await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
        assert(overflow <= 1, `Page overflow of ${overflow}px at ${width}px`);
        if (width===320) {
          const wrapper = page.locator('.doc').getByRole('region',{name:'Markdown table'});
          assert(await wrapper.evaluate(e=>e.scrollWidth>e.clientWidth));
          await wrapper.focus();
          await page.keyboard.press('ArrowRight');
          await page.waitForFunction(()=>document.activeElement.scrollLeft>0);
        }
      }
    } finally {
      await page.setViewportSize({width:1280,height:900});
    }
  });
  await test('One-place dialogs preselect and cancellation keeps files',async()=>{
    await go('skill/sole-copy');
    const f=file('.claude','sole-copy'),before=fs.readFileSync(f);
    await page.getByRole('button',{name:'Move to Trash',exact:true}).click();
    assert.equal(await page.locator('.pick input:checked').count(),1);
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    assert.deepEqual(fs.readFileSync(f),before);
  });
  await test('Reader diagnosis and copy locations state what will be inspected', async () => {
    await go('skill/majority-minor');
    await page.getByText('Folder locations and source updates', {exact:true}).click();
    const codex = page.locator('.folder-paths > div').filter({hasText:'Codex'});
    assert.equal(await codex.locator('code').innerText(), path.dirname(file('.codex', 'majority-minor')));
    await page.getByText('AI maintenance', {exact:true}).click();
    const trigger = page.getByRole('button', {name:'Test a prompt or trace'});
    await trigger.click();
    const dialog = page.getByRole('dialog', {name:/^Why didn.t this skill run\?$/});
    await dialog.getByRole('heading', {name:'Discovery on disk'}).waitFor();
    await dialog.getByText('Skill folder', {exact:true}).press('Enter');
    assert.match(await dialog.locator('.ai-diagnosis .paths code').innerText(), /majority-minor$/);
    await dialog.getByRole('button', {name:'Cancel'}).click();
    assert(await trigger.evaluate(element => element === document.activeElement));
  });
  await test('Why page separates observed settings from unknown runtime and rechecks disk (F6)', async () => {
    const settings = path.join(home, '.claude/settings.json'), original = fs.readFileSync(settings);
    try {
      await page.setViewportSize({width:390,height:844});
      await go('skill/same-everywhere');
      await page.getByRole('link', {name:/Why isn.t it running/}).click();
      await page.getByRole('heading', {name:/Why isn.t same-everywhere running/}).waitFor();
      await page.getByRole('heading', {name:/Claude Code.s own settings turn this skill off/}).waitFor();
      const checks = page.getByRole('region', {name:'Checks in each place'});
      const loaded = checks.getByRole('row').filter({hasText:'Actually loaded'});
      assert.equal(await loaded.getByRole('cell', {name:'Unknown', exact:true}).count(), 4);
      assert(await checks.evaluate(element => element.scrollWidth > element.clientWidth));
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      fs.writeFileSync(settings, '{}');
      await page.getByRole('button', {name:'Check again', exact:true}).click();
      await page.getByRole('heading', {name:/OpenCode.s own settings turn this skill off/}).waitFor();
      await page.reload();
      await page.getByRole('heading', {name:/OpenCode.s own settings turn this skill off/}).waitFor();
      await page.getByRole('navigation', {name:'Breadcrumb'}).getByRole('link', {name:'same-everywhere'}).click();
      await page.locator('.jf-reader-heading').waitFor();
    } finally {
      fs.writeFileSync(settings, original);
      await page.setViewportSize({width:1280,height:900});
    }
  });
  await test('Why prioritizes problems in existing copies and links to the skill', async () => {
    const enabled = file('.agents', 'share-three'), disabled = enabled + '.disabled';
    try {
      await go('skills/share-three/why');
      const card = page.locator('.jf-why-next');
      const noFailure = page.locator('.jf-why-no-failure');
      await noFailure.getByText(/Missing copies matter only/).waitFor();
      assert.equal(await card.count(), 0);
      assert.equal(await noFailure.getByRole('link', {name:'Open skill page'}).getAttribute('href'), '#/skills/share-three');
      fs.renameSync(enabled, disabled);
      await noFailure.getByRole('button', {name:'Check again'}).click();
      await card.getByRole('heading', {name:'The file is switched off in Shared folder'}).waitFor();
      await card.getByRole('link', {name:'Open skill page'}).click();
      await page.locator('.jf-reader-heading').waitFor();
    } finally {
      if (fs.existsSync(disabled)) fs.renameSync(disabled, enabled);
    }
  });
  await test('Porting notes and risk findings run with AI off', async () => {
    await go('skill/sole-copy');
    await page.getByText('AI maintenance', {exact:true}).click();
    await page.getByRole('button', {name:'Check agent compatibility'}).click();
    const skill = page.getByLabel('Skill', {exact:true});
    await page.waitForURL(url => url.hash === '#/advanced/ai-port');
    await skill.waitFor();
    assert.equal(await skill.inputValue(), 'sole-copy');
    await page.getByRole('button', {name:'Find the facts'}).click();
    await page.getByText('Nothing agent-specific found').waitFor();
    await go('tools/ai-explain');
    await skill.selectOption('sole-copy');
    await page.getByRole('button', {name:'Scan', exact:true}).click();
    await page.getByText('No findings', {exact:true}).waitFor();
  });
  await test('Add-to-agent single target is selected and creates a copy',async()=>{
    await go('skill/share-three');await page.getByRole('button',{name:'Add to agent',exact:true}).click();
    assert.equal(await page.locator('.pick input:checked').count(),1);
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    const f=file('.config/opencode','share-three');assert(!fs.existsSync(f));
    await page.getByRole('button',{name:'Add to agent',exact:true}).click();
    await page.locator('.dlg-f button').filter({hasText:/^Add$/}).click();
    await page.waitForTimeout(500);assert(fs.existsSync(f));
    await page.getByRole('button',{name:'Undo',exact:true}).click();
    await page.locator('.toast').getByText('Undone',{exact:true}).waitFor();
    assert(!fs.existsSync(f));
  });
  await test('Trash explains library-only emptying and limits large lists', async () => {
    const trashRoute = url => url.pathname === '/api/trash' && !url.searchParams.has('scope');
    const agentTrashRoute = url => url.pathname === '/api/trash' && url.searchParams.has('scope');
    const historyRoute = url => url.pathname === '/api/history' && url.searchParams.get('limit') === '8';
    const now = new Date().toISOString();
    const rows = Array.from({length:103}, (_, i) => ({name:`fixture-trash-${i}`, trash_path:`/fixture/trash/${i}`, trashed_at:now}));
    const history = Array.from({length:103}, (_, i) => ({id:i+1, action:'create', name:`fixture-history-${i}`, at:now}));
    try {
      await page.route(trashRoute, route => route.fulfill({json:rows}));
      await page.route(agentTrashRoute, route => route.fulfill({json:[]}));
      await page.route(historyRoute, route => route.fulfill({json:history}));
      await go('trash');
      await trashList.getByRole('heading', {name:'Trash · 103'}).waitFor();
      assert.equal(await trashList.locator('.jf-trash-entry').count(),50);
      await trashList.getByRole('button',{name:'Show 50 more trash items'}).click();
      assert.equal(await trashList.locator('.jf-trash-entry').count(),100);
      await trashList.getByRole('button',{name:'Show 3 more trash items'}).press('Enter');
      assert.equal(await trashList.locator('.jf-trash-entry').count(),103);
      assert(await trashList.locator('.jf-trash-entry').nth(100).evaluate(row => row === document.activeElement));
      const recent = trashScreen.locator('section[aria-labelledby="rec-history"]');
      assert.equal(await recent.locator('.jf-trash-recent').count(),50);
      assert(await recent.locator('.jf-trash-recent').first().evaluate(row => {
        const time = row.lastElementChild.getBoundingClientRect();
        const inset = Number.parseFloat(getComputedStyle(row).paddingInlineEnd);
        return Math.abs(row.getBoundingClientRect().right - time.right - inset) < 1;
      }));
      await recent.getByRole('button',{name:'Show 50 more changes'}).click();
      assert.equal(await recent.locator('.jf-trash-recent').count(),100);
      await recent.getByRole('button',{name:'Show 3 more changes'}).press('Enter');
      assert.equal(await recent.locator('.jf-trash-recent').count(),103);
      assert(await recent.locator('.jf-trash-recent').nth(100).evaluate(row => row === document.activeElement));
    } finally {
      await page.unroute(trashRoute);
      await page.unroute(agentTrashRoute);
      await page.unroute(historyRoute);
    }
    await page.route(trashRoute, route => route.fulfill({json:[]}));
    try {
      await go('trash');
      await trashList.getByText('Library trash is empty. Agent trash is not emptied here.').waitFor();
      assert(await trashList.getByRole('button',{name:'Empty library trash…'}).isDisabled());
    } finally { await page.unroute(trashRoute); }
    await page.route(trashRoute, route => route.fulfill({status:503,json:{error:'Library unavailable'}}));
    try {
      await go('trash');
      await trashList.getByText('Library trash could not be read. Retry trash first.').waitFor();
      assert(await trashList.getByRole('button',{name:'Empty library trash…'}).isDisabled());
    } finally { await page.unroute(trashRoute); }
  });
  await test('Trash backup preview distinguishes no changes from full metadata additions', async () => {
    await go('trash');
    const downloadPreference = 'jackfield-last-library-backup';
    const previousDownload = await page.evaluate(key => localStorage.getItem(key), downloadPreference);
    const backup = trashScreen.locator('section[aria-labelledby="rec-backup"]');
    const input = backup.locator('#imp-file');
    const download = async (label, filename) => {
      const event = page.waitForEvent('download');
      await backup.getByRole('button',{name:label,exact:true}).click();
      const saved = path.join(root, filename);
      await (await event).saveAs(saved);
      return saved;
    };
    const catalog = path.join(root,'data','jackfield','catalog','metadata.json');
    const savedCatalog = fs.existsSync(catalog) ? fs.readFileSync(catalog) : null;
    try {
      const ordinary = await download('Download backup','unchanged.tar.gz');
      const full = await download('Download full archive','unchanged-full.tar.gz');
      await input.setInputFiles(ordinary);
      await backup.getByRole('button',{name:'Preview backup'}).click();
      await backup.getByText('No entries will change.').waitFor();
      assert(await backup.getByRole('button',{name:'Load backup',exact:true}).isDisabled());
      if (savedCatalog) fs.unlinkSync(catalog);
      await input.setInputFiles(full);
      await backup.getByLabel('Include library trash, templates, and catalog metadata').check();
      await backup.getByRole('button',{name:'Preview backup'}).click();
      const preview = backup.getByRole('region',{name:'Backup preview'});
      await preview.getByText('Add · Catalog').waitFor();
      assert(await preview.getByRole('button',{name:'Load backup',exact:true}).isEnabled());
    } finally {
      if (savedCatalog) fs.writeFileSync(catalog,savedCatalog);
      await page.evaluate(([key,value]) => {
        if (value === null) localStorage.removeItem(key);
        else localStorage.setItem(key, value);
      }, [downloadPreference, previousDownload]);
    }
  });
  await test('Trash & backups records a download only after successful handoff', async () => {
    await go('trash');
    const backup = trashScreen.locator('section[aria-labelledby="rec-backup"]');
    const lastDownload = backup.getByText(/^Last download started/);
    assert.equal(await lastDownload.count(), 0);
    const full=backup.getByRole('button',{name:'Download full archive'});
    const pattern=/\/api\/export\?full=1$/;
    let release, downloads=0;
    const pending=new Promise(resolve=>{release=resolve;});
    const countDownload=()=>{downloads++;};
    page.on('download',countDownload);
    await page.route(pattern,async route=>{
      await pending;
      await route.fulfill({status:409,json:{code:'backup_source_changed',error:'/private/source changed'}});
    });
    try {
      await full.click();
      await backup.getByRole('status').getByText('Preparing backup…').waitFor();
      assert(await full.isDisabled());
      assert(await backup.getByRole('button',{name:'Download backup', exact:true}).isDisabled());
      release();
      const alert=backup.getByRole('alert');
      await alert.waitFor();
      assert.match(await alert.innerText(),/Wait for changes to finish/);
      assert.doesNotMatch(await alert.innerText(),/private|HTTP 409/);
      assert.equal(downloads,0);
      assert.equal(await lastDownload.count(), 0);
      await page.unroute(pattern);
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.waitForURL(url => url.hash === '#/skills');
      await page.locator('.tabs a[href="#/trash"]').click();
      await backup.waitFor();
      assert.equal(await alert.count(), 0);
      const success=page.waitForEvent('download');
      await full.click();
      assert.equal((await success).suggestedFilename(),'full-export.tar.gz');
      await alert.waitFor({state:'detached'});
      await lastDownload.waitFor();
      const date = await lastDownload.innerText();
      const live = page.locator('#app > .sr-only[aria-live]');
      assert.equal(await live.textContent(), 'Backup download started.');
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.locator('.jf-skills-screen').waitFor();
      assert.equal(await live.textContent(), '');
      assert.equal(await page.locator('.toast').getByText('Backup download started.').count(), 0);
      await page.locator('.tabs a[href="#/trash"]').click();
      await lastDownload.waitFor();
      await page.reload();
      await lastDownload.waitFor();
      assert.equal(await lastDownload.innerText(), date);
    } finally {
      release();
      await page.unroute(pattern);
      page.off('download',countDownload);
    }
  });
  await test('Trash & backups previews an archive before loading and explains invalid archives', async () => {
    const name = 'phase-four-archive-load';
    const installed = libraryFile(name);
    const companion = path.join(path.dirname(installed), 'notes.txt');
    const companionBytes = Buffer.from('Archived supporting file.\r\n');
    const collision = libraryFile('library-fixture');
    const collisionBefore = fs.readFileSync(collision);
    const seeded = await page.request.post(base + '/api/skills', {
      data:{name, description:'Private archive review fixture.', body:'# A skill to restore\n'},
    });
    assert.equal(seeded.status(), 201);
    const original = fs.readFileSync(installed);
    fs.writeFileSync(companion, companionBytes);
    await go('trash');
    const download = page.waitForEvent('download');
    await trashScreen.getByRole('button', {name:'Download backup', exact:true}).click();
    const saved = path.join(root, 'fixture-backup.tar.gz');
    await (await download).saveAs(saved);
    assert(fs.statSync(saved).size > 0);
    const removed = await page.request.delete(base + '/api/skills/' + name + '?scope=global');
    assert(removed.ok());

    const section = trashScreen.locator('section[aria-labelledby="rec-backup"]');
    const input = section.locator('#imp-file');
    const preview = section.getByRole('button', {name:'Preview backup', exact:true});
    const load = section.getByRole('button', {name:'Load backup', exact:true});
    const isImport = req => req.method() === 'PUT' && new URL(req.url()).pathname === '/api/import';
    const requests = [];
    const observe = req => { if (isImport(req)) requests.push(new URL(req.url()).searchParams); };
    page.on('request', observe);
    try {
      await input.setInputFiles(saved);
      await preview.click();
      await load.waitFor();
      const plan = section.getByRole('region', {name:'Backup preview', exact:true});
      const add = plan.getByRole('listitem').filter({has:page.getByText(name, {exact:true})});
      const skip = plan.getByRole('listitem').filter({has:page.getByText('library-fixture', {exact:true})});
      assert.match(await add.innerText(), /Add.*library/i);
      assert.match(await skip.innerText(), /Skip.*library/i);
      await skip.getByText('already exists', {exact:true}).waitFor();
      assert(await plan.getByRole('heading').evaluate(heading => heading === document.activeElement));
      assert.deepEqual(requests.map(q => q.get('preview')), ['1']);
      assert(!fs.existsSync(installed));
      assert.deepEqual(fs.readFileSync(collision), collisionBefore);

      await section.getByRole('button', {name:'Cancel preview', exact:true}).click();
      await load.waitFor({state:'hidden'});
      assert(await preview.evaluate(button => button === document.activeElement));
      assert.equal(requests.length, 1);
      assert(!fs.existsSync(installed));
      await preview.click();
      await load.waitFor();
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.waitForURL(url => url.hash === '#/skills');
      await page.locator('.tabs a[href="#/trash"]').click();
      await section.waitFor();
      assert.equal(await load.count(), 0);
      assert.equal(await input.evaluate(element => element.files.length), 0);
      await input.setInputFiles(saved);
      await preview.click();
      await load.waitFor();
      const commitResponse = () => page.waitForResponse(response => isImport(response.request()) &&
        !!new URL(response.url()).searchParams.get('plan_id'));
      const external = Buffer.concat([original, Buffer.from('\nCreated outside Jackfield after preview.\n')]);
      fs.mkdirSync(path.dirname(installed));
      fs.writeFileSync(installed, external);
      try {
        const stale = commitResponse();
        await load.click();
        assert(!(await stale).ok());
        await section.getByRole('alert').filter({hasText:/preview is stale|preview.*again/i}).waitFor();
        assert.deepEqual(fs.readFileSync(installed), external);
        assert(!fs.existsSync(companion));
        assert.deepEqual(fs.readFileSync(collision), collisionBefore);
      } finally {
        fs.unlinkSync(installed);
        fs.rmdirSync(path.dirname(installed));
      }

      await input.setInputFiles(saved);
      await preview.click();
      await load.waitFor();
      const committed = commitResponse();
      await load.click();
      assert((await committed).ok());
      assert.deepEqual(requests.map(q => q.get('preview')), ['1', '1', '1', null, '1', null]);
      assert(requests[3].get('plan_id'));
      assert(requests[5].get('plan_id'));
      assert.deepEqual(fs.readFileSync(installed), original);
      assert.deepEqual(fs.readFileSync(companion), companionBytes);
      assert.deepEqual(fs.readFileSync(collision), collisionBefore);
      await section.getByText(/1 skill imported/).waitFor();
      await section.getByText('Skipped entries', {exact:true}).click();
      await section.getByText('library-fixture', {exact:true}).waitFor();
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.locator('.jf-skills-screen').waitFor();
      await page.locator('.tabs a[href="#/trash"]').click();
      await section.waitFor();
      assert.equal(await section.getByText(/1 skill imported/).count(), 0);

      const bad = path.join(root, 'bad-archive.tar.gz');
      fs.writeFileSync(bad, 'not an archive');
      await page.waitForFunction(() => !document.getElementById('imp-file').disabled);
      await input.setInputFiles(bad);
      await preview.click();
      const error = await section.getByRole('alert').innerText();
      assert.match(error, /not a backup archive/);
      assert.doesNotMatch(error, /ReadError|Traceback|[/]tmp[/]/);
      assert(!(await load.isVisible()));
      await input.setInputFiles({name:'wrong.txt', mimeType:'text/plain', buffer:Buffer.from('fixture')});
      await section.getByRole('alert').filter({hasText:/not a backup file/}).waitFor();
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.locator('.jf-skills-screen').waitFor();
      await page.locator('.tabs a[href="#/trash"]').click();
      await section.waitFor();
      assert.equal(await section.getByRole('alert').count(), 0);
    } finally { page.off('request', observe); }
    await page.route('**/api/scopes',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'Traceback /home/private/secret PermissionError'})}));
    try{await go('home');assert.doesNotMatch(await page.locator('main').innerText(),/Traceback|PermissionError|[/]home[/]private/);}finally{await page.unrouteAll({behavior:'wait'});}
  });
  await test('Skills totals and navigation targets remain usable',async()=>{
    await go('skills');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    assert.match(await page.locator('.jf-grid-count').innerText(), /^Showing \d+ of \d+$/);
    assert.doesNotMatch(await page.locator('main').innerText(),/1 copy differ(?!s)/);
    const box=await page.locator('.top .tabs a[href="#/advanced"]').boundingBox();assert(box.height>=24);assert(box.width>=24);
  });
  await test('Retired shelf links retain search on reload', async () => {
    await page.goto(base+'/?fixture-step='+(++navigation)+'#/skills?view=shelf&q=majority-minor');
    await page.waitForURL(url => url.hash === '#/skills?q=majority-minor');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    const filter = page.getByRole('searchbox',{name:'Filter skills'});
    assert.equal(await filter.inputValue(),'majority-minor');
    await page.reload();
    assert.equal(await filter.inputValue(),'majority-minor');
    assert.equal(await page.locator('.jf-grid tbody tr').count(), 1);
  });
  await test('Skills reads copy states, filters, and returns keyboard focus from details', async () => {
    await page.setViewportSize({width:768,height:900});
    try {
      await go('skills');
      const welcome = page.getByRole('button', {name:'Show my skills'});
      if (await welcome.isVisible()) await welcome.click();
      const filter = page.getByRole('searchbox', {name:'Filter skills'});
      const square = page.getByRole('button', {name:'majority-minor in Codex: Different'});
      await square.waitFor();
      await filter.fill('majority-minor');
      assert.equal(await page.locator('.jf-grid tbody tr').count(), 1);
      await square.focus();
      await page.keyboard.press('Enter');
      const panel = page.getByRole('dialog', {name:'majority-minor'});
      await panel.waitFor();
      assert(await panel.evaluate(el => el.contains(document.activeElement)));
      await page.keyboard.press('Escape');
      await panel.waitFor({state:'hidden'});
      assert(await square.evaluate(el => el === document.activeElement));
      await filter.fill('no-such-fixture');
      await page.getByText('No skills match this filter.').waitFor();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    } finally {
      await page.setViewportSize({width:1280,height:900});
    }
  });
  await test('Copy comparison wraps on phones, reads the selected path and recovers after a read failure', async () => {
    const target = file('.codex', 'majority-minor');
    const original = fs.readFileSync(target);
    const longLine = '# ' + 'long-unbroken-markdown-path-'.repeat(30);
    fs.appendFileSync(target, '\n'+longLine+'\n');
    let allowRead = false;
    const match = url => url.pathname==='/api/skills/majority-minor' && url.searchParams.get('scope')==='codex';
    const request = route => allowRead ? route.continue() : route.fulfill({status:503, contentType:'application/json', body:'{"error":"Fixture read unavailable"}'});
    await page.route(match, request);
    try {
      await page.setViewportSize({width:1440,height:960});
      await openAttention('majority-minor:codex:different');
      await attention.getByRole('button', {name:/^The shared version/}).click();
      const panel = page.getByRole('region', {name:'Document comparison'});
      assert.match(await panel.getByRole('alert').innerText(), /Codex.*Fixture read unavailable/);
      assert((await panel.innerText()).includes(path.dirname(target)));
      allowRead = true;
      await panel.getByRole('button', {name:'Retry comparison'}).focus();
      await page.keyboard.press('Enter');
      const removed = panel.locator('.compare-line.del code').filter({hasText:longLine});
      await removed.waitFor();
      assert.equal(await panel.getByRole('alert').count(), 0);
      assert(await panel.isVisible());
      const chooser = panel.getByRole('button', {name:'Unified view'});
      assert(await chooser.isVisible());
      assert.equal(await chooser.getAttribute('aria-pressed'), 'false');
      await chooser.click();
      assert.equal(await chooser.getAttribute('aria-pressed'), 'true');
      await chooser.click();
      await panel.screenshot({path:path.join(root,'copy-comparison-desktop.png')});
      for (const width of [390,320]) {
        await page.setViewportSize({width,height:844});
        assert(!(await chooser.isVisible()));
        assert(await removed.evaluate(e=>e.scrollWidth<=e.clientWidth+1));
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
        await panel.screenshot({path:path.join(root,'copy-comparison-'+width+'.png')});
      }

    } finally {
      fs.writeFileSync(target, original);
      await page.unroute(match, request);
      await page.setViewportSize({width:1280,height:900});
    }
  });
  await test('Skills retains the search when opening a details panel', async () => {
    await go('skills?q=majority-minor');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    const filter=page.getByRole('searchbox',{name:'Filter skills'});
    await page.getByRole('button',{name:'majority-minor in Codex: Different'}).click();
    await page.locator('.jf-panel').waitFor();
    assert.equal(await filter.inputValue(),'majority-minor');
    assert.equal(await page.locator('.jf-grid tbody tr').count(),1);
  });
  await test('Skills bounds rows and filters a large inventory', async () => {
    const list = /[/]api[/]skills[?]scope=all(?:&body=0)?$/;
    const records = await (await page.request.get(base+'/api/skills?scope=all')).json();
    const row = records.find(record => record.scope === 'codex' && record.name === 'same-everywhere');
    const many = Array.from({length:10000}, (_, i) => ({
      ...row, name:'fixture-'+String(i).padStart(5,'0'), path:undefined, physical_path:undefined, body:undefined,
    }));
    try {
      await page.route(list, route => route.fulfill({json:many}));
      await go('skills');
      const welcome = page.getByRole('button', {name:'Show my skills'});
      if (await welcome.isVisible()) await welcome.click();
      const table = page.getByRole('grid', {name:'Skills table'});
      assert.equal(await table.locator('tbody tr').count(), 50);
      await page.getByRole('button', {name:/Show 50 more/}).click();
      assert.equal(await table.locator('tbody tr').count(), 100);
      const filter = page.getByRole('searchbox', {name:'Filter skills'});
      await filter.fill('fixture-09999');
      assert.equal(await table.locator('tbody tr').count(), 1);
      assert.match(await table.locator('tbody tr').innerText(), /fixture-09999/);
    } finally { await page.unrouteAll({behavior:'wait'}); }
  });
  await test('Skills clears selected rows without changing files', async () => {
    await go('skills');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    const target=file('.codex','majority-minor'), before=fs.readFileSync(target);
    const select=page.getByRole('checkbox',{name:'Select majority-minor'});
    await select.check();
    await page.getByText('1 selected', {exact:true}).waitFor();
    await page.getByRole('button',{name:'Clear selection'}).click();
    assert(!(await select.isChecked()));
    assert.deepEqual(fs.readFileSync(target),before);
  });
  await test('Skills problem filter combines with name search', async () => {
    await go('skills');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    const table = page.getByRole('grid', {name:'Skills table'});
    const review = page.getByRole('button', {name:'Show only these', exact:true});
    const search = page.getByRole('searchbox', {name:'Filter skills'});
    await review.click();
    for (const name of ['damaged-one', 'majority-minor', 'split-even']) {
      assert(await table.getByRole('button',{name,exact:true}).isVisible(), name + ' needs review');
    }
    assert.equal(await table.getByRole('button',{name:'sole-copy',exact:true}).count(), 0);
    await search.fill('damaged');
    assert(await table.getByRole('button',{name:'damaged-one',exact:true}).isVisible());
    await search.fill('sole-copy');
    await page.getByText('No skills match this filter.').waitFor();
    await review.click();
    assert(await table.getByRole('button',{name:'sole-copy',exact:true}).isVisible());
  });
  await test('Skills displays duplicated copies and uninspected links', async () => {
    const list = '**/api/skills?scope=all&body=0';
    const records = await (await page.request.get(base+'/api/skills?scope=all&body=0')).json();
    const copy = records.find(record => record.scope === 'codex' && record.name === 'same-everywhere');
    const record = (name, suffix) => ({...copy, name, path:undefined, physical_path:`/fixture/${name}/${suffix}`});
    const fixtures = [record('repeated', 'one'), record('repeated', 'two'), {
      ...record('uninspected', 'link'), decode_error:'Link outside the managed root', content_hash:null,
    }];
    try {
      await page.route(list, route => route.fulfill({json:fixtures}));
      await go('skills');
      const welcome = page.getByRole('button', {name:'Show my skills'});
      if (await welcome.isVisible()) await welcome.click();
      const table = page.getByRole('grid', {name:'Skills table'});
      assert(await table.getByRole('button', {name:'repeated', exact:true}).isVisible());
      assert(await table.getByRole('button', {name:'uninspected', exact:true}).isVisible());
      assert(await table.getByRole('button', {name:"uninspected in Codex: Can't read"}).isVisible());
      await table.getByRole('button', {name:'repeated', exact:true}).click();
      const choices = page.getByLabel('Read copy').locator('option');
      await choices.filter({hasText:'/fixture/repeated/one'}).waitFor({state:'attached'});
      await choices.filter({hasText:'/fixture/repeated/two'}).waitFor({state:'attached'});
    } finally {
      await page.unroute(list);
    }
  });
  await test('Skills keeps Undo and restores the unsuccessful copy after a partial batch', async () => {
    const name = 'zz-batch-failure-fixture';
    const target = file('.codex', 'majority-minor');
    const before = fs.readFileSync(target);
    const additions = ['.claude', '.codex', '.agents'].map(scope => file(scope, name));
    const secondBefore = 'Different.';
    const endpoint = '**/api/batch/execute';
    try {
      for (const [i, filename] of additions.entries()) {
        fs.mkdirSync(path.dirname(filename));
        fs.writeFileSync(filename, `---\nname: ${name}\ndescription: Exercise partial sync.\n---\n${i === 1 ? secondBefore : 'Reference.'}\n`);
      }
      const secondBytes = fs.readFileSync(additions[1]);
      await page.route(endpoint, async route => {
        if (route.request().postDataJSON().operation !== 'sync') return route.continue();
        const response = await route.fetch();
        const body = await response.json();
        const failed = body.results.find(row => row.name === name);
        assert(failed && failed.status === 'ok');
        fs.rmSync(path.dirname(additions[1]), {recursive:true, force:true});
        Object.assign(failed, {status:'failed', error:'Fixture sync interrupted', synced:[]});
        body.ok = false; body.partial = true;
        await route.fulfill({response, json:body});
      });
      await go('skills');
      const welcome = page.getByRole('button', {name:'Show my skills'});
      if (await welcome.isVisible()) await welcome.click();
      await page.getByRole('checkbox', {name:'Select majority-minor'}).check();
      await page.getByRole('checkbox', {name:`Select ${name}`}).check();
      await page.getByLabel('Destination').selectOption('codex');
      await page.getByRole('button', {name:'Make these match in Codex'}).click();
      await page.getByRole('dialog').getByRole('button', {name:'Make these match',exact:true}).click();
      const toast = page.locator('.toast').filter({hasText:'1 copies changed. 1 could not be changed.'});
      await toast.waitFor();
      assert.notDeepEqual(fs.readFileSync(target), before);
      assert.deepEqual(fs.readFileSync(additions[1]), secondBytes);
      await toast.getByRole('button', {name:'Undo', exact:true}).click();
      await page.locator('.toast').filter({hasText:'Undone'}).waitFor();
      assert.deepEqual(fs.readFileSync(target), before);
      assert.deepEqual(fs.readFileSync(additions[1]), secondBytes);
    } finally {
      await page.unroute(endpoint);
      fs.writeFileSync(target, before);
      for (const filename of additions) fs.rmSync(path.dirname(filename), {recursive:true, force:true});
    }
  });
  await test('Responsive layouts in both themes', async () => {
    const viewport = page.viewportSize();
    try {
      for (const [label, width, height] of [['desktop', 1280, 900], ['phone', 390, 844]]) {
        for (const mode of ['light', 'dark']) {
          await page.setViewportSize({width, height});
          await go('skills');
          await theme(mode);
          for (const route of ['skills', 'skill/same-everywhere', 'attention', 'trash']) {
            if (route !== 'skills') await go(route);
            assert.equal(await page.locator('html').getAttribute('data-theme'), mode);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1),
              false, `${label} ${mode} ${route}`);
            await page.screenshot({path:path.join(root, `${label}-${mode}-${route.replace('/', '-')}.png`)});
          }
        }
      }
    } finally { await page.setViewportSize(viewport); }
  });
  await test('Phone dark Skills sampled text contrast',async()=>{
    await page.setViewportSize({width:390,height:844});await go('skills');await theme('dark');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    const samples=await page.locator('.jf-grid-skill button').evaluateAll(rows=>rows.map(row=>{
      const rgb=value=>value.match(/[0-9.]+/g).slice(0,3).map(Number);
      const lum=value=>rgb(value).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
      const foreground=getComputedStyle(row).color;
      let parent=row, background='';
      while(parent){const value=getComputedStyle(parent).backgroundColor;if(!/rgba\([^)]*,\s*0\)$/.test(value)){background=value;break;}parent=parent.parentElement;}
      const a=lum(foreground),b=lum(background);
      return {foreground,background,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
    }));
    assert(samples.length);for(const sample of samples)assert(sample.ratio>=4.5,JSON.stringify(sample));
    fs.writeFileSync(path.join(root,'skills-contrast.json'),JSON.stringify(samples,null,2)+'\n');
    await page.setViewportSize({width:1280,height:900});
  });
  await test('Empty and one-record Skills tables render without stale rows',async()=>{
    const response=await page.request.get(base+'/api/skills?scope=all'),records=await response.json();
    const selected=records.find(r=>r.name==='same-everywhere' && r.scope==='codex');assert(selected);
    for(const fixture of [[],[selected]]){
      await page.route(/[/]api[/]skills[?]scope=all(?:&body=0)?$/,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(fixture)}));
      try {
        await go('skills');
        const welcome = page.getByRole('button', {name:'Show my skills'});
        if (await welcome.isVisible()) await welcome.click();
        assert.equal(await page.locator('.jf-grid tbody tr').count(),fixture.length);
        if (fixture.length) assert(await page.getByRole('button',{name:/^same-everywhere in Codex:/}).isVisible());
        else assert(await page.getByRole('heading', {name:'No skills yet'}).isVisible());
      } finally {
        await page.unrouteAll({behavior:'wait'});
      }
    }
  });
  await test('Forced colors focus indicator',async()=>{await page.emulateMedia({forcedColors:'active'});await go('skills');await page.keyboard.press('Tab');assert(await page.evaluate(()=>matchMedia('(forced-colors: active)').matches && document.activeElement!==document.body && getComputedStyle(document.activeElement).outlineStyle!=='none'));await page.screenshot({path:path.join(root,'forced-colors.png')});await page.emulateMedia({forcedColors:'none'});});
  if(engine==='chromium' && headed) await test('Actual Chrome zoom at 200 and 400 percent',async()=>{
    const {execFileSync}=require('node:child_process');
    await page.setViewportSize({width:1280,height:900});await go('home');
    const windows=execFileSync('xwininfo',['-root','-tree'],{encoding:'utf8'});
    fs.writeFileSync(path.join(root,'x-windows.txt'),windows);
    const windowId=execFileSync('xdotool',['search','--onlyvisible','--class','[Cc]hrome'],{encoding:'utf8'}).trim().split('\n').pop();
    execFileSync('xdotool',['windowfocus','--sync',windowId]);
    execFileSync('xdotool',['key','--clearmodifiers','ctrl+0']);
    const baseline=await page.evaluate(()=>devicePixelRatio),samples=[];
    for(const [percent,keys] of [[200,5],[400,3]]){
      for(let n=0;n<keys;n++)execFileSync('xdotool',['key','--clearmodifiers','ctrl+equal']);
      await page.waitForTimeout(350);
      const sample=await page.evaluate(()=>({dpr:devicePixelRatio,width:innerWidth,client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));
      assert(Math.abs(sample.dpr/baseline-percent/100)<0.05,JSON.stringify({percent,baseline,...sample}));
      assert(sample.scroll<=sample.client+1,JSON.stringify(sample));samples.push({percent,...sample});
      for(const route of ['home','skills','skill/same-everywhere','map','attention','trash','advanced','advanced/doctor']){
        await go(route);
        await page.screenshot({path:path.join(root,`browser-zoom-${percent}-${route.replace('/','-')}.png`)});
        const overflow=await page.evaluate(()=>[...document.querySelectorAll('main *')].filter(e=>{const b=e.getBoundingClientRect();return b.width>0 && b.right>document.documentElement.clientWidth+1;}).map(e=>({tag:e.tagName,cls:e.className,text:e.innerText?.slice(0,80),width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right})));
        fs.writeFileSync(path.join(root,`overflow-${percent}-${route.replace('/','-')}.json`),JSON.stringify(overflow,null,2));
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1),false,`browser zoom ${percent}: ${route}`);
      }
      await go('skills');await page.getByRole('link',{name:'New skill',exact:true}).first().click();
      assert(await page.locator('#nf-name').evaluate(e=>e===document.activeElement));
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1),false);
      await page.keyboard.press('Escape');
    }
    fs.writeFileSync(path.join(root,'browser-zoom.json'),JSON.stringify(samples,null,2)+'\n');
    execFileSync('xdotool',['key','--clearmodifiers','ctrl+0']);
  });
  await test('V2 Templates creates a real stored template and a skill with metadata',async()=>{
    await go('tools/templates');
    const form=page.locator('form').filter({has:page.getByRole('heading',{name:'New template',exact:true})});
    await form.getByLabel('Name',{exact:true}).fill('v2-browser-template');
    await form.getByLabel('Document body',{exact:true}).fill('# Browser template\n\nUse this fixture for checks.');
    await form.getByRole('button',{name:'Save template',exact:true}).click();
    await page.getByRole('button',{name:'v2-browser-template',exact:true}).click();
    await page.getByRole('button',{name:'Use template',exact:true}).click();
    const create=page.locator('form').filter({has:page.getByRole('heading',{name:'Create skill from template',exact:true})});
    await create.getByLabel('Name',{exact:true}).fill('v2-browser-created');
    await create.getByLabel('Description',{exact:true}).fill('Use when running v2 browser verification.');
    await create.getByLabel('Category',{exact:true}).fill('quality');
    await create.getByRole('button',{name:'Create skill',exact:true}).click();
    await page.waitForResponse(r=>r.url().includes('/api/skills?scope=all')).catch(()=>{});
    const doc=path.join(root,'data/jackfield/skills/v2-browser-created/SKILL.md');
    assert(fs.existsSync(doc));assert.match(fs.readFileSync(doc,'utf8'),/Browser template/);assert.match(fs.readFileSync(doc,'utf8'),/category: quality/);
  });
  await test('V2 Profiles stores metadata and executes an exact enable-only plan',async()=>{
    await go('tools/profiles');const form=page.locator('form').filter({has:page.getByRole('heading',{name:'Profile details',exact:true})});
    await form.getByLabel('Name',{exact:true}).fill('v2-browser-profile');
    await form.getByLabel('Description',{exact:true}).fill('Browser fixture profile.');
    await form.getByLabel('Filter skills',{exact:true}).fill('v2-browser-created');await form.locator('.tp-pick-list label').filter({hasText:'v2-browser-created'}).locator('input').check();
    await form.getByPlaceholder('Add a name not installed yet').fill('absent-member');await form.getByRole('button',{name:'Add',exact:true}).click();
    await form.getByRole('textbox',{name:'Native off list',exact:true}).fill('same-everywhere');
    await form.getByRole('button',{name:'Save profile',exact:true}).click();
    const row=page.locator('.v2-tool-row').filter({has:page.locator('strong').filter({hasText:'v2-browser-profile'})});
    await row.waitFor();
    await page.getByRole('button',{name:'New profile',exact:true}).click();
    await form.getByLabel('Name',{exact:true}).fill('v2-browser-profile');
    await form.getByRole('button',{name:'Save profile',exact:true}).click();
    await page.getByText('A saved profile has this name. Open it with Edit to make changes.').waitFor();
    await row.getByRole('button',{name:'Edit',exact:true}).click();
    assert.equal(await page.getByRole('textbox',{name:'Native off list',exact:true}).inputValue(),'same-everywhere');
    await row.getByRole('button',{name:'Preview',exact:true}).click();
    await page.getByText('absent-member',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Review enable-only plan',exact:true}).click();
    const response=page.waitForResponse(r=>r.url().endsWith('/api/batch/execute'));
    await page.getByRole('button',{name:'Execute reviewed plan',exact:true}).click();
    assert.equal((await response).status(),200);
    assert(fs.existsSync(path.join(root,'data/jackfield/skills/v2-browser-created/SKILL.md')));
    assert(fs.existsSync(file('.codex','same-everywhere')));
    assert(!fs.existsSync(path.join(home,'.claude/settings.local.json')));
  });
  await test('V2 Workspace evidence and settings persist through navigation',async()=>{
    await go('tools/workspaces');await page.getByLabel('Project path',{exact:true}).fill(root);await page.getByRole('button',{name:'Inspect project',exact:true}).click();
    await page.getByText(/Status: Outside managed roots/).waitFor();
    await go('tools/settings');await page.getByLabel('Theme',{exact:true}).selectOption('dark');
    await page.getByLabel('Text size',{exact:true}).selectOption('large');await page.getByLabel('Regional format',{exact:true}).selectOption('en-IN');
    assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');assert.match(await page.locator('main').innerText(),/12,34,567.89/);
    await go('tools/settings');assert.equal(await page.getByLabel('Regional format',{exact:true}).inputValue(),'en-IN');
    await page.getByLabel('Text size',{exact:true}).selectOption('standard');await page.getByLabel('Theme',{exact:true}).selectOption('light');
    await page.keyboard.press('Control+k');await page.locator('#command-q').fill('templates');await page.locator('#command-list').getByRole('option',{name:/Templates/}).click();await page.getByRole('heading',{name:'Templates',exact:true}).waitFor();
  });
  await test('Peer scope link reads through and the owner copy remains editable',async()=>{
    const name='browser-peer-owner';
    const created=await page.request.post(base+'/api/skills?scope=agents',{data:{name,description:'Peer link browser fixture.',body:'# Original owner text\n'}});
    assert(created.ok(),await created.text());
    const target=path.join(home,'.agents','skills',name),link=path.join(home,'.claude','skills',name);
    fs.symlinkSync(target,link,'dir');
    const listed=await page.request.get(base+'/api/skills?scope=claude-code&body=1');
    assert(listed.ok());const alias=(await listed.json()).find(row=>row.name===name);
    assert(alias);assert.equal(alias.body,'# Original owner text\n');assert.equal(alias.link_followed,true);assert.equal(alias.read_only,true);
    await go('skills');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    await page.getByRole('button',{name:'Refresh files',exact:true}).click();
    await page.getByRole('searchbox',{name:'Filter skills'}).fill(name);
    await page.getByRole('button',{name,exact:true}).click();
    const copyPicker=page.getByLabel('Read copy');
    await copyPicker.selectOption({label:'Claude Code'});
    assert(await page.getByRole('button',{name:/^Edit/}).isDisabled());
    await copyPicker.selectOption({label:'Shared folder'});
    await page.getByRole('button',{name:'Edit',exact:true}).click();
    const targets=page.getByRole('complementary',{name:'Save to'});
    assert.equal(await targets.getByRole('checkbox',{name:/Claude Code/}).count(),0);
    assert.equal(await targets.locator('input:checked').count(),1);
    assert(await targets.getByRole('checkbox',{name:/Shared folder/}).isChecked());
    await page.locator('#ed-body').fill('# Updated by the owner UI\n');
    await page.locator('.savebar button').filter({hasText:'Save'}).click();
    await page.waitForTimeout(500);
    assert.match(fs.readFileSync(path.join(target,'SKILL.md'),'utf8'),/Updated by the owner UI/);
    assert.match(fs.readFileSync(path.join(link,'SKILL.md'),'utf8'),/Updated by the owner UI/);
  });
  await test('Trash & backups restores an exact agent folder and preserves both on conflict', async () => {
    const name='browser-agent-trash';
    const created=await page.request.post(base+'/api/skills?scope=agents',{data:{name,description:'Agent trash browser fixture.',body:'# Trash fixture\n'}});
    assert(created.ok(),await created.text());
    const filePath=path.join(home,'.agents','skills',name,'SKILL.md');
    const original=fs.readFileSync(filePath);
    const companion = path.join(path.dirname(filePath), 'notes.txt');
    const originalNotes = Buffer.from('The first revision has its own notes.\r\n');
    fs.writeFileSync(companion, originalNotes);
    await go('skill/'+name);
    await page.getByRole('button',{name:'Move to Trash',exact:true}).click();
    await page.locator('.dlg-f .btn-danger').click();
    await page.getByRole('button',{name:'Undo',exact:true}).last().waitFor().catch(async error => { throw Error(error.message + ' | toast: ' + await page.locator('.toasts').innerText() + ' | route: ' + page.url()); });
    assert(!fs.existsSync(filePath));
    await page.getByRole('button',{name:'Undo',exact:true}).last().click();
    await page.waitForTimeout(500);
    assert(fs.existsSync(filePath));
    assert.deepEqual(fs.readFileSync(filePath),original);
    assert.deepEqual(fs.readFileSync(companion), originalNotes);

    await go('skill/'+name);
    await page.getByRole('button',{name:'Move to Trash',exact:true}).click();
    await page.locator('.dlg-f .btn-danger').click();
    await page.waitForTimeout(500);
    assert(!fs.existsSync(filePath));
    const replacement=await page.request.post(base+'/api/skills?scope=agents',{data:{name,description:'Second archive fixture.',body:'# Newer text\n'}});
    assert(replacement.ok(),await replacement.text());
    await go('skill/'+name);
    await page.getByRole('button',{name:'Move to Trash',exact:true}).click();
    await page.locator('.dlg-f .btn-danger').click();
    await page.waitForTimeout(500);
    assert(!fs.existsSync(filePath));
    await go('trash');
    const older = restoreButton(name, 'Shared folder', 'copy 2 of 2');
    await older.waitFor();
    assert.equal(await restoreButton(name, 'Shared folder', 'copy 1 of 2').count(), 1);
    await older.focus();
    await page.keyboard.press('Enter');
    const review=page.getByRole('dialog',{name:`Restore ${name}?`});
    assert.match(await review.innerText(), /supporting files[\s\S]*copy 2 of 2/);
    assert.doesNotMatch(await review.innerText(), /skillsmgr-e2e-|\/trash\//);
    const entries=await (await page.request.get(base+'/api/trash?scope=agents')).json();
    const [newer, olderEntry] = entries.filter(row => row.name === name);
    const savedFolder = olderEntry.trash_path;
    assert.deepEqual(fs.readFileSync(path.join(savedFolder, 'notes.txt')), originalNotes);
    assert(!fs.existsSync(filePath));
    await page.keyboard.press('Escape');
    assert(await older.evaluate(b=>b===document.activeElement));
    await older.click();
    fs.mkdirSync(path.dirname(filePath));
    const occupied = Buffer.from('---\nname: browser-agent-trash\ndescription: Occupied browser fixture.\n---\n# Live copy\n');
    fs.writeFileSync(filePath, occupied);
    try {
      await review.getByRole('button',{name:'Restore folder',exact:true}).click();
      assert.match(await review.getByRole('alert').innerText(), /already exists/);
      assert.deepEqual(fs.readFileSync(filePath), occupied);
      assert.deepEqual(fs.readFileSync(path.join(savedFolder, 'SKILL.md')), original);
      assert.deepEqual(fs.readFileSync(path.join(savedFolder, 'notes.txt')), originalNotes);
      assert(fs.existsSync(newer.trash_path));
    } finally {
      fs.unlinkSync(filePath);
      fs.rmdirSync(path.dirname(filePath));
    }
    const restore=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().includes('/api/trash/'+name+'?scope=agents'));
    await review.getByRole('button',{name:'Restore folder',exact:true}).click();
    const response=await restore;
    assert(response.ok());
    assert.equal(response.request().postDataJSON().trash_path,savedFolder);
    await review.waitFor({state:'hidden'});
    assert.deepEqual(fs.readFileSync(filePath),original);
    assert.deepEqual(fs.readFileSync(companion), originalNotes);
    assert(!fs.existsSync(savedFolder));
    assert(fs.existsSync(newer.trash_path));
    await restoreButton(name, 'Shared folder').waitFor();
    const restored = trashList.getByRole('link', {name:'Show restored copy', exact:true});
    await restored.waitFor();
    const route = new URLSearchParams((await restored.getAttribute('href')).split('?')[1]);
    assert.equal(route.get('scope'), 'agents');
    assert.equal(route.get('copy'), path.dirname(filePath));
  });
  await test('Trash & backups labels an unreadable agent scope and retries its listing', async () => {
    const matches = url => url.pathname==='/api/trash' && url.searchParams.get('scope')==='codex';
    const fail = route => route.fulfill({status:503, contentType:'application/json', body:'{"error":"Fixture trash unavailable"}'});
    await page.route(matches, fail);
    try {
      await go('trash');
      assert.match(await trashList.getByRole('alert').innerText(), /Codex.*Fixture trash unavailable/);
    } finally { await page.unroute(matches, fail); }
    await trashList.getByRole('button', {name:'Retry trash', exact:true}).focus();
    await page.keyboard.press('Enter');
    await trashList.getByRole('alert').waitFor({state:'hidden'});
    assert.equal(await page.evaluate(() => document.activeElement.id), 'rec-trash');
  });
  await test('V2 tool read failure stays visible and a retry recovers',async()=>{
    await page.route('**/api/catalog',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Fixture catalog unavailable'})}));
    try{await go('tools/profiles');await page.getByRole('alert').filter({hasText:'Fixture catalog unavailable'}).waitFor();assert(await page.getByRole('button',{name:'Retry profiles',exact:true}).isVisible());}
    finally{await page.unroute('**/api/catalog');}
    await page.getByRole('button',{name:'Retry profiles',exact:true}).click();await page.getByText('v2-browser-profile',{exact:true}).waitFor();
  });
  await test('V2 Quality labels APM evidence for the selected project',async()=>{
    const project=path.join(root,'data','jackfield','apm-fixture');
    fs.mkdirSync(project);
    fs.writeFileSync(path.join(project,'apm.yml'),'name: browser-fixture\nversion: 1.0.0\n');
    await go('tools/quality');
    await page.getByLabel('Project path',{exact:true}).fill(project);
    await page.getByRole('button',{name:'Inspect project',exact:true}).click();
    const evidence=page.locator('.evidence-limits');
    const manifest=evidence.getByText(/apm\.yml is present/);
    await manifest.waitFor({state:'attached'});
    await evidence.locator('summary').click();
    await manifest.waitFor();
    assert.equal(await evidence.getByText(/apm\.lock\.yaml is present/).count(),0);
    const apmAudit=evidence.getByRole('link',{name:'Audit the project with Microsoft APM'});
    assert.equal(await apmAudit.getAttribute('href'),'https://microsoft.github.io/apm/reference/cli/audit/');
    await page.getByRole('button',{name:'Clear project',exact:true}).click();
    await evidence.locator('summary').waitFor();
    assert.equal(await manifest.count(),0);
    assert.equal(await apmAudit.count(),0);
  });
  await test('Quality finding evidence uses a separate disclosure', async () => {
    await go('tools/quality');
    const finding = page.locator('.tp-findings > li > details').first();
    await finding.locator(':scope > summary').click();
    const evidence = finding.getByText('Finding evidence', {exact:true});
    assert(await evidence.evaluate(element =>
      getComputedStyle(element).display !== 'grid' && getComputedStyle(element, '::before').content !== 'none'));
    await evidence.press('Enter');
    await finding.getByRole('region', {name:/^Evidence for /}).waitFor();
  });
  await test('Paper follow-up explains incomplete Quality scans and estimates plainly', async () => {
    const doctor = url => url.pathname === '/api/doctor' && url.searchParams.get('hygiene') === '1';
    const stats = url => url.pathname === '/api/stats';
    const partial = async route => {
      const response = await route.fetch(), json = await response.json();
      json.hygiene.document_fingerprints.status = 'observed';
      json.hygiene.document_fingerprints.omitted = 0;
      json.degraded = [{section:'settings'}];
      await route.fulfill({response, json});
    };
    const estimated = async route => {
      const response = await route.fetch(), json = await response.json();
      json.has_tiktoken = false;
      await route.fulfill({response, json});
    };
    await page.route(doctor, partial);
    await page.route(stats, estimated);
    try {
      await go('advanced/quality');
      await page.getByText('Jackfield could not finish all checks. The saved baseline cannot be updated.').waitFor();
      assert(await page.getByRole('button', {name:'Save browser baseline'}).isDisabled());
      await page.getByRole('button', {name:'Statistics', exact:true}).click();
      await page.getByText('Estimated from text length. The available space can vary.').waitFor();
    } finally {
      await page.unroute(doctor, partial);
      await page.unroute(stats, estimated);
    }
  });
  await test('Skill copies restores exact selection, tags and profiles', async () => {
    const name = 'constructor';
    const created = await page.request.post(base+'/api/skills?scope=agents', {data:{name,description:'Exact copies browser fixture.',body:'# Owner\n'}});
    assert(created.ok(), await created.text());
    const owner = path.join(home,'.agents','skills',name), link = path.join(home,'.claude','skills',name);
    fs.symlinkSync(owner,link,'dir');
    const originalProfile = {name:'browser-existing', description:'Keep this description', skills:['sole-copy'], targets:['claude-code'], native:{off:['sole-copy']}, expected_profile:null};
    const seeded = await page.request.post(base+'/api/catalog/profiles',{data:originalProfile});
    assert(seeded.ok(),await seeded.text());
    try {
      await go('advanced');
      await page.getByRole('link',{name:/^Skill copies/}).click();
      await page.getByRole('heading',{name:'Skill copies',exact:true}).waitFor();
      await page.getByLabel('Find a skill').fill(name);
      const rows = page.locator('.instance-row').filter({hasText:name});
      assert.equal(await rows.count(),2);
      await page.getByLabel('Tag',{exact:true}).selectOption('__untagged');
      assert.equal(await rows.count(),2);
      await page.getByLabel('Tag',{exact:true}).selectOption('');
      const linked = rows.filter({hasText:'linked copy is read-only'}), writable = rows.filter({hasNotText:'linked copy is read-only'});
      assert(await linked.getByRole('checkbox').isDisabled());
      assert(await linked.getByRole('button',{name:'Review update'}).isDisabled());
      assert(await writable.getByRole('checkbox').isEnabled());
      await writable.getByRole('checkbox').check();
      await page.getByRole('button',{name:'Edit tags'}).click();
      await page.getByLabel('Tags, separated by commas').fill('browser-tag, __untagged');
      await page.getByRole('button',{name:'Update tags'}).click();
      await page.locator('.instance-tags').getByText('browser-tag',{exact:true}).first().waitFor();
      await page.getByLabel('Tag',{exact:true}).selectOption('tag:browser-tag');
      assert.equal(await rows.count(),2);
      await page.getByLabel('Tag',{exact:true}).selectOption('tag:__untagged');
      assert.equal(await rows.count(),2);
      await page.getByLabel('Tag',{exact:true}).selectOption('__untagged');
      assert.equal(await rows.count(),0);
      await page.getByLabel('Tag',{exact:true}).selectOption('');
      await page.getByRole('button',{name:'Save as profile'}).click();
      let profilePosts = 0;
      const countProfilePost = request => { if (request.url().endsWith('/api/catalog/profiles') && request.method() === 'POST') profilePosts++; };
      page.on('request', countProfilePost);
      await page.getByLabel('Profile name').fill('browser-existing');
      await page.getByRole('button',{name:'Save profile',exact:true}).click();
      await page.getByRole('dialog').getByRole('alert').getByText('A profile named browser-existing already exists. Choose it from the list to add to it.').waitFor();
      assert.equal(profilePosts, 0);
      page.off('request', countProfilePost);
      await page.getByLabel('Profile name').fill('browser-profile');
      const saved = page.waitForResponse(r => r.url().endsWith('/api/catalog/profiles') && r.request().method() === 'POST');
      await page.getByRole('button',{name:'Save profile',exact:true}).click();
      assert.equal((await saved).status(),200);
      const catalog = await (await page.request.get(base+'/api/catalog')).json();
      assert(catalog.profiles['browser-profile'].skills.includes(name));
      await page.getByRole('button',{name:'Save as profile'}).click();
      assert.equal(await page.getByLabel('Choose a profile').locator('option[value="browser-profile"]').count(),1);
      await page.getByLabel('Choose a profile').selectOption('browser-existing');
      const merged = page.waitForResponse(r => r.url().endsWith('/api/catalog/profiles') && r.request().method() === 'POST');
      await page.getByRole('button',{name:'Save profile',exact:true}).click();
      assert.equal((await merged).status(),200);
      const afterMerge = (await (await page.request.get(base+'/api/catalog')).json()).profiles['browser-existing'];
      assert.equal(afterMerge.description,'Keep this description');
      assert.deepEqual(afterMerge.native,{off:['sole-copy']});
      assert.deepEqual(afterMerge.skills.sort(),[name,'sole-copy'].sort());
      assert.deepEqual(afterMerge.targets.sort(),['agents','claude-code'].sort());
      await page.getByRole('button',{name:'Save as profile'}).click();
      await page.getByLabel('Choose a profile').selectOption('browser-existing');
      const changed = await page.request.post(base+'/api/catalog/profiles',{data:{...afterMerge,name:'browser-existing',description:'Changed elsewhere',expected_profile:afterMerge}});
      assert(changed.ok(),await changed.text());
      const stale = page.waitForResponse(r => r.url().endsWith('/api/catalog/profiles') && r.request().method() === 'POST');
      await page.getByRole('button',{name:'Save profile',exact:true}).click();
      assert.equal((await stale).status(),400);
      await page.getByRole('dialog').getByRole('alert').waitFor();
      assert.equal((await (await page.request.get(base+'/api/catalog')).json()).profiles['browser-existing'].description,'Changed elsewhere');
      await page.getByRole('dialog').getByRole('button',{name:'Cancel'}).click();
      await page.getByRole('button',{name:'Move to trash',exact:true}).click();
      const dialog = page.getByRole('dialog',{name:'Review moving to trash'});
      await dialog.getByText(/cop(?:y|ies) reviewed/).waitFor();
      await dialog.getByRole('button',{name:'Move to trash'}).click();
      const undo = page.locator('.toast').getByRole('button',{name:'Undo'}).last();
      await undo.waitFor();
      assert(!fs.existsSync(owner));
      const restored = page.waitForResponse(r => new URL(r.url()).pathname === '/api/trash/' + name && r.request().method() === 'POST');
      await undo.click();
      assert.equal((await restored).status(),200);
      assert(fs.existsSync(path.join(owner,'SKILL.md')));
    } finally { fs.unlinkSync(link); fs.rmSync(owner,{recursive:true,force:true}); }
  });
  await test('Skill copies ignores a stale catalog read after saving', async () => {
    const oldCatalog = await (await page.request.get(base+'/api/catalog')).json();
    let release, started;
    const pending = new Promise(resolve => { release = resolve; });
    const requested = new Promise(resolve => { started = resolve; });
    const match = url => url.pathname === '/api/catalog';
    const delay = async route => { started(); await pending; await route.fulfill({json:oldCatalog}); };
    await page.route(match,delay);
    try {
      await page.goto(base+'/?fixture-step='+(++navigation)+'#/advanced/instances',{waitUntil:'domcontentloaded'});
      await requested;
      const copy = page.locator('.instance-row').filter({hasText:'sole-copy'}).first();
      await copy.getByRole('checkbox').check();
      await page.getByRole('button',{name:'Save as profile'}).click();
      await page.getByLabel('Profile name').fill('stale-read-profile');
      const saved = page.waitForResponse(r => r.url().endsWith('/api/catalog/profiles') && r.request().method() === 'POST');
      await page.getByRole('button',{name:'Save profile',exact:true}).click();
      assert.equal((await saved).status(),200);
      const oldRead = page.waitForResponse(r => new URL(r.url()).pathname === '/api/catalog' && r.request().method() === 'GET');
      release();
      await oldRead;
      await page.getByRole('button',{name:'Save as profile'}).click();
      assert.equal(await page.getByLabel('Choose a profile').locator('option[value="stale-read-profile"]').count(),1);
      await page.getByRole('dialog').getByRole('button',{name:'Cancel'}).click();
    } finally { release(); await page.unroute(match,delay); }
  });
  await test('Skill copies inventory failure offers retry', async () => {
    const match = url => url.pathname === '/api/skills' && url.searchParams.get('scope') === 'all';
    const fail = route => route.fulfill({status:503,contentType:'application/json',body:'{"error":"Inventory unavailable"}'});
    await page.route(match,fail);
    try {
      await go('advanced/instances');
      const error = page.getByRole('alert').filter({hasText:'Could not read skill copies'});
      await error.waitFor();
      assert.equal(await page.locator('.v2-instances').count(),0);
      await page.unroute(match,fail);
      await error.getByRole('button',{name:'Try again'}).click();
      await page.locator('.instance-row').first().waitFor();
    } finally { await page.unroute(match,fail); }
  });
  await test('Advanced lists tools and retains its search after opening one',async()=>{
    await page.setViewportSize({width:390,height:844});
    await go('advanced');
    const screen=page.locator('.jf-advanced');
    await screen.getByRole('heading',{name:'Advanced',exact:true}).waitFor();
    for(const name of ['Add skills','Check my setup','AI assist','Settings','Write','Test','Shorten','Find conflicts'])
      assert(await screen.getByRole('heading',{name,exact:true}).isVisible(),name);
    const links=screen.getByRole('link');
    for(const id of ['install','profiles','templates','quality','workspaces','source-update','doctor','ai-settings','ai-ask','ai-draft','ai-concise','ai-profile','ai-trigger','ai-improve','ai-budget','ai-evals','ai-ablate','ai-conflicts','ai-overlap','ai-explain','ai-port'])
      assert.equal(await screen.locator(`a[href="#/advanced/${id}"]`).count(),1,id);
    assert.equal(await screen.locator('a[href="#/settings"]').count(),1);
    assert.equal(await screen.locator('a[href="#/settings/tracking"]').count(),1);
    const search=page.getByRole('searchbox',{name:'Find a tool',exact:true});
    await search.fill('  INDEX   maintenance  ');
    assert.equal(await links.count(),1);
    assert.match(await links.innerText(),/Settings/);
    await search.press('Tab');
    assert(await links.evaluate(link=>link===document.activeElement));
    await page.keyboard.press('Enter');
    await page.getByRole('heading',{name:'Settings',exact:true}).waitFor();
    await page.goBack();
    await screen.getByRole('heading',{name:'Advanced',exact:true}).waitFor();
    assert.match(await search.inputValue(),/INDEX/);
    await screen.getByRole('status').filter({hasText:'1 matching tool'}).waitFor();
    await search.fill('<unmatched>');
    assert.equal(await links.count(),0);
    await page.getByRole('status').filter({hasText:'0 matching tools'}).waitFor();
    await search.fill('');
    assert(await links.count()>10);
  });
  await test('Advanced uses the destination names and explains tests in plain language', async () => {
    await go('advanced');
    const screen = page.locator('.jf-advanced');
    const places = screen.getByRole('link', {name:/^Where agents look/});
    await places.click();
    await page.getByRole('heading', {name:'Where agents look', exact:true}).waitFor();
    await go('advanced');
    await screen.getByText(/compare how often your model picks each skill/).waitFor();
    await screen.getByText(/run the same requests with and without a skill/i).waitFor();
    assert.doesNotMatch(await screen.innerText(), /selection rates|assertions/);
    await screen.getByRole('link', {name:/^Connection/}).click();
    await page.getByRole('heading', {name:'Connection', exact:true}).waitFor();
  });
  await test('Advanced group switches guard direct routes and Doctor reads real evidence',async()=>{
    const endpoint=base+'/api/tracking';
    const read=async()=>(await page.request.get(endpoint)).json();
    const write=async(settings)=>{
      const response=await page.request.put(endpoint,{headers:{Origin:base},data:settings});
      assert.equal(response.status(),200,await response.text());
    };
    const previous=(await read()).settings;
    const requests=[];
    const observe=request=>{const url=new URL(request.url());if(['/api/doctor','/api/catalog','/api/templates','/api/workspaces'].some(p=>url.pathname===p||url.pathname.startsWith(p+'/'))||url.pathname.startsWith('/api/source-updates'))requests.push(url.pathname+url.search);};
    page.on('request',observe);
    try {
      const disabled={...previous,tool_groups:{...previous.tool_groups,'add-skills':false,'check-setup':false,'ai-assist':false}};
      await write(disabled);
      await go('advanced');
      const screen=page.locator('.jf-advanced');
      assert.equal(await screen.locator('a[href="#/settings"]').count(),1);
      assert.equal(await screen.locator('a[href="#/advanced/source-update"],a[href="#/advanced/doctor"],a[href="#/advanced/ai-draft"]').count(),0);
      for (const [tool, group] of [['source-update','Add skills'],['doctor','Check my setup'],
        ['profiles','Add skills'],['instances','Add skills'],['quality','Check my setup']]) {
        requests.length=0;
        await go('advanced/'+tool);
        await page.getByRole('heading',{name:group+' is switched off',exact:true}).waitFor();
        // The shell loads the catalog at startup. Profiles must not load it a second time.
        assert(requests.length<=1 && requests.every(url=>url==='/api/catalog'),`${tool}: ${requests.join(', ')}`);
      }
      await write({...disabled,revision:(await read()).revision,tool_groups:{...disabled.tool_groups,'check-setup':true}});
      await go('advanced/doctor');
      await page.getByRole('heading',{name:'Doctor',exact:true}).waitFor();
      const response=page.waitForResponse(r=>r.url()===base+'/api/doctor?scope=all&hygiene=1' && r.request().method()==='GET');
      await page.getByRole('button',{name:'Run Doctor',exact:true}).click();
      assert.equal((await response).status(),200);
      await page.getByRole('heading',{name:'Doctor results',exact:true}).waitFor();
      const report = page.getByRole('region',{name:'Doctor results'});
      assert.match(await report.innerText(), /index result covers the library index only/i);
      assert.match(await report.innerText(), /Skills table counts affected skill names/);
      assert.match(await report.innerText(), /Information not available/);
      assert.equal(await report.getByRole('link',{name:'Review Needs attention'}).getAttribute('href'),'#/attention');
      await go('advanced/source-update');
      await page.getByRole('heading',{name:'Add skills is switched off',exact:true}).waitFor();
    } finally {
      page.off('request',observe);
      await write({...previous,revision:(await read()).revision});
    }
  });
  await test('Quality jumps focus headings without changing the route', async () => {
    await page.setViewportSize({width:320,height:780});
    await go('tools/quality');
    const url = page.url();
    const jumps = page.getByRole('group', {name:'On this page'});
    for (const [label, id] of [['Findings', 'tp-findings'], ['Diagnostics', 'tp-diagnostics']]) {
      await jumps.getByRole('button', {name:label, exact:true}).press('Enter');
      assert.equal(page.url(), url);
      assert(await page.locator('#' + id).evaluate(heading => {
        const top = heading.getBoundingClientRect().top;
        return heading === document.activeElement && top >= document.querySelector('.top').getBoundingClientRect().bottom && top < innerHeight / 2;
      }), id);
    }
  });
  await test('Advanced copies and profiles fit phones and have touch targets', async () => {
    try {
      for (const mode of ['light','dark']) {
        await go('advanced/settings');
        await page.getByLabel('Theme',{exact:true}).selectOption(mode);
        for (const width of [320,375,390]) {
          await page.setViewportSize({width,height:900});
          for (const route of ['advanced/instances','advanced/profiles']) {
            await go(route);
            const tool = page.locator('.v2-tools.page');
            await tool.locator('h1').waitFor();
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${route} ${width} ${mode}`);
            if (width !== 390) continue;
            if (route.endsWith('instances')) {
              await tool.locator('.instance-row input:not(:disabled)').first().check();
              await tool.getByRole('button',{name:'Sync',exact:true}).click();
            }
            const controls = tool.locator('button, select, input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=file]), textarea, label:has(input[type=checkbox]), label:has(input[type=radio])');
            let checked = 0;
            for (const control of await controls.all()) {
              if (!(await control.isVisible())) continue;
              const box = await control.boundingBox();
              assert(box.height >= 44, `small target on ${route}: ${await control.evaluate(e => e.outerHTML.slice(0,160))}`);
              checked++;
            }
            assert(checked > 5, `missing controls on ${route}`);
            if (route.endsWith('instances')) await tool.getByRole('dialog').getByRole('button',{name:'Cancel'}).click();
          }
        }
      }
    } finally { await page.setViewportSize({width:1280,height:900}); }
  });
  await test('All v2 tool routes fit desktop and small phone in both themes',async()=>{
    // Reuse one browser context per theme across the widths. Each route still
    // loads and settles at each width before its layout checks.
    const outcomes = await Promise.allSettled(['light','dark'].map(async mode => {
      const themeContext = await browser.newContext({viewport:{width:320,height:900}, colorScheme:mode});
      try {
        const view = await themeContext.newPage();
        view.setDefaultTimeout(5000);
        view.on('pageerror', error => exceptions.push(error.message));
        await go('tools/settings', view);
        await view.getByLabel('Theme',{exact:true}).selectOption(mode);
        for (const width of [320,768,1280]) {
          await view.setViewportSize({width,height:900});
          for (const route of ['tools','tools/install','tools/profiles','tools/instances','tools/templates','tools/quality',
            'tools/workspaces','tools/doctor','tools/settings','tools/source-update','tools/ai-settings','skills','trash',
            'settings/tracking','settings/tracking/add-agent']) {
            await go(route, view);
            assert.equal(await view.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${route} ${width} ${mode}`);
            if (!route.startsWith('tools/')) continue;
            const nav = view.getByRole('navigation',{name:'Tools navigation'});
            if (width <= 860) {
              assert(await nav.getByRole('link',{name:'All tools',exact:true}).isVisible());
              assert.equal(await nav.getByRole('link').count(),1);
            } else {
              const active = nav.locator('[aria-current="page"]');
              assert(await active.evaluate(link => {
                const tab = link.getBoundingClientRect(), nav = link.closest('nav').getBoundingClientRect();
                return tab.top >= nav.top - 1 && tab.bottom <= nav.bottom + 1 && nav.bottom <= innerHeight;
              }), `active tool is clipped on ${route} at ${width}px`);
            }
          }
        }
      } finally { await themeContext.close(); }
    }));
    for (const outcome of outcomes) if (outcome.status === 'rejected') throw outcome.reason;
    await page.setViewportSize({width:1280,height:900});
    await go('tools');
    await theme('dark');
    await page.screenshot({path:path.join(root,'final-tools-desktop.png')});
  });
  await test('Stop tracking an agent leaves its files alone and Undo brings its column back', async () => {
    const f=file('.codex','same-everywhere'), bytes=fs.readFileSync(f);
    const heads=async()=>(await page.locator('.jf-grid thead th').allInnerTexts()).map(t=>t.replace(/\s+/g,' ').trim());
    await go('skills');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    assert((await heads()).some(t=>t.includes('Codex')));
    await page.getByRole('button',{name:'Codex options',exact:true}).click();
    await page.getByRole('button',{name:'Stop tracking Codex…'}).click();
    const form=page.locator('.jf-panel');
    assert.match(await form.innerText(),/The Codex column and its counts leave the table[\s\S]*Nothing on disk changes/);
    assert(await form.evaluate(el => el.contains(document.activeElement)));
    await form.getByRole('button',{name:'Stop tracking Codex',exact:true}).click();
    const toast=page.locator('.toast',{hasText:'Stopped tracking Codex. Nothing on disk changed.'});
    await toast.waitFor();
    assert(!(await heads()).some(t=>t.includes('Codex')));
    assert(!(await (await context.request.get(base+'/api/scopes')).json()).some(s=>s.id==='codex'));
    assert.deepEqual(fs.readFileSync(f),bytes);
    await toast.getByRole('button',{name:'Undo'}).click();
    await page.locator('.toast',{hasText:'Tracking Codex again.'}).waitFor();
    assert((await heads()).some(t=>t.includes('Codex')));
    assert((await (await context.request.get(base+'/api/scopes')).json()).some(s=>s.id==='codex'));
  });
  await test('Add other agent checks the folder live, adds a column, and Remove keeps its folder', async () => {
    const kilo=path.join(home,'.kilo','skills','kilo-only','SKILL.md'), bytes=fs.readFileSync(kilo);
    await go('settings/tracking');
    await page.getByRole('link',{name:'Add other agent'}).click();
    const folder=page.locator('#trk-folder'); await folder.waitFor();
    await folder.fill('/etc');
    await page.locator('#trk-folder-hint',{hasText:'Pick a folder inside your home folder.'}).waitFor();
    await folder.fill('~/.kilo/skills');
    await page.locator('#trk-folder-hint',{hasText:'1 skill found in ~/.kilo/skills'}).waitFor();
    assert.equal(await page.locator('#trk-name').inputValue(),'Kilo');
    await page.getByRole('button',{name:'Add Kilo',exact:true}).click();
    await page.locator('.toast',{hasText:'Added Kilo.'}).waitFor();
    assert.equal(new URL(page.url()).hash,'#/settings/tracking');
    assert.match(await page.locator('#trk-st-custom-kilo').innerText(),/Tracked · 1 skill/);
    await go('skills');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    assert((await page.locator('.jf-grid thead th').allInnerTexts()).some(t=>t.includes('Kilo')));
    await go('settings/tracking');
    await page.locator('.trk-row',{hasText:'Kilo'}).getByRole('button',{name:'Details'}).click();
    await page.locator('.trk-row',{hasText:'Kilo'}).getByRole('button',{name:'Remove'}).click();
    assert.match(await page.locator('.dlg').innerText(),/Remove Kilo\?[\s\S]*Nothing on disk changes/);
    await page.locator('.dlg-f').getByRole('button',{name:'Remove Kilo',exact:true}).click();
    await page.locator('.toast',{hasText:'Removed Kilo. Its folder is unchanged.'}).waitFor();
    assert.equal(await page.locator('#trk-st-custom-kilo').count(),0);
    assert.deepEqual(fs.readFileSync(kilo),bytes);
  });
  await test('Review fixes: observed settings and attention count stay accurate across routes', async () => {
    await go('skills');
    const welcome = page.getByRole('button', {name:'Show my skills'});
    if (await welcome.isVisible()) await welcome.click();
    for (const agent of ['Claude Code', 'OpenCode']) {
      await page.getByRole('button', {name:`same-everywhere in ${agent}: Off in settings`, exact:true}).waitFor();
    }
    const attention = page.locator('.tabs a[href="#/attention"]');
    const label = await attention.getAttribute('aria-label');
    assert.match(label, /Needs attention, \d+ items/);
    await attention.click();
    await page.waitForURL(url => url.hash === '#/attention');
    assert.equal(await attention.getAttribute('aria-label'), label);
    await expectAttentionCount(Number(label.match(/\d+/)[0]));
  });
  await test('Review fixes: tablet sheet, split comparison and tracking confirmation', async () => {
    await page.setViewportSize({width:768, height:900});
    try {
      await go('skills');
      const welcome = page.getByRole('button', {name:'Show my skills'});
      if (await welcome.isVisible()) await welcome.click();
      const square = page.getByRole('button', {name:/^split-even in Codex: Version [12]$/});
      await square.click();
      const panel = page.getByRole('dialog', {name:'split-even'});
      const confirm = panel.getByRole('button', {name:'Make all 4 match'});
      assert(await confirm.isDisabled());
      const keepVersion = panel.getByRole('button', {name:'Keep version 1'});
      await keepVersion.focus();
      assert.equal(await page.locator('.jf-square.is-camp').count(), 2);
      assert.equal(await panel.evaluate(el => getComputedStyle(el).position), 'fixed');
      await panel.getByRole('button', {name:'Compare the two versions'}).click();
      await panel.getByRole('region', {name:'Version 1 instructions'}).waitFor();
      await panel.getByRole('region', {name:'Version 2 instructions'}).waitFor();
      assert(await confirm.isDisabled());
      await page.keyboard.press('Escape');
      await panel.waitFor({state:'hidden'});
      assert(await square.evaluate(el => el === document.activeElement));
      await page.getByRole('button', {name:'Codex options', exact:true}).click();
      await page.getByRole('button', {name:'Stop tracking Codex…'}).click();
      const stop = page.getByRole('dialog', {name:'Stop tracking Codex?'});
      await stop.getByText(/Nothing on disk changes/).waitFor();
      await stop.getByRole('button', {name:'Keep tracking', exact:true}).click();
      await stop.waitFor({state:'hidden'});
      assert(await page.getByRole('button', {name:'Codex options', exact:true}).evaluate(el => el === document.activeElement));
    } finally { await page.setViewportSize({width:1280,height:900}); }
  });
  await test('Review fixes: tracking Undo keeps another window’s changes after refresh', async () => {
    const endpoint = base + '/api/tracking';
    const read = async () => (await page.request.get(endpoint)).json();
    const write = async (settings) => {
      const response = await page.request.put(endpoint, {headers:{Origin:base}, data:settings});
      assert.equal(response.status(), 200, await response.text());
      return response.json();
    };
    const previous = (await read()).settings;
    try {
      await go('skills');
      const welcome = page.getByRole('button', {name:'Show my skills'});
      if (await welcome.isVisible()) await welcome.click();
      await page.getByRole('button', {name:'Codex options', exact:true}).click();
      await page.getByRole('button', {name:'Stop tracking Codex…'}).click();
      await page.getByRole('button', {name:'Stop tracking Codex', exact:true}).click();
      const undo = page.locator('.toast', {hasText:'Stopped tracking Codex.'}).getByRole('button', {name:'Undo', exact:true});
      await undo.waitFor();
      const later = (await read()).settings;
      later.agents.tracked = later.agents.tracked.filter(id => id !== 'opencode');
      const advanced = await write(later);
      await page.getByRole('button', {name:'Refresh files', exact:true}).click();
      await page.getByRole('button', {name:'OpenCode options', exact:true}).waitFor({state:'hidden'});
      await page.waitForLoadState('networkidle');
      await undo.click();
      await page.locator('.toast', {hasText:/Couldn.t undo:.*changed in another window/i}).waitFor();
      const after = await read();
      assert.equal(after.revision, advanced.revision);
      assert.deepEqual(after.settings, advanced.settings);
    } finally {
      await write({...previous, revision:(await read()).revision});
    }
  });
  for (const method of ['keyboard', 'mouse']) {
    await test(`Phase 2 F2 Codex-only toggle and Undo by ${method}`, async () => {
      const name = 'code-review', scopes = ['.claude', '.codex'];
      const bytes = Buffer.from('---\nname: code-review\ndescription: Browser benchmark fixture.\n---\n# Code review\n');
      for (const scope of scopes) {
        const target = file(scope, name);
        assert(!fs.existsSync(target) && !fs.existsSync(target + '.disabled'));
        fs.mkdirSync(path.dirname(target), {recursive:true}); fs.writeFileSync(target, bytes);
      }
      const codex = file('.codex', name), claude = file('.claude', name);
      try {
        for (const [width, themeName] of [[1440,'light'], [1440,'dark'], [390,'light'], [390,'dark']]) {
          await page.setViewportSize({width, height:900});
          await go('skills'); await theme(themeName);
          const showSkills = page.getByRole('button', {name:'Show my skills'});
          if (await showSkills.isVisible()) await showSkills.click();
          const filter = page.getByRole('searchbox', {name:'Filter skills'});
          const filterToggle = page.getByRole('button', {name:'Filter and sort'});
          if (!(await filter.isVisible()) && await filterToggle.isVisible()) await filterToggle.click();
          await filter.fill(name);
          const agentPicker = page.getByRole('combobox', {name:'Showing place'});
          if (await agentPicker.isVisible()) await agentPicker.selectOption({label:'Codex'});
          const square = page.getByRole('button', {name:/code-review in Codex: On/i});
          await square.waitFor();
          if (method === 'keyboard') {
            await filter.focus();
            for (let i=0; i<20 && !(await page.evaluate(() => document.activeElement?.textContent?.trim() === 'code-review')); i++) await page.keyboard.press('Tab');
            assert.equal(await page.evaluate(() => document.activeElement?.textContent?.trim()), name);
            for (let i=0; i<10 && !(await square.evaluate(el => el === document.activeElement)); i++) await page.keyboard.press('ArrowRight');
            assert(await square.evaluate(el => el === document.activeElement));
            await page.keyboard.press('Enter');
            const primary = page.getByRole('button', {name:/Turn off in Codex/}); await primary.waitFor();
            await primary.focus(); await page.keyboard.press('Enter');
          } else {
            await square.click();
            const primary = page.getByRole('button', {name:/Turn off in Codex/});
            if (width === 1440 && themeName === 'light') {
              await primary.evaluate(button => button.addEventListener('click', () => {
                const start = performance.now();
                const observer = new MutationObserver(() => {
                  if (!document.querySelector('button[aria-label="code-review in Codex: Off"]')) return;
                  observer.disconnect();
                  window.fixtureToggleMs = performance.now() - start;
                });
                observer.observe(document.querySelector('main'), {subtree:true, childList:true, attributes:true});
              }, {once:true, capture:true}));
            }
            await primary.click();
          }
          await page.getByRole('button', {name:/code-review in Codex: Off/i}).waitFor();
          if (method === 'mouse' && width === 1440 && themeName === 'light') {
            const elapsed = await page.evaluate(() => window.fixtureToggleMs);
            assert(elapsed <= 300, `confirmed file toggle took ${elapsed} ms (limit 300 ms)`);
          }
          assert(!fs.existsSync(codex)); assert.deepEqual(fs.readFileSync(codex+'.disabled'), bytes);
          assert.deepEqual(fs.readFileSync(claude), bytes); assert(!fs.existsSync(claude+'.disabled'));
          const undo = page.getByRole('button', {name:'Undo', exact:true}).last(); await undo.waitFor();
          if (method === 'keyboard') { await undo.focus(); await page.keyboard.press('Enter'); } else await undo.click();
          await page.getByRole('button', {name:/code-review in Codex: On/i}).waitFor();
          assert.deepEqual(fs.readFileSync(codex), bytes); assert(!fs.existsSync(codex+'.disabled'));
          assert.deepEqual(fs.readFileSync(claude), bytes);
        }
      } finally {
        for (const scope of scopes) fs.rmSync(path.dirname(file(scope, name)), {recursive:true, force:true});
        await page.setViewportSize({width:1280,height:900});
      }
    });
  }
  await test('Skills shows a pending change on its own square while keeping other statuses', async () => {
    const active = file('.codex'), disabled = active + '.disabled';
    const endpoint = '**/api/batch/execute';
    let release;
    const pending = new Promise(resolve => { release = resolve; });
    const delayToggle = async route => {
      if (route.request().postDataJSON().operation === 'disable') await pending;
      await route.continue();
    };
    await page.route(endpoint, delayToggle);
    try {
      await go('skills?q=same-everywhere');
      await page.getByRole('button', {name:'same-everywhere in Codex: On', exact:true}).click();
      await page.locator('.jf-panel').getByRole('button', {name:/^Turn off/}).click();
      await page.getByRole('button', {name:'same-everywhere in Codex: Working…', exact:true}).waitFor();
      assert(await page.getByRole('button', {name:'same-everywhere in Claude Code: Off in settings', exact:true}).isVisible());
      release();
      await page.getByRole('button', {name:'same-everywhere in Codex: Off', exact:true}).waitFor();
      await page.locator('.toast').getByRole('button', {name:'Undo', exact:true}).click();
      await page.getByRole('button', {name:'same-everywhere in Codex: On', exact:true}).waitFor();
    } finally {
      release();
      await page.unroute(endpoint, delayToggle);
      if (fs.existsSync(disabled) && !fs.existsSync(active)) fs.renameSync(disabled, active);
    }
  });
  await test('Phase 2 Shift+Space selects a row without writing', async () => {
    await go('skills');
    const showSkills = page.getByRole('button', {name:'Show my skills'});
    if (await showSkills.isVisible()) await showSkills.click();
    const source = file('.claude', 'sole-copy'), bytes = fs.readFileSync(source);
    let writes = 0;
    const observe = req => { if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(req.method())) writes++; };
    page.on('request', observe);
    try {
      const filter = page.getByRole('searchbox', {name:'Filter skills'}); await filter.fill('sole-copy');
      await filter.focus();
      for (let i=0; i<20 && !(await page.evaluate(() => document.activeElement?.textContent?.trim() === 'sole-copy')); i++) await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(() => document.activeElement?.textContent?.trim()), 'sole-copy');
      await page.keyboard.press('Shift+Space');
      assert(await page.getByRole('checkbox', {name:'Select sole-copy'}).isChecked());
      assert.equal(writes, 0); assert.deepEqual(fs.readFileSync(source), bytes);
      await page.keyboard.press('Shift+Space');
      assert(!(await page.getByRole('checkbox', {name:'Select sole-copy'}).isChecked()));
      assert.equal(writes, 0);
    } finally { page.off('request', observe); }
  });
  await test('A backup preview that finishes after navigation belongs to the old Trash visit', async () => {
    let release;
    const pending = new Promise(resolve => { release = resolve; });
    const previewRequest = url => url.pathname === '/api/import' && url.searchParams.get('preview') === '1';
    const delayedPreview = async route => {
      await pending;
      await route.fulfill({json:{plan_id:'fixture-preview', entries:[{name:'synthetic', action:'add'}]}});
    };
    await page.route(previewRequest, delayedPreview);
    try {
      await go('trash');
      await trashScreen.locator('#imp-file').setInputFiles({name:'synthetic.zip', mimeType:'application/zip', buffer:Buffer.from('fixture')});
      const requested = page.waitForRequest(request => previewRequest(new URL(request.url())));
      await trashScreen.getByRole('button', {name:'Preview backup', exact:true}).click();
      await requested;
      await page.locator('.tabs a[href="#/skills"]').click();
      await page.locator('.jf-skills-screen').waitFor();
      await page.locator('.tabs a[href="#/trash"]').click();
      await trashScreen.waitFor();
      release();
      await page.waitForFunction(() => !document.getElementById('imp-file').disabled);
      assert.equal(await trashScreen.getByRole('region', {name:'Backup preview', exact:true}).count(), 0);
      assert.equal(await trashScreen.getByRole('button', {name:'Load backup', exact:true}).count(), 0);
      assert.equal(await trashScreen.getByText('synthetic.zip', {exact:true}).count(), 0);
    } finally {
      release();
      await page.unroute(previewRequest, delayedPreview);
    }
  });
  await test('Phase 2 add a missing copy and Undo restores the filesystem', async () => {
    const name = 'phase-two-add', source = file('.claude', name), target = file('.codex', name);
    const bytes = Buffer.from('---\nname: phase-two-add\ndescription: Browser copy fixture.\n---\n# Copy fixture\n');
    assert(!fs.existsSync(source) && !fs.existsSync(target));
    fs.mkdirSync(path.dirname(source), {recursive:true}); fs.writeFileSync(source, bytes);
    try {
      await go('skills');
      const showSkills = page.getByRole('button', {name:'Show my skills'});
      if (await showSkills.isVisible()) await showSkills.click();
      await page.getByRole('searchbox', {name:'Filter skills'}).fill(name);
      await page.getByRole('button', {name:/phase-two-add in Codex: Not here/i}).click();
      await page.getByRole('button', {name:/Add to Codex/}).click();
      await page.getByRole('button', {name:/phase-two-add in Codex: On/i}).waitFor();
      assert.deepEqual(fs.readFileSync(target), bytes); assert.deepEqual(fs.readFileSync(source), bytes);
      await page.getByRole('button', {name:'Undo', exact:true}).last().click();
      await page.getByRole('button', {name:/phase-two-add in Codex: Not here/i}).waitFor();
      assert(!fs.existsSync(target)); assert.deepEqual(fs.readFileSync(source), bytes);
    } finally {
      fs.rmSync(path.dirname(source), {recursive:true, force:true});
      fs.rmSync(path.dirname(target), {recursive:true, force:true});
    }
  });
  await test('Phase 2 stale Undo preserves an edited companion file', async () => {
    const name = 'phase-two-stale', source = file('.claude', name), target = file('.codex', name);
    const bytes = Buffer.from('---\nname: phase-two-stale\ndescription: Browser stale fixture.\n---\n# Stale fixture\n');
    const companion = 'notes.txt', original = Buffer.from('Original notes\n'), edited = Buffer.from('Edited after copy\n');
    assert(!fs.existsSync(source) && !fs.existsSync(target));
    fs.mkdirSync(path.dirname(source), {recursive:true}); fs.writeFileSync(source, bytes);
    fs.writeFileSync(path.join(path.dirname(source), companion), original);
    try {
      await go('skills');
      const showSkills = page.getByRole('button', {name:'Show my skills'});
      if (await showSkills.isVisible()) await showSkills.click();
      await page.getByRole('searchbox', {name:'Filter skills'}).fill(name);
      await page.getByRole('button', {name:/phase-two-stale in Codex: Not here/i}).click();
      await page.getByRole('button', {name:/Add to Codex/}).click();
      await page.getByRole('button', {name:/phase-two-stale in Codex: On/i}).waitFor();
      const targetCompanion = path.join(path.dirname(target), companion);
      assert.deepEqual(fs.readFileSync(targetCompanion), original);
      fs.writeFileSync(targetCompanion, edited);
      await page.getByRole('button', {name:'Undo', exact:true}).last().click();
      await page.locator('.toast').filter({hasText:/Couldn't undo/i}).last().waitFor();
      assert.deepEqual(fs.readFileSync(target), bytes);
      assert.deepEqual(fs.readFileSync(targetCompanion), edited);
      assert.deepEqual(fs.readFileSync(source), bytes);
      assert.deepEqual(fs.readFileSync(path.join(path.dirname(source), companion)), original);
    } finally {
      fs.rmSync(path.dirname(source), {recursive:true, force:true});
      fs.rmSync(path.dirname(target), {recursive:true, force:true});
    }
  });
  await test('Phase 2 replace a different copy and Undo restores its bytes and disabled state', async () => {
    const target = file('.codex', 'majority-minor'), source = file('.claude', 'majority-minor');
    const disabledTarget = target + '.disabled';
    const fixture = fs.readFileSync(target), replacement = fs.readFileSync(source);
    const lateInstruction = 'Review this instruction after line forty.';
    const before = Buffer.concat([fixture, Buffer.from('\n' + 'Context line\n'.repeat(40) + lateInstruction + '\n')]);
    fs.renameSync(target, disabledTarget);
    fs.writeFileSync(disabledTarget, before);
    const previewRequest = url => url.pathname === '/api/batch/preview';
    const refuseOnce = route => route.fulfill({status:409, json:{error:'Fixture refused the first preview'}});
    try {
      await go('skills');
      const showSkills = page.getByRole('button', {name:'Show my skills'});
      if (await showSkills.isVisible()) await showSkills.click();
      await page.getByRole('searchbox', {name:'Filter skills'}).fill('majority-minor');
      await page.getByRole('button', {name:/majority-minor in Codex: Different/i}).click();
      await page.getByRole('button', {name:/Compare the two versions/}).click();
      const confirm = page.getByRole('button', {name:'Make copies match', exact:true});
      assert(await confirm.isDisabled());
      await page.locator('.jf-panel-details summary', {hasText:'Codex'}).click();
      await page.getByRole('region', {name:'Codex instructions'}).getByText(lateInstruction, {exact:false}).waitFor();
      await page.getByRole('button', {name:/Keep Claude Code’s version/}).click();
      await page.locator('.jf-panel-preview').getByText(/skill file will be switched on in Codex/).waitFor();
      await page.route(previewRequest, refuseOnce, {times:1});
      await confirm.click();
      await page.getByRole('alert').filter({hasText:'Couldn’t complete the change'}).waitFor();
      assert(!fs.existsSync(target));
      assert.deepEqual(fs.readFileSync(disabledTarget), before);
      await page.getByRole('button', {name:'Try again', exact:true}).click();
      assert(await confirm.isDisabled());
      await page.getByRole('button', {name:/Keep Claude Code’s version/}).click();
      await confirm.click();
      await page.getByRole('button', {name:/majority-minor in Codex: On/i}).waitFor();
      assert.deepEqual(fs.readFileSync(target), replacement);
      assert(!fs.existsSync(disabledTarget));
      await page.getByRole('button', {name:'Undo', exact:true}).last().click();
      await page.getByRole('button', {name:/majority-minor in Codex: Different/i}).waitFor();
      assert(!fs.existsSync(target));
      assert.deepEqual(fs.readFileSync(disabledTarget), before);
      assert.deepEqual(fs.readFileSync(source), replacement);
    } finally {
      await page.unroute(previewRequest, refuseOnce);
      fs.rmSync(disabledTarget, {force:true});
      fs.mkdirSync(path.dirname(target), {recursive:true});
      fs.writeFileSync(target, fixture);
    }
  });
  await test('Phase 2 Skills and command suggestions return focus to their search fields', async () => {
    await go('skills');
    const show = page.getByRole('button', {name:'Show my skills'});
    if (await show.isVisible()) await show.click();
    const filter = page.getByRole('searchbox', {name:'Filter skills'});
    await filter.fill('sole-copx');
    const tableIdea = page.getByRole('button', {name:'sole-copy', exact:true});
    await tableIdea.focus();
    await page.keyboard.press('Enter');
    assert.equal(await filter.inputValue(), 'sole-copy');
    assert(await filter.evaluate(el => el === document.activeElement));
    await page.keyboard.press('Control+k');
    const palette = page.getByRole('combobox', {name:'Search skills, actions and pages'});
    await palette.fill('sole-copx');
    await page.getByRole('dialog').getByRole('button', {name:'sole-copy', exact:true}).focus();
    await page.keyboard.press('Enter');
    assert.equal(await palette.inputValue(), 'sole-copy');
    assert(await palette.evaluate(el => el === document.activeElement));
    await page.keyboard.press('ArrowDown');
    assert(await palette.getAttribute('aria-activedescendant'));
    await page.keyboard.press('Escape');
  });
  await test('Phase 2 1000 skills paginate and filter in the browser', async () => {
    const list = /[/]api[/]skills[?]scope=all(?:&body=0)?$/;
    const records = await (await page.request.get(base+'/api/skills?scope=all')).json();
    const copy = records.find(record => record.scope === 'codex' && record.name === 'same-everywhere');
    assert(copy);
    const many = Array.from({length:1000}, (_, i) => ({...copy, name:'fixture-'+String(i).padStart(4,'0'), path:undefined, physical_path:undefined, body:undefined}));
    try {
      await page.route(list, route => route.fulfill({json:many}));
      await page.goto(base + '/?fixture-step=table-budget#/skills?q=fixture', {waitUntil:'commit'});
      const grid = page.getByRole('grid', {name:'Skills table'});
      const tableMs = await (await page.waitForFunction(() =>
        document.querySelector('.jf-grid tbody tr') && performance.now())).jsonValue();
      assert(tableMs <= 1500, `Skills table became interactive in ${tableMs} ms (limit 1500 ms)`);
      assert.equal(await grid.locator('tbody tr').count(), 50);
      await page.getByRole('button', {name:'Show 50 more'}).click();
      assert.equal(await grid.locator('tbody tr').count(), 100);
      const enterTimedQuery = async (input) => {
        const start = performance.now();
        input.value = 'fixture-0999';
        input.dispatchEvent(new Event('input', {bubbles:true}));
        await window.Vue.nextTick();
        return performance.now() - start;
      };
      const filterMs = await page.getByRole('searchbox', {name:'Filter skills'}).evaluate(enterTimedQuery);
      assert(filterMs <= 100, `table filter took ${filterMs} ms (limit 100 ms)`);
      assert.equal(await grid.locator('tbody tr').count(), 1);
      assert.match(await grid.locator('tbody tr').innerText(), /fixture-0999/);
      await page.keyboard.press('Control+k');
      const paletteMs = await page.getByRole('combobox', {name:'Search skills, actions and pages'}).evaluate(enterTimedQuery);
      assert(paletteMs <= 100, `palette results took ${paletteMs} ms (limit 100 ms)`);
      await page.getByRole('option', {name:/fixture-0999/}).waitFor();
      await page.keyboard.press('Escape');
    } finally { await page.unrouteAll({behavior:'wait'}); }
  });
  await test('Phase 2 status case table runs in the browser Model', async () => {
    const cases = JSON.parse(fs.readFileSync(path.join(__dirname, '../../tests/fixtures/square-status-cases.json'), 'utf8'));
    await go('skills');
    const failures = await page.evaluate(cases => {
      const M = window.SkillsV2Model;
      const scopes = ['a', 'b', 'c'].map(id => ({id, label:id, kind:'agent', exists:true}));
      return cases.flatMap(c => {
        const model = M.build(c.records, scopes), row = model.skills[0], busy = new Set(c.busy || []);
        return Object.entries(c.expected).flatMap(([id, expected]) => {
          const actual = M.squareStatus(row, model.agent(id), busy);
          return actual === expected ? [] : [`${c.name} ${id}: ${actual} != ${expected}`];
        });
      });
    }, cases);
    assert.deepEqual(failures, []);
  });
  await test('Trash & backups empties only library trash after confirmation', async () => {
    const name = 'phase-four-empty-trash';
    const trashed = [];
    for (const scope of ['global', 'codex']) {
      const created = await page.request.post(base + '/api/skills?scope=' + scope, {
        data:{name, description:'Private purge fixture.', body:`# ${scope} only\n`},
      });
      assert.equal(created.status(), 201);
      const removed = await page.request.delete(`${base}/api/skills/${name}?scope=${scope}`);
      assert(removed.ok());
      trashed.push((await removed.json()).trash_path);
    }
    const [library, agent] = trashed;
    const original = fs.readFileSync(path.join(agent, 'SKILL.md'));
    const purgeRequest = request => request.method() === 'POST' && request.url() === base + '/api/trash/purge';
    let purges = 0;
    const observe = request => { if (purgeRequest(request)) purges++; };
    page.on('request', observe);
    try {
      await go('trash');
      const libraryRestore = restoreButton(name, 'Your library');
      const agentRestore = restoreButton(name, 'Codex');
      await libraryRestore.waitFor();
      await agentRestore.waitFor();
      const empty = trashList.getByRole('button', {name:'Empty library trash…', exact:true});
      await empty.click();
      const confirm = page.getByRole('dialog', {name:/Empty.*library trash/i});
      assert.match(await confirm.innerText(), /permanent|cannot be undone/i);
      await confirm.getByRole('button', {name:'Cancel', exact:true}).click();
      await confirm.waitFor({state:'hidden'});
      assert.equal(purges, 0);
      assert(fs.existsSync(library));
      assert(fs.existsSync(agent));
      await empty.click();
      const purge = page.waitForResponse(response => purgeRequest(response.request()));
      await confirm.getByRole('button', {name:'Delete permanently', exact:true}).click();
      assert((await purge).ok());
      await libraryRestore.waitFor({state:'hidden'});
      await agentRestore.waitFor();
      assert.equal(purges, 1);
      assert(!fs.existsSync(library));
      assert.deepEqual(fs.readFileSync(path.join(agent, 'SKILL.md')), original);
      assert.equal(await page.locator('.toast').getByRole('button', {name:'Undo', exact:true}).count(), 0);
    } finally { page.off('request', observe); }
  });
  await test('No uncaught page errors',async()=>assert.deepEqual(exceptions,[]));
  record('Coverage limit','NOTE','Actual browser zoom is checked only in headed Chrome. Screen-reader and perceptual review require a person.');
  fs.writeFileSync(path.join(root,'results.json'),JSON.stringify({engine,browserVersion,results,failures:failed},null,2)+'\n');await browser.close();process.exitCode=failed?1:0;
})().catch(e=>{console.error(e);process.exitCode=2}).finally(async()=>{if(browser)await browser.close();});
