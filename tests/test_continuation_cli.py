"""Reported CLI failures exercised with temporary HOME and data roots."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr import cli, scopes
from skillsmgr.store import Store


class CliContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict(os.environ, {"HOME": str(self.root / "home"),
                                    "SKILLS_MANAGER_DATA": str(self.root / "data")})
        env.start()
        self.addCleanup(env.stop)
        self.store = Store()
        self.token = scopes._GLOBAL_STORE.set(self.store)
        self.addCleanup(scopes._GLOBAL_STORE.reset, self.token)

    def invoke(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(args)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_search_skips_refused_entries_without_aborting_good_matches(self):
        scopes.create_skill("claude-code", "good", "Use this skill for testing")
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_text("secret outside bytes")
        (self.root / "home/.claude/skills/skill-link").symlink_to(outside, target_is_directory=True)
        for scope in ("claude-code", "all"):
            with self.subTest(scope=scope):
                code, out, err = self.invoke(["search", "skill", "--scope", scope, "--json"])
                self.assertEqual(code, 0, err)
                self.assertIn("good", [row["name"] for row in json.loads(out)])
                self.assertNotIn("secret outside bytes", out + err)

    def test_doctor_only_labels_decoding_failures_as_utf8(self):
        directory = self.root / "home/.claude/skills"
        for name in ("bad-encoding", "Bad_Name", "README.md"):
            path = directory / name
            path.mkdir(parents=True)
            (path / "SKILL.md").write_bytes(b'---\nname: demo\ndescription: test\n---\n' + (b'\xffsecret' if name == "bad-encoding" else b'valid'))
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_text("outside")
        (directory / "outside-link").symlink_to(outside, target_is_directory=True)
        code, out, err = self.invoke(["doctor", "--scope", "claude-code", "--json"])
        report = json.loads(out)
        self.assertEqual(report["undecodable_documents"], ["bad-encoding"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_bare_db_is_usage_error_and_does_not_create_index(self):
        code, _, _ = self.invoke(["db"])
        self.assertEqual(code, 2)
        self.assertFalse(self.store.db_path.exists())

    def test_at_missing_text_file_fails_instead_of_estimating_the_path(self):
        code, out, err = self.invoke(["tokens", "--text", "@" + str(self.root / "missing"), "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertNotIn("unexpected error", err)

    def test_no_tokens_also_omits_json_totals(self):
        self.store.init_db()
        self.store.create("demo", "demo skill")
        code, out, err = self.invoke(["scopes", "--no-tokens", "--json"])
        self.assertEqual((code, err), (0, ""))
        rows = json.loads(out)
        self.assertTrue(rows)
        self.assertFalse(any(key in row for row in rows for key in ("tokens", "avg_tokens", "max_tokens")))

    def test_out_of_range_port_is_usage_error_before_bootstrap(self):
        for port in ("-1", "65536"):
            with self.subTest(port=port):
                code, _, err = self.invoke(["webui", "--port", port, "--no-browser"])
                self.assertEqual(code, 2)
                self.assertNotIn("unexpected error", err)
                self.assertFalse(self.store.db_path.exists())

    def test_export_directory_destination_is_a_clean_error(self):
        target = self.root / "destination"
        target.mkdir()
        code, out, err = self.invoke(["export", "--dest", str(target)])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertNotIn("Errno", err)
        self.assertNotIn(".skillsmgr-export", err)
        self.assertTrue(target.is_dir())
        self.assertFalse(list(self.root.glob(".*.skillsmgr-export")))


if __name__ == "__main__":
    unittest.main()
