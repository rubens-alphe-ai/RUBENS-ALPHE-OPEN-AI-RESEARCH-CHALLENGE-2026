#!/usr/bin/env python3
"""Create a rotating, blinded holdout split for evaluator calibration.

The public manifest keeps all packets in a shuffled order and does not reveal
which are calibration or holdout items.  The split is deterministic for a
given experiment and round, while changing the round rotates membership.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path


def bucket(experiment_id: str, round_id: int, blind_id: str) -> int:
    material = f"{experiment_id}:holdout:{round_id}:{blind_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-manifest", type=Path, required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--holdout-fraction", type=float, default=0.25)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()

    if not 0 < args.holdout_fraction < 1:
        raise SystemExit("holdout fraction must be between 0 and 1")
    packet_manifest = json.loads(args.packet_manifest.read_text(encoding="utf-8"))
    packets = packet_manifest.get("packets", [])
    if len(packets) < 2:
        raise SystemExit("at least two blind packets are required")

    ordered = sorted(
        packets,
        key=lambda packet: bucket(packet_manifest["experiment_id"], args.round, packet["blind_id"]),
    )
    holdout_count = max(1, min(len(ordered) - 1, round(len(ordered) * args.holdout_fraction)))
    holdout_ids = {packet["blind_id"] for packet in ordered[:holdout_count]}
    public_packets = list(packets)
    random.Random(bucket(packet_manifest["experiment_id"], args.round, "public-order")).shuffle(public_packets)

    public = {
        "packet_version": "RA-PSI-HOLDOUT-PACKET-V1",
        "experiment_id": packet_manifest["experiment_id"],
        "round": args.round,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": packet_manifest["protocol_sha256"],
        "prompt_sha256": packet_manifest["prompt_sha256"],
        "condition_labels_exposed": False,
        "calibration_and_holdout_labels_exposed": False,
        "packets": public_packets,
        "status": "READY_FOR_BLIND_CALIBRATION",
    }
    private = {
        "split_version": "RA-PSI-HOLDOUT-SPLIT-V1",
        "experiment_id": packet_manifest["experiment_id"],
        "round": args.round,
        "holdout_fraction": args.holdout_fraction,
        "holdout_blind_ids": sorted(holdout_ids),
        "calibration_blind_ids": sorted(
            packet["blind_id"] for packet in packets if packet["blind_id"] not in holdout_ids
        ),
        "warning": "Do not disclose the split until calibration scorecards are frozen.",
    }
    args.public_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.public_output.write_text(json.dumps(public, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.private_output.write_text(json.dumps(private, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"public_output": str(args.public_output), "private_output": str(args.private_output), "holdout_count": holdout_count, "round": args.round}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
