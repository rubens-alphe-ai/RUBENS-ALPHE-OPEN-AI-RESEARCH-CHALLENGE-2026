"""Input-safety tests for the QCM report, written by Codex (QCM-QUALITE-001).

They found that letters without a key, partial credit, short rows, a short or
repeated key and an empty header were accepted or crashed, and that markup in
answers reached the report unescaped. The strict contract in qcm_report.parse
answers all ten.
"""
from __future__ import annotations

import html
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import qcm_report as qr  # noqa: E402


def sample(values: str, key: str | None = None, header: str = "Q1;Q2") -> str:
    lines = ["ID;" + header]
    if key is not None:
        lines.append("KEY;" + key)
    lines.extend("P%d;%s" % (i, values) for i in range(6))
    return "\n".join(lines)


class QcmInputSafety(unittest.TestCase):
    def assert_refused(self, text: str) -> None:
        # A validation error is acceptable; an IndexError is not validation.
        with self.assertRaises((SystemExit, ValueError)):
            qr.parse(text)

    def test_valid_binary_control(self):
        self.assertEqual(qr.parse(sample("1;0"))["scored"], [[1, 0]] * 6)

    def test_valid_keyed_control(self):
        self.assertEqual(qr.parse(sample("A;B", "A;B"))["scored"], [[1, 1]] * 6)

    def test_letters_without_key_are_refused(self):
        self.assert_refused(sample("A;B"))

    def test_fractional_scores_are_refused(self):
        self.assert_refused(sample("0.5;1"))

    def test_short_rows_are_not_silently_padded(self):
        self.assert_refused(sample("1"))

    def test_short_key_is_a_validation_error(self):
        self.assert_refused(sample("A;B", "A"))

    def test_two_conflicting_keys_are_refused(self):
        self.assert_refused(sample("A;B", "A;B") + "\nKEY;B;A")

    def test_zero_questions_are_refused(self):
        self.assert_refused("ID\nP1\nP2\nP3\nP4\nP5\nP6")

    def assert_markup_not_rendered(self, text: str, marker: str) -> None:
        try:
            data = qr.parse(text)
        except (SystemExit, ValueError):
            return  # Refusing non-answer input is safe too.
        report = qr.single_report("SYNTHETIC-ONLY", data, qr.analyse(data))
        self.assertTrue(marker not in report, "Input markup was embedded as HTML")
        self.assertIn(html.escape(marker), report)

    def test_answer_markup_is_refused_or_escaped(self):
        marker = "<EM DATA-QCM-PROBE=1>X</EM>"
        self.assert_markup_not_rendered(sample(marker + ";B", "A;B"), marker)

    def test_key_markup_is_refused_or_escaped(self):
        marker = "<EM DATA-QCM-PROBE=2>X</EM>"
        self.assert_markup_not_rendered(sample("A;B", marker + ";B"), marker)


if __name__ == "__main__":
    unittest.main()
