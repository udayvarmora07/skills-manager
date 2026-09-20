"""CLI/REST integration contracts for the registry operations."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.request import Request, urlopen

from skillsmgr import cli, registry
from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


def _snapshot():
    files = [{
        "path": "SKILL.md",
        "contents": "---\nname: demo\ndescription: Use demo when testing.\n---\n# Demo\n",
    }]
    return {
        "id": "owner/repo/demo",
        "source": "owner/repo",
        "slug": "demo",
        "page_url": "https://skills.sh/owner/repo/demo",
        "api_url": "https://skills.sh/api/download/owner/repo/demo",
        "files": files,
        "hash": registry.registry_snapshot_hash(files),
        "snapshot_hash": registry.snapshot_hash(files),
        "registry_hash": registry.registry_snapshot_hash(files),
        "hash_verified": True,
        "_registry": {"cache_state": "miss", "stale": False, "url": "https://skills.sh/api/download/owner/repo/demo"},
    }


class RegistryCliIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["SKILLS_MANAGER_DATA"] = self.tmp.name

    def tearDown(self):
        if self.old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = self.old_data

    def invoke(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", self.tmp.name, *argv])
        return code, out.getvalue(), err.getvalue()

    def test_browse_and_search_use_existing_install_surface(self):
        fake = mock.Mock()
        fake.browse.return_value = {"data": [{"id": "owner/repo/demo", "installs": 4}], "_registry": {"cache_state": "miss"}}
        fake.search.return_value = {"data": [{"id": "owner/repo/demo"}], "_registry": {"cache_state": "fresh"}}
        with mock.patch("skillsmgr.cli_handlers._registry_client", return_value=fake):
            code, out, err = self.invoke(["install", "--browse", "--json"])
            self.assertEqual(code, cli.EXIT_OK)
            self.assertEqual(json.loads(out)["data"][0]["id"], "owner/repo/demo")
            code, out, err = self.invoke(["install", "--search", "demo", "--json"])
            self.assertEqual(code, cli.EXIT_OK)
            self.assertEqual(json.loads(out)["data"][0]["id"], "owner/repo/demo")
        fake.browse.assert_called_once()
        fake.search.assert_called_once_with("demo", allow_stale=False)
        self.assertEqual(err, "")

    def test_fetch_installs_sidecar_and_exposes_it_in_store_records(self):
        fake = mock.Mock()
        fake.fetch.return_value = _snapshot()
        with mock.patch("skillsmgr.cli_handlers._registry_client", return_value=fake):
            code, out, err = self.invoke(["install", "--fetch", "owner/repo/demo", "--json"])
            review = json.loads(out)
            self.assertEqual(code, cli.EXIT_OK)
            self.assertEqual(Store().list(), [])
            code, out, err = self.invoke([
                "install", "--fetch", "--review", review["review_id"], "--trust-confirmed", "--json"
            ])
        self.assertEqual(code, cli.EXIT_OK)
        result = json.loads(out)
        self.assertEqual(result["name"], "demo")
        self.assertEqual(err, "")
        self.assertTrue(result["inspection"]["validation"]["valid"])
        self.assertTrue(result["inspection"]["reviewed_before_install"])
        store = Store()
        record = store.get("demo")
        self.assertEqual(record["registry_provenance"]["id"], "owner/repo/demo")
        sidecar = Path(record["path"]) / registry.PROVENANCE_FILENAME
        self.assertTrue(sidecar.is_file())
        self.assertNotIn("token", sidecar.read_text(encoding="utf-8").lower())
        fake.fetch.assert_called_once()

    def test_fetch_requires_global_scope_and_rejects_ignored_flags(self):
        code, out, err = self.invoke(["install", "--fetch", "owner/repo/demo", "--trust-confirmed", "--scope", "agents"])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("global manager store", err)
        code, out, err = self.invoke(["install", "--browse", "--dry-run"])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("cannot be combined", err)

    def test_fetch_normalizes_noncanonical_remote_display_name(self):
        snapshot = _snapshot()
        snapshot["files"] = [{
            "path": "SKILL.md",
            "contents": snapshot["files"][0]["contents"].replace("name: demo", "name: Demo Skill"),
        }]
        fake = mock.Mock()
        fake.fetch.return_value = snapshot
        with mock.patch("skillsmgr.cli_handlers._registry_client", return_value=fake):
            code, out, err = self.invoke([
                "install", "--fetch", "owner/repo/demo", "--json"
            ])
            review = json.loads(out)
            code, out, err = self.invoke([
                "install", "--fetch", "--review", review["review_id"], "--trust-confirmed", "--json"
            ])
        self.assertEqual(code, cli.EXIT_OK)
        result = json.loads(out)
        self.assertIn("normalized to slug", result["registry"]["normalization"])
        record = Store().get("demo")
        self.assertIn("name: demo", (Path(record["path"]) / "SKILL.md").read_text(encoding="utf-8"))
        self.assertTrue(record["registry_provenance"]["normalization"])

    def test_fetch_rejects_invalid_snapshot_before_store_add(self):
        snapshot = _snapshot()
        snapshot["files"] = [{
            "path": "SKILL.md",
            "contents": "---\nname: demo\n---\nunsafe\n",
        }]
        snapshot["hash"] = registry.registry_snapshot_hash(snapshot["files"])
        snapshot["registry_hash"] = snapshot["hash"]
        snapshot["snapshot_hash"] = registry.snapshot_hash(snapshot["files"])
        fake = mock.Mock()
        fake.fetch.return_value = snapshot
        with mock.patch("skillsmgr.cli_handlers._registry_client", return_value=fake):
            code, out, err = self.invoke([
                "install", "--fetch", "owner/repo/demo", "--json"
            ])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("failed validation before install", err)
        self.assertEqual(Store().list(), [])


class RegistryRestIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(data_dir=self.tmp.name)
        self.store.init_db()
        self.server = WebAppServer(self.store, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.httpd.server_close()

    def post(self, payload):
        request = Request(
            self.server.url + "api/install",
            data=json.dumps(payload).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request) as response:
            return json.loads(response.read())

    def test_browse_and_search_payloads(self):
        fake = mock.Mock()
        fake.browse.return_value = {"data": [{"id": "owner/repo/demo"}], "_registry": {"cache_state": "miss"}}
        fake.search.return_value = {"data": [{"id": "owner/repo/demo"}], "_registry": {"cache_state": "miss"}}
        with mock.patch("skillsmgr.registry.RegistryClient", return_value=fake):
            self.assertEqual(self.post({"browse": True})["data"][0]["id"], "owner/repo/demo")
            self.assertEqual(self.post({"search": "demo"})["data"][0]["id"], "owner/repo/demo")
        fake.browse.assert_called_once_with(page=0, per_page=25, view="all-time", allow_stale=False)
        fake.search.assert_called_once_with("demo", limit=50, owner=None, allow_stale=False)

    def test_fetch_payload_installs_and_returns_provenance(self):
        fake = mock.Mock()
        fake.fetch.return_value = _snapshot()
        with mock.patch("skillsmgr.cli_handlers._registry_client", return_value=fake):
            result = self.post({"fetch": True, "source": "owner/repo/demo"})
            self.assertIn("review_id", result)
            self.assertEqual(self.store.list(), [])
            result = self.post({"fetch": True, "review_id": result["review_id"], "trust_confirmed": True})
        self.assertEqual(result["name"], "demo")
        self.assertEqual(self.store.get("demo")["registry_provenance"]["local_snapshot_hash"], _snapshot()["snapshot_hash"])


if __name__ == "__main__":
    unittest.main()
