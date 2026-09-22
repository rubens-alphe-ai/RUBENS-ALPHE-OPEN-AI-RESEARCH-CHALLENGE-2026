#!/usr/bin/env python3
"""Ask how many things a test measures, before reporting one number for it.

`scripts/item_analysis.py` reports Cronbach's alpha. Alpha is a lower bound on
reliability **only if the items are essentially tau-equivalent** — one common
factor, and every item loading on it equally. This project published alpha for
its own quiz in the same work that demonstrated the quiz measures two things:
four questions carried three quarters of the disagreement between readers and
correlated with each other an order of magnitude more than with the rest. Using
alpha there was a technical error, committed beside the proof that its
assumption was false.

This script is the repair, and it is deliberately two separate repairs:

**McDonald's omega**, reported beside alpha rather than instead of it. Omega
drops the equal-loadings assumption; it does not by itself drop the
one-dimension assumption, and saying otherwise is the usual way this statistic
is oversold. Two versions are reported. `omega_unidimensional` fits one common
factor, and is coefficient omega as normally quoted. `omega_total` fits however
many factors the data supports and is McDonald's omega-total — the share of the
total score variance that any common factor explains. That one makes no
unidimensionality assumption. The gap between alpha and omega is the size of
the tau-equivalence violation, and is worth more than either figure alone.

**Dimensionality found rather than noticed.** The four contested questions were
located by a person reading answers, choosing a group, and then computing a
correlation over the group he had chosen. That is inspection wearing the
clothes of a method: the correlation could not have come out low. Here the
structure is estimated from the whole item correlation matrix by principal-axis
factoring, and the number of factors is decided by parallel analysis against
random data of the same shape — not by an eigenvalue-above-one rule, which
over-retains, and not by a scree plot, which is an eye again.

Parallel analysis here permutes **each item's own column** rather than drawing
Gaussian noise. That destroys every relationship between items while preserving
each item's exact difficulty, so the null has the same marginals, the same
number of trials and the same number of items as the real data. It matters:
these are 0/1 items with difficulties as extreme as 0.01, and a Gaussian null
would be answering a question about a dataset nobody collected. It matters
twice over when there are more items than trials — 110 MMLU items answered by
91 models — because the correlation matrix is then singular and its eigenvalues
are shaped mostly by that fact. A null of the identical shape is singular in
exactly the same way, and the comparison survives it.

What this refuses to do:

- It will not compute a correlation for an item nobody varies on. Those items
  are dropped by name and counted, because a zero in a correlation matrix that
  means "undefined" propagates into every eigenvalue downstream.
- It will not report a factor count from an eigenvalue threshold.
- It will not let a retained factor pass without saying how many trials it rests
  on. Two items that one respondent of a hundred and twenty failed, and failed
  together, correlate at 0.7 and will be kept by any factor rule ever written.
  The rule is not wrong; the data cannot tell that case from a real dimension,
  and a report that prints the factor without printing the number 1 beside it is
  the same mistake as printing alpha for a scale with two dimensions.
- It will not claim tetrachoric correlations. It uses Pearson on 0/1 data,
  which is a known approximation that **understates** loadings between items of
  unlike difficulty and can manufacture a spurious extra factor grouping items
  by difficulty rather than by content ("difficulty factors"). Tetrachoric
  correlations would be the right estimator and need a bivariate normal
  integral this repository has no dependency to supply.

  python scripts/dimensionality.py --quiz-results experiments/PROP-EXP-MEM-007/results/quiz
  python scripts/dimensionality.py --table experiments/PUBLIC-AUDIT-2026-09/helm-lite-mmlu-econometrics.csv
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import item_analysis as ia  # noqa: E402

# A loading below this is not read as membership. It is the conventional
# reporting cut, chosen before looking at these data, and it decides only which
# items get *printed* under a factor — never how many factors there are.
SALIENT = 0.40

# Communalities are held below 1. A principal-axis iteration that pushes one to
# or past 1 is a Heywood case: the model is claiming an item has no unique
# variance at all, which is impossible and which makes the next iteration
# diverge. Clamping is the standard handling; the count is reported because a
# solution with many of them should not be trusted.
MAX_COMMUNALITY = 0.995

# A factor every one of whose items was answered the minority way by fewer than
# this many trials is not a dimension of the test. It is a handful of
# respondents. Two items each failed once, by the same reader, correlate at
# about 0.7 and will be retained by any factor rule ever written — the rule is
# not wrong, the data simply cannot tell that case from a real one.
THIN = 5


def minority_count(column: list[float]) -> int:
    """How many trials fall on the rarer side of a 0/1 item."""
    right = sum(1 for value in column if value)
    return min(right, len(column) - right)

DEFAULT_SEED = 20260922
DEFAULT_REPLICATES = 100
DEFAULT_PERCENTILE = 95.0


def jacobi_eigen(matrix: list[list[float]], want_vectors: bool = True,
                 max_sweeps: int = 60, tol: float = 1e-12
                 ) -> tuple[list[float], list[list[float]] | None]:
    """Eigenvalues and eigenvectors of a real symmetric matrix, sorted descending.

    The cyclic Jacobi method: repeatedly pick an off-diagonal entry and apply
    the plane rotation that zeroes it, until the off-diagonal mass is gone. It
    is slower than the tridiagonal-plus-QL method every library uses, and it is
    here because it is short enough to read and check, and because it does not
    lose accuracy on the nearly-singular correlation matrices that arise when
    there are more items than trials — which is the normal case for a benchmark.

    `want_vectors=False` skips accumulating the rotation product. Parallel
    analysis needs only eigenvalues and runs this hundreds of times, so the
    saving is the difference between a script that finishes and one that does not.

    Returns eigenvectors as columns: `vectors[i][f]` is the i-th component of
    the f-th eigenvector.
    """
    n = len(matrix)
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)] if want_vectors else None
    for _sweep in range(max_sweeps):
        off = 0.0
        for i in range(n):
            row = a[i]
            for j in range(i + 1, n):
                off += row[j] * row[j]
        if off <= tol:
            break
        for p in range(n - 1):
            ap = a[p]
            for q in range(p + 1, n):
                apq = ap[q]
                if abs(apq) < 1e-15:
                    continue
                aq = a[q]
                theta = (aq[q] - ap[p]) / (2.0 * apq)
                sign = 1.0 if theta >= 0 else -1.0
                t = sign / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                # The rotated entry is zero by construction. Writing the zero
                # rather than computing it keeps the symmetry exact, which is
                # what lets the remaining update touch each off-diagonal once.
                ap[p] -= t * apq
                aq[q] += t * apq
                ap[q] = aq[p] = 0.0
                for k in range(n):
                    if k == p or k == q:
                        continue
                    row = a[k]
                    akp, akq = row[p], row[q]
                    row[p] = ap[k] = c * akp - s * akq
                    row[q] = aq[k] = s * akp + c * akq
                if v is not None:
                    for k in range(n):
                        row = v[k]
                        vkp, vkq = row[p], row[q]
                        row[p] = c * vkp - s * vkq
                        row[q] = s * vkp + c * vkq
    order = sorted(range(n), key=lambda i: -a[i][i])
    values = [a[i][i] for i in order]
    if v is None:
        return values, None
    vectors = [[v[i][j] for j in order] for i in range(n)]
    return values, vectors


def columns_of(rows: list[dict], items: list[str]) -> dict[str, list[float]]:
    return {item: [float(row[item]) for row in rows] for item in items}


def varying(columns: dict[str, list[float]], items: list[str]) -> tuple[list[str], list[str]]:
    """Split items into those that vary and those that do not.

    An item every trial gets right, or every trial gets wrong, has no
    correlation with anything — not a correlation of zero, an undefined one.
    Writing a zero there is the quiet mistake: it is a legal number, it makes
    the matrix look complete, and it changes every eigenvalue after it.
    """
    keep = [item for item in items if ia.variance(columns[item]) > 0]
    return keep, [item for item in items if item not in set(keep)]


def correlation_matrix(columns: dict[str, list[float]], items: list[str]) -> list[list[float]]:
    """Pearson correlations between items, with no undefined entry permitted.

    Pearson on 0/1 responses is the phi coefficient. Its ceiling is below 1
    whenever two items differ in difficulty, so every loading estimated from it
    is biased **towards zero** and unequal difficulties can split one real
    factor into two. Stated here rather than in a footnote because it is the
    single largest approximation in this script.
    """
    centred, norms = {}, {}
    for item in items:
        values = columns[item]
        mean = sum(values) / len(values)
        column = [value - mean for value in values]
        norm = math.sqrt(sum(value * value for value in column))
        if norm == 0.0:
            raise ValueError("item %r does not vary; drop it before building the matrix" % item)
        centred[item], norms[item] = column, norm
    n = len(items)
    matrix = [[1.0] * n for _ in range(n)]
    for i in range(n):
        a, na = centred[items[i]], norms[items[i]]
        for j in range(i + 1, n):
            b, nb = centred[items[j]], norms[items[j]]
            r = sum(x * y for x, y in zip(a, b)) / (na * nb)
            matrix[i][j] = matrix[j][i] = r
    return matrix


def principal_axis(corr: list[list[float]], n_factors: int,
                   max_iterations: int = 250, tol: float = 1e-6) -> dict:
    """Principal-axis factoring: common variance only, communalities iterated.

    Principal components would be simpler and is what most people run when they
    say "factor analysis". It is the wrong model here: components explain the
    items' *total* variance including the part unique to each item, which is
    exactly the part a reliability argument must exclude.

    Communalities start at each item's largest absolute correlation — the usual
    cheap start. The squared multiple correlation is the better one and needs
    the matrix inverse, which does not exist when there are more items than
    trials, which is most benchmarks.
    """
    n = len(corr)
    if n_factors < 1 or n_factors > n:
        raise ValueError("cannot extract %d factors from %d items" % (n_factors, n))
    communality = [max((abs(corr[i][j]) for j in range(n) if j != i), default=0.0)
                   for i in range(n)]
    loadings: list[list[float]] = [[0.0] * n_factors for _ in range(n)]
    heywood = 0
    converged = False
    for _step in range(max_iterations):
        reduced = [row[:] for row in corr]
        for i in range(n):
            reduced[i][i] = communality[i]
        values, vectors = jacobi_eigen(reduced)
        assert vectors is not None
        # Counted per iteration, not accumulated, so the reported number is
        # "items the final solution had to clamp" rather than "clamps performed".
        heywood = 0
        # A reduced correlation matrix is not positive semi-definite in general,
        # so some eigenvalues come out negative. Those factors carry no common
        # variance; taking sqrt of a clamped zero drops them rather than raising.
        scale = [math.sqrt(values[f]) if values[f] > 0 else 0.0 for f in range(n_factors)]
        loadings = [[vectors[i][f] * scale[f] for f in range(n_factors)] for i in range(n)]
        updated = []
        for i in range(n):
            h = sum(load * load for load in loadings[i])
            if h > MAX_COMMUNALITY:
                heywood += 1
                h = MAX_COMMUNALITY
            updated.append(h)
        shift = max(abs(a - b) for a, b in zip(updated, communality))
        communality = updated
        if shift < tol:
            converged = True
            break
    return {"loadings": loadings, "communalities": communality,
            "heywood_clamps": heywood, "converged": converged}


def varimax(loadings: list[list[float]], max_iterations: int = 100,
            tol: float = 1e-9) -> list[list[float]]:
    """Rotate factors so each item loads on as few of them as possible.

    Rotation changes nothing that matters — the reproduced correlations, the
    communalities and omega are all identical before and after. It changes only
    whether a human can read the answer, which is why an unrotated multi-factor
    solution is reported by nobody and believed by nobody.

    Kaiser-normalised, so that items with low communality do not dominate the
    criterion merely by being poorly explained.
    """
    n = len(loadings)
    if n == 0:
        return []
    k = len(loadings[0])
    if k < 2:
        return [row[:] for row in loadings]
    norms = [math.sqrt(sum(load * load for load in row)) for row in loadings]
    rotated = [[load / norm if norm > 1e-12 else 0.0 for load in row]
               for row, norm in zip(loadings, norms)]
    for _step in range(max_iterations):
        moved = 0.0
        for p in range(k - 1):
            for q in range(p + 1, k):
                a = b = c = d = 0.0
                for i in range(n):
                    x, y = rotated[i][p], rotated[i][q]
                    u = x * x - y * y
                    w = 2.0 * x * y
                    a += u
                    b += w
                    c += u * u - w * w
                    d += 2.0 * u * w
                num = d - 2.0 * a * b / n
                den = c - (a * a - b * b) / n
                if abs(num) < 1e-14 and abs(den) < 1e-14:
                    continue
                phi = math.atan2(num, den) / 4.0
                if abs(phi) < tol:
                    continue
                moved = max(moved, abs(phi))
                cos, sin = math.cos(phi), math.sin(phi)
                for i in range(n):
                    x, y = rotated[i][p], rotated[i][q]
                    rotated[i][p] = x * cos + y * sin
                    rotated[i][q] = -x * sin + y * cos
        if moved < tol:
            break
    return [[load * norm for load in row] for row, norm in zip(rotated, norms)]


def percentile(values: list[float], point: float) -> float:
    """Linear-interpolated percentile. Sorting is the caller's business."""
    if not values:
        raise ValueError("no values to take a percentile of")
    if len(values) == 1:
        return values[0]
    position = (point / 100.0) * (len(values) - 1)
    low = int(math.floor(position))
    high = min(low + 1, len(values) - 1)
    weight = position - low
    return values[low] * (1.0 - weight) + values[high] * weight


