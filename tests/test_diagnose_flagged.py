"""The diagnosis experiment's parsing and scoring, without asking any model."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import diagnose_flagged as df  # noqa: E402


def item(name: str, screening: bool, key_error: bool, any_error: bool) -> dict:
    return {"subject": "s", "item": name, "screening": screening, "strict": False,
            "error_type": "wrong_groundtruth" if key_error else ("bad_question_clarity" if any_error else "ok"),
            "key_error": key_error, "any_error": any_error}


class ParseTests(unittest.TestCase):
    def test_a_verdict_inside_prose_is_read(self) -> None:
        got = df.parse('Here: {"verdict": "key_wrong", "best_option": "c", "reason": "C is right"} done')
        self.assertEqual((got["verdict"], got["best_option"]), ("KEY_WRONG", "C"))

    def test_a_verdict_without_an_option_is_read(self) -> None:
        # Stopped the first run: best_option null raised instead of parsing.
        self.assertIsNone(df.parse('{"verdict": "UNCLEAR", "best_option": null}')["best_option"])
        self.assertIsNone(df.parse('{"verdict": "UNCLEAR", "best_option": ""}')["best_option"])

    def test_an_unknown_verdict_is_unusable(self) -> None:
        self.assertIsNone(df.parse('{"verdict": "MAYBE"}'))
        self.assertIsNone(df.parse("no json at all"))


class ScoreTests(unittest.TestCase):
    def test_no_verdict_counts_as_missed_and_leaves_precision_alone(self) -> None:
        chosen = [item("1", True, True, True), item("2", True, True, True), item("3", True, False, False),
                  item("4", False, False, False)]
        answers = {("s", "1"): {"verdict": "KEY_WRONG"}, ("s", "3"): {"verdict": "KEY_OK"},
                   ("s", "4"): {"verdict": "KEY_OK"}}
        result = df.score(chosen, answers)
        self.assertEqual(result["D1_expert_key_error_among_KEY_WRONG"]["n"], 1)
        self.assertEqual(result["D2_share_of_expert_key_errors_called_KEY_WRONG"]["hits"], 1)
        self.assertEqual(result["D2_share_of_expert_key_errors_called_KEY_WRONG"]["n"], 2)
        self.assertEqual(result["no_verdict"], 1)
        self.assertEqual(result["D4_KEY_WRONG_rate_on_unflagged_controls"]["hits"], 0)


if __name__ == "__main__":
    unittest.main()
