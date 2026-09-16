"""Focused regressions for FM-11 skill-directory name validation."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr.frontmatter import dump_frontmatter
from skillsmgr.validator import validate_skill


class ValidatorDirectoryNameTests(unittest.TestCase):
    def _write_skill(self, skill_dir: Path, frontmatter_name: str) -> None:
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            dump_frontmatter(
                {
                    "name": frontmatter_name,
                    "description": "Use this when validating directory names.",
                }
            )
            + "# Instructions\n\nFollow these instructions.\n",
            encoding="utf-8",
        )

    def test_frontmatter_name_is_checked_against_directory_not_caller(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "directory-name"
            self._write_skill(skill_dir, "caller-name")

            result = validate_skill("caller-name", skill_dir)

            self.assertTrue(
                any(
                    issue.message
                    == "frontmatter name 'caller-name' does not match directory name "
                    "'directory-name'"
                    for issue in result.errors
                ),
                [issue.message for issue in result.issues],
            )

    def test_matching_caller_and_directory_remains_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "directory-name"
            self._write_skill(skill_dir, "directory-name")

            result = validate_skill("directory-name", skill_dir)

            self.assertTrue(result.valid, [issue.message for issue in result.issues])

    def test_caller_name_format_validation_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "directory-name"
            self._write_skill(skill_dir, "directory-name")

            result = validate_skill("not a valid name", skill_dir)

            self.assertTrue(
                any("name must match lowercase pattern" in issue.message for issue in result.errors),
                [issue.message for issue in result.issues],
            )

    def test_symlinked_scope_root_keeps_skill_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_root = root / "real-scope-root"
            linked_root = root / "linked-scope-root"
            real_root.mkdir()
            try:
                os.symlink(real_root, linked_root, target_is_directory=True)
            except (OSError, NotImplementedError):  # pragma: no cover - platform guard
                self.skipTest("symlinks are unavailable on this platform")

            skill_dir = linked_root / "directory-name"
            self._write_skill(skill_dir, "directory-name")

            result = validate_skill("directory-name", skill_dir)

            self.assertTrue(result.valid, [issue.message for issue in result.issues])
            self.assertFalse(
                any("does not match directory name" in issue.message for issue in result.errors),
                [issue.message for issue in result.issues],
            )

    def test_in_root_skill_alias_uses_resolved_directory_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_dir = root / "directory-name"
            alias_dir = root / "alias-name"
            self._write_skill(real_dir, "directory-name")
            try:
                os.symlink(real_dir, alias_dir, target_is_directory=True)
            except (OSError, NotImplementedError):  # pragma: no cover - platform guard
                self.skipTest("symlinks are unavailable on this platform")

            result = validate_skill("alias-name", alias_dir)

            self.assertTrue(result.valid, [issue.message for issue in result.issues])
            self.assertFalse(
                any("does not match directory name" in issue.message for issue in result.errors),
                [issue.message for issue in result.issues],
            )

    def test_unresolvable_directory_returns_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "directory-name"
            self._write_skill(skill_dir, "directory-name")

            for exc in (
                OSError("symlink loop"),
                RuntimeError("symlink loop"),
                ValueError("symlink loop"),
            ):
                with self.subTest(exception=type(exc).__name__):
                    with mock.patch.object(
                        Path, "resolve", side_effect=[skill_dir, exc]
                    ):
                        result = validate_skill("directory-name", skill_dir)

                    self.assertFalse(result.valid)
                    self.assertEqual(
                        [issue.message for issue in result.errors],
                        ["cannot resolve skill directory: symlink loop"],
                    )


if __name__ == "__main__":
    unittest.main()
