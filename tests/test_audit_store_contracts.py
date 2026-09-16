"""Red-first regression tests for the deep-audit Store findings (batch 3).

Each test drives the real ``Store`` seam that produced the finding in
``DEEP-AUDIT-2026-09-11.md`` -- a temporary data root, a real trash directory,
real filesystem permissions -- and asserts the user-visible symptom, not merely
"did not raise".  Stdlib unittest only.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sqlite3
import tarfile
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr.atomic_io import tree_content_hash
from skillsmgr.store import SkillNotFound, Store, StoreError
from skillsmgr import store as store_mod


class AuditStoreTestCase(unittest.TestCase):
    """Base: fresh data root per test, no environment leakage."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = Store(data_dir=Path(self._tmp.name) / "data")
        self.store.init_db()
        self.data_dir = Path(self.store.data_dir)

    def make_skill(self, name="demo", extra_dirs=(), links=()):
        self.store.create(name, f"{name} skill")
        skill_dir = self.data_dir / "skills" / name
        for relative in extra_dirs:
            (skill_dir / relative).mkdir(parents=True, exist_ok=True)
        for relative, target in links:
            (skill_dir / relative).parent.mkdir(parents=True, exist_ok=True)
            os.symlink(target, skill_dir / relative)
        return skill_dir

    def make_undeletable(self, path: Path) -> None:
        """Make a directory tree undeletable, and clean up wherever it ends up.

        A failed purge *displaces* the skill tree (STORE-7), so the directory
        this was called on may no longer exist by cleanup time -- the original
        path would then raise ``FileNotFoundError`` from the teardown instead of
        the test asserting anything.  Restore write permission on the original
        path and on any staging sibling the purge parked it under.
        """
        path.chmod(0o500)
        skill_dir = path.parent
        self.addCleanup(self._restore_write, skill_dir)

    @staticmethod
    def _restore_write(skill_dir: Path) -> None:
        candidates = [skill_dir, *skill_dir.parent.glob(f"{skill_dir.name}*")]
        for parent in candidates:
            if not parent.is_dir():
                continue
            for target in [parent, *(p for p in parent.rglob("*") if p.is_dir())]:
                with contextlib.suppress(OSError):
                    target.chmod(0o700)


class PurgeTransactionContractTests(AuditStoreTestCase):
    def test_purge_trash_does_not_hold_a_write_transaction_across_rmtree(self):
        # STORE-6: the delete transaction stayed open for the whole purge, so a
        # concurrent writer waited out sqlite3's busy timeout and then failed
        # with a RAW sqlite3.OperationalError.  With the filesystem deletions
        # done first, the writer never sees that window.
        for name in ("t1", "t2"):
            self.store.create(name, f"{name} skill")
            self.store.remove(name)
        real_rmtree = shutil.rmtree
        outcome: dict[str, object] = {}

        def slow_rmtree(path, *args, **kwargs):
            time.sleep(0.6)
            return real_rmtree(path, *args, **kwargs)

        def concurrent_create():
            try:
                outcome["value"] = self.store.create("during", "concurrent")
            except Exception as exc:  # pragma: no cover - the defect path
                outcome["value"] = exc

        with mock.patch.object(store_mod.shutil, "rmtree", side_effect=slow_rmtree):
            worker = threading.Thread(target=concurrent_create)
            worker.start()
            purged = self.store.purge_trash()
            worker.join(timeout=30)

        self.assertEqual(sorted(purged["purged"]), ["t1", "t2"])
        self.assertNotIsInstance(outcome.get("value"), sqlite3.Error)
        self.assertNotIsInstance(outcome.get("value"), Exception)
        self.assertEqual(
            self.store.get("during")["description"], "concurrent"
        )

    def test_failed_purge_keeps_every_index_row(self):
        # STORE-6/STORE-7: rows were deleted one entry at a time while the
        # rmtree loop ran, so a failure part-way left skills listed that had no
        # copy anywhere on disk.
        self.store.create("demo", "demo skill")
        self.store.remove("demo")
        with mock.patch.object(
            store_mod.shutil, "rmtree", side_effect=OSError("permission denied")
        ):
            with self.assertRaises(StoreError):
                self.store.purge_trash()
        self.assertEqual(self.store.get("demo")["status"], "trashed")
        self.assertEqual(len(self.store.trash_list()), 1)


