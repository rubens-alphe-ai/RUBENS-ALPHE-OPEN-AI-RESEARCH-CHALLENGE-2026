"""The buyer-facing page: what it must refuse to say."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import diagnose_report as dr  # noqa: E402

VERIFY = {"recompute_command": "python scripts/regression_suite.py", "runs": {"a.json": "x"}}


def bench(control_last: float, other: dict, usable: bool = True, absent: int = 8) -> dict:
    rows = {"summary": {"facts_kept_pct": control_last, "inventions": 0, "absent_questions_asked": absent * 6,
                        "ci95": [0, 0], "runs": 6}}
    rows.update(other)
    meta = {"document": "d.md", "fact_questions": 23, "absent_questions": absent, "repeats": 6,
            "generator": "w", "reader": "r", "word_limit": 150, "failed_runs": 0,
            "usability": {"usable": usable, "reason": "failures fall unevenly across arms",
                          "failed_by_arm": {"summary": 2}, "runs_by_arm": {"summary": 6}}}
    return {"meta": meta, "by_hop": {"1": dict(rows), "5": rows}}


def arm(pct: float, delta: float, ci: list[float]) -> dict:
    return {"facts_kept_pct": pct, "vs_control_pp": delta, "vs_control_ci95": ci,
            "inventions": 0, "absent_questions_asked": 48, "ci95": [0, 0], "runs": 6}


class RefusalTests(unittest.TestCase):
    def test_an_unusable_run_carries_no_numbers_at_all(self) -> None:
        page = dr.render(bench(62.0, {"checklist": arm(91.0, 29.7, [8.6, 50.8])}, usable=False), VERIFY, "summary")
        self.assertIn("produced no result", page)
        self.assertNotIn("91%", page)
        self.assertNotIn("+30 points", page)

    def test_an_effect_whose_interval_crosses_zero_is_never_sold_as_a_gain(self) -> None:
        # The whole commercial value of the page is that it does not do this.
        page = dr.render(bench(62.0, {"checklist": arm(70.0, 8.0, [-3.0, 19.0])}, usable=True), VERIFY, "summary")
        self.assertIn("No alternative instruction was distinguishable", page)
        self.assertNotIn("recovers **8 points**", page)

    def test_a_resolved_effect_is_stated_plainly(self) -> None:
        page = dr.render(bench(62.0, {"checklist": arm(91.0, 29.7, [8.6, 50.8])}, usable=True), VERIFY, "summary")
        self.assertIn("recovers **30 points**", page)
        self.assertIn("| yes |", page)

    def test_an_unresolved_row_is_marked_in_the_table(self) -> None:
        page = dr.render(bench(62.0, {"facts_only": arm(57.0, -4.3, [-19.3, 10.6])}, usable=True), VERIFY, "summary")
        self.assertIn("**no**", page)

    def test_the_question_count_and_the_answer_count_are_not_confused(self) -> None:
        # An earlier version said "48 questions the document never answered" in
        # the body and "8" in the appendix. A reader who notices that stops
        # reading, and is right to.
        page = dr.render(bench(62.0, {"checklist": arm(91.0, 29.7, [8.6, 50.8])}, absent=8), VERIFY, "summary")
        self.assertIn("never answers 8 of the questions", page)
        self.assertIn("6 times per instruction", page)

    def test_no_stray_percent_escape_survives_into_the_page(self) -> None:
        page = dr.render(bench(62.0, {"checklist": arm(91.0, 29.7, [8.6, 50.8])}), VERIFY, "summary")
        self.assertNotIn("%%", page)

    def test_the_page_tells_the_reader_how_to_recompute_it(self) -> None:
        page = dr.render(bench(62.0, {"checklist": arm(91.0, 29.7, [8.6, 50.8])}), VERIFY, "summary")
        self.assertIn(VERIFY["recompute_command"], page)


if __name__ == "__main__":
    unittest.main()
