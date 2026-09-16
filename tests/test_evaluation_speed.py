"""Faster evaluation rules: rate-limit parsing, batch checks, reuse, policy."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import evaluate_experiment as ev  # noqa: E402
from model_adapter import parse_duration, parse_rate_limit  # noqa: E402
from probe_free_models import is_free, rank  # noqa: E402

COMPONENTS = {"mission_reconstruction": 20, "current_state_fidelity": 15, "failure_recovery": 10,
              "next_action_quality": 15, "missing_information_detection": 5, "reproducibility": 5}


def card(blind_id: str, total: int | None = None) -> dict:
    scores = dict(COMPONENTS)
    if total is not None:
        scores["total"] = total
    return {"blind_id": blind_id, "scores": scores, "critical_fabrications": [], "notes": ""}


class RateLimitTests(unittest.TestCase):
    def test_durations(self) -> None:
        self.assertEqual(parse_duration("7.5s"), 7.5)
        self.assertEqual(parse_duration("1m2.5s"), 62.5)
        self.assertAlmostEqual(parse_duration("120ms"), 0.12)
        self.assertEqual(parse_duration("30"), 30.0)
        self.assertIsNone(parse_duration("soon"))
        self.assertIsNone(parse_duration(None))

    def test_groq_style_headers(self) -> None:
        limits = parse_rate_limit({"x-ratelimit-remaining-tokens": "5000", "x-ratelimit-reset-tokens": "20.4s"})
        self.assertEqual(limits, {"remaining_tokens": 5000, "reset_tokens_seconds": 20.4})

    def test_no_wait_when_the_next_prompt_fits(self) -> None:
        self.assertEqual(ev.pause_before_next({"remaining_tokens": 8000, "reset_tokens_seconds": 30}, "x" * 3500, 65), 0.0)

    def test_wait_until_reset_when_it_does_not_fit(self) -> None:
        self.assertEqual(ev.pause_before_next({"remaining_tokens": 500, "reset_tokens_seconds": 30}, "x" * 35000, 65), 31.0)

    def test_provider_retry_after_wins(self) -> None:
        self.assertEqual(ev.pause_before_next({"retry_after_seconds": 12}, "x", 65), 12.0)

    def test_fixed_pause_when_provider_says_nothing(self) -> None:
        self.assertEqual(ev.pause_before_next({}, "x", 65), 65.0)


class BatchCheckTests(unittest.TestCase):
    def test_complete_valid_batch_passes(self) -> None:
        self.assertEqual(ev.batch_problems({"cards": [card("BLIND-01", 70), card("BLIND-02")]}, ["BLIND-01", "BLIND-02"]), [])

    def test_wrong_total_is_reported(self) -> None:
        problems = ev.batch_problems({"cards": [card("BLIND-01", 95), card("BLIND-02")]}, ["BLIND-01", "BLIND-02"])
        self.assertTrue(any("declared total" in p for p in problems))

    def test_missing_and_unexpected_cards_are_reported(self) -> None:
        problems = ev.batch_problems({"cards": [card("BLIND-01"), card("BLIND-09")]}, ["BLIND-01", "BLIND-02"])
        self.assertTrue(any("missing" in p for p in problems))
        self.assertTrue(any("unexpected" in p for p in problems))

    def test_checking_does_not_modify_the_answer(self) -> None:
        part = {"cards": [card("BLIND-01")]}
        ev.batch_problems(part, ["BLIND-01"])
        self.assertNotIn("total", part["cards"][0]["scores"])


class PromptAndPolicyTests(unittest.TestCase):
    def test_no_total_prompt_asks_for_no_total(self) -> None:
        text = ev.BATCH_OUTPUT_NO_TOTAL.format(ids="BLIND-01")
        self.assertNotIn('"total"', text)
        self.assertIn("do not write a total", text)

    def test_defaults_keep_frozen_behaviour(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            policy = ev.load_policy(Path(folder))
        self.assertTrue(policy["evaluator_writes_total"])
        self.assertFalse(policy["reuse_valid_batches"])
        self.assertEqual(policy["invalid_batch_retries"], 0)

    def test_unknown_policy_field_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "evaluation_policy.json").write_text(json.dumps({"skip_blinding": True}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                ev.load_policy(Path(folder))


class ReuseTests(unittest.TestCase):
    def store(self, folder: Path, prompt: str, content: str) -> None:
        entry = {"evaluator_id": "e", "provider": "p", "model": "m", "endpoint": "https://x.invalid/v1"}
        ev.store_raw(folder, "e-batch01", entry, prompt, content, "m")

    def test_valid_batch_for_the_same_prompt_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.store(Path(folder), "prompt", json.dumps({"cards": [card("BLIND-01")]}))
            self.assertIsNotNone(ev.reusable_batch(Path(folder), "e-batch01", "prompt", ["BLIND-01"]))

    def test_answer_to_another_prompt_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.store(Path(folder), "old prompt", json.dumps({"cards": [card("BLIND-01")]}))
            self.assertIsNone(ev.reusable_batch(Path(folder), "e-batch01", "prompt", ["BLIND-01"]))

    def test_edited_answer_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.store(Path(folder), "prompt", json.dumps({"cards": [card("BLIND-01")]}))
            Path(folder, "e-batch01.raw.txt").write_text(json.dumps({"cards": [card("BLIND-01", 1)]}), encoding="utf-8")
            self.assertIsNone(ev.reusable_batch(Path(folder), "e-batch01", "prompt", ["BLIND-01"]))

    def test_invalid_batch_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.store(Path(folder), "prompt", json.dumps({"cards": [card("BLIND-01", 99)]}))
            self.assertIsNone(ev.reusable_batch(Path(folder), "e-batch01", "prompt", ["BLIND-01"]))


class ProbeTests(unittest.TestCase):
    def test_free_detection(self) -> None:
        self.assertTrue(is_free({"id": "a/b:free"}))
        self.assertTrue(is_free({"id": "a/b", "pricing": {"prompt": "0", "completion": "0"}}))
        self.assertFalse(is_free({"id": "a/b", "pricing": {"prompt": "0.000001", "completion": "0"}}))
        self.assertFalse(is_free({"id": "a/b"}))

    def test_working_fast_models_rank_first(self) -> None:
        ranked = rank([{"model": "slow", "status": "OK", "seconds": 9}, {"model": "limited", "status": "RATE_LIMITED", "seconds": 1},
                       {"model": "fast", "status": "OK", "seconds": 2}])
        self.assertEqual([item["model"] for item in ranked], ["fast", "slow", "limited"])


if __name__ == "__main__":
    unittest.main()
