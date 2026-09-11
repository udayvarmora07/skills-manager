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
        self.assertTrue(plan["may_install"])
        self.assertEqual(plan["blockers"], [])
        self.assertTrue(plan["trust_confirmed"])
        self.assertEqual(plan["hash_status"], "not-provided")
        self.assertIn("no registry API request", plan["network"])

    def test_plan_blocks_without_trust_and_reports_provenance(self):
        plan = insights.registry_bridge_plan("vercel-labs/skills")
        self.assertFalse(plan["may_install"])
        self.assertFalse(plan["trust_confirmed"])
        self.assertEqual(len(plan["blockers"]), 1)
        self.assertIn("trust not confirmed", plan["blockers"][0])
        self.assertEqual(plan["description_status"], "not-provided")
        self.assertIn("authenticated catalog read", plan["provenance_note"])

    def test_plan_reports_a_supplied_hash(self):
        plan = insights.registry_bridge_plan(
            "vercel-labs/skills/find-skills",
            trust_confirmed=True,
            description="finds skills",
            content_hash="a1b2c3",
        )
        self.assertEqual(plan["hash_status"], "provided")
        self.assertEqual(plan["content_hash"], "a1b2c3")
        self.assertIn("detect", plan["hash_use"])

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
        self.assertTrue(payload["may_install"])
        self.assertEqual(len(payload["audit_links"]), 3)

    def test_preview_rejects_unsupported_reference_cleanly(self):
        code, out, err = self.invoke(["install", "--preview", "https://evil.example.com/a/b"])
        self.assertEqual(code, cli.EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("unsupported registry host", err)
        self.assertNotIn("Traceback", err)

    def test_dry_run_output_is_unchanged(self):
        code, out, err = self.invoke(["install", "vercel-labs/agent-skills", "--dry-run"])
        self.assertEqual(code, cli.EXIT_OK)
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
        self.assertTrue(payload["registry"]["may_install"])
        self.assertEqual(len(payload["registry"]["audit_links"]), 3)

    def test_preview_rejects_an_unsupported_reference(self):
        from urllib.error import HTTPError

        with self.assertRaises(HTTPError) as caught:
            self.post("api/install", {"source": "https://evil.example.com/a/b", "preview": True})
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
