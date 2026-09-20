"""Contracts for the synthetic DEL-01 baseline fixture plan."""

from __future__ import annotations

import unittest

from baseline_harness import fixture_plan


class BaselineFixturePlanTests(unittest.TestCase):
    def test_plan_covers_the_required_library_shapes(self):
        plan = fixture_plan()
        self.assertEqual(
            set(plan), {"empty", "small", "divergent", "malformed", "large"}
        )
        self.assertEqual(plan["large"]["skill_count"], 2000)

    def test_plan_is_returned_as_a_copy(self):
        plan = fixture_plan()
        plan["small"]["skill_count"] = 99
        self.assertEqual(fixture_plan()["small"]["skill_count"], 12)

    def test_divergent_fixture_names_the_two_required_states(self):
        self.assertEqual(
            fixture_plan()["divergent"]["expected_states"],
            ["duplicated", "divergent"],
        )

    def test_malformed_fixture_keeps_a_valid_comparison_case(self):
        self.assertEqual(
            fixture_plan()["malformed"]["expected_states"], ["active", "malformed"]
        )

    def test_fixture_counts_are_deterministic(self):
        self.assertEqual(
            {name: spec["skill_count"] for name, spec in fixture_plan().items()},
            {"empty": 0, "small": 12, "divergent": 4, "malformed": 2, "large": 2000},
        )


if __name__ == "__main__":
    unittest.main()
