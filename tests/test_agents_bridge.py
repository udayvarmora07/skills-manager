"""docs/29 H2, explain-only: skills in ~/.agents/skills that Claude Code cannot see.

Claude Code documents ``~/.claude/skills`` and project ``.claude/skills`` but not
``~/.agents/skills`` (docs/34), so a skill installed only there is invisible to
it. The hygiene report explains that gap read-only. It never creates a link or a
copy; the remedy it names is the existing ``sync`` command.
"""
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from skillsmgr import cli_handlers, hygiene, scopes

DOCUMENT = "---\nname: {name}\ndescription: Use {name} when testing the bridge.\n---\n# {name}\n"


class AgentsBridgeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name).resolve()
        base.chmod(0o700)
        self.home = base / "home"
        self.home.mkdir(mode=0o700)
        data = base / "data"
        data.mkdir(mode=0o700)
        self._old = {key: os.environ.get(key) for key in ("HOME", "SKILLS_MANAGER_DATA")}
        os.environ["HOME"] = str(self.home)
        os.environ["SKILLS_MANAGER_DATA"] = str(data)
        scopes.set_global_store(None)
        self.addCleanup(self._restore)
        self.agents = self.home / ".agents/skills"
        self.claude = self.home / ".claude/skills"
        for name in ("only-agents", "copied", "linked", "turned-off"):
            self._skill(self.agents / name, name)
        self._skill(self.claude / "copied", "copied")
        (self.claude / "linked").symlink_to(self.agents / "linked", target_is_directory=True)
        (self.agents / "turned-off/SKILL.md").rename(self.agents / "turned-off/SKILL.md.disabled")

    def _restore(self):
        scopes.set_global_store(None)
        for key, old in self._old.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    @staticmethod
    def _skill(directory: Path, name: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SKILL.md").write_text(DOCUMENT.format(name=name), encoding="utf-8")

    def _report(self, scope="all"):
        records = scopes.list_all() if scope == "all" else scopes.scan_scope(scope)
        return hygiene.hygiene_report(records, scope=scope, home=self.home)

    def _snapshot(self):
        return sorted(
            (str(path.relative_to(self.home)), path.is_symlink())
            for path in self.home.rglob("*")
        )

    def test_names_only_the_enabled_skill_claude_code_cannot_see(self):
        section = self._report()["agents_bridge"]
        self.assertEqual(section["state"], "observed")
        self.assertEqual(section["consumer"], "claude-code")
        self.assertEqual([item["name"] for item in section["missing"]], ["only-agents"])
        self.assertEqual(section["missing_total"], 1)
        self.assertEqual(section["missing"][0]["path"], "~/.agents/skills/only-agents")
        self.assertIn("code.claude.com/docs/en/skills", section["source"])

    def test_a_copy_and_a_link_both_count_as_present(self):
        section = self._report()["agents_bridge"]
        missing = {item["name"] for item in section["missing"]}
        self.assertNotIn("copied", missing)
        self.assertNotIn("linked", missing)
        self.assertNotIn("turned-off", missing)

    def test_remedies_use_existing_commands_and_name_the_link_caveat(self):
        section = self._report()["agents_bridge"]
        kinds = {item["kind"]: item for item in section["remedies"]}
        self.assertEqual(
            kinds["copy"]["command"], "skills-mgr sync <name> --from agents --to claude-code"
        )
        self.assertIn("14836", kinds["link"]["note"])
        self.assertTrue(section["writes_nothing"])

    def test_one_advisory_finding_lists_the_gap(self):
        findings = [f for f in self._report()["findings"] if f["category"] == "agents-bridge-gap"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "info")
        self.assertEqual(findings[0]["evidence"]["missing_total"], 1)

    def test_no_gap_means_no_finding(self):
        (self.agents / "only-agents/SKILL.md").rename(self.agents / "only-agents/SKILL.md.disabled")
        report = self._report()
        self.assertEqual(report["agents_bridge"]["missing_total"], 0)
        self.assertFalse([f for f in report["findings"] if f["category"] == "agents-bridge-gap"])

    def test_a_single_scope_report_says_it_cannot_compare(self):
        section = self._report("agents")["agents_bridge"]
        self.assertEqual(section["state"], "unavailable")
        self.assertIn("--scope all", section["reason"])
        self.assertEqual(section["missing"], [])

    def test_the_report_writes_nothing(self):
        before = self._snapshot()
        self._report()
        self.assertEqual(self._snapshot(), before)

    def test_missing_list_is_bounded(self):
        for index in range(hygiene.MAX_BRIDGE_NAMES + 5):
            self._skill(self.agents / f"extra-{index:03d}", f"extra-{index:03d}")
        section = self._report()["agents_bridge"]
        self.assertEqual(len(section["missing"]), hygiene.MAX_BRIDGE_NAMES)
        self.assertEqual(section["missing_total"], hygiene.MAX_BRIDGE_NAMES + 6)
        self.assertEqual(section["omitted"], 6)

    def test_cli_prints_one_summary_line(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            cli_handlers._render_agents_bridge_text(self._report()["agents_bridge"])
        self.assertEqual(
            buffer.getvalue().strip(),
            "Claude Code cannot see 1 skill that is only in ~/.agents/skills "
            "(copy it with: skills-mgr sync <name> --from agents --to claude-code)",
        )


if __name__ == "__main__":
    unittest.main()
