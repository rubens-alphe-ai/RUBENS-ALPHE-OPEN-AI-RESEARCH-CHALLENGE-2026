"""The guard that would have caught MEM-010 and MEM-012 before they ran."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_headroom as ch  # noqa: E402


def policy(decision: dict) -> dict:
    return {"decision": decision}


class HeadroomTests(unittest.TestCase):
    def test_a_difference_in_points_cannot_exceed_what_is_left_above_the_control(self) -> None:
        self.assertEqual(ch.headroom(94.2, "points"), 100.0 - 94.2)

    def test_a_ratio_on_a_bounded_quantity_cannot_exceed_its_room_to_multiply(self) -> None:
        self.assertAlmostEqual(ch.headroom(50.0, "ratio"), 2.0)
        self.assertAlmostEqual(ch.headroom(91.7, "ratio"), 100.0 / 91.7)


class FindingTests(unittest.TestCase):
    def test_mem_010s_threshold_is_named_impossible(self) -> None:
        rows = ch.findings(policy({"keep_min_delta_pp": 20,
                                   "control_prior_pct": {"keep_min_delta_pp": {"clinic": 94.2}}}))
        self.assertEqual(rows[0]["status"], "IMPOSSIBLE")
        self.assertIn("94.2", rows[0]["reason"])

    def test_mem_011s_threshold_is_reachable_against_a_control_that_loses(self) -> None:
        rows = ch.findings(policy({"keep_min_delta_pp": 20,
                                   "control_prior_pct": {"keep_min_delta_pp": {"clinic": 61.6}}}))
        self.assertEqual(rows[0]["status"], "OK")

    def test_doubling_a_metric_already_above_half_is_impossible(self) -> None:
        rows = ch.findings(policy({"gap_targeting_ratio": 2.0,
                                   "control_prior_pct": {"gap_targeting_ratio": {"observatory": 91.7}}}))
        self.assertEqual(rows[0]["status"], "IMPOSSIBLE")

    def test_a_threshold_with_no_declared_prior_is_flagged_not_passed(self) -> None:
        rows = ch.findings(policy({"keep_min_delta_pp": 20}))
        self.assertEqual(rows[0]["status"], "UNDECLARED")

    def test_nothing_is_reported_for_a_policy_with_no_thresholds(self) -> None:
        self.assertEqual(ch.findings(policy({})), [])



class MarginTests(unittest.TestCase):
    """A margin in points, which is what a ratio should have been."""

    def test_a_document_that_cannot_express_the_margin_is_refused(self) -> None:
        # The anchored arm reached 91.7 % gap-targeting on the observatory, so a
        # further +10 is not a demanding test, it is an impossible one.
        rows = ch.findings(policy({"gap_targeting_margin_pp": 10,
                                   "control_prior_pct": {"gap_targeting_margin_pp": {"observatory": 91.7}}}))
        self.assertEqual(rows[0]["status"], "IMPOSSIBLE")

    def test_a_document_with_room_passes(self) -> None:
        rows = ch.findings(policy({"gap_targeting_margin_pp": 10,
                                   "control_prior_pct": {"gap_targeting_margin_pp": {"clinic": 46.9}}}))
        self.assertEqual(rows[0]["status"], "OK")

    def test_a_margin_stays_testable_where_a_ratio_did_not(self) -> None:
        # The same three priors that made a x2 impossible on two documents leave
        # room for +10 on two of them: 80.2 + 10 fits, 91.7 + 10 does not. Two of
        # three is what the rule needs, so it survives with a warning about the
        # third rather than being decided in advance. That difference is the
        # whole argument for a margin over a ratio near a bounded endpoint.
        import json as _json
        import tempfile
        from pathlib import Path as _Path
        folder = _Path(tempfile.mkdtemp()) / "experiments" / "FAKE-EXP"
        folder.mkdir(parents=True)
        (folder / "evaluation_policy.json").write_text(_json.dumps({
            "decision": {"gap_targeting_margin_pp": 10, "documents_required": 2,
                         "control_prior_pct": {"gap_targeting_margin_pp":
                                               {"clinic": 46.9, "vineyard": 80.2, "observatory": 91.7}}}}),
            encoding="utf-8")
        original = ch.ROOT
        ch.ROOT = folder.parents[1]
        try:
            result = ch.check("FAKE-EXP")
        finally:
            ch.ROOT = original
        self.assertEqual(result["status"], "WARN")
        self.assertEqual(result["thresholds_short_of_the_documents_they_need"], [])


if __name__ == "__main__":
    unittest.main()
