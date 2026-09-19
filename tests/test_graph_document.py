"""A document and its key, both derived from a graph, with no model involved."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import graph_document as gd  # noqa: E402
import handoff_quiz as hq  # noqa: E402

GRAPH = {
    "graph_version": "TEST-GRAPH-V1",
    "title": "Depot",
    "tuples": [
        {"id": "T01", "kind": "count", "entity": "The depot", "relation": "holds", "value": "18 vehicles"},
        {"id": "T02", "kind": "date", "entity": "The depot", "relation": "certified", "value": "March 2024"},
        {"id": "T03", "kind": "rule", "entity": "A dispatch", "relation": "requires", "value": "two signatures"},
        {"id": "T04", "kind": "status", "entity": "The night shift", "value": "understaffed",
         "polarity": "negate"},
    ],
    "decoys": {
        "count": ["four vehicles", "nine vehicles", "forty vehicles", "six vehicles"],
        "date": ["July 2019", "January 2030", "May 2021", "August 2017"],
        "rule": ["a deposit", "a spare key", "a medical form", "an escort"],
        "status": ["relocated", "audited", "merged", "dissolved"],
    },
    "absent_probes": [
        {"id": "P01", "entity": "The depot", "relation": "insurer", "kind": "name",
         "distractors": ["Clemence Mutual", "Ardent Group", "Vasse et Fils", "Northrail"]},
    ],
}


class RenderTests(unittest.TestCase):
    def test_every_tuple_reaches_the_document(self) -> None:
        text = gd.render_document(GRAPH, "seed")
        for item in GRAPH["tuples"]:
            self.assertIn(item["value"], text, item["id"])

    def test_a_negated_tuple_is_rendered_as_a_denial(self) -> None:
        text = gd.render_document(GRAPH, "seed")
        self.assertIn("The night shift is not understaffed.", text)

    def test_rendering_is_deterministic_for_a_seed(self) -> None:
        self.assertEqual(gd.render_document(GRAPH, "seed", 3), gd.render_document(GRAPH, "seed", 3))

    def test_spreading_changes_the_layout_without_losing_a_fact(self) -> None:
        together = gd.render_document(GRAPH, "seed", 0)
        scattered = gd.render_document(GRAPH, "seed", 4)
        self.assertNotEqual(together, scattered)
        for item in GRAPH["tuples"]:
            self.assertIn(item["value"], scattered, item["id"])


class QuizTests(unittest.TestCase):
    def test_the_key_is_the_graph_and_no_model_is_consulted(self) -> None:
        quiz = gd.build_quiz(GRAPH)
        facts = [item for item in quiz["questions"] if item["kind"] == "fact"]
        self.assertEqual(len(facts), len(GRAPH["tuples"]))
        self.assertEqual(facts[0]["correct"], "18 vehicles")
        self.assertEqual(facts[0]["tuple_id"], "T01")

    def test_no_distractor_is_a_real_value_from_the_document(self) -> None:
        # A distractor that is true of something else would mark a reader wrong
        # for having found a fact.
        real = {item["value"] for item in GRAPH["tuples"]}
        for question in gd.build_quiz(GRAPH)["questions"]:
            self.assertFalse(real & set(question["distractors"]), question["id"])

    def test_an_absent_probe_the_graph_can_answer_is_refused(self) -> None:
        graph = {**GRAPH, "absent_probes": [{"id": "P9", "entity": "The depot", "relation": "holds",
                                             "kind": "count", "distractors": ["a", "b", "c", "d"]}]}
        with self.assertRaises(ValueError):
            gd.build_quiz(graph)

    def test_too_few_decoys_raises_rather_than_quietly_reusing_one(self) -> None:
        graph = {**GRAPH, "decoys": {**GRAPH["decoys"], "count": ["four vehicles"]}}
        with self.assertRaises(ValueError):
            gd.build_quiz(graph)

    def test_the_quiz_renders_through_the_existing_pipeline(self) -> None:
        # The point of matching the published format is that nothing downstream
        # has to know where a quiz came from.
        rendered, key = hq.render_quiz(gd.build_quiz(GRAPH), "TEST-GRAPH-V1")
        self.assertEqual(len(rendered), len(GRAPH["tuples"]) + 1)
        for item in rendered:
            self.assertEqual(len(item["options"]), len(hq.LETTERS))
        absent = [item for item in rendered if item["kind"] == "absent"][0]
        self.assertEqual(key[absent["id"]], hq.LETTERS[-1])


if __name__ == "__main__":
    unittest.main()
