"""Merging independent chains: what is fed in, and what is claimed from it."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import handoff_quiz as hq  # noqa: E402
import merge_chains as mc  # noqa: E402

NOT_STATED = "the text does not say"


def quiz(facts: int = 3, absent: int = 2) -> dict:
    questions = [{"id": "Q%02d" % (index + 1), "kind": "fact", "question": "fact %d?" % index,
                  "correct": "right %d" % index,
                  "distractors": ["wrong %d.%d" % (index, other) for other in range(3)]}
                 for index in range(facts)]
    questions += [{"id": "A%02d" % (index + 1), "kind": "absent", "question": "absent %d?" % index,
                   "distractors": ["invented %d.%d" % (index, other) for other in range(4)]}
                  for index in range(absent)]
    return {"quiz_version": "fixture-1", "not_stated_option": NOT_STATED, "questions": questions}


def chain(repeat: int, hop_texts: dict[int, str], accuracy: float) -> dict:
    return {"strategy": "summary", "repeat": repeat,
            "chain": [{"hop": hop, "text": text, "words_kept": len(text.split()), "trimmed": False}
                      for hop, text in sorted(hop_texts.items())],
            "grades": {str(hop): {"fact_accuracy": accuracy, "inventions": 0, "absent_questions": 8}
                       for hop in hop_texts}}


class SourceTests(unittest.TestCase):
    def folder_with(self, records: list[dict]) -> Path:
        folder = Path(tempfile.mkdtemp())
        for record in records:
            (folder / ("summary-%02d.json" % record["repeat"])).write_text(json.dumps(record), encoding="utf-8")
        return folder

    def test_takes_the_handoff_written_at_that_hop(self) -> None:
        folder = self.folder_with([chain(1, {1: "first one", 5: "fifth one"}, 0.5)])
        found = mc.sources(folder, "summary", 5)
        self.assertEqual(found[0]["text"], "fifth one")

    def test_ignores_failed_and_ungraded_chains(self) -> None:
        folder = self.folder_with([chain(1, {5: "kept"}, 0.5)])
        (folder / "summary-02.failed.json").write_text(json.dumps({"strategy": "summary", "repeat": 2}), encoding="utf-8")
        (folder / "summary-03.json").write_text(json.dumps(
            {"strategy": "summary", "repeat": 3, "chain": [{"hop": 5, "text": "x", "words_kept": 1, "trimmed": False}],
             "grades": {}}), encoding="utf-8")
        self.assertEqual([item["repeat"] for item in mc.sources(folder, "summary", 5)], [1])


class PromptTests(unittest.TestCase):
    def test_every_note_is_included_and_the_budget_is_stated(self) -> None:
        prompt = mc.merge_prompt(["note one", "note two", "note three"], 150)
        self.assertIn("3 handover notes", prompt)
        self.assertIn("under 150 words", prompt)
        for text in ("note one", "note two", "note three"):
            self.assertIn(text, prompt)

    def test_the_merger_is_told_not_to_add_anything(self) -> None:
        prompt = mc.merge_prompt(["a note"], 150)
        self.assertIn("Do not add anything that appears in none of them", prompt)
        self.assertNotIn("invent", prompt.lower())


class RecordTests(unittest.TestCase):
    """MEM-009's defect at its source: a grade filed without the answers behind it.

    Six merge directories were published holding a `grade` and no `answers`,
    which left three headline recovery figures impossible to recompute. These
    pin the record shape rather than the arithmetic: the grading itself is
    covered by the handoff_quiz tests.
    """

    def setUp(self) -> None:
        self.rendered, self.key = hq.render_quiz(quiz(), "fixture:fixture-1")
        self.answers = {item["id"]: (self.key[item["id"]] if item["kind"] == "fact" else hq.LETTERS[-1])
                        for item in self.rendered}
        self.base = {"merge": 1, "strategy": "summary", "hop": 5, "sources": 6}

    def test_a_merge_record_stores_the_reader_answers_beside_the_grade(self) -> None:
        record = mc.merge_record(self.base, "a merged note", False, self.answers, [],
                                 self.key, self.rendered)
        self.assertEqual(record["answers"], self.answers)
        self.assertIn("grade", record)

    def test_a_stored_merge_record_can_be_regraded_from_its_own_answers(self) -> None:
        # This is what "every published verdict is recomputable" means for a
        # merge: the grade must be a function of letters that are on disk.
        record = mc.merge_record(self.base, "a merged note", False, self.answers, [],
                                 self.key, self.rendered)
        round_tripped = json.loads(json.dumps(record))
        self.assertEqual(hq.grade(round_tripped["answers"], self.key, self.rendered),
                         round_tripped["grade"])

    def test_a_merge_record_with_no_answers_is_refused_rather_than_written(self) -> None:
        with self.assertRaises(ValueError) as refusal:
            mc.merge_record(self.base, "a merged note", False, {}, [], self.key, self.rendered)
        self.assertIn("answers", str(refusal.exception))

    def test_the_merged_text_is_stored_with_a_hash_that_matches_it(self) -> None:
        record = mc.merge_record(self.base, "a merged note", False, self.answers, [],
                                 self.key, self.rendered)
        self.assertEqual(mc.sha256_text(record["merged"]), record["merged_sha256"])


if __name__ == "__main__":
    unittest.main()
