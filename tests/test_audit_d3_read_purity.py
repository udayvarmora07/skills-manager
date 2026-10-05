"""Red-first regressions: a read must not create, repair, or hide (docs/24 §D3).

``Store.list()`` and its siblings called the same ``_init_db()`` every write
path uses, which creates the data layout, creates the SQLite file, and runs the
schema script.  On the read path that made two things true that no read should
make true:

* one ``GET /api/skills`` against a data directory that did not exist created
  five directories and a 32 KB index, so merely looking could change the disk;
* with a component of the layout replaced by a regular file, the same read
  answered ``400`` naming an internal path, leaving ``/api/scopes`` and
  ``/api/trash`` still answering 200 and the user no route back.

Both are reproduced here against the real ``Store`` and a real loopback server.
Every test fails against the pre-fix code for its own reason.
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

from skillsmgr.store import (
    SkillNotFound,
    Store,
    StoreError,
    StoreLayoutError,
)
from skillsmgr.webapp import WebAppServer


class ReadPurityTestCase(unittest.TestCase):
    """A private data root per test; no environment leakage."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.data_dir = self.root / "data"
        self._saved_env = {
            key: os.environ.get(key)
            for key in ("SKILLS_MANAGER_DATA", "XDG_DATA_HOME", "HOME")
        }
        self.addCleanup(self._restore_env)
        # Isolate HOME as well as the data root.  ``WebAppServer`` binds a Store
        # but every scope route still reads the *real* agent scope roots through
        # ``scopes.known_scopes()``, so without this ``/api/stats`` walks the
        # developer's actual ~/.claude, ~/.codex, ~/.gemini and friends -- 1,965
        # documents on this machine, 3.7 s warm, and enough under load to blow a
        # client's request timeout.  That made this test, and the pre-existing
        # ``test_web_client_contracts`` suite, flaky for a reason that has
        # nothing to do with what they assert.
        home = self.root / "home"
        home.mkdir(mode=0o700)
        os.environ["HOME"] = str(home)

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _store(self) -> Store:
        """A Store bound to the private root, without bootstrapping anything."""
        return Store(data_dir=self.data_dir)

    def seed(self, count: int = 3) -> Store:
        store = self._store()
        store.init_db()
        for i in range(count):
            store.create(f"demo-{i}", f"demo skill {i}")
        self.addCleanup(shutil.rmtree, self.data_dir, True)
        return store


class ReadDoesNotCreateTheLayoutTests(ReadPurityTestCase):
    """D3-4 half one: looking must not change the disk."""

    def test_no_skill_is_installed_and_no_directory_exists(self):
        store = self._store()
        self.assertEqual([], store.list())
        self.assertEqual([], store.search("anything"))
        self.assertEqual([], store.history())
        self.assertFalse(
            self.data_dir.exists(),
            "a read created the data directory; nothing was installed",
        )

    def test_stats_and_doctor_on_a_missing_tree_report_nothing(self):
        store = self._store()
        stats = store.stats()
        self.assertEqual(0, stats["total"])
        self.assertEqual(0, stats["active"])
        report = store.doctor()
        self.assertFalse(
            self.data_dir.exists(),
            "a read created the data directory; doctor must report, not repair",
        )
        self.assertIsInstance(report, dict)

    def test_get_reports_not_installed_without_creating_anything(self):
        store = self._store()
        with self.assertRaises(SkillNotFound):
            store.get("nothing-here")
        self.assertFalse(
            self.data_dir.exists(),
            "a read created the data directory to answer a miss",
        )

    def test_a_get_over_http_creates_nothing(self):
        store = self._store()
        server = WebAppServer(store, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        for route in ("/api/skills", "/api/stats", "/api/trash", "/api/templates"):
            with self.subTest(route=route):
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.port}{route}",
                    headers={"Host": f"127.0.0.1:{server.port}"},
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    self.assertEqual(200, response.status)
                    json.loads(response.read())
        self.assertFalse(
            self.data_dir.exists(),
            "a GET created the data directory and its SQLite index",
        )


