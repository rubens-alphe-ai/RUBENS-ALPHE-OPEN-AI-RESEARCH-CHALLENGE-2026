#!/usr/bin/env python3
"""Fail a build when switching models is not backed by your own evaluation.

A team swaps the model behind its product because a new one "scores higher".
This gate reads the per-item results of the current model and of the
candidate on the same evaluation set, compares them item by item (exact
McNemar), and exits non-zero according to the policy you choose:

- `--require better` (for a switch made to gain quality): pass only if the
  candidate is shown better at 95%.
- `--require not-worse` (for a switch made to save money): pass unless the
  candidate is shown worse at 95%. This is a weak guarantee, and the report
  says so: with few items, a real loss can go undetected, so the report gives
  the smallest loss the test could have caught.

Input files are CSV with columns `item,correct` (one file per model), or one
table `trial,item,correct` with `--trial-current` and `--trial-candidate`.
Nothing is sent anywhere; no model is called.

  python scripts/model_gate.py --current old.csv --candidate new.csv --require better
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from claim_check import Z80, Z95, compare  # noqa: E402

TRUE = {"1", "true", "correct", "pass", "yes"}
FALSE = {"0", "false", "incorrect", "fail", "no"}


def read(path: Path, trial: str | None = None) -> dict[str, int]:
    out = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if trial is not None and row.get("trial") != trial:
                continue
            value = str(row.get("correct", "")).strip().lower()
            if value not in TRUE | FALSE:
                raise SystemExit("cannot read %r as correct or incorrect in %s" % (row.get("correct"), path))
            out[str(row["item"])] = 1 if value in TRUE else 0
    if not out:
        raise SystemExit("no results read from %s%s" % (path, " for trial %r" % trial if trial else ""))
    return out


def smallest_detectable_loss(n: int, discordant_rate: float) -> float | None:
    """Gap (as a proportion) that a paired test of this size detects with 80% power."""
    if n == 0 or discordant_rate <= 0:
        return None
    return (Z95 + Z80) * math.sqrt(discordant_rate / n)


def decide(current: dict[str, int], candidate: dict[str, int], require: str) -> dict:
    result = compare(candidate, current)  # positive gap = candidate ahead
    lo, hi = result["gap_interval_95_pts"]
    shown_better = result["supported_at_95"] and result["gap_pts"] > 0
    shown_worse = result["supported_at_95"] and result["gap_pts"] < 0
    passed = shown_better if require == "better" else not shown_worse
    disc = (result["items_only_a_right"] + result["items_only_b_right"]) / result["shared_items"]
    detectable = smallest_detectable_loss(result["shared_items"], disc)
    if require == "better":
        reading = ("PASS: the candidate is shown better by %.1f points (95%% interval %.1f to %.1f)." % (result["gap_pts"], lo, hi)
                   if passed else
                   "FAIL: the candidate is not shown better (gap %.1f points, 95%% interval %.1f to %.1f). "
                   "A higher score on this set is not evidence of a better model." % (result["gap_pts"], lo, hi))
    else:
        reading = ("FAIL: the candidate is shown worse by %.1f points (95%% interval %.1f to %.1f)." % (-result["gap_pts"], lo, hi)
                   if not passed else
                   "PASS: the candidate is not shown worse (gap %.1f points, 95%% interval %.1f to %.1f). This does not "
                   "show the two are equal: a loss smaller than about %.1f points could go undetected with %d items."
                   % (result["gap_pts"], lo, hi, 100 * (detectable or 0), result["shared_items"]))
    return {"require": require, "passed": passed, "reading": reading,
            "smallest_detectable_gap_pts": None if detectable is None else round(100 * detectable, 1), **result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--current", type=Path, required=True, help="results of the model in production")
    parser.add_argument("--candidate", type=Path, help="results of the candidate (default: same file as --current)")
    parser.add_argument("--trial-current", help="trial name, when both models are in one trial,item,correct table")
    parser.add_argument("--trial-candidate")
    parser.add_argument("--require", choices=("better", "not-worse"), required=True)
    parser.add_argument("--json", type=Path, help="also write the full result here")
    args = parser.parse_args()
    current = read(args.current, args.trial_current)
    candidate = read(args.candidate or args.current, args.trial_candidate)
    result = decide(current, candidate, args.require)
    print(result["reading"])
    if args.json:
        args.json.write_text(json.dumps(result, indent=1), encoding="utf-8")
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
