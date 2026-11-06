"""Contracts for the v2 interface (``skillsmgr/webui/v2``).

The v2 interface is the prototype-final design wired to the real API. It adds
presentation and workflow framing only: the same endpoints, the same observed
state vocabulary, and no new CLI command, Store method, schema or dependency.

Every behavioural check runs the *checked-in* ``model.js`` under Node with the
real ``domain.js``, so it fails when the sources drift rather than when a mock
goes stale.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "skillsmgr" / "webui" / "v2"
DOMAIN_JS = ROOT / "skillsmgr" / "webui" / "domain.js"


def _node(body: str):
    """Load domain.js and model.js into a Node vm and return ``body``'s JSON."""
    script = (
        "const vm=require('vm'),fs=require('fs');"
        "const ctx={window:{},console,Blob,FormData};ctx.window.window=ctx.window;vm.createContext(ctx);"
        f"vm.runInContext(fs.readFileSync({json.dumps(str(DOMAIN_JS))},'utf8'),ctx);"
        f"vm.runInContext(fs.readFileSync({json.dumps(str(V2 / 'model.js'))},'utf8'),ctx);"
        "const M=ctx.window.SkillsV2Model;"
        f"const out=(function(){{{body}}})();"
        "Promise.resolve(out).then(value=>console.log(JSON.stringify(value)))"
        ".catch(error=>{console.error(error);process.exit(1);});"
    )
    res = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, cwd=str(ROOT))
    return json.loads(res.stdout)


NODE = shutil.which("node") is not None
HELPERS = r"""
const scopes=[
 {id:'claude-code',label:'Claude Code',kind:'agent',exists:true,writable:true,consumer:'claude-code',path:'/h/.claude/skills'},
 {id:'codex',label:'Codex',kind:'agent',exists:true,writable:true,consumer:'codex',path:'/h/.codex/skills'},
 {id:'opencode',label:'Opencode',kind:'agent',exists:true,writable:true,consumer:'opencode',path:'/h/.config/opencode/skills'}];
let n=0;
const rec=(name,scope,over)=>Object.assign({name,scope,scope_label:scope,description:'d',category:'uncategorized',
 body:'b',tokens:100,content_hash:'h1',physical_path:'/p/'+scope+'/'+name,path:'/p/'+scope+'/'+name,
 instance_states:['active'],disabled:0,malformed:false,addressable:true,decode_error:''},over||{});
"""


@unittest.skipUnless(NODE, "node is required")
class ModelStatusTests(unittest.TestCase):
    def _status(self, records_js: str):
        return _node(HELPERS + f"const m=M.build({records_js},scopes);"
                     "return Object.fromEntries(m.skills.map(s=>[s.name,s.status.label]));")

    def test_matching_copies_are_working(self):
        out = self._status("[rec('a','claude-code'),rec('a','codex')]")
        self.assertEqual(out, {"a": "Working"})

    def test_differing_copies_are_named_without_claiming_an_older_one(self):
        out = self._status("[rec('a','claude-code'),rec('a','codex',{content_hash:'h2'})]")
        self.assertEqual(out, {"a": "Copies differ"})

    def test_a_refused_symlink_is_not_a_damaged_skill(self):
        # The agent reads a linked skill fine; this tool just will not follow it.
        out = self._status(
            "[rec('a','claude-code',{malformed:true,instance_states:['invalid'],"
            "decode_error:'skill path escapes managed root'})]")
        self.assertEqual(out, {"a": "Linked elsewhere"})

    def test_a_damaged_document_cannot_be_read(self):
        out = self._status(
            "[rec('a','codex',{malformed:true,instance_states:['invalid'],decode_error:'bad frontmatter'})]")
        self.assertEqual(out, {"a": "Can't be read"})

    def test_system_files_in_a_skills_folder_are_not_skills(self):
        out = self._status(
            "[rec('README.md','codex',{malformed:true,addressable:false,instance_states:['invalid','unaddressable']}),"
            "rec('.system','codex',{malformed:true,addressable:false,instance_states:['invalid','unaddressable']})]")
        self.assertEqual(out, {"README.md": "Not a skill", ".system": "Not a skill"})

    def test_disabled_everywhere_is_turned_off(self):
        out = self._status(
            "[rec('a','codex',{disabled:1,instance_states:['disabled']}),"
            "rec('a','claude-code',{disabled:1,instance_states:['disabled']})]")
        self.assertEqual(out, {"a": "Turned off"})

    def test_native_off_evidence_stays_separate_from_file_enabled_state(self):
        out = _node(HELPERS + """
        const native={effective_state:'unknown',partial:true,sources:[{source:'user',status:'ok',declared:'off'}]};
        const c=M.build([rec('a','claude-code',{native_state:native})],scopes).skills[0].copies[0];
        return {state:c.state,native:c.record.native_state};""")
        self.assertEqual(out["state"], "on")
        self.assertEqual(out["native"]["effective_state"], "unknown")
        self.assertEqual(out["native"]["sources"][0]["declared"], "off")

    def test_aliases_of_one_physical_document_count_once(self):
        out = _node(HELPERS + "const r=[rec('a','claude-code'),rec('a','claude-code')];"
                    "const m=M.build(r,scopes);return m.skills[0].copies.length;")
        self.assertEqual(out, 1)


