"""``browser_harness.py`` can now say "this host cannot run it", not just "no".

Backlog 9.4b. The precedent is ``.redesign/verify.sh``: 9.4 taught the e2e
loop that a missing THIRD-PARTY module is a host fact, while a missing PROJECT
module is a broken checkout. ``step "browser: browser_harness.py"`` is a
different call site and had the same blind spot in a worse form -- it printed
``FAILED: <label>`` for both.

These are executed behaviours, not source greps. Each test below runs the real
``run()`` with one capability removed and reads the exit code and the JSON the
harness actually printed, because the defect this row is about is a REPORTING
defect and a test that reads the source reports PASS about a path it cannot
see -- this repository's own recurring failure, and the reason the row says
"do not assume it is UNRUN: read its exit path first".

Every test redirects HOME/XDG_DATA_HOME/SKILLS_MANAGER_DATA at throwaway
directories before importing the harness (RULES #8: never touch the real home).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@contextlib.contextmanager
def _throwaway_environment():
    """Point every data root at a temp dir for the duration of the block."""
    with tempfile.TemporaryDirectory(prefix="harness-report-") as directory:
        base = Path(directory)
        saved = {
            key: os.environ.get(key)
            for key in ("HOME", "XDG_DATA_HOME", "SKILLS_MANAGER_DATA")
        }
        os.environ["HOME"] = str(base / "home")
        os.environ["XDG_DATA_HOME"] = str(base / "home" / ".local" / "share")
        os.environ["SKILLS_MANAGER_DATA"] = str(base / "data")
        (base / "home").mkdir(parents=True, exist_ok=True)
        try:
            yield
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


@contextlib.contextmanager
def _harness_argv():
    """`run()` calls `parser.parse_args()`, which reads the real `sys.argv`.

    Under `unittest` that is the test runner's own argv, so without this the
    first thing the harness did was exit 2 on an unrecognised flag -- which is
    also how this file found out that 2 is the wrong code to have chosen.
    """
    saved = sys.argv
    sys.argv = ["browser_harness.py"]
    try:
        yield
    finally:
        sys.argv = saved


def _load_harness():
    with _throwaway_environment():
        sys.path.insert(0, str(ROOT))
        try:
            import browser_harness  # noqa: PLC0415 - deliberately late

            return browser_harness
        finally:
            sys.path.remove(str(ROOT))


class HarnessReportTests(unittest.TestCase):
    """The three states a caller must be able to tell apart."""

    def setUp(self):
        self.harness = _load_harness()
        # The harness is a MODULE, so a stub assigned in one test is still
        # there for the next. The first version of this file replaced `_chrome`
        # and never gave it back, and the following test failed on a reason
        # string left over from its predecessor -- a test reporting about the
        # previous test's world, which is the same class as the row's own
        # unreproducible measurement. `addCleanup` restores whatever the
        # individual test chose to stub.
        for name in ("_chrome", "_node"):
            original = getattr(self.harness, name)
            self.addCleanup(setattr, self.harness, name, original)

    # -- the state the row is about -----------------------------------------

    def test_a_host_without_chrome_exits_with_its_own_code(self):
        with _throwaway_environment(), _harness_argv():
            self.harness._chrome = lambda: (_ for _ in ()).throw(
                RuntimeError("Chrome/Chromium is required for browser_harness.py (no match)")
            )
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = self.harness.run()
        self.assertEqual(
            code,
            self.harness.EXIT_CANNOT_RUN,
            "a host with no trusted Chrome must not report itself as a product defect",
        )

    def test_that_state_still_prints_a_report_a_reader_can_parse(self):
        with _throwaway_environment(), _harness_argv():
            self.harness._chrome = lambda: (_ for _ in ()).throw(
                RuntimeError("Chrome/Chromium is required for browser_harness.py (no match)")
            )
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.harness.run()
        report = json.loads(stream.getvalue())
        self.assertIs(report["ran"], False)
        self.assertIs(report["passed"], False)
        self.assertIn("Chrome", report["reason"])

    def test_the_two_codes_are_distinct_and_both_non_zero(self):
        self.assertNotEqual(self.harness.EXIT_DEFECT, self.harness.EXIT_CANNOT_RUN)
        for name in ("EXIT_DEFECT", "EXIT_CANNOT_RUN"):
            self.assertNotEqual(getattr(self.harness, name), 0, f"{name} must fail its caller")

    def test_the_cannot_run_code_is_not_the_one_argparse_already_uses(self):
        """`argparse` exits 2 on a bad flag. Choosing 2 would have reclassified
        `--typo` as "this host cannot run it" -- a third state wearing a
        second state's clothes, and found by running the thing rather than by
        reasoning about it."""
        bad_flag = subprocess.run(
            [sys.executable, str(ROOT / "browser_harness.py"), "--no-such-flag"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(bad_flag.returncode, 2)
        self.assertNotEqual(
            bad_flag.returncode,
            self.harness.EXIT_CANNOT_RUN,
            "a mistyped flag must never read as a host that cannot run the harness",
        )

    def test_a_missing_node_is_the_same_state_as_a_missing_chrome(self):
        """The other half of the capability precheck, and the one nobody
        measured: `_node()` is only reached once a probe is about to run, so a
        host without Node used to fail AFTER building a fixture and starting a
        server."""
        with _throwaway_environment(), _harness_argv():
            self.harness._node = lambda: (_ for _ in ()).throw(
                RuntimeError("a trusted Node executable is required (no match)")
            )
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = self.harness.run()
        self.assertEqual(code, self.harness.EXIT_CANNOT_RUN)
        self.assertIn("Node", json.loads(stream.getvalue())["reason"])

    # -- the direction the row demands proof for ---------------------------

    def test_a_missing_project_module_is_not_reclassified_as_cannot_run(self):
        """The other side of the rule: a broken checkout must stay red.

        The script is COPIED into an empty directory and run from there: Python
        puts the script's own directory first on `sys.path`, so running the
        repository copy would have imported the repository's `skillsmgr/` and
        passed -- the first version of this test asserted `returncode == 0`
        and failed for exactly that reason.
        """
        with tempfile.TemporaryDirectory(prefix="harness-noproj-") as directory:
            base = Path(directory)
            shutil.copy(ROOT / "browser_harness.py", base / "browser_harness.py")
            environment = dict(os.environ)
            environment["PYTHONPATH"] = ""
            environment["HOME"] = str(base / "home")
            environment["XDG_DATA_HOME"] = str(base / "share")
            environment["SKILLS_MANAGER_DATA"] = str(base / "data")
            completed = subprocess.run(
                [sys.executable, str(base / "browser_harness.py")],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                timeout=120,
            )
        self.assertNotEqual(completed.returncode, 0, "a broken checkout must not pass")
        self.assertNotEqual(
            completed.returncode,
            self.harness.EXIT_CANNOT_RUN,
            "ModuleNotFoundError for a PROJECT module is a defect, not a host fact",
        )
        self.assertIn("ModuleNotFoundError", completed.stderr)

    # -- the claim the harness makes ---------------------------------------

    def test_passed_and_the_exit_code_share_one_predicate(self):
        """`passed` and the exit code were two spellings of one question.

        Before this row the success path read `return 1 if failures else 0`
        and printed `"passed": not failures` -- two expressions that could
        drift. The mutation this rejects is inverting one of them, which is
        exactly the shape of the row's own (unreproducible) claim that the
        harness printed `passed: true` and still exited non-zero.
        """
        source = (ROOT / "browser_harness.py").read_text(encoding="utf-8")
        self.assertIn("return EXIT_DEFECT if failures else 0", source)
        self.assertIn('"passed": not failures', source)
        self.assertNotIn("return 1 if failures else 0", source)

    def test_every_report_carries_the_ran_key(self):
        """A reader that only ever saw `passed` cannot tell "nothing was
        checked" from "nothing was wrong" -- opposite facts."""
        source = (ROOT / "browser_harness.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("_emit(") - 1, source.count('"ran":'), "each report states `ran`")
        self.assertEqual(source.count("_emit(") - 1, 3, "three report sites: pass, no-Chrome, no-DevTools")


if __name__ == "__main__":  # pragma: no cover - manual invocation
    unittest.main()