def parallel_analysis(columns: dict[str, list[float]], items: list[str],
                      replicates: int = DEFAULT_REPLICATES, seed: int = DEFAULT_SEED,
                      point: float = DEFAULT_PERCENTILE,
                      observed: list[float] | None = None) -> dict:
    """How many eigenvalues are larger than chance would have made them.

    Horn's procedure, with a permutation null. Each replicate shuffles every
    item's responses independently across trials: the item keeps its exact
    difficulty, every relationship between items is destroyed, and the shape of
    the dataset is untouched. The number of factors retained is the number of
    leading eigenvalues that beat the chosen percentile of the null, stopping at
    the first that does not — a factor after a failure is not evidence, it is
    the tail of a distribution.

    The seed is recorded in the output. An answer from random data that nobody
    can regenerate is not an answer.
    """
    if replicates < 2:
        raise ValueError("parallel analysis needs at least two replicates")
    rng = random.Random(seed)
    n = len(items)
    draws: list[list[float]] = [[] for _ in range(n)]
    for _trial in range(replicates):
        shuffled = {}
        for item in items:
            column = columns[item][:]
            rng.shuffle(column)
            shuffled[item] = column
        values, _ = jacobi_eigen(correlation_matrix(shuffled, items), want_vectors=False)
        for index, value in enumerate(values):
            draws[index].append(value)
    thresholds = [percentile(sorted(draw), point) for draw in draws]
    retained = 0
    if observed is not None:
        for value, threshold in zip(observed, thresholds):
            if value > threshold:
                retained += 1
            else:
                break
    return {"method": "permutation of each item's own responses across trials",
            "seed": seed, "replicates": replicates, "percentile": point,
            "null_eigenvalues": thresholds, "factors_retained": retained}


