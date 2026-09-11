"""Local non-browser client contract pins (issue #8).

Issue #8 asks for a VS Code extension over the existing REST API. The recorded
verdict is that the extension belongs in its own repository and needs no backend
change here, and that any *missing* endpoint gets its own ASK. These tests make
the sufficiency claim checkable: they pin the client contract an editor
extension (or any other local, non-browser integration) actually depends on, so
a future security edit cannot silently break every non-browser client — and so
the deliberate absence of CORS stays a decision rather than an oversight.

Why no CORS: the server is loopback-only with no authentication, so a
cross-origin browser request must keep being rejected. An extension must call
the API from its extension host (Node) rather than from a webview origin; that
path carries no browser origin headers and is therefore allowed by design.
"""

from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from skillsmgr.store import Store, StoreError
from skillsmgr.webapp import WebAppServer


class LocalClientContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["SKILLS_MANAGER_DATA"] = cls.tmp.name
        cls.store = Store()
        cls.store.init_db()
        cls.store.create("demo", "Use this when demoing the client contract")
        cls.server = WebAppServer(cls.store, port=0)
        cls.port = cls.server.httpd.server_port
        cls.url = f"http://127.0.0.1:{cls.port}"
        cls._thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls._thread.join(timeout=5)
        cls.server.httpd.server_close()
        cls.tmp.cleanup()
        if cls._old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = cls._old_data

    @classmethod
    def call(cls, method: str, path: str, *, body=None, headers=None):
        """Issue a request the way a local non-browser client would."""
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request_headers = {"Content-Type": "application/json"} if data else {}
        request_headers.update(headers or {})
        request = urllib.request.Request(
            cls.url + path, data=data, headers=request_headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, cls._decode(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, cls._decode(exc.read())

    @staticmethod
    def _decode(raw: bytes):
        """Return parsed JSON when the endpoint serves JSON, else the text."""
        if not raw:
            return None
        text = raw.decode("utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    # ---------------------------------------------------------- reads

    def test_extension_read_endpoints_answer(self):
        for path in ("/api/scopes", "/api/skills", "/api/skills/demo",
                     "/api/skills/demo/raw", "/api/stats", "/api/doctor",
                     "/api/history?name=demo"):
            with self.subTest(path=path):
                status, _ = self.call("GET", path)
                self.assertEqual(status, 200)

    def test_raw_document_is_plain_text_for_an_editor_buffer(self):
        status, text = self.call("GET", "/api/skills/demo/raw")
        self.assertEqual(status, 200)
        self.assertIsInstance(text, str)
        self.assertIn("Use this when demoing", text)

    def test_skill_json_carries_the_fields_an_extension_needs(self):
        status, record = self.call("GET", "/api/skills/demo")
        self.assertEqual(status, 200)
        for field in ("name", "description", "body", "path", "disabled",
                      "category", "version", "license"):
            self.assertIn(field, record)

    # ------------------------------------------------------- mutations

    def test_header_absent_mutation_is_allowed_by_design(self):
        """The extension-host path: no Origin/Referer/Sec-Fetch-Site headers."""
        status, created = self.call(
            "POST", "/api/skills",
            body={"name": "from-client", "description": "Use this when testing clients"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(created["name"], "from-client")
        status, edited = self.call(
            "PATCH", "/api/skills/from-client",
            body={"description": "Use this when testing edited clients"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(edited, {"name": "from-client", "changed": True})
        # The edit is observable through the read endpoint the extension uses.
        status, record = self.call("GET", "/api/skills/from-client")
        self.assertEqual(status, 200)
        self.assertEqual(record["description"], "Use this when testing edited clients")
        status, removed = self.call("DELETE", "/api/skills/from-client")
        self.assertEqual(status, 200)
        self.assertEqual(removed["action"], "trashed")

    def _raw_request(self, method: str, path: str, headers: dict, body: bytes | None = None):
        """Send exact headers (urllib rewrites ``Host``, so use http.client)."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read().decode("utf-8")
            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, raw
        finally:
            connection.close()

    def test_wrong_host_header_is_rejected_for_mutations(self):
        status, payload = self._raw_request(
            "POST", "/api/skills",
            {"Host": "example.com", "Content-Type": "application/json"},
            json.dumps({"name": "nope", "description": "Use this when probing"}).encode(),
        )
        self.assertEqual(status, 403)
        self.assertIn("Host", payload["error"])

    def test_localhost_host_header_is_rejected_for_mutations(self):
        """Tracked integration limitation (see issue #14), not an endorsement.

        The default bind is ``127.0.0.1``, so ``allowed_hosts`` holds only
        ``127.0.0.1:<port>`` and a client configured with the equally-loopback
        name ``localhost`` gets 403 on every state-changing call. The extension
        must therefore use ``127.0.0.1`` until the alias question is decided.
        """
        status, payload = self._raw_request(
            "POST", "/api/skills",
            {"Host": f"localhost:{self.port}", "Content-Type": "application/json"},
            json.dumps({"name": "nope", "description": "Use this when probing"}).encode(),
        )
        self.assertEqual(status, 403)
        self.assertIn("invalid Host header", payload["error"])

    def test_read_path_host_validation_is_a_tracked_gap(self):
        """Characterization only: reads are not Host-validated (issue #14).

        The pre-handler policy deliberately covers state-changing methods, and
        no CORS headers are served, so a browser cannot read a cross-origin
        response. A DNS-rebound page whose origin *is* the rebound host is not
        covered by that reasoning; that path is recorded in issue #14 rather
        than changed here.
        """
        status, payload = self._raw_request("GET", "/api/skills", {"Host": "evil.example"})
        self.assertEqual(status, 200)  # current behavior, tracked in #14
        self.assertTrue(any(row["name"] == "demo" for row in payload))

    def test_cross_site_browser_request_is_still_rejected(self):
        """No CORS relaxation: loopback-only + no auth must stay fail-closed."""
        status, payload = self.call(
            "POST", "/api/skills",
            body={"name": "nope", "description": "Use this when probing"},
            headers={"Origin": "http://attacker.example",
                     "Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(status, 403)
        self.assertIn("cross-origin", payload["error"])

    def test_no_cors_headers_are_advertised(self):
        request = urllib.request.Request(self.url + "/api/stats")
        with urllib.request.urlopen(request, timeout=10) as response:
            headers = {key.lower(): value for key, value in response.headers.items()}
        self.assertNotIn("access-control-allow-origin", headers)
        self.assertNotIn("access-control-allow-methods", headers)

    def test_errors_stay_machine_readable_for_a_client(self):
        status, payload = self.call("GET", "/api/skills/does-not-exist")
        self.assertEqual(status, 404)
        self.assertIn("error", payload)

    def test_client_can_verify_the_server_identity_before_trusting_it(self):
        """An extension must be able to tell *this* server from a random one.

        There is no dedicated health endpoint, and adding one would be a new
        surface; the documented answer is the loopback URL plus a payload only
        this tool serves. This pins that shape so it cannot quietly change.
        """
        status, stats = self.call("GET", "/api/stats")
        self.assertEqual(status, 200)
        for field in ("total", "disabled", "trashed", "size_bytes", "categories"):
            self.assertIn(field, stats)


class ServerBindingContractTests(unittest.TestCase):
    """The extension depends on the loopback-only binding staying true."""

    def test_non_loopback_bind_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(data_dir=Path(tmp) / "data")
            store.init_db()
            with self.assertRaises(StoreError) as caught:
                WebAppServer(store, host="0.0.0.0", port=0)
            self.assertIn("loopback", str(caught.exception))

    def test_default_bind_is_loopback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(data_dir=Path(tmp) / "data")
            store.init_db()
            server = WebAppServer(store, port=0)
            try:
                self.assertEqual(server.host, "127.0.0.1")
                self.assertTrue(server.url.startswith("http://127.0.0.1:"))
                self.assertEqual(server.httpd.allowed_hosts,
                                 {f"127.0.0.1:{server.port}"})
            finally:
                server.httpd.server_close()


if __name__ == "__main__":
    unittest.main()
