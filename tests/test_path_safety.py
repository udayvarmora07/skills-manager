"""Regression tests for canonical names and filesystem containment."""

import io
import json
import shutil
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from skillsmgr import cli
from skillsmgr.loader import scan_dir
from skillsmgr.paths import contained_path
from skillsmgr.scopes import (
    edit_skill,
    get_raw,
    remove_skill,
    set_global_store,
    toggle_skill,
)
from skillsmgr.store import Store, StoreError
from skillsmgr.validator import validate_skill_name


class TestSkillNameValidation(unittest.TestCase):
    def test_accepts_canonical_skill_name(self):
        self.assertEqual(validate_skill_name("review-pr"), "review-pr")

    def test_rejects_path_fragments_and_invalid_names(self):
        for name in ("", ".", "..", "../victim", "Bad Name", "--bad", "a/"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_skill_name(name)


class TestContainedPath(unittest.TestCase):
    def test_resolves_normal_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            self.assertEqual(contained_path(root, "child"), root / "child")

    def test_rejects_parent_escape_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "link").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                contained_path(root, "..", "outside")
            with self.assertRaises(ValueError):
                contained_path(root, Path(tmp) / "outside")
            with self.assertRaises(ValueError):
                contained_path(root, "link", "file.txt")
            (outside / "SKILL.md").write_text(
                "---\nname: outside\ndescription: outside\n---\nbody\n",
                encoding="utf-8",
            )
            self.assertEqual(scan_dir(root), [])


class TestStoreAndEntryPointGuards(unittest.TestCase):
    def test_store_mutations_reject_traversal_without_touching_victim(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir = base / "manager"
            victim = base / "victim"
            victim.mkdir()
            (victim / "sentinel").write_text("keep", encoding="utf-8")
            store = Store(data_dir=data_dir)
            store.init_db()
            for operation in (
                lambda: store.get("../../victim"),
                lambda: store.edit("../../victim", description="x"),
                lambda: store.remove("../../victim", purge=True),
                lambda: store.disable("../../victim"),
                lambda: store.enable("../../victim"),
            ):
                with self.subTest(operation=operation):
                    if victim.exists():
                        shutil.rmtree(victim)
                    victim.mkdir()
                    (victim / "sentinel").write_text("keep", encoding="utf-8")
                    with self.assertRaises((StoreError, ValueError)):
                        operation()
                    self.assertTrue(victim.is_dir())
                    self.assertTrue((victim / "sentinel").is_file())

    def test_agent_scope_mutations_reject_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_home = __import__("os").environ.get("HOME")
            __import__("os").environ["HOME"] = tmp
            try:
                victim = Path(tmp) / "victim"
                victim.mkdir()
                global_store = Store(data_dir=Path(tmp) / "data")
                global_store.init_db()
                set_global_store(global_store)
                with self.assertRaises((StoreError, ValueError)):
                    remove_skill("agents", "../../victim", purge=True)
                for operation in (
                    lambda: get_raw("agents", "../../victim"),
                    lambda: edit_skill("agents", "../../victim", description="x"),
                    lambda: toggle_skill("agents", "../../victim", enable=False),
                ):
                    with self.assertRaises((StoreError, ValueError)):
                        operation()
                self.assertTrue(victim.is_dir())
            finally:
                set_global_store(None)
                if old_home is None:
                    __import__("os").environ.pop("HOME", None)
                else:
                    __import__("os").environ["HOME"] = old_home

    def test_cli_rejects_traversal_before_purge(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            victim = base / "victim"
            victim.mkdir()
            error = StringIO()
            with redirect_stderr(error):
                code = cli.main(
                    [
                        "--data-dir",
                        str(base / "manager"),
                        "remove",
                        "../../victim",
                        "--purge",
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("invalid skill name", error.getvalue())
            self.assertFalse((base / "manager" / "skills-manager.db").exists())
            self.assertTrue(victim.is_dir())

    def test_manifestless_fallback_rejects_invalid_skill_directory_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(data_dir=Path(tmp) / "manager")
            store.init_db()
            archive = Path(tmp) / "invalid-name.tar.gz"
            content = (
                "---\nname: weird-name\ndescription: invalid directory test\n---\nbody\n"
            ).encode("utf-8")
            with tarfile.open(archive, "w:gz") as tar:
                manifest = json.dumps({"skills": []}).encode("utf-8")
                manifest_info = tarfile.TarInfo("manifest.json")
                manifest_info.size = len(manifest)
                tar.addfile(manifest_info, io.BytesIO(manifest))
                skill_info = tarfile.TarInfo("skills/weird name/SKILL.md")
                skill_info.size = len(content)
                tar.addfile(skill_info, io.BytesIO(content))

            result = store.import_(archive)
            self.assertEqual(result["imported"], [])
            self.assertIn("weird name", result["skipped"])
            self.assertFalse((store.skills_dir / "weird name").exists())


if __name__ == "__main__":
    unittest.main()