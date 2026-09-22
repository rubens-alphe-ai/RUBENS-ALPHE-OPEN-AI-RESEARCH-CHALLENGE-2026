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
        self.assertTrue(any("pass it" in flag for flag in report["A"]["flags"]))
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


class EffectiveLengthTests(unittest.TestCase):
    """The number a buyer reads: items counted against items measuring."""

    def test_constants_do_not_count_towards_what_a_test_measures_with(self) -> None:
        per_item = [{"item": "A", "difficulty": 1.0, "discrimination": None},
                    {"item": "B", "difficulty": 0.5, "discrimination": 0.6},
                    {"item": "C", "difficulty": 0.5, "discrimination": 0.02}]
        got = ia.effective_length(per_item)
        self.assertEqual(got["items_counted"], 3)
        self.assertEqual(got["items_carrying"], 1)
        self.assertEqual(got["carrying_items"], ["B"])
        self.assertIn("3 items that measures with 1", got["reading"])

    def test_our_own_quiz_measures_with_a_fraction_of_what_it_counts(self) -> None:
        folder = ROOT / "experiments" / "PROP-EXP-MEM-007" / "results" / "quiz"
        rows, _key, rendered = ia.responses([folder])
        items = [item["id"] for item in rendered if item["kind"] == "fact"]
        got = ia.effective_length(ia.analyse(rows, items))
        self.assertLess(got["items_carrying"], got["items_counted"] / 3)

class TableInputTests(unittest.TestCase):
    """Anyone's harness can emit three columns; almost none emit more."""

    def write(self, text: str) -> Path:
        folder = Path(tempfile.mkdtemp())
        path = folder / "responses.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_three_column_table_is_read_into_trials(self) -> None:
        path = self.write("trial,item,correct\n1,A,1\n1,B,0\n2,A,1\n2,B,1\n3,A,0\n3,B,1\n")
        rows, items = ia.from_table(path)
        self.assertEqual(items, ["A", "B"])
        self.assertEqual(len(rows), 3)

    def test_words_and_binary_numbers_both_read_as_correctness(self) -> None:
        path = self.write("run_id,question_id,is_correct\n1,A,true\n1,B,fail\n"
                          "2,A,PASS\n2,B,0\n3,A,1\n3,B,no\n")
        rows, _items = ia.from_table(path)
        self.assertEqual(rows[0]["A"], 1)
        self.assertEqual(rows[0]["B"], 0)

    def test_a_graded_score_is_refused_rather_than_rounded(self) -> None:
        # Rounding a 1-to-5 rubric here put every item at difficulty 1.0 and
        # told its owner they had a test measuring with nothing. A healthy
        # instrument declared dead, silently, is the worst answer available.
        path = self.write("trial,item,score\n1,A,4\n1,B,2\n2,A,5\n2,B,3\n3,A,3\n3,B,1\n")
        with self.assertRaises(SystemExit) as caught:
            ia.from_table(path)
        self.assertIn("graded score", str(caught.exception))
        self.assertIn("graded_items.py", str(caught.exception))

    def test_a_trial_missing_an_item_is_dropped_not_scored_zero(self) -> None:
        # Filling a zero would turn an unanswered item into a wrong one, which
        # is the difference between a gap in the data and a failure.
        path = self.write("trial,item,correct\n1,A,1\n1,B,1\n2,A,1\n3,A,1\n3,B,0\n")
        rows, _items = ia.from_table(path)
        self.assertEqual(len(rows), 2)

    def test_a_table_without_the_columns_says_which_are_missing(self) -> None:
        path = self.write("a,b,c\n1,2,3\n")
        with self.assertRaises(SystemExit) as caught:
            ia.from_table(path)
        self.assertIn("no column named", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
