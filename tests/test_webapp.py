"""REST API tests: serve the real WebAppServer on an ephemeral port."""

import io
import json
import os
import tarfile
import tempfile
import unittest
import zipfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote
from unittest import mock

from skillsmgr.store import Store, StoreError
from skillsmgr.webapp import RequestError, WebAppHandler, WebAppServer


class BrowserOpenerTests(unittest.TestCase):
    def test_trusted_opener_receives_absolute_url_as_one_shell_free_argument(self):
        from skillsmgr import webapp

        with mock.patch.object(webapp, "trusted_executable", return_value="/safe/xdg-open"):
            with mock.patch.object(webapp.subprocess, "Popen") as popen:
                webapp._open_browser("http://127.0.0.1:8765/?q=one two")
        popen.assert_called_once()
        args, kwargs = popen.call_args
        self.assertEqual(args[0], ["/safe/xdg-open", "http://127.0.0.1:8765/?q=one two"])
        self.assertFalse(kwargs["shell"])

    def test_unsafe_first_path_match_is_skipped_for_a_safe_later_match(self):
        from skillsmgr import webapp

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsafe_dir = root / "unsafe"
            safe_dir = root / "safe"
            unsafe_dir.mkdir()
            safe_dir.mkdir()
            unsafe_dir.chmod(0o700)
            safe_dir.chmod(0o700)
            unsafe = unsafe_dir / "xdg-open"
            safe = safe_dir / "xdg-open"
            unsafe.write_text("unsafe\n", encoding="utf-8")
            safe.write_text("safe\n", encoding="utf-8")
            unsafe.chmod(0o777)
            safe.chmod(0o700)
            with mock.patch.dict(os.environ, {"PATH": f"{unsafe_dir}:{safe_dir}"}, clear=False):
                with mock.patch.object(webapp.subprocess, "Popen") as popen:
                    webapp._open_browser("http://127.0.0.1:8765/")
            self.assertEqual(popen.call_args.args[0][0], str(safe.resolve()))

    def test_missing_opener_and_launch_failure_are_clean(self):
        from skillsmgr import webapp

        with mock.patch.object(webapp, "trusted_executable", return_value=None):
            with mock.patch.object(webapp.subprocess, "Popen") as popen:
                webapp._open_browser("http://127.0.0.1:8765/")
            popen.assert_not_called()
        with mock.patch.object(webapp, "trusted_executable", return_value="/safe/xdg-open"):
            with mock.patch.object(webapp.subprocess, "Popen", side_effect=OSError("no opener")):
                with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
                    webapp._open_browser("http://127.0.0.1:8765/")
        self.assertIn("browser opener failed", stderr.getvalue())


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

    @staticmethod
    def _persisted(store, name):
        """Return the durable state of one skill, without read-time stamps.

        ``Store.get()`` decorates the stored row with observations computed at
        read time (``observed_at`` is stamped with ``datetime.now()``), so two
        reads that straddle a UTC second boundary differ even when nothing was
        written. The no-mutation contract is about persisted state, so compare
        the stored row and the document bytes and drop only the read-time stamp.
        """
        record = dict(store.get(name))
        record.pop("observed_at", None)
        document = (store.skills_dir / name / "SKILL.md").read_text(encoding="utf-8")
        return record, document

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
        status, body = self._get("/api/doctor?scope=global&hygiene=1")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("hygiene", payload)
        self.assertEqual(payload["hygiene"]["summary"]["physical_instances"], 1)

    def test_safe_local_update_rest_review_apply_and_snapshots(self):
        boundary = "skillsmgr-update-test"
        document = b"---\nname: demo\ndescription: Demo skill\n---\nupdated\n"
        body = b"".join([
            b"--" + boundary.encode() + b"\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\ndemo\r\n",
            b"--" + boundary.encode() + b"\r\nContent-Disposition: form-data; name=\"scope\"\r\n\r\nglobal\r\n",
            b"--" + boundary.encode() + b"\r\nContent-Disposition: form-data; name=\"files\"; filename=\"SKILL.md\"\r\n\r\n",
            document,
            b"\r\n--" + boundary.encode() + b"--\r\n",
        ])
        status, body, _ = self._request(
            "POST", "/api/source-updates/reviews", body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        self.assertEqual(status, 201)
        review = json.loads(body)
        self.assertEqual(review["review_state"], "pending")
        self.assertEqual(review["source"]["value"], "browser-upload")
        self.assertNotIn("skillsmgr-update-", json.dumps(review))
        status, body, _ = self._request(
            "POST", f"/api/source-updates/reviews/{review['review_id']}/commit",
            body={"name": "demo", "scope": "global", "approve": True},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertTrue(result["committed"])
        status, body, _ = self._request("GET", "/api/source-updates/snapshots?name=demo&scope=global")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["snapshots"]), 1)

    def test_long_query_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/api/search?q=" + "x" * 300)
        self.assertEqual(ctx.exception.code, 400)

    def test_over_limit_body_is_drained_and_returns_413(self):
        class FakeHandler:
            headers = {"Content-Length": "5"}
            rfile = io.BytesIO(b"12345")

            def _drain_body(self, length):
                return WebAppHandler._drain_body(self, length)

        handler = FakeHandler()
        with self.assertRaises(RequestError) as ctx:
            WebAppHandler._read_body(handler, limit=4)
        self.assertEqual(ctx.exception.status, 413)
        self.assertEqual(handler.rfile.read(), b"")

    def test_client_disconnect_during_response_is_ignored(self):
        class BrokenWriter:
            def write(self, body):
                raise BrokenPipeError()

        handler = object.__new__(WebAppHandler)
        handler.wfile = BrokenWriter()
        WebAppHandler._write_body(handler, b"response")

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

    def test_cross_site_get_is_rejected_for_every_read_route(self):
        # SEC-1: the Host/Origin/Fetch-Metadata policy used to run only for
        # mutating methods, so a hostile web page could read the whole skill
        # library (and the full export archive) through GET.
        for path in ("/api/skills", "/api/skills/demo", "/api/doctor", "/api/export?full=1"):
            for headers in (
                {"Host": f"attacker.example:{self.port}"},
                {"Sec-Fetch-Site": "cross-site"},
                {"Origin": "http://attacker.example"},
                {"Referer": "http://attacker.example/landing"},
            ):
                with self.subTest(path=path, headers=headers):
                    with self.assertRaises(urllib.error.HTTPError) as ctx:
                        self._request("GET", path, headers=headers)
                    self.assertEqual(ctx.exception.code, 403)

    def test_same_origin_get_remains_allowed(self):
        status, body, _ = self._request(
            "GET",
            "/api/skills",
            headers={
                "Origin": f"http://127.0.0.1:{self.port}",
                "Sec-Fetch-Site": "same-origin",
                "Host": f"127.0.0.1:{self.port}",
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body))

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

    def test_install_rejects_traversal_absolute_and_oversized_values(self):
        for payload in (
            {"source": "../../tmp/pwn"},
            {"source": "/etc/passwd"},
            {"source": "C:/Windows"},
            {"source": "owner/repo", "agents": ["../tmp"]},
            {"source": "owner/repo", "skills": ["/etc/passwd"]},
            {"source": "owner/repo", "agents": ["x" * 257]},
        ):
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/install",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(request)
            self.assertEqual(ctx.exception.code, 400, payload)
            self.assertIn("invalid", json.loads(ctx.exception.read())["error"])

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
        before = self._persisted(store, "demo")
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
        self.assertEqual(self._persisted(store, "demo"), before)
        self.assertFalse((store.skills_dir / "bad-meta").exists())

    def test_malformed_patch_fields_return_json_400_without_mutation(self):
        store = self.server.httpd.store
        before = self._persisted(store, "demo")
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
        after = self._persisted(store, "demo")
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

    def test_zip_import_route_accepts_archive_content(self):
        payload = b"---\nname: web-zip\ndescription: Use this ZIP route test.\n---\nZIP body.\n"
        manifest = json.dumps({"app": "skills-mgr", "version": "1.0.0", "created": "2026-09-08T00:00:00Z", "skills": [{"name": "web-zip"}]}).encode()
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("manifest.json", manifest)
            zipped.writestr("skills/web-zip/SKILL.md", payload)
        request = urllib.request.Request(
            self.server.url + "api/import?filename=web-zip.zip",
            data=archive.getvalue(),
            method="PUT",
        )
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["imported"], ["web-zip"])
        self.assertIn("ZIP body.", self.server.httpd.store.get("web-zip")["body"])

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
