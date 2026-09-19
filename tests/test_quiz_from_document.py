"""Building a quiz from any document: what is kept, and what is thrown away."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_quiz_from_document as bq  # noqa: E402
import handoff_quiz as hq  # noqa: E402

DOCUMENT = (
    "The Lyon bakery opened in 2019 and employs four bakers. "
    "Its oven broke in January and was repaired within a week. "
    "The owner plans to add a coffee corner next spring and keeps the accounts in a notebook."
)


def fact(question: str, correct: str, distractors: list[str], quote: str) -> dict:
    return {"question": question, "correct": correct, "distractors": distractors, "quote": quote}


class SupportTests(unittest.TestCase):
    def test_quote_present_and_answer_inside_is_supported(self) -> None:
        self.assertTrue(bq.supported(DOCUMENT, "The Lyon bakery opened in 2019 and employs four bakers", "four bakers"))

    def test_invented_quote_is_refused(self) -> None:
        self.assertFalse(bq.supported(DOCUMENT, "The bakery employs twelve pastry chefs daily", "twelve"))

    def test_quote_that_does_not_contain_the_answer_is_refused(self) -> None:
        self.assertFalse(bq.supported(DOCUMENT, "Its oven broke in January and was repaired within a week", "four bakers"))

    def test_a_distractor_found_in_the_document_is_refused(self) -> None:
        self.assertFalse(bq.unsupported(DOCUMENT, ["four bakers", "nine bakers", "two bakers"]))
        self.assertTrue(bq.unsupported(DOCUMENT, ["nine bakers", "two bakers", "eleven bakers"]))


class BuildTests(unittest.TestCase):
    def build_with(self, written: dict, absent: dict, checks: list[dict]) -> dict:
        answers = [written, absent] + checks
        with mock.patch.object(bq, "ask", side_effect=answers):
            return bq.build(DOCUMENT, {"evaluator_id": "w"}, {"evaluator_id": "c"}, facts=2, absent=1, max_tokens=100)

    def test_keeps_verified_questions_and_drops_the_rest(self) -> None:
        written = {"questions": [
            fact("How many bakers does the bakery employ?", "Four", ["Nine", "Two", "Eleven"],
                 "The Lyon bakery opened in 2019 and employs four bakers"),
            fact("When did the oven break?", "In January", ["In March", "In August", "In December"],
                 "Its oven broke in January and was repaired within a week"),
            fact("Who supplies the flour?", "A mill in Provence", ["A cooperative", "A wholesaler", "A neighbour"],
                 "The bakery buys its flour from a mill in Provence"),
        ]}
        absent = {"questions": [
            {"question": "What is the bakery's annual revenue?", "distractors": ["€100k", "€250k", "€1M", "€5M"]},
            {"question": "How many bakers work there?", "distractors": ["One", "Three", "Six", "Ten"]},
        ]}
        built = self.build_with(written, absent, [{"answerable": False}, {"answerable": True}])
        quiz, report = built["quiz"], built["report"]
        self.assertEqual(report["kept_facts"], 2)
        self.assertEqual(report["kept_absent"], 1)
        self.assertTrue(any("quote not found" in item["why"] for item in report["dropped"]))
        self.assertEqual([q["question"] for q in quiz["questions"] if q["kind"] == "absent"],
                         ["What is the bakery's annual revenue?"])

    def test_the_result_renders_as_a_usable_quiz(self) -> None:
        written = {"questions": [
            fact("How many bakers does the bakery employ?", "Four", ["Nine", "Two", "Eleven"],
                 "The Lyon bakery opened in 2019 and employs four bakers"),
            fact("When did the oven break?", "In January", ["In March", "In August", "In December"],
                 "Its oven broke in January and was repaired within a week"),
        ]}
        absent = {"questions": [{"question": "What is the annual revenue?", "distractors": ["€100k", "€250k", "€1M", "€5M"]}]}
        quiz = self.build_with(written, absent, [{"answerable": False}])["quiz"]
        rendered, key = hq.render_quiz(quiz, "seed")
        self.assertEqual(len(rendered), 3)
        self.assertTrue(all(len(item["options"]) == 5 for item in rendered))
        self.assertEqual(key["X01"], "E")
        prompt = hq.reader_prompt(quiz, rendered, "a handoff")
        self.assertNotIn("The Lyon bakery opened in 2019", prompt)

    def test_an_absent_question_whose_option_is_in_the_document_is_dropped(self) -> None:
        written = {"questions": []}
        absent = {"questions": [
            {"question": "How many bakers are on duty at night?", "distractors": ["four bakers", "One", "Six", "Ten"]},
            {"question": "What is the annual revenue?", "distractors": ["€100k", "€250k", "€1M", "€5M"]},
        ]}
        built = self.build_with(written, absent, [{"answerable": False}])
        self.assertEqual(built["report"]["kept_absent"], 1)
        self.assertTrue(any("an option appears" in item["why"] for item in built["report"]["dropped"]))

    def test_a_question_the_document_answers_is_never_kept_as_absent(self) -> None:
        written = {"questions": []}
        absent = {"questions": [{"question": "How many bakers work there?", "distractors": ["One", "Three", "Six", "Ten"]}]}
        built = self.build_with(written, absent, [{"answerable": True, "quote": "employs four bakers"}])
        self.assertEqual(built["report"]["kept_absent"], 0)
        self.assertTrue(any("does answer it" in item["why"] for item in built["report"]["dropped"]))


if __name__ == "__main__":
    unittest.main()
