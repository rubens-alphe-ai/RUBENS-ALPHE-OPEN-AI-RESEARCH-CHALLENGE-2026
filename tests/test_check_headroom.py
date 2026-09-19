"""The guard that would have caught MEM-010 and MEM-012 before they ran."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_headroom as ch  # noqa: E402


def policy(decision: dict) -> dict:
    return {"decision": decision}


class HeadroomTests(unittest.TestCase):
    def test_a_difference_in_points_cannot_exceed_what_is_left_above_the_control(self) -> None:
        self.assertEqual(ch.headroom(94.2, "points"), 100.0 - 94.2)

    def test_a_ratio_on_a_bounded_quantity_cannot_exceed_its_room_to_multiply(self) -> None:
        self.assertAlmostEqual(ch.headroom(50.0, "ratio"), 2.0)
        self.assertAlmostEqual(ch.headroom(91.7, "ratio"), 100.0 / 91.7)


class FindingTests(unittest.TestCase):
    def test_mem_010s_threshold_is_named_impossible(self) -> None:
        rows = ch.findings(policy({"keep_min_delta_pp": 20,
                                   "control_prior_pct": {"keep_min_delta_pp": {"clinic": 94.2}}}))
        self.assertEqual(rows[0]["status"], "IMPOSSIBLE")
        self.assertIn("94.2", rows[0]["reason"])

    def test_mem_011s_threshold_is_reachable_against_a_control_that_loses(self) -> None:
        rows = ch.findings(policy({"keep_min_delta_pp": 20,
                                   "control_prior_pct": {"keep_min_delta_pp": {"clinic": 61.6}}}))
        self.assertEqual(rows[0]["status"], "OK")

    def test_doubling_a_metric_already_above_half_is_impossible(self) -> None:
        rows = ch.findings(policy({"gap_targeting_ratio": 2.0,
                                   "control_prior_pct": {"gap_targeting_ratio": {"observatory": 91.7}}}))
        self.assertEqual(rows[0]["status"], "IMPOSSIBLE")

    def test_a_threshold_with_no_declared_prior_is_flagged_not_passed(self) -> None:
        rows = ch.findings(policy({"keep_min_delta_pp": 20}))
        self.assertEqual(rows[0]["status"], "UNDECLARED")

    def test_nothing_is_reported_for_a_policy_with_no_thresholds(self) -> None:
        self.assertEqual(ch.findings(policy({})), [])


if __name__ == "__main__":
    unittest.main()
