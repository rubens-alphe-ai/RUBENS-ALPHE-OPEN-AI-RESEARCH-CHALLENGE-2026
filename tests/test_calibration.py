"""Calibration pass rule and anchor set integrity."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from calibrate_evaluators import build_prompt, judge  # noqa: E402

ANCHORS = json.loads((ROOT / "calibration" / "PCRB2" / "anchors.json").read_text(encoding="utf-8"))
NAMES = ["mission_reconstruction", "current_state_fidelity", "failure_recovery",
         "next_action_quality", "missing_information_detection", "reproducibility"]
MAXIMA = [25, 20, 15, 20, 10, 10]


def card(blind_id: str, total: int, fabrication: bool = False) -> dict:
    scores, left = {}, total
    for name, maximum in zip(NAMES, MAXIMA):
        scores[name] = min(maximum, left)
        left -= scores[name]
    return {"blind_id": blind_id, "scores": scores,
            "critical_fabrications": [{"description": "invented result"}] if fabrication else []}


def good_cards() -> list[dict]:
    return [card("CAL-01", 92), card("CAL-02", 60), card("CAL-03", 20), card("CAL-04", 50, True), card("CAL-05", 10)]


class CalibrationTests(unittest.TestCase):
    def test_well_calibrated_evaluator_passes(self) -> None:
        self.assertTrue(judge(ANCHORS, good_cards())["passed"])

    def test_missed_fabrication_fails(self) -> None:
        cards = good_cards()
        cards[3] = card("CAL-04", 50)
        verdict = judge(ANCHORS, cards)
        self.assertFalse(verdict["passed"])
        self.assertTrue(any("CAL-04" in failure for failure in verdict["failures"]))

    def test_ceiling_scoring_fails(self) -> None:
        cards = [card("CAL-01", 100), card("CAL-02", 100), card("CAL-03", 100), card("CAL-04", 100, True), card("CAL-05", 10)]
        self.assertFalse(judge(ANCHORS, cards)["passed"])

    def test_false_fabrication_on_a_clean_answer_fails(self) -> None:
        cards = good_cards()
        cards[0] = card("CAL-01", 92, True)
        self.assertFalse(judge(ANCHORS, cards)["passed"])

    def test_prompt_uses_components_only_and_every_anchor(self) -> None:
        ids, prompt = build_prompt(ANCHORS)
        self.assertEqual(ids, ["CAL-01", "CAL-02", "CAL-03", "CAL-04", "CAL-05"])
        self.assertNotIn('"total"', prompt)
        for anchor in ANCHORS["anchors"]:
            self.assertIn(anchor["text"].strip()[:40], prompt)

    def test_bands_are_consistent_with_the_required_order(self) -> None:
        band = {anchor["blind_id"]: anchor["expected_total"] for anchor in ANCHORS["anchors"]}
        self.assertLessEqual(band["CAL-02"][0], band["CAL-01"][1])
        self.assertTrue(all(0 <= low <= high <= 100 for low, high in band.values()))


if __name__ == "__main__":
    unittest.main()
