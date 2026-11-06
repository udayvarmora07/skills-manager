"""Real HTTP regressions for the template read used by v2 creation."""

import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


class TemplateReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "data")
        self.store.init_db()
        self.store.templates_dir.mkdir(parents=True, exist_ok=True)
        self.server = WebAppServer(self.store, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.base = "http://127.0.0.1:" + str(self.server.port)

    def stop(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.httpd.server_close()

    def request(self, path, method="GET", headers=None):
        request = urllib.request.Request(self.base + path, method=method, headers=headers or {})
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def test_unicode_content_is_read_without_mutating_template_or_index(self):
        template = self.store.templates_dir / "review.md"
        template.write_text("# Review\n\nગુજરાતી · café\n", encoding="utf-8")
        before = {p.relative_to(self.store.data_dir): p.read_bytes() for p in self.store.data_dir.rglob("*") if p.is_file()}
        status, body, headers = self.request("/api/templates/review")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"name": "review", "body": template.read_text(encoding="utf-8")})
        self.assertIn("no-store", headers["Cache-Control"])
        after = {p.relative_to(self.store.data_dir): p.read_bytes() for p in self.store.data_dir.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(json.loads(self.request("/api/templates")[1]), {"templates": ["review"]})

    def test_missing_template_is_a_clean_404_and_head_has_no_body(self):
        status, body, _ = self.request("/api/templates/missing")
        self.assertEqual(status, 404)
        self.assertIn("not found", json.loads(body)["error"].lower())
        self.assertEqual(self.request("/api/templates/missing", "HEAD")[:2], (404, b""))
        (self.store.templates_dir / "review.md").write_text("Hello", encoding="utf-8")
        status, body, headers = self.request("/api/templates/review", "HEAD")
        self.assertEqual((status, body), (200, b""))
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_unsafe_names_and_nested_routes_do_not_return_file_content(self):
        for suffix in ("..", "%2e%2e", "a%2fb", "a%5cb", "%2fetc%2fpasswd", "review/extra"):
            with self.subTest(suffix=suffix):
                status, body, _ = self.request("/api/templates/" + suffix)
                self.assertIn(status, (400, 404))
                self.assertIn("error", json.loads(body))
                self.assertNotIn(str(self.root).encode(), body)

    def test_regular_templates_are_required_even_for_in_root_links(self):
        real = self.store.templates_dir / "real.md"
        real.write_text("private template", encoding="utf-8")
        link = self.store.templates_dir / "linked.md"
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        status, body, _ = self.request("/api/templates/linked")
        self.assertEqual(status, 400)
        self.assertNotIn(b"private template", body)
        link.unlink()
        external = self.root / "outside.md"
        external.write_text("outside secret", encoding="utf-8")
        link.symlink_to(external)
        status, body, _ = self.request("/api/templates/linked")
        self.assertEqual(status, 400)
        self.assertNotIn(b"outside secret", body)
        self.assertNotIn(str(external).encode(), body)

    def test_corrupt_template_is_not_a_traceback_or_false_empty_success(self):
        (self.store.templates_dir / "broken.md").write_bytes(b"\xff\xfe")
        status, body, _ = self.request("/api/templates/broken")
        self.assertEqual(status, 400)
        self.assertNotIn(b"Traceback", body)
        self.assertIn("UTF-8", json.loads(body)["error"])

    def test_template_reads_inherit_host_origin_and_fetch_metadata_policy(self):
        for headers in ({"Host": "attacker.invalid"}, {"Origin": "https://attacker.invalid"}, {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request("/api/templates/review", headers=headers)[0], 403)
