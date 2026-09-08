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
        self.assertEqual(check_docs._command_inventory(), (27, 7, 3, 37))


if __name__ == "__main__":
    unittest.main()
