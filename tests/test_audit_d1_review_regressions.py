"""Red-first regressions for the self-review of docs/24 §D1 / §D3-4.

An independent review of commits ``cfdf56a`` and ``b258c23`` found six real
defects in the fix itself.  Each is reproduced here against the tree that
carries the fix, and each test fails because the defect is present -- not
because a name is missing.

  F1  a partially-created index answers HTTP 500 with the driver's own text
  F2  a write path still emits the interpreter text the fix promised to remove,
      and the new docstring/docs claim it does not
  F3  two routes answer 200 beside four that answer 404 for the same broken
      layout, so "every route answers the same status" is false
  F5  ``_check_store_layout`` uses ``Path.exists()``, so a *dangling symlink*
      at a layout component reads as "nothing installed" and an entire library
      behind one is reported as empty
  F6  ``doctor()["repair"]`` has no reader, so the promised repair line is
      never shown to anybody
  F8  ``_coalesced_read`` leaks an in-flight entry on ``BaseException``, so one
      Ctrl-C permanently wedges that endpoint
"""

from __future__ import annotations

import io
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr
from pathlib import Path

from skillsmgr import store as store_mod
from skillsmgr.store import Store, StoreError, StoreLayoutError, _coalesced_read

MINIMAL_SKILLS_TABLE = """
CREATE TABLE skills (
  name TEXT PRIMARY KEY, status TEXT, description TEXT, body TEXT,
  category TEXT, license TEXT, version TEXT, disabled INTEGER,
  added_at TEXT, updated_at TEXT
);
"""


class ReviewTestCase(unittest.TestCase):
    """A private data root and a private HOME per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.data_dir = self.root / "data"
        self._saved = {k: os.environ.get(k) for k in ("SKILLS_MANAGER_DATA", "HOME")}
        self.addCleanup(self._restore)
        home = self.root / "home"
        home.mkdir(mode=0o700)
        os.environ["HOME"] = str(home)
        os.environ["SKILLS_MANAGER_DATA"] = str(self.data_dir)
        self.store = Store()
        self.store.init_db()

    def _restore(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def serve(self):
        from skillsmgr.webapp import WebAppServer

        server = WebAppServer(self.store, port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return server

    def get(self, server, path):
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.port}{path}",
            headers={"Host": f"127.0.0.1:{server.port}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()


class PartialIndexTests(ReviewTestCase):
    """F1 — the index probe checks one table; queries touch more than one."""

    def _skills_only_index(self) -> None:
        self.store.create("demo", "a demo skill")
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(str(self.store.db_path) + suffix).unlink(missing_ok=True)
        conn = sqlite3.connect(self.store.db_path)
        try:
            conn.executescript(MINIMAL_SKILLS_TABLE)
            conn.commit()
        finally:
            conn.close()

    def test_history_does_not_raise_a_raw_driver_error(self):
        self._skills_only_index()
        server = self.serve()
        status, body = self.get(server, "/api/history?limit=5")
        self.assertNotEqual(
            500, status,
            f"a partial index produced an unhandled 500: {body[:160]!r}",
        )

    def test_no_sqlite_error_text_reaches_the_client(self):
        self._skills_only_index()
        server = self.serve()
        for path in ("/api/history?limit=5", "/api/skills", "/api/stats", "/api/doctor"):
            with self.subTest(path=path):
                status, body = self.get(server, path)
                self.assertNotIn(b"no such table", body)
                self.assertNotIn(b"OperationalError", body)
                self.assertNotEqual(500, status)

    def test_it_is_a_clean_store_error_naming_the_repair(self):
        self._skills_only_index()
        with self.assertRaises(StoreError) as caught:
            self.store.history(limit=5)
        self.assertIn("db rebuild", str(caught.exception))

    def test_the_driver_error_never_escapes_the_store(self):
        """`_connect`'s contract is that no sqlite3.Error reaches a caller."""
        self._skills_only_index()
        with self.assertRaises(StoreError):
            self.store.history(limit=5)


class WritePathLayoutTests(ReviewTestCase):
    """F2 — the write path must not emit the text the fix promised to remove."""

    def _break_skills_dir(self) -> None:
        shutil.rmtree(self.store.skills_dir)
        self.store.skills_dir.write_text("not a directory", encoding="utf-8")

    def test_a_write_raises_the_same_named_error_as_a_read(self):
        self._break_skills_dir()
        with self.assertRaises(StoreLayoutError):
            self.store.create("new-skill", "a skill")

    def test_a_write_does_not_leak_the_interpreter_text(self):
        self._break_skills_dir()
        for label, call in (
            ("create", lambda: self.store.create("new-skill", "a skill")),
            ("remove", lambda: self.store.remove("demo")),
            ("resync", self.store.resync),
        ):
            with self.subTest(call=label):
                with self.assertRaises(StoreError) as caught:
                    call()
                self.assertNotIn("cannot create directory below non-directory",
                                 str(caught.exception))

    def test_a_write_route_answers_with_the_same_status_as_a_read(self):
        self._break_skills_dir()
        server = self.serve()
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.port}/api/rebuild",
            data=b"",
            headers={"Host": f"127.0.0.1:{server.port}"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=20)
        self.assertNotIn(b"cannot create directory below non-directory", caught.exception.read())


