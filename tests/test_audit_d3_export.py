"""Red-first regressions: downloading an export must not grow the store
(docs/24 §D3-3).

``GET /api/export`` called ``Store.export()`` with no destination, so every
request created ``<data>/backups/export-<timestamp>.tar.gz`` and never removed
it.  ``backups/`` has no retention (``snapshots/`` keeps ``SNAPSHOT_KEEP = 5``),
so a browser prefetch, a retry, or a double click grows the directory
permanently with archives the user never asked to keep.  Measured before the
fix: four requests, four files.

The CLI's ``export``/``backup`` command is a *different* contract -- it names
the file it wrote and the user is meant to keep it -- so it is pinned here as
unchanged rather than "fixed" too.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


class ExportDownloadTests(unittest.TestCase):
    """`GET /api/export` is a read: it leaves nothing behind in the data dir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._saved = {k: os.environ.get(k) for k in ("SKILLS_MANAGER_DATA", "HOME")}
        self.addCleanup(self._restore)
        home = Path(self._tmp.name) / "home"
        home.mkdir(mode=0o700)
        os.environ["HOME"] = str(home)
        self.store = Store(data_dir=Path(self._tmp.name) / "data")
        self.store.init_db()
        for index in range(3):
            self.store.create(f"demo-{index}", f"demo skill {index}", body="body text\n")
        self.server = WebAppServer(self.store, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)

    def _restore(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _get(self, path: str):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.port}{path}",
            headers={"Host": f"127.0.0.1:{self.server.port}"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, dict(response.headers), response.read()

    def _backups(self) -> list[Path]:
        if not self.store.backups_dir.is_dir():
            return []
        return sorted(p for p in self.store.backups_dir.iterdir() if p.is_file())

    def test_repeated_downloads_leave_nothing_in_backups(self):
        for index in range(4):
            with self.subTest(request=index):
                status, headers, body = self._get("/api/export")
                self.assertEqual(200, status)
                self.assertTrue(body, "the download was empty")
                self.assertEqual(len(body), int(headers["Content-Length"]))
        self.assertEqual(
            [], self._backups(),
            "GET /api/export wrote archives into <data>/backups",
        )

    def test_the_download_is_a_real_archive_with_every_skill(self):
        import io
        import tarfile

        status, headers, body = self._get("/api/export")
        self.assertEqual(200, status)
        self.assertIn("attachment;", headers["Content-Disposition"])
        with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tar:
            names = {m.name for m in tar.getmembers()}
        for index in range(3):
            self.assertIn(f"skills/demo-{index}/SKILL.md", names)

    def test_the_full_export_download_still_works_and_leaves_nothing(self):
        self.store.remove("demo-2")
        status, _, body = self._get("/api/export?full=1")
        self.assertEqual(200, status)
        self.assertTrue(body)
        self.assertEqual([], self._backups())

    def test_head_reports_the_length_without_a_body(self):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.port}/api/export",
            headers={"Host": f"127.0.0.1:{self.server.port}"},
            method="HEAD",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            self.assertEqual(200, response.status)
            self.assertGreater(int(response.headers["Content-Length"]), 0)
            self.assertEqual(b"", response.read())
        self.assertEqual([], self._backups())

    def test_a_non_global_scope_export_is_still_refused(self):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.port}/api/export?scope=agents",
            headers={"Host": f"127.0.0.1:{self.server.port}"},
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=30)
        self.assertEqual(400, caught.exception.code)


class CliExportStillWritesItsArchiveTests(unittest.TestCase):
    """The CLI export is a different contract and must not change."""

    def test_export_with_no_destination_still_lands_in_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(data_dir=Path(tmp) / "data")
            store.init_db()
            store.create("kept", "a skill the user asked to back up")
            archive = store.export()
            self.assertTrue(archive.is_file())
            self.assertEqual(store.backups_dir, archive.parent)
            self.assertTrue(archive.name.startswith("export-"))

    def test_two_exports_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(data_dir=Path(tmp) / "data")
            store.init_db()
            store.create("kept", "a skill")
            first = store.export()
            second = store.export()
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_file() and second.is_file())

    def test_an_explicit_destination_is_honoured_and_leaves_no_archive(self):
        """An explicit destination writes there, and `backups/` holds no archive.

        It does **not** assert that `backups/` is absent: `export()` is one of
        the documented write entry points, so it bootstraps the layout (see
        docs/04-store-api.md).  That is a one-time empty directory, which is a
        different thing from the per-request archives this closes.
        """
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(data_dir=Path(tmp) / "data")
            store.init_db()
            store.create("kept", "a skill")
            shutil.rmtree(store.backups_dir)
            target = Path(tmp) / "elsewhere" / "mine.tar.gz"
            archive = store.export(dest=target)
            self.assertEqual(target, archive)
            self.assertTrue(archive.is_file())
            leftovers = (
                sorted(p.name for p in store.backups_dir.iterdir())
                if store.backups_dir.is_dir()
                else []
            )
            self.assertEqual(
                [], leftovers,
                "an export to an explicit destination left an archive in backups/",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()