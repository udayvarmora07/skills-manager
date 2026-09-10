"""Hermetic regression corpus for the tar import/export contract."""

import io
import json
import os
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


def _write_zip(path: Path, members: list[tuple[str, bytes]], *, names=(), symlinks=()) -> None:
    """Write a ZIP corpus, optionally preserving duplicate and symlink entries."""
    symlinks = set(symlinks)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", _manifest(*names))
        for name, payload in members:
            info = zipfile.ZipInfo(name)
            if name in symlinks:
                info.external_attr = (0o120777 << 16) | 0x10
            archive.writestr(info, payload)


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

    def test_zip_archive_round_trip(self):
        source = self._store("zip-source")
        source.create("zip-demo", "ZIP demo", body="zip round-trip body")
        archive = source.export(self.root / "zip-round-trip.tar.gz")
        zip_archive = self.root / "zip-round-trip.zip"
        with zipfile.ZipFile(zip_archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            with tarfile.open(archive, "r:gz") as tar:
                for member in tar.getmembers():
                    payload = tar.extractfile(member).read() if member.isreg() else b""
                    zipped.writestr(member.name, payload)
        target = self._store("zip-target")
        result = target.import_(zip_archive)
        self.assertEqual(result["imported"], ["zip-demo"])
        self.assertIn("zip round-trip body", target.get("zip-demo")["body"])

    def test_zip_traversal_absolute_windows_and_symlink_members_rejected_before_extraction(self):
        victim = self.root / "victim.txt"
        victim.write_text("keep", encoding="utf-8")
        cases = {
            "traversal": "skills/demo/../../victim.txt",
            "absolute": "/victim.txt",
            "backslash": "skills\\demo\\escape.txt",
            "drive": "C:/victim.txt",
            "symlink": "skills/demo/link",
        }
        for label, member_name in cases.items():
            with self.subTest(label=label):
                archive = self.root / f"{label}.zip"
                _write_zip(archive, [(member_name, b"escape")], symlinks={member_name} if label == "symlink" else ())
                try:
                    self._store(label).import_(archive, force=True)
                except StoreError:
                    pass
                else:
                    # Windows: zipfile normalizes "\\" to "/" inside ZipInfo on
                    # both write and read, so this member can no longer smuggle a
                    # separator past name validation; the import must then stay
                    # contained and simply find no skill document.
                    self.assertEqual(label, "backslash")
                    self.assertEqual(os.name, "nt", "only Windows may accept the backslash member")
                # The invariant that matters on every host: nothing escaped.
                self.assertEqual(victim.read_text(encoding="utf-8"), "keep")

    def test_zip_per_member_compression_ratio_is_enforced(self):
        # A stored, incompressible member must not mask a later highly
        # compressible one: the ratio budget is a per-member invariant.
        archive = self.root / "ratio-mask.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("manifest.json", _manifest("demo"))
            zipped.writestr(
                zipfile.ZipInfo("skills/demo/padding.bin"),
                bytes(range(256)) * 3907,
                compress_type=zipfile.ZIP_STORED,
            )
            zipped.writestr(
                zipfile.ZipInfo("skills/demo/bomb.bin"),
                b"\x00" * (8 * 1024 * 1024),
                compress_type=zipfile.ZIP_DEFLATED,
            )
            zipped.writestr("skills/demo/SKILL.md", _document("demo"))

        with self.assertRaisesRegex(StoreError, "compression ratio"):
            self._store().import_(archive)

    def test_zip_slash_directory_without_unix_directory_bits_is_accepted(self):
        # Many ZIP writers emit "skills/demo/" with no Unix/DOS directory bit;
        # the trailing slash is the portable marker.
        archive = self.root / "plain-dirs.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("manifest.json", _manifest("demo"))
            for name in ("skills/", "skills/demo/"):
                info = zipfile.ZipInfo(name)
                info.external_attr = 0
                zipped.writestr(info, b"")
            zipped.writestr("skills/demo/SKILL.md", _document("demo"))

        result = self._store().import_(archive)
        self.assertEqual(result["imported"], ["demo"])

    def test_zip_duplicate_members_are_rejected(self):
        archive = self.root / "duplicate.zip"
        _write_zip(
            archive,
            [("skills/demo/SKILL.md", _document("demo")), ("skills/demo/SKILL.md", _document("demo"))],
            names=("demo",),
        )
        with self.assertRaisesRegex(StoreError, "duplicate"):
            self._store().import_(archive)

    def test_zip_content_is_rejected_even_with_tar_filename(self):
        archive = self.root / "actually-a-tar.tar.gz"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("manifest.json", _manifest().decode("utf-8"))

        result = self._store().import_(archive)
        self.assertEqual(result["imported"], [])

    def test_malformed_zip_metadata_is_a_clean_store_error(self):
        archive = self.root / "bad-metadata.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("manifest.json", _manifest().decode("utf-8"))
        raw = bytearray(archive.read_bytes())
        central = raw.find(b"PK\x01\x02")
        self.assertGreaterEqual(central, 0)
        raw[central + 6 : central + 8] = b"\xff\xff"
        archive.write_bytes(raw)
        with self.assertRaisesRegex(StoreError, "invalid archive"):
            self._store().import_(archive)

    def test_zip_full_manifest_types_are_rejected_before_skill_commit(self):
        archive = self.root / "bad-full.zip"
        manifest = {
            "app": "skills-mgr",
            "version": __version__,
            "created": _CREATED,
            "full": True,
            "skills": [{"name": "demo"}],
            "trash": 123,
            "templates": [],
        }
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("manifest.json", json.dumps(manifest))
            zipped.writestr("skills/demo/SKILL.md", _document("demo", "new"))
        target = self._store()
        target.create("demo", "Original", body="old")
        with self.assertRaisesRegex(StoreError, "trash"):
            target.import_(archive, force=True, full=True)
        self.assertIn("old", target.get("demo")["body"])

    def test_new_skill_commit_failure_removes_destination(self):
        source = self._store("source-new")
        source.create("new-skill", "New skill", body="new body")
        archive = source.export(self.root / "new-failure.tar.gz")
        target = self._store("target-new")
        original_upsert = target._upsert_entry
        with mock.patch.object(target, "_upsert_entry", side_effect=StoreError("injected index failure")):
            result = target.import_(archive, force=True)
        self.assertEqual(result["imported"], [])
        self.assertTrue(result["skipped"])
        self.assertFalse((target.skills_dir / "new-skill").exists())
        self.assertEqual(target.list(), [])

    def test_failed_stage_copy_preserves_existing_skill(self):
        # Regression: staging runs before the original destination is moved
        # aside, so a failed staging copy must never delete the user's skill.
        source = self._store("stage-fail-source")
        source.create("demo", "Replacement", body="new body")
        archive = source.export(self.root / "stage-fail.tar.gz")
        target = self._store("stage-fail-target")
        target.create("demo", "Original", body="old body")

        def partial_copy(src, dst, **kwargs):
            Path(dst).mkdir(parents=True, exist_ok=True)
            (Path(dst) / "partial").write_text("torn", encoding="utf-8")
            raise OSError(5, "Input/output error")

        with mock.patch("skillsmgr.archive.shutil.copytree", side_effect=partial_copy):
            result = target.import_(archive, force=True)

        self.assertEqual(result["imported"], [])
        self.assertTrue(any("demo" in item for item in result["skipped"]))
        self.assertTrue((target.skills_dir / "demo" / "SKILL.md").is_file())
        self.assertEqual(target.get("demo")["description"], "Original")
        self.assertEqual(target.get("demo")["body"], "old body\n")

    def test_full_import_copy_failure_is_clean_and_preserves_previous_state(self):
        source = self._store("full-fail-source")
        source.create("keep", "Keep", body="keep body")
        source.create("goner", "Gone", body="gone body")
        source.remove("goner")
        (source.templates_dir / "one.md").write_text("# One\n", encoding="utf-8")
        (source.templates_dir / "two.md").write_text("# Two\n", encoding="utf-8")
        archive = source.export(self.root / "full-fail.tar.gz", full=True)

        target = self._store("full-fail-target")
        (target.templates_dir / "one.md").write_text("# Original one\n", encoding="utf-8")
        real_copyfile = __import__("shutil").copyfile
        calls = {"n": 0}

        def fail_second_template(src, dst, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError(28, "No space left on device")
            return real_copyfile(src, dst, **kwargs)

        with mock.patch("skillsmgr.archive.shutil.copyfile", side_effect=fail_second_template):
            with self.assertRaisesRegex(StoreError, "full archive payload"):
                target.import_(archive, force=True, full=True)

        self.assertEqual(
            (target.templates_dir / "one.md").read_text(encoding="utf-8"),
            "# Original one\n",
        )
        self.assertFalse((target.templates_dir / "two.md").exists())
        self.assertEqual(list(target.templates_dir.glob("*.skillsmgr-*")), [])

    def test_full_import_rejects_malformed_full_metadata_before_mutation(self):
        archive = self.root / "bad-full-metadata.zip"
        manifest = {
            "app": "skills-mgr",
            "version": __version__,
            "created": _CREATED,
            "full": "yes",
            "skills": [{"name": "demo"}],
            "trash": ["../escape"],
            "templates": [],
        }
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("manifest.json", json.dumps(manifest))
            zipped.writestr("skills/demo/SKILL.md", _document("demo", "new"))
        target = self._store()
        target.create("demo", "Original", body="old")
        with self.assertRaisesRegex(StoreError, "full must be a boolean"):
            target.import_(archive, force=True, full=True)
        self.assertIn("old", target.get("demo")["body"])

    def test_full_import_records_restored_trash_in_the_index(self):
        source = self._store("full-index-source")
        source.create("keep", "Keep")
        source.create("goner", "Gone")
        source.remove("goner")
        archive = source.export(self.root / "full-index.tar.gz", full=True)

        target = self._store("full-index-target")
        result = target.import_(archive, full=True)

        self.assertEqual(len(result["restored_trash"]), 1)
        self.assertEqual(len(target.trash_list()), 1)
        self.assertEqual(target.stats()["trashed"], 1)
        self.assertTrue(target.doctor()["ok"])

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
