#!/usr/bin/env python3
"""Deterministic V4 gate for independent, paired RA-PSI evaluations.

The script evaluates candidate evidence only.  It never edits canonical state.
It deliberately separates these outcomes:

* PROVISIONAL_KEEP: pilot evidence is promising, but adoption is forbidden;
* FINAL_KEEP: the replication and regression gates passed, so adoption may be
  staged by a separate, human-auditable state-delta step;
* REJECT: the candidate is discarded;
* INCONCLUSIVE: evidence is incomplete or evaluators disagree.

Input is a JSON object containing ``evaluations`` (or the legacy alias
``scorecards``).  Each card must carry hashes for the protocol, prompt, input
state, raw output and scorecard itself.  Cards are paired by ``pair_id`` and
matched by evaluator identity before any aggregate is computed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCORE_FIELDS = (
    "mission_reconstruction",
    "current_state_fidelity",
    "failure_recovery",
    "next_action_quality",
    "missing_information_detection",
    "reproducibility",
)
SCORE_MAXIMA = {
    "mission_reconstruction": 25,
    "current_state_fidelity": 20,
    "failure_recovery": 15,
    "next_action_quality": 20,
    "missing_information_detection": 10,
    "reproducibility": 10,
}
HASH_FIELDS = (
    "output_sha256",
    "protocol_sha256",
    "prompt_sha256",
    "state_sha256",
    "scorecard_sha256",
)
DECISIONS = {"PROVISIONAL_KEEP", "FINAL_KEEP", "REJECT", "INCONCLUSIVE"}
HEX_SHA256 = set("0123456789abcdef")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and set(value).issubset(HEX_SHA256)
    )


def score_total(card: dict[str, Any]) -> float:
    return float(card["scores"]["total"])


def normalized_fabrications(card: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize current and legacy fabrication representations.

    V4 uses objects so two evaluators can be compared without relying on
    keyword matching.  Integer counts are accepted only for migration and are
    treated as output-level reports, which still require independent
    confirmation before rejection.
    """

    raw = card.get("critical_fabrications", [])
    if raw is None:
        return []
    if isinstance(raw, int):
        return [
            {
                "fabrication_id": f"legacy-{index + 1}",
                "description": "Legacy count-only fabrication report",
            }
            for index in range(max(raw, 0))
        ]
    if not isinstance(raw, list):
        return [{"fabrication_id": "invalid", "description": str(raw)}]

    result: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        if isinstance(item, dict):
            result.append(
                {
                    "fabrication_id": str(
                        item.get("fabrication_id", f"fabrication-{index + 1}")
                    ),
                    "description": str(item.get("description", "")),
                }
            )
        else:
            result.append(
                {
                    "fabrication_id": f"fabrication-{index + 1}",
                    "description": str(item),
                }
            )
    return result


def validate_card(card: Any, index: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(card, dict):
        return [f"card[{index}] is not an object"]

    required = (
        "card_id",
        "evaluator_id",
        "model",
        "provider",
        "pair_id",
        "seed",
        "condition",
        "scores",
        *HASH_FIELDS,
    )
    for field in required:
        if field not in card:
            errors.append(f"card[{index}] missing {field}")

    if card.get("condition") not in {"baseline", "structured"}:
        errors.append(f"card[{index}] has invalid condition")

    for field in HASH_FIELDS:
        if field in card and not is_sha256(card[field]):
            errors.append(f"card[{index}] has invalid {field}")

    scores = card.get("scores")
    if not isinstance(scores, dict):
        errors.append(f"card[{index}] scores is not an object")
        return errors

    for field in SCORE_FIELDS:
        value = scores.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"card[{index}] score {field} is not numeric")
        elif not 0 <= float(value) <= SCORE_MAXIMA[field]:
            errors.append(f"card[{index}] score {field} is outside its rubric bound")

    total = scores.get("total")
    if not isinstance(total, (int, float)) or isinstance(total, bool):
        errors.append(f"card[{index}] score total is not numeric")
    else:
        expected = sum(float(scores.get(field, 0)) for field in SCORE_FIELDS)
        if not math.isclose(float(total), expected, abs_tol=1e-9):
            errors.append(
                f"card[{index}] total {total} does not equal component sum {expected}"
            )
        if not 0 <= float(total) <= 100:
            errors.append(f"card[{index}] total is outside 0..100")

    # The scorecard hash is calculated over the card without its self-hash.
    if is_sha256(card.get("scorecard_sha256")):
        unhashed = {key: value for key, value in card.items() if key != "scorecard_sha256"}
        if sha256_json(unhashed) != card["scorecard_sha256"]:
            errors.append(f"card[{index}] scorecard_sha256 does not match card content")

    return errors


