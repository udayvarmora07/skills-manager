"""REST API tests: serve the real WebAppServer on an ephemeral port."""

import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from skillsmgr.store import Store, StoreError
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

    def _request(self, method, path, body=None, headers=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = None
        request_headers = dict(headers or {})
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers=request_headers,
            method=method,
        )
        with urllib.request.urlopen(request) as resp:
            return resp.status, resp.read(), resp.headers

    def _get(self, path):
        status, body, _ = self._request("GET", path)
        return status, body

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

    def test_cross_origin_purge_is_rejected_before_mutation(self):
        self.server.httpd.store.create("csrf-demo", "CSRF demo")
        self.server.httpd.store.remove("csrf-demo")
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/trash/purge",
            headers={
                "Origin": "http://attacker.example",
                "Sec-Fetch-Site": "cross-site",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code, 403)
        self.assertTrue(any(row["name"] == "csrf-demo" for row in self.server.httpd.store.trash_list()))
        self.server.httpd.store.purge_trash()

    def test_same_origin_purge_remains_allowed(self):
        self.server.httpd.store.create("same-origin-demo", "Same origin demo")
        self.server.httpd.store.remove("same-origin-demo")
        status, body, _ = self._request(
            "POST",
            "/api/trash/purge",
            headers={
                "Origin": f"http://127.0.0.1:{self.port}",
                "Sec-Fetch-Site": "same-origin",
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("same-origin-demo", body.decode("utf-8"))

    def test_host_fetch_metadata_and_referer_checks_reject_cross_site_requests(self):
        cases = (
            {"Host": f"attacker.example:{self.port}"},
            {"Sec-Fetch-Site": "cross-site"},
            {"Referer": "http://attacker.example/landing"},
        )
        for headers in cases:
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/trash/purge",
                headers=headers,
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request)
            self.assertEqual(ctx.exception.code, 403, headers)

    def test_cross_origin_is_rejected_for_every_mutating_method(self):
        for method, path in (
            ("POST", "/api/trash/purge"),
            ("PATCH", "/api/skills/demo"),
            ("DELETE", "/api/skills/demo"),
            ("PUT", "/api/import"),
        ):
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{path}",
                data=b"{}" if method in ("POST", "PATCH") else None,
                headers={
                    "Origin": "http://attacker.example",
                    "Content-Type": "application/json",
                },
                method=method,
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request)
            self.assertEqual(ctx.exception.code, 403, (method, path))

    def test_json_mutation_rejects_browser_form_content_type(self):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/skills",
            data=json.dumps({"name": "form-demo", "description": "no"}).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code, 415)

    def test_security_headers_are_present(self):
        status, _, headers = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")
        self.assertIn("frame-ancestors 'none'", headers.get("Content-Security-Policy", ""))

    def test_export_download_includes_security_headers(self):
        status, _, headers = self._request("GET", "/api/export")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")

    def test_history_snapshot_and_full_export_import_routes(self):
        try:
            self._request("POST", "/api/skills", {"name": "route-demo", "description": "Original"}, {"Content-Type": "application/json"})
            self._request("PATCH", "/api/skills/route-demo", {"description": "Changed"}, {"Content-Type": "application/json"})
            status, body, _ = self._request("GET", "/api/history?name=route-demo&snapshots=1")
            self.assertEqual(status, 200)
            snapshots = json.loads(body)["snapshots"]
            self.assertEqual(len(snapshots), 1)
            status, body, _ = self._request("POST", f"/api/trash/route-demo?snapshot={quote(snapshots[0])}")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["snapshot"], snapshots[0])
        finally:
            try:
                self.server.httpd.store.remove("route-demo", purge=True)
            except Exception:
                pass

    def test_localhost_bind_accepts_localhost_origin(self):
        local_store = Store(data_dir=self._tmp.name)
        local_store.init_db()
        local_server = WebAppServer(local_store, host="localhost", port=0)
        import threading

        local_thread = threading.Thread(target=local_server.serve_forever, daemon=True)
        local_thread.start()
        try:
            local_server.httpd.store.create("localhost-demo", "Localhost demo")
            local_server.httpd.store.remove("localhost-demo")
            request = urllib.request.Request(
                local_server.url + "api/trash/purge",
                headers={"Origin": local_server.url.rstrip("/")},
                method="POST",
            )
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.status, 200)
        finally:
            local_server.shutdown()
            local_thread.join(timeout=5)

    def test_non_loopback_bind_is_rejected(self):
        with self.assertRaises(StoreError):
            WebAppServer(Store(data_dir=self._tmp.name), host="0.0.0.0", port=0)

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
