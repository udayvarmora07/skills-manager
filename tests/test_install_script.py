"""Contracts for the one-command installers (`install.sh`, `install.ps1`).

The shell installer is run for real under `/bin/sh` with a sandboxed PATH:
fake `uv`, `pipx` and `python3` executables record the arguments they were
given, so every branch is exercised offline and nothing touches the network
or the real home directory. A real install from this checkout is done by the
cross-platform CI job (`.github/workflows/ci.yml`, job `xplat`).
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = ROOT / "install.sh"
INSTALL_PS1 = ROOT / "install.ps1"

# The only host programs install.sh may rely on besides the fakes.
HOST_TOOLS = (
    "sh", "sed", "dirname", "mkdir", "ln", "readlink", "grep", "id", "rm", "cat",
)
# Needed by the fakes below, not by install.sh.
FAKE_TOOLS = ("chmod",)

FAKE_UV = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_LOG"
case "$1 $2" in
    "tool list") cat "$FAKE_STATE/uv-tools" 2>/dev/null ;;
esac
exit 0
"""

FAKE_PIPX = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_LOG"
case "$1" in
    list) cat "$FAKE_STATE/pipx-list" 2>/dev/null ;;
esac
exit 0
"""

# A python3 that is "3.12": answers the version probe, creates a fake venv
# whose pip records its arguments and drops a working skills-mgr script.
FAKE_PYTHON = """#!/bin/sh
case "$1" in
    -c) exit 0 ;;
    -m)
        if [ "$2" = venv ]; then
            mkdir -p "$3/bin"
            printf 'home = fake\\n' > "$3/pyvenv.cfg"
            cat > "$3/bin/python" <<'PY'
#!/bin/sh
printf 'pip %s\\n' "$*" >> "$FAKE_LOG"
dir=$(dirname "$0")
printf '#!/bin/sh\\necho "skills-mgr 9.9.9"\\n' > "$dir/skills-mgr"
chmod +x "$dir/skills-mgr"
PY
            chmod +x "$3/bin/python"
            printf 'venv %s\\n' "$3" >> "$FAKE_LOG"
            exit 0
        fi ;;
