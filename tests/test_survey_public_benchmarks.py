"""Which published benchmarks enter the survey, and which are counted out."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import survey_public_benchmarks as survey  # noqa: E402


class QuestionSetTests(unittest.TestCase):
    def test_a_scenario_carrying_settings_splits_on_the_comma_form(self) -> None:
        got = survey.question_set("mmlu:subject=anatomy,method=multiple_choice_joint,model=x")
        self.assertEqual(got, ("mmlu:subject=anatomy,method=multiple_choice_joint", ",model="))

    def test_a_scenario_carrying_no_settings_is_not_dropped(self) -> None:
        # The regression this file exists for. HELM writes `med_qa:model=x`
        # with a colon when a scenario has no settings of its own. Matching
        # only the comma form excluded eleven question-sets -- among them
        # GSM8K, MedQA and NarrativeQA -- from a table that claimed to cover
        # the field, and excluded them silently, which is worse than failing.
        self.assertEqual(survey.question_set("med_qa:model=x"), ("med_qa", ":model="))
        self.assertEqual(survey.question_set("gsm:model=x"), ("gsm", ":model="))

    def test_the_marker_is_returned_so_the_filter_matches_the_source(self) -> None:
        # Handing the importer the wrong separator selects nothing, or worse,
        # selects a neighbouring question-set.
        _key, marker = survey.question_set("legal_support,method=mcj,model=y")
        self.assertEqual(marker, ",model=")

    def test_a_run_naming_no_model_takes_no_part(self) -> None:
        self.assertIsNone(survey.question_set("scenario:subject=x"))
        self.assertIsNone(survey.question_set("model=leading"))

    def test_two_levels_of_one_scenario_are_different_question_sets(self) -> None:
        # `math:level=1` and `math:level=5` ask different questions. Pooling
        # them would put respondents together on items they never answered,
        # which is the one join error that invalidates everything downstream.
        one = survey.question_set("math:subject=algebra,level=1,model=a")[0]
        five = survey.question_set("math:subject=algebra,level=5,model=a")[0]
        self.assertNotEqual(one, five)


class SummaryTests(unittest.TestCase):
    def test_failures_are_counted_beside_the_successes(self) -> None:
        # A survey that reports only what worked is a survey of what worked.
        rows = [{"status": "audited", "respondents": 40, "items": 10, "items_carrying": 5,
                 "share_carrying_pct": 50.0, "items_running_backwards": 1, "alpha": 0.8},
                {"status": "failed", "reason": "metric is not binary"}]
        got = survey.summarise(rows)
        self.assertEqual(got["audited"], 1)
        self.assertEqual(got["failed"], 1)

    def test_nothing_audited_says_so_rather_than_reporting_zeroes(self) -> None:
        got = survey.summarise([{"status": "failed", "reason": "whatever"}])
        self.assertEqual(got["audited"], 0)
        self.assertIn("nothing to summarise", got["note"])

    def test_an_item_running_backwards_carries_its_false_alarm_rate(self) -> None:
        # The flag we sell on. Publishing a count of them without pointing at
        # how often the flag is wrong would be the single most misleading
        # number this survey could print.
        rows = [{"status": "audited", "respondents": 40, "items": 10, "items_carrying": 5,
                 "share_carrying_pct": 50.0, "items_running_backwards": 2, "alpha": 0.8}]
        self.assertIn("DETECTION-2026-09", survey.summarise(rows)["note"])


class FailureKindTests(unittest.TestCase):
    """A dropped connection is not a verdict on somebody else's benchmark."""

    def test_a_dropped_connection_is_not_a_refusal(self) -> None:
        # The first run of this survey produced 107 of these and would have
        # reported them as benchmarks that could not be audited -- a finding
        # about other people's work invented out of our own rate limit.
        self.assertEqual(survey.failure_kind(
            "http.client.RemoteDisconnected: Remote end closed connection without response"),
            "unreachable")
        self.assertEqual(survey.failure_kind("could not fetch https://example/x"), "unreachable")
        self.assertEqual(survey.failure_kind("import exceeded 1800s"), "unreachable")

    def test_a_principled_refusal_is_about_their_data(self) -> None:
        self.assertEqual(survey.failure_kind(
            "records exact_match more than once for instance id1295; collapsing repeats into "
            "one bit is a decision this import will not make silently"), "refused")
        self.assertEqual(survey.failure_kind(
            "nothing survived the join; refusing to write an empty table"), "refused")

    def test_a_process_that_never_started_is_not_a_refusal(self) -> None:
        # Windows failing to launch the import (0xC0000142) was filed as a
        # refusal against 52 MMLU subjects, and a refusal is never retried. A
        # verdict about their data now needs a refusal we recognise.
        self.assertEqual(survey.failure_kind("exit 3221225794"), "unreachable")
        self.assertEqual(survey.failure_kind("some failure nobody has seen yet"), "unreachable")

    def test_a_benchmark_scored_by_another_metric_is_refused_by_name(self) -> None:
        # exact_match on a translation is nearly always zero, which produced
        # "a test of 1000 items that measures with 20" for WMT -- a sentence
        # about our metric, presented as one about their benchmark.
        self.assertIn("BLEU", survey.metric_refusal("wmt_14:language_pair=fr-en"))
        self.assertIsNone(survey.metric_refusal("med_qa"))
        self.assertIsNone(survey.metric_refusal("mmlu:subject=anatomy,method=multiple_choice_joint"))
        self.assertEqual(survey.failure_kind(survey.metric_refusal("wmt_14:language_pair=de-en")),
                         "refused")

    def test_the_summary_keeps_the_two_apart_and_says_it_is_incomplete(self) -> None:
        rows = [{"status": "audited", "respondents": 40, "items": 10, "items_carrying": 5,
                 "share_carrying_pct": 50.0, "items_running_backwards": 0, "alpha": 0.8},
                {"status": "failed", "reason": "metric not binary", "failure_kind": "refused"},
                {"status": "failed", "reason": "could not fetch", "failure_kind": "unreachable"}]
        got = survey.summarise(rows)
        self.assertEqual(got["refused"], 1)
        self.assertEqual(got["unreachable"], 1)
        self.assertIn("INCOMPLETE", got["incomplete"])

    def test_a_complete_run_claims_no_incompleteness(self) -> None:
        rows = [{"status": "audited", "respondents": 40, "items": 10, "items_carrying": 5,
                 "share_carrying_pct": 50.0, "items_running_backwards": 0, "alpha": 0.8},
                {"status": "failed", "reason": "metric not binary", "failure_kind": "refused"}]
        self.assertIsNone(survey.summarise(rows)["incomplete"])


