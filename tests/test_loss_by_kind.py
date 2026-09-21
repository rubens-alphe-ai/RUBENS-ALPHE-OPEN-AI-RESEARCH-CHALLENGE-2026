"""Loss split by kind of fact: the classification rule, the refusals, and what it never touches."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import graph_document as gd  # noqa: E402
import handoff_quiz as hq  # noqa: E402
import loss_by_kind as lk  # noqa: E402

DEPOT_GRAPH = ROOT / "experiments" / "graphs" / "depot.json"

QUIZ = {"quiz_version": "KIND-TEST-V1", "not_stated_option": "The text does not say.", "questions": [
    {"id": "Q01", "kind": "fact", "question": "How many bakers are there?", "correct": "four",
     "distractors": ["nine", "two", "eleven"]},
    {"id": "Q02", "kind": "fact", "question": "How many ovens are there?", "correct": "three",
     "distractors": ["nine", "two", "eleven"]},
    {"id": "Q03", "kind": "fact", "question": "How many sacks are stored?", "correct": "twelve",
     "distractors": ["ninety", "twenty", "eighty"]},
    {"id": "Q04", "kind": "fact", "question": "How much flour is milled?", "correct": "900 kilograms",
     "distractors": ["40 kilograms", "12 kilograms", "8 kilograms"]},
    {"id": "Q05", "kind": "fact", "question": "How often is the mill cleaned?", "correct": "twice weekly",
     "distractors": ["yearly", "hourly", "never"]},
    {"id": "Q06", "kind": "fact", "question": "When did the oven break?", "correct": "January 2024",
     "distractors": ["March 2024", "August 2023", "December 2021"]},
    {"id": "Q07", "kind": "fact", "question": "What does a delivery require?", "correct": "a signed docket",
     "distractors": ["a stamp", "a photograph", "a phone call"]},
    {"id": "X01", "kind": "absent", "question": "What is the revenue?",
     "distractors": ["100k", "250k", "1M", "5M"]},
]}


def bench_folder(root: Path, answers_by_run: dict[str, dict[str, str]]) -> Path:
    """A stored benchmark folder, written once, then only ever read."""
    rendered, key = hq.render_quiz(QUIZ, "kind-test")
    folder = root / "bench"
    folder.mkdir()
    (folder / "answer-key.json").write_text(
        json.dumps({"key": key, "rendered": rendered}, indent=2) + "\n", encoding="utf-8")
    for name, answers in answers_by_run.items():
        strategy, repeat = name.rsplit("-", 1)
        record = {"strategy": strategy, "repeat": int(repeat), "read_at": [1],
                  "chain": [{"hop": 1, "text": "handoff", "words_kept": 5, "trimmed": False}],
                  "grades": {"1": {"answers": answers, "problems": [],
                                   **hq.grade(answers, key, rendered)}}}
        (folder / ("%s.json" % name)).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return folder


def all_right(key: dict[str, str]) -> dict[str, str]:
    return dict(key)


def wrong_on(key: dict[str, str], ids: list[str]) -> dict[str, str]:
    letters = "ABCDE"
    answers = dict(key)
    for question_id in ids:
        answers[question_id] = letters[(letters.index(key[question_id]) + 1) % 4]
    return answers


class ClassificationRuleTests(unittest.TestCase):
    def test_the_written_rule_reproduces_every_kind_the_depot_graph_declared(self) -> None:
        graph = json.loads(DEPOT_GRAPH.read_text(encoding="utf-8"))
        quiz = gd.build_quiz(graph)
        truth = lk.kinds_from_graph(quiz, graph)
        derived = {item["id"]: lk.classify(item["question"], item.get("correct", ""))
                   for item in quiz["questions"] if item["kind"] == "fact"}
        self.assertEqual(derived, truth)

    def test_a_deontic_question_is_a_rule_even_when_it_asks_how_often(self) -> None:
        self.assertEqual(lk.classify("How often must a temperature excursion be reported?", "same day"), "rule")
        self.assertEqual(lk.classify("What is forbidden on the western plots?", "irrigation"), "rule")

    def test_the_answer_is_consulted_only_when_the_stem_says_nothing(self) -> None:
        # The stem asks for a quantity, so February 2025 in the text of the
        # question must not turn a count into a date.
        self.assertEqual(lk.classify("How much photometry was lost in February 2025?", "three weeks"), "count")
        # Here the stem carries no type at all and the answer does.
        self.assertEqual(lk.classify("What is the earliest certification date for biodynamic?", "2026"), "date")
        self.assertEqual(lk.classify("What is the current no-show rate?", "9 percent"), "count")

    def test_a_question_the_rule_cannot_type_is_unclassified_and_not_guessed(self) -> None:
        self.assertEqual(lk.classify("What did the affected batch lose?", "its aromatic profile"),
                         lk.UNCLASSIFIED)
        self.assertEqual(lk.classify("Where is the data archived?", "a university server in Marseille"),
                         lk.UNCLASSIFIED)
        self.assertNotIn(lk.UNCLASSIFIED, lk.KINDS)

    def test_a_why_question_is_a_reason_and_beats_every_other_stem_test(self) -> None:
        # Causal questions were the worst-kept facts in the stored prose runs.
        # Left in `unclassified` they diluted a bucket that does get a rate, so
        # they are typed; `reason` outranks `rule` because "Why must X?" asks
        # for the cause and not for the obligation.
        self.assertEqual(lk.classify("Why is a paper log kept as a backup?", "the alarm failed silently"),
                         "reason")
        self.assertEqual(lk.classify("Why must the excursion be reported?", "the agency requires it"), "reason")
        self.assertIn("reason", lk.KINDS)
        self.assertNotIn("reason", lk.GRAPH_KINDS)

    def test_a_negated_tuple_keeps_the_kind_of_the_tuple_it_negates(self) -> None:
        # Polarity changes whether the document asserts the value, not what kind
        # of fact it is; a negated status must not fall out of the status bucket.
        item = {"id": "T99", "kind": "status", "entity": "The night shift", "value": "fully staffed",
                "polarity": "negate"}
        self.assertEqual(lk.classify(gd.question_for(item), item["value"]), "status")


class BreakdownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _, self.key = hq.render_quiz(QUIZ, "kind-test")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def analyse(self, runs: dict[str, dict[str, str]], **kwargs) -> dict:
        folder = bench_folder(self.root, runs)
        return lk.analyse(folder, control="summary", **kwargs)

    def test_a_kind_with_too_few_questions_carries_counts_but_no_rate(self) -> None:
        runs = {"summary-%02d" % i: all_right(self.key) for i in (1, 2, 3)}
        entry = self.analyse(runs)["kinds"]["1"]["rule"]
        thin = entry["arms"]["summary"]
        self.assertEqual(entry["questions"], 1)
        self.assertFalse(thin["sufficient"])
        self.assertIsNone(thin["accuracy_pct"])
        self.assertIsNone(thin["ci95"])
        self.assertEqual(thin["correct"], 3)
        self.assertIn("at least 5 questions", thin["withheld_because"])

    def test_a_thin_kind_is_never_printed_as_a_percentage(self) -> None:
        runs = {"summary-%02d" % i: all_right(self.key) for i in (1, 2, 3)}
        page = lk.render_markdown(self.analyse(runs))
        self.assertIn("| rule | 1 | summary | 3 | 3 of 3 | insufficient |", page)
        self.assertNotIn("| rule | 1 | summary | 3 | 3 of 3 | 100.0%", page)

    def test_a_kind_with_enough_questions_carries_a_rate_and_a_paired_difference(self) -> None:
        # Five count questions clear the minimum. The control misses two of them
        # in every run; the other arm misses none.
        runs = {"summary-%02d" % i: wrong_on(self.key, ["Q01", "Q02"]) for i in (1, 2, 3)}
        runs.update({"checklist-%02d" % i: all_right(self.key) for i in (1, 2, 3)})
        table = self.analyse(runs)["kinds"]["1"]["count"]
        self.assertEqual(table["questions"], 5)
        self.assertEqual(table["arms"]["summary"]["accuracy_pct"], 60.0)
        self.assertEqual(table["arms"]["checklist"]["accuracy_pct"], 100.0)
        self.assertEqual(table["arms"]["checklist"]["vs_control_pp"], 40.0)
        self.assertEqual(table["arms"]["checklist"]["vs_control_ci95"], [40.0, 40.0])

    def test_the_paired_difference_matches_runs_by_repeat_not_by_position(self) -> None:
        # The control keeps repeats 1 to 4; the other arm lost repeat 2. Both
        # arms miss the same two count questions in repeat 4 and nothing else,
        # so the honest difference is zero. Zipping the two lists positionally
        # would line repeat 4 up against repeat 3 and report -13.3 pp.
        runs = {"summary-01": all_right(self.key), "summary-02": all_right(self.key),
                "summary-03": all_right(self.key), "summary-04": wrong_on(self.key, ["Q01", "Q02"]),
                "checklist-01": all_right(self.key), "checklist-03": all_right(self.key),
                "checklist-04": wrong_on(self.key, ["Q01", "Q02"])}
        cell = self.analyse(runs)["kinds"]["1"]["count"]["arms"]["checklist"]
        self.assertEqual(cell["paired_runs"], 3)
        self.assertEqual(cell["vs_control_pp"], 0.0)

    def test_absent_fact_questions_never_enter_a_kind(self) -> None:
        result = self.analyse({"summary-%02d" % i: all_right(self.key) for i in (1, 2, 3)})
        self.assertEqual(result["meta"]["absent_questions"], 1)
        self.assertEqual(result["meta"]["fact_questions"], 7)
        self.assertNotIn("X01", result["question_kinds"])
        self.assertEqual(sum(entry["questions"] for entry in result["kinds"]["1"].values()), 7)

    def test_inventions_are_reported_apart_from_every_kind(self) -> None:
        invented = dict(self.key)
        invented["X01"] = "A" if self.key["X01"] != "A" else "B"
        result = self.analyse({"summary-%02d" % i: invented for i in (1, 2, 3)})
        self.assertEqual(result["inventions"]["1"]["summary"]["inventions"], 3)
        self.assertEqual(result["inventions"]["1"]["summary"]["absent_questions_asked"], 3)
        for entry in result["kinds"]["1"].values():
            for cell in entry["arms"].values():
                self.assertLessEqual(cell["correct"], cell["observations"])

    def test_the_per_kind_correct_counts_add_back_up_to_the_stored_fact_total(self) -> None:
        runs = {"summary-%02d" % i: wrong_on(self.key, ["Q01", "Q06"]) for i in (1, 2, 3)}
        folder = bench_folder(self.root, runs)
        result = lk.analyse(folder, control="summary")
        stored = json.loads((folder / "summary-01.json").read_text(encoding="utf-8"))
        per_run = sum(entry["arms"]["summary"]["correct"] for entry in result["kinds"]["1"].values()) / 3
        self.assertEqual(per_run, stored["grades"]["1"]["fact_correct"])

    def test_reading_a_stored_folder_changes_nothing_in_it(self) -> None:
        runs = {"summary-%02d" % i: all_right(self.key) for i in (1, 2, 3)}
        folder = bench_folder(self.root, runs)
        before = {path.name: path.read_bytes() for path in sorted(folder.iterdir())}
        lk.analyse(folder, control="summary")
        lk.render_markdown(lk.analyse(folder, control="summary"))
        after = {path.name: path.read_bytes() for path in sorted(folder.iterdir())}
        self.assertEqual(before, after)


class NoJudgeTests(unittest.TestCase):
    def test_the_analysis_cannot_call_a_model_because_it_never_imports_one(self) -> None:
        # The point of this re-analysis is that it needs nothing but the stored
        # letters. An import of the adapter would be the first step back towards
        # a judge, so it is refused here rather than argued about in review.
        source = (ROOT / "scripts" / "loss_by_kind.py").read_text(encoding="utf-8")
        for forbidden in ("evaluate_experiment", "model_adapter", "requests", "urllib",
                          "http.client", "socket", "openai"):
            self.assertNotIn("import %s" % forbidden, source)
            self.assertNotIn("from %s import" % forbidden, source)

    def test_the_analysis_declares_in_its_own_output_that_no_model_was_called(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, key = hq.render_quiz(QUIZ, "kind-test")
            folder = bench_folder(Path(tmp), {"summary-%02d" % i: all_right(key) for i in (1, 2, 3)})
            result = lk.analyse(folder, control="summary")
        self.assertTrue(result["meta"]["no_model_calls"])
        self.assertIn("No model was called", lk.render_markdown(result))


if __name__ == "__main__":
    unittest.main()
