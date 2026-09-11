"""Encoding contract regressions for issue #13 (non-UTF8 ``SKILL.md``).

Contract pinned here (maintainer decision 2026-09-11, recorded on issue #13):

* **Read/report paths tolerate an undecodable document.** ``loader.load_skill``,
  ``scan_dir``, ``Store.list``/``get``, ``Store.resync`` and ``Store.doctor``
  never raise a raw ``UnicodeDecodeError``.  The row is kept - the filesystem
  is the source of truth, so a directory that exists on disk must stay visible -
  and is marked ``malformed`` (which already maps to the observed ``invalid``
  instance state) plus a ``decode_error`` message naming the file and the fix.
  ``doctor`` additionally reports the skill in ``undecodable_documents`` and
  stops reporting ``ok``.
* **Write paths fail closed.** Any path that would rewrite a document from text
  it read back (``Store.update``, ``Store.restore``, ``read_snapshot``,
  ``scopes.edit_skill``, ``scopes.restore_snapshot``, ``get_raw``, sync
  overwrite) raises a clean :class:`StoreError` naming the skill and the fix,
  and leaves the file byte-identical.  Lossy replacement characters must never
  reach a write.

All state lives in an isolated temporary data directory/HOME.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from skillsmgr import cli, scopes
from skillsmgr.frontmatter import dump_frontmatter
from skillsmgr.loader import load_skill, scan_dir
from skillsmgr.root_discovery import annotate_instance_states
from skillsmgr.store import Store, StoreError, read_snapshot, write_snapshot
from skillsmgr.validator import validate_skill


def document(name: str, description: str = "A useful skill", body: str = "Body.\n") -> str:
    return dump_frontmatter({"name": name, "description": description}) + body


def corrupt_utf8(path: Path, *, name: str = "enc") -> bytes:
    """Append a lone latin-1 byte, making ``path`` invalid UTF-8."""
    with path.open("ab") as handle:
        handle.write(b"caf\xe9\n")
    return path.read_bytes()


class EncodingCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        self._old_home = os.environ.get("HOME")
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(self.tmp.name) / "data")
        os.environ["HOME"] = self.tmp.name
        self.store = Store()
        self.store.init_db()
        scopes.set_global_store(self.store)
        self.addCleanup(self._reset_environment)

    def _reset_environment(self):
        scopes.set_global_store(None)
        for key, old in (
            ("SKILLS_MANAGER_DATA", self._old_data),
            ("HOME", self._old_home),
        ):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def install(self, name: str = "enc") -> Path:
        """Create an indexed skill whose SKILL.md is then made invalid UTF-8."""
        self.store.create(name, description="Encoding probe")
        skill_dir = self.store.skills_dir / name
        corrupt_utf8(skill_dir / "SKILL.md", name=name)
        self.broken_bytes = (skill_dir / "SKILL.md").read_bytes()
        return skill_dir

    def install_agent(self, name: str = "enc") -> Path:
        """Create an unindexed agent-scope skill, then make it invalid UTF-8."""
        skill_dir = Path(self.tmp.name) / ".agents" / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(document(name), encoding="utf-8")
        corrupt_utf8(skill_dir / "SKILL.md", name=name)
        self.broken_bytes = (skill_dir / "SKILL.md").read_bytes()
        return skill_dir

    def invoke(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", str(Path(self.tmp.name) / "data"), *argv])
        return code, out.getvalue(), err.getvalue()


class TestReadPathsTolerateUndecodableDocuments(EncodingCase):
    def test_load_skill_marks_the_row_instead_of_raising(self):
        skill_dir = self.install("enc")
        entry = load_skill(skill_dir)
        self.assertEqual(entry["name"], "enc")
        self.assertTrue(entry["malformed"])
        self.assertIn("not valid UTF-8", entry["decode_error"])
        self.assertIn("SKILL.md", entry["decode_error"])
        # The body stays readable (U+FFFD for the bad byte) rather than empty.
        self.assertIn("\ufffd", entry["body"])

    def test_scan_dir_keeps_and_marks_the_undecodable_row(self):
        self.install("enc")
        entries = scan_dir(self.store.skills_dir)
        self.assertEqual([e["name"] for e in entries], ["enc"])
        self.assertTrue(entries[0]["malformed"])
        self.assertIn("not valid UTF-8", entries[0]["decode_error"])

    def test_clean_documents_report_no_decode_error(self):
        self.store.create("clean", description="Clean skill")
        entry = load_skill(self.store.skills_dir / "clean")
        self.assertIsNone(entry["decode_error"])
        self.assertFalse(entry["malformed"])

    def test_store_list_survives_and_surfaces_the_decode_error(self):
        self.install("enc")
        rows = {row["name"]: row for row in self.store.list()}
        self.assertIn("enc", rows)
        self.assertTrue(rows["enc"]["malformed"])
        self.assertIn("not valid UTF-8", rows["enc"]["decode_error"])
        # Observation enrichment still ran (the loop must not bail out).
        self.assertIn("content_hash", rows["enc"])

    def test_store_get_survives_and_surfaces_the_decode_error(self):
        self.install("enc")
        record = self.store.get("enc")
        self.assertTrue(record["malformed"])
        self.assertIn("not valid UTF-8", record["decode_error"])

    def test_store_resync_reports_counts_without_raising(self):
        self.install("enc")
        self.store.create("clean", description="Clean skill")
        result = self.store.resync()
        self.assertEqual(result["removed"], 0)
        rows = {row["name"]: row for row in self.store.list()}
        self.assertEqual(sorted(rows), ["clean", "enc"])

    def test_store_doctor_reports_undecodable_document_as_drift(self):
        self.install("enc")
        self.store.resync()
        report = self.store.doctor()
        self.assertEqual(report["undecodable_documents"], ["enc"])
        self.assertFalse(report["ok"])
        self.assertEqual(report["skills_on_disk"], 1)

    def test_doctor_reports_ok_once_the_document_is_repaired(self):
        skill_dir = self.install("enc")
        (skill_dir / "SKILL.md").write_bytes(self.broken_bytes.replace(b"caf\xe9", b"cafe"))
        report = self.store.doctor()
        self.assertEqual(report["undecodable_documents"], [])
        self.store.resync()
        self.assertTrue(self.store.doctor()["ok"])

    def test_undecodable_row_is_classified_invalid_not_hidden(self):
        self.install("enc")
        records = scan_dir(self.store.skills_dir)
        record = records[0]
        record["scope"] = "global"
        annotate_instance_states([record])
        self.assertEqual(record["instance_state"], "invalid")
        self.assertEqual(record["effective_state"], "unresolved")

    def test_agent_scope_scan_marks_undecodable_row(self):
        self.install_agent("enc")
        rows = {row["name"]: row for row in scopes.scan_scope("agents")}
        self.assertIn("enc", rows)
        self.assertTrue(rows["enc"]["malformed"])
        self.assertIn("invalid", rows["enc"]["instance_states"])

    def test_validator_still_reports_a_clean_encoding_error(self):
        skill_dir = self.install("enc")
        result = validate_skill("enc", skill_dir)
        self.assertFalse(result.valid)
        messages = [getattr(issue, "message", str(issue)) for issue in result.errors]
        self.assertTrue(any("UTF-8" in message for message in messages), messages)


class TestWritePathsFailClosedOnUndecodableDocuments(EncodingCase):
    def assert_refused(self, callable_, name: str = "enc"):
        with self.assertRaises(StoreError) as caught:
            callable_()
        message = str(caught.exception)
        self.assertIn(name, message)
        self.assertIn("not valid UTF-8", message)
        self.assertIn("UTF-8", message)
        return message

    def assert_file_unchanged(self, skill_dir: Path):
        self.assertEqual((skill_dir / "SKILL.md").read_bytes(), self.broken_bytes)

    def test_store_edit_refuses_and_leaves_the_file_untouched(self):
        skill_dir = self.install("enc")
        self.assert_refused(lambda: self.store.edit("enc", description="Rewritten"))
        self.assert_file_unchanged(skill_dir)

    def test_store_restore_refuses_when_current_document_is_undecodable(self):
        self.store.create("enc", description="Encoding probe")
        snapshot = write_snapshot(
            self.store.data_dir, "global", "enc", document("enc") + "old body\n"
        )
        skill_dir = self.store.skills_dir / "enc"
        corrupt_utf8(skill_dir / "SKILL.md")
        self.broken_bytes = (skill_dir / "SKILL.md").read_bytes()
        self.assert_refused(lambda: self.store.restore("enc", snapshot=snapshot))
        self.assert_file_unchanged(skill_dir)

    def test_scope_get_raw_reports_a_clean_error(self):
        self.install_agent("enc")
        self.assert_refused(lambda: scopes.get_raw("agents", "enc"))

    def test_scope_edit_refuses_and_leaves_the_file_untouched(self):
        skill_dir = self.install_agent("enc")
        self.assert_refused(lambda: scopes.edit_skill("agents", "enc", description="Rewritten"))
        self.assert_file_unchanged(skill_dir)

    def test_read_snapshot_refuses_an_undecodable_snapshot(self):
        self.store.create("enc", description="Encoding probe")
        snapshot_id = write_snapshot(
            self.store.data_dir, "global", "enc", "original body\n"
        )
        snap = (
            self.store.data_dir / "snapshots" / "global" / "enc" / f"{snapshot_id}.md"
        )
        corrupt_utf8(snap)
        self.assert_refused(
            lambda: read_snapshot(self.store.data_dir, "global", "enc", snapshot_id)
        )


class TestCliSurfacesStayClean(EncodingCase):
    def test_list_and_doctor_never_print_a_traceback(self):
        self.install("enc")
        self.store.resync()
        code, out, err = self.invoke(["doctor", "--json"])
        self.assertNotIn("Traceback", err)
        self.assertNotIn("codec", err.lower())
        report = json.loads(out)
        self.assertEqual(report["undecodable_documents"], ["enc"])
        self.assertFalse(report["ok"])
        # The JSON doctor branch keeps its historical exit-code contract.
        self.assertEqual(code, cli.EXIT_OK)

    def test_doctor_human_output_names_the_document_and_the_fix(self):
        self.install("enc")
        self.store.resync()
        code, out, err = self.invoke(["doctor"])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertNotIn("Traceback", err)
        self.assertIn("not valid UTF-8", out)
        self.assertIn("enc", out)
        self.assertIn("re-save as UTF-8", out)

    def test_list_still_returns_the_skill(self):
        self.install("enc")
        code, out, err = self.invoke(["list", "--json"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertNotIn("Traceback", err)
        rows = {row["name"]: row for row in json.loads(out)}
        self.assertIn("enc", rows)
        self.assertTrue(rows["enc"]["malformed"])

    def test_edit_reports_a_clean_error_instead_of_a_codec_message(self):
        self.install("enc")
        code, _, err = self.invoke(["edit", "enc", "--description", "Rewritten"])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertNotIn("Traceback", err)
        self.assertNotIn("codec", err.lower())
        self.assertIn("UTF-8", err)


class TestRestSurfacesStayClean(unittest.TestCase):
    """The REST read surfaces must report drift, never a 500 or a codec error."""

    @classmethod
    def setUpClass(cls):
        import threading
        import urllib.request

        from skillsmgr.webapp import WebAppServer

        cls._urllib = urllib.request
        cls.tmp = tempfile.TemporaryDirectory()
        cls._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["SKILLS_MANAGER_DATA"] = cls.tmp.name
        store = Store()
        store.init_db()
        store.create("enc", description="Encoding probe")
        corrupt_utf8(store.skills_dir / "enc" / "SKILL.md")
        cls.store = store
        cls.server = WebAppServer(store, port=0)
        cls.base = f"http://127.0.0.1:{cls.server.httpd.server_port}"
        cls._thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls._thread.join(timeout=5)
        cls.server.httpd.server_close()
        cls.tmp.cleanup()
        if cls._old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = cls._old_data

    @classmethod
    def get(cls, path: str):
        try:
            with cls._urllib.urlopen(cls.base + path, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except cls._urllib.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_list_reports_the_malformed_row(self):
        status, rows = self.get("/api/skills")
        self.assertEqual(status, 200)
        row = next(item for item in rows if item["name"] == "enc")
        self.assertTrue(row["malformed"])
        self.assertIn("not valid UTF-8", row["decode_error"])

    def test_detail_reports_the_malformed_row_instead_of_404(self):
        status, record = self.get("/api/skills/enc")
        self.assertEqual(status, 200)
        self.assertTrue(record["malformed"])
        self.assertIn("not valid UTF-8", record["decode_error"])

    def test_doctor_reports_the_undecodable_document(self):
        status, report = self.get("/api/doctor")
        self.assertEqual(status, 200)
        self.assertEqual(report["undecodable_documents"], ["enc"])
        self.assertFalse(report["ok"])


if __name__ == "__main__":
    unittest.main()

