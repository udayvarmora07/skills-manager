"""Red-first regression tests for the deep-audit batch 4 (low/info) findings.

Covers STORE-14, BUG-8..BUG-15 and SCOPE-14..SCOPE-18.  Stdlib only; every test
drives the real seam the audit described (a live server, a real scope root, a
real archive) rather than asserting on internals.
"""

from __future__ import annotations

import http.client
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


class BatchFourCase(unittest.TestCase):
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
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, old in self._old.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


# --------------------------------------------------------------- BUG-10 / SCOPE-14


class UnaddressableNamesTests(BatchFourCase):
    def _scope_skill(self, name: str, description: str = "A skill for tests.") -> Path:
        target = self.home / ".agents" / "skills" / name
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(
            f"---\nname: {name if name.islower() else 'x'}\ndescription: {description}\n---\nbody\n",
            encoding="utf-8",
        )
        return target

    def test_a_dot_directory_is_listed_but_marked_unaddressable(self):
        # BUG-10/SCOPE-14: a dot-directory was offered as an ordinary row and
        # then errored on click, because no name-addressed operation accepts it.
        self._scope_skill("good", "A perfectly good skill.")
        self._scope_skill(".hidden-skill", "A hidden directory skill.")

        from skillsmgr import scopes

        rows = {row["name"]: row for row in scopes.scan_scope("agents")}

        self.assertIn(".hidden-skill", rows, "the filesystem entry must stay visible")
        self.assertFalse(rows[".hidden-skill"]["addressable"])
        self.assertIn("unaddressable", rows[".hidden-skill"]["instance_states"])
        self.assertTrue(rows["good"]["addressable"])
        self.assertNotIn("unaddressable", rows["good"]["instance_states"])

    def test_a_non_canonical_name_is_marked_unaddressable(self):
        self._scope_skill("Upper-Case", "An upper-case directory name.")

        from skillsmgr import scopes

        row = next(r for r in scopes.scan_scope("agents") if r["name"] == "Upper-Case")
        self.assertFalse(row["addressable"])
        self.assertIn("unaddressable", row["instance_states"])

    def test_an_undecodable_document_reports_no_mojibake_description(self):
        # BUG-10: the row is correctly flagged malformed, but its description
        # was still populated with replacement characters and shown/counted.
        target = self.home / ".agents" / "skills" / "badenc"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_bytes(
            b"---\nname: badenc\ndescription: \xff\xff bad\n---\nbody\n"
        )

        from skillsmgr import scopes

        row = next(r for r in scopes.scan_scope("agents") if r["name"] == "badenc")
        self.assertTrue(row["malformed"])
        self.assertIn("not valid UTF-8", row["decode_error"])
        self.assertEqual(row["description"], "")
        self.assertNotIn("\ufffd", row["description"])

    def test_the_body_stays_readable_for_an_undecodable_document(self):
        # The existing issue-#13 contract: only the description is suppressed.
        target = self.home / ".agents" / "skills" / "badenc"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_bytes(b"---\nname: badenc\n---\n\xffbody\n")

        from skillsmgr import scopes

        row = next(r for r in scopes.scan_scope("agents") if r["name"] == "badenc")
        self.assertIn("\ufffd", row["body"])


# ------------------------------------------------------------------- SCOPE-15


