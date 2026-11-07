"""Contracts for the ignored-frontmatter hygiene finding (docs/29 H1, docs/34).

The finding is advisory: it reports a key that has a documented behavioural
effect in Claude Code when the consumer reading that scope documents no such
effect.  It never claims the key was rejected -- only the claude.ai upload and
Skills API surfaces are documented to reject unknown keys.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from skillsmgr import hygiene, key_support
from skillsmgr.frontmatter import dump_frontmatter


def write_skill(root: Path, name: str, extra: dict | None = None,
                description: str = "Use this skill when doing the work.") -> Path:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    frontmatter = {"name": name, "description": description}
    frontmatter.update(extra or {})
    (directory / "SKILL.md").write_text(
        dump_frontmatter(frontmatter) + "Body.\n", encoding="utf-8"
    )
    return directory


def record(directory: Path, scope: str, name: str = "deploy") -> dict:
    return {
        "name": name,
        "scope": scope,
        "scope_label": scope,
        "path": str(directory),
    }


def key_findings(report: dict) -> list[dict]:
    return [
        finding for finding in report["findings"]
        if finding["category"] == "ignored-frontmatter"
    ]


class TestDocumentedKeyTable(unittest.TestCase):
    def test_spot_keys_match_docs_34(self):
        self.assertTrue(key_support.documents("claude-code", "disable-model-invocation"))
        self.assertTrue(key_support.documents("claude-code", "when_to_use"))
        self.assertFalse(key_support.documents("codex", "disable-model-invocation"))
        self.assertTrue(key_support.documents("zed", "disable-model-invocation"))
        self.assertTrue(key_support.documents("opencode", "disable-model-invocation"))
        self.assertFalse(key_support.documents("opencode", "user-invocable"))
        self.assertTrue(key_support.documents("amp", "mcpServers"))
        self.assertTrue(key_support.documents("kiro", "license"))
        self.assertFalse(key_support.documents("roo", "allowed-tools"))

    def test_dotted_entry_documents_its_top_level_key(self):
        self.assertIn("metadata.opencode/autoinvoke",
                      key_support.documented_keys("opencode"))
        self.assertTrue(key_support.documents("opencode", "metadata"))

    def test_every_row_cites_its_source(self):
        for consumer in key_support.known_consumers():
            self.assertTrue(key_support.source(consumer).startswith("https://"))

    def test_claude_ai_rejection_is_recorded_only_there(self):
        self.assertIn("hard error",
                      key_support.DOCUMENTED_KEYS["claude.ai-api"]["unknown_keys"])
        self.assertIn("ignores unrecognized keys",
                      key_support.DOCUMENTED_KEYS["claude-code"]["unknown_keys"])


class TestIgnoredFrontmatterFinding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_codex_reports_the_key_with_its_own_switch(self):
        directory = write_skill(self.root, "deploy",
                                {"disable-model-invocation": True})
        report = hygiene.hygiene_report([record(directory, "codex")], scope="codex")
        findings = key_findings(report)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["severity"], "info")
        self.assertEqual(finding["evidence"]["key"], "disable-model-invocation")
        self.assertEqual(finding["evidence"]["not_documented_by"], ["Codex"])
        self.assertEqual(finding["evidence"]["documented_by"], [])
        self.assertIn("agents/openai.yaml", finding["explanation"])
        self.assertIn("policy.allow_implicit_invocation", finding["explanation"])
        self.assertIn("https://learn.chatgpt.com/docs/build-skills",
                      finding["evidence"]["sources"])
        self.assertIn("not a rejection claim", finding["explanation"])

    def test_claude_code_documents_the_key_so_nothing_is_reported(self):
        directory = write_skill(self.root, "deploy",
                                {"disable-model-invocation": True})
        report = hygiene.hygiene_report([record(directory, "claude-code")],
                                        scope="claude-code")
        self.assertEqual(key_findings(report), [])

    def test_shared_agents_scope_names_who_documents_the_key(self):
        directory = write_skill(self.root, "deploy",
                                {"disable-model-invocation": True})
        report = hygiene.hygiene_report([record(directory, "agents")], scope="agents")
        findings = key_findings(report)
        self.assertEqual(len(findings), 1)
        evidence = findings[0]["evidence"]
        self.assertEqual(evidence["documented_by"], ["OpenCode", "Zed"])
        self.assertEqual(
            evidence["not_documented_by"],
            ["Amp", "Codex", "Gemini CLI", "Roo Code"],
        )

    def test_shared_agents_scope_names_who_does_not_document_a_key(self):
        directory = write_skill(self.root, "deploy", {"allowed-tools": ["Bash"]})
        report = hygiene.hygiene_report([record(directory, "agents")], scope="agents")
        evidence = key_findings(report)[0]["evidence"]
        self.assertEqual(evidence["documented_by"], [])
        self.assertEqual(
            evidence["not_documented_by"],
            ["Amp", "Codex", "Gemini CLI", "OpenCode", "Roo Code", "Zed"],
        )

    def test_opencode_documents_disable_model_invocation(self):
        directory = write_skill(self.root, "deploy",
                                {"disable-model-invocation": True})
        report = hygiene.hygiene_report([record(directory, "opencode")],
                                        scope="opencode")
        self.assertEqual(key_findings(report), [])

    def test_non_behavioural_unknown_keys_are_not_reported(self):
        directory = write_skill(self.root, "deploy", {"some-custom-flag": True})
        report = hygiene.hygiene_report([record(directory, "codex")], scope="codex")
        self.assertEqual(key_findings(report), [])

    def test_scopes_without_a_key_list_are_unavailable_not_silent(self):
        directory = write_skill(self.root, "deploy",
                                {"disable-model-invocation": True})
        report = hygiene.hygiene_report([record(directory, "global")], scope="global")
        self.assertEqual(key_findings(report), [])
        signals = {item["signal"]: item for item in report["unavailable_signals"]}
        self.assertIn("frontmatter-key-support", signals)
        self.assertIn("global", signals["frontmatter-key-support"]["explanation"])

    def test_findings_are_bounded_and_json_serializable(self):
        records = [
            record(write_skill(self.root, f"skill-{index}",
                               {"disable-model-invocation": True}),
                   "codex", name=f"skill-{index}")
            for index in range(105)
        ]
        report = hygiene.hygiene_report(records, scope="codex")
        findings = key_findings(report)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(len(finding["instances"]), hygiene.MAX_GROUP_INSTANCES)
        self.assertTrue(finding["evidence"]["instances_truncated"])
        self.assertEqual(finding["evidence"]["instances_total"], 105)
        json.dumps(report)


if __name__ == "__main__":
    unittest.main()
