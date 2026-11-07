"""R16/S5: a hostile repository's local Git config must not run programs.

``_run_git`` executes Git inside a caller-supplied repository.  Repository-local
configuration can name a program for Git to execute (``core.sshCommand`` during
a fetch, ``core.fsmonitor``, hooks, a pager, ...), so every invocation pins the
dangerous knobs with ``-c`` overrides and a scrubbed environment while leaving
credential delegation to the user's own helper or SSH agent intact.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import backup_sync


# Declared literally rather than read from the module under test: a test that
# mirrors the implementation's own table would pass even if both were wrong.
EXPECTED_OVERRIDES = (
    ("core.sshCommand", "ssh"),
    ("core.fsmonitor", "false"),
    ("core.hooksPath", os.devnull),
    ("core.askPass", ""),
    ("protocol.ext.allow", "never"),
    ("protocol.file.allow", "user"),
    ("uploadpack.packObjectsHook", ""),
    ("core.gitProxy", ""),
    ("diff.external", ""),
)
EXPECTED_CONFIG_ARGV = [
    token for key, value in EXPECTED_OVERRIDES for token in ("-c", f"{key}={value}")
]
REMOVED_VARIABLES = (
    "GIT_SSH",
    "GIT_PROXY_COMMAND",
    "GIT_EXTERNAL_DIFF",
    "GIT_ASKPASS",
    "SSH_ASKPASS",
)


class GitConfigHardeningContracts(unittest.TestCase):
    def _capture_git_calls(self, operation):
        """Run ``operation`` against a fake repo, recording argv and env."""
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((list(argv), dict(kwargs)))
            if "rev-parse" in argv:
                return mock.Mock(returncode=0, stdout="a" * 40 + "\n", stderr="")
            return mock.Mock(
                returncode=0, stdout="https://example.invalid/skills.git\n", stderr=""
            )

        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            with mock.patch.object(
                backup_sync.subprocess, "run", side_effect=fake_run
            ), mock.patch.object(
                backup_sync, "_trusted_git", return_value="/usr/bin/git"
            ):
                operation(repo)
        return calls

    def test_every_invocation_pins_config_before_the_subcommand(self):
        calls = self._capture_git_calls(
            lambda repo: backup_sync.git_remote_info(repo)
        )
        self.assertEqual(len(calls), 2)
        expected_subcommands = ["remote", "rev-parse"]
        for (argv, _kwargs), subcommand in zip(calls, expected_subcommands):
            self.assertEqual(argv[0], "/usr/bin/git")
            self.assertEqual(argv[1], "-C")
            self.assertEqual(argv[3], "--no-optional-locks")
            self.assertEqual(
                argv[4 : 4 + len(EXPECTED_CONFIG_ARGV)],
                EXPECTED_CONFIG_ARGV,
                "every override must appear as '-c key=value'",
            )
            subcommand_index = 4 + len(EXPECTED_CONFIG_ARGV)
            self.assertEqual(argv[subcommand_index], subcommand)
            for offset, (key, value) in enumerate(EXPECTED_OVERRIDES):
                self.assertEqual(argv[4 + 2 * offset], "-c")
                self.assertEqual(argv[5 + 2 * offset], f"{key}={value}")

    def test_environment_blocks_program_hooks_and_keeps_delegation(self):
        hostile = {name: "/tmp/evil-helper" for name in REMOVED_VARIABLES}
        hostile["GIT_SSH_COMMAND"] = "/tmp/evil-ssh"
        hostile["GIT_TERMINAL_PROMPT"] = "1"
        hostile["R16_KEEP_ME"] = "kept"
        with mock.patch.dict(os.environ, hostile, clear=False):
            calls = self._capture_git_calls(
                lambda repo: backup_sync.git_remote_info(repo)
            )
        self.assertTrue(calls)
        for _argv, kwargs in calls:
            environment = kwargs["env"]
            self.assertEqual(environment["GIT_SSH_COMMAND"], "ssh")
            self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
            self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
            self.assertEqual(environment["R16_KEEP_ME"], "kept")
            for name in REMOVED_VARIABLES:
                self.assertNotIn(name, environment)

    def test_repository_local_ssh_command_never_executes(self):
        git = shutil.which("git")
        if git is None:
            self.skipTest("git is not installed")
        try:
            trusted = backup_sync._trusted_git()
        except backup_sync.BackupSyncError:
            self.skipTest("no trusted git executable is available")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            marker = root / "marker"
            script = root / "hostile-ssh.sh"
            subprocess.run([git, "init", "-q", str(repo)], check=True)
            script.write_text(
                "#!/bin/sh\ntouch " + shlex.quote(str(marker)) + "\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            subprocess.run(
                [git, "-C", str(repo), "config", "core.sshCommand", str(script)],
                check=True,
            )
            subprocess.run(
                [
                    git,
                    "-C",
                    str(repo),
                    "-c",
                    "user.email=test@example.invalid",
                    "-c",
                    "user.name=Test",
                    "commit",
                    "--allow-empty",
                    "-qm",
                    "initial",
                ],
                check=True,
            )
            subprocess.run(
                [
                    git,
                    "-C",
                    str(repo),
                    "remote",
                    "add",
                    "origin",
                    "ssh://example.invalid/x.git",
                ],
                check=True,
            )
            # The sandbox has no network, so the fetch must fail; the point is
            # that it fails without running the repository's program hook.
            with self.assertRaises(backup_sync.BackupSyncError):
                backup_sync.git_fetch(repo, timeout=20)
            self.assertFalse(
                marker.exists(),
                f"repository-local core.sshCommand executed via {trusted}",
            )


if __name__ == "__main__":
    unittest.main()