def omega(loadings: list[list[float]], corr: list[list[float]]) -> float | None:
    """McDonald's omega-total: the share of scale variance any common factor explains.

    Numerator is the sum of every entry of the reproduced common-variance matrix
    (loadings times their transpose); denominator is the sum of every entry of
    the observed correlation matrix, which is the variance of the standardised
    total score. With one factor this is coefficient omega as usually written,
    `(sum of loadings)^2 / ((sum of loadings)^2 + sum of uniquenesses)`. With
    more than one it is the figure alpha was never entitled to report.

    Using the *observed* denominator rather than the model-implied one is
    deliberate: they agree only when the model fits, and when it does not, the
    observed one is the honest denominator and the smaller number.
    """
    n = len(loadings)
    if n == 0:
        return None
    k = len(loadings[0])
    common = 0.0
    for i in range(n):
        for j in range(n):
            common += sum(loadings[i][f] * loadings[j][f] for f in range(k))
    total = sum(sum(row) for row in corr)
    if total <= 0:
        return None
    return common / total


def analyse(rows: list[dict], items: list[str], max_factors: int = 8,
            replicates: int = DEFAULT_REPLICATES, seed: int = DEFAULT_SEED,
            point: float = DEFAULT_PERCENTILE) -> dict:
    """The whole question: how many dimensions, and what is reliability given that."""
    if len(rows) < 3:
        raise ValueError("only %d trials; a correlation matrix needs more than that" % len(rows))
    columns = columns_of(rows, items)
    kept, dropped = varying(columns, items)
    report = {"record_version": "RA-PSI-DIM-V1", "trials": len(rows),
              "items_counted": len(items), "items_analysed": len(kept),
              "items_dropped_no_variance": dropped}
    if len(kept) < 3:
        report["reading"] = ("%d of %d items vary; there is no correlation matrix to factor"
                             % (len(kept), len(items)))
        report["factors_retained"] = None
        return report
    corr = correlation_matrix(columns, kept)
    # Fewer trials than items means the matrix cannot have full rank. Factor
    # analysis still runs and parallel analysis still compares like with like,
    # but nobody should read a loading from it as if it were estimated well.
    report["singular_correlation_matrix"] = len(rows) <= len(kept)
    observed, _ = jacobi_eigen(corr, want_vectors=False)
    report["observed_eigenvalues"] = observed
    ceiling = min(max_factors, len(kept) - 1, max(1, len(rows) - 1))
    horn = parallel_analysis(columns, kept, replicates, seed, point, observed)
    report["parallel_analysis"] = horn
    retained = horn["factors_retained"]
    report["factors_retained"] = retained
    if retained > ceiling:
        report["factors_retained_capped_at"] = ceiling
        retained = ceiling

    one = principal_axis(corr, 1)
    report["reliability"] = {
        "alpha": ia.alpha(rows, kept),
        "alpha_all_items_including_constant": ia.alpha(rows, items),
        "omega_unidimensional": omega(one["loadings"], corr),
        "omega_total": None,
    }
    report["one_factor_fit"] = {"heywood_clamps": one["heywood_clamps"],
                                "converged": one["converged"]}
    if retained >= 1:
        many = principal_axis(corr, retained)
        rotated = varimax(many["loadings"])
        report["reliability"]["omega_total"] = omega(many["loadings"], corr)
        report["multi_factor_fit"] = {"factors": retained,
                                      "heywood_clamps": many["heywood_clamps"],
                                      "converged": many["converged"],
                                      "rotation": "varimax, Kaiser normalised"
                                      if retained > 1 else "none needed for one factor"}
        report["loadings"] = {item: [round(load, 3) for load in row]
                              for item, row in zip(kept, rotated)}
        report["communalities"] = {item: round(value, 3)
                                   for item, value in zip(kept, many["communalities"])}
        groups = []
        for f in range(retained):
            members = [(item, rotated[i][f]) for i, item in enumerate(kept)
                       if abs(rotated[i][f]) >= SALIENT
                       and abs(rotated[i][f]) == max(abs(load) for load in rotated[i])]
            members.sort(key=lambda pair: -abs(pair[1]))
            # Mean difficulty per factor is printed so that the phi-correlation
            # artifact is checkable from the report rather than only warned
            # about: a factor of uniformly easy items beside a factor of
            # uniformly hard ones is the signature of a difficulty factor, and
            # is not evidence that the test measures two things.
            hardness = [sum(columns[item]) / len(rows) for item, _ in members]
            thinnest = min((minority_count(columns[item]) for item, _ in members),
                           default=0)
            flags = []
            if members and thinnest < THIN:
                flags.append("rests on %d trial%s: the least-varying item on it was "
                             "answered the minority way that few times, so this may "
                             "be a coincidence between respondents rather than a "
                             "dimension" % (thinnest, "" if thinnest == 1 else "s"))
            groups.append({"factor": f + 1,
                           "sum_of_squared_loadings": round(
                               sum(rotated[i][f] ** 2 for i in range(len(kept))), 3),
                           "mean_difficulty": round(sum(hardness) / len(hardness), 3)
                           if hardness else None,
                           "difficulty_range": [round(min(hardness), 3),
                                                round(max(hardness), 3)]
                           if hardness else None,
                           "trials_on_the_minority_side_of_its_thinnest_item": thinnest,
                           "flags": flags,
                           "items": [{"item": item, "loading": round(load, 3)}
                                     for item, load in members]})
        report["factors"] = groups
        report["factors_resting_on_too_few_trials"] = [group["factor"] for group in groups
                                                       if group["flags"]]
        report["items_on_no_factor"] = [item for i, item in enumerate(kept)
                                        if max(abs(load) for load in rotated[i]) < SALIENT]

    alpha_value = report["reliability"]["alpha"]
    omega_value = report["reliability"]["omega_total"]
    if alpha_value is not None and omega_value is not None:
        report["reliability"]["omega_total_minus_alpha"] = omega_value - alpha_value
    report["estimator"] = {
        "correlations": "Pearson on 0/1 responses (phi); understates association "
                        "between items of unlike difficulty, biasing loadings "
                        "towards zero and able to split one factor into two",
        "better_and_not_available": "tetrachoric correlations, which need a "
                                    "bivariate normal integral and a dependency "
                                    "this repository does not have",
        "extraction": "principal-axis factoring, iterated communalities, "
                      "started from each item's largest absolute correlation",
        "factor_count": "parallel analysis, permutation null, %d replicates, "
                        "seed %d, %g-th percentile" % (replicates, seed, point),
        "read_the_count_as": "an upper bound when items differ widely in "
                             "difficulty, because phi correlations can split one "
                             "factor into a group of easy items and a group of "
                             "hard ones. Compare each factor's mean difficulty "
                             "before believing it is about content.",
    }
    report["reading"] = reading(report)
    return report