@unittest.skipUnless(NODE, "node is required")
class ModelProblemTests(unittest.TestCase):
    def test_reference_is_the_majority_and_a_tie_is_ambiguous(self):
        out = _node(HELPERS + """
        const maj=M.build([rec('a','claude-code'),rec('a','codex',{content_hash:'h2'}),rec('a','opencode')],scopes).skills[0];
        const tie=M.build([rec('a','claude-code'),rec('a','codex',{content_hash:'h2'})],scopes).skills[0];
        return {majority:maj.ref.holders.map(c=>c.scope), majAmbig:maj.ref.ambiguous,
                differing:maj.differing.map(c=>c.scope), tieAmbig:tie.ref.ambiguous};""")
        self.assertEqual(out["majority"], ["claude-code", "opencode"])
        self.assertFalse(out["majAmbig"])
        self.assertEqual(out["differing"], ["codex"])
        self.assertTrue(out["tieAmbig"])

    def test_only_a_damaged_document_with_a_working_copy_is_auto_fixable(self):
        out = _node(HELPERS + """
        const m=M.build([
          rec('dmg','claude-code'),
          rec('dmg','codex',{malformed:true,instance_states:['invalid'],decode_error:'bad'}),
          rec('lnk','claude-code'),
          rec('lnk','codex',{malformed:true,instance_states:['invalid'],decode_error:'escapes managed root'}),
          rec('badname','codex',{addressable:false,instance_states:['unaddressable'],malformed:true}),
          rec('badname','claude-code')],scopes);
        return m.problems.map(p=>({id:p.id,fixable:!!p.fixable,key:p.key}));""")
        by = {p["id"]: p for p in out}
        self.assertTrue(by["bad:dmg"]["fixable"])
        self.assertNotIn("bad:lnk", by)  # a link is a notice, never an error
        self.assertFalse(by["bad:badname"]["fixable"])  # needs a rename on disk
        self.assertTrue(any(p["id"].startswith("link:") for p in out))

    def test_each_distinct_text_gets_a_letter_and_a_is_the_majority(self):
        out = _node(HELPERS + """
        const s=M.build([rec('a','claude-code'),rec('a','codex',{content_hash:'h2'}),rec('a','opencode')],scopes).skills[0];
        return Object.fromEntries(s.copies.map(c=>[c.scope,c.version]));""")
        self.assertEqual(out, {"claude-code": "A", "codex": "B", "opencode": "A"})

    def test_an_undecodable_copy_is_never_offered_an_automatic_overwrite(self):
        # E2E D1: force sync can preserve binary snapshots, but this screen's
        # text Undo cannot restore them. Keep manual guidance here.
        out = _node(HELPERS + """
        const m=M.build([rec('u','claude-code'),
          rec('u','codex',{malformed:true,instance_states:['invalid'],decode_error:"'utf-8' codec can't decode byte 0xff"})],scopes);
        const p=m.problems.find(x=>x.id==='bad:u'); return {fixable:p.fixable, action:p.action, short:p.short};""")
        self.assertFalse(out["fixable"])
        self.assertEqual(out["action"], "Show me how")
        self.assertEqual(out["short"], "Not readable text")

    def test_mixed_damaged_targets_do_not_offer_text_undo_for_binary_bytes(self):
        out = _node(HELPERS + """
        const m=M.build([rec('u','claude-code',{malformed:true,instance_states:['invalid'],decode_error:'bad frontmatter'}),
          rec('u','codex',{malformed:true,instance_states:['invalid'],decode_error:'not valid UTF-8'}),
          rec('u','opencode')],scopes);
        const p=m.problems.find(x=>x.id==='bad:u');return {fixable:p.fixable,short:p.short};""")
        self.assertFalse(out["fixable"])
        self.assertEqual(out["short"], "Not readable text")

    def test_a_refused_link_cannot_be_the_source_of_a_repair(self):
        out = _node(HELPERS + """
        const m=M.build([rec('u','claude-code',{malformed:true,instance_states:['invalid'],decode_error:'bad frontmatter'}),
          rec('u','codex',{malformed:true,instance_states:['invalid'],decode_error:'skill path escapes managed root'})],scopes);
        return m.problems.find(x=>x.id==='bad:u').fixable;""")
        self.assertFalse(out)

    def test_problems_are_ordered_serious_first(self):
        out = _node(HELPERS + """
        const m=M.build([rec('a','claude-code'),rec('a','codex',{content_hash:'h2'}),
          rec('z','codex',{malformed:true,instance_states:['invalid'],decode_error:'bad'}),rec('z','claude-code')],scopes);
        return m.problems.map(p=>p.key);""")
        self.assertEqual(out, sorted(out, key={"bad": 0, "warn": 1, "info": 2}.get))
        self.assertEqual(out[0], "bad")

    def test_an_unreachable_agent_folder_is_not_listed(self):
        out = _node(HELPERS + "const m=M.build([],scopes.concat([{id:'cursor',label:'Cursor',kind:'agent',exists:false}]));"
                    "return m.agents.map(a=>a.id);")
        self.assertNotIn("cursor", out)


