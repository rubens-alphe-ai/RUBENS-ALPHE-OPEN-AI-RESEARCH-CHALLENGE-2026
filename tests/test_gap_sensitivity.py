"""The sensitivity layer `zhaoxuan` asked for: what surface overlap cannot see."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import regrade_gap_targeting as rg  # noqa: E402


class StrictCarryTests(unittest.TestCase):
    def test_a_changed_value_is_a_gap_even_when_the_words_survive(self) -> None:
        entry = "The clinic serves 4200 patients."
        self.assertTrue(rg.carried_strict(entry, "The clinic serves 4200 patients daily."))
        self.assertFalse(rg.carried_strict(entry, "The clinic serves 3100 patients daily."))

    def test_a_flipped_polarity_is_a_gap(self) -> None:
        entry = "The accreditation is valid."
        self.assertTrue(rg.carried_strict(entry, "The accreditation is valid until April."))
        self.assertFalse(rg.carried_strict(entry, "The accreditation is not valid."))

    def test_a_paraphrase_is_still_missed_and_that_is_declared(self) -> None:
        # The failure the stricter test does not fix: same fact, other words.
        self.assertFalse(rg.carried_strict("Twelve nurses work in three shifts.",
                                           "Staffing: 12 nursing staff across 3 rotations."))

    def test_thousands_separators_do_not_make_a_value_look_changed(self) -> None:
        self.assertEqual(rg.numbers("4,200 patients"), rg.numbers("4200 patients"))

    def test_an_entry_without_negation_is_not_failed_by_a_negating_note(self) -> None:
        # A note may legitimately negate something else; only the entry's own
        # polarity is at stake.
        self.assertTrue(rg.carried_strict("Six rooms are in use.",
                                          "Six rooms are in use; no beds are free."))


if __name__ == "__main__":
    unittest.main()