class RemovePurgeAtomicityTests(AuditStoreTestCase):
    def test_remove_purge_never_advertises_a_destroyed_skill(self):
        # STORE-7: SKILL.md was unlinked before the failing rmtree, a raw
        # PermissionError escaped, and the row stayed 'active' -- so list()
        # advertised a skill whose document was already gone.
        skill_dir = self.make_skill(extra_dirs=["scripts"])
        (skill_dir / "scripts" / "run.sh").write_text("x", encoding="utf-8")
        self.make_undeletable(skill_dir / "scripts")

        with self.assertRaises(StoreError) as ctx:
            self.store.remove("demo", purge=True)

        self.assertIn("could not purge skill 'demo'", str(ctx.exception))
        self.assertNotIsInstance(ctx.exception, OSError)
        self.assertEqual(
            [r["name"] for r in self.store.list()], [], "a husk was advertised"
        )
        with self.assertRaises(SkillNotFound):
            self.store.get("demo")
        report = self.store.doctor()
        self.assertFalse(report["ok"])
        self.assertEqual(
            report["transaction_artifacts"], ["skills/demo.skillsmgr-stage"]
        )

    def test_remove_purge_keeps_the_tree_when_nothing_was_deleted(self):
        # The other honest outcome: if the delete fails before touching the
        # document, the skill is still fully installed.
        skill_dir = self.make_skill()
        with mock.patch.object(
            store_mod.shutil, "rmtree", side_effect=OSError("nfs said no")
        ):
            with self.assertRaises(StoreError) as ctx:
                self.store.remove("demo", purge=True)
        self.assertNotIsInstance(ctx.exception, OSError)
        self.assertTrue((skill_dir / "SKILL.md").is_file())
        self.assertEqual(self.store.get("demo")["status"], "active")
        self.assertEqual([r["name"] for r in self.store.list()], ["demo"])

    def test_remove_purge_removes_the_tree_and_the_row(self):
        self.make_skill(extra_dirs=["scripts"])
        result = self.store.remove("demo", purge=True)
        self.assertEqual(result["action"], "purged")
        self.assertFalse((self.data_dir / "skills" / "demo").exists())
        with self.assertRaises(SkillNotFound):
            self.store.get("demo")
        self.assertEqual(self.store.list(), [])


class ExportAtomicityTests(AuditStoreTestCase):
    def test_two_exports_in_one_second_do_not_share_a_path(self):
        # STORE-8: export() and backup() shared a one-second filename, so the
        # second archive silently replaced the first.
        self.make_skill()
        first = self.store.export()
        second = self.store.backup()
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file())
        self.assertTrue(second.is_file())
        self.assertEqual(
            len(list((self.data_dir / "backups").glob("export-*.tar.gz"))), 2
        )

    def test_failed_export_leaves_the_existing_archive_untouched(self):
        self.make_skill()
        target = self.store.export()
        before = target.read_bytes()
        real_open = tarfile.open

        def exploding_open(name, *args, **kwargs):
            if args and args[0] == "w:gz":
                raise OSError("simulated I/O error")
            return real_open(name, *args, **kwargs)

        with mock.patch.object(store_mod.tarfile, "open", side_effect=exploding_open):
            with self.assertRaises(OSError):
                self.store.export(dest=target)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(
            [p.name for p in target.parent.iterdir() if p.name.startswith(".")], []
        )

    def test_failed_export_leaves_no_temporary_file(self):
        self.make_skill()
        with mock.patch.object(
            store_mod.tarfile, "open", side_effect=OSError("boom")
        ):
            with self.assertRaises(OSError):
                self.store.export()
        leftovers = [
            p.name
            for p in (self.data_dir / "backups").iterdir()
            if p.name.endswith(".skillsmgr-export")
        ]
        self.assertEqual(leftovers, [])