class RogueIndexRowTests(BatchFourCase):
    def _store_with_rogue_row(self):
        from skillsmgr.store import Store

        store = Store()
        store.init_db()
        target = store.skills_dir / "Bad_Name"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(
            "---\nname: Bad_Name\ndescription: A rogue row skill.\n---\nbody\n",
            encoding="utf-8",
        )
        store.create("fine", "A perfectly fine skill.")
        conn = sqlite3.connect(store.db_path)
        conn.execute(
            "INSERT INTO skills (name, status, description, body, category, disabled) "
            "VALUES ('Bad_Name', 'active', 'rogue', 'body', 'uncategorized', 0)"
        )
        conn.commit()
        conn.close()
        return store

    def test_one_rogue_row_no_longer_kills_every_global_aggregate(self):
        # SCOPE-15: the rogue row made scan_scope('global'), list_all() and
        # search_all() all raise while list_scopes() still rendered.
        from skillsmgr import scopes

        store = self._store_with_rogue_row()
        scopes.set_global_store(store)
        self.addCleanup(scopes.set_global_store, None)

        for label, call in (
            ("list()", store.list),
            ("scan_scope('global')", lambda: scopes.scan_scope("global")),
            ("list_all()", scopes.list_all),
            ("find_duplicates()", scopes.find_duplicates),
            ("list_scopes()", scopes.list_scopes),
        ):
            with self.subTest(label=label):
                call()

    def test_the_rogue_row_is_reported_as_unaddressable_residue(self):
        from skillsmgr import scopes

        store = self._store_with_rogue_row()
        scopes.set_global_store(store)
        self.addCleanup(scopes.set_global_store, None)

        rows = {row["name"]: row for row in scopes.scan_scope("global")}
        self.assertIn("Bad_Name", rows)
        self.assertFalse(rows["Bad_Name"]["addressable"])
        self.assertTrue(rows["Bad_Name"]["malformed"])
        self.assertIsNone(rows["Bad_Name"]["path"])
        self.assertIn("fine", rows)


# ------------------------------------------------------------------- SCOPE-16


class BudgetEnforcementTests(BatchFourCase):
    def test_the_both_load_scan_respects_max_instances(self):
        # SCOPE-16: the budget was enforced only in _build_tier, so a large
        # monorepo produced more instances than MAX_INSTANCES with no warning.
        from skillsmgr import effective

        project = self.base / "mono"
        for i in range(effective.MAX_ROOTS):
            for j in range(20):
                target = project / f"apps/a{i:02d}" / ".claude" / "skills" / f"s{i:02d}x{j:02d}"
                target.mkdir(parents=True)
                (target / "SKILL.md").write_text(
                    f"---\nname: s{i:02d}x{j:02d}\ndescription: skill {i} {j} here.\n---\nb\n",
                    encoding="utf-8",
                )

        report = effective.explain("claude-code", project)

        tier_total = sum(
            len(tier["instances"]) + len(tier["skipped"]) for tier in report["tiers"]
        )
        also_total = sum(len(entry.get("also_loads") or []) for entry in report["skills"].values())
        self.assertLessEqual(tier_total + also_total, effective.MAX_INSTANCES)
        self.assertTrue(
            any("truncated" in warning for warning in report["warnings"]),
            f"no truncation warning in {report['warnings']}",
        )


# ------------------------------------------------------------------- SCOPE-17


class HomeAndRelativeRootTests(BatchFourCase):
    def test_an_empty_home_does_not_relocate_scopes_to_the_root(self):
        # SCOPE-17: HOME="" made Path.home() return "/", so every agent scope
        # became a read/write target at the filesystem root.
        from skillsmgr import paths, scopes

        self.addCleanup(os.environ.__setitem__, "HOME", str(self.home))
        os.environ["HOME"] = ""

        self.assertNotEqual(str(paths.home_dir()), "/")
        bases = [scope.base for scope in scopes.known_scopes()]
        for base in bases:
            self.assertFalse(
                str(base).startswith("/."),
                f"scope relocated to the filesystem root: {base}",
            )

    def test_a_whitespace_home_is_treated_as_unset(self):
        from skillsmgr import paths

        self.addCleanup(os.environ.__setitem__, "HOME", str(self.home))
        os.environ["HOME"] = "   "
        self.assertNotEqual(str(paths.home_dir()), "/")

    def test_a_relative_data_dir_is_anchored_to_an_absolute_path(self):
        from skillsmgr import paths

        old_cwd = Path.cwd()
        os.chdir(self.base)
        self.addCleanup(os.chdir, old_cwd)
        os.environ["SKILLS_MANAGER_DATA"] = "relative-data"
        resolved = paths.data_dir()
        self.assertTrue(resolved.is_absolute(), resolved)
        self.assertEqual(
            resolved,
            self.base / "relative-data" / "skills-manager",
        )


# ------------------------------------------------------------------- SCOPE-18


