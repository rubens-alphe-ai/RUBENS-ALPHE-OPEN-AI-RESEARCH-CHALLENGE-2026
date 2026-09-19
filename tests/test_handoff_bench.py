"""The strategy benchmark: chains, length control, per-depth comparison, visible failures."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import handoff_bench as hb  # noqa: E402
import handoff_quiz as hq  # noqa: E402

QUIZ = {"quiz_version": "TEST-V1", "not_stated_option": "The text does not say.", "questions": [
    {"id": "Q01", "kind": "fact", "question": "How many bakers?", "correct": "Four",
     "distractors": ["Nine", "Two", "Eleven"]},
    {"id": "Q02", "kind": "fact", "question": "When did the oven break?", "correct": "January",
     "distractors": ["March", "August", "December"]},
    {"id": "X01", "kind": "absent", "question": "What is the revenue?",
     "distractors": ["100k", "250k", "1M", "5M"]},
]}
RENDERED, KEY = hq.render_quiz(QUIZ, "test")


class TrimTests(unittest.TestCase):
    def test_a_handoff_over_the_limit_is_cut(self) -> None:
        text, cut = hb.trim("one two three four five", 3)
        self.assertEqual(text, "one two three")
        self.assertTrue(cut)

    def test_a_short_handoff_is_untouched(self) -> None:
        text, cut = hb.trim("one two", 3)
        self.assertEqual(text, "one two")
        self.assertFalse(cut)

    def test_no_limit_keeps_everything(self) -> None:
        self.assertEqual(hb.trim("one two three", None), ("one two three", False))


class ChainTests(unittest.TestCase):
    def test_each_hop_sees_only_the_previous_trimmed_handoff(self) -> None:
        seen = []

        def fake_call(entry, prompt, max_tokens, limits=None):
            seen.append(prompt)
            return " ".join(["word%d" % len(seen)] * 10), entry["model"]

        with mock.patch.object(hb, "call", fake_call):
            chain = hb.write_chain({"model": "m"}, "THE DOCUMENT", "Summarise.", hops=3, max_tokens=100, words=4)
        self.assertEqual([step["hop"] for step in chain], [1, 2, 3])
        self.assertTrue(all(step["words_kept"] == 4 and step["trimmed"] for step in chain))
        self.assertIn("THE DOCUMENT", seen[0])
        self.assertNotIn("THE DOCUMENT", seen[1])
        self.assertIn("word1 word1 word1 word1", seen[1])

    def test_an_empty_answer_is_asked_again_before_failing(self) -> None:
        calls = []

        def flaky(entry, prompt, max_tokens, limits=None):
            calls.append(1)
            if len(calls) == 1:
                raise hb.AdapterError("model returned only reasoning and no answer")
            return "a handoff", entry["model"]

        with mock.patch.object(hb, "call", flaky):
            chain = hb.write_chain({"model": "m"}, "doc", "Summarise.", hops=1, max_tokens=100, words=None)
        self.assertEqual(len(chain), 1)
        self.assertEqual(len(calls), 2)


class StrategyTests(unittest.TestCase):
    def test_every_strategy_gets_the_same_length_limit(self) -> None:
        chosen = hb.strategies(150)
        self.assertTrue(all("under 150 words" in text for text in chosen.values()))
        self.assertEqual(sorted(chosen), sorted(hb.INSTRUCTIONS))


def record(strategy: str, repeat: int, per_hop: dict[int, int], words: int = 120, trimmed: bool = False) -> dict:
    return {"strategy": strategy, "repeat": repeat,
            "chain": [{"hop": hop, "words_kept": words, "trimmed": trimmed} for hop in sorted(per_hop)],
            "grades": {str(hop): {"fact_accuracy": correct / 2, "inventions": 0, "absent_questions": 1}
                       for hop, correct in per_hop.items()}}


class SummaryTests(unittest.TestCase):
    def test_each_depth_is_summarised_separately(self) -> None:
        records = [record("summary", i, {1: 2, 2: 1}) for i in range(1, 5)]
        self.assertEqual(hb.summarise(records, 1)["summary"]["facts_kept_pct"], 100.0)
        self.assertEqual(hb.summarise(records, 2)["summary"]["facts_kept_pct"], 50.0)

    def test_paired_difference_against_the_control(self) -> None:
        records = [record("summary", i, {1: 1}) for i in range(1, 5)] + \
                  [record("checklist", i, {1: 2}) for i in range(1, 5)]
        table = hb.summarise(records, 1)
        self.assertEqual(table["checklist"]["vs_control_pp"], 50.0)
        self.assertNotIn("vs_control_pp", table["summary"])

    def test_trimmed_runs_are_counted(self) -> None:
        records = [record("summary", 1, {1: 2}, trimmed=True), record("summary", 2, {1: 2})]
        self.assertEqual(hb.summarise(records, 1)["summary"]["trimmed_runs"], 1)

    def test_failed_runs_never_enter_the_table(self) -> None:
        records = [record("summary", 1, {1: 2}), {"strategy": "summary", "repeat": 2, "error": "timeout"}]
        self.assertEqual(hb.summarise(records, 1)["summary"]["runs"], 1)


class ReportTests(unittest.TestCase):
    def test_report_shows_one_table_per_depth_and_the_cuts(self) -> None:
        records = [record("summary", i, {1: 2, 3: 1}, trimmed=True) for i in range(1, 4)]
        tables = {"1": hb.summarise(records, 1), "3": hb.summarise(records, 3)}
        markup = hb.render_report(tables, {"document": "d.md", "fact_questions": 2, "absent_questions": 1,
                                           "repeats": 3, "generator": "g", "reader": "r", "word_limit": 150,
                                           "failed_runs": 2})
        self.assertIn("## After 1 handoff(s)", markup)
        self.assertIn("## After 3 handoff(s)", markup)
        self.assertIn("cut to 150 words", markup)
        self.assertIn("Failed runs", markup)


class CaseTests(unittest.TestCase):
    def test_a_finished_case_is_not_run_again(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / "summary-01.json").write_text(json.dumps({"strategy": "summary", "repeat": 1, "grades": {}}),
                                                 encoding="utf-8")
            with mock.patch.object(hb, "call", side_effect=AssertionError("should not be called")):
                got = hb.run_case({"strategy": "summary", "repeat": 1, "instruction": "x"}, "doc", QUIZ, RENDERED,
                                  KEY, {"model": "g"}, {"model": "r"}, [1], 100, out)
        self.assertEqual(got["repeat"], 1)

    def test_a_failure_is_written_down(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            with mock.patch.object(hb, "call", side_effect=hb.AdapterError("no answer")):
                got = hb.run_case({"strategy": "summary", "repeat": 2, "instruction": "x"}, "doc", QUIZ, RENDERED,
                                  KEY, {"model": "g"}, {"model": "r"}, [1], 100, out)
            self.assertIn("error", got)
            self.assertTrue((out / "summary-02.failed.json").is_file())


if __name__ == "__main__":
    unittest.main()
