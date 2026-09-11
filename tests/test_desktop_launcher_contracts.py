"""Desktop launcher contracts (issue #9).

The recorded verdict on issue #9 rejects a bundled pywebview wrapper and allows
exactly one artefact: an unbundled, loopback-only launcher that never replaces
the dependency-free browser path. These tests pin that boundary — no new runtime
dependency, loopback-only binding, a real browser fallback when no
Chromium-family browser exists, and no packaging change.
"""

from __future__ import annotations

import ast
import contextlib
import io
import sys
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import desktop_launcher as launcher


class PureHelperTests(unittest.TestCase):
    def test_loopback_hosts_are_accepted(self):
        for host in ("127.0.0.1", "::1", "localhost"):
            with self.subTest(host=host):
                self.assertEqual(launcher.validate_host(host), host)

    def test_non_loopback_hosts_are_refused(self):
        for host in ("0.0.0.0", "192.168.1.10", "example.com", "::"):
            with self.subTest(host=host):
                with self.assertRaises(launcher.LauncherError):
                    launcher.validate_host(host)

    def test_chromium_is_preferred_in_documented_order(self):
        found = {"brave-browser": "/usr/bin/brave-browser",
                 "google-chrome": "/usr/bin/google-chrome"}
        self.assertEqual(
            launcher.find_chromium(lambda name: found.get(name)),
            "/usr/bin/google-chrome",
        )

    def test_missing_browser_returns_none(self):
        self.assertIsNone(launcher.find_chromium(lambda name: None))

    def test_window_command_uses_app_mode(self):
        command = launcher.window_command("/usr/bin/chromium", "http://127.0.0.1:8765/")
        self.assertEqual(command[0], "/usr/bin/chromium")
        self.assertIn("--app=http://127.0.0.1:8765/", command)

    def test_describe_is_honest_about_each_path(self):
        window = launcher.describe("/usr/bin/google-chrome", "http://127.0.0.1:8765/")
        self.assertIn("desktop window", window)
        self.assertIn("google-chrome", window)
        plain = launcher.describe("/usr/bin/google-chrome", "http://127.0.0.1:8765/",
                                  plain=True)
        self.assertIn("--plain", plain)
        fallback = launcher.describe(None, "http://127.0.0.1:8765/")
        self.assertIn("no Chromium-family browser found", fallback)
        self.assertIn("http://127.0.0.1:8765/", fallback)

    def test_open_target_prefers_the_window_then_falls_back(self):
        popen = mock.Mock()
        opener = mock.Mock()
        mode = launcher.open_target(
            "http://127.0.0.1:8765/", browser="/usr/bin/chromium", plain=False,
            popen=popen, opener=opener,
        )
        self.assertEqual(mode, "window")
        popen.assert_called_once()
        opener.assert_not_called()

        # No browser: the canonical browser path must still run.
        popen.reset_mock()
        opener.reset_mock()
        mode = launcher.open_target(
            "http://127.0.0.1:8765/", browser=None, plain=False,
            popen=popen, opener=opener,
        )
        self.assertEqual(mode, "browser")
        popen.assert_not_called()
        opener.assert_called_once_with("http://127.0.0.1:8765/")

    def test_open_target_survives_a_browser_that_fails_to_start(self):
        popen = mock.Mock(side_effect=OSError("no such file"))
        opener = mock.Mock()
        mode = launcher.open_target(
            "http://127.0.0.1:8765/", browser="/usr/bin/chromium", plain=False,
            popen=popen, opener=opener,
        )
        self.assertEqual(mode, "browser")
        opener.assert_called_once_with("http://127.0.0.1:8765/")

    def test_plain_flag_bypasses_app_mode(self):
        popen = mock.Mock()
        opener = mock.Mock()
        mode = launcher.open_target(
            "http://127.0.0.1:8765/", browser="/usr/bin/chromium", plain=True,
            popen=popen, opener=opener,
        )
        self.assertEqual(mode, "browser")
        popen.assert_not_called()


