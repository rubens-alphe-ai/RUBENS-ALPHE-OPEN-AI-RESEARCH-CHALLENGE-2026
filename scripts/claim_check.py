#!/usr/bin/env python3
"""Does a claimed gap between two models hold on the items they both answered?

"Model A beats model B on benchmark X" is the sentence in a launch post, a pitch
deck or a vendor comparison. With per-item results it can be tested properly:
both models answered the same questions, so the right comparison is paired —
only the questions on which they *disagree* carry information about which is
better.

McNemar's exact test does that. Of the items where exactly one model is right,
count how many favour A (b) and how many favour B (c). If the two were equally
good, each of those disagreements would be a coin toss; the test asks how
unlikely the observed split is under that.

It reports, in words a non-statistician can act on:

- the gap in points, with a 95% interval;
- whether the data support it, and at what significance;
- if not, roughly how many items it would take to settle it at the observed
  gap — the honest answer to "is this benchmark big enough for this claim";
- if a gap was claimed, whether the claimed size sits inside the interval.

WHAT IT REFUSES. A model missing from the table; fewer than 30 shared items,
where any verdict would rest on a handful of disagreements; and a claim it
cannot test — with aggregate scores only, it points to `leaderboard_check.py`,
which says what aggregates can and cannot establish.

  python scripts/claim_check.py --table results.csv --model-a A --model-b B --claimed-gap 3.0
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

FEWEST_SHARED = 30
Z95, Z80 = 1.959964, 0.841621


def load(path: Path) -> dict[str, dict[str, int]]:
    by: dict[str, dict[str, int]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = str(row.get("correct", "")).strip().lower()
            if value in ("1", "true", "correct", "pass", "yes"):
                bit = 1
            elif value in ("0", "false", "incorrect", "fail", "no"):
                bit = 0
            else:
                raise SystemExit("cannot read %r as correct or incorrect; this test needs right/wrong per item"
                                 % row.get("correct"))
            by.setdefault(str(row["trial"]), {})[str(row["item"])] = bit
    return by


def binomial_tail(k: int, n: int) -> float:
    """P(X <= k) for X ~ Binomial(n, 1/2), computed in log space for large n."""
    if n == 0:
        return 1.0
    log_half_n = -n * math.log(2)
    total = 0.0
    for i in range(0, k + 1):
        total += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + log_half_n)
    return min(1.0, total)


def compare(a: dict[str, int], b: dict[str, int]) -> dict:
    shared = sorted(set(a) & set(b))
    n = len(shared)
    if n < FEWEST_SHARED:
        raise SystemExit("only %d items were answered by both models; below %d, a verdict would rest on a "
                         "handful of disagreements" % (n, FEWEST_SHARED))
    favour_a = sum(1 for i in shared if a[i] == 1 and b[i] == 0)
    favour_b = sum(1 for i in shared if a[i] == 0 and b[i] == 1)
    discordant = favour_a + favour_b
    gap = (favour_a - favour_b) / n
    se = math.sqrt(max(discordant - (favour_a - favour_b) ** 2 / n, 0.0)) / n
    p = 1.0 if discordant == 0 else min(1.0, 2 * binomial_tail(min(favour_a, favour_b), discordant))
    needed = None
    p_disc = discordant / n
    if gap != 0 and p_disc > gap * gap:
        needed = math.ceil(((Z95 * math.sqrt(p_disc) + Z80 * math.sqrt(p_disc - gap * gap)) ** 2) / (gap * gap))
    return {
        "shared_items": n,
        "score_a_pct": round(100 * sum(a[i] for i in shared) / n, 2),
        "score_b_pct": round(100 * sum(b[i] for i in shared) / n, 2),
        "items_only_a_right": favour_a,
        "items_only_b_right": favour_b,
        "gap_pts": round(100 * gap, 2),
        "gap_interval_95_pts": [round(100 * (gap - Z95 * se), 2), round(100 * (gap + Z95 * se), 2)],
        "mcnemar_exact_p": round(p, 5),
        "supported_at_95": p < 0.05,
        "items_needed_for_80pct_power_at_this_gap": needed,
    }


def reading(result: dict, name_a: str, name_b: str, claimed: float | None) -> str:
    lo, hi = result["gap_interval_95_pts"]
    lines = []
    if result["items_only_a_right"] + result["items_only_b_right"] == 0:
        lines.append("The two models give the same result on every shared item; the data cannot order them.")
    elif result["supported_at_95"]:
        ahead = name_a if result["gap_pts"] > 0 else name_b
        lines.append("%s is ahead by %.1f points (95%% interval %.1f to %.1f); the gap is supported "
                     "(exact McNemar p = %.4f)." % (ahead, abs(result["gap_pts"]), lo, hi, result["mcnemar_exact_p"]))
    else:
        lines.append("The gap of %.1f points is not supported: the data are consistent with no difference "
                     "(95%% interval %.1f to %.1f; exact McNemar p = %.3f)."
                     % (result["gap_pts"], lo, hi, result["mcnemar_exact_p"]))
        if result["items_needed_for_80pct_power_at_this_gap"]:
            lines.append("Settling a gap this size would take about %d items at this rate of disagreement; "
                         "the test has %d." % (result["items_needed_for_80pct_power_at_this_gap"],
                                               result["shared_items"]))
    if claimed is not None:
        inside = lo <= claimed <= hi
        lines.append("The claimed gap of %.1f points is %s the 95%% interval." % (claimed, "inside" if inside else "outside"))
    lines.append("Paired comparison on %d items both models answered; %d favour %s, %d favour %s."
                 % (result["shared_items"], result["items_only_a_right"], name_a,
                    result["items_only_b_right"], name_b))
    return " ".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--table", type=Path, required=True, help="CSV of trial,item,correct")
    parser.add_argument("--model-a", required=True)
    parser.add_argument("--model-b", required=True)
    parser.add_argument("--claimed-gap", type=float, help="the gap claimed for A over B, in points")
    args = parser.parse_args()
    by = load(args.table)
    for model in (args.model_a, args.model_b):
        if model not in by:
            raise SystemExit("no trial named %r in %s; found %s" % (model, args.table, ", ".join(sorted(by)[:12])))
    result = compare(by[args.model_a], by[args.model_b])
    result["model_a"], result["model_b"] = args.model_a, args.model_b
    result["claimed_gap_pts"] = args.claimed_gap
    result["reading"] = reading(result, args.model_a, args.model_b, args.claimed_gap)
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
