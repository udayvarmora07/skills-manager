"""Unit tests for skills-manager. Stdlib unittest only (no third-party deps).

Hermetic: every test uses an isolated $SKILLS_MANAGER_DATA tmp dir.
Filesystem is the source of truth; the DB is only an index.

Run:  python3 -m unittest discover -s tests -v
"""

import hashlib
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr.frontmatter import FrontmatterError, dump_frontmatter, parse_frontmatter
from skillsmgr.loader import load_skill
from skillsmgr.scopes import known_scopes
from skillsmgr.search import rank_results
from skillsmgr.store import SkillNotFound, Store, StoreError
from skillsmgr.validator import description_score, validate_skill, validate_text


def _skill_body(name="demo", description="Demo skill"):
    return dump_frontmatter(
        {
            "name": name,
            "description": description,
            "license": "",
            "compatibility": "",
            "version": "",
            "allowed_tools": "",
        },
    ) + "# Demo\n\nBody text.\n"


class IsolatedStoreTestCase(unittest.TestCase):
    """Base: fresh $SKILLS_MANAGER_DATA per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        os.environ["SKILLS_MANAGER_DATA"] = self._tmp.name
        self.store = Store()
        self.store.init_db()

    def make_skill_dir(self, name, text=None, disabled=False):
        from pathlib import Path

        d = Path(self._tmp.name) / name
        d.mkdir(exist_ok=True)
        fname = "SKILL.md.disabled" if disabled else "SKILL.md"
        (d / fname).write_text(
            text if text is not None else _skill_body(name), encoding="utf-8"
        )
        return d


class TestCreateGetList(IsolatedStoreTestCase):
    def test_create_and_get(self):
        rec = self.store.create("demo", "Demo skill", body="Hello.")
        self.assertEqual(rec["name"], "demo")
        self.assertEqual(self.store.get("demo")["description"], "Demo skill")
        self.assertEqual(len(self.store.list()), 1)

    def test_create_rejects_bad_name(self):
        with self.assertRaises(StoreError):
            self.store.create("Bad Name!", "x")

    def test_create_rejects_duplicate(self):
        self.store.create("demo", "Demo skill")
        with self.assertRaises(StoreError):
            self.store.create("demo", "Other description")

    def test_get_missing_raises(self):
        with self.assertRaises(SkillNotFound):
            self.store.get("nope")


class TestEditToggle(IsolatedStoreTestCase):
    def test_edit_partial(self):
        self.store.create("demo", "Demo skill")
        out = self.store.edit("demo", description="New desc")
        self.assertTrue(out["changed"])
        self.assertEqual(self.store.get("demo")["description"], "New desc")

    def test_edit_preserves_unknown_client_frontmatter(self):
        source = self.make_skill_dir(
            "custom",
            "---\nname: custom\ndescription: Original\nclient-x:\n  mode: strict\n  flags: [a, b]\n---\nbody\n",
        )
        self.store.add(source)

        self.store.edit("custom", description="Updated")

        text = (self.store.skills_dir / "custom" / "SKILL.md").read_text(encoding="utf-8")
        data, _ = parse_frontmatter(text)
        self.assertEqual(data["description"], "Updated")
        self.assertEqual(data["client-x"], {"mode": "strict", "flags": ["a", "b"]})

    def test_disable_enable_cycle(self):
        self.store.create("demo", "Demo skill")
        self.store.disable("demo")
        rows = self.store.list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["disabled"], 1)
        self.store.enable("demo")
        rows = self.store.list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["disabled"], 0)

    def test_disable_refuses_a_directory_holding_both_documents(self):
        # STORE-3: with both documents present the rename used to land on top
        # of the other one, destroying it silently (no snapshot either).
        self.store.create("demo", "Demo skill", body="Enabled body")
        skill_dir = self.store.skills_dir / "demo"
        (skill_dir / "SKILL.md.disabled").write_text(
            _skill_body(name="demo", description="Disabled copy"), encoding="utf-8"
        )

        with self.assertRaises(StoreError) as ctx:
            self.store.disable("demo")
        self.assertIn("both SKILL.md and SKILL.md.disabled", str(ctx.exception))

        self.assertTrue((skill_dir / "SKILL.md").is_file())
        self.assertTrue((skill_dir / "SKILL.md.disabled").is_file())

        with self.assertRaises(StoreError):
            self.store.enable("demo")
        self.assertTrue((skill_dir / "SKILL.md").is_file())
        self.assertTrue((skill_dir / "SKILL.md.disabled").is_file())

    def test_doctor_reports_a_directory_holding_both_documents(self):
        self.store.create("demo", "Demo skill")
        (self.store.skills_dir / "demo" / "SKILL.md.disabled").write_text(
            _skill_body(name="demo", description="Second copy"), encoding="utf-8"
        )

        report = self.store.doctor()

        self.assertFalse(report["ok"])
        self.assertEqual(report["conflicting_documents"], ["demo"])

    def test_add_refuses_a_source_holding_both_documents(self):
        source = Path(self._tmp.name) / "mixed-source"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            _skill_body(name="mixed", description="Enabled"), encoding="utf-8"
        )
        (source / "SKILL.md.disabled").write_text(
            _skill_body(name="mixed", description="Disabled"), encoding="utf-8"
        )

        with self.assertRaises(StoreError) as ctx:
            self.store.add(source, name="mixed")
        self.assertIn("both SKILL.md and SKILL.md.disabled", str(ctx.exception))
        self.assertFalse((self.store.skills_dir / "mixed").exists())

    def test_edit_preserves_original_when_atomic_replacement_fails(self):
        self.store.create("demo", "Demo skill", body="Original body")
        original = (self.store.skills_dir / "demo" / "SKILL.md").read_text(encoding="utf-8")

        with mock.patch("skillsmgr.store.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(StoreError):
                self.store.edit("demo", description="Changed")

        self.assertEqual(
            (self.store.skills_dir / "demo" / "SKILL.md").read_text(encoding="utf-8"),
            original,
        )
        self.assertEqual(self.store.get("demo")["description"], "Demo skill")

    def test_edit_rolls_back_when_index_update_fails(self):
        self.store.create("demo", "Demo skill", body="Original body")
        original = (self.store.skills_dir / "demo" / "SKILL.md").read_text(encoding="utf-8")

        with mock.patch.object(self.store, "_upsert_entry", side_effect=StoreError("db failed")):
            with self.assertRaises(StoreError):
                self.store.edit("demo", description="Changed")

        self.assertEqual(
            (self.store.skills_dir / "demo" / "SKILL.md").read_text(encoding="utf-8"),
            original,
        )

    def test_concurrent_edits_leave_one_complete_document(self):
        self.store.create("demo", "Demo skill", body="Original body")
        errors = []

        def edit(description):
            try:
                Store(data_dir=self.store.data_dir).edit("demo", description=description)
            except Exception as exc:  # pragma: no cover - assertion below reports the error
                errors.append(exc)

        threads = [
            threading.Thread(target=edit, args=(f"Description {index}",))
            for index in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertEqual(errors, [])
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        loaded = self.store.get("demo")
        self.assertIn(loaded["description"], {f"Description {index}" for index in range(8)})
        self.assertTrue((self.store.skills_dir / "demo" / "SKILL.md").read_text(encoding="utf-8").endswith("\n"))


    def test_add_and_remove_are_mutually_exclusive(self):
        # STORE-2: add() used to copy straight into the live tree with no lock,
        # so a concurrent remove() could carry the half-copied directory to the
        # trash and leave a husk that doctor() still called healthy.
        #
        # The property asserted is *mutual exclusion*, not a particular lock
        # key: add() and remove() must acquire at least one lock in common.
        # The library-wide index lock (STORE-12) also satisfies this, so this
        # test survives a locking redesign instead of pinning an implementation
        # detail that a stronger design is free to change.
        from skillsmgr import store as store_mod

        source = Path(self._tmp.name) / "racing"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(_skill_body("racing"), encoding="utf-8")
        self.store.create("racing", "Placeholder")
        self.store.remove("racing")

        real_lock = store_mod._mutation_lock
        seen: list[int] = []

        def spy(path):
            lock = real_lock(path)
            seen.append(id(lock))
            return lock

        with mock.patch.object(store_mod, "_mutation_lock", spy):
            seen.clear()
            self.store.add(source, name="racing")
            add_locks = set(seen)
        installed = self.store.get("racing")
        self.assertEqual(installed["name"], "racing")

        with mock.patch.object(store_mod, "_mutation_lock", spy):
            seen.clear()
            self.store.remove("racing")
            remove_locks = set(seen)

        self.assertTrue(add_locks, "add() took no lock at all")
        self.assertTrue(remove_locks, "remove() took no lock at all")
        self.assertTrue(
            add_locks & remove_locks,
            "add() and remove() share no lock, so they can interleave",
        )
        self.assertTrue(self.store.doctor()["ok"])

    def test_add_leaves_no_staging_directory_and_fails_cleanly(self):
        source = Path(self._tmp.name) / "incoming"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(_skill_body("staged"), encoding="utf-8")

        with mock.patch("skillsmgr.store.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(StoreError) as ctx:
                self.store.add(source, name="staged")
        self.assertIn("could not install skill 'staged'", str(ctx.exception))
        self.assertFalse((self.store.skills_dir / "staged").exists())
        self.assertEqual(
            sorted(p.name for p in self.store.skills_dir.iterdir()), []
        )
        self.assertTrue(self.store.doctor()["ok"])


class TestTrash(IsolatedStoreTestCase):
    def test_remove_trash_restore_purge(self):
        self.store.create("demo", "Demo skill")
        self.store.remove("demo")
        self.assertEqual(len(self.store.list()), 0)
        self.assertEqual(len(self.store.trash_list()), 1)
        self.store.restore("demo")
        self.assertEqual(len(self.store.list()), 1)
        self.store.remove("demo", purge=True)
        self.assertEqual(len(self.store.trash_list()), 0)

    def test_restore_prefix_collision(self):
        """Restoring 'demo' must not match trashed 'demo-x'."""
        self.store.create("demo", "Demo skill")
        self.store.create("demo-x", "Demo x skill")
        self.store.remove("demo-x")
        self.store.remove("demo")
        self.store.restore("demo")
        self.assertEqual(self.store.get("demo")["description"], "Demo skill")
        self.assertEqual(len(self.store.trash_list()), 1)


    def test_restore_reports_a_lost_trash_copy_as_a_store_error(self):
        # STORE-5: when the trash copy disappears between listing and moving,
        # a raw FileNotFoundError used to escape to callers (REST answered
        # 500 instead of a clean dialog).
        self.store.create("demo", "Demo skill")
        self.store.remove("demo")
        source = next(p for p in self.store.trash_dir.iterdir() if p.is_dir())

        with mock.patch("skillsmgr.store.shutil.move", side_effect=OSError("gone")):
            with self.assertRaises(StoreError) as ctx:
                self.store.restore("demo")
        self.assertIn("cannot restore 'demo'", str(ctx.exception))
        self.assertTrue(source.exists())

    def test_resync_repairs_a_trashed_row_with_no_trash_copy(self):
        # STORE-5: a lost race creates a 'trashed' row with no trash directory
        # that no resync could ever repair, leaving doctor() permanently
        # unhealthy.
        import shutil

        self.store.create("demo", "Demo skill")
        self.store.remove("demo")
        shutil.rmtree(self.store.trash_dir)

        report = self.store.resync()

        self.assertEqual(report["removed"], 1)
        self.assertEqual(self.store.trash_list(), [])
        self.assertTrue(self.store.doctor()["ok"])

    def test_purge_trash_and_restore_share_one_lock(self):
        # STORE-5: both consume the same trash entries, so they must not run
        # concurrently.
        import threading

        from skillsmgr.atomic_io import mutation_lock

        self.store.create("demo", "Demo skill")
        self.store.remove("demo")
        lock = mutation_lock(self.store.trash_dir / ".trash-lock")
        lock.acquire()
        try:
            done = threading.Event()

            def purge():
                self.store.purge_trash()
                done.set()

            worker = threading.Thread(target=purge)
            worker.start()
            self.assertFalse(done.wait(0.4), "purge_trash ignored the trash lock")
        finally:
            lock.release()
        worker.join(timeout=10)
        self.assertTrue(done.is_set())
        self.assertEqual(self.store.trash_list(), [])


class TestSearchStatsHistoryDoctor(IsolatedStoreTestCase):
    def test_search_ranked(self):
        self.store.create("deploy-app", "Deploys the app")
        self.store.create("other", "Unrelated")
        hits = self.store.search("deploy")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["name"], "deploy-app")

    def test_stats_counts(self):
        self.store.create("a", "Skill a")
        self.store.create("b", "Skill b")
        stats = self.store.stats()
        self.assertEqual(stats["total"], 2)

    def test_history_records(self):
        self.store.create("demo", "Demo skill")
        names = [h["name"] for h in self.store.history(limit=10)]
        self.assertIn("demo", names)

    def test_doctor_ok(self):
        self.store.create("demo", "Demo skill")
        self.assertTrue(self.store.doctor()["ok"])

    def test_db_rebuild_roundtrip(self):
        self.store.create("demo", "Demo skill")
        out = self.store.db_rebuild()
        self.assertIn("added", out)
        self.assertEqual(len(self.store.list()), 1)


class TestExportImport(IsolatedStoreTestCase):
    def test_export_import_roundtrip(self):
        from pathlib import Path

        self.store.create("demo", "Demo skill", body="Hello.")
        dest = Path(self._tmp.name) / "exp.tar.gz"
        out = self.store.export(dest=str(dest))
        self.assertTrue(Path(str(out)).is_file())
        self.store.remove("demo", purge=True)
        result = self.store.import_(str(dest))
        self.assertIn("demo", result["imported"])
        self.assertEqual(len(self.store.list()), 1)

    def test_full_export_import_restores_trash_and_templates(self):
        from pathlib import Path

        self.store.create("keep", "Keeper skill")
        self.store.create("goner", "Doomed skill")
        self.store.remove("goner")
        (self.store.templates_dir / "tmpl.md").write_text("# T\n", encoding="utf-8")
        dest = Path(self._tmp.name) / "full.tar.gz"
        self.store.export(dest=str(dest), full=True)
        self.store.remove("keep", purge=True)
        self.store.purge_trash()
        (self.store.templates_dir / "tmpl.md").unlink()
        result = self.store.import_(str(dest), full=True)
        self.assertIn("keep", result["imported"])
        self.assertEqual(len(result["restored_trash"]), 1)
        self.assertEqual(result["restored_templates"], ["tmpl.md"])
        self.assertEqual(len(self.store.trash_list()), 1)
        self.assertTrue((self.store.templates_dir / "tmpl.md").is_file())

    def test_full_import_rejects_slim_archive(self):
        from pathlib import Path

        self.store.create("demo", "Demo skill", body="Hello.")
        dest = Path(self._tmp.name) / "slim.tar.gz"
        self.store.export(dest=str(dest))
        with self.assertRaises(StoreError):
            self.store.import_(str(dest), full=True)

    def test_plain_import_ignores_full_payload(self):
        from pathlib import Path

        self.store.create("keep", "Keeper skill")
        self.store.create("goner", "Doomed skill")
        self.store.remove("goner")
        dest = Path(self._tmp.name) / "full2.tar.gz"
        self.store.export(dest=str(dest), full=True)
        self.store.remove("keep", purge=True)
        self.store.purge_trash()
        result = self.store.import_(str(dest))
        self.assertIn("keep", result["imported"])
        self.assertNotIn("restored_trash", result)
        self.assertEqual(self.store.trash_list(), [])

    def test_create_rolls_back_when_index_update_fails(self):
        with mock.patch.object(self.store, "_upsert_entry", side_effect=StoreError("db failed")):
            with self.assertRaises(StoreError):
                self.store.create("demo", "Demo skill")

        self.assertFalse((self.store.skills_dir / "demo").exists())

    def test_create_rolls_back_on_a_driver_failure_as_a_clean_error(self):
        # BUG-1: a sqlite3 driver failure must surface through the Store error
        # contract, never as a raw sqlite3 exception (cli.py catches StoreError/
        # ValueError/OSError, so a raw driver error became "unexpected error").
        real_connect = self.store._connect

        class _FailingHistory:
            """Real connection that fails only on the history write."""

            def __init__(self, conn):
                self._conn = conn

            def __getattr__(self, item):
                return getattr(self._conn, item)

            def execute(self, sql, *args):
                if "INSERT INTO history" in sql:
                    raise sqlite3.OperationalError("history failed")
                return self._conn.execute(sql, *args)

        with mock.patch.object(
            self.store, "_connect", side_effect=lambda: _FailingHistory(real_connect())
        ):
            with self.assertRaises(StoreError) as ctx:
                self.store.create("demo", "Demo skill")
        self.assertIn("could not record history for 'demo'", str(ctx.exception))

        self.assertFalse((self.store.skills_dir / "demo").exists())
        self.assertEqual(self.store.list(), [])

    def test_create_works_on_a_fresh_data_dir_without_init_db(self):
        # BUG-1: create() was the only public entry point that never called
        # _init_db(), so the first mutation on a fresh data dir raised a raw
        # sqlite3.OperationalError('no such table: skills') and left a skill
        # directory behind.
        fresh = Store(data_dir=Path(self._tmp.name) / "fresh")

        created = fresh.create("alpha", "A skill made on a fresh store")

        self.assertEqual(created["name"], "alpha")
        self.assertTrue((fresh.skills_dir / "alpha" / "SKILL.md").is_file())
        self.assertEqual([row["name"] for row in fresh.list()], ["alpha"])
        self.assertEqual([row["action"] for row in fresh.history("alpha")], ["create"])
        self.assertTrue(fresh.doctor()["ok"])

    def test_doctor_reports_transaction_artifacts_snapshot_issues_and_drift(self):
        self.store.create("demo", "Demo skill", body="Original body")
        skill_file = self.store.skills_dir / "demo" / "SKILL.md"
        skill_file.write_text(skill_file.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
        (self.store.skills_dir / ".demo.skillsmgr-stage").mkdir()
        snapshot_dir = self.store.data_dir / "snapshots" / "global" / "demo"
        snapshot_dir.mkdir(parents=True)
        (snapshot_dir / "not-a-snapshot.md").write_text("stale", encoding="utf-8")

        report = self.store.doctor()

        self.assertFalse(report["ok"])
        self.assertIn("demo", report["filesystem_index_drift"])
        self.assertTrue(report["transaction_artifacts"])
        self.assertTrue(report["temporary_files"])
        self.assertTrue(report["stale_snapshots"])

    def test_backup_restore_is_verified_by_content_hashes(self):
        source = self.store
        source.create("demo", "Demo skill", body="Hash me")
        source.create("second", "Second skill", body="And me")

        def tree_hash(root):
            digest = hashlib.sha256()
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    digest.update(str(path.relative_to(root)).encode("utf-8"))
                    digest.update(path.read_bytes())
            return digest.hexdigest()

        archive = source.backup(self.store.data_dir / "backup.tar.gz")
        restored_dir = Path(self._tmp.name) / "restored"
        restored = Store(data_dir=restored_dir)
        restored.import_(archive)

        self.assertEqual(tree_hash(source.skills_dir), tree_hash(restored.skills_dir))

    def test_import_rejects_tampered_content_hash(self):
        import io
        import json
        import tarfile

        self.store.create("demo", "Demo skill", body="Original")
        archive = self.store.export(self.store.data_dir / "hash.tar.gz")
        tampered = self.store.data_dir / "tampered.tar.gz"
        with tarfile.open(archive, "r:gz") as source, tarfile.open(tampered, "w:gz") as target:
            for member in source.getmembers():
                if member.name == "manifest.json":
                    payload = json.loads(source.extractfile(member).read().decode("utf-8"))
                    payload["skills"][0]["content_hash"] = "0" * 64
                    encoded = json.dumps(payload).encode("utf-8")
                    replacement = tarfile.TarInfo(member.name)
                    replacement.size = len(encoded)
                    target.addfile(replacement, io.BytesIO(encoded))
                else:
                    target.addfile(member, source.extractfile(member) if member.isfile() else None)

        restored = Store(data_dir=Path(self._tmp.name) / "hash-target")
        result = restored.import_(tampered)
        self.assertEqual(result["imported"], [])
        self.assertTrue(any("hash mismatch" in item for item in result["skipped"]))
        self.assertFalse((restored.skills_dir / "demo").exists())


class TestSnapshots(IsolatedStoreTestCase):
    def test_edit_creates_snapshot_and_restore_rolls_back(self):
        self.store.create("demo", "Original", body="old")
        self.store.edit("demo", description="Changed", body="new")
        from skillsmgr.store import list_snapshots

        snapshots = list_snapshots(self.store.data_dir, "global", "demo")
        self.assertEqual(len(snapshots), 1)
        result = self.store.restore("demo", snapshot=snapshots[0])
        self.assertEqual(result["snapshot"], snapshots[0])
        self.assertEqual(self.store.get("demo")["description"], "Original")
        self.assertIn("old", self.store.get("demo")["body"])

    def test_snapshot_retention_keeps_newest_five(self):
        self.store.create("demo", "Original", body="old")
        for i in range(7):
            self.store.edit("demo", body=f"body-{i}")
        from skillsmgr.store import list_snapshots

        snapshots = list_snapshots(self.store.data_dir, "global", "demo")
        self.assertEqual(len(snapshots), 5)


class TestValidatorLoaderScopes(unittest.TestCase):
    def test_validator_accepts_good_skill(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "demo"
            p.mkdir()
            (p / "SKILL.md").write_text(_skill_body(), encoding="utf-8")
            result = validate_skill("demo", p)
            self.assertTrue(result.valid, [i.message for i in result.issues])

    def test_validator_rejects_bad_name(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "Bad Name!"
            p.mkdir()
            (p / "SKILL.md").write_text(_skill_body(), encoding="utf-8")
            self.assertFalse(validate_skill("Bad Name!", p).valid)

    def test_validator_warns_on_link_escape(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "demo"
            p.mkdir()
            (p / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Demo skill.\n---\n"
                "See [x](../../evil.md).\n",
                encoding="utf-8",
            )
            result = validate_skill("demo", p)
            self.assertTrue(
                any(
                    "outside" in i.message.lower() or "escape" in i.message.lower()
                    for i in result.issues
                )
            )

    def test_validator_reads_disabled_file(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "demo"
            p.mkdir()
            (p / "SKILL.md.disabled").write_text(
                "---\nname: demo\ndescription: Demo skill.\n---\nBody.\n",
                encoding="utf-8",
            )
            self.assertTrue(validate_skill("demo", p).valid)

    def test_validator_warns_on_missing_use_context(self):
        result = validate_text(_skill_body(description="Does stuff"))
        self.assertTrue(
            any("use-context" in i.message for i in result.warnings),
            [i.message for i in result.issues],
        )
        ok = validate_text(
            _skill_body(description="Use when deploying to staging.")
        )
        self.assertFalse(
            any("use-context" in i.message for i in ok.issues),
            [i.message for i in ok.issues],
        )

    def test_validator_warns_on_vague_filler(self):
        result = validate_text(_skill_body(description="Handles various stuff"))
        self.assertTrue(
            any("filler" in i.message for i in result.warnings),
            [i.message for i in result.issues],
        )

    def test_validator_warns_on_missing_layout_file(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "demo"
            p.mkdir()
            (p / "SKILL.md").write_text(
                _skill_body(description="Use when testing refs.")
                + "\nRead references/api.md when the API errors.\n",
                encoding="utf-8",
            )
            result = validate_skill("demo", p)
            self.assertTrue(
                any("references/api.md" in i.message for i in result.warnings),
                [i.message for i in result.issues],
            )
            (p / "references").mkdir()
            (p / "references" / "api.md").write_text("# API\n", encoding="utf-8")
            result = validate_skill("demo", p)
            self.assertFalse(
                any("references/api.md" in i.message for i in result.issues),
                [i.message for i in result.issues],
            )

    def test_validator_warns_on_oversize_body_tokens(self):
        big = "word " * 6000  # heuristic ~9000 tokens, over the 5000 cap
        result = validate_text(_skill_body() + "\n" + big)
        self.assertTrue(
            any("tokens" in i.message for i in result.warnings),
            [i.message for i in result.issues],
        )

    def test_description_score(self):
        good = description_score("Use this skill when reviewing pull requests.")
        self.assertTrue(good["has_use_context"])
        self.assertEqual(good["filler_hits"], [])
        bad = description_score("Handles various things appropriately.")
        self.assertFalse(bad["has_use_context"])
        self.assertIn("various", bad["filler_hits"])

    def test_loader_flags_malformed_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            from pathlib import Path

            p = Path(d) / "broken"
            p.mkdir()
            (p / "SKILL.md").write_text(
                "---\nname: [unclosed\n---\nbody\n", encoding="utf-8"
            )
            self.assertTrue(load_skill(p).get("malformed"))

    def test_loader_exposes_observations_and_frontmatter_extensions(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "observed"
            p.mkdir()
            (p / "SKILL.md").write_text(
                "---\nname: observed\ndescription: Observed\nclient-x:\n  mode: strict\n---\nbody\n",
                encoding="utf-8",
            )

            record = load_skill(p)

            self.assertEqual(record["frontmatter_extensions"], {"client-x": {"mode": "strict"}})
            self.assertEqual(len(record["content_hash"]), 64)
            self.assertEqual(len(record["metadata_hash"]), 64)
            self.assertEqual(record["provenance"]["path"], str(p))
            self.assertTrue(record["observed_at"].endswith("Z"))

    def test_known_scopes_include_all_agents(self):
        ids = {s.id for s in known_scopes()}
        self.assertTrue(
            {
                "global",
                "claude-code",
                "codex",
                "cursor",
                "opencode",
                "gemini",
                "commandcode",
                "agents",
            }
            <= ids
        )


class TestFrontmatterSearchUnits(unittest.TestCase):
    def test_frontmatter_roundtrip(self):
        fm, body = parse_frontmatter(_skill_body(name="x", description="Y"))
        self.assertEqual(fm["name"], "x")
        self.assertIn("Body", body)

    def test_search_scoring_prefers_exact(self):
        recs = [
            {"name": "other", "description": "mentions deploy here", "category": ""},
            {"name": "deploy", "description": "", "category": ""},
        ]
        ranked = rank_results(recs, "deploy")
        self.assertEqual(ranked[0][0]["name"], "deploy")

    def test_search_includes_body_matches(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(data_dir=d)
            store.init_db()
            store.create("body-only", "Unrelated description", body="contains unique-body-term")
            self.assertEqual([r["name"] for r in store.search("unique-body-term")], ["body-only"])

    def test_adversarial_wildcards_fail_fast(self):
        with self.assertRaises(ValueError):
            rank_results([{"name": "x", "description": "a" * 200}], "*a" * 12)
        with self.assertRaises(ValueError):
            rank_results([{"name": "x", "description": "plain"}], "x" * 201)

    def test_repeated_wildcards_are_safe_and_normal_patterns_work(self):
        ranked = rank_results(
            [{"name": "deploy-app", "description": "Deploys the app"}],
            "deploy***",
        )
        self.assertEqual(ranked[0][0]["name"], "deploy-app")

    def test_deep_frontmatter_returns_clean_error(self):
        deep = "---\n" + "".join(f"{'  ' * i}k{i}:\n" for i in range(100)) + "---\nbody\n"
        with self.assertRaises(FrontmatterError):
            parse_frontmatter(deep)

    def test_frontmatter_resource_limits_return_clean_errors(self):
        oversized = "---\ndescription: " + ("x" * 20_000) + "\n---\nbody\n"
        with self.assertRaises(FrontmatterError):
            parse_frontmatter(oversized)
        many_keys = "---\n" + "".join(f"k{i}: v\n" for i in range(300)) + "---\nbody\n"
        with self.assertRaises(FrontmatterError):
            parse_frontmatter(many_keys)


if __name__ == "__main__":
    unittest.main()
