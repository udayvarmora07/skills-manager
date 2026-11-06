"""Regression tests for scoped mutation serialization."""
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import scopes


class ScopeMutationTests(unittest.TestCase):
    def test_retained_backup_does_not_abort_other_sync_targets(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            store = scopes.Store()
            store.init_db()
            token = scopes._GLOBAL_STORE.set(store)
            try:
                scopes.create_skill("agents", "demo", "source")
                target = Path(scopes.create_skill("codex", "demo", "target")["path"])
                backup = target.parent / ".demo.skillsmgr-backup"
                backup.mkdir()
                (backup / "recover.txt").write_text("recover me")
                result = scopes.sync_skill("demo", "agents", ["codex", "claude-code"], force=True)
                self.assertEqual(result["synced"], ["claude-code"])
                self.assertEqual(result["skipped"][0]["scope"], "codex")
                self.assertEqual((backup / "recover.txt").read_text(), "recover me")
            finally:
                scopes._GLOBAL_STORE.reset(token)

    def test_edit_and_disable_are_serialized(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            scopes.create_skill("agents", "demo", "original")
            directory = Path(tmp) / ".agents/skills/demo"
            entered = threading.Event()
            release = threading.Event()
            done = threading.Event()
            errors = []
            real_parse = scopes.parse_frontmatter

            def pause(text):
                entered.set()
                if not release.wait(5):
                    raise AssertionError("edit not released")
                return real_parse(text)

            def edit():
                try:
                    scopes.edit_skill("agents", "demo", description="edited")
                except Exception as exc:
                    errors.append(exc)

            def disable():
                try:
                    scopes.toggle_skill("agents", "demo", enable=False)
                except Exception as exc:
                    errors.append(exc)
                finally:
                    done.set()

            with mock.patch.object(scopes, "parse_frontmatter", side_effect=pause):
                first = threading.Thread(target=edit)
                second = None
                first.start()
                try:
                    self.assertTrue(entered.wait(5))
                    second = threading.Thread(target=disable)
                    second.start()
                    finished_early = done.wait(.3)
                finally:
                    release.set()
                    first.join(5)
                    if second is not None:
                        second.join(5)
            self.assertFalse(finished_early, "toggle entered while edit was reading")
            self.assertFalse(errors, errors)
            self.assertFalse((directory / "SKILL.md").exists())
            self.assertIn("edited", (directory / "SKILL.md.disabled").read_text())

    def test_alias_toggle_waits_for_other_process_lock(self):
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            created = scopes.create_skill("agents", "demo", "original")
            directory = Path(created["path"])
            (directory.parent / "alias").symlink_to(directory, target_is_directory=True)
            code = 'from skillsmgr import scopes; print("ready", flush=True); scopes.toggle_skill("agents", "alias", enable=False)'
            process = None
            try:
                with scopes._mutation_lock(directory / "SKILL.md"):
                    process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    self.assertEqual(process.stdout.readline().strip(), "ready")
                    with self.assertRaises(subprocess.TimeoutExpired):
                        process.wait(timeout=.3)
                out, err = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, err)
            finally:
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.communicate()
            self.assertTrue((directory / "SKILL.md.disabled").exists())
            self.assertFalse((directory / "SKILL.md").exists())
            with self.assertRaisesRegex(scopes.StoreError, "already disabled"):
                scopes.toggle_skill("agents", "demo", enable=False)

    def test_mutations_refuse_symlinked_document_without_touching_target(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            directory = Path(scopes.create_skill("agents", "demo", "original")["path"])
            document = directory / "SKILL.md"
            target = directory / "original.md"
            document.rename(target)
            document.symlink_to(target.name)
            original = target.read_bytes()
            for operation in (lambda: scopes.edit_skill("agents", "demo", description="edited"),
                              lambda: scopes.toggle_skill("agents", "demo", enable=False)):
                with self.assertRaisesRegex(scopes.StoreError, "symlinked skill document"):
                    operation()
                self.assertTrue(document.is_symlink())
                self.assertEqual(target.read_bytes(), original)

    def test_repeated_mixed_mutations_leave_one_valid_document(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            directory = Path(scopes.create_skill("agents", "demo", "original")["path"])
            for _ in range(3):
                barrier = threading.Barrier(6)
                errors = []

                def worker(index):
                    scopes.set_global_store(store)
                    try:
                        barrier.wait(timeout=5)
                        for turn in range(10):
                            try:
                                if index % 3 == 0:
                                    scopes.edit_skill("agents", "demo", description=f"edit {index} {turn}")
                                else:
                                    scopes.toggle_skill("agents", "demo", enable=index % 3 == 1)
                            except scopes.StoreError as exc:
                                if not any(text in str(exc) for text in ("already enabled", "already disabled", "enable it first")):
                                    errors.append(exc)
                    except Exception as exc:
                        errors.append(exc)
                    finally:
                        scopes.set_global_store(None)

                threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(15)
                self.assertFalse(any(thread.is_alive() for thread in threads))
                self.assertFalse(errors, errors)
                documents = [directory / name for name in ("SKILL.md", "SKILL.md.disabled") if (directory / name).exists()]
                self.assertEqual(len(documents), 1)
                data, _ = scopes.parse_frontmatter(documents[0].read_text(encoding="utf-8"))
                self.assertEqual(data["name"], "demo")

    def test_restore_and_disable_are_serialized(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            directory = Path(scopes.create_skill("agents", "demo", "original")["path"])
            snapshot = scopes._global_store().data_dir
            from skillsmgr.store import write_snapshot
            snapshot = write_snapshot(snapshot, "agents", "demo", (directory / "SKILL.md").read_text())
            entered, release, done = threading.Event(), threading.Event(), threading.Event()
            errors = []
            real_read = scopes.read_skill_text_strict

            def paused_read(*args, **kwargs):
                entered.set()
                if not release.wait(5):
                    raise AssertionError("restore not released")
                return real_read(*args, **kwargs)

            def run(action, finished=None):
                scopes.set_global_store(store)
                try:
                    action()
                except Exception as exc:
                    errors.append(exc)
                finally:
                    scopes.set_global_store(None)
                    if finished:
                        finished.set()

            with mock.patch.object(scopes, "read_skill_text_strict", side_effect=paused_read):
                first = threading.Thread(target=run, args=(lambda: scopes.restore_snapshot("agents", "demo", snapshot),))
                second = None
                first.start()
                try:
                    self.assertTrue(entered.wait(5))
                    second = threading.Thread(target=run, args=(lambda: scopes.toggle_skill("agents", "demo", enable=False), done))
                    second.start()
                    finished_early = done.wait(.3)
                finally:
                    release.set()
                    first.join(5)
                    if second:
                        second.join(5)
            self.assertFalse(finished_early)
            self.assertFalse(errors, errors)
            self.assertFalse((directory / "SKILL.md").exists())
            self.assertTrue((directory / "SKILL.md.disabled").is_file())

    def test_force_sync_preserves_undecodable_target_bytes_in_history(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            scopes.create_skill("agents", "demo", "source")
            target = Path(scopes.create_skill("codex", "demo", "target")["path"])
            broken = b"---\nname: demo\ndescription: \xff\n---\n"
            (target / "SKILL.md").write_bytes(broken)
            result = scopes.sync_skill("demo", "agents", ["codex"], force=True)
            self.assertEqual(result["synced"], ["codex"])
            snapshots = scopes.list_snapshots_for("codex", "demo")
            self.assertEqual(len(snapshots), 1)
            path = store.data_dir / "snapshots" / "codex" / "demo" / (snapshots[0] + ".md")
            self.assertEqual(path.read_bytes(), broken)
            self.assertEqual(scopes.get_skill("codex", "demo")["description"], "source")

    def test_raw_read_is_lossy_and_detail_does_not_log_raw_bytes(self):
        from io import StringIO
        from contextlib import redirect_stderr
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            target = Path(scopes.create_skill("agents", "demo", "target")["path"])
            (target / "SKILL.md").write_bytes(b"---\nname: demo\ndescription: secret\xff\n---\n")
            self.assertIn("\ufffd", scopes.get_raw("agents", "demo"))
            stderr = StringIO()
            with redirect_stderr(stderr):
                record = scopes.get_skill("agents", "demo")
            self.assertTrue(record["malformed"])
            self.assertNotIn("secret", stderr.getvalue())

    def test_force_sync_preserves_disabled_global_target_bytes(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            scopes.create_skill("agents", "demo", "source")
            scopes.create_skill("global", "demo", "target")
            scopes.toggle_skill("global", "demo", enable=False)
            target = store.skills_dir / "demo"
            broken = b"invalid \xff byte"
            (target / "SKILL.md.disabled").write_bytes(broken)
            result = scopes.sync_skill("demo", "agents", ["global"], force=True)
            self.assertEqual(result["synced"], ["global"])
            snapshots = scopes.list_snapshots_for("global", "demo")
            self.assertEqual((store.data_dir / "snapshots" / "global" / "demo" / (snapshots[0] + ".md")).read_bytes(), broken)
            self.assertEqual(store.get("demo")["description"], "source")

    def test_snapshot_failure_does_not_replace_destination(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            scopes.create_skill("agents", "demo", "source")
            target = Path(scopes.create_skill("codex", "demo", "target")["path"])
            original = (target / "SKILL.md").read_bytes()
            with mock.patch("skillsmgr.store._write_snapshot_bytes", side_effect=OSError("private bytes")):
                with self.assertRaisesRegex(scopes.StoreError, "could not snapshot") as error:
                    scopes.sync_skill("demo", "agents", ["codex"], force=True)
            self.assertNotIn("private bytes", str(error.exception))
            self.assertEqual((target / "SKILL.md").read_bytes(), original)

    def test_sync_and_toggle_share_destination_lock(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            scopes.create_skill("agents", "demo", "source")
            target = Path(scopes.create_skill("codex", "demo", "target")["path"])
            entered, release, done = threading.Event(), threading.Event(), threading.Event()
            errors = []
            from skillsmgr import store as store_module
            real_snapshot = store_module._write_snapshot_bytes

            def paused_snapshot(*args):
                entered.set()
                if not release.wait(5):
                    raise AssertionError("sync not released")
                return real_snapshot(*args)

            def run(action, finished=None):
                scopes.set_global_store(store)
                try:
                    action()
                except Exception as exc:
                    errors.append(exc)
                finally:
                    scopes.set_global_store(None)
                    if finished:
                        finished.set()

            with mock.patch.object(store_module, "_write_snapshot_bytes", side_effect=paused_snapshot):
                first = threading.Thread(target=run, args=(lambda: scopes.sync_skill("demo", "agents", ["codex"], force=True),))
                second = None
                first.start()
                try:
                    self.assertTrue(entered.wait(5))
                    second = threading.Thread(target=run, args=(lambda: scopes.toggle_skill("codex", "demo", enable=False), done))
                    second.start()
                    finished_early = done.wait(.3)
                finally:
                    release.set()
                    first.join(5)
                    if second:
                        second.join(5)
            self.assertFalse(finished_early)
            self.assertFalse(errors, errors)
            self.assertFalse((target / "SKILL.md").exists())
            self.assertTrue((target / "SKILL.md.disabled").is_file())

    def test_sync_backup_cleanup_failure_keeps_installed_destination(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            scopes.create_skill("agents", "demo", "new source")
            target = Path(scopes.create_skill("codex", "demo", "old target")["path"])
            (target / "extra").write_text("old auxiliary")
            real_rmtree = shutil.rmtree

            def fail_cleanup(path, *args, **kwargs):
                path = Path(path)
                if path.name == ".demo.skillsmgr-backup" and path.exists():
                    (path / "extra").unlink()
                    raise OSError("cleanup failed")
                return real_rmtree(path, *args, **kwargs)

            with mock.patch("skillsmgr.scopes.shutil.rmtree", side_effect=fail_cleanup):
                result = scopes.sync_skill("demo", "agents", ["codex"], force=True)
            self.assertEqual(result["synced"], ["codex"])
            self.assertEqual(scopes.get_skill("codex", "demo")["description"], "new source")
            backup = target.parent / ".demo.skillsmgr-backup"
            self.assertTrue(backup.exists())
            with self.assertRaisesRegex(scopes.StoreError, "manual review"):
                scopes.sync_skill("demo", "agents", ["codex"], force=True)
            self.assertTrue(backup.exists())
            self.assertEqual(scopes.get_skill("codex", "demo")["description"], "new source")

    def test_sync_failed_install_restores_old_destination(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp, "SKILLS_MANAGER_DATA": str(Path(tmp) / "data")}):
            (Path(tmp) / "data").mkdir(mode=0o700)
            store = scopes.Store()
            store.init_db()
            scopes.set_global_store(store)
            self.addCleanup(scopes.set_global_store, None)
            scopes.create_skill("agents", "demo", "new source")
            target = Path(scopes.create_skill("codex", "demo", "old target")["path"])
            (target / "extra").write_text("old auxiliary")
            real_move = shutil.move

            def fail_stage(src, dst, *args, **kwargs):
                if Path(src).name == ".demo.skillsmgr-stage":
                    raise OSError("install failed")
                return real_move(src, dst, *args, **kwargs)

            with mock.patch("skillsmgr.scopes.shutil.move", side_effect=fail_stage):
                with self.assertRaises(scopes.StoreError):
                    scopes.sync_skill("demo", "agents", ["codex"], force=True)
            self.assertEqual(scopes.get_skill("codex", "demo")["description"], "old target")
            self.assertEqual((target / "extra").read_text(), "old auxiliary")
