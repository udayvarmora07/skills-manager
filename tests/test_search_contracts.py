"""Hermetic search complexity, ranking, and adapter contract regressions."""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from skillsmgr import cli, scopes
from skillsmgr.search import compile_wildcard, rank_results
from skillsmgr.store import Store, StoreError
from skillsmgr.webapp import WebAppServer


class SearchContractCase(unittest.TestCase):
    """Use isolated global and agent roots for every search contract."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_home = os.environ.get("HOME")
        self.old_data = os.environ.get("SKILLS_MANAGER_DATA")
        os.environ["HOME"] = self.tmp.name
        os.environ["SKILLS_MANAGER_DATA"] = str(Path(self.tmp.name) / "data")
        self.store = Store()
        self.store.init_db()
        scopes.set_global_store(self.store)
        self.addCleanup(scopes.set_global_store, None)
        self.addCleanup(self._restore_environment)

    def _restore_environment(self) -> None:
        if self.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.old_home
        if self.old_data is None:
            os.environ.pop("SKILLS_MANAGER_DATA", None)
        else:
            os.environ["SKILLS_MANAGER_DATA"] = self.old_data

    def add_global_fixtures(self) -> None:
        self.store.create("zeta", "Exact zeta skill", body="ordinary body")
        self.store.create("a-zeta", "Prefix zeta skill", body="ordinary body")
        self.store.create(
            "global-body",
            "Global body fixture",
            body="A distinctive needle appears only in this body.",
        )
        self.store.create(
            "global-description",
            "A distinctive needle appears in this description",
            body="ordinary body",
        )
        self.store.create("deploy-global", "Global deployment skill")

    def add_agent_fixtures(self) -> None:
        scopes.create_skill(
            "agents",
            "agent-body",
            "Agent body fixture",
            body="A distinctive needle appears only in the agent body.",
        )
        scopes.create_skill("agents", "agent-alpha", "Agent alpha skill", body="ordinary body")
        scopes.create_skill("agents", "deploy-agent", "Agent deployment skill")


class WildcardComplexityTests(SearchContractCase):
    def test_repeated_stars_are_collapsed_and_alternating_stars_are_bounded(self):
        repeated = compile_wildcard("a" + "*" * 198 + "b")
        self.assertIsNotNone(repeated.fullmatch("a value between b"))

        with self.assertRaisesRegex(ValueError, r"too many '\*'"):
            compile_wildcard("*a" * 11)
        with self.assertRaisesRegex(ValueError, r"too many '\*'"):
            compile_wildcard("*?" * 11)

    def test_query_length_and_star_caps_have_clean_store_and_scope_errors(self):
        self.add_global_fixtures()
        for query in ("x" * 201, "*a" * 11):
            with self.subTest(query=query):
                with self.assertRaises((ValueError, StoreError)) as store_error:
                    self.store.search(query)
                self.assertNotIn("Traceback", str(store_error.exception))
                with self.assertRaises(StoreError) as scope_error:
                    scopes.search_all(query, scope_id="all")
                self.assertNotIn("Traceback", str(scope_error.exception))

    def test_boundary_length_and_star_count_are_accepted(self):
        self.assertIsNotNone(compile_wildcard("x" * 200))
        self.assertIsNotNone(compile_wildcard("*a" * 10))


class SearchRankingTests(SearchContractCase):
    def test_exact_ranking_is_stable_and_literal(self):
        records = [
            {"name": "my-alpha", "description": "ordinary", "body": "ordinary"},
            {"name": "Alpha", "description": "ordinary", "body": "ordinary"},
            {"name": "docs", "description": "alpha in docs", "body": "ordinary"},
            {"name": "body-hit", "description": "ordinary", "body": "alpha in body"},
            {"name": "alpha-tool", "description": "ordinary", "body": "ordinary"},
        ]
        ranked = rank_results(records, "alpha")
        self.assertEqual(
            [(record["name"], score) for record, score in ranked],
            [
                ("Alpha", 100),
                ("alpha-tool", 80),
                ("my-alpha", 70),
                ("body-hit", 40),
                ("docs", 40),
            ],
        )

    def test_body_matching_is_included_in_store_search(self):
        self.add_global_fixtures()
        self.assertEqual(
            [record["name"] for record in self.store.search("needle")],
            ["global-body", "global-description"],
        )


class SearchRecordLoadingTests(SearchContractCase):
    """Pin *how many* documents a search reads, not only what it returns.

    A test that asserts the returned rows passes equally before and after the
    per-row ``Store.get()`` is removed, so it cannot see this defect at all. The
    wasted work was invisible to every ranking test in this file.
    """

    def test_global_search_records_do_not_re_read_every_document(self):
        self.add_global_fixtures()
        calls = {"get": 0}
        original = self.store.get

        def counting_get(name):
            calls["get"] += 1
            return original(name)

        self.store.get = counting_get
        try:
            records = scopes._global_search_records(self.store)
        finally:
            self.store.get = original

        self.assertGreater(len(records), 1, "fixture should produce several records")
        self.assertEqual(
            calls["get"], 0,
            "a search body must not cost one Store.get() per row: Store.get() "
            "returns body from the index and spends its document read filling "
            "_OBSERVED_KEYS, which this caller discards entirely",
        )

    def test_global_search_records_attach_the_indexed_body(self):
        self.add_global_fixtures()
        records = {r["name"]: r for r in scopes._global_search_records(self.store)}
        self.assertIn("needle", records["global-body"]["body"])
        self.assertIn("body", records["global-description"])
        # A row the caller holds must never be left without a body string,
        # because the ranking scorer matches against it unconditionally.
        for name, record in records.items():
            self.assertIsInstance(record["body"], str, name)

    def test_search_bodies_are_never_read_from_a_stale_document(self):
        """Bodies come from the index, so an unresynced disk edit is not matched.

        This is the behaviour the optimisation had to *preserve*. If a future
        change makes this route filesystem-authoritative, ``skills-mgr search``
        (which matches on the indexed body via ``Store.search()``) and this
        route would disagree about the same query -- a worse defect than the
        staleness, so it is pinned rather than left to be discovered.
        """
        self.add_global_fixtures()
        self.assertEqual(
            [r["name"] for r in scopes.search_all("needle", scope_id="global")],
            ["global-body", "global-description"],
        )
        path = Path(self.store.skills_dir) / "global-body" / "SKILL.md"
        text = path.read_text(encoding="utf-8").replace(
            "needle in the body", "kettle in the body",
        )
        path.write_text(text, encoding="utf-8")
        self.assertEqual(
            [r["name"] for r in scopes.search_all("kettle", scope_id="global")],
            [],
            "an unresynced on-disk edit must not become searchable yet",
        )

    def test_the_search_route_has_no_second_unreachable_search_path(self):
        """``scope`` is coerced non-empty, so a ``""`` branch can never run.

        The route used to test ``scope in ("all", "")`` and keep an else-branch
        calling ``self.store.search(q)``. It was unreachable on every request,
        so no behavioural test can see it -- it read as a live path and hid
        where search actually runs. Only reading the source catches this, which
        is the same reason ``tests/test_one_document_invariant.py`` has one
        source-reading test.
        """
        source = Path(scopes.__file__).resolve().parent / "webapp.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        route = next(
            node
            for cls in tree.body if isinstance(cls, ast.ClassDef)
            for node in cls.body
            if isinstance(node, ast.FunctionDef) and node.name == "_route_search_get"
        )
        called = [
            ast.unparse(node.func)
            for node in ast.walk(route)
            if isinstance(node, ast.Call)
        ]
        self.assertNotIn(
            "self.store.search",
            called,
            "_route_search_get must route every scope through scopes.search_all; "
            "a Store.search call here is either dead code or a second, "
            "differently-behaving search path",
        )


class ScopeAndCliSearchTests(SearchContractCase):
    def test_global_agent_and_merged_search_match_body_and_preserve_ranking(self):
        self.add_global_fixtures()
        self.add_agent_fixtures()

        self.assertEqual(
            [record["name"] for record in scopes.search_all("needle", scope_id="global")],
            ["global-body", "global-description"],
        )
        self.assertEqual(
            [record["name"] for record in scopes.search_all("needle", scope_id="agents")],
            ["agent-body"],
        )
        merged = scopes.search_all("needle", scope_id="all")
        self.assertEqual(
            [(record["scope"], record["name"]) for record in merged],
            [("agents", "agent-body"), ("global", "global-body"), ("global", "global-description")],
        )
        self.assertEqual(
            [record["name"] for record in scopes.search_all("zeta", scope_id="global")],
            ["zeta", "a-zeta"],
        )

    def _invoke_cli(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--data-dir", str(Path(self.tmp.name) / "data"), *argv])
        return code, out.getvalue(), err.getvalue()

    def test_cli_global_agent_and_merged_search_are_bounded_and_clean(self):
        self.add_global_fixtures()
        self.add_agent_fixtures()

        code, out, err = self._invoke_cli(["search", "needle", "--json"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual([row["name"] for row in json.loads(out)], ["global-body", "global-description"])
        self.assertEqual(err, "")

        code, out, err = self._invoke_cli(["search", "needle", "--scope", "agents", "--json"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual([row["name"] for row in json.loads(out)], ["agent-body"])
        self.assertEqual(err, "")

        code, out, err = self._invoke_cli(["search", "needle", "--scope", "all", "--json"])
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(
            [(row["scope"], row["name"]) for row in json.loads(out)],
            [("agents", "agent-body"), ("global", "global-body"), ("global", "global-description")],
        )
        self.assertEqual(err, "")

        for query in ("x" * 201, "*a" * 11):
            code, out, err = self._invoke_cli(["search", query, "--json"])
            self.assertEqual(code, cli.EXIT_ERROR)
            self.assertEqual(out, "")
            self.assertNotIn("unexpected error", err.lower())
            self.assertNotIn("traceback", err.lower())

    def test_cli_search_uses_requested_data_dir_for_global_and_merged_scopes(self):
        with tempfile.TemporaryDirectory() as root:
            requested_base = Path(root) / "requested"
            other_base = Path(root) / "other"
            requested = Store(requested_base / "skills-manager")
            other = Store(other_base / "skills-manager")
            requested.init_db()
            other.init_db()
            requested.create("requested-only", "needle in requested data")
            other.create("wrong-only", "needle in another data dir")
            scopes.create_skill("agents", "agent-only", "needle in agent scope")
            scopes.set_global_store(other)
            self.addCleanup(scopes.set_global_store, self.store)

            def invoke(data_dir: Path, *extra: str):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = cli.main(
                        ["--data-dir", str(data_dir), "search", "needle", "--json", *extra]
                    )
                return code, json.loads(out.getvalue()), err.getvalue()

            code, rows, err = invoke(requested_base)
            self.assertEqual(code, cli.EXIT_OK)
            self.assertEqual([row["name"] for row in rows], ["requested-only"])
            self.assertEqual(err, "")

            code, rows, err = invoke(requested_base, "--scope", "all")
            self.assertEqual(code, cli.EXIT_OK)
            self.assertEqual(
                [(row["scope"], row["name"]) for row in rows],
                [("agents", "agent-only"), ("global", "requested-only")],
            )
            self.assertEqual(err, "")


class RestSearchContractTests(SearchContractCase):
    def setUp(self) -> None:
        super().setUp()
        self.add_global_fixtures()
        self.add_agent_fixtures()
        self.server = WebAppServer(self.store, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)

    def _get_json(self, path: str):
        with urllib.request.urlopen(self.server.url.rstrip("/") + path) as response:
            return response.status, json.loads(response.read())

    def _assert_http_error(self, path: str, message: str) -> None:
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self.server.url.rstrip("/") + path)
        self.assertEqual(context.exception.code, 400)
        payload = json.loads(context.exception.read())
        self.assertEqual(payload, {"error": message, "code": "bad_request"})

    def test_rest_global_agent_and_merged_search_match_body(self):
        for scope, expected in (
            ("global", ["global-body"]),
            ("agents", ["agent-body"]),
            ("all", ["agent-body", "global-body"]),
        ):
            with self.subTest(scope=scope):
                _, rows = self._get_json(
                    "/api/search?q=" + quote("only in") + "&scope=" + scope
                )
                self.assertEqual([row["name"] for row in rows], expected)

    def test_rest_two_servers_keep_global_and_merged_search_isolated(self):
        term = "isolation-needle"
        self.store.create("server-a-only", term)
        scopes.create_skill("agents", "agent-isolation", "Agent isolation skill", body=term)

        store_b = Store(Path(self.tmp.name) / "data-b" / "skills-manager")
        store_b.init_db()
        store_b.create("server-b-only", term)
        server_b = WebAppServer(store_b, port=0)
        thread_b = threading.Thread(target=server_b.serve_forever, daemon=True)
        thread_b.start()

        def stop_server_b() -> None:
            server_b.shutdown()
            thread_b.join(timeout=5)

        self.addCleanup(stop_server_b)

        for server, own_global in (
            (self.server, "server-a-only"),
            (server_b, "server-b-only"),
        ):
            with self.subTest(server=own_global):
                base = server.url.rstrip("/")
                for endpoint in ("/api/search", "/api/skills"):
                    with self.subTest(endpoint=endpoint, scope="global"):
                        _, rows = self._get_json_from(
                            base + endpoint + "?scope=global&q=" + quote(term)
                        )
                        self.assertEqual([row["name"] for row in rows], [own_global])
                    with self.subTest(endpoint=endpoint, scope="all"):
                        _, rows = self._get_json_from(
                            base + endpoint + "?scope=all&q=" + quote(term)
                        )
                        self.assertEqual(
                            [(row["scope"], row["name"]) for row in rows],
                            [("agents", "agent-isolation"), ("global", own_global)],
                        )

    def _get_json_from(self, url: str):
        with urllib.request.urlopen(url) as response:
            return response.status, json.loads(response.read())

    def test_rest_query_length_and_star_complexity_return_bounded_json_errors(self):
        self._assert_http_error(
            "/api/search?q=" + quote("x" * 201),
            "search query too long",
        )
        self._assert_http_error(
            "/api/search?q=" + quote("*a" * 11),
            "wildcard pattern has too many '*' (max 10)",
        )
        self._assert_http_error(
            "/api/skills?scope=all&q=" + quote("x" * 201),
            "search query too long",
        )


if __name__ == "__main__":
    unittest.main()
