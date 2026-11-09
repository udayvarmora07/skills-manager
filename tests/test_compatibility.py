"""Compatibility probes for helpers extracted behind legacy module interfaces."""

import contextlib
import io
import json
import unittest

from skillsmgr import cli, cli_handlers, key_support, webapp
from skillsmgr.web_serialization import json_bytes
from skillsmgr.web_upload import parse_multipart
from skillsmgr.cli_output import err, print_json, render_table, truncate
from skillsmgr.store import StoreError
from skillsmgr.web_security import RequestError as ExtractedRequestError


class ExtractedHelperCompatibilityTests(unittest.TestCase):
    def test_extracted_web_helpers_keep_behavior(self):
        self.assertEqual(json_bytes({"ok": True}), b'{"ok": true}')

        boundary = "compat-boundary"
        raw = (
            b"--compat-boundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="demo/SKILL.md"\r\n'
            b"\r\n"
            b"body\r\n"
            b"--compat-boundary--\r\n"
        )
        self.assertEqual(
            parse_multipart(raw, boundary),
            [{"name": "file", "filename": "demo/SKILL.md", "content": b"body"}],
        )

    def test_webapp_request_error_import_remains_compatible(self):
        self.assertIs(webapp.RequestError, ExtractedRequestError)
        error = webapp.RequestError(403, "blocked")
        self.assertIsInstance(error, StoreError)
        self.assertEqual(error.status, 403)
        self.assertEqual(str(error), "blocked")

    def test_cli_output_helpers_keep_one_argument_shapes(self):

        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            print_json({"ok": True})
            err("blocked")
        self.assertEqual(json.loads(stdout.getvalue()), {"ok": True})
        self.assertIn("blocked", stderr.getvalue())
        self.assertEqual(truncate("abcdef", 5), "ab...")
        self.assertEqual(render_table([["A"], ["b"]]), "A\nb")


    def test_documented_key_lookup_export_remains_available(self):
        self.assertIn("documents_anywhere", key_support.__all__)
        self.assertTrue(key_support.documents_anywhere("disable-model-invocation"))
        self.assertTrue(key_support.documents_anywhere("metadata"))
        self.assertFalse(key_support.documents_anywhere("not-a-documented-key"))

    def test_cli_public_handler_exports_remain_available(self):
        self.assertIs(cli.COMMANDS, cli_handlers.COMMANDS)
        handlers = (
            'cmd_init',
            'cmd_list',
            'cmd_create',
            'cmd_add',
            'cmd_view',
            'cmd_edit',
            'cmd_open',
            'cmd_remove',
            'cmd_disable',
            'cmd_enable',
            'cmd_validate',
            'cmd_search',
            'cmd_import',
            'cmd_export',
            'cmd_backup',
            'cmd_restore',
            'cmd_doctor',
            'cmd_stats',
            'cmd_trash_list',
            'cmd_trash_purge',
            'cmd_templates_list',
            'cmd_templates_new',
            'cmd_history',
            'cmd_db_rebuild',
            'cmd_db_resync',
            'cmd_sync',
            'cmd_scopes',
            'cmd_tokens',
            'cmd_install',
            'cmd_update',
            'cmd_gui',
        )
        for name in handlers:
            self.assertIn(name, cli.__all__)
            self.assertIs(getattr(cli, name), getattr(cli_handlers, name))


if __name__ == "__main__":
    unittest.main()