class RunFlowTests(unittest.TestCase):
    def test_non_loopback_host_exits_two_with_a_clean_message(self):
        lines: list[str] = []
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = launcher.run(["--host", "0.0.0.0", "--print-only"], out=lines.append)
        self.assertEqual(code, launcher.EXIT_USAGE)
        self.assertEqual(lines, [])
        self.assertIn("loopback-only", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_print_only_does_not_serve_or_open(self):
        lines: list[str] = []
        popen = mock.Mock()
        opener = mock.Mock()
        code = launcher.run(["--print-only"], server_factory=lambda: self.fail(
            "--print-only must not start a server"
        ), which=lambda name: "/usr/bin/chromium", popen=popen, opener=opener,
            out=lines.append)
        self.assertEqual(code, launcher.EXIT_OK)
        self.assertEqual(len(lines), 1)
        self.assertIn("desktop window", lines[0])
        self.assertIn("http://127.0.0.1:8765/", lines[0])
        popen.assert_not_called()
        opener.assert_not_called()

    def test_bound_host_and_url_match_so_the_host_header_is_allowed(self):
        """Issue #14 F-2: binding host X and linking host X keeps Host valid."""
        lines: list[str] = []
        launcher.run(["--host", "localhost", "--print-only"],
                     which=lambda name: None, out=lines.append)
        self.assertIn("http://localhost:8765/", lines[0])

    def test_run_serves_then_shuts_down(self):
        served = {"count": 0}

        class FakeServer:
            def serve_forever(self):
                served["count"] += 1
                raise KeyboardInterrupt

            def shutdown(self):
                served["stopped"] = True

        opened: list[str] = []
        lines: list[str] = []
        code = launcher.run(
            ["--port", "9999"],
            server_factory=lambda: FakeServer(),
            which=lambda name: "/usr/bin/chromium",
            popen=mock.Mock(),
            opener=lambda url: opened.append(url),
            out=lines.append,
        )
        self.assertEqual(code, launcher.EXIT_OK)
        self.assertEqual(served["count"], 1)
        self.assertTrue(served.get("stopped"))
        self.assertIn("http://127.0.0.1:9999/", " ".join(lines))
        self.assertIn("stopped", " ".join(lines))


class UnbundledBoundaryTests(unittest.TestCase):
    """The launcher must stay optional: no dependency, no packaged entry point."""

    def test_launcher_module_imports_only_the_standard_library(self):
        tree = ast.parse(Path(launcher.__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        third_party = {name for name in imported if name not in sys.stdlib_module_names}
        # ``skillsmgr`` is the product itself, imported lazily inside run().
        self.assertEqual(third_party, {"skillsmgr"}, sorted(third_party))

    def test_launcher_is_not_packaged_and_adds_no_console_script(self):
        pyproject = tomllib.loads(
            (Path(launcher.__file__).parent / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            pyproject["tool"]["setuptools"]["packages"]["find"]["include"],
            ["skillsmgr*"],
            "the launcher must stay outside the wheel (issue #9 verdict)",
        )
        self.assertEqual(
            list(pyproject["project"]["scripts"]), ["skills-mgr"],
            "no new console entry point: `skills-mgr webui` remains canonical",
        )

    def test_no_webview_dependency_or_import_exists(self):
        root = Path(launcher.__file__).parent
        pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertNotIn("dependencies", pyproject["project"])
        self.assertNotIn("optional-dependencies", pyproject["project"])
        for path in sorted((root / "skillsmgr").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(module=path.name):
                self.assertNotIn("import webview", text)
                self.assertNotIn("pywebview", text)

    def test_the_supported_entry_point_still_exists(self):
        """The browser path stays canonical: `webui` (alias `gui`) opens it."""
        parser_source = (Path(launcher.__file__).parent / "skillsmgr"
                         / "cli_parser.py").read_text(encoding="utf-8")
        self.assertIn('"webui"', parser_source)
        self.assertIn('aliases=["gui"]', parser_source)


if __name__ == "__main__":
    unittest.main()
