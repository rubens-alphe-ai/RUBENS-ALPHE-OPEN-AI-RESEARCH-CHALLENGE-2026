"""The model gate passes and fails on established gaps only."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import model_gate as mg  # noqa: E402


def results(right: int, n: int = 300, offset: int = 0) -> dict[str, int]:
    return {str(i): 1 if offset <= i < offset + right else 0 for i in range(n)}


class GateTests(unittest.TestCase):
    def test_a_small_lead_does_not_pass_require_better(self) -> None:
        current, candidate = results(200), results(205)
        self.assertFalse(mg.decide(current, candidate, "better")["passed"])

    def test_a_clear_lead_passes_require_better(self) -> None:
        current, candidate = results(180), results(240)
        self.assertTrue(mg.decide(current, candidate, "better")["passed"])

    def test_a_clear_loss_fails_require_not_worse(self) -> None:
        current, candidate = results(240), results(180)
        self.assertFalse(mg.decide(current, candidate, "not-worse")["passed"])

    def test_not_worse_says_what_it_could_have_missed(self) -> None:
        got = mg.decide(results(200), results(197), "not-worse")
        self.assertTrue(got["passed"])
        self.assertIn("does not show the two are equal", got["reading"])
        self.assertIsNotNone(got["smallest_detectable_gap_pts"])


if __name__ == "__main__":
    unittest.main()
