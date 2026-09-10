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
        return {name: (b"vue payload" if name == check_package_data.VUE_MEMBER else b"asset") for name in expected}

    def test_expected_webui_members_are_sorted_and_include_vendored_vue(self):
        members = check_package_data.expected_webui_members()
        self.assertEqual(members, tuple(sorted(members)))
        self.assertIn(check_package_data.VUE_MEMBER, members)
        self.assertGreaterEqual(len(members), 1)
        self.assertIn("skillsmgr/webui/index.html", members)

    def test_wheel_and_sdist_have_exact_webui_member_set_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            members = self._members()
            wheel = self._write_wheel(root, members)
            sdist = self._write_sdist(root, {"skill_control_plane-1.0.1/" + name: data for name, data in members.items()})

            wheel_report = check_package_data.inspect_archive(wheel)
            sdist_report = check_package_data.inspect_archive(sdist)

            expected = check_package_data.expected_webui_members()
            self.assertEqual(wheel_report.webui_members, expected)
            self.assertEqual(sdist_report.webui_members, expected)
            self.assertEqual(wheel_report.vue_size, len(b"vue payload"))
            self.assertEqual(sdist_report.vue_size, len(b"vue payload"))

    def test_missing_package_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            members = self._members()
            members.pop(check_package_data.VUE_MEMBER)
            wheel = self._write_wheel(Path(directory), members)
            with self.assertRaisesRegex(AssertionError, "missing=.*vue.global.prod.js"):
                check_package_data.inspect_archive(wheel)


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
