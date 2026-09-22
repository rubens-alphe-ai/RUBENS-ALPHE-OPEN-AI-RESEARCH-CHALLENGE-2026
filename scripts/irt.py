#!/usr/bin/env python3
"""Fit a two-parameter logistic model, and test whether its items say the same
thing about strong respondents as they say about everyone.

This exists because of an objection to `scripts/item_analysis.py`, and the
objection is correct on the mechanism. Classical item statistics — difficulty,
discrimination, alpha — are properties of a test *and* of the people who sat
it. Restrict the sample to a narrow band of ability and the variance falls;
correlations fall with it. That is restriction of range, it has been known for a
century, and it means the collapse we published (alpha 0.948 to -0.442 on
`computer_security` when the panel goes from 91 models to the top 20) is
explained by the restriction alone unless something rules that out.

Item response theory is what rules it out, or fails to. A 2PL says the
probability that respondent *i* answers item *j* correctly is

    P(correct) = 1 / (1 + exp(-a_j * (theta_i - b_j)))

with `a_j` the item's discrimination, `b_j` its difficulty and `theta_i` the
respondent's ability. The item parameters are, in principle, *invariant to the
sample*: fit on all 91 models or fit on the top 20 and — after the two fits are
put on a common scale, which is not optional and is done here by mean-sigma
linking — the same item should come back with the same numbers. So:

- If the parameters agree, the classical collapse is restriction of range, and
  the item parameters then say directly how much information the test carries
  *at the ability where the decision is made*. The published claim survives in
  a stronger form.
- If they disagree, the items behave differently for strong respondents than
  for weak ones. That is item bias, and it is a larger finding.

**A third answer is available and is the one to expect at these sizes.** Twenty
respondents is very few for a 2PL. Estimates from twenty respondents are noisy
enough that two fits could disagree completely while the items are perfectly
invariant. So this module does not report the agreement between two fits and
stop. It simulates, from the fitted full-sample parameters, data in which the
items are invariant *by construction*, restricts it the same way, refits, and
reports what agreement looks like when the null is true. An observed
correlation is only evidence if it falls outside that band.

## The estimator, and what is wrong with it

**Joint maximum likelihood.** Abilities and item parameters are estimated
together, by alternating Newton steps: one Fisher-scoring step per item on
`(a, b)`, one Newton step per respondent on `theta`, repeated until nothing
moves. Named plainly because an unnamed estimator is worse than a biased one.

What is wrong with it, stated in advance rather than in a footnote:

- **JML is not consistent.** Each respondent brings a new parameter, so the
  number of parameters grows with the sample and the usual asymptotics do not
  apply. This is the incidental-parameters problem (Neyman and Scott). More
  respondents does not fix it.
- **Discriminations come out too high.** The bias is upward and of order
  `J/(J-1)` for `J` items — about 1% at 111 items, about 3% at 32. The report
  states the factor; it does not apply it, because a crude correction applied
  silently is worse than a stated bias.
- **Standard errors come from the item information matrix with the abilities
  held fixed**, as if they were known rather than estimated. They are therefore
  too small — how much too small is not known here. Every "moves by more than
  its uncertainty" count below is, for that reason, an over-count, and the
  simulated null band is the honest reference rather than the z-test.
- Marginal maximum likelihood — integrating the abilities out against a
  population distribution — is the better estimator and is not this. It needs
  quadrature and an EM loop, and the reason it is not here is effort, not
  judgement.

Standard library only, on purpose. No numpy. A stranger should be able to run
this with a stock Python and no install, because that is the product.

## The things that break a 2PL, and what is done about them

A respondent who answers everything correctly has unbounded ability: the
likelihood rises forever as theta goes to infinity. An item nobody fails has
unbounded difficulty for the same reason. These are dropped — respondents and
items both, iteratively, because dropping an item can make a respondent
perfect — and the counts are reported. Nothing is bounded and called a fit.

Abilities are additionally clamped to +/- 6 logits and discriminations to
[0.05, 4.0] as a guard against a single Newton step wandering off. When a
clamp binds, it is reported. Convergence is reported as a flag and a largest
remaining change, and a number from a fit that did not converge is not a number.

    python scripts/irt.py --table experiments/PUBLIC-AUDIT-2026-09/helm-lite-mmlu-computer_security.csv \
        --restricted experiments/PUBLIC-AUDIT-2026-09/helm-lite-mmlu-computer_security-top20.csv \
        --replications 40
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from item_analysis import from_table  # noqa: E402  (the one CSV reader; not modified)

# Guards, not model assumptions. A 2PL has no opinion about these; a Newton
# step taken on a nearly-flat likelihood does, and it is usually wrong.
ABILITY_LIMIT = 6.0
DIFFICULTY_LIMIT = 6.0
DISCRIMINATION_FLOOR, DISCRIMINATION_CEILING = 0.05, 4.0
STEP_LIMIT = 1.0  # logits per parameter per iteration


def logistic(z: float) -> float:
    """1/(1+e^-z), written so neither tail overflows."""
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else (high if value > high else value)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _sd(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))


def correlation(a: list[float], b: list[float]) -> float | None:
    """Pearson r, or None when one side does not vary — never 0.0 for that."""
    if len(a) < 3 or len(a) != len(b):
        return None
    ma, mb = _mean(a), _mean(b)
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    if den == 0.0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / den


def screen(rows: list[dict], items: list[str]) -> tuple[list[dict], list[str], dict]:
    """Remove the respondents and items whose maximum-likelihood estimates do not exist.

    A respondent with a perfect or an empty score has no finite ability under a
    2PL; an item everyone passes or everyone fails has no finite difficulty.
    Both are removed rather than bounded, because a bounded estimate of an
    infinite quantity is a number the reader will use as if it meant something.

    The loop repeats because the two interact: drop the items everyone passed
    and a respondent who was not perfect before may be perfect now.
    """
    kept_items = list(items)
    kept_rows = [dict(row) for row in rows]
    removed_items: list[str] = []
    removed_rows = 0
    while True:
        if not kept_items or not kept_rows:
            break
        constant = [item for item in kept_items
                    if len({row[item] for row in kept_rows}) < 2]
        if constant:
            removed_items.extend(constant)
            kept_items = [item for item in kept_items if item not in set(constant)]
            continue
        extreme = [row for row in kept_rows
                   if len({row[item] for item in kept_items}) < 2]
        if extreme:
            removed_rows += len(extreme)
            kept = []
            for row in kept_rows:
                if len({row[item] for item in kept_items}) >= 2:
                    kept.append(row)
            kept_rows = kept
            continue
        break
    report = {
        "respondents_in": len(rows),
        "respondents_kept": len(kept_rows),
        "respondents_dropped_perfect_or_zero": removed_rows,
        "items_in": len(items),
        "items_kept": len(kept_items),
        "items_dropped_constant": len(removed_items),
        "items_dropped": sorted(removed_items),
    }
    return kept_rows, kept_items, report


@dataclass
class Fit:
    """What a 2PL fit is, including whether it is one."""

    items: list[str]
    discrimination: dict[str, float]
    difficulty: dict[str, float]
    se_discrimination: dict[str, float | None]
    se_difficulty: dict[str, float | None]
    ability: list[float]
    respondents: int
    converged: bool
    iterations: int
    largest_change: float
    loglikelihood: float
    screening: dict = field(default_factory=dict)
    clamped: list[str] = field(default_factory=list)

    def probability(self, theta: float, item: str) -> float:
        return logistic(self.discrimination[item] * (theta - self.difficulty[item]))

    def information(self, theta: float, item: str) -> float:
        """Fisher information this item carries about an ability of exactly theta.

        a^2 * P * (1-P). It peaks at theta == b and dies away from it, which is
        the whole point: an item can be excellent and still tell you nothing
        about the comparison you are making.
        """
        p = self.probability(theta, item)
        return self.discrimination[item] ** 2 * p * (1.0 - p)

    def test_information(self, theta: float) -> float:
        return sum(self.information(theta, item) for item in self.items)

    def effective_items_at(self, theta: float) -> float:
        """How many items are doing the work at this ability, without a threshold.

        The participation ratio (sum I)^2 / sum I^2. It equals the item count
        when every item contributes equally and falls towards 1 when one item
        carries everything. It is reported instead of a count above a cutoff
        because the cutoff would be arbitrary and would be argued about instead
        of the finding.
        """
        infos = [self.information(theta, item) for item in self.items]
        total = sum(infos)
        square = sum(i * i for i in infos)
        if square <= 0.0:
            return 0.0
        return total * total / square

    def standard_error_of_measurement(self, theta: float) -> float | None:
        info = self.test_information(theta)
        return None if info <= 0.0 else 1.0 / math.sqrt(info)


def _initial(rows: list[dict], items: list[str]) -> tuple[list[float], dict, dict]:
    abilities = []
    for row in rows:
        share = _clamp(sum(row[item] for item in items) / len(items), 0.05, 0.95)
        abilities.append(math.log(share / (1.0 - share)))
    difficulty, discrimination = {}, {}
    for item in items:
        share = _clamp(sum(row[item] for row in rows) / len(rows), 0.05, 0.95)
        difficulty[item] = -math.log(share / (1.0 - share))
        discrimination[item] = 1.0
    return abilities, discrimination, difficulty


def fit_2pl(rows: list[dict], items: list[str], *, max_iterations: int = 400,
            tolerance: float = 1e-4, do_screen: bool = True) -> Fit:
    """Joint maximum likelihood for a 2PL, by alternating Newton steps.

    The scale of a 2PL is not identified: multiply every ability and difficulty
    by a constant and divide every discrimination by it and the likelihood does
    not change. This fixes it by standardising the abilities to mean 0 and
    standard deviation 1 after every cycle, carrying the same transformation
    through the item parameters so the fit itself is untouched. Any comparison
    between two fits must therefore be linked first — see `link_mean_sigma`,
    which exists because forgetting this step produces a confident wrong answer.
    """
    screening: dict = {}
    if do_screen:
        rows, items, screening = screen(rows, items)
    if len(items) < 2 or len(rows) < 3:
        raise ValueError("a 2PL needs at least 2 varying items and 3 usable respondents; "
                         "have %d and %d" % (len(items), len(rows)))

    abilities, discrimination, difficulty = _initial(rows, items)
    responses = [[row[item] for item in items] for row in rows]
    converged, iterations, largest = False, 0, float("inf")

    for iterations in range(1, max_iterations + 1):
        previous = {item: (discrimination[item], difficulty[item]) for item in items}

        # Ability step: one Newton step per respondent. The 2PL ability
        # likelihood is strictly concave, so this needs no line search, only a
        # limit on how far one step may travel.
        for i, answers in enumerate(responses):
            theta = abilities[i]
            gradient = 0.0
            hessian = 0.0
            for j, item in enumerate(items):
                a = discrimination[item]
                p = logistic(a * (theta - difficulty[item]))
                gradient += a * (answers[j] - p)
                hessian -= a * a * p * (1.0 - p)
            if hessian < -1e-12:
                step = _clamp(-gradient / hessian, -STEP_LIMIT, STEP_LIMIT)
                abilities[i] = _clamp(theta + step, -ABILITY_LIMIT, ABILITY_LIMIT)

        # Item step: one Fisher-scoring step per item on (a, b). Expected
        # information rather than the observed Hessian, because the observed
        # one is not negative definite far from the optimum and will happily
        # step uphill.
        for j, item in enumerate(items):
            a, b = discrimination[item], difficulty[item]
            g_a = g_b = i_aa = i_ab = i_bb = 0.0
            for i, theta in enumerate(abilities):
                p = logistic(a * (theta - b))
                w = p * (1.0 - p)
                residual = responses[i][j] - p
                g_a += residual * (theta - b)
                g_b += -a * residual
                i_aa += w * (theta - b) ** 2
                i_ab += -a * w * (theta - b)
                i_bb += a * a * w
            det = i_aa * i_bb - i_ab * i_ab
            if abs(det) > 1e-10:
                step_a = (i_bb * g_a - i_ab * g_b) / det
                step_b = (-i_ab * g_a + i_aa * g_b) / det
                a += _clamp(step_a, -STEP_LIMIT, STEP_LIMIT)
                b += _clamp(step_b, -STEP_LIMIT, STEP_LIMIT)
                discrimination[item] = _clamp(a, DISCRIMINATION_FLOOR, DISCRIMINATION_CEILING)
                difficulty[item] = _clamp(b, -DIFFICULTY_LIMIT, DIFFICULTY_LIMIT)

        # Identification. Abilities to mean 0, sd 1; the item parameters follow
        # so that a*(theta-b) is unchanged for every pair.
        centre, spread = _mean(abilities), _sd(abilities)
        if spread > 1e-8:
            abilities = [(theta - centre) / spread for theta in abilities]
            for item in items:
                discrimination[item] = _clamp(discrimination[item] * spread,
                                              DISCRIMINATION_FLOOR, DISCRIMINATION_CEILING)
                difficulty[item] = _clamp((difficulty[item] - centre) / spread,
                                          -DIFFICULTY_LIMIT, DIFFICULTY_LIMIT)

        largest = max(max(abs(discrimination[item] - previous[item][0]),
                          abs(difficulty[item] - previous[item][1])) for item in items)
        if largest < tolerance:
            converged = True
            break

    loglik = 0.0
    for i, answers in enumerate(responses):
        for j, item in enumerate(items):
            p = _clamp(logistic(discrimination[item] * (abilities[i] - difficulty[item])),
                       1e-12, 1.0 - 1e-12)
            loglik += math.log(p) if answers[j] else math.log(1.0 - p)

    se_a, se_b = _standard_errors(responses, items, abilities, discrimination, difficulty)
    clamped = [item for item in items
               if discrimination[item] in (DISCRIMINATION_FLOOR, DISCRIMINATION_CEILING)
               or abs(difficulty[item]) >= DIFFICULTY_LIMIT]

    return Fit(items=items, discrimination=discrimination, difficulty=difficulty,
               se_discrimination=se_a, se_difficulty=se_b, ability=abilities,
               respondents=len(rows), converged=converged, iterations=iterations,
               largest_change=largest, loglikelihood=loglik, screening=screening,
               clamped=clamped)


def _standard_errors(responses: list[list[int]], items: list[str], abilities: list[float],
                     discrimination: dict, difficulty: dict) -> tuple[dict, dict]:
    """Per-item standard errors from the 2x2 information matrix, abilities held fixed.

    Held fixed is the lie in this function and it is deliberate: propagating the
    ability uncertainty into the item parameters is what marginal maximum
    likelihood does and this is not that. These errors are too small. They are
    reported because an interval that is known to be too narrow is still more
    informative than a point estimate, provided the direction is stated.
    """
    se_a: dict[str, float | None] = {}
    se_b: dict[str, float | None] = {}
    for j, item in enumerate(items):
        a, b = discrimination[item], difficulty[item]
        i_aa = i_ab = i_bb = 0.0
        for theta in abilities:
            p = logistic(a * (theta - b))
            w = p * (1.0 - p)
            i_aa += w * (theta - b) ** 2
            i_ab += -a * w * (theta - b)
            i_bb += a * a * w
        det = i_aa * i_bb - i_ab * i_ab
        if det <= 1e-10:
            se_a[item] = se_b[item] = None
            continue
        var_a, var_b = i_bb / det, i_aa / det
        se_a[item] = math.sqrt(var_a) if var_a > 0 else None
        se_b[item] = math.sqrt(var_b) if var_b > 0 else None
    return se_a, se_b


def simulate(abilities: list[float], discrimination: dict, difficulty: dict,
             items: list[str], rng: random.Random) -> list[dict]:
    """Responses from a 2PL with the parameters given — the only ground truth available.

    Everything else in this file is an estimate of something unobserved. This
    function is what makes the estimates checkable: generate from parameters
    that are known because they were chosen, and see what comes back.
    """
    rows = []
    for theta in abilities:
        row = {}
        for item in items:
            p = logistic(discrimination[item] * (theta - difficulty[item]))
            row[item] = 1 if rng.random() < p else 0
        rows.append(row)
    return rows


def link_mean_sigma(reference: dict, other: dict, items: list[str]) -> tuple[float, float]:
    """The (slope, intercept) putting `other`'s difficulties on `reference`'s scale.

    Two 2PL fits of the same items on different samples are each identified only
    up to a linear transformation of the ability scale, so their difficulties
    cannot be compared as they stand. Mean-sigma linking chooses the
    transformation matching the mean and standard deviation of the common
    items' difficulties:

        b* = A*b + B,   a* = a / A

    This is the standard method and it has a real cost worth naming: it *forces*
    the two difficulty distributions to share a mean and a spread, so it cannot
    detect a uniform shift or stretch, only disagreement about the ordering and
    spacing of items. A test built on it is a test of relative position.
    """
    theirs = [other[item] for item in items]
    ours = [reference[item] for item in items]
    spread_theirs, spread_ours = _sd(theirs), _sd(ours)
    if spread_theirs < 1e-8:
        return 1.0, _mean(ours) - _mean(theirs)
    slope = spread_ours / spread_theirs
    return slope, _mean(ours) - slope * _mean(theirs)


def invariance(full: Fit, restricted: Fit) -> dict:
    """Do the two fits agree about the items, once put on a common scale?

    Reported before any interpretation, and with the number of items the
    question could even be asked about — which is the first casualty of
    restriction, because an item every strong respondent passes has no
    parameters in the restricted fit at all.
    """
    common = [item for item in full.items if item in restricted.discrimination]
    restricted_precision = precision(restricted)
    result: dict = {
        "items_in_full_fit": len(full.items),
        "items_in_restricted_fit": len(restricted.items),
        "items_comparable": len(common),
        "items_lost_to_restriction": len(full.items) - len(common),
        "both_converged": bool(full.converged and restricted.converged),
        # Reported first because it decides whether the rest is readable. An
        # item that lost all its variance under restriction has no parameters
        # in the second fit, so it is not evidence for invariance or against it
        # — it has dropped out of the question entirely.
        "restricted_fit_precision": restricted_precision,
        "answerable": bool(len(common) >= 3
                           and restricted_precision["usable_for_comparing_two_fits"]
                           and full.converged and restricted.converged),
    }
    if len(common) < 3:
        result["verdict"] = ("fewer than three items survive in both samples; "
                             "invariance cannot be tested")
        return result
    if not restricted_precision["usable_for_comparing_two_fits"]:
        result["verdict"] = (
            "the restricted fit does not pin its difficulties down (median standard "
            "error %s logits on a scale about 6 logits wide), so agreement and "
            "disagreement between the two fits are both consistent with noise; "
            "the statistics below are reported but should not be read as an answer"
            % restricted_precision["median_se_difficulty"])

    slope, intercept = link_mean_sigma(full.difficulty, restricted.difficulty, common)
    linked_b = {item: slope * restricted.difficulty[item] + intercept for item in common}
    linked_a = {item: restricted.discrimination[item] / slope for item in common}

    result["linking"] = {"method": "mean-sigma on the common items",
                         "slope": round(slope, 4), "intercept": round(intercept, 4)}
    result["difficulty_correlation"] = correlation([full.difficulty[i] for i in common],
                                                   [linked_b[i] for i in common])
    result["discrimination_correlation"] = correlation([full.discrimination[i] for i in common],
                                                       [linked_a[i] for i in common])
    result["difficulty_rmsd"] = math.sqrt(
        sum((full.difficulty[i] - linked_b[i]) ** 2 for i in common) / len(common))

    # "Moves by more than its uncertainty", with the uncertainty from standard
    # errors that are known to be too small. Over-counts. The simulated null
    # band is the reference to trust; this is here to be compared with it.
    moved_1, moved_2, usable, biggest = 0, 0, 0, []
    for item in common:
        se_full = full.se_difficulty.get(item)
        se_rest = restricted.se_difficulty.get(item)
        if se_full is None or se_rest is None:
            continue
        combined = math.sqrt(se_full ** 2 + (slope * se_rest) ** 2)
        if combined <= 0:
            continue
        usable += 1
        z = (full.difficulty[item] - linked_b[item]) / combined
        biggest.append((abs(z), item, round(full.difficulty[item], 3),
                        round(linked_b[item], 3), round(z, 2)))
        if abs(z) > 1.0:
            moved_1 += 1
        if abs(z) > 1.96:
            moved_2 += 1
    biggest.sort(reverse=True)
    result["difficulty_shift"] = {
        "items_with_both_standard_errors": usable,
        "moved_more_than_1_se": moved_1,
        "moved_more_than_2_se": moved_2,
        "share_moved_more_than_2_se": round(moved_2 / usable, 3) if usable else None,
        "largest": [{"item": item, "difficulty_full": bf, "difficulty_linked": bl, "z": z}
                    for _, item, bf, bl, z in biggest[:5]],
        "caveat": ("standard errors hold the abilities fixed and are too small, "
                   "so these counts are upper bounds"),
    }
    return result


def null_band(full: Fit, restricted_size: int, *, replications: int = 40,
              rng: random.Random | None = None, max_iterations: int = 400) -> dict:
    """What agreement looks like when the items *are* invariant, at these sample sizes.

    This is the control the invariance question cannot be answered without. Data
    are generated from the full-sample fit, so the items are invariant by
    construction; the same restriction is applied (the top `restricted_size`
    respondents by raw score); both fits are redone and linked exactly as the
    real ones were. Whatever agreement comes back is what the procedure produces
    when the answer is yes.

    If the observed agreement sits inside this band, the honest report is that
    the data cannot distinguish invariance from its failure at this size. That
    is a result, and it is a better one than a correlation quoted without it.
    """
    rng = rng or random.Random(20260922)
    correlations_b: list[float] = []
    correlations_a: list[float] = []
    rmsds: list[float] = []
    comparable: list[int] = []
    failures = 0
    for _ in range(replications):
        rows = simulate(full.ability, full.discrimination, full.difficulty, full.items, rng)
        try:
            sim_full = fit_2pl(rows, full.items, max_iterations=max_iterations)
        except ValueError:
            failures += 1
            continue
        ranked = sorted(rows, key=lambda row: -sum(row.values()))
        top = ranked[:restricted_size]
        try:
            sim_rest = fit_2pl(top, full.items, max_iterations=max_iterations)
        except ValueError:
            failures += 1
            continue
        report = invariance(sim_full, sim_rest)
        comparable.append(report["items_comparable"])
        if report.get("difficulty_correlation") is not None:
            correlations_b.append(report["difficulty_correlation"])
        if report.get("discrimination_correlation") is not None:
            correlations_a.append(report["discrimination_correlation"])
        if report.get("difficulty_rmsd") is not None:
            rmsds.append(report["difficulty_rmsd"])
    return {
        "replications": replications,
        "replications_unusable": failures,
        "note": ("data simulated from the full-sample fit, so the items are invariant "
                 "by construction; this is what the test returns when the answer is yes"),
        "items_comparable": _quantiles(list(map(float, comparable))),
        "difficulty_correlation": _quantiles(correlations_b),
        "discrimination_correlation": _quantiles(correlations_a),
        "difficulty_rmsd": _quantiles(rmsds),
    }


def simulate_with_drift(abilities: list[float], discrimination: dict, difficulty: dict,
                        items: list[str], rng: random.Random, *, drifting: set[str],
                        shift: float, above: float = 0.0) -> list[dict]:
    """A 2PL in which named items are harder for able respondents than for weak ones.

    This is item bias written down as a data-generating process: for respondents
    above `above` on the ability scale, the listed items have their difficulty
    moved by `shift`. Nothing about the 2PL allows this, which is the point —
    it is the alternative the invariance test is supposed to be able to see.
    """
    rows = []
    for theta in abilities:
        row = {}
        for item in items:
            b = difficulty[item] + (shift if (item in drifting and theta > above) else 0.0)
            row[item] = 1 if rng.random() < logistic(discrimination[item] * (theta - b)) else 0
        rows.append(row)
    return rows


def drift_sensitivity(full: Fit, restricted_size: int, *, shift: float, share: float = 0.25,
                      replications: int = 40, rng: random.Random | None = None,
                      max_iterations: int = 400) -> dict:
    """How much drift this procedure would have caught, had there been any.

    A null band alone licenses "no evidence of drift" and nothing more. Whether
    that sentence is worth reading depends entirely on what the procedure could
    have detected, so this runs the same machinery against data built to violate
    invariance by a stated amount, and reports where the statistic lands. If a
    large drift produces the same numbers as no drift, the honest conclusion is
    that the test is uninformative and the earlier "no evidence" means nothing.
    """
    rng = rng or random.Random(20260922)
    drifting_count = max(1, int(round(share * len(full.items))))
    correlations: list[float] = []
    for _ in range(replications):
        drifting = set(rng.sample(full.items, drifting_count))
        rows = simulate_with_drift(full.ability, full.discrimination, full.difficulty,
                                   full.items, rng, drifting=drifting, shift=shift)
        ranked = sorted(rows, key=lambda row: -sum(row.values()))
        try:
            sim_full = fit_2pl(rows, full.items, max_iterations=max_iterations)
            sim_rest = fit_2pl(ranked[:restricted_size], full.items,
                               max_iterations=max_iterations)
        except ValueError:
            continue
        report = invariance(sim_full, sim_rest)
        if report.get("difficulty_correlation") is not None:
            correlations.append(report["difficulty_correlation"])
    return {"shift_in_logits": shift, "share_of_items_drifting": share,
            "items_drifting": drifting_count, "replications": replications,
            "applied_to": "respondents above ability 0 (the sample median)",
            "difficulty_correlation": _quantiles(correlations)}


def _quantiles(values: list[float]) -> dict | None:
    if not values:
        return None
    ordered = sorted(values)

    def at(q: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        position = q * (len(ordered) - 1)
        low = int(math.floor(position))
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (position - low) * (ordered[high] - ordered[low])

    return {"n": len(ordered), "min": round(ordered[0], 4), "p05": round(at(0.05), 4),
            "median": round(at(0.5), 4), "p95": round(at(0.95), 4),
            "max": round(ordered[-1], 4), "mean": round(_mean(ordered), 4)}


def information_profile(fit: Fit, *, top: int | None = None) -> dict:
    """Where on the ability scale this test still measures, and with how many items.

    This is the half of the argument that only an IRT fit can make, and the half
    that survives whatever happens to the invariance test. Classical
    discrimination is one number for one population, so restricting the
    population changes it and the change can always be blamed on the
    restriction. Item information is a function of ability estimated *once*, on
    the whole sample, and then read off at whichever ability is of interest. No
    second sample, no restriction, nothing to blame.

    `effective_items` is a participation ratio rather than a count above a
    threshold, and it is worth reading against the classical figure rather than
    as a replacement for it: the classical statistic counts items correlated
    with the rest, this one measures how evenly the information is spread. A
    test can carry almost no information and still spread it evenly over a
    hundred items, and that is not the same picture as four items doing the work.

    One extrapolation warning that applies to the top of the range: where no
    item sits, the 2PL is predicting rather than measuring, and a standard error
    quoted out there is a property of the model, not of the data.
    """
    ordered = sorted(fit.ability)
    points: list[tuple[str, float]] = [
        ("weakest respondent", ordered[0]),
        ("first quartile", _quantile_of(ordered, 0.25)),
        ("median respondent", _quantile_of(ordered, 0.5)),
        ("third quartile", _quantile_of(ordered, 0.75)),
        ("strongest respondent", ordered[-1]),
    ]
    if top and 0 < top <= len(ordered):
        band = ordered[-top:]
        points.append(("weakest of the top %d" % top, band[0]))
        points.append(("median of the top %d" % top, _median(band)))
    out = []
    for label, theta in points:
        info = fit.test_information(theta)
        out.append({"where": label, "ability": round(theta, 3),
                    "test_information": round(info, 3),
                    "standard_error_of_measurement":
                        None if info <= 0 else round(1.0 / math.sqrt(info), 3),
                    "effective_items": round(fit.effective_items_at(theta), 1)})
    return {"items_in_fit": len(fit.items),
            "note": ("information is Fisher information about ability; the standard "
                     "error of measurement is 1/sqrt(information), in logits"),
            "at": out}


def _quantile_of(ordered: list[float], q: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    low = int(math.floor(position))
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def precision(fit: Fit) -> dict:
    """How well the item parameters are pinned down — the gate on every comparison.

    A fit can converge, report a tidy log-likelihood and contain nothing. With
    twenty respondents most items are answered correctly by nineteen of them,
    and an item like that carries almost no information about where its own
    difficulty sits: the likelihood is nearly flat over several logits. The
    median standard error below is the number that decides whether any
    comparison between two fits is worth making, and it is reported before the
    comparison rather than after it.

    The useful part of the difficulty scale is about -3 to +3 logits. A median
    standard error near or above 1 logit means the ordering of items is not
    established, and a comparison of two such orderings measures noise.
    """
    ses = [fit.se_difficulty[item] for item in fit.items
           if fit.se_difficulty[item] is not None]
    median_se = _median(ses) if ses else None
    return {
        "median_se_difficulty": None if median_se is None else round(median_se, 3),
        "items_with_se_difficulty_over_1_logit": sum(1 for s in ses if s > 1.0),
        "items_with_a_standard_error_at_all": len(ses),
        "at_discrimination_ceiling": sum(1 for i in fit.items
                                         if fit.discrimination[i] >= DISCRIMINATION_CEILING - 1e-9),
        "at_discrimination_floor": sum(1 for i in fit.items
                                       if fit.discrimination[i] <= DISCRIMINATION_FLOOR + 1e-9),
        "at_difficulty_limit": sum(1 for i in fit.items
                                   if abs(fit.difficulty[i]) >= DIFFICULTY_LIMIT - 1e-9),
        "reading": ("item difficulties are pinned to about +/-%.2f logits on a scale "
                    "whose useful range is about 6 logits wide" % median_se)
        if median_se is not None else "no item has a usable standard error",
        "usable_for_comparing_two_fits": bool(median_se is not None and median_se < 1.0),
    }


def describe(fit: Fit) -> dict:
    """A fit as JSON, convergence first, because the rest is void without it."""
    j = len(fit.items)
    return {
        "estimator": "joint maximum likelihood, alternating Fisher-scoring steps",
        "known_bias": ("JML is inconsistent (incidental parameters) and its "
                       "discriminations come back too high. Measured against known "
                       "parameters by tests/test_irt.py, the inflation is about 9%% at "
                       "500 respondents x 30 items, about 18%% at 91 x 111, and about "
                       "3x at 20 x 111, far worse than the textbook J/(J-1) = %.3f. "
                       "Nothing is corrected for it. Difficulties are far more robust: "
                       "they recover at r = 0.99, 0.96 and 0.72 in those three cases."
                       % (j / (j - 1) if j > 1 else float("nan"))),
        "converged": fit.converged,
        "iterations": fit.iterations,
        "largest_final_change": round(fit.largest_change, 6),
        "loglikelihood": round(fit.loglikelihood, 3),
        "respondents_fitted": fit.respondents,
        "items_fitted": j,
        "screening": fit.screening,
        "precision": precision(fit),
        "parameters_at_a_clamp": fit.clamped,
        "ability_spread_note": "abilities standardised to mean 0, sd 1 for identification",
        "discrimination": {"median": round(_median(list(fit.discrimination.values())), 3),
                           "min": round(min(fit.discrimination.values()), 3),
                           "max": round(max(fit.discrimination.values()), 3)},
        "difficulty": {"median": round(_median(list(fit.difficulty.values())), 3),
                       "min": round(min(fit.difficulty.values()), 3),
                       "max": round(max(fit.difficulty.values()), 3)},
    }


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        return float("nan")
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def per_item(fit: Fit) -> list[dict]:
    return [{"item": item,
             "discrimination": round(fit.discrimination[item], 3),
             "se_discrimination": None if fit.se_discrimination[item] is None
             else round(fit.se_discrimination[item], 3),
             "difficulty": round(fit.difficulty[item], 3),
             "se_difficulty": None if fit.se_difficulty[item] is None
             else round(fit.se_difficulty[item], 3)}
            for item in fit.items]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--table", type=Path,
                        help="CSV of trial,item,correct — the full sample")
    parser.add_argument("--quiz-results", type=Path, nargs="*", default=[],
                        help="folders of stored reader answers, as item_analysis reads them")
    parser.add_argument("--kind", default="fact", choices=("fact", "absent", "all"))
    parser.add_argument("--restricted", type=Path,
                        help="CSV of the same items on a restricted sample; "
                             "with this, the invariance test is run")
    parser.add_argument("--replications", type=int, default=0,
                        help="simulated replications for the null band; 0 skips it, "
                             "and without it the invariance numbers have no reference")
    parser.add_argument("--drift", type=float, nargs="*", default=[],
                        help="logit shifts to inject into a quarter of the items, to "
                             "show what drift this procedure could have detected")
    parser.add_argument("--drift-share", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--max-iterations", type=int, default=400)
    parser.add_argument("--per-item", action="store_true", help="include every item's parameters")
    args = parser.parse_args()

    if bool(args.table) == bool(args.quiz_results):
        raise SystemExit("give either --table or --quiz-results, not both and not neither")
    if args.table:
        rows, items = from_table(args.table)
        source = str(args.table)
    else:
        from item_analysis import responses  # local: only this branch needs it
        rows, _key, rendered = responses(list(args.quiz_results))
        items = [item["id"] for item in rendered
                 if args.kind == "all" or item["kind"] == args.kind]
        source = ", ".join(str(folder) for folder in args.quiz_results)

    full = fit_2pl(rows, items, max_iterations=args.max_iterations)
    report: dict = {"record_version": "RA-PSI-IRT-V1", "model": "2PL",
                    "source": source, "full_sample": describe(full)}
    if args.per_item:
        report["full_sample_per_item"] = per_item(full)

    if args.restricted:
        rows_r, items_r = from_table(args.restricted)
        restricted = fit_2pl(rows_r, items_r, max_iterations=args.max_iterations)
        report["restricted_source"] = str(args.restricted)
        report["restricted_sample"] = describe(restricted)
        # Reported before anything that interprets it, and before the profile
        # that would be the temptation to interpret it with.
        report["invariance"] = invariance(full, restricted)
        if args.replications > 0:
            report["invariance_null_band"] = null_band(
                full, restricted.respondents, replications=args.replications,
                rng=random.Random(args.seed), max_iterations=args.max_iterations)
        else:
            report["invariance_null_band"] = (
                "not computed; without it the correlations above cannot be read, "
                "because twenty respondents produce low correlations even when the "
                "items are identical")
        if args.drift and args.replications > 0:
            report["drift_this_would_have_caught"] = [
                drift_sensitivity(full, restricted.respondents, shift=shift,
                                  share=args.drift_share, replications=args.replications,
                                  rng=random.Random(args.seed + 1),
                                  max_iterations=args.max_iterations)
                for shift in args.drift]
        if args.per_item:
            report["restricted_per_item"] = per_item(restricted)

    report["information"] = information_profile(
        full, top=restricted.respondents if args.restricted else None)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
