"""Red-first contracts for the next five low/info audit remediations.

The tests are intentionally hermetic and repository-local.  They pin the
workflow supply-chain boundary (SEC-14), the browser/launcher execution
boundary (SEC-15/SEC-16), release governance (SEC-17), and preventive secret
hygiene (SEC-18).
"""

from __future__ import annotations

import os
import re
import stat
import tempfile
import unittest
from pathlib import Path

import browser_harness
import desktop_launcher
from skillsmgr.launcher_security import trusted_executable


ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

EXPECTED_FIRST_PARTY_SHAS = {
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/setup-python": "a26af69be951a213d495a4c3e4e4022e16d87065",
    "actions/setup-node": "49933ea5288caeca8642d1e84afbd3f7d6820020",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
    "actions/download-artifact": "d3f86a106a0bac45b974a628896c90dbdf5c8093",
    "actions/attest-build-provenance": "96b4a1ef7235a096b17240c259729fdd70c83d45",
}

# A step may declare its action on the same line as the list dash
# (``- uses: actions/x@sha``) or on the line after ``- name:``
# (``        uses: actions/x@sha``).  Both are ordinary YAML and both are used
# in this repository.  The leading ``-`` is therefore OPTIONAL here.
#
# It was not, and that made this gate report PASS about nine pin sites it never
# read -- including the release attestation, all five artifact
# download/upload sites, and setup-node.  Repinning
# ``actions/attest-build-provenance`` to a floating ``@v2`` tag left this test
# green.  This is the repository's own recorded failure mode: a gate that
# reports PASS about a path it cannot see is not a gate.
_FIRST_PARTY_PIN_RE = re.compile(
    r"^\s*(?:-\s+)?uses:\s+(actions/[A-Za-z0-9_.-]+)@([^\s#]+)"
)


def _first_party_pins(text: str) -> list[tuple[str, str]]:
    """Every ``actions/*`` pin in *text*, in either YAML step form."""
    return [(m.group(1), m.group(2)) for m in
            (_FIRST_PARTY_PIN_RE.match(line) for line in text.splitlines()) if m]


def _unreviewed_first_party_pins(workflow: Path) -> list[tuple[str, str]]:
    """Pins in *workflow* whose ref is not that action's reviewed full SHA."""
    return [
        (action, ref)
        for action, ref in _first_party_pins(workflow.read_text(encoding="utf-8"))
        if ref != EXPECTED_FIRST_PARTY_SHAS.get(action)
    ]


class WorkflowHardeningTests(unittest.TestCase):
    def test_sec14_every_first_party_action_is_pinned(self):
        for workflow in (WORKFLOWS / "ci.yml", WORKFLOWS / "release.yml"):
            for action, ref in _first_party_pins(workflow.read_text(encoding="utf-8")):
                self.assertEqual(
                    ref,
                    EXPECTED_FIRST_PARTY_SHAS.get(action),
                    f"{workflow.name}: {action} must use its reviewed full SHA",
                )

    def test_sec14_reads_both_yaml_step_forms(self):
        """A pin on the line after ``- name:`` is as pinned as one on the dash.

        Red-first: with a mandatory leading ``-`` this fixture yields nothing,
        so the gate covered only the sites it happened to be written against.
        """
        dash_form = "      - uses: actions/checkout@" + "a" * 40 + "\n"
        name_form = (
            "      - name: Attest\n"
            "        uses: actions/attest-build-provenance@" + "b" * 40 + "\n"
        )
        pins = _first_party_pins(dash_form + name_form)
        self.assertEqual(
            [action for action, _ in pins],
            ["actions/checkout", "actions/attest-build-provenance"],
            "both YAML step forms must be read, or the gate has a blind spot",
        )
        self.assertEqual([ref for _, ref in pins], ["a" * 40, "b" * 40])

    def test_sec14_rejects_an_unreviewed_attestation_sha(self):
        """The blind spot was exploitable, not theoretical.

        Repinning the release attestation to a floating ``@v2`` tag -- or to any
        unreviewed SHA -- used to leave this gate **green**, because the line was
        never read.  Red-first: with the old mandatory-dash parser this
        fixture yields ``[]`` and the assertion fails, which is exactly the
        silent pass being pinned shut.
        """
        reviewed = EXPECTED_FIRST_PARTY_SHAS["actions/attest-build-provenance"]
        step = "      - name: Attest\n        uses: actions/attest-build-provenance@{}\n"
        with tempfile.TemporaryDirectory() as tmp:
            workflow = Path(tmp) / "release.yml"

            workflow.write_text(step.format(reviewed), encoding="utf-8")
            self.assertEqual(_unreviewed_first_party_pins(workflow), [])

            workflow.write_text(step.format("v2"), encoding="utf-8")
            self.assertEqual(
                _unreviewed_first_party_pins(workflow),
                [("actions/attest-build-provenance", "v2")],
                "a floating tag on the attestation must be rejected",
            )

            workflow.write_text(step.format("0" * 39 + "1"), encoding="utf-8")
            self.assertEqual(
                _unreviewed_first_party_pins(workflow),
                [("actions/attest-build-provenance", "0" * 39 + "1")],
                "an unreviewed attestation SHA must be rejected",
            )

    def test_sec17_release_writer_has_a_protected_environment(self):
        text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
        writer = text.split("\n  github-release:", 1)[1].split(
            "\n  postpublish-verify:", 1
        )[0]
        self.assertIn("environment: release", writer)

    def test_sec17_codeowners_and_dependabot_cover_workflows(self):
        codeowners = ROOT / ".github" / "CODEOWNERS"
        dependabot = ROOT / ".github" / "dependabot.yml"
        self.assertTrue(codeowners.is_file())
        codeowners_text = codeowners.read_text(encoding="utf-8")
        self.assertIn("/.github/workflows/ @udayvarmora07", codeowners_text)
        self.assertIn("* @udayvarmora07", codeowners_text)
        self.assertTrue(dependabot.is_file())
        dependabot_text = dependabot.read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: github-actions", dependabot_text)
        self.assertIn("directory: /", dependabot_text)
        self.assertIn("schedule:", dependabot_text)


