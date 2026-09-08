"""REST API tests: serve the real WebAppServer on an ephemeral port."""

import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

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

    def test_encoded_skill_traversal_is_rejected_before_delete(self):
        victim = Path(self._tmp.name).parent / "webapp-victim"
        victim.mkdir()
        try:
            encoded_name = quote("../../webapp-victim", safe="")
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/skills/{encoded_name}?purge=1",
                method="DELETE",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request)
            self.assertEqual(ctx.exception.code, 400)
            self.assertTrue(victim.is_dir())
        finally:
            victim.rmdir()

    def test_encoded_skill_traversal_is_rejected_before_raw_read(self):
        victim = Path(self._tmp.name).parent / "webapp-raw-victim"
        victim.mkdir()
        (victim / "SKILL.md").write_text(
            "---\nname: leaked\ndescription: must not leak\n---\nsecret\n",
            encoding="utf-8",
        )
        try:
            encoded_name = quote("../../webapp-raw-victim", safe="")
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/skills/{encoded_name}/raw",
                method="GET",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request)
            self.assertEqual(ctx.exception.code, 400)
            self.assertNotIn("secret", ctx.exception.read().decode("utf-8"))
        finally:
            (victim / "SKILL.md").unlink()
            victim.rmdir()


if __name__ == "__main__":
    unittest.main()
