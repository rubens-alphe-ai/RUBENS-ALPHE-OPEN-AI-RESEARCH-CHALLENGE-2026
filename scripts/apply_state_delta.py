#!/usr/bin/env python3
"""Apply a candidate state only after an explicit FINAL_KEEP decision.

Default mode is a dry-run.  ``--apply`` is required for the actual copy.  The
command refuses provisional, rejected or inconclusive decisions and verifies
the pre-state hash before changing the target.  It records an append-only JSONL
delta event; it never performs an automatic rollback of an already-adopted
state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--delta-log", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="perform the explicit final adoption")
    args = parser.parse_args()

    decision = json.loads(args.decision.read_text(encoding="utf-8"))
    actual_from_hash = file_sha256(args.canonical)
    candidate_hash = file_sha256(args.candidate)
    expected_from_hash = decision.get("from_state_sha256", decision.get("pre_state_sha256"))
    expected_candidate_hash = decision.get("candidate_state_sha256")

    if decision.get("decision") != "FINAL_KEEP" or decision.get("canonical_update_allowed") is not True:
        raise SystemExit("Refusing state adoption: decision is not FINAL_KEEP with canonical_update_allowed=true")
    if expected_from_hash and expected_from_hash != actual_from_hash:
        raise SystemExit("Refusing state adoption: canonical pre-state hash changed")
    if expected_candidate_hash and expected_candidate_hash != candidate_hash:
        raise SystemExit("Refusing state adoption: candidate state hash does not match decision")

    event = {
        "delta_id": f"delta-{decision.get('decision_id', 'unknown')}",
        "proposal_id": decision.get("proposal_id", "unknown"),
        "decision_id": decision.get("decision_id", "unknown"),
        "from_state_sha256": actual_from_hash,
        "candidate_state_sha256": candidate_hash,
        "decision": "FINAL_KEEP",
        "canonical_update_allowed": True,
        "candidate_action": "ADOPT",
        "canonical_state_action": "ADOPT" if args.apply else "NO_CHANGE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "rollback": {
            "candidate_discarded": False,
            "canonical_rollback_performed": False,
            "reason": "Adoption is guarded by the pre-state hash; rollback remains an explicit review action.",
        },
    }

    if args.apply:
        args.canonical.write_bytes(args.candidate.read_bytes())
        args.delta_log.parent.mkdir(parents=True, exist_ok=True)
        with args.delta_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        print(json.dumps({"applied": True, "canonical": str(args.canonical), "event": event}, indent=2, ensure_ascii=False))
    else:
        event["dry_run"] = True
        print(json.dumps({"applied": False, "event": event}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
