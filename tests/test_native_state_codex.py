"""Codex ``[[skills.config]]`` native skill-switch observations (D-1, read-only).

Facts are cited in docs/34: entries live in ``~/.codex/config.toml`` (Codex
writes through ``$CODEX_HOME``), each entry uses exactly one selector -- an
absolute ``path`` that matches one ``SKILL.md`` file, or a ``name`` that matches
every skill with that name -- plus ``enabled``, and the last matching entry
wins.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr import native_state, scopes
from skillsmgr.native_state import observe_codex_states, observe_native_state


class CodexCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir(mode=0o700)
        self.home.chmod(0o700)
        self.data = self.base / "data"
        self.data.mkdir(mode=0o700)
        self.data.chmod(0o700)
        self.skill = self.home / ".codex/skills/deploy"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: deploy\ndescription: d\n---\nbody\n")
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CODEX_HOME", None)
        os.environ["SKILLS_MANAGER_DATA"] = str(self.data)

    def config(self, text: str, root: Path | None = None) -> None:
        target = (root or self.home / ".codex") / "config.toml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def observe(self, name="deploy", document=None) -> dict:
        document = self.skill / "SKILL.md" if document is None else document
        return observe_codex_states([(name, document)], home=self.home)[0]

    @staticmethod
    def user(result: dict) -> dict:
        return next(e for e in result["sources"] if e["source"] == "user")


class CodexSelectorTests(CodexCase):
    def test_path_selector_disables_that_document(self):
        self.config(f'[[skills.config]]\npath = "{self.skill / "SKILL.md"}"\nenabled = false\n')
        result = self.observe()
        self.assertEqual(result["consumer"], "codex")
        self.assertEqual(result["observed_setting"], "disabled")
        self.assertEqual(self.user(result)["declared"], "disabled")
        self.assertEqual(self.user(result)["matched_selector"], "path")
        self.assertEqual(result["effective_state"], "unknown")
        self.assertTrue(result["partial"])

    def test_name_selector_disables_every_copy(self):
        self.config('[[skills.config]]\nname = "deploy"\nenabled = false\n')
        result = self.observe(document=self.base / "elsewhere/deploy/SKILL.md")
        self.assertEqual(result["observed_setting"], "disabled")
        self.assertEqual(self.user(result)["matched_selector"], "name")

    def test_last_matching_entry_wins(self):
        self.config(
            '[[skills.config]]\nname = "deploy"\nenabled = false\n\n'
            f'[[skills.config]]\npath = "{self.skill / "SKILL.md"}"\nenabled = true\n'
        )
        self.assertEqual(self.observe()["observed_setting"], "enabled")

    def test_a_directory_path_matches_no_skill(self):
        # The shape on the maintainer's machine: a directory, not a SKILL.md.
        self.config(f'[[skills.config]]\npath = "{self.skill.parent}"\nenabled = false\n')
        result = self.observe()
        self.assertEqual(result["observed_setting"], "not disabled by the files read")
        self.assertNotIn("declared", self.user(result))

    def test_path_selector_is_canonicalized(self):
        alias = self.base / "alias"
        alias.symlink_to(self.skill.parent, target_is_directory=True)
        self.config(f'[[skills.config]]\npath = "{alias / "deploy/SKILL.md"}"\nenabled = false\n')
        self.assertEqual(self.observe()["observed_setting"], "disabled")

    def test_other_names_are_untouched(self):
        self.config('[[skills.config]]\nname = "other"\nenabled = false\n')
        self.assertEqual(self.observe()["observed_setting"], "not disabled by the files read")

    def test_document_is_optional_for_name_only_matching(self):
        self.config(f'[[skills.config]]\npath = "{self.skill / "SKILL.md"}"\nenabled = false\n')
        result = observe_native_state("codex", "deploy", home=self.home)
        self.assertEqual(result["consumer"], "codex")
        self.assertEqual(result["observed_setting"], "not disabled by the files read")
        self.config('[[skills.config]]\nname = "deploy"\nenabled = false\n')
        self.assertEqual(observe_native_state("codex", "deploy", home=self.home)["observed_setting"], "disabled")


class CodexBoundsTests(CodexCase):
    def test_missing_file_is_missing(self):
        result = self.observe()
        self.assertEqual(self.user(result)["status"], "missing")
        self.assertEqual(result["observed_setting"], "not disabled by the files read")

    def test_malformed_toml_is_unavailable_not_an_exception(self):
        self.config("[[skills.config]\npath = \n")
        result = self.observe()
        self.assertEqual(self.user(result)["status"], "unavailable")
        self.assertNotIn("observed_setting", result)

    def test_oversized_file_is_unavailable(self):
        self.config("# " + "x" * (native_state.MAX_CONFIG_BYTES + 10) + "\n")
        self.assertEqual(self.user(self.observe())["status"], "unavailable")

    def test_fifo_is_refused(self):
        target = self.home / ".codex/config.toml"
        target.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(target)
        self.assertEqual(self.user(self.observe())["status"], "unavailable")

    def test_invalid_entries_are_counted_and_ignored(self):
        self.config(
            '[[skills.config]]\nname = "deploy"\npath = "/x/SKILL.md"\nenabled = false\n\n'
            '[[skills.config]]\nname = "deploy"\nenabled = "no"\n\n'
            '[[skills.config]]\npath = "relative/SKILL.md"\nenabled = false\n'
        )
        result = self.observe()
        self.assertEqual(self.user(result)["invalid_entries"], 3)
        self.assertEqual(result["observed_setting"], "not disabled by the files read")

    def test_wrong_skills_shape_is_invalid(self):
        self.config('skills = "off"\n')
        self.assertEqual(self.user(self.observe())["status"], "invalid")

    def test_codex_home_is_honoured(self):
        other = self.base / "codex-home"
        self.config('[[skills.config]]\nname = "deploy"\nenabled = false\n', root=other)
        with patch.dict(os.environ, {"CODEX_HOME": str(other)}):
            self.assertEqual(self.observe()["observed_setting"], "disabled")

    def test_reads_the_file_once_per_batch(self):
        self.config('[[skills.config]]\nname = "deploy"\nenabled = false\n')
        with patch.object(native_state, "_load_toml", wraps=native_state._load_toml) as spy:
            observe_codex_states([("deploy", None), ("other", None), ("x", None)], home=self.home)
        self.assertEqual(spy.call_count, 1)


class CodexScopeIntegrationTests(CodexCase):
    def test_codex_scope_rows_carry_the_path_matched_observation(self):
        self.config(f'[[skills.config]]\npath = "{self.skill / "SKILL.md"}"\nenabled = false\n')
        with patch.object(scopes.paths, "home_dir", return_value=self.home), \
                patch.object(Path, "home", return_value=self.home):
            rows = scopes.scan_scope("codex")
        row = next(r for r in rows if r["name"] == "deploy")
        self.assertEqual(row["native_state"]["consumer"], "codex")
        self.assertEqual(row["native_state"]["observed_setting"], "disabled")
        # Observation only: the manager's own on/off state is unchanged.
        self.assertFalse(row["disabled"])
        self.assertTrue((self.skill / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
