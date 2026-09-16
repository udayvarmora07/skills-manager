"""Scope tests for skills-manager. Stdlib unittest only (no third-party deps).

Hermetic: HOME and $SKILLS_MANAGER_DATA are redirected to a tmp dir per
test, so agent-scope writes land in tmp (e.g. tmp/.agents/skills) and the
global store uses an isolated data dir. The injected global store is reset
after every test.

Run:  python3 -m unittest tests.test_web_scopes -v
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import scopes
from skillsmgr.store import StoreError


class ScopedHomeTestCase(unittest.TestCase):
    """Base: fresh HOME + SKILLS_MANAGER_DATA per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old_home = os.environ.get("HOME")
        self._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["HOME"] = self._tmp.name
        os.environ["SKILLS_MANAGER_DATA"] = str(
            Path(self._tmp.name) / "data"
        )
        scopes.set_global_store(scopes.Store())
        scopes._global_store().init_db()

    def tearDown(self):
        scopes.set_global_store(None)
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        if self._old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = self._old_data


class TestTwoServersDoNotCrossTalk(ScopedHomeTestCase):
    """SCOPE-10: one process, two servers, two data dirs -- no shared state."""

    def _server(self, data_name: str, skill_name: str, description: str):
        import threading

        from skillsmgr.webapp import WebAppServer

        store = scopes.Store(data_dir=Path(self._tmp.name) / data_name)
        store.init_db()
        store.create(skill_name, description)
        server = WebAppServer(store, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return server, store

    @staticmethod
    def _names(server, path: str) -> list[str]:
        import json
        import urllib.request

        url = f"http://127.0.0.1:{server.port}{path}"
        with urllib.request.urlopen(url, timeout=10) as response:
            return sorted(row["name"] for row in json.loads(response.read()))

    def test_each_server_answers_from_its_own_store(self):
        # As a module global the last set_global_store won, so server A's
        # ?scope=all answered with server B's skill while its ?scope=global
        # answered with its own.
        server_a, _store_a = self._server("data-a", "a-only", "in data-a")
        server_b, _store_b = self._server("data-b", "b-only", "in data-b")

        self.assertEqual(self._names(server_a, "/api/skills?scope=global"), ["a-only"])
        self.assertEqual(self._names(server_b, "/api/skills?scope=global"), ["b-only"])
        # The All view goes through the injected global store; it must agree
        # with the same server's Global view.
        self.assertEqual(self._names(server_a, "/api/skills?scope=all"), ["a-only"])
        self.assertEqual(self._names(server_b, "/api/skills?scope=all"), ["b-only"])

    def test_agent_scope_snapshots_stay_in_the_requesting_servers_data_dir(self):
        server_a, store_a = self._server("data-a", "a-only", "in data-a")
        _server_b, store_b = self._server("data-b", "b-only", "in data-b")
        scopes.create_skill("agents", "cursorless", "Agent-scope skill")

        # Server A edits an agent-scope skill, which writes a snapshot through
        # the injected store; it must land in A's data dir, not B's.
        import json
        import urllib.request

        request = urllib.request.Request(
            f"http://127.0.0.1:{server_a.port}/api/skills/cursorless?scope=agents",
            data=json.dumps({"description": "Edited via server A"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            self.assertEqual(response.status, 200)

        self.assertEqual(
            len(list((store_a.data_dir / "snapshots").rglob("*.md"))),
            1,
            "snapshot did not land in A's data dir",
        )
        self.assertEqual(
            list((store_b.data_dir / "snapshots").rglob("*.md")),
            [],
            "server A wrote into server B's data dir",
        )


class TestListScopes(ScopedHomeTestCase):
    def test_all_eight_tier1_ids_known(self):
        ids = {s.id for s in scopes.known_scopes()}
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

    def test_global_scope_counts_new_skill(self):
        scopes._global_store().create("gdemo", "Global demo skill")
        descs = {d["id"]: d for d in scopes.list_scopes()}
        self.assertTrue(descs["global"]["exists"])
        self.assertEqual(descs["global"]["count"], 1)

    def test_missing_agent_scopes_hidden_by_default(self):
        ids = {d["id"] for d in scopes.list_scopes()}
        self.assertIn("global", ids)
        self.assertNotIn("agents", ids)

    def test_cursor_uses_current_agent_skills_root(self):
        cursor = next(scope for scope in scopes.known_scopes() if scope.id == "cursor")
        self.assertEqual(cursor.base, Path(self._tmp.name) / ".cursor" / "skills")

    def test_aliased_physical_roots_are_counted_once(self):
        agents_root = Path(self._tmp.name) / ".agents" / "skills"
        agents_root.mkdir(parents=True)
        cursor_root = Path(self._tmp.name) / ".cursor" / "skills"
        cursor_root.parent.mkdir(parents=True)
        cursor_root.symlink_to(agents_root, target_is_directory=True)
        descriptors = scopes.list_scopes(include_missing=True)
        physical = [Path(item["path"]).resolve() for item in descriptors]
        self.assertEqual(len(physical), len(set(physical)))

    def test_sync_skips_duplicate_physical_target_root(self):
        scopes._global_store().create("shared", "Shared skill")
        agents_root = Path(self._tmp.name) / ".agents" / "skills"
        agents_root.mkdir(parents=True)
        cursor_root = Path(self._tmp.name) / ".cursor" / "skills"
        cursor_root.parent.mkdir(parents=True)
        cursor_root.symlink_to(agents_root, target_is_directory=True)

        result = scopes.sync_skill("shared", "global", ["agents", "cursor"])

        self.assertEqual(result["synced"], ["agents"])
        self.assertEqual(result["skipped"], [{"scope": "cursor", "reason": "same physical root as another target"}])

    def test_recursive_consumer_scope_discovers_nested_skill(self):
        nested = Path(self._tmp.name) / ".cursor" / "skills" / "nested" / "demo"
        nested.mkdir(parents=True)
        (nested / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Nested demo\n---\nbody\n",
            encoding="utf-8",
        )

        rows = scopes.scan_scope("cursor")

        self.assertEqual([row["name"] for row in rows], ["demo"])
        self.assertTrue(rows[0]["discovery_recursive"])
        self.assertEqual(rows[0]["root_availability"], "writable")
        self.assertEqual(scopes.get_skill("cursor", "demo")["description"], "Nested demo")

    def test_missing_and_read_only_root_states_are_distinct(self):
        missing = scopes.Scope("missing-test", "Missing", Path(self._tmp.name) / "missing", "agent", True)
        readonly = scopes.Scope("readonly-test", "Readonly", Path(self._tmp.name) / "readonly", "agent", False)
        readonly.base.mkdir()
        with mock.patch("skillsmgr.scopes.known_scopes", return_value=[missing, readonly]):
            descriptors = {item["id"]: item for item in scopes.list_scopes(include_missing=True)}
        self.assertEqual(descriptors["missing-test"]["availability"], "missing")
        self.assertEqual(descriptors["readonly-test"]["availability"], "read-only")


class TestSymlinkPolicy(ScopedHomeTestCase):
    """SCOPE-1/2/3: one policy for symlinks -- reads and writes must agree."""

    def _skill(self, root: Path, name: str, description: str = "A skill") -> Path:
        target = root / name
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description} for tests.\n---\nbody\n",
            encoding="utf-8",
        )
        return target

    def test_sync_refuses_a_link_that_points_outside_the_skill(self):
        # SCOPE-1: copytree followed links, so an 88-byte skill produced 65 KB
        # of files that lived outside it, materialized into another agent scope.
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("SECRET-TOKEN-1234\n", encoding="utf-8")
        root = Path(self._tmp.name) / ".agents" / "skills"
        src = self._skill(root, "shared")
        (src / "big.bin").symlink_to(outside / "secret.txt")

        with self.assertRaises(StoreError) as ctx:
            scopes.sync_skill("shared", "agents", ["gemini"])

        self.assertIn("symlinks that point outside it", str(ctx.exception))
        dest = Path(self._tmp.name) / ".gemini" / "skills" / "shared"
        self.assertFalse(dest.exists())
        self.assertFalse((dest / "big.bin").exists())

    def test_sync_copies_an_in_root_link_as_a_link(self):
        root = Path(self._tmp.name) / ".agents" / "skills"
        src = self._skill(root, "linked")
        (src / "notes.md").write_text("notes\n", encoding="utf-8")
        (src / "alias.md").symlink_to(src / "notes.md")

        result = scopes.sync_skill("linked", "agents", ["gemini"])

        self.assertEqual(result["synced"], ["gemini"])
        copied = Path(self._tmp.name) / ".gemini" / "skills" / "linked" / "alias.md"
        self.assertTrue(copied.is_symlink())

    def test_escaping_link_is_visible_as_drift_instead_of_hidden(self):
        # SCOPE-2: the escape was invisible to every read view while blocking
        # every write, exactly the shape `skills-mgr install` produces.
        outside = Path(self._tmp.name) / "npm-cache"
        self._skill(outside, "myskill", "Installed elsewhere")
        root = Path(self._tmp.name) / ".claude" / "skills"
        root.mkdir(parents=True)
        (root / "myskill").symlink_to(outside / "myskill", target_is_directory=True)

        rows = scopes.scan_scope("claude-code")

        self.assertEqual([row["name"] for row in rows], ["myskill"])
        self.assertTrue(rows[0]["malformed"])
        self.assertIn("escapes managed root", rows[0]["decode_error"])
        self.assertIn("myskill", {row["name"] for row in scopes.list_all()})

    def test_in_root_alias_addresses_the_named_entry(self):
        # SCOPE-3: get_skill('alias') reported 'real', a write through the alias
        # mutated 'real', and remove('alias') deleted 'real' and left a
        # dangling link while the physical skill was listed twice.
        root = Path(self._tmp.name) / ".claude" / "skills"
        real = self._skill(root, "real", "The real skill")
        (root / "alias").symlink_to(real, target_is_directory=True)

        rows = scopes.scan_scope("claude-code")
        self.assertEqual(sorted(row["name"] for row in rows), ["alias", "real"])
        self.assertEqual(scopes.get_skill("claude-code", "alias")["name"], "alias")
        self.assertEqual(
            Path(scopes.get_skill("claude-code", "alias")["path"]).name, "alias"
        )

        # Removing the alias must move the *link*, never the real directory:
        # the old code resolved the alias to its target and trashed that,
        # leaving a dangling link and destroying the skill.
        scopes.remove_skill("claude-code", "alias")

        self.assertTrue(real.is_dir())
        self.assertTrue((real / "SKILL.md").is_file())
        self.assertFalse((root / "alias").exists())
        self.assertEqual(
            [row["name"] for row in scopes.scan_scope("claude-code")], ["real"]
        )


class TestAgentScopeCrud(ScopedHomeTestCase):
    def test_create_scan_get(self):
        scopes.create_skill("agents", "ademo", "Agent demo skill")
        rows = scopes.scan_scope("agents")
        self.assertEqual([r["name"] for r in rows], ["ademo"])
        self.assertEqual(rows[0]["scope"], "agents")
        rec = scopes.get_skill("agents", "ademo")
        self.assertEqual(rec["description"], "Agent demo skill")
        self.assertIn("ademo", rec.get("body", "") or "")

    def test_edit_partial(self):
        scopes.create_skill("agents", "ademo", "Agent demo skill")
        out = scopes.edit_skill("agents", "ademo", description="New desc")
        self.assertTrue(out["changed"])
        self.assertEqual(
            scopes.get_skill("agents", "ademo")["description"], "New desc"
        )

    def test_toggle_refuses_a_mixed_document_state(self):
        # SCOPE-13: the scope-side twin of STORE-3.  With both SKILL.md and
        # SKILL.md.disabled present, the rename landed on top of the other
        # document and destroyed it with no snapshot.  The scope adapter must
        # refuse instead of guessing which document the user meant.
        scopes.create_skill("agents", "mixed", "Agent mixed skill")
        base = Path(self._tmp.name) / ".agents" / "skills" / "mixed"
        (base / "SKILL.md.disabled").write_text(
            "---\nname: mixed\ndescription: The disabled copy.\n---\nDISABLED\n",
            encoding="utf-8",
        )

        for enable in (True, False):
            with self.subTest(enable=enable):
                with self.assertRaises(StoreError) as ctx:
                    scopes.toggle_skill("agents", "mixed", enable=enable)
                self.assertIn("both SKILL.md and SKILL.md.disabled", str(ctx.exception))
                self.assertTrue((base / "SKILL.md").is_file())
                self.assertTrue((base / "SKILL.md.disabled").is_file())

    def test_toggle_disable_enable(self):
        scopes.create_skill("agents", "ademo", "Agent demo skill")
        scopes.toggle_skill("agents", "ademo", enable=False)
        rows = scopes.scan_scope("agents")
        self.assertEqual(rows[0]["status"], "disabled")
        base = Path(self._tmp.name) / ".agents" / "skills" / "ademo"
        self.assertTrue((base / "SKILL.md.disabled").is_file())
        scopes.toggle_skill("agents", "ademo", enable=True)
        rows = scopes.scan_scope("agents")
        self.assertEqual(rows[0]["status"], "active")

    def test_remove_purge(self):
        scopes.create_skill("agents", "ademo", "Agent demo skill")
        scopes.remove_skill("agents", "ademo", purge=True)
        self.assertEqual(scopes.scan_scope("agents"), [])

    def test_remove_trash_goes_to_sibling_trash(self):
        scopes.create_skill("agents", "ademo", "Agent demo skill")
        scopes.remove_skill("agents", "ademo")
        self.assertEqual(scopes.scan_scope("agents"), [])
        trash = Path(self._tmp.name) / ".agents" / "trash"
        self.assertTrue(trash.is_dir())
        self.assertEqual(len(list(trash.iterdir())), 1)

    def test_unknown_scope_raises(self):
        with self.assertRaises(StoreError):
            scopes.scan_scope("nope")
        with self.assertRaises(StoreError):
            scopes.create_skill("nope", "x", "X skill")


class TestSyncAndSearch(ScopedHomeTestCase):
    def test_sync_global_to_agents(self):
        scopes._global_store().create("shared", "Shared skill")
        out = scopes.sync_skill("shared", "global", ["agents"])
        self.assertEqual(out["synced"], ["agents"])
        self.assertEqual(
            scopes.get_skill("agents", "shared")["description"], "Shared skill"
        )
        # Second sync without force skips.
        out2 = scopes.sync_skill("shared", "global", ["agents"])
        self.assertEqual(out2["synced"], [])
        self.assertEqual(out2["skipped"][0]["scope"], "agents")

    def test_sync_force_creates_snapshot_and_agent_snapshot_restores(self):
        scopes._global_store().create("shared", "Global version", body="global")
        scopes.create_skill("agents", "shared", "Agent version", body="agent")
        out = scopes.sync_skill("shared", "global", ["agents"], force=True)
        self.assertEqual(out["synced"], ["agents"])
        snapshots = scopes.list_snapshots_for("agents", "shared")
        self.assertEqual(len(snapshots), 1)
        result = scopes.restore_snapshot("agents", "shared", snapshots[0])
        self.assertEqual(result["scope"], "agents")
        self.assertEqual(scopes.get_skill("agents", "shared")["description"], "Agent version")

    def test_sync_force_failure_preserves_existing_destination(self):
        scopes._global_store().create("shared", "Global version", body="global")
        scopes.create_skill("agents", "shared", "Agent version", body="agent")
        with mock.patch("skillsmgr.scopes.shutil.copytree", side_effect=OSError("copy failed")):
            with self.assertRaises(StoreError):
                scopes.sync_skill("shared", "global", ["agents"], force=True)
        self.assertEqual(scopes.get_skill("agents", "shared")["description"], "Agent version")

    def test_search_all_finds_both_scopes(self):
        scopes._global_store().create("gskill", "Global unique-term skill")
        scopes.create_skill("agents", "askill", "Agent unique-term skill")
        hits = scopes.search_all("unique-term", scope_id="all")
        self.assertEqual(
            {(h["scope"], h["name"]) for h in hits},
            {("global", "gskill"), ("agents", "askill")},
        )

    def test_search_all_uses_wildcards_consistently(self):
        scopes._global_store().create("deploy-global", "Global deployment skill")
        scopes.create_skill("agents", "deploy-agent", "Agent deployment skill")
        hits = scopes.search_all("deploy-*", scope_id="all")
        self.assertEqual(
            {(h["scope"], h["name"]) for h in hits},
            {("global", "deploy-global"), ("agents", "deploy-agent")},
        )

    def test_search_query_cap(self):
        with self.assertRaises(StoreError):
            scopes.search_all("x" * 201, scope_id="all")

    def test_list_all_merges(self):
        scopes._global_store().create("gskill", "Global skill")
        scopes.create_skill("agents", "askill", "Agent skill")
        merged = scopes.list_all()
        self.assertEqual(
            {(r["scope"], r["name"]) for r in merged},
            {("global", "gskill"), ("agents", "askill")},
        )


class TestFindDuplicates(ScopedHomeTestCase):
    def test_no_duplicates_empty(self):
        scopes._global_store().create("solo", "Solo skill")
        self.assertEqual(scopes.find_duplicates(), [])

    def test_same_name_global_and_agent(self):
        scopes._global_store().create("shared", "Shared skill")
        scopes.create_skill("agents", "shared", "Shared skill")
        dupes = scopes.find_duplicates()
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0]["name"], "shared")
        self.assertEqual(dupes[0]["scopes"], ["agents", "global"])
        self.assertFalse(dupes[0]["descriptions_differ"])

    def test_descriptions_differ_flag(self):
        scopes._global_store().create("shared", "Global wording")
        scopes.create_skill("agents", "shared", "Agent wording")
        dupes = scopes.find_duplicates()
        self.assertEqual(len(dupes), 1)
        self.assertTrue(dupes[0]["descriptions_differ"])
        self.assertIn("divergent", dupes[0]["records"][0]["instance_states"])
        self.assertEqual(dupes[0]["records"][0]["effective_state"], "unresolved")

    def test_disabled_and_malformed_instances_are_classified(self):
        scopes.create_skill("agents", "disabled-one", "Disabled")
        scopes.toggle_skill("agents", "disabled-one", enable=False)
        malformed = Path(self._tmp.name) / ".agents" / "skills" / "broken"
        malformed.mkdir(parents=True)
        (malformed / "SKILL.md").write_text("---\nname: [broken\n---\nbody\n", encoding="utf-8")

        rows = {row["name"]: row for row in scopes.scan_scope("agents")}

        self.assertIn("disabled", rows["disabled-one"]["instance_states"])
        self.assertIn("invalid", rows["broken"]["instance_states"])

    def test_single_scope_same_name_dir_not_duplicate(self):
        # Same store listed twice is impossible; a dir existing in only one
        # scope must not report.
        scopes.create_skill("agents", "lone", "Lone skill")
        self.assertEqual(scopes.find_duplicates(), [])

    def test_sync_into_global_reactivates_stale_trashed_row(self):
        # OPEN-3 regression: syncing agents -> global writes the directory
        # directly; a 'trashed' row left by an earlier global remove must be
        # reactivated so list/doctor/duplicates stay consistent.
        store = scopes._global_store()
        store.create("syncme", "Global old", body="global")
        store.remove("syncme")  # row -> trashed, dir -> trash
        scopes.create_skill("agents", "syncme", "Agent new", body="agent")
        out = scopes.sync_skill("syncme", "agents", ["global"])
        self.assertEqual(out["synced"], ["global"])
        # row reactivated by the post-sync resync
        import sqlite3 as _sqlite3

        row = _sqlite3.connect(store.db_path).execute(
            "SELECT status FROM skills WHERE name = 'syncme'"
        ).fetchone()
        self.assertEqual(row[0], "active")
        self.assertIn("syncme", [r["name"] for r in store.list()])
        dupes = {d["name"] for d in scopes.find_duplicates()}
        self.assertIn("syncme", dupes)
        self.assertTrue(store.doctor()["ok"])


if __name__ == "__main__":
    unittest.main()
