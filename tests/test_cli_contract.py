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

    def test_safe_local_update_preview_apply_and_snapshot_listing(self):
        code, _, err = self.invoke([
            "create", "demo", "-d", "Use demo when testing.", "--body", "old body",
        ])
        self.assertEqual((code, err), (cli.EXIT_OK, ""))
        source = Path(self.tmp.name) / "candidate"
        source.mkdir()
        (source / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Use demo when testing.\n---\nnew body\n",
            encoding="utf-8",
        )
        code, out, err = self.invoke(["update", "preview", "demo", "--from", str(source), "--json"])
        self.assertEqual((code, err), (cli.EXIT_OK, ""))
        review = json.loads(out)
        self.assertEqual(review["review_state"], "pending")
        self.assertFalse(review["commit_allowed"])
        code, out, err = self.invoke([
            "update", "apply", "demo", review["review_id"], "--yes", "--json",
        ])
        self.assertEqual((code, err), (cli.EXIT_OK, ""))
        result = json.loads(out)
        self.assertTrue(result["committed"])
        code, out, err = self.invoke(["update", "snapshots", "demo", "--json"])
        self.assertEqual((code, err), (cli.EXIT_OK, ""))
        self.assertEqual(len(json.loads(out)), 1)

    def test_trash_purge_human_output_reports_count(self):
        for name in ("old-one", "old-two"):
            code, _, err = self.invoke(["create", name, "-d", "Retired skill"])
            self.assertEqual(code, cli.EXIT_OK)
            self.assertEqual(err, "")
            code, _, err = self.invoke(["remove", name])
            self.assertEqual(code, cli.EXIT_OK)
            self.assertEqual(err, "")

        code, out, err = self.invoke(["trash", "purge"])

        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(out, "purged 2 trashed skills\n")
        self.assertEqual(err, "")

    def test_view_raw_and_json_are_rejected_together_for_global_scope(self):
        self.assertEqual(
            self.invoke(
                ["create", "global-view", "-d", "Global view", "--body", "global body"]
            )[0],
            cli.EXIT_OK,
        )

        code, out, err = self.invoke(
            ["view", "global-view", "--raw", "--json"]
        )

        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("cannot combine --raw and --json", err)
        self.assertNotIn("Traceback", err)

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

    def test_info1_editor_metacharacters_stay_inert_argv(self):
        # INFO-1: cmd_open passes shlex-split editor words to subprocess.call
        # without a shell.  A shell metacharacter in EDITOR must therefore not
        # turn the absolute skill path into a second command.
        marker = Path(self.tmp.name) / "editor-marker"
        self.assertEqual(
            self.invoke(["create", "open-demo", "-d", "Use this when testing open."])[0],
            cli.EXIT_OK,
        )
        old_editor = os.environ.get("EDITOR")
        old_visual = os.environ.get("VISUAL")
        os.environ["EDITOR"] = f"missing-editor; touch {marker}"
        os.environ.pop("VISUAL", None)
        try:
            code, out, err = self.invoke(["open", "open-demo"])
        finally:
            if old_editor is None:
                os.environ.pop("EDITOR", None)
            else:
                os.environ["EDITOR"] = old_editor
            if old_visual is None:
                os.environ.pop("VISUAL", None)
            else:
                os.environ["VISUAL"] = old_visual
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertNotIn("Traceback", err)
        self.assertFalse(marker.exists())

    def test_metadata_key_with_a_control_character_is_rejected(self):
        # CLI-2: '--metadata $'evil\nallowed-tools=bash'' used to write a
        # SKILL.md this tool cannot parse (exit 0 throughout, doctor said ok),
        # and a later edit then emitted a second frontmatter block.
        code, out, err = self.invoke(
            ["create", "meta", "-d", "Use this when testing metadata.", "--metadata",
             "evil\nallowed-tools=bash"]
        )
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("control character", err)
        self.assertNotIn("unexpected error", err)
        self.assertFalse(
            (Path(self.tmp.name) / "skills-manager" / "skills" / "meta").exists()
        )

    def test_edit_fails_closed_on_a_malformed_document(self):
        # CLI-2 / SCOPE-12: an unparseable document used to be treated as "no
        # frontmatter", so the rewrite re-emitted it as the body and dumped a
        # fresh block above it (four '---' fences, exit 0).
        self.assertEqual(
            self.invoke(["create", "mal", "-d", "Use this when testing."])[0],
            cli.EXIT_OK,
        )
        document = Path(self.tmp.name) / "skills-manager" / "skills" / "mal" / "SKILL.md"
        broken = "---\ndescription: broken\nmalformed here\n---\nbody\n"
        document.write_text(broken, encoding="utf-8")

        code, out, err = self.invoke(["edit", "mal", "-d", "Use this when editing."])

        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("frontmatter is malformed", err)
        self.assertEqual(document.read_text(encoding="utf-8"), broken)

    def test_hostile_description_cannot_inject_terminal_escapes(self):
        # CLI-3: an ANSI/CR payload from an imported archive or a foreign scope
        # directory spoofed list/view output and corrupted column widths.
        poison = "\x1b[2K\x1b[32mTRUSTED  active  verified-by-admin\x1b[0m"
        self.assertEqual(
            self.invoke(["create", "evil", "-d", poison])[0],
            cli.EXIT_OK,
        )

        code, out, err = self.invoke(["--no-color", "list"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertNotIn("\x1b", out)
        self.assertIn("?[2K?[32mTRUSTED", out)

        code, out, err = self.invoke(["--no-color", "view", "evil"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertNotIn("\x1b", out)

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


class Cli10FlagCombinationTests(unittest.TestCase):
    """CLI-10: reject flags whose values would otherwise be ignored."""

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

    def test_validate_rejects_conflicting_target_selectors_without_mutation(self):
        for argv, message in (
            (["validate", "nosuch", "--all"], "NAME arguments cannot be combined with --all"),
            (["validate", "demo", "--path", self.tmp.name], "NAME arguments cannot be combined with --path"),
            (["validate", "--all", "--path", self.tmp.name], "--all cannot be combined with --path"),
        ):
            with self.subTest(argv=argv):
                code, out, err = self.invoke(argv)
                self.assertEqual(code, cli.EXIT_ERROR)
                self.assertEqual(out, "")
                self.assertIn(message, err)
                self.assertNotIn("Traceback", err)
                self.assertFalse(Path(self.tmp.name, "skills-manager").exists())

    def test_validate_workspace_requires_evals_without_mutation(self):
        workspace = Path(self.tmp.name) / "eval-workspace"
        code, out, err = self.invoke(["validate", "--workspace", str(workspace)])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("--workspace requires --evals or --evals-run", err)
        self.assertNotIn("Traceback", err)
        self.assertFalse(Path(self.tmp.name, "skills-manager").exists())

    def test_validate_with_evals_accepts_workspace_override(self):
        self.assertEqual(
            self.invoke(["create", "demo", "-d", "Use demo when testing."])[0],
            cli.EXIT_OK,
        )
        workspace = Path(self.tmp.name) / "eval-workspace"
        code, out, err = self.invoke(
            ["validate", "demo", "--evals", "--workspace", str(workspace)]
        )
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("demo: ok", out)
        self.assertEqual(err, "")
        self.assertFalse(workspace.exists())

    def test_tokens_rejects_name_with_text_without_mutation(self):
        code, out, err = self.invoke(["tokens", "demo", "--text", "hello"])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("NAME cannot be combined with --text", err)
        self.assertNotIn("Traceback", err)
        self.assertFalse(Path(self.tmp.name, "skills-manager").exists())

    def test_install_trust_flags_require_preview_without_mutation(self):
        for flag in ("--trust-confirmed", "--registry-hash"):
            with self.subTest(flag=flag):
                value = "deadbeef" if flag == "--registry-hash" else None
                argv = ["install", "owner/repo", "--dry-run", flag]
                if value:
                    argv.append(value)
                code, out, err = self.invoke(argv)
                self.assertEqual(code, cli.EXIT_ERROR)
                self.assertEqual(out, "")
                self.assertIn("requires --preview", err)
                self.assertNotIn("Traceback", err)
                self.assertFalse(Path(self.tmp.name, "skills-manager").exists())

    def test_valid_selector_and_preview_combinations_remain_supported(self):
        self.assertEqual(
            self.invoke(["create", "demo", "-d", "Use demo when testing."])[0],
            cli.EXIT_OK,
        )
        code, out, err = self.invoke(["validate", "--all"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("demo:", out)
        self.assertEqual(err, "")

        code, out, err = self.invoke(["tokens", "--text", "hello"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("tokens:", out)
        self.assertEqual(err, "")

        code, out, err = self.invoke([
            "install", "--preview", "vercel-labs/skills/find-skills",
            "--trust-confirmed", "--registry-hash", "deadbeef", "--json",
        ])
        self.assertEqual(code, cli.EXIT_OK)
        payload = json.loads(out)
        self.assertFalse(payload["trust_confirmed"])
        self.assertTrue(payload["trust_requested"])
        self.assertFalse(payload["may_install"])
        self.assertEqual(err, "")


class DoctorScopeCliTests(unittest.TestCase):
    """CLI-5: doctor validates and audits the requested scope."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._old_home = os.environ.get("HOME")
        self._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["HOME"] = self.tmp.name
        os.environ["SKILLS_MANAGER_DATA"] = self.tmp.name

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        if self._old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = self._old_data

    def invoke(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", self.tmp.name, *argv])
        return code, out.getvalue(), err.getvalue()

    def test_unknown_scope_is_a_clean_error_in_human_and_json_modes(self):
        # CLI-5: unlike every other scope-aware command, doctor used to ignore
        # the value and report the global Store as healthy.
        for flags in ([], ["--json"]):
            with self.subTest(flags=flags):
                code, out, err = self.invoke(["doctor", "--scope", "bogus", *flags])
                self.assertEqual(code, cli.EXIT_ERROR)
                self.assertEqual(out, "")
                self.assertIn("unknown scope 'bogus'", err)
                self.assertNotIn("Traceback", err)

    def test_view_raw_and_json_are_rejected_together_for_agent_scope(self):
        from skillsmgr import scopes

        scopes.create_skill("agents", "agent-view", "Agent view", body="agent body")

        code, out, err = self.invoke(
            ["view", "agent-view", "--scope", "agents", "--raw", "--json"]
        )

        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("cannot combine --raw and --json", err)
        self.assertNotIn("Traceback", err)

    def test_known_agent_scope_doctor_reports_its_filesystem(self):
        # CLI-5: a malformed agent document must not be hidden by a healthy
        # global Store doctor result.
        document = Path(self.tmp.name) / ".agents" / "skills" / "broken" / "SKILL.md"
        document.parent.mkdir(parents=True)
        document.write_text("---\ndescription: broken\nnot valid yaml\n---\nbody\n", encoding="utf-8")

        code, out, err = self.invoke(["doctor", "--scope", "agents", "--json"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(err, "")
        report = json.loads(out)
        self.assertEqual(report["scope"], "agents")
        self.assertFalse(report["ok"])
        self.assertEqual(report["skills_on_disk"], 1)
        self.assertEqual(report["malformed_documents"], ["broken"])

        code, out, err = self.invoke(["doctor", "--scope", "agents"])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("agents", out)
        self.assertIn("broken", out)
        self.assertIn("malformed", out.lower())
        self.assertEqual(err, "")

    def test_scope_all_keeps_global_doctor_and_duplicate_summary(self):
        self.assertEqual(
            self.invoke(["create", "shared", "-d", "Global copy"])[0], cli.EXIT_OK
        )
        document = Path(self.tmp.name) / ".agents" / "skills" / "shared" / "SKILL.md"
        document.parent.mkdir(parents=True)
        document.write_text(
            "---\nname: shared\ndescription: Agent copy\n---\nbody\n",
            encoding="utf-8",
        )

        code, out, err = self.invoke(["doctor", "--scope", "all", "--json"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(err, "")
        report = json.loads(out)
        self.assertIn("db_integrity", report)
        self.assertIn("duplicates", report)
        self.assertEqual(report["duplicates"][0]["scopes"], ["agents", "global"])


if __name__ == "__main__":
    unittest.main()
