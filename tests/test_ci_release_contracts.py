"""Hermetic contracts for release engineering: CI pins, release workflow, assets.

Stdlib unittest only. No network: every check reads checked-in workflow YAML
and local source/docs facts with deterministic text assertions.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import check_package_data

ROOT = Path(__file__).resolve().parent.parent

# Full-length commit SHAs are the only acceptable pin for third-party actions;
# first-party actions/* and github/* on moving tags are out of the pin policy.
_THIRD_PARTY_PIN_RE = re.compile(
    r"^\s*-\s*uses:\s*(?!actions/|github/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([^\s#]+)"
)
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _workflow_text(name: str) -> str:
    path = ROOT / ".github" / "workflows" / name
    if not path.is_file():
        raise AssertionError(f"missing workflow: .github/workflows/{name}")
    return path.read_text(encoding="utf-8")


def _third_party_pins(text: str) -> list[tuple[str, str]]:
    pins: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = _THIRD_PARTY_PIN_RE.match(line)
        if match:
            action, ref = match.group(1), match.group(2).split("#", 1)[0].strip()
            pins.append((action, ref))
    return pins


def _job_ids(text: str) -> list[str]:
    jobs_block = text.split("\n  jobs:", 1)
    scope = jobs_block[1] if len(jobs_block) == 2 else text
    ids = re.findall(r"(?m)^  ([a-z0-9_.-]+):\s*$", scope)
    return ids


class CiWorkflowContractTests(unittest.TestCase):
    def test_ci_matrix_covers_supported_interpreters(self):
        text = _workflow_text("ci.yml")
        self.assertIn('"3.10"', text)
        self.assertIn('"3.14"', text)
        for version in ("3.10", "3.11", "3.12", "3.13", "3.14"):
            self.assertIn(f'"{version}"', text, f"CI matrix is missing Python {version}")

    def test_ci_declares_least_privilege_permissions(self):
        text = _workflow_text("ci.yml")
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\s*$")

    def test_ci_tests_exact_release_artifacts(self):
        text = _workflow_text("ci.yml")
        self.assertIn("artifacts", text)
        self.assertIn("check_package_data.py --dist-dir", text)
        self.assertIn("python3 -m unittest discover -s tests", text)
        self.assertIn("smoke_store.py", text)
        self.assertIn("smoke_web.py", text)

    def test_ci_xplat_job_uses_portable_python_executable(self):
        text = _workflow_text("ci.yml")
        xplat = text.split("\n  xplat:", 1)[1].split("\n  browser:", 1)[0]
        self.assertNotIn("run: python3 -m", xplat)
        # compileall takes directories and files, so the command works on
        # Windows runners where the shell does not expand "skillsmgr/*.py".
        self.assertIn("run: python -m compileall", xplat)
        self.assertNotIn("*.py", xplat)
        self.assertIn("run: python -m unittest", xplat)

    def test_ci_browser_job_runs_harness_and_both_frontend_syntax_checks(self):
        text = _workflow_text("ci.yml")
        browser = text.split("\n  browser:", 1)[1]
        self.assertIn("python3 browser_harness.py", browser)
        self.assertIn("node --check skillsmgr/webui/app.js", browser)
        self.assertIn("node --check skillsmgr/webui/domain.js", browser)

    def test_ci_has_separate_named_jobs(self):
        ids = set(_job_ids(_workflow_text("ci.yml")))
        for expected in ("unit", "adversarial", "package", "docs", "browser", "xplat"):
            self.assertIn(expected, ids, f"CI is missing the {expected!r} job")

    def test_third_party_actions_are_pinned_to_shas(self):
        for name in ("ci.yml", "release.yml"):
            path = ROOT / ".github" / "workflows" / name
            if not path.is_file():
                continue
            for action, ref in _third_party_pins(path.read_text(encoding="utf-8")):
                self.assertRegex(
                    ref,
                    _SHA_RE,
                    f"{name}: third-party action {action}@{ref} is not pinned to a full commit SHA",
                )

    def test_unpinned_workflow_fixture_is_rejected(self):
        fixture = "jobs:\n  test:\n    steps:\n      - uses: pypa/gh-action-pypi-publish@v1\n"
        self.assertEqual(_third_party_pins(fixture), [("pypa/gh-action-pypi-publish", "v1")])
        for _, ref in _third_party_pins(fixture):
            self.assertIsNone(
                _SHA_RE.match(ref),
                "fixture unpinned ref must fail the SHA pin assertion pattern",
            )


class CrossPlatformContractTests(unittest.TestCase):
    def test_contained_path_enforces_nt_separators_on_all_platforms(self):
        from skillsmgr import path_safety

        with self.assertRaises(ValueError):
            path_safety.contained_path(Path("/tmp/xyz-skills-root"), "a\\b")

    def test_archive_member_backslash_is_always_unsafe(self):
        from skillsmgr import archive

        with self.assertRaises(archive.ArchiveError):
            archive.normalize_member_name("skills\\evil")

    def test_package_data_inspects_both_archive_kinds_offline(self):
        self.assertGreaterEqual(len(check_package_data.expected_webui_members()), 1)
        self.assertIn(
            check_package_data.VUE_MEMBER,
            check_package_data.expected_webui_members(),
        )

    def test_package_data_supports_build_once_dist_dir_inspection(self):
        import contextlib
        import io
        import tarfile
        import tempfile
        import zipfile

        members = {
            name: (b"vue payload" if name == check_package_data.VUE_MEMBER else b"asset")
            for name in check_package_data.expected_webui_members()
        }
        with tempfile.TemporaryDirectory() as directory:
            dist_dir = Path(directory) / "dist"
            dist_dir.mkdir()
            wheel = dist_dir / "skills_manager-1.0.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_STORED) as archive:
                for name, data in sorted(members.items()):
                    archive.writestr(name, data)
            sdist = dist_dir / "skills_manager-1.0.0.tar.gz"
            with tarfile.open(sdist, "w:gz") as archive:
                for name, data in sorted(members.items()):
                    info = tarfile.TarInfo("skills_manager-1.0.0/" + name)
                    info.size = len(data)
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(data))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check_package_data.run_check(dist_dir=dist_dir), 0)
            wheel.unlink()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(check_package_data.run_check(dist_dir=dist_dir), 1)

    def test_dist_dir_install_flag_actually_installs_exact_artifacts(self):
        import contextlib
        import io
        import tarfile
        import tempfile
        import zipfile
        from unittest import mock

        members = {
            name: (b"vue payload" if name == check_package_data.VUE_MEMBER else b"asset")
            for name in check_package_data.expected_webui_members()
        }
        with tempfile.TemporaryDirectory() as directory:
            dist_dir = Path(directory) / "dist"
            dist_dir.mkdir()
            wheel = dist_dir / "skills_manager-1.0.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_STORED) as archive:
                for name, data in sorted(members.items()):
                    archive.writestr(name, data)
            sdist = dist_dir / "skills_manager-1.0.0.tar.gz"
            with tarfile.open(sdist, "w:gz") as archive:
                for name, data in sorted(members.items()):
                    info = tarfile.TarInfo("skills_manager-1.0.0/" + name)
                    info.size = len(data)
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(data))
            installed: list[str] = []
            with mock.patch.object(
                check_package_data, "clean_install", side_effect=lambda artifact, root: installed.append(artifact.name)
            ), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check_package_data.run_check(dist_dir=dist_dir, install=True), 0)
            self.assertEqual(installed, [wheel.name, sdist.name])


class ReleaseWorkflowContractTests(unittest.TestCase):
    def test_release_is_tag_gated_with_protected_environments(self):
        text = _workflow_text("release.yml")
        self.assertIn('"v*"', text)
        self.assertIn("environment: release", text)
        self.assertIn("environment: testpypi", text)

    def test_release_uses_trusted_publishing_without_long_lived_tokens(self):
        text = _workflow_text("release.yml")
        self.assertIn("id-token: write", text)
        self.assertIn("pypa/gh-action-pypi-publish@", text)
        self.assertNotIn("TWINE_PASSWORD", text)
        self.assertNotIn("PYPI_API_TOKEN", text)

    def test_release_validates_tag_before_build_and_publish(self):
        text = _workflow_text("release.yml")
        self.assertIn("Verify release tag matches package version", text)
        self.assertIn('tag != "v" + version', text)
        self.assertLess(text.index("Verify release tag matches package version"), text.index("publish-testpypi:"))

    def test_release_builds_once_tests_exact_artifacts_and_attests(self):
        text = _workflow_text("release.yml")
        self.assertIn("python3 -m build --wheel --sdist --outdir dist", text)
        self.assertIn("check_package_data.py --dist-dir dist", text)
        self.assertIn("attest-build-provenance", text)
        self.assertIn("test.pypi.org/legacy", text)

    def test_release_creates_github_release_and_verifies_post_publish(self):
        text = _workflow_text("release.yml")
        self.assertIn("action-gh-release@", text)
        self.assertIn("skills-manager==", text)
        self.assertIn("vue.global.prod.js", text)
        self.assertIn("SKILLS_MANAGER_DATA=$(mktemp -d)", text)

    def test_release_declares_least_privilege_permissions(self):
        text = _workflow_text("release.yml")
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read\s*$")
        self.assertIn("contents: write", text)
        github_release = text.split("\n  github-release:", 1)[1]
        self.assertNotIn("id-token: write", github_release.split("\n  ", 1)[0])


class ReleaseClaimContractTests(unittest.TestCase):
    def test_pypi_claims_are_qualified_until_publication_is_real(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("PyPI badge tracks a future release", readme)
        self.assertIn("pip install skills-manager", readme)

    def test_pypi_badge_is_removed(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("img.shields.io/pypi/v/skills-manager", readme)


if __name__ == "__main__":
    unittest.main()