def policy(data: dict[str, Any]) -> dict[str, Any]:
    configured = data.get("evidence_policy", {})
    if not isinstance(configured, dict):
        configured = {}
    return {
        "provisional_min_paired_trials": int(
            configured.get("provisional_min_paired_trials", data.get("min_paired_trials", 3))
        ),
        "final_min_paired_trials": int(
            configured.get("final_min_paired_trials", data.get("final_min_replication_trials", 9))
        ),
        "min_independent_evaluators": int(
            configured.get("min_independent_evaluators", data.get("min_independent_evaluators", 2))
        ),
        "final_min_generation_models": int(
            configured.get("final_min_generation_models", data.get("final_min_generation_models", 2))
        ),
        "final_min_evaluator_providers": int(
            configured.get("final_min_evaluator_providers", data.get("final_min_evaluator_providers", 2))
        ),
        "final_requires_holdout": bool(
            configured.get("final_requires_holdout", data.get("final_requires_holdout", True))
        ),
        "final_requires_regression_suite": bool(
            configured.get(
                "final_requires_regression_suite",
                data.get("final_requires_regression_suite", True),
            )
        ),
        "final_requires_calibration": bool(
            configured.get("final_requires_calibration", data.get("final_requires_calibration", True))
        ),
        "minimum_mean_improvement": float(
            data.get("required_mean_improvement", data.get("success_threshold", 10.0))
        ),
        "minimum_lower_95_bound": float(data.get("minimum_lower_95_bound", 5.0)),
        "max_evaluator_disagreement": float(
            data.get("max_evaluator_disagreement", 15.0)
        ),
        # ADR-004. "any": a confirmed fabrication in either condition rejects
        # the candidate (V4 behaviour). "comparative": it rejects only when the
        # structured condition has more confirmed fabrications than baseline,
        # which is the acceptance rule PCRB-1 itself states.
        "fabrication_rule": str(configured.get("fabrication_rule", "any")),
        # ADR-004. Share of pairs allowed to exceed max_evaluator_disagreement
        # before the whole experiment is inconclusive. 0 keeps V4 behaviour.
        "max_disagreeing_pair_fraction": float(configured.get("max_disagreeing_pair_fraction", 0.0)),
    }


def stage_name(data: dict[str, Any], requested: str) -> str:
    if requested != "auto":
        return requested
    value = str(data.get("stage", "pilot")).lower()
    if value in {"replication", "final", "replicating"}:
        return "replication"
    return "pilot"