class EveryRouteSeesTheSameLayoutErrorTests(ReviewTestCase):
    """F3 — no route may answer 200 beside the routes that answer 404."""

    ROUTES = ("/api/skills", "/api/stats", "/api/doctor", "/api/search?q=x",
              "/api/scopes", "/api/trash", "/api/history")

    def _break_skills_dir(self) -> None:
        shutil.rmtree(self.store.skills_dir)
        self.store.skills_dir.write_text("not a directory", encoding="utf-8")

    def test_every_route_answers_the_same_status(self):
        self.store.create("demo", "a demo skill")
        self._break_skills_dir()
        server = self.serve()
        statuses = {}
        for path in self.ROUTES:
            with self.subTest(path=path):
                statuses[path] = self.get(server, path)[0]
        self.assertEqual(
            {404}, set(statuses.values()),
            f"a broken layout answered a mixture of statuses: {statuses}",
        )


class DanglingLayoutLinkTests(ReviewTestCase):
    """F5 — `Path.exists()` follows links, so a dangling one reads as absent."""

    def _make_dangling(self) -> None:
        self.store.create("demo", "a demo skill")
        shutil.rmtree(self.store.skills_dir)
        os.symlink(str(self.store.data_dir / "nowhere-at-all"), str(self.store.skills_dir))

    def test_a_dangling_layout_link_is_a_layout_error_not_an_empty_library(self):
        self._make_dangling()
        with self.assertRaises(StoreLayoutError):
            self.store.list()

    def test_every_read_reports_it_rather_than_reporting_nothing_installed(self):
        self._make_dangling()
        for label, call in (
            ("list", self.store.list),
            ("search", lambda: self.store.search("x")),
            ("stats", self.store.stats),
            ("history", self.store.history),
            ("doctor", self.store.doctor),
            ("scopes", __import__("skillsmgr.scopes", fromlist=["x"]).list_scopes),
        ):
            with self.subTest(read=label):
                with self.assertRaises(StoreLayoutError):
                    call()

    def test_the_message_names_the_path(self):
        self._make_dangling()
        with self.assertRaises(StoreLayoutError) as caught:
            self.store.list()
        self.assertIn(str(self.store.skills_dir), str(caught.exception))


class DoctorRepairIsReadableTests(ReviewTestCase):
    """F6 — a field with no reader is a promise nobody keeps."""

    def test_the_repair_line_names_the_command_a_user_can_run(self):
        self.store.create("demo", "a demo skill")
        self.store.db_path.unlink(missing_ok=True)
        report = self.store.doctor()
        self.assertTrue(report["repair"], "doctor reported drift with no repair guidance")
        self.assertTrue(
            any("db rebuild" in line for line in report["repair"]),
            f"the repair line does not name a command: {report['repair']}",
        )

    def test_the_cli_prints_it(self):
        script = (
            "import os, sys\n"
            f"os.environ['SKILLS_MANAGER_DATA'] = {str(self.data_dir)!r}\n"
            f"sys.path.insert(0, {str(Path(__file__).resolve().parents[1])!r})\n"
            "from skillsmgr.store import Store\n"
            "store = Store()\n"
            "store.init_db()\n"
            "store.create('demo', 'a demo skill')\n"
            "store.db_path.unlink(missing_ok=True)\n"
            "from skillsmgr.cli import main\n"
            "sys.exit(main(['doctor']))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        output = proc.stdout + proc.stderr
        self.assertIn(
            "db rebuild", output,
            f"the CLI never showed the repair it computed:\n{output}",
        )
        self.assertNotIn("database integrity check failed", output)

    def test_an_unindexed_store_is_not_reported_as_a_failed_integrity_check(self):
        self.store.create("demo", "a demo skill")
        self.store.db_path.unlink(missing_ok=True)
        report = self.store.doctor()
        self.assertEqual(
            "unindexed", report["db_integrity"],
            "a store whose index was never built is not an integrity failure",
        )
        self.assertFalse(report["ok"])


class CoalescedReadInterruptTests(unittest.TestCase):
    """F8 — one Ctrl-C used to wedge the endpoint forever."""

    def test_a_base_exception_does_not_leak_the_in_flight_entry(self):
        flights: dict = {}
        lock = threading.Lock()

        def interrupted():
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            _coalesced_read(flights, lock, ("list",), interrupted)
        self.assertEqual(
            {}, flights,
            "the flight survived the interrupt, so the next caller waits forever",
        )

    def test_the_next_caller_after_an_interrupt_still_reads(self):
        flights: dict = {}
        lock = threading.Lock()
        entered = threading.Event()
        results: list = []

        def interrupted():
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            _coalesced_read(flights, lock, ("list",), interrupted)

        def read():
            entered.set()
            results.append(_coalesced_read(flights, lock, ("list",), lambda: ["ok"]))

        worker = threading.Thread(target=read, daemon=True)
        worker.start()
        self.assertTrue(entered.wait(timeout=5))
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive(), "the reader after an interrupt hung")
        self.assertEqual([["ok"]], results)


class ExportReadPurityTests(ReviewTestCase):
    """F4 — `GET /api/export` still bootstrapped the whole layout."""

    def test_a_download_on_a_missing_data_dir_creates_nothing(self):
        shutil.rmtree(self.data_dir)
        server = self.serve()
        status, _ = self.get(server, "/api/export")
        self.assertEqual(200, status)
        created = sorted(p.name for p in self.data_dir.iterdir()) if self.data_dir.exists() else []
        self.assertEqual(
            [], created,
            f"GET /api/export created {created} in a data directory that did not exist",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()