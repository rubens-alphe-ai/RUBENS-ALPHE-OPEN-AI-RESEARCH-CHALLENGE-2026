#!/usr/bin/env python3
"""Neutralise copied state identifiers in raw outputs before blinding.

MEM-003's generator copied section keys of the structured state
(``verified_knowledge``, ``open_questions``) into three answers. An evaluator
who sees such a key can guess the condition. This script replaces each strong
marker from ``leak_markers.json`` — an identifier with an underscore — by the
same words with spaces, in every output of the experiment, whatever its
condition. The words stay; only the identifier form that exists solely in the
structured file disappears.

Nothing is lost: each original is copied once to ``results/unredacted/`` and
``results/redaction-log.json`` records both hashes and the number of
replacements per output. Running it twice changes nothing.

Using it is a protocol decision and must be recorded before any scoring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strong_markers(experiment: Path) -> list[str]:
    markers = json.loads((experiment / "leak_markers.json").read_text(encoding="utf-8")).get("only_in_STATE_B", [])
    # Longest first, so a marker that contains another is replaced whole.
    return sorted({marker for marker in markers if "_" in marker}, key=len, reverse=True)


def redact_text(text: str, markers: list[str]) -> tuple[str, int]:
    count = 0
    for marker in markers:
        found = text.count(marker)
        if found:
            text = text.replace(marker, marker.replace("_", " "))
            count += found
    return text, count


def run(experiment_id: str) -> dict:
    experiment = ROOT / "experiments" / experiment_id
    results = experiment / "results"
    manifest = json.loads((results / "experiment-manifest.json").read_text(encoding="utf-8"))
    markers = strong_markers(experiment)
    originals = results / "unredacted"
    originals.mkdir(exist_ok=True)
    entries = []
    for trial in manifest["trials"]:
        output = ROOT / trial["output_path"]
        kept = originals / output.name
        if not kept.is_file():
            shutil.copyfile(output, kept)
        original = kept.read_bytes()
        text, count = redact_text(original.decode("utf-8"), markers)
        redacted = text.encode("utf-8")
        if output.read_bytes() != redacted:
            output.write_bytes(redacted)
        entries.append({"trial_id": trial["trial_id"], "original_sha256": sha256_bytes(original),
                        "redacted_sha256": sha256_bytes(redacted), "replacements": count})
    log = {"record_version": "RA-PSI-REDACTION-V1", "experiment_id": experiment_id,
           "rule": "each strong leak marker (identifier with an underscore) replaced by the same words with spaces, in every output",
           "markers": markers, "outputs": entries,
           "outputs_changed": sum(1 for entry in entries if entry["replacements"])}
    (results / "redaction-log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"outputs": len(entries), "outputs_changed": log["outputs_changed"],
            "replacements": sum(entry["replacements"] for entry in entries)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.experiment), indent=2))


if __name__ == "__main__":
    main()
