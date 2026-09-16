"""ADR-004: pre-registered comparative fabrication rule and disagreement share."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from adjudicate_evaluations import adjudicate, sha256_json  # noqa: E402
from test_adjudicate_evaluations import make_packet  # noqa: E402


def fabricate(packet: dict, condition: str, pair_id: str) -> None:
    """Both scorers report a fabrication on one output: confirmed by two votes."""
    for card in packet["evaluations"]:
        if card["condition"] == condition and card["pair_id"] == pair_id:
            card["critical_fabrications"] = [{"fabrication_id": "F-1", "description": "claims a result"}]
            card.pop("scorecard_sha256")
            card["scorecard_sha256"] = sha256_json(card)


def set_total(packet: dict, pair_id: str, condition: str, evaluator_id: str, total: int) -> None:
    for card in packet["evaluations"]:
        if (card["pair_id"], card["condition"], card["evaluator_id"]) == (pair_id, condition, evaluator_id):
            maxima = {"mission_reconstruction": 25, "current_state_fidelity": 20, "failure_recovery": 15,
                      "next_action_quality": 20, "missing_information_detection": 10, "reproducibility": 10}
            missing = total - card["scores"]["total"]
            for name, maximum in maxima.items():  # spread the increase within rubric maxima
                step = min(missing, maximum - card["scores"][name])
                card["scores"][name] += step
                missing -= step
            assert missing == 0
            card["scores"]["total"] = total
            card.pop("scorecard_sha256")
            card["scorecard_sha256"] = sha256_json(card)


class FabricationRuleTests(unittest.TestCase):
    def test_default_rule_still_rejects_a_baseline_fabrication(self) -> None:
        packet = make_packet()
        fabricate(packet, "baseline", "pair-1")
        self.assertEqual(adjudicate(packet)["reason_codes"], ["CRITICAL_FABRICATION_CONFIRMED_BY_TWO_EVALUATORS"])

    def test_comparative_rule_does_not_blame_structure_for_baseline_fabrications(self) -> None:
        packet = make_packet()
        packet["evidence_policy"] = {"fabrication_rule": "comparative"}
        fabricate(packet, "baseline", "pair-1")
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "PROVISIONAL_KEEP")
        self.assertEqual(result["score_summary"]["confirmed_fabrications_by_condition"], {"baseline": 1, "structured": 0})

    def test_comparative_rule_tolerates_equal_counts(self) -> None:
        packet = make_packet()
        packet["evidence_policy"] = {"fabrication_rule": "comparative"}
        fabricate(packet, "baseline", "pair-1")
        fabricate(packet, "structured", "pair-2")
        self.assertEqual(adjudicate(packet)["decision"], "PROVISIONAL_KEEP")

    def test_comparative_rule_rejects_more_structured_fabrications(self) -> None:
        packet = make_packet()
        packet["evidence_policy"] = {"fabrication_rule": "comparative"}
        fabricate(packet, "structured", "pair-2")
        self.assertEqual(adjudicate(packet)["reason_codes"], ["STRUCTURED_CONDITION_HAS_MORE_CONFIRMED_FABRICATIONS"])

    def test_unresolved_reports_still_block_the_comparative_rule(self) -> None:
        packet = make_packet()
        packet["evidence_policy"] = {"fabrication_rule": "comparative"}
        card = packet["evaluations"][0]
        card["critical_fabrications"] = [{"fabrication_id": "F-1", "description": "one report"}]
        card.pop("scorecard_sha256")
        card["scorecard_sha256"] = sha256_json(card)
        self.assertEqual(adjudicate(packet)["decision"], "INCONCLUSIVE")

    def test_unknown_rule_is_inconclusive(self) -> None:
        packet = make_packet()
        packet["evidence_policy"] = {"fabrication_rule": "lenient"}
        self.assertEqual(adjudicate(packet)["reason_codes"], ["UNKNOWN_FABRICATION_RULE"])


class DisagreementShareTests(unittest.TestCase):
    def packet_with_one_disagreeing_pair(self, pairs: int) -> dict:
        packet = make_packet(pair_count=pairs)
        set_total(packet, "pair-1", "structured", "eval-google", 90)  # 65 vs 90
        return packet

    def test_default_one_disagreeing_pair_is_inconclusive(self) -> None:
        self.assertEqual(adjudicate(self.packet_with_one_disagreeing_pair(5))["decision"], "INCONCLUSIVE")

    def test_share_within_limit_is_analysed(self) -> None:
        packet = self.packet_with_one_disagreeing_pair(5)
        packet["evidence_policy"] = {"max_disagreeing_pair_fraction": 0.2}
        result = adjudicate(packet)
        self.assertEqual(result["decision"], "PROVISIONAL_KEEP")
        self.assertEqual(result["score_summary"]["disagreeing_pairs"], ["pair-1"])

    def test_share_above_limit_is_inconclusive(self) -> None:
        packet = self.packet_with_one_disagreeing_pair(3)
        packet["evidence_policy"] = {"max_disagreeing_pair_fraction": 0.2}
        result = adjudicate(packet)
        self.assertEqual(result["reason_codes"], ["INCOMPLETE_OR_DISAGREEING_PAIRS"])


if __name__ == "__main__":
    unittest.main()
