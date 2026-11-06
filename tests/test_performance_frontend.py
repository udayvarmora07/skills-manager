"""Behavioral regressions for frontend performance changes."""

from __future__ import annotations

import json
import re
import subprocess
import unittest


def run_frontend(script: str) -> dict:
    capture_error = "process.on('uncaughtException',e=>{console.error('CAUGHT '+e.name+': '+e.message);process.exitCode=1}); process.on('unhandledRejection',e=>{console.error('CAUGHT '+e.name+': '+e.message);process.exitCode=1});\n"
    result = subprocess.run(["node", "-e", capture_error + script], capture_output=True, text=True, timeout=30)
    if result.returncode:
        lines = [line for line in result.stderr.splitlines() if len(line) < 1000]
        raise AssertionError("\n".join(lines[-8:]))
    return json.loads(result.stdout)


class FrontendPerformanceBehaviorTests(unittest.TestCase):
    def test_startup_starts_all_loaders_once_and_list_can_render_before_stats(self):
        result = run_frontend(r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {
  window: {}, Vue: {createApp(app){sandbox.app = app; return {mount(){}};}},
  localStorage: {getItem(){return null;}, setItem(){}},
  document: {addEventListener(){}, removeEventListener(){}, documentElement:{dataset:{},lang:'en'}, querySelectorAll(){return[];}, querySelector(){return null;}},
  setTimeout, clearTimeout
};
const context=vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js','utf8'), context);
vm.runInContext(fs.readFileSync('skillsmgr/webui/app.js','utf8'), context);
const app = sandbox.app, calls = [], pending = {};
const ctx = {...app.data(), ...app.methods, $nextTick(){}};
for (const name of ['loadScopes','loadSkills','loadTrash','loadOverviewHistory','loadCatalog','loadStatsTokens']) {
  ctx[name] = () => {
    calls.push(name);
    if (name === 'loadSkills') { ctx.skills = [{name:'alpha',scope:'global'}]; return Promise.resolve(); }
    return new Promise(resolve => { pending[name] = resolve; });
  };
}
const visible = () => ctx.libraryMode === 'instances' ? ctx.skills
  : app.computed.logicalSkills.call({...ctx, filteredSkills:app.computed.filteredSkills.call(ctx)});
(async () => {
  const startup = ctx.loadInitialData();
  await Promise.resolve();
  const readyBeforeStats = visible().map(row => row.name);
  const calledOnce = calls.length === 6 && new Set(calls).size === 6;
  for (const resolve of Object.values(pending)) resolve();
  await startup;
  console.log(JSON.stringify({calls, calledOnce, readyBeforeStats}));
})();
''')
        self.assertTrue(result["calledOnce"])
        self.assertEqual(result["readyBeforeStats"], ["alpha"])

    def test_real_domain_formatters_preserve_locale_output_and_bound_cache(self):
        result = run_frontend(r'''
const fs = require('fs'), vm = require('vm');
const NativeNumber = Intl.NumberFormat, NativeDate = Intl.DateTimeFormat;
let numberBuilds = 0, dateBuilds = 0;
class CountedNumber extends NativeNumber { constructor(...args){ super(...args); numberBuilds++; } }
class CountedDate extends NativeDate { constructor(...args){ super(...args); dateBuilds++; } }
const sandbox = {window:{}, Intl:{NumberFormat:CountedNumber,DateTimeFormat:CountedDate}};
const context=vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js','utf8'), context);
const d = sandbox.window.SkillManagerDomain;
const first = d.numberFormatter('en-IN').format(1234567);
const second = d.numberFormatter('en-IN').format(1234567);
const reusedAfterRepeat = numberBuilds;
const usDefault = d.numberFormatter('en-US').format(1234567);
const usFixed = d.numberFormatter('en-US',{minimumFractionDigits:2}).format(1234567);
const date1 = d.dateFormatter('en-GB',{dateStyle:'medium',timeStyle:'short'}).format(new Date('2026-09-22T13:45:00Z'));
const date2 = d.dateFormatter('en-GB',{dateStyle:'medium',timeStyle:'short'}).format(new Date('2026-09-22T13:45:00Z'));
const reusedDate = dateBuilds;
for (let i=0;i<70;i++) d.numberFormatter('en-US',{
  minimumFractionDigits:i%21,
  signDisplay:['auto','never','always','exceptZero'][Math.floor(i/21)]
}).format(7);
// The cache is capped at 64 entries; after its reset the oldest key must be
// reconstructed, while repeated current keys above reuse the same instance.
d.numberFormatter('en-US',{minimumFractionDigits:0,signDisplay:'auto'}).format(7);
console.log(JSON.stringify({first,second,usDefault,usFixed,date1,date2,reusedAfterRepeat,reusedDate,numberBuilds,dateBuilds}));
''')
        self.assertEqual(result["first"], "12,34,567")
        self.assertEqual(result["second"], result["first"])
        self.assertEqual(result["reusedAfterRepeat"], 1)
        self.assertEqual(result["usDefault"], "1,234,567")
        self.assertEqual(result["usFixed"], "1,234,567.00")
        self.assertEqual(result["date2"], result["date1"])
        self.assertEqual(result["reusedDate"], 1)
        self.assertEqual(result["dateBuilds"], 1)
        self.assertEqual(result["numberBuilds"], 74)

    def test_real_vue_row_cache_tracks_row_scope_mode_and_selection_changes(self):
        result = run_frontend(r'''
const fs = require('fs'), vm = require('vm');
const sandbox = {localStorage:{getItem(){return null;},setItem(){}},
  document:{addEventListener(){},removeEventListener(){},documentElement:{dataset:{},lang:'en'},querySelectorAll(){return[];},querySelector(){return null;},createElement(){return{};},createElementNS(){return{};},createTextNode(){return{};},createComment(){return{};}},setTimeout,clearTimeout};
 sandbox.window=sandbox;
const context=vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/domain.js','utf8'),context);
vm.runInContext(fs.readFileSync('skillsmgr/webui/static/vendor/vue.global.prod.js','utf8'),context);
const Vue=sandbox.Vue, createApp=Vue.createApp; Vue.createApp=app=>{sandbox.app=app;return{mount(){}};};
vm.runInContext(fs.readFileSync('skillsmgr/webui/app.js','utf8'),context); Vue.createApp=createApp;
const app=sandbox.app, ctx=Vue.reactive({...app.data(),...app.methods,$nextTick(){}});
ctx.filteredSkills=Vue.computed(()=>app.computed.filteredSkills.call(ctx));
ctx.logicalSkills=Vue.computed(()=>app.computed.logicalSkills.call(ctx));
ctx.visibleSkills=Vue.computed(()=>app.computed.visibleSkills.call(ctx));
ctx.libraryRowMeta=Vue.computed(()=>app.computed.libraryRowMeta.call(ctx));
ctx.selectedKeySet=Vue.computed(()=>app.computed.selectedKeySet.call(ctx));
ctx.libraryMode='instances';
ctx.scopes=[{id:'global',label:'First label',kind:'global',consumer:'manager'}];
const raw={name:'alpha',scope:'global',disabled:false,tags:['one'],physical_path:'/root/alpha'};
const secondRaw={name:'beta',scope:'agents',disabled:true,tags:['two'],physical_path:'/agents/beta'};
ctx.scopes.push({id:'agents',label:'Agent skills',kind:'agent',consumer:'shared'});
ctx.skills=[raw,secondRaw];ctx.allSkills=ctx.skills;
const computed=ctx.libraryRowMeta, one=computed.get(Vue.toRaw(ctx.skills[0]));
const firstLabel=one.groups[0].names[0], firstBadge=one.badges[0].text;
ctx.liveAnnouncement='unrelated';
const beforeUnrelated=computed;
const stable=beforeUnrelated===ctx.libraryRowMeta;
ctx.scopes[0].label='Second label';
const newMeta=ctx.libraryRowMeta.get(Vue.toRaw(ctx.skills[0]));
const secondLabel=newMeta.groups[0].names[0];
ctx.skills[0].tags.push('new');
const rowTags=ctx.rowBadgeItems(ctx.skills[0]).map(item=>item.text);
ctx.selectedKeys=[ctx.targetKey(ctx.skills[0])];
const selected=ctx.isSelected(ctx.skills[0]);
ctx.filter='disabled';
const filteredNames=ctx.visibleSkills.map(row=>row.name);
ctx.skills[0].disabled=true;
const disabledNames=ctx.visibleSkills.map(row=>row.name);
ctx.skills[0].disabled=false;
ctx.filter='';
ctx.libraryMode='library';
const logicalNames=ctx.visibleSkills.map(row=>row.name);
const logicalLabel=ctx.groupedIdentities(ctx.visibleSkills[0])[0].names[0];
const libraryBadges=ctx.rowBadgeItems(ctx.visibleSkills[0]).map(item=>item.text);
ctx.selectedKeys=[];
const cleared=ctx.isSelected(ctx.skills[0]);
console.log(JSON.stringify({firstLabel,secondLabel,firstBadge,stable,selected,filteredNames,disabledNames,rowTags,logicalNames,logicalLabel,libraryBadges,cleared}));
''')
        self.assertEqual(result["firstLabel"], "First label")
        self.assertEqual(result["secondLabel"], "Second label")
        self.assertTrue(result["stable"])
        self.assertTrue(result["selected"])
        self.assertEqual(result["filteredNames"], ["beta"])
        self.assertEqual(result["disabledNames"], ["alpha", "beta"])
        self.assertEqual(result["rowTags"], ["#one", "#new"])
        self.assertEqual(result["logicalNames"], ["alpha", "beta"])
        self.assertEqual(result["logicalLabel"], "Second label")
        self.assertEqual(result["libraryBadges"], ["#one", "#new"])
        self.assertFalse(result["cleared"])

    def test_edit_waits_for_body_and_does_not_open_for_stale_or_missing_selection(self):
        result = run_frontend(r'''
const fs = require('fs'), vm = require('vm');
let releaseAlpha, releaseBeta, holdAlpha=false;
const requests=[];
const Domain={api:url=>{
  requests.push(url);
  if(url==='/api/skills/alpha?scope=global') {
    if (!holdAlpha) return Promise.resolve({name:'alpha',scope:'global',description:'A'});
    return new Promise(resolve=>{releaseAlpha=()=>resolve({name:'alpha',scope:'global',description:'A'});});
  }
  if(url==='/api/skills/beta?scope=global') return new Promise(resolve=>{releaseBeta=()=>resolve({name:'beta',scope:'global',description:'B'});});
  throw new Error(url);
},
  apiText:async url=> url.includes('/beta/') ? '---\nname: beta\ndescription: B\n---\nbeta body' : '---\nname: alpha\ndescription: A\n---\nalpha body',
  parseFrontmatter:text=>({body:text.endsWith('beta body')?'beta body':'alpha body'}),formatBytes(){},formatTokens(){},tokenPctClass(){},tokenBarWidth(){},numberFormatter(){},dateFormatter(){},renderMarkdown(){},formatCompat(){},formatTools(){},groupLogicalSkills(){return[];},deriveLogicalSkillIdentity(){},observedIdentity(){},observeRecord(){},observedStateFor(){},observedStateKeys(){}};
const sandbox={window:{SkillManagerDomain:Domain},Vue:{createApp(app){sandbox.app=app;return{mount(){}};}},
  localStorage:{getItem(){return null;},setItem(){}},document:{activeElement:null,addEventListener(){},removeEventListener(){},documentElement:{dataset:{},lang:'en'},querySelectorAll(){return[];},querySelector(){return null;}},setTimeout,clearTimeout};
const context=vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('skillsmgr/webui/app.js','utf8'),context);
const ctx={...sandbox.app.data(),...sandbox.app.methods,$nextTick(){}};
(async()=>{
  ctx.selectedName='alpha';ctx.selected=null;ctx.activeScope='all';
  ctx.skills=[{name:'alpha',scope:'global'},{name:'alpha',scope:'codex'}];
  ctx.loadingDetail=true;
  const pendingRequestCount=requests.length;
  await ctx.openEdit();
  const openedDuringUnknownDetail=!!ctx.modals.skill;
  const issuedCompetingRequest=requests.length!==pendingRequestCount;
  ctx.loadingDetail=false;ctx.modals.skill=null;
  holdAlpha=true;
  ctx.selectedName='alpha';ctx.selected=null;
  const opening=ctx.openEdit();
  await Promise.resolve();
  let firstError=null;
  if (releaseAlpha) {
    const beta=ctx.loadDetail('beta','global');
    await Promise.resolve();
    releaseBeta(); await beta;
    releaseAlpha(); await opening;
  } else {
    try { await opening; } catch (e) { firstError=e.message; }
  }
  const wrongEditor=!!ctx.modals.skill;
  ctx.modals.skill=null;ctx.selectedName='alpha';ctx.selected={name:'alpha',scope:'global',description:'A'};
  ctx.skills=[{name:'alpha',scope:'global'}];ctx.view='quality';ctx.query='old';ctx.filter='disabled';ctx.tagFilter='tag';
  ctx.switchView=view=>{ctx.view=view;};ctx.$nextTick=fn=>fn();
  ctx.inspectQualityInLibrary();
  const qualityView=ctx.view;
  const openingAlpha=ctx.openEdit();await Promise.resolve();
  if (releaseAlpha) { releaseAlpha(); await openingAlpha; }
  const body=ctx.modals.skill && ctx.modals.skill.form.body;
  console.log(JSON.stringify({openedDuringUnknownDetail,issuedCompetingRequest,firstError,wrongEditor,body,qualityView}));
})();
''')
        self.assertFalse(result["openedDuringUnknownDetail"])
        self.assertFalse(result["issuedCompetingRequest"])
        self.assertIsNone(result["firstError"])
        self.assertFalse(result["wrongEditor"])
        self.assertEqual(result["body"], "alpha body")
        self.assertEqual(result["qualityView"], "skills")


if __name__ == "__main__":
    unittest.main()
