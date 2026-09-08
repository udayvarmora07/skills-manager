"""Hermetic public contract tests for global and agent scope adapters.

These tests exercise the same scope-facing operations against the manager's
(global) root and a user/agent root.  All filesystem and index state lives in
an isolated temporary HOME/data directory.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import scopes
from skillsmgr.store import SkillNotFound, StoreError


class IsolatedScopeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old_home = os.environ.get("HOME")
        self._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["HOME"] = self._tmp.name
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(self._tmp.name) / "data")
        self.store = scopes.Store()
        scopes.set_global_store(self.store)
        self.store.init_db()
        self.addCleanup(self._reset_environment)

    def _reset_environment(self):
        scopes.set_global_store(None)
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        if self._old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = self._old_data

    def _root(self, scope_id: str) -> Path:
        if scope_id == "global":
            return self.store.skills_dir
        return next(item.base for item in scopes.known_scopes() if item.id == scope_id)

    def _create(self, scope_id: str, name: str = "contract", description: str = "Contract skill"):
        return scopes.create_skill(
            scope_id,
            name,
            description,
            category="testing",
            body="Original contract body",
        )


class TestGlobalAndFlatAgentContracts(IsolatedScopeTestCase):
    """Operations shared by the global and flat ``agents`` adapters."""

    def test_list_get_create_edit_contract(self):
        for scope_id in ("global", "agents"):
            with self.subTest(scope=scope_id):
                self._create(scope_id)
                listed = scopes.scan_scope(scope_id)
                self.assertEqual([row["name"] for row in listed], ["contract"])
                self.assertEqual(listed[0]["scope"], scope_id)
                self.assertEqual(scopes.get_skill(scope_id, "contract")["description"], "Contract skill")

                changed = scopes.edit_skill(
                    scope_id,
                    "contract",
                    description="Edited contract",
                    body="Edited contract body",
                )
                self.assertTrue(changed["changed"])
                record = scopes.get_skill(scope_id, "contract")
                self.assertEqual(record["description"], "Edited contract")
                self.assertEqual(record["body"], "Edited contract body\n")

    def test_disable_enable_contract(self):
        for scope_id in ("global", "agents"):
            with self.subTest(scope=scope_id):
                self._create(scope_id)
                disabled = scopes.toggle_skill(scope_id, "contract", enable=False)
                self.assertTrue(disabled["disabled"])
                row = scopes.scan_scope(scope_id)[0]
                if scope_id == "global":
                    self.assertEqual(row["disabled"], 1)
                else:
                    self.assertEqual(row["status"], "disabled")
                    self.assertTrue(row["disabled"])
                self.assertTrue((self._root(scope_id) / "contract" / "SKILL.md.disabled").is_file())

                enabled = scopes.toggle_skill(scope_id, "contract", enable=True)
                self.assertFalse(enabled["disabled"])
                self.assertEqual(scopes.scan_scope(scope_id)[0]["status"], "active")
                self.assertTrue((self._root(scope_id) / "contract" / "SKILL.md").is_file())

    def test_remove_contract_and_global_restore_from_trash(self):
        for scope_id in ("global", "agents"):
            with self.subTest(scope=scope_id):
                self._create(scope_id)
                result = scopes.remove_skill(scope_id, "contract")
                self.assertEqual(result["action"], "trashed")
                self.assertEqual(scopes.scan_scope(scope_id), [])
                self.assertFalse((self._root(scope_id) / "contract").exists())
                self.assertTrue(Path(result["trash_path"]).is_dir())

                if scope_id == "global":
                    restored = self.store.restore("contract")
                    self.assertEqual(restored["name"], "contract")
                    self.assertEqual(scopes.get_skill(scope_id, "contract")["description"], "Contract skill")
                else:
                    # Agent roots expose snapshot restore, but intentionally no
                    # trash-restore API. Purge the already-trashed fixture.
                    self.assertTrue(Path(result["trash_path"]).is_dir())

    def test_snapshot_restore_contract(self):
        for scope_id in ("global", "agents"):
            with self.subTest(scope=scope_id):
                self._create(scope_id)
                scopes.edit_skill(scope_id, "contract", body="Changed contract body")
                snapshots = scopes.list_snapshots_for(scope_id, "contract")
                self.assertEqual(len(snapshots), 1)
                restored = scopes.restore_snapshot(scope_id, "contract", snapshots[0])
                self.assertEqual(restored["scope"], scope_id) if scope_id != "global" else self.assertEqual(restored["name"], "contract")
                self.assertEqual(scopes.get_skill(scope_id, "contract")["body"], "Original contract body\n")

    def test_purge_remove_contract(self):
        for scope_id in ("global", "agents"):
            with self.subTest(scope=scope_id):
                self._create(scope_id)
                result = scopes.remove_skill(scope_id, "contract", purge=True)
                self.assertEqual(result["action"], "purged")
                self.assertEqual(scopes.scan_scope(scope_id), [])
                self.assertFalse((self._root(scope_id) / "contract").exists())

    def test_search_contract_in_each_scope_and_aggregate(self):
        self._create("global", "global-contract", "Global needle skill")
        self._create("agents", "agent-contract", "Agent needle skill")
        for scope_id, expected in (
            ("global", {"global-contract"}),
            ("agents", {"agent-contract"}),
            ("all", {"global-contract", "agent-contract"}),
        ):
            with self.subTest(scope=scope_id):
                hits = scopes.search_all("needle", scope_id=scope_id)
                self.assertEqual({hit["name"] for hit in hits}, expected)

    def test_missing_names_and_invalid_inputs_are_consistent(self):
        for scope_id in ("global", "agents"):
            with self.subTest(scope=scope_id):
                with self.assertRaises(SkillNotFound):
                    scopes.get_skill(scope_id, "missing")
                with self.assertRaises(SkillNotFound):
                    scopes.toggle_skill(scope_id, "missing", enable=False)
                with self.assertRaises(StoreError):
                    scopes.create_skill(scope_id, "bad name", "Description")
                with self.assertRaises(StoreError):
                    scopes.search_all("x" * 201, scope_id=scope_id)


class TestScopeDiscoveryContracts(IsolatedScopeTestCase):
    def test_disabled_and_malformed_agent_instances_are_observable(self):
        self._create("agents", "disabled-one", "Disabled skill")
        scopes.toggle_skill("agents", "disabled-one", enable=False)
        malformed = Path(self._tmp.name) / ".agents" / "skills" / "broken"
        malformed.mkdir(parents=True)
        (malformed / "SKILL.md").write_text(
            "---\nname: [broken\n---\nbody\n", encoding="utf-8"
        )

        rows = {row["name"]: row for row in scopes.scan_scope("agents")}
        self.assertEqual(rows["disabled-one"]["status"], "disabled")
        self.assertIn("disabled", rows["disabled-one"]["instance_states"])
        self.assertTrue(rows["broken"]["malformed"])
        self.assertIn("invalid", rows["broken"]["instance_states"])
        self.assertTrue(scopes.get_skill("agents", "broken")["malformed"])

    def test_recursive_and_flat_discovery_are_distinct(self):
        flat_root = Path(self._tmp.name) / ".codex" / "skills"
        flat_nested = flat_root / "category" / "nested-flat"
        flat_nested.mkdir(parents=True)
        (flat_nested / "SKILL.md").write_text(
            "---\nname: nested-flat\ndescription: Flat nested\n---\nbody\n",
            encoding="utf-8",
        )
        recursive_root = Path(self._tmp.name) / ".cursor" / "skills"
        recursive_nested = recursive_root / "category" / "nested-recursive"
        recursive_nested.mkdir(parents=True)
        (recursive_nested / "SKILL.md").write_text(
            "---\nname: nested-recursive\ndescription: Recursive nested\n---\nbody\n",
            encoding="utf-8",
        )

        self.assertEqual(scopes.scan_scope("agents"), [])
        recursive_rows = scopes.scan_scope("cursor")
        self.assertEqual([row["name"] for row in recursive_rows], ["nested-recursive"])
        self.assertTrue(recursive_rows[0]["discovery_recursive"])
        self.assertEqual(scopes.get_skill("cursor", "nested-recursive")["description"], "Recursive nested")

    def test_availability_states_are_public_and_distinct(self):
        missing = scopes.Scope(
            "missing", "Missing", Path(self._tmp.name) / "missing", "agent", True
        )
        readonly_root = Path(self._tmp.name) / "readonly"
        readonly_root.mkdir()
        readonly = scopes.Scope("readonly", "Readonly", readonly_root, "agent", False)
        unsupported = scopes.Scope(
            "unsupported", "Unsupported", Path(self._tmp.name) / "unsupported", "agent", True, supported=False
        )
        with mock.patch("skillsmgr.scopes.known_scopes", return_value=[missing, readonly, unsupported]):
            descriptors = {
                item["id"]: item for item in scopes.list_scopes(include_missing=True)
            }
        self.assertEqual(descriptors["missing"]["availability"], "missing")
        self.assertEqual(descriptors["readonly"]["availability"], "read-only")
        self.assertEqual(descriptors["unsupported"]["availability"], "unsupported")

    def test_aggregate_lists_one_descriptor_for_resolved_aliases(self):
        agents_root = Path(self._tmp.name) / ".agents" / "skills"
        agents_root.mkdir(parents=True)
        (agents_root / "shared").mkdir()
        (agents_root / "shared" / "SKILL.md").write_text(
            "---\nname: shared\ndescription: Shared\n---\nbody\n", encoding="utf-8"
        )
        cursor_root = Path(self._tmp.name) / ".cursor" / "skills"
        cursor_root.parent.mkdir(parents=True)
        cursor_root.symlink_to(agents_root, target_is_directory=True)

        descriptors = scopes.list_scopes(include_missing=True)
        physical = [Path(item["path"]).resolve() for item in descriptors]
        self.assertEqual(len(physical), len(set(physical)))
        merged = scopes.list_all()
        shared = [row for row in merged if row["name"] == "shared"]
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0]["scope"], "cursor")


if __name__ == "__main__":
    unittest.main()