class FlatPathShortCircuitTests(BatchFourCase):
    def test_a_grouping_directory_sharing_the_skill_name_does_not_hide_it(self):
        # SCOPE-18: the flat short-circuit accepted the grouping directory, so
        # scan listed the skill while get_skill reported SkillNotFound.
        target = self.home / ".cursor" / "skills" / "deploy" / "deploy"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(
            "---\nname: deploy\ndescription: A nested deploy skill.\n---\nbody\n",
            encoding="utf-8",
        )

        from skillsmgr import scopes

        listed = scopes.scan_scope("cursor")
        self.assertEqual([row["name"] for row in listed], ["deploy"])
        record = scopes.get_skill("cursor", "deploy")
        self.assertEqual(Path(record["path"]).name, "deploy")
        self.assertEqual(Path(record["path"]).parent.name, "deploy")
        self.assertEqual(record["description"], "A nested deploy skill.")


# ------------------------------------------------------------------- BUG-11


class TemplateLockOrderTests(BatchFourCase):
    def test_the_template_directory_exists_before_the_lock_is_taken(self):
        # BUG-11: the lock was taken before mkdir, so a future file-backed lock
        # would have created its lock file in a directory that did not exist.
        from skillsmgr import atomic_io, templates

        templates_dir = self.base / "templates-never-created"
        self.assertFalse(templates_dir.exists())
        observed: list[bool] = []
        real_lock = atomic_io.mutation_lock

        def spy(path):
            observed.append(templates_dir.is_dir())
            return real_lock(path)

        with mock.patch.object(templates, "_mutation_lock", spy):
            templates.create_template(templates_dir, "demo")

        self.assertTrue(observed, "no lock was taken at all")
        self.assertTrue(all(observed), "the lock was taken before the directory existed")

    def test_create_template_still_works_and_rejects_duplicates(self):
        from skillsmgr import templates

        target = templates.create_template(self.base / "t", "demo")
        self.assertTrue(target.is_file())
        with self.assertRaises(FileExistsError):
            templates.create_template(self.base / "t", "demo")

    def test_fm21_templates_share_bounded_canonical_name_validation(self):
        # FM-21: template_path used to omit the skill-name length and reserved
        # Windows-device checks, allowing drift and eventually raw OSError.
        from skillsmgr import templates

        for name in ("a" * 65, "con", "NUL", "lpt9"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "invalid"):
                    templates.template_path(self.base / "t", name)


# ------------------------------------------------------------------- BUG-12


class BoundedLockTableTests(unittest.TestCase):
    def test_the_lock_table_stays_bounded(self):
        # BUG-12: one RLock was retained per distinct resolved path, forever.
        from skillsmgr import atomic_io

        for index in range(atomic_io.MAX_MUTATION_LOCKS * 4):
            atomic_io.mutation_lock(Path(f"/tmp/bug12-probe-{index}/SKILL.md"))

        self.assertLessEqual(len(atomic_io._MUTATION_LOCKS), atomic_io.MAX_MUTATION_LOCKS)

    def test_the_same_path_still_yields_the_same_lock(self):
        from skillsmgr import atomic_io

        first = atomic_io.mutation_lock(Path("/tmp/bug12-same/SKILL.md"))
        second = atomic_io.mutation_lock(Path("/tmp/bug12-same/SKILL.md"))
        self.assertIs(first, second)

    def test_a_held_lock_is_never_evicted(self):
        # Eviction must not break mutual exclusion for a lock in use.
        from skillsmgr import atomic_io

        held = atomic_io.mutation_lock(Path("/tmp/bug12-held/SKILL.md"))
        held.acquire()
        self.addCleanup(held.release)
        for index in range(atomic_io.MAX_MUTATION_LOCKS * 3):
            atomic_io.mutation_lock(Path(f"/tmp/bug12-churn-{index}/SKILL.md"))
        self.assertIs(
            atomic_io.mutation_lock(Path("/tmp/bug12-held/SKILL.md")),
            held,
            "a held lock was evicted, which would break exclusion",
        )


# --------------------------------------------------------- BUG-8 / BUG-9 (HTTP)