class LauncherHardeningTests(unittest.TestCase):
    def test_sec15_keeps_the_chrome_sandbox_and_binds_cdp_to_loopback(self):
        source = (ROOT / "browser_harness.py").read_text(encoding="utf-8")
        self.assertNotIn("--no-sandbox", source)
        self.assertIn("--remote-debugging-address=127.0.0.1", source)
        self.assertIn("--remote-debugging-port=0", source)

    def test_sec16_browser_and_node_lookups_use_trusted_executables(self):
        source = (ROOT / "browser_harness.py").read_text(encoding="utf-8")
        self.assertIn("trusted_executable", source)
        self.assertIn("_node()", source)
        self.assertIn("subprocess.run([_node(),", source)
        desktop_source = (ROOT / "desktop_launcher.py").read_text(encoding="utf-8")
        self.assertIn("trusted_executable", desktop_source)

    @unittest.skipUnless(os.name == "posix", "ownership checks are POSIX-specific")
    def test_sec16_rejects_a_world_writable_path_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fake-browser"
            path.write_text("#!/bin/sh\n", encoding="utf-8")
            path.chmod(stat.S_IRWXU | stat.S_IWGRP | stat.S_IWOTH)
            self.assertIsNone(
                trusted_executable("fake-browser", which=lambda _name: str(path))
            )

    def test_sec16_accepts_a_private_executable_path_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fake-browser"
            path.write_text("#!/bin/sh\n", encoding="utf-8")
            path.chmod(stat.S_IRWXU)
            self.assertEqual(
                trusted_executable("fake-browser", which=lambda _name: str(path)),
                str(path.resolve()),
            )

    @unittest.skipUnless(os.name == "posix", "PATH permission checks are POSIX-specific")
    def test_sec16_skips_an_unsafe_earlier_path_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsafe_dir = root / "unsafe"
            safe_dir = root / "safe"
            unsafe_dir.mkdir()
            safe_dir.mkdir()
            unsafe_dir.chmod(0o700)
            safe_dir.chmod(0o700)
            unsafe = unsafe_dir / "node"
            safe = safe_dir / "node"
            for path in (unsafe, safe):
                path.write_text("#!/bin/sh\n", encoding="utf-8")
                path.chmod(0o700)
            unsafe_dir.chmod(0o777)
            old_path = os.environ.get("PATH")
            os.environ["PATH"] = os.pathsep.join((str(unsafe_dir), str(safe_dir)))
            try:
                self.assertEqual(trusted_executable("node"), str(safe.resolve()))
            finally:
                if old_path is None:
                    os.environ.pop("PATH", None)
                else:
                    os.environ["PATH"] = old_path


class GitignoreHygieneTests(unittest.TestCase):
    def test_sec18_ignores_local_configuration_databases_and_keys(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", ".env.*", "*.db", "*.sqlite*", "*.pem", "*.key", ".netrc"):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, text)


if __name__ == "__main__":
    unittest.main()
