"""The training-provider demonstration builds from stored verdicts, without calling a model."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_outbound_claims as oc  # noqa: E402
import demo_formation as df  # noqa: E402


class DemoTests(unittest.TestCase):
    def test_the_demo_builds_and_passes_the_claims_check(self) -> None:
        rng = random.Random(df.SEED)
        bodies = [df.section(label, df.load_module(subject), rng)[0] for subject, label in df.MODULES]
        page = df.page(bodies)
        self.assertIn("DÉMONSTRATION PRIVÉE", page)
        self.assertEqual(oc.check(page), [])


if __name__ == "__main__":
    unittest.main()