class WebAppHardeningTests(BatchFourCase):
    @classmethod
    def _serve(cls, store):
        from skillsmgr import webapp

        server = webapp.WebAppServer(store, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def _store(self):
        from skillsmgr.store import Store

        store = Store()
        store.init_db()
        store.create("demo", "A demo skill for HTTP tests.")
        return store

    def _request(self, port, method, path):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request(method, path)
        response = conn.getresponse()
        body = response.read()
        headers = {key.lower(): value for key, value in response.getheaders()}
        conn.close()
        return response.status, body, headers

    def test_head_mirrors_get_without_a_body(self):
        # BUG-9: HEAD was answered by the stdlib with a header-less HTML 501.
        store = self._store()
        server, thread = self._serve(store)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)

        status, body, headers = self._request(server.port, "HEAD", "/api/skills")

        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertIn("content-security-policy", headers)
        self.assertIn("x-content-type-options", headers)

    def test_options_and_trace_carry_the_security_headers(self):
        store = self._store()
        server, thread = self._serve(store)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)

        for method in ("OPTIONS", "TRACE"):
            with self.subTest(method=method):
                status, body, headers = self._request(server.port, method, "/api/skills")
                self.assertEqual(status, 405)
                self.assertIn("content-security-policy", headers)
                self.assertIn("allow", headers)
                self.assertEqual(json.loads(body)["error"], "method not allowed")

    def test_unknown_api_paths_stay_json_routing_errors(self):
        store = self._store()
        server, thread = self._serve(store)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)

        for path in ("/api", "/api/nope", "/api/skills/demo/extra"):
            with self.subTest(path=path):
                status, body, headers = self._request(server.port, "GET", path)
                self.assertEqual(status, 404)
                self.assertEqual(json.loads(body)["error"], "unknown endpoint")
                self.assertIn("content-security-policy", headers)

    def test_a_failed_scope_enrichment_is_reported_not_hidden(self):
        # BUG-8: the swallow returned a 200 payload without scopes/duplicates
        # while reporting success, so a client could not tell "no duplicates"
        # from "the scan crashed".
        store = self._store()
        server, thread = self._serve(store)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)

        with mock.patch("skillsmgr.scopes.list_scopes", side_effect=RuntimeError("boom")):
            status, body, headers = self._request(server.port, "GET", "/api/doctor?scope=all")

        self.assertEqual(status, 200)
        report = json.loads(body)
        self.assertEqual(report["scopes"], [])
        self.assertEqual(report["duplicates"], [])
        self.assertTrue(report.get("degraded"), "the degradation was not reported")
        self.assertIn("scopes/duplicates", json.dumps(report["degraded"]))

    def test_a_failed_stats_enrichment_still_fills_documented_keys(self):
        # BUG-8/BUG-7: the swallow is what produced a 200 with keys missing.
        store = self._store()
        server, thread = self._serve(store)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)

        with mock.patch("skillsmgr.scopes.list_scopes", side_effect=RuntimeError("boom")):
            status, body, headers = self._request(server.port, "GET", "/api/stats?scope=all")

        self.assertEqual(status, 200)
        payload = json.loads(body)
        for key in ("scopes", "all_total", "all_tokens", "window_tokens", "largest"):
            self.assertIn(key, payload, f"{key} missing from the degraded payload")


# --------------------------------------------------------------- BUG-13 / BUG-14


