"""The release-day check reads leads the way the error bars allow, and no further."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import launch_check as lc  # noqa: E402


def row(version: str, score: float, err: float, date: str = "2026-01-01") -> dict:
    return {"Model version": version, "mean_score": str(score), "stderr": str(err), "Release date": date}


FIELD = [row("old-%d" % i, 0.50 - 0.02 * i, 0.01) for i in range(6)]


class LaunchCheckTests(unittest.TestCase):
    def test_a_lead_inside_the_error_bars_is_not_established(self) -> None:
        got = lc.check("b", FIELD + [row("new_max", 0.51, 0.02)], "new")
        self.assertEqual(got["rank"], 1)
        self.assertEqual(got["reading"], "first, but the lead is not established at this sample size")

    def test_a_clear_lead_is_established(self) -> None:
        got = lc.check("b", FIELD + [row("new_max", 0.80, 0.01)], "new")
        self.assertEqual(got["reading"], "lead established")

    def test_an_equal_score_is_level_not_first(self) -> None:
        got = lc.check("b", FIELD + [row("new_max", 0.50, 0.01)], "new")
        self.assertEqual(got["reading"], "level with the best other model")

    def test_settings_of_one_model_count_once_at_their_best(self) -> None:
        got = lc.check("b", FIELD + [row("new_low", 0.30, 0.01), row("new_high", 0.52, 0.01)], "new")
        self.assertEqual(got["setting"], "new_high")
        self.assertEqual(got["models_compared"], 7)

    def test_a_board_with_too_few_other_models_is_skipped(self) -> None:
        self.assertIsNone(lc.check("b", FIELD[:3] + [row("new_max", 0.9, 0.01)], "new"))

    def test_newest_is_found_by_release_date(self) -> None:
        boards = {"b": FIELD + [row("new_max", 0.5, 0.01, "2026-09-29")]}
        self.assertEqual(lc.newest(boards), "new")


if __name__ == "__main__":
    unittest.main()
