#!/usr/bin/env python3
"""On the day a model is released: which of its benchmark leads are established?

A release is announced with scores, and the scores are read as a ranking. This
takes the new model's results from Epoch AI's public benchmark data (CC BY 4.0,
with a standard error per model) and, on every benchmark where it appears,
asks the only question the error bars can answer: is its score separated from
the best other model's at 95%, and from how many models is it not separated?

It uses the same rule as `leaderboard_reality.py`: unpaired, Epoch's published
standard errors, one entry per model at its best setting, no correction for
multiple comparisons. A paired test on per-item results separates more pairs;
this one is conservative. "Not established" means "not shown at this sample
size", never "false".

  python scripts/launch_check.py --zip benchmark_data.zip --model gpt-6.1-sol
  python scripts/launch_check.py --zip benchmark_data.zip --newest
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from leaderboard_reality import Z, base_model, separated  # noqa: E402

FEWEST_OTHERS = 5


def boards(archive: zipfile.ZipFile) -> dict[str, list[dict]]:
    out = {}
    for name in sorted(archive.namelist()):
        if name.endswith(".csv"):
            out[name[:-4]] = list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8"))))
    return out


def best_entries(rows: list[dict]) -> dict[str, dict]:
    """One entry per model, at its best setting, with a usable score and error."""
    best: dict[str, dict] = {}
    for row in rows:
        try:
            score, err = float(row["mean_score"]), float(row["stderr"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0.0 <= score <= 1.0 or err < 0:
            continue
        model = base_model(row["Model version"])
        if model not in best or score > best[model]["score"]:
            best[model] = {"model": model, "setting": row["Model version"], "score": score, "stderr": err,
                           "release_date": row.get("Release date") or ""}
    return best


def newest(all_boards: dict[str, list[dict]]) -> str:
    dated = {}
    for rows in all_boards.values():
        for entry in best_entries(rows).values():
            if entry["release_date"]:
                dated[entry["model"]] = max(dated.get(entry["model"], ""), entry["release_date"])
    if not dated:
        raise SystemExit("no release dates in this bundle")
    return max(dated, key=lambda m: (dated[m], m))


def check(name: str, rows: list[dict], model: str) -> dict | None:
    entries = best_entries(rows)
    mine = entries.get(model)
    others = sorted((e for m, e in entries.items() if m != model), key=lambda e: -e["score"])
    if mine is None or len(others) < FEWEST_OTHERS:
        return None
    pair = (mine["score"], mine["stderr"])
    rival = others[0]
    gap = mine["score"] - rival["score"]
    se = math.sqrt(mine["stderr"] ** 2 + rival["stderr"] ** 2)
    rank = 1 + sum(e["score"] > mine["score"] for e in others)
    if gap == 0:
        reading = "level with the best other model"
    elif rank == 1:
        reading = ("lead established" if separated(pair, (rival["score"], rival["stderr"]))
                   else "first, but the lead is not established at this sample size")
    elif separated(pair, (rival["score"], rival["stderr"])):
        reading = "behind the leader, and the gap is established"
    else:
        reading = "behind the leader, but not separated from it"
    return {
        "benchmark": name,
        "setting": mine["setting"],
        "score_pct": round(100 * mine["score"], 1),
        "rank": rank,
        "models_compared": len(others) + 1,
        "best_other": rival["setting"],
        "best_other_pct": round(100 * rival["score"], 1),
        "gap_pts": round(100 * gap, 1),
        "gap_interval_95_pts": [round(100 * (gap - Z * se), 1), round(100 * (gap + Z * se), 1)],
        "not_separated_from": sum(1 for e in others if not separated(pair, (e["score"], e["stderr"]))),
        "reading": reading,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip", type=Path, required=True, help="Epoch AI benchmark_data.zip")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--model", help="model name without its setting suffix, e.g. gpt-6.1-sol")
    group.add_argument("--newest", action="store_true", help="the model with the latest release date")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    all_boards = boards(zipfile.ZipFile(args.zip))
    model = newest(all_boards) if args.newest else base_model(args.model)
    results = [r for r in (check(n, rows, model) for n, rows in all_boards.items()) if r]
    if not results:
        raise SystemExit("%s has no benchmark with a published error and at least %d other models" % (model, FEWEST_OTHERS))
    firsts = [r for r in results if r["rank"] == 1]
    record = {
        "record_version": "RA-PSI-LAUNCH-CHECK-V1",
        "model": model,
        "source": "Epoch AI, Capabilities & benchmarking, https://epoch.ai/benchmarks, CC BY 4.0",
        "rule": "95%, unpaired, Epoch's published standard errors, best setting per model, no multiple-comparison correction",
        "summary": {
            "benchmarks": len(results),
            "first_alone": sum(r["gap_pts"] > 0 for r in firsts),
            "level_with_the_best_other": sum(r["reading"] == "level with the best other model" for r in firsts),
            "lead_established": sum(r["reading"] == "lead established" for r in firsts),
            "behind_and_gap_established": sum(r["reading"] == "behind the leader, and the gap is established"
                                              for r in results),
        },
        "benchmarks": sorted(results, key=lambda r: (r["rank"], -r["gap_pts"])),
    }
    text = json.dumps(record, indent=1, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
