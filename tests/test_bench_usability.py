"""The rule every protocol states and nothing enforced: when a run may not be analysed."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import handoff_bench as hb  # noqa: E402

ARMS = ["summary", "checklist", "sections", "facts_only"]


def runs(failed_per_arm: dict[str, int], repeats: int = 6) -> list[dict]:
    records = []
    for arm in ARMS:
        for repeat in range(1, repeats + 1):
            record = {"strategy": arm, "repeat": repeat}
            if repeat > failed_per_arm.get(arm, 0):
                record["grades"] = {"5": {"fact_accuracy": 0.8, "inventions": 0}}
            records.append(record)
    return records


class UsabilityTests(unittest.TestCase):
    def test_a_clean_run_is_usable(self) -> None:
        self.assertTrue(hb.usability(runs({}), ARMS)["usable"])

    def test_the_batch_that_had_to_be_refused_by_hand_is_refused_by_code(self) -> None:
        # MEM-014's first batch: 2/2/2/0 across four arms of six. It was declared
        # unusable manually, after its scores had already been read.
        verdict = hb.usability(runs({"summary": 2, "checklist": 2, "sections": 2}), ARMS)
        self.assertFalse(verdict["usable"])
        self.assertAlmostEqual(verdict["failure_rate_spread"], 2 / 6, places=4)
        self.assertIn("unusable rather than analysable", verdict["reason"])

    def test_failures_spread_evenly_do_not_make_a_run_unusable(self) -> None:
        # Losing a run in every arm costs power; it does not bias the comparison,
        # which is what the rule is about.
        self.assertTrue(hb.usability(runs({arm: 1 for arm in ARMS}), ARMS)["usable"])

    def test_one_failure_in_one_arm_of_six_is_over_the_tolerance(self) -> None:
        verdict = hb.usability(runs({"checklist": 1}), ARMS)
        self.assertFalse(verdict["usable"])
        self.assertEqual(verdict["failed_by_arm"]["checklist"], 1)

    def test_an_unusable_verdict_is_the_first_thing_the_report_says(self) -> None:
        meta = {"document": "d.md", "fact_questions": 30, "absent_questions": 10, "repeats": 6,
                "generator": "w", "reader": "r", "word_limit": 150,
                "usability": hb.usability(runs({"summary": 2}), ARMS)}
        report = hb.render_report({"5": {}}, meta)
        self.assertIn("UNUSABLE", report.splitlines()[2])

    def test_a_usable_run_gets_no_banner(self) -> None:
        meta = {"document": "d.md", "fact_questions": 30, "absent_questions": 10, "repeats": 6,
                "generator": "w", "reader": "r", "word_limit": 150,
                "usability": hb.usability(runs({}), ARMS)}
        self.assertNotIn("UNUSABLE", hb.render_report({"5": {}}, meta))


if __name__ == "__main__":
    unittest.main()
