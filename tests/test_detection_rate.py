"""What the audit catches, what it invents, and how both depend on sample size."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import detection_rate as dr  # noqa: E402
import item_analysis as ia  # noqa: E402


class PlantingTests(unittest.TestCase):
    def test_a_miskeyed_item_is_the_better_performances_getting_it_wrong(self) -> None:
        # Not noise, and not a hard question: an item whose correctness is
        # inverted must correlate *negatively* with the rest of the test.
        rng = random.Random(1)
        rows, items, truth = dr.one_dataset(rng, 200, 12, {"miskeyed": 1, "dead": 0, "noise": 0})
        name = next(item for item, kind in truth.items() if kind == "miskeyed")
        report = {row["item"]: row for row in ia.analyse(rows, items)}
        self.assertLess(report[name]["discrimination"], 0)

    def test_every_planted_item_is_labelled_and_every_label_is_planted(self) -> None:
        rng = random.Random(2)
        _rows, items, truth = dr.one_dataset(rng, 40, 5, {"miskeyed": 2, "dead": 1, "noise": 3})
        self.assertEqual(sorted(truth), sorted(items))
        counts = {kind: sum(1 for k in truth.values() if k == kind) for kind in truth.values()}
        self.assertEqual(counts["healthy"], 5)
        self.assertEqual(counts["miskeyed"], 2)
        self.assertEqual(counts["noise"], 3)


class RateTests(unittest.TestCase):
    def test_a_miskeyed_item_is_found_almost_always_at_a_comfortable_size(self) -> None:
        # The claim the product is sold on. If this ever drops, the headline
        # claim drops with it.
        got = dr.characterise(100, 15, {"miskeyed": 3, "dead": 0, "noise": 0}, 40, 7)
        self.assertGreater(got["detection"]["miskeyed"]["rate"], 0.90)

    def test_false_alarms_are_reported_beside_every_detection_rate(self) -> None:
        # Detection alone is not a result: a tool that flags everything detects
        # everything. The structure of the output has to make that impossible
        # to quote in isolation.
        got = dr.characterise(50, 10, {"miskeyed": 2, "dead": 2, "noise": 2}, 30, 3)
        self.assertIn("detection", got)
        self.assertIn("false_alarm", got)
        self.assertIsNotNone(got["false_alarm"]["rate"])

    def test_false_alarms_fall_as_respondents_are_added(self) -> None:
        # The honest caveat the report must carry: at twenty respondents a
        # healthy item is flagged often enough to matter.
        small = dr.characterise(20, 20, {"miskeyed": 1, "dead": 1, "noise": 1}, 60, 11)
        large = dr.characterise(200, 20, {"miskeyed": 1, "dead": 1, "noise": 1}, 60, 11)
        self.assertGreater(small["false_alarm"]["rate"], large["false_alarm"]["rate"])

    def test_effective_length_is_understated_rather_than_overstated_when_small(self) -> None:
        # Which way the error runs decides what it costs the buyer. Understating
        # loses them items they could have kept; overstating would leave dead
        # items in the test, which is the worse failure and must not be the one
        # we make.
        got = dr.characterise(20, 20, {"miskeyed": 1, "dead": 1, "noise": 1}, 60, 13)
        self.assertLess(got["effective_length"]["bias"], 0)

    def test_an_interval_is_given_rather_than_a_bare_rate(self) -> None:
        got = dr.characterise(50, 10, {"miskeyed": 2, "dead": 0, "noise": 0}, 30, 5)
        low, high = got["detection"]["miskeyed"]["interval_95"]
        self.assertLessEqual(low, got["detection"]["miskeyed"]["rate"])
        self.assertGreaterEqual(high, got["detection"]["miskeyed"]["rate"])


class RefusalTests(unittest.TestCase):
    """Rates this module will not print."""

    def run_main(self, argv: list[str]) -> str:
        saved = sys.argv
        sys.argv = ["detection_rate.py"] + argv
        try:
            with self.assertRaises(SystemExit) as caught:
                dr.main()
            return str(caught.exception)
        finally:
            sys.argv = saved

    def test_too_few_replications_is_refused_rather_than_rounded(self) -> None:
        message = self.run_main(["--replications", "5"])
        self.assertIn("too few", message)

    def test_planting_nothing_is_refused(self) -> None:
        message = self.run_main(["--miskeyed", "0", "--dead", "0", "--noise", "0"])
        self.assertIn("nothing was planted", message)

    def test_too_few_healthy_items_is_refused(self) -> None:
        # Discrimination is computed against the other items, so a rate from two
        # of them would be measuring the arithmetic, not the tool.
        message = self.run_main(["--healthy", "2"])
        self.assertIn("3 healthy items", message)


class HonestyTests(unittest.TestCase):
    def test_the_generating_model_and_its_limit_travel_with_the_numbers(self) -> None:
        # These rates hold for data of one shape. Separating that sentence from
        # the numbers is how an upper bound gets quoted as a guarantee.
        import io
        import json
        from contextlib import redirect_stdout

        saved = sys.argv
        sys.argv = ["detection_rate.py", "--replications", "30", "--respondents", "50",
                    "--healthy", "6", "--miskeyed", "1", "--dead", "1", "--noise", "1"]
        try:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                dr.main()
        finally:
            sys.argv = saved
        report = json.loads(buffer.getvalue())
        self.assertIn("logistic", report["generating_model"])
        self.assertIn("upper bound", report["limit"])
        self.assertIn("not tuned here", report["thresholds_used"]["note"])

    def test_the_thresholds_are_the_shipped_ones_not_a_tuned_copy(self) -> None:
        # Tuning the flag thresholds here and reporting the resulting rates
        # would describe a tool nobody is sold.
        import item_analysis as ia
        self.assertEqual((ia.FLOOR, ia.CEILING, ia.WEAK), (0.05, 0.95, 0.20))


if __name__ == "__main__":
    unittest.main()