class ExportSymlinkTests(AuditStoreTestCase):
    def test_export_does_not_store_symlink_members(self):
        # STORE-9: tar.add stores a symlink as SYMTYPE and validate_members
        # rejects those, so one symlink made the whole archive -- every skill
        # in it -- unimportable.
        skill_dir = self.make_skill(links=[("scripts/link.sh", "real.sh")])
        (skill_dir / "scripts" / "real.sh").write_text("echo hi\n", encoding="utf-8")
        archive = self.store.export()
        with tarfile.open(archive) as tar:
            types = {member.name: member.type for member in tar.getmembers()}
        self.assertNotIn(b"2", types.values())
        self.assertIn("skills/demo/scripts/real.sh", types)

    def test_symlinked_skill_archives_round_trip(self):
        skill_dir = self.make_skill(links=[("scripts/link.sh", "real.sh")])
        (skill_dir / "scripts" / "real.sh").write_text("echo hi\n", encoding="utf-8")
        (skill_dir / "linked.md").symlink_to(skill_dir / "SKILL.md")
        archive = self.store.export()

        other = Store(data_dir=Path(self._tmp.name) / "restored")
        other.init_db()
        report = other.import_(archive)

        self.assertEqual(report["imported"], ["demo"])
        restored = Path(other.data_dir) / "skills" / "demo"
        self.assertTrue((restored / "scripts" / "real.sh").is_file())
        self.assertTrue((restored / "SKILL.md").is_file())

    def test_content_hash_ignores_symlinks_and_escaping_links(self):
        # STORE-9: the manifest hash followed the link, so it covered bytes the
        # archive does not contain and read data outside the managed root.
        skill_dir = self.make_skill(links=[("scripts/link.sh", "real.sh")])
        (skill_dir / "scripts" / "real.sh").write_text("echo hi\n", encoding="utf-8")
        outside = Path(self._tmp.name) / "outside.txt"
        outside.write_text("SECRET\n", encoding="utf-8")
        (skill_dir / "escape.md").symlink_to(outside)

        digest = tree_content_hash(skill_dir)
        (skill_dir / "escape.md").unlink()
        self.assertEqual(
            tree_content_hash(skill_dir), digest,
            "the digest changed when the escaping symlink was removed, so it "
            "hashed bytes outside the managed root",
        )

    def test_archive_manifest_hash_matches_the_archived_tree(self):
        skill_dir = self.make_skill(links=[("alias.md", "SKILL.md")])
        (skill_dir / "alias.md").unlink()
        archive = self.store.export()
        with tarfile.open(archive) as tar:
            import json

            manifest = json.load(tar.extractfile("manifest.json"))
        entry = next(e for e in manifest["skills"] if e["name"] == "demo")
        self.assertEqual(entry["content_hash"], tree_content_hash(skill_dir))


class FilesystemTruthTests(AuditStoreTestCase):
    def test_list_get_and_search_hide_a_row_whose_directory_is_gone(self):
        # STORE-10: a crash between the filesystem move and the index commit
        # left an 'active' row that list()/get()/search() served over the
        # missing directory, contradicting the documented invariant.
        self.make_skill()
        shutil.move(
            str(self.data_dir / "skills" / "demo"),
            str(Path(self._tmp.name) / "parked"),
        )

        self.assertEqual(self.store.list(), [])
        self.assertEqual(self.store.search("demo"), [])
        self.assertEqual(self.store.search(""), [])
        record = self.store.get("demo")
        self.assertFalse(record["installed"])
        self.assertIsNone(record["path"])

    def test_get_still_serves_a_trashed_skill(self):
        # The trash legitimately moves the directory away: get() stays callable
        # and reports the skill as not installed instead of raising.
        self.make_skill()
        self.store.remove("demo")
        record = self.store.get("demo")
        self.assertEqual(record["status"], "trashed")
        self.assertFalse(record["installed"])

    def test_stats_counts_only_skills_that_exist_on_disk(self):
        self.make_skill("alpha")
        self.make_skill("beta")
        shutil.move(
            str(self.data_dir / "skills" / "beta"),
            str(Path(self._tmp.name) / "parked"),
        )
        stats = self.store.stats()
        self.assertEqual(stats["active"], 1)
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["categories"], {"uncategorized": 1})

    def test_doctor_still_reports_the_ghost_row_as_drift(self):
        self.make_skill()
        shutil.move(
            str(self.data_dir / "skills" / "demo"),
            str(Path(self._tmp.name) / "parked"),
        )
        report = self.store.doctor()
        self.assertEqual(report["stale_rows"], ["demo"])
        self.assertFalse(report["ok"])


