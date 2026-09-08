"""Compatibility probes for helpers extracted behind legacy module interfaces."""

import contextlib
import io
import json
import unittest

from skillsmgr import cli, webapp
from skillsmgr.cli_output import err, print_json, render_table, truncate
from skillsmgr.store import StoreError
from skillsmgr.web_security import RequestError as ExtractedRequestError


class ExtractedHelperCompatibilityTests(unittest.TestCase):
    def test_webapp_private_helpers_keep_legacy_call_shapes(self):
        self.assertEqual(webapp._json_bytes({"ok": True}, 418), b'{"ok": true}')

        boundary = "compat-boundary"
        raw = (
            b"--compat-boundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="demo/SKILL.md"\r\n'
            b"\r\n"
            b"body\r\n"
            b"--compat-boundary--\r\n"
        )
        self.assertEqual(
            webapp._parse_multipart(raw, boundary),
            [{"name": "file", "filename": "demo/SKILL.md", "content": b"body"}],
        )

    def test_webapp_request_error_import_remains_compatible(self):
        self.assertIs(webapp.RequestError, ExtractedRequestError)
        error = webapp.RequestError(403, "blocked")
        self.assertIsInstance(error, StoreError)
        self.assertEqual(error.status, 403)
        self.assertEqual(str(error), "blocked")

    def test_cli_output_aliases_keep_legacy_one_argument_shapes(self):
        self.assertIs(cli._print_json, print_json)
        self.assertIs(cli._err, err)
        self.assertIs(cli._truncate, truncate)
        self.assertIs(cli._render_table, render_table)

        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            cli._print_json({"ok": True})
            cli._err("blocked")
        self.assertEqual(json.loads(stdout.getvalue()), {"ok": True})
        self.assertIn("blocked", stderr.getvalue())
        self.assertEqual(cli._truncate("abcdef", 5), "ab...")
        self.assertEqual(cli._render_table([["A"], ["b"]]), "A\nb")


if __name__ == "__main__":
    unittest.main()
