"""Real PATCH roundtrips for fields exposed by the v2 editor."""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from skillsmgr import scopes
from skillsmgr.frontmatter import dump_frontmatter, parse_frontmatter
from skillsmgr.webapp import WebAppServer
from tests.test_web_scopes import ScopedHomeTestCase


class EditFieldsTests(ScopedHomeTestCase):
    def setUp(self):
        super().setUp()
        self.store = scopes._global_store()
        self.server = WebAppServer(self.store, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.httpd.server_close()

    def patch(self, scope, fields):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.port}/api/skills/editable?scope={scope}",
            method="PATCH", data=json.dumps(fields).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def seed(self, scope):
        fields = dict(license="MIT", category="quality", version="1", compatibility="Python", allowed_tools="Read", body="# Original")
        if scope == "global":
            self.store.create("editable", "Keep description", **fields)
            return self.store.skills_dir / "editable" / "SKILL.md"
        scopes.create_skill(scope, "editable", "Keep description", **fields)
        return Path(self._tmp.name) / ".codex" / "skills" / "editable" / "SKILL.md"

    def test_explicit_empty_optional_fields_and_body_are_persisted(self):
        for scope in ("global", "codex"):
            with self.subTest(scope=scope):
                path = self.seed(scope)
                status, _ = self.patch(scope, dict.fromkeys(("license", "category", "version", "compatibility", "allowed_tools", "body"), ""))
                self.assertEqual(status, 200)
                data, body = parse_frontmatter(path.read_text(encoding="utf-8"))
                self.assertEqual(data["description"], "Keep description")
                self.assertEqual(data["metadata"]["category"], "")
                for key in ("license", "version", "compatibility", "allowed-tools"):
                    self.assertEqual(data[key], "")
                self.assertEqual(body.strip(), "")

    def test_omitted_fields_survive_and_empty_description_is_rejected(self):
        path = self.seed("global")
        self.assertEqual(self.patch("global", {"body": "# Changed"})[0], 200)
        data, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        self.assertEqual(data["license"], "MIT")
        before = path.read_bytes()
        status, result = self.patch("global", {"description": "", "body": "Must not write"})
        self.assertEqual(status, 400)
        self.assertIn("description", result["error"])
        self.assertEqual(path.read_bytes(), before)

    def test_body_only_patch_preserves_non_mapping_legacy_metadata(self):
        for scope in ("global", "codex"):
            with self.subTest(scope=scope):
                path = self.seed(scope)
                data, body = parse_frontmatter(path.read_text(encoding="utf-8"))
                data["metadata"] = "legacy metadata value"
                path.write_text(dump_frontmatter(data) + body, encoding="utf-8")
                self.assertEqual(self.patch(scope, {"body": "# Changed"})[0], 200)
                current, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
                self.assertEqual(current, data)
