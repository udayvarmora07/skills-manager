"""Malformed requests fail cleanly before reaching filesystem mutations."""

from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


class RequestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            "HOME": str(self.root / "home"),
            "SKILLS_MANAGER_DATA": str(self.root / "data"),
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.store = Store(self.root / "data")
        self.store.init_db()
        self.store.create("demo", "Request regression fixture")
        self.server = WebAppServer(self.store, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.httpd.server_close)
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=3)
        try:
            conn.request(method, path, body=body, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()


class RequestFailures(RequestCase):
    def test_deep_json_is_a_clean_400_on_post_and_patch(self):
        before = self.store.get("demo")["body"]
        raw = b'{"metadata_extra":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'
        for method, path in (("POST", "/api/skills"), ("PATCH", "/api/skills/demo"),
                             ("POST", "/api/source-updates/reviews/from-snapshot")):
            with self.subTest(method=method, path=path):
                status, payload = self.request(method, path, raw)
                self.assertEqual(status, 400)
                self.assertEqual(payload["code"], "bad_request")
                self.assertNotIn("RecursionError", payload["error"])
        self.assertEqual(self.store.get("demo")["body"], before)

    def test_unresolvable_project_is_a_clean_400(self):
        project = "~skillsmgr-no-such-user-6a2c9/x"
        for path in ("/api/workspaces?project=", "/api/doctor?explain=claude-code&project="):
            with self.subTest(path=path):
                status, payload = self.request("GET", path + project)
                self.assertEqual(status, 400)
                self.assertEqual(payload["code"], "bad_request")
                self.assertNotIn(project, payload["error"])



if __name__ == "__main__":
    unittest.main()
