#!/usr/bin/env python3
"""Treat a quiz as a measuring instrument and report whether it is one.

Before a scale is used on people, four things are established: how hard each
item is, whether each item separates strong performances from weak ones,
whether the items hang together as one dimension, and how much of the score is
signal rather than luck. LLM benchmarks skip all four and report a mean.

This project found out why that matters by accident. Four questions of
forty-two carried most of the disagreement between readers, and they correlated
with each other ten to twenty times more than with the rest — which is the
signature of a scale measuring two things while reporting one number. That was
found by hand. These are the standard statistics that would have found it
directly, applied here to the project's own quiz before anyone else's.

What is computed, per item:

- **difficulty**, the share of trials answering it correctly. An item everyone
  passes or everyone fails carries no information about anything, whatever it
  asks.
- **discrimination**, the correlation between getting that item right and the
  score on *every other item*. Correcting for the item itself matters: an
  uncorrected figure is inflated by the item's own contribution, and a short
  quiz inflates it a lot. Near zero means the item is unrelated to whatever the
  rest of the quiz measures. **Negative means the better performances get it
  wrong**, which is a defect, not a difficult question.
- **alpha if this item were dropped**, against the whole quiz's alpha. An item
  whose removal *raises* internal consistency is subtracting from the
  instrument.

None of this says an item is wrong. It says the item does not belong to the
same scale as the others, which is a different and more useful statement — and
one this project got wrong when it first proposed deleting the offenders.

  python scripts/item_analysis.py --quiz-results experiments/PROP-EXP-MEM-007/results/quiz
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# An item this easy or this hard cannot separate anything, so its
# discrimination is undefined in practice rather than bad.
FLOOR, CEILING = 0.05, 0.95
WEAK = 0.20  # below this, an item is not measuring what the rest measures


def responses(folders: list[Path]) -> tuple[list[dict], dict, list[dict]]:
    """Per-trial correctness, pooled over every reader folder given."""
    key_path = next((folder / "answer-key.json" for folder in folders
                     if (folder / "answer-key.json").is_file()), None)
    if key_path is None:
        raise SystemExit("no answer-key.json in any of the folders given")
    key_file = json.loads(key_path.read_text(encoding="utf-8"))
    key, rendered = key_file["key"], key_file["rendered"]
    rows = []
    for folder in folders:
        for path in sorted(folder.glob("*.json")):
            if "decision" in path.name or "answer-key" in path.name:
                continue
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            given = record.get("answers")
            if given:
                rows.append({item["id"]: 1 if given.get(item["id"]) == key[item["id"]] else 0
                             for item in rendered})
    return rows, key, rendered


def variance(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / (n - 1)


def correlation(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3 or variance(a) == 0 or variance(b) == 0:
        return None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else None


def alpha(rows: list[dict], items: list[str]) -> float | None:
    """Cronbach's alpha: how much of the score is the scale rather than luck."""
    k = len(items)
    if k < 2 or len(rows) < 3:
        return None
    item_var = sum(variance([row[q] for row in rows]) for q in items)
    total_var = variance([sum(row[q] for q in items) for row in rows])
    if total_var == 0:
        return None
    return (k / (k - 1)) * (1 - item_var / total_var)


def analyse(rows: list[dict], items: list[str]) -> list[dict]:
    whole = alpha(rows, items)
    out = []
    for item in items:
        scores = [row[item] for row in rows]
        difficulty = sum(scores) / len(scores)
        # Against the rest, never against a total that contains the item.
        rest = [sum(row[q] for q in items if q != item) for row in rows]
        discrimination = correlation([float(s) for s in scores], [float(r) for r in rest])
        without = alpha(rows, [q for q in items if q != item])
        flags = []
        if difficulty >= CEILING:
            flags.append("all but at most %d in 100 pass it" % round(100 * (1 - CEILING)))
        if difficulty <= FLOOR:
            flags.append("all but at most %d in 100 fail it" % round(100 * FLOOR))
        if discrimination is None:
            flags.append("no variance, discrimination undefined")
        elif discrimination < 0:
            flags.append("negative: better performances get it wrong")
        elif discrimination < WEAK:
            flags.append("unrelated to what the rest of the quiz measures")
        if whole is not None and without is not None and without > whole:
            flags.append("dropping it raises alpha from %.3f to %.3f" % (whole, without))
        out.append({"item": item, "difficulty": round(difficulty, 3),
                    "discrimination": None if discrimination is None else round(discrimination, 3),
                    "alpha_without": None if without is None else round(without, 3),
                    "flags": flags})
    return out


