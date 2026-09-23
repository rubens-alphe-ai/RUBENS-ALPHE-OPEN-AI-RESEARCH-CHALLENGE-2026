#!/usr/bin/env python3
"""Cut a trial,item,correct table down to its strongest N respondents.

Alpha is not a property of a test. It is a property of a test *and* the people
who sat it, and the September audit of HELM MMLU turned on exactly that: four
subsets with alpha 0.87 to 0.95 across ninety-one models, two of them below zero
across the top twenty. The items did not change. The population did.

So the restricted panel is not a footnote to that analysis, it *is* the
analysis, and the way it gets built deserves a script rather than a shell
one-liner nobody kept. Three things this does that a one-liner did not:

- **the tie at the cut is named.** Taking "the top 20" when the 20th and 21st
  respondents scored the same is an arbitrary choice between them. It is still
  made — some choice has to be — but it is recorded, so a reader can see whether
  the panel boundary was a real gap or a coin toss.
- **the source table is hashed.** A restricted panel that cannot be traced to
  the table it came from is a file of numbers with a suggestive filename.
- **correctness stays binary.** The same refusal as everywhere else in this
  project: a value that is neither 0 nor 1 is not rounded, because choosing
  where the cut falls would change every statistic downstream.

Selection is by total items correct, descending, ties broken by ascending trial
name. That rule is dull on purpose. Any rule that looked at the items would let
the panel be chosen to produce a result.

  python scripts/restrict_panel.py \
      --table experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa.csv \
      --top 20 \
      --out experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa-top20.csv \
      --manifest experiments/PUBLIC-AUDIT-2026-10/helm-lite-med_qa-top20.panel.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TRUTHY = {"1", "true", "t", "yes", "y", "correct", "pass", "right"}
FALSY = {"0", "false", "f", "no", "n", "incorrect", "fail", "wrong"}


def read_binary(value: str, path: Path) -> int:
    """0 or 1, or a refusal. Never a threshold."""
    text = str(value).strip().lower()
    if text in TRUTHY:
        return 1
    if text in FALSY:
        return 0
    try:
        number = float(text)
    except ValueError:
        raise SystemExit("%s: cannot read %r as correct or incorrect" % (path, value))
    if number not in (0.0, 1.0):
        raise SystemExit(
            "%s holds %r, which is a graded score rather than correct or incorrect. "
            "Ranking respondents on a rounded score would pick a different panel than "
            "ranking them on the real one. Use scripts/graded_items.py." % (path, value)
        )
    return int(number)


def read_table(path: Path) -> tuple[dict[str, dict[str, int]], list[str]]:
    """Per-trial answers plus the item order as the file gave it."""
    by_trial: dict[str, dict[str, int]] = {}
    order: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        names = {name.strip().lower(): name for name in (reader.fieldnames or [])}
        missing = [c for c in ("trial", "item", "correct") if c not in names]
        if missing:
            raise SystemExit("%s has no %s column; found %s"
                             % (path, ", ".join(missing), ", ".join(reader.fieldnames or [])))
        for line in reader:
            trial, item = str(line[names["trial"]]), str(line[names["item"]])
            if item not in order:
                order.append(item)
            by_trial.setdefault(trial, {})[item] = read_binary(line[names["correct"]], path)
    if not by_trial:
        raise SystemExit("%s has a header and no rows" % path)
    return by_trial, order


def rank(by_trial: dict[str, dict[str, int]], items: list[str]) -> list[tuple[str, int]]:
    """Trials by total correct, descending; ties by ascending name.

    A trial short of an item is ranked on what it answered, because inventing
    the missing answer either way would move it up or down the ranking on a
    question nobody put to it. Whether such a trial should be here at all is the
    caller's problem, and `--require-complete` is how the caller says so.
    """
    scored = [(name, sum(answers.get(item, 0) for item in items))
              for name, answers in by_trial.items()]
    return sorted(scored, key=lambda pair: (-pair[1], pair[0]))


def cut(ranked: list[tuple[str, int]], top: int) -> dict:
    """Where the panel boundary falls, and whether it fell on a tie."""
    if top >= len(ranked):
        raise SystemExit(
            "asked for the top %d of %d trials, which is not a restriction. The point of a "
            "restricted panel is that it is smaller than the field." % (top, len(ranked)))
    if top < 3:
        raise SystemExit("a panel of %d cannot support item statistics; ask for at least 3" % top)
    kept = ranked[:top]
    lowest_kept, highest_dropped = kept[-1][1], ranked[top][1]
    tied = [name for name, score in ranked if score == lowest_kept]
    return {
        "kept": [name for name, _ in kept],
        "lowest_kept_score": lowest_kept,
        "highest_dropped_score": highest_dropped,
        "gap_at_the_cut": lowest_kept - highest_dropped,
        # A gap of zero means the panel's last member and the first excluded one
        # are indistinguishable on this table, and which of them is in was
        # decided by their names.
        "cut_falls_on_a_tie": lowest_kept == highest_dropped,
        "trials_tied_at_the_cut": tied if lowest_kept == highest_dropped else [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--table", type=Path, required=True, help="CSV of trial,item,correct")
    parser.add_argument("--top", type=int, required=True, help="how many trials to keep")
    parser.add_argument("--out", type=Path, required=True, help="restricted CSV to write")
    parser.add_argument("--manifest", type=Path, help="where to record how the panel was picked")
    parser.add_argument("--require-complete", action="store_true",
                        help="refuse a trial that did not answer every item")
    args = parser.parse_args()

    raw = args.table.read_bytes()
    by_trial, items = read_table(args.table)
    incomplete = sorted(name for name, answers in by_trial.items() if len(answers) != len(items))
    if incomplete and args.require_complete:
        raise SystemExit("%d trials did not answer every item: %s"
                         % (len(incomplete), ", ".join(incomplete[:5])))
    if incomplete:
        print("# %d of %d trials did not answer every item; they are ranked on what they did "
              "answer" % (len(incomplete), len(by_trial)), file=sys.stderr)

    ranked = rank(by_trial, items)
    boundary = cut(ranked, args.top)
    kept = set(boundary["kept"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["trial", "item", "correct"])
        writer.writeheader()
        for name, _score in sorted(ranked):
            if name not in kept:
                continue
            for item in items:
                if item in by_trial[name]:
                    writer.writerow({"trial": name, "item": item,
                                     "correct": by_trial[name][item]})

    record = {
        "record_version": "RA-PSI-PANEL-V1",
        "source_table": str(args.table),
        "source_table_sha256": hashlib.sha256(raw).hexdigest(),
        "table": str(args.out),
        "rule": "top %d trials by total items correct, descending; ties by ascending trial name"
                % args.top,
        "trials_in_full_field": len(by_trial),
        "trials_kept": len(kept),
        "items": len(items),
        "trials_that_did_not_answer_every_item": incomplete,
        "scores": {name: score for name, score in ranked},
        **boundary,
    }
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k != "scores"},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
