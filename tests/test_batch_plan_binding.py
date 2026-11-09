"""A batch plan is bound to the content and state it previewed (P3 decision).

Before 2026-11-07 the plan id hashed only ``(name, scope, physical_path)``, so
a preview stayed valid after the document it described was rewritten, toggled
or -- for sync -- after the destination copy it would overwrite changed.  The
user approved one set of bytes and the batch acted on another.
"""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from skillsmgr import context
from skillsmgr import batch, scopes, webapp
from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


def _private(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


class BatchPlanBindingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = _private(Path(self._tmp.name).resolve())
        self.home = _private(base / "home")
        self.agents = _private(self.home / ".agents/skills")
        saved = {key: os.environ.get(key) for key in ("SKILLS_MANAGER_DATA", "HOME")}
        os.environ["SKILLS_MANAGER_DATA"] = str(_private(base / "data"))
        os.environ["HOME"] = str(self.home)

        def restore():
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.addCleanup(restore)
        self.store = Store()
        self.store.init_db()
        self.store.create("demo", "Demo skill", body="# demo\n\noriginal\n")
        self.server = WebAppServer(self.store, port=0)
        self.port = self.server.httpd.server_port
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()

        def stop():
            self.server.shutdown()
            thread.join(timeout=5)
            self.server.httpd.server_close()
            context.set_active_store(None)

        self.addCleanup(stop)

    def request(self, method, path, body=None):
        raw = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=raw, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def target(self, scope="global"):
        _, rows = self.request("GET", "/api/skills?scope=all&body=0")
        row = next(r for r in rows if r["name"] == "demo" and r["scope"] == scope)
        return {"name": row["name"], "scope": row["scope"], "physical_path": row["physical_path"]}

    def preview(self, operation, target, **extra):
        status, plan = self.request("POST", "/api/batch/preview",
                                    {"operation": operation, "targets": [target], **extra})
        self.assertEqual(status, 200, plan)
        return plan

    def execute(self, operation, target, plan, **extra):
        return self.request("POST", "/api/batch/execute", {
            "operation": operation, "targets": [target], "plan_id": plan["plan_id"], **extra,
        })

    def document(self) -> Path:
        return Path(self.store.data_dir) / "skills/demo/SKILL.md"

    def test_unchanged_target_still_executes(self):
        target = self.target()
        plan = self.preview("disable", target)
        status, result = self.execute("disable", target, plan)
        self.assertEqual(status, 200, result)
        self.assertTrue(result["ok"])

    def test_preview_reports_the_bound_content_hash(self):
        plan = self.preview("disable", self.target())
        self.assertRegex(plan["targets"][0]["content_hash"], r"^[0-9a-f]{64}$")

    def test_rewritten_document_makes_the_plan_stale(self):
        target = self.target()
        plan = self.preview("remove", target)
        self.store.edit("demo", body="# demo\n\nrewritten after review\n")
        status, result = self.execute("remove", target, plan)
        self.assertEqual(status, 400)
        self.assertIn("stale", result["error"])
        self.assertTrue(self.document().exists(), "the stale plan must not trash the skill")

    def test_toggled_state_makes_the_plan_stale(self):
        target = self.target()
        plan = self.preview("remove", target)
        self.store.disable("demo")
        status, result = self.execute("remove", target, plan)
        self.assertEqual(status, 400)
        self.assertIn("stale", result["error"])

    def test_changed_sync_destination_makes_a_forced_plan_stale(self):
        scopes.sync_skill("demo", "global", ["agents"], force=False)
        destination = self.agents / "demo/SKILL.md"
        self.assertTrue(destination.exists())
        target = self.target()
        plan = self.preview("sync", target, to_scopes=["agents"], force=True)
        edited = destination.read_text().replace("original", "local work")
        destination.write_text(edited)
        status, result = self.execute("sync", target, plan, to_scopes=["agents"], force=True)
        self.assertEqual(status, 400)
        self.assertIn("stale", result["error"])
        self.assertEqual(destination.read_text(), edited, "the destination edit must survive")

    def test_source_companion_change_makes_sync_stale(self):
        reference = self.document().parent / "reference.txt"
        reference.write_text("reviewed")
        target = self.target()
        plan = self.preview("sync", target, to_scopes=["agents"], force=True)
        reference.write_text("changed")
        status, result = self.execute("sync", target, plan, to_scopes=["agents"], force=True)
        self.assertEqual(status, 400, result)
        self.assertIn("stale", result["error"])
        self.assertFalse((self.agents / "demo").exists())

    def test_destination_companion_change_makes_sync_stale(self):
        reference = self.document().parent / "reference.txt"
        reference.write_text("reviewed")
        scopes.sync_skill("demo", "global", ["agents"], force=False)
        target = self.target()
        plan = self.preview("sync", target, to_scopes=["agents"], force=True)
        destination = self.agents / "demo/reference.txt"
        destination.write_text("local work")
        status, result = self.execute("sync", target, plan, to_scopes=["agents"], force=True)
        self.assertEqual(status, 400, result)
        self.assertIn("stale", result["error"])
        self.assertEqual("local work", destination.read_text())

    def test_batch_rejects_symlink_in_skill_tree(self):
        (self.document().parent / "reference").symlink_to(self.home, target_is_directory=True)
        status, result = self.request("POST", "/api/batch/preview", {
            "operation": "remove", "targets": [self.target()],
        })
        self.assertEqual(status, 400, result)
        self.assertIn("symlink", result["error"])

    def test_linked_target_never_hashes_outside_tree(self):
        outside = self.home / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_text("secret")
        (self.agents / "linked").symlink_to(outside, target_is_directory=True)
        row = {"name": "linked", "scope": "agents", "path": str(self.agents / "linked"),
               "physical_path": str(outside), "instance_state": "link_escape"}
        with mock.patch.object(batch, "_batch_tree_hash") as hashed:
            with self.assertRaises(webapp.StoreError):
                batch.resolve_target(row, [row], set())
            hashed.assert_not_called()

    def test_linked_destination_never_hashes_outside_tree(self):
        outside = self.home / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_text("secret")
        (self.agents / "demo").symlink_to(outside, target_is_directory=True)
        row = {"name": "demo", "scope": "agents", "path": str(self.agents / "demo"),
               "physical_path": str(outside), "read_only": True}
        with mock.patch.object(batch, "_batch_tree_hash") as hashed:
            with self.assertRaises(webapp.StoreError):
                batch._sync_destinations("demo", {"to_scopes": ["agents"]}, [row])
            hashed.assert_not_called()

    def test_malformed_skill_can_be_trashed(self):
        self.document().write_text("---\nname: [broken\n---\nbody\n")
        target = self.target()
        plan = self.preview("remove", target)
        status, result = self.execute("remove", target, plan)
        self.assertEqual(200, status, result)
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.document().exists())

    def test_scope_root_symlink_allows_real_child(self):
        actual = self.home / "real-agent-skills"
        self.agents.rename(actual)
        self.agents.symlink_to(actual, target_is_directory=True)
        demo = actual / "agentdemo"
        demo.mkdir()
        (demo / "SKILL.md").write_text("---\nname: agentdemo\ndescription: Demo\n---\nbody\n")
        status, rows = self.request("GET", "/api/skills?scope=all&body=0")
        row = next(r for r in rows if r["name"] == "agentdemo" and r["scope"] == "agents")
        target = {"name": row["name"], "scope": row["scope"], "physical_path": row["physical_path"]}
        plan = self.preview("remove", target)
        status, result = self.execute("remove", target, plan)
        self.assertEqual(200, status, result)
        self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
