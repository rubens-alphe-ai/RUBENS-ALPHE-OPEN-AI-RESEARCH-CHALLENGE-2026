"""Items that are scored rather than marked, and what the graded path refuses."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import graded_items as gi  # noqa: E402

FIVE = gi.Scale.declared(1, 5)


def rows_from(pattern: list[list[float]], items: list[str]) -> list[dict]:
    return [dict(zip(items, row)) for row in pattern]


def write(text: str) -> Path:
    path = Path(tempfile.mkdtemp()) / "scores.csv"
    path.write_text(text, encoding="utf-8")
    return path


class ScaleTests(unittest.TestCase):
    def test_a_mean_is_never_reported_without_the_range_it_sits_in(self) -> None:
        # 4.2 is near the ceiling of a 1-to-5 rubric and nowhere near the
        # ceiling of a 1-to-10 one. A mean alone cannot say which.
        items = ["A", "B"]
        rows = rows_from([[4, 1], [4, 5], [5, 3], [4, 2], [4, 4]], items)
        narrow = {row["item"]: row for row in gi.analyse(rows, items, gi.Scale.declared(1, 5))}["A"]
        wide = {row["item"]: row for row in gi.analyse(rows, items, gi.Scale.declared(1, 10))}["A"]
        self.assertEqual(narrow["mean"], wide["mean"])
        self.assertEqual(narrow["scale"], "1 to 5")
        self.assertGreater(narrow["position_in_range"], wide["position_in_range"])

    def test_a_range_with_no_width_is_refused_rather_than_divided_by(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            gi.Scale.declared(3, 3)
        self.assertIn("no range", str(caught.exception))

    def test_a_two_point_scale_is_sent_back_to_the_binary_script(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            gi.Scale.declared(1, 5, points=2)
        self.assertIn("item_analysis.py", str(caught.exception))

    def test_point_count_comes_from_the_declared_bounds_never_from_the_data(self) -> None:
        self.assertEqual(gi.Scale.declared(1, 5).points, 5)
        self.assertEqual(gi.Scale.declared(0, 4).points, 5)
        # Non-integer bounds have no derivable points, and none are invented.
        self.assertIsNone(gi.Scale.declared(0, 1.0).points)
        self.assertIsNone(gi.Scale.declared(0, 2.5).points)


class RefusalTests(unittest.TestCase):
    def test_the_scale_range_is_required_and_is_never_read_off_the_data(self) -> None:
        # Values run 1 to 4 here. A tool that inferred a 1-to-4 scale would call
        # a mean of 3.8 "at the ceiling" when on the real 1-to-5 rubric it is
        # not, and would report the rubric fully used when a fifth of it is not.
        path = write("trial,item,score\n1,A,1\n1,B,4\n2,A,4\n2,B,4\n3,A,3\n3,B,4\n")
        rows, items = gi.read_scores(path, gi.Scale.declared(1, 5))
        report = {row["item"]: row for row in gi.analyse(rows, items, gi.Scale.declared(1, 5))}
        self.assertEqual(report["B"]["position_in_range"], 0.75)
        self.assertEqual(report["B"]["levels_available"], 5)
        guessed = {row["item"]: row for row in gi.analyse(rows, items, gi.Scale.declared(1, 4))}
        self.assertEqual(guessed["B"]["position_in_range"], 1.0)
        # The two disagree about whether item B is dead. That disagreement is
        # the reason the range cannot be guessed.
        self.assertNotEqual(report["B"]["flags"], guessed["B"]["flags"])

    def test_a_score_outside_the_declared_scale_stops_the_run_and_is_not_clamped(self) -> None:
        path = write("trial,item,score\n1,A,1\n1,B,6\n2,A,4\n2,B,4\n3,A,3\n3,B,2\n")
        with self.assertRaises(SystemExit) as caught:
            gi.read_scores(path, gi.Scale.declared(1, 5))
        self.assertIn("outside the declared scale", str(caught.exception))
        self.assertIn("item 'B'", str(caught.exception))

    def test_a_non_numeric_score_column_says_to_use_the_binary_script(self) -> None:
        path = write("trial,item,score\n1,A,pass\n1,B,fail\n2,A,pass\n2,B,pass\n")
        with self.assertRaises(SystemExit) as caught:
            gi.read_scores(path, FIVE)
        self.assertIn("item_analysis.py", str(caught.exception))

    def test_the_collapse_check_reports_itself_as_not_run_rather_than_guessing(self) -> None:
        items = ["A", "B"]
        rows = rows_from([[0.1, 0.9], [0.4, 0.2], [0.8, 0.5]], items)
        scale = gi.Scale.declared(0, 1.0)
        got = gi.rubric_use(gi.analyse(rows, items, scale), scale)
        self.assertFalse(got["checked"])
        self.assertIn("no declared point count", got["reason"])

    def test_a_trial_missing_an_item_is_dropped_not_scored_at_the_floor(self) -> None:
        path = write("trial,item,score\n1,A,3\n1,B,4\n2,A,2\n3,A,5\n3,B,1\n")
        rows, _items = gi.read_scores(path, FIVE)
        self.assertEqual(len(rows), 2)


class DeadItemTests(unittest.TestCase):
    def test_an_item_everyone_scores_four_on_carries_nothing(self) -> None:
        # The binary version of this flag only fires at the ends of the scale.
        # A constant in the middle of a rubric is just as dead.
        items = ["A", "B", "C"]
        rows = rows_from([[4, 1, 5], [4, 5, 2], [4, 3, 3], [4, 2, 4]], items)
        report = {row["item"]: row for row in gi.analyse(rows, items, FIVE)}
        self.assertIn("every response scores 4", report["A"]["flags"][0])
        self.assertIsNone(report["A"]["discrimination"])
        self.assertEqual(gi.effective_length(list(report.values()))["items_that_never_vary"], 1)

    def test_an_item_at_the_ceiling_of_its_range_is_flagged_with_the_range_named(self) -> None:
        items = ["A", "B", "C"]
        rows = rows_from([[5, 1, 5], [5, 5, 2], [4.9, 3, 3], [5, 2, 4]], items)
        report = {row["item"]: row for row in gi.analyse(rows, items, FIVE)}
        self.assertTrue(any("top of the 1 to 5 scale" in flag for flag in report["A"]["flags"]))

    def test_scores_that_move_independently_of_the_rest_are_called_unrelated(self) -> None:
        # The other three items march together from 1 to 5; A's scores are a
        # permutation chosen to have exactly zero covariance with them.
        items = ["A", "B", "C", "D"]
        rows = rows_from([[4, 1, 1, 1], [1, 2, 2, 2], [3, 3, 3, 3], [5, 4, 4, 4], [2, 5, 5, 5]], items)
        report = {row["item"]: row for row in gi.analyse(rows, items, FIVE)}
        self.assertLess(abs(report["A"]["discrimination"]), gi.WEAK)
        self.assertTrue(any("unrelated" in flag for flag in report["A"]["flags"]))

    def test_an_item_the_better_performances_score_lower_on_is_called_out(self) -> None:
        items = ["A", "B", "C"]
        rows = rows_from([[5, 1, 1], [4, 2, 2], [2, 4, 4], [1, 5, 5]], items)
        report = {row["item"]: row for row in gi.analyse(rows, items, FIVE)}
        self.assertLess(report["A"]["discrimination"], 0)
        self.assertTrue(any("negative" in flag for flag in report["A"]["flags"]))

    def test_discrimination_is_measured_against_the_other_items_not_the_total(self) -> None:
        items = ["A", "B", "C", "D"]
        rows = rows_from([[5, 5, 5, 5], [1, 1, 1, 1], [5, 5, 1, 1], [1, 1, 5, 5]], items)
        got = {row["item"]: row["discrimination"] for row in gi.analyse(rows, items, FIVE)}
        self.assertLess(got["A"], 1.0)


class RubricCollapseTests(unittest.TestCase):
    """The failure mode a right/wrong item cannot have."""

    def test_a_five_point_rubric_graded_on_two_points_is_a_finding_about_the_rubric(self) -> None:
        items = ["A", "B", "C"]
        rows = rows_from([[1, 1, 5], [5, 5, 2], [1, 3, 3], [5, 4, 4], [5, 4, 1]], items)
        report = gi.analyse(rows, items, FIVE)
        by_item = {row["item"]: row for row in report}
        self.assertEqual(by_item["A"]["levels_used"], 2)
        self.assertTrue(any("2 of the 5 points" in flag for flag in by_item["A"]["flags"]))
        # It is invisible in the mean: item A and item B have the same one.
        self.assertEqual(by_item["A"]["mean"], by_item["B"]["mean"])
        self.assertFalse(any("points on the scale" in flag for flag in by_item["B"]["flags"]))

    def test_the_summary_counts_how_many_items_use_half_the_rubric_or_less(self) -> None:
        items = ["A", "B", "C"]
        rows = rows_from([[1, 1, 5], [5, 5, 2], [1, 3, 3], [5, 4, 4], [5, 4, 1]], items)
        got = gi.rubric_use(gi.analyse(rows, items, FIVE), FIVE)
        self.assertTrue(got["checked"])
        self.assertEqual(got["collapsed_items"], ["A"])
        self.assertIn("1 of 3 items", got["reading"])

    def test_a_dead_constant_item_is_not_also_reported_as_a_collapsed_rubric(self) -> None:
        # One level used is not a grader who ignores the middle of the scale;
        # it is an item that separates nothing, and it is already flagged as
        # that. Counting it twice would inflate a finding about the rubric.
        items = ["A", "B", "C"]
        rows = rows_from([[3, 1, 5], [3, 5, 2], [3, 3, 3], [3, 2, 4], [3, 4, 1]], items)
        got = gi.rubric_use(gi.analyse(rows, items, FIVE), FIVE)
        self.assertEqual(got["collapsed_items"], [])


class EffectiveLengthTests(unittest.TestCase):
    def test_a_graded_instrument_reports_the_same_sentence_a_binary_one_does(self) -> None:
        per_item = [{"item": "A", "position_in_range": 1.0, "discrimination": None, "sd": 0.0},
                    {"item": "B", "position_in_range": 0.5, "discrimination": 0.6, "sd": 1.2},
                    {"item": "C", "position_in_range": 0.5, "discrimination": 0.02, "sd": 1.1}]
        got = gi.effective_length(per_item)
        self.assertEqual(got["carrying_items"], ["B"])
        self.assertIn("3 items that measures with 1", got["reading"])


if __name__ == "__main__":
    unittest.main()
