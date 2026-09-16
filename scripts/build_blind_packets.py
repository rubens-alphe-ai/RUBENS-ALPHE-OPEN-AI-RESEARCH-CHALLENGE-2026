#!/usr/bin/env python3
"""Build blinded evaluator packets from frozen raw trial outputs.

The public packet contains only blind IDs, raw-output hashes and the common
protocol/prompt hashes.  The condition map is written to a separate private
path supplied by the operator and is never placed in the evaluator packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(args: argparse.Namespace) -> dict[str, object]:
    root = args.root.resolve()
    manifest = json.loads(args.manifest.resolve().read_text(encoding="utf-8"))
    trials = manifest.get("trials", [])
    if not isinstance(trials, list) or len(trials) == 0:
        raise ValueError("manifest contains no trials")

    entries: list[dict[str, object]] = []
    for trial in trials:
        output = root / str(trial["output_path"])
        if not output.is_file() or output.stat().st_size == 0:
            raise FileNotFoundError(f"raw trial output is missing or empty: {output}")
        actual_hash = file_sha256(output)
        expected_hash = trial.get("output_sha256")
        if expected_hash and expected_hash != actual_hash:
            raise ValueError(f"raw output hash mismatch for {trial['trial_id']}")
        entries.append({**trial, "actual_output_sha256": actual_hash})

    shuffle_material = f"{manifest['experiment_id']}:{manifest['protocol_sha256']}"
    shuffle_seed = int.from_bytes(hashlib.sha256(shuffle_material.encode()).digest()[:8], "big")
    random.Random(shuffle_seed).shuffle(entries)

    public_dir = args.public_dir.resolve()
    private_map = args.private_map.resolve()
    public_dir.mkdir(parents=True, exist_ok=True)
    private_map.parent.mkdir(parents=True, exist_ok=True)

    public_entries: list[dict[str, object]] = []
    private_entries: list[dict[str, object]] = []
    for index, trial in enumerate(entries, start=1):
        blind_id = f"BLIND-{index:02d}"
        source = root / str(trial["output_path"])
        destination = public_dir / f"{blind_id}.txt"
        shutil.copyfile(source, destination)
        public_entries.append(
            {
                "blind_id": blind_id,
                "evaluator_packet": str(destination.relative_to(root)).replace("\\", "/"),
                "output_sha256": trial["actual_output_sha256"],
                "protocol_sha256": trial["protocol_sha256"],
                "prompt_sha256": trial["prompt_sha256"],
            }
        )
        private_entries.append(
            {
                "blind_id": blind_id,
                "trial_id": trial["trial_id"],
                "pair_id": trial["pair_id"],
                "seed": trial["seed"],
                "condition": trial["condition"],
                "state_sha256": trial["state_sha256"],
                "output_sha256": trial["actual_output_sha256"],
                "generation_provider": trial.get("generation_provider"),
                "generation_model": trial.get("generation_model"),
            }
        )

    public_manifest = {
        "packet_version": "RA-PSI-BLIND-PACKET-V1",
        "experiment_id": manifest["experiment_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "shuffle_seed_sha256": hashlib.sha256(str(shuffle_seed).encode()).hexdigest(),
        "protocol_sha256": manifest["protocol_sha256"],
        "prompt_sha256": manifest["prompt_sha256"],
        "condition_labels_exposed": False,
        "packets": public_entries,
        "status": "READY_FOR_INDEPENDENT_EVALUATION",
    }
    private_payload = {
        "private_map_version": "RA-PSI-BLIND-MAP-V1",
        "experiment_id": manifest["experiment_id"],
        "created_at_utc": public_manifest["created_at_utc"],
        "packets": private_entries,
        "warning": "Do not share this file with evaluators before scorecards are frozen.",
    }
    public_manifest_path = public_dir / "packet-manifest.json"
    public_manifest_path.write_text(json.dumps(public_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    private_map.write_text(json.dumps(private_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "public_manifest": str(public_manifest_path),
        "private_map": str(private_map),
        "packet_count": len(public_entries),
        "condition_labels_exposed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root_default = Path(__file__).resolve().parents[1]
    parser.add_argument("--root", type=Path, default=root_default)
    parser.add_argument("--manifest", type=Path, default=root_default / "experiments" / "PROP-EXP-MEM-001" / "results" / "experiment-manifest.json")
    parser.add_argument("--public-dir", type=Path, default=root_default / "experiments" / "PROP-EXP-MEM-001" / "results" / "blind_packets")
    parser.add_argument("--private-map", type=Path, default=root_default / "experiments" / "PROP-EXP-MEM-001" / "results" / "condition-map.private.json")
    args = parser.parse_args()
    print(json.dumps(build(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
