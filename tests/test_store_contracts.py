"""Hermetic contract coverage for every public :class:`Store` operation.

These tests intentionally assert independently-derived filesystem/index results;
they do not mock the Store implementation or depend on a user's data directory.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from skillsmgr.frontmatter import dump_frontmatter
from skillsmgr.store import (
    SkillNotFound,
    Store,
    StoreError,
    list_snapshots,
    read_snapshot,
    write_snapshot,
)



def document(name: str, description: str = "A useful skill", body: str = "Body.\n") -> str:
    return dump_frontmatter({"name": name, "description": description}) + body


class StoreContractCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["SKILLS_MANAGER_DATA"] = self.tmp.name
        self.store = Store()
        self.store.init_db()

    def write_external(self, name="external", text=None):
        root = Path(self.tmp.name) / "external" / name
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(
            text if text is not None else document(name), encoding="utf-8"
        )
        return root


class TestStoreConstructionAndCrud(StoreContractCase):
    def test_init_db_creates_layout_and_schema(self):
        self.assertTrue(self.store.skills_dir.is_dir())
        self.assertTrue(self.store.trash_dir.is_dir())
        self.assertTrue(self.store.templates_dir.is_dir())
        self.assertTrue(self.store.backups_dir.is_dir())
        with sqlite3.connect(self.store.db_path) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertTrue({"skills", "history", "meta"} <= tables)
            self.assertEqual(
                conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
                "1",
            )

    def test_create_persists_options_and_returns_path(self):
        result = self.store.create(
            "  configured ",
            "  Use this skill when configuring apps. ",
            license="MIT",
            category="devops",
            compatibility="Python",
            version="2.0",
            allowed_tools=[" shell ", "", "git"],
            metadata_extra={"owner": "platform"},
            body="Instructions",
        )
        self.assertEqual(result["name"], "configured")
        path = Path(result["path"])
        self.assertTrue(path.joinpath("SKILL.md").is_file())
        record = self.store.get("configured")
        self.assertEqual(record["description"], "Use this skill when configuring apps.")
        self.assertEqual(record["category"], "devops")
        self.assertEqual(record["license"], "MIT")
        self.assertEqual(record["version"], "2.0")
        self.assertTrue(record["body"].endswith("Instructions\n"))
        self.assertEqual(record["portable_frontmatter"]["allowed-tools"], ["shell", "git"])

    def test_create_rejects_empty_and_oversized_inputs(self):
        with self.assertRaisesRegex(StoreError, "description is required"):
            self.store.create("empty", "  ")
        with self.assertRaises(StoreError):
            self.store.create("long", "x" * 1025)
        with self.assertRaises(StoreError):
            self.store.create("compat", "ok", compatibility="x" * 501)
        with self.assertRaises(StoreError):
            self.store.create("../escape", "ok")

    def test_add_accepts_skill_file_and_custom_name(self):
        source = self.write_external("source", document("imported", "Imported"))
        result = self.store.add(source / "SKILL.md", name="imported")
        self.assertEqual(result["name"], "imported")
        self.assertEqual(self.store.get("imported")["description"], "Imported")
        self.assertEqual(self.store.history("imported", limit=1)[0]["action"], "add")

    def test_add_rejects_bad_source_duplicate_and_frontmatter_name(self):
        with self.assertRaisesRegex(StoreError, "not a directory"):
            self.store.add(Path(self.tmp.name) / "missing")
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(StoreError, "must contain SKILL.md"):
            self.store.add(empty)
        source = self.write_external("source", document("source"))
        with self.assertRaises(StoreError):
            self.store.add(source, name="different")
        self.store.create("taken", "Taken")
        with self.assertRaises(StoreError):
            self.store.add(self.write_external("other", document("other")), name="taken")

    def test_get_and_edit_missing_disabled_invalid_and_noop(self):
        with self.assertRaises(SkillNotFound):
            self.store.edit("missing", description="x")
        with self.assertRaises(StoreError):
            self.store.edit("../bad", description="x")
        self.store.create("demo", "Original", body="old")
        self.assertFalse(self.store.edit("demo")["changed"])
        with self.assertRaises(StoreError):
            self.store.edit("demo", description=" ")
        with self.assertRaises(StoreError):
            self.store.edit("demo", description="x" * 1025)
        with self.assertRaises(StoreError):
            self.store.edit("demo", compatibility="x" * 501)
        self.store.disable("demo")
        with self.assertRaisesRegex(StoreError, "disabled"):
            self.store.edit("demo", body="new")
        with self.assertRaises(SkillNotFound):
            self.store.get("missing")

    def test_list_search_and_resync_are_index_and_filesystem_contracts(self):
        self.store.create("zeta", "Unrelated", category="ops", body="unique body")
        self.store.create("alpha", "Deploy application", category="dev")
        self.store.disable("zeta")
        names = [entry["name"] for entry in self.store.list()]
        self.assertEqual(names, ["alpha", "zeta"])
        empty_results = self.store.search("")
        self.assertEqual([entry["name"] for entry in empty_results], ["alpha", "zeta"])
        self.assertTrue(all("body" not in entry for entry in empty_results))
        self.assertEqual(self.store.search("unique")[0]["name"], "zeta")
        self.assertEqual(self.store.search("ops")[0]["name"], "zeta")
        with self.assertRaises(ValueError):
            self.store.search("*x" * 12)

        # Drift is repaired from disk, with no history side effect.
        before_history = len(self.store.history())
        external = self.store.skills_dir / "on-disk"
        external.mkdir()
        (external / "SKILL.md").write_text(document("on-disk", "Disk only"), encoding="utf-8")
        (self.store.skills_dir / "alpha" / "SKILL.md").write_text(
            document("alpha", "Changed on disk"), encoding="utf-8"
        )
        (self.store.skills_dir / "zeta").rename(self.store.data_dir / "removed")
        result = self.store.resync()
        self.assertEqual(result, {"added": 1, "updated": 1, "removed": 1})
        self.assertEqual(self.store.get("alpha")["description"], "Changed on disk")
        self.assertEqual(len(self.store.history()), before_history)
        self.assertTrue(external.is_dir())

    def test_db_rebuild_drops_stale_rows_but_not_files(self):
        self.store.create("demo", "Demo")
        with sqlite3.connect(self.store.db_path) as conn:
            conn.execute("INSERT INTO skills(name, status) VALUES('stale', 'active')")
            conn.commit()
        result = self.store.db_rebuild()
        self.assertEqual(result["added"], 1)
        with self.assertRaises(SkillNotFound):
            self.store.get("stale")
        self.assertTrue((self.store.skills_dir / "demo" / "SKILL.md").is_file())


class TestStoreLifecycle(StoreContractCase):
    def test_remove_errors_and_disable_enable_error_branches(self):
        with self.assertRaises(SkillNotFound):
            self.store.remove("missing")
        with self.assertRaises(SkillNotFound):
            self.store.disable("missing")
        with self.assertRaises(SkillNotFound):
            self.store.enable("missing")
        self.store.create("demo", "Demo")
        with self.assertRaisesRegex(StoreError, "already enabled"):
            self.store.enable("demo")
        self.store.disable("demo")
        with self.assertRaisesRegex(StoreError, "already disabled"):
            self.store.disable("demo")
        self.store.enable("demo")
        self.store.remove("demo")
        self.store.create("demo", "Replacement")
        with self.assertRaisesRegex(StoreError, "already exists"):
            self.store.restore("demo")
        self.store.remove("demo", purge=True)
        self.store.restore("demo")
        self.store.remove("demo", purge=True)
        with self.assertRaisesRegex(StoreError, "no trashed"):
            self.store.restore("demo")
        with self.assertRaises(SkillNotFound):
            self.store.remove("demo", purge=True)

    def test_trash_list_ignores_malformed_symlink_and_prefix_collision(self):
        self.store.create("demo", "Demo")
        self.store.remove("demo")
        trash = self.store.trash_list()
        self.assertEqual([x["name"] for x in trash], ["demo"])
        self.assertGreater(trash[0]["size_bytes"], 0)
        (self.store.trash_dir / "demo-not-a-timestamp").mkdir()
        (self.store.trash_dir / "demo-x-2024-01-01_00-00-00Z").mkdir()
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        try:
            (self.store.trash_dir / "demo-2024-01-01_00-00-00Z").symlink_to(outside)
        except (OSError, NotImplementedError):
            pass
        self.assertEqual([x["name"] for x in self.store.trash_list()], ["demo", "demo-x"])
        result = self.store.purge_trash()
        self.assertEqual(result["purged"], ["demo", "demo-x"])
        self.assertEqual(self.store.trash_list(), [])

    def test_restore_errors_for_invalid_snapshot_missing_and_conflict(self):
        self.store.create("demo", "Demo")
        with self.assertRaises(StoreError):
            self.store.restore("../bad", snapshot="x")
        with self.assertRaisesRegex(StoreError, "invalid snapshot"):
            self.store.restore("demo", snapshot="../../bad")
        with self.assertRaisesRegex(StoreError, "no snapshot"):
            self.store.restore("demo", snapshot="2024-01-01_00-00-00Z")
        self.store.remove("demo")
        with self.assertRaisesRegex(StoreError, "no snapshot"):
            self.store.restore("demo", snapshot="2024-01-01_00-00-00Z")
        with self.assertRaisesRegex(StoreError, "no trashed"):
            self.store.restore("missing")

    def test_history_filter_and_limit(self):
        self.store.create("one", "One")
        self.store.create("two", "Two")
        self.store.disable("one")
        rows = self.store.history("one", limit=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "disable")
        self.assertEqual(len(self.store.history(limit=2)), 2)
        self.assertEqual(self.store.history("missing"), [])

    def test_stats_counts_active_disabled_trashed_and_categories(self):
        self.store.create("active", "Active", category="ops")
        self.store.create("disabled", "Disabled", category="ops")
        self.store.disable("disabled")
        self.store.create("trashed", "Trashed", category="old")
        self.store.remove("trashed")
        stats = self.store.stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["active"], 2)
        self.assertEqual(stats["disabled"], 1)
        self.assertEqual(stats["trashed"], 1)
        self.assertEqual(stats["categories"], {"ops": 2})
        self.assertGreater(stats["size_bytes"], 0)
        self.assertGreater(stats["db_bytes"], 0)


class TestStoreSnapshotsAndArchives(StoreContractCase):
    def test_snapshot_helpers_validate_targets_and_read_content(self):
        with self.assertRaises(StoreError):
            write_snapshot(self.store.data_dir, "../global", "demo", "x")
        with self.assertRaises(StoreError):
            write_snapshot(self.store.data_dir, "global", "../demo", "x")
        snap = write_snapshot(self.store.data_dir, "global", "demo", "snapshot body")
        self.assertEqual(list_snapshots(self.store.data_dir, "global", "demo"), [snap])
        self.assertEqual(read_snapshot(self.store.data_dir, "global", "demo", snap), "snapshot body")
        with self.assertRaises(StoreError):
            read_snapshot(self.store.data_dir, "global", "demo", "bad")

    def test_export_default_and_backup_alias_create_tar_archives(self):
        self.store.create("demo", "Demo")
        exported = self.store.export()
        backed = self.store.backup()
        self.assertTrue(Path(exported).is_file())
        self.assertTrue(Path(backed).is_file())
        with tarfile.open(exported, "r:gz") as tar:
            manifest = json.load(tar.extractfile("manifest.json"))
        self.assertEqual(manifest["skills"][0]["name"], "demo")
        self.assertFalse(manifest["full"])

    def test_import_rejects_missing_zip_invalid_tar_and_bad_manifest(self):
        with self.assertRaises(StoreError):
            self.store.import_(Path(self.tmp.name) / "missing.tar.gz")
        zip_path = Path(self.tmp.name) / "bad.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("manifest.json", "{}")
        with self.assertRaisesRegex(StoreError, "ZIP"):
            self.store.import_(zip_path)
        invalid = Path(self.tmp.name) / "invalid.tar"
        invalid.write_bytes(b"not a tar")
        with self.assertRaises(StoreError):
            self.store.import_(invalid)
        bad_manifest = Path(self.tmp.name) / "manifest.tar.gz"
        with tarfile.open(bad_manifest, "w:gz") as tar:
            payload = b'{}'
            info = tarfile.TarInfo("manifest.json")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        with self.assertRaises(StoreError):
            self.store.import_(bad_manifest)

    def test_import_skips_existing_without_force_and_force_replaces(self):
        self.store.create("demo", "Original", body="old")
        source = Store(data_dir=Path(self.tmp.name) / "source")
        source.init_db()
        source.create("demo", "Imported", body="new")
        archive = source.export(Path(self.tmp.name) / "import.tar.gz")
        skipped = self.store.import_(archive)
        self.assertEqual(skipped["imported"], [])
        self.assertEqual(self.store.get("demo")["description"], "Original")
        imported = self.store.import_(archive, force=True)
        self.assertEqual(imported["imported"], ["demo"])
        self.assertEqual(self.store.get("demo")["description"], "Imported")

    def test_import_commit_failure_isolated_and_previous_destination_survives(self):
        self.store.create("demo", "Original", body="old")
        source = Store(data_dir=Path(self.tmp.name) / "source2")
        source.init_db()
        source.create("demo", "Replacement", body="new")
        archive = source.export(Path(self.tmp.name) / "failure.tar.gz")
        with mock.patch.object(self.store, "_upsert_entry", side_effect=StoreError("index unavailable")):
            result = self.store.import_(archive, force=True)
        self.assertEqual(result["imported"], [])
        self.assertTrue(any("index unavailable" in item for item in result["skipped"]))
        self.assertEqual(self.store.get("demo")["description"], "Original")
        self.assertEqual(self.store.get("demo")["body"], "old\n")


if __name__ == "__main__":
    unittest.main()
