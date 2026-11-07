"""Exercise shipped v2 operation guards under Node, with no real user data."""

import json
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "skillsmgr" / "webui" / "v2"
HARNESS = r"""
const fs=require('fs'),vm=require('vm');
let calls=[],events=[],handler=async()=>({});
const api=async(url,opts={})=>{calls.push({url,opts});return handler(url,opts)};
class Form { constructor(){this.parts=[]} append(...part){this.parts.push(part)} }
const ctx={window:{SkillManagerDomain:{api,observeRecord:()=>({linkEscape:false})}},console,
 localStorage:{getItem:()=>null,setItem:()=>{}},matchMedia:()=>({matches:false}),
 FormData:Form,confirm:()=>true,navigator:{clipboard:{writeText:async()=>{}}}};
vm.createContext(ctx);
for(const name of ['library-tools.js','tool-center.js'])vm.runInContext(fs.readFileSync(V2+'/'+name,'utf8'),ctx);
function mount(component,props={}){
 const h=Object.assign(component.data(),{records:[],scopes:[],names:[],agentFilter:'all',catalog:{},page:'tools',alive:true,target:null},props);
 h.$emit=(...args)=>events.push(args);h.$nextTick=fn=>Promise.resolve().then(fn);
 h.$refs={review:{showModal(){},close(){}}};
 for(const [name,fn] of Object.entries(component.methods))h[name]=fn.bind(h);
 for(const [name,fn] of Object.entries(component.computed))Object.defineProperty(h,name,{get:()=>fn.call(h),configurable:true});
 return h;
}
const tick=()=>new Promise(r=>setImmediate(r));
"""


