"""Merging independent chains: what is fed in, and what is claimed from it."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import merge_chains as mc  # noqa: E402


def chain(repeat: int, hop_texts: dict[int, str], accuracy: float) -> dict:
    return {"strategy": "summary", "repeat": repeat,
            "chain": [{"hop": hop, "text": text, "words_kept": len(text.split()), "trimmed": False}
                      for hop, text in sorted(hop_texts.items())],
            "grades": {str(hop): {"fact_accuracy": accuracy, "inventions": 0, "absent_questions": 8}
                       for hop in hop_texts}}


class SourceTests(unittest.TestCase):
    def folder_with(self, records: list[dict]) -> Path:
        folder = Path(tempfile.mkdtemp())
        for record in records:
            (folder / ("summary-%02d.json" % record["repeat"])).write_text(json.dumps(record), encoding="utf-8")
        return folder

    def test_takes_the_handoff_written_at_that_hop(self) -> None:
        folder = self.folder_with([chain(1, {1: "first one", 5: "fifth one"}, 0.5)])
        found = mc.sources(folder, "summary", 5)
        self.assertEqual(found[0]["text"], "fifth one")

    def test_ignores_failed_and_ungraded_chains(self) -> None:
        folder = self.folder_with([chain(1, {5: "kept"}, 0.5)])
        (folder / "summary-02.failed.json").write_text(json.dumps({"strategy": "summary", "repeat": 2}), encoding="utf-8")
        (folder / "summary-03.json").write_text(json.dumps(
            {"strategy": "summary", "repeat": 3, "chain": [{"hop": 5, "text": "x", "words_kept": 1, "trimmed": False}],
             "grades": {}}), encoding="utf-8")
        self.assertEqual([item["repeat"] for item in mc.sources(folder, "summary", 5)], [1])


class PromptTests(unittest.TestCase):
    def test_every_note_is_included_and_the_budget_is_stated(self) -> None:
        prompt = mc.merge_prompt(["note one", "note two", "note three"], 150)
        self.assertIn("3 handover notes", prompt)
        self.assertIn("under 150 words", prompt)
        for text in ("note one", "note two", "note three"):
            self.assertIn(text, prompt)

    def test_the_merger_is_told_not_to_add_anything(self) -> None:
        prompt = mc.merge_prompt(["a note"], 150)
        self.assertIn("Do not add anything that appears in none of them", prompt)
        self.assertNotIn("invent", prompt.lower())


if __name__ == "__main__":
    unittest.main()
