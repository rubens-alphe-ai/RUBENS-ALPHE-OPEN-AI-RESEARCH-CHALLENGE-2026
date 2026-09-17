#!/usr/bin/env python3
"""Check that an evaluator scores answers of known quality where they belong.

Two scorers in MEM-002 disagreed by up to 20 points on the same answer, and one
gave full marks to half of all answers. Agreement between evaluators says
nothing about whether either is right. Calibration does: a fixed set of anchor
answers, written from the state before any evaluator saw them, each with an
expected score band, one invented result that must be reported as a critical
fabrication, and an order that must hold (complete > partial > generic).

Each evaluator receives the anchors exactly as it would receive real answers:
the same header, rubric and output format as experiment scoring. The raw answer
and a pass/fail record are stored under the anchor set's results folder. The
V4 adjudicator requires calibration evidence before FINAL_KEEP.

Example:
  python scripts/calibrate_evaluators.py --anchors calibration/PCRB2/anchors.json \
      --experiment PROP-EXP-MEM-003 --config ~/.ra-psi/run-config.json --only groq-gpt-oss-120b
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import evaluate_experiment as ev
from model_adapter import AdapterError

ROOT = Path(__file__).resolve().parents[1]


def build_prompt(anchor_set: dict) -> tuple[list[str], str]:
    rubric = (ROOT / anchor_set["rubric"]).read_text(encoding="utf-8")
    anchors = anchor_set["anchors"]
    ids = [anchor["blind_id"] for anchor in anchors]
    parts = [ev.BATCH_HEADER.format(part=1, parts=1, count=len(ids)), rubric,
             ev.BATCH_OUTPUT_NO_TOTAL.format(ids=", ".join(ids))]
    for anchor in anchors:
        parts.append("\n## %s\n\n```text\n%s\n```\n" % (anchor["blind_id"], anchor["text"].strip()))
    return ids, "".join(parts)


def judge(anchor_set: dict, cards: list[dict]) -> dict:
    """Apply the anchor set's pass rule to one evaluator's cards."""
    by_id = {card["blind_id"]: card for card in cards}
    totals = {blind_id: sum(v for k, v in card["scores"].items() if k != "total") for blind_id, card in by_id.items()}
    reported = {blind_id for blind_id, card in by_id.items() if card.get("critical_fabrications")}
    rule = anchor_set["pass_rule"]
    failures = []
    for anchor in anchor_set["anchors"]:
        low, high = anchor["expected_total"]
        total = totals.get(anchor["blind_id"])
        if total is None:
            failures.append("%s: no card" % anchor["blind_id"])
        elif rule.get("every_total_within_band") and not low <= total <= high:
            failures.append("%s: total %s outside %s-%s" % (anchor["blind_id"], total, low, high))
    for blind_id in rule.get("fabrication_detected_on", []):
        if blind_id not in reported:
            failures.append("%s: invented result not reported as a critical fabrication" % blind_id)
    for blind_id in rule.get("no_fabrication_reported_on", []):
        if blind_id in reported:
            failures.append("%s: fabrication reported on an answer that has none" % blind_id)
    order = rule.get("strict_order", [])
    for higher, lower in zip(order, order[1:]):
        if higher in totals and lower in totals and not totals[higher] > totals[lower]:
            failures.append("order: %s (%s) not above %s (%s)" % (higher, totals[higher], lower, totals[lower]))
    for low_id, high_id in rule.get("below", []):
        if low_id in totals and high_id in totals and not totals[low_id] < totals[high_id]:
            failures.append("order: %s (%s) not below %s (%s)" % (low_id, totals[low_id], high_id, totals[high_id]))
    return {"passed": not failures, "failures": failures, "totals": totals, "fabrications_reported": sorted(reported)}


def calibrate(anchor_path: Path, entry: dict, max_tokens: int) -> dict:
    anchor_set = json.loads(anchor_path.read_text(encoding="utf-8"))
    ids, prompt = build_prompt(anchor_set)
    results = anchor_path.parent / "results"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = "%s-%s" % (entry["evaluator_id"], stamp)
    record = {"record_version": "RA-PSI-CALIBRATION-RESULT-V1", "anchor_set_version": anchor_set["anchor_set_version"],
              "anchor_set_sha256": ev.sha256_text(anchor_path.read_text(encoding="utf-8")),
              "evaluator_id": entry["evaluator_id"], "provider": entry["provider"], "requested_model": entry["model"],
              "run_at_utc": stamp}
    try:
        content, served = ev.call(entry, prompt, max_tokens)
    except AdapterError as exc:
        record.update(status="CALL_FAILED", error=str(exc)[:300])
    else:
        raw = ev.store_raw(results, name, entry, prompt, content, served)
        record["served_model"] = served
        try:
            part = ev.read_evaluator_json(raw)
        except SystemExit as exc:
            record.update(status="UNPARSEABLE", error=str(exc)[:300])
        else:
            problems = ev.batch_problems(part, ids)
            if problems:
                record.update(status="INVALID", problems=problems[:5])
            else:
                verdict = judge(anchor_set, part["cards"])
                record.update(status="PASSED" if verdict["passed"] else "FAILED", **verdict)
    results.mkdir(parents=True, exist_ok=True)
    (results / ("%s.result.json" % name)).write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--anchors", type=Path, required=True)
    parser.add_argument("--experiment", required=True, help="experiment whose evaluator ladders are calibrated")
    parser.add_argument("--config", type=Path, required=True, help="private file naming where each key is")
    parser.add_argument("--only", nargs="*", help="evaluator ids to calibrate (default: every scorer and checker)")
    parser.add_argument("--max-tokens", type=int, default=8000)
    args = parser.parse_args()
    policy = ev.load_policy(ROOT / "experiments" / args.experiment)
    config = ev.ladder_config(policy, json.loads(args.config.expanduser().read_text(encoding="utf-8")))
    entries = [entry for entry in config["scorers"] + config["checkers"]
               if (not args.only or entry["evaluator_id"] in args.only) and ev.key_available(entry)]
    summary = [{k: v for k, v in calibrate(args.anchors, entry, args.max_tokens).items()
                if k in ("evaluator_id", "status", "failures", "totals", "problems", "error")} for entry in entries]
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
