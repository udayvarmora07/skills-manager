"""REST API tests: serve the real WebAppServer on an ephemeral port."""

import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


class WebAppTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        os.environ["SKILLS_MANAGER_DATA"] = cls._tmp.name
        store = Store()
        store.init_db()
        store.create("demo", "Demo skill", body="Hello.")
        cls.server = WebAppServer(store, port=0)
        cls.port = cls.server.httpd.server_port
        import threading

        cls._thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls._thread.join(timeout=5)
        cls.server.httpd.server_close()
        cls._tmp.cleanup()

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url) as resp:
            return resp.status, resp.read()

    def test_list_and_detail(self):
        status, body = self._get("/api/skills")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)), 1)
        status, body = self._get("/api/skills/demo")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["name"], "demo")

    def test_long_query_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/api/search?q=" + "x" * 300)
        self.assertEqual(ctx.exception.code, 400)

    def test_static_traversal_blocked(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/static/../webapp.py")
        self.assertIn(ctx.exception.code, (400, 404))


if __name__ == "__main__":
    unittest.main()
