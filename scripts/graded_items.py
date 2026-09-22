#!/usr/bin/env python3
"""The same instrument questions, for items that are scored rather than marked.

`item_analysis.py` reads one bit per item: right or wrong. A large share of real
evaluation is not one bit. A rubric runs 1 to 5, a judge model rates relevance
0 to 1, a partial-credit grader gives half marks. Those teams cannot use that
script at all, and the questions they need answered are the same ones:

- **difficulty** becomes the mean score — but a mean is meaningless without its
  range. 4.2 sits near the ceiling of a 1-to-5 rubric; 0.84 sits in the same
  place on a 0-to-1 judge score; 4.2 on a 1-to-10 scale is nowhere near it. So
  every mean reported here carries its scale and its position within it.
- **discrimination** stays what it was: the correlation between this item's
  score and the total of *every other* item. Same corrected form, Pearson on
  graded values instead of on ones and zeros.
- **a dead item** is no longer only one that everybody passes. An item where
  every response scores 4 carries nothing, whatever the scale says. So does one
  whose scores move independently of the rest of the instrument.

And one failure mode a binary item cannot have:

- **a rubric whose graders only ever use two of its five points.** A 1-to-5
  scale used as a 2-point scale is a finding about the rubric, not about the
  systems being graded, and it is invisible in a mean: the mean of a collapsed
  scale looks exactly like the mean of a used one.

What this refuses to do:

1. **It will not guess the scale range.** A column whose observed values run 1
   to 4 might be a 1-to-5 rubric nobody awarded a 5 on. Inferring 1-to-4 from
   that silently rescales every position, turns a mean of 3.8 from "near the
   top" into "at the top", and makes the collapse check report four points used
   of four. The range is a fact about the rubric, so it must be declared.
2. **It will not accept a score outside the declared range.** A 6 on a 1-to-5
   scale means the declaration and the data disagree. Clamping it would hide
   whichever of the two is wrong.
3. **It will not run the collapse check on a scale whose point count it was not
   told and cannot derive.** A continuous judge score has no points to count.
   The check is reported as not run, rather than run on a guess.
4. **It will not take a two-point scale.** That is a binary item wearing a
   range; `item_analysis.py` already reads it, and reads it better.

  python scripts/graded_items.py --table rubric.csv --scale 1 5
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import item_analysis as ia  # noqa: E402  (variance, correlation, alpha, thresholds)

# Positions within the declared range, not raw scores: the whole point of
# demanding the range is that these thresholds can then mean the same thing on a
# 1-to-5 rubric and on a 0-to-1 judge score.
FLOOR, CEILING = 0.05, 0.95
WEAK = ia.WEAK  # below this an item is not measuring what the rest measures

# A rubric is called collapsed when its graders used at most this share of the
# points available to them. Half is a judgement call, and it is stated here
# rather than buried: 2 of 5 is a collapse, 3 of 5 is reported and not called
# one.
COLLAPSE_SHARE = 0.5


def trim(value: float) -> str:
    """Format a bound the way a rubric author wrote it: 1, not 1.0."""
    return str(int(value)) if float(value).is_integer() else ("%g" % value)


class Scale:
    """A declared range, and the number of points in it if that is knowable.

    Exists as an object rather than a pair of floats so that no mean can be
    reported without it. Every position, every ceiling flag and the whole
    collapse check are computed through here.
    """

    def __init__(self, low: float, high: float, points: int | None) -> None:
        self.low, self.high, self.points = float(low), float(high), points

    @property
    def span(self) -> float:
        return self.high - self.low

    def position(self, value: float) -> float:
        return (value - self.low) / self.span

    def describe(self) -> str:
        return "%s to %s" % (trim(self.low), trim(self.high))

    def as_dict(self) -> dict:
        return {"low": self.low, "high": self.high, "points": self.points,
                "reading": self.describe()}

    @classmethod
    def declared(cls, low: float, high: float, points: int | None = None) -> "Scale":
        low, high = float(low), float(high)
        if high <= low:
            raise SystemExit("a scale of %s to %s has no range; give --scale low high"
                             % (trim(low), trim(high)))
        if points is None and float(low).is_integer() and float(high).is_integer():
            # Derived from the declaration, never from the observed values. A
            # span of 1 is left alone: 0-to-1 is the binary case below, and a
            # continuous 0-to-1 judge score has no points to count.
            if high - low >= 2:
                points = int(round(high - low)) + 1
        if points is not None and points < 3:
            raise SystemExit("a %d-point scale is a binary item wearing a range; "
                             "scripts/item_analysis.py reads those, and reads them better" % points)
        return cls(low, high, points)


def read_scores(path: Path, scale: Scale) -> tuple[list[dict], list[str]]:
    """Per-item scores from a three-column table whose third column is numeric.

    The same shape `item_analysis.from_table` reads — trial, item, score — so a
    harness that can emit one can emit the other. The difference is that the
    third column is kept as a number instead of being cut at a threshold, and
    that a score outside the declared range stops the run.
    """
    by_trial: dict[str, dict[str, float]] = {}
    order: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) < 3:
            raise SystemExit("%s needs a header row with trial, item and score columns" % path)
        names = {name.strip().lower(): name for name in reader.fieldnames}

        def column(*candidates: str) -> str:
            for candidate in candidates:
                if candidate in names:
                    return names[candidate]
            raise SystemExit("%s has no column named any of %s; found %s"
                             % (path, " / ".join(candidates), ", ".join(reader.fieldnames)))

        trial_col = column("trial", "trial_id", "run", "run_id", "sample", "example_id", "model")
        item_col = column("item", "item_id", "question", "question_id", "task", "id")
        score_col = column("score", "rating", "grade", "points", "judgment", "value", "correct")
        for line in reader:
            raw = str(line[score_col]).strip()
            try:
                score = float(raw)
            except ValueError:
                raise SystemExit("cannot read %r in column %r as a number. This reads graded "
                                 "items; for right/wrong use scripts/item_analysis.py"
                                 % (line[score_col], score_col))
            if not (scale.low <= score <= scale.high):
                # Refusing rather than clamping: one of the declaration and the
                # data is wrong, and clamping picks a winner without saying so.
                raise SystemExit("score %s is outside the declared scale of %s (item %r, trial %r). "
                                 "Either the scale is wrong or the grader is."
                                 % (trim(score), scale.describe(), line[item_col], line[trial_col]))
            trial, item = str(line[trial_col]), str(line[item_col])
            if item not in order:
                order.append(item)
            by_trial.setdefault(trial, {})[item] = score
    # As in item_analysis: a trial missing an item was not scored on it, and
    # filling the scale's floor would turn silence into a bad grade.
    complete = [row for row in by_trial.values() if len(row) == len(order)]
    dropped = len(by_trial) - len(complete)
    if dropped:
        print("# %d of %d trials were not scored on every item and were dropped"
              % (dropped, len(by_trial)), file=sys.stderr)
    return complete, order


def analyse(rows: list[dict], items: list[str], scale: Scale) -> list[dict]:
    whole = ia.alpha(rows, items)
    out = []
    for item in items:
        scores = [float(row[item]) for row in rows]
        mean = sum(scores) / len(scores)
        position = scale.position(mean)
        rest = [sum(float(row[q]) for q in items if q != item) for row in rows]
        discrimination = ia.correlation(scores, rest)
        without = ia.alpha(rows, [q for q in items if q != item])
        levels = sorted(set(scores))
        spread = ia.variance(scores)

        flags = []
        if spread == 0:
            flags.append("every response scores %s: it separates nothing" % trim(levels[0]))
        if position >= CEILING:
            flags.append("mean %.2f is at the top of the %s scale" % (mean, scale.describe()))
        if position <= FLOOR:
            flags.append("mean %.2f is at the bottom of the %s scale" % (mean, scale.describe()))
        if discrimination is None:
            flags.append("no variance, discrimination undefined")
        elif discrimination < 0:
            flags.append("negative: the better performances score lower on it")
        elif discrimination < WEAK:
            flags.append("unrelated to what the rest of the instrument measures")
        if scale.points is not None and spread > 0 and len(levels) <= scale.points * COLLAPSE_SHARE:
            flags.append("graders used %d of the %d points on the scale"
                         % (len(levels), scale.points))
        if whole is not None and without is not None and without > whole:
            flags.append("dropping it raises alpha from %.3f to %.3f" % (whole, without))

        out.append({"item": item,
                    "mean": round(mean, 3),
                    "scale": scale.describe(),
                    "position_in_range": round(position, 3),
                    "sd": round(spread ** 0.5, 3),
                    "levels_used": len(levels),
                    "levels_available": scale.points,
                    "discrimination": None if discrimination is None else round(discrimination, 3),
                    "alpha_without": None if without is None else round(without, 3),
                    "flags": flags})
    return out


def effective_length(per_item: list[dict]) -> dict:
    """Items counted against items measuring, on a graded scale.

    Same count and same sentence as `item_analysis.effective_length`, because a
    buyer comparing a rubric to a multiple-choice test should be reading the
    same number. The only change is that "everyone passes it" becomes "the mean
    sits at the end of its declared range", which is the reason the range had to
    be declared.

    The constant count is named `items_that_never_vary` rather than borrowing the
    binary record's `items_all_but_a_few_answer_alike`, because on a rubric the
    commonest dead item is a constant 4 in the middle of the scale, which nobody
    got right and nobody got wrong.
    """
    carrying = [row for row in per_item
                if row["discrimination"] is not None and row["discrimination"] >= WEAK
                and FLOOR < row["position_in_range"] < CEILING]
    constant = [row for row in per_item
                if row["position_in_range"] >= CEILING or row["position_in_range"] <= FLOOR
                or row["sd"] == 0]
    return {"items_counted": len(per_item), "items_carrying": len(carrying),
            "items_that_never_vary": len(constant),
            "share_carrying_pct": round(100.0 * len(carrying) / len(per_item), 1) if per_item else 0.0,
            "carrying_items": [row["item"] for row in carrying],
            "reading": ("a test of %d items that measures with %d"
                        % (len(per_item), len(carrying)))}


def rubric_use(per_item: list[dict], scale: Scale) -> dict:
    """How much of the rubric the graders actually used.

    A finding about the instrument's authors rather than about anyone it graded,
    and the one thing in this file that has no counterpart in the binary case.
    """
    if scale.points is None:
        return {"checked": False,
                "reason": ("the scale has no declared point count and none could be derived from "
                           "its bounds, so there is nothing to count against; pass --scale-points "
                           "if the rubric has discrete levels")}
    collapsed = [row["item"] for row in per_item
                 if row["sd"] > 0 and row["levels_used"] <= scale.points * COLLAPSE_SHARE]
    used_anywhere = sorted({row["levels_used"] for row in per_item})
    return {"checked": True, "points_available": scale.points,
            "items_using_at_most_half_the_points": len(collapsed),
            "collapsed_items": collapsed,
            "levels_used_per_item": used_anywhere,
            "reading": ("%d of %d items are graded on at most %d of the %d points available"
                        % (len(collapsed), len(per_item), int(scale.points * COLLAPSE_SHARE),
                           scale.points))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--table", type=Path, required=True,
                        help="a CSV of trial,item,score with a numeric third column")
    parser.add_argument("--scale", type=float, nargs=2, metavar=("LOW", "HIGH"), required=True,
                        help="the declared range of the score column. Required, and never "
                             "inferred: observed values of 1 to 4 may be a 1-to-5 rubric "
                             "nobody awarded a 5 on.")
    parser.add_argument("--scale-points", type=int, default=None,
                        help="how many discrete points the scale has, when that cannot be "
                             "derived from integer bounds")
    args = parser.parse_args()

    scale = Scale.declared(args.scale[0], args.scale[1], args.scale_points)
    rows, items = read_scores(args.table, scale)
    if len(rows) < 3:
        raise SystemExit("only %d trials found; item statistics need more than that" % len(rows))
    per_item = analyse(rows, items, scale)
    report = {"record_version": "RA-PSI-GRADED-ITEMS-V1", "source": str(args.table),
              "trials": len(rows), "items": len(items), "scale": scale.as_dict(),
              "alpha": ia.alpha(rows, items),
              "effective_length": effective_length(per_item),
              "rubric_use": rubric_use(per_item, scale),
              "per_item": per_item}
    report["flagged"] = sum(1 for row in per_item if row["flags"])
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
