"""Red-first regressions: a list route needs a real paging contract
(docs/24 §D3-9).

``GET /api/skills`` had none.  ``?limit=5``, ``?offset=3``, ``?page=2``,
``?per_page=2`` and ``?cursor=abc`` were **all silently ignored** and the same
full row set came back every time -- about 1 MB at 1,000 skills.  A client that
paged and got everything could not tell its request had been ignored, which is
the same defect §D3-8 closed for scalars.

The paging contract is **opt-in**: the web UI asks for ``/api/skills?scope=all``
with no paging parameters and needs every row, so an unpaged request keeps
returning everything.  What changes is that a *paging* parameter which is
supplied is honoured, and one which is not implemented is refused rather than
ignored.
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

from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


class PagingTests(unittest.TestCase):
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
        for index in range(12):
            self.store.create(f"skill-{index:02d}", f"demo skill {index}")
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
                return response.status, dict(response.headers), json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, dict(error.headers), json.loads(error.read())

    def test_limit_bounds_the_rows(self):
        status, _, rows = self.get("/api/skills?limit=5")
        self.assertEqual(200, status)
        self.assertEqual(5, len(rows))
        self.assertEqual("skill-00", rows[0]["name"])

    def test_offset_skips_rows(self):
        status, _, rows = self.get("/api/skills?offset=10")
        self.assertEqual(200, status)
        self.assertEqual(2, len(rows))
        self.assertEqual("skill-10", rows[0]["name"])

    def test_limit_and_offset_page_together(self):
        status, _, rows = self.get("/api/skills?limit=3&offset=4")
        self.assertEqual(200, status)
        self.assertEqual(["skill-04", "skill-05", "skill-06"],
                         [r["name"] for r in rows])

    def test_total_count_is_reported_and_is_the_unpaged_total(self):
        _, headers, _ = self.get("/api/skills?limit=2")
        self.assertEqual("12", headers["X-Total-Count"])
        _, headers, rows = self.get("/api/skills")
        self.assertEqual("12", headers["X-Total-Count"])
        self.assertEqual(12, len(rows))

    def test_an_offset_past_the_end_is_an_empty_page_not_an_error(self):
        status, _, rows = self.get("/api/skills?offset=999")
        self.assertEqual(200, status)
        self.assertEqual([], rows)

    def test_paging_works_on_every_scope(self):
        for query in ("", "&scope=global", "&scope=all"):
            with self.subTest(scope=query or "(default)"):
                _, headers, rows = self.get(f"/api/skills?limit=3{query}")
                self.assertEqual(3, len(rows))
                self.assertIn("X-Total-Count", headers)

    def test_paging_works_with_a_search_query(self):
        status, _, rows = self.get("/api/skills?q=skill&limit=4")
        self.assertEqual(200, status)
        self.assertEqual(4, len(rows))

    def test_an_unpaged_request_still_returns_everything(self):
        """The web UI depends on this; paging is opt-in, not a default cap."""
        _, _, rows = self.get("/api/skills")
        self.assertEqual(12, len(rows))

    def test_an_unimplemented_paging_parameter_is_refused_not_ignored(self):
        for name in ("page", "per_page", "cursor", "before", "after", "start"):
            with self.subTest(param=name):
                status, _, payload = self.get(f"/api/skills?{name}=2")
                self.assertEqual(400, status, f"?{name}=2 was silently ignored")
                self.assertIn(name, payload["error"])

    def test_the_error_says_what_is_supported(self):
        _, _, payload = self.get("/api/skills?page=2")
        self.assertIn("limit", payload["error"])
        self.assertIn("offset", payload["error"])

    def test_a_bad_limit_is_a_400(self):
        for value in ("abc", "-1", "0", "1.5"):
            with self.subTest(limit=value):
                status, _, _ = self.get(f"/api/skills?limit={value}")
                self.assertEqual(400, status)

    def test_an_absurd_limit_is_bounded_not_honoured(self):
        _, headers, rows = self.get("/api/skills?limit=100000000")
        self.assertEqual(12, len(rows))
        self.assertEqual("12", headers["X-Total-Count"])

    def test_a_page_is_materially_smaller_than_the_whole_list(self):
        def size(path):
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.server.port}{path}",
                headers={"Host": f"127.0.0.1:{self.server.port}"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read()

        paged, whole = size("/api/skills?limit=3"), size("/api/skills")
        self.assertEqual(3, len(json.loads(paged)))
        self.assertEqual(12, len(json.loads(whole)))
        self.assertLess(
            len(paged) * 3, len(whole),
            "paging three of twelve rows should cost well under a third of them",
        )

    def test_head_reports_the_total_without_a_body(self):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.port}/api/skills?limit=3",
            headers={"Host": f"127.0.0.1:{self.server.port}"},
            method="HEAD",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            self.assertEqual(200, response.status)
            self.assertEqual("12", response.headers["X-Total-Count"])
            self.assertEqual(b"", response.read())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()