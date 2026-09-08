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

    def test_malformed_create_fields_return_json_400_without_mutation(self):
        store = self.server.httpd.store
        initial_names = {row["name"] for row in store.list()}
        initial_templates = set(store.templates_dir.glob("*.md"))
        cases = (
            ("/api/skills", {"name": 123, "description": "bad"}, "name must be a non-empty string"),
            ("/api/skills", {"name": "bad", "description": 123}, "description must be a non-empty string"),
            ("/api/skills", {"name": "bad-tools", "description": "bad", "allowed_tools": {}}, "allowed_tools must be a string"),
            ("/api/templates", {"name": 123}, "template name must be a non-empty string"),
            ("/api/sync", {"name": 123}, "name must be a string"),
            ("/api/validate", {"name": 123}, "skill name must be a non-empty string"),
        )
        for path, payload, message in cases:
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{path}",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request)
            self.assertEqual(ctx.exception.code, 400, (path, payload))
            self.assertEqual(json.loads(ctx.exception.read()), {"error": message})
        self.assertEqual({row["name"] for row in store.list()}, initial_names)
        self.assertEqual(set(store.templates_dir.glob("*.md")), initial_templates)

    def test_install_scalar_types_return_json_400(self):
        cases = (
            ({"source": 123}, "source must be a string"),
            ({"source": "owner/repo", "scope": 123}, "scope must be a string"),
            ({"source": "owner/repo", "runner": 123}, "runner must be a string"),
        )
        for payload, message in cases:
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/install",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request)
            self.assertEqual(ctx.exception.code, 400, payload)
            self.assertEqual(json.loads(ctx.exception.read()), {"error": message})

    def test_scalar_metadata_types_return_json_400_without_mutation(self):
        store = self.server.httpd.store
        before = (store.get("demo"), (store.skills_dir / "demo" / "SKILL.md").read_text(encoding="utf-8"))
        for method, path, base in (
            ("POST", "/api/skills", {"name": "bad-meta", "description": "bad"}),
            ("PATCH", "/api/skills/demo", {}),
        ):
            for field in ("category", "license", "version", "compatibility", "body"):
                payload = {**base, field: 123}
                request = urllib.request.Request(
                    f"http://127.0.0.1:{self.port}{path}",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method=method,
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(request)
                self.assertEqual(ctx.exception.code, 400, (method, field))
                self.assertEqual(json.loads(ctx.exception.read()), {"error": f"{field} must be a string"})
        self.assertEqual((store.get("demo"), (store.skills_dir / "demo" / "SKILL.md").read_text(encoding="utf-8")), before)
        self.assertFalse((store.skills_dir / "bad-meta").exists())

    def test_malformed_patch_fields_return_json_400_without_mutation(self):
        store = self.server.httpd.store
        before = (store.get("demo"), (store.skills_dir / "demo" / "SKILL.md").read_text(encoding="utf-8"))
        for field in ("description", "body", "allowed_tools"):
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/skills/demo",
                data=json.dumps({field: 123}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="PATCH",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request)
            self.assertEqual(ctx.exception.code, 400)
            expected = f"{field} must be a string"
            self.assertEqual(json.loads(ctx.exception.read()), {"error": expected})
        after = (store.get("demo"), (store.skills_dir / "demo" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(after, before)

    def test_allowed_tools_lists_are_rejected_for_global_and_agent_scopes(self):
        store = self.server.httpd.store
        for method, path in (("POST", "/api/skills"), ("PATCH", "/api/skills/demo")):
            payload = {"allowed_tools": ["git"]}
            if method == "POST":
                payload.update(name="global-list", description="Global list")
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{path}",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method=method,
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request)
            self.assertEqual(ctx.exception.code, 400)
            self.assertEqual(json.loads(ctx.exception.read()), {"error": "allowed_tools must be a string"})
        self.assertFalse((store.skills_dir / "global-list").exists())

        old_home = os.environ.get("HOME")
        agent_home = Path(self._tmp.name) / "agent-home"
        os.environ["HOME"] = str(agent_home)
        try:
            (agent_home / ".agents" / "skills").mkdir(parents=True)
            for method, path, payload in (
                ("POST", "/api/skills?scope=agents", {"name": "agent-list", "description": "Agent list", "allowed_tools": ["git"]}),
                ("POST", "/api/skills?scope=agents", {"name": "agent-string", "description": "Agent string", "allowed_tools": "git"}),
            ):
                request = urllib.request.Request(
                    f"http://127.0.0.1:{self.port}{path}",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method=method,
                )
                if payload["name"] == "agent-list":
                    with self.assertRaises(urllib.error.HTTPError) as ctx:
                        urllib.request.urlopen(request)
                    self.assertEqual(ctx.exception.code, 400)
                    self.assertEqual(json.loads(ctx.exception.read()), {"error": "allowed_tools must be a string"})
                else:
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status, 201)
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/skills/agent-string?scope=agents",
                data=json.dumps({"allowed_tools": ["git"]}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="PATCH",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request)
            self.assertEqual(ctx.exception.code, 400)
            self.assertEqual(json.loads(ctx.exception.read()), {"error": "allowed_tools must be a string"})
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

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

    def test_full_import_query_flag_restores_full_archive_payload(self):
        source = Store(data_dir=Path(self._tmp.name) / "full-source")
        source.init_db()
        source.create("full-route", "Full route skill")
        source.create("full-trash", "Full route trash")
        source.remove("full-trash")
        (source.templates_dir / "route-template.md").write_text("# Route\n", encoding="utf-8")
        archive = source.export(full=True)
        target = Store(data_dir=Path(self._tmp.name) / "full-target")
        target.init_db()
        server = WebAppServer(target, port=0)
        thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                server.url + "api/import?filename=full.tar.gz&full=1",
                data=Path(archive).read_bytes(),
                method="PUT",
            )
            with urllib.request.urlopen(request) as response:
                payload = json.loads(response.read())
            self.assertEqual(payload["imported"], ["full-route"])
            self.assertEqual(len(target.trash_list()), 1)
            self.assertEqual(payload["restored_templates"], ["route-template.md"])
            self.assertTrue((target.templates_dir / "route-template.md").is_file())
        finally:
            server.shutdown()
            thread.join(timeout=5)

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
