"""Two defects found by three agents reading each other's ground, and their fixes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import graph_document as gd  # noqa: E402
import handoff_bench as hb  # noqa: E402


def record(strategy: str, repeat: int, accuracy: float) -> dict:
    return {"strategy": strategy, "repeat": repeat,
            "chain": [{"hop": 5, "text": "x", "words_kept": 1, "trimmed": False}],
            "grades": {"5": {"fact_accuracy": accuracy, "inventions": 0, "absent_questions": 8}}}


class PairingTests(unittest.TestCase):
    """A gap on one side used to shift every later pair."""

    def test_a_one_sided_failure_no_longer_mispairs_the_rest(self) -> None:
        # Control rises with the repeat number; the treatment is a flat 10 points
        # above it. Repeat 2 of the treatment is missing. Pairing by position
        # would compare treatment 3 with control 2 and inflate the difference.
        records = [record("summary", index, 0.50 + 0.05 * index) for index in range(1, 5)]
        records += [record("t", index, 0.60 + 0.05 * index) for index in (1, 3, 4)]
        table = hb.summarise(records, 5, control="summary")
        self.assertAlmostEqual(table["t"]["vs_control_pp"], 10.0, places=6)

    def test_the_published_vineyard_number_moves_and_the_conclusion_does_not(self) -> None:
        # The real case: facts_only-04 failed. Direction and verdict unchanged,
        # magnitude overstated by up to 1.6 points.
        import json
        folder = ROOT / "experiments" / "PROP-EXP-MEM-008" / "results" / "vineyard"
        records = [json.loads(path.read_text(encoding="utf-8")) for path in folder.glob("*.json")
                   if path.name not in ("report.json", "answer-key.json") and not path.name.endswith(".failed.json")]
        table = hb.summarise(records, 5, control="summary")
        self.assertAlmostEqual(table["facts_only"]["vs_control_pp"], 16.7, places=1)
        self.assertGreater(table["facts_only"]["vs_control_pp"], 0)

    def test_arms_with_no_repeat_in_common_are_dropped_not_averaged(self) -> None:
        records = [record("summary", 1, 0.5), record("t", 2, 0.9)]
        table = hb.summarise(records, 5, control="summary")
        self.assertNotIn("vs_control_pp", table["t"])


class PolarityTests(unittest.TestCase):
    """The key said the opposite of the document it was generated from."""

    def test_a_negated_tuple_is_keyed_to_the_negated_statement(self) -> None:
        item = {"id": "T1", "kind": "status", "entity": "The night shift",
                "value": "fully staffed", "polarity": "negate"}
        self.assertEqual(gd.answer_for(item), "not fully staffed")
        self.assertIn("is not fully staffed", gd.render_tuple(item))

    def test_an_affirmed_tuple_is_unchanged(self) -> None:
        item = {"id": "T2", "kind": "status", "entity": "The bay", "value": "scheduled"}
        self.assertEqual(gd.answer_for(item), "scheduled")

    def test_the_depot_graph_no_longer_keys_three_questions_backwards(self) -> None:
        import json
        graph = json.loads((ROOT / "experiments" / "graphs" / "depot.json").read_text(encoding="utf-8"))
        document = gd.render_document(graph, graph["graph_version"])
        quiz = gd.build_quiz(graph)
        negated = {item["id"] for item in graph["tuples"] if item.get("polarity") == "negate"}
        checked = 0
        for question in quiz["questions"]:
            if question.get("tuple_id") in negated:
                checked += 1
                self.assertTrue(question["correct"].startswith("not "), question["id"])
                self.assertIn(question["correct"].replace("not ", "not "), document)
        self.assertEqual(checked, 3)


if __name__ == "__main__":
    unittest.main()
