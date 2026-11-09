"""SCOPE-2: a scope link into another managed root is readable, never writable.

A skill directory inside an agent scope that is a symlink to a folder outside
that scope used to be refused outright: the row carried an empty body and an
"escapes managed root" reason.  That refusal protects two properties -- a write
can never land outside a managed root, and the tool never reads bytes from an
unmanaged location -- and both are kept.  What changes is that a link whose
target sits inside *another* known managed scope root ("peer root") is read
read-only, because the peer scope would load it anyway.  Every write through
such a link stays refused, with a message naming the target.

Stdlib ``unittest`` only; a private ``HOME`` and data root per test.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from skillsmgr import context
from skillsmgr import scopes
from skillsmgr.store import StoreError, write_snapshot

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "skillsmgr" / "webui" / "v2"
DOMAIN_JS = ROOT / "skillsmgr" / "webui" / "domain.js"
NODE = shutil.which("node") is not None

DOCUMENT = "---\nname: demo\ndescription: Demo skill\n---\nbody\n"


def _node(body: str):
    """Load domain.js, model.js and app.js into a Node vm; return ``body``."""
    script = (
        "const vm=require('vm'),fs=require('fs');"
        "const ctx={window:{},console,Blob,FormData,document:{createElement(){return {};},body:{appendChild(){}}},"
        "location:{hash:'#/skills'},localStorage:{getItem(){return null;},setItem(){}}};"
        "ctx.window.window=ctx.window;vm.createContext(ctx);"
        f"vm.runInContext(fs.readFileSync({json.dumps(str(DOMAIN_JS))},'utf8'),ctx);"
        f"vm.runInContext(fs.readFileSync({json.dumps(str(V2 / 'model.js'))},'utf8'),ctx);"
        "ctx.Vue={createApp(options){ctx.options=options;return {component(){},mount(){}};},markRaw:x=>x};"
        f"vm.runInContext(fs.readFileSync({json.dumps(str(V2 / 'app.js'))},'utf8'),ctx);"
        f"const out=(function(){{{body}}})();"
        "Promise.resolve(out).then(value=>console.log(JSON.stringify(value)))"
        ".catch(error=>{console.error(error);process.exit(1);});"
    )
    res = subprocess.run(["node", "-e", script], capture_output=True, text=True, cwd=str(ROOT))
    if res.returncode:
        raise AssertionError(f"Node helper failed: {res.stderr}")
    return json.loads(res.stdout)


class PeerLinkCase(unittest.TestCase):
    """Fresh private HOME and ``SKILLS_MANAGER_DATA`` per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.home.mkdir(mode=0o700)
        self._old = {key: os.environ.get(key) for key in ("HOME", "SKILLS_MANAGER_DATA")}
        os.environ["HOME"] = str(self.home)
        data = self.base / "data"
        data.mkdir(mode=0o700)
        os.environ["SKILLS_MANAGER_DATA"] = str(data)
        context.set_active_store(None)
        self.addCleanup(self._restore)

    def _restore(self):
        context.set_active_store(None)
        for key, old in self._old.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def _skill(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(DOCUMENT, encoding="utf-8")
        return directory

    def _symlink(self, target: Path, link: Path) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform
            self.skipTest(f"symlinks are unavailable on this platform: {exc}")

    def _peer_setup(self) -> tuple[Path, Path]:
        target = self._skill(self.home / ".agents" / "skills" / "demo")
        link = self.home / ".claude" / "skills" / "demo"
        self._symlink(target, link)
        return target, link

    @staticmethod
    def _rows(scope_id: str) -> dict[str, dict]:
        return {row["name"]: row for row in scopes.scan_scope(scope_id)}


class PeerLinkReadTests(PeerLinkCase):
    def test_a_link_into_a_peer_root_reads_the_real_document(self):
        target, link = self._peer_setup()

        row = self._rows("claude-code")["demo"]

        self.assertEqual("Demo skill", row["description"])
        self.assertEqual("body", row["body"].strip())
        self.assertTrue(row["link_followed"])
        self.assertTrue(row["read_only"])
        self.assertFalse(row["malformed"])
        self.assertNotIn("invalid", row["instance_states"])
        self.assertFalse(row.get("link_escape", False))
        self.assertEqual(str(link), row["path"])
        self.assertEqual(str(target.resolve()), row["linked_to"])
        self.assertEqual(str((self.home / ".agents" / "skills").resolve()), row["link_target_root"])
        self.assertEqual(self._rows("agents")["demo"]["physical_path"], row["physical_path"])

    def test_the_name_addressed_detail_reads_through_the_link(self):
        target, link = self._peer_setup()

        detail = scopes.get_skill("claude-code", "demo")
        raw = scopes.get_raw("claude-code", "demo")

        self.assertEqual("body", detail["body"].strip())
        self.assertTrue(detail["link_followed"])
        self.assertEqual(str(link), detail["path"])
        self.assertIn("Demo skill", raw)
        self.assertEqual(DOCUMENT.encode("utf-8"), (target / "SKILL.md").read_bytes())

    def test_a_link_outside_every_managed_root_keeps_the_escape_record(self):
        outside = self._skill(self.home / "elsewhere" / "demo")
        self._symlink(outside, self.home / ".claude" / "skills" / "demo")

        row = self._rows("claude-code")["demo"]

        self.assertTrue(row["malformed"])
        self.assertTrue(row["link_escape"])
        self.assertIn("escapes managed root", row["decode_error"])
        self.assertEqual("", row["body"])
        self.assertFalse(row.get("link_followed", False))

    def test_a_chain_that_leaves_the_peer_root_is_not_followed(self):
        outside = self._skill(self.home / "elsewhere" / "demo")
        agents_root = self.home / ".agents" / "skills"
        self._symlink(outside, agents_root / "demo")
        self._symlink(agents_root / "demo", self.home / ".claude" / "skills" / "demo")

        row = self._rows("claude-code")["demo"]

        self.assertTrue(row["malformed"])
        self.assertTrue(row["link_escape"])
        self.assertEqual("", row["body"])
        self.assertFalse(row.get("link_followed", False))
        # A recursive scan walks documents, not directory links, so the peer's
        # own row is absent -- exactly as before this change.
        self.assertNotIn("demo", self._rows("agents"))

    def test_a_dangling_link_keeps_todays_behaviour(self):
        missing = self.home / ".agents" / "skills" / "missing"
        self._symlink(missing, self.home / ".claude" / "skills" / "demo")

        # A dangling link is not a directory, so today's flat scan does not
        # list it at all. Nothing here changes that.
        self.assertNotIn("demo", self._rows("claude-code"))

    def test_list_all_reports_aliases_of_one_physical_document(self):
        self._peer_setup()

        rows = {row["scope"]: row for row in scopes.list_all() if row["name"] == "demo"}

        self.assertEqual({"claude-code", "agents"}, set(rows))
        self.assertEqual(rows["claude-code"]["physical_path"], rows["agents"]["physical_path"])
        self.assertNotEqual(rows["claude-code"]["path"], rows["agents"]["path"])

    def test_the_global_store_scan_is_unchanged(self):
        target = self._skill(self.home / ".agents" / "skills" / "demo")
        store = scopes._global_store()
        store.init_db()
        self._symlink(target, store.skills_dir / "demo")

        rows = {row["name"]: row for row in store._scan_dir(store.skills_dir)}

        self.assertTrue(rows["demo"]["link_escape"])
        self.assertEqual("", rows["demo"]["body"])
        self.assertFalse(rows["demo"].get("link_followed", False))


class PeerLinkWriteRefusalTests(PeerLinkCase):
    def test_every_scoped_write_through_the_link_is_refused(self):
        target, _link = self._peer_setup()
        before = (target / "SKILL.md").read_bytes()
        store = scopes._global_store()
        store.init_db()
        store.create("demo", "global copy")
        snapshot = write_snapshot(store.data_dir, "claude-code", "demo", "previous\n")

        operations = {
            "edit": lambda: scopes.edit_skill("claude-code", "demo", description="changed"),
            "toggle": lambda: scopes.toggle_skill("claude-code", "demo", enable=False),
            "remove": lambda: scopes.remove_skill("claude-code", "demo"),
            "restore_snapshot": lambda: scopes.restore_snapshot("claude-code", "demo", snapshot),
            "sync destination": lambda: scopes.sync_skill("demo", "global", ["claude-code"]),
            "create over the link": lambda: scopes.create_skill("claude-code", "demo", "again"),
        }
        for label, operation in operations.items():
            with self.subTest(operation=label):
                with self.assertRaises(StoreError) as ctx:
                    operation()
                message = str(ctx.exception)
                self.assertIn("is a link into", message)
                self.assertIn(str((self.home / ".agents" / "skills").resolve()), message)
                self.assertIn("change it there", message)
                self.assertEqual(before, (target / "SKILL.md").read_bytes())

        self.assertTrue((self.home / ".claude" / "skills" / "demo").is_symlink())


@unittest.skipUnless(NODE, "node is required")
class PeerLinkInterfaceTests(PeerLinkCase):
    HELPERS = r"""
    const scopes=[
     {id:'claude-code',label:'Claude Code',kind:'agent',exists:true,writable:true,consumer:'claude-code',path:'/h/.claude/skills'},
     {id:'agents',label:'Agents',kind:'agent',exists:true,writable:true,consumer:'shared-agent-skills',path:'/h/.agents/skills'}];
    const rec=(name,scope,over)=>Object.assign({name,scope,scope_label:scope,description:'d',category:'uncategorized',
     body:'b',tokens:100,content_hash:'h1',physical_path:'/p/'+scope+'/'+name,path:'/p/'+scope+'/'+name,
     instance_states:['active'],disabled:0,malformed:false,addressable:true,decode_error:''},over||{});
    """

    def test_physical_alias_is_a_scope_view_but_counts_once_for_reference(self):
        out = _node(self.HELPERS + """
        const followed=rec('a','claude-code',{link_followed:true,read_only:true,linked_to:'/h/.agents/skills/a',
          link_target_root:'/h/.agents/skills',physical_path:'/p/agents/a',path:'/h/.claude/skills/a'});
        const real=rec('a','agents',{physical_path:'/p/agents/a',path:'/p/agents/a'});
        const M=ctx.window.SkillsV2Model;
        const skill=M.build([followed,real],scopes).skills[0];
        const reversedModel=M.build([real,followed],scopes),reversed=reversedModel.skills[0];
        const alias=skill.copies.find(c=>c.scope==='claude-code');
        const owner=skill.copies.find(c=>c.scope==='agents');
        const visibleContext={m:reversedModel,query:'',filter:'all',agentFilter:'claude-code',tagFilter:'',catalog:{tags:{}}};
        const visible=ctx.options.computed.visible.call(visibleContext);
        const defaultRef=ctx.options.computed.refCopy.call({skill,readCopyName:'',readCopyScope:'',readCopyPath:''});
        const exactAlias=ctx.options.computed.refCopy.call({skill,readCopyName:'a',readCopyScope:'claude-code',readCopyPath:'/p/agents/a'});
        const refused=M.build([rec('r','claude-code',{malformed:true,instance_states:['invalid'],
          decode_error:'skill path escapes managed root'})],scopes).skills[0];
        return {scopes:skill.copies.map(c=>c.scope),aliasState:alias.state,aliasReadOnly:alias.readOnly,
          ownerReadOnly:owner.readOnly,aliasPath:alias.path,ownerPath:owner.path,
          reverseScopes:reversed.copies.map(c=>c.scope),claudeSkills:M.build([followed,real],scopes).info('claude-code').mine.length,
          visible:visible.map(s=>s.name),referenceScopes:skill.ref.holders.map(c=>c.scope),
          referenceCount:skill.ref.groups[0].length,status:skill.status.label,
          defaultRef:defaultRef.scope,exactAlias:exactAlias.scope,
          ownerCanEdit:ctx.options.computed.canEdit.call({skill,refCopy:owner,editable:true,docWhy:null,bodyFetchable:()=>true}),
          aliasCanEdit:ctx.options.computed.canEdit.call({skill,refCopy:alias,editable:true,docWhy:null,bodyFetchable:()=>true}),
          refused:refused.status.label};""")

        self.assertEqual(["claude-code", "agents"], out["scopes"])
        self.assertEqual(["claude-code", "agents"], out["reverseScopes"])
        self.assertEqual("on", out["aliasState"])
        self.assertTrue(out["aliasReadOnly"])
        self.assertFalse(out["ownerReadOnly"])
        self.assertEqual(out["ownerPath"], out["aliasPath"])
        self.assertEqual(1, out["claudeSkills"])
        self.assertEqual(["a"], out["visible"])
        self.assertEqual(["agents"], out["referenceScopes"])
        self.assertEqual(1, out["referenceCount"])
        self.assertEqual("agents", out["defaultRef"])
        self.assertEqual("claude-code", out["exactAlias"])
        self.assertEqual("Working", out["status"])
        self.assertTrue(out["ownerCanEdit"])
        self.assertFalse(out["aliasCanEdit"])
        self.assertEqual("Linked elsewhere", out["refused"])

    def test_a_followed_link_alone_stays_readable_and_read_only(self):
        out = _node(self.HELPERS + """
        const followed=rec('a','claude-code',{link_followed:true,read_only:true,linked_to:'/h/.agents/skills/a',
          link_target_root:'/h/.agents/skills',physical_path:'/p/agents/a',path:'/h/.claude/skills/a'});
        const M=ctx.window.SkillsV2Model;
        const copy=M.build([followed],scopes).skills[0].copies[0];
        const context={skill:{name:'a',copies:[copy]},refCopy:copy,editable:true,docWhy:null,
          bodyFetchable:()=>true,readOnlyWhy:ctx.options.methods.readOnlyWhy};
        return {state:copy.state,readOnly:copy.readOnly,canEdit:ctx.options.computed.canEdit.call(context),
          why:ctx.options.computed.editWhy.call(context)};""")

        self.assertEqual("on", out["state"])
        self.assertTrue(out["readOnly"])
        self.assertFalse(out["canEdit"])
        self.assertIn("This is a link into /h/.agents/skills", out["why"])


if __name__ == "__main__":
    unittest.main()
