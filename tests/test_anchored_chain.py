"""The archive arm: what a writer is allowed to see, and what it is not."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import anchored_chain as ac  # noqa: E402
import build_ledger as bl  # noqa: E402

DOCUMENT = ("# Clinic\n\nThe clinic serves 4200 patients. It runs 6 rooms.\n\n"
            "The fridge failed in March 2024 and 2100 euros of stock was discarded.\n")


class LedgerTests(unittest.TestCase):
    def test_one_entry_per_sentence_each_with_its_hash(self) -> None:
        entries = bl.entries(DOCUMENT)
        self.assertEqual([entry["id"] for entry in entries], ["E01", "E02", "E03", "E04"])
        for entry in entries:
            self.assertEqual(entry["sha256"], bl.sha256_text(entry["text"]))

    def test_the_index_shows_labels_and_never_the_content(self) -> None:
        entries = bl.entries(DOCUMENT)
        index = bl.render_index(entries)
        self.assertIn("E04", index)
        self.assertNotIn("2100", index)
        self.assertNotIn("discarded", index)

    def test_a_label_is_cut_to_its_first_words(self) -> None:
        entries = bl.entries(DOCUMENT, label_words=2)
        self.assertEqual(entries[1]["label"], "The clinic…")

    def test_a_label_masks_every_digit(self) -> None:
        # An index names a topic; it must not quote the value, or consulting it
        # would replace retrieving the entry.
        label = bl.entries(DOCUMENT)[1]["label"]
        self.assertIn("####", label)
        self.assertNotIn("4200", label)

    def test_a_hard_wrapped_paragraph_is_unwrapped_before_splitting(self) -> None:
        wrapped = "The fridge failed in March 2024 and\n2100 euros of stock was discarded.\n"
        entries = bl.entries(wrapped)
        self.assertEqual(len(entries), 1)
        self.assertIn("March 2024 and 2100 euros", entries[0]["text"])

    def test_retrieval_stops_at_the_limit_and_ignores_unknown_ids(self) -> None:
        entries = bl.entries(DOCUMENT)
        got = bl.fetch(entries, ["E04", "E99", "E02", "E03"], limit=2)
        self.assertEqual([entry["id"] for entry in got], ["E04", "E02"])

    def test_a_tampered_entry_is_refused_rather_than_served(self) -> None:
        entries = bl.entries(DOCUMENT)
        entries[0]["text"] = "something else"
        with self.assertRaises(ValueError):
            bl.fetch(entries, ["E01"], limit=1)


class AskTests(unittest.TestCase):
    def test_identifiers_are_read_in_order_without_duplicates(self) -> None:
        self.assertEqual(ac.parse_ids("I want E04, E02 and E04 again", 4), ["E04", "E02"])

    def test_no_more_identifiers_than_the_limit_allows(self) -> None:
        self.assertEqual(ac.parse_ids("E01 E02 E03 E04 E05", 2), ["E01", "E02"])

    def test_prose_without_identifiers_retrieves_nothing(self) -> None:
        self.assertEqual(ac.parse_ids("I do not need anything.", 4), [])


class RegimeTests(unittest.TestCase):
    """Every call is recorded instead of made, so the prompts can be inspected."""

    def setUp(self) -> None:
        self.prompts: list[str] = []
        self.ledger = bl.entries(DOCUMENT)
        self.index = bl.render_index(self.ledger)

        def fake_call(entry, prompt, max_tokens):  # noqa: ANN001
            self.prompts.append(prompt)
            return ("E04" if prompt.startswith("Below is a handover note") else "a handoff"), "fake"

        self.original = ac.call
        ac.call = fake_call

    def tearDown(self) -> None:
        ac.call = self.original

    def chain(self, regime: str) -> list[dict]:
        return ac.write_chain(regime, {}, DOCUMENT, "Write a handover.", 2,
                              self.ledger, self.index, 2, 100, 150)

    def test_the_bare_regime_never_mentions_the_archive(self) -> None:
        self.chain("bare")
        self.assertEqual(len(self.prompts), 2)
        for prompt in self.prompts:
            self.assertNotIn("E04", prompt)

    def test_the_index_regime_shows_the_index_but_retrieves_nothing(self) -> None:
        chain = self.chain("index")
        self.assertIn("E04", self.prompts[1])
        self.assertNotIn("2100 euros", self.prompts[1])
        self.assertEqual(chain[1]["retrieved"], [])

    def test_the_anchored_regime_asks_then_receives_the_entry_verbatim(self) -> None:
        chain = self.chain("anchored")
        self.assertEqual(chain[1]["asked"], ["E04"])
        self.assertEqual(chain[1]["retrieved"], ["E04"])
        self.assertIn("2100 euros", self.prompts[2])

    def test_the_first_hop_is_identical_under_every_regime(self) -> None:
        # Hop 1 reads the document itself; an archive there would only be a copy
        # of what is already in front of the writer.
        first = []
        for regime in ("bare", "index", "anchored"):
            self.prompts.clear()
            self.chain(regime)
            first.append(self.prompts[0])
        self.assertEqual(len(set(first)), 1)


if __name__ == "__main__":
    unittest.main()