def reading(report: dict) -> str:
    retained = report.get("factors_retained")
    if retained is None:
        return "not enough varying items to say"
    counted, analysed = report["items_counted"], report["items_analysed"]
    if retained == 0:
        body = ("%d items counted, %d varying, and no common factor larger than "
                "chance would have made it" % (counted, analysed))
    else:
        body = ("%d items counted, %d varying, %d dimension%s"
                % (counted, analysed, retained, "" if retained == 1 else "s"))
        thin = len(report.get("factors_resting_on_too_few_trials", []))
        if thin:
            body += ", %d of them resting on fewer than %d trials" % (thin, THIN)
    alpha_value = report["reliability"].get("alpha")
    omega_value = report["reliability"].get("omega_total")
    parts = []
    if alpha_value is not None:
        parts.append("alpha %.3f" % alpha_value)
    if omega_value is not None:
        parts.append("omega %.3f" % omega_value)
    return body + (" (%s)" % ", ".join(parts) if parts else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quiz-results", type=Path, nargs="*", default=[],
                        help="one or more folders of stored reader answers; pooled")
    parser.add_argument("--table", type=Path,
                        help="a CSV of trial,item,correct — any harness can emit this")
    parser.add_argument("--kind", default="fact", choices=("fact", "absent", "all"))
    parser.add_argument("--replicates", type=int, default=DEFAULT_REPLICATES,
                        help="random datasets for parallel analysis")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="seed for the permutation null; printed in the report")
    parser.add_argument("--percentile", type=float, default=DEFAULT_PERCENTILE,
                        help="percentile of the null an eigenvalue must beat")
    parser.add_argument("--max-factors", type=int, default=8,
                        help="cap on factors extracted, not on factors counted")
    parser.add_argument("--eigenvalues", type=int, default=12,
                        help="how many leading eigenvalues to print")
    args = parser.parse_args()

    if bool(args.table) == bool(args.quiz_results):
        raise SystemExit("give either --table or --quiz-results, not both and not neither")
    if args.table:
        rows, items = ia.from_table(args.table)
        source = str(args.table)
    else:
        rows, _key, rendered = ia.responses(args.quiz_results)
        items = [item["id"] for item in rendered
                 if args.kind == "all" or item["kind"] == args.kind]
        source = ", ".join(str(folder) for folder in args.quiz_results)
    try:
        report = analyse(rows, items, args.max_factors, args.replicates,
                         args.seed, args.percentile)
    except ValueError as error:
        raise SystemExit(str(error))
    report["source"] = source
    report["kind"] = "from table" if args.table else args.kind
    cut = max(0, args.eigenvalues)
    if "observed_eigenvalues" in report:
        report["observed_eigenvalues"] = [round(v, 4) for v in report["observed_eigenvalues"][:cut]]
    if "parallel_analysis" in report:
        report["parallel_analysis"]["null_eigenvalues"] = [
            round(v, 4) for v in report["parallel_analysis"]["null_eigenvalues"][:cut]]
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
