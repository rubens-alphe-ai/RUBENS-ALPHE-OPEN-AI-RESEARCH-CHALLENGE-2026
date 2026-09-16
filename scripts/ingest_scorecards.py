#!/usr/bin/env python3
"""Ingest scorecards produced by an external evaluator, and un-blind them.

The evaluator works blind: it sees BLIND-01..BLIND-06 and the rubric, never a
condition. It therefore cannot fill the trial_id, pair_id, seed, condition and
state_sha256 that the scorecard schema requires. This script performs that
join, after the fact, from the private condition map.

The operator drops the evaluator's raw JSON into a file. Nothing here talks to
a model, a browser or a screen: the channel is a file on disk, which is cheap
to read, reviewable, and versioned with its provenance.

Refusals are deliberate. A scorecard is rejected when its blind id is unknown,
when a component score exceeds its maximum, when the declared total disagrees
with the components, or when the raw output it claims to have scored no longer
hashes to what was generated. A scorecard that cannot be tied back to a frozen
output is not evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "PROP-EXP-MEM-001" / "results"
CONDITION_MAP = RESULTS / "condition-map.private.json"
PACKETS = RESULTS / "blind_packets"
OUTPUT_DIR = RESULTS / "scorecards"

COMPONENT_MAXIMA = {
    "mission_reconstruction": 25,
    "current_state_fidelity": 20,
    "failure_recovery": 15,
    "next_action_quality": 20,
    "missing_information_detection": 10,
    "reproducibility": 10,
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_evaluator_json(path: Path) -> dict:
    """Read the evaluator's answer as pasted, not as ideally formatted.

    A chat model wraps JSON in ```json fences, adds a sentence before it, or
    both. The operator should not have to clean that up by hand, so the first
    complete JSON object in the file is taken and the surrounding prose is
    ignored.
    """
    raw = path.read_text(encoding="utf-8-sig")
    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.S)
    candidate = (fenced.group(1) if fenced else raw).strip()
    if not candidate:
        raise SystemExit(
            "%s is empty. Paste the evaluator's JSON answer into it and save "
            "the file (Ctrl+S) before running this." % path
        )
    decoder = json.JSONDecoder()
    index = candidate.find("{")
    while index != -1:
        try:
            value, _ = decoder.raw_decode(candidate, index)
        except json.JSONDecodeError:
            index = candidate.find("{", index + 1)
            continue
        if isinstance(value, dict):
            return value
        index = candidate.find("{", index + 1)
    raise SystemExit(
        "%s contains no complete JSON object. Copy the whole answer, including "
        "its opening and closing braces." % path
    )


def load_condition_map() -> dict:
    if not CONDITION_MAP.is_file():
        raise SystemExit(
            "condition map not found: %s\nRun scripts/build_blind_packets.py first."
            % CONDITION_MAP
        )
    payload = json.loads(CONDITION_MAP.read_text(encoding="utf-8"))
    return {entry["blind_id"]: entry for entry in payload["packets"]}


def validate_card(card: dict, mapping: dict, errors: list) -> bool:
    blind_id = card.get("blind_id")
    if blind_id not in mapping:
        errors.append("unknown blind_id: %r" % blind_id)
        return False

    scores = card.get("scores")
    if not isinstance(scores, dict):
        errors.append("%s: scores missing or not an object" % blind_id)
        return False

    missing = [name for name in COMPONENT_MAXIMA if name not in scores]
    if missing:
        errors.append("%s: missing components %s" % (blind_id, ", ".join(sorted(missing))))
        return False

    for name, maximum in COMPONENT_MAXIMA.items():
        value = scores[name]
        if not isinstance(value, (int, float)):
            errors.append("%s: %s is not a number" % (blind_id, name))
            return False
        if value < 0 or value > maximum:
            errors.append("%s: %s = %s is outside 0..%d" % (blind_id, name, value, maximum))
            return False

    computed = sum(scores[name] for name in COMPONENT_MAXIMA)
    declared = scores.get("total")
    if declared is None:
        scores["total"] = computed
    elif abs(float(declared) - computed) > 0.001:
        # A total that disagrees with its parts is an arithmetic failure, not a
        # rounding preference. It is refused rather than silently rewritten.
        errors.append(
            "%s: declared total %s does not equal the component sum %s"
            % (blind_id, declared, computed)
        )
        return False

    fabrications = card.get("critical_fabrications", [])
    if not isinstance(fabrications, list):
        errors.append("%s: critical_fabrications must be a list" % blind_id)
        return False
    for item in fabrications:
        if not isinstance(item, dict) or not item.get("description"):
            errors.append("%s: a critical_fabrication entry has no description" % blind_id)
            return False

    return True


def build_scorecard(card: dict, source: dict, entry: dict) -> dict:
    scorecard = {
        "card_id": "%s-%s" % (source["evaluator_id"], entry["blind_id"]),
        "evaluator_id": source["evaluator_id"],
        "model": source["model"],
        "provider": source["provider"],
        "pair_id": entry["pair_id"],
        "seed": entry["seed"],
        "trial_id": entry["trial_id"],
        "condition": entry["condition"],
        "output_sha256": entry["output_sha256"],
        "protocol_sha256": source["protocol_sha256"],
        "prompt_sha256": source["prompt_sha256"],
        "state_sha256": entry["state_sha256"],
        "scores": {name: card["scores"][name] for name in COMPONENT_MAXIMA},
        "critical_fabrications": [
            {
                "fabrication_id": str(item.get("fabrication_id") or "F%d" % (index + 1)),
                "description": str(item["description"]),
                **({"evidence": str(item["evidence"])} if item.get("evidence") else {}),
            }
            for index, item in enumerate(card.get("critical_fabrications", []))
        ],
    }
    scorecard["scores"]["total"] = sum(card["scores"][name] for name in COMPONENT_MAXIMA)
    if card.get("notes"):
        scorecard["notes"] = str(card["notes"])
    # The scorecard hash covers the card without its own hash field. The
    # canonical form must match scripts/adjudicate_evaluations.py exactly --
    # compact separators included -- or the adjudicator rejects every card as
    # having a provenance mismatch.
    material = {key: value for key, value in scorecard.items() if key != "scorecard_sha256"}
    scorecard["scorecard_sha256"] = hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return scorecard


def verify_packet_integrity(mapping: dict, errors: list) -> None:
    """Refuse to attach scores to packets that no longer match what was sent."""
    for blind_id, entry in sorted(mapping.items()):
        packet = PACKETS / ("%s.txt" % blind_id)
        if not packet.is_file():
            errors.append("%s: blind packet file is missing" % blind_id)
            continue
        actual = hashlib.sha256(packet.read_bytes()).hexdigest()
        if actual != entry["output_sha256"]:
            errors.append(
                "%s: packet content no longer matches the frozen output hash" % blind_id
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="file holding the evaluator's raw JSON")
    parser.add_argument("--write", action="store_true", help="persist the joined scorecards")
    parser.add_argument("--experiment", default="PROP-EXP-MEM-001")
    args = parser.parse_args()

    global RESULTS, CONDITION_MAP, PACKETS, OUTPUT_DIR
    RESULTS = ROOT / "experiments" / args.experiment / "results"
    CONDITION_MAP = RESULTS / "condition-map.private.json"
    PACKETS = RESULTS / "blind_packets"
    OUTPUT_DIR = RESULTS / "scorecards"

    source = read_evaluator_json(args.input)
    for field in ("evaluator_id", "model", "provider", "cards"):
        if not source.get(field):
            raise SystemExit("input is missing required field: %s" % field)

    mapping = load_condition_map()
    manifest = json.loads((PACKETS / "packet-manifest.json").read_text(encoding="utf-8"))
    source.setdefault("protocol_sha256", manifest["protocol_sha256"])
    source.setdefault("prompt_sha256", manifest["prompt_sha256"])

    errors: list = []
    verify_packet_integrity(mapping, errors)

    accepted = []
    seen = set()
    for card in source["cards"]:
        if not isinstance(card, dict):
            errors.append("a card is not an object")
            continue
        if card.get("blind_id") in seen:
            errors.append("%s: scored twice by the same evaluator" % card.get("blind_id"))
            continue
        if validate_card(card, mapping, errors):
            seen.add(card["blind_id"])
            accepted.append(build_scorecard(card, source, mapping[card["blind_id"]]))

    missing = sorted(set(mapping) - seen)
    report = {
        "evaluator_id": source["evaluator_id"],
        "model": source["model"],
        "provider": source["provider"],
        "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
        "accepted": len(accepted),
        "expected": len(mapping),
        "not_scored": missing,
        "errors": errors,
        "written": False,
    }

    if errors or missing:
        report["status"] = "REFUSED"
        report["note"] = "Nothing written. Fix the evaluator output and run again."
        print(json.dumps(report, indent=2, ensure_ascii=False))
        raise SystemExit(1)

    if args.write:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        target = OUTPUT_DIR / ("scorecards-%s.json" % source["evaluator_id"])
        target.write_text(
            json.dumps(accepted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        report["written"] = True
        report["output"] = str(target.relative_to(ROOT)).replace("\\", "/")

    report["status"] = "ACCEPTED"
    report["note"] = "Two independent evaluators are required before adjudication."
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
