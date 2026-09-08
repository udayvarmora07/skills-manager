"""Regression tests for the machine-checkable documentation gate."""

import unittest

import check_docs


class DocumentationConsistencyTests(unittest.TestCase):
    def test_repository_docs_match_current_source_contracts(self):
        self.assertEqual(check_docs.run_checks(), [])


if __name__ == "__main__":
    unittest.main()