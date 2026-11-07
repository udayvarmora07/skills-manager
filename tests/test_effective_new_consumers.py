"""Effective-resolution rows added from docs/34 (2026-11-07).

Pins the documented orders for the consumers whose primary source was read on
2026-11-07: the corrected ``opencode`` row plus ``cline``, ``kiro``, ``amp``,
``roo``, ``zed``, ``copilot`` and ``devin``.  Each test builds a temporary
project and a temporary HOME, puts same-name skills in two tiers, and asserts
only the winner/source those pages document -- never a guess.

The module also pins that a ``home``-relative root is confined and redacted over
the HTTP boundary exactly like the existing absolute ``path`` roots (SEC-2/SEC-3)
and that unobservable documented tiers are warned about rather than silently
dropped.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from skillsmgr import effective
from skillsmgr.frontmatter import dump_frontmatter


def document(name: str, description: str) -> str:
    return dump_frontmatter({"name": name, "description": description}) + "Body.\n"


def skill(root: Path, name: str = "deploy", description: str = "copy") -> Path:
    target = root / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(document(name, description), encoding="utf-8")
    return target


class NewConsumerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.project = self.base / "project"
        self.data = self.base / "data"
        self.home.mkdir()
        self.project.mkdir()
        self._old_home = os.environ.get("HOME")
        self._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["HOME"] = str(self.home)
        os.environ["SKILLS_MANAGER_DATA"] = str(self.data)
        self.addCleanup(self._restore_env)
        self._home_patch = mock.patch.object(Path, "home", return_value=self.home)
        self._home_patch.start()
        self.addCleanup(self._home_patch.stop)

    def _restore_env(self):
        for key, old in (("HOME", self._old_home),
                         ("SKILLS_MANAGER_DATA", self._old_data)):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def home_skill(self, rel: str, description: str = "home copy") -> Path:
        return skill(self.home / rel, description=description)

    def project_skill(self, rel: str, description: str = "project copy") -> Path:
        return skill(self.project / rel, description=description)

    def explain(self, consumer: str) -> dict:
        return effective.explain(consumer, str(self.project))

    def entry(self, report: dict, name: str = "deploy") -> dict:
        return report["skills"][name]

    def assert_winner(self, report: dict, tier: str, path: Path) -> None:
        entry = self.entry(report)
        self.assertEqual(entry["resolution"], "resolved")
        self.assertEqual(entry["winner_tier"], tier)
        self.assertEqual(entry["winner"]["path"], str(path))

    def assert_shadowed_by(self, report: dict, tier: str, path: Path) -> None:
        shadowed = self.entry(report)["shadowed"]
        matching = [item for item in shadowed if item["path"] == str(path)]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["shadowed_by"], tier)


class TestOpenCodeDocumentedOrder(NewConsumerCase):
    """docs/34 corrects the earlier 'no documented order' row."""

    def test_project_beats_user_root(self):
        project = self.project_skill(".opencode/skills", "project")
        user = self.home_skill(".config/opencode/skills", "user")
        report = self.explain("opencode")
        self.assertEqual(report["policy"], "ordered")
        self.assert_winner(report, "project", project)
        self.assert_shadowed_by(report, "project", user)

    def test_home_and_project_agents_compat_copies_are_ambiguous(self):
        self.project_skill(".agents/skills", "project agents")
        self.home_skill(".agents/skills", "home agents")
        report = self.explain("opencode")
        entry = self.entry(report)
        self.assertEqual(entry["resolution"], "ambiguous")
        self.assertIsNone(entry["winner"])
        self.assertEqual(len(entry["candidates"]), 2)

    def test_explicit_config_tier_makes_a_lower_win_provisional(self):
        project = self.project_skill(".opencode/skills")
        report = self.explain("opencode")
        self.assert_winner(report, "project", project)
        self.assertIn("config", report["unobservable_tiers"])
        self.assertIn("provisional", " ".join(report["warnings"]))
        tiers = {tier["id"]: tier for tier in report["tiers"]}
        self.assertFalse(tiers["config"]["path_known"])


class TestClineOrder(NewConsumerCase):
    def test_global_beats_project(self):
        global_copy = self.home_skill(".cline/skills", "global")
        project = self.project_skill(".cline/skills", "project")
        report = self.explain("cline")
        self.assert_winner(report, "global", global_copy)
        self.assert_shadowed_by(report, "global", project)

    def test_the_three_project_roots_tie_is_ambiguous(self):
        self.project_skill(".cline/skills", "a")
        self.project_skill(".claude/skills", "b")
        entry = self.entry(self.explain("cline"))
        self.assertEqual(entry["resolution"], "ambiguous")
        self.assertEqual(len(entry["candidates"]), 2)


class TestKiroOrder(NewConsumerCase):
    def test_workspace_beats_global(self):
        workspace = self.project_skill(".kiro/skills", "workspace")
        global_copy = self.home_skill(".kiro/skills", "global")
        report = self.explain("kiro")
        self.assert_winner(report, "workspace", workspace)
        self.assert_shadowed_by(report, "workspace", global_copy)


class TestAmpFirstMatch(NewConsumerCase):
    def test_higher_search_order_wins_regardless_of_tier(self):
        first = self.home_skill(".config/amp/skills", "amp config")
        project = self.project_skill(".agents/skills", "repo agents")
        report = self.explain("amp")
        self.assert_winner(report, "config-amp", first)
        self.assert_shadowed_by(report, "config-amp", project)

    def test_first_documented_home_root_beats_the_shared_agents_root(self):
        first = self.home_skill(".config/agents/skills", "agents config")
        shared = self.home_skill(".agents/skills", "shared")
        report = self.explain("amp")
        self.assert_winner(report, "config-agents", first)
        self.assert_shadowed_by(report, "config-agents", shared)

    def test_project_claude_loses_to_project_agents(self):
        agents = self.project_skill(".agents/skills", "agents")
        self.project_skill(".claude/skills", "claude")
        report = self.explain("amp")
        self.assert_winner(report, "repo-agents", agents)

    def test_configured_tier_is_unobservable(self):
        self.project_skill(".agents/skills")
        report = self.explain("amp")
        self.assertIn("configured", report["unobservable_tiers"])


class TestRooEightTiers(NewConsumerCase):
    def test_project_roo_beats_project_agents(self):
        roo = self.project_skill(".roo/skills", "roo")
        agents = self.project_skill(".agents/skills", "agents")
        report = self.explain("roo")
        self.assert_winner(report, "project-roo", roo)
        self.assert_shadowed_by(report, "project-roo", agents)

    def test_global_roo_beats_global_agents(self):
        roo = self.home_skill(".roo/skills", "roo")
        agents = self.home_skill(".agents/skills", "agents")
        report = self.explain("roo")
        self.assert_winner(report, "global-roo", roo)
        self.assert_shadowed_by(report, "global-roo", agents)

    def test_mode_specific_tiers_are_unobservable(self):
        self.project_skill(".roo/skills")
        report = self.explain("roo")
        self.assertEqual(
            report["unobservable_tiers"],
            [
                "project-roo-mode",
                "project-agents-mode",
                "global-roo-mode",
                "global-agents-mode",
            ],
        )
        self.assertTrue(all(
            "mode slug" in tier["note"]
            for tier in report["tiers"]
            if tier["id"] in report["unobservable_tiers"]
        ))


class TestZedOrder(NewConsumerCase):
    def test_project_beats_user(self):
        project = self.project_skill(".agents/skills", "project")
        user = self.home_skill(".agents/skills", "user")
        report = self.explain("zed")
        self.assert_winner(report, "project", project)
        self.assert_shadowed_by(report, "project", user)


class TestUndocumentedConsumers(NewConsumerCase):
    def test_copilot_lists_roots_without_electing_a_winner(self):
        self.project_skill(".github/skills", "project")
        self.home_skill(".copilot/skills", "user")
        report = self.explain("copilot")
        self.assertEqual(report["resolution"], "undocumented-precedence")
        self.assertEqual(report["policy"], "undocumented")
        entry = self.entry(report)
        self.assertIsNone(entry["winner"])
        self.assertEqual(len(entry["candidates"]), 2)
        self.assertIn("no winner is elected", entry["reason"])

    def test_devin_lists_legacy_and_current_roots_without_a_winner(self):
        self.project_skill(".devin/skills", "devin")
        self.home_skill(".config/devin/skills", "user")
        report = self.explain("devin")
        self.assertEqual(report["label"], "Windsurf / Devin")
        self.assertEqual(report["resolution"], "undocumented-precedence")
        self.assertIsNone(self.entry(report)["winner"])
        roots = [root for tier in report["tiers"] for root in tier["roots"]]
        self.assertTrue(any(root.endswith(".windsurf/skills") for root in roots))

    def test_known_consumers_include_the_new_rows(self):
        for consumer in ("amp", "cline", "copilot", "devin", "kiro", "roo", "zed"):
            self.assertIn(consumer, effective.known_consumers())


class TestHomeRootRedaction(unittest.TestCase):
    """A ``home`` root is confined and redacted exactly like a ``path`` root."""

    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name)
        cls.home = cls.base / "home"
        cls.home.mkdir()
        skill(cls.home / ".kiro/skills", description="home copy")
        cls._old_home = os.environ.get("HOME")
        cls._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["HOME"] = str(cls.home)
        os.environ["SKILLS_MANAGER_DATA"] = str(cls.base / "data")
        cls.store = Store()
        cls.store.init_db()
        cls.managed = cls.store.data_dir / "project"
        skill(cls.managed / ".kiro/skills", description="project copy")
        cls.server = WebAppServer(cls.store, port=0)
        cls.base_url = f"http://127.0.0.1:{cls.server.httpd.server_port}"
        cls._thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls._thread.join(timeout=5)
        cls.server.httpd.server_close()
        cls.tmp.cleanup()
        for key, old in (("HOME", cls._old_home), ("SKILLS_MANAGER_DATA", cls._old_data)):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    @classmethod
    def get(cls, path: str):
        with urllib.request.urlopen(cls.base_url + path, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_home_root_is_redacted_and_the_project_root_is_not(self):
        status, payload = self.get(f"/api/doctor?explain=kiro&project={self.managed}")
        self.assertEqual(status, 200)
        report = payload["explain"]
        self.assertEqual(report["skills"]["deploy"]["winner_tier"], "workspace")
        self.assertTrue(report["paths_redacted"])
        self.assertNotIn(str(self.home), json.dumps(report))
        tiers = {tier["id"]: tier for tier in report["tiers"]}
        self.assertEqual(tiers["global"]["roots"], ["<redacted>"])
        self.assertEqual(
            tiers["workspace"]["roots"], [str(self.managed / ".kiro/skills")]
        )


if __name__ == "__main__":
    unittest.main()
