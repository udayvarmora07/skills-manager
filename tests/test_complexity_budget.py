"""Unit tests for the repository complexity ratchet."""

from __future__ import annotations

import unittest

import check_complexity


class ComplexityMetricTests(unittest.TestCase):
    def test_synthetic_ast_reports_span_and_decisions(self) -> None:
        source = """
def sample(value, items):
    if value and items:
        for item in items:
            if item:
                return item
    return None

class Container:
    async def method(self, value):
        return value if value else 0
"""

        metrics = check_complexity.collect_metrics(source, "synthetic.py")
        by_key = {metric.key: metric for metric in metrics}

        self.assertEqual(by_key["synthetic.py::sample"].complexity, 5)
        self.assertEqual(by_key["synthetic.py::sample"].lineno, 2)
        self.assertEqual(by_key["synthetic.py::sample"].end_lineno, 7)
        self.assertEqual(by_key["synthetic.py::Container.method"].complexity, 2)
        self.assertEqual(by_key["synthetic.py::Container.method"].lineno, 10)

    def test_nested_function_is_measured_separately(self) -> None:
        source = """
def outer(value):
    def inner(item):
        if item:
            return item
        return None
    return inner(value)
"""

        metrics = check_complexity.collect_metrics(source, "nested.py")
        self.assertEqual(
            {metric.name: metric.complexity for metric in metrics},
            {"outer": 1, "outer.inner": 2},
        )


class ComplexityRatchetTests(unittest.TestCase):
    def test_new_function_over_threshold_is_a_violation(self) -> None:
        metrics = check_complexity.collect_metrics(
            "def new(value):\n    if value:\n        return 1\n    return 0\n",
            "synthetic.py",
        )
        baseline = check_complexity.build_baseline([], threshold=1)

        violations = check_complexity.evaluate_metrics(metrics, baseline)

        self.assertEqual([violation.kind for violation in violations], ["new violation"])
        self.assertIn("synthetic.py::new", violations[0].message())

    def test_new_function_at_threshold_is_allowed(self) -> None:
        metrics = check_complexity.collect_metrics(
            "def new(value):\n    if value:\n        return 1\n    return 0\n",
            "synthetic.py",
        )
        baseline = check_complexity.build_baseline([], threshold=2)

        self.assertEqual(check_complexity.evaluate_metrics(metrics, baseline), [])

    def test_existing_function_metric_increase_fails_even_below_threshold(self) -> None:
        current = check_complexity.collect_metrics(
            "def stable(value):\n    if value:\n        return 1\n    return 0\n",
            "synthetic.py",
        )
        baseline = check_complexity.build_baseline(
            [
                check_complexity.FunctionMetric(
                    path="synthetic.py",
                    name="stable",
                    lineno=1,
                    end_lineno=1,
                    complexity=1,
                )
            ],
            threshold=15,
        )

        violations = check_complexity.evaluate_metrics(current, baseline)

        self.assertEqual([violation.kind for violation in violations], ["metric increase"])
        self.assertEqual(violations[0].baseline_complexity, 1)
        self.assertIn("complexity 1 -> 2", violations[0].message())

    def test_baseline_contains_deterministic_function_records(self) -> None:
        metrics = [
            check_complexity.FunctionMetric("b.py", "second", 4, 5, 2),
            check_complexity.FunctionMetric("a.py", "first", 1, 2, 1),
        ]

        baseline = check_complexity.build_baseline(metrics, threshold=7)

        self.assertEqual(baseline["version"], 1)
        self.assertEqual(baseline["threshold"], 7)
        self.assertEqual(list(baseline["functions"]), ["a.py::first", "b.py::second"])


if __name__ == "__main__":
    unittest.main()
