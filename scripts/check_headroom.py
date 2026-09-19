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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def headroom(prior_pct: float, kind: str) -> float:
    """The largest value a threshold of this kind could possibly take."""
    if kind == "ratio":
        return 100.0 / prior_pct if prior_pct else float("inf")
    return 100.0 - prior_pct


def findings(policy: dict) -> list[dict]:
    """One row per registered threshold that can be checked against a prior."""
    decision = policy.get("decision") or {}
    priors = decision.get("control_prior_pct") or {}
    rows = []
    for name, kind in (("keep_min_delta_pp", "points"), ("pays_for_itself_pp", "points"),
                       ("gap_targeting_ratio", "ratio")):
        threshold = decision.get(name)
        if threshold is None:
            continue
        prior = priors.get(name)
        if prior is None:
            rows.append({"threshold": name, "value": threshold, "kind": kind,
                         "status": "UNDECLARED",
                         "reason": "no control_prior_pct declared for %s: the threshold cannot be checked" % name})
            continue
        for document, value in (prior.items() if isinstance(prior, dict) else [("all", prior)]):
            room = headroom(float(value), kind)
            ok = float(threshold) <= room
            rows.append({"threshold": name, "value": threshold, "kind": kind, "document": document,
                         "control_prior_pct": value, "headroom": round(room, 2),
                         "status": "OK" if ok else "IMPOSSIBLE",
                         "reason": "" if ok else
                         "%s of %s needs a control at or below %.1f %%, and it is declared at %.1f %%"
                         % (name, threshold, 100.0 - float(threshold) if kind == "points"
                            else 100.0 / float(threshold), float(value))})
    return rows


def check(experiment_id: str) -> dict:
    policy = json.loads((ROOT / "experiments" / experiment_id / "evaluation_policy.json").read_text(encoding="utf-8"))
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
    status = "REFUSED" if (impossible and short) else ("WARN" if undeclared or impossible else "REACHABLE")
    return {"experiment": experiment_id, "documents_required": required, "rows": rows,
            "thresholds_short_of_the_documents_they_need": short, "status": status}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", required=True)
    args = parser.parse_args()
    result = check(args.experiment)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] == "REFUSED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
