"""A 2PL is only worth reporting if it can recover parameters it was not told.

Everything in `scripts/irt.py` estimates something unobservable, so almost none
of it can be checked against a known answer on real data. The exception is
simulation: generate responses from item parameters chosen here, fit them back,
and see what returns. Those tests are first in this file because they are the
only ones that could catch a fit that is confidently wrong, and the numbers they
pin are the ones quoted in the module's own account of its bias.

The rest record what the estimator does at the sample sizes this project
actually has, including the things it cannot do. A test that fails when 91
models and 20 models stop being unanswerable is a test worth having.
"""

from __future__ import annotations

import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import irt  # noqa: E402

PUBLIC = ROOT / "experiments" / "PUBLIC-AUDIT-2026-09"


def known_instrument(items: int, rng: random.Random) -> tuple[list[str], dict, dict]:
    names = ["q%d" % k for k in range(items)]
    return (names,
            {name: round(rng.uniform(0.6, 2.0), 3) for name in names},
            {name: round(rng.uniform(-2.0, 2.0), 3) for name in names})


def recover(n_respondents: int, n_items: int, seed: int) -> dict:
    """Fit a 2PL to data from parameters we chose, and measure what came back."""
    rng = random.Random(seed)
    names, true_a, true_b = known_instrument(n_items, rng)
    abilities = [rng.gauss(0.0, 1.0) for _ in range(n_respondents)]
    rows = irt.simulate(abilities, true_a, true_b, names, rng)
    fit = irt.fit_2pl(rows, names)
    common = fit.items
    # Two fits of the same items are identified only up to a linear
    # transformation, and the truth is a fit like any other, so this comparison
    # needs linking exactly as the real one does.
    slope, intercept = irt.link_mean_sigma(true_b, fit.difficulty, common)
    linked_b = {i: slope * fit.difficulty[i] + intercept for i in common}
    linked_a = {i: fit.discrimination[i] / slope for i in common}
    return {
        "fit": fit,
        "items_recovered": len(common),
        "difficulty_correlation": irt.correlation([true_b[i] for i in common],
                                                  [linked_b[i] for i in common]),
        "discrimination_correlation": irt.correlation([true_a[i] for i in common],
                                                      [linked_a[i] for i in common]),
        "difficulty_rmse": math.sqrt(sum((true_b[i] - linked_b[i]) ** 2
                                         for i in common) / len(common)),
        "discrimination_ratio": sum(linked_a[i] / true_a[i] for i in common) / len(common),
    }


class RecoveryTests(unittest.TestCase):
    """The only tests here with a right answer to be compared against."""

    def test_it_recovers_difficulties_it_was_never_told_at_a_comfortable_size(self) -> None:
        got = recover(500, 30, seed=7)
        self.assertTrue(got["fit"].converged)
        self.assertGreater(got["difficulty_correlation"], 0.97)
        self.assertLess(got["difficulty_rmse"], 0.25)

    def test_it_recovers_discriminations_less_well_than_difficulties(self) -> None:
        # Recorded because it is the estimator's character, not an accident:
        # difficulty is a location and is easy, discrimination is a slope and
        # needs respondents spread either side of the item to be seen at all.
        got = recover(500, 30, seed=7)
        self.assertGreater(got["discrimination_correlation"], 0.85)
        self.assertLess(got["discrimination_correlation"], got["difficulty_correlation"])

    def test_more_respondents_does_not_remove_the_discrimination_bias(self) -> None:
        """The incidental-parameters problem, visible rather than asserted.

        A consistent estimator would have this bias shrink towards 1 as the
        sample grows. Joint maximum likelihood is not consistent and it does
        not. If this test ever starts failing because the ratio fell, the
        estimator changed and the module's stated bias is out of date.
        """
        small = recover(500, 30, seed=7)["discrimination_ratio"]
        large = recover(2000, 30, seed=7)["discrimination_ratio"]
        self.assertGreater(small, 1.03)
        self.assertGreater(large, 1.03)
        self.assertAlmostEqual(small, large, delta=0.10)

    def test_at_ninety_one_respondents_difficulties_survive_and_discriminations_inflate(self) -> None:
        # The shape of the real full-sample fit: 91 respondents, 111 items.
        got = recover(91, 111, seed=11)
        self.assertGreater(got["difficulty_correlation"], 0.90)
        self.assertGreater(got["discrimination_ratio"], 1.05)

    def test_at_twenty_respondents_the_fit_stops_being_a_measurement(self) -> None:
        """The finding this whole module exists to establish, stated as a test.

        Twenty respondents on a hundred-odd items does not fail loudly. It
        converges, returns numbers and reports a log-likelihood. What it does
        not do is recover the parameters: difficulties come back at a
        correlation under 0.85 with an error near a whole logit, and
        discriminations come back multiples too large.
        """
        got = recover(20, 111, seed=11)
        self.assertTrue(got["fit"].converged)  # it converges, which is the trap
        self.assertLess(got["difficulty_correlation"], 0.85)
        self.assertGreater(got["difficulty_rmse"], 0.5)
        self.assertGreater(got["discrimination_ratio"], 2.0)


