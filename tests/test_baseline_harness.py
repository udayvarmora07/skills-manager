"""Contracts for the synthetic DEL-01 baseline fixture plan."""

from __future__ import annotations

import unittest
import time
from pathlib import Path

from baseline_harness import (
    FULL_INVENTORY_ROUTES,
    FULL_INVENTORY_SAMPLES,
    FULL_INVENTORY_SIZES,
    MIN_P95_SAMPLES,
    _nearest_rank,
    _sample_inventory_routes,
    _summarize_inventory_rows,
    fixture_plan,
    summarize_samples,
)


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


class FullInventoryBaselineContractTests(unittest.TestCase):
    def test_inventory_sizes_and_routes_cover_the_requested_surface(self):
        self.assertEqual(FULL_INVENTORY_SIZES, (100, 1000, 10000))
        self.assertGreaterEqual(FULL_INVENTORY_SAMPLES, 20)
        self.assertEqual(
            set(FULL_INVENTORY_ROUTES),
            {"scopes", "merged_list", "stats", "doctor", "hygiene"},
        )

    def test_nearest_rank_p95_is_explicit_for_twenty_samples(self):
        samples = [float(value) for value in range(1, 21)]
        self.assertEqual(_nearest_rank(samples, 0.95), 19.0)
        self.assertIsNone(_nearest_rank([], 0.95))

    def test_summary_never_reports_percentiles_without_samples(self):
        summary = summarize_samples([])
        self.assertIsNone(summary["median_ms"])
        self.assertIsNone(summary["p95_ms_nearest_rank"])
        self.assertEqual(summarize_samples([2.0, 4.0])["median_ms"], 3.0)

    def test_inventory_p95_requires_twenty_successful_samples(self):
        short = _summarize_inventory_rows([
            {"status": "ok", "elapsed_ms": float(value)} for value in range(1, MIN_P95_SAMPLES)
        ])
        complete = _summarize_inventory_rows([
            {"status": "ok", "elapsed_ms": float(value)} for value in range(1, MIN_P95_SAMPLES + 1)
        ])
        self.assertIsNone(short["p95_ms_nearest_rank"])
        self.assertIn("requires at least 20 successful samples", short["p95_unavailable_reason"])
        self.assertEqual(complete["sample_count"], 20)
        self.assertEqual(complete["p95_ms_nearest_rank"], 19.0)

    def test_inventory_runtime_budget_does_not_start_partial_timeout_samples(self):
        deadline = time.perf_counter() + 0.01
        cold, warm = _sample_inventory_routes(
            Path("/unused"),
            size=100,
            samples=20,
            timeout_s=60,
            deadline=deadline,
        )
        for group in (cold, warm):
            for summary in group.values():
                self.assertEqual(summary["sample_count"], 0)
                self.assertEqual(summary["failed_samples"], 20)
                self.assertTrue(all(
                    row["reason"] == "insufficient runtime budget for request timeout"
                    for row in summary["sample_order"]
                ))


if __name__ == "__main__":
    unittest.main()
