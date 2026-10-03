"""The French business test: answers are computed, read and graded without a model."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fr_business_bench as fb  # noqa: E402


class GenerationTests(unittest.TestCase):
    def test_generation_is_reproducible_and_balanced(self) -> None:
        a, b = fb.generate(), fb.generate()
        self.assertEqual(a, b)
        self.assertEqual(len(a), fb.PER_AREA * len(fb.AREAS))
        self.assertEqual(len({i["id"] for i in a}), len(a))

    def test_a_deadline_ending_on_a_sunday_moves_to_monday(self) -> None:
        item = [i for i in fb.generate() if i["id"] == "juridique-00"][0]
        self.assertEqual(item["answer"], "17/08/2026")
        self.assertEqual(date(2026, 8, 16).weekday(), 6)


class GradingTests(unittest.TestCase):
    def test_money_in_french_format_is_read(self) -> None:
        item = {"kind": "money", "answer": "1847.36"}
        for text in ("1 847,36 €", "1 847,36 €", "1847,36 euros", "1847.36"):
            self.assertEqual(fb.correct(item, text), 1, text)
        self.assertEqual(fb.correct(item, "2 097,36 €"), 0)

    def test_the_last_answer_line_is_the_one_graded(self) -> None:
        text = "Je pense RÉPONSE : B au début, mais en relisant...\nRÉPONSE : C"
        self.assertEqual(fb.final_answer(text), "C")
        self.assertEqual(fb.correct({"kind": "letter", "answer": "C"}, fb.final_answer(text)), 1)

    def test_dates_and_numbers(self) -> None:
        self.assertEqual(fb.correct({"kind": "date", "answer": "17/08/2026"}, "lundi 17/08/2026"), 1)
        self.assertEqual(fb.correct({"kind": "date", "answer": "17/08/2026"}, "7/8/2026"), 0)
        self.assertEqual(fb.correct({"kind": "number", "answer": "12.5"}, "12,5 jours"), 1)
        self.assertEqual(fb.correct({"kind": "number", "answer": "325"}, "325 mg"), 1)
        self.assertEqual(fb.correct({"kind": "number", "answer": "325"}, None), 0)


if __name__ == "__main__":
    unittest.main()
