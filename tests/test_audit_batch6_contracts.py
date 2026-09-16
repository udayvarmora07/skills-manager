"""Red-first regression tests for the deep-audit batch 6 findings.

Covers the three remaining Medium rows and the next two Low rows in the audit's
own severity order:

* ``STORE-11`` — the mutation lock is process-local, so two real processes on one
  data dir produced a raw ``FileNotFoundError`` out of the toggle rename and
  stranded ``.skillsmgr-tmp`` artifacts that no repair path could clear.
* ``SCOPE-5`` — ``_safe_scope_skill_path`` mixed a resolved record path with an
  unresolved root, making nested skills unreachable when an ancestor of the scope
  root is a symlink.  This one is **pinned, not red-first**: see the class
  docstring, the code was already correct here and the test records the proof.
* ``SCOPE-8`` — ``sync_skill`` leaked a raw ``OSError`` to callers, discarded a
  multi-target run's completed work, and accepted read-only targets.
* ``SEC-10`` — an aggregate GET rescanned every scope twice per request.
* ``SEC-11`` — the multipart parser altered uploaded content (``rstrip`` ate real
  trailing newlines; a literal delimiter inside content split a part).

Stdlib only.  Each test drives the real seam the audit described: a real Store
tree, real scope roots (with real symlinks), a live loopback server where the
finding was an HTTP behaviour, and the real multipart parser.
"""

from __future__ import annotations

import http.client
import json
import multiprocessing
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import skillsmgr.paths as paths_module
from skillsmgr import loader, scopes
from skillsmgr.store import Store, StoreError


class BatchSixCase(unittest.TestCase):
    """Base: fresh HOME + data root per test, no environment leakage."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self._old = {key: os.environ.get(key) for key in ("HOME", "SKILLS_MANAGER_DATA")}
        os.environ["HOME"] = str(self.home)
        os.environ["SKILLS_MANAGER_DATA"] = str(self.base / "data")
        scopes.set_global_store(None)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        scopes.set_global_store(None)
        for key, old in self._old.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    @staticmethod
    def _document(name: str, description: str = "A skill for tests.") -> str:
        return f"---\nname: {name}\ndescription: {description}\n---\nbody\n"

    def _agent_skill(self, scope_id: str, name: str, relative: str | None = None) -> Path:
        roots = {
            "agents": self.home / ".agents" / "skills",
            "cursor": self.home / ".cursor" / "skills",
            "gemini": self.home / ".gemini" / "skills",
            "codex": self.home / ".codex" / "skills",
        }
        target = roots[scope_id] / (relative or name)
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(self._document(name), encoding="utf-8")
        return target

    def _store(self) -> Store:
        store = Store()
        store.init_db()
        return store


# ------------------------------------------------------------------- STORE-11


class ConcurrentMutationResilienceTests(BatchSixCase):
    """STORE-11: real processes share the mutation exclusion contract."""

    @staticmethod
    def _hold_lock(path: str, ready, release):
        from skillsmgr.atomic_io import mutation_lock

        lock = mutation_lock(Path(path))
        lock.acquire()
        ready.set()
        release.wait(5)
        lock.release()

    def test_mutation_lock_excludes_a_real_second_process(self):
        from skillsmgr.atomic_io import mutation_lock

        context = multiprocessing.get_context("fork")
        lock_path = self.base / "cross-process.lock"
        ready = context.Event()
        release = context.Event()
        process = context.Process(
            target=self._hold_lock, args=(str(lock_path), ready, release)
        )
        process.start()
        self.addCleanup(release.set)
        self.addCleanup(process.join, 5)
        self.assertTrue(ready.wait(5))

        acquired = threading.Event()
        elapsed = []

        def contender():
            started = time.monotonic()
            lock = mutation_lock(lock_path)
            lock.acquire()
            elapsed.append(time.monotonic() - started)
            acquired.set()
            lock.release()

        thread = threading.Thread(target=contender)
        thread.start()
        self.assertFalse(acquired.wait(0.2), "second process did not exclude the lock")
        release.set()
        thread.join(5)
        process.join(5)
        self.assertTrue(acquired.is_set())
        self.assertGreaterEqual(elapsed[0], 0.15)
        self.assertEqual(process.exitcode, 0)


    def _racing_rename(self, original):
        """Return a ``Path.rename`` that loses the race the way a second process does.

        The audit's reproduction had two real processes on one data dir: the
        check passed, then the other process moved the document away, and the
        rename failed with a raw ``FileNotFoundError``.
        """

        def rename(self, target, *args, **kwargs):
            try:
                os.unlink(self)
            except OSError:
                pass
            return original(self, target, *args, **kwargs)

        return rename

    def test_disable_reports_a_concurrent_change_instead_of_a_raw_oserror(self):
        store = self._store()
        store.create("raced", "A skill another process will move.")
        original = Path.rename
        with mock.patch.object(Path, "rename", self._racing_rename(original)):
            with self.assertRaises(StoreError) as ctx:
                store.disable("raced")
        message = str(ctx.exception)
        self.assertIn("raced", message)
        self.assertTrue(
            "concurrent" in message.lower() or "changed" in message.lower(),
            f"the message must name the cross-process cause: {message!r}",
        )
        self.assertNotIsInstance(ctx.exception, FileNotFoundError)

    def test_enable_reports_a_concurrent_change_instead_of_a_raw_oserror(self):
        store = self._store()
        store.create("raced-enable", "A skill another process will move.")
        store.disable("raced-enable")
        original = Path.rename
        with mock.patch.object(Path, "rename", self._racing_rename(original)):
            with self.assertRaises(StoreError) as ctx:
                store.enable("raced-enable")
        self.assertNotIsInstance(ctx.exception, FileNotFoundError)
        self.assertIn("raced-enable", str(ctx.exception))

    def test_a_scope_toggle_reports_a_concurrent_change_cleanly(self):
        self._agent_skill("agents", "scope-raced")
        original = Path.rename
        with mock.patch.object(Path, "rename", self._racing_rename(original)):
            with self.assertRaises(StoreError) as ctx:
                scopes.toggle_skill("agents", "scope-raced", enable=False)
        self.assertNotIsInstance(ctx.exception, FileNotFoundError)

    def test_resync_clears_abandoned_transaction_residue(self):
        # The audit's repro: a cross-process move stranded ``.skillsmgr-tmp``
        # files inside trash copies, and neither resync() nor doctor() could
        # clear them, so doctor().ok stayed False until a human intervened.
        store = self._store()
        store.create("residue", "A skill that will be trashed.")
        store.remove("residue")
        trash_dirs = sorted((store.data_dir / "trash").iterdir())
        self.assertTrue(trash_dirs, "the trash copy must exist for this regression")
        stale = trash_dirs[-1] / ".SKILL.md.abc123.skillsmgr-tmp"
        stale.write_text("half-written", encoding="utf-8")
        old = time.time() - 3600
        os.utime(stale, (old, old))

        before = store.doctor()
        self.assertIn(
            str(stale.relative_to(store.data_dir)), before["temporary_files"]
        )
        self.assertFalse(before["ok"])

        store.resync()
        self.assertFalse(stale.exists(), "resync must clear abandoned residue")

        after = store.doctor()
        self.assertEqual(after["transaction_artifacts"], [])
        self.assertTrue(after["ok"], f"doctor must be repairable: {after}")

    def test_a_fresh_transaction_artifact_is_never_swept(self):
        # A concurrent writer's staging file must survive: only artifacts older
        # than the documented grace window are abandoned.
        store = self._store()
        store.create("live-artifact", "A skill with a live staging file.")
        fresh = store.skills_dir / ".SKILL.md.live.skillsmgr-tmp"
        fresh.write_text("mid-write", encoding="utf-8")

        store.resync()

        self.assertTrue(fresh.exists(), "a fresh staging file is a live writer's")
        self.assertFalse(store.doctor()["ok"])
        fresh.unlink()

    def test_the_sweep_is_reported_through_the_diagnostics_channel(self):
        import contextlib
        import io

        store = self._store()
        store.create("reported", "A skill whose residue is reported.")
        stale = store.skills_dir / ".SKILL.md.report.skillsmgr-tmp"
        stale.write_text("half-written", encoding="utf-8")
        old = time.time() - 3600
        os.utime(stale, (old, old))

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            store.resync()

        self.assertFalse(stale.exists())
        self.assertIn("skillsmgr-tmp", stderr.getvalue())


# -------------------------------------------------------------------- SCOPE-5


class SymlinkedScopeRootTests(BatchSixCase):
    """SCOPE-5, pinned as already-closed.

    On the current tree the record path is **not** resolved for a recursive
    scope (``loader.scan_dir`` stores the on-disk child path), so the
    ``relative_to`` mismatch the audit reproduced no longer exists; the fix that
    removed it was SCOPE-18's rewrite of this loop.  Verified against the
    audit's own shape — an ancestor of the scope root is a symlink — before
    accepting the finding as closed.  These tests keep it closed.
    """

    def _linked_home(self) -> Path:
        real = self.base / "realhome"
        real.mkdir()
        link = self.base / "linkhome"
        try:
            os.symlink(real, link)
        except (OSError, NotImplementedError):  # pragma: no cover - platform guard
            self.skipTest("symlinks are unavailable on this platform")
        return link

    def test_nested_skills_stay_reachable_below_a_symlinked_home(self):
        linked = self._linked_home()
        os.environ["HOME"] = str(linked)
        scopes.set_global_store(None)
        base = linked / ".cursor" / "skills"
        for relative, name in (("cat/one", "one"), ("grp/sub/two", "two")):
            target = base / relative
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text(self._document(name), encoding="utf-8")

        self.assertEqual(
            [r["name"] for r in scopes.scan_scope("cursor")], ["one", "two"]
        )
        for name in ("one", "two"):
            with self.subTest(skill=name):
                self.assertEqual(scopes.get_skill("cursor", name)["name"], name)
                self.assertIn(f"name: {name}", scopes.get_raw("cursor", name))
                scopes.toggle_skill("cursor", name, enable=False)
                self.assertTrue(scopes.get_skill("cursor", name)["disabled"])
                scopes.toggle_skill("cursor", name, enable=True)

    def test_a_symlinked_scope_root_itself_stays_addressable(self):
        linked = self._linked_home()
        os.environ["HOME"] = str(linked)
        scopes.set_global_store(None)
        real_root = self.base / "real-cursor-skills"
        (real_root / "cat" / "nested").mkdir(parents=True)
        (real_root / "cat" / "nested" / "SKILL.md").write_text(
            self._document("nested"), encoding="utf-8"
        )
        (linked / ".cursor").mkdir(parents=True)
        os.symlink(real_root, linked / ".cursor" / "skills")

        self.assertEqual(scopes.get_skill("cursor", "nested")["name"], "nested")
        scopes.toggle_skill("cursor", "nested", enable=False)
        self.assertTrue(scopes.get_skill("cursor", "nested")["disabled"])

    def test_a_grouping_directory_sharing_the_name_does_not_hide_the_skill(self):
        # SCOPE-18's shape, kept alongside SCOPE-5 because both live in the same
        # resolver: the flat path exists but holds no document.
        linked = self._linked_home()
        os.environ["HOME"] = str(linked)
        scopes.set_global_store(None)
        target = linked / ".cursor" / "skills" / "deploy" / "deploy"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(self._document("deploy"), encoding="utf-8")

        self.assertEqual(scopes.get_skill("cursor", "deploy")["name"], "deploy")
        self.assertIn("deploy", scopes.get_raw("cursor", "deploy"))


# -------------------------------------------------------------------- SCOPE-8


class SyncFailureHandlingTests(BatchSixCase):
    def _read_only(self, scope_id: str) -> Path:
        """Create an existing scope root that cannot be written to."""
        target = self._agent_skill(scope_id, f"placeholder-{scope_id}")
        shutil.rmtree(target)
        root = target.parent
        os.chmod(root, 0o500)
        self.addCleanup(os.chmod, root, 0o700)
        if os.access(root, os.W_OK):  # pragma: no cover - e.g. running as root
            self.skipTest("this platform ignores directory write permissions")
        return root

    def test_a_read_only_target_is_not_an_implicit_target(self):
        # The default target list is documented as "every writable existing
        # scope"; a read-only root is not writable, so it is not a target and
        # the run must not fail.
        self._read_only("gemini")
        scopes._global_store().create("implicit", "A skill for the implicit target list.")

        result = scopes.sync_skill("implicit", "global", None)

        self.assertEqual(result["synced"], [])
        self.assertEqual(result["skipped"], [])

    def test_an_explicit_read_only_target_is_skipped_with_a_reason(self):
        self._read_only("gemini")
        scopes._global_store().create("explicit", "A skill for an explicit target.")

        result = scopes.sync_skill("explicit", "global", ["gemini"])

        self.assertEqual(result["synced"], [])
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(result["skipped"][0]["scope"], "gemini")
        self.assertIn("read-only", result["skipped"][0]["reason"])

    def test_a_failed_target_does_not_discard_the_targets_that_succeeded(self):
        self._read_only("gemini")
        scopes._global_store().create("partial", "A skill synced to two targets.")

        with mock.patch.object(
            scopes.shutil, "copytree", side_effect=self._fail_for_stage("agents")
        ):
            result = scopes.sync_skill("partial", "global", ["codex", "agents"])

        self.assertEqual(result["synced"], ["codex"])
        self.assertEqual([entry["scope"] for entry in result["skipped"]], ["agents"])
        self.assertIn("copy failed", result["skipped"][0]["reason"])
        self.assertEqual(scopes.get_skill("codex", "partial")["name"], "partial")

    @staticmethod
    def _fail_for_stage(scope_id: str):
        original = shutil.copytree

        def copytree(source, destination, *args, **kwargs):
            if scope_id in str(destination):
                raise OSError("copy failed")
            return original(source, destination, *args, **kwargs)

        return copytree

    def test_a_total_failure_is_a_clean_store_error(self):
        scopes._global_store().create("total", "A skill whose only target fails.")

        with mock.patch.object(
            scopes.shutil, "copytree", side_effect=self._fail_for_stage("codex")
        ):
            with self.assertRaises(StoreError) as ctx:
                scopes.sync_skill("total", "global", ["codex"])

        self.assertNotIsInstance(ctx.exception, OSError)
        self.assertIn("copy failed", str(ctx.exception))

    def test_the_rest_sync_route_never_answers_500_for_a_target_failure(self):
        from skillsmgr import webapp

        store = self._store()
        store.create("rest-sync", "A skill synced over REST.")
        self._read_only("gemini")
        server = webapp.WebAppServer(store, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)

        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        conn.request(
            "POST",
            "/api/sync",
            body=json.dumps({"name": "rest-sync", "from_scope": "global", "to_scopes": ["gemini"]}),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        status = response.status
        payload = json.loads(response.read())
        conn.close()

        self.assertNotEqual(status, 500)
        self.assertEqual(status, 200)
        self.assertEqual(payload["synced"], [])
        self.assertIn("read-only", payload["skipped"][0]["reason"])


# -------------------------------------------------------------------- SEC-10


class AggregateScanCostTests(BatchSixCase):
    def _seed_scopes(self, count: int = 3) -> list[str]:
        for scope_id in ("agents", "cursor", "gemini")[:count]:
            for index in range(3):
                self._agent_skill(scope_id, f"{scope_id}-{index}")
        return [d["id"] for d in scopes.list_scopes() if d["id"] != "global"]

    def test_a_merged_list_scans_each_scope_once(self):
        expected_scopes = self._seed_scopes()
        self.assertTrue(expected_scopes)
        calls: list[str] = []
        real = scopes.scan_dir

        def counting(root, *args, **kwargs):
            calls.append(str(root))
            return real(root, *args, **kwargs)

        with mock.patch.object(scopes, "scan_dir", counting):
            scopes.list_all()

        self.assertEqual(
            len(calls),
            len(expected_scopes),
            f"each scope must be scanned once per request, saw {calls}",
        )

    def test_the_merged_list_still_reports_every_scope_and_path(self):
        self._seed_scopes()
        scopes._global_store().create("global-skill", "A global skill.")

        rows = scopes.list_all()

        by_key = {(r["scope"], r["name"]) for r in rows}
        self.assertIn(("global", "global-skill"), by_key)
        self.assertIn(("agents", "agents-0"), by_key)
        self.assertIn(("cursor", "cursor-1"), by_key)
        for row in rows:
            self.assertTrue(row.get("path"), f"missing path on {row}")
            self.assertTrue(row.get("scope_label"), f"missing label on {row}")

    def test_a_scan_resolves_the_root_once_instead_of_once_per_skill(self):
        scope_dir = self.home / ".agents" / "skills"
        for index in range(6):
            self._agent_skill("agents", f"resolve-{index}")
        calls: list[str] = []
        real = paths_module.contained_entry

        def counting(root, *args, **kwargs):
            calls.append(str(root))
            return real(root, *args, **kwargs)

        with mock.patch.object(paths_module, "contained_entry", counting):
            rows = loader.scan_dir(scope_dir, recursive=True)

        self.assertEqual(len(rows), 6)
        self.assertEqual(
            calls,
            [],
            "the per-entry containment check must reuse the root resolved once per scan",
        )


# -------------------------------------------------------------------- SEC-11


class MultipartFidelityTests(unittest.TestCase):
    BOUNDARY = "batch6boundary"

    @classmethod
    def _body(cls, parts, *, close: bool = True) -> bytes:
        body = b""
        for name, content in parts:
            body += (
                f"--{cls.BOUNDARY}\r\n"
                f'Content-Disposition: form-data; name="files"; filename="{name}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode("utf-8") + content + b"\r\n"
        if close:
            body += f"--{cls.BOUNDARY}--\r\n".encode("utf-8")
        return body

    def _parse(self, raw: bytes):
        from skillsmgr.webapp import _parse_multipart

        return _parse_multipart(raw, self.BOUNDARY)

    def test_uploaded_content_keeps_its_trailing_newlines(self):
        # The damaging half of SEC-11: an unconditional rstrip meant every Web UI
        # folder upload stored a document that differed from the user's file.
        original = b"---\nname: x\ndescription: d\n---\nline1\n\n\n"
        parts = self._parse(self._body([("x/SKILL.md", original)]))

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["content"], original)

    def test_a_delimiter_lookalike_inside_content_does_not_split_the_part(self):
        original = f"before--{self.BOUNDARY}-after".encode("utf-8")
        parts = self._parse(self._body([("x/SKILL.md", original)]))

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["content"], original)

    def test_a_boundary_prefix_on_a_new_line_is_still_file_content(self):
        original = f"before\r\n--{self.BOUNDARY}-not-a-delimiter\r\nafter".encode("utf-8")
        parts = self._parse(self._body([("x/SKILL.md", original)]))

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["content"], original)

    def test_a_crlf_terminated_delimiter_lookalike_still_follows_the_rfc(self):
        # A delimiter is CRLF + "--" + boundary, so the well-formed framing is
        # still honoured; the sender is responsible for encoding such content.
        parts = self._parse(self._body([("x/SKILL.md", b"one"), ("y/SKILL.md", b"two")]))

        self.assertEqual([part["filename"] for part in parts], ["x/SKILL.md", "y/SKILL.md"])
        self.assertEqual([part["content"] for part in parts], [b"one", b"two"])

    def test_an_rfc2231_encoded_filename_is_decoded(self):
        # Browsers switch to RFC 5987/2231 when a filename needs it (non-ASCII,
        # quotes).  The previous regex matched either nothing or a truncated
        # prefix of the raw parameter.
        raw = (
            f"--{self.BOUNDARY}\r\n".encode()
            + b"Content-Disposition: form-data; name=\"files\"; "
            + b"filename*=UTF-8''caf%C3%A9%22x/SKILL.md\r\n\r\n"
            + b"body\r\n"
            + f"--{self.BOUNDARY}--\r\n".encode()
        )
        parts = self._parse(raw)

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["filename"], 'café"x/SKILL.md')

    def test_a_part_without_a_closing_delimiter_is_still_read(self):
        parts = self._parse(self._body([("x/SKILL.md", b"body")], close=False))

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["content"], b"body")

    def test_the_pinned_legacy_shape_is_unchanged(self):
        # tests/test_compatibility.py pins this exact call; keep it working.
        from skillsmgr.webapp import _parse_multipart

        raw = (
            b"--compat-boundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="demo/SKILL.md"\r\n'
            b"\r\n"
            b"body\r\n"
            b"--compat-boundary--\r\n"
        )
        self.assertEqual(
            _parse_multipart(raw, "compat-boundary"),
            [{"name": "file", "filename": "demo/SKILL.md", "content": b"body"}],
        )


if __name__ == "__main__":
    unittest.main()