def effective_length(per_item: list[dict]) -> dict:
    """How many items are doing the work, against how many are being counted.

    A test reports its length in items. What it actually measures with is the
    subset that varies *and* relates to the rest: an item everyone passes
    contributes a constant, and a constant carries no information about anyone.

    This project's own quiz declares thirty-two fact questions and measures with
    five. That gap is the number worth reporting, because a length everyone
    quotes and nobody checks is the easiest thing in a benchmark to be wrong
    about.

    It is a count, deliberately, not an estimate from a latent-trait model.
    Fitting one to five varying items would produce a more impressive number
    resting on less.
    """
    carrying = [row for row in per_item
                if row["discrimination"] is not None and row["discrimination"] >= WEAK
                and FLOOR < row["difficulty"] < CEILING]
    constant = [row for row in per_item if row["difficulty"] >= CEILING or row["difficulty"] <= FLOOR]
    return {"items_counted": len(per_item), "items_carrying": len(carrying),
            "items_all_but_a_few_answer_alike": len(constant),
            "share_carrying_pct": round(100.0 * len(carrying) / len(per_item), 1) if per_item else 0.0,
            "carrying_items": [row["item"] for row in carrying],
            "reading": ("a test of %d items that measures with %d"
                        % (len(per_item), len(carrying)))}


def from_table(path: Path) -> tuple[list[dict], list[str]]:
    """Per-item responses from a plain table, so this runs on anyone's data.

    Three columns, named in a header row: a trial identifier, an item
    identifier, and whether that trial got that item right. Every evaluation
    harness can emit that, and almost none emit anything richer — which is the
    reason most benchmarks cannot be checked this way at all.

    Accepts `1/0`, `true/false`, `correct/incorrect`, `pass/fail`, `yes/no`.
    """
    import csv

    truthy = {"1", "true", "t", "yes", "y", "correct", "pass", "right"}
    falsy = {"0", "false", "f", "no", "n", "incorrect", "fail", "wrong"}
    by_trial: dict[str, dict[str, int]] = {}
    order: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) < 3:
            raise SystemExit("%s needs a header row with trial, item and correct columns" % path)
        names = {name.strip().lower(): name for name in reader.fieldnames}

        def column(*candidates: str) -> str:
            for candidate in candidates:
                if candidate in names:
                    return names[candidate]
            raise SystemExit("%s has no column named any of %s; found %s"
                             % (path, " / ".join(candidates), ", ".join(reader.fieldnames)))

        trial_col = column("trial", "trial_id", "run", "run_id", "sample", "example_id")
        item_col = column("item", "item_id", "question", "question_id", "task", "id")
        right_col = column("correct", "is_correct", "score", "right", "pass", "result")
        for line in reader:
            value = str(line[right_col]).strip().lower()
            if value in truthy:
                right = 1
            elif value in falsy:
                right = 0
            else:
                # Thresholding a graded score here was silent and destructive. A
                # 1-to-5 rubric arrived as all ones: every item at difficulty
                # 1.0, alpha undefined, and the report told its owner they had
                # "a test of 8 items that measures with 0". A healthy instrument
                # declared dead, with no warning, is the worst answer this tool
                # can give — so a value that is neither a word for correctness
                # nor exactly 0 or 1 is refused, with somewhere to go.
                try:
                    number = float(value)
                except ValueError:
                    raise SystemExit("cannot read %r in column %r as correct or incorrect"
                                     % (line[right_col], right_col))
                if number not in (0.0, 1.0):
                    raise SystemExit(
                        "column %r holds %r, which is a graded score rather than correct or "
                        "incorrect. Rounding it here would report your instrument as dead when it "
                        "is not. Use scripts/graded_items.py, which takes the scale range."
                        % (right_col, line[right_col]))
                right = int(number)
            trial, item = str(line[trial_col]), str(line[item_col])
            if item not in order:
                order.append(item)
            by_trial.setdefault(trial, {})[item] = right
    # A trial missing an item cannot be scored on it, and quietly filling a zero
    # would turn an absent answer into a wrong one.
    complete = [row for row in by_trial.values() if len(row) == len(order)]
    dropped = len(by_trial) - len(complete)
    if dropped:
        print("# %d of %d trials did not answer every item and were dropped"
              % (dropped, len(by_trial)), file=sys.stderr)
    return complete, order


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quiz-results", type=Path, nargs="*", default=[],
                        help="one or more folders of stored reader answers; pooled")
    parser.add_argument("--table", type=Path,
                        help="a CSV of trial,item,correct — any harness can emit this")
    parser.add_argument("--kind", default="fact", choices=("fact", "absent", "all"))
    args = parser.parse_args()

    if bool(args.table) == bool(args.quiz_results):
        raise SystemExit("give either --table or --quiz-results, not both and not neither")
    if args.table:
        rows, items = from_table(args.table)
        source = str(args.table)
    else:
        rows, _key, rendered = responses(args.quiz_results)
        items = [item["id"] for item in rendered if args.kind == "all" or item["kind"] == args.kind]
        source = ", ".join(str(folder) for folder in args.quiz_results)
    if len(rows) < 3:
        raise SystemExit("only %d trials found; item statistics need more than that" % len(rows))
    per_item = analyse(rows, items)
    report = {"record_version": "RA-PSI-ITEMS-V1", "source": source, "trials": len(rows),
              "items": len(items), "kind": args.kind if not args.table else "from table",
              "alpha": alpha(rows, items), "effective_length": effective_length(per_item),
              "per_item": per_item}
    report["flagged"] = sum(1 for row in per_item if row["flags"])
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