@unittest.skipUnless(NODE, "node is required")
class RenderSafetyTests(unittest.TestCase):
    PAYLOADS = [
        "<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "**<b onmouseover=x>** y",
        "[x](javascript:alert(1))", "`<svg onload=alert(1)>`", "```\n<iframe src=//evil></iframe>\n```",
        "> <a href=\"javascript:1\">k</a>", "- <style>*{}</style>", "# \"><script>1</script>",
    ]

    def test_hostile_skill_text_is_escaped_to_inert_text(self):
        out = _node(HELPERS + f"const P={json.dumps(self.PAYLOADS)};return P.map(p=>M.renderDoc(p, new Set()));")
        for html in out:
            tags = set(re.findall(r"<\s*/?\s*([a-zA-Z0-9]+)", html))
            self.assertLessEqual(tags, {"p", "h2", "ul", "ol", "li", "blockquote", "strong", "em", "code", "pre", "mark"},
                                 f"unexpected tag in {html!r}")
            self.assertNotRegex(html, r"<[^>]+\son\w+\s*=")  # no live event-handler attribute

    def test_links_and_italics_render_as_safe_text(self):
        out = _node(HELPERS + "return M.renderDoc('see [docs](https://x.test/a) and *this*', new Set());")
        self.assertNotIn("<a", out)
        self.assertIn("<code>https://x.test/a</code>", out)
        self.assertIn("<em>this</em>", out)

    def test_a_marked_line_is_highlighted_and_nothing_else(self):
        out = _node(HELPERS + "return M.renderDoc('one\\n\\ntwo', new Set(['two']));")
        self.assertIn("<mark>", out)
        self.assertEqual(out.count("<mark>"), 1)

    def test_diff_reports_only_changes_and_survives_large_inputs(self):
        out = _node(HELPERS + """
        const small=M.changes('a\\nb\\nc','a\\nx\\nc').map(l=>l.t+':'+l.x);
        const big=Array.from({length:3000},(_,i)=>'line '+i).join('\\n');
        const t0=Date.now();const d=M.diffLines(big.split('\\n'),big.split('\\n').reverse());
        return {small, bigLines:d.length, ms:Date.now()-t0};""")
        self.assertIn("del:b", out["small"])
        self.assertIn("add:x", out["small"])
        self.assertLess(out["ms"], 5000)  # the cell budget degrades to a plain replace, never a hang


@unittest.skipUnless(NODE, "node is required")
class ErrorPresentationTests(unittest.TestCase):
    def test_library_errors_are_actionable_and_private_paths_are_removed(self):
        source = json.dumps(str(V2 / "app.js"))
        out = _node(f"""
        ctx.Vue={{createApp(options){{ctx.options=options;return {{component(){{}},mount(){{}}}};}},markRaw:x=>x}};
        vm.runInContext(fs.readFileSync({source},'utf8'),ctx);
        return ['Traceback /home/private/secret', 'PermissionError: [Errno 13] /home/private/file',
          'invalid archive: ReadError /tmp/private/upload', "skill '/home/private/demo' changed since review"]
          .map(message=>ctx.options.methods.friendly(message));""")
        for text in out:
            self.assertNotRegex(text, r"/home/|/tmp/|Traceback|PermissionError|ReadError|Errno")
        self.assertIn("backup archive", out[2])
        self.assertIn("changed since review", out[3])


