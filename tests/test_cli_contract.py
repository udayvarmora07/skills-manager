"""Hermetic CLI contract regressions for stable command output and errors."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from skillsmgr import cli


class CliContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["SKILLS_MANAGER_DATA"] = self.tmp.name

    def tearDown(self):
        if self._old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = self._old_data

    def invoke(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", self.tmp.name, *argv])
        return code, out.getvalue(), err.getvalue()

    def test_scopes_human_output_is_successful(self):
        code, out, err = self.invoke(["scopes"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("ID", out)
        self.assertNotIn("unexpected error", err)

    def test_scopes_no_tokens_omits_token_column(self):
        code, out, err = self.invoke(["scopes", "--no-tokens"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("COUNT", out)
        self.assertNotIn("TOKENS", out)
        self.assertEqual(err, "")

    def test_scopes_json_shape_remains_a_list(self):
        code, out, err = self.invoke(["scopes", "--json"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIsInstance(json.loads(out), list)
        self.assertEqual(err, "")

    def test_parser_scopes_has_no_accidental_skill_name(self):
        args = cli.build_parser().parse_args(["scopes"])
        self.assertFalse(hasattr(args, "name"))
        self.assertFalse(hasattr(args, "snapshots"))

    def test_documented_exit_codes_for_missing_command_and_invalid_name(self):
        code, _, err = self.invoke([])
        self.assertEqual(code, cli.EXIT_USAGE)
        self.assertEqual(err, "")
        code, _, err = self.invoke(["view", "../outside"])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("invalid skill name", err)
        # the invalid name must be rejected before any data-dir mutation
        self.assertFalse((Path(self.tmp.name) / "skills-manager" / "skills-manager.db").exists())

    def test_mutation_commands_work_on_fresh_data_dir_without_init(self):
        # Regression: create on a brand-new data dir used to die with
        # 'no such table: skills' unless `init` (or an auto-initializing
        # read command) ran first.
        code, out, err = self.invoke(["create", "fresh-skill", "-d", "first run"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertNotIn("unexpected error", err)
        self.assertNotIn("no such table", err)
        code, out, err = self.invoke(["list"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("fresh-skill", out)
        self.assertTrue((Path(self.tmp.name) / "skills-manager" / "skills-manager.db").is_file())


if __name__ == "__main__":
    unittest.main()