class RecordTests(unittest.TestCase):
    def test_a_partial_run_keeps_every_set_it_did_not_touch(self) -> None:
        # Two sets retried on their own once overwrote a 193-set record.
        previous = {"a": {"question_set": "a", "status": "audited"},
                    "b": {"question_set": "b", "status": "failed", "failure_kind": "refused"},
                    "c": {"question_set": "c", "status": "failed", "failure_kind": "unreachable"}}
        rows = [{"question_set": "c", "status": "audited"}]
        whole = {row["question_set"]: row for row in survey.merge_record(rows, previous)}
        self.assertEqual(sorted(whole), ["a", "b", "c"])
        self.assertEqual(whole["c"]["status"], "audited")


class RefusalTests(unittest.TestCase):
    def test_a_panel_too_small_to_report_from_is_refused(self) -> None:
        saved = sys.argv
        sys.argv = ["survey_public_benchmarks.py", "--fewest-models", "10"]
        try:
            with self.assertRaises(SystemExit) as caught:
                survey.main()
        finally:
            sys.argv = saved
        self.assertIn("false alarm", str(caught.exception))


class SlugTests(unittest.TestCase):
    def test_a_question_set_becomes_a_filename_without_losing_its_identity(self) -> None:
        one = survey.slug("mmlu", "mmlu:subject=anatomy,method=multiple_choice_joint")
        two = survey.slug("mmlu", "mmlu:subject=astronomy,method=multiple_choice_joint")
        self.assertNotEqual(one, two)
        self.assertNotIn(":", one)
        self.assertNotIn("=", one)


if __name__ == "__main__":
    unittest.main()
