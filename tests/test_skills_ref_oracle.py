"""R17: the agentskills.io reference validator as a dev-only differential oracle.

`skills-ref` (PyPI, agentskills/agentskills) needs Python >= 3.11 plus
click/strictyaml, so it is never a dependency of this stdlib-only package.
Point SKILLS_REF_PYTHON at an interpreter that can `import skills_ref`
(for example a throwaway venv with `pip install skills-ref==0.1.1`); without it
the whole module skips.

Verdicts (any error vs none) must agree with ours on every case except the
documented divergences below. Each divergence is asserted to still exist, so a
change on either side is noticed instead of silently drifting.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from skillsmgr.validator import validate_skill

ORACLE = os.environ.get("SKILLS_REF_PYTHON", "")

CASES = {
    "valid": ("ok-skill", "---\nname: ok-skill\ndescription: Use when testing.\n---\nBody\n"),
    "uppercase-name": ("Bad", "---\nname: Bad\ndescription: d\n---\nB\n"),
    "leading-hyphen": ("-bad", "---\nname: -bad\ndescription: d\n---\nB\n"),
    "double-hyphen": ("a--b", "---\nname: a--b\ndescription: d\n---\nB\n"),
    "too-long-name": ("a" * 65, "---\nname: " + "a" * 65 + "\ndescription: d\n---\nB\n"),
    "unicode-name": ("café", "---\nname: café\ndescription: d\n---\nB\n"),
    "dir-mismatch": ("other-dir", "---\nname: ok-skill\ndescription: d\n---\nB\n"),
    "empty-description": ("e", "---\nname: e\ndescription: \"\"\n---\nB\n"),
    "missing-description": ("m", "---\nname: m\n---\nB\n"),
    "long-description": ("l", "---\nname: l\ndescription: " + "x" * 1025 + "\n---\nB\n"),
    "long-compat": ("c", "---\nname: c\ndescription: d\ncompatibility: " + "x" * 501 + "\n---\nB\n"),
    "unknown-field": ("u", "---\nname: u\ndescription: d\nfoo: bar\n---\nB\n"),
    "allowed-tools": ("t", "---\nname: t\ndescription: d\nallowed-tools: Bash\n---\nB\n"),
    "metadata-map": ("md", "---\nname: md\ndescription: d\nmetadata:\n  k: v\n---\nB\n"),
    "no-frontmatter": ("nf", "Just body\n"),
    "unquoted-colon": ("uc", "---\nname: uc\ndescription: Use when: testing\n---\nB\n"),
}

# case -> (reference verdict is error?, our verdict is error?, why, warning key we must emit or None)
DIVERGENCES = {
    "unicode-name": (False, True, "NFKC Unicode names are R18, a locked name rule awaiting a decision", None),
    "unknown-field": (True, False, "Claude Code ignores unknown keys; R6 warns instead of failing", None),
    "unquoted-colon": (True, False, "lenient parser accepts it; the silent-failure lint warns", "description"),
}


@unittest.skipUnless(ORACLE, "set SKILLS_REF_PYTHON to an interpreter with skills_ref installed")
class SkillsRefOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dirs = {}
        for case, (dirname, text) in CASES.items():
            path = Path(cls.tmp.name) / case / dirname
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text(text, encoding="utf-8")
            cls.dirs[case] = str(path)
        script = (
            "import json,sys\nfrom pathlib import Path\n"
            "from skills_ref.validator import validate\n"
            "m=json.load(sys.stdin)\n"
            "print(json.dumps({k: validate(Path(v)) for k, v in m.items()}))\n"
        )
        done = subprocess.run([ORACLE, "-I", "-c", script], input=json.dumps(cls.dirs),
                              capture_output=True, text=True, timeout=120, check=True)
        cls.reference = json.loads(done.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def ours(self, case):
        path = Path(self.dirs[case])
        return validate_skill(path.name, path)

    def test_verdicts_agree_outside_documented_divergences(self):
        for case in CASES:
            if case in DIVERGENCES:
                continue
            with self.subTest(case=case):
                self.assertEqual(bool(self.reference[case]), bool(self.ours(case).errors),
                                 f"reference={self.reference[case]!r}")

    def test_documented_divergences_still_exist(self):
        for case, (ref_err, our_err, why, warning_key) in DIVERGENCES.items():
            with self.subTest(case=case, why=why):
                result = self.ours(case)
                self.assertEqual(bool(self.reference[case]), ref_err)
                self.assertEqual(bool(result.errors), our_err)
                if warning_key:
                    self.assertIn(warning_key, [i.key for i in result.warnings])


if __name__ == "__main__":
    unittest.main()
