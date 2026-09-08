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

    def test_force_import_invalid_manifest_name_cannot_delete_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = Store(data_dir=base / "manager")
            store.init_db()
            victim = base / "victim"
            victim.mkdir()
            (victim / "sentinel").write_text("keep", encoding="utf-8")
            archive = base / "invalid-force.tar.gz"
            manifest = json.dumps({"skills": [{"name": "../victim"}]}).encode("utf-8")
            with tarfile.open(archive, "w:gz") as tar:
                info = tarfile.TarInfo("manifest.json")
                info.size = len(manifest)
                tar.addfile(info, io.BytesIO(manifest))

            result = store.import_(archive, force=True)
            self.assertEqual(result["imported"], [])
            self.assertTrue(victim.is_dir())
            self.assertTrue((victim / "sentinel").is_file())

    def test_archive_traversal_member_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = Store(data_dir=base / "manager")
            store.init_db()
            victim = base / "victim.txt"
            victim.write_text("keep", encoding="utf-8")
            archive = base / "traversal.tar.gz"
            payload = b"escape"
            with tarfile.open(archive, "w:gz") as tar:
                manifest = b'{"skills": []}'
                manifest_info = tarfile.TarInfo("manifest.json")
                manifest_info.size = len(manifest)
                tar.addfile(manifest_info, io.BytesIO(manifest))
                evil = tarfile.TarInfo("../../victim.txt")
                evil.size = len(payload)
                tar.addfile(evil, io.BytesIO(payload))

            with self.assertRaises(StoreError):
                store.import_(archive, force=True)
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep")

    def test_force_import_rejects_unsafe_member_before_deleting_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = Store(data_dir=base / "manager")
            store.init_db()
            store.create("demo", "Original demo", body="original")
            archive = base / "force-traversal.tar.gz"
            manifest = b'{"skills": [{"name": "demo"}]}'
            with tarfile.open(archive, "w:gz") as tar:
                manifest_info = tarfile.TarInfo("manifest.json")
                manifest_info.size = len(manifest)
                tar.addfile(manifest_info, io.BytesIO(manifest))
                evil = tarfile.TarInfo("skills/demo/../../victim")
                evil.size = 6
                tar.addfile(evil, io.BytesIO(b"escape"))

            with self.assertRaises(StoreError):
                store.import_(archive, force=True)
            self.assertEqual(store.get("demo")["description"], "Original demo")
            self.assertFalse((base / "victim").exists())

    def test_archive_duplicate_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(data_dir=Path(tmp) / "manager")
            store.init_db()
            archive = Path(tmp) / "duplicate.tar.gz"
            manifest = b'{"skills": []}'
            with tarfile.open(archive, "w:gz") as tar:
                for _ in range(2):
                    info = tarfile.TarInfo("manifest.json")
                    info.size = len(manifest)
                    tar.addfile(info, io.BytesIO(manifest))

            with self.assertRaises(StoreError):
                store.import_(archive)

    def test_archive_special_member_is_rejected_without_tar_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(data_dir=Path(tmp) / "manager")
            store.init_db()
            archive = Path(tmp) / "symlink.tar.gz"
            manifest = b'{"skills": []}'
            with tarfile.open(archive, "w:gz") as tar:
                manifest_info = tarfile.TarInfo("manifest.json")
                manifest_info.size = len(manifest)
                tar.addfile(manifest_info, io.BytesIO(manifest))
                link = tarfile.TarInfo("skills/demo/link")
                link.type = tarfile.SYMTYPE
                link.linkname = "../../outside"
                tar.addfile(link)

            original_filter = getattr(tarfile, "data_filter", None)
            had_filter = hasattr(tarfile, "data_filter")
            if had_filter:
                delattr(tarfile, "data_filter")
            try:
                with self.assertRaises(StoreError):
                    store.import_(archive)
            finally:
                if had_filter:
                    tarfile.data_filter = original_filter

    def test_archive_hard_link_and_fifo_members_are_rejected(self):
        for member_type, label in ((tarfile.LNKTYPE, "hardlink"), (tarfile.FIFOTYPE, "fifo")):
            with self.subTest(member_type=label), tempfile.TemporaryDirectory() as tmp:
                store = Store(data_dir=Path(tmp) / "manager")
                store.init_db()
                archive = Path(tmp) / f"{label}.tar.gz"
                manifest = b'{"skills": []}'
                with tarfile.open(archive, "w:gz") as tar:
                    manifest_info = tarfile.TarInfo("manifest.json")
                    manifest_info.size = len(manifest)
                    tar.addfile(manifest_info, io.BytesIO(manifest))
                    special = tarfile.TarInfo(f"skills/demo/{label}")
                    special.type = member_type
                    if member_type == tarfile.LNKTYPE:
                        special.linkname = "SKILL.md"
                    tar.addfile(special)

                with self.assertRaises(StoreError):
                    store.import_(archive)

    def test_valid_archive_import_works_without_tar_data_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Store(data_dir=Path(tmp) / "source")
            source.init_db()
            source.create("demo", "Demo skill", body="valid archive")
            archive = source.export()
            target = Store(data_dir=Path(tmp) / "target")
            target.init_db()

            original_filter = getattr(tarfile, "data_filter", None)
            had_filter = hasattr(tarfile, "data_filter")
            if had_filter:
                delattr(tarfile, "data_filter")
            try:
                result = target.import_(archive)
            finally:
                if had_filter:
                    tarfile.data_filter = original_filter

            self.assertEqual(result["imported"], ["demo"])
            self.assertEqual(target.get("demo")["description"], "Demo skill")

    def test_malformed_trash_entries_are_ignored_by_all_trash_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(data_dir=Path(tmp) / "manager")
            store.init_db()
            store.create("demo", "Demo skill")
            store.remove("demo")

            malformed = store.trash_dir / "demo_x-2026-09-08_00-00-00Z"
            malformed.mkdir()
            (malformed / "sentinel").write_text("keep", encoding="utf-8")

            listed = store.trash_list()
            self.assertEqual([row["name"] for row in listed], ["demo"])
            with self.assertRaises(StoreError):
                store.restore("demo_x")
            purge = store.purge_trash()
            self.assertEqual(purge["purged"], ["demo"])
            self.assertTrue(malformed.is_dir())
            self.assertTrue((malformed / "sentinel").is_file())
            self.assertEqual(store.doctor()["trash_count"], 0)


if __name__ == "__main__":
    unittest.main()