@unittest.skipUnless(NODE, "node is required")
class SyncUndoTests(unittest.TestCase):
    def test_sync_undo_requires_complete_unambiguous_snapshot_coverage(self):
        source = json.dumps(str(V2 / "app.js"))
        out = _node(f"""
        let mode='',posts=0;
        ctx.window.SkillManagerDomain={{...ctx.window.SkillManagerDomain,api:async(url,options={{}})=>{{
          if(options.method==='POST'){{posts++;return {{synced:['codex','opencode']}};}}
          if(url.includes('scope=opencode') && mode==='missing-prior') throw new Error('missing');
          return {{disabled:1,decode_error:mode==='binary'?'not valid UTF-8':''}};
        }}}};
        ctx.Vue={{createApp(options){{ctx.options=options;return {{component(){{}},mount(){{}}}};}},markRaw:x=>x}};
        vm.runInContext(fs.readFileSync({source},'utf8'),ctx);
        return (async()=>{{
          const results=[];
          for(mode of ['normal','new-target','missing-prior','post-failure','before-failure','stale','ambiguous','binary']){{
            const counts={{}};posts=0;
            const context={{snapshotIds:async(_name,scope)=>{{
              const call=counts[scope]=(counts[scope]||0)+1;
              if(mode==='before-failure' && call===1) throw new Error('read failed');
              if(mode==='post-failure' && scope==='opencode' && call===2) throw new Error('read failed');
              if(call===1 || (scope==='opencode' && (mode==='new-target' || mode==='stale'))) return ['old'];
              return mode==='ambiguous'?['old','new','another']:['old','new'];
            }}}};
            try{{const result=await ctx.options.methods.doSync.call(context,'sample','claude-code',['codex','opencode']);
              results.push({{mode,posts,undo:!!ctx.options.methods.undoFor.call({{}},'sample',[result])}});
            }}catch(e){{results.push({{mode,posts,error:e.message}});}}
          }}
          return results;
        }})();""")
        self.assertTrue(out[0]["undo"])
        for result in out[1:]:
            with self.subTest(mode=result["mode"]):
                if result["mode"] == "before-failure":
                    self.assertEqual(result["posts"], 0)
                    self.assertEqual(result["error"], "read failed")
                else:
                    self.assertFalse(result["undo"])
                    self.assertEqual(result["posts"], 1)

    def _restore(self, initially_disabled, was_disabled, fail_restore=False):
        source = json.dumps(str(V2 / "app.js"))
        return _node(f"""
        const calls=[];let disabled={json.dumps(initially_disabled)};
        ctx.window.SkillManagerDomain={{...ctx.window.SkillManagerDomain,api:async(url,options={{}})=>{{
          calls.push([options.method||'GET',url]);
          if(url.includes('/enable?')) disabled=false;
          else if(url.includes('/disable?')) disabled=true;
          else if(url.includes('/api/trash/') && {json.dumps(fail_restore)}) throw new Error('restore failed');
          return {{disabled}};
        }}}};
        ctx.Vue={{createApp(options){{ctx.options=options;return {{component(){{}},mount(){{}}}};}},markRaw:x=>x}};
        vm.runInContext(fs.readFileSync({source},'utf8'),ctx);
        return (async()=>{{
          let error='';
          try{{await ctx.options.methods.restoreSyncText('sample','codex','snapshot-1',{json.dumps(was_disabled)});}}
          catch(e){{error=e.message;}}
          return {{disabled,calls,error}};
        }})();""")

    def test_undo_restores_disabled_target_state_after_enabled_source_sync(self):
        out = self._restore(False, True)
        self.assertTrue(out["disabled"])
        self.assertEqual(out["error"], "")
        self.assertIn("/disable?", out["calls"][-1][1])

    def test_undo_temporarily_enables_a_disabled_copy_for_text_restore(self):
        out = self._restore(True, False)
        self.assertFalse(out["disabled"])
        self.assertIn("/enable?", out["calls"][1][1])
        self.assertIn("/api/trash/", out["calls"][2][1])

    def test_failed_undo_restores_state_before_undo_attempt(self):
        out = self._restore(True, False, fail_restore=True)
        self.assertTrue(out["disabled"])
        self.assertEqual(out["error"], "restore failed")
        self.assertIn("/disable?", out["calls"][-1][1])


