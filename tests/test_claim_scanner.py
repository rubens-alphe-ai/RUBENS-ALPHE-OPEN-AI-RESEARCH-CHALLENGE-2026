"""The claim scanner keeps only comparisons it can test, and tests them conservatively."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import claim_scanner as cs  # noqa: E402


class ScoreTests(unittest.TestCase):
    def test_percentages_and_proportions_are_read(self) -> None:
        self.assertAlmostEqual(cs.as_proportion("85.3"), 0.853)
        self.assertAlmostEqual(cs.as_proportion("85.3%"), 0.853)
        self.assertAlmostEqual(cs.as_proportion("0.853"), 0.853)
        self.assertAlmostEqual(cs.as_proportion("0,853"), 0.853)
        self.assertAlmostEqual(cs.as_proportion("85"), 0.85)

    def test_non_scores_are_refused(self) -> None:
        self.assertIsNone(cs.as_proportion("1250 Elo"))
        self.assertIsNone(cs.as_proportion("130"))


class BenchmarkTests(unittest.TestCase):
    def test_specific_names_win(self) -> None:
        self.assertEqual(cs.benchmark_of("MMLU-Pro", "")[0], "MMLU-Pro")
        self.assertEqual(cs.benchmark_of("**MMLU**", "")[0], "MMLU")
        self.assertEqual(cs.benchmark_of("GPQA-Diamond", "")[1], 198)
        self.assertEqual(cs.benchmark_of("AIME 2025", "")[1], 30)
        self.assertEqual(cs.benchmark_of("AIME2026", "")[0], "AIME 2026")
        self.assertEqual(cs.benchmark_of("ARC-Chal", "")[0], "ARC-Challenge")
        self.assertEqual(cs.benchmark_of("ARC-Easy", "")[0], "ARC-Easy")
        self.assertIsNone(cs.benchmark_of("ARC-AGI-2", ""))
        self.assertEqual(cs.benchmark_of("SWE-bench Pro", "")[1], 731)

    def test_ambiguous_names_are_skipped(self) -> None:
        self.assertIsNone(cs.benchmark_of("GPQA", ""))
        self.assertIsNone(cs.benchmark_of("MMLU-Redux", ""))
        self.assertIsNone(cs.benchmark_of("HumanEval+", ""))
        self.assertIsNone(cs.benchmark_of("LiveCodeBench v6", ""))


class VerdictTests(unittest.TestCase):
    def test_a_small_gap_on_a_small_test_is_not_established(self) -> None:
        got = cs.verdict(0.80, 0.733, 30)  # AIME: 24/30 against 22/30
        self.assertFalse(got["established"])
        self.assertGreater(got["questions_needed_80pct"], 30)

    def test_a_large_gap_on_a_large_test_is_established(self) -> None:
        self.assertTrue(cs.verdict(0.85, 0.80, 14042)["established"])


if __name__ == "__main__":
    unittest.main()


class RowTests(unittest.TestCase):
    ROWS = "| Benchmark | Ours-7B | Rival-8B |\n|---|---|---|\n| GSM8K | 81.2 | 79.0 |\n| MMLU | 70.1 | 72.3 |\n"
    COLUMNS = "| Model | GSM8K | MMLU |\n|---|---|---|\n| Ours-7B | 81.2 | 70.1 |\n| Rival-8B | 79.0 | 72.3 |\n"

    def test_benchmarks_as_rows(self) -> None:
        self.assertTrue(cs.same_table_row(self.ROWS, "GSM8K", "org/Ours-7B", "Rival-8B", "81.2", "79.0"))
        self.assertFalse(cs.same_table_row(self.ROWS, "GSM8K", "org/Ours-7B", "Rival-8B", "81.2", "72.3"))

    def test_benchmarks_as_columns(self) -> None:
        self.assertTrue(cs.same_table_row(self.COLUMNS, "GSM8K", "org/Ours-7B", "Rival-8B", "81.2", "79.0"))
        self.assertFalse(cs.same_table_row(self.COLUMNS, "GSM8K", "org/Ours-7B", "Rival-8B", "72.3", "79.0"))


class HtmlRowTests(unittest.TestCase):
    def test_html_tables_are_read(self) -> None:
        card = ("<table><tr><th>Benchmark</th><th>Ours-7B</th><th>Rival-8B</th></tr>"
                "<tr><td>SWE-bench Verified</td><td>79</td><td>76.4</td></tr></table>")
        self.assertTrue(cs.same_table_row(card, "SWE-bench Verified", "org/Ours-7B", "Rival-8B", "79", "76.4"))

    def test_names_match_without_punctuation(self) -> None:
        card = "| Model | GSM8K |\n|---|---|\n| Laguna XS 2.1 | 81.2 |\n| Rival 8B | 79.0 |\n"
        self.assertTrue(cs.same_table_row(card, "GSM8K", "org/Laguna-XS-2.1", "Rival-8B", "81.2", "79.0"))