class BrokenLayoutIsReportedNotHiddenTests(ReadPurityTestCase):
    """D3-4 half two: a damaged layout gets a repair hint, not an internal path."""

    def _break_skills_dir(self) -> Store:
        store = self._store()
        store.init_db()
        self.addCleanup(shutil.rmtree, self.data_dir, True)
        shutil.rmtree(store.skills_dir)
        store.skills_dir.write_text("not a directory", encoding="utf-8")
        return store

    def test_reads_fail_with_a_repairable_layout_error(self):
        store = self._break_skills_dir()
        for label, call in (
            ("list", store.list),
            ("search", lambda: store.search("x")),
            ("get", lambda: store.get("anything")),
            ("stats", store.stats),
        ):
            with self.subTest(read=label):
                with self.assertRaises(StoreLayoutError) as caught:
                    call()
                message = str(caught.exception)
                self.assertIn(str(store.skills_dir), message)
                self.assertIn(
                    "mv", message,
                    "the error must name the fix, not only the condition",
                )

    def test_the_layout_error_is_still_a_store_error(self):
        store = self._break_skills_dir()
        with self.assertRaises(StoreError):
            store.list()

    def test_it_never_reports_the_readers_own_error_text(self):
        """Before the fix this was the interpreter's `mkdir_private` message."""
        store = self._break_skills_dir()
        with self.assertRaises(StoreError) as caught:
            store.list()
        self.assertNotIn("cannot create directory below non-directory",
                         str(caught.exception))

    def test_every_broken_route_answers_the_same_status_and_shape(self):
        """The UI used to be half-broken: /api/scopes still answered 200."""
        store = self._break_skills_dir()
        server = WebAppServer(store, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        seen = {}
        for route in ("/api/skills", "/api/stats", "/api/doctor", "/api/search?q=x"):
            with self.subTest(route=route):
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.port}{route}",
                    headers={"Host": f"127.0.0.1:{server.port}"},
                )
                try:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        seen[route] = (response.status, response.read())
                except urllib.error.HTTPError as error:
                    seen[route] = (error.code, error.read())
        self.assertTrue(seen)
        statuses = {route: status for route, (status, _) in seen.items()}
        self.assertEqual(
            {404}, set(statuses.values()),
            f"a broken layout must not answer a mixture of statuses: {statuses}",
        )
        for route, (status, body) in seen.items():
            with self.subTest(route=route):
                payload = json.loads(body)
                self.assertIn("error", payload)
                self.assertIn("skills", payload["error"])


class ReadsStayAuthoritativeAfterAWriteTests(ReadPurityTestCase):
    """The read-only bootstrap must not stop normal reads from working."""

    def test_a_seeded_store_reads_exactly_as_before(self):
        store = self.seed()
        names = [row["name"] for row in store.list()]
        self.assertEqual(["demo-0", "demo-1", "demo-2"], names)
        self.assertEqual(3, store.stats()["active"])
        self.assertEqual(1, len(store.search("demo-0")))
        self.assertTrue(store.doctor()["ok"])
        self.assertEqual(3, len(store.history()))

    def test_a_row_whose_directory_disappeared_is_still_filtered(self):
        store = self.seed()
        shutil.rmtree(store.skills_dir / "demo-1")
        self.assertEqual(["demo-0", "demo-2"], [r["name"] for r in store.list()])

    def test_a_deleted_index_is_reported_not_silently_rebuilt_on_read(self):
        store = self.seed()
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(str(store.db_path) + suffix).unlink(missing_ok=True)
        # The filesystem is still the source of truth, so the skills are still
        # there; a read must not resurrect the index behind the user's back.
        self.assertEqual([], store.list())
        self.assertFalse(store.db_path.exists(), "a read rebuilt the index file")
        # ... and the next write brings it back.
        store.create("demo-9", "written after the index was removed")
        self.assertIn("demo-9", [row["name"] for row in store.list()])

    def test_doctor_tells_the_user_to_rebuild_a_missing_index(self):
        store = self.seed()
        store.db_path.unlink(missing_ok=True)
        report = store.doctor()
        self.assertFalse(report["ok"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()