esac
exit 1
"""


def _write_exe(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@unittest.skipUnless(os.name == "posix" and Path("/bin/sh").exists(), "POSIX shell required")
class InstallShTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.bin = self.tmp / "sandbox-bin"
        self.bin.mkdir()
        self.state = self.tmp / "state"
        self.state.mkdir()
        self.log = self.tmp / "calls.log"
        for tool in HOST_TOOLS + FAKE_TOOLS:
            found = shutil.which(tool)
            if found is None:
                self.skipTest(f"host tool {tool!r} not found")
            (self.bin / tool).symlink_to(found)

    def add_fake(self, name: str, body: str) -> None:
        _write_exe(self.bin / name, body)

    def run_sh(self, *args: str, expect: int = 0) -> subprocess.CompletedProcess:
        env = {
            "PATH": str(self.bin),
            "HOME": str(self.home),
            "FAKE_LOG": str(self.log),
            "FAKE_STATE": str(self.state),
        }
        proc = subprocess.run(
            ["/bin/sh", str(INSTALL_SH), *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            proc.returncode, expect, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
        return proc

    def calls(self) -> list[str]:
        if not self.log.exists():
            return []
        return self.log.read_text(encoding="utf-8").splitlines()

    # --- method selection -------------------------------------------------

    def test_uv_is_preferred_and_gets_python_and_extras(self):
        self.add_fake("uv", FAKE_UV)
        self.add_fake("pipx", FAKE_PIPX)
        self.run_sh("--version", "1.0.2", "--with-tiktoken")
        self.assertIn(
            "tool install --force --python >=3.11 --with tiktoken skill-control-plane==1.0.2",
            self.calls(),
        )
        self.assertFalse(any(c.startswith("install") for c in self.calls()), "pipx must not run")

    def test_pipx_is_used_when_uv_is_absent(self):
        self.add_fake("pipx", FAKE_PIPX)
        self.add_fake("python3", FAKE_PYTHON)
        self.run_sh("--with-tiktoken")
        calls = self.calls()
        self.assertIn(
            f"install --force --python {self.bin / 'python3'} skill-control-plane", calls
        )
        self.assertIn("inject skill-control-plane tiktoken", calls)

    def test_venv_install_links_a_working_command(self):
        self.add_fake("python3", FAKE_PYTHON)
        out = self.run_sh("--source").stdout
        prefix = self.home / ".local/share/skill-control-plane/venv"
        link = self.home / ".local/bin/skills-mgr"
        self.assertIn(f"venv {prefix}", self.calls())
        self.assertTrue(
            any(c.startswith("pip -m pip install") and c.endswith("main.tar.gz") for c in self.calls()),
            self.calls(),
        )
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(os.readlink(link)), prefix / "bin/skills-mgr")
        self.assertIn("installed: skills-mgr 9.9.9", out)
        # PATH does not contain ~/.local/bin here, and the rc files stay untouched.
        self.assertIn('export PATH="', out)
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), [".local"])

    def test_xdg_data_home_and_explicit_dirs_are_honoured(self):
        self.add_fake("python3", FAKE_PYTHON)
        prefix = self.tmp / "custom/env"
        bindir = self.tmp / "custom/bin"
        self.run_sh("--method", "venv", "--prefix", str(prefix), "--bin-dir", str(bindir))
        self.assertTrue((prefix / "pyvenv.cfg").exists())
        self.assertTrue((bindir / "skills-mgr").is_symlink())
        self.assertFalse((self.home / ".local").exists())

    def test_dry_run_changes_nothing(self):
        self.add_fake("python3", FAKE_PYTHON)
        out = self.run_sh("--dry-run").stdout
        self.assertIn("-m venv", out)
        self.assertIn("dry run: nothing was changed", out)
        self.assertEqual(self.calls(), [])
        self.assertEqual(list(self.home.iterdir()), [])

    # --- refusals ---------------------------------------------------------

    def test_no_python_and_no_uv_is_a_clear_error(self):
        proc = self.run_sh(expect=1)
        self.assertIn("no Python 3.11 or newer found", proc.stderr)
        self.assertIn("uv", proc.stderr)

    def test_bad_arguments_are_refused_before_anything_runs(self):
        self.add_fake("uv", FAKE_UV)
        for args, message in (
            (("--method", "brew"), "--method must be uv, pipx or venv"),
            (("--version", "1.0; rm -rf ~"), "invalid --version"),
            (("--version", "-e"), "invalid --version"),
            (("--source", "--version", "1.0.2"), "cannot be combined"),
            (("--from", "--editable"), "cannot start with '-'"),
            (("--frobnicate",), "unknown option"),
            (("--method",), "needs a value"),
        ):
            with self.subTest(args=args):
                proc = self.run_sh(*args, expect=1)
                self.assertIn(message, proc.stderr)
        self.assertEqual(self.calls(), [])

    def test_existing_non_venv_prefix_is_not_touched(self):
        self.add_fake("python3", FAKE_PYTHON)
        prefix = self.tmp / "precious"
        prefix.mkdir()
        (prefix / "keep.txt").write_text("mine", encoding="utf-8")
        proc = self.run_sh("--prefix", str(prefix), expect=1)
        self.assertIn("is not a virtual environment", proc.stderr)
        self.assertEqual([p.name for p in prefix.iterdir()], ["keep.txt"])

    def test_existing_regular_file_at_link_path_is_not_replaced(self):
        self.add_fake("python3", FAKE_PYTHON)
        bindir = self.home / ".local/bin"
        bindir.mkdir(parents=True)
        (bindir / "skills-mgr").write_text("someone else's", encoding="utf-8")
        proc = self.run_sh(expect=1)
        self.assertIn("is not a link", proc.stderr)
        self.assertEqual((bindir / "skills-mgr").read_text(encoding="utf-8"), "someone else's")

    # --- uninstall --------------------------------------------------------

    def test_uninstall_removes_venv_and_link_but_never_skill_data(self):
        self.add_fake("python3", FAKE_PYTHON)
        self.run_sh()
        data = self.home / ".local/share/skills-manager/skills/demo"
        data.mkdir(parents=True)
        (data / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
        out = self.run_sh("--uninstall").stdout
        self.assertIn("removed", out)
        self.assertFalse((self.home / ".local/share/skill-control-plane/venv").exists())
        self.assertFalse((self.home / ".local/bin/skills-mgr").exists())
        self.assertTrue((data / "SKILL.md").exists())

    def test_uninstall_leaves_a_foreign_link_alone(self):
        bindir = self.home / ".local/bin"
        bindir.mkdir(parents=True)
        (bindir / "skills-mgr").symlink_to("/opt/elsewhere/skills-mgr")
        out = self.run_sh("--uninstall").stdout
        self.assertIn("leaving", out)
        self.assertTrue((bindir / "skills-mgr").is_symlink())

    def test_uninstall_uses_uv_and_pipx_only_when_they_hold_the_tool(self):
        self.add_fake("uv", FAKE_UV)
        self.add_fake("pipx", FAKE_PIPX)
        out = self.run_sh("--uninstall").stdout
        self.assertIn("nothing installed by this script was found", out)
        self.assertNotIn("tool uninstall skill-control-plane", self.calls())
        (self.state / "uv-tools").write_text("skill-control-plane v1.0.2\n- skills-mgr\n", encoding="utf-8")
        (self.state / "pipx-list").write_text("skill-control-plane 1.0.2\n", encoding="utf-8")
        self.run_sh("--uninstall")
        self.assertIn("tool uninstall skill-control-plane", self.calls())
        self.assertIn("uninstall skill-control-plane", self.calls())

    # --- structure --------------------------------------------------------

    def test_script_body_runs_only_from_its_last_line(self):
        # `curl | sh` on a cut-short download must not execute half a script.
        lines = [l for l in INSTALL_SH.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(lines[-1], 'main "$@"')

    def test_script_never_edits_shell_startup_files(self):
        text = INSTALL_SH.read_text(encoding="utf-8")
        for rc in (".bashrc", ".zshrc", ".profile", ".bash_profile"):
            self.assertNotIn(rc, text)
        self.assertNotIn("| sh", text.split("set -eu", 1)[1])

    @unittest.skipUnless(shutil.which("shellcheck"), "shellcheck not installed")
    def test_shellcheck_is_clean(self):
        proc = subprocess.run(
            ["shellcheck", "-s", "sh", str(INSTALL_SH)], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class InstallPs1Tests(unittest.TestCase):
    def test_powershell_installer_offers_the_same_options(self):
        text = INSTALL_PS1.read_text(encoding="utf-8")
        for option in ("$Method", "$Version", "$Source", "$From", "$WithTiktoken",
                       "$Prefix", "$DryRun", "$Uninstall"):
            self.assertIn(option, text)
        for method in ("'uv'", "'pipx'", "'venv'"):
            self.assertIn(method, text)

    def test_powershell_installer_never_changes_the_user_environment(self):
        text = INSTALL_PS1.read_text(encoding="utf-8")
        self.assertNotIn("SetEnvironmentVariable", text)
        self.assertNotIn("$PROFILE", text)
        self.assertNotIn("Invoke-Expression", text)

    @unittest.skipUnless(shutil.which("pwsh"), "pwsh not installed")
    def test_powershell_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                ["pwsh", "-NoProfile", "-File", str(INSTALL_PS1), "-Method", "venv",
                 "-Prefix", str(Path(tmp) / "env"), "-DryRun"],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("dry run: nothing was changed", proc.stdout)
            self.assertFalse((Path(tmp) / "env").exists())


if __name__ == "__main__":
    unittest.main()
