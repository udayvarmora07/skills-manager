"""Round 5: Codex explicit-only skills and machine-local link targets.

openai/codex#23454: a skill whose ``agents/openai.yaml`` sets
``policy.allow_implicit_invocation: false`` is ``hidden_from_prompt``
(codex-rs/ext/skills/src/provider/host.rs, read 2026-11-13), so it never
appears in the model-visible listing and the model can wrongly answer that
the skill does not exist.  The Codex listing estimate must not count it, and
the report should name it.

google-gemini/gemini-cli#29548: a shipped SKILL.md linked to
``file:///Users/<someone>/...``.  The validator skipped every ``://`` link
silently and reported ``/home/<someone>/...`` only as "escapes the skill
directory".  Both now say the target exists on one machine only.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsmgr import hygiene, loader, native_state, validator

DOC = "---\nname: {n}\ndescription: {d}\n---\n{b}\n"


class _Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name).resolve()
        self.root = self.home / ".agents" / "skills"
        self.root.mkdir(parents=True)
        env = patch.dict(os.environ, {"CODEX_HOME": ""})
        env.start()
        self.addCleanup(env.stop)

    def skill(self, name: str, description: str = "Use when testing.", body: str = "Body") -> Path:
        folder = self.root / name
        folder.mkdir()
        (folder / "SKILL.md").write_text(DOC.format(n=name, d=description, b=body), encoding="utf-8")
        return folder

    def metadata(self, folder: Path, text: str) -> Path:
        (folder / "agents").mkdir(exist_ok=True)
        path = folder / "agents" / "openai.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def report(self, scope: str = "agents", window: str = "gpt-5"):
        records = loader.scan_dir(self.root, annotate_paths=True)
        for record in records:
            record["scope"] = scope
        return hygiene.hygiene_report(records, scope=scope, home=self.home, window=window)

    def findings(self, report, category):
        return [f for f in report["findings"] if f["category"] == category]


class CodexImplicitInvocationTests(_Fixture):
    def test_block_policy_false_is_explicit_only(self):
        folder = self.skill("quiet")
        self.metadata(folder, "interface:\n  display_name: Quiet\npolicy:\n  allow_implicit_invocation: false\n")
        self.assertEqual(native_state.codex_implicit_invocation(folder)["state"], "explicit_only")

    def test_flow_policy_and_comment_and_case_are_read(self):
        folder = self.skill("flow")
        self.metadata(folder, "policy: {allow_implicit_invocation: False}  # manual only\n")
        self.assertEqual(native_state.codex_implicit_invocation(folder)["state"], "explicit_only")
        other = self.skill("commented")
        self.metadata(other, "policy:\n  # keep manual\n  allow_implicit_invocation: false   # see #23454\n")
        self.assertEqual(native_state.codex_implicit_invocation(other)["state"], "explicit_only")

    def test_true_missing_and_other_keys_allow_implicit(self):
        folder = self.skill("loud")
        self.metadata(folder, "policy:\n  allow_implicit_invocation: true\n")
        self.assertEqual(native_state.codex_implicit_invocation(folder)["state"], "allowed")
        plain = self.skill("plain")
        self.assertEqual(native_state.codex_implicit_invocation(plain)["state"], "allowed")
        nested = self.skill("nested")
        # The key outside ``policy`` is not Codex's switch.
        self.metadata(nested, "interface:\n  allow_implicit_invocation: false\npolicy:\n  products: []\n")
        self.assertEqual(native_state.codex_implicit_invocation(nested)["state"], "allowed")

    def test_symlinked_or_oversized_metadata_is_unread_not_followed(self):
        target = self.home / "elsewhere.yaml"
        target.write_text("policy:\n  allow_implicit_invocation: false\n", encoding="utf-8")
        folder = self.skill("linked")
        (folder / "agents").mkdir()
        (folder / "agents" / "openai.yaml").symlink_to(target)
        self.assertEqual(native_state.codex_implicit_invocation(folder)["state"], "unread")
        big = self.skill("big")
        self.metadata(big, "policy:\n  allow_implicit_invocation: false\n" + "#" * (70 * 1024))
        self.assertEqual(native_state.codex_implicit_invocation(big)["state"], "unread")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs POSIX FIFOs")
    def test_fifo_metadata_does_not_block(self):
        folder = self.skill("fifo")
        (folder / "agents").mkdir()
        os.mkfifo(folder / "agents" / "openai.yaml")
        self.assertEqual(native_state.codex_implicit_invocation(folder)["state"], "unread")

    def test_listing_excludes_explicit_only_and_names_it_once(self):
        self.skill("kept")
        quiet = self.skill("quiet", "Use when reviewing " + "z" * 400)
        self.metadata(quiet, "policy:\n  allow_implicit_invocation: false\n")
        report = self.report()
        section = report["codex_listing"]
        self.assertEqual(section["listed_skills"], 1)
        self.assertEqual(section["excluded"]["explicit_only"], 1)
        self.assertEqual(section["explicit_only"]["names"], ["quiet"])
        self.assertLess(section["listing_tokens_estimate"], 60)
        found = self.findings(report, "codex-explicit-only-skill")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "info")
        self.assertIn("$quiet", found[0]["recommendation"])

    def test_no_explicit_only_means_no_finding(self):
        self.skill("kept")
        report = self.report()
        self.assertEqual(report["codex_listing"]["excluded"]["explicit_only"], 0)
        self.assertEqual(report["codex_listing"]["explicit_only"]["names"], [])
        self.assertFalse(self.findings(report, "codex-explicit-only-skill"))

    def test_names_are_bounded(self):
        for i in range(60):
            folder = self.skill(f"quiet-{i:02d}")
            self.metadata(folder, "policy:\n  allow_implicit_invocation: false\n")
        block = self.report()["codex_listing"]["explicit_only"]
        self.assertEqual(block["total"], 60)
        self.assertLessEqual(len(block["names"]), 50)
        self.assertEqual(block["omitted"], 60 - len(block["names"]))


class MachineLocalLinkTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "linker"
        self.dir.mkdir()

    def validate(self, body: str):
        text = DOC.format(n="linker", d="Use when linking files together.", b=body)
        (self.dir / "SKILL.md").write_text(text, encoding="utf-8")
        return validator.validate_skill("linker", self.dir)

    def messages(self, result):
        return [issue.message for issue in result.warnings]

    def test_file_url_is_reported_as_machine_local(self):
        result = self.validate("See [evals](file:///Users/abhi/code/docs/evals/README.md).")
        self.assertTrue(result.valid)
        local = [m for m in self.messages(result) if "one machine" in m]
        self.assertEqual(len(local), 1)

    def test_home_absolute_paths_are_machine_local_not_out_of_root(self):
        for target in ("/home/alice/notes.md", "/Users/bob/x.md", "C:/Users/carol/x.md", "C:\\Users\\dan\\x.md"):
            with self.subTest(target=target):
                messages = self.messages(self.validate(f"[n]({target})"))
                self.assertTrue(any("one machine" in m for m in messages), messages)
                self.assertFalse(any("escapes the skill directory" in m for m in messages), messages)

    def test_web_links_and_other_absolute_paths_are_unchanged(self):
        messages = self.messages(self.validate("[w](https://example.com/a) [m](mailto:a@b.c)"))
        self.assertFalse(any("one machine" in m for m in messages))
        messages = self.messages(self.validate("[e](/etc/hosts)"))
        self.assertTrue(any("escapes the skill directory" in m for m in messages))
        self.assertFalse(any("one machine" in m for m in messages))

    def test_hygiene_reports_machine_local_kind(self):
        root = Path(self._tmp.name) / "scope"
        folder = root / "linker"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(
            DOC.format(n="linker", d="Use when linking files together.", b="[x](file:///home/eve/x.md)"),
            encoding="utf-8")
        records = loader.scan_dir(root, annotate_paths=True)
        for record in records:
            record["scope"] = "claude-code"
        report = hygiene.hygiene_report(records, scope="claude-code", home=Path(self._tmp.name))
        broken = [f for f in report["findings"] if f["category"] == "broken-reference"]
        self.assertEqual(len(broken), 1)
        kinds = {issue["kind"] for issue in broken[0]["evidence"]["issues"]}
        self.assertEqual(kinds, {"machine-local"})



class CodexExplicitCliTextTests(unittest.TestCase):
    def test_text_names_explicit_only_skills_even_when_nothing_is_listed(self):
        import contextlib
        import io

        from skillsmgr import cli_handlers

        section = {"status": "no_instances", "explicit_only": {
            "names": [f"q{i}\x1b[2K" for i in range(7)], "total": 9, "omitted": 2}}
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cli_handlers._render_codex_listing_text(section)
        out = buffer.getvalue()
        self.assertNotIn("Codex listing:", out)
        self.assertIn("Codex explicit-only", out)
        self.assertIn("and 4 more", out)
        self.assertNotIn("\x1b", out)


if __name__ == "__main__":
    unittest.main()
