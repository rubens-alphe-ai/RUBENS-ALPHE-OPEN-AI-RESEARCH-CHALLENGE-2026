"""A claimed gap between two models, tested where it can be: item by item."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import claim_check as cc  # noqa: E402


def models(both_right: int, only_a: int, only_b: int, both_wrong: int) -> tuple[dict, dict]:
    a, b, k = {}, {}, 0
    for count, (x, y) in ((both_right, (1, 1)), (only_a, (1, 0)), (only_b, (0, 1)), (both_wrong, (0, 0))):
        for _ in range(count):
            a["q%d" % k], b["q%d" % k] = x, y
            k += 1
    return a, b


class CompareTests(unittest.TestCase):
    def test_only_disagreements_carry_the_verdict(self) -> None:
        # A thousand items both models get right change nothing.
        few = cc.compare(*models(20, 12, 3, 5))
        many = cc.compare(*models(1020, 12, 3, 5))
        self.assertEqual(few["mcnemar_exact_p"], many["mcnemar_exact_p"])

    def test_a_clear_gap_is_supported(self) -> None:
        got = cc.compare(*models(300, 60, 10, 30))
        self.assertTrue(got["supported_at_95"])
        self.assertGreater(got["gap_pts"], 0)

    def test_a_small_gap_on_a_small_test_is_not_supported_and_says_what_would_settle_it(self) -> None:
        got = cc.compare(*models(150, 9, 6, 35))
        self.assertFalse(got["supported_at_95"])
        self.assertGreater(got["items_needed_for_80pct_power_at_this_gap"], got["shared_items"])

    def test_the_exact_p_matches_a_hand_computed_binomial(self) -> None:
        # 8 against 2 of 10 disagreements: two-sided exact p = 2 * P(X <= 2) = 0.109375.
        got = cc.compare(*models(30, 8, 2, 0))
        self.assertAlmostEqual(got["mcnemar_exact_p"], 0.10938, places=4)

    def test_identical_results_cannot_be_ordered(self) -> None:
        got = cc.compare(*models(40, 0, 0, 10))
        self.assertFalse(got["supported_at_95"])
        self.assertIn("cannot order", cc.reading(got, "A", "B", None))

    def test_too_few_shared_items_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            cc.compare(*models(10, 3, 2, 4))

    def test_a_claimed_gap_is_checked_against_the_interval(self) -> None:
        got = cc.compare(*models(300, 60, 10, 30))
        self.assertIn("outside", cc.reading(got, "A", "B", 40.0))
        self.assertIn("inside", cc.reading(got, "A", "B", got["gap_pts"]))


if __name__ == "__main__":
    unittest.main()
