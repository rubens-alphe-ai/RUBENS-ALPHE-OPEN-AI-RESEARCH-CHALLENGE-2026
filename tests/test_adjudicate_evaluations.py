from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from adjudicate_evaluations import adjudicate, sha256_json  # noqa: E402


def make_card(
    pair_id: str,
    condition: str,
    evaluator_id: str,
    provider: str,
    model: str,
    total: float,
    output_sha256: str,
    fabrication: bool = False,
) -> dict[str, object]:
    if condition == "baseline":
        values = {
            "mission_reconstruction": 15,
            "current_state_fidelity": 12,
            "failure_recovery": 8,
            "next_action_quality": 10,
            "missing_information_detection": 5,
            "reproducibility": total - 50,
        }
    else:
        values = {
            "mission_reconstruction": 20,
            "current_state_fidelity": 15,
            "failure_recovery": 10,
            "next_action_quality": 10,
            "missing_information_detection": 5,
            "reproducibility": total - 60,
        }
    card: dict[str, object] = {
        "card_id": f"{pair_id}-{condition}-{evaluator_id}",
        "evaluator_id": evaluator_id,
        "model": model,
        "provider": provider,
        "pair_id": pair_id,
        "seed": 100 + int(pair_id.split("-")[-1]),
        "trial_id": f"{condition}-{pair_id}",
        "condition": condition,
        "output_sha256": output_sha256,
        "protocol_sha256": "a" * 64,
        "prompt_sha256": "b" * 64,
        "state_sha256": ("c" if condition == "baseline" else "d") * 64,
        "scores": {**values, "total": total},
        "critical_fabrications": [
            {"fabrication_id": "F-1", "description": "test fabrication"}
        ]
        if fabrication
        else [],
        "notes": "synthetic test card",
    }
    card["scorecard_sha256"] = sha256_json(card)
    return card


def make_packet(pair_count: int = 3, stage: str = "pilot") -> dict[str, object]:
    cards: list[dict[str, object]] = []
    trials: list[dict[str, object]] = []
    evaluators = (
        ("eval-openai", "OpenAI", "gpt-test"),
        ("eval-google", "Google", "gemini-test"),
    )
    for index in range(pair_count):
        pair_id = f"pair-{index + 1}"
        seed = 101 + index
        trials.extend(
            [
                {
                    "pair_id": pair_id,
                    "condition": condition,
                    "seed": seed,
                    "generation_provider": "ollama" if index % 2 == 0 else "openai",
                    "generation_model": "qwen3:4b" if index % 2 == 0 else "cloud-test",
                }
                for condition in ("baseline", "structured")
            ]
        )
        for evaluator_id, provider, model in evaluators:
            cards.append(
                make_card(
                    pair_id,
                    "baseline",
                    evaluator_id,
                    provider,
                    model,
                    50 if evaluator_id == "eval-openai" else 52,
                    f"{index + 1:064x}",
                )
            )
            cards.append(
                make_card(
                    pair_id,
                    "structured",
                    evaluator_id,
                    provider,
                    model,
                    65 if evaluator_id == "eval-openai" else 67,
                    f"{index + 100:064x}",
                )
            )
    return {
        "experiment_id": "PROP-EXP-MEM-001",
        "proposal_id": "PROP-EXP-MEM-001",
        "stage": stage,
        "trials": trials,
        "evaluations": cards,
        "holdout_passed": True,
        "regression_passed": True,
        "calibration_passed": True,
    }


class AdjudicationTests(unittest.TestCase):
    def test_three_pairs_are_only_provisional(self) -> None:
        result = adjudicate(make_packet())
        self.assertEqual(result["decision"], "PROVISIONAL_KEEP")
        self.assertFalse(result["canonical_update_allowed"])
        self.assertEqual(result["next_stage"], "REPLICATING")

    def test_final_keep_requires_and_accepts_replication_gates(self) -> None:
        result = adjudicate(make_packet(pair_count=9, stage="replication"))
        self.assertEqual(result["decision"], "FINAL_KEEP")
        self.assertTrue(result["canonical_update_allowed"])

    def test_one_fabrication_report_is_inconclusive(self) -> None:
        packet = make_packet()
        packet["evaluations"][0]["critical_fabrications"] = [
            {"fabrication_id": "F-1", "description": "one report"}
        ]
        card = packet["evaluations"][0]
        del card["scorecard_sha256"]
        card["scorecard_sha256"] = sha256_json(card)
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "INCONCLUSIVE")

    def test_two_confirmations_on_same_output_reject(self) -> None:
        packet = make_packet()
        for index in (0, 2):
            packet["evaluations"][index]["critical_fabrications"] = [
                {"fabrication_id": "F-1", "description": "confirmed"}
            ]
            card = packet["evaluations"][index]
            del card["scorecard_sha256"]
            card["scorecard_sha256"] = sha256_json(card)
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "REJECT")
        self.assertFalse(result["canonical_update_allowed"])

    def _one_report(self) -> dict[str, object]:
        packet = make_packet()
        card = packet["evaluations"][0]
        card["critical_fabrications"] = [{"fabrication_id": "F-1", "description": "one report"}]
        del card["scorecard_sha256"]
        card["scorecard_sha256"] = sha256_json(card)
        return packet

    def test_checker_confirmation_turns_one_report_into_reject(self) -> None:
        packet = self._one_report()
        packet["fabrication_confirmations"] = [
            {
                "evaluator_id": "checker-anthropic",
                "output_sha256": packet["evaluations"][0]["output_sha256"],
                "confirms_fabrication": True,
            }
        ]
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "REJECT")

    def test_checker_rejection_leaves_one_report_inconclusive(self) -> None:
        packet = self._one_report()
        packet["fabrication_confirmations"] = [
            {
                "evaluator_id": "checker-anthropic",
                "output_sha256": packet["evaluations"][0]["output_sha256"],
                "confirms_fabrication": False,
            }
        ]
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "INCONCLUSIVE")

    def test_same_evaluator_cannot_confirm_its_own_report(self) -> None:
        packet = self._one_report()
        first = packet["evaluations"][0]
        packet["fabrication_confirmations"] = [
            {
                "evaluator_id": first["evaluator_id"],
                "output_sha256": first["output_sha256"],
                "confirms_fabrication": True,
            }
        ]
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "INCONCLUSIVE")

    def test_confirmation_of_an_unscored_output_is_refused(self) -> None:
        packet = self._one_report()
        packet["fabrication_confirmations"] = [
            {"evaluator_id": "checker-anthropic", "output_sha256": "f" * 64, "confirms_fabrication": True}
        ]
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertIn("INVALID_FABRICATION_CONFIRMATION", result["reason_codes"])

    def test_pair_count_and_disagreement_are_not_silently_ignored(self) -> None:
        packet = make_packet(pair_count=2)
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertIn("INSUFFICIENT_PILOT_PAIRS", result["reason_codes"])

        packet = make_packet()
        changed = packet["evaluations"][1]
        changed["scores"]["total"] = 70
        changed["scores"]["reproducibility"] = 10
        packet["max_evaluator_disagreement"] = 2
        del changed["scorecard_sha256"]
        changed["scorecard_sha256"] = sha256_json(changed)
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "INCONCLUSIVE")

    def test_failed_regression_rejects_candidate(self) -> None:
        packet = make_packet(pair_count=9, stage="replication")
        packet["regression_results"] = [{"capability": "mission", "passed": False}]
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "REJECT")


if __name__ == "__main__":
    unittest.main()
