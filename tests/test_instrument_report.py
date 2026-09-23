"""The one page a buyer reads: what it must say, and what it must refuse to say."""

from __future__ import annotations

import csv
import json
import math
import sys
import tempfile
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


class CostingAbsentTests(unittest.TestCase):
    """Off by default, and off means byte-for-byte unchanged.

    A costing section is the buyer's to ask for. A page that prints an empty
    one, or a placeholder, or an "n/a", has invented a number-shaped hole where
    the buyer's own figures belong and invited someone to fill it in by eye.
    """

    def test_the_page_without_costing_flags_is_the_page_as_it_was(self) -> None:
        # The guard on every other test in this file: the whole costing feature
        # is required to be invisible until asked for.
        self.assertEqual(ir.render(record(SAMPLE, 0.7), "T", "twenty models"),
                         ir.render(record(SAMPLE, 0.7), "T", "twenty models", costing=None))

    def test_no_money_word_reaches_a_page_nobody_asked_to_cost(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models").lower()
        for word in ("eur", "usd", "currency", "per year", "a year", "cost per run",
                     "n/a", "runs-per-year", "annual"):
            self.assertNotIn(word, page, "costing leaked %r into an uncosted page" % word)

    def test_asking_for_nothing_produces_no_costing_at_all(self) -> None:
        self.assertIsNone(ir.Costing.declared())
        # --currency alone is not a request to cost anything: it has a default,
        # so its presence can never be read as the buyer opting in.
        self.assertIsNone(ir.Costing.declared(currency="USD"))

    def test_the_real_audit_page_is_unchanged_without_the_flags(self) -> None:
        report = json.loads((AUDIT / "report-computer_security-top20.json")
                            .read_text(encoding="utf-8"))
        self.assertNotIn("EUR", ir.render(report, "MMLU computer_security", "the top 20"))


class CostingRefusalTests(unittest.TestCase):
    """A wrong number in a currency is worse than no number at all.

    Every figure in the costing is the buyer's rate times a count. That makes a
    bad rate silent: it produces a plausible page with a wrong cheque in it. So
    each way of being bad exits naming itself.
    """

    def refusal(self, **kwargs) -> str:
        with self.assertRaises(SystemExit) as caught:
            ir.Costing.declared(**kwargs)
        return str(caught.exception)

    def test_a_cost_of_zero_or_less_is_refused_rather_than_costed(self) -> None:
        for bad in ("0", "0.0", "-1", "-0.004"):
            message = self.refusal(cost_per_run=bad, runs_per_year="12")
            self.assertIn("--cost-per-run", message)
            self.assertIn("free or negative", message)

    def test_a_non_numeric_rate_names_itself_instead_of_crashing(self) -> None:
        for bad in ("abc", "EUR 0.004", "0,004", "$1", ""):
            message = self.refusal(cost_per_run=bad, runs_per_year="12")
            self.assertIn("--cost-per-run", message)
            self.assertIn("not a number", message)

    def test_an_infinite_or_undefined_rate_is_refused(self) -> None:
        for bad in ("nan", "inf", "-inf"):
            self.assertIn("not a finite number", self.refusal(cost_per_run=bad, runs_per_year="12"))

    def test_running_the_suite_less_than_once_a_year_is_refused(self) -> None:
        for bad in ("0", "0.5", "-3"):
            message = self.refusal(cost_per_run="0.004", runs_per_year=bad)
            self.assertIn("--runs-per-year", message)
            self.assertIn("at least 1", message)

    def test_a_rate_without_a_frequency_does_not_quietly_become_once_a_year(self) -> None:
        message = self.refusal(cost_per_run="0.004")
        self.assertIn("--runs-per-year", message)
        self.assertIn("will not assume a frequency you did not state", message)

    def test_a_frequency_without_a_rate_is_refused_too(self) -> None:
        message = self.refusal(runs_per_year="12")
        self.assertIn("not what a run costs you", message)

    def test_two_disagreeing_sources_of_truth_for_the_cost_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            table = Path(folder) / "costs.csv"
            table.write_text("item,cost\nA,0.01\n", encoding="utf-8")
            message = self.refusal(cost_per_run="0.004", cost_table=table, runs_per_year="12")
        self.assertIn("disagree by construction", message)

    def test_an_empty_currency_is_refused_because_every_figure_carries_its_unit(self) -> None:
        self.assertIn("--currency", self.refusal(cost_per_run="0.004", runs_per_year="12",
                                                 currency="  "))

    def test_refusals_are_ascii_so_a_windows_console_can_print_them(self) -> None:
        # A refusal that cannot be encoded to the console becomes a traceback
        # about encoding, which tells the buyer nothing about their input.
        for kwargs in ({"cost_per_run": "abc", "runs_per_year": "12"},
                       {"cost_per_run": "0", "runs_per_year": "12"},
                       {"cost_per_run": "0.004", "runs_per_year": "0"},
                       {"cost_per_run": "0.004"},
                       {"runs_per_year": "12"}):
            self.refusal(**kwargs).encode("ascii")


class CostingFiguresTests(unittest.TestCase):
    """Three numbers, each traceable to a count already on the page."""

    def costed(self, **kwargs) -> str:
        kwargs.setdefault("cost_per_run", "0.01")
        kwargs.setdefault("runs_per_year", "10")
        return ir.render(record(SAMPLE, 0.7), "T", "twenty models",
                         ir.Costing.declared(**kwargs))

    def test_the_three_figures_are_the_rate_times_the_counts_on_the_page(self) -> None:
        # SAMPLE: 6 counted, 2 carrying, so 4 carry nothing; C and D are the
        # only two on the drop list. At 0.01 a run and 10 runs a year.
        page = self.costed()
        self.assertIn("Running all 6 items costs EUR 0.60 a year", page)
        self.assertIn("The 4 items that carry nothing cost EUR 0.40 of that", page)
        self.assertIn("Dropping the 2 items this page puts on the drop list saves EUR 0.20", page)
        self.assertIn("6 items x EUR 0.01 an item-run x 10 runs a year", page)

    def test_the_saving_is_a_share_of_the_suite_not_of_the_dead_weight(self) -> None:
        # 2 of 6 items, so a third. Quoting 4 of 6 would be the overstatement.
        self.assertIn("33% of what the suite costs you", self.costed())

    def test_the_currency_is_the_buyers_and_nothing_is_converted(self) -> None:
        page = self.costed(currency="GBP")
        self.assertIn("GBP 0.60", page)
        self.assertNotIn("EUR", page)

    def test_a_rate_smaller_than_a_cent_is_printed_and_not_rounded_to_zero(self) -> None:
        page = self.costed(cost_per_run="0.0004")
        self.assertIn("EUR 0.0004 an item-run", page)
        self.assertNotIn("EUR 0.00 an item-run", page)

    def test_the_time_saving_is_stated_in_hours_beside_the_money(self) -> None:
        page = self.costed(seconds_per_run="30")
        self.assertIn("Running all 6 items takes 30 minutes of item-run time a year", page)
        self.assertIn("Dropping the 2 items on the drop list gives back 10 minutes", page)
        self.assertIn("not time on a clock", page)

    def test_time_can_be_costed_without_money(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models",
                         ir.Costing.declared(seconds_per_run="30", runs_per_year="10"))
        self.assertIn("of item-run time a year", page)
        self.assertNotIn("EUR", page)


class CostingOverstatementTests(unittest.TestCase):
    """The one way this section could lie, pinned from both sides.

    The page says 107 items carry nothing and puts 78 of them on the drop list.
    A costing that charges the saving to all 107 inflates it by a third using
    precisely the items the page has just refused to delete -- the ones still
    separating respondents, and the ones whose answer key has not been checked
    yet. It must be counted on the drop list and on nothing else.
    """

    def report(self) -> dict:
        return json.loads((AUDIT / "report-computer_security-top20.json")
                          .read_text(encoding="utf-8"))

    def test_the_saving_is_counted_on_the_drop_list_and_not_on_the_dead_weight(self) -> None:
        report = self.report()
        costing = ir.Costing.declared(cost_per_run="1", runs_per_year="1")
        droppable, measuring, backwards = ir.to_drop(report["per_item"])
        page = ir.render(report, "MMLU computer_security", "the top 20", costing)

        counted = report["effective_length"]["items_counted"]
        dead = counted - report["effective_length"]["items_carrying"]
        self.assertEqual((counted, dead, len(droppable)), (111, 107, 78))
        self.assertIn("saves EUR 78.00 a year", page)
        self.assertNotIn("saves EUR 107.00", page)
        self.assertNotIn("saves EUR 83.00", page)  # nor the near-constant count

    def test_an_item_held_back_from_deletion_is_never_counted_as_a_saving(self) -> None:
        report = self.report()
        costing = ir.Costing.declared(cost_per_run="1", runs_per_year="1")
        droppable, measuring, backwards = ir.to_drop(report["per_item"])
        self.assertTrue(measuring and backwards, "fixture no longer exercises the held-back path")
        self.assertEqual(costing.annual_money(droppable), float(len(droppable)))
        self.assertNotIn(costing.annual_money(droppable),
                         (float(len(droppable) + len(measuring) + len(backwards)),))

    def test_the_page_accounts_for_every_item_it_did_not_count_as_a_saving(self) -> None:
        # An earlier draft explained 5 of the 29 and left 24 unexplained, which
        # reads as though the saving had been trimmed for no stated reason.
        report = self.report()
        page = ir.render(report, "MMLU computer_security", "the top 20",
                         ir.Costing.declared(cost_per_run="1", runs_per_year="1"))
        self.assertIn("not on all 107 that carry nothing. Of the other 29:", page)
        self.assertIn("1 still separates respondents", page)
        self.assertIn("4 are waiting on the key check", page)
        self.assertIn("24 do vary between respondents", page)

    def test_a_page_with_nothing_to_drop_reports_a_saving_of_zero(self) -> None:
        alive = [item("A", 0.5, 0.6), item("B", 0.45, 0.55), item("C", 0.4, 0.5)]
        page = ir.render(record(alive, 0.7), "T", "twenty models",
                         ir.Costing.declared(cost_per_run="1", runs_per_year="1"))
        self.assertIn("the saving available today is EUR 0.00", page)
        self.assertNotIn("saves EUR", page)

    def test_the_assumption_is_stated_in_the_body_beside_the_number(self) -> None:
        page = ir.render(record(SAMPLE, 0.7), "T", "twenty models",
                         ir.Costing.declared(cost_per_run="0.01", runs_per_year="10"))
        body = body_of(page)
        self.assertIn("assumes every item costs you the same to run", body)
        self.assertIn("usually false", body)
        # And the costs that do not go away when an item does.
        self.assertIn("billed per run of the whole suite rather than per item", body)
        self.assertIn("saving on this population", body)

    def test_the_costing_carries_no_statistical_vocabulary_either(self) -> None:
        body = body_of(ir.render(record(SAMPLE, 0.7), "T", "twenty models",
                                 ir.Costing.declared(cost_per_run="0.01", runs_per_year="10",
                                                     seconds_per_run="5"))).lower()
        for word in ("alpha", "discrimination", "correlation", "cronbach", "variance",
                     "internal consistency", "standard error", "p-value"):
            self.assertNotIn(word, body, "jargon %r reached the costed body" % word)

    def test_no_stray_percent_escape_survives_the_costing(self) -> None:
        self.assertNotIn("%%", ir.render(record(SAMPLE, 0.7), "T", "twenty models",
                                         ir.Costing.declared(cost_per_run="0.01",
                                                             runs_per_year="10",
                                                             seconds_per_run="5")))


class CostTableTests(unittest.TestCase):
    """When the buyer can price the items individually, stop assuming."""

    def table(self, folder: str, rows: list[tuple[str, object]]) -> Path:
        path = Path(folder) / "costs.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["item", "cost"])
            writer.writerows(rows)
        return path

    def test_per_item_costs_replace_the_equal_cost_assumption(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            # C and D are the drop list; price them high to prove the money
            # follows the item rather than the count.
            path = self.table(folder, [("A", 0.01), ("B", 0.01), ("C", 1.0), ("D", 1.0),
                                       ("E", 0.01), ("F", 0.01)])
            page = ir.render(record(SAMPLE, 0.7), "T", "twenty models",
                             ir.Costing.declared(cost_table=path, runs_per_year="10"))
        self.assertIn("Running all 6 items costs EUR 20.40 a year", page)
        self.assertIn("Dropping the 2 items this page puts on the drop list saves EUR 20.00", page)
        self.assertIn("do not assume the items cost the same", page)
        self.assertNotIn("assumes every item costs you the same", page)

    def test_an_item_with_no_cost_is_refused_rather_than_priced_at_zero(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = self.table(folder, [("A", 0.01), ("B", 0.01), ("C", 0.01)])
            costing = ir.Costing.declared(cost_table=path, runs_per_year="10")
            with self.assertRaises(SystemExit) as caught:
                ir.render(record(SAMPLE, 0.7), "T", "twenty models", costing)
        message = str(caught.exception)
        self.assertIn("prices 3 items, but the analysis counts 6", message)
        for missing in ("`D`", "`E`", "`F`"):
            self.assertIn(missing, message)

    def test_a_bad_cost_in_the_table_names_the_item_it_came_from(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = self.table(folder, [("A", 0.01), ("B", "free")])
            with self.assertRaises(SystemExit) as caught:
                ir.Costing.declared(cost_table=path, runs_per_year="10")
        self.assertIn("'B'", str(caught.exception))
        self.assertIn("not a number", str(caught.exception))

    def test_one_item_priced_twice_and_differently_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = self.table(folder, [("A", 0.01), ("A", 0.02)])
            with self.assertRaises(SystemExit) as caught:
                ir.Costing.declared(cost_table=path, runs_per_year="10")
        self.assertIn("two different costs", str(caught.exception))

    def test_a_table_with_no_cost_column_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "costs.csv"
            path.write_text("item,notes\nA,cheap\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as caught:
                ir.Costing.declared(cost_table=path, runs_per_year="10")
        self.assertIn("no column named", str(caught.exception))


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
