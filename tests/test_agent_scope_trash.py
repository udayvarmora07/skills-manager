"""Agent-scope trash: listing, restoring, and the REST routes around them.

Written first, against the pre-implementation tree: every route-level test here
is intended to fail before ``scopes.scope_trash_list`` / ``scopes.restore_trashed``
and the scope-aware ``/api/trash`` routes exist.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from skillsmgr import scopes
from skillsmgr.store import Store, StoreError
from skillsmgr.webapp import WebAppServer

DOCUMENT = "---\nname: demo\ndescription: Demo skill\n---\nbody\n"

OLD_STAMP = "2026-11-07_10-00-00Z"
NEW_STAMP = "2026-11-07_11-00-00Z"


class AgentScopeTrashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old_data = os.environ.get("SKILLS_MANAGER_DATA")
        cls.old_home = os.environ.get("HOME")
        cls.home = Path(cls.tmp.name) / "home"
        cls.home.mkdir(mode=0o700)
        os.chmod(cls.home, 0o700)
        os.environ["HOME"] = str(cls.home)
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(cls.tmp.name) / "data")
        cls.store = Store()
        cls.store.init_db()
        cls.server = WebAppServer(cls.store, port=0)
        cls.port = cls.server.httpd.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.httpd.server_close()
        scopes.set_global_store(None)
        cls.tmp.cleanup()
        if cls.old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = cls.old_data
        if cls.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = cls.old_home

    def setUp(self):
        agent_root = self.home / ".agents"
        if agent_root.exists():
            shutil.rmtree(agent_root)
        self.skills_dir = agent_root / "skills"
        self.skills_dir.mkdir(parents=True)
        self.trash = agent_root / "trash"

    # -- helpers ---------------------------------------------------------

    def request(self, method, path, body=None, content_type="application/json"):
        raw = None if body is None else json.dumps(body).encode("utf-8")
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=raw,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = response.read()
                return response.status, json.loads(payload) if payload else None
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            return exc.code, json.loads(payload) if payload else None

    def write_skill(self, text=DOCUMENT, name="demo"):
        directory = self.skills_dir / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(text, encoding="utf-8")
        return directory

    def write_trash_entry(self, stamp, text, name="demo", scope_id="agents"):
        directory = self.trash / f"{scope_id}__{name}-{stamp}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(text, encoding="utf-8")
        return directory

    def remove_skill(self, name="demo", scope_id="agents"):
        status, payload = self.request(
            "DELETE", f"/api/skills/{name}?scope={scope_id}&purge=0"
        )
        self.assertEqual(status, 200, payload)
        return payload

    # -- listing ---------------------------------------------------------

    def test_missing_trash_dir_lists_nothing(self):
        self.assertEqual(scopes.scope_trash_list("agents"), [])
        self.assertFalse(self.trash.exists())

    def test_unknown_and_global_scopes_are_refused(self):
        with self.assertRaises(StoreError):
            scopes.scope_trash_list("no-such-scope")
        with self.assertRaises(StoreError):
            scopes.scope_trash_list("global")

    def test_remove_then_list_then_restore_round_trips_the_bytes(self):
        original = "---\nname: demo\ndescription: Demo skill\n---\nexact bytes\n"
        self.write_skill(original)

        removed = self.remove_skill()
        self.assertTrue(removed["trash_path"])
        self.assertFalse((self.skills_dir / "demo").exists())

        status, rows = self.request("GET", "/api/trash?scope=agents")
        self.assertEqual(status, 200, rows)
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        self.assertEqual(row["name"], "demo")
        self.assertEqual(row["scope"], "agents")
        self.assertEqual(row["trash_path"], removed["trash_path"])
        self.assertTrue(row["trashed_at"].startswith("2026-11-07"))
        self.assertGreater(row["size_bytes"], 0)

        status, payload = self.request(
            "POST",
            "/api/trash/demo?scope=agents",
            {"trash_path": removed["trash_path"]},
        )
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["action"], "restored")
        self.assertEqual((self.skills_dir / "demo" / "SKILL.md").read_text("utf-8"), original)
        self.assertFalse(Path(removed["trash_path"]).exists())

        status, rows = self.request("GET", "/api/trash?scope=agents")
        self.assertEqual(status, 200)
        self.assertEqual(rows, [])

    def test_unparseable_and_invalid_names_are_skipped(self):
        self.trash.mkdir(parents=True)
        self.write_trash_entry(OLD_STAMP, "valid\n")
        (self.trash / "agents__Bad-2026-11-07_12-00-00Z").mkdir()
        (self.trash / "agents__demo-not-a-timestamp").mkdir()
        (self.trash / "unrelated").mkdir()
        rows = scopes.scope_trash_list("agents")
        self.assertEqual([row["name"] for row in rows], ["demo"])

    def test_symlinked_trash_entry_is_never_listed_or_restored(self):
        target = Path(self.tmp.name) / "outside"
        target.mkdir(exist_ok=True)
        (target / "SKILL.md").write_text("outside\n", encoding="utf-8")
        self.trash.mkdir(parents=True)
        link = self.trash / f"agents__demo-{OLD_STAMP}"
        link.symlink_to(target, target_is_directory=True)

        self.assertEqual(scopes.scope_trash_list("agents"), [])

        status, payload = self.request("POST", "/api/trash/demo?scope=agents")
        self.assertEqual(status, 404, payload)
        self.assertFalse((self.skills_dir / "demo").exists())
        self.assertTrue(link.is_symlink())
        self.assertEqual((target / "SKILL.md").read_text("utf-8"), "outside\n")

    # -- restore selection ----------------------------------------------

    def test_restore_picks_the_newest_and_an_explicit_path_picks_the_older(self):
        self.trash.mkdir(parents=True)
        older = self.write_trash_entry(OLD_STAMP, "older\n")
        newer = self.write_trash_entry(NEW_STAMP, "newer\n")

        rows = scopes.scope_trash_list("agents")
        self.assertEqual([row["trash_path"] for row in rows], [str(newer), str(older)])

        status, payload = self.request("POST", "/api/trash/demo?scope=agents")
        self.assertEqual(status, 200, payload)
        self.assertEqual(
            (self.skills_dir / "demo" / "SKILL.md").read_text("utf-8"), "newer\n"
        )
        self.assertFalse(newer.exists())
        self.assertTrue(older.exists())

        # Free the destination, then restore the older copy by exact path.
        shutil.rmtree(self.skills_dir / "demo")
        status, payload = self.request(
            "POST", "/api/trash/demo?scope=agents", {"trash_path": str(older)}
        )
        self.assertEqual(status, 200, payload)
        self.assertEqual(
            (self.skills_dir / "demo" / "SKILL.md").read_text("utf-8"), "older\n"
        )

    def test_trash_path_outside_the_listing_is_refused_and_nothing_moves(self):
        self.write_skill()
        removed = self.remove_skill()
        listed = Path(removed["trash_path"])
        self.trash.mkdir(parents=True, exist_ok=True)
        other_scope = self.write_trash_entry(OLD_STAMP, "codex copy\n", scope_id="codex")
        outside = Path(self.tmp.name) / "elsewhere"
        outside.mkdir(exist_ok=True)

        for candidate in (
            str(outside),
            str(self.trash / ".." / "skills" / "demo"),
            str(other_scope),
        ):
            status, payload = self.request(
                "POST", "/api/trash/demo?scope=agents", {"trash_path": candidate}
            )
            self.assertEqual(status, 400, (candidate, payload))

        self.assertFalse((self.skills_dir / "demo").exists())
        self.assertTrue(listed.is_dir())
        self.assertTrue(other_scope.is_dir())

    def test_existing_destination_is_refused_and_both_copies_survive(self):
        self.write_skill()
        removed = self.remove_skill()
        recreated = self.write_skill("---\nname: demo\ndescription: Newer\n---\nnew work\n")

        status, payload = self.request("POST", "/api/trash/demo?scope=agents")
        self.assertEqual(status, 400, payload)
        self.assertEqual(
            (recreated / "SKILL.md").read_text("utf-8"),
            "---\nname: demo\ndescription: Newer\n---\nnew work\n",
        )
        self.assertTrue(Path(removed["trash_path"]).is_dir())

    def test_invalid_names_are_refused_before_any_filesystem_access(self):
        self.write_skill()
        self.remove_skill()
        before = sorted(path.name for path in self.trash.iterdir())

        for bad in ("Bad", "..%2Fx"):
            status, payload = self.request("POST", f"/api/trash/{bad}?scope=agents")
            self.assertEqual(status, 400, (bad, payload))

        self.assertEqual(before, sorted(path.name for path in self.trash.iterdir()))
        self.assertFalse((self.skills_dir / "demo").exists())

    # -- global behaviour unchanged --------------------------------------

    def test_global_trash_routes_are_unchanged(self):
        self.store.create("global-demo", "Global demo skill")
        status, payload = self.request(
            "DELETE", "/api/skills/global-demo?scope=global&purge=0"
        )
        self.assertEqual(status, 200, payload)

        self.trash.mkdir(parents=True, exist_ok=True)
        self.write_trash_entry(NEW_STAMP, "agent copy\n")

        status, rows = self.request("GET", "/api/trash")
        self.assertEqual(status, 200, rows)
        names = [row["name"] for row in rows]
        self.assertIn("global-demo", names)
        self.assertNotIn("demo", names)

        status, payload = self.request("POST", "/api/trash/global-demo")
        self.assertEqual(status, 200, payload)
        self.assertTrue((self.store.skills_dir / "global-demo").is_dir())

    def test_scoped_restore_requires_json_content_type(self):
        self.write_skill()
        self.remove_skill()
        status, payload = self.request(
            "POST", "/api/trash/demo?scope=agents", content_type=None
        )
        self.assertEqual(status, 415, payload)

    # -- source contract --------------------------------------------------

    def test_old_agent_trash_copy_is_gone_from_v2(self):
        root = Path(__file__).resolve().parent.parent / "skillsmgr" / "webui" / "v2"
        offenders = [
            path.name
            for path in sorted(root.iterdir())
            if path.suffix in {".js", ".html"}
            and "cannot be restored in-app" in path.read_text("utf-8")
        ]
        self.assertEqual(offenders, [])
        self.assertIn("Agent trash", (root / "index.html").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
