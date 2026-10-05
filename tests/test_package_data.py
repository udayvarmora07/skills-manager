"""Offline, deterministic tests for distribution package-data coverage."""

from __future__ import annotations

import io
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import check_package_data


_REPO_ROOT = Path(__file__).resolve().parent.parent
#: The packaging gate pins the exact upstream Vue payload (SEC-9), so hermetic
#: archive fixtures must carry the real bytes rather than a placeholder.
_VENDORED_VUE = (_REPO_ROOT / check_package_data.VUE_MEMBER).read_bytes()
_LICENSE = (_REPO_ROOT / "LICENSE").read_bytes()
_METADATA = (
    b"Metadata-Version: 2.4\n"
    b"Name: skill-control-plane\n"
    b"Version: 1.0.1\n"
    b"License-Expression: MIT\n"
    b"License-File: LICENSE\n"
    b"\n"
)


class PackageDataArchiveTests(unittest.TestCase):
    def _write_wheel(self, root: Path, members: dict[str, bytes]) -> Path:
        path = root / "skill_control_plane-1.0.1-py3-none-any.whl"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in sorted(members.items()):
                archive.writestr(name, data)
        return path

    def _write_sdist(self, root: Path, members: dict[str, bytes]) -> Path:
        path = root / "skill_control_plane-1.0.1.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mtime = 0
                archive.addfile(info, io.BytesIO(data))
        return path

    def _members(self) -> dict[str, bytes]:
        expected = check_package_data.expected_webui_members()
        return {name: (_VENDORED_VUE if name == check_package_data.VUE_MEMBER else b"asset") for name in expected}

    @staticmethod
    def _example_members() -> dict[str, bytes]:
        """Real example bytes, so the fixture matches what a build would ship."""

        root = _REPO_ROOT / "skillsmgr" / "examples"
        return {
            (Path("skillsmgr") / "examples" / path.relative_to(root)).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def _wheel_members(self, *, examples: bool = True) -> dict[str, bytes]:
        members = self._members()
        if examples:
            members.update(self._example_members())
        members.update(
            {
                "skill_control_plane-1.0.1.dist-info/METADATA": _METADATA,
                "skill_control_plane-1.0.1.dist-info/licenses/LICENSE": _LICENSE,
            }
        )
        return members

    def _sdist_members(self, *, examples: bool = True) -> dict[str, bytes]:
        root = "skill_control_plane-1.0.1/"
        members = {root + name: data for name, data in self._members().items()}
        if examples:
            members.update({root + name: data for name, data in self._example_members().items()})
        members.update({root + "PKG-INFO": _METADATA, root + "LICENSE": _LICENSE})
        return members

    def test_expected_webui_members_are_sorted_and_include_vendored_vue(self):
        members = check_package_data.expected_webui_members()
        self.assertEqual(members, tuple(sorted(members)))
        self.assertIn(check_package_data.VUE_MEMBER, members)
        self.assertGreaterEqual(len(members), 1)
        self.assertIn("skillsmgr/webui/index.html", members)

    # -- packaged example skills (audit A8) ---------------------------------
    #
    # `examples/skills-manager-management/SKILL.md` is the only artifact that
    # lets an AI agent drive this tool safely.  Before this contract existed the
    # gate was green on artifacts that silently dropped it, so an installed
    # distribution had no agent entry point at all.

    def test_expected_example_members_are_sorted_and_ship_the_management_skill(self):
        members = check_package_data.expected_example_members()
        self.assertEqual(members, tuple(sorted(members)))
        self.assertTrue(members, "the gate needs at least one packaged example to assert")
        self.assertIn("skillsmgr/examples/skills-manager-management/SKILL.md", members)

    def test_wheel_and_sdist_carry_the_exact_example_member_set_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = self._write_wheel(root, self._wheel_members())
            sdist = self._write_sdist(root, self._sdist_members())
            expected = check_package_data.expected_example_members()
            self.assertEqual(check_package_data.inspect_archive(wheel).example_members, expected)
            self.assertEqual(check_package_data.inspect_archive(sdist).example_members, expected)

    def test_artifact_that_drops_or_invents_an_example_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing_wheel = self._write_wheel(root, self._wheel_members(examples=False))
            with self.assertRaisesRegex(AssertionError, r"example package-data mismatch.*missing="):
                check_package_data.inspect_archive(missing_wheel)
            missing_sdist = self._write_sdist(root, self._sdist_members(examples=False))
            with self.assertRaisesRegex(AssertionError, r"example package-data mismatch.*missing="):
                check_package_data.inspect_archive(missing_sdist)

            extra = self._wheel_members()
            extra["skillsmgr/examples/not-a-real-example/SKILL.md"] = b"---\nname: nope\n---\n"
            extra_wheel = self._write_wheel(root, extra)
            with self.assertRaisesRegex(AssertionError, r"example package-data mismatch.*unexpected="):
                check_package_data.inspect_archive(extra_wheel)

    def test_packaged_example_bytes_must_match_the_repository_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            members = self._wheel_members()
            name = "skillsmgr/examples/skills-manager-management/SKILL.md"
            original = members[name]
            self.assertIn(b"Manual opt-in installation", original)
            members[name] = original.replace(b"Manual opt-in installation", b"Tampered")
            wheel = self._write_wheel(root, members)
            with self.assertRaisesRegex(AssertionError, "differs from the repository source"):
                check_package_data.inspect_archive(wheel)

    def test_example_document_must_be_a_loadable_skill_named_after_its_directory(self):
        shipped = self._example_members()["skillsmgr/examples/skills-manager-management/SKILL.md"]
        self.assertIsNone(
            check_package_data.example_document_error(
                "skillsmgr/examples/skills-manager-management/SKILL.md", shipped
            )
        )
        with self.subTest("not utf-8"):
            self.assertIn("not valid UTF-8", check_package_data.example_document_error(
                "skillsmgr/examples/demo/SKILL.md", b"---\nname: demo\n---\n\xff\xfe"
            ))
        with self.subTest("no frontmatter"):
            self.assertIn("declares no frontmatter block", check_package_data.example_document_error(
                "skillsmgr/examples/demo/SKILL.md", b"# just markdown\n"
            ))
        with self.subTest("no name"):
            self.assertIn("declares no frontmatter name", check_package_data.example_document_error(
                "skillsmgr/examples/demo/SKILL.md", b"---\ndescription: hi\n---\nbody\n"
            ))
        with self.subTest("name does not match directory"):
            self.assertIn("does not match its directory", check_package_data.example_document_error(
                "skillsmgr/examples/demo/SKILL.md", b"---\nname: other\ndescription: hi\n---\nbody\n"
            ))

    def test_install_probe_asserts_the_example_reaches_site_packages(self):
        # The archive check proves the bytes are in the artifact; only a clean
        # install proves an installed distribution actually exposes them. The
        # probe path is package-relative, because `skillsmgr.__file__` already
        # resolves to the installed package directory.
        self.assertIn("examples/skills-manager-management/SKILL.md", check_package_data.INSTALL_PROBE)
        self.assertIn("webui/static/vendor/vue.global.prod.js", check_package_data.INSTALL_PROBE)

    def test_forbidden_members_are_still_rejected(self):
        forbidden = {
            "tests/test_store.py",
            "docs/01-architecture.md",
            ".env",
            "config/.env",
            ".netrc",
            "skills-manager.db",
            "skillsmgr/__pycache__/store.cpython-312.pyc",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for member in sorted(forbidden):
                with self.subTest(member=member):
                    members = self._wheel_members()
                    members[member] = b"payload"
                    wheel = self._write_wheel(root, members)
                    with self.assertRaisesRegex(AssertionError, "must never be published"):
                        check_package_data.inspect_archive(wheel)

    def test_wheel_and_sdist_have_exact_webui_member_set_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            members = self._wheel_members()
            wheel = self._write_wheel(root, members)
            sdist = self._write_sdist(root, self._sdist_members())

            wheel_report = check_package_data.inspect_archive(wheel)
            sdist_report = check_package_data.inspect_archive(sdist)

            expected = check_package_data.expected_webui_members()
            self.assertEqual(wheel_report.webui_members, expected)
            self.assertEqual(sdist_report.webui_members, expected)
            self.assertEqual(wheel_report.vue_size, len(_VENDORED_VUE))
            self.assertEqual(sdist_report.vue_size, len(_VENDORED_VUE))

    def test_missing_package_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            members = self._wheel_members()
            members.pop(check_package_data.VUE_MEMBER)
            wheel = self._write_wheel(Path(directory), members)
            with self.assertRaisesRegex(AssertionError, "missing=.*vue.global.prod.js"):
                check_package_data.inspect_archive(wheel)

    def test_license_metadata_and_bytes_are_required_for_both_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = self._write_wheel(root, self._wheel_members())
            sdist = self._write_sdist(root, self._sdist_members())
            self.assertEqual(check_package_data.inspect_archive(wheel).license_files,
                             ("skill_control_plane-1.0.1.dist-info/licenses/LICENSE",))
            self.assertEqual(check_package_data.inspect_archive(sdist).license_files, ("LICENSE",))

            broken = self._wheel_members()
            broken["skill_control_plane-1.0.1.dist-info/licenses/LICENSE"] = b"wrong"
            broken_wheel = self._write_wheel(root, broken)
            with self.assertRaisesRegex(AssertionError, "bytes differ"):
                check_package_data.inspect_archive(broken_wheel)

    def test_missing_license_member_or_legacy_classifier_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = self._wheel_members()
            missing.pop("skill_control_plane-1.0.1.dist-info/licenses/LICENSE")
            missing_wheel = self._write_wheel(root, missing)
            with self.assertRaisesRegex(AssertionError, "missing its declared LICENSE"):
                check_package_data.inspect_archive(missing_wheel)

            legacy = self._wheel_members()
            legacy["skill_control_plane-1.0.1.dist-info/METADATA"] = _METADATA.replace(
                b"\n\n", b"\nClassifier: License :: OSI Approved :: MIT License\n\n"
            )
            legacy_wheel = self._write_wheel(root, legacy)
            with self.assertRaisesRegex(AssertionError, "deprecated license classifier"):
                check_package_data.inspect_archive(legacy_wheel)


class PackageDataBuildToolTests(unittest.TestCase):
    def test_build_command_is_exact_and_missing_tool_is_unavailable(self):
        result = mock.Mock(returncode=1, stdout="", stderr="/usr/bin/python3: No module named build")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with mock.patch("check_package_data.subprocess.run", return_value=result) as run:
                with self.assertRaises(check_package_data.BuildUnavailable):
                    check_package_data.build_distributions(Path(directory), output)
            command = run.call_args.args[0]
            self.assertEqual(command[1:5], ["-m", "build", "--wheel", "--sdist"])
            self.assertEqual(command[5:7], ["--outdir", str(output)])

    def test_dist_dir_install_receives_absolute_artifact_paths(self):
        """Regression: ``--dist-dir dist --install`` ran pip inside a temporary
        cwd while passing the *relative* artifact path, so the install could
        never locate the file it was asked to install.  CI never combines the two
        flags, which is why this stayed latent."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist = root / "dist"
            dist.mkdir()
            (dist / "a-1.0-py3-none-any.whl").write_bytes(b"")
            (dist / "a-1.0.tar.gz").write_bytes(b"")
            # Restore the cwd *before* the TemporaryDirectory is cleaned up.
            # An addCleanup would run after the `with` block exits, leaving the
            # process inside the directory it is trying to delete -- which
            # Linux allows and Windows refuses with WinError 32, so the test
            # passed locally and failed on every Windows leg.
            previous = os.getcwd()
            try:
                os.chdir(root)
                report = check_package_data.ArchiveReport(
                    path=dist / "a-1.0-py3-none-any.whl", kind="wheel", webui_members=(), vue_size=0
                )
                with mock.patch("check_package_data.inspect_archive", return_value=report), mock.patch(
                    "check_package_data.clean_install"
                ) as install:
                    # The project root stays the real checkout; only the *dist
                    # dir* is relative, which is the shape
                    # `--dist-dir dist --install` uses and the defect this pins.
                    code = check_package_data.run_check(
                        check_package_data.ROOT, install=True, dist_dir=Path("dist")
                    )
            finally:
                os.chdir(previous)
            self.assertEqual(code, 0)
            recorded = [call.args[0] for call in install.call_args_list]
            self.assertEqual(len(recorded), 2)
            for path in recorded:
                self.assertTrue(path.is_absolute(), path)
                self.assertTrue(path.is_file(), path)

    def test_missing_example_directory_is_a_clean_failure_not_an_empty_pass(self):
        """Zero examples must fail loudly rather than pass vacuously.

        `expected_webui_members` behaves this way for the web UI; the example
        set needs the same property or deleting the whole directory would
        silently satisfy an "exact match" against nothing.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(AssertionError, "missing packaged example directory"):
                check_package_data.expected_example_members(root)

    def test_corrupt_artifact_is_a_clean_failure_not_a_traceback(self):
        """A truncated or mislabelled artifact must read as FAIL, not crash.

        `inspect_archive` lets archive-format errors escape, so a corrupt
        wheel reached the release job as an unhandled ``BadZipFile``
        traceback instead of the gate's own verdict.
        """

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken-1.0-py3-none-any.whl").write_bytes(b"this is not a zip")
            (root / "broken-1.0.tar.gz").write_bytes(b"this is not a gzip stream")
            code = check_package_data.run_check(check_package_data.ROOT, dist_dir=root)
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
