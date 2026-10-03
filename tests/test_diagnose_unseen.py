"""Planting and scoring of the unseen-question replication, without asking any model."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import diagnose_unseen as du  # noqa: E402


def clean_items(n: int) -> list[dict]:
    return [{"id": "q%03d" % i, "subject": "anatomy", "question": "Q%d?" % i,
             "choices": ["a", "b", "c", "d"], "key": "ABCD"[i % 4]} for i in range(n)]


class PlantTests(unittest.TestCase):
    def test_a_fixed_fifth_is_planted_with_a_wrong_key(self) -> None:
        sample = du.plant(clean_items(400))
        self.assertEqual(len(sample), du.SAMPLE)
        planted = [i for i in sample if i["planted"]]
        self.assertEqual(len(planted), du.PLANTED)
        self.assertTrue(all(i["key"] != i["original_key"] for i in planted))
        self.assertTrue(all(i["key"] == i["original_key"] for i in sample if not i["planted"]))

    def test_planting_is_reproducible(self) -> None:
        self.assertEqual(du.plant(clean_items(400)), du.plant(clean_items(400)))


class ScoreTests(unittest.TestCase):
    def test_precision_recall_and_false_alarms(self) -> None:
        sample = du.plant(clean_items(400))
        verdicts = {}
        for item in sample:
            if item["planted"]:
                verdicts[item["id"]] = {"verdict": "KEY_WRONG", "best_option": item["original_key"]}
            else:
                verdicts[item["id"]] = {"verdict": "KEY_OK"}
        result = du.score(sample, verdicts)
        self.assertEqual(result["U1_precision_of_KEY_WRONG"]["rate"], 1.0)
        self.assertEqual(result["U2_planted_errors_called_KEY_WRONG"]["rate"], 1.0)
        self.assertEqual(result["U3_KEY_WRONG_on_clean_items"]["hits"], 0)
        self.assertTrue(all(v == "held" for v in result["predictions"].values()))


if __name__ == "__main__":
    unittest.main()
