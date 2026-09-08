"""Hermetic regression corpus for the tar import/export contract."""

import io
import json
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from skillsmgr import __version__
from skillsmgr.store import (
    MAX_ARCHIVE_COMPRESSION_RATIO,
    MAX_ARCHIVE_EXPANDED_BYTES,
    MAX_ARCHIVE_MEMBER_BYTES,
    MAX_ARCHIVE_MEMBERS,
    MAX_ARCHIVE_NESTING,
    MAX_ARCHIVE_PATH_LENGTH,
    Store,
    StoreError,
)


_CREATED = "2026-09-08T00:00:00Z"


def _document(name: str, body: str | None = None) -> bytes:
    body = body or f"# {name}\n\nImported body.\n"
    return (
        f"---\nname: {name}\ndescription: Use this skill for archive tests.\n---\n"
        f"{body}"
    ).encode("utf-8")


def _manifest(*names: str) -> bytes:
    return json.dumps(
        {
            "app": "skills-mgr",
            "version": __version__,
            "created": _CREATED,
            "skills": [{"name": name} for name in names],
        }
    ).encode("utf-8")


def _write_tar(path: Path, members: list[tuple[str, bytes | None, int | None]], *, names=()) -> None:
    """Write a deliberately small tar corpus, preserving duplicate/type entries."""
    with tarfile.open(path, "w:gz") as archive:
        manifest = _manifest(*names)
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest)
        archive.addfile(info, io.BytesIO(manifest))
        for name, payload, member_type in members:
            info = tarfile.TarInfo(name)
            if member_type is not None:
                info.type = member_type
                archive.addfile(info)
            else:
                payload = payload or b""
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))


class ArchiveContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _store(self, name: str = "manager") -> Store:
        store = Store(data_dir=self.root / name)
        store.init_db()
        return store

    def test_valid_tar_round_trip(self):
        source = self._store("source")
        source.create("demo", "Archive demo", body="round-trip body")
        archive = source.export(self.root / "round-trip.tar.gz")

        target = self._store("target")
        result = target.import_(archive)

        self.assertEqual(result["imported"], ["demo"])
        self.assertEqual(target.get("demo")["description"], "Archive demo")
        self.assertIn("round-trip body", target.get("demo")["body"])

    def test_absolute_and_traversal_members_are_rejected_before_extraction(self):
        victim = self.root / "victim.txt"
        victim.write_text("keep", encoding="utf-8")
        cases = {
            "absolute": "/victim.txt",
            "traversal": "skills/demo/../../victim.txt",
            "backslash": "skills\\demo\\escape.txt",
        }
        for label, member_name in cases.items():
            with self.subTest(label=label):
                archive = self.root / f"{label}.tar.gz"
                _write_tar(archive, [(member_name, b"escape", None)])
                with self.assertRaises(StoreError):
                    self._store(label).import_(archive, force=True)
                self.assertEqual(victim.read_text(encoding="utf-8"), "keep")

    def test_duplicate_members_are_rejected(self):
        archive = self.root / "duplicate.tar.gz"
        _write_tar(
            archive,
            [
                ("skills/demo/SKILL.md", _document("demo"), None),
                ("skills/demo/SKILL.md", _document("demo"), None),
            ],
        )

        with self.assertRaisesRegex(StoreError, "duplicate"):
            self._store().import_(archive)

    def test_symlink_hardlink_fifo_and_device_members_are_rejected(self):
        special_members = [
            ("symlink", getattr(tarfile, "SYMTYPE", None), "outside"),
            ("hardlink", getattr(tarfile, "LNKTYPE", None), "SKILL.md"),
            ("fifo", getattr(tarfile, "FIFOTYPE", None), None),
            ("character-device", getattr(tarfile, "CHRTYPE", None), None),
            ("block-device", getattr(tarfile, "BLKTYPE", None), None),
        ]
        for label, member_type, linkname in special_members:
            if member_type is None:  # pragma: no cover - platform tarfile guard
                continue
            with self.subTest(member_type=label):
                archive = self.root / f"{label}.tar.gz"
                _write_tar(archive, [(f"skills/demo/{label}", linkname.encode() if linkname else None, member_type)])
                with self.assertRaisesRegex(StoreError, "unsupported archive member type"):
                    self._store(label).import_(archive)

    def test_member_size_limit_is_rejected(self):
        archive = self.root / "member-size.tar.gz"
        payload = b"x" * (MAX_ARCHIVE_MEMBER_BYTES + 1)
        _write_tar(archive, [("skills/demo/payload.bin", payload, None)])

        with self.assertRaisesRegex(StoreError, "member exceeds"):
            self._store().import_(archive)

    def test_expanded_size_limit_is_rejected(self):
        archive = self.root / "expanded-size.tar.gz"
        payload = b"x" * MAX_ARCHIVE_MEMBER_BYTES
        _write_tar(
            archive,
            [
                ("skills/demo/one.bin", payload, None),
                ("skills/demo/two.bin", payload, None),
            ],
        )

        with self.assertRaisesRegex(StoreError, "expanded size"):
            self._store().import_(archive)

    def test_member_count_limit_is_rejected(self):
        archive = self.root / "member-count.tar.gz"
        members = [
            (f"skills/demo/file-{index}.txt", b"x", None)
            for index in range(MAX_ARCHIVE_MEMBERS)
        ]
        _write_tar(archive, members)

        with self.assertRaisesRegex(StoreError, "too many members"):
            self._store().import_(archive)

    def test_member_path_length_limit_is_rejected(self):
        archive = self.root / "path-length.tar.gz"
        long_name = "skills/demo/" + ("x" * MAX_ARCHIVE_PATH_LENGTH)
        _write_tar(archive, [(long_name, b"x", None)])

        with self.assertRaisesRegex(StoreError, "path is too long"):
            self._store().import_(archive)

    def test_member_depth_limit_is_rejected(self):
        archive = self.root / "depth.tar.gz"
        nested = "/".join(f"d{index}" for index in range(MAX_ARCHIVE_NESTING))
        _write_tar(archive, [(f"skills/demo/{nested}/file.txt", b"x", None)])

        with self.assertRaisesRegex(StoreError, "nested too deeply"):
            self._store().import_(archive)

    def test_compression_ratio_limit_is_rejected(self):
        archive = self.root / "ratio.tar.gz"
        _write_tar(
            archive,
            [("skills/demo/repetitive.bin", b"0" * MAX_ARCHIVE_MEMBER_BYTES, None)],
        )

        with self.assertRaisesRegex(StoreError, "compression ratio"):
            self._store().import_(archive)
        self.assertGreater(MAX_ARCHIVE_COMPRESSION_RATIO, 0)

    def test_strict_manifest_rejects_missing_and_undeclared_skills(self):
        missing = self.root / "missing.tar.gz"
        _write_tar(missing, [], names=("declared",))
        with self.assertRaisesRegex(StoreError, "missing"):
            self._store("missing-target").import_(missing)

        extra = self.root / "extra.tar.gz"
        _write_tar(
            extra,
            [
                ("skills/declared/SKILL.md", _document("declared"), None),
                ("skills/extra/SKILL.md", _document("extra"), None),
            ],
            names=("declared",),
        )
        with self.assertRaisesRegex(StoreError, "missing from manifest"):
            self._store("extra-target").import_(extra)

    def test_manifestless_skill_list_falls_back_to_archive_directories(self):
        archive = self.root / "manifestless.tar.gz"
        _write_tar(
            archive,
            [("skills/loose/SKILL.md", _document("loose"), None)],
            names=(),
        )

        target = self._store()
        result = target.import_(archive)

        self.assertEqual(result["imported"], ["loose"])
        self.assertEqual(target.get("loose")["description"], "Use this skill for archive tests.")

    def test_zip_content_is_rejected_even_with_tar_filename(self):
        archive = self.root / "actually-a-tar.tar.gz"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("manifest.json", _manifest().decode("utf-8"))

        with self.assertRaisesRegex(StoreError, "ZIP archives are not supported"):
            self._store().import_(archive)

    def test_failed_per_skill_commit_restores_destination_and_reports_result(self):
        source = self._store("source")
        source.create("first", "New first", body="new first body")
        source.create("second", "New second", body="new second body")
        archive = source.export(self.root / "commit-failure.tar.gz")

        target = self._store("target")
        target.create("first", "Old first", body="old first body")
        target.create("second", "Old second", body="old second body")
        real_upsert = target._upsert_entry

        def fail_second(name):
            if name == "second":
                raise StoreError("injected per-skill commit failure")
            return real_upsert(name)

        with mock.patch.object(target, "_upsert_entry", side_effect=fail_second):
            result = target.import_(archive, force=True)

        self.assertEqual(result["imported"], ["first"])
        self.assertEqual(len(result["skipped"]), 1)
        self.assertIn("second", result["skipped"][0])
        self.assertIn("injected per-skill commit failure", result["skipped"][0])
        self.assertEqual(target.get("first")["description"], "New first")
        self.assertEqual(target.get("second")["description"], "Old second")
        self.assertIn("old second body", target.get("second")["body"])
        self.assertFalse((target.skills_dir / "second.skillsmgr-stage").exists())


if __name__ == "__main__":
    unittest.main()
