"""The one page a buyer reads: what it must say, and what it must refuse to say."""

from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import instrument_report as ir  # noqa: E402
import item_analysis as ia  # noqa: E402

AUDIT = ROOT / "experiments" / "PUBLIC-AUDIT-2026-09"


def item(name: str, difficulty: float, discrimination: float | None) -> dict:
    return {"item": name, "difficulty": difficulty, "discrimination": discrimination,
            "alpha_without": None, "flags": []}


def record(per_item: list[dict], alpha: float | None, trials: int = 20) -> dict:
    counted = len(per_item)
    carrying = [row for row in per_item
                if row["discrimination"] is not None and row["discrimination"] >= ia.WEAK
                and ia.FLOOR < row["difficulty"] < ia.CEILING]
    constant = [row for row in per_item if ir.is_constant(row)]
    return {"record_version": "RA-PSI-ITEMS-V1", "source": "responses.csv", "trials": trials,
            "items": counted, "alpha": alpha, "per_item": per_item,
            "effective_length": {"items_counted": counted, "items_carrying": len(carrying),
                                 "items_all_but_a_few_answer_alike": len(constant),
                                 "carrying_items": [row["item"] for row in carrying],
                                 "reading": "a test of %d items that measures with %d"
                                            % (counted, len(carrying))}}


def body_of(page: str) -> str:
    """Everything before the appendix — the part a buyer actually reads."""
    head, _, _tail = page.partition(ir.APPENDIX)
    return head


SAMPLE = [item("A", 0.5, 0.6), item("B", 0.45, 0.55), item("C", 0.98, None),
          item("D", 0.02, None), item("E", 0.4, -0.3), item("F", 0.6, 0.05)]


