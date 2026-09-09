"""Hermetic concurrency contracts for atomic Store and HTTP operations."""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from skillsmgr.atomic_io import atomic_write_text
from skillsmgr.store import Store
from skillsmgr.webapp import WebAppServer


class ConcurrencyContractTests(unittest.TestCase):
    """Exercise public Store and REST seams under deterministic contention."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = Store(data_dir=Path(self._tmp.name) / "manager")
        self.store.init_db()

    def _documents(self):
        """Create two independently known complete versions of one skill."""
        self.store.create("demo", "old description", body="old body")
        skill_file = self.store.skills_dir / "demo" / "SKILL.md"
        old_text = skill_file.read_text(encoding="utf-8")
        self.store.edit("demo", description="new description", body="new body")
        new_text = skill_file.read_text(encoding="utf-8")
        self.store.edit("demo", description="old description", body="old body")
        self.store.resync()
        return skill_file, old_text, new_text

    @staticmethod
    def _join_all(threads, timeout=10):
        for thread in threads:
            thread.join(timeout=timeout)
        return [thread for thread in threads if thread.is_alive()]

    def test_same_skill_edits_and_reads_observe_complete_documents(self):
        skill_file, old_text, new_text = self._documents()
        expected_texts = {old_text, new_text}
        expected_records = {
            ("old description", "old body\n"),
            ("new description", "new body\n"),
        }
        barrier = threading.Barrier(6)
        readers_ready = threading.Event()
        read_counts = [0, 0, 0, 0]
        stop_readers = threading.Event()
        errors = []
        errors_lock = threading.Lock()

        def record_error(exc):
            with errors_lock:
                errors.append(exc)

        def writer(value):
            try:
                barrier.wait(timeout=5)
                readers_ready.wait(timeout=5)
                writer_store = Store(data_dir=self.store.data_dir)
                for _ in range(8):
                    writer_store.edit(
                        "demo",
                        description=value[0],
                        body=value[1],
                    )
            except Exception as exc:  # pragma: no cover - assertion reports it
                record_error(exc)

        def reader(index):
            try:
                barrier.wait(timeout=5)
                readers_ready.set()
                while not stop_readers.is_set():
                    read_counts[index] += 1
                    observed_text = skill_file.read_text(encoding="utf-8")
                    observed = self.store.get("demo")
                    self.assertIn(observed_text, expected_texts)
                    self.assertIn(
                        (observed["description"], observed["body"]),
                        expected_records,
                    )
            except Exception as exc:  # pragma: no cover - assertion reports it
                record_error(exc)

        threads = [
            threading.Thread(
                target=writer,
                args=(("old description", "old body"),),
                name="store-old-writer",
            ),
            threading.Thread(
                target=writer,
                args=(("new description", "new body"),),
                name="store-new-writer",
            ),
            *(threading.Thread(target=reader, args=(i,), name=f"store-reader-{i}") for i in range(4)),
        ]
        for thread in threads:
            thread.start()
        writers = threads[:2]
        readers = threads[2:]
        try:
            stuck_writers = self._join_all(writers)
            stop_readers.set()
            stuck_readers = self._join_all(readers)
        finally:
            stop_readers.set()
            self._join_all(threads)

        self.assertEqual(errors, [])
        self.assertEqual(stuck_writers, [])
        self.assertEqual(stuck_readers, [])
        self.assertTrue(all(count > 0 for count in read_counts), read_counts)
        self.assertIn(skill_file.read_text(encoding="utf-8"), expected_texts)
        self.assertTrue(self.store.doctor()["ok"])

    def test_concurrent_http_requests_observe_complete_documents_and_cleanup(self):
        skill_file, old_text, new_text = self._documents()
        expected_texts = {old_text, new_text}
        expected_records = {
            ("old description", "old body\n"),
            ("new description", "new body\n"),
        }
        read_counts = [0, 0, 0, 0]
        server = WebAppServer(self.store, port=0)
        server_thread = threading.Thread(
            target=server.serve_forever,
            name="concurrency-contract-http-server",
            daemon=True,
        )
        server_thread.start()
        barrier = threading.Barrier(6)
        readers_ready = threading.Event()
        stop_readers = threading.Event()
        errors = []
        errors_lock = threading.Lock()

        def record_error(exc):
            with errors_lock:
                errors.append(exc)

        def request(method, path, payload=None):
            data = None
            headers = {}
            if payload is not None:
                data = json.dumps(payload).encode("utf-8")
                headers["Content-Type"] = "application/json"
            req = urllib.request.Request(
                f"{server.url}{path}",
                data=data,
                headers=headers,
                method=method,
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read()

        def writer(value):
            try:
                barrier.wait(timeout=5)
                readers_ready.wait(timeout=5)
                for _ in range(8):
                    status, _ = request(
                        "PATCH",
                        "/api/skills/demo",
                        {"description": value[0], "body": value[1]},
                    )
                    self.assertEqual(status, 200)
            except Exception as exc:  # pragma: no cover - assertion reports it
                record_error(exc)

        def reader(index):
            try:
                barrier.wait(timeout=5)
                readers_ready.set()
                while not stop_readers.is_set():
                    read_counts[index] += 1
                    status, raw = request("GET", "/api/skills/demo/raw")
                    self.assertEqual(status, 200)
                    self.assertIn(raw.decode("utf-8"), expected_texts)
                    status, body = request("GET", "/api/skills/demo")
                    self.assertEqual(status, 200)
                    record = json.loads(body)
                    self.assertIn(
                        (record["description"], record["body"]),
                        expected_records,
                    )
            except Exception as exc:  # pragma: no cover - assertion reports it
                record_error(exc)

        threads = [
            threading.Thread(
                target=writer,
                args=(value,),
                name=f"http-{value[0].split()[0]}-writer",
            )
            for value in (
                ("old description", "old body"),
                ("new description", "new body"),
            )
        ]
        threads.extend(
            threading.Thread(target=reader, args=(i,), name=f"http-reader-{i}")
            for i in range(4)
        )
        for thread in threads:
            thread.start()
        writers = threads[:2]
        readers = threads[2:]
        try:
            stuck_writers = self._join_all(writers)
            stop_readers.set()
            stuck_readers = self._join_all(readers)
            self.assertEqual(errors, [])
            self.assertEqual(stuck_writers, [])
            self.assertEqual(stuck_readers, [])
            self.assertTrue(all(count > 0 for count in read_counts), read_counts)
            self.assertIn(skill_file.read_text(encoding="utf-8"), expected_texts)
        finally:
            stop_readers.set()
            self._join_all(threads)
            server.shutdown()
            server_thread.join(timeout=5)

        self.assertFalse(server_thread.is_alive())
        with self.assertRaises(urllib.error.URLError):
            urllib.request.urlopen(f"{server.url}api/skills/demo", timeout=1)

    def test_doctor_and_resync_repair_a_complete_document_drift(self):
        skill_file, old_text, new_text = self._documents()
        self.assertTrue(self.store.doctor()["ok"])
        current = skill_file.read_text(encoding="utf-8")
        replacement = new_text if current == old_text else old_text
        atomic_write_text(skill_file, replacement)

        report = self.store.doctor()
        self.assertFalse(report["ok"])
        self.assertEqual(report["filesystem_index_drift"], ["demo"])

        result = self.store.resync()
        self.assertEqual(result["updated"], 1)
        self.assertTrue(self.store.doctor()["ok"])
        self.assertEqual(skill_file.read_text(encoding="utf-8"), replacement)

    def test_remove_and_edit_race_leaves_no_residue_or_raw_errors(self):
        # OPEN-5 regression: whole-dir moves (remove) must serialize with
        # file writes (edit/disable) on the same per-skill lock. Without the
        # lock, a mid-write temp file can be stranded inside a trash copy and
        # raw FileNotFoundError can escape the Store API.
        from skillsmgr.store import SkillNotFound, StoreError

        self.store.create("raced", "seed", body="seed")
        stop = threading.Event()
        errors = []

        def churn(seed):
            for _ in range(400):
                try:
                    self.store.edit("raced", description=f"d{seed}", body="x" * 30000)
                except (StoreError, SkillNotFound):
                    pass
                except Exception as exc:  # pragma: no cover - raw leak
                    errors.append(f"edit {type(exc).__name__}: {exc}")
                    return
                if not stop.is_set():
                    try:
                        self.store.disable("raced")
                        self.store.enable("raced")
                    except (StoreError, SkillNotFound):
                        pass
                    except Exception as exc:  # pragma: no cover - raw leak
                        errors.append(f"toggle {type(exc).__name__}: {exc}")
                        return

        def remover():
            for _ in range(120):
                try:
                    self.store.remove("raced")
                    self.store.create("raced", "seed", body="seed")
                except (StoreError, SkillNotFound):
                    pass
                except Exception as exc:  # pragma: no cover - raw leak
                    errors.append(f"remove {type(exc).__name__}: {exc}")
                    return

        threads = [threading.Thread(target=churn, args=(i,)) for i in range(3)]
        threads.append(threading.Thread(target=remover))
        for t in threads:
            t.start()
        stop.set()
        alive = self._join_all(threads)
        self.assertEqual(alive, [])
        self.assertEqual(errors, [])
        self.store.resync()
        doctor = self.store.doctor()
        self.assertTrue(doctor["ok"], doctor)
        leftovers = [
            p.name
            for p in Path(self._tmp.name).rglob("*")
            if ".skillsmgr-tmp" in p.name
        ]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
