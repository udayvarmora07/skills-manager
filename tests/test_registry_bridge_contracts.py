"""Contract tests for the offline registry bridge (insights + install surfaces).

Hermetic and stdlib-only: no test performs a network request, and one test
pins that the bridge modules import no network client at all.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.request import Request, urlopen

from skillsmgr import cli, insights


class RegistryReferenceTests(unittest.TestCase):
    def test_bare_source_and_github_url_forms(self):
        for spec in ("vercel-labs/skills", "https://github.com/vercel-labs/skills"):
            reference = insights.registry_reference(spec)
            self.assertEqual(reference["source"], "vercel-labs/skills")
            self.assertIsNone(reference["slug"])
            self.assertEqual(reference["form"], "source")
            self.assertIsNone(reference["registry_id"])
            self.assertEqual(reference["audit_links"], [])

    def test_skill_id_and_page_url_forms(self):
        for spec in (
            "vercel-labs/skills/find-skills",
            "https://skills.sh/vercel-labs/skills/find-skills",
            "https://www.skills.sh/vercel-labs/skills/find-skills",
        ):
            reference = insights.registry_reference(spec)
            self.assertEqual(reference["source"], "vercel-labs/skills")
            self.assertEqual(reference["slug"], "find-skills")
            self.assertEqual(reference["registry_id"], "vercel-labs/skills/find-skills")
            self.assertEqual(
                reference["page_url"],
                "https://skills.sh/vercel-labs/skills/find-skills",
            )
            providers = [link["provider"] for link in reference["audit_links"]]
            self.assertEqual(providers, list(insights.REGISTRY_AUDIT_PROVIDERS))
            self.assertTrue(
                all("/security/" in link["url"] for link in reference["audit_links"])
            )

    def test_well_known_source_page_url(self):
        reference = insights.registry_reference("https://skills.sh/mintlify.com/mintlify")
        self.assertEqual(reference["source"], "mintlify.com")
        self.assertEqual(reference["slug"], "mintlify")
        self.assertEqual(reference["page_url"], "https://skills.sh/mintlify.com/mintlify")

    def test_url_query_and_fragment_are_ignored(self):
        reference = insights.registry_reference(
            "https://skills.sh/vercel-labs/skills/find-skills?utm=1#readme"
        )
        self.assertEqual(reference["registry_id"], "vercel-labs/skills/find-skills")

    def test_unsafe_and_unsupported_references_are_rejected(self):
        for bad in (
            "",
            "   ",
            "../evil",
            "owner/../evil",
            "owner/repo/",
            "/owner/repo",
            "owner//repo",
            "owner/repo/skill/extra",
            "owner\\repo",
            "https://evil.example.com/owner/repo",
            "https://github.com/onlyone",
            "sk-" + "a" * 600,
        ):
            with self.subTest(spec=bad):
                with self.assertRaises(ValueError):
                    insights.registry_reference(bad)

    def test_segment_length_cap(self):
        long_segment = "a" * (insights.MAX_REGISTRY_SEGMENT + 1)
        with self.assertRaises(ValueError):
            insights.registry_reference(f"owner/{long_segment}")


class InstallCommandTests(unittest.TestCase):
    def test_argv_matches_the_historical_display_contract(self):
        self.assertEqual(
            insights.install_command_line("vercel-labs/agent-skills", "npx", "global"),
            "npx skills add vercel-labs/agent-skills -g",
        )
        self.assertEqual(
            insights.install_command_line("vercel-labs/agent-skills", "pnpm", "project"),
            "pnpm dlx skills add vercel-labs/agent-skills",
        )
        self.assertEqual(
            insights.install_command_line("vercel-labs/agent-skills", "yarn", "project"),
            "yarn dlx skills add vercel-labs/agent-skills",
        )
        self.assertEqual(
            insights.install_command_line("vercel-labs/agent-skills", "bunx", "global"),
            "bunx skills add vercel-labs/agent-skills -g",
        )
        command = insights.install_command_line(
            "vercel-labs/agent-skills", "npx", "global", ["claude-code"], ["review-pr"],
            True, True,
        )
        self.assertEqual(
            command,
            "npx skills add vercel-labs/agent-skills -g -a claude-code -s review-pr --copy -l",
        )

    def test_cli_display_helper_delegates_to_the_shared_renderer(self):
        from skillsmgr.cli_handlers import install_command_for_display

        self.assertEqual(
            install_command_for_display("vercel-labs/x", "pnpm", "global", None, None, False, False),
            insights.install_command_line("vercel-labs/x", "pnpm", "global"),
        )

    def test_argv_rejects_injection_shapes(self):
        for source in ("--flag", "a;b", "$(whoami)", "a b"):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    insights.install_argv(source)

    def test_cli_rejects_traversal_absolute_and_oversized_install_values(self):
        from skillsmgr.cli_handlers import validated_install_source, validated_install_value

        for label, value in (
            ("source", "../../tmp/pwn"),
            ("source", "/etc/passwd"),
            ("source", "C:/Windows"),
            ("agent", ".."),
            ("agent", "../../tmp/pwn"),
            ("agent", "/etc/passwd"),
            ("agent", "C:/Windows"),
            ("skill", "../secret"),
            ("skill", "x" * 257),
        ):
            with self.subTest(label=label, value=value):
                with self.assertRaises(Exception):
                    if label == "source":
                        validated_install_source(value)
                    else:
                        validated_install_value(label, value)
        for runner in ("unknown", "uvx", ""):
            with self.subTest(runner=runner):
                with self.assertRaises(ValueError):
                    insights.install_argv("owner/repo", runner)
        with self.assertRaises(ValueError):
            insights.install_argv("owner/repo", "npx", "global", None, ["--evil"])


class RegistryBridgePlanTests(unittest.TestCase):
    def test_plan_maps_a_skill_id_onto_the_runner_command(self):
        plan = insights.registry_bridge_plan(
            "vercel-labs/skills/find-skills",
            trust_confirmed=True,
            description="finds skills",
        )
        self.assertEqual(
            plan["install_command"],
            "npx skills add vercel-labs/skills -g -s find-skills",
        )
        self.assertFalse(plan["may_install"])
        self.assertEqual(len(plan["blockers"]), 1)
        self.assertFalse(plan["trust_confirmed"])
        self.assertTrue(plan["trust_requested"])
        self.assertFalse(plan["trust_verified"])
        self.assertEqual(plan["trust_status"], "unverified-offline")
        self.assertEqual(plan["eligibility_status"], "unverified-offline")
        self.assertEqual(plan["hash_status"], "not-provided")
        self.assertFalse(plan["hash_verified"])
        self.assertIn("no registry API request", plan["network"])

    def test_plan_blocks_without_trust_and_reports_provenance(self):
        plan = insights.registry_bridge_plan("vercel-labs/skills")
        self.assertFalse(plan["may_install"])
        self.assertFalse(plan["trust_confirmed"])
        self.assertFalse(plan["trust_requested"])
        self.assertFalse(plan["trust_verified"])
        self.assertEqual(len(plan["blockers"]), 2)
        self.assertIn("trust not confirmed", plan["blockers"][0])
        self.assertIn("eligibility", plan["blockers"][1])
        self.assertEqual(plan["description_status"], "not-provided")
        self.assertIn("authenticated catalog read", plan["provenance_note"])

    def test_plan_reports_a_supplied_hash(self):
        plan = insights.registry_bridge_plan(
            "vercel-labs/skills/find-skills",
            trust_confirmed=True,
            description="finds skills",
            content_hash="a1b2c3",
        )
        self.assertEqual(plan["hash_status"], "unverified-provided")
        self.assertEqual(plan["content_hash"], "a1b2c3")
        self.assertFalse(plan["hash_verified"])
        self.assertIn("authenticated registry read", plan["hash_use"])

    def test_INS_2_offline_plan_never_asserts_verified_trust_eligibility_or_hash(self):
        plan = insights.registry_bridge_plan(
            "vercel-labs/skills/find-skills",
            trust_confirmed=True,
            description="finds skills",
            content_hash="deadbeef",
        )

        self.assertFalse(plan["trust_confirmed"])
        self.assertTrue(plan["trust_requested"])
        self.assertEqual(plan["trust_status"], "unverified-offline")
        self.assertFalse(plan["trust_verified"])
        self.assertFalse(plan["may_install"])
        self.assertEqual(plan["eligibility_status"], "unverified-offline")
        self.assertEqual(plan["hash_status"], "unverified-provided")
        self.assertFalse(plan["hash_verified"])
        self.assertTrue(any("eligibility" in blocker
                            for blocker in plan["blockers"]))

    def test_agent_scope_plan_omits_the_global_flag(self):
        plan = insights.registry_bridge_plan(
            "mintlify.com/mintlify", scope="agents", trust_confirmed=True,
            description="docs",
        )
        self.assertEqual(plan["install_command"], "npx skills add mintlify.com/mintlify")
        self.assertEqual(plan["target_scope"], "agents")


class NoNetworkImportTests(unittest.TestCase):
    def test_bridge_modules_import_no_network_client(self):
        banned = {"urllib.request", "http.client", "socket", "ssl", "requests"}
        for module in ("insights.py", "evals.py", "web_upload.py"):
            path = Path(insights.__file__).parent / module
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            self.assertFalse(imported & banned, f"{module} imports {imported & banned}")


class InstallPreviewCliTests(unittest.TestCase):
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

    def test_preview_is_informational_and_executes_nothing(self):
        code, out, err = self.invoke(["install", "--preview", "vercel-labs/skills/find-skills"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertIn("registry preview (offline", out)
        self.assertIn("https://skills.sh/vercel-labs/skills/find-skills", out)
        self.assertIn("npx skills add vercel-labs/skills -g -s find-skills", out)
        self.assertIn("trust not confirmed", out)
        self.assertNotIn("running:", out)
        self.assertEqual(err, "")

    def test_preview_json_shape(self):
        code, out, _ = self.invoke([
            "install", "--preview", "vercel-labs/skills/find-skills",
            "--trust-confirmed", "--registry-hash", "deadbeef", "--json",
        ])
        self.assertEqual(code, cli.EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(payload["registry_id"], "vercel-labs/skills/find-skills")
        self.assertEqual(payload["content_hash"], "deadbeef")
        self.assertFalse(payload["may_install"])
        self.assertEqual(payload["hash_status"], "unverified-provided")
        self.assertFalse(payload["hash_verified"])
        self.assertEqual(len(payload["audit_links"]), 3)

    def test_preview_rejects_unsupported_reference_cleanly(self):
        code, out, err = self.invoke(["install", "--preview", "https://evil.example.com/a/b"])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("unsupported registry host", err)
        self.assertNotIn("Traceback", err)

    @mock.patch("skillsmgr.cli_handlers.subprocess.run")
    def test_list_only_executes_runner_with_list_flag_and_reports_output(self, run):
        run.return_value = mock.Mock(returncode=0, stdout="available-skill\n", stderr="")

        code, out, err = self.invoke([
            "install", "vercel-labs/agent-skills", "--list-only",
        ])

        self.assertEqual(code, cli.EXIT_OK)
        run.assert_called_once_with(
            ["npx", "skills", "add", "vercel-labs/agent-skills", "-g", "-l"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertIn("running: npx skills add vercel-labs/agent-skills -g -l", out)
        self.assertIn("available-skill", out)
        self.assertEqual(err, "")

    @mock.patch("skillsmgr.cli_handlers.subprocess.run")
    def test_list_only_returns_runner_exit_behavior_and_json_output(self, run):
        run.return_value = mock.Mock(returncode=7, stdout="partial\n", stderr="runner failed\n")

        code, out, err = self.invoke([
            "install", "vercel-labs/agent-skills", "--list-only", "--json",
        ])

        self.assertEqual(code, cli.EXIT_ERROR)
        run.assert_called_once()
        self.assertEqual(json.loads(out), {
            "command": "npx skills add vercel-labs/agent-skills -g -l",
            "exit_code": 7,
            "stdout": "partial\n",
            "stderr": "runner failed\n",
        })
        self.assertEqual(err, "")

    @mock.patch("skillsmgr.cli_handlers.subprocess.run")
    def test_dry_run_does_not_execute_runner(self, run):
        code, out, err = self.invoke([
            "install", "vercel-labs/agent-skills", "--dry-run",
        ])

        self.assertEqual(code, cli.EXIT_OK)
        run.assert_not_called()
        self.assertEqual(out.strip(), "npx skills add vercel-labs/agent-skills -g")
        self.assertEqual(err, "")


class InstallPreviewRestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["SKILLS_MANAGER_DATA"] = self._tmp.name
        from skillsmgr.store import Store
        from skillsmgr.webapp import WebAppServer

        self.store = Store(data_dir=self._tmp.name)
        self.store.init_db()
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

    def test_legacy_install_payload_is_unchanged(self):
        payload = self.post("api/install", {"source": "vercel-labs/agent-skills"})
        self.assertEqual(sorted(payload), ["command", "executed", "runner", "source"])
        self.assertFalse(payload["executed"])

    def test_preview_payload_adds_the_registry_plan(self):
        payload = self.post("api/install", {
            "source": "vercel-labs/skills/find-skills",
            "preview": True,
            "trust_confirmed": True,
            "description": "finds skills",
        })
        self.assertFalse(payload["executed"])
        self.assertEqual(
            payload["command"], "npx skills add vercel-labs/skills -g -s find-skills"
        )
        self.assertEqual(payload["registry"]["install_command"], payload["command"])
        self.assertFalse(payload["registry"]["may_install"])
        self.assertFalse(payload["registry"]["trust_verified"])
        self.assertEqual(len(payload["registry"]["audit_links"]), 3)

    def test_preview_rejects_an_unsupported_reference(self):
        from urllib.error import HTTPError

        with self.assertRaises(HTTPError) as caught:
            self.post("api/install", {"source": "https://evil.example.com/a/b", "preview": True})
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
