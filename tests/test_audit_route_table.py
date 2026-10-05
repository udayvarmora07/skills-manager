"""Characterisation tests for the web route table (docs/24 §C4 #3).

**This is a characterisation test, not a specification of desired behaviour.**
Every expectation below was *measured* against the pre-refactor tree at
``0b447e4`` by driving a real ``WebAppServer`` over HTTP and recording the
status, the JSON body shape, the stable error ``code`` and the response
headers.  The split of ``_route_get`` / ``_route_post`` into a route table is
a **purely structural** change, so this file passes unchanged both before and
after it.  If a refactor turns anything here red, the refactor changed
observable behaviour: revert the refactor, do not relax the expectation.

What is pinned, per the task's bar:

* the status code of every ``GET`` and ``POST`` route the two routers own;
* the JSON body shape -- which keys a success carries, and that every failure
  carries the one ``{"error", "code"}`` shape introduced by ``0b447e4``;
* the stable ``code`` string, not just the human ``error`` message;
* the security header set, on successes *and* on errors;
* the 404 / 405 / 403 boundary behaviour (SEC-1, BUG-9, D3-7);
* **near-miss paths that must keep answering ``unknown_endpoint``** -- the
  sharpest available test against a route table that accidentally matches
  more than the path it names.

The router methods are exercised only over HTTP: nothing in the suite calls
``_route_get`` / ``_route_post`` directly, so this is the only place their
observable surface can be pinned.

The hermetic-server idiom (``HOME`` *and* ``SKILLS_MANAGER_DATA`` redirected,
explicit ``Host`` header, ``HTTPError`` returned rather than raised) is the
one already used by ``tests/test_audit_d3_parameter_coercion.py``.
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

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer

# The security header set every routed answer carries, errors included.
SECURITY_HEADERS = (
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
    "Cross-Origin-Resource-Policy",
    "Content-Security-Policy",
)

# --- measured GET behaviour -------------------------------------------------
# (path, expected_status, expected_error_code_or_None, expected_body_kind,
#  keys_that_must_be_present)
#
# ``body_kind`` is "dict", "list" or "text".  ``keys`` is a subset assertion:
# it pins the fields that identify *which branch* answered, not every
# incidental field the branch happens to emit.
GET_ROUTES = (
    # -- root / workspace discovery ------------------------------------------
    ("/api/scopes", 200, None, "list", ()),
    ("/api/workspaces", 200, None, "dict", ("adapters", "model", "project")),
    ("/api/workspaces?project=/nope", 200, None, "dict", ("adapters", "model", "project")),
    ("/api/catalog", 200, None, "dict", ("profiles", "tags", "version")),
    ("/api/catalog/profiles/nope/preview", 404, "not_found", "dict", ("code", "error")),
    # -- the skill list, every scope/search/paging variant --------------------
    ("/api/skills", 200, None, "list", ()),
    ("/api/skills?scope=global", 200, None, "list", ()),
    ("/api/skills?scope=all", 200, None, "list", ()),
    ("/api/skills?scope=claude-code", 200, None, "list", ()),
    ("/api/skills?q=demo", 200, None, "list", ()),
    ("/api/skills?scope=all&q=demo", 200, None, "list", ()),
    ("/api/skills?limit=1", 200, None, "list", ()),
    ("/api/skills?offset=99", 200, None, "list", ()),
    ("/api/skills?limit=abc", 400, "bad_request", "dict", ("code", "error")),
    ("/api/skills?limit=0", 400, "bad_request", "dict", ("code", "error")),
    ("/api/skills?page=2", 400, "bad_request", "dict", ("code", "error")),
    # -- one skill: detail and raw -------------------------------------------
    ("/api/skills/demo", 200, None, "dict", ("name", "body", "path", "tokens")),
    ("/api/skills/nope", 404, "not_found", "dict", ("code", "error")),
    ("/api/skills/demo/raw", 200, None, "text", ()),
    ("/api/skills/nope/raw", 404, "not_found", "dict", ("code", "error")),
    # -- search ---------------------------------------------------------------
    ("/api/search", 200, None, "list", ()),
    ("/api/search?q=demo", 200, None, "list", ()),
    ("/api/search?q=demo&scope=all", 200, None, "list", ()),
    ("/api/search?q=demo&scope=global", 200, None, "list", ()),
    ("/api/search?q=demo&scope=claude-code", 200, None, "list", ()),
    ("/api/search?q=" + "x" * 400, 400, "bad_request", "dict", ("code", "error")),
    ("/api/search?q=*a*b*c*d*e*f*g*h*i*j*k*l*", 400, "bad_request", "dict", ("code", "error")),
    # -- trash / templates / history -----------------------------------------
    ("/api/trash", 200, None, "list", ()),
    ("/api/templates", 200, None, "dict", ("templates",)),
    ("/api/history", 200, None, "list", ()),
    ("/api/history?limit=abc", 400, "bad_request", "dict", ("code", "error")),
    ("/api/history?name=demo&snapshots=1", 200, None, "dict", ("name", "scope", "snapshots")),
    ("/api/history?name=demo&snapshots=1&scope=global", 200, None, "dict",
     ("name", "scope", "snapshots")),
    # -- stats / tokens ------------------------------------------------------
    ("/api/stats", 200, None, "dict",
     ("scopes", "all_total", "all_tokens", "window", "window_tokens", "largest")),
    ("/api/stats?window=gpt-5", 200, None, "dict", ("window", "window_tokens")),
    ("/api/stats?window=bogus", 400, "bad_request", "dict", ("code", "error")),
    ("/api/tokens", 200, None, "dict", ("total_tokens", "count", "window", "pct_window")),
    ("/api/tokens?text=hello", 200, None, "dict", ("tokens", "chars", "lines")),
    ("/api/tokens?name=demo", 200, None, "dict", ("tokens", "chars", "lines")),
    ("/api/tokens?name=demo&scope=global", 200, None, "dict", ("tokens", "chars", "lines")),
    ("/api/tokens?name=nope", 404, "not_found", "dict", ("code", "error")),
    ("/api/tokens?scope=global", 200, None, "dict", ("total_tokens", "count")),
    ("/api/tokens?scope=claude-code", 200, None, "dict", ("total_tokens", "count")),
    ("/api/tokens?window=bogus", 400, "bad_request", "dict", ("code", "error")),
    # -- doctor --------------------------------------------------------------
    ("/api/doctor", 200, None, "dict", ("data_dir", "db_integrity", "conflicting_documents")),
    ("/api/doctor?scope=all", 200, None, "dict", ("scopes", "duplicates")),
    ("/api/doctor?scope=all&hygiene=1", 200, None, "dict", ("hygiene",)),
    ("/api/doctor?explain=bogus", 200, None, "dict", ("explain",)),
    ("/api/doctor?explain=claude-code&project=/nope", 200, None, "dict", ("explain",)),
    # -- export --------------------------------------------------------------
    ("/api/export", 200, None, "text", ()),
    ("/api/export?full=1", 200, None, "text", ()),
    ("/api/export?scope=claude-code", 400, "bad_request", "dict", ("code", "error")),
    # -- source updates (the already-extracted guard, kept as the precedent) --
    ("/api/source-updates/snapshots?name=demo&scope=global", 200, None, "dict",
     ("name", "scope", "snapshots")),
    ("/api/source-updates/reviews/deadbeef", 400, "invalid-review-id", "dict",
     ("code", "error")),
    # -- unrouted ------------------------------------------------------------
    ("/api/nope", 404, "unknown_endpoint", "dict", ("code", "error")),
)

# Measured: every one of these must keep answering unknown_endpoint.  A route
# table that matches a prefix, or an entry copied with the wrong segment
# count, turns one of these into a 200 and this file goes red.
GET_UNROUTED = (
    "/api/skill", "/api/skillsx", "/api/searchx", "/api/doctorx", "/api/tokensx",
    "/api/trashx", "/api/scopes/extra", "/api/stats/extra", "/api/history/extra",
    "/api/export/extra", "/api/workspaces/extra", "/api/templates/extra",
    "/api/resync/extra", "/api/rebuild/extra", "/api/search/extra",
    "/api/validate/extra", "/api/skills/demo/bogus", "/api/trash/x/y/z",
    "/api/catalog/profiles/nope", "/api/catalog/profiles/nope/preview/extra",
)

# Measured: POST bodies rejected for shape.  ``code`` is pinned because these
# are the branches that decide whether a request is refused or coerced.
POST_ROUTES = (
    ("/api/sync", {"name": ""}, 400, "bad_request"),
    ("/api/sync", {"name": 5}, 400, "bad_request"),
    ("/api/sync", {"name": "demo", "to_scopes": "global"}, 400, "bad_request"),
    ("/api/sync", {"name": "demo", "to_scopes": [7]}, 400, "bad_request"),
    ("/api/install", {"source": 7}, 400, "bad_request"),
    ("/api/install", {"source": ""}, 400, "bad_request"),
    ("/api/install", {}, 400, "bad_request"),
    ("/api/install", {"source": "o/r", "runner": "uvx"}, 400, "bad_request"),
    ("/api/install", {"source": "o/r", "runner": "bogus"}, 400, "bad_request"),
    ("/api/install", {"source": "o/r", "runner": 7}, 400, "bad_request"),
    # A browse request is refused locally, without a network round trip: the
    # leaderboard route needs a project token a laptop binary cannot mint.
    ("/api/install", {"browse": True}, 400, "bad_request"),
    ("/api/skills", {"description": "no name"}, 400, "bad_request"),
    ("/api/skills", {"name": "x"}, 400, "bad_request"),
    ("/api/skills", {"name": 7, "description": "d"}, 400, "bad_request"),
    ("/api/skills/nope/disable", None, 404, "not_found"),
    ("/api/skills/nope/bogus", None, 404, "unknown_endpoint"),
    ("/api/templates", {"name": ""}, 400, "bad_request"),
    ("/api/templates", {"name": "t", "body": 7}, 400, "bad_request"),
    ("/api/validate", {"name": ""}, 400, "bad_request"),
    ("/api/validate", {"name": "demo", "scope": "  "}, 400, "bad_request"),
    ("/api/validate", {"name": "nope"}, 404, "not_found"),
    ("/api/batch/preview", {"operation": "bogus"}, 400, "bad_request"),
    ("/api/batch/preview", {"operation": "sync"}, 400, "bad_request"),
    ("/api/catalog/tags", {"names": "x", "tags": []}, 400, "bad_request"),
    ("/api/catalog/profiles", {"name": 7}, 400, "bad_request"),
    ("/api/nope", None, 404, "unknown_endpoint"),
    ("/api/trash", None, 404, "unknown_endpoint"),
)

POST_UNROUTED = (
    ("/api/syncx", {"name": "demo"}),
    ("/api/installx", {"source": "o/r"}),
    ("/api/skills/demo/reset", None),
    ("/api/trash/purge/extra", None),
    ("/api/trash/demo/extra", None),
    ("/api/validatex", {"name": "demo"}),
    ("/api/resyncx", None),
    ("/api/rebuildx", None),
    ("/api/templatesx", {"name": "t"}),
)


class RouteTableTestCase(unittest.TestCase):
    """Serve a real server over a hermetic data dir and isolated ``HOME``."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._saved = {key: os.environ.get(key) for key in ("SKILLS_MANAGER_DATA", "HOME")}
        self.addCleanup(self._restore_env)
        home = Path(self._tmp.name) / "home"
        home.mkdir(mode=0o700)
        os.environ["HOME"] = str(home)
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(self._tmp.name) / "data")
        self.store = Store()
        self.store.init_db()
        self.store.create("demo", "A demo skill for route characterisation.",
                          body="Hello.\n\n## Section\n\nBody text.")
        self.server = WebAppServer(self.store, port=0)
        self.port = self.server.port
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        self.addCleanup(self._thread.join, 5)
        self.addCleanup(self.server.shutdown)

    def _restore_env(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # -- request helpers -----------------------------------------------------

    def request(self, method, path, body=None, headers=None):
        """Return ``(status, raw_body, headers)``; an HTTPError is not raised."""
        request_headers = {"Host": f"127.0.0.1:{self.port}"}
        request_headers.update(headers or {})
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data, headers=request_headers, method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status, response.read(), dict(response.headers)
        except urllib.error.HTTPError as error:
            return error.code, error.read(), dict(error.headers)

    def raw_request(self, method, path, headers, body=None):
        """Issue a request urllib would rewrite -- needed for a custom ``Host``."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    # -- assertions ----------------------------------------------------------

    def assert_json_shape(self, raw, kind, required, where):
        self.assertTrue(
            all(header in self._last_headers for header in SECURITY_HEADERS),
            f"{where}: missing a security header in {sorted(self._last_headers)}",
        )
        if kind == "text":
            return None
        try:
            payload = json.loads(raw)
        except ValueError:
            self.fail(f"{where}: body is not JSON: {raw[:200]!r}")
        if kind == "list":
            self.assertIsInstance(payload, list, f"{where}: expected a list")
        else:
            self.assertIsInstance(payload, dict, f"{where}: expected an object")
            missing = [key for key in required if key not in payload]
            self.assertEqual(missing, [], f"{where}: missing keys {missing}")
        return payload

    # -- GET -----------------------------------------------------------------

    def test_every_get_route_answers_the_measured_status_and_shape(self):
        for path, status, code, kind, required in GET_ROUTES:
            with self.subTest(path=path):
                got_status, raw, headers = self.request("GET", path)
                self._last_headers = headers
                self.assertEqual(got_status, status, f"GET {path} status")
                payload = self.assert_json_shape(raw, kind, required, f"GET {path}")
                if code is not None:
                    self.assertIsInstance(payload, dict, f"GET {path}: error body")
                    self.assertEqual(payload.get("code"), code, f"GET {path} code")
                    self.assertIn("error", payload, f"GET {path}: error message")

    def test_get_near_miss_paths_stay_unrouted(self):
        """A route table must not match more than the path it names."""
        for path in GET_UNROUTED:
            with self.subTest(path=path):
                status, raw, headers = self.request("GET", path)
                self._last_headers = headers
                self.assertEqual(status, 404, f"GET {path} status")
                payload = self.assert_json_shape(raw, "dict", ("code", "error"), f"GET {path}")
                self.assertEqual(payload["code"], "unknown_endpoint", f"GET {path} code")

    # -- POST ----------------------------------------------------------------

    def test_every_post_route_answers_the_measured_status_and_code(self):
        for path, body, status, code in POST_ROUTES:
            with self.subTest(path=path, body=body):
                got_status, raw, headers = self.request("POST", path, body)
                self._last_headers = headers
                self.assertEqual(got_status, status, f"POST {path} {body} status")
                payload = self.assert_json_shape(raw, "dict", ("code", "error"), f"POST {path}")
                self.assertEqual(payload.get("code"), code, f"POST {path} {body} code")

    def test_post_near_miss_paths_stay_unrouted(self):
        for path, body in POST_UNROUTED:
            with self.subTest(path=path):
                status, raw, headers = self.request("POST", path, body)
                self._last_headers = headers
                self.assertEqual(status, 404, f"POST {path} status")
                payload = self.assert_json_shape(raw, "dict", ("code", "error"), f"POST {path}")
                self.assertEqual(payload["code"], "unknown_endpoint", f"POST {path} code")

    def test_post_success_shapes(self):
        """The success bodies, which the error tables above cannot reach."""
        expected = (
            ("POST", "/api/install", {"source": "o/r"}, 200,
             ("command", "runner", "source", "executed")),
            ("POST", "/api/rebuild", None, 200, ("added", "updated", "removed")),
            ("POST", "/api/resync", None, 200, ("added", "updated", "removed")),
            ("POST", "/api/validate", {"name": "demo"}, 200, ("valid", "issues")),
            ("POST", "/api/trash/purge", None, 200, ("purged",)),
        )
        for method, path, body, status, required in expected:
            with self.subTest(path=path):
                got_status, raw, headers = self.request(method, path, body)
                self._last_headers = headers
                self.assertEqual(got_status, status, f"{method} {path} status")
                self.assert_json_shape(raw, "dict", required, f"{method} {path}")

    def test_install_preview_is_not_executed(self):
        """A preview request never runs the runner (docs/24 D3 read purity)."""
        status, raw, _ = self.request("POST", "/api/install", {"source": "o/r"})
        self.assertEqual(status, 200)
        payload = json.loads(raw)
        self.assertEqual(payload["command"], "npx skills add o/r -g")
        self.assertIs(payload["executed"], False)

    def test_skill_toggle_lifecycle_routes(self):
        """``POST /api/skills/{name}/disable|enable`` -- smoke-only until now."""
        status, raw, _ = self.request(
            "POST", "/api/skills",
            {"name": "toggled", "description": "A skill to toggle."},
        )
        self.assertEqual(status, 201)
        for verb, key in (("disable", "disable"), ("enable", "enable")):
            with self.subTest(verb=verb):
                status, raw, _ = self.request("POST", f"/api/skills/toggled/{verb}")
                self.assertEqual(status, 200)
                payload = json.loads(raw)
                self.assertEqual(payload, {"name": "toggled", key: True})

    def test_trash_restore_without_a_snapshot(self):
        status, raw, _ = self.request("POST", "/api/skills",
                                      {"name": "restorable", "description": "To trash."})
        self.assertEqual(status, 201)
        self.request("DELETE", "/api/skills/restorable")
        status, raw, _ = self.request("GET", "/api/trash")
        self.assertEqual(status, 200)
        self.assertIn("restorable", [row["name"] for row in json.loads(raw)])
        status, raw, _ = self.request("POST", "/api/trash/restorable")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["name"], "restorable")

    # -- boundaries that are not the route table's business ------------------

    def test_a_read_with_a_foreign_host_is_403_not_a_silent_success(self):
        """SEC-1: the request policy guards ``GET`` as well as mutations."""
        status, raw, headers = self.raw_request(
            "GET", "/api/skills", {"Host": "evil.example"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(raw)["code"], "forbidden")
        for header in SECURITY_HEADERS:
            self.assertIn(header, headers)

    def test_a_mutation_with_a_foreign_host_is_403(self):
        status, raw, _ = self.raw_request(
            "POST", "/api/rebuild", {"Host": "evil.example"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(raw)["code"], "forbidden")

    def test_cross_site_fetch_metadata_is_403_on_a_read(self):
        status, raw, _ = self.request(
            "GET", "/api/skills", headers={"Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(raw)["code"], "forbidden")

    def test_head_mirrors_get_with_the_body_suppressed(self):
        """BUG-9: ``HEAD`` answers with the ``GET`` headers and no body."""
        status, raw, headers = self.request("HEAD", "/api/skills")
        self.assertEqual(status, 200)
        self.assertEqual(raw, b"")
        get_status, get_raw, get_headers = self.request("GET", "/api/skills")
        self.assertEqual(headers.get("Content-Length"),
                         get_headers.get("Content-Length"))
        self.assertEqual(len(raw), 0)
        self.assertGreater(len(get_raw), 0)
        for header in SECURITY_HEADERS:
            self.assertIn(header, headers)

    def test_options_and_trace_are_json_405_with_allow_and_security_headers(self):
        for verb in ("OPTIONS", "TRACE"):
            with self.subTest(verb=verb):
                status, raw, headers = self.request(verb, "/api/skills")
                self.assertEqual(status, 405)
                self.assertEqual(headers.get("Allow"),
                                 "GET, HEAD, POST, PATCH, PUT, DELETE")
                self.assertEqual(json.loads(raw)["error"], "method not allowed")
                for header in SECURITY_HEADERS:
                    self.assertIn(header, headers)

    def test_an_encoded_separator_cannot_smuggle_a_traversal(self):
        """Segments are URL-decoded one at a time before the name guard."""
        status, raw, headers = self.request("GET", "/api/skills/..%2f..%2fetc%2fpasswd/raw")
        self.assertIn(status, (400, 404))
        self.assertIn(json.loads(raw)["code"], ("bad_request", "not_found",
                                                "skill_not_found"))

    def test_doctor_explain_nests_its_own_report(self):
        """``explain`` is nested under the ordinary Doctor payload."""
        status, raw, _ = self.request("GET", "/api/doctor?explain=bogus")
        self.assertEqual(status, 200)
        report = json.loads(raw)["explain"]
        self.assertEqual(report["resolution"], "unknown-consumer")
        self.assertIn("known_consumers", report)
        # The diagnostic writes nothing and never claims a persisted winner.
        self.assertIs(report["read_only"], True)
        self.assertIs(report["persists_nothing"], True)
        self.assertEqual(report["effective_state"], "unresolved")

        status, raw, _ = self.request(
            "GET", "/api/doctor?explain=claude-code&project=/nope")
        self.assertEqual(status, 200)
        report = json.loads(raw)["explain"]
        self.assertEqual(report["resolution"], "missing-project")

    def test_a_get_does_not_create_anything_on_disk(self):
        """D3-4: reads create no files, no database, no layout."""
        data_dir = Path(os.environ["SKILLS_MANAGER_DATA"])
        before = sorted(p.name for p in data_dir.iterdir()) if data_dir.is_dir() else []
        for path in ("/api/skills", "/api/stats", "/api/doctor", "/api/history",
                     "/api/tokens", "/api/trash", "/api/search?q=demo"):
            self.request("GET", path)
        after = sorted(p.name for p in data_dir.iterdir()) if data_dir.is_dir() else []
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()