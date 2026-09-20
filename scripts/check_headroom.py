#!/usr/bin/env python3
"""Refuse a threshold that the quantity it constrains cannot reach.

This project has now registered two thresholds that were arithmetically
impossible before their first call:

- **MEM-010**: +20 points over a control that already kept 94 % of the facts.
  The most that was available was +6.
- **MEM-012**: a metric required to *double* when it was already at 92 %.

Both refusals stand — a threshold is not moved after seeing data. But both were
avoidable by arithmetic, and the second happened after the first had been
written up. So the arithmetic is a script, run before the run, like the budget.

An experiment declares what it believes the control will do. For a difference
in percentage points the headroom is 100 minus that; for a ratio on a bounded
quantity it is 100 divided by it. A threshold above the headroom is refused,
and the refusal says by how much.

Declaring the prior is the point: it is a prediction, recorded before the data,
and a policy that declines to make one gets a warning rather than a pass.

  python scripts/check_headroom.py --experiment PROP-EXP-MEM-012
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from handoff_quiz import T_975  # noqa: E402


def headroom(prior_pct: float, kind: str) -> float:
    """The largest value a threshold of this kind could possibly take."""
    if kind == "ratio":
        return 100.0 / prior_pct if prior_pct else float("inf")
    return 100.0 - prior_pct


def smallest_passing_mean(threshold: float, repeats: int, paired_sd_pp: float) -> float:
    """The smallest observed effect that would satisfy the whole rule.

    Every acceptance rule in this project has two clauses: the effect must reach
    the threshold, **and** the 95 % lower bound must sit above zero. Only the
    first was ever checked here. The second is a separate demand — the mean must
    exceed t × the standard error — and at small repeat counts it is by far the
    harder one.

    Ignoring it let PROP-EXP-MEM-013 register as REACHABLE while being
    unmeetable: at six repeats and a paired standard deviation of about 11
    points, the interval clause alone needs an observed 8.8 points, against an
    arithmetic ceiling of 7. The threshold fit; the rule could not be satisfied.
    """
    if repeats < 2 or paired_sd_pp <= 0:
        return threshold
    standard_error = paired_sd_pp / math.sqrt(repeats)
    return max(threshold, T_975.get(repeats - 1, 1.96) * standard_error)


def findings(policy: dict) -> list[dict]:
    """One row per registered threshold that can be checked against a prior."""
    decision = policy.get("decision") or {}
    priors = decision.get("control_prior_pct") or {}
    rows = []
    # `gap_targeting_margin_pp` replaces the ratio this project should never
    # have registered. The agent `zhaoxuan` put the reason plainly: a margin in
    # points sits above the experiment's own construction-noise band and avoids
    # the distortion of ratios near a bounded endpoint, where doubling a
    # quantity already at 92 % is not a demanding test but an impossible one.
    for name, kind in (("keep_min_delta_pp", "points"), ("pays_for_itself_pp", "points"),
                       ("gap_targeting_margin_pp", "points"), ("gap_targeting_ratio", "ratio")):
        threshold = decision.get(name)
        if threshold is None:
            continue
        prior = priors.get(name)
        if prior is None:
            rows.append({"threshold": name, "value": threshold, "kind": kind,
                         "status": "UNDECLARED",
                         "reason": "no control_prior_pct declared for %s: the threshold cannot be checked" % name})
            continue
        # What the rule actually demands, once its interval clause is counted.
        # A rule is checked against this, not against its headline threshold.
        needed = float(threshold)
        repeats, sd = decision.get("repeats"), decision.get("paired_sd_pp")
        if kind == "points" and repeats and sd:
            needed = smallest_passing_mean(float(threshold), int(repeats), float(sd))
        for document, value in (prior.items() if isinstance(prior, dict) else [("all", prior)]):
            room = headroom(float(value), kind)
            ok = needed <= room
            row = {"threshold": name, "value": threshold, "kind": kind, "document": document,
                   "control_prior_pct": value, "headroom": round(room, 2),
                   "smallest_passing_mean": round(needed, 2),
                   "status": "OK" if ok else "IMPOSSIBLE"}
            if kind == "points" and not (repeats and sd):
                # Silence about the noise is not a claim that there is none. The
                # check is left exactly as weak as it was, and says so, because
                # the alternative is a REACHABLE that was never earned.
                row["noise_undeclared"] = True
                row["note"] = ("no `repeats` and `paired_sd_pp` declared, so the 95 %% lower bound clause "
                               "of this rule is unchecked; only the %s-point threshold was tested" % threshold)
            if not ok and needed > float(threshold):
                row["reason"] = ("the interval clause, not the threshold: at %s repeats with a paired SD of "
                                 "%s points the 95%% lower bound only clears zero above %.1f, and the ceiling "
                                 "here is %.1f" % (repeats, sd, needed, room))
            elif not ok:
                row["reason"] = ("%s of %s needs a control at or below %.1f %%, and it is declared at %.1f %%"
                                 % (name, threshold, 100.0 - float(threshold) if kind == "points"
                                    else 100.0 / float(threshold), float(value)))
            else:
                row["reason"] = ""
            rows.append(row)
    return rows


def check(experiment_id: str | None = None, policy_path: Path | None = None) -> dict:
    """Check one experiment of this project, or any policy file anywhere.

    Nothing in the arithmetic is specific to this repository: a threshold, a
    prior for what the control will do, and the number of runs are all a policy
    has to declare. The path argument exists so the check can be run against
    someone else's project without copying their files into this one.
    """
    if policy_path is None:
        if experiment_id is None:
            raise SystemExit("give either an experiment id or a path to a policy file")
        policy_path = ROOT / "experiments" / experiment_id / "evaluation_policy.json"
    if not policy_path.is_file():
        raise SystemExit("no policy file at %s" % policy_path)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    experiment_id = experiment_id or policy.get("experiment_id") or policy_path.parent.name
    rows = findings(policy)
    impossible = [row for row in rows if row["status"] == "IMPOSSIBLE"]
    undeclared = [row for row in rows if row["status"] == "UNDECLARED"]
    # An impossible threshold on *any* document required to pass is fatal: the
    # rule asks for two of three, and a rule that can only ever be met on one is
    # already decided.
    required = int((policy.get("decision") or {}).get("documents_required", 1))
    reachable = {row["threshold"] for row in rows if row["status"] == "OK"}
    per_threshold: dict[str, int] = {}
    for row in rows:
        if row["status"] == "OK":
            per_threshold[row["threshold"]] = per_threshold.get(row["threshold"], 0) + 1
    short = [name for name in reachable if per_threshold.get(name, 0) < required]
    unchecked = [row for row in rows if row.get("noise_undeclared")]
    status = ("REFUSED" if (impossible and short)
              else ("WARN" if undeclared or impossible or unchecked else "REACHABLE"))
    return {"experiment": experiment_id, "documents_required": required, "rows": rows,
            "thresholds_short_of_the_documents_they_need": short,
            "rules_whose_interval_clause_is_unchecked": [row["threshold"] for row in unchecked],
            "status": status}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", help="an experiment id in this repository")
    parser.add_argument("--policy", type=Path,
                        help="a path to any evaluation policy JSON, in this project or another")
    args = parser.parse_args()
    if not args.experiment and not args.policy:
        raise SystemExit("give --experiment or --policy")
    result = check(args.experiment, args.policy)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] == "REFUSED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