class HuskVisibilityTests(AuditStoreTestCase):
    def test_doctor_reports_a_directory_with_no_document(self):
        # STORE-13: scan_dir skipped any directory whose load_skill raised, so
        # the husk from an interrupted remove/purge was invisible to both
        # doctor() and resync().
        self.make_skill("demo")
        husk = self.data_dir / "skills" / "husk"
        (husk / "scripts").mkdir(parents=True)
        (husk / "scripts" / "run.sh").write_text("x", encoding="utf-8")

        report = self.store.doctor()

        self.assertEqual(report["orphan_dirs"], ["husk"])
        self.assertFalse(report["ok"])
        self.assertEqual(report["skills_on_disk"], 2)

    def test_resync_never_indexes_a_document_less_directory(self):
        self.make_skill("demo")
        (self.data_dir / "skills" / "husk").mkdir()
        self.store.resync()
        self.assertEqual([r["name"] for r in self.store.list()], ["demo"])
        self.assertEqual(self.store.doctor()["orphan_dirs"], ["husk"])

    def test_store_scan_still_ignores_its_own_staging_markers(self):
        self.make_skill("demo")
        (self.data_dir / "skills" / "demo.skillsmgr-stage").mkdir()
        report = self.store.doctor()
        self.assertEqual(report["orphan_dirs"], [])
        self.assertEqual(
            report["transaction_artifacts"], ["skills/demo.skillsmgr-stage"]
        )


class IndexMutationLockTests(AuditStoreTestCase):
    def test_resync_holds_the_shared_index_lock(self):
        # STORE-12: a skill created between the scan and the delete pass was
        # reported as removed while its directory was on disk.
        #
        # The lock under test is the one the implementation actually shares
        # between whole-tree scans and mutations, resolved through the module's
        # own helper -- locking a hand-written path here would silently stop
        # testing anything the moment that key changes.
        self.store.create("existing", "existing skill")
        from skillsmgr.atomic_io import mutation_lock

        lock = mutation_lock(store_mod._index_lock_path(self.store.skills_dir))
        lock.acquire()
        done = threading.Event()

        def resync():
            self.store.resync()
            done.set()

        worker = threading.Thread(target=resync)
        worker.start()
        try:
            self.assertFalse(done.wait(0.4), "resync ignored the shared index lock")
        finally:
            lock.release()
        worker.join(timeout=30)
        self.assertTrue(done.is_set())

    def test_resync_and_create_share_a_lock(self):
        # The property the key exists for: a whole-tree scan and a mutation must
        # not be able to interleave, whatever key they use.
        real_lock = store_mod._mutation_lock
        seen: list[int] = []

        def spy(path):
            lock = real_lock(path)
            seen.append(id(lock))
            return lock

        with mock.patch.object(store_mod, "_mutation_lock", spy):
            seen.clear()
            self.store.create("alpha", "alpha skill")
            create_locks = set(seen)

        with mock.patch.object(store_mod, "_mutation_lock", spy):
            seen.clear()
            self.store.resync()
            resync_locks = set(seen)

        self.assertTrue(create_locks, "create() took no lock at all")
        self.assertTrue(resync_locks, "resync() took no lock at all")
        self.assertTrue(
            create_locks & resync_locks,
            "resync() and create() share no lock, so a scan can drop a new row",
        )

    def test_db_rebuild_removes_the_journal_siblings(self):
        self.store.create("demo", "demo skill")
        journal = Path(f"{self.store.db_path}-journal")
        journal.write_text("stale", encoding="utf-8")
        report = self.store.db_rebuild()
        self.assertEqual(report["added"], 1)
        self.assertFalse(journal.exists())
        self.assertEqual([r["name"] for r in self.store.list()], ["demo"])


if __name__ == "__main__":
    unittest.main()
