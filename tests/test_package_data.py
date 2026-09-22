"""Offline, deterministic tests for distribution package-data coverage."""

from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import check_package_data


#: The packaging gate pins the exact upstream Vue payload (SEC-9), so hermetic
#: archive fixtures must carry the real bytes rather than a placeholder.
_VENDORED_VUE = (
    Path(__file__).resolve().parent.parent / check_package_data.VUE_MEMBER
).read_bytes()
_LICENSE = (Path(__file__).resolve().parent.parent / "LICENSE").read_bytes()
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

    def _wheel_members(self) -> dict[str, bytes]:
        members = self._members()
        members.update(
            {
                "skill_control_plane-1.0.1.dist-info/METADATA": _METADATA,
                "skill_control_plane-1.0.1.dist-info/licenses/LICENSE": _LICENSE,
            }
        )
        return members

    def _sdist_members(self) -> dict[str, bytes]:
        root = "skill_control_plane-1.0.1/"
        members = {root + name: data for name, data in self._members().items()}
        members.update({root + "PKG-INFO": _METADATA, root + "LICENSE": _LICENSE})
        return members

    def test_expected_webui_members_are_sorted_and_include_vendored_vue(self):
        members = check_package_data.expected_webui_members()
        self.assertEqual(members, tuple(sorted(members)))
        self.assertIn(check_package_data.VUE_MEMBER, members)
        self.assertGreaterEqual(len(members), 1)
        self.assertIn("skillsmgr/webui/index.html", members)

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


if __name__ == "__main__":
    unittest.main()
