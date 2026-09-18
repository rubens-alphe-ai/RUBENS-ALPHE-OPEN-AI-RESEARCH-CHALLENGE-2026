"""The published results page, and regrading a quiz experiment from stored answers.

Two promises are checked here. First, the summary the site publishes comes from
the recorded decisions and is not written by hand. Second, the claim the project
makes to others — "you can regrade our results yourself" — holds: recomputing a
quiz verdict from the stored reader answers reproduces the published decision
exactly, without calling any model.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_results_page as page  # noqa: E402
import handoff_quiz as hq  # noqa: E402

QUIZ_EXPERIMENTS = ["PROP-EXP-MEM-004", "PROP-EXP-MEM-005"]


def regrade(experiment_id: str) -> dict:
    """Recompute a verdict from the stored answers, as an outsider would."""
    results = ROOT / "experiments" / experiment_id / "results"
    policy = json.loads((ROOT / "experiments" / experiment_id / "evaluation_policy.json").read_text(encoding="utf-8"))
    quiz = json.loads((ROOT / "experiments" / experiment_id / policy["quiz"]["file"]).read_text(encoding="utf-8"))
    rendered, key = hq.render_quiz(quiz, experiment_id + ":" + quiz["quiz_version"])
    stored = json.loads((results / "quiz" / "answer-key.json").read_text(encoding="utf-8"))["key"]
    assert stored == key, "the published key is not reproducible from the quiz file"
    pairs: dict[str, dict] = {}
    for path in sorted((results / "quiz").glob("*.json")):
        if path.name == "answer-key.json":
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        grade = hq.grade(record["answers"], key, rendered)
        pairs.setdefault(record["pair_id"], {"pair_id": record["pair_id"]})[record["condition"]] = grade
    complete = sorted((p for p in pairs.values() if "baseline" in p and "structured" in p), key=lambda p: p["pair_id"])
    return hq.decide(complete, policy["quiz"])


class RegradeTests(unittest.TestCase):
    def test_published_quiz_verdicts_reproduce_from_stored_answers(self) -> None:
        for experiment_id in QUIZ_EXPERIMENTS:
            published_path = ROOT / "experiments" / experiment_id / "results" / "decision.json"
            if not published_path.is_file():
                continue
            published = json.loads(published_path.read_text(encoding="utf-8"))
            again = regrade(experiment_id)
            with self.subTest(experiment=experiment_id):
                self.assertEqual(again["decision"], published["decision"])
                self.assertEqual(again["reason_codes"], published["reason_codes"])
                for field in ("pairs", "mean_paired_delta_pp", "ci95_delta_pp", "inventions"):
                    self.assertEqual(again["summary"][field], published["summary"][field], field)


class ResultsPageTests(unittest.TestCase):
    def test_every_experiment_appears_with_its_recorded_verdict(self) -> None:
        rows = page.collect()
        by_id = {row["experiment_id"]: row for row in rows}
        self.assertTrue(by_id)
        for experiment in sorted((ROOT / "experiments").glob("PROP-EXP-*")):
            self.assertIn(experiment.name, by_id)
            decision_path = experiment / "results" / "decision.json"
            expected = json.loads(decision_path.read_text(encoding="utf-8"))["decision"] if decision_path.is_file() else "NOT_DECIDED"
            self.assertEqual(by_id[experiment.name]["decision"], expected, experiment.name)

    def test_negative_results_are_not_hidden(self) -> None:
        decisions = {row["decision"] for row in page.collect()}
        self.assertTrue({"REJECT", "INCONCLUSIVE"} & decisions)

    def test_page_renders_without_placeholders(self) -> None:
        markup = page.render_html(page.collect(), "2026-01-01")
        self.assertIn("<table>", markup)
        self.assertNotIn("%s", markup)
        self.assertNotIn("None", markup)


if __name__ == "__main__":
    unittest.main()