class BoundaryTests(unittest.TestCase):
    """Perfect scores have no maximum likelihood estimate, so they are removed."""

    def test_a_respondent_who_answers_everything_correctly_is_dropped_and_counted(self) -> None:
        items = ["A", "B", "C", "D"]
        rows = [dict(zip(items, pattern)) for pattern in
                [[1, 1, 1, 1], [1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 1, 0], [0, 1, 0, 1]]]
        kept, kept_items, report = irt.screen(rows, items)
        self.assertEqual(report["respondents_dropped_perfect_or_zero"], 1)
        self.assertEqual(len(kept), 4)
        self.assertEqual(kept_items, items)

    def test_an_item_nobody_fails_is_dropped_and_named(self) -> None:
        items = ["A", "B", "C"]
        rows = [dict(zip(items, pattern)) for pattern in
                [[1, 1, 0], [1, 0, 1], [1, 1, 1], [1, 0, 0]]]
        _kept, kept_items, report = irt.screen(rows, items)
        self.assertEqual(report["items_dropped"], ["A"])
        self.assertNotIn("A", kept_items)

    def test_dropping_an_item_can_make_a_respondent_perfect_and_the_screen_repeats(self) -> None:
        # B is constant. Once it goes, the second respondent has nothing but
        # ones left, and a screen that ran once would have kept them.
        items = ["A", "B", "C"]
        rows = [dict(zip(items, pattern)) for pattern in
                [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 1]]]
        kept, kept_items, report = irt.screen(rows, items)
        self.assertEqual(kept_items, ["A", "C"])
        self.assertEqual(report["respondents_dropped_perfect_or_zero"], 1)
        self.assertEqual(len(kept), 3)

    def test_a_fit_with_nothing_left_to_fit_raises_rather_than_returning_numbers(self) -> None:
        items = ["A", "B"]
        rows = [dict(zip(items, pattern)) for pattern in [[1, 1], [1, 1], [1, 1]]]
        with self.assertRaises(ValueError):
            irt.fit_2pl(rows, items)

    def test_convergence_is_reported_and_not_assumed(self) -> None:
        rng = random.Random(3)
        names, true_a, true_b = known_instrument(20, rng)
        rows = irt.simulate([rng.gauss(0, 1) for _ in range(200)], true_a, true_b, names, rng)
        stopped_early = irt.fit_2pl(rows, names, max_iterations=2)
        self.assertFalse(stopped_early.converged)
        self.assertGreater(stopped_early.largest_change, 1e-4)
        self.assertTrue(irt.fit_2pl(rows, names).converged)


class ScaleTests(unittest.TestCase):
    """A 2PL has no absolute scale, and forgetting that produces a wrong answer."""

    def test_the_fit_is_identified_by_standardising_the_abilities(self) -> None:
        rng = random.Random(5)
        names, true_a, true_b = known_instrument(25, rng)
        rows = irt.simulate([rng.gauss(0, 1) for _ in range(300)], true_a, true_b, names, rng)
        fit = irt.fit_2pl(rows, names)
        self.assertAlmostEqual(irt._mean(fit.ability), 0.0, places=6)
        self.assertAlmostEqual(irt._sd(fit.ability), 1.0, places=4)

    def test_linking_undoes_a_change_of_scale_exactly(self) -> None:
        reference = {"a": -1.0, "b": 0.0, "c": 1.0, "d": 2.0}
        shifted = {name: 3.0 * value + 7.0 for name, value in reference.items()}
        slope, intercept = irt.link_mean_sigma(reference, shifted, list(reference))
        for name in reference:
            self.assertAlmostEqual(slope * shifted[name] + intercept, reference[name], places=9)

    def test_linking_cannot_see_a_uniform_shift_and_the_module_says_so(self) -> None:
        # Named as a test because it bounds what the invariance result can mean:
        # every item becoming a logit harder for strong respondents is invisible
        # to mean-sigma linking, by construction.
        reference = {"a": -1.0, "b": 0.0, "c": 1.0}
        moved = {name: value + 1.0 for name, value in reference.items()}
        slope, intercept = irt.link_mean_sigma(reference, moved, list(reference))
        linked = {name: slope * moved[name] + intercept for name in reference}
        self.assertEqual(round(irt.correlation(list(reference.values()),
                                               list(linked.values())), 6), 1.0)


