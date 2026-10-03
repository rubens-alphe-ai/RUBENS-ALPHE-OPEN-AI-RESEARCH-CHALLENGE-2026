#!/usr/bin/env python3
"""Which orderings at the top of a published leaderboard do its own error bars support?

Epoch AI publishes, under CC BY 4.0, a score and a standard error for every
model it runs on each benchmark. Those error bars are on the page; what nobody
prints is what they imply for the order of the models at the top, which is the
part people act on. This reads Epoch's CSV bundle and says it.

For each benchmark with at least ten distinct models:

- **tied with the leader** — models whose score cannot be separated from the
  first at 95%, on the leader's and their own published standard errors;
- **adjacent orderings unsupported** — of the nine neighbouring pairs in the top
  ten, how many are not separated;
- **first against fifth, first against tenth** — whether the ends of the top
  group are separated at all.

DISTINCT MODELS, NOT SETTINGS. Epoch lists one model under several reasoning
settings (`_max`, `_high`, `_low`...). Two settings of one model are expected to
be close, and counting them as neighbours would inflate every "unsupported"
figure. Each model is kept once, at its best setting.

IDENTICAL SCORES SEPARATE NOBODY. Sixteen models sit at 100% on one benchmark
with a published error of zero. A rule that treats a difference of zero against
an error of zero as "separated" would report their order as supported; it is
the opposite.

WHAT THIS DOES NOT DO. It compares two models without pairing, which is
conservative: a paired test on per-item results would separate some pairs this
cannot. It applies no correction for comparing many pairs, which would make
fewer separations, not more. It takes Epoch's standard errors as published.

  python scripts/leaderboard_reality.py --zip benchmark_data.zip --out result.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
import zipfile
from pathlib import Path

SETTING = re.compile(r"(_(max|xhigh|high|medium|med|low|minimal|none|thinking|nothinking|default|\d+[kK]))+$")
FEWEST_MODELS = 10
Z = 1.96


def base_model(version: str) -> str:
    return SETTING.sub("", version)


def separated(a: tuple[float, float], b: tuple[float, float]) -> bool:
    (sa, ea), (sb, eb) = a, b
    if sa == sb:
        return False
    return abs(sa - sb) >= Z * math.sqrt(ea * ea + eb * eb)


def best_per_model(rows: list[dict]) -> list[tuple[str, float, float]]:
    best: dict[str, tuple[float, float, str]] = {}
    for row in rows:
        try:
            score, err = float(row["mean_score"]), float(row["stderr"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0.0 <= score <= 1.0 or err < 0:
            continue
        key = base_model(row["Model version"])
        if key not in best or score > best[key][0]:
            best[key] = (score, err, row["Model version"])
    return sorted(((v[2], v[0], v[1]) for v in best.values()), key=lambda t: -t[1])


def assess(name: str, board: list[tuple[str, float, float]]) -> dict | None:
    if len(board) < FEWEST_MODELS:
        return None
    top = [(s, e) for _, s, e in board[:10]]
    return {
        "benchmark": name,
        "distinct_models": len(board),
        "leader": board[0][0],
        "leader_pct": round(100 * board[0][1], 1),
        "tied_with_leader": sum(1 for _, s, e in board[1:] if not separated(top[0], (s, e))),
        "top10_adjacent_unsupported": sum(1 for a, b in zip(top, top[1:]) if not separated(a, b)),
        "first_vs_fifth_separated": separated(top[0], top[4]),
        "first_vs_tenth_separated": separated(top[0], top[9]),
        "top10_span_pts": round(100 * (top[0][0] - top[9][0]), 1),
        "at_99pct_or_more": sum(1 for _, s, _ in board if s >= 0.99),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip", type=Path, required=True, help="Epoch AI benchmark_data.zip")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    archive = zipfile.ZipFile(args.zip)
    results = []
    for name in sorted(archive.namelist()):
        if not name.endswith(".csv"):
            continue
        rows = list(csv.DictReader(io.StringIO(archive.read(name).decode("utf-8"))))
        verdict = assess(name[:-4], best_per_model(rows))
        if verdict:
            results.append(verdict)
    if not results:
        raise SystemExit("no benchmark in %s has %d distinct models with a published error" % (args.zip, FEWEST_MODELS))
    results.sort(key=lambda r: -r["tied_with_leader"])
    record = {
        "record_version": "RA-PSI-LEADERBOARD-REALITY-V1",
        "source": "Epoch AI, Capabilities & benchmarking, https://epoch.ai/benchmarks, CC BY 4.0",
        "rule": "95%, unpaired, no multiple-comparison correction, Epoch's published standard errors, best setting per model",
        "benchmarks": results,
        "summary": {
            "benchmarks": len(results),
            "all_nine_adjacent_orderings_unsupported": sum(r["top10_adjacent_unsupported"] == 9 for r in results),
            "first_not_separated_from_fifth": sum(not r["first_vs_fifth_separated"] for r in results),
            "first_not_separated_from_tenth": sum(not r["first_vs_tenth_separated"] for r in results),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(record["summary"], indent=1))


if __name__ == "__main__":
    main()
