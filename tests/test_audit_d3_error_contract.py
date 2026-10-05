"""Red-first regressions: the last three error-contract gaps (docs/24 §D3).

  D3-6  ``get()`` and ``list()`` disagree about a skill whose directory is
        gone, and the REST route served the deleted document's stored body.
  D3-7  two error-body shapes: 39 routes emit ``{"error": ...}`` while the
        source-update family emits ``{"code", "error"}``, so a client cannot
        branch on one key.
  D3-12 the web server binds the *unstripped* host while the policy checks the
        normalised one, so a host that passes validation then raises a raw
        ``gaierror``.

Each was reproduced on the live server first:

```text
GET /api/skills        -> 200 ['kept']            # the row is correctly omitted
GET /api/skills/gone   -> 200 installed=False  body="# gone\\n"
GET /api/skills/nope   -> 404 keys=['error']
host='127.0.0.1 '      -> gaierror: [Errno -2] Name or service not known
host='::1'             -> gaierror: [Errno -9] Address family ... not supported
```
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

from skillsmgr.store import Store, StoreError
from skillsmgr.webapp import WebAppServer


class RestErrorContractTestCase(unittest.TestCase):
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

    def _restore(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def serve(self):
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


class DeletedSkillTests(RestErrorContractTestCase):
    """D3-6 — one skill, one answer, whichever way it is asked for."""

    def setUp(self):
        super().setUp()
        self.store.create("gone", "a skill whose directory will disappear")
        self.store.create("kept", "a skill that stays")
        shutil.rmtree(self.store.skills_dir / "gone")
        self.server = self.serve()

    def test_the_deleted_skill_is_a_404_like_every_other_route(self):
        status, body = self.get(self.server, "/api/skills/gone")
        self.assertEqual(404, status)
        self.assertIn("error", json.loads(body))

    def test_the_deleted_skills_stored_body_is_never_served(self):
        _, body = self.get(self.server, "/api/skills/gone")
        self.assertNotIn(b"# gone", body)

    def test_it_agrees_with_the_list_route(self):
        listed = json.loads(self.get(self.server, "/api/skills")[1])
        self.assertEqual(["kept"], [r["name"] for r in listed])
        self.assertEqual(404, self.get(self.server, "/api/skills/gone")[0])

    def test_an_installed_skill_is_unaffected(self):
        status, body = self.get(self.server, "/api/skills/kept")
        self.assertEqual(200, status)
        record = json.loads(body)
        self.assertTrue(record["installed"])
        self.assertIn("body", record)

    def test_doctor_still_reports_the_stale_row(self):
        """404 for a reader must not hide the drift from the tool that finds it."""
        report = self.store.doctor()
        self.assertIn("gone", report["stale_rows"])
        self.assertFalse(report["ok"])

    def test_the_store_still_reports_installed_false_for_its_own_callers(self):
        """STORE-10's documented signal is unchanged; only the route changed."""
        record = self.store.get("gone")
        self.assertFalse(record["installed"])
        self.assertIsNone(record["path"])


class ErrorBodyShapeTests(RestErrorContractTestCase):
    """D3-7 — one error shape a client can branch on."""

    def setUp(self):
        super().setUp()
        self.store.create("demo", "a demo skill")
        self.server = self.serve()

    def test_every_error_body_carries_both_keys(self):
        for path in ("/api/skills/nope", "/api/nothing"):
            with self.subTest(path=path):
                status, body = self.get(self.server, path)
                self.assertGreaterEqual(status, 400)
                payload = json.loads(body)
                self.assertIn("error", payload)
                self.assertIn("code", payload, f"{path} has no machine-readable code")

    def test_the_code_is_a_stable_string_not_a_number(self):
        _, body = self.get(self.server, "/api/skills/nope")
        code = json.loads(body)["code"]
        self.assertIsInstance(code, str)
        self.assertEqual(code, code.strip())

    def test_a_not_found_is_distinguishable_from_a_bad_request(self):
        _, not_found = self.get(self.server, "/api/skills/nope")
        _, unknown = self.get(self.server, "/api/nothing")
        self.assertNotEqual(
            json.loads(not_found)["code"], json.loads(unknown)["code"],
            "two different 404s must not share one code",
        )

    def test_a_specific_error_code_is_preserved_rather_than_replaced(self):
        from skillsmgr.source_update import SourceUpdateError

        payload = SourceUpdateError("review-not-found", "no such review").as_dict()
        self.assertIn("error", payload)
        self.assertIn("code", payload)
        self.assertEqual("review-not-found", payload["code"])


class BindHostTests(unittest.TestCase):
    """D3-12 — bind the host that was validated, or fail cleanly."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._saved = {k: os.environ.get(k) for k in ("SKILLS_MANAGER_DATA", "HOME")}
        self.addCleanup(self._restore)
        home = Path(self._tmp.name) / "home"
        home.mkdir(mode=0o700)
        os.environ["HOME"] = str(home)
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(self._tmp.name) / "data")

    def _restore(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _bind(self, host):
        server = WebAppServer(Store(), host=host, port=0)
        try:
            return server, server.httpd.server_address[0]
        finally:
            server.httpd.server_close()

    def test_a_trailing_space_is_normalised_rather_than_bound_verbatim(self):
        server, bound = self._bind("127.0.0.1 ")
        self.assertEqual("127.0.0.1", bound)

    def test_an_ipv6_loopback_literal_binds_or_fails_cleanly(self):
        """`::1` passes the loopback policy, so a failure here is the socket's.

        Whether it binds depends on the host having IPv6 at all, so the
        requirement is only that the outcome is a clean StoreError naming the
        host -- never the interpreter's own ``gaierror``.
        """
        try:
            self._bind("::1")
        except StoreError as exc:
            self.assertNotIsInstance(exc, OSError)
            self.assertIn("::1", str(exc))
        else:
            pass  # bound, which is equally acceptable

    def test_a_bind_failure_is_a_store_error_not_a_raw_gaierror(self):
        for host in ("127.0.0.1 ", "::1", "nonexistent.invalid"):
            with self.subTest(host=host):
                try:
                    self._bind(host)
                except StoreError as exc:
                    self.assertNotIsInstance(exc, OSError)
                except Exception as exc:  # noqa: BLE001 - the point of the test
                    self.fail(
                        f"host={host!r} raised {type(exc).__name__}: {exc}"
                    )

    def test_a_non_loopback_host_is_still_refused(self):
        with self.assertRaises(StoreError) as caught:
            self._bind("0.0.0.0")
        self.assertIn("loopback", str(caught.exception))

    def test_a_genuine_loopback_still_binds(self):
        server, bound = self._bind("127.0.0.1")
        self.assertEqual("127.0.0.1", bound)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()