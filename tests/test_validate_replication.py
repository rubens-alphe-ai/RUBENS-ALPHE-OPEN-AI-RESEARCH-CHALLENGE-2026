"""Reviewing an outside replication: what is accepted, and what is refused."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_replication as vr  # noqa: E402

EXPERIMENT = "PROP-EXP-MEM-005"
QUIZ, RENDERED, KEY, POLICY = vr.load_experiment(EXPERIMENT)


def submission(pairs: int = 6, delta: int = 0) -> dict:
    """A well-formed submission; `delta` extra correct facts in the treatment."""
    facts = [item["id"] for item in RENDERED if item["kind"] == "fact"]
    made = []
    for index in range(pairs):
        # The baseline omits six facts; the treatment omits `delta` fewer.
        base = dict(KEY, **{q: "E" for q in facts[:6]})
        treat = dict(KEY, **{q: "E" for q in facts[: 6 - delta]})
        made.append({"pair_id": "pair-%02d" % index, "seed": index,
                     "baseline": {"handoff": "Baseline handoff number %d. " % index + "x" * 60, "answers": base},
                     "structured": {"handoff": "Treatment handoff number %d. " % index + "y" * 60, "answers": treat}})
    return {"submission_version": "RA-PSI-REPLICATION-V1", "experiment_id": EXPERIMENT,
            "quiz_version": QUIZ["quiz_version"], "submitted_by": "someone",
            "generator": {"model": "their-model", "provider": "their-cloud", "temperature": 0.8},
            "reader": {"model": "their-reader", "provider": "their-cloud"}, "pairs": made}


def review_of(payload: dict) -> dict:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "submission.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return vr.review(path, EXPERIMENT)


class AcceptanceTests(unittest.TestCase):
    def test_well_formed_submission_is_regraded(self) -> None:
        report = review_of(submission())
        self.assertEqual(report["status"], "ACCEPTED")
        self.assertEqual(report["evidence_tier"], "reproducible_contribution")
        self.assertEqual(report["pairs"], 6)
        self.assertIn(report["decision"], {"PROVISIONAL_KEEP", "REJECT", "INCONCLUSIVE"})

    def test_declared_models_are_recorded_as_declared(self) -> None:
        report = review_of(submission())
        self.assertEqual(report["declared_generator"], "their-model")
        self.assertIn("cannot be verified", report["identity_note"])

    def test_a_real_improvement_is_visible_in_the_regrade(self) -> None:
        report = review_of(submission(pairs=8, delta=6))
        self.assertGreater(report["summary"]["mean_paired_delta_pp"], 0)


class RefusalTests(unittest.TestCase):
    def refused_for(self, payload: dict, fragment: str) -> None:
        report = review_of(payload)
        self.assertEqual(report["status"], "REFUSED")
        self.assertTrue(any(fragment in problem for problem in report["problems"]), report["problems"])

    def test_wrong_quiz_version(self) -> None:
        payload = submission()
        payload["quiz_version"] = "SOMETHING-ELSE"
        self.refused_for(payload, "quiz_version")

    def test_identical_handoffs_in_a_pair(self) -> None:
        payload = submission()
        payload["pairs"][0]["structured"]["handoff"] = payload["pairs"][0]["baseline"]["handoff"]
        self.refused_for(payload, "same handoff")

    def test_unknown_question_id(self) -> None:
        payload = submission()
        payload["pairs"][0]["baseline"]["answers"]["Q99"] = "A"
        self.refused_for(payload, "unknown question ids")

    def test_answer_that_is_not_a_letter(self) -> None:
        payload = submission()
        payload["pairs"][0]["baseline"]["answers"]["Q01"] = "OpenAlex"
        self.refused_for(payload, "one letter")

    def test_too_few_pairs(self) -> None:
        payload = submission(pairs=3)
        self.refused_for(payload, "at least five")

    def test_missing_reader(self) -> None:
        payload = submission()
        del payload["reader"]
        self.refused_for(payload, "reader needs a model")

    def test_totals_from_the_sender_are_never_used(self) -> None:
        payload = submission()
        payload_with_claim = copy.deepcopy(payload)
        payload_with_claim["notes"] = "our own analysis says +40 points"
        self.assertEqual(review_of(payload)["summary"]["mean_paired_delta_pp"],
                         review_of(payload_with_claim)["summary"]["mean_paired_delta_pp"])


if __name__ == "__main__":
    unittest.main()
