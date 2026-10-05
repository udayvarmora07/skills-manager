"""Red-first regressions: bad parameters must be rejected, not guessed at
(docs/24 §D3-8).

Two shapes of the same defect, both measured on the live server first:

* a **numeric** parameter that cannot be parsed was silently replaced by a
  default -- ``?limit=abc`` answered 200 with 50 rows, ``?window=bogus``
  answered 200 with Claude's window, so a client could not tell its request
  was ignored;
* **scope** values were not validated at all on ``/api/sync``, while the batch
  plan validated their shape. ``to_scopes: [123]`` answered 200 and reflected
  the integer back as an "unknown scope", and ``to_scopes: "global"`` -- a
  string where a list was expected -- answered 200 by iterating the string's
  *characters*::

      {"skipped": [{"scope": "g", ...}, {"scope": "l", ...}, {"scope": "o", ...},
                   {"scope": "b", ...}, {"scope": "a", ...}, {"scope": "l", ...}]}
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._saved = {k: os.environ.get(k) for k in ("SKILLS_MANAGER_DATA", "HOME")}
        self.addCleanup(self._restore)
        home = Path(self._tmp.name) / "home"
        home.mkdir(mode=0o700)
        os.environ["HOME"] = str(home)
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(self._tmp.name) / "data")
        self.store = Store()
        self.store.init_db()
        self.store.create("demo", "a demo skill")
        self.server = WebAppServer(self.store, port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)

    def _restore(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def get(self, path):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.port}{path}",
            headers={"Host": f"127.0.0.1:{self.server.port}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def post(self, path, payload):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.port}{path}",
            data=json.dumps(payload).encode(),
            headers={
                "Host": f"127.0.0.1:{self.server.port}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()


class NumericParameterTests(RouteTestCase):
    """A parameter that cannot be parsed is a 400, not a silent default."""

    BAD = ("abc", "1.5", "", " ", "1e3", "0x10", "NaN", "١٢٣", "9,9")

    def test_history_limit_rejects_an_unparseable_value(self):
        for value in self.BAD:
            with self.subTest(limit=value):
                status, body = self.get(
                    f"/api/history?limit={quote(value, safe='')}"
                )
                self.assertEqual(400, status, f"limit={value!r} was silently ignored")

    def test_the_error_names_the_parameter(self):
        status, body = self.get("/api/history?limit=abc")
        self.assertEqual(400, status)
        self.assertIn("limit", json.loads(body)["error"])

    def test_a_valid_limit_still_works(self):
        for value in ("1", "5", "1000", " 5 ".strip()):
            with self.subTest(limit=value):
                status, body = self.get(f"/api/history?limit={value}")
                self.assertEqual(200, status)
                self.assertIsInstance(json.loads(body), list)

    def test_tokens_window_rejects_an_unknown_window(self):
        status, body = self.get("/api/tokens?window=bogus")
        self.assertEqual(400, status)
        self.assertIn("window", json.loads(body)["error"])

    def test_a_known_window_still_works(self):
        for window in ("claude", "gpt-5", "gemini"):
            with self.subTest(window=window):
                status, body = self.get(f"/api/tokens?window={window}")
                self.assertEqual(200, status)
                self.assertEqual(window, json.loads(body)["window"])

    def test_stats_window_rejects_an_unknown_window(self):
        status, body = self.get("/api/stats?window=bogus")
        self.assertEqual(400, status)
        self.assertIn("window", json.loads(body)["error"])

    def test_an_omitted_parameter_is_still_the_documented_default(self):
        status, body = self.get("/api/tokens")
        self.assertEqual(200, status)
        self.assertEqual("claude", json.loads(body)["window"])


class ScopeParameterTests(RouteTestCase):
    """`to_scopes` is validated the same way on every route that takes it."""

    def test_a_string_to_scopes_is_rejected_not_iterated(self):
        status, body = self.post(
            "/api/sync", {"name": "demo", "from_scope": "global", "to_scopes": "global"}
        )
        self.assertEqual(400, status, json.loads(body))
        self.assertNotIn(b'"g"', body, "the string was iterated character by character")

    def test_a_non_string_scope_is_rejected(self):
        status, body = self.post(
            "/api/sync", {"name": "demo", "from_scope": "global", "to_scopes": [123]}
        )
        self.assertEqual(400, status)
        payload = json.loads(body)
        self.assertIn("to_scopes", payload["error"])

    def test_a_non_string_from_scope_is_rejected(self):
        status, body = self.post(
            "/api/sync", {"name": "demo", "from_scope": 7, "to_scopes": ["agents"]}
        )
        self.assertEqual(400, status)

    def test_an_empty_or_blank_scope_is_rejected(self):
        for value in ("", "   "):
            with self.subTest(scope=value):
                status, _ = self.post(
                    "/api/sync", {"name": "demo", "from_scope": "global", "to_scopes": [value]}
                )
                self.assertEqual(400, status)

    def test_an_unknown_but_well_formed_scope_is_still_reported_as_skipped(self):
        """A real scope id that does not exist is not a malformed request."""
        status, body = self.post(
            "/api/sync", {"name": "demo", "from_scope": "global", "to_scopes": ["no-such-scope"]}
        )
        self.assertEqual(200, status)
        self.assertEqual(
            [{"scope": "no-such-scope", "reason": "unknown scope"}],
            json.loads(body)["skipped"],
        )

    def test_a_well_formed_request_still_works(self):
        status, body = self.post(
            "/api/sync", {"name": "demo", "from_scope": "global", "to_scopes": ["agents"]}
        )
        self.assertEqual(200, status)
        payload = json.loads(body)
        self.assertEqual("demo", payload["name"])

    def test_the_batch_plan_validates_the_same_way(self):
        status, body = self.post(
            "/api/batch/preview",
            {
                "operation": "sync",
                "targets": [{"name": "demo", "scope": "global"}],
                "to_scopes": [123],
            },
        )
        self.assertEqual(400, status)
        self.assertIn("to_scopes", json.loads(body)["error"])

    def test_a_rejected_sync_changed_nothing(self):
        before = sorted(p.name for p in (self.store.data_dir / "skills").iterdir())
        self.post("/api/sync", {"name": "demo", "from_scope": "global", "to_scopes": "global"})
        after = sorted(p.name for p in (self.store.data_dir / "skills").iterdir())
        self.assertEqual(before, after)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()