class GateBlindSpotTests(unittest.TestCase):
    def test_packaging_check_flags_members_that_must_never_ship(self):
        # BUG-13: only skillsmgr/webui/ was inspected, so tests/, docs/, .env
        # or a database added to a build were never flagged.
        import check_package_data

        offenders = check_package_data.unexpected_members(
            {
                "skillsmgr/webui/index.html": b"x",
                "tests/test_store.py": b"x",
                "docs/01-architecture.md": b"x",
                ".env": b"x",
                "skills-manager.db": b"x",
                "skillsmgr/__pycache__/a.pyc": b"x",
                "pyproject.toml": b"x",
                "README.md": b"x",
            }
        )
        for name in ("tests/test_store.py", "docs/01-architecture.md", ".env",
                     "skills-manager.db", "skillsmgr/__pycache__/a.pyc"):
            self.assertIn(name, offenders)
        for allowed in ("skillsmgr/webui/index.html", "pyproject.toml", "README.md"):
            self.assertNotIn(allowed, offenders)

    def test_the_sha_pin_contract_covers_reusable_workflow_refs(self):
        # BUG-14: the pattern required owner/repo@ immediately, so a reusable
        # workflow reference escaped the pin check entirely.
        from tests.test_ci_release_contracts import _SHA_RE, _THIRD_PARTY_PIN_RE

        sha = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
        reusable = f"      - uses: owner/repo/.github/workflows/reusable.yml@{sha}"
        match = _THIRD_PARTY_PIN_RE.match(reusable)
        self.assertIsNotNone(match, "a reusable-workflow ref must be pin-checked")
        self.assertTrue(_SHA_RE.match(match.group(2)))

        moving = "      - uses: owner/repo/.github/workflows/reusable.yml@main"
        match = _THIRD_PARTY_PIN_RE.match(moving)
        self.assertIsNotNone(match)
        self.assertFalse(_SHA_RE.match(match.group(2)))

        for first_party in ("      - uses: actions/checkout@v4",
                            "      - uses: github/codeql-action/upload-sarif@v3"):
            self.assertIsNone(_THIRD_PARTY_PIN_RE.match(first_party))


# ------------------------------------------------------------------- STORE-14


class DocumentedStoreContractTests(BatchFourCase):
    def test_the_documented_contracts_match_the_implementation(self):
        # STORE-14: five documented claims contradicted the implementation.
        import inspect

        from skillsmgr.store import Store

        self.assertNotIn(
            "include_disabled",
            inspect.signature(Store.list).parameters,
            "the docs no longer promise this parameter; keep the signature honest",
        )

    def test_the_constructor_does_not_create_the_layout(self):
        from skillsmgr.store import Store

        data_dir = self.base / "ctor-only"
        Store(data_dir=data_dir)
        self.assertFalse(
            data_dir.exists(),
            "docs/04-store-api.md now says the constructor assigns paths only",
        )

    def test_create_and_edit_return_their_documented_shapes(self):
        from skillsmgr.store import Store

        store = Store()
        store.init_db()
        created = store.create("demo", "A demo skill here.")
        self.assertEqual(sorted(created), ["name", "path"])
        edited = store.edit("demo", license="MIT")
        self.assertEqual(sorted(edited), ["changed", "name"])

    def test_a_failed_recreate_keeps_the_original_history_record(self):
        # STORE-14: the rollback deleted *every* 'create' row for the name, so a
        # failed re-create of a once-removed skill erased its creation record.
        from skillsmgr.store import Store, StoreError

        store = Store()
        store.init_db()
        store.create("demo", "First creation here.")
        store.remove("demo")
        self.assertIn("create", [row["action"] for row in store.history("demo")])

        with mock.patch.object(store, "_upsert_entry", side_effect=StoreError("db failed")):
            with self.assertRaises(StoreError):
                store.create("demo", "Second creation here.")

        actions = [row["action"] for row in store.history("demo")]
        self.assertIn("create", actions, "the original creation record was erased")

    def test_a_users_own_tmp_file_is_not_a_transaction_artifact(self):
        # STORE-14: any *.tmp file turned doctor().ok into False with no
        # API-accessible fix.
        from skillsmgr.store import Store

        store = Store()
        store.init_db()
        store.create("demo", "A demo skill here.")
        (store.skills_dir / "demo" / "notes.tmp").write_text("user data", encoding="utf-8")

        report = store.doctor()
        self.assertEqual(report["temporary_files"], [])
        self.assertTrue(report["ok"])

    def test_our_own_residue_is_still_flagged(self):
        from skillsmgr.store import Store

        store = Store()
        store.init_db()
        store.create("demo", "A demo skill here.")
        (store.data_dir / ".x.skillsmgr-tmp").write_text("residue", encoding="utf-8")

        self.assertTrue(store.doctor()["temporary_files"])


if __name__ == "__main__":
    unittest.main()