class ReliabilityRefusalTests(unittest.TestCase):
    """A reliability figure is a property of a test and its respondents both.

    This project's own audit put the same 111 MMLU items at 0.948 across 91
    models and -0.442 across the top 20. A page that prints one of those and
    calls the instrument good or bad is wrong in a way that travels.
    """

    def test_the_reliability_figure_never_appears_in_the_body(self) -> None:
        for alpha in (0.948, 0.51, -0.442):
            page = ir.render(record(SAMPLE, alpha), "T", "twenty models")
            self.assertNotIn("%.3f" % alpha, body_of(page), "alpha %s leaked into the body" % alpha)
            self.assertNotIn("alpha", body_of(page).lower())

    def test_the_page_never_calls_the_instrument_good_or_bad(self) -> None:
        for alpha in (0.98, -0.6):
            page = ir.render(record(SAMPLE, alpha), "T", "twenty models").lower()
            for verdict in ("a good instrument", "a bad instrument", "highly reliable",
                            "unreliable", "reliability is high", "reliability is low",
                            "this benchmark is sound", "passes", "fails"):
                self.assertNotIn(verdict, page, "page delivered the verdict %r" % verdict)

    def test_the_figure_is_printed_only_beside_the_population_that_produced_it(self) -> None:
        page = ir.render(record(SAMPLE, 0.948), "T", "twenty models")
        _head, _, appendix = page.partition(ir.APPENDIX)
        self.assertIn("0.948", appendix)
        self.assertIn("0.948 across all 91 models", appendix)
        self.assertIn("-0.442", appendix)

    def test_the_page_says_when_nobody_named_the_population(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", population=None)
        self.assertIn(ir.UNNAMED, page)

    def test_no_resolution_is_quoted_when_the_items_disagree_with_each_other(self) -> None:
        # A negative alpha is not a low reliability; it is a statement that
        # there is no single scale. An interval computed off it is arithmetic
        # dressed as a finding.
        self.assertIsNone(ir.resolution(record(SAMPLE, -0.442)))
        page = ir.render(record(SAMPLE, -0.442), "T", "twenty models")
        self.assertIn("cannot resolve any difference", page)
        self.assertIn("arithmetic dressed as a finding", page)


class ContestedItemRefusalTests(unittest.TestCase):
    """This project proposed deleting its four most-contested questions.

    It was corrected in public and then found those four were the four
    highest-discriminating items it had. Contested means load-bearing at least
    as often as it means broken.
    """

    def test_an_item_that_still_separates_respondents_is_never_on_the_drop_list(self) -> None:
        # Nearly unanimous and yet still discriminating: the exact shape that a
        # rule based on difficulty alone would delete.
        nearly = item("N", 0.96, 0.45)
        per_item = SAMPLE + [nearly]
        drop, measuring, _backwards = ir.to_drop(per_item)
        self.assertNotIn(nearly, drop)
        self.assertIn(nearly, measuring)

    def test_the_most_disagreed_about_items_are_named_as_keepers_not_candidates(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models")
        contested = ir.most_disagreement(SAMPLE)
        self.assertEqual([row["item"] for row in contested][0], "A")
        self.assertIn("Keep the contested items", page)
        for row in contested:
            self.assertIn("`%s`" % row["item"], page)
        self.assertIn("Disagreement is not evidence that an item is broken", page)

    def test_the_page_never_proposes_deleting_an_item_for_being_argued_about(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models").lower()
        for phrase in ("delete the contested", "drop the contested", "remove the contested",
                       "delete the disputed", "drop the disputed"):
            self.assertNotIn(phrase, page)

    def test_a_mis_keyed_item_is_sent_for_repair_before_it_can_be_deleted(self) -> None:
        # Deleting it destroys the only evidence that the key was wrong.
        suspect = item("K", 0.97, -0.4)
        drop, _measuring, backwards = ir.to_drop(SAMPLE + [suspect])
        self.assertNotIn(suspect, drop)
        self.assertIn(suspect, backwards)


class PlainLanguageTests(unittest.TestCase):
    def test_the_body_carries_no_statistical_vocabulary(self) -> None:
        body = body_of(ir.render(record(SAMPLE, 0.7), "T", "twenty models")).lower()
        for word in ("alpha", "discrimination", "correlation", "cronbach", "variance",
                     "internal consistency", "standard error", "p-value"):
            self.assertNotIn(word, body, "jargon %r reached the body" % word)

    def test_the_length_is_stated_as_a_sentence_a_buyer_can_repeat(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models")
        self.assertIn("a test of 6 items that measures with 2", page)

    def test_a_wrong_key_is_called_a_wrong_key_and_not_a_hard_question(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models")
        self.assertIn("the better performances are the ones marked wrong", page)
        self.assertIn("almost always a wrong answer key", page)
        self.assertIn("`E`", page)

    def test_the_page_states_what_size_of_difference_it_cannot_resolve(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models")
        self.assertIn("points out of 100", page)
        self.assertIn("three-point difference", page)

    def test_dropping_dead_items_is_offered_as_a_saving_not_a_loss(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models")
        self.assertIn("Drop 2 of those 2 items", page)
        self.assertIn("% of the runs", page)
        self.assertIn("keeps the same standing", page)

    def test_the_page_tells_the_reader_how_to_disprove_it(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models")
        self.assertIn("How to disprove this page", page)
        self.assertIn("python scripts/item_analysis.py --table responses.csv", page)


class RenderingDefectTests(unittest.TestCase):
    """The two defects the sibling report shipped, caught only by reading it."""

    def test_no_stray_percent_escape_survives_into_the_page(self) -> None:
        for alpha in (0.7, -0.4):
            self.assertNotIn("%%", ir.render(record(SAMPLE, alpha), "T", "twenty models"))

    def test_the_counts_in_the_body_and_the_appendix_are_the_same_counts(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models")
        body, _, appendix = page.partition(ir.APPENDIX)
        self.assertIn("**a test of 6 items that measures with 2**", body)
        self.assertIn("| Items counted | 6 |", appendix)
        self.assertIn("| Items carrying the measurement | 2 |", appendix)

    def test_every_item_it_says_needs_repair_is_named_somewhere_on_the_page(self) -> None:
        # An earlier draft printed twelve rows and "and 6 more", telling the
        # reader there was work it would not let them do.
        many = [item("x%d" % i, 0.4, -0.05 * (i + 1)) for i in range(15)]
        page = ir.render(record(many + [item("ok", 0.5, 0.6)], 0.7), "T", "twenty models")
        self.assertIn("Repair 15 items", page)
        for row in many:
            self.assertIn("`%s`" % row["item"], page)

    def test_a_windows_path_is_not_pasted_into_a_shell_command_as_written(self) -> None:
        got = record(SAMPLE, 0.7)
        got["source"] = "experiments\\PUBLIC-AUDIT-2026-09\\table.csv"
        page = ir.render(got, "T", "twenty models")
        self.assertIn("--table experiments/PUBLIC-AUDIT-2026-09/table.csv", page)
        self.assertNotIn("\\PUBLIC-AUDIT", page)

    def test_a_graded_record_is_refused_rather_than_read_as_right_and_wrong(self) -> None:
        graded = record(SAMPLE, 0.7)
        graded["record_version"] = "RA-PSI-GRADED-ITEMS-V1"
        with self.assertRaises(SystemExit) as caught:
            ir.render(graded)
        self.assertIn("graded record", str(caught.exception))


class RealDataTests(unittest.TestCase):
    """Rendered against the public MMLU audit, because a page nobody read is a draft."""

    def load(self, name: str) -> dict:
        return json.loads((AUDIT / name).read_text(encoding="utf-8"))

    def test_the_saturated_subset_reports_four_items_and_refuses_a_resolution(self) -> None:
        page = ir.render(self.load("report-computer_security-top20.json"),
                         "MMLU computer_security", "the top 20 models in HELM Lite v1.13.0")
        self.assertIn("a test of 111 items that measures with 4", page)
        self.assertIn("Ranking these respondents on this test ranks noise", page)
        self.assertNotIn("0.442", body_of(page))

    def test_the_same_items_on_the_full_field_do_get_a_resolution(self) -> None:
        # Same 111 questions, same answers, different population. The page is
        # allowed to say different things about them; it is not allowed to call
        # either one the instrument's grade.
        page = ir.render(self.load("report-computer_security.json"),
                         "MMLU computer_security", "all 91 models in HELM Lite v1.13.0")
        self.assertIn("points out of 100", body_of(page))
        self.assertNotIn("0.948", body_of(page))

    def test_the_drop_counts_add_up_to_the_count_the_body_quotes(self) -> None:
        report = self.load("report-computer_security-top20.json")
        drop, measuring, backwards = ir.to_drop(report["per_item"])
        self.assertEqual(len(drop) + len(measuring) + len(backwards),
                         report["effective_length"]["items_all_but_a_few_answer_alike"])
        page = ir.render(report, "MMLU computer_security", "the top 20")
        self.assertIn("Drop %d of those %d items"
                      % (len(drop), report["effective_length"]["items_all_but_a_few_answer_alike"]),
                      page)

    def test_the_resolution_matches_the_spread_of_the_real_total_scores(self) -> None:
        # The page recovers the total-score spread from alpha and the per-item
        # difficulties, because the record it reads carries no per-respondent
        # totals. That recovery is checked here against the actual responses.
        rows, items = ia.from_table(AUDIT / "helm-lite-mmlu-abstract_algebra.csv")
        measured = math.sqrt(ia.variance([float(sum(row[q] for q in items)) for row in rows]))
        derived = ir.resolution(self.load("report-abstract_algebra.json"))["total_sd_items"]
        self.assertAlmostEqual(measured, derived, delta=0.05)


if __name__ == "__main__":
    unittest.main()
