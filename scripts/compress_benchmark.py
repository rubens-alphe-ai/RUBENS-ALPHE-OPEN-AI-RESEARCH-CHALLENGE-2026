#!/usr/bin/env python3
"""Can a benchmark be run on fewer items and still rank tomorrow's models the same way?

Running an evaluation costs money per item, and for agentic benchmarks each
item is a long, expensive run. Many items give every leading model the same
result and so cannot change any decision. This selects items using only the
models released first, then checks the selection on models released later,
which the selection never saw: the only test that says whether a shorter
benchmark keeps working as new models arrive.

Rules (pre-registered in experiments/COMPRESSION-SWEBENCH-2026-10):

- R1, conservative: drop the items every training model solved.
- R2, aggressive: drop the items on which the ten best training models all
  agree (all solved, or all failed).

Both are compared with random subsets of the same size, so that the value of
choosing the items, as opposed to merely using fewer, is measured too.

  python scripts/compress_benchmark.py --table swe.csv --epoch-zip epoch.zip --benchmark swe_bench_verified --out result.json
  python scripts/compress_benchmark.py --table medqa.csv --dates-json dates.json --window 30 --benchmark med_qa --out result.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from claim_check import binomial_tail  # noqa: E402
from validate_against_redux import spearman  # noqa: E402

TRAIN_COUNT, TOP_TRAIN = 20, 10
RANDOM_DRAWS, SEED = 1000, 20261003


def load_table(path: Path) -> dict[str, dict[str, int]]:
    by: dict[str, dict[str, int]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            by.setdefault(row["trial"], {})[row["item"]] = int(float(row["correct"]))
    return by


def release_dates(zip_path: Path, benchmark: str) -> dict[str, str]:
    rows = csv.DictReader(io.StringIO(zipfile.ZipFile(zip_path).read(benchmark + ".csv").decode("utf-8")))
    return {r["Model version"]: r.get("Release date") or "" for r in rows}


def split(models: list[str], dates: dict[str, str], window: int | None = None) -> tuple[list[str], list[str]]:
    """Order by release date; keep the `window` most recent; the first 20 train, the rest test."""
    missing = [m for m in models if not dates.get(m)]
    if missing:
        raise SystemExit("no release date for %s" % ", ".join(missing))
    ordered = sorted(models, key=lambda m: (dates[m], m))
    if window:
        ordered = ordered[-window:]
    return ordered[:TRAIN_COUNT], ordered[TRAIN_COUNT:]


def score(results: dict[str, int], items: list[str]) -> float:
    return sum(results[i] for i in items) / len(items)


def select(by: dict[str, dict[str, int]], train: list[str], items: list[str]) -> dict[str, list[str]]:
    best = sorted(train, key=lambda m: -score(by[m], items))[:TOP_TRAIN]
    r1 = [i for i in items if not all(by[m][i] == 1 for m in train)]
    r2 = [i for i in items if len({by[m][i] for m in best}) > 1]
    return {"R1": r1, "R2": r2}


def mcnemar(a: dict[str, int], b: dict[str, int], items: list[str]) -> tuple[float, float]:
    favour_a = sum(1 for i in items if a[i] == 1 and b[i] == 0)
    favour_b = sum(1 for i in items if a[i] == 0 and b[i] == 1)
    disc = favour_a + favour_b
    p = 1.0 if disc == 0 else min(1.0, 2 * binomial_tail(min(favour_a, favour_b), disc))
    return (favour_a - favour_b) / len(items), p


def evaluate(by: dict[str, dict[str, int]], test: list[str], full: list[str], subset: list[str]) -> dict:
    full_scores = [score(by[m], full) for m in test]
    sub_scores = [score(by[m], subset) for m in test]
    rho = spearman(full_scores, sub_scores)
    kept_order = supported = lost = 0
    for x in range(len(test)):
        for y in range(x + 1, len(test)):
            a, b = by[test[x]], by[test[y]]
            gap_full, p_full = mcnemar(a, b, full)
            if p_full >= 0.05:
                continue
            supported += 1
            gap_sub, p_sub = mcnemar(a, b, subset)
            kept_order += (gap_sub > 0) == (gap_full > 0) and gap_sub != 0
            lost += p_sub >= 0.05
    return {"items": len(subset), "share_of_items": round(len(subset) / len(full), 3),
            "spearman_full_vs_subset": None if rho is None else round(rho, 4),
            "pairs_supported_on_full": supported, "same_order_on_subset": kept_order,
            "share_same_order": round(kept_order / supported, 3) if supported else None,
            "supported_pairs_no_longer_significant": lost}


def random_baseline(by, test, full, size, draws, rng) -> dict:
    rhos = []
    for _ in range(draws):
        subset = rng.sample(full, size)
        rho = spearman([score(by[m], full) for m in test], [score(by[m], subset) for m in test])
        if rho is not None:
            rhos.append(rho)
    rhos.sort()
    return {"draws": len(rhos), "median_spearman": round(rhos[len(rhos) // 2], 4),
            "p05_spearman": round(rhos[int(0.05 * len(rhos))], 4)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--epoch-zip", type=Path, help="release dates from Epoch AI's bundle")
    parser.add_argument("--dates-json", type=Path, help="release dates as a JSON object {model: YYYY-MM-DD}")
    parser.add_argument("--window", type=int, help="keep only this many most recent models")
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    by = load_table(args.table)
    models = sorted(by)
    items = sorted(set.intersection(*(set(by[m]) for m in models)))
    if args.dates_json:
        dates = json.loads(args.dates_json.read_text(encoding="utf-8"))
    elif args.epoch_zip:
        dates = release_dates(args.epoch_zip, args.benchmark)
    else:
        raise SystemExit("give --epoch-zip or --dates-json")
    train, test = split(models, dates, args.window)
    rules = select(by, train, items)
    rng = random.Random(SEED)
    record = {"record_version": "RA-PSI-COMPRESSION-V1", "benchmark": args.benchmark, "items": len(items),
              "train_models": train, "test_models": test, "rules": {}}
    for name, subset in rules.items():
        result = evaluate(by, test, items, subset)
        result["random_same_size"] = random_baseline(by, test, items, len(subset), RANDOM_DRAWS, rng)
        record["rules"][name] = result
    r = record["rules"]

    def held(ok):
        return "held" if ok else "FAILED"

    record["predictions"] = {
        "C1_spearman_ge_0_90_R1": held((r["R1"]["spearman_full_vs_subset"] or 0) >= 0.90),
        "C1_spearman_ge_0_90_R2": held((r["R2"]["spearman_full_vs_subset"] or 0) >= 0.90),
        "C2_same_order_ge_0_95_R1": held((r["R1"]["share_same_order"] or 0) >= 0.95),
        "C2_same_order_ge_0_95_R2": held((r["R2"]["share_same_order"] or 0) >= 0.95),
        "C3_R2_beats_median_random": held((r["R2"]["spearman_full_vs_subset"] or 0)
                                          >= r["R2"]["random_same_size"]["median_spearman"]),
    }
    record["selected_items"] = rules
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k != "selected_items"}, indent=1))


if __name__ == "__main__":
    main()
