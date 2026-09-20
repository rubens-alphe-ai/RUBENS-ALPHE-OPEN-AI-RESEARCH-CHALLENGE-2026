"""Five fields that cannot pay for one another."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import status_tuple as st  # noqa: E402


class ShapeTests(unittest.TestCase):
    def test_every_field_is_always_present(self) -> None:
        # A field that goes missing when it is inconvenient is the trade this
        # exists to prevent.
        state = {"fields": {name: {"state": "x", "detail": "y"} for name, _ in st.FIELDS}}
        rendered = st.markdown(state)
        for name, _ in st.FIELDS:
            self.assertIn(name, rendered)

    def test_there_is_no_overall_score_to_trade_against(self) -> None:
        # status() is deliberately not called here: pipeline_field() runs the
        # whole test suite, so a test that builds the real tuple runs the suite
        # inside the suite. The shape is what this pins, not the values.
        self.assertEqual([name for name, _ in st.FIELDS],
                         ["pipeline", "reproducibility", "invalidations", "risks", "external"])
        rendered = st.markdown({"fields": {name: {"state": "x", "detail": "y"} for name, _ in st.FIELDS}})
        self.assertNotIn("score", rendered.lower())
        self.assertNotIn("overall", rendered.lower())


class ExternalTests(unittest.TestCase):
    def test_no_external_run_is_unmeasured_and_not_zero(self) -> None:
        # Zero completed external runs and an unmeasured external
        # reproducibility are different statements. This project spent a day
        # confusing them.
        field = st.external_field()
        self.assertEqual(field["state"], st.UNMEASURED)
        self.assertIn("unmeasured because no external run has completed", field["detail"])

    def test_the_counts_are_still_reported_beside_the_word(self) -> None:
        field = st.external_field()
        for name in ("replications_submitted", "replications_reviewed", "panel_answers"):
            self.assertIsInstance(field[name], int)


class RiskTests(unittest.TestCase):
    def test_an_undeclared_register_is_unmeasured_not_empty(self) -> None:
        original = st.ROOT
        st.ROOT = Path(tempfile.mkdtemp())
        try:
            field = st.risks_field()
        finally:
            st.ROOT = original
        self.assertEqual(field["state"], st.UNMEASURED)
        self.assertIn("not the same as none", field["detail"])

    def test_this_repository_declares_its_risks_and_each_says_how_it_closes(self) -> None:
        field = st.risks_field()
        self.assertNotEqual(field["state"], st.UNMEASURED)
        for risk in field["risks"]:
            self.assertTrue(risk.get("closes_when"), risk.get("id"))


class InvalidationTests(unittest.TestCase):
    def test_invalidations_are_named_not_counted_away(self) -> None:
        field = st.invalidations_field()
        self.assertTrue(field["named"], "known invalidations exist and must be listed")
        self.assertIn("PROP-EXP-MEM-007", " ".join(field["named"]))


if __name__ == "__main__":
    unittest.main()
