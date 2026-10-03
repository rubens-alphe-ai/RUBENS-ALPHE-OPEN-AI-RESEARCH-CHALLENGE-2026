"""The model-choice report groups models by established gaps and never calls them equal."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_outbound_claims as oc  # noqa: E402
import model_choice_report as mr  # noqa: E402


def table() -> dict:
    n = 400
    by = {"strong": {}, "mid1": {}, "mid2": {}}
    for i in range(n):
        by["strong"][str(i)] = 1 if i < 340 else 0
        by["mid1"][str(i)] = 1 if i < 290 else 0
        by["mid2"][str(i)] = 1 if (i < 285 or 330 <= i < 333) else 0
    return by


class ReportTests(unittest.TestCase):
    def test_the_best_alone_leads_when_its_gaps_are_established(self) -> None:
        result = mr.analyse(table(), ["strong", "mid1", "mid2"])
        self.assertEqual(result["leading"], ["strong"])

    def test_the_text_passes_the_claims_tripwire(self) -> None:
        result = mr.analyse(table(), ["strong", "mid1", "mid2"])
        page = mr.render("t", "s", ["strong", "mid1", "mid2"], {}, {"mid1": [1, 9], "mid2": [0.2, 0.4], "strong": [5, 25]}, result)
        self.assertEqual(oc.check(page), [])
        self.assertIn("aucun écart établi", page)


if __name__ == "__main__":
    unittest.main()