class InformationTests(unittest.TestCase):
    def test_an_item_carries_most_information_at_its_own_difficulty(self) -> None:
        fit = irt.Fit(items=["A"], discrimination={"A": 1.5}, difficulty={"A": 0.5},
                      se_discrimination={"A": None}, se_difficulty={"A": None},
                      ability=[0.0], respondents=1, converged=True, iterations=1,
                      largest_change=0.0, loglikelihood=0.0)
        peak = fit.information(0.5, "A")
        self.assertGreater(peak, fit.information(-0.5, "A"))
        self.assertGreater(peak, fit.information(1.5, "A"))
        self.assertAlmostEqual(peak, 1.5 ** 2 * 0.25, places=9)

    def test_effective_items_falls_when_one_item_carries_everything(self) -> None:
        even = irt.Fit(items=["A", "B", "C", "D"],
                       discrimination={k: 1.0 for k in "ABCD"},
                       difficulty={k: 0.0 for k in "ABCD"},
                       se_discrimination={}, se_difficulty={}, ability=[0.0],
                       respondents=1, converged=True, iterations=1,
                       largest_change=0.0, loglikelihood=0.0)
        self.assertAlmostEqual(even.effective_items_at(0.0), 4.0, places=6)
        lopsided = irt.Fit(items=["A", "B", "C", "D"],
                           discrimination={"A": 2.0, "B": 0.1, "C": 0.1, "D": 0.1},
                           difficulty={k: 0.0 for k in "ABCD"},
                           se_discrimination={}, se_difficulty={}, ability=[0.0],
                           respondents=1, converged=True, iterations=1,
                           largest_change=0.0, loglikelihood=0.0)
        self.assertLess(lopsided.effective_items_at(0.0), 1.2)


class DriftTests(unittest.TestCase):
    """The alternative the invariance test is supposed to be able to see."""

    def test_injected_drift_really_does_change_the_data(self) -> None:
        rng = random.Random(13)
        names, true_a, true_b = known_instrument(40, rng)
        abilities = [rng.gauss(0, 1) for _ in range(400)]
        drifting = set(names[:10])
        plain = irt.simulate(abilities, true_a, true_b, names, random.Random(1))
        drifted = irt.simulate_with_drift(abilities, true_a, true_b, names,
                                          random.Random(1), drifting=drifting,
                                          shift=2.0, above=0.0)
        able = [i for i, theta in enumerate(abilities) if theta > 0]
        for item in list(drifting)[:3]:
            before = sum(plain[i][item] for i in able)
            after = sum(drifted[i][item] for i in able)
            self.assertLess(after, before)  # harder means fewer correct
        for item in names[10:13]:
            self.assertEqual(sum(plain[i][item] for i in able),
                             sum(drifted[i][item] for i in able))


