"""Treating the quiz as an instrument: the statistics that judge it."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import item_analysis as ia  # noqa: E402


def rows_from(pattern: list[list[int]], items: list[str]) -> list[dict]:
    return [dict(zip(items, row)) for row in pattern]


class DiscriminationTests(unittest.TestCase):
    def test_an_item_everyone_passes_is_flagged_as_carrying_nothing(self) -> None:
        items = ["A", "B", "C"]
        rows = rows_from([[1, 1, 0], [1, 0, 1], [1, 1, 1], [1, 0, 0]], items)
        report = {row["item"]: row for row in ia.analyse(rows, items)}
        self.assertEqual(report["A"]["difficulty"], 1.0)
        self.assertIn("everyone passes it", report["A"]["flags"])
        self.assertIsNone(report["A"]["discrimination"])

    def test_discrimination_excludes_the_item_from_the_score_it_is_compared_to(self) -> None:
        # Comparing an item against a total containing itself inflates it, and on
        # a short quiz it inflates it a lot.
        items = ["A", "B", "C", "D"]
        rows = rows_from([[1, 1, 1, 1], [0, 0, 0, 0], [1, 1, 0, 0], [0, 0, 1, 1]], items)
        got = {row["item"]: row["discrimination"] for row in ia.analyse(rows, items)}
        self.assertLess(got["A"], 1.0)

    def test_an_item_the_better_performances_get_wrong_is_called_out(self) -> None:
        items = ["A", "B", "C"]
        rows = rows_from([[0, 1, 1], [0, 1, 1], [1, 0, 0], [1, 0, 0]], items)
        report = {row["item"]: row for row in ia.analyse(rows, items)}
        self.assertLess(report["A"]["discrimination"], 0)
        self.assertTrue(any("negative" in flag for flag in report["A"]["flags"]))

    def test_alpha_is_undefined_rather_than_zero_when_nothing_varies(self) -> None:
        items = ["A", "B"]
        self.assertIsNone(ia.alpha(rows_from([[1, 1], [1, 1], [1, 1]], items), items))


class RealQuizTests(unittest.TestCase):
    """What the project's own instrument turns out to be."""

    def setUp(self) -> None:
        folder = ROOT / "experiments" / "PROP-EXP-MEM-007" / "results" / "quiz"
        self.rows, _key, rendered = ia.responses([folder])
        self.items = [item["id"] for item in rendered if item["kind"] == "fact"]

    def test_most_of_the_quiz_is_answered_correctly_by_everyone(self) -> None:
        # Recorded because it is the finding, not because it should stay true:
        # three quarters of the fact questions separate nothing.
        report = ia.analyse(self.rows, self.items)
        dead = [row for row in report if row["difficulty"] >= ia.CEILING]
        self.assertGreater(len(dead), len(self.items) // 2)

    def test_the_contested_questions_are_the_ones_carrying_the_measurement(self) -> None:
        # They were nearly deleted for being contested. They are the four
        # highest-discriminating items in the instrument.
        report = {row["item"]: row for row in ia.analyse(self.rows, self.items)}
        ranked = sorted((row for row in report.values() if row["discrimination"] is not None),
                        key=lambda row: -row["discrimination"])
        top = {row["item"] for row in ranked[:4]}
        self.assertTrue({"Q28", "Q29", "Q30"} <= top, top)


if __name__ == "__main__":
    unittest.main()
