"""The barometer drafts posts for new models only, from launch_check's readings."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import barometer as bm  # noqa: E402


def row(version: str, score: float, err: float, date: str) -> dict:
    return {"Model version": version, "mean_score": str(score), "stderr": str(err), "Release date": date}


BOARD = [row("old-%d" % i, 0.50 - 0.02 * i, 0.01, "2026-01-01") for i in range(6)] + [row("new_max", 0.51, 0.02, "2026-09-29")]


class BarometerTests(unittest.TestCase):
    def test_only_models_released_after_the_date_are_new(self) -> None:
        self.assertEqual(bm.new_models({"b": BOARD}, "2026-09-01"), [("new", "2026-09-29")])
        self.assertEqual(bm.new_models({"b": BOARD}, "2026-09-29"), [])

    def test_a_draft_says_a_lead_inside_the_error_bars_is_not_established(self) -> None:
        result = bm.lc.check("b", BOARD, "new")
        text = bm.draft("new", "2026-09-29", [result], "2026-10-03")
        self.assertIn("avance non établie", text)
        self.assertIn("lead not established", text)
        self.assertIn("Draft only", text)


if __name__ == "__main__":
    unittest.main()
