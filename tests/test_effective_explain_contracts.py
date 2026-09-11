"""Effective-resolution diagnostic contracts (issue #12).

Pins the read-only ``doctor --explain CONSUMER --project DIR`` diagnostic:

* per-consumer precedence is derived at read time from filesystem facts and
  cited to the primary source recorded in
  ``docs/12-agent-root-discovery-2026-09-08.md`` (Command Code six-way order,
  Codex no-merge, Claude triple plus both-load);
* a consumer with no recorded order returns ``undocumented-precedence`` and an
  unknown consumer returns ``unknown-consumer`` — never a guess;
* a missing project directory returns ``missing-project``;
* nothing is written: no file changes, no SQLite database appears, no
  ``effective_state`` other than ``unresolved`` is claimed.

All state lives in an isolated temporary HOME/data directory.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from skillsmgr import cli, effective
from skillsmgr.frontmatter import dump_frontmatter


def document(name: str, description: str) -> str:
    return dump_frontmatter({"name": name, "description": description}) + "Body.\n"


def skill(root: Path, name: str, description: str) -> Path:
    target = root / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(document(name, description), encoding="utf-8")
    return target


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


class ExplainCase(unittest.TestCase):
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

    def _restore_env(self):
        for key, old in (("HOME", self._old_home),
                         ("SKILLS_MANAGER_DATA", self._old_data)):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def home_skill(self, rel: str, name: str = "deploy", description="user copy") -> Path:
        return skill(self.home / rel, name, description)

    def project_skill(self, rel: str, name: str = "deploy", description="project copy") -> Path:
        return skill(self.project / rel, name, description)

    def invoke(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", str(self.data), *argv])
        return code, out.getvalue(), err.getvalue()

    def explain(self, consumer: str, **kwargs) -> dict:
        return effective.explain(consumer, str(self.project), **kwargs)

    def winner_path(self, report: dict, name: str = "deploy") -> str | None:
        winner = report["skills"][name]["winner"]
        return winner["path"] if winner else None


class TestCommandCodeSixWayOrder(ExplainCase):
    def test_project_commandcode_beats_every_lower_tier(self):
        expected = self.project_skill(".commandcode/skills", description="winner")
        self.project_skill(".agents/skills")
        self.home_skill(".commandcode/skills")
        self.home_skill(".agents/skills")
        report = self.explain("commandcode")
        self.assertEqual(report["resolution"], "resolved")
        self.assertEqual(report["skills"]["deploy"]["winner_tier"], "project-commandcode")
        self.assertEqual(self.winner_path(report), str(expected))
        shadowed = {item["tier"] for item in report["skills"]["deploy"]["shadowed"]}
        self.assertEqual(shadowed, {"project-agents", "user-commandcode", "user-agents"})

    def test_project_agents_beats_user_roots(self):
        expected = self.project_skill(".agents/skills", description="winner")
        self.home_skill(".commandcode/skills")
        self.home_skill(".agents/skills")
        report = self.explain("commandcode")
        self.assertEqual(report["skills"]["deploy"]["winner_tier"], "project-agents")
        self.assertEqual(self.winner_path(report), str(expected))

    def test_user_commandcode_beats_user_agents(self):
        expected = self.home_skill(".commandcode/skills", description="winner")
        self.home_skill(".agents/skills")
        report = self.explain("commandcode")
        self.assertEqual(report["skills"]["deploy"]["winner_tier"], "user-commandcode")
        self.assertEqual(self.winner_path(report), str(expected))

    def test_user_agents_wins_when_nothing_else_exists(self):
        expected = self.home_skill(".agents/skills", description="winner")
        report = self.explain("commandcode")
        self.assertEqual(report["skills"]["deploy"]["winner_tier"], "user-agents")
        self.assertEqual(self.winner_path(report), str(expected))

    def test_unobservable_extras_and_bundled_tiers_are_warned_not_guessed(self):
        self.project_skill(".commandcode/skills")
        report = self.explain("commandcode")
        self.assertEqual(report["unobservable_tiers"], ["extras", "bundled"])
        self.assertEqual(len(report["warnings"]), 2)
        self.assertIn("extras", " ".join(report["warnings"]))

    def test_source_url_is_cited(self):
        report = self.explain("commandcode")
        self.assertEqual(report["source"], "https://commandcode.ai/docs/skills")
        self.assertIn("six-way", report["notes"][0])

    def test_skill_filter_narrows_the_report(self):
        self.project_skill(".commandcode/skills", name="deploy")
        self.project_skill(".commandcode/skills", name="review")
        report = self.explain("commandcode", skill="deploy")
        self.assertEqual(list(report["skills"]), ["deploy"])
        self.assertEqual(self.explain("commandcode")["skill_count"], 2)


class TestCodexNoMerge(ExplainCase):
    def test_no_winner_is_elected_and_both_copies_are_reported(self):
        repo = self.project_skill(".agents/skills", description="repo copy")
        user = self.home_skill(".agents/skills", description="user copy")
        report = self.explain("codex")
        self.assertEqual(report["resolution"], "no-merge")
        self.assertEqual(report["policy"], "no-merge")
        entry = report["skills"]["deploy"]
        self.assertIsNone(entry["winner"])
        self.assertIsNone(entry["winner_tier"])
        self.assertEqual(entry["shadowed"], [])
        self.assertEqual(
            {item["path"] for item in entry["candidates"]},
            {str(repo), str(user)},
        )
        self.assertIn("do not merge", entry["reason"])

    def test_facade_codex_root_never_wins_and_is_warned(self):
        facade = self.home_skill(".codex/skills", description="facade copy")
        self.project_skill(".agents/skills", description="repo copy")
        report = self.explain("codex")
        warnings = " ".join(report["warnings"])
        self.assertIn("compatibility-only", warnings)
        self.assertIn(str(facade.parent), warnings)
        self.assertIn("deploy", warnings)
        candidates = {item["path"] for item in report["skills"]["deploy"]["candidates"]}
        self.assertNotIn(str(facade), candidates)

    def test_documented_admin_root_is_reported(self):
        tiers = {tier["id"]: tier for tier in self.explain("codex")["tiers"]}
        self.assertEqual(tiers["admin"]["roots"], ["/etc/codex/skills"])
        self.assertEqual(tiers["system"]["path_known"], False)


class TestClaudeTripleAndBothLoad(ExplainCase):
    def test_personal_beats_project(self):
        personal = self.home_skill(".claude/skills", description="personal")
        self.project_skill(".claude/skills", description="project")
        report = self.explain("claude-code")
        self.assertEqual(report["skills"]["deploy"]["winner_tier"], "personal")
        self.assertEqual(self.winner_path(report), str(personal))
        shadowed = [item["path"] for item in report["skills"]["deploy"]["shadowed"]]
        self.assertEqual(shadowed, [str(self.project / ".claude/skills/deploy")])

    def test_project_wins_when_no_personal_copy_exists(self):
        project = self.project_skill(".claude/skills", description="project")
        report = self.explain("claude-code")
        self.assertEqual(report["skills"]["deploy"]["winner_tier"], "project")
        self.assertEqual(self.winner_path(report), str(project))

    def test_nested_project_copy_both_loads_instead_of_being_shadowed(self):
        self.project_skill(".claude/skills", description="project")
        nested = self.project_skill("apps/web/.claude/skills", description="nested")
        report = self.explain("claude-code")
        entry = report["skills"]["deploy"]
        self.assertEqual(entry["winner_tier"], "project")
        self.assertNotIn(
            str(nested),
            [item["path"] for item in entry["shadowed"]],
        )
        self.assertEqual(
            [item["path"] for item in entry["also_loads"]],
            [str(nested)],
        )
        self.assertIn("both load", entry["also_loads_reason"])

    def test_unobservable_enterprise_tier_is_reported(self):
        self.home_skill(".claude/skills")
        report = self.explain("claude-code")
        self.assertIn("enterprise", report["unobservable_tiers"])
        self.assertIn("provisional", " ".join(report["warnings"]))


class TestGeminiTieAndUndocumentedConsumers(ExplainCase):
    def test_documented_workspace_tie_is_ambiguous_not_a_guess(self):
        self.project_skill(".gemini/skills", description="a")
        self.project_skill(".agents/skills", description="b")
        report = self.explain("gemini")
        entry = report["skills"]["deploy"]
        self.assertEqual(entry["resolution"], "ambiguous")
        self.assertIsNone(entry["winner"])
        self.assertEqual(len(entry["candidates"]), 2)
        self.assertEqual(report["resolution"], "ambiguous")

    def test_workspace_beats_user(self):
        workspace = self.project_skill(".gemini/skills", description="workspace")
        self.home_skill(".gemini/skills", description="user")
        report = self.explain("gemini")
        self.assertEqual(report["skills"]["deploy"]["winner_tier"], "workspace")
        self.assertEqual(self.winner_path(report), str(workspace))

    def test_undocumented_consumer_reports_no_order(self):
        self.home_skill(".cursor/skills")
        self.project_skill(".cursor/skills")
        report = self.explain("cursor")
        self.assertEqual(report["resolution"], "undocumented-precedence")
        entry = report["skills"]["deploy"]
        self.assertIsNone(entry["winner"])
        self.assertEqual(len(entry["candidates"]), 2)
        self.assertIn("no winner is elected", entry["reason"])

    def test_unknown_consumer_is_explicit_and_never_a_guess(self):
        report = self.explain("not-a-consumer")
        self.assertEqual(report["resolution"], "unknown-consumer")
        self.assertEqual(report["known_consumers"], sorted(effective.known_consumers()))
        self.assertNotIn("skills", report)
        self.assertIn("no order is guessed", report["reason"])

    def test_empty_consumer_is_rejected_without_raising(self):
        report = effective.explain("   ")
        self.assertEqual(report["resolution"], "unknown-consumer")

    def test_missing_project_is_reported(self):
        report = effective.explain("codex", str(self.base / "nope"))
        self.assertEqual(report["resolution"], "missing-project")
        self.assertIn("does not exist", report["reason"])


class TestInstanceStatesAndSkips(ExplainCase):
    def test_disabled_copy_is_skipped_with_a_reason(self):
        target = self.project_skill(".commandcode/skills")
        (target / "SKILL.md").rename(target / "SKILL.md.disabled")
        report = self.explain("commandcode")
        entry = report["skills"]["deploy"]
        self.assertEqual(entry["resolution"], "no-instances")
        self.assertIn("only disabled or invalid copies were found", entry["reason"])
        tier = next(t for t in report["tiers"] if t["id"] == "project-commandcode")
        self.assertEqual(tier["instances"], [])
        self.assertEqual(tier["skipped"][0]["state"], "disabled")
        self.assertIn("SKILL.md.disabled", tier["skipped"][0]["skipped_reason"])

    def test_invalid_document_cannot_win(self):
        self.project_skill(".commandcode/skills", description="broken")
        broken = self.project / ".commandcode/skills/deploy/SKILL.md"
        broken.write_text("---\nname: [broken\n---\nbody\n", encoding="utf-8")
        fallback = self.project_skill(".agents/skills", description="healthy")
        report = self.explain("commandcode")
        entry = report["skills"]["deploy"]
        self.assertEqual(entry["winner_tier"], "project-agents")
        self.assertEqual(self.winner_path(report), str(fallback))
        tier = next(t for t in report["tiers"] if t["id"] == "project-commandcode")
        self.assertEqual(tier["skipped"][0]["state"], "invalid")

    def test_undecodable_document_is_skipped_not_fatal(self):
        target = self.project_skill(".commandcode/skills")
        with (target / "SKILL.md").open("ab") as handle:
            handle.write(b"caf\xe9\n")
        fallback = self.project_skill(".agents/skills", description="healthy")
        report = self.explain("commandcode")
        self.assertEqual(self.winner_path(report), str(fallback))
        tier = next(t for t in report["tiers"] if t["id"] == "project-commandcode")
        self.assertEqual(tier["skipped"][0]["state"], "invalid")
        self.assertIn("not valid UTF-8", tier["skipped"][0]["decode_error"])

    def test_every_instance_reports_unresolved_effective_state(self):
        self.project_skill(".commandcode/skills")
        report = self.explain("commandcode")
        self.assertEqual(report["effective_state"], "unresolved")
        for tier in report["tiers"]:
            for instance in tier["instances"]:
                self.assertEqual(instance["effective_state"], "unresolved")


class TestReadOnlyGuarantees(ExplainCase):
    def test_diagnostic_writes_nothing(self):
        self.home_skill(".agents/skills")
        self.project_skill(".commandcode/skills")
        before = tree_digest(self.base)
        for consumer in effective.known_consumers():
            effective.explain(consumer, str(self.project))
        self.assertEqual(tree_digest(self.base), before)

    def test_diagnostic_creates_no_database(self):
        self.project_skill(".commandcode/skills")
        effective.explain("commandcode", str(self.project))
        self.assertEqual(list(self.data.rglob("*.db")) if self.data.exists() else [], [])

    def test_result_declares_read_only_and_no_persistence(self):
        report = self.explain("commandcode")
        self.assertTrue(report["read_only"])
        self.assertTrue(report["persists_nothing"])


class TestCliExplainSurface(ExplainCase):
    def test_text_output_names_the_winner_and_the_source(self):
        winner = self.project_skill(".commandcode/skills", description="winner")
        self.project_skill(".agents/skills", description="loser")
        code, out, err = self.invoke(
            ["doctor", "--explain", "commandcode", "--project", str(self.project)]
        )
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("effective resolution for consumer", out)
        self.assertIn(str(winner), out)
        self.assertIn("shadowed by project-commandcode", out)
        self.assertIn("https://commandcode.ai/docs/skills", out)

    def test_json_output_is_the_report(self):
        self.project_skill(".commandcode/skills")
        code, out, err = self.invoke(
            ["doctor", "--explain", "commandcode", "--project", str(self.project), "--json"]
        )
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(err, "")
        report = json.loads(out)
        self.assertEqual(report["consumer"], "commandcode")
        self.assertEqual(report["resolution"], "resolved")

    def test_unknown_consumer_exits_one_with_a_clean_message(self):
        code, out, err = self.invoke(
            ["doctor", "--explain", "nope", "--project", str(self.project)]
        )
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("no recorded precedence row", err)
        self.assertIn("known consumers", err)
        self.assertNotIn("Traceback", err)

    def test_missing_project_exits_one_with_a_clean_message(self):
        code, _, err = self.invoke(
            ["doctor", "--explain", "codex", "--project", str(self.base / "nope")]
        )
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("does not exist", err)
        self.assertNotIn("Traceback", err)

    def test_skill_flag_limits_the_report(self):
        self.project_skill(".commandcode/skills", name="deploy")
        self.project_skill(".commandcode/skills", name="review")
        code, out, _ = self.invoke(
            ["doctor", "--explain", "commandcode", "--project", str(self.project),
             "--skill", "review", "--json"]
        )
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(list(json.loads(out)["skills"]), ["review"])

    def test_plain_doctor_payload_is_unchanged(self):
        code, out, _ = self.invoke(["doctor", "--json"])
        self.assertEqual(code, cli.EXIT_OK)
        report = json.loads(out)
        self.assertNotIn("explain", report)
        self.assertIn("filesystem_index_drift", report)


class TestRestExplainSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name)
        cls.home = cls.base / "home"
        cls.project = cls.base / "project"
        cls.home.mkdir()
        cls.project.mkdir()
        skill(cls.project / ".commandcode/skills", "deploy", "winner")
        skill(cls.project / ".agents/skills", "deploy", "loser")
        cls._old_home = os.environ.get("HOME")
        cls._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["HOME"] = str(cls.home)
        os.environ["SKILLS_MANAGER_DATA"] = str(cls.base / "data")
        store = Store()
        store.init_db()
        cls.server = WebAppServer(store, port=0)
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

    def test_doctor_explain_query_adds_the_report(self):
        status, payload = self.get(
            f"/api/doctor?explain=commandcode&project={self.project}"
        )
        self.assertEqual(status, 200)
        report = payload["explain"]
        self.assertEqual(report["consumer"], "commandcode")
        self.assertEqual(report["resolution"], "resolved")
        self.assertEqual(
            report["skills"]["deploy"]["winner_tier"], "project-commandcode"
        )

    def test_doctor_without_explain_keeps_its_shape(self):
        status, payload = self.get("/api/doctor")
        self.assertEqual(status, 200)
        self.assertNotIn("explain", payload)

    def test_rest_unknown_consumer_is_an_explicit_result_not_an_error(self):
        status, payload = self.get("/api/doctor?explain=nope")
        self.assertEqual(status, 200)
        self.assertEqual(payload["explain"]["resolution"], "unknown-consumer")


if __name__ == "__main__":
    unittest.main()
