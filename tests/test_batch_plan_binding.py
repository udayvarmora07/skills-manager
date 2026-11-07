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

from skillsmgr import scopes
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
            scopes.set_global_store(None)

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


if __name__ == "__main__":
    unittest.main()
