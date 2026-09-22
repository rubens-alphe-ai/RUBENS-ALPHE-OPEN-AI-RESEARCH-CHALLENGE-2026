"""How many things the instrument measures, and what reliability means given that."""

from __future__ import annotations

import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dimensionality as dm  # noqa: E402
import item_analysis as ia  # noqa: E402

QUIZ = ROOT / "experiments" / "PROP-EXP-MEM-007" / "results" / "quiz"


def rows_from(columns: dict[str, list[float]]) -> list[dict]:
    names = list(columns)
    return [dict(zip(names, values)) for values in zip(*(columns[name] for name in names))]


def reproduce(loadings: list[list[float]]) -> list[list[float]]:
    """The correlation matrix a loading matrix implies, ones on the diagonal."""
    n = len(loadings)
    matrix = [[sum(a * b for a, b in zip(loadings[i], loadings[j])) for j in range(n)]
              for i in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
    return matrix


def standardised_alpha(corr: list[list[float]]) -> float:
    """Alpha computed from a correlation matrix, for comparing against omega."""
    k = len(corr)
    return (k / (k - 1)) * (1.0 - k / sum(sum(row) for row in corr))


class JacobiTests(unittest.TestCase):
    """The one piece of numerical machinery here that nothing else can check."""

    def test_it_recovers_eigenvalues_worked_out_by_hand(self) -> None:
        # [[2, 1], [1, 2]] has eigenvalues 3 and 1, on (1, 1) and (1, -1).
        values, vectors = dm.jacobi_eigen([[2.0, 1.0], [1.0, 2.0]])
        self.assertAlmostEqual(values[0], 3.0, places=10)
        self.assertAlmostEqual(values[1], 1.0, places=10)
        self.assertAlmostEqual(abs(vectors[0][0]), abs(vectors[1][0]), places=10)

    def test_a_block_matrix_with_a_known_spectrum_comes_back_sorted(self) -> None:
        # Block diag of [[4, 1], [1, 4]] (5 and 3) and [2]: 5, 3, 2.
        values, _ = dm.jacobi_eigen([[4.0, 1.0, 0.0], [1.0, 4.0, 0.0], [0.0, 0.0, 2.0]],
                                    want_vectors=False)
        for got, want in zip(values, [5.0, 3.0, 2.0]):
            self.assertAlmostEqual(got, want, places=10)

    def test_the_eigenvectors_rebuild_the_matrix_they_came_from(self) -> None:
        source = [[1.0, 0.4, 0.2], [0.4, 1.0, 0.6], [0.2, 0.6, 1.0]]
        values, vectors = dm.jacobi_eigen(source)
        for i in range(3):
            for j in range(3):
                rebuilt = sum(vectors[i][f] * values[f] * vectors[j][f] for f in range(3))
                self.assertAlmostEqual(rebuilt, source[i][j], places=9)

    def test_a_singular_matrix_gives_a_zero_eigenvalue_rather_than_failing(self) -> None:
        # Two identical rows: rank 2 of 3, so one eigenvalue must be exactly zero.
        # This is the normal case for a benchmark with more items than models.
        values, _ = dm.jacobi_eigen([[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                                    want_vectors=False)
        self.assertAlmostEqual(values[-1], 0.0, places=10)

    def test_the_trace_is_preserved_because_a_rotation_cannot_change_it(self) -> None:
        source = [[1.0, 0.3, -0.5, 0.1], [0.3, 1.0, 0.2, -0.4],
                  [-0.5, 0.2, 1.0, 0.7], [0.1, -0.4, 0.7, 1.0]]
        values, _ = dm.jacobi_eigen(source, want_vectors=False)
        self.assertAlmostEqual(sum(values), 4.0, places=9)


class ConstantItemTests(unittest.TestCase):
    """An undefined correlation is not a zero, and must not be written as one."""

    def test_an_item_nobody_varies_on_is_named_in_the_report_not_silently_used(self) -> None:
        columns = {"A": [1.0, 0.0, 1.0, 0.0], "B": [1.0, 1.0, 1.0, 1.0],
                   "C": [0.0, 1.0, 0.0, 1.0]}
        kept, dropped = dm.varying(columns, ["A", "B", "C"])
        self.assertEqual(kept, ["A", "C"])
        self.assertEqual(dropped, ["B"])

    def test_the_correlation_matrix_refuses_a_constant_rather_than_filling_a_zero(self) -> None:
        columns = {"A": [1.0, 0.0, 1.0], "B": [1.0, 1.0, 1.0]}
        with self.assertRaises(ValueError) as caught:
            dm.correlation_matrix(columns, ["A", "B"])
        self.assertIn("does not vary", str(caught.exception))

    def test_identical_and_opposite_items_correlate_one_and_minus_one(self) -> None:
        columns = {"A": [1.0, 0.0, 1.0, 0.0], "B": [1.0, 0.0, 1.0, 0.0],
                   "C": [0.0, 1.0, 0.0, 1.0]}
        matrix = dm.correlation_matrix(columns, ["A", "B", "C"])
        self.assertAlmostEqual(matrix[0][1], 1.0, places=10)
        self.assertAlmostEqual(matrix[0][2], -1.0, places=10)


class OmegaTests(unittest.TestCase):
    """Omega beside alpha, and the gap between them read as a measurement."""

    def test_omega_equals_alpha_when_every_item_loads_equally(self) -> None:
        # Tau-equivalence is exactly the condition under which alpha is not a
        # lower bound but the answer. Where it holds, omega must agree, or the
        # implementation is measuring something else.
        loadings = [[0.6] for _ in range(6)]
        corr = reproduce(loadings)
        self.assertAlmostEqual(dm.omega(loadings, corr), standardised_alpha(corr), places=9)

    def test_omega_is_larger_than_alpha_when_the_loadings_are_not_equal(self) -> None:
        # Unequal loadings are the violation alpha cannot survive, and the
        # direction of its error is downwards.
        loadings = [[0.9], [0.85], [0.3], [0.25]]
        corr = reproduce(loadings)
        self.assertGreater(dm.omega(loadings, corr), standardised_alpha(corr))

    def test_omega_matches_the_closed_form_for_a_one_factor_model(self) -> None:
        loadings = [[0.8], [0.7], [0.6], [0.5]]
        corr = reproduce(loadings)
        total = sum(row[0] for row in loadings)
        expected = total ** 2 / (total ** 2 + sum(1.0 - row[0] ** 2 for row in loadings))
        self.assertAlmostEqual(dm.omega(loadings, corr), expected, places=9)

    def test_two_uncorrelated_clusters_give_an_omega_no_single_factor_could(self) -> None:
        # Four items on one factor, four on another, the two unrelated. A
        # one-factor omega has to call half the common variance unique; the
        # multi-factor one does not. This is the case alpha was used on.
        loadings = [[0.8, 0.0], [0.8, 0.0], [0.8, 0.0], [0.8, 0.0],
                    [0.0, 0.8], [0.0, 0.8], [0.0, 0.8], [0.0, 0.8]]
        corr = reproduce(loadings)
        many = dm.omega(loadings, corr)
        one = dm.omega([[row[0]] for row in loadings], corr)
        self.assertGreater(many, one)


class PrincipalAxisTests(unittest.TestCase):
    def test_it_recovers_loadings_that_were_planted_in_the_matrix(self) -> None:
        planted = [[0.8], [0.7], [0.6], [0.75]]
        fit = dm.principal_axis(reproduce(planted), 1)
        sign = 1.0 if fit["loadings"][0][0] > 0 else -1.0
        for got, want in zip(fit["loadings"], planted):
            self.assertAlmostEqual(sign * got[0], want[0], places=3)
        self.assertTrue(fit["converged"])

    def test_it_finds_two_groups_in_a_matrix_built_from_two_groups(self) -> None:
        planted = [[0.8, 0.0], [0.75, 0.0], [0.7, 0.0],
                   [0.0, 0.8], [0.0, 0.75], [0.0, 0.7]]
        fit = dm.principal_axis(reproduce(planted), 2)
        rotated = dm.varimax(fit["loadings"])
        first = max(range(2), key=lambda f: abs(rotated[0][f]))
        self.assertLess(abs(rotated[0][1 - first]), 0.2)
        self.assertLess(abs(rotated[5][first]), 0.2)

    def test_a_communality_that_would_exceed_one_is_clamped_and_counted(self) -> None:
        # r12 * r13 / r23 comes to 1.62 here, which is not a communality any
        # item can have. Left unclamped the next iteration diverges.
        corr = [[1.0, 0.9, 0.9], [0.9, 1.0, 0.5], [0.9, 0.5, 1.0]]
        fit = dm.principal_axis(corr, 1)
        self.assertGreater(fit["heywood_clamps"], 0)
        self.assertLessEqual(max(fit["communalities"]), dm.MAX_COMMUNALITY)

    def test_asking_for_more_factors_than_items_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            dm.principal_axis([[1.0, 0.3], [0.3, 1.0]], 3)


class VarimaxTests(unittest.TestCase):
    def test_one_factor_is_returned_untouched_because_there_is_nothing_to_rotate(self) -> None:
        loadings = [[0.8], [0.4], [-0.6]]
        self.assertEqual(dm.varimax(loadings), loadings)

    def test_rotation_does_not_change_any_communality(self) -> None:
        loadings = [[0.6, 0.5], [0.7, -0.3], [0.2, 0.8], [-0.4, 0.4]]
        rotated = dm.varimax(loadings)
        for before, after in zip(loadings, rotated):
            self.assertAlmostEqual(sum(v * v for v in before),
                                   sum(v * v for v in after), places=9)

    def test_it_returns_a_mixed_solution_to_the_simple_structure_it_came_from(self) -> None:
        simple = [[0.9, 0.0], [0.8, 0.0], [0.0, 0.9], [0.0, 0.8]]
        angle = math.radians(35.0)
        mixed = [[x * math.cos(angle) - y * math.sin(angle),
                  x * math.sin(angle) + y * math.cos(angle)] for x, y in simple]
        rotated = dm.varimax(mixed)
        for row in rotated:
            self.assertLess(min(abs(row[0]), abs(row[1])), 0.05)


class PercentileTests(unittest.TestCase):
    def test_the_midpoint_of_two_values_is_interpolated_not_rounded(self) -> None:
        self.assertAlmostEqual(dm.percentile([0.0, 10.0], 50.0), 5.0)

    def test_the_ends_are_the_ends(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0]
        self.assertAlmostEqual(dm.percentile(values, 0.0), 1.0)
        self.assertAlmostEqual(dm.percentile(values, 100.0), 4.0)


class ParallelAnalysisTests(unittest.TestCase):
    """The thing that decides the number of factors, so that nobody's eye does."""

    def noise(self, trials: int, items: int, seed: int) -> dict[str, list[float]]:
        rng = random.Random(seed)
        return {"i%02d" % n: [float(rng.randint(0, 1)) for _ in range(trials)]
                for n in range(items)}

    def test_data_with_no_structure_is_almost_always_given_no_factors(self) -> None:
        # Twenty independent noise datasets rather than one, because a 95th
        # percentile keeps a factor from noise about one time in twenty by
        # construction. Pinning a single lucky seed here would hide the false
        # positive rate rather than state it; at the time of writing exactly one
        # of these twenty is a false positive, which is the rate asked for.
        retained = []
        for seed in range(20):
            columns = self.noise(200, 8, seed=seed)
            items = list(columns)
            observed, _ = dm.jacobi_eigen(dm.correlation_matrix(columns, items),
                                          want_vectors=False)
            got = dm.parallel_analysis(columns, items, replicates=40, seed=1,
                                       observed=observed)
            retained.append(got["factors_retained"])
        self.assertGreaterEqual(retained.count(0), 17, retained)

    def test_data_built_around_one_latent_is_given_one_factor(self) -> None:
        rng = random.Random(7)
        latent = [rng.random() for _ in range(200)]
        columns = {}
        for n in range(8):
            columns["i%d" % n] = [1.0 if value + rng.gauss(0, 0.35) > 0.5 else 0.0
                                  for value in latent]
        items = list(columns)
        observed, _ = dm.jacobi_eigen(dm.correlation_matrix(columns, items), want_vectors=False)
        got = dm.parallel_analysis(columns, items, replicates=40, seed=1, observed=observed)
        self.assertEqual(got["factors_retained"], 1)

    def test_the_seed_is_reported_and_the_same_seed_gives_the_same_answer(self) -> None:
        columns = self.noise(60, 6, seed=3)
        items = list(columns)
        first = dm.parallel_analysis(columns, items, replicates=20, seed=99)
        second = dm.parallel_analysis(columns, items, replicates=20, seed=99)
        self.assertEqual(first["seed"], 99)
        self.assertEqual(first["null_eigenvalues"], second["null_eigenvalues"])

    def test_a_different_seed_is_allowed_to_disagree_and_is_recorded(self) -> None:
        columns = self.noise(60, 6, seed=3)
        items = list(columns)
        other = dm.parallel_analysis(columns, items, replicates=20, seed=100)
        self.assertEqual(other["seed"], 100)

    def test_one_replicate_is_refused_because_a_percentile_of_one_draw_is_not_one(self) -> None:
        columns = self.noise(20, 4, seed=5)
        with self.assertRaises(ValueError):
            dm.parallel_analysis(columns, list(columns), replicates=1)

    def test_the_null_keeps_each_item_at_its_own_difficulty(self) -> None:
        # The null has to be data that could have come from the same test. A
        # Gaussian null would not be, for items at difficulty 0.01.
        columns = {"A": [1.0] * 19 + [0.0], "B": [1.0] * 10 + [0.0] * 10}
        items = ["A", "B"]
        got = dm.parallel_analysis(columns, items, replicates=5, seed=2)
        # Permuted columns keep their sums, so no null eigenvalue can exceed 2.
        self.assertLessEqual(got["null_eigenvalues"][0], 2.0)


class NoiseEndToEndTests(unittest.TestCase):
    def test_pure_noise_is_reported_as_zero_dimensions_with_no_loadings(self) -> None:
        rng = random.Random(21)
        columns = {"i%d" % n: [float(rng.randint(0, 1)) for _ in range(150)] for n in range(6)}
        report = dm.analyse(rows_from(columns), list(columns), replicates=30, seed=4)
        self.assertEqual(report["factors_retained"], 0)
        self.assertNotIn("loadings", report)
        self.assertIsNone(report["reliability"]["omega_total"])
        self.assertTrue(any("no factor" in note
                            for note in report["reliability"]["notes"]))

    def test_a_negative_alpha_is_explained_rather_than_printed_as_a_small_number(self) -> None:
        # Items that disagree with each other drive alpha below zero, where it
        # is no longer a proportion of anything and must not be read as one.
        # A and B are exact opposites; C is unrelated to both. The total score
        # barely moves while the items move a lot, which is what drives alpha
        # below zero.
        columns = {"A": [1.0, 0.0] * 30, "B": [0.0, 1.0] * 30,
                   "C": [1.0, 1.0, 0.0, 0.0] * 15}
        report = dm.analyse(rows_from(columns), list(columns), replicates=20, seed=6)
        self.assertLess(report["reliability"]["alpha"], 0)
        self.assertTrue(any("negative" in note
                            for note in report["reliability"]["notes"]))

    def test_constant_items_are_excluded_from_the_count_and_named(self) -> None:
        columns = {"A": [1.0, 0.0, 1.0, 0.0, 1.0, 0.0], "B": [1.0] * 6,
                   "C": [0.0, 1.0, 0.0, 1.0, 0.0, 1.0], "D": [0.0] * 6}
        report = dm.analyse(rows_from(columns), ["A", "B", "C", "D"], replicates=5, seed=4)
        self.assertEqual(report["items_counted"], 4)
        self.assertEqual(report["items_analysed"], 2)
        self.assertEqual(report["items_dropped_no_variance"], ["B", "D"])

    def test_a_test_where_almost_nothing_varies_says_so_instead_of_factoring(self) -> None:
        columns = {"A": [1.0, 0.0, 1.0, 0.0], "B": [1.0] * 4, "C": [1.0] * 4}
        report = dm.analyse(rows_from(columns), ["A", "B", "C"], replicates=5, seed=4)
        self.assertIsNone(report["factors_retained"])
        self.assertIn("no correlation matrix", report["reading"])

    def test_more_items_than_trials_is_flagged_rather_than_hidden(self) -> None:
        rng = random.Random(33)
        columns = {"i%d" % n: [float(rng.randint(0, 1)) for _ in range(6)] for n in range(10)}
        report = dm.analyse(rows_from(columns), list(columns), replicates=5, seed=4)
        self.assertTrue(report["singular_correlation_matrix"])


class ThinFactorTests(unittest.TestCase):
    """A factor can be real, retained, and still be two respondents."""

    def test_the_minority_side_of_an_item_is_counted_not_its_difficulty(self) -> None:
        self.assertEqual(dm.minority_count([1.0] * 19 + [0.0]), 1)
        self.assertEqual(dm.minority_count([0.0] * 19 + [1.0]), 1)
        self.assertEqual(dm.minority_count([1.0] * 10 + [0.0] * 10), 10)

    def test_a_factor_built_out_of_one_respondent_is_flagged(self) -> None:
        # Two items that only one trial of sixty gets wrong, and the same trial
        # both times. Their correlation is 1.0 and every factor rule on earth
        # keeps them. The report has to say what they are made of.
        shared = {"A": [1.0] * 59 + [0.0], "B": [1.0] * 59 + [0.0]}
        rng = random.Random(4)
        for n in range(6):
            shared["n%d" % n] = [float(rng.randint(0, 1)) for _ in range(60)]
        report = dm.analyse(rows_from(shared), list(shared), replicates=30, seed=8)
        flagged = [group for group in report["factors"] if group["flags"]]
        self.assertTrue(flagged)
        self.assertEqual(flagged[0]["trials_on_the_minority_side_of_its_thinnest_item"], 1)
        self.assertIn("coincidence", flagged[0]["flags"][0])
        self.assertIn(flagged[0]["factor"], report["factors_resting_on_too_few_trials"])

    def test_a_factor_with_plenty_of_disagreement_behind_it_is_not_flagged(self) -> None:
        rng = random.Random(12)
        latent = [rng.random() for _ in range(120)]
        columns = {"i%d" % n: [1.0 if value + rng.gauss(0, 0.3) > 0.5 else 0.0
                               for value in latent] for n in range(6)}
        report = dm.analyse(rows_from(columns), list(columns), replicates=30, seed=8)
        self.assertEqual(report["factors_resting_on_too_few_trials"], [])

    def test_each_factor_reports_the_difficulty_of_its_own_items(self) -> None:
        # Stated so the phi-correlation artifact can be checked from the report
        # rather than taken on the estimator note's word.
        rng = random.Random(15)
        latent = [rng.random() for _ in range(120)]
        columns = {"i%d" % n: [1.0 if value + rng.gauss(0, 0.3) > 0.5 else 0.0
                               for value in latent] for n in range(6)}
        report = dm.analyse(rows_from(columns), list(columns), replicates=30, seed=8)
        group = report["factors"][0]
        low, high = group["difficulty_range"]
        self.assertLessEqual(low, group["mean_difficulty"])
        self.assertLessEqual(group["mean_difficulty"], high)


class RealQuizTests(unittest.TestCase):
    """Whether the method finds what a person found by hand, without being told."""

    @classmethod
    def setUpClass(cls) -> None:
        rows, _key, rendered = ia.responses([QUIZ])
        items = [item["id"] for item in rendered if item["kind"] == "fact"]
        cls.report = dm.analyse(rows, items)

    def test_the_quiz_is_not_one_dimensional(self) -> None:
        self.assertGreater(self.report["factors_retained"], 1)

    def test_the_four_contested_questions_come_back_as_one_factor_unprompted(self) -> None:
        # Nothing here names Q07, Q28, Q29 or Q30. They were grouped by hand in
        # September 2026 from reader disagreement; parallel analysis and a
        # varimax rotation put the same four on the first factor and nothing
        # else on it. That is the check on the earlier finding, and it passes.
        first = {entry["item"] for entry in self.report["factors"][0]["items"]}
        self.assertEqual(first, {"Q07", "Q28", "Q29", "Q30"})

    def test_only_the_contested_factor_has_enough_disagreement_behind_it(self) -> None:
        # Three factors are retained and two of them are a single reader: Q25
        # and Q26 are each failed once in 120 trials, by the same reader, and
        # that one trial is the whole of factor 2. Retaining it is correct and
        # believing it is not. The four-item factor is the only one with real
        # disagreement underneath it.
        self.assertEqual(self.report["factors_resting_on_too_few_trials"], [2, 3])
        self.assertGreater(
            self.report["factors"][0]["trials_on_the_minority_side_of_its_thinnest_item"],
            dm.THIN)

    def test_two_thirds_of_the_quiz_is_dropped_before_any_factor_is_estimated(self) -> None:
        self.assertEqual(self.report["items_counted"], 32)
        self.assertLess(self.report["items_analysed"], 32 // 2)

    def test_omega_is_reported_beside_alpha_and_not_instead_of_it(self) -> None:
        reliability = self.report["reliability"]
        self.assertIsNotNone(reliability["alpha"])
        self.assertIsNotNone(reliability["omega_unidimensional"])
        self.assertIsNotNone(reliability["omega_total"])

    def test_alpha_is_the_same_figure_item_analysis_publishes(self) -> None:
        # The two scripts must not disagree about alpha on the same data, or the
        # comparison with omega is between a number and a different number.
        rows, _key, rendered = ia.responses([QUIZ])
        items = [item["id"] for item in rendered if item["kind"] == "fact"]
        self.assertAlmostEqual(self.report["reliability"]["alpha_all_items_including_constant"],
                               ia.alpha(rows, items), places=12)

    def test_the_estimator_and_its_bias_are_stated_in_the_output(self) -> None:
        # A loading from Pearson correlations on 0/1 data is an approximation,
        # and a report that does not say so is claiming more than it has.
        estimator = self.report["estimator"]
        self.assertIn("Pearson", estimator["correlations"])
        self.assertIn("tetrachoric", estimator["better_and_not_available"])
        self.assertIn("seed", estimator["factor_count"])


if __name__ == "__main__":
    unittest.main()
