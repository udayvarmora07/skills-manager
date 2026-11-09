"""Contracts for the advisory risk scan's original (pre-Phase B) checks."""

from __future__ import annotations

import unittest

from skillsmgr.risk import risk_scan


class TestRiskScan(unittest.TestCase):




    def test_risk_scan_rejects_a_non_record(self):
        with self.assertRaises(ValueError):
            risk_scan(None)

    def test_large_bodies_complete_within_budget(self):
        import time

        started = time.time()
        risk_scan({"body": "ok\n" * 200000})
        self.assertLess(time.time() - started, 5)


if __name__ == "__main__":
    unittest.main()
