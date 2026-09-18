"""Handoff quiz: rendering, parsing, grading and the pre-registered decision."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import handoff_quiz as hq  # noqa: E402

QUIZ_PATHS = [ROOT / "experiments" / "PROP-EXP-MEM-004" / "QUIZ.json",
              ROOT / "experiments" / "HOLDOUT-2026-09" / "QUIZ.json"]
QUIZ = json.loads(QUIZ_PATHS[0].read_text(encoding="utf-8"))
RULE = {"keep_min_delta_pp": 10, "invention_margin": 5}


def grade_for(accuracy_correct: int, inventions: int) -> dict:
    return {"fact_accuracy": accuracy_correct / 32, "inventions": inventions}


class QuizContentTests(unittest.TestCase):
    def test_ids_unique_and_option_counts_fixed(self) -> None:
        ids = [q["id"] for q in QUIZ["questions"]]
        self.assertEqual(len(ids), len(set(ids)))
        rendered, key = hq.render_quiz(QUIZ, "seed")
        self.assertTrue(all(len(item["options"]) == 5 for item in rendered))
        self.assertEqual(set(key), set(ids))

    def test_correct_option_is_never_duplicated_among_distractors(self) -> None:
        for q in QUIZ["questions"]:
            options = ([q["correct"]] if q["kind"] == "fact" else []) + q["distractors"] + [QUIZ["not_stated_option"]]
            self.assertEqual(len(options), len(set(options)), q["id"])

    def test_absent_questions_are_keyed_to_not_stated(self) -> None:
        rendered, key = hq.render_quiz(QUIZ, "seed")
        for item in rendered:
            if item["kind"] == "absent":
                self.assertEqual(key[item["id"]], "E")
            else:
                self.assertNotEqual(key[item["id"]], "E")

    def test_rendering_is_deterministic_and_not_a_pattern(self) -> None:
        first = hq.render_quiz(QUIZ, "same")[1]
        self.assertEqual(first, hq.render_quiz(QUIZ, "same")[1])
        fact_letters = {v for q, v in first.items() if q.startswith("Q")}
        self.assertGreaterEqual(len(fact_letters), 3)

    def test_prompt_contains_no_answer_key_and_the_text(self) -> None:
        rendered, key = hq.render_quiz(QUIZ, "seed")
        prompt = hq.reader_prompt(QUIZ, rendered, "HANDOFF TEXT HERE")
        self.assertIn("HANDOFF TEXT HERE", prompt)
        self.assertNotIn('"correct"', prompt)
        self.assertNotIn("kind", prompt)


class EveryQuizFileTests(unittest.TestCase):
    def test_each_quiz_renders_with_one_key_per_question(self) -> None:
        for path in QUIZ_PATHS:
            quiz = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(quiz=path.parent.name):
                rendered, key = hq.render_quiz(quiz, path.parent.name)
                ids = [q["id"] for q in quiz["questions"]]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(set(key), set(ids))
                self.assertTrue(all(len(item["options"]) == 5 for item in rendered))
                for item in rendered:
                    self.assertEqual(key[item["id"]] == "E", item["kind"] == "absent")


class ParseAndGradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rendered, self.key = hq.render_quiz(QUIZ, "seed")
        self.ids = [item["id"] for item in self.rendered]

    def test_parse_tolerates_prose_and_formats(self) -> None:
        raw = 'Here you go: {"answers": {"Q01": "a", "Q02": "(B)", "Q03": "C."}}'
        answers, problems = hq.parse_answers(raw, ["Q01", "Q02", "Q03", "Q04"])
        self.assertEqual(answers, {"Q01": "A", "Q02": "B", "Q03": "C"})
        self.assertEqual(len(problems), 1)

    def test_perfect_reader(self) -> None:
        result = hq.grade(dict(self.key), self.key, self.rendered)
        self.assertEqual(result["fact_correct"], 32)
        self.assertEqual(result["inventions"], 0)

    def test_inventions_and_missing_answers(self) -> None:
        answers = dict(self.key)
        answers["X05"] = "A"          # claims a result that does not exist
        del answers["X06"]             # missing: not an invention, not correct
        del answers["Q01"]             # missing fact answer counts as wrong
        result = hq.grade(answers, self.key, self.rendered)
        self.assertEqual(result["inventions"], 1)
        self.assertEqual(result["fact_correct"], 31)
        self.assertEqual(result["unanswered"], 2)


class DecisionTests(unittest.TestCase):
    def pairs(self, deltas: list[int], base: int = 16, inv_b: int = 0, inv_s: int = 0) -> list[dict]:
        return [{"pair_id": "p%d" % i, "baseline": grade_for(base, inv_b), "structured": grade_for(base + d, inv_s)}
                for i, d in enumerate(deltas)]

    def test_clear_improvement_is_provisional_keep(self) -> None:
        self.assertEqual(hq.decide(self.pairs([5, 6, 4, 5, 6, 5, 4, 6]), RULE)["decision"], "PROVISIONAL_KEEP")

    def test_no_effect_excludes_threshold_and_rejects(self) -> None:
        self.assertEqual(hq.decide(self.pairs([0, 1, -1, 0, 1, -1, 0, 0, 1, -1]), RULE)["decision"], "REJECT")

    def test_noisy_effect_is_inconclusive(self) -> None:
        self.assertEqual(hq.decide(self.pairs([10, -6, 8, -5, 9, -4]), RULE)["decision"], "INCONCLUSIVE")

    def test_more_inventions_rejects_even_with_better_accuracy(self) -> None:
        result = hq.decide(self.pairs([5, 6, 4, 5, 6, 5, 4, 6], inv_s=1), RULE)
        self.assertEqual(result["reason_codes"], ["STRUCTURED_INVENTS_MORE"])


if __name__ == "__main__":
    unittest.main()
