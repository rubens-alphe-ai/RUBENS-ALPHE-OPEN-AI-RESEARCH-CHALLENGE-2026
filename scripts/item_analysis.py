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
            flags.append("everyone passes it")
        if difficulty <= FLOOR:
            flags.append("nobody passes it")
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quiz-results", type=Path, nargs="+", required=True,
                        help="one or more folders of stored reader answers; pooled")
    parser.add_argument("--kind", default="fact", choices=("fact", "absent", "all"))
    args = parser.parse_args()

    rows, _key, rendered = responses(args.quiz_results)
    if len(rows) < 3:
        raise SystemExit("only %d trials found; item statistics need more than that" % len(rows))
    items = [item["id"] for item in rendered if args.kind == "all" or item["kind"] == args.kind]
    report = {"record_version": "RA-PSI-ITEMS-V1", "trials": len(rows), "items": len(items),
              "kind": args.kind, "alpha": alpha(rows, items),
              "per_item": analyse(rows, items)}
    flagged = [row for row in report["per_item"] if row["flags"]]
    report["flagged"] = len(flagged)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
