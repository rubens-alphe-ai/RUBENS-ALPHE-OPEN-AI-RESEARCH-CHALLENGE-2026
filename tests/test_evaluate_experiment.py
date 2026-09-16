"""Independence rules of the automated evaluation chain."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from evaluate_experiment import independence_problems  # noqa: E402


def entry(evaluator_id: str, provider: str, model: str) -> dict:
    return {"evaluator_id": evaluator_id, "provider": provider, "model": model,
            "endpoint": "http://example.invalid", "api_key_file": "k"}


class IndependenceTests(unittest.TestCase):
    def test_two_scorers_from_different_providers_pass(self) -> None:
        config = {"scorers": [entry("a", "Google", "m1"), entry("b", "Groq", "m2")], "checkers": []}
        self.assertEqual(independence_problems(config, "llama3.2:3b"), [])

    def test_a_single_scorer_is_refused(self) -> None:
        config = {"scorers": [entry("a", "Google", "m1")], "checkers": []}
        self.assertTrue(independence_problems(config, "llama3.2:3b"))

    def test_same_provider_twice_is_refused(self) -> None:
        config = {"scorers": [entry("a", "Google", "m1"), entry("b", "google ", "m2")], "checkers": []}
        self.assertTrue(independence_problems(config, "llama3.2:3b"))

    def test_generator_model_cannot_evaluate_itself(self) -> None:
        config = {"scorers": [entry("a", "Google", "m1"), entry("b", "Ollama", "LLAMA3.2:3B")], "checkers": []}
        self.assertTrue(any("generator" in p for p in independence_problems(config, "llama3.2:3b")))

    def test_duplicate_evaluator_ids_are_refused(self) -> None:
        config = {"scorers": [entry("a", "Google", "m1"), entry("a", "Groq", "m2")], "checkers": []}
        self.assertTrue(independence_problems(config, "llama3.2:3b"))


if __name__ == "__main__":
    unittest.main()
