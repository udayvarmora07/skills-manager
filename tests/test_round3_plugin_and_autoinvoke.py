"""Round 3: skills-dir plugins and OpenCode's autoinvoke override.

vercel-labs/skills#2609: Claude Code loads a folder in a skills directory
that holds ``.claude-plugin/plugin.json`` as a plugin ``<name>@skills-dir``
(code.claude.com/docs/en/skills, "Skill folder as a plugin").  Copying only a
nested ``skills/<skill>/`` folder drops the manifest, hooks and the
``${CLAUDE_PLUGIN_ROOT}`` substitution.

sst/opencode#52747 (merged 2026-10-02): OpenCode maps
``disable-model-invocation`` onto ``autoinvoke``, and when both it and
``metadata.opencode/autoinvoke`` are set, ``opencode/autoinvoke`` wins.  A
skill whose two switches disagree is hidden in one agent and offered in the
other.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr import hygiene, loader

DOC = "---\nname: {n}\ndescription: Use when {n}.\n{extra}---\nBody\n"


class _Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name).resolve()
        env = patch.dict(os.environ, {"CODEX_HOME": ""})
        env.start()
        self.addCleanup(env.stop)

    def write(self, folder: Path, name: str, extra: str = "") -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(DOC.format(n=name, extra=extra), encoding="utf-8")
        return folder

    def plugin(self, folder: Path, manifest: str = '{"name": "my-plugin"}') -> Path:
        (folder / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (folder / ".claude-plugin" / "plugin.json").write_text(manifest, encoding="utf-8")
        return folder

    def report(self, root: Path, scope: str):
        records = loader.scan_dir(root, recursive=True, annotate_paths=True)
        for record in records:
            record["scope"] = scope
        return hygiene.hygiene_report(records, scope=scope, home=self.home)

    @staticmethod
    def findings(report, category):
        return [f for f in report["findings"] if f["category"] == category]


class PluginMemberTests(_Fixture):
    def test_a_skill_inside_a_plugin_folder_is_named_with_its_plugin(self):
        root = self.home / ".agents" / "skills"
        plugin = self.plugin(root / "my-plugin")
        self.write(plugin / "skills" / "my-skill", "my-skill")
        self.write(root / "plain", "plain")
        found = self.findings(self.report(root, "agents"), "plugin-member-skill")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "info")
        self.assertEqual(found[0]["instances"][0]["name"], "my-skill")
        self.assertEqual(found[0]["evidence"]["plugin_name"], "my-plugin")
        self.assertEqual(found[0]["evidence"]["plugin_dir"], "~/.agents/skills/my-plugin")
        self.assertIn("vercel-labs/skills#2609", found[0]["explanation"])

    def test_a_manifest_that_is_not_the_documented_layout_is_ignored(self):
        root = self.home / ".agents" / "skills"
        holder = self.plugin(root / "holder")
        self.write(holder / "other" / "deep", "deep")
        self.assertFalse(self.findings(self.report(root, "agents"), "plugin-member-skill"))

    def test_a_symlinked_or_unparseable_manifest_does_not_crash(self):
        root = self.home / ".agents" / "skills"
        plugin = root / "linked"
        (plugin / ".claude-plugin").mkdir(parents=True)
        target = self.home / "elsewhere.json"
        target.write_text('{"name": "x"}', encoding="utf-8")
        (plugin / ".claude-plugin" / "plugin.json").symlink_to(target)
        self.write(plugin / "skills" / "a", "a")
        broken = self.plugin(root / "broken", manifest="{not json")
        self.write(broken / "skills" / "b", "b")
        found = self.findings(self.report(root, "agents"), "plugin-member-skill")
        self.assertEqual([f["instances"][0]["name"] for f in found], ["b"])
        self.assertIsNone(found[0]["evidence"]["plugin_name"])


class HostileManifestTests(_Fixture):
    def test_a_deeply_nested_manifest_is_present_without_a_name(self):
        root = self.home / ".agents" / "skills"
        plugin = self.plugin(root / "deep", manifest="[" * 60000)
        self.write(plugin / "skills" / "c", "c")
        found = self.findings(self.report(root, "agents"), "plugin-member-skill")
        self.assertEqual(len(found), 1)
        self.assertIsNone(found[0]["evidence"]["plugin_name"])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs FIFOs")
    def test_a_fifo_manifest_is_never_opened(self):
        root = self.home / ".claude" / "skills"
        (root / "pipe" / ".claude-plugin").mkdir(parents=True)
        os.mkfifo(root / "pipe" / ".claude-plugin" / "plugin.json")
        self.write(root / "plain", "plain")
        self.assertEqual(self.report(root, "claude-code")["skills_dir_plugins"]["total"], 0)

    def test_an_unresolvable_home_degrades_instead_of_raising(self):
        with patch("skillsmgr.hygiene.paths.home_dir", side_effect=RuntimeError("no home")):
            section = hygiene._skills_dir_plugins_section("claude-code", None, [])
        self.assertEqual(section["state"], "unavailable")


class SkillsDirPluginSectionTests(_Fixture):
    def test_claude_code_plugins_without_a_root_document_are_listed(self):
        root = self.home / ".claude" / "skills"
        plugin = self.plugin(root / "my-plugin")
        self.write(plugin / "skills" / "one", "one")
        self.write(plugin / "skills" / "two", "two")
        scaffold = self.plugin(root / "scaffold", '{"name": "scaffold"}')
        self.write(scaffold, "scaffold")
        self.write(root / "plain", "plain")
        report = self.report(root, "claude-code")
        section = report["skills_dir_plugins"]
        self.assertEqual(section["state"], "observed")
        by_dir = {p["dir"]: p for p in section["plugins"]}
        self.assertEqual(set(by_dir), {"my-plugin", "scaffold"})
        self.assertFalse(by_dir["my-plugin"]["root_document"])
        self.assertEqual(by_dir["my-plugin"]["nested_skills"], 2)
        self.assertEqual(by_dir["my-plugin"]["loads_as"], "my-plugin@skills-dir")
        self.assertTrue(by_dir["scaffold"]["root_document"])
        self.assertEqual(section["total"], 2)

    def test_other_scopes_report_the_section_unavailable(self):
        root = self.home / ".agents" / "skills"
        self.write(root / "plain", "plain")
        self.assertEqual(self.report(root, "agents")["skills_dir_plugins"]["state"], "unavailable")

    def test_terminal_line_is_silent_without_plugins(self):
        from skillsmgr import cli_handlers
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli_handlers._render_skills_dir_plugins_text({"state": "observed", "total": 0, "plugins": []})
            cli_handlers._render_skills_dir_plugins_text(
                {"state": "observed", "total": 1,
                 "plugins": [{"dir": "my-plugin", "root_document": False, "nested_skills": 2}]})
        self.assertEqual(out.getvalue().count("\n"), 1)
        self.assertIn("1 skills-dir plugin", out.getvalue())


class AutoinvokeConflictTests(_Fixture):
    def report_for(self, extra: str, scope: str = "opencode"):
        root = self.home / "root"
        self.write(root / "s", "s", extra)
        return self.report(root, scope)

    def test_disagreeing_switches_are_a_warning(self):
        report = self.report_for('disable-model-invocation: true\nmetadata:\n  opencode/autoinvoke: "yes"\n')
        found = self.findings(report, "opencode-autoinvoke-conflict")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "warning")
        self.assertIs(found[0]["evidence"]["opencode_autoinvoke"], True)
        self.assertIs(found[0]["evidence"]["disable_model_invocation"], True)
        self.assertIn("sst/opencode#52747", found[0]["explanation"])

    def test_agreeing_switches_and_spellings_are_quiet(self):
        for extra in ('disable-model-invocation: "on"\nmetadata:\n  opencode/autoinvoke: "off"\n',
                      "disable-model-invocation: true\n",
                      "metadata:\n  opencode/autoinvoke: false\n",
                      'disable-model-invocation: maybe\nmetadata:\n  opencode/autoinvoke: "yes"\n'):
            with self.subTest(extra=extra):
                self.assertFalse(self.findings(self.report_for(extra), "opencode-autoinvoke-conflict"))

    def test_a_scope_opencode_does_not_read_is_not_flagged(self):
        report = self.report_for('disable-model-invocation: true\nmetadata:\n  opencode/autoinvoke: true\n',
                                 scope="gemini")
        self.assertFalse(self.findings(report, "opencode-autoinvoke-conflict"))


class ReportStaysJsonTests(_Fixture):
    def test_new_sections_serialize(self):
        root = self.home / ".claude" / "skills"
        self.write(self.plugin(root / "p") / "skills" / "x", "x")
        json.dumps(self.report(root, "claude-code"))


if __name__ == "__main__":
    unittest.main()
