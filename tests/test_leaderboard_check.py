"""What a leaderboard alone can establish, and everything it must refuse to say.

The free check exists to be read by a stranger with nobody standing beside it to
explain what it left out, so most of what is pinned here is the leaving out: the
refusals, the two directions the assumptions can be wrong in, and the case where
the honest answer is "your ranking is fine" and the tool has to say that instead
of manufacturing an alarm.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import leaderboard_check as lc  # noqa: E402


def write(text: str, name: str = "board.csv") -> Path:
    path = Path(tempfile.mkdtemp()) / name
    path.write_text(text, encoding="utf-8")
    return path


def board(pairs: list[tuple[str, float]], header: str = "model,score") -> Path:
    body = "".join("%s,%s\n" % (model, score) for model, score in pairs)
    return write(header + "\n" + body)


# A field genuinely spread out: ten-point gaps on a thousand items, where the
# error on a difference is about 1.6 points. Nothing here should be called into
# question by the check.
FAR_APART = [("alpha", 90.0), ("beta", 80.0), ("gamma", 70.0),
             ("delta", 60.0), ("epsilon", 50.0)]

# A field inside its own error bar: tenths of a point apart on a hundred items,
# where one score alone carries an error of about 3.4 points.
TIGHT = [("alpha", 87.0), ("beta", 86.9), ("gamma", 86.5),
         ("delta", 86.2), ("epsilon", 85.9)]


class ItemCountTests(unittest.TestCase):
    """Without n there is no sampling error, so there is no report."""

    def test_it_refuses_to_run_without_the_item_count(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            lc.main(["--table", str(board(FAR_APART))])
        message = str(caught.exception)
        self.assertIn("--items is required", message)
        self.assertIn("sqrt(p(1-p)/n)", message)

    def test_the_item_count_is_never_inferred_from_the_number_of_models(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            lc.required_items(None)
        self.assertIn("never assumed", str(caught.exception))

    def test_an_item_count_below_one_is_refused(self) -> None:
        for given in (0, -5):
            with self.assertRaises(SystemExit) as caught:
                lc.required_items(given)
            self.assertIn("undefined at n=0", str(caught.exception))

    def test_an_item_count_that_is_not_a_whole_number_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            lc.required_items("lots")
        self.assertIn("not a whole number", str(caught.exception))


class ScaleTests(unittest.TestCase):
    """0-1 or 0-100 is the whole answer, not a rounding of it."""

    def test_a_board_that_could_be_proportions_or_percentages_is_refused(self) -> None:
        path = board([("alpha", 0.87), ("beta", 0.86), ("gamma", 0.85)])
        with self.assertRaises(SystemExit) as caught:
            lc.read_leaderboard(path)
        message = str(caught.exception)
        self.assertIn("--scale proportion", message)
        self.assertIn("factor of a hundred", message)

    def test_the_ambiguity_is_resolved_by_declaring_it_and_never_by_guessing(self) -> None:
        path = board([("alpha", 0.87), ("beta", 0.86), ("gamma", 0.85)])
        rows, scale = lc.read_leaderboard(path, "proportion")
        self.assertEqual(scale, "proportion")
        self.assertAlmostEqual(rows[0]["score"], 0.87)
        # Declared the other way the same file is a benchmark nobody beats 1% on,
        # and every error below it changes by two orders of magnitude.
        other, _scale = lc.read_leaderboard(path, "percent")
        self.assertAlmostEqual(other[0]["score"], 0.0087)
        self.assertLess(lc.standard_error(other[0]["score"], 100),
                        lc.standard_error(rows[0]["score"], 100) / 3)

    def test_a_score_above_one_settles_the_scale_with_no_judgement_needed(self) -> None:
        rows, scale = lc.read_leaderboard(board(FAR_APART))
        self.assertEqual(scale, "percent")
        self.assertAlmostEqual(rows[0]["score"], 0.90)

    def test_a_score_outside_the_plausible_range_is_refused_not_clamped(self) -> None:
        for bad in (150.0, -3.0):
            path = board([("alpha", 90.0), ("beta", bad), ("gamma", 70.0)])
            with self.assertRaises(SystemExit) as caught:
                lc.read_leaderboard(path)
            self.assertIn("'beta'", str(caught.exception))
            self.assertIn("outside 0 to", str(caught.exception))

    def test_a_declared_proportion_scale_still_refuses_a_percentage_in_the_column(self) -> None:
        path = board([("alpha", 0.9), ("beta", 87.0), ("gamma", 0.7)])
        with self.assertRaises(SystemExit) as caught:
            lc.read_leaderboard(path, "proportion")
        self.assertIn("outside 0 to 1", str(caught.exception))


class TableRefusalTests(unittest.TestCase):
    def test_fewer_than_three_models_is_refused(self) -> None:
        path = board([("alpha", 90.0), ("beta", 80.0)])
        with self.assertRaises(SystemExit) as caught:
            lc.read_leaderboard(path)
        self.assertIn("fewer than three", str(caught.exception))

    def test_a_non_numeric_score_is_refused_naming_the_model(self) -> None:
        path = board([("alpha", 90.0), ("beta", "n/a"), ("gamma", 70.0)])
        with self.assertRaises(SystemExit) as caught:
            lc.read_leaderboard(path)
        self.assertIn("'beta'", str(caught.exception))
        self.assertIn("not a score", str(caught.exception))

    def test_a_model_listed_twice_is_refused_because_every_count_would_be_wrong(self) -> None:
        path = board([("alpha", 90.0), ("beta", 80.0), ("alpha", 70.0), ("gamma", 60.0)])
        with self.assertRaises(SystemExit) as caught:
            lc.read_leaderboard(path)
        self.assertIn("appears twice", str(caught.exception))

    def test_columns_it_cannot_identify_are_refused_with_the_names_it_looked_for(self) -> None:
        path = write("thing,number\na,90\nb,80\nc,70\n")
        with self.assertRaises(SystemExit) as caught:
            lc.read_leaderboard(path)
        self.assertIn("no column named", str(caught.exception))
        self.assertIn("thing, number", str(caught.exception))

    def test_the_usual_leaderboard_column_names_are_accepted(self) -> None:
        path = board(FAR_APART, header="model_name,accuracy")
        rows, _scale = lc.read_leaderboard(path)
        self.assertEqual(rows[0]["model"], "alpha")


class DoesNotCryWolfTests(unittest.TestCase):
    """A field that is genuinely spread out must be reported as one."""

    def test_wide_gaps_on_a_long_test_are_reported_as_supported(self) -> None:
        rows, scale = lc.read_leaderboard(board(FAR_APART))
        found = lc.check(rows, items=1000)
        self.assertEqual(found["indistinguishable_from_the_leader"]["count"], 0)
        self.assertEqual(found["adjacent_pairs"]["not_separated_at_95"], 0)
        self.assertEqual(found["top_group"]["orderings_unsupported"], 0)
        self.assertFalse(found["top_group"]["whole_group_unorderable"])

        page = lc.render(found, "board.csv", scale)
        self.assertIn("Nothing here is an accusation", page)
        self.assertIn("Every other model on this board is separated", page)
        # And it does not reach for the language it uses when the board is tight.
        self.assertNotIn("does not order the leading group", page)

    def test_a_clean_ordering_is_not_sold_as_a_clean_benchmark(self) -> None:
        rows, scale = lc.read_leaderboard(board(FAR_APART))
        page = lc.render(lc.check(rows, items=1000), "board.csv", scale)
        self.assertIn("narrow clean bill", page)
        self.assertIn("keyed correctly", page)


class CompressionTests(unittest.TestCase):
    """A top cluster inside the error bar, and the exact claim that licenses."""

    def test_a_tight_top_cluster_is_inside_the_error_bar(self) -> None:
        rows, _scale = lc.read_leaderboard(board(TIGHT))
        found = lc.check(rows, items=100)
        # One score on 100 items at 87% carries an error of about 3.4 points;
        # the whole group spans 1.1.
        self.assertAlmostEqual(found["typical_standard_error_pct"], 3.4, places=1)
        self.assertAlmostEqual(found["top_group"]["span_pct"], 1.1, places=6)
        self.assertTrue(found["top_group"]["whole_group_unorderable"])
        self.assertEqual(found["top_group"]["orderings_unsupported"], 4)
        self.assertEqual(found["indistinguishable_from_the_leader"]["count"], 4)
        self.assertEqual(found["adjacent_pairs"]["inside_one_standard_error"], 4)

    def test_the_same_board_on_a_long_enough_test_orders_itself(self) -> None:
        # The compression is a joint fact about the gaps and the item count, so
        # the finding has to move when the item count does.
        rows, _scale = lc.read_leaderboard(board(TIGHT))
        self.assertEqual(lc.check(rows, items=100)["adjacent_pairs"]["not_separated_at_95"], 4)
        self.assertEqual(lc.check(rows, items=50_000_000)["adjacent_pairs"]["not_separated_at_95"], 0)

    def test_clustering_is_never_reported_as_a_verdict_on_the_benchmark(self) -> None:
        rows, scale = lc.read_leaderboard(board(TIGHT))
        page = lc.render(lc.check(rows, items=100), "board.csv", scale)
        self.assertIn("It licenses nothing about the benchmark", page)
        self.assertIn("The models really are that close", page)
        self.assertIn("this page does not offer one", page)

    def test_the_headline_tie_count_is_stated_plainly(self) -> None:
        rows, scale = lc.read_leaderboard(board(TIGHT))
        found = lc.check(rows, items=100)
        self.assertIn("cannot be separated from alpha",
                      found["indistinguishable_from_the_leader"]["reading"])
        page = lc.render(found, "board.csv", scale)
        self.assertIn("4 of the 4 other models cannot be told apart from alpha", page)
        # A non-rejection is not a finding of equality, and the page says so.
        self.assertIn("not a claim that they are equal", page)


class WhatItRefusesToSayTests(unittest.TestCase):
    """The most important section: the three claims that need the real audit."""

    def test_the_page_names_the_three_things_it_cannot_establish(self) -> None:
        rows, scale = lc.read_leaderboard(board(TIGHT))
        page = lc.render(lc.check(rows, items=100), "board.csv", scale)
        self.assertIn("it is not an audit of the benchmark", page)
        self.assertIn("keyed to the wrong answer", page)
        self.assertIn("Dead items", page)
        self.assertIn("Effective length", page)

    def test_it_names_what_the_real_audit_adds_and_what_that_needs(self) -> None:
        rows, scale = lc.read_leaderboard(board(TIGHT))
        page = lc.render(lc.check(rows, items=100), "board.csv", scale)
        self.assertIn("trial, item, correct", page)
        self.assertIn("item_analysis.py", page)

    def test_the_limits_are_a_section_of_their_own_and_not_a_closing_footnote(self) -> None:
        rows, scale = lc.read_leaderboard(board(FAR_APART))
        page = lc.render(lc.check(rows, items=1000), "board.csv", scale)
        limits = page.index("## What this is not")
        self.assertLess(limits, len(page) / 2)
        # It survives in the record too, so a caller reading the JSON cannot
        # print the findings without them.
        found = lc.check(rows, items=1000)
        self.assertEqual(len(found["cannot_establish"]), 3)
        self.assertIn("item_analysis.py", found["what_the_audit_adds"])

    def test_the_independence_assumption_is_stated_in_the_direction_it_hurts(self) -> None:
        rows, scale = lc.read_leaderboard(board(TIGHT))
        page = lc.render(lc.check(rows, items=100), "board.csv", scale)
        self.assertIn("Items are independent and scored right or wrong", page)
        self.assertIn("the true error is **larger**", page)
        self.assertIn("undercount", page)

    def test_the_paired_test_it_cannot_run_is_named_as_the_other_direction(self) -> None:
        rows, scale = lc.read_leaderboard(board(TIGHT))
        page = lc.render(lc.check(rows, items=100), "board.csv", scale)
        self.assertIn("conservative in this one direction", page)
        self.assertIn("could only find *fewer* pairs tied", page)

    def test_a_score_at_the_end_of_the_range_carries_its_own_warning(self) -> None:
        rows, scale = lc.read_leaderboard(board([("alpha", 100.0), ("beta", 60.0),
                                                 ("gamma", 50.0)]))
        found = lc.check(rows, items=200)
        self.assertEqual(found["scores_at_the_ends_of_the_range"], ["alpha"])
        page = lc.render(found, "board.csv", scale)
        self.assertIn("known failure of this interval", page)


class ArithmeticTests(unittest.TestCase):
    def test_the_standard_error_is_the_binomial_one(self) -> None:
        self.assertAlmostEqual(lc.standard_error(0.5, 100), 0.05)
        self.assertAlmostEqual(lc.standard_error(0.87, 100), 0.0336303, places=6)

    def test_the_error_on_a_difference_is_the_unpaired_one(self) -> None:
        got = lc.difference_error(0.9, 0.8, 1000)
        self.assertAlmostEqual(got, (0.9 * 0.1 / 1000 + 0.8 * 0.2 / 1000) ** 0.5)
        self.assertGreater(got, lc.standard_error(0.9, 1000))

    def test_the_top_group_shrinks_to_the_board_when_the_board_is_short(self) -> None:
        rows, _scale = lc.read_leaderboard(board(TIGHT))
        self.assertEqual(lc.check(rows, items=100, top=20)["top_group"]["size"], 5)

    def test_a_top_group_of_fewer_than_two_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            lc.main(["--table", str(board(TIGHT)), "--items", "100", "--top", "1"])
        self.assertIn("no ordering in it", str(caught.exception))


class EndToEndTests(unittest.TestCase):
    def test_the_command_prints_a_page_and_the_json_flag_prints_the_record(self) -> None:
        import io
        import contextlib

        path = str(board(TIGHT))
        page = io.StringIO()
        with contextlib.redirect_stdout(page):
            lc.main(["--table", path, "--items", "100"])
        self.assertIn("# What this leaderboard can and cannot tell you", page.getvalue())

        record = io.StringIO()
        with contextlib.redirect_stdout(record):
            lc.main(["--table", path, "--items", "100", "--json"])
        import json
        got = json.loads(record.getvalue())
        self.assertEqual(got["record_version"], "RA-PSI-LEADERBOARD-V1")
        self.assertEqual(got["items"], 100)
        self.assertEqual(got["scale"], "percent")


if __name__ == "__main__":
    unittest.main()
