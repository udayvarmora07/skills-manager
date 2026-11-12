"""Codex ``[[skills.config]]`` path entries that can never match a skill.

openai/codex#51044: a ``path`` entry that names the skill *folder* does not
disable the skill; Codex compares it with the ``SKILL.md`` file path.  The
user believes the skill is off and it is not.  These checks name such
entries read-only; nothing is written.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr import hygiene, native_state


class DeadEntryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name).resolve()
        self.codex = self.home / ".codex"
        self.skill = self.codex / "skills" / "demo"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: demo\ndescription: d\n---\n", encoding="utf-8")
        env = patch.dict(os.environ, {"CODEX_HOME": ""})
        env.start()
        self.addCleanup(env.stop)

    def write_config(self, text: str) -> None:
        (self.codex / "config.toml").write_text(text, encoding="utf-8")

    def entries(self):
        return native_state.codex_config_dead_entries(home=self.home)

    def test_folder_path_is_reported_with_the_document_path_to_use(self):
        self.write_config(f'[[skills.config]]\npath = "{self.skill}"\nenabled = false\n')
        report = self.entries()
        self.assertEqual(report["state"], "observed")
        self.assertEqual(len(report["entries"]), 1)
        entry = report["entries"][0]
        self.assertEqual(entry["problem"], "folder")
        self.assertFalse(entry["enabled"])
        self.assertEqual(entry["suggested_path"], str(self.skill / "SKILL.md"))

    def test_document_path_and_name_entries_are_not_reported(self):
        self.write_config(f'[[skills.config]]\npath = "{self.skill / "SKILL.md"}"\nenabled = false\n'
                          '[[skills.config]]\nname = "demo"\nenabled = false\n')
        self.assertEqual(self.entries()["entries"], [])

    def test_missing_and_non_document_paths_are_reported(self):
        other = self.skill / "notes.md"
        other.write_text("x", encoding="utf-8")
        self.write_config(f'[[skills.config]]\npath = "{self.home / "gone" / "SKILL.md"}"\nenabled = false\n'
                          f'[[skills.config]]\npath = "{other}"\nenabled = false\n')
        problems = [e["problem"] for e in self.entries()["entries"]]
        self.assertEqual(problems, ["missing", "not-skill-document"])

    def test_tilde_paths_resolve_and_are_judged(self):
        self.write_config('[[skills.config]]\npath = "~/.codex/skills/demo"\nenabled = false\n')
        with patch.dict(os.environ, {"HOME": str(self.home)}):
            report = self.entries()
        self.assertEqual(report["entries"][0]["problem"], "folder")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads every directory")
    def test_an_entry_behind_an_unreadable_directory_is_not_called_missing(self):
        locked = self.home / "locked"
        (locked / "demo").mkdir(parents=True)
        self.write_config(f'[[skills.config]]\npath = "{locked / "demo" / "SKILL.md"}"\nenabled = false\n')
        locked.chmod(0)
        self.addCleanup(locked.chmod, 0o700)
        self.assertEqual(self.entries()["entries"], [])

    def test_absent_and_unreadable_config_never_raise(self):
        self.assertEqual(self.entries()["state"], "missing")
        self.write_config("not = [valid toml")
        self.assertEqual(self.entries()["state"], "unavailable")

    def test_many_entries_are_bounded(self):
        rows = "".join(f'[[skills.config]]\npath = "{self.home}/gone{i}"\nenabled = false\n'
                       for i in range(native_state.MAX_DEAD_ENTRIES + 7))
        self.write_config(rows)
        report = self.entries()
        self.assertEqual(len(report["entries"]), native_state.MAX_DEAD_ENTRIES)
        self.assertEqual(report["total"], native_state.MAX_DEAD_ENTRIES + 7)
        self.assertEqual(report["omitted"], 7)

    def test_hygiene_reports_a_warning_and_a_redacted_section(self):
        self.write_config(f'[[skills.config]]\npath = "{self.skill}"\nenabled = false\n')
        report = hygiene.hygiene_report([], scope="codex", home=self.home)
        section = report["codex_config"]
        self.assertEqual(section["state"], "observed")
        self.assertTrue(section["entries"][0]["path"].startswith("~/"))
        self.assertTrue(section["entries"][0]["suggested_path"].endswith("/SKILL.md"))
        findings = [f for f in report["findings"] if f["category"] == "codex-config-dead-entry"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "warning")
        self.assertFalse(findings[0]["automatic_action"])

    def test_other_scopes_do_not_read_the_codex_config(self):
        self.write_config(f'[[skills.config]]\npath = "{self.skill}"\nenabled = false\n')
        report = hygiene.hygiene_report([], scope="claude-code", home=self.home)
        self.assertEqual(report["codex_config"]["state"], "unavailable")
        self.assertFalse([f for f in report["findings"] if f["category"] == "codex-config-dead-entry"])



class DeadEntryTextTests(unittest.TestCase):
    def test_terminal_output_names_each_entry_and_sanitizes_it(self):
        import contextlib
        import io

        from skillsmgr import cli_handlers
        section = {"total": 1, "entries": [{"problem": "folder", "path": "~/.codex/skills/de\x1b[2Kmo",
                                             "suggested_path": "~/.codex/skills/demo/SKILL.md"}]}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli_handlers._render_codex_config_text(section)
        text = out.getvalue()
        self.assertIn("1 path entry matches no skill", text)
        self.assertIn("-> use ~/.codex/skills/demo/SKILL.md", text)
        self.assertNotIn("\x1b", text)


if __name__ == "__main__":
    unittest.main()
