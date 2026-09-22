"""Importing somebody else's results: the joins, and what they refuse to pool.

Nothing here touches the network. The import's risk is not in fetching bytes,
it is in the three places where two models' records get lined up next to each
other and could be lined up wrongly.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import import_public_results as ipr  # noqa: E402


def instance(id_: str, question: str, answer: str = "A") -> dict:
    return {
        "id": id_,
        "input": {"text": question},
        "references": [{"output": {"text": answer}, "tags": ["correct"]},
                       {"output": {"text": "other"}, "tags": []}],
        "split": "test",
    }


def stat(name: str, mean: float) -> dict:
    return {"name": {"name": name, "split": "test"}, "mean": mean}


def entry(instance_id: str, correct: float, metric: str = "exact_match") -> dict:
    return {"instance_id": instance_id, "train_trial_index": 0,
            "stats": [stat("num_references", 4.0), stat(metric, correct)]}


def run(model: str, answers: dict[str, int], questions: dict[str, str] | None = None,
        scenario: str = "mmlu:subject=college_chemistry") -> dict:
    questions = questions or {k: "what is %s" % k for k in answers}
    return {
        "run": "%s,model=%s" % (scenario, model), "suite": "v1.4.0",
        "scenario": scenario, "model": model,
        "correct": dict(answers),
        "fingerprints": ipr.fingerprint_instances(
            [instance(k, questions[k]) for k in answers]),
    }


class RunNameTests(unittest.TestCase):
    def test_the_model_is_separated_from_the_scenario_it_was_run_on(self) -> None:
        scenario, model = ipr.split_run_name(
            "mmlu:subject=econometrics,method=multiple_choice_joint,model=openai_gpt-4o-2024-05-13")
        self.assertEqual(model, "openai_gpt-4o-2024-05-13")
        self.assertEqual(scenario, "mmlu:subject=econometrics,method=multiple_choice_joint")

    def test_a_scenario_is_labelled_by_its_subject_when_it_has_one(self) -> None:
        self.assertEqual(
            ipr.short_scenario("mmlu:subject=abstract_algebra,method=multiple_choice_joint"),
            "abstract_algebra")

    def test_items_sort_by_their_number_rather_than_alphabetically(self) -> None:
        got = sorted(["id10", "id9", "id1"], key=ipr.sort_key)
        self.assertEqual(got, ["id1", "id9", "id10"])


class CorrectnessTests(unittest.TestCase):
    def test_a_binary_metric_is_read_straight_through(self) -> None:
        got = ipr.correctness([entry("id0", 1.0), entry("id1", 0.0)], "exact_match", "run")
        self.assertEqual(got, {"id0": 1, "id1": 0})

    def test_a_score_between_right_and_wrong_is_refused_rather_than_thresholded(self) -> None:
        # Where the cut falls would change every statistic downstream, so the
        # import declines to place it.
        with self.assertRaises(SystemExit) as raised:
            ipr.correctness([entry("id0", 0.6)], "exact_match", "run")
        self.assertIn("threshold", str(raised.exception))

    def test_an_instance_answered_twice_is_refused_rather_than_averaged(self) -> None:
        with self.assertRaises(SystemExit):
            ipr.correctness([entry("id0", 1.0), entry("id0", 0.0)], "exact_match", "run")

    def test_an_instance_without_the_metric_is_left_out_rather_than_scored_zero(self) -> None:
        got = ipr.correctness([entry("id0", 1.0), {"instance_id": "id1", "stats": []}],
                              "exact_match", "run")
        self.assertEqual(got, {"id0": 1})


class FingerprintTests(unittest.TestCase):
    def test_the_same_question_fingerprints_the_same_for_two_models(self) -> None:
        a = ipr.fingerprint_instances([instance("id0", "what is a mole")])
        b = ipr.fingerprint_instances([instance("id0", "what is a mole")])
        self.assertEqual(a, b)

    def test_changing_which_reference_is_correct_changes_the_fingerprint(self) -> None:
        one = ipr.fingerprint_instances([instance("id0", "q", "A")])
        two = ipr.fingerprint_instances([instance("id0", "q", "B")])
        self.assertNotEqual(one["id0"], two["id0"])


class AssembleTests(unittest.TestCase):
    def test_every_model_contributes_a_row_for_every_shared_item(self) -> None:
        rows, notes = ipr.assemble([run("m1", {"id0": 1, "id1": 0}),
                                    run("m2", {"id0": 1, "id1": 1})], prefix_items=False)
        self.assertEqual(len(rows), 4)
        self.assertEqual(notes["models"], 2)
        self.assertEqual(notes["items_common_to_every_model"], 2)

    def test_an_item_only_some_models_were_asked_is_dropped_not_marked_wrong(self) -> None:
        # Padding the absent model with a zero would turn a question nobody put
        # to it into a question it failed.
        rows, notes = ipr.assemble([run("m1", {"id0": 1, "id1": 0}),
                                    run("m2", {"id0": 0})], prefix_items=False)
        self.assertEqual({row["item"] for row in rows}, {"id0"})
        self.assertEqual(notes["items_dropped_for_not_being_universal"], ["id1"])
        self.assertEqual(notes["models_that_were_missing_an_item"], ["m2"])

    def test_the_same_id_holding_a_different_question_is_refused(self) -> None:
        # Instance ids are positional. Two runs agreeing on `id0` is not
        # evidence they were asked the same thing.
        with self.assertRaises(SystemExit) as raised:
            ipr.assemble([run("m1", {"id0": 1}, {"id0": "what is a mole"}),
                          run("m2", {"id0": 1}, {"id0": "what is a joule"})],
                         prefix_items=False)
        self.assertIn("different question", str(raised.exception))

    def test_pooling_two_scenarios_keeps_their_items_apart(self) -> None:
        rows, notes = ipr.assemble(
            [run("m1", {"id0": 1}, scenario="mmlu:subject=econometrics"),
             run("m1", {"id0": 0}, scenario="mmlu:subject=anatomy")], prefix_items=True)
        self.assertEqual({row["item"] for row in rows},
                         {"econometrics/id0", "anatomy/id0"})
        self.assertEqual(notes["items_common_to_every_model"], 2)


class EndToEndShapeTests(unittest.TestCase):
    """The CSV this writes has to be the CSV item_analysis reads."""

    def test_the_rows_load_back_through_item_analysis_from_table(self) -> None:
        import csv
        import tempfile

        import item_analysis as ia

        rows, _notes = ipr.assemble([run("m1", {"id0": 1, "id1": 0}),
                                     run("m2", {"id0": 1, "id1": 1}),
                                     run("m3", {"id0": 1, "id1": 0})], prefix_items=False)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "table.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["trial", "item", "correct"])
                writer.writeheader()
                writer.writerows(rows)
            loaded, items = ia.from_table(path)
        self.assertEqual(items, ["id0", "id1"])
        self.assertEqual(len(loaded), 3)
        report = {row["item"]: row for row in ia.analyse(loaded, items)}
        self.assertEqual(report["id0"]["difficulty"], 1.0)
        self.assertTrue(any("pass it" in flag for flag in report["id0"]["flags"]))


if __name__ == "__main__":
    unittest.main()
