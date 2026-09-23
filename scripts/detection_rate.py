#!/usr/bin/env python3
"""Plant defects we know about, and measure how often the audit finds them.

`scripts/item_analysis.py` makes claims a buyer acts on: this item is mis-keyed,
this item carries nothing, your test of N items measures with M. Those claims
have been checked against real data and against our own quiz. They have never
been checked against data whose defects are *known in advance*, which is the
only way to say how often the tool is right.

A laboratory that measures things for a living asks two questions about any
instrument, in this order:

- **How often does it find a defect that is there?**  (detection)
- **How often does it report a defect that is not?**  (false alarm)

Either number alone is worthless. A tool that flags every item detects every
defect. A tool that flags nothing never raises a false alarm. So this module
never prints one without the other, and refuses to summarise a run as a single
score, because there is no single score: the two rates trade against each other
and the trade is the buyer's to make.

What is planted, and what counts as finding it:

- **mis-keyed** — an item generated normally, then scored against the wrong
  answer, so the respondents who know most get it wrong. Found when the item is
  flagged `negative: better performances get it wrong`.
- **dead** — an item nearly everyone passes, whatever their ability. Found when
  flagged at the ceiling or floor, or as having no variance.
- **noise** — an item answered at a constant rate unrelated to ability, the
  shape of a question that measures something else entirely. Found when flagged
  as unrelated to the rest, or as negative.
- **healthy** — no defect. Any flag on one of these is a false alarm.

THE GENERATING MODEL IS AN ASSUMPTION, AND IT IS THE LIMIT OF THIS RESULT.
Responses come from a two-parameter logistic: one ability per respondent drawn
from a standard normal, one difficulty and one discrimination per item, and
correctness drawn independently. Real benchmarks are not that. Items there share
topics, respondents share training data, and neither independence nor a single
ability holds. So these rates describe the tool's behaviour *on data of this
shape*, and a real dataset can only be harder. They are an upper bound, and the
output says so rather than leaving it to be assumed.

  python scripts/detection_rate.py --replications 200
  python scripts/detection_rate.py --respondents 20 50 100 --replications 200
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import item_analysis as ia  # noqa: E402

# Below this, a rate rests on too few runs to be worth printing. Reporting
# "0.90" from ten replications invites a reader to believe two digits that are
# not there.
FEWEST_REPLICATIONS = 30

KINDS = ("miskeyed", "dead", "noise")


def probability(ability: float, difficulty: float, discrimination: float) -> float:
    return 1.0 / (1.0 + math.exp(-discrimination * (ability - difficulty)))


def one_dataset(rng: random.Random, respondents: int, healthy: int,
                planted: dict[str, int]) -> tuple[list[dict], list[str], dict[str, str]]:
    """Responses whose defects are known because we put them there."""
    abilities = [rng.gauss(0.0, 1.0) for _ in range(respondents)]
    truth: dict[str, str] = {}
    columns: dict[str, list[int]] = {}

    def healthy_column(name: str) -> list[int]:
        # Difficulty kept near the middle on purpose: an item that lands at the
        # ceiling by construction is not healthy, and counting a correct flag on
        # it as a false alarm would flatter the tool.
        difficulty = rng.uniform(-0.8, 0.8)
        discrimination = rng.uniform(0.9, 1.8)
        return [1 if rng.random() < probability(a, difficulty, discrimination) else 0
                for a in abilities]

    for index in range(healthy):
        name = "H%02d" % (index + 1)
        columns[name] = healthy_column(name)
        truth[name] = "healthy"

    for index in range(planted.get("miskeyed", 0)):
        name = "M%02d" % (index + 1)
        # Generated like any other item, then scored against the wrong answer.
        # This is what a key entered one line off actually looks like.
        columns[name] = [1 - value for value in healthy_column(name)]
        truth[name] = "miskeyed"

    for index in range(planted.get("dead", 0)):
        name = "D%02d" % (index + 1)
        columns[name] = [1 if rng.random() < 0.98 else 0 for _ in abilities]
        truth[name] = "dead"

    for index in range(planted.get("noise", 0)):
        name = "N%02d" % (index + 1)
        columns[name] = [1 if rng.random() < 0.5 else 0 for _ in abilities]
        truth[name] = "noise"

    items = sorted(columns)
    rows = [{name: columns[name][trial] for name in items} for trial in range(respondents)]
    return rows, items, truth


def found(kind: str, flags: list[str]) -> bool:
    """Whether the tool said, about this item, the thing that is true of it."""
    joined = " ".join(flags)
    if kind == "miskeyed":
        return "negative" in joined
    if kind == "dead":
        return "pass it" in joined or "fail it" in joined or "no variance" in joined
    if kind == "noise":
        return "unrelated" in joined or "negative" in joined or "no variance" in joined
    raise ValueError(kind)


def interval(hits: int, total: int) -> list[float] | None:
    """Wilson bounds, because a rate from a few hundred runs is not a point."""
    if total == 0:
        return None
    z = 1.96
    p = hits / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - spread), 3), round(min(1.0, centre + spread), 3)]


def characterise(respondents: int, healthy: int, planted: dict[str, int],
                 replications: int, seed: int, field: str = "flags") -> dict:
    """`field` picks which judgement is being measured: the point-estimate
    flags, or `flags_confident`, which fires only when the interval around the
    estimate excludes the threshold."""
    rng = random.Random(seed)
    caught = {kind: 0 for kind in KINDS}
    present = {kind: 0 for kind in KINDS}
    healthy_seen = 0
    healthy_flagged = 0
    carrying_counts: list[int] = []
    undefined_alpha = 0

    for _ in range(replications):
        rows, items, truth = one_dataset(rng, respondents, healthy, planted)
        per_item = ia.analyse(rows, items)
        if ia.alpha(rows, items) is None:
            undefined_alpha += 1
        for row in per_item:
            kind = truth[row["item"]]
            if kind == "healthy":
                healthy_seen += 1
                if row[field]:
                    healthy_flagged += 1
            else:
                present[kind] += 1
                if found(kind, row[field]):
                    caught[kind] += 1
        carrying_counts.append(ia.effective_length(per_item)["items_carrying"])

    detection = {}
    for kind in KINDS:
        if present[kind] == 0:
            continue
        detection[kind] = {
            "planted": present[kind],
            "found": caught[kind],
            "rate": round(caught[kind] / present[kind], 3),
            "interval_95": interval(caught[kind], present[kind]),
        }

    mean_carrying = sum(carrying_counts) / len(carrying_counts)
    return {
        "respondents": respondents,
        "items": healthy + sum(planted.values()),
        "healthy_items": healthy,
        "replications": replications,
        "detection": detection,
        "false_alarm": {
            "healthy_items_examined": healthy_seen,
            "healthy_items_flagged": healthy_flagged,
            "rate": round(healthy_flagged / healthy_seen, 3) if healthy_seen else None,
            "interval_95": interval(healthy_flagged, healthy_seen),
            "note": ("a flag on a healthy item is counted against the tool even when the "
                     "flag states something true of that sample, because the buyer reads "
                     "it as a defect in their test"),
        },
        "effective_length": {
            "items_truly_carrying": healthy,
            "mean_reported_carrying": round(mean_carrying, 2),
            "bias": round(mean_carrying - healthy, 2),
            "note": ("negative bias means the report understates how much of the test "
                     "measures, which costs the buyer items they did not need to lose"),
        },
        "alpha_undefined_in_runs": undefined_alpha,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--respondents", type=int, nargs="+", default=[20, 50, 100, 200],
                        help="how many respondents sat the test; the rates depend on this")
    parser.add_argument("--healthy", type=int, default=20)
    parser.add_argument("--miskeyed", type=int, default=3)
    parser.add_argument("--dead", type=int, default=3)
    parser.add_argument("--noise", type=int, default=3)
    parser.add_argument("--replications", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260922)
    args = parser.parse_args()

    if args.replications < FEWEST_REPLICATIONS:
        raise SystemExit(
            "%d replications is too few to report a rate from; %d is the minimum. A rate "
            "printed to three digits from a handful of runs reads as precision that is not "
            "there." % (args.replications, FEWEST_REPLICATIONS))
    if args.healthy < 3:
        raise SystemExit("discrimination is computed against the other items, so at least "
                         "3 healthy items are needed; got %d" % args.healthy)

    planted = {"miskeyed": args.miskeyed, "dead": args.dead, "noise": args.noise}
    if sum(planted.values()) == 0:
        raise SystemExit("nothing was planted, so there is no detection rate to measure; "
                         "raise --miskeyed, --dead or --noise above zero")

    report = {
        "record_version": "RA-PSI-DETECTION-V1",
        "generating_model": ("two-parameter logistic; ability ~ N(0,1); healthy items "
                             "difficulty ~ U(-0.8,0.8), discrimination ~ U(0.9,1.8); "
                             "responses drawn independently"),
        "limit": ("real benchmarks violate the independence and single-ability assumptions "
                  "above, so these are an upper bound on detection and a lower bound on "
                  "false alarms; a real dataset can only be harder"),
        "thresholds_used": {"floor": ia.FLOOR, "ceiling": ia.CEILING, "weak": ia.WEAK,
                            "note": "taken from item_analysis.py unchanged; not tuned here"},
        "planted_per_dataset": planted,
        "seed": args.seed,
        "judgements_compared": {
            "flags": "the threshold applied to the point estimate; what was shipped first",
            "flags_confident": ("the threshold applied to the 95% interval around the "
                                "estimate, so a flag fires only where a healthy item could "
                                "not plausibly have produced the data"),
        },
        "by_respondents": [characterise(n, args.healthy, planted, args.replications, args.seed)
                           for n in sorted(args.respondents)],
        "by_respondents_confident": [
            characterise(n, args.healthy, planted, args.replications, args.seed,
                         field="flags_confident")
            for n in sorted(args.respondents)],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
