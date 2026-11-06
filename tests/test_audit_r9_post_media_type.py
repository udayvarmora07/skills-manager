"""R9 / S4 (docs/28): bodyless mutating POSTs require ``application/json``.

``POST /api/trash/purge`` with ``text/plain`` used to answer 200 and delete
data, because only routes that parsed a body checked the media type.
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


class BodylessPostMediaType(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="r9-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.tmp / "home")
        self.addCleanup(lambda: os.environ.__setitem__("HOME", old_home) if old_home else os.environ.pop("HOME", None))
        self.store = Store(self.tmp / "data")
        self.store.init_db()
        self.server = WebAppServer(store=self.store, host="127.0.0.1", port=0)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.httpd.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.port

    def post(self, path: str, ctype: str | None) -> int:
        headers = {"Content-Type": ctype} if ctype else {}
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code

    def test_text_plain_purge_is_refused_and_deletes_nothing(self) -> None:
        self.store.create("demo", "Use when testing R9.")
        self.store.remove("demo")
        for ctype in (None, "text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x"):
            with self.subTest(ctype=ctype):
                self.assertEqual(self.post("/api/trash/purge", ctype), 415)
        self.assertEqual(len(self.store.trash_list()), 1)
        self.assertEqual(self.post("/api/trash/purge", "application/json"), 200)
        self.assertEqual(self.store.trash_list(), [])

    def test_other_bodyless_mutations_are_refused_without_json(self) -> None:
        self.store.create("demo", "Use when testing R9.")
        for path in ("/api/rebuild", "/api/resync", "/api/skills/demo/disable"):
            with self.subTest(path=path):
                self.assertEqual(self.post(path, "text/plain"), 415)
        self.assertFalse(self.store.get("demo")["disabled"])
        self.assertEqual(self.post("/api/skills/demo/disable", "application/json; charset=utf-8"), 200)


if __name__ == "__main__":
    unittest.main()
