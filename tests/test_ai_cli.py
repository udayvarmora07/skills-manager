"""A14: no-send estimates and fail-closed, versioned CI evidence."""

import contextlib
import http.server
import io
import json
import os
import tempfile
import threading
import tracemalloc
import unittest
from pathlib import Path
from unittest import mock

from skillsmgr import ai, ai_skills, cli, cli_ai, context
from tests.test_ai_features import FakeProvider, SECRET
from tools.ai_fidelity import run as fidelity


class AiCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeProvider)
        cls.thread = threading.Thread(target=cls.provider.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.provider.shutdown()
        cls.provider.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / "data"
        self.base.mkdir(mode=0o700)
        self.data = self.base / "skills-manager"
        self.data.mkdir(mode=0o700)
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.root),
                                               "SKILLS_MANAGER_DATA": str(self.base)})
        self.env.start()
        self.addCleanup(self.env.stop)
        previous = context.ACTIVE_STORE.get()
        context.set_active_store(None)
        self.addCleanup(context.set_active_store, previous)
        self.skill = self.root / ".claude/skills/sql-tuning/SKILL.md"
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text("---\nname: sql-tuning\ndescription: SQL queries database tuning\n---\nBody\n")
        self.configure()
        self.prompts = [{"text": "SQL database queries tuning", "expected": "sql-tuning"},
                        {"text": "brew some coffee", "expected": None}]
        ai_skills.save_prompt_set(self.data, {"scope": "claude-code", "prompts": self.prompts})
        FakeProvider.calls = []
        FakeProvider.mode = "normal"

    def configure(self, **extra):
        ai.save_settings(self.data, {"provider": "custom", "model": "fake-model",
                                     "api_key": SECRET,
                                     "base_url": f"http://127.0.0.1:{self.provider.server_port}/v1",
                                     **extra})

    def invoke(self, *flags):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", str(self.base), "ai", "trigger-test",
                             "--scope", "claude-code", "--saved", "--json", *flags])
        return code, json.loads(out.getvalue()), err.getvalue()

    def baseline(self):
        code, report, err = self.invoke("--run", "--seed", "17", "--repeats", "2")
        self.assertEqual((code, err), (0, ""))
        return report["result"]["run_id"]

    def mutate_baseline(self, run_id, change):
        path = self.data / "ai/runs" / f"{run_id}.json"
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))

    def test_default_estimate_sends_nothing_and_does_not_create_index_or_run(self):
        code, report, err = self.invoke("--seed", "17")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["status"], "estimate")
        self.assertEqual(report["result"]["seed"], 17)
        self.assertEqual(report["result"]["run"]["calls"], 0)
        self.assertEqual(FakeProvider.calls, [])
        self.assertFalse((self.data / "skills-manager.db").exists())
        self.assertFalse((self.data / "ai/runs").exists())
        self.assertFalse((self.data / "ai/usage.jsonl").exists())

    def test_seed_controls_request_order_and_provenance_is_saved_without_keys(self):
        other = self.skill.parent.parent / "git-release/SKILL.md"
        other.parent.mkdir()
        other.write_text("---\nname: git-release\ndescription: git release tagging\n---\nBody\n")
        first = self.baseline()
        requests = [r["body"] for r in FakeProvider.calls]
        FakeProvider.calls = []
        code, report, _ = self.invoke("--run", "--seed", "17", "--repeats", "2")
        self.assertEqual(code, 0)
        self.assertEqual(requests, [r["body"] for r in FakeProvider.calls])
        stored = ai_skills.read_run(self.data, first)
        self.assertEqual(stored["provenance"], report["result"]["provenance"])
        self.assertEqual(len(stored["provenance"]["listing_sha256"]), 64)
        self.assertNotIn(SECRET, json.dumps(report) + json.dumps(stored))

    def test_gate_without_baseline_fails_before_spending(self):
        code, report, _ = self.invoke("--run", "--fail-on-regression")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "ai-baseline-missing")
        self.assertEqual(FakeProvider.calls, [])

    def test_gate_passes_complete_comparable_runs_and_reports_counts(self):
        baseline = self.baseline()
        code, report, err = self.invoke("--run", "--seed", "17", "--repeats", "2",
                                        "--baseline", baseline, "--fail-on-regression")
        self.assertEqual((code, err), (0, ""))
        comparison = report["comparison"]
        self.assertEqual(comparison["status"], "compared")
        self.assertEqual(comparison["baseline_run_id"], baseline)
        self.assertFalse(comparison["regressed"])
        self.assertEqual(comparison["metrics"][0]["before"], {"hits": 2, "answers": 2})

    def test_gate_detects_skill_recall_loss_with_changed_listing(self):
        baseline = self.baseline()
        self.skill.write_text("---\nname: sql-tuning\ndescription: Handles stuff\n---\nBody\n")
        code, report, _ = self.invoke("--run", "--seed", "17", "--repeats", "2",
                                     "--baseline", baseline, "--fail-on-regression")
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "regression")
        self.assertTrue(report["comparison"]["listing_changed"])
        self.assertTrue(report["comparison"]["regressed"])
        self.assertEqual(report["comparison"]["metrics"][0]["after"]["hits"], 0)
        self.assertEqual(len(FakeProvider.calls), 4)

    def test_gate_detects_near_miss_false_trigger_loss(self):
        baseline = self.baseline()
        self.skill.write_text("---\nname: sql-tuning\ndescription: SQL queries database tuning brew coffee\n---\nBody\n")
        code, report, _ = self.invoke("--run", "--seed", "17", "--repeats", "2",
                                     "--baseline", baseline, "--fail-on-regression")
        self.assertEqual(code, 1)
        metric = next(m for m in report["comparison"]["metrics"] if m["expected"] is None)
        self.assertTrue(metric["regressed"])

    def test_changed_prompt_model_seed_repeats_or_endpoint_refuses_before_spending(self):
        baseline = self.baseline()
        for flags, config in [([], {"model": "other-model"}),
                              (["--seed", "18", "--repeats", "2"], {}),
                              (["--seed", "17", "--repeats", "1"], {}),
                              ([], {"base_url": "https://example.invalid/v1"})]:
            with self.subTest(flags=flags, config=config):
                self.configure(**config)
                FakeProvider.calls = []
                selected = flags or ["--seed", "17", "--repeats", "2"]
                code, report, _ = self.invoke("--run", "--baseline", baseline,
                                             "--fail-on-regression", *selected)
                self.assertEqual(code, 1)
                self.assertEqual(report["error"]["code"], "ai-baseline-incomparable")
                self.assertEqual(FakeProvider.calls, [])
        self.configure()
        ai_skills.save_prompt_set(self.data, {"scope": "claude-code", "replace": True,
                                              "prompts": self.prompts[:1]})
        code, report, _ = self.invoke("--run", "--seed", "17", "--repeats", "2",
                                     "--baseline", baseline, "--fail-on-regression")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "ai-baseline-incomparable")
        self.assertEqual(FakeProvider.calls, [])

    def test_incomplete_corrupt_and_legacy_baselines_cannot_pass_gate(self):
        baseline = self.baseline()
        path = self.data / "ai/runs" / f"{baseline}.json"
        original = path.read_text()
        for change in (lambda r: r.update(missing_answers=1),
                       lambda r: r.update(invalid_answers=1),
                       lambda r: r.update(status="disconnected"),
                       lambda r: r.pop("provenance"),
                       lambda r: r["prompts"][0].update(answered=1),
                       lambda r: r["prompts"][0].update(choices={"made-up": 2}),
                       lambda r: r["prompts"][0].update(choices={"sql-tuning": True}),
                       lambda r: r.update(prompts=[])):
            with self.subTest(change=change):
                path.write_text(original)
                self.mutate_baseline(baseline, change)
                FakeProvider.calls = []
                code, report, _ = self.invoke("--run", "--seed", "17", "--repeats", "2",
                                             "--baseline", baseline, "--fail-on-regression")
                self.assertEqual(code, 1)
                self.assertEqual(report["error"]["code"], "ai-baseline-incomparable")
                self.assertEqual(FakeProvider.calls, [])

    def test_deleted_expected_skill_is_not_silently_skipped(self):
        self.skill.rename(self.skill.with_suffix(".md.disabled"))
        other = self.skill.parent.parent / "git-release/SKILL.md"
        other.parent.mkdir()
        other.write_text("---\nname: git-release\ndescription: git release tagging\n---\nBody\n")
        code, report, _ = self.invoke("--run")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "ai-input")
        self.assertEqual(FakeProvider.calls, [])

    def test_corrupt_saved_prompt_sets_are_clean_errors(self):
        path = self.data / "ai/prompt-sets/claude-code.json"
        for value in ("[]", '{"prompts":[null]}', '{"prompts":{}}', "[" * 2000):
            with self.subTest(value=value[:30]):
                path.write_text(value)
                code, report, err = self.invoke("--run")
                self.assertEqual(code, 1)
                self.assertIn("error", report)
                self.assertNotIn("unexpected error", err)
                self.assertEqual(FakeProvider.calls, [])

    def test_no_provider_configuration_is_a_structured_no_send_error(self):
        (self.data / "ai/settings.json").unlink()
        code, report, _ = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "ai-not-configured")
        self.assertEqual(FakeProvider.calls, [])

    def test_invalid_or_missing_current_answers_fail_even_without_a_baseline_gate(self):
        for answer in ({"answers": []}, {"answers": [{"id": "p1", "skill": "made-up"},
                                                     {"id": "p2", "skill": None}]}):
            with self.subTest(answer=answer), mock.patch.object(FakeProvider, "_answer", return_value=answer):
                code, report, _ = self.invoke("--run")
                self.assertEqual(code, 1)
                self.assertEqual(report["status"], "incomplete")
                self.assertNotEqual(report["comparison"]["status"], "compared")

    def test_empty_and_oversized_saved_sets_refuse_without_calls(self):
        path = self.data / "ai/prompt-sets/claude-code.json"
        for prompts in ([], self.prompts * 61, self.prompts * 5000):
            with self.subTest(size=len(prompts)):
                path.write_text(json.dumps({"scope": "claude-code", "prompts": prompts}))
                code, report, _ = self.invoke("--run")
                self.assertEqual(code, 1)
                self.assertEqual(report["error"]["code"], "ai-input")
                self.assertEqual(FakeProvider.calls, [])

    def test_whole_saved_run_budget_is_checked_before_the_first_call(self):
        prompts = [{"text": "SQL database tuning " + ("query " * 45) + str(i),
                    "expected": "sql-tuning"} for i in range(20)]
        ai_skills.save_prompt_set(self.data, {"scope": "claude-code", "replace": True,
                                              "prompts": prompts})
        code, report, _ = self.invoke()
        self.assertEqual(code, 0)
        estimate = report["result"]["run"]["estimated_input_tokens"]
        self.assertGreater(estimate, 2000)
        self.configure(max_run_tokens=int(estimate * 0.75))
        code, report, _ = self.invoke("--run")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "ai-budget")
        self.assertEqual(FakeProvider.calls, [])

    def test_single_prompt_and_implicit_latest_baseline_work(self):
        ai_skills.save_prompt_set(self.data, {"scope": "claude-code", "replace": True,
                                              "prompts": self.prompts[:1]})
        baseline = self.baseline()
        code, report, _ = self.invoke("--run", "--seed", "17", "--repeats", "2", "--fail-on-regression")
        self.assertEqual(code, 0)
        self.assertEqual(report["comparison"]["baseline_run_id"], baseline)

    def test_baseline_identifiers_cannot_escape_run_directory(self):
        code, report, _ = self.invoke("--run", "--baseline", "../../settings")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "ai-input")
        self.assertEqual(FakeProvider.calls, [])

    def test_malformed_newest_history_is_not_skipped_to_an_older_green_baseline(self):
        self.baseline()
        newer = self.data / "ai/runs/trigger-test-20990101T000000Z-12345678.json"
        newer.write_text("{")
        os.utime(newer, (4_070_908_800, 4_070_908_800))
        FakeProvider.calls = []
        code, report, _ = self.invoke("--run", "--seed", "17", "--repeats", "2", "--fail-on-regression")
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "error")
        self.assertEqual(FakeProvider.calls, [])

    def test_preflight_and_send_use_one_prompt_and_configuration_snapshot(self):
        baseline = self.baseline()
        validate = cli_ai._validate_baseline
        changed = False

        def change_after_validation(previous, current):
            nonlocal changed
            result = validate(previous, current)
            if not changed:
                changed = True
                self.configure(model="changed-after-preflight")
                ai_skills.save_prompt_set(self.data, {"scope": "claude-code", "replace": True,
                                                      "prompts": self.prompts[:1]})
            return result

        FakeProvider.calls = []
        with mock.patch.object(cli_ai, "_validate_baseline", side_effect=change_after_validation):
            code, report, _ = self.invoke("--run", "--seed", "17", "--repeats", "2",
                                         "--baseline", baseline, "--fail-on-regression")
        self.assertEqual(code, 0)
        self.assertEqual(report["result"]["run"]["model"], "fake-model")
        self.assertEqual(len(report["result"]["prompts"]), 2)
        self.assertTrue(all(call["body"]["model"] == "fake-model" for call in FakeProvider.calls))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_linked_saved_prompt_file_is_refused_before_transmission(self):
        path = self.data / "ai/prompt-sets/claude-code.json"
        other = self.root / "other-data.json"
        path.rename(other)
        try:
            path.symlink_to(other)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable for this user")
        code, report, _ = self.invoke("--run")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "ai-input")
        self.assertEqual(FakeProvider.calls, [])

    def test_baseline_reads_are_bounded_and_refuse_non_regular_files(self):
        baseline = self.baseline()
        path = self.data / "ai/runs" / f"{baseline}.json"
        with path.open("wb") as stream:
            stream.truncate(32 * 1024 * 1024)
        FakeProvider.calls = []
        tracemalloc.start()
        try:
            code, report, _ = self.invoke("--run", "--baseline", baseline, "--fail-on-regression")
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 8 * 1024 * 1024, "baseline reading must have a bounded allocation")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"]["code"], "ai-input")
        self.assertEqual(FakeProvider.calls, [])
        if hasattr(os, "mkfifo"):
            path.unlink()
            os.mkfifo(path)
            code, report, _ = self.invoke("--run", "--baseline", baseline, "--fail-on-regression")
            self.assertEqual(code, 1)
            self.assertEqual(report["error"]["code"], "ai-input")

    def test_supported_unicode_prompt_sets_and_listing_snapshots_round_trip(self):
        prompts = [{"text": str(i) + "\U0001f9e0" * 600, "expected": f"skill-{i // 20}"}
                   for i in range(500)]
        ai_skills.save_prompt_set(self.data, {"scope": "claude-code", "replace": True,
                                              "prompts": prompts})
        self.assertEqual(len(ai_skills.read_prompt_set(self.data, "claude-code")["prompts"]), 500)
        listing = [{"name": f"skill-{i}", "description": "\U0001f9e0" * ai_skills.DESCRIPTION_CAP}
                   for i in range(ai_skills.MAX_LISTED)]
        result = {"kind": "trigger-test", "listing_snapshot": listing, "run": {"model": "fake-model"}}
        run_id = ai_skills._save_run(self.data, result)
        self.assertEqual(ai_skills.read_run(self.data, run_id), result)
        observed, _ = fidelity._read_json(str(self.data / "ai/runs" / f"{run_id}.json"))
        self.assertEqual(observed, result)

    def test_human_output_sanitizes_model_labels(self):
        path = self.data / "ai/settings.json"
        config = json.loads(path.read_text())
        config["model"] = "fake\x1b[2Jmodel"
        path.write_text(json.dumps(config))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", str(self.base), "ai", "trigger-test",
                             "--scope", "claude-code", "--saved"])
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out.getvalue())
        self.assertNotIn(SECRET, out.getvalue() + err.getvalue())

    def test_gate_requires_explicit_run_and_seed_and_repeats_are_bounded(self):
        for flags in (["--fail-on-regression"], ["--seed", "-1"], ["--seed", "4294967296"],
                      ["--repeats", "0"], ["--repeats", "6"]):
            with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    self.invoke(*flags)
                self.assertEqual(raised.exception.code, 2)
        self.assertEqual(FakeProvider.calls, [])


if __name__ == "__main__":
    unittest.main()
