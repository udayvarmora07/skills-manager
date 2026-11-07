"""Contracts for the read-only Claude Code skill-listing budget section.

Every fact this section reports comes from
``docs/34-agent-skill-loading-research-2026-11-07.md`` ("Claude Code skill
listing budget"): the listing always holds every name, descriptions are capped
per entry, the character budget scales from a token window (an undocumented
conversion, so every figure here is an estimate), and Claude Code drops
descriptions starting with the least-invoked skills -- which this tool cannot
observe, so it may only name candidates by size.  Nothing here writes files,
adds a CLI/REST/Store surface, or makes a network request.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import hygiene, loader, native_state
from skillsmgr.frontmatter import dump_frontmatter


class ClaudeListingContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        os.chmod(root, 0o700)
        self.home = root / "home"
        self.home.mkdir(mode=0o700)
        self.skills = self.home / ".claude" / "skills"
        self.skills.mkdir(parents=True)
        self.data = root / "data"
        self.data.mkdir(mode=0o700)
        environment = mock.patch.dict(
            os.environ, {"HOME": str(self.home), "SKILLS_MANAGER_DATA": str(self.data)}
        )
        environment.start()
        self.addCleanup(environment.stop)
        # A developer machine may export the real budget; every test states it.
        os.environ.pop(native_state.LISTING_BUDGET_ENV, None)
        home = mock.patch.object(Path, "home", return_value=self.home)
        home.start()
        self.addCleanup(home.stop)

    # -- fixtures -----------------------------------------------------------
    def write_skill(self, name, description="Use this when testing.", extra=None,
                    disabled=False):
        directory = self.skills / name
        directory.mkdir()
        frontmatter = {"name": name, "description": description}
        frontmatter.update(extra or {})
        document = directory / ("SKILL.md.disabled" if disabled else "SKILL.md")
        document.write_text(dump_frontmatter(frontmatter) + "Body.\n", encoding="utf-8")
        return directory

    def write_settings(self, value, source="user"):
        home_file = self.home / ".claude/settings.json"
        if source == "user":
            path = home_file
        else:
            path = self.home / ".claude" / "settings.local.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def records(self):
        rows = loader.scan_dir(self.skills)
        for row in rows:
            row["scope"] = "claude-code"
            row["scope_label"] = "Claude Code"
            row["consumer"] = "claude-code"
            row["path"] = str(self.skills / row["name"])
            row["physical_path"] = row["path"]
        return rows

    def section(self, **kwargs):
        kwargs.setdefault("home", self.home)
        report = hygiene.hygiene_report(self.records(), scope="claude-code", **kwargs)
        return report, report["claude_listing"]

    # -- per-entry evidence -------------------------------------------------
    def test_a_name_only_override_counts_only_the_name(self):
        self.write_skill("alpha", "D" * 100)
        self.write_skill("beta", "B" * 10)
        self.write_settings({"skillOverrides": {"alpha": "name-only"}})
        _report, section = self.section()
        entries = {entry["name"]: entry for entry in section["entries"]}
        self.assertEqual(entries["alpha"]["listing"], "name-only")
        self.assertEqual(entries["alpha"]["entry_chars"], len("alpha"))
        self.assertEqual(entries["alpha"]["counted_description_chars"], 0)
        self.assertEqual(section["excluded"]["name_only"], 1)
        self.assertEqual(
            section["listing_chars"],
            len("alpha") + len("\n") + len("beta: " + "B" * 10),
        )

    def test_an_off_override_is_not_listed(self):
        self.write_skill("alpha", "D" * 100)
        self.write_skill("beta", "B" * 10)
        self.write_settings({"skillOverrides": {"alpha": "off"}})
        _report, section = self.section()
        self.assertEqual([entry["name"] for entry in section["entries"]], ["beta"])
        self.assertEqual(section["excluded"]["skillOverrides_off"], 1)
        self.assertEqual(section["listed_skills"], 1)
        self.assertEqual(section["instances_observed"], 2)

    def test_a_user_invocable_only_override_is_hidden_from_the_listing(self):
        # Documented: "user-invocable-only" -> Listed to Claude: Hidden.
        self.write_skill("alpha", "D" * 100)
        self.write_skill("beta", "B" * 10)
        self.write_settings({"skillOverrides": {"alpha": "user-invocable-only"}})
        _report, section = self.section()
        self.assertEqual([entry["name"] for entry in section["entries"]], ["beta"])
        self.assertEqual(section["excluded"]["skillOverrides_user_invocable_only"], 1)

    def test_disable_model_invocation_keeps_the_skill_out_of_the_listing(self):
        self.write_skill("alpha", "D" * 100, extra={"disable-model-invocation": True})
        self.write_skill("beta", "B" * 10)
        _report, section = self.section()
        self.assertEqual([entry["name"] for entry in section["entries"]], ["beta"])
        self.assertEqual(section["excluded"]["disable_model_invocation"], 1)

    def test_without_a_project_root_the_estimate_is_marked_partial(self):
        self.write_skill("beta", "B" * 10)
        _report, section = self.section()
        self.assertEqual(section["confidence"], "partial")
        self.assertTrue(any("project settings were not read" in r for r in section["partial_reasons"]))
        self.assertIn(section["status"], ("within_budget", "over_budget_estimate"))

    def test_a_disabled_document_is_not_listed(self):
        self.write_skill("alpha", "D" * 100, disabled=True)
        self.write_skill("beta", "B" * 10)
        _report, section = self.section()
        self.assertEqual([entry["name"] for entry in section["entries"]], ["beta"])
        self.assertEqual(section["excluded"]["disabled"], 1)
        self.assertEqual(section["listed_skills"], 1)

    def test_when_to_use_is_counted_with_the_description(self):
        self.write_skill("alpha", "short", {"when_to_use": "when the task needs it"})
        _report, section = self.section()
        entry = section["entries"][0]
        self.assertEqual(entry["description_chars"], len("short") + len("when the task needs it"))
        self.assertEqual(
            section["listing_chars"], len("alpha: " + "shortwhen the task needs it")
        )

    # -- cap ----------------------------------------------------------------
    def test_the_default_cap_is_1536_characters(self):
        self.write_skill("alpha", "D" * 1600)
        _report, section = self.section()
        entry = section["entries"][0]
        self.assertEqual(section["max_description_chars"], 1536)
        self.assertEqual(entry["counted_description_chars"], 1536)
        self.assertEqual(entry["description_chars"], 1600)
        self.assertTrue(entry["over_cap"])
        self.assertEqual(section["over_cap"]["count"], 1)
        self.assertEqual(section["over_cap"]["names"], ["alpha"])
        self.assertEqual(section["listing_chars"], len("alpha: " + "D" * 1536))

    def test_skill_listing_max_desc_chars_from_settings_wins(self):
        self.write_skill("alpha", "D" * 100)
        self.write_settings({"skillListingMaxDescChars": 40})
        _report, section = self.section()
        self.assertEqual(section["max_description_chars"], 40)
        self.assertEqual(section["entries"][0]["counted_description_chars"], 40)
        self.assertTrue(section["entries"][0]["over_cap"])
        self.assertEqual(section["settings"]["max_desc_chars"], 40)

    def test_an_unusable_cap_is_reported_as_invalid_evidence(self):
        self.write_skill("alpha", "D" * 100)
        self.write_settings({"skillListingMaxDescChars": 0})
        _report, section = self.section()
        self.assertEqual(section["max_description_chars"], 1536)
        user = section["settings"]["sources"][0]
        self.assertEqual(user["invalid_keys"], ["skillListingMaxDescChars"])

    # -- budget -------------------------------------------------------------
    def test_the_environment_budget_overrides_the_fraction(self):
        self.write_skill("alpha", "D" * 100)
        self.write_settings({"skillListingBudgetFraction": 0.5})
        with mock.patch.dict(os.environ, {native_state.LISTING_BUDGET_ENV: "300"}):
            _report, section = self.section()
        budget = section["budget"]
        self.assertEqual(budget["basis"], f"env {native_state.LISTING_BUDGET_ENV}")
        self.assertEqual(budget["budget_chars"], 300)
        self.assertEqual(budget["budget_chars_estimate"], 300)
        self.assertIsNone(budget["budget_tokens"])
        self.assertEqual(budget["fraction"], None)

    def test_an_invalid_environment_budget_falls_back_to_the_fraction(self):
        self.write_skill("alpha", "D" * 100)
        self.write_settings({"skillListingBudgetFraction": 0.5})
        with mock.patch.dict(os.environ, {native_state.LISTING_BUDGET_ENV: "secret-abc"}):
            _report, section = self.section()
        self.assertEqual(section["budget"]["fraction"], 0.5)
        self.assertEqual(section["settings"]["env_budget"]["status"], "invalid")
        self.assertNotIn("secret-abc", json.dumps(section["settings"]))

    def test_the_fraction_comes_from_settings_and_scales_the_window(self):
        self.write_skill("alpha", "D" * 100)
        self.write_settings({"skillListingBudgetFraction": 0.5})
        _report, section = self.section(window="claude-haiku")
        budget = section["budget"]
        self.assertEqual(budget["basis"], "skillListingBudgetFraction setting")
        self.assertEqual(budget["window"], "claude-haiku")
        self.assertEqual(budget["window_tokens"], 200_000)
        self.assertEqual(budget["budget_tokens"], 100_000)
        self.assertEqual(budget["budget_chars_estimate"], 400_000)
        self.assertIn("4 characters per token", budget["assumption"])

    def test_the_default_fraction_is_one_percent_of_the_window(self):
        self.write_skill("alpha", "D" * 100)
        _report, section = self.section()
        budget = section["budget"]
        self.assertEqual(budget["fraction"], 0.01)
        self.assertEqual(budget["budget_tokens"], 10_000)
        self.assertEqual(budget["budget_chars_estimate"], 40_000)
        self.assertIn("default 1%", budget["basis"])

    def test_within_and_over_budget_statuses(self):
        self.write_skill("alpha", "D" * 100)
        with mock.patch.dict(os.environ, {native_state.LISTING_BUDGET_ENV: "100000"}):
            report, section = self.section()
        self.assertEqual(section["status"], "within_budget")
        self.assertEqual(section["chars_to_free"], 0)
        self.assertEqual(
            [f for f in report["findings"] if f["category"] == "claude-listing-budget"], []
        )

        with mock.patch.dict(os.environ, {native_state.LISTING_BUDGET_ENV: "10"}):
            report, section = self.section()
        self.assertEqual(section["status"], "over_budget_estimate")
        self.assertEqual(section["chars_to_free"], section["listing_chars"] - 10)
        findings = [f for f in report["findings"] if f["category"] == "claude-listing-budget"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "info")
        self.assertTrue(findings[0]["evidence"]["candidates_by_size_only"])

    # -- R13 candidates -----------------------------------------------------
    def test_candidates_are_sorted_bounded_and_exclude_name_only_entries(self):
        for index in range(30):
            self.write_skill(f"skill-{index:02d}", "D" * (10 + index))
        self.write_skill("name-only-one", "D" * 500)
        self.write_settings({"skillOverrides": {"name-only-one": "name-only"}})
        _report, section = self.section()
        candidates = section["name_only_candidates"]
        self.assertEqual(candidates["total"], 30)
        self.assertEqual(len(candidates["candidates"]), 25)
        self.assertEqual(candidates["omitted"], 5)
        self.assertNotIn(
            "name-only-one", [item["name"] for item in candidates["candidates"]]
        )
        sizes = [item["description_chars"] for item in candidates["candidates"]]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        self.assertEqual(sizes[0], 10 + 29)
        first = candidates["candidates"][0]
        self.assertEqual(first["freed_chars"], len(f": {'D' * 39}"))
        self.assertTrue(first["path"].startswith("~/"))

    # -- confidence / evidence ---------------------------------------------
    def test_partial_settings_evidence_is_disclosed(self):
        self.write_skill("alpha", "D" * 100)
        (self.home / ".claude" / "settings.json").write_text("{", encoding="utf-8")
        _report, section = self.section()
        self.assertEqual(section["confidence"], "partial")
        self.assertEqual(section["status"], "unknown")
        # The numbers are still computed and reported.
        self.assertGreater(section["listing_chars"], 0)
        self.assertEqual(section["settings"]["sources"][0]["status"], "unavailable")

    def test_project_instances_are_included_only_with_a_project_root(self):
        self.write_skill("alpha", "D" * 10)
        project = Path(self.tmp.name) / "project"
        (project / ".claude" / "skills" / "gamma").mkdir(parents=True)
        (project / ".claude" / "skills" / "gamma" / "SKILL.md").write_text(
            dump_frontmatter({"name": "gamma", "description": "G" * 10}) + "Body.\n",
            encoding="utf-8",
        )
        _report, section = self.section(project_root=project)
        self.assertEqual(
            sorted(entry["name"] for entry in section["entries"]), ["alpha", "gamma"]
        )
        self.assertEqual(section["project_skills"]["state"], "observed")
        self.assertEqual(section["project_skills"]["instances"], 1)

        _report, section = self.section()
        self.assertEqual(section["project_skills"]["state"], "unavailable")
        self.assertIn("no project root", section["project_skills"]["reason"])

    def test_a_report_without_claude_code_instances_says_so(self):
        report = hygiene.hygiene_report([], scope="global", home=self.home)
        self.assertEqual(report["claude_listing"]["instances_observed"], 0)
        signals = {item["signal"] for item in report["unavailable_signals"]}
        self.assertIn("claude-listing-scope", signals)

    # -- pure read ----------------------------------------------------------
    def test_the_section_writes_nothing(self):
        self.write_skill("alpha", "D" * 100)
        self.write_settings({
            "skillOverrides": {"alpha": "name-only"},
            "skillListingBudgetFraction": 0.02,
        })
        project = Path(self.tmp.name) / "project"
        (project / ".claude" / "skills" / "gamma").mkdir(parents=True)
        (project / ".claude" / "skills" / "gamma" / "SKILL.md").write_text(
            dump_frontmatter({"name": "gamma", "description": "G"}) + "Body.\n",
            encoding="utf-8",
        )
        before = self.snapshot()
        self.section(project_root=project)
        self.assertEqual(self.snapshot(), before)

    def snapshot(self):
        entries = []
        for path in sorted(Path(self.tmp.name).rglob("*")):
            info = path.lstat()
            entries.append((str(path.relative_to(self.tmp.name)), info.st_size, info.st_mtime_ns))
        return entries

    # -- serialization / argument contract ----------------------------------
    def test_the_whole_report_is_json_serializable(self):
        self.write_skill("alpha", "D" * 100, {"when_to_use": "W" * 20})
        self.write_settings({"skillOverrides": {"alpha": "name-only"}})
        report, _section = self.section()
        encoded = json.dumps(report, ensure_ascii=False)
        self.assertIn("claude_listing", encoded)

    def test_an_unknown_window_is_a_clean_error(self):
        with self.assertRaises(hygiene.HygieneError) as caught:
            hygiene.hygiene_report([], scope="all", window="bogus")
        self.assertIn("bogus", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
