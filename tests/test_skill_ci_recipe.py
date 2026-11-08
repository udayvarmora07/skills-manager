"""Execute the Skill CI recipe exactly as documented in docs/36.

The script is cut from between the doc's markers, so a doc edit that breaks it
breaks this test, and the exit codes the doc states are measured here.
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "36-skill-ci-recipe-2026-11-08.md"
GOOD = "---\nname: {name}\ndescription: Use {name} when checking the CI recipe.\n---\n# {name}\n"


def _script() -> str:
    text = DOC.read_text(encoding="utf-8")
    match = re.search(
        r"<!-- skill-ci-script:begin -->\n```bash\n(.*?)```\n<!-- skill-ci-script:end -->",
        text, re.S,
    )
    if match is None:
        raise AssertionError("docs/36 no longer carries the marked script block")
    return match.group(1)


@unittest.skipIf(shutil.which("bash") is None, "bash is required to run the recipe")
class SkillCiRecipeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()
        self.base.chmod(0o700)
        self.skills = self.base / "skills"
        self.skills.mkdir()
        self.script = self.base / "check-skills.sh"
        self.script.write_text(_script(), encoding="utf-8")

    def _skill(self, name: str, text: str | None = None) -> None:
        folder = self.skills / name
        folder.mkdir()
        (folder / "SKILL.md").write_text(text or GOOD.format(name=name), encoding="utf-8")

    def _run(self, root: Path | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.pop("SKILLS_MANAGER_DATA", None)
        env["TMPDIR"] = str(self.base)
        env["SKILLS_MGR"] = f"{sys.executable} -m skillsmgr"
        env["PYTHONPATH"] = str(ROOT)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            ["bash", str(self.script), str(root or self.skills)],
            env=env, cwd=str(self.base), capture_output=True, text=True, timeout=120,
        )

    def test_all_valid_folders_pass(self):
        self._skill("alpha")
        self._skill("beta")
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("alpha: ok", result.stdout)
        self.assertIn("beta: ok", result.stdout)

    def test_one_invalid_folder_fails_the_run_and_still_checks_the_rest(self):
        self._skill("alpha")
        self._skill("broken", "---\nname: Broken_Name\n---\n# x\n")
        self._skill("zeta")
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("broken: invalid", result.stdout)
        self.assertIn("zeta: ok", result.stdout)

    def test_no_skill_folders_is_a_failure(self):
        (self.skills / "notes").mkdir()
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no skill folders found", result.stderr)

    def test_the_private_data_directory_is_removed(self):
        self._skill("alpha")
        before = {p.name for p in self.base.iterdir()}
        self.assertEqual(self._run().returncode, 0)
        self.assertEqual({p.name for p in self.base.iterdir()}, before)

    def _env(self, mgr: str) -> dict:
        env = dict(os.environ)
        env.pop("SKILLS_MANAGER_DATA", None)
        env.update({"TMPDIR": str(self.base), "SKILLS_MGR": mgr,
                    "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"})
        return env

    def test_the_command_is_not_glob_expanded(self):
        self._skill("alpha")
        (self.base / "decoy-file").write_text("", encoding="utf-8")
        result = subprocess.run(
            ["bash", str(self.script), str(self.skills)],
            env=self._env(f"{sys.executable} -m skillsmgr --color decoy*"),
            cwd=str(self.base), capture_output=True, text=True, timeout=120,
        )
        # Unquoted expansion would have turned decoy* into decoy-file; the
        # literal word reaches the CLI, which rejects it as a usage error.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("decoy*", result.stderr)
        self.assertNotIn("decoy-file", result.stderr)

    def test_a_terminated_run_still_removes_its_data_directory(self):
        self._skill("alpha")
        slow = self.base / "slow-mgr"
        slow.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
        slow.chmod(0o700)
        before = {p.name for p in self.base.iterdir()}
        process = subprocess.Popen(
            ["bash", str(self.script), str(self.skills)], env=self._env(str(slow)),
            cwd=str(self.base), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = __import__("time").monotonic() + 10
        while {p.name for p in self.base.iterdir()} == before and __import__("time").monotonic() < deadline:
            __import__("time").sleep(0.05)
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=30)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual({p.name for p in self.base.iterdir()}, before)

    def test_workflow_pins_match_this_repository(self):
        text = DOC.read_text(encoding="utf-8")
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        for pin in re.findall(r"uses: (actions/[\w-]+@[0-9a-f]{40})", text):
            self.assertIn(pin, ci, f"{pin} is not a SHA this repository reviewed")


if __name__ == "__main__":
    unittest.main()
