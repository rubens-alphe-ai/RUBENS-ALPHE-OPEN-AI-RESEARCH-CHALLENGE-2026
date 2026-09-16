"""Redaction of copied state identifiers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from redact_leak_markers import redact_text  # noqa: E402


class RedactionTests(unittest.TestCase):
    def test_identifier_becomes_plain_words(self) -> None:
        text, count = redact_text("See verified_knowledge and open_questions.", ["verified_knowledge", "open_questions"])
        self.assertEqual(text, "See verified knowledge and open questions.")
        self.assertEqual(count, 2)

    def test_longer_marker_is_replaced_whole(self) -> None:
        text, _ = redact_text("the open_questions_list", ["open_questions_list", "open_questions"])
        self.assertEqual(text, "the open questions list")

    def test_idempotent(self) -> None:
        once, _ = redact_text("verified_knowledge", ["verified_knowledge"])
        twice, count = redact_text(once, ["verified_knowledge"])
        self.assertEqual(once, twice)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
