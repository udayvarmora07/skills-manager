"""Red-first contracts for SEC-19 trust-root selection."""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from skillsmgr import paths


class TrustRootSelectionTests(unittest.TestCase):
    def setUp(self):
        self._old = {
            key: os.environ.get(key)
            for key in ("HOME", "SKILLS_MANAGER_DATA", "XDG_DATA_HOME")
        }
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        os.environ["HOME"] = str(self.home)
        os.environ.pop("SKILLS_MANAGER_DATA", None)
        os.environ.pop("XDG_DATA_HOME", None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, old in self._old.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def test_safe_explicit_root_is_canonical_and_preserves_precedence(self):
        selected = self.base / "selected-link"
        target = self.base / "selected"
        target.mkdir()
        target.chmod(0o700)
        selected.symlink_to(target, target_is_directory=True)
        os.environ["SKILLS_MANAGER_DATA"] = str(selected)
        os.environ["XDG_DATA_HOME"] = str(self.base / "ignored-xdg")

        self.assertEqual(paths.data_dir(), target.resolve() / "skills-manager")

    def test_rejects_the_filesystem_root_as_an_environment_data_root(self):
        os.environ["SKILLS_MANAGER_DATA"] = "/"

        with self.assertRaisesRegex(ValueError, "unsafe data root"):
            paths.data_dir()

    def test_safe_xdg_root_is_used_when_explicit_override_is_blank(self):
        selected = self.base / "xdg"
        selected.mkdir()
        selected.chmod(0o700)
        os.environ["SKILLS_MANAGER_DATA"] = "  "
        os.environ["XDG_DATA_HOME"] = str(selected)

        self.assertEqual(paths.data_dir(), selected / "skills-manager")

    @unittest.skipUnless(os.name == "posix", "POSIX permission contract")
    def test_rejects_a_group_or_world_writable_selected_root(self):
        unsafe = self.base / "unsafe"
        unsafe.mkdir()
        unsafe.chmod(stat.S_IRWXU | stat.S_IWGRP)
        os.environ["SKILLS_MANAGER_DATA"] = str(unsafe)

        with self.assertRaisesRegex(ValueError, "unsafe data root"):
            paths.data_dir()

    @unittest.skipUnless(os.name == "posix", "POSIX permission contract")
    def test_upgrades_a_legacy_group_writable_manager_root_in_place(self):
        """The upgrade path SEC-19 never pinned.

        A data directory created before the ownership control landed is
        permanently unusable: every subcommand refuses, and nothing in the
        product said what to do about it. This pins that a recognisable,
        owner-held root is tightened to 0o700 with its contents intact.
        """
        manager = self.base / "skills-manager"
        manager.mkdir(mode=0o700)
        skills = manager / "skills"
        skills.mkdir(mode=0o700)
        document = skills / "demo" / "SKILL.md"
        document.parent.mkdir()
        document.write_text("---\nname: demo\n---\n\nbody\n", encoding="utf-8")
        (manager / "skills-manager.db").write_bytes(b"index")
        for path in (skills, manager):
            path.chmod(stat.S_IRWXU | stat.S_IWGRP | stat.S_IXGRP)
        os.environ["SKILLS_MANAGER_DATA"] = str(self.base)

        resolved = paths.data_dir()

        self.assertEqual(resolved, manager)
        self.assertEqual(
            stat.S_IMODE(resolved.stat().st_mode), 0o700,
            "a recognisable owner-held root should be tightened to 0o700",
        )
        # Tightening permissions must never cost the user their data.
        self.assertEqual(document.read_text(encoding="utf-8").count("name: demo"), 1)
        self.assertTrue((resolved / "skills-manager.db").is_file())

    @unittest.skipUnless(os.name == "posix", "POSIX permission contract")
    def test_refuses_to_repair_a_directory_it_does_not_recognise(self):
        """The repair must only ever touch a directory that is recognisably ours."""
        manager = self.base / "skills-manager"
        manager.mkdir(mode=0o700)
        (manager / "someone-elses-file.txt").write_text("not ours", encoding="utf-8")
        manager.chmod(stat.S_IRWXU | stat.S_IWGRP | stat.S_IXGRP)
        os.environ["SKILLS_MANAGER_DATA"] = str(self.base)

        with self.assertRaises(ValueError) as ctx:
            paths.data_dir()

        message = str(ctx.exception)
        # The refusal must say how to fix it, not only what is wrong.
        self.assertIn(f"chmod 700 {manager}", message)
        self.assertIn("SKILLS_MANAGER_DATA", message)
        self.assertEqual(
            stat.S_IMODE(manager.stat().st_mode),
            stat.S_IRWXU | stat.S_IWGRP | stat.S_IXGRP,
            "an unrecognised directory must be left exactly as it was",
        )

    @unittest.skipUnless(os.name == "posix", "POSIX permission contract")
    def test_rejects_a_new_root_directly_below_shared_tmp(self):
        selected = Path(tempfile.gettempdir()) / "skillsmgr-sec19-untrusted-root"
        if selected.exists():
            self.skipTest(f"test path already exists: {selected}")
        os.environ["SKILLS_MANAGER_DATA"] = str(selected)

        with self.assertRaisesRegex(ValueError, "unsafe data root"):
            paths.data_dir()

    @unittest.skipUnless(os.name == "posix", "POSIX permission contract")
    def test_rejects_a_group_or_world_writable_existing_ancestor(self):
        unsafe = self.base / "unsafe-parent"
        unsafe.mkdir()
        unsafe.chmod(stat.S_IRWXU | stat.S_IWOTH)
        selected = unsafe / "data"
        os.environ["XDG_DATA_HOME"] = str(selected)

        with self.assertRaisesRegex(ValueError, "unsafe data root"):
            paths.data_dir()

    def test_rejects_a_selected_file_as_a_root(self):
        selected = self.base / "not-a-directory"
        selected.write_text("not a directory", encoding="utf-8")
        os.environ["SKILLS_MANAGER_DATA"] = str(selected)

        with self.assertRaisesRegex(ValueError, "data root.*directory"):
            paths.data_dir()

    @unittest.skipUnless(os.name == "posix", "POSIX permission contract")
    def test_rejects_a_non_writable_existing_root(self):
        selected = self.base / "read-only"
        selected.mkdir()
        selected.chmod(stat.S_IRUSR | stat.S_IXUSR)
        os.environ["SKILLS_MANAGER_DATA"] = str(selected)

        try:
            with self.assertRaisesRegex(ValueError, "unsafe data root"):
                paths.data_dir()
        finally:
            selected.chmod(stat.S_IRWXU)

    def test_rejects_unsafe_explicit_override_instead_of_falling_back(self):
        unsafe = self.base / "unsafe"
        unsafe.mkdir()
        if os.name == "posix":
            unsafe.chmod(stat.S_IRWXU | stat.S_IWGRP)
        os.environ["SKILLS_MANAGER_DATA"] = str(unsafe)
        os.environ["XDG_DATA_HOME"] = str(self.base / "safe-xdg")

        if os.name == "posix":
            with self.assertRaisesRegex(ValueError, "unsafe data root"):
                paths.data_dir()
        else:
            self.assertEqual(paths.data_dir(), unsafe / "skills-manager")

    def test_relative_root_remains_absolute_and_safe(self):
        old_cwd = Path.cwd()
        os.chdir(self.base)
        self.addCleanup(os.chdir, old_cwd)
        os.environ["SKILLS_MANAGER_DATA"] = "relative-data"

        resolved = paths.data_dir()

        self.assertEqual(resolved, (self.base / "relative-data" / "skills-manager").resolve())


if __name__ == "__main__":
    unittest.main()
