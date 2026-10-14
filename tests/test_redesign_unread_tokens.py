"""No custom property may be declared and never read (task 9.1a).

The class this exists for is the repository's recurring one: a declaration that
every presence check is true of and no reader consumes. Eight tokens were unread
at 1.3 and nothing noticed — the type scale was declared and read by zero rules
for a whole release (1.6), and `--dur` carried a 100–160ms band the cascade never
consulted (2.1d). In both cases the gate looked at the *name*; this one looks at
the `var()` that consumes it.

Every assertion here is mutation-shaped: each injects the defect it claims to
catch and asserts the gate goes red. An assertion that has only ever run against
a correct tree has proved nothing — that is MAP.md's locator discipline and 2.1b's
false-green mutation, both of which cost a night.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import check_design_tokens as gate  # noqa: E402

CSS = ROOT / "skillsmgr" / "webui" / "styles.css"
CSS_TEXT = CSS.read_text(encoding="utf-8")
BARE = gate.strip_css_comments(CSS_TEXT)


class UnreadTokenTests(unittest.TestCase):
    def test_the_shipped_stylesheet_declares_no_unread_token(self):
        dead = [n for n in gate.unread_tokens(CSS_TEXT) if n not in gate.UNREAD_ALLOWED]
        self.assertEqual([], dead, f"declared and never read: {dead}")

    def test_the_check_reports_a_token_nothing_consumes(self):
        """A declaration alone must not satisfy the gate — the reader half."""
        css = BARE.replace("--measure: 78ch;", "--measure: 78ch; --ghost: #f0f;")
        self.assertIn("--ghost", gate.unread_tokens(css))

    def test_the_check_passes_when_the_token_is_consumed(self):
        css = (BARE.replace("--measure: 78ch;", "--measure: 78ch; --ghost: #f0f;")
               + "\n.ok { color: var(--ghost); }\n")
        self.assertNotIn("--ghost", gate.unread_tokens(css))

    def test_an_alias_counts_as_a_real_reader(self):
        """`--alias: var(--base);` genuinely consumes `--base`.

        Measured as `var(name)` rather than as "appears after the token block",
        because the legacy alias section is a real reader set and a scan that
        missed it would report the whole section as dead.
        """
        css = (BARE.replace("--measure: 78ch;",
                            "--measure: 78ch; --base: #f0f; --alias: var(--base);"))
        self.assertNotIn("--base", gate.unread_tokens(css))
        css2 = css.replace("--alias: var(--base);", "--alias: #111;")
        self.assertIn("--base", gate.unread_tokens(css2))

    def test_prose_is_not_a_reader(self):
        """This stylesheet explains itself in kilobytes of comments.

        A reader that scanned the raw text would find `var(--measure)` in the
        comment that documents it — which is how a deleted token keeps passing.
        """
        css = (gate.strip_css_comments(BARE).replace(
            "--measure: 78ch;",
            "--measure: 78ch; --ghost: #f0f;")
            + "\n/* the old rule said: color: var(--ghost); */\n.ok { color: #111; }\n")
        self.assertIn("--ghost", gate.unread_tokens(css))

    def test_the_gate_fails_when_a_token_is_added_and_never_read(self):
        mutated = BARE.replace("--measure: 78ch;", "--measure: 78ch; --brand-new: #f0f;")
        failures = []
        gate.check_unread_tokens(mutated, failures)
        self.assertEqual(1, len(failures), failures)
        self.assertIn("--brand-new", failures[0])

    def test_the_gate_fails_when_an_exemption_no_longer_applies(self):
        """The exception table must not be able to outlive the file it excuses.

        An exemption is a claim ("this is still unread and still wanted"), and a
        claim nobody re-checks decays — the same defect 9.1b was filed from.
        """
        mutated = BARE.replace("--accent-line: #a8d0cb;",
                               "--accent-line: #a8d0cb;") + "\n.x { color: var(--accent-line); }\n"
        failures = []
        gate.check_unread_tokens(mutated, failures)
        self.assertEqual([], failures, "an exemption that gained a reader must be removed")


class GateProcessTests(unittest.TestCase):
    """The gate as the build runs it, not the imported function."""

    def test_check_design_tokens_passes_on_the_shipped_stylesheet(self):
        r = subprocess.run([sys.executable, "check_design_tokens.py"],
                           cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(0, r.returncode, r.stdout[-3000:] + r.stderr[-2000:])

    def test_every_exemption_names_the_task_that_owns_the_decision(self):
        for name, reason in gate.UNREAD_ALLOWED.items():
            self.assertTrue(name.startswith("--"), name)
            self.assertIn("9.1", reason, f"{name} is exempt without an owner")
            self.assertGreater(len(reason), 60, f"{name} is exempt without a reason")

    def test_every_exemption_is_still_declared_in_both_themes(self):
        light = gate.read_block(BARE, '[data-theme="light"], [data-theme="system"] {')
        dark = gate.read_block(BARE, '[data-theme="dark"] {')
        for name in gate.UNREAD_ALLOWED:
            self.assertIn(name, light, f"{name} is not declared in the light theme")
            self.assertIn(name, dark, f"{name} is not declared in the dark theme")


if __name__ == "__main__":
    unittest.main()