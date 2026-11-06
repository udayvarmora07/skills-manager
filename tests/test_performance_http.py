"""HTTP contracts for lightweight lists, shared scans and the v2 entry URL."""

from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from skillsmgr import scopes
from skillsmgr.store import Store
from smoke_fixtures import start_server, stop_server


class PerformanceHTTPTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="perf-http-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        home = root / "home"
        home.mkdir()
        environment = mock.patch.dict(os.environ, {
            "HOME": str(home), "SKILLS_MANAGER_DATA": str(root / "data"),
        })
        environment.start()
        self.addCleanup(environment.stop)
        cwd = mock.patch.object(scopes, "_cwd", return_value=home)
        cwd.start()
        self.addCleanup(cwd.stop)
        self.store = Store()
        self.store.init_db()
        store_token = scopes._GLOBAL_STORE.set(self.store)
        self.addCleanup(scopes._GLOBAL_STORE.reset, store_token)
        self.store.create("alpha", "First skill", body="ONLY_IN_THE_BODY\n" + "x" * 4096)
        self.store.create("beta", "Second skill", body="A different document")
        agent = home / ".codex" / "skills" / "alpha"
        agent.mkdir(parents=True)
        agent.joinpath("SKILL.md").write_bytes(
            (self.store.skills_dir / "alpha" / "SKILL.md").read_bytes()
        )
        self.server, self.thread = start_server(self.store)
        self.addCleanup(stop_server, self.server, self.thread)

    def request(self, path, method="GET"):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=10)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            data = response.read()
            headers = dict(response.getheaders())
            return response.status, headers, data
        finally:
            connection.close()

    def rows(self, path):
        status, headers, data = self.request(path)
        self.assertEqual(status, 200, data[:300])
        return headers, json.loads(data)

    def test_projection_preserves_other_fields_and_the_default_keeps_bodies(self):
        for scope in ("global", "all", "codex"):
            with self.subTest(scope=scope):
                _, full = self.rows(f"/api/skills?scope={scope}")
                _, explicit = self.rows(f"/api/skills?scope={scope}&body=1")
                _, light = self.rows(f"/api/skills?scope={scope}&body=0")
                self.assertTrue(full)
                if scope == "codex":
                    self.assertIn("ONLY_IN_THE_BODY", full[0]["body"])
                self.assertTrue(all("body" not in row for row in light))
                # Read-time timestamps can change between requests.
                def stable(rows):
                    return [{key: value for key, value in row.items()
                             if key not in ("body", "observed_at")} for row in rows]
                self.assertEqual(stable(full), stable(explicit))
                self.assertEqual(stable(full), stable(light))
                if scope in ("all", "codex"):
                    self.assertGreater(len(json.dumps(full)) - len(json.dumps(light)), 4000)

    def test_body_search_still_matches_when_the_response_omits_bodies(self):
        for scope in ("global", "all", "codex"):
            with self.subTest(scope=scope):
                _, rows = self.rows(f"/api/skills?scope={scope}&q=ONLY_IN_THE_BODY&body=0")
                self.assertTrue(rows)
                self.assertEqual({row["name"] for row in rows}, {"alpha"})
                self.assertTrue(all("body" not in row for row in rows))

    def test_pagination_and_head_describe_the_projected_response(self):
        path = "/api/skills?scope=all&body=0&limit=1&offset=1"
        status, headers, data = self.request(path)
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Total-Count"], "3")
        self.assertEqual(len(json.loads(data)), 1)
        self.assertNotIn("body", json.loads(data)[0])
        head_status, head_headers, head_body = self.request(path, "HEAD")
        self.assertEqual(head_status, 200)
        self.assertEqual(head_body, b"")
        self.assertEqual(head_headers["X-Total-Count"], "3")
        self.assertEqual(int(head_headers["Content-Length"]), len(data))

    def test_empty_projected_page_is_an_empty_array(self):
        headers, rows = self.rows("/api/skills?scope=all&body=0&offset=999")
        self.assertEqual(rows, [])
        self.assertEqual(headers["X-Total-Count"], "3")

    def test_detail_and_later_lists_keep_the_document_after_projection(self):
        _, before = self.rows("/api/skills?scope=all")
        self.rows("/api/skills?scope=all&body=0")
        _, detail = self.rows("/api/skills/alpha?scope=codex")
        self.assertIn("ONLY_IN_THE_BODY", detail["body"])
        _, full = self.rows("/api/skills?scope=all")
        self.assertEqual([(row["scope"], row["name"], row.get("body")) for row in full],
                         [(row["scope"], row["name"], row.get("body")) for row in before])

    def test_bad_or_repeated_body_flags_are_rejected_before_scanning(self):
        with mock.patch.object(scopes, "list_all", side_effect=AssertionError("unexpected scan")):
            for value in ("", "false", "2", "-1", "0&body=1", "1&body=0"):
                with self.subTest(value=value):
                    status, _, data = self.request("/api/skills?scope=all&body=" + value)
                    self.assertEqual(status, 400, data[:300])
                    payload = json.loads(data)
                    self.assertEqual(payload["code"], "bad_request")
                    self.assertIn("body", payload["error"])

    def test_scope_summary_matches_a_fresh_scan_and_refreshes_after_an_edit(self):
        expected = scopes.list_scopes()
        _, actual = self.rows("/api/scopes")
        self.assertEqual(actual, expected)
        self.store.create("gamma", "Fresh filesystem entry", body="New document")
        _, fresh = self.rows("/api/scopes")
        global_scope = next(row for row in fresh if row["id"] == "global")
        self.assertEqual(global_scope["count"], 3)
        self.assertEqual(fresh, scopes.list_scopes())

    def test_scope_summary_includes_unindexed_global_documents(self):
        directory = self.store.skills_dir / "unindexed"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\nname: unindexed\ndescription: A filesystem-only skill.\n---\nBody\n",
            encoding="utf-8",
        )
        _, summary = self.rows("/api/scopes")
        self.assertEqual(next(row for row in summary if row["id"] == "global")["count"], 3)
        self.assertEqual(summary, scopes.list_scopes())

    def test_scope_summary_does_not_require_or_repair_the_index(self):
        original = self.store.db_path.read_bytes()
        expected = scopes.list_scopes()
        for condition in ("missing", "corrupt"):
            with self.subTest(index=condition):
                if condition == "missing":
                    self.store.db_path.unlink()
                else:
                    self.store.db_path.write_bytes(b"not a SQLite database")
                try:
                    _, summary = self.rows("/api/scopes")
                    self.assertEqual(summary, expected)
                    if condition == "missing":
                        self.assertFalse(self.store.db_path.exists())
                    else:
                        self.assertEqual(self.store.db_path.read_bytes(), b"not a SQLite database")
                finally:
                    self.store.db_path.write_bytes(original)

    def test_overlapping_startup_routes_share_a_scan_without_losing_bodies(self):
        original = scopes._list_all_uncached
        scan_started = threading.Event()
        release_scan = threading.Event()
        calls = []

        def blocked_scan(**kwargs):
            calls.append(1)
            scan_started.set()
            if not release_scan.wait(5):
                raise TimeoutError("test did not release the shared scan")
            return original(**kwargs)

        with mock.patch.object(scopes, "_list_all_uncached", side_effect=blocked_scan):
            with ThreadPoolExecutor(max_workers=3) as executor:
                requests = [executor.submit(self.rows, path) for path in (
                    "/api/skills?scope=all&body=0", "/api/scopes", "/api/stats",
                )]
                try:
                    self.assertTrue(scan_started.wait(5))
                    # The real coalescer joins all three HTTP requests. Poll a
                    # bounded condition instead of relying on scheduler sleep.
                    import time
                    deadline = time.monotonic() + 5
                    joined = False
                    while time.monotonic() < deadline:
                        with scopes._SCOPE_READ_FLIGHTS_LOCK:
                            joined = any(flight.get("waiters", 0) == 2
                                         for flight in scopes._SCOPE_READ_FLIGHTS.values())
                        if joined:
                            break
                        time.sleep(0.005)
                    self.assertTrue(joined, "startup routes did not join one scan")
                finally:
                    release_scan.set()
                light, summary, stats = [future.result(timeout=10)[1] for future in requests]
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(light), 3)
        self.assertTrue(all("body" not in row for row in light))
        self.assertEqual(sum(row["count"] for row in summary), 3)
        self.assertEqual(stats["all_total"], 3)
        self.assertEqual(stats["all_tokens"], sum(row["tokens"] for row in summary))
        _, full = self.rows("/api/skills?scope=all")
        self.assertIn("ONLY_IN_THE_BODY", next(row for row in full if row["scope"] == "codex")["body"])

    def test_v2_redirect_keeps_query_parameters_and_is_always_local(self):
        for path in ("/v2", "/v2?window=claude&next=https%3A%2F%2Fexample.invalid"):
            with self.subTest(path=path):
                status, headers, data = self.request(path)
                self.assertEqual(status, 308)
                self.assertEqual(data, b"")
                self.assertEqual(headers["Location"], path.replace("/v2", "/v2/", 1))
                self.assertEqual(headers["Content-Length"], "0")
                self.assertIn("Content-Security-Policy", headers)
                self.assertEqual(self.request(headers["Location"])[0], 200)

    def test_head_redirects_without_a_body_and_v2_assets_stay_distinct(self):
        status, headers, data = self.request("/v2?window=claude", "HEAD")
        self.assertEqual(status, 308)
        self.assertEqual(headers["Location"], "/v2/?window=claude")
        self.assertEqual(data, b"")
        status, _, page = self.request("/v2/")
        self.assertEqual(status, 200)
        self.assertIn(b"model.js", page)
        assets = Path(__file__).resolve().parents[1] / "skillsmgr" / "webui"
        self.assertEqual(self.request("/v2/model.js")[2], (assets / "v2/model.js").read_bytes())
        self.assertEqual(self.request("/domain.js")[2], (assets / "domain.js").read_bytes())
        self.assertEqual(self.request("/v2/%2e%2e/%2e%2e/AGENTS.md")[0], 404)


if __name__ == "__main__":
    unittest.main()