def run_node(body):
    script = "const V2=" + json.dumps(str(V2)) + ";" + HARNESS + "\n(async()=>{" + body + "})().then(v=>console.log(JSON.stringify(v))).catch(e=>{console.error(e);process.exit(1)});"
    result = subprocess.run(["node", "-e", script], cwd=ROOT, text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


@unittest.skipUnless(shutil.which("node"), "Node is required for frontend behavior checks")
class ToolBehaviorTests(unittest.TestCase):
    def test_independent_report_reads_do_not_discard_each_others_results(self):
        out = run_node(r"""
          const resolve={};handler=url=>new Promise(r=>resolve[url]=r);
          const h=mount(ctx.window.SkillsV2ToolCenter);
          const a=h.read('/quality','quality'),b=h.read('/stats','report');
          resolve['/stats']({total:3});await b;resolve['/quality']({findings:['evidence']});await a;
          return {quality:h.quality,report:h.report};
        """)
        self.assertEqual(out["quality"], {"findings": ["evidence"]})
        self.assertEqual(out["report"], {"total": 3})

    def test_batch_execution_uses_reviewed_targets_and_options_after_ui_changes(self):
        out = run_node(r"""
          const a={name:'one',scope:'codex',path:'/skills/one',physical_path:'/skills/one',addressable:true};
          const b={name:'two',scope:'codex',path:'/skills/two',physical_path:'/skills/two',addressable:true};
          const h=mount(ctx.window.SkillsV2LibraryTools,{records:[a,b],names:['one','two'],scopes:[{id:'codex',writable:true}]});
          h.selected=[h.key(a)];h.operation='sync';h.frozen=[{name:a.name,scope:a.scope,path:a.path,physical_path:a.physical_path}];h.targets=['claude-code'];h.force=false;
          handler=async url=>url.endsWith('/preview')?{plan_id:'reviewed',target_count:1}:{ok:true,results:[]};
          await h.preview();h.selected=[h.key(b)];h.targets=['other-scope'];h.force=true;await h.execute();
          return calls.map(c=>JSON.parse(c.opts.body));
        """)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[1], {**out[0], "plan_id": "reviewed"})
        self.assertEqual(out[1]["targets"][0]["name"], "one")
        self.assertEqual(out[1]["to_scopes"], ["claude-code"])
        self.assertFalse(out[1]["force"])

    def test_failed_workspace_lookup_clears_previous_project_evidence(self):
        out = run_node(r"""
          const h=mount(ctx.window.SkillsV2ToolCenter,{project:'/new-project',workspace:{project:{path:'/old-project'}}});
          handler=async()=>{throw Error('Project unavailable')};h.loadWorkspace();await tick();
          return {workspace:h.workspace,error:h.error};
        """)
        self.assertIsNone(out["workspace"])
        self.assertEqual(out["error"], "Project unavailable")

    def test_failed_validation_cannot_relabel_old_statistics_as_validation(self):
        out = run_node(r"""
          const h=mount(ctx.window.SkillsV2ToolCenter,{validationName:'one',report:{all_total:4},reportKind:'stats'});
          handler=async()=>{throw Error('Validation unavailable')};await h.validateNamed();
          return {report:h.report,kind:h.reportKind,error:h.error};
        """)
        self.assertIsNone(out["report"])
        self.assertEqual(out["kind"], "validate")
        self.assertEqual(out["error"], "Validation unavailable")

    def test_runner_failure_requests_refresh_without_claiming_completed_refresh(self):
        out = run_node(r"""
          const h=mount(ctx.window.SkillsV2ToolCenter,{source:'owner/repository'});h.runnerPreview=h.runnerSignature;
          handler=async()=>{throw Error('Runner timed out')};await h.runRunner(true);
          return {events,error:h.error,preview:h.runnerPreview,calls:calls.length};
        """)
        self.assertEqual(out["calls"], 1)
        self.assertIn(["changed"], out["events"])
        self.assertIn("refresh was requested", out["error"])
        self.assertNotIn("has been refreshed", out["error"])
        self.assertEqual(out["preview"], "")

    def test_review_completing_after_target_change_is_cancelled(self):
        out = run_node(r"""
          let resolveReview;handler=(url)=>url.endsWith('/reviews')?new Promise(r=>resolveReview=r):Promise.resolve({cancelled:true});
          const a={name:'one',scope:'codex',physical_path:'/skills/one'};
          const h=mount(ctx.window.SkillsV2ToolCenter,{page:'source-update',target:a,files:[{name:'SKILL.md'}]});
          const pending=h.prepareSource();await tick();h.target={name:'two',scope:'codex',physical_path:'/skills/two'};
          resolveReview({review_id:'private-review',review_state:'pending'});await pending;
          return {review:h.sourceReview,calls:calls.map(c=>[c.url,c.opts.method]),error:h.error};
        """)
        self.assertIsNone(out["review"])
        self.assertIn(["/api/source-updates/reviews/private-review", "DELETE"], out["calls"])
        self.assertIn("Target changed", out["error"])

    def test_folder_import_requires_review_and_informed_confirmation(self):
        out = run_node(r"""
          const file={name:'SKILL.md',webkitRelativePath:'new-skill/SKILL.md',size:10,text:async()=> '# Instructions'};
          const h=mount(ctx.window.SkillsV2ToolCenter,{files:[file]});handler=async()=>({imported:['new-skill'],skipped:[]});
          await h.uploadFolder();const before=calls.length;await h.reviewFolder();await h.uploadFolder();const unconfirmed=calls.length;
          h.folderTrust=true;await h.uploadFolder();
          return {before,unconfirmed,after:calls.length,url:calls[0]?.url,reviewed:h.folderDocuments[0].previewed};
        """)
        self.assertEqual((out["before"], out["unconfirmed"], out["after"]), (0, 0, 1))
        self.assertEqual(out["url"], "/api/import")
        self.assertTrue(out["reviewed"])

    def test_folder_selection_change_cannot_reuse_pending_or_completed_review(self):
        out = run_node(r"""
          let resolveText;const old={name:'SKILL.md',webkitRelativePath:'old/SKILL.md',size:10,text:()=>new Promise(r=>resolveText=r)};
          const next={name:'SKILL.md',webkitRelativePath:'new/SKILL.md',size:10,text:async()=> '# New'};
          const h=mount(ctx.window.SkillsV2ToolCenter,{files:[old]});
          const pending=h.reviewFolder();await tick();h.files=[next];resolveText('# Old');await pending;
          h.folderTrust=true;await h.uploadFolder();const staleCalls=calls.length,staleApproved=h.folderReviewed;
          await h.reviewFolder();h.folderTrust=true;h.files=[old];await h.uploadFolder();
          return {staleCalls,staleApproved,after:calls.length};
        """)
        self.assertFalse(out["staleApproved"])
        self.assertEqual(out["staleCalls"], 0)
        self.assertEqual(out["after"], 0)

    def test_exact_copy_editor_uses_its_description_and_only_its_scope(self):
        out = run_node(r"""
          let component;
          ctx.location={hash:''};ctx.Vue={createApp:c=>{component=c;return {component(){},mount(){}}},markRaw:v=>v};
          ctx.window.SkillsV2Model={stripFrontmatter:v=>v};
          Object.assign(ctx.window.SkillManagerDomain,{formatCompat:v=>v||'',formatTools:v=>v||''});
          vm.runInContext(fs.readFileSync(V2+'/app.js','utf8'),ctx);
          const h={skill:{name:'divergent',description:'Primary description'},route:{page:'skill'},refCopy:{name:'divergent',scope:'codex',hash:'h1',description:'Selected copy description',body:'# Selected',bodyLoaded:true,record:{}},readCopyPath:'/codex/divergent',editTargets:[{scope:'codex'},{scope:'claude-code'}],$nextTick:()=>{},bodies:{},bodyErrors:{},ensureBodies:async()=>{},bodyKey:component.methods.bodyKey,bodyOf:component.methods.bodyOf,bodyReady:component.methods.bodyReady,bodyErrorOf:component.methods.bodyErrorOf,bodyFetchable:component.methods.bodyFetchable,toast:()=>{}};
          await component.methods.startEdit.call(h);return h.edit;
        """)
        self.assertEqual(out["desc"], "Selected copy description")
        self.assertEqual(out["baseDesc"], "Selected copy description")
        self.assertEqual(out["targets"], ["codex"])

    def test_body_only_editor_save_omits_unchanged_optional_metadata(self):
        out = run_node(r"""
          let component;
          ctx.location={hash:''};ctx.Vue={createApp:c=>{component=c;return {component(){},mount(){}}},markRaw:v=>v};
          ctx.window.SkillsV2Model={plural:(n,s)=>s};
          vm.runInContext(fs.readFileSync(V2+'/app.js','utf8'),ctx);
          const metadata={category:'',version:'',license:'',compatibility:'',allowed_tools:''};
          const h={edit:{name:'one',desc:'Unchanged',baseDesc:'Unchanged',body:'# Changed',baseBody:'# Original',metadata,baseMetadata:{...metadata},targets:['global']},editError:'',snapshotIds:async()=>[],refresh:async()=>{},toast:()=>{}};
          await component.methods.saveEdit.call(h);return JSON.parse(calls[0].opts.body);
        """)
        self.assertEqual(out, {"body": "# Changed"})

    def test_source_apply_requires_positive_validation_evidence(self):
        out = run_node(r"""
          const h=mount(ctx.window.SkillsV2ToolCenter,{trust:true,sourceTarget:{name:'one',scope:'codex',path:'/skills/one'},sourceReview:{review_id:'r',review_state:'pending',validation:{},comparison:{changed_files:[{path:'SKILL.md'}]}}});
          await h.applySource();return calls.length;
        """)
        self.assertEqual(out, 0)

    def test_profile_enable_preserves_exact_divergent_copies_without_syncing(self):
        out = run_node(r"""
          const h=mount(ctx.window.SkillsV2ToolCenter,{profilePreview:{members:[{name:'one',state:'divergent',instances:[{scope:'codex',physical_path:'/c/one'},{scope:'claude-code',physical_path:'/a/one'}]},{name:'missing',state:'missing',instances:[]}]}});
          handler=async()=>({plan_id:'p'});await h.previewPlan();return JSON.parse(calls[0].opts.body);
        """)
        self.assertEqual(out["operation"], "enable")
        self.assertEqual(len(out["targets"]), 2)
        self.assertEqual(out["to_scopes"], [])
        self.assertFalse(out["force"])


