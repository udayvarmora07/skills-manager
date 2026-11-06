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
        f"const out=(function(){{{body}}})();console.log(JSON.stringify(out));"
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
        # E2E D1: the backend refuses to overwrite a non-UTF-8 file, so the UI
        # must not promise a one-click fix it cannot deliver.
        out = _node(HELPERS + """
        const m=M.build([rec('u','claude-code'),
          rec('u','codex',{malformed:true,instance_states:['invalid'],decode_error:"'utf-8' codec can't decode byte 0xff"})],scopes);
        const p=m.problems.find(x=>x.id==='bad:u'); return {fixable:p.fixable, action:p.action, short:p.short};""")
        self.assertFalse(out["fixable"])
        self.assertEqual(out["action"], "Show me how")
        self.assertEqual(out["short"], "Not readable text")

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

    def test_it_uses_the_existing_api_only(self):
        called = set(re.findall(r'(?:api\(|`|")(/api/[a-z-]+)', self.app))
        self.assertLessEqual(called, {"/api/scopes", "/api/skills", "/api/history", "/api/sync", "/api/trash", "/api/import", "/api/export"})

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

    def test_the_classic_interface_is_untouched(self):
        status, _, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"overview", body.lower())


if __name__ == "__main__":
    unittest.main()
