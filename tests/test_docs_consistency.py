"""Regression tests for the machine-checkable documentation gate."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import check_docs


class DocumentationConsistencyTests(unittest.TestCase):
    def test_repository_docs_match_current_source_contracts(self):
        self.assertEqual(check_docs.run_checks(), [])

    def test_broken_at_docs_link_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("See @docs/missing.md.\n", encoding="utf-8")
            errors = check_docs.check_doc_links(root)
        self.assertEqual(errors, ["README.md: broken @docs/missing.md"])

    def test_documented_store_symbol_must_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "skillsmgr").mkdir()
            (root / "skillsmgr" / "store.py").write_text(
                "class Store:\n    def list(self):\n        return []\n", encoding="utf-8"
            )
            (root / "docs").mkdir()
            (root / "docs" / "04-store-api.md").write_text(
                "Store.list() and Store.removed()\n", encoding="utf-8"
            )
            with mock.patch.object(check_docs, "CURRENT_DOCS", ("docs/04-store-api.md",)):
                errors = check_docs.check_documented_source_symbols(root)
        self.assertEqual(errors, ["docs/04-store-api.md: documented source symbol does not exist: Store.removed"])

    def test_source_and_project_versions_must_align(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "skillsmgr").mkdir()
            (root / "skillsmgr" / "__init__.py").write_text(
                '__version__ = "1.2.0"\n', encoding="utf-8"
            )
            (root / "pyproject.toml").write_text(
                '[project]\nversion = "1.1.0"\n', encoding="utf-8"
            )
            errors = check_docs.check_version_alignment(root)
        self.assertEqual(
            errors,
            ["version mismatch: skillsmgr.__version__='1.2.0', pyproject project.version='1.1.0'"],
        )

    def test_command_inventory_is_derived_from_parser_source(self):
        self.assertEqual(check_docs._command_inventory(), (28, 10, 3, 41))

    # -- checks added by the 2026-09-11 documentation truth pass -------------
    # Each of these caught real drift that the older gate could not see.

    def _root(self, directory, *, docs=(), files=()):
        root = Path(directory)
        (root / "docs").mkdir(exist_ok=True)
        (root / "skillsmgr").mkdir(exist_ok=True)
        for rel, text in docs:
            path = root / "docs" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        for rel, text in files:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def test_a_docs_file_missing_a_hads_marker_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory, docs=[("01-x.md", "# X\n\nBody with no version line.\n")])
            errors = check_docs.check_house_style(root)
        self.assertIn("docs/01-x.md: version line not within the first 20 lines", errors)
        self.assertIn("docs/01-x.md: AI manifest not within the first 20 lines", errors)

    def test_an_unescaped_pipe_that_breaks_a_table_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory, files=[("README.md",
                "| A | B |\n|---|---|\n| `x=0|1` | y |\n")])
            errors = check_docs.check_house_style(root)
        self.assertTrue(any("inconsistent cell counts" in e for e in errors), errors)

    def test_a_file_without_a_final_newline_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory, files=[("README.md", "# R\n\nno newline at the end")])
            errors = check_docs.check_house_style(root)
        self.assertIn("README.md: file does not end with a newline", errors)

    def test_a_dead_markdown_anchor_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory, files=[
                ("README.md", "# R\n\n[good](OTHER.md#real-heading) [bad](OTHER.md#nope)\n"),
                ("OTHER.md", "# Other\n\n## Real heading\n"),
            ])
            errors = check_docs.check_markdown_anchors(root)
        self.assertEqual(errors, ["README.md: dead markdown anchor -> OTHER.md#nope"])

    def test_a_rest_route_implemented_but_undocumented_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            (root / "skillsmgr" / "webapp.py").write_text(
                'if parts == ["api", "skills"]:\n    pass\n'
                'if parts == ["api", "tokens"]:\n    pass\n', encoding="utf-8")
            (root / "docs" / "08-web-ui.md").write_text(
                "| GET | `/api/skills` |\n", encoding="utf-8")
            errors = check_docs.check_surface_parity(root)
        self.assertEqual(errors, ["docs/08-web-ui.md: /api/tokens is implemented but undocumented"])

    def test_a_documented_rest_route_that_is_not_implemented_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            (root / "skillsmgr" / "webapp.py").write_text(
                'if parts == ["api", "skills"]:\n    pass\n', encoding="utf-8")
            (root / "docs" / "08-web-ui.md").write_text(
                "| GET | `/api/skills` |\n| GET | `/api/stats-bogus` |\n", encoding="utf-8")
            errors = check_docs.check_surface_parity(root)
        self.assertIn("docs/08-web-ui.md: /api/stats-bogus is documented but not implemented", errors)

    def test_a_store_method_documented_but_not_implemented_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            (root / "skillsmgr" / "store.py").write_text(
                "class Store:\n    def resync(self):\n        return {}\n", encoding="utf-8")
            (root / "docs" / "04-store-api.md").write_text(
                "## Public methods\n\n- `resync(self) -> dict`\n- `db_resync(self) -> dict`\n"
                "\n## SQLite schema\n", encoding="utf-8")
            errors = check_docs.check_surface_parity(root)
        self.assertIn("docs/04-store-api.md: documents Store.db_resync() which does not exist", errors)

    def test_a_cli_command_without_a_heading_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            (root / "skillsmgr" / "cli_parser.py").write_text(
                "def build_parser(commands):\n"
                "    sub = parser.add_subparsers()\n"
                "    sub.add_parser('list', aliases=['ls'])\n"
                "    sub.add_parser('stats')\n", encoding="utf-8")
            (root / "docs" / "03-cli-surface.md").write_text(
                "### `list` / `ls [--json]`\n", encoding="utf-8")
            errors = check_docs.check_surface_parity(root)
        self.assertIn("docs/03-cli-surface.md: CLI command 'stats' has no documented heading", errors)
        self.assertNotIn("docs/03-cli-surface.md: CLI command 'ls' has no documented heading", errors)

    def test_a_missing_file_in_the_session_context_inventory_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory, docs=[("SESSION-CONTEXT.md",
                "# S\n\n## File inventory (build-relevant)\n\n```text\n"
                "skillsmgr/\n  real.py\n  gone.py\n```\n")])
            (root / "skillsmgr" / "real.py").write_text("x = 1\n", encoding="utf-8")
            errors = check_docs.check_surface_parity(root)
        self.assertIn("docs/SESSION-CONTEXT.md: inventory lists missing file gone.py", errors)


if __name__ == "__main__":
    unittest.main()