def base_result(data: dict[str, Any], decision: str, status: str, reasons: list[str]) -> dict[str, Any]:
    assert decision in DECISIONS
    candidate_action = {
        "PROVISIONAL_KEEP": "HOLD",
        "FINAL_KEEP": "ADOPT",
        "REJECT": "DISCARD",
        "INCONCLUSIVE": "REVIEW",
    }[decision]
    canonical_action = "ADOPT" if decision == "FINAL_KEEP" else "NO_CHANGE"
    input_hash = sha256_json(data)
    result = {
        "contract_version": "RA-PSI-EVAL-V4",
        "decision_id": f"decision-{input_hash[:16]}",
        "experiment_id": data.get("experiment_id", "PROP-EXP-MEM-001"),
        "proposal_id": data.get("proposal_id", "PROP-EXP-MEM-001"),
        "decision": decision,
        "status": status,
        "reason_codes": reasons,
        "candidate_action": candidate_action,
        "canonical_state_action": canonical_action,
        "canonical_update_allowed": decision == "FINAL_KEEP",
        "canonical_rollback_required": False,
        "input_sha256": input_hash,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if is_sha256(data.get("pre_state_sha256")):
        result["from_state_sha256"] = data["pre_state_sha256"]
    if is_sha256(data.get("candidate_state_sha256")):
        result["candidate_state_sha256"] = data["candidate_state_sha256"]
    # A report dismissed by majority no longer blocks the decision, but it is
    # never silently forgotten: every result names the outputs it concerned.
    cards = data.get("evaluations", data.get("scorecards"))
    if isinstance(cards, list) and cards:
        try:
            dismissed = tally_fabrication_votes(cards, data.get("fabrication_confirmations", []))["dismissed"]
        except (KeyError, TypeError, AttributeError):
            dismissed = []
        if dismissed:
            result["dismissed_fabrication_outputs"] = dismissed
    return result


def rejection(data: dict[str, Any], reasons: list[str], summary: dict[str, Any] | None = None) -> dict[str, Any]:
    result = base_result(data, "REJECT", "REJECTED", reasons)
    result["score_summary"] = summary or {}
    result["rollback_note"] = (
        "Discard the candidate delta only. No already-adopted canonical state is rolled back by this gate."
    )
    return result


def inconclusive(
    data: dict[str, Any],
    reasons: list[str],
    status: str = "INCONCLUSIVE",
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = base_result(data, "INCONCLUSIVE", status, reasons)
    result["score_summary"] = summary or {}
    result["rollback_note"] = (
        "Hold the candidate for review or more evidence. Do not change canonical state."
    )
    return result


def tally_fabrication_votes(cards: list[dict[str, Any]], confirmations: Any) -> dict[str, Any]:
    """Count independent votes on every output a critical fabrication was reported on.

    A vote for comes from a scorer that reported the fabrication or a checker
    that confirmed it; a vote against comes from a checker that rejected it.
    Each evaluator counts once per output, and a scorer that reported a
    fabrication cannot also vote against it.

    Decision rule, per output (owner's decision, 2026-09-16):
    - two or more votes for: confirmed -> the candidate is rejected;
    - one vote for, two or more against: dismissed by majority;
    - one vote for, one against: a second independent checker is required;
    - one vote for, none against: an independent check is required.
    """
    votes_for: dict[str, set[str]] = defaultdict(set)
    votes_against: dict[str, set[str]] = defaultdict(set)
    details: dict[str, list[dict[str, Any]]] = defaultdict(list)
    errors: list[str] = []

    for card in cards:
        output_hash = str(card["output_sha256"])
        fabrications = normalized_fabrications(card)
        if fabrications:
            votes_for[output_hash].add(str(card["evaluator_id"]))
            details[output_hash].append(
                {"evaluator_id": card["evaluator_id"], "condition": card["condition"],
                 "pair_id": card["pair_id"], "fabrications": fabrications}
            )

    scored_outputs = {str(card["output_sha256"]) for card in cards}
    if not isinstance(confirmations, list):
        return {"errors": ["fabrication_confirmations must be a list"], "details": {}, "confirmed": [],
                "dismissed": [], "needs_second_check": [], "unconfirmed": []}
    for index, item in enumerate(confirmations):
        if not isinstance(item, dict):
            errors.append(f"confirmation[{index}] is not an object")
            continue
        output_hash = str(item.get("output_sha256", ""))
        checker = str(item.get("evaluator_id", "")).strip()
        if not is_sha256(output_hash) or output_hash not in scored_outputs:
            errors.append(f"confirmation[{index}] names an output that no scorecard evaluated")
            continue
        if not checker:
            errors.append(f"confirmation[{index}] has no evaluator_id")
            continue
        if not isinstance(item.get("confirms_fabrication"), bool):
            errors.append(f"confirmation[{index}] confirms_fabrication must be true or false")
            continue
        entry = {"evaluator_id": checker, "role": "fabrication_checker",
                 "confirms_fabrication": item["confirms_fabrication"], "reasoning": str(item.get("reasoning", ""))}
        details[output_hash].append(entry)
        if item["confirms_fabrication"]:
            votes_for[output_hash].add(checker)
        else:
            votes_against[output_hash].add(checker)

    confirmed, dismissed, needs_second_check, unconfirmed = [], [], [], []
    for output_hash, supporters in votes_for.items():
        against = votes_against.get(output_hash, set()) - supporters
        if len(supporters) >= 2:
            confirmed.append(output_hash)
        elif len(against) >= 2:
            dismissed.append(output_hash)
        elif len(against) == 1:
            needs_second_check.append(output_hash)
        else:
            unconfirmed.append(output_hash)
    return {"errors": errors, "details": details, "confirmed": confirmed, "dismissed": dismissed,
            "needs_second_check": needs_second_check, "unconfirmed": unconfirmed}


def adjudicate(data: dict[str, Any], requested_stage: str = "auto") -> dict[str, Any]:
    if not isinstance(data, dict):
        return inconclusive({"raw_input": data}, ["INPUT_NOT_OBJECT"])

    cards = data.get("evaluations", data.get("scorecards", []))
    if not isinstance(cards, list):
        return inconclusive(data, ["EVALUATIONS_NOT_ARRAY"])
    if not cards:
        return inconclusive(data, ["NO_EVALUATIONS"], status="EVALUATING")

    errors: list[str] = []
    identity_keys: set[tuple[str, str, str]] = set()
    for index, card in enumerate(cards):
        errors.extend(validate_card(card, index))
        if isinstance(card, dict):
            key = (
                str(card.get("pair_id", "")),
                str(card.get("condition", "")),
                str(card.get("evaluator_id", "")),
            )
            if key in identity_keys:
                errors.append(f"duplicate evaluator card for {key}")
            identity_keys.add(key)

    if errors:
        return inconclusive(data, ["INVALID_CARD_OR_PROVENANCE"], summary={"errors": errors})

    cfg = policy(data)
    if cfg["fabrication_rule"] not in {"any", "comparative"}:
        return inconclusive(data, ["UNKNOWN_FABRICATION_RULE"])
    tally = tally_fabrication_votes(cards, data.get("fabrication_confirmations", []))
    if tally["errors"]:
        return inconclusive(data, ["INVALID_FABRICATION_CONFIRMATION"], summary={"errors": tally["errors"]})
    details = tally["details"]
    condition_of = {str(card["output_sha256"]): str(card["condition"]) for card in cards}
    confirmed_by_condition = {"baseline": 0, "structured": 0}
    for output_hash in tally["confirmed"]:
        confirmed_by_condition[condition_of[output_hash]] += 1
    if tally["confirmed"] and cfg["fabrication_rule"] == "any":
        return rejection(
            data,
            ["CRITICAL_FABRICATION_CONFIRMED_BY_TWO_EVALUATORS"],
            {"confirmed_fabrication_outputs": tally["confirmed"], "details": details},
        )
    # Under the comparative rule every report must still be resolved first: an
    # unresolved report could change either count.
    if tally["needs_second_check"]:
        return inconclusive(
            data,
            ["CRITICAL_FABRICATION_REQUIRES_SECOND_CHECK"],
            summary={"disputed_fabrication_outputs": tally["needs_second_check"], "details": details},
        )
    if tally["unconfirmed"]:
        return inconclusive(
            data,
            ["CRITICAL_FABRICATION_REQUIRES_INDEPENDENT_CONFIRMATION"],
            summary={"unconfirmed_fabrication_outputs": tally["unconfirmed"], "details": details},
        )
    fabrication_summary = {"fabrication_rule": cfg["fabrication_rule"],
                           "confirmed_fabrications_by_condition": confirmed_by_condition,
                           "confirmed_fabrication_outputs": tally["confirmed"]}
    if confirmed_by_condition["structured"] > confirmed_by_condition["baseline"]:
        return rejection(data, ["STRUCTURED_CONDITION_HAS_MORE_CONFIRMED_FABRICATIONS"],
                         {**fabrication_summary, "details": details})

    grouped: dict[str, dict[str, dict[str, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for card in cards:
        grouped[str(card["pair_id"])][str(card["condition"])][str(card["evaluator_id"])] = card

    pair_results: list[dict[str, Any]] = []
    pair_problems: list[str] = []
    all_evaluator_ids: set[str] = set()
    evaluator_fingerprints: set[tuple[str, str]] = set()

    disagreeing_pairs: set[str] = set()
    for pair_id in sorted(grouped):
        pair = grouped[pair_id]
        baseline = pair.get("baseline", {})
        structured = pair.get("structured", {})
        overlap = sorted(set(baseline).intersection(structured))
        all_evaluator_ids.update(overlap)
        for evaluator_id in overlap:
            card = baseline[evaluator_id]
            evaluator_fingerprints.add((str(card["provider"]), str(card["model"])))

        if not baseline or not structured:
            pair_problems.append(f"{pair_id}:missing_condition")
            continue
        baseline_seeds = {int(baseline[evaluator_id]["seed"]) for evaluator_id in baseline}
        structured_seeds = {int(structured[evaluator_id]["seed"]) for evaluator_id in structured}
        if len(baseline_seeds) != 1 or len(structured_seeds) != 1 or baseline_seeds != structured_seeds:
            pair_problems.append(f"{pair_id}:paired_seed_mismatch")
            continue
        if len(overlap) < cfg["min_independent_evaluators"]:
            pair_problems.append(
                f"{pair_id}:requires_{cfg['min_independent_evaluators']}_independent_evaluators"
            )
            continue

        condition_means: dict[str, float] = {}
        disagreement: dict[str, float] = {}
        for condition, cards_by_evaluator in (("baseline", baseline), ("structured", structured)):
            values = [score_total(cards_by_evaluator[evaluator_id]) for evaluator_id in overlap]
            condition_means[condition] = sum(values) / len(values)
            disagreement[condition] = max(values) - min(values)
            if disagreement[condition] > cfg["max_evaluator_disagreement"]:
                disagreeing_pairs.add(pair_id)
                if cfg["max_disagreeing_pair_fraction"] <= 0:
                    pair_problems.append(
                        f"{pair_id}:{condition}:evaluator_disagreement_{disagreement[condition]:g}"
                    )

        pair_results.append(
            {
                "pair_id": pair_id,
                "evaluator_count": len(overlap),
                "baseline_mean": condition_means["baseline"],
                "structured_mean": condition_means["structured"],
                "paired_delta": condition_means["structured"] - condition_means["baseline"],
                "disagreement": disagreement,
            }
        )

    summary: dict[str, Any] = {
        "paired_trial_count": len(pair_results),
        "pair_problems": pair_problems,
        "evaluator_count": len(all_evaluator_ids),
        "evaluator_provider_model_count": len(evaluator_fingerprints),
        "confirmed_fabrications_by_condition": confirmed_by_condition,
        "fabrication_rule": cfg["fabrication_rule"],
        "disagreeing_pairs": sorted(disagreeing_pairs),
    }
    if cfg["max_disagreeing_pair_fraction"] > 0 and pair_results:
        # Disagreeing pairs stay in the analysis (their score is the evaluators'
        # mean); only a larger share than pre-registered makes it inconclusive.
        if len(disagreeing_pairs) / len(pair_results) > cfg["max_disagreeing_pair_fraction"]:
            pair_problems.append(
                "evaluator_disagreement_in_%d_of_%d_pairs" % (len(disagreeing_pairs), len(pair_results))
            )
    if pair_problems:
        return inconclusive(data, ["INCOMPLETE_OR_DISAGREEING_PAIRS"], summary=summary)

    if not pair_results:
        return inconclusive(data, ["NO_COMPLETE_PAIRED_TRIALS"], summary=summary)

    deltas = [float(pair["paired_delta"]) for pair in pair_results]
    baselines = [float(pair["baseline_mean"]) for pair in pair_results]
    structured_scores = [float(pair["structured_mean"]) for pair in pair_results]
    mean_delta = sum(deltas) / len(deltas)
    mean_baseline = sum(baselines) / len(baselines)
    mean_structured = sum(structured_scores) / len(structured_scores)
    if len(deltas) > 1:
        variance = sum((value - mean_delta) ** 2 for value in deltas) / (len(deltas) - 1)
        sample_std = math.sqrt(variance)
        standard_error = sample_std / math.sqrt(len(deltas))
    else:
        sample_std = 0.0
        standard_error = 0.0
    lower_95 = mean_delta - 1.96 * standard_error
    summary.update(
        {
            "mean_baseline": mean_baseline,
            "mean_structured": mean_structured,
            "mean_delta": mean_delta,
            "sample_std_delta": sample_std,
            "standard_error_delta": standard_error,
            "lower_95_bound_delta": lower_95,
            "pair_results": pair_results,
            "required_mean_improvement": cfg["minimum_mean_improvement"],
            "required_lower_95_bound": cfg["minimum_lower_95_bound"],
        }
    )

    if mean_delta < cfg["minimum_mean_improvement"]:
        return rejection(data, ["MEAN_IMPROVEMENT_BELOW_THRESHOLD"], summary)
    if lower_95 <= cfg["minimum_lower_95_bound"]:
        return rejection(data, ["LOWER_95_BOUND_BELOW_THRESHOLD"], summary)

    stage = stage_name(data, requested_stage)
    if stage == "pilot":
        if len(pair_results) < cfg["provisional_min_paired_trials"]:
            return inconclusive(data, ["INSUFFICIENT_PILOT_PAIRS"], status="EVALUATING", summary=summary)
        result = base_result(data, "PROVISIONAL_KEEP", "PROVISIONAL_KEEP", [])
        result["score_summary"] = summary
        result["next_stage"] = "REPLICATING"
        result["replication_requirements"] = {
            "minimum_paired_trials": cfg["final_min_paired_trials"],
            "minimum_generation_models": cfg["final_min_generation_models"],
            "minimum_evaluator_providers": cfg["final_min_evaluator_providers"],
            "holdout_required": cfg["final_requires_holdout"],
            "regression_suite_required": cfg["final_requires_regression_suite"],
            "calibration_required": cfg["final_requires_calibration"],
        }
        return result

    final_problems: list[str] = []
    if len(pair_results) < cfg["final_min_paired_trials"]:
        final_problems.append("FINAL_REPLICATION_PAIR_COUNT_NOT_REACHED")

    trials = data.get("trials", [])
    generation_models = {
        (str(trial.get("generation_provider", "")), str(trial.get("generation_model", "")))
        for trial in trials
        if isinstance(trial, dict) and trial.get("generation_model")
    }
    if generation_models and len(generation_models) < cfg["final_min_generation_models"]:
        final_problems.append("GENERATION_MODEL_DIVERSITY_NOT_REACHED")
    elif not generation_models:
        final_problems.append("GENERATION_MODEL_PROVENANCE_MISSING")

    if len(evaluator_fingerprints) < cfg["final_min_evaluator_providers"]:
        final_problems.append("EVALUATOR_DIVERSITY_NOT_REACHED")

    holdout_passed = data.get("holdout_passed") is True
    if cfg["final_requires_holdout"] and not holdout_passed:
        final_problems.append("HOLDOUT_GATE_NOT_PASSED")

    regression_results = data.get("regression_results")
    if isinstance(regression_results, list) and any(
        isinstance(item, dict) and item.get("passed") is False for item in regression_results
    ):
        return rejection(data, ["REGRESSION_GATE_FAILED"], summary)
    if cfg["final_requires_regression_suite"] and not (
        data.get("regression_passed") is True
        or isinstance(regression_results, list)
        and bool(regression_results)
        and all(item.get("passed") is True for item in regression_results if isinstance(item, dict))
    ):
        final_problems.append("REGRESSION_GATE_NOT_PASSED")

    calibration = data.get("calibration_passed") is True
    if cfg["final_requires_calibration"] and not calibration:
        final_problems.append("CALIBRATION_GATE_NOT_PASSED")

    if final_problems:
        return inconclusive(data, final_problems, status="REPLICATING", summary=summary)

    result = base_result(data, "FINAL_KEEP", "FINAL_KEEP", [])
    result["score_summary"] = summary
    result["provenance_required_for_state_delta"] = [
        "protocol_sha256",
        "prompt_sha256",
        "state_sha256",
        "output_sha256",
        "scorecard_sha256",
        "decision_id",
    ]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="evaluation packet JSON")
    parser.add_argument("--output", type=Path, help="optional decision JSON output")
    parser.add_argument(
        "--stage",
        choices=("auto", "pilot", "replication"),
        default="auto",
        help="evidence stage; auto reads the packet stage",
    )
    parser.add_argument("--fail-on-reject", action="store_true")
    parser.add_argument("--fail-on-inconclusive", action="store_true")
    args = parser.parse_args(argv)

    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"decision": "INCONCLUSIVE", "reason": str(exc)}), file=sys.stderr)
        return 2

    result = adjudicate(data, args.stage)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if args.fail_on_reject and result["decision"] == "REJECT":
        return 3
    if args.fail_on_inconclusive and result["decision"] == "INCONCLUSIVE":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
