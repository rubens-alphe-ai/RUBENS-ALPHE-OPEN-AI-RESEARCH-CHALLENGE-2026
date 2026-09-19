"""Reading frozen handoffs again with another reader."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cross_read as cr  # noqa: E402
import handoff_quiz as hq  # noqa: E402

QUIZ = {"quiz_version": "TEST-V1", "not_stated_option": "The text does not say.", "questions": [
    {"id": "Q01", "kind": "fact", "question": "How many bakers?", "correct": "Four",
     "distractors": ["Nine", "Two", "Eleven"]},
    {"id": "X01", "kind": "absent", "question": "What is the revenue?",
     "distractors": ["100k", "250k", "1M", "5M"]},
]}
RENDERED, KEY = hq.render_quiz(QUIZ, "test")
RULE = {"keep_min_delta_pp": 5, "invention_margin": 5}


def graded(pair: str, condition: str, accuracy: float, inventions: int = 0) -> dict:
    return {"pair_id": pair, "condition": condition,
            "grade": {"fact_accuracy": accuracy, "inventions": inventions, "absent_questions": 1}}


class DecisionTests(unittest.TestCase):
    def test_only_complete_pairs_are_compared(self) -> None:
        records = [graded("p1", "baseline", 0.5), graded("p1", "structured", 1.0),
                   graded("p2", "baseline", 0.5),
                   graded("p3", "baseline", 0.5), graded("p3", "structured", 1.0)]
        self.assertEqual(cr.decide_from(records, RULE)["summary"]["pairs"], 2)

    def test_failed_readings_are_ignored(self) -> None:
        records = [graded("p1", "baseline", 0.5), graded("p1", "structured", 1.0),
                   {"pair_id": "p2", "condition": "baseline", "error": "timeout"}]
        self.assertEqual(cr.decide_from(records, RULE)["summary"]["pairs"], 1)


class ReadTrialTests(unittest.TestCase):
    def test_an_existing_reading_is_not_repeated(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / "baseline-1.json").write_text(json.dumps({"trial_id": "baseline-1", "grade": {}}), encoding="utf-8")
            with mock.patch.object(cr, "call", side_effect=AssertionError("should not be called")):
                record = cr.read_trial({"trial_id": "baseline-1", "pair_id": "p1", "condition": "baseline",
                                        "output_path": "x"}, {"evaluator_id": "r"}, QUIZ, RENDERED, KEY, out)
        self.assertEqual(record["trial_id"], "baseline-1")

    def test_a_reader_failure_is_recorded_without_a_grade(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            trial = {"trial_id": "t1", "pair_id": "p1", "condition": "baseline", "output_path": "README.md"}
            with mock.patch.object(cr, "call", side_effect=cr.AdapterError("boom")):
                record = cr.read_trial(trial, {"evaluator_id": "r"}, QUIZ, RENDERED, KEY, out)
        self.assertIn("error", record)
        self.assertNotIn("grade", record)
        self.assertFalse((out / "t1.json").exists())

    def test_a_good_reading_is_graded_and_stored(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            trial = {"trial_id": "t2", "pair_id": "p1", "condition": "structured", "output_path": "README.md"}
            answer = json.dumps({"answers": {"Q01": KEY["Q01"], "X01": "E"}})
            with mock.patch.object(cr, "call", return_value=(answer, "served-model")):
                record = cr.read_trial(trial, {"evaluator_id": "r"}, QUIZ, RENDERED, KEY, out)
            self.assertTrue((out / "t2.json").is_file())
        self.assertEqual(record["grade"]["fact_correct"], 1)
        self.assertEqual(record["grade"]["inventions"], 0)


if __name__ == "__main__":
    unittest.main()
