#!/usr/bin/env python3
"""Check raw trial outputs before they are blinded and sent to evaluators.

Two things made PROP-EXP-MEM-001 look cleaner than it was: two of its three
pairs were byte-identical at temperature 0, and every structured output carried
its condition label. Both were visible in the raw outputs and neither was
checked. This script checks both, for any experiment with a manifest:

* every output hash must be distinct;
* no output may contain a condition-identifying string. The strings come from
  ``leak_markers.json`` when the experiment has one, plus the manifest's own
  input file names, which a generator can only know by copying them.

Plain English words that happen to be section keys (``decisions``, ``rules``)
are reported as weak signals, not failures: an answer from either condition
can use them naturally. Identifiers containing an underscore are strong
signals, because prose never produces them by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True)
    args = parser.parse_args()

    experiment = ROOT / "experiments" / args.experiment
    manifest = json.loads((experiment / "results" / "experiment-manifest.json").read_text(encoding="utf-8"))

    strong: set[str] = set()
    weak: set[str] = set()
    markers_path = experiment / "leak_markers.json"
    if markers_path.is_file():
        for marker in json.loads(markers_path.read_text(encoding="utf-8")).get("only_in_STATE_B", []):
            (strong if "_" in marker else weak).add(marker)
    for trial in manifest["trials"]:
        name = Path(str(trial["state_path"])).name
        strong.add(name)
        strong.add(Path(name).stem)

    hashes: dict[str, list[str]] = defaultdict(list)
    report = []
    missing = []
    for trial in manifest["trials"]:
        output = ROOT / str(trial["output_path"])
        if not output.is_file() or output.stat().st_size == 0:
            missing.append(trial["trial_id"])
            continue
        text = output.read_text(encoding="utf-8")
        hashes[hashlib.sha256(output.read_bytes()).hexdigest()].append(trial["trial_id"])
        strong_hits = sorted(marker for marker in strong if marker in text)
        weak_hits = sorted(
            marker for marker in weak if re.search(r"\b%s\b" % re.escape(marker), text, re.I)
        )
        report.append(
            {
                "trial_id": trial["trial_id"],
                "condition": trial["condition"],
                "strong_leaks": strong_hits,
                "weak_signals": weak_hits,
            }
        )

    duplicates = [ids for ids in hashes.values() if len(ids) > 1]
    leaking = [row for row in report if row["strong_leaks"]]
    weak_by_condition: dict[str, int] = defaultdict(int)
    for row in report:
        if row["weak_signals"]:
            weak_by_condition[row["condition"]] += 1

    ok = not missing and not duplicates and not leaking
    print(
        json.dumps(
            {
                "experiment_id": manifest["experiment_id"],
                "outputs_checked": len(report),
                "missing_outputs": missing,
                "distinct_output_hashes": len(hashes),
                "duplicate_outputs": duplicates,
                "strong_leaks": leaking,
                "outputs_with_weak_signals_by_condition": dict(weak_by_condition),
                "status": "CLEAR" if ok else "BLOCKED",
                "note": "Weak signals are reported, not blocking; compare their rate across conditions.",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
