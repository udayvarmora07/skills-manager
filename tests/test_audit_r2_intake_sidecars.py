"""R2 / S2 (docs/28): manager sidecars never survive external intake.

``.skillsmgr-provenance.json`` and ``.skillsmgr-source-lock.json`` are
unauthenticated.  A forged provenance file made ``Store.get`` report
``registry_provenance`` with ``hash_verified: true`` for a skill that was never
fetched, and a forged lock showed "known-verified" with a fake git source.
Every external intake must drop both: ``Store.add``, archive import (skills and
full-archive trash), the multipart folder upload, and registry snapshot
validation.
"""

from __future__ import annotations

import gzip
import io
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from skillsmgr import registry
from skillsmgr.source_lock import source_lock_status
from skillsmgr.store import Store, StoreError
from skillsmgr.web_upload import upload_folder

PROVENANCE = ".skillsmgr-provenance.json"
LOCK = ".skillsmgr-source-lock.json"
DOCUMENT = "---\nname: demo\ndescription: Use demo when testing intake.\n---\n# Demo\n"


def _snapshot() -> dict:
    files = [{"path": "SKILL.md", "contents": DOCUMENT}]
    return {
        "id": "owner/repo/demo",
        "source": "owner/repo",
        "slug": "demo",
        "page_url": "https://skills.sh/owner/repo/demo",
        "api_url": "https://skills.sh/api/download/owner/repo/demo",
        "files": files,
        "hash": registry.registry_snapshot_hash(files),
        "snapshot_hash": registry.snapshot_hash(files),
        "registry_hash": registry.registry_snapshot_hash(files),
        "hash_verified": True,
        "_registry": {"cache_state": "miss", "stale": False},
    }


def _forged_lock() -> str:
    return json.dumps({
        "version": 1,
        "state": "known-verified",
        "source": {"kind": "git", "url": "https://example.invalid/forged.git"},
        "content_hash": "0" * 64,
    })


class IntakeStripsSidecars(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="r2-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.store = Store(self.tmp / "data")
        self.store.init_db()

    def _forged_source(self, *, provenance_only: bool = False) -> Path:
        source = self.tmp / "incoming" / "demo"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(DOCUMENT, encoding="utf-8")
        # A real, well-formed provenance record: forging one needs no secret.
        registry.write_provenance(source, registry.provenance_for_snapshot(_snapshot()))
        if provenance_only:
            return source
        (source / LOCK).write_text(_forged_lock(), encoding="utf-8")
        nested = source / "references"
        nested.mkdir()
        (nested / PROVENANCE).write_text("{}", encoding="utf-8")
        return source

    def _assert_clean(self, skill_dir: Path) -> None:
        leftovers = sorted(
            path.relative_to(skill_dir).as_posix()
            for path in skill_dir.rglob("*")
            if path.name in (PROVENANCE, LOCK)
        )
        self.assertEqual(leftovers, [])

    def test_forged_provenance_is_not_reported_after_add(self) -> None:
        source = self._forged_source(provenance_only=True)
        self.assertTrue(registry.read_provenance(source)["hash_verified"])  # the forgery is well-formed
        self.store.add(source)
        record = self.store.get("demo")
        self.assertNotIn("registry_provenance", record)
        self._assert_clean(self.store.skills_dir / "demo")
        # The caller's own folder is not modified.
        self.assertTrue((source / PROVENANCE).is_file())

    def test_forged_source_lock_is_not_carried_in_by_add(self) -> None:
        self.store.add(self._forged_source())
        status = source_lock_status(self.store.skills_dir / "demo")
        self.assertEqual(status["state"], "missing")

    def _archive_with_sidecars(self, *, full: bool) -> Path:
        self.store.create("alpha", "Use when testing intake sidecars.")
        exported = Path(self.store.export(self.tmp / "clean.tar.gz", full=full))
        plain = gzip.decompress(exported.read_bytes())
        buffer = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(plain)) as source, tarfile.open(fileobj=buffer, mode="w") as out:
            for member in source.getmembers():
                payload = source.extractfile(member) if member.isreg() else None
                out.addfile(member, payload)
            extra = {
                f"skills/alpha/{PROVENANCE}": "{}",
                f"skills/alpha/{LOCK}": _forged_lock(),
                f"skills/alpha/sub/{LOCK}": _forged_lock(),
            }
            for name, text in extra.items():
                data = text.encode()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                out.addfile(info, io.BytesIO(data))
        archive = self.tmp / "forged.tar.gz"
        archive.write_bytes(gzip.compress(buffer.getvalue()))
        return archive

    def test_archive_import_strips_sidecars(self) -> None:
        archive = self._archive_with_sidecars(full=False)
        target = Store(self.tmp / "other")
        target.init_db()
        result = target.import_(archive)
        self.assertEqual(result["imported"], ["alpha"])
        self._assert_clean(target.skills_dir / "alpha")
        self.assertNotIn("registry_provenance", target.get("alpha"))

    def test_multipart_upload_strips_sidecars(self) -> None:
        parts = [
            {"filename": "demo/SKILL.md", "content": DOCUMENT.encode()},
            {"filename": f"demo/{PROVENANCE}", "content": b"{}"},
            {"filename": f"demo/{LOCK}", "content": _forged_lock().encode()},
        ]
        result = upload_folder(parts, self.store.add)
        self.assertEqual(result["imported"], ["demo"])
        self._assert_clean(self.store.skills_dir / "demo")

    def test_registry_snapshot_rejects_the_lock_sidecar(self) -> None:
        for path in (LOCK, f"nested/{LOCK}", f"nested/{PROVENANCE}"):
            with self.subTest(path=path):
                snapshot = _snapshot()
                snapshot["files"] = snapshot["files"] + [{"path": path, "contents": "{}"}]
                with self.assertRaises(StoreError) as ctx:
                    registry.validate_snapshot(snapshot)
                self.assertIn("manager sidecar", str(ctx.exception))

    def test_registry_install_is_undone_when_provenance_cannot_be_recorded(self) -> None:
        from unittest import mock

        from skillsmgr import cli_handlers

        source = self.tmp / "staged" / "demo"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(DOCUMENT, encoding="utf-8")
        installed = self.store.add(source)
        with mock.patch.object(registry, "write_provenance", side_effect=registry.RegistryError("disk full")):
            with self.assertRaises(StoreError) as ctx:
                cli_handlers._record_registry_provenance(
                    self.store, "demo", installed, registry.provenance_for_snapshot(_snapshot())
                )
        self.assertIn("rolled back", str(ctx.exception))
        self.assertFalse((self.store.skills_dir / "demo").exists())


if __name__ == "__main__":
    unittest.main()
