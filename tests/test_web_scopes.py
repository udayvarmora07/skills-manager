"""Scope tests for skills-manager. Stdlib unittest only (no third-party deps).

Hermetic: HOME and $SKILLS_MANAGER_DATA are redirected to a tmp dir per
test, so agent-scope writes land in tmp (e.g. tmp/.agents/skills) and the
global store uses an isolated data dir. The injected global store is reset
after every test.

Run:  python3 -m unittest tests.test_web_scopes -v
"""

import os
import tempfile
import unittest
from pathlib import Path

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

    def test_search_all_finds_both_scopes(self):
        scopes._global_store().create("gskill", "Global unique-term skill")
        scopes.create_skill("agents", "askill", "Agent unique-term skill")
        hits = scopes.search_all("unique-term", scope_id="all")
        self.assertEqual(
            {(h["scope"], h["name"]) for h in hits},
            {("global", "gskill"), ("agents", "askill")},
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


if __name__ == "__main__":
    unittest.main()