@unittest.skipUnless(shutil.which("node"), "Node is required for frontend behavior checks")
class ClaudeListingCardTests(unittest.TestCase):
    """The Quality page's "What Claude Code sees" card is read-only evidence."""

    def test_verdict_is_a_worded_pill_for_each_status(self):
        out = run_node(r"""
          const h=mount(ctx.window.SkillsV2ToolCenter);
          return ['within_budget','over_budget_estimate','unknown','surprising'].map(s=>h.listingVerdict({status:s}));
        """)
        self.assertEqual(out[0], {"text": "Fits the listing budget", "tone": "ok"})
        self.assertEqual(out[1], {"text": "Over the listing budget (estimate)", "tone": "warn"})
        self.assertEqual(out[2], {"text": "Can't tell — a settings file couldn't be read", "tone": "off"})
        # An unrecognised status must never read as a green "fits".
        self.assertEqual(out[3], {"text": "Budget status not recognised", "tone": "off"})

    def test_the_snippet_is_valid_json_for_any_skill_name(self):
        out = run_node(r"""
          const h=mount(ctx.window.SkillsV2ToolCenter);
          return JSON.parse('{'+h.listingSnippet('we"ird\\name')+'}');
        """)
        self.assertEqual(out, {"skillOverrides": {'we"ird\\name': "name-only"}})

    def test_meter_measures_the_listing_against_its_budget(self):
        out = run_node(r"""
          const h=mount(ctx.window.SkillsV2ToolCenter);
          const over={status:'over_budget_estimate',listing_chars:77516,budget:{budget_chars_estimate:40000}};
          const fits={status:'within_budget',listing_chars:10000,budget:{budget_chars_estimate:40000}};
          const none={status:'within_budget',listing_chars:10,budget:{budget_chars_estimate:0}};
          return {over:{pct:h.listingPct(over),fill:h.listingFill(over),over:h.listingOver(over)},
                  fits:{pct:h.listingPct(fits),fill:h.listingFill(fits),over:h.listingOver(fits)},
                  none:{pct:h.listingPct(none),fill:h.listingFill(none)}};
        """)
        self.assertEqual(out["over"]["pct"], 193.8)
        self.assertEqual(out["over"]["fill"], "100%")
        self.assertTrue(out["over"]["over"])
        self.assertEqual(out["fits"]["pct"], 25.0)
        self.assertEqual(out["fits"]["fill"], "25%")
        self.assertFalse(out["fits"]["over"])
        self.assertEqual(out["none"]["pct"], 0)
        self.assertEqual(out["none"]["fill"], "1.5%")

    def test_the_listing_and_its_partial_reasons_come_from_the_report(self):
        out = run_node(r"""
          const section={instances_observed:3,listed_skills:3,confidence:'partial',
            partial_reasons:['project settings were not read (no project root), so a project skillOverrides entry could change this estimate'],
            status:'within_budget',listing_chars:10,budget:{budget_chars_estimate:1000,assumption:'estimated from 1% of the window'}};
          const h=mount(ctx.window.SkillsV2ToolCenter,{quality:{claude_listing:section}});
          return {card:h.claudeListing,confidence:h.claudeListing.confidence,reasons:h.claudeListing.partial_reasons};
        """)
        self.assertTrue(out["card"])
        self.assertEqual(out["confidence"], "partial")
        self.assertEqual(len(out["reasons"]), 1)

    def test_a_candidate_renders_the_exact_settings_fragment(self):
        out = run_node("const h=mount(ctx.window.SkillsV2ToolCenter);return h.listingSnippet('alpha-skill');")
        self.assertEqual(out, '"skillOverrides": { "alpha-skill": "name-only" }')

    def test_a_missing_section_or_no_instances_shows_no_card(self):
        out = run_node(r"""
          const missing=mount(ctx.window.SkillsV2ToolCenter,{quality:{}});
          const zero=mount(ctx.window.SkillsV2ToolCenter,{quality:{claude_listing:{instances_observed:0}}});
          const present=mount(ctx.window.SkillsV2ToolCenter,{quality:{claude_listing:{instances_observed:2,status:'within_budget'}}});
          return {missing:missing.claudeListing,zero:zero.claudeListing,present:!!present.claudeListing};
        """)
        self.assertIsNone(out["missing"])
        self.assertIsNone(out["zero"])
        self.assertTrue(out["present"])

    def test_excluded_keys_read_as_words_not_api_slugs(self):
        out = run_node(r"""
          const h=mount(ctx.window.SkillsV2ToolCenter);
          return ['disabled','skillOverrides_off','unreadable','name_only','skillOverrides_user_invocable_only','disable_model_invocation','something_new']
            .map(k=>h.listingExcludedLabel(k));
        """)
        self.assertEqual(out, ["Turned off on disk", "Off in settings", "Could not be read",
                               "Name only", "User-invocable only", "Model invocation disabled",
                               "Something new"])

    def test_the_card_adds_no_html_sink_and_binds_every_piece_as_text(self):
        source = (V2 / "tool-center.js").read_text(encoding="utf-8")
        self.assertNotIn("v-html", source)
        for binding in ("claudeListing.partial_reasons", 'pill off">Partial',
                        "Ranked by description size only. Claude Code drops descriptions starting with the skills you use least, which this tool can't see.",
                        "listingSnippet(c.name)", "copyListingSnippet(c.name)",
                        "Free about", "No Claude Code skills were observed"):
            self.assertIn(binding, source)
