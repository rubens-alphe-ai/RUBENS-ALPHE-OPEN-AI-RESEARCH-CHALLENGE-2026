"""Reading a published leaderboard's own error bars into what its order supports."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import leaderboard_reality as lr  # noqa: E402


def row(version: str, score: float, err: float) -> dict:
    return {"Model version": version, "mean_score": str(score), "stderr": str(err)}


class RuleTests(unittest.TestCase):
    def test_identical_scores_separate_nobody_even_with_zero_error(self) -> None:
        # Sixteen models at 100% with a published error of zero: a rule that
        # calls that "separated" reports an order that does not exist.
        self.assertFalse(lr.separated((1.0, 0.0), (1.0, 0.0)))

    def test_a_gap_well_outside_the_errors_is_separated(self) -> None:
        self.assertTrue(lr.separated((0.90, 0.01), (0.80, 0.01)))
        self.assertFalse(lr.separated((0.90, 0.02), (0.88, 0.02)))

    def test_settings_of_one_model_count_once_at_their_best(self) -> None:
        # Two reasoning settings of one model are expected to sit side by side;
        # counting them as neighbours inflates every unsupported ordering.
        board = lr.best_per_model([row("m-1_max", 0.9, 0.01), row("m-1_high", 0.88, 0.01),
                                   row("m-2", 0.7, 0.01)])
        self.assertEqual([b[0] for b in board], ["m-1_max", "m-2"])

    def test_a_board_too_small_is_not_assessed(self) -> None:
        board = [("m%d" % i, 0.9 - i / 100, 0.01) for i in range(9)]
        self.assertIsNone(lr.assess("tiny", board))

    def test_a_clearly_spread_board_is_not_called_unsupported(self) -> None:
        board = [("m%d" % i, 0.95 - i * 0.08, 0.005) for i in range(12)]
        got = lr.assess("spread", board)
        self.assertEqual(got["top10_adjacent_unsupported"], 0)
        self.assertEqual(got["tied_with_leader"], 0)
        self.assertTrue(got["first_vs_fifth_separated"])


if __name__ == "__main__":
    unittest.main()
