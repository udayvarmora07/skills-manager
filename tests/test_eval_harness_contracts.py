"""Contract tests for the file-based, advisory-only eval harness."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from skillsmgr import cli, evals


def _write_evals(skill_dir: Path, cases, skill_name="demo") -> Path:
    evals_dir = skill_dir / evals.EVALS_DIRNAME
    evals_dir.mkdir(parents=True, exist_ok=True)
    path = evals_dir / evals.EVALS_FILENAME
    path.write_text(json.dumps({"skill_name": skill_name, "evals": cases}), encoding="utf-8")
    return path


class LoadCasesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.skill = Path(self._tmp.name) / "demo"
        self.skill.mkdir()

    def test_missing_file_is_not_an_error(self):
        report = evals.load_cases(self.skill)
        self.assertFalse(report["present"])
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["cases"], [])

    def test_valid_file_is_normalized(self):
        _write_evals(self.skill, [
            {"id": 1, "prompt": "do the thing", "expected_output": "the thing done",
             "files": ["evals/files/input.csv"],
             "assertions": [{"type": "contains", "value": "done"}]},
        ])
        (self.skill / "evals" / "files").mkdir(parents=True)
        (self.skill / "evals" / "files" / "input.csv").write_text("a,b\n", encoding="utf-8")
        report = evals.load_cases(self.skill)
        self.assertTrue(report["present"])
        self.assertEqual(report["skill_name"], "demo")
        self.assertEqual(report["issues"], [])
        case = report["cases"][0]
        self.assertEqual(case["id"], 1)
        self.assertEqual(case["files"], ["evals/files/input.csv"])
        self.assertEqual(len(case["assertions"]), 1)

    def test_case_ids_default_to_position(self):
        _write_evals(self.skill, [{"prompt": "a", "expected_output": "b"}])
        report = evals.load_cases(self.skill)
        self.assertEqual([case["id"] for case in report["cases"]], [1])

    def test_malformed_documents_report_errors_without_raising(self):
        for body in ("{not json", "[1,2,3]", '{"evals": []}', '{"evals": "nope"}'):
            with self.subTest(body=body):
                (self.skill / "evals").mkdir(exist_ok=True)
                (self.skill / "evals" / "evals.json").write_text(body, encoding="utf-8")
                report = evals.load_cases(self.skill)
                self.assertEqual([issue["level"] for issue in report["issues"]], ["error"])
                self.assertEqual(report["cases"], [])

    def test_case_level_errors_and_duplicate_ids(self):
        _write_evals(self.skill, [
            {"id": 1, "prompt": "ok", "expected_output": "fine"},
            {"id": 1, "prompt": "dupe", "expected_output": "fine"},
            {"id": 2, "prompt": "", "expected_output": "fine"},
            {"id": 3, "prompt": "x", "expected_output": "y", "files": ["../escape.csv"]},
        ])
        report = evals.load_cases(self.skill)
        messages = [issue["message"] for issue in report["issues"]]
        self.assertEqual(len(report["cases"]), 1)
        self.assertTrue(any("duplicate id" in message for message in messages))
        self.assertTrue(any("prompt must be a non-empty string" in message for message in messages))
        self.assertTrue(any("stay inside the skill directory" in message for message in messages))

    def test_missing_input_file_is_a_warning(self):
        _write_evals(self.skill, [
            {"id": 1, "prompt": "x", "expected_output": "y", "files": ["evals/files/gone.csv"]},
        ])
        report = evals.load_cases(self.skill)
        self.assertEqual([issue["level"] for issue in report["issues"]], ["warning"])
        self.assertEqual(len(report["cases"]), 1)

    def test_oversized_case_count_is_rejected(self):
        _write_evals(self.skill, [
            {"id": index, "prompt": "x", "expected_output": "y"}
            for index in range(evals.MAX_CASES + 1)
        ])
        report = evals.load_cases(self.skill)
        self.assertEqual([issue["level"] for issue in report["issues"]], ["error"])
        self.assertIn("more than", report["issues"][0]["message"])

    def test_assertion_validation(self):
        for assertion, expected in (
            ({"type": "unknown", "value": "x"}, "unsupported assertion type"),
            ({"type": "regex", "value": "("}, "invalid regex assertion pattern"),
            ({"type": "contains"}, "must be a non-empty string"),
            ({"type": "regex", "value": "a" * (evals.MAX_PATTERN_LENGTH + 1)}, "exceeds"),
        ):
            with self.subTest(assertion=assertion):
                _write_evals(self.skill, [
                    {"id": 1, "prompt": "x", "expected_output": "y", "assertions": [assertion]},
                ])
                report = evals.load_cases(self.skill)
                self.assertEqual([issue["level"] for issue in report["issues"]], ["error"])
                self.assertIn(expected, report["issues"][0]["message"])


class GradingTests(unittest.TestCase):
    def _case(self, assertions):
        return {"id": 1, "prompt": "p", "expected_output": "e", "assertions": assertions}

    def test_equals_contains_and_not_contains(self):
        cases = [
            ("equals", "Hello   World", "hello world", True),
            ("equals", "Hello", "Goodbye", False),
            ("contains", "the BAR chart", "bar", True),
            ("not_contains", "I cannot help", "I cannot", False),
        ]
        for kind, output, value, expected in cases:
            with self.subTest(kind=kind, output=output):
                case = self._case([{"type": kind, "value": value}])
                result = evals.grade_output(case, output)
                self.assertEqual(result["passed"], 1 if expected else 0)
                self.assertTrue(result["graded"])

    def test_case_sensitive_option(self):
        case = self._case([{"type": "contains", "value": "Bar", "case_sensitive": True}])
        self.assertEqual(evals.grade_output(case, "bar chart")["passed"], 0)
        self.assertEqual(evals.grade_output(case, "Bar chart")["passed"], 1)

    def test_regex_and_is_json(self):
        case = self._case([{"type": "regex", "value": r"\b\d+\b"}])
        self.assertEqual(evals.grade_output(case, "cleaned 4 rows")["passed"], 1)
        self.assertEqual(evals.grade_output(case, "no digits here")["passed"], 0)
        plain = self._case([{"type": "is_json"}])
        self.assertEqual(evals.grade_output(plain, '{"a": 1}')["passed"], 1)
        self.assertEqual(evals.grade_output(plain, "not json")["passed"], 0)
        valued = self._case([{"type": "is_json", "value": {"a": 1}}])
        self.assertEqual(evals.grade_output(valued, '{"a": 1}')["passed"], 1)
        self.assertEqual(evals.grade_output(valued, '{"a": 2}')["passed"], 0)

    def test_case_without_assertions_is_ungraded(self):
        result = evals.grade_output(self._case([]), "anything")
        self.assertFalse(result["graded"])
        self.assertIsNone(result["passed"])
        self.assertEqual(result["total"], 0)

    def test_output_bounds(self):
        with self.assertRaises(ValueError):
            evals.grade_output(self._case([]), "x" * (evals.MAX_OUTPUT_TEXT + 1))
        with self.assertRaises(ValueError):
            evals.grade_output(self._case([]), 5)


class WorkspaceTests(unittest.TestCase):
    def test_workspace_defaults_live_outside_the_skills_tree(self):
        data_dir = Path("/data")
        self.assertEqual(
            evals.workspace_for(data_dir, "demo"),
            Path("/data/evals/demo-workspace"),
        )
        self.assertEqual(
            evals.workspace_beside(Path("/repo/demo")),
            Path("/repo/demo-workspace"),
        )

    def test_workspace_rejects_a_traversal_name(self):
        with self.assertRaises(ValueError):
            evals.workspace_for(Path("/data"), "../escape")

    def test_iteration_and_directory_validation(self):
        with self.assertRaises(ValueError):
            evals.iteration_dir(Path("/w"), 0)
        with self.assertRaises(ValueError):
            evals.iteration_dir(Path("/w"), True)
        with self.assertRaises(ValueError):
            evals.case_dir(Path("/w"), 1, "../escape")
        with self.assertRaises(ValueError):
            evals.variant_dir(Path("/w"), 1, "eval-x", "wrong_variant")
        self.assertEqual(
            evals.variant_dir(Path("/w"), 2, "eval-x", "with_skill"),
            Path("/w/iteration-2/eval-x/with_skill"),
        )

    def test_workspace_for_dir_keeps_the_store_skills_tree_clean(self):
        data_dir = Path("/data")
        self.assertEqual(
            evals.workspace_for_dir(Path("/data/skills/demo"), data_dir, "demo"),
            Path("/data/evals/demo-workspace"),
        )
        self.assertEqual(
            evals.workspace_for_dir(Path("/repo/demo"), data_dir, "demo"),
            Path("/repo/demo-workspace"),
        )

    def test_case_slugs_are_derived_and_deduplicated(self):
        cases = [
            {"id": 1, "prompt": "I have a CSV of monthly sales!", "slug": None},
            {"id": 2, "prompt": "I have a CSV of monthly sales!", "slug": None},
            {"id": 3, "prompt": "x", "slug": "Top Months Chart"},
        ]
        self.assertEqual(
            evals.case_slugs(cases),
            ["eval-i-have-a-csv-of-monthly", "eval-i-have-a-csv-of-monthly-2", "eval-top-months-chart"],
        )

    def test_case_slugs_fall_back_for_unnamable_prompts(self):
        self.assertEqual(evals.case_slugs([{"id": 7, "prompt": "!!!", "slug": None}]), ["eval-case-7"])


class ScoreAndRecordTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.cases = [
            {"id": 1, "prompt": "top months", "expected_output": "chart",
             "assertions": [{"type": "contains", "value": "bar chart"}]},
            {"id": 2, "prompt": "clean csv", "expected_output": "count", "assertions": []},
        ]
        self.runs = [
            {"case": 1, "variant": "with_skill", "output": "bar chart of top months", "duration_ms": 900, "tokens": 120},
            {"case": 1, "variant": "without_skill", "output": "no idea"},
            {"case": 2, "variant": "with_skill", "output": "cleaned"},
        ]

    def test_score_runs_reports_a_baseline_delta(self):
        scored = evals.score_runs(self.cases, self.runs)
        benchmark = scored["benchmark"]
        self.assertEqual(benchmark["variants"]["with_skill"]["cases_passed"], 1)
        self.assertEqual(benchmark["variants"]["with_skill"]["pass_rate"], 1.0)
        self.assertEqual(benchmark["variants"]["without_skill"]["pass_rate"], 0.0)
        self.assertEqual(benchmark["delta"], 1.0)
        self.assertEqual(benchmark["ungraded_cases"], 1)
        self.assertTrue(benchmark["advisory"])
        self.assertIn("advisory-only", benchmark["policy"])

    def test_invalid_runs_are_rejected(self):
        for runs, expected in (
            ([{"case": 99, "output": "x"}], "unknown eval case"),
            ([{"case": 1, "variant": "nope", "output": "x"}], "unsupported variant"),
            ([{"case": 1}], "output must be a string"),
            ([{"case": 1, "output": "x", "tokens": -1}], "non-negative"),
            ([{"case": 1, "output": "x" * (evals.MAX_OUTPUT_TEXT + 1)}], "exceeds"),
            ("nope", "non-empty list"),
            ([], "non-empty list"),
        ):
            with self.subTest(runs=str(runs)[:40]):
                with self.assertRaises(ValueError) as caught:
                    evals.score_runs(self.cases, runs)
                self.assertIn(expected, str(caught.exception))

    def test_record_runs_writes_the_documented_workspace_layout(self):
        workspace = self.root / "workspace"
        recorded = evals.record_runs(workspace, 1, self.cases, self.runs)
        iteration = workspace / "iteration-1"
        self.assertEqual(recorded["workspace"], str(iteration))
        self.assertTrue((iteration / "benchmark.json").is_file())
        graded = iteration / "eval-top-months" / "with_skill"
        self.assertEqual((graded / "outputs" / "output.txt").read_text(), "bar chart of top months")
        self.assertTrue((graded / "grading.json").is_file())
        timing = json.loads((graded / "timing.json").read_text())
        self.assertEqual(timing["duration_ms"], 900)
        self.assertEqual(timing["tokens"], 120)
        self.assertTrue(timing["recorded_at"].endswith("Z"))
        ungraded = iteration / "eval-clean-csv" / "with_skill" / "grading.json"
        self.assertFalse(json.loads(ungraded.read_text())["graded"])
        self.assertEqual(
            sorted(path.name for path in iteration.rglob("*.skillsmgr-tmp")), []
        )
        self.assertEqual(
            json.loads((iteration / "benchmark.json").read_text())["delta"], 1.0
        )

    def test_record_runs_never_touches_skill_files_or_the_index(self):
        from skillsmgr.store import Store

        data_dir = self.root / "data"
        store = Store(data_dir=data_dir)
        store.init_db()
        store.create("demo", "Use this when demoing")
        skill_dir = data_dir / "skills" / "demo"
        _write_evals(skill_dir, [{"id": 1, "prompt": "p", "expected_output": "e",
                                  "assertions": [{"type": "contains", "value": "x"}]}])
        before_skill = (skill_dir / "SKILL.md").read_bytes()
        before_rows = store.list()
        before_files = sorted(
            str(path.relative_to(data_dir))
            for path in data_dir.rglob("*")
            if path.is_file()
        )
        workspace = evals.workspace_for(data_dir, "demo")
        evals.record_runs(workspace, 1, evals.load_cases(skill_dir)["cases"], [
            {"case": 1, "variant": "with_skill", "output": "x marks the spot"},
        ])
        self.assertEqual((skill_dir / "SKILL.md").read_bytes(), before_skill)
        self.assertEqual(store.list(), before_rows)
        after_files = [
            str(path.relative_to(data_dir))
            for path in data_dir.rglob("*")
            if path.is_file() and not str(path).startswith(str(workspace))
        ]
        self.assertEqual(sorted(after_files), before_files)


class EvalCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["SKILLS_MANAGER_DATA"] = self._tmp.name

    def tearDown(self):
        if self._old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = self._old_data

    def invoke(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", self._tmp.name, *argv])
        return code, out.getvalue(), err.getvalue()

    def _skill_with_evals(self, name="demo"):
        self.invoke(["create", name, "-d", "Use this when demoing"])
        skill_dir = Path(self._tmp.name) / "skills-manager" / "skills" / name
        _write_evals(skill_dir, [
            {"id": 1, "prompt": "do the demo", "expected_output": "demo done",
             "assertions": [{"type": "contains", "value": "demo"}]},
        ], skill_name=name)
        return skill_dir

    def test_validate_without_evals_flag_keeps_the_historical_output(self):
        self._skill_with_evals()
        code, out, _ = self.invoke(["validate", "demo"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertNotIn("evals", out)
        self.assertEqual(out.strip(), "demo: ok")

    def test_validate_evals_reports_advisory_status(self):
        self._skill_with_evals()
        code, out, err = self.invoke(["validate", "demo", "--evals"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("1 case(s) in evals/evals.json (advisory-only)", out)
        self.assertIn("demo-workspace", out)
        self.assertEqual(err, "")

    def test_validate_evals_run_records_results_and_stays_advisory(self):
        skill_dir = self._skill_with_evals()
        before = (skill_dir / "SKILL.md").read_bytes()
        runs = Path(self._tmp.name) / "runs.json"
        runs.write_text(json.dumps({
            "iteration": 3,
            "runs": [
                {"case": 1, "variant": "with_skill", "output": "demo complete"},
                {"case": 1, "variant": "without_skill", "output": "no"},
            ],
        }), encoding="utf-8")
        code, out, err = self.invoke(["validate", "demo", "--evals-run", str(runs)])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("with_skill 1/1 case(s)", out)
        self.assertIn("with_skill - without_skill = +1.0000", out)
        benchmark = Path(self._tmp.name) / "skills-manager" / "evals" / "demo-workspace" / "iteration-3" / "benchmark.json"
        self.assertTrue(benchmark.is_file())
        self.assertEqual(err, "")
        self.assertEqual((skill_dir / "SKILL.md").read_bytes(), before)

    def test_validate_evals_run_json_shape(self):
        self._skill_with_evals()
        runs = Path(self._tmp.name) / "runs.json"
        runs.write_text(json.dumps([
            {"case": 1, "variant": "with_skill", "output": "demo"},
        ]), encoding="utf-8")
        code, out, _ = self.invoke(["validate", "demo", "--evals-run", str(runs), "--json"])
        self.assertEqual(code, cli.EXIT_OK)
        payload = json.loads(out)
        self.assertTrue(payload["valid"])
        report = payload["skills"][0]["evals"]
        self.assertEqual(report["recording"]["iteration"], 1)
        self.assertEqual(report["recording"]["benchmark"]["variants"]["with_skill"]["pass_rate"], 1.0)

    def test_validate_workspace_override(self):
        self._skill_with_evals()
        override = Path(self._tmp.name) / "custom-workspace"
        runs = Path(self._tmp.name) / "runs.json"
        runs.write_text(json.dumps([{"case": 1, "output": "demo"}]), encoding="utf-8")
        code, out, _ = self.invoke([
            "validate", "demo", "--evals-run", str(runs), "--workspace", str(override),
        ])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertTrue((override / "iteration-1" / "benchmark.json").is_file())
        self.assertIn(str(override), out)

    def test_validate_bad_runs_input_fails_cleanly(self):
        self._skill_with_evals()
        code, out, err = self.invoke(["validate", "demo", "--evals-run", str(Path(self._tmp.name) / "missing.json")])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("eval runs file not found", err)
        self.assertNotIn("Traceback", err)
        bad = Path(self._tmp.name) / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        code, _, err = self.invoke(["validate", "demo", "--evals-run", str(bad)])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("not valid JSON", err)

    def test_validate_evals_run_requires_a_single_target(self):
        self._skill_with_evals()
        self._skill_with_evals("demo-two")
        runs = Path(self._tmp.name) / "runs.json"
        runs.write_text(json.dumps([{"case": 1, "output": "demo"}]), encoding="utf-8")
        code, _, err = self.invoke(["validate", "demo", "--all", "--evals-run", str(runs)])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertIn("exactly one skill", err)

    def test_malformed_evals_file_stays_advisory(self):
        skill_dir = self._skill_with_evals()
        (skill_dir / "evals" / "evals.json").write_text("{not json", encoding="utf-8")
        code, out, _ = self.invoke(["validate", "demo", "--evals"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("evals.json is unreadable", out)

    def test_validate_path_on_a_store_skill_keeps_workspaces_out_of_skills(self):
        skill_dir = self._skill_with_evals()
        runs = Path(self._tmp.name) / "runs.json"
        runs.write_text(json.dumps([{"case": 1, "output": "demo"}]), encoding="utf-8")
        code, out, err = self.invoke(["validate", "--path", str(skill_dir), "--evals-run", str(runs)])
        self.assertEqual(code, cli.EXIT_OK)
        skills_root = Path(self._tmp.name) / "skills-manager" / "skills"
        self.assertEqual(
            [path.name for path in skills_root.iterdir() if path.is_dir()], ["demo"]
        )
        self.assertTrue(
            (Path(self._tmp.name) / "skills-manager" / "evals" / "demo-workspace" / "iteration-1" / "benchmark.json").is_file()
        )
        self.assertIn("demo-workspace", out)

    def test_validate_path_outside_the_store_uses_the_beside_workspace(self):
        skill_dir = Path(self._tmp.name) / "checkout" / "demo"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Use this when demoing\n---\n# Demo\n",
            encoding="utf-8",
        )
        _write_evals(skill_dir, [
            {"id": 1, "prompt": "demo", "expected_output": "done",
             "assertions": [{"type": "contains", "value": "demo"}]},
        ])
        runs = Path(self._tmp.name) / "runs.json"
        runs.write_text(json.dumps([{"case": 1, "output": "demo"}]), encoding="utf-8")
        code, out, _ = self.invoke(["validate", "--path", str(skill_dir), "--evals-run", str(runs)])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertTrue((Path(self._tmp.name) / "checkout" / "demo-workspace" / "iteration-1" / "benchmark.json").is_file())
        self.assertIn("demo-workspace", out)

    def test_help_lists_the_new_flags(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as exit_info:
            cli.main(["validate", "--help"])
        self.assertEqual(exit_info.exception.code, 0)
        for flag in ("--evals", "--evals-run", "--workspace"):
            self.assertIn(flag, out.getvalue())


class EvalRestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["SKILLS_MANAGER_DATA"] = self._tmp.name
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        self.store = Store(data_dir=self._tmp.name)
        self.store.init_db()
        self.store.create("demo", "Use this when demoing")
        self.skill_dir = Path(self._tmp.name) / "skills" / "demo"
        _write_evals(self.skill_dir, [
            {"id": 1, "prompt": "demo", "expected_output": "done",
             "assertions": [{"type": "contains", "value": "demo"}]},
        ])
        self.server = WebAppServer(self.store, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self._old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = self._old_data

    def _stop_server(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.httpd.server_close()

    def post(self, path, payload):
        request = Request(
            self.server.url + path,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request) as response:
            return json.loads(response.read())

    def test_validate_without_evals_keeps_the_historical_shape(self):
        payload = self.post("api/validate", {"name": "demo"})
        self.assertEqual(sorted(payload), ["issues", "valid"])
        self.assertFalse((Path(self._tmp.name) / "evals").exists())

    def test_validate_reports_evals_read_only(self):
        before = (self.skill_dir / "SKILL.md").read_bytes()
        payload = self.post("api/validate", {"name": "demo", "evals": True})
        self.assertTrue(payload["evals"]["present"])
        self.assertEqual(len(payload["evals"]["cases"]), 1)
        self.assertNotIn("recording", payload["evals"])
        self.assertEqual((self.skill_dir / "SKILL.md").read_bytes(), before)

    def test_validate_records_runs_inside_the_data_dir(self):
        payload = self.post("api/validate", {
            "name": "demo",
            "runs": [{"case": 1, "variant": "with_skill", "output": "demo!"}],
            "iteration": 2,
        })
        workspace = Path(payload["evals"]["recording"]["workspace"])
        self.assertTrue(workspace.is_dir())
        self.assertTrue(str(workspace).startswith(str(Path(self._tmp.name))))
        self.assertTrue((workspace / "benchmark.json").is_file())

    def test_validate_rejects_unknown_case_and_bad_iteration(self):
        from urllib.error import HTTPError

        for payload, expected in (
            ({"name": "demo", "runs": [{"case": 42, "output": "x"}]}, "unknown eval case"),
            ({"name": "demo", "runs": [{"case": 1, "output": "x"}], "iteration": 0}, "positive integer"),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(HTTPError) as caught:
                    self.post("api/validate", payload)
                self.assertEqual(caught.exception.code, 400)
                self.assertIn(expected, caught.exception.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
