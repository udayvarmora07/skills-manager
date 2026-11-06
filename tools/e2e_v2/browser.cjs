/* Optional developer-only browser checks; launched by run.py with isolated HOME/data. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = process.env.BROWSER_TEST_ROOT, base = process.env.BROWSER_TEST_BASE;
if (!root || !base) throw Error('Use run.py to create a safe isolated fixture');
if (new URL(base).hostname!=='127.0.0.1' || new URL(base).protocol!=='http:' || fs.readFileSync(path.join(root,'server-url.txt'),'utf8')!==base) throw Error('Use only the isolated loopback server started by run.py');
const home = process.env.BROWSER_TEST_HOME, results = [], exceptions = [];
let failed = 0, browser;
function record(name, status, detail='') { results.push({name, status, detail}); console.log(`${status} ${name}${detail ? ': '+detail : ''}`); }
async function test(name, fn) { if(process.env.BROWSER_TEST_FILTER && !name.includes(process.env.BROWSER_TEST_FILTER)) return; try { await fn(); record(name, 'PASS'); } catch (e) { failed++; record(name, 'FAIL', String(e.message)); } }
(async () => {
  browser = await chromium.launch({executablePath:process.env.CHROME_BIN || undefined, headless:process.env.BROWSER_TEST_HEADED!=='1', args:process.env.BROWSER_TEST_HEADED==='1'?['--ozone-platform=x11']:[], chromiumSandbox:true});
  const context = await browser.newContext({viewport:{width:1280,height:900}});
  const page = await context.newPage(); page.setDefaultTimeout(5000);
  page.on('pageerror', e => exceptions.push(e.message));
  let navigation = 0;
  async function go(route) { await page.goto(base+'/v2/?fixture-step='+(++navigation)+'#/'+route); await page.locator('main').waitFor(); await page.waitForLoadState('networkidle'); if (route.startsWith('skill/')) await page.locator('.use').first().waitFor(); await page.waitForTimeout(200); }
  async function theme(t) { for (let i=0;i<3 && await page.locator('html').getAttribute('data-theme')!==t;i++) await page.locator('.themebtn').first().click(); assert.equal(await page.locator('html').getAttribute('data-theme'),t); }
  const file=(scope,name='same-everywhere')=>path.join(home,scope,'skills',name,'SKILL.md');
  await test('Unreadable Inbox guidance preserves original bytes',async()=>{ await go('inbox');const f=file('.codex','damaged-one'), bytes=fs.readFileSync(f);if (!(await page.locator('#focus-t').innerText()).includes('damaged-one')) await page.locator('.qi').filter({hasText:'damaged-one'}).click();assert.equal(await page.locator('[data-primary]').innerText(),'Show me how');await page.locator('[data-primary]').click();assert.match(await page.locator('.dlg').innerText(),/original file/);assert.deepEqual(fs.readFileSync(f),bytes);await page.keyboard.press('Escape'); });
  await test('Home Inbox count equals queue; acknowledging a note is not a fix',async()=>{await go('home');let t=await page.locator('.side .card').first().innerText();let n=Number(t.match(/(\d+) things?/)[1]);await page.locator('.look a').first().click();let prog=await page.locator('.prog').innerText();assert.equal(Number(prog.match(/(\d+) to go/)[1]),n);await page.locator('.qi').filter({hasText:'.system'}).click();await page.locator('[data-primary]').click();assert.match(await page.locator('.prog').innerText(),/^0 fixed/);await page.locator('.tabs a').filter({hasText:'Home'}).click();assert.match(await page.locator('.side .card').first().innerText(),new RegExp(`\\b${n-1} things?`));});
  await test('Disabled Enter does not sync a tied copy',async()=>{await go('inbox');await page.locator('.qi').filter({hasText:'split-even'}).click();let f=file('.codex','split-even'), bytes=fs.readFileSync(f),posts=0;const observe=req=>{if(req.method()==='POST'&&req.url().endsWith('/api/sync'))posts++;};page.on('request',observe);assert(await page.locator('[data-primary]').isDisabled());await page.locator('#h1').focus();await page.keyboard.press('Enter');await page.waitForTimeout(300);assert.deepEqual(fs.readFileSync(f),bytes);page.off('request',observe);assert.equal(posts,0);});
  await test('Keyboard: Enter on Open skill navigates and never runs the fix (SR-1)',async()=>{await go('inbox');if(!(await page.locator('#focus-t').innerText()).includes('damaged-fm'))await page.locator('.qi').filter({hasText:'damaged-fm'}).click();const f=file('.codex','damaged-fm'),bytes=fs.readFileSync(f);let posts=0;const observe=req=>{if(req.method()==='POST'&&req.url().endsWith('/api/sync'))posts++;};page.on('request',observe);try{await page.locator('.f-acts a.link').filter({hasText:'Open skill'}).focus();await page.keyboard.press('Enter');await page.waitForTimeout(500);assert(page.url().includes('#/skill/damaged-fm'),page.url());assert.equal(posts,0);assert.deepEqual(fs.readFileSync(f),bytes);}finally{page.off('request',observe);}});
  await test('Skip link keeps the current page and focuses its heading (SR-2)',async()=>{await go('skill/same-everywhere');await page.locator('a.skip').focus();await page.keyboard.press('Enter');await page.waitForTimeout(200);assert(page.url().endsWith('#/skill/same-everywhere'),page.url());assert.equal(await page.evaluate(()=>document.activeElement&&document.activeElement.id),'h1');});
  await test('Accessible names: brand at phone width, differing copy on its switch, distinct Fix and Peek names (SR-4/6/7/11)',async()=>{await page.setViewportSize({width:390,height:844});try{await go('home');assert.equal(await page.locator('a.brand').getAttribute('aria-label'),'Skills Manager home');const fixes=await page.locator('.look a').evaluateAll(a=>a.map(x=>x.getAttribute('aria-label')));assert.equal(new Set(fixes).size,fixes.length);}finally{await page.setViewportSize({width:1280,height:900});}await go('skill/majority-minor');const names=await page.locator('.use .switch .sr-only').allInnerTexts();assert(names.some(n=>/Codex.*differs from most places/.test(n)),names.join(' | '));await go('map');await page.locator('.node').filter({hasText:'Codex'}).click();const peeks=await page.locator('.peek').evaluateAll(a=>a.map(x=>x.getAttribute('aria-label')));assert(peeks.length>0&&new Set(peeks).size===peeks.length,peeks.join(' | '));});
  await test('An Undo toast stays while focused (SR-3)',async()=>{await go('skill/same-everywhere');await page.locator('.use').filter({hasText:'Codex'}).locator('label.switch').click();const undo=page.locator('.toast button').filter({hasText:'Undo'}).last();await undo.waitFor();await undo.focus();const held=await page.evaluate(()=>!!document.activeElement.closest('.toast'));assert(held);await undo.click();await page.waitForTimeout(700);assert(fs.existsSync(file('.codex')));});
  await test('Delayed double click issues one sync and Undo restores bytes and queue',async()=>{await go('inbox');await page.locator('.qi').filter({hasText:'majority-minor'}).click();let f=file('.codex','majority-minor'),before=fs.readFileSync(f),count=0;await page.route('**/api/sync',async r=>{count++;await new Promise(resolve=>setTimeout(resolve,400));await r.continue();});try{await page.locator('[data-primary]').dblclick({delay:25}).catch(()=>{});await page.waitForTimeout(900);assert.equal(count,1);assert.notDeepEqual(fs.readFileSync(f),before);await page.locator('.toast button').filter({hasText:'Undo'}).last().click();await page.waitForTimeout(700);assert.deepEqual(fs.readFileSync(f),before);assert.match(await page.locator('main').innerText(),/majority-minor/);assert.match(await page.locator('.prog').innerText(),/^0 fixed/);}finally{await page.unrouteAll({behavior:'wait'});}});
  await test('Stale file toggle reports error without resurrecting fixture',async()=>{await go('skill/same-everywhere');const f=file('.codex'),old=fs.readFileSync(f);fs.unlinkSync(f);try{await page.locator('.use').filter({hasText:'Codex'}).locator('label.switch').click();await page.waitForTimeout(600);assert(!fs.existsSync(f));assert(!fs.existsSync(f+'.disabled'));assert.match((await page.locator('.toast').allInnerTexts()).join(' '),/not installed|not found/i);}finally{fs.writeFileSync(f,old);}});
  await test('Native setting evidence is partial and file switch Undo preserves files',async()=>{await go('skill/same-everywhere');await page.locator('.native-settings summary').click();let t=await page.locator('.native-settings').innerText();assert.match(t,/partial/i);assert.match(t,/loading is unknown/i);assert.match(t,/Declared setting: off/);assert.match(t,/Declared setting: deny/);const f=file('.codex');await page.locator('.use').filter({hasText:'Codex'}).locator('label.switch').click();await page.waitForTimeout(500);assert(fs.existsSync(f+'.disabled'));await page.locator('.toast button').filter({hasText:'Undo'}).last().click();await page.waitForTimeout(600);assert(fs.existsSync(f));assert(!fs.existsSync(f+'.disabled'));});
  await test('Native invalid and unavailable settings render without exposing values',async()=>{let config=path.join(home,'.config/opencode/opencode.json'),saved=fs.readFileSync(config),claude=path.join(home,'.claude/settings.json'),oldClaude=fs.readFileSync(claude);fs.writeFileSync(config,'{"private":"fixture-secret",');fs.writeFileSync(claude,JSON.stringify({skillOverrides:{'majority-minor':'invalid-fixture-value'}}));try{await go('skill/majority-minor');await page.locator('.native-settings summary').click();let t=await page.locator('.native-settings').innerText();assert.match(t,/invalid/);assert.match(t,/unavailable/);assert.doesNotMatch(t,/fixture-secret|invalid-fixture-value/);}finally{fs.writeFileSync(config,saved);fs.writeFileSync(claude,oldClaude);}});
  await test('Discard navigation, dialog focus trap and cancellation',async()=>{await go('skill/same-everywhere');await page.locator('.acts button').filter({hasText:'Edit'}).click();assert(await page.locator('#ed-desc').evaluate(e=>e===document.activeElement));await page.locator('.ed-area').fill('Unsaved browser fixture');await page.locator('.tabs a').filter({hasText:'Home'}).click();await page.locator('.dlg').waitFor();for(let i=0;i<10;i++){await page.keyboard.press('Tab');assert(await page.evaluate(()=>document.querySelector('.dlg').contains(document.activeElement)));}await page.getByRole('button',{name:'Keep editing'}).click();assert(await page.locator('.ed-area').isVisible());await page.locator('.tabs a').filter({hasText:'Home'}).click();await page.getByRole('button',{name:'Discard changes'}).click();await page.waitForTimeout(300);assert(page.url().endsWith('#/home'));});
  await test('Global Recovery restores a trashed fixture',async()=>{await go('skill/library-fixture');await page.locator('.btn-danger').click();assert.equal(await page.locator('.pick input:checked').count(),1);await page.locator('.dlg-f .btn-danger').click();await page.waitForTimeout(700);let f=path.join(root,'data/skills-manager/skills/library-fixture/SKILL.md');assert(!fs.existsSync(f));await go('recovery');assert.match(await page.locator('.rec-list').innerText(),/last changed/);await page.locator('.rec-list button').filter({hasText:'Restore'}).click();await page.waitForTimeout(700);assert(fs.existsSync(f));});
  await test('Classic disable and enable send bodyless POST requests',async()=>{await page.goto(base+'/');await page.waitForTimeout(700);await page.getByRole('button',{name:'Library',exact:true}).first().click();await page.waitForTimeout(400);await page.locator('[data-skill-key$="/library-fixture"]').click();await page.waitForTimeout(400);let requests=[];page.on('request', req=>{if(req.method()==='POST'&&/\/api\/skills\/library-fixture\/(disable|enable)/.test(req.url())) requests.push({url:req.url(),body:req.postData()});});await page.getByRole('button',{name:'Disable',exact:true}).click();await page.waitForTimeout(600);await page.getByRole('button',{name:'Enable',exact:true}).click();await page.waitForTimeout(600);assert.equal(requests.length,2);assert(requests.every(r=>!r.body));let f=path.join(root,'data/skills-manager/skills/library-fixture/SKILL.md');assert(fs.existsSync(f));});
  for (const [name,sourceDisabled,targetDisabled] of [['target-disabled',false,true],['source-disabled',true,false]]) {
    await test(`Sync Undo restores ${name} bytes and disabled state`,async()=>{
      await go('inbox');let focus=await page.locator('#focus-t').innerText();if(!focus.includes(name))await page.locator('.qi').filter({hasText:name}).click();
      const target=file('.codex',name), prior=target+(targetDisabled?'.disabled':'');const source=file('.claude',name)+(sourceDisabled?'.disabled':'');const old=fs.readFileSync(prior),sourceBytes=fs.readFileSync(source);
      await page.locator('.srcpick label').filter({hasText:'Claude Code'}).locator('input').check();await page.locator('[data-primary]').click();await page.waitForTimeout(700);
      const current=fs.existsSync(target)?target:target+'.disabled';assert.deepEqual(fs.readFileSync(current),sourceBytes);await page.locator('.toast button').filter({hasText:'Undo'}).last().click();await page.waitForTimeout(900);
      assert(fs.existsSync(prior));assert(!fs.existsSync(target+(targetDisabled?'':'.disabled')));assert.deepEqual(fs.readFileSync(prior),old);
    });
  }
  await test('Malformed text Inbox repair and Undo reappear',async()=>{
    await go('inbox');
    if (!(await page.locator('#focus-t').innerText()).includes('damaged-fm')) await page.locator('.qi').filter({hasText:'damaged-fm'}).click();
    const f=file('.codex','damaged-fm'), before=fs.readFileSync(f);
    await page.locator('[data-primary]').click();
    await page.getByRole('button',{name:'Undo',exact:true}).last().waitFor();
    assert.notDeepEqual(fs.readFileSync(f),before);
    await page.getByRole('button',{name:'Undo',exact:true}).last().click();
    await page.waitForFunction(()=>document.querySelector('#focus-t')?.textContent.includes('damaged-fm') || [...document.querySelectorAll('.qi')].some(e=>e.textContent.includes('damaged-fm')));
    assert.deepEqual(fs.readFileSync(f),before);
    assert.match(await page.locator('.prog').innerText(),/^0 fixed/);
  });
  await test('Create, editor focus, safe Markdown, save and Undo',async()=>{
    await go('skills');
    await page.getByRole('button',{name:'New skill',exact:true}).first().click();
    const name=page.locator('.dlg input').first();
    assert(await name.evaluate(e=>e===document.activeElement));
    await name.fill('created-browser');

    await page.locator('#nf-desc').fill('Use this fixture to verify browser creation.');
    await page.getByRole('button',{name:'Create skill',exact:true}).click();
    await page.locator('.acts button').filter({hasText:'Edit'}).waitFor();
    const f=file('.claude','created-browser'), original=fs.readFileSync(f);
    await page.locator('.acts button').filter({hasText:'Edit'}).click();
    assert(await page.locator('#ed-desc').evaluate(e=>e===document.activeElement));
    await page.locator('#ed-body').fill('Read *italic* and [docs](https://example.test/a).\n\n<img src=x onerror="window.fixtureAttack=1">');
    await page.getByRole('tab',{name:'Preview',exact:true}).click();
    assert.equal(await page.locator('.doc em').innerText(),'italic');
    assert.equal(await page.locator('.doc a,.doc img,.doc script').count(),0);
    assert.equal(await page.evaluate(()=>window.fixtureAttack),undefined);
    await page.locator('.savebar button').filter({hasText:'Save to'}).click();
    await page.getByRole('button',{name:'Undo',exact:true}).last().waitFor();
    assert.notDeepEqual(fs.readFileSync(f),original);
    await page.getByRole('button',{name:'Undo',exact:true}).last().click();
    await page.waitForTimeout(400);
    assert.deepEqual(fs.readFileSync(f),original);
  });
  await test('One-place dialogs preselect and cancellation keeps files',async()=>{
    await go('skill/sole-copy');
    const f=file('.claude','sole-copy'),before=fs.readFileSync(f);
    await page.getByRole('button',{name:'Move to trash',exact:true}).click();
    assert.equal(await page.locator('.pick input:checked').count(),1);
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    assert.deepEqual(fs.readFileSync(f),before);
  });
  await test('Add-to-agent single target is selected and creates a copy',async()=>{
    await go('skill/share-three');await page.getByRole('button',{name:'Add to agent',exact:true}).click();
    assert.equal(await page.locator('.pick input:checked').count(),1);
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    const f=file('.config/opencode','share-three');assert(!fs.existsSync(f));
    await page.getByRole('button',{name:'Add to agent',exact:true}).click();
    await page.locator('.dlg-f button').filter({hasText:/^Add$/}).click();
    await page.waitForTimeout(500);assert(fs.existsSync(f));
    assert.match((await page.locator('.toast').allInnerTexts()).join(' '),/Undo is unavailable/);
  });
  await test('Backup download/import and invalid archive error',async()=>{
    await go('recovery');
    const download=page.waitForEvent('download');
    await page.getByRole('button',{name:'Download a backup',exact:true}).click();
    const saved=path.join(root,'fixture-backup.tar.gz');await (await download).saveAs(saved);
    assert(fs.statSync(saved).size>0);
    await page.locator('#imp-file').setInputFiles(saved);
    await page.getByRole('button',{name:'Load skills',exact:true}).click();
    await page.waitForTimeout(500);
    assert.match((await page.locator('.toast').allInnerTexts()).join(' '),/already there and kept/);
    const bad=path.join(root,'bad-archive.tar.gz');fs.writeFileSync(bad,'not an archive');
    await page.locator('#imp-file').setInputFiles(bad);
    await page.getByRole('button',{name:'Load skills',exact:true}).click();await page.waitForTimeout(500);
    const text=(await page.locator('.toast').allInnerTexts()).join(' ');
    assert.match(text,/not a backup archive/);assert.doesNotMatch(text,/ReadError|Traceback|[/]tmp[/]/);
    await page.route('**/api/scopes',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'Traceback /home/private/secret PermissionError'})}));
    try{await go('home');assert.doesNotMatch(await page.locator('main').innerText(),/Traceback|PermissionError|[/]home[/]private/);}finally{await page.unrouteAll({behavior:'wait'});}
  });
  await test('Sync map totals, singular grammar and top-link target size',async()=>{
    await go('skills');const total=Number((await page.locator('.seg button').first().innerText()).match(/\d+/)?.[0]);
    await go('map');assert.equal(Number((await page.locator('.hub .num').innerText()).replace(/,/g,'')),total);
    assert.doesNotMatch(await page.locator('main').innerText(),/1 copy differ(?!s)/);
    await page.setViewportSize({width:1280,height:900});
    const box=await page.locator('.top .classic').boundingBox();assert(box.height>=24);assert(box.width>=24);
  });
  await test('Responsive layouts in both themes',async()=>{for(const [label,w,h] of [['desktop',1280,900],['phone',390,844]])for(const t of ['light','dark']){await page.setViewportSize({width:w,height:h});await go('home');await theme(t);for(const r of ['home','skills','skill/same-everywhere','map','inbox','recovery']){await go(r);assert.equal(await page.locator('html').getAttribute('data-theme'),t);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1),false,`${label} ${t} ${r}`);await page.screenshot({path:path.join(root,`${label}-${t}-${r.replace('/','-')}.png`)});}}});
  await test('Phone dark Sync map sampled text contrast',async()=>{
    await page.setViewportSize({width:390,height:844});await go('map');await theme('dark');
    const samples=await page.locator('.maplist .mrow').evaluateAll(rows=>rows.map(row=>{
      const style=getComputedStyle(row),rgb=value=>value.match(/[0-9.]+/g).slice(0,3).map(Number);
      const lum=value=>rgb(value).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
      const foreground=style.color,background=style.backgroundColor,a=lum(foreground),b=lum(background);
      return {foreground,background,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};
    }));
    assert(samples.length);for(const sample of samples)assert(sample.ratio>=4.5,JSON.stringify(sample));
    fs.writeFileSync(path.join(root,'map-contrast.json'),JSON.stringify(samples,null,2)+'\n');
  });
  await test('Empty and one-record shelves render without stale cards',async()=>{
    const response=await page.request.get(base+'/api/skills?scope=all'),records=await response.json();
    const selected=records.find(r=>r.name==='library-fixture');assert(selected);
    for(const fixture of [[],[selected]]){
      await page.route(/[/]api[/]skills[?]scope=all$/,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(fixture)}));
      try{await go('skills');assert.equal(await page.locator('.sk').count(),fixture.length);}finally{await page.unrouteAll({behavior:'wait'});}
    }
  });
  await test('Forced colors focus indicator',async()=>{await page.emulateMedia({forcedColors:'active'});await go('skills');await page.keyboard.press('Tab');assert(await page.evaluate(()=>matchMedia('(forced-colors: active)').matches && document.activeElement!==document.body && getComputedStyle(document.activeElement).outlineStyle!=='none'));await page.screenshot({path:path.join(root,'forced-colors.png')});await page.emulateMedia({forcedColors:'none'});});
  if(process.env.BROWSER_TEST_HEADED==='1') await test('Actual Chrome zoom at 200 and 400 percent',async()=>{
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
      for(const route of ['home','skills','skill/same-everywhere','map','inbox','recovery']){
        await go(route);
        await page.screenshot({path:path.join(root,`browser-zoom-${percent}-${route.replace('/','-')}.png`)});
        const overflow=await page.evaluate(()=>[...document.querySelectorAll('main *')].filter(e=>{const b=e.getBoundingClientRect();return b.width>0 && b.right>document.documentElement.clientWidth+1;}).map(e=>({tag:e.tagName,cls:e.className,text:e.innerText?.slice(0,80),width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right})));
        fs.writeFileSync(path.join(root,`overflow-${percent}-${route.replace('/','-')}.json`),JSON.stringify(overflow,null,2));
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1),false,`browser zoom ${percent}: ${route}`);
      }
      await go('skills');await page.getByRole('button',{name:'New skill',exact:true}).first().click();
      assert(await page.locator('#nf-name').evaluate(e=>e===document.activeElement));
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1),false);
      await page.keyboard.press('Escape');
    }
    fs.writeFileSync(path.join(root,'browser-zoom.json'),JSON.stringify(samples,null,2)+'\n');
    execFileSync('xdotool',['key','--clearmodifiers','ctrl+0']);
  });
  await test('No uncaught page errors',async()=>assert.deepEqual(exceptions,[]));
  record('Coverage limit','NOTE','No screen-reader validation; real browser zoom is checked only in isolated headed mode. CSS magnification is not browser zoom. Screenshots and overflow checks do not constitute a complete accessibility audit.');
  fs.writeFileSync(path.join(root,'results.json'),JSON.stringify({results,failures:failed},null,2)+'\n');await browser.close();process.exitCode=failed?1:0;
})().catch(e=>{console.error(e);process.exitCode=2}).finally(async()=>{if(browser)await browser.close();});
