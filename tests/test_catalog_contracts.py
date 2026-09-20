"""Contracts for sidecar organization metadata, batches, and adapters."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.request

from skillsmgr.adapters import catalog as adapter_catalog, project_observation
from skillsmgr.catalog import (
    catalog_path,
    load_catalog,
    profile_preview,
    save_profile,
    update_tags,
)
from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


class CatalogContractTests(unittest.TestCase):
    def test_sidecar_tags_profiles_and_preview_are_filesystem_owned(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            store.init_db()
            store.create("demo", "Demo skill")
            update_tags(tmp, ["demo"], "add", ["release"])
            save_profile(tmp, "ship", {"description": "Ship", "skills": ["demo", "missing"], "targets": ["global"]})
            data = load_catalog(tmp)
            self.assertEqual(data["tags"]["demo"], ["release"])
            preview = profile_preview(data["profiles"]["ship"], [dict(row, scope="global") for row in store.list()])
            self.assertEqual([member["state"] for member in preview["members"]], ["observed", "missing"])
            self.assertTrue(catalog_path(tmp).is_file())
            store.db_rebuild()
            self.assertEqual(load_catalog(tmp)["profiles"]["ship"]["skills"], ["demo", "missing"])

    def test_adapter_catalog_surfaces_evidence_and_unknown_precedence(self):
        records = adapter_catalog()
        by_id = {record["id"]: record for record in records}
        self.assertIn("claude-code", by_id)
        self.assertEqual(by_id["claude-code"]["status"], "verified")
        self.assertEqual(by_id["cursor"]["status"], "unknown-precedence")
        self.assertTrue(by_id["claude-code"]["precedence"]["evidence"].startswith("https://"))
        self.assertIn("last_verified", by_id["claude-code"])

    def test_project_observation_redacts_outside_allowed_roots(self):
        with tempfile.TemporaryDirectory() as managed, tempfile.TemporaryDirectory() as outside:
            result = project_observation(outside, [os.path.realpath(managed)])
            self.assertEqual(result["status"], "outside-managed-roots")
            self.assertTrue(result["paths_redacted"])


class CatalogWebContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old_data = os.environ.get("SKILLS_MANAGER_DATA")
        cls.old_home = os.environ.get("HOME")
        os.environ["SKILLS_MANAGER_DATA"] = os.path.join(cls.tmp.name, "data")
        os.environ["HOME"] = os.path.join(cls.tmp.name, "home")
        cls.store = Store()
        cls.store.init_db()
        cls.store.create("demo", "Demo skill")
        cls.server = WebAppServer(cls.store, port=0)
        cls.port = cls.server.httpd.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        from skillsmgr import scopes

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

    @classmethod
    def request(cls, method, path, body=None):
        raw = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            f"http://127.0.0.1:{cls.port}{path}",
            data=raw,
            method=method,
            headers={"Content-Type": "application/json"} if raw else {},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())

    def test_tags_profiles_batch_and_workspace_routes(self):
        status, rows = self.request("GET", "/api/skills?scope=all")
        self.assertEqual(status, 200)
        target = next(row for row in rows if row["name"] == "demo" and row["scope"] == "global")
        status, catalog = self.request("POST", "/api/catalog/tags", {"operation": "add", "names": ["demo"], "tags": ["release"]})
        self.assertEqual(status, 200)
        self.assertEqual(catalog["tags"]["demo"], ["release"])
        status, catalog = self.request("POST", "/api/catalog/profiles", {"name": "ship", "skills": ["demo"], "targets": ["global"]})
        self.assertEqual(status, 200)
        status, preview = self.request("POST", "/api/batch/preview", {"operation": "disable", "targets": [target]})
        self.assertEqual(status, 200)
        self.assertEqual(preview["target_count"], 1)
        status, result = self.request("POST", "/api/batch/execute", {"operation": "disable", "plan_id": preview["plan_id"], "targets": [target]})
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])
        status, profile = self.request("GET", "/api/catalog/profiles/ship/preview")
        self.assertEqual(status, 200)
        self.assertEqual(profile["summary"]["disabled"], 1)
        status, workspaces = self.request("GET", "/api/workspaces")
        self.assertEqual(status, 200)
        self.assertTrue(any(item["id"] == "claude-code" for item in workspaces["adapters"]))
