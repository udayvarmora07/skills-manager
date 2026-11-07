"""Sidecars are trusted only for the install this tool wrote them for."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import atomic_io, hygiene, registry, sidecar_binding
from skillsmgr.source_lock import (
    SourceLockError,
    local_manifest,
    source_identity,
    source_lock_record,
    source_lock_status,
    write_source_lock,
)

DOCUMENT = "---\nname: demo\ndescription: Use demo when testing.\n---\n# Demo\n"
PROVENANCE = registry.PROVENANCE_FILENAME
LOCK = ".skillsmgr-source-lock.json"


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


def _provenance() -> dict:
    return registry.provenance_for_snapshot(_snapshot())


def _lock_record(skill: Path, state: str = "known-unverified") -> dict:
    return source_lock_record(
        source_identity("git", "owner/repo", revision="abc"),
        local_manifest(skill)["sha256"],
        {
            "scope": "global",
            "physical_root": str(skill.parent),
            "physical_path": str(skill),
            "contained": True,
        },
        state=state,
    )


class SidecarBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="sidecar-binding-"))
        os.chmod(self.tmp, 0o700)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data = self.tmp / "data"
        self.data.mkdir(mode=0o700)
        self.home = self.tmp / "home"
        self.home.mkdir(mode=0o700)
        self._saved = {
            name: os.environ.get(name) for name in ("SKILLS_MANAGER_DATA", "HOME")
        }
        os.environ["SKILLS_MANAGER_DATA"] = str(self.data)
        os.environ["HOME"] = str(self.home)
        self.addCleanup(self._restore_env)
        # Every write records under the root this Store would register, so the
        # private binding directory never falls back to another test's root.
        atomic_io.register_lock_root(self.data)
        self.skills = self.data / "skills"
        self.skills.mkdir(mode=0o700)

    def _restore_env(self) -> None:
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _skill(self, name: str = "demo") -> Path:
        directory = self.skills / name
        directory.mkdir(mode=0o700)
        (directory / "SKILL.md").write_text(DOCUMENT, encoding="utf-8")
        return directory

    def _copy_tree(self, source: Path, name: str) -> Path:
        destination = self.skills / name
        shutil.copytree(source, destination)
        return destination

    # -- provenance ----------------------------------------------------

    def test_written_provenance_reads_back_recorded_and_trusted(self) -> None:
        skill = self._skill()
        registry.write_provenance(skill, _provenance())
        loaded = registry.read_provenance(skill)
        self.assertEqual(loaded["install_binding"], "recorded")
        self.assertIs(loaded["trusted"], True)
        self.assertIs(loaded["hash_verified"], True)
        self.assertNotIn("install_binding", json.loads((skill / PROVENANCE).read_text(encoding="utf-8")))

    def test_forged_provenance_is_unrecorded_and_untrusted(self) -> None:
        real = self._skill("real")
        registry.write_provenance(real, _provenance())
        forged = self._skill("forged")
        shutil.copyfile(real / PROVENANCE, forged / PROVENANCE)
        loaded = registry.read_provenance(forged)
        self.assertEqual(loaded["install_binding"], "unrecorded")
        self.assertIs(loaded["trusted"], False)
        self.assertIs(loaded["hash_verified"], False)
        self.assertIs(loaded["remote_hash_verified"], False)

    def test_copied_provenance_is_unrecorded(self) -> None:
        real = self._skill("real")
        registry.write_provenance(real, _provenance())
        copied = self._copy_tree(real, "copied")
        loaded = registry.read_provenance(copied)
        self.assertEqual(loaded["install_binding"], "unrecorded")
        self.assertIs(loaded["trusted"], False)

    def test_edited_provenance_bytes_are_a_mismatch(self) -> None:
        skill = self._skill()
        registry.write_provenance(skill, _provenance())
        path = skill / PROVENANCE
        path.write_text(json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=4) + "\n", encoding="utf-8")
        loaded = registry.read_provenance(skill)
        self.assertEqual(loaded["install_binding"], "mismatch")
        self.assertIs(loaded["trusted"], False)
        self.assertIs(loaded["hash_verified"], False)

    def test_a_sidecar_carrying_read_time_annotations_is_rejected(self) -> None:
        skill = self._skill()
        registry.write_provenance(skill, _provenance())
        path = skill / PROVENANCE
        value = json.loads(path.read_text(encoding="utf-8"))
        for key in ("install_binding", "trusted"):
            with self.subTest(key=key):
                forged = dict(value)
                forged[key] = "recorded" if key == "install_binding" else True
                path.write_text(json.dumps(forged), encoding="utf-8")
                with self.assertRaises(registry.RegistryError):
                    registry.read_provenance(skill)

    def test_recording_failure_leaves_no_provenance_sidecar(self) -> None:
        skill = self._skill()
        with mock.patch(
            "skillsmgr.sidecar_binding.record_binding", side_effect=OSError("disk full")
        ):
            with self.assertRaises(registry.RegistryError):
                registry.write_provenance(skill, _provenance())
        self.assertFalse((skill / PROVENANCE).exists())

    # -- source lock ---------------------------------------------------

    def test_written_source_lock_reads_back_recorded(self) -> None:
        skill = self._skill()
        write_source_lock(skill, _lock_record(skill))
        status = source_lock_status(skill)
        self.assertEqual(status["install_binding"], "recorded")
        self.assertIs(status["trusted"], True)
        self.assertEqual(status["state"], "known-unverified")

    def test_copied_source_lock_is_unbound(self) -> None:
        real = self._skill("real")
        write_source_lock(real, _lock_record(real))
        copied = self._copy_tree(real, "copied")
        status = source_lock_status(copied)
        self.assertEqual(status["install_binding"], "unrecorded")
        self.assertIs(status["trusted"], False)
        self.assertEqual(status["state"], "unbound")
        self.assertEqual(status["recorded_state"], "known-unverified")

    def test_edited_source_lock_bytes_are_a_mismatch(self) -> None:
        skill = self._skill()
        write_source_lock(skill, _lock_record(skill))
        path = skill / LOCK
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        status = source_lock_status(skill)
        self.assertEqual(status["install_binding"], "mismatch")
        self.assertIs(status["trusted"], False)
        self.assertEqual(status["state"], "unbound")

    def test_binding_is_checked_on_the_bytes_that_were_validated(self) -> None:
        """A swap between validation and the binding check must not yield trust.

        The genuine, recorded lock is put back on disk *after* the forged one
        has been read and validated, which is the window a second read opens.
        """
        from skillsmgr import source_lock as module

        skill = self._skill()
        write_source_lock(skill, _lock_record(skill))
        path = skill / LOCK
        genuine = path.read_bytes()
        forged = json.loads(genuine)
        forged["source"] = dict(forged["source"], value="https://example.invalid/forged")
        forged_text = json.dumps(forged, sort_keys=True)
        real_validate = module._validate_lock

        def validate_then_restore(value):
            result = real_validate(value)
            path.write_bytes(genuine)
            return result

        path.write_text(forged_text, encoding="utf-8")
        with mock.patch.object(module, "_validate_lock", side_effect=validate_then_restore):
            status = source_lock_status(skill)
        self.assertIs(status["trusted"], False)
        self.assertEqual(status["install_binding"], "mismatch")

    def test_recording_failure_leaves_no_source_lock_sidecar(self) -> None:
        skill = self._skill()
        with mock.patch(
            "skillsmgr.sidecar_binding.record_binding", side_effect=OSError("disk full")
        ):
            with self.assertRaises(SourceLockError):
                write_source_lock(skill, _lock_record(skill))
        self.assertFalse((skill / LOCK).exists())

    def test_hygiene_reports_an_unbound_lock_instead_of_raising(self) -> None:
        real = self._skill("real")
        write_source_lock(real, _lock_record(real))
        forged = self._copy_tree(real, "forged")
        record = {"name": "forged", "scope": "global", "path": str(forged)}
        report = hygiene.hygiene_report([record], scope="global")
        categories = {finding["category"] for finding in report["findings"]}
        self.assertIn("source-lock-unbound", categories)

    # -- the binding record itself -------------------------------------

    def test_binding_state_creates_nothing(self) -> None:
        skill = self._skill()
        before = sorted(path.name for path in self.data.iterdir())
        self.assertEqual(
            sidecar_binding.binding_state(skill, PROVENANCE, b"{}"), "unrecorded"
        )
        self.assertEqual(sorted(path.name for path in self.data.iterdir()), before)

    def test_binding_directory_is_private_and_record_is_owner_only(self) -> None:
        skill = self._skill()
        record = sidecar_binding.record_binding(skill, PROVENANCE, b"payload")
        directory = self.data / sidecar_binding.BINDING_DIRNAME
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(record.stat().st_mode & 0o777, 0o600)
        stored = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(stored["sidecar"], PROVENANCE)
        self.assertEqual(stored["path"], os.path.realpath(skill))

    def test_symlinked_binding_directory_is_refused(self) -> None:
        skill = self._skill()
        outside = self.tmp / "outside"
        outside.mkdir()
        (self.data / sidecar_binding.BINDING_DIRNAME).symlink_to(
            outside, target_is_directory=True
        )
        with self.assertRaises(OSError):
            sidecar_binding.record_binding(skill, PROVENANCE, b"payload")
        self.assertEqual(
            sidecar_binding.binding_state(skill, PROVENANCE, b"payload"), "mismatch"
        )
        with self.assertRaises(registry.RegistryError):
            registry.write_provenance(skill, _provenance())
        self.assertFalse((skill / PROVENANCE).exists())
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