@unittest.skipUnless(NODE, "node is required")
class TransportTests(unittest.TestCase):
    """R9: mutating requests declare JSON; forms and files keep their own type."""

    def test_content_type_is_added_only_where_it_belongs(self):
        out = _node("""
        const D = ctx.window.SkillManagerDomain, ct = (o) => (o.headers || {})["Content-Type"] || null;
        return {
          get: ct(D.withJsonType({})),
          bodylessPost: ct(D.withJsonType({ method: "POST" })),
          del: ct(D.withJsonType({ method: "DELETE" })),
          kept: ct(D.withJsonType({ method: "POST", headers: { "content-type": "text/x" } })) ,
          keptLower: D.withJsonType({ method: "POST", headers: { "content-type": "text/x" } }).headers["content-type"],
          blob: ct(D.withJsonType({ method: "PUT", body: new Blob(["x"]) })),
          form: ct(D.withJsonType({ method: "POST", body: new FormData() })),
        };""")
        self.assertIsNone(out["get"])
        self.assertEqual(out["bodylessPost"], "application/json")
        self.assertEqual(out["del"], "application/json")
        self.assertIsNone(out["kept"])
        self.assertEqual(out["keptLower"], "text/x")
        self.assertIsNone(out["blob"])
        self.assertIsNone(out["form"])


class InterfaceSourceTests(unittest.TestCase):
    def setUp(self):
        self.html = (V2 / "index.html").read_text(encoding="utf-8")
        self.css = (V2 / "styles.css").read_text(encoding="utf-8")
        self.app = (V2 / "app.js").read_text(encoding="utf-8")

    def test_no_inline_script_and_no_external_resource(self):
        self.assertNotRegex(self.html, r"<script(?![^>]*\bsrc=)[^>]*>")
        for text in (self.html, self.css, self.app):
            self.assertNotRegex(text, r"https?://(?!www\.w3\.org)", "no runtime fetch from another origin")

    def test_html_is_injected_only_from_the_escaped_renderer_or_constant_icons(self):
        sites = re.findall(r'v-html="([^"]+)"', self.html + self.app)
        self.assertEqual(sorted(set(sites)), ["docHtml", "path", "renderDoc(edit.body)", "themeIcon"])

    def test_every_asset_it_references_exists(self):
        for src in re.findall(r'(?:src|href)="([^"#]+)"', self.html):
            if src.startswith(("/", "http", "#", "data:")):
                continue
            self.assertTrue((V2 / src).resolve().exists(), f"missing {src}")
        for rel in re.findall(r'url\("([^")]+\.woff2)"\)', self.css):
            self.assertTrue((V2 / rel).exists(), f"missing font {rel}")

    def test_tooling_uses_only_the_documented_api_families(self):
        modules = self.app + (V2 / "library-tools.js").read_text(encoding="utf-8") + (V2 / "tool-center.js").read_text(encoding="utf-8")
        called = set(re.findall(r"[\"'`](/api/[a-z-]+)", modules))
        self.assertLessEqual(called, {"/api/scopes", "/api/skills", "/api/history", "/api/sync", "/api/trash", "/api/import", "/api/export", "/api/catalog", "/api/templates", "/api/batch", "/api/install", "/api/doctor", "/api/stats", "/api/tokens", "/api/workspaces", "/api/source-updates", "/api/validate"})
        self.assertIn("/api/templates", called)
        self.assertIn("/api/batch", called)

    def test_every_css_variable_it_uses_is_declared(self):
        declared = set(re.findall(r"(--[a-z0-9-]+)\s*:", self.css))
        used = set(re.findall(r"var\((--[a-z0-9-]+)", self.css))
        self.assertEqual(used - declared, set())

    def test_both_themes_meet_contrast_for_text_and_controls(self):
        def tokens(block):
            return dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", block))
        light = tokens(self.css[: self.css.index("*, *::before")])
        dark = {**light, **tokens(self.css[self.css.index(':root[data-theme="dark"] {'):])}

        def lum(h):
            r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
            f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

        def ratio(a, b):
            hi, lo = sorted((lum(a), lum(b)), reverse=True)
            return (hi + 0.05) / (lo + 0.05)

        for name, t in (("light", light), ("dark", dark)):
            for fg in ("--ink", "--ink-2", "--muted"):
                for bg in ("--bg", "--surface", "--sunken"):
                    self.assertGreaterEqual(ratio(t[fg], t[bg]), 4.5, f"{name} {fg} on {bg}")
            for fg, bg in (("--ok", "--ok-bg"), ("--warn", "--warn-bg"), ("--bad", "--bad-bg"), ("--off", "--off-bg")):
                self.assertGreaterEqual(ratio(t[fg], t[bg]), 4.5, f"{name} {fg} on {bg}")
            self.assertGreaterEqual(ratio(t["--line-strong"], t["--surface"]), 3.0, f"{name} control boundary")

    def test_phone_navigation_reaches_every_page(self):
        nav = self.html[self.html.index('class="bottomnav"'):]
        nav = nav[: nav.index("</nav>")]
        for page in ("home", "skills", "map", "inbox", "recovery"):
            self.assertIn(f'href="#/{page}"', nav)

    def test_reduced_motion_is_honoured(self):
        self.assertIn("prefers-reduced-motion", self.css)

    def test_every_dialog_and_nav_target_is_reachable(self):
        for page in ("home", "skills", "map", "inbox"):
            self.assertIn(f'href="#/{page}"', self.html)


class ServedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os

        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        # Isolate HOME as well as the data root: scope-aware routes read the
        # real agent folders otherwise (see test_web_client_contracts).
        cls._old = {k: os.environ.get(k) for k in ("HOME", "SKILLS_MANAGER_DATA")}
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["HOME"] = cls.tmp.name
        data = Path(cls.tmp.name) / "data"
        data.mkdir(mode=0o700)
        os.environ["SKILLS_MANAGER_DATA"] = str(data)
        cls.store = Store()
        cls.store.init_db()
        cls.server = WebAppServer(cls.store, port=0)
        cls.port = cls.server.httpd.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        import os

        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.httpd.server_close()
        cls.tmp.cleanup()
        for key, value in cls._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _get(self, path):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers.get("Content-Type", ""), exc.read()

    def test_the_interface_and_its_assets_are_served(self):
        for path, kind in (("/v2/", "text/html"), ("/v2/index.html", "text/html"), ("/v2/app.js", "javascript"),
                           ("/v2/model.js", "javascript"), ("/v2/styles.css", "text/css"),
                           ("/v2/library-tools.js", "javascript"), ("/v2/tool-center.js", "javascript"), ("/v2/tools.css", "text/css"),
                           ("/classic/", "text/html"), ("/classic/app.js", "javascript"), ("/classic/domain.js", "javascript"), ("/classic/styles.css", "text/css"),
                           ("/v2/fonts/Newsreader-var.woff2", "font/woff2")):
            status, ctype, body = self._get(path)
            self.assertEqual(status, 200, path)
            self.assertIn(kind, ctype, path)
            self.assertTrue(body, path)

    def test_traversal_out_of_the_interface_directory_is_refused(self):
        for path in ("/v2/../../pyproject.toml", "/v2/%2e%2e/%2e%2e/pyproject.toml", "/v2/..%2f..%2fpyproject.toml"):
            status, _, body = self._get(path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"[project]", body)

    def test_v2_is_default_and_classic_remains_available_explicitly(self):
        status, _, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b'src="model.js"', body)
        status, _, body = self._get("/classic/")
        self.assertEqual(status, 200)
        self.assertIn(b"overview", body.lower())

    def test_classic_namespace_cannot_read_files_outside_webui(self):
        for path in ("/classic/../../pyproject.toml", "/classic/%2e%2e/%2e%2e/pyproject.toml", "/classic/static/../../../pyproject.toml"):
            status, _, body = self._get(path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"[project]", body)

    def test_entry_redirects_keep_queries_and_use_only_fixed_local_paths(self):
        import http.client

        for path, expected in (("/", "/v2/"), ("/?window=claude&x=1", "/v2/?window=claude&x=1"),
                               ("/index.html?x=1", "/v2/?x=1"), ("/classic?x=1", "/classic/?x=1"),
                               ("/v2?x=1", "/v2/?x=1")):
            with self.subTest(path=path):
                connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
                try:
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 308)
                    self.assertEqual(response.getheader("Location"), expected)
                    self.assertEqual(response.read(), b"")
                finally:
                    connection.close()


if __name__ == "__main__":
    unittest.main()
