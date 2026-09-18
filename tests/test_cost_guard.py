"""The spend guard: pessimistic estimates, and a refusal when they exceed the budget."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cost_guard  # noqa: E402

PAID = {"prompt": 1e-6, "completion": 2e-6}   # $1 and $2 per million tokens
FREE = {"prompt": 0.0, "completion": 0.0}


class EstimateTests(unittest.TestCase):
    def test_counts_every_call_prompt_and_full_output_budget(self) -> None:
        # 35,000 chars ≈ 10,000 prompt tokens, plus 1,000 output tokens, twice.
        cost = cost_guard.estimate(2, 35000, 1000, PAID)
        self.assertAlmostEqual(cost, 2 * (10000 * 1e-6 + 1000 * 2e-6), places=9)

    def test_free_models_cost_nothing(self) -> None:
        self.assertEqual(cost_guard.estimate(500, 40000, 4000, FREE), 0.0)


class PlanTests(unittest.TestCase):
    def test_plan_matches_the_experiment_policy(self) -> None:
        steps = cost_guard.plan_for("PROP-EXP-MEM-006")
        self.assertEqual([step["stage"] for step in steps], ["generation", "reading"])
        self.assertEqual(steps[0]["calls"], 120)   # sixty pairs, two conditions
        self.assertEqual(steps[1]["calls"], 120)
        self.assertGreater(steps[0]["prompt_chars"], 4000)


class CheckTests(unittest.TestCase):
    def check_with(self, table: dict, budget: float) -> dict:
        policy = {"generation": {"model": "gen", "seeds": [1, 2, 3, 4, 5], "max_output_tokens": 1000,
                                 "baseline_state": "STATE_A.txt", "structured_state": "STATE_A.txt"},
                  "reader": {"model": "read", "max_tokens": 1500}, "quiz": {"file": "QUIZ.json"},
                  "budget": {"max_usd": budget}}
        paid_endpoint = "https://openrouter.ai/api/v1/chat/completions"
        plan = [{"stage": "generation", "model": "gen", "calls": 10, "prompt_chars": 35000,
                 "max_output_tokens": 1000, "endpoint": paid_endpoint},
                {"stage": "reading", "model": "read", "calls": 10, "prompt_chars": 35000,
                 "max_output_tokens": 1500, "endpoint": paid_endpoint}]
        with mock.patch.object(cost_guard, "prices", return_value=table), \
             mock.patch.object(cost_guard, "plan_for", return_value=plan), \
             mock.patch.object(cost_guard.json, "loads", return_value=policy), \
             mock.patch.object(Path, "read_text", return_value="{}"):
            return cost_guard.check("PROP-EXP-TEST", key_file=None)

    def test_within_budget_is_allowed(self) -> None:
        report = self.check_with({"gen": PAID, "read": PAID}, budget=1.0)
        self.assertEqual(report["status"], "WITHIN_BUDGET")
        self.assertGreater(report["estimated_usd"], 0)

    def test_over_budget_is_refused(self) -> None:
        report = self.check_with({"gen": PAID, "read": PAID}, budget=0.0001)
        self.assertEqual(report["status"], "REFUSED")
        self.assertIn("exceeds the budget", report["reason"])

    def test_a_model_with_no_published_price_is_refused(self) -> None:
        report = self.check_with({"gen": PAID}, budget=100.0)
        self.assertEqual(report["status"], "REFUSED")
        self.assertIn("no published price", report["reason"])

    def test_another_provider_is_not_charged_to_this_credit(self) -> None:
        policy = {"budget": {"max_usd": 0.0}}
        plan = [{"stage": "generation", "model": "gen", "calls": 500, "prompt_chars": 35000,
                 "max_output_tokens": 2000, "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions"}]
        with mock.patch.object(cost_guard, "prices", return_value={"gen": PAID}),              mock.patch.object(cost_guard, "plan_for", return_value=plan),              mock.patch.object(cost_guard.json, "loads", return_value=policy),              mock.patch.object(Path, "read_text", return_value="{}"):
            report = cost_guard.check("PROP-EXP-TEST", key_file=None)
        self.assertEqual(report["status"], "WITHIN_BUDGET")
        self.assertEqual(report["estimated_usd"], 0.0)
        self.assertFalse(report["steps"][0]["billed_here"])

    def test_free_models_pass_a_zero_budget(self) -> None:
        report = self.check_with({"gen": FREE, "read": FREE}, budget=0.0)
        self.assertEqual(report["status"], "WITHIN_BUDGET")
        self.assertEqual(report["estimated_usd"], 0.0)


if __name__ == "__main__":
    unittest.main()