class PublicDataTests(unittest.TestCase):
    """What the estimator does on the data the published claim rests on.

    These record real numbers and will need updating if the estimator changes.
    That is the point: the account given in the report should not be able to
    drift away from the code without something failing.
    """

    @classmethod
    def setUpClass(cls) -> None:
        table = PUBLIC / "helm-lite-mmlu-computer_security.csv"
        restricted = PUBLIC / "helm-lite-mmlu-computer_security-top20.csv"
        if not table.is_file() or not restricted.is_file():
            raise unittest.SkipTest("the public audit CSVs are not present")
        rows, items = irt.from_table(table)
        rows_r, items_r = irt.from_table(restricted)
        cls.full = irt.fit_2pl(rows, items)
        cls.restricted = irt.fit_2pl(rows_r, items_r)

    def test_the_full_sample_fit_converges_and_pins_its_difficulties_down(self) -> None:
        self.assertTrue(self.full.converged)
        self.assertEqual(self.full.respondents, 91)
        self.assertLess(irt.precision(self.full)["median_se_difficulty"], 0.5)

    def test_the_restricted_fit_converges_and_measures_nothing(self) -> None:
        # It converges. It reports a log-likelihood. Its median item difficulty
        # is uncertain by more than a logit on a scale six logits wide, which is
        # the whole reason the invariance question comes back unanswerable.
        self.assertTrue(self.restricted.converged)
        self.assertEqual(self.restricted.respondents, 20)
        self.assertGreater(irt.precision(self.restricted)["median_se_difficulty"], 1.0)
        self.assertFalse(irt.precision(self.restricted)["usable_for_comparing_two_fits"])

    def test_restriction_removes_most_items_from_the_question_entirely(self) -> None:
        report = irt.invariance(self.full, self.restricted)
        self.assertGreater(report["items_lost_to_restriction"], 60)
        self.assertLess(report["items_comparable"], 45)

    def test_the_invariance_test_reports_itself_unanswerable(self) -> None:
        report = irt.invariance(self.full, self.restricted)
        self.assertFalse(report["answerable"])
        self.assertIn("noise", report["verdict"])

    def test_the_test_carries_far_less_information_at_the_top_than_at_the_middle(self) -> None:
        """The claim that survives, and it needs only the one well-estimated fit.

        This is the restriction-of-range objection answered rather than dodged:
        the item parameters come from all 91 models at once, and the falling
        information is read off the fitted curve at a higher ability. No second
        sample is involved, so no restriction can be blamed for it.
        """
        ordered = sorted(self.full.ability)
        middle = irt._median(ordered)
        top_twenty = irt._median(ordered[-20:])
        self.assertGreater(self.full.test_information(middle),
                           3 * self.full.test_information(top_twenty))

    def test_the_information_is_spread_thinly_rather_than_held_by_a_few_items(self) -> None:
        # Worth pinning because it corrects a tempting reading of the classical
        # result. "Four items carrying" at the top 20 is a count of items whose
        # correlation with the rest clears a threshold; it does not mean four
        # items hold the information. Twenty-odd items each hold a little.
        top_twenty = irt._median(sorted(self.full.ability)[-20:])
        self.assertGreater(self.full.effective_items_at(top_twenty), 10)


class OwnQuizTests(unittest.TestCase):
    """Most of this project's own quiz cannot be fitted at all, which is the finding."""

    @classmethod
    def setUpClass(cls) -> None:
        folder = ROOT / "experiments" / "PROP-EXP-MEM-007" / "results" / "quiz"
        if not folder.is_dir():
            raise unittest.SkipTest("the quiz results are not present")
        from item_analysis import responses
        rows, _key, rendered = responses([folder])
        items = [item["id"] for item in rendered if item["kind"] == "fact"]
        cls.screened = irt.screen(rows, items)

    def test_most_of_the_thirty_two_fact_items_have_no_parameters_to_estimate(self) -> None:
        _rows, items, report = self.screened
        self.assertEqual(report["items_in"], 32)
        self.assertGreater(report["items_dropped_constant"], 15)
        self.assertLess(len(items), 16)

    def test_readers_with_perfect_scores_are_dropped_rather_than_bounded(self) -> None:
        _rows, _items, report = self.screened
        self.assertGreater(report["respondents_dropped_perfect_or_zero"], 0)
        self.assertLess(report["respondents_kept"], report["respondents_in"])

    def test_what_remains_is_a_different_and_much_shorter_instrument(self) -> None:
        # Stated as a test so that nobody fits the survivors and calls the
        # result "the quiz". It is thirteen-odd items with the easy ones gone,
        # which is a harder instrument than the one anybody sat.
        rows, items, _report = self.screened
        fit = irt.fit_2pl(rows, items, do_screen=False)
        self.assertTrue(fit.converged)
        self.assertLess(len(fit.items), 16)
        self.assertLess(irt._median([fit.difficulty[i] for i in fit.items]), 0.0)


if __name__ == "__main__":
    unittest.main()
