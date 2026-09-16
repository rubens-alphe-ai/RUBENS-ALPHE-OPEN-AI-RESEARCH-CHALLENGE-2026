"""Pre-registered evaluator ladder and the unattended run orchestration."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import evaluate_experiment as ev  # noqa: E402
import run_experiment  # noqa: E402


def rung(evaluator_id: str, provider: str, key: str = "k") -> dict:
    return {"evaluator_id": evaluator_id, "provider": provider, "model": evaluator_id + "-model",
            "endpoint": "https://x.invalid/v1/chat/completions", "key": key}


class LadderConfigTests(unittest.TestCase):
    def test_keys_are_resolved_from_private_locations(self) -> None:
        policy = {"scorer_ladder": [rung("a", "Groq", "groq")], "checker_ladder": [rung("c", "OpenRouter", "or")]}
        private = {"keys": {"groq": {"api_key_file": "~/g.key"}, "or": {"api_key_env": "OR_KEY", "ignored": 1}}}
        built = ev.ladder_config(policy, private)
        self.assertEqual(built["scorers"][0]["api_key_file"], "~/g.key")
        self.assertNotIn("key", built["scorers"][0])
        self.assertEqual(built["checkers"][0]["api_key_env"], "OR_KEY")
        self.assertNotIn("ignored", built["checkers"][0])

    def test_missing_key_location_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            ev.ladder_config({"scorer_ladder": [rung("a", "Groq", "groq")]}, {"keys": {}})


class LadderWalkTests(unittest.TestCase):
    def walk(self, candidates: list[dict], results: dict[str, str]) -> tuple[list[dict], dict, list[list[str]]]:
        rounds: list[list[str]] = []

        def fake_score_one(experiment, entry, batches, max_tokens, policy):
            rounds.append([entry["evaluator_id"]])
            return {"evaluator_id": entry["evaluator_id"], "status": results[entry["evaluator_id"]]}

        with tempfile.TemporaryDirectory() as folder:
            experiment = Path(folder)
            packets = experiment / "results" / "blind_packets"
            packets.mkdir(parents=True)
            (packets / "EVALUATOR_PROMPT.md").write_text("prompt", encoding="utf-8")
            api = experiment / "results" / "api_evaluations"
            api.mkdir()
            (api / "b-batch01.raw.txt").write_text("old answer", encoding="utf-8")
            with mock.patch.object(ev, "score_one", side_effect=fake_score_one):
                log = ev.score_with_ladder(experiment, candidates, 1000, 0, dict(ev.DEFAULT_POLICY))
            record = json.loads((experiment / "results" / "evaluation-ladder-log.json").read_text(encoding="utf-8"))
            record["abandoned_files"] = sorted(p.name for p in (api / "abandoned").rglob("*") if p.is_file()) if (api / "abandoned").is_dir() else []
        return log, record, rounds

    def test_first_two_distinct_providers_are_enough(self) -> None:
        _, record, _ = self.walk([rung("a", "Groq"), rung("b", "OpenRouter"), rung("c", "Mistral")],
                                 {"a": "ingested", "b": "ingested", "c": "ingested"})
        self.assertEqual(record["accepted"], ["a", "b"])
        self.assertEqual(record["untried"], ["c"])

    def test_failed_rung_is_replaced_and_its_answers_set_aside(self) -> None:
        _, record, _ = self.walk([rung("a", "Groq"), rung("b", "OpenRouter"), rung("c", "OpenRouter")],
                                 {"a": "ingested", "b": "invalid batch", "c": "ingested"})
        self.assertEqual(record["accepted"], ["a", "c"])
        self.assertEqual(record["abandoned_files"], ["b-batch01.raw.txt"])

    def test_same_provider_is_never_accepted_twice(self) -> None:
        _, record, _ = self.walk([rung("a", "Groq"), rung("b", "groq "), rung("c", "OpenRouter")],
                                 {"a": "ingested", "b": "ingested", "c": "call failed"})
        self.assertEqual(record["accepted"], ["a"])
        self.assertIn("b", record["untried"])

    def test_resumed_run_counts_already_scored(self) -> None:
        _, record, _ = self.walk([rung("a", "Groq"), rung("b", "OpenRouter")],
                                 {"a": "already scored", "b": "already scored"})
        self.assertEqual(record["accepted"], ["a", "b"])


class OrchestrationTests(unittest.TestCase):
    def test_generation_block_is_required_and_checked(self) -> None:
        with self.assertRaises(SystemExit):
            run_experiment.generation_spec({})
        with self.assertRaises(SystemExit):
            run_experiment.generation_spec({"generation": {"provider": "x", "surprise": 1}})

    def test_leak_scan_report_keeps_no_per_trial_conditions(self) -> None:
        scan = json.dumps({"duplicate_outputs": [], "strong_leaks": [{"trial_id": "t", "condition": "structured"}],
                           "missing_outputs": []})
        completed = mock.Mock(returncode=1, stdout=scan, stderr="")
        with mock.patch.object(run_experiment, "script", return_value=completed):
            step = run_experiment.leak_scan(Path("X"))
        self.assertEqual(step["status"], "blocked")
        self.assertEqual(step["strong_leak_count"], 1)
        self.assertNotIn("structured", json.dumps(step))


if __name__ == "__main__":
    unittest.main()
