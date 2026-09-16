#!/usr/bin/env python3
"""Validate RA-PSI machine-readable artifacts without accepting evidence.

This is intentionally dependency-free so it can run locally and in GitHub
Actions.  It checks structure, mirrors and provenance shape; it does not
semantic-score model answers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from adjudicate_evaluations import validate_card


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path, errors: list[str]) -> object | None:
    if not path.is_file():
        errors.append(f"missing JSON artifact: {path.relative_to(ROOT)}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
        return None


def validate(errors: list[str], warnings: list[str]) -> None:
    state_path = ROOT / "state" / "latest-state.json"
    public_state_path = ROOT / "docs" / "api" / "latest-state.json"
    state = read_json(state_path, errors)
    public_state = read_json(public_state_path, errors)
    read_json(ROOT / "docs" / "api" / "next-unsolved-problem.json", errors)

    if state is not None and public_state is not None and state != public_state:
        errors.append("state/latest-state.json and docs/api/latest-state.json differ")

    for schema in (
        "evaluator-scorecard.schema.json",
        "evaluator-contract-v4.schema.json",
        "experiment-registry.schema.json",
        "model-adapter.schema.json",
        "memory-v2.schema.json",
        "state-delta.schema.json",
        "rapc-task-envelope.schema.json",
        "rapc-response-envelope.schema.json",
        "rapc-ledger-event.schema.json",
    ):
        read_json(ROOT / "schemas" / schema, errors)

    experiment = ROOT / "experiments" / "PROP-EXP-MEM-001"
    manifest_path = experiment / "results" / "experiment-manifest.json"
    if manifest_path.is_file():
        manifest = read_json(manifest_path, errors)
        if isinstance(manifest, dict):
            trials = manifest.get("trials")
            if not isinstance(trials, list) or len(trials) != 6:
                errors.append("experiment manifest must contain exactly six trials")
            else:
                keys = {(t.get("pair_id"), t.get("condition")) for t in trials if isinstance(t, dict)}
                if len(keys) != 6:
                    errors.append("experiment manifest contains duplicate pair/condition entries")
                for pair_id in sorted({t.get("pair_id") for t in trials if isinstance(t, dict)}):
                    pair = [t for t in trials if isinstance(t, dict) and t.get("pair_id") == pair_id]
                    if {t.get("condition") for t in pair} != {"baseline", "structured"}:
                        errors.append(f"manifest pair {pair_id} is not baseline/structured")
                    seeds = {t.get("seed") for t in pair}
                    if len(seeds) != 1:
                        errors.append(f"manifest pair {pair_id} does not share one seed")
    else:
        warnings.append("no experiment manifest yet; run create_experiment_manifest.py")

    evaluation_path = experiment / "results" / "evaluations.json"
    if evaluation_path.is_file():
        packet = read_json(evaluation_path, errors)
        if isinstance(packet, dict):
            cards = packet.get("evaluations", packet.get("scorecards", []))
            if not isinstance(cards, list):
                errors.append("evaluations.json evaluations must be an array")
            else:
                for index, card in enumerate(cards):
                    errors.extend(validate_card(card, index))
    else:
        warnings.append("no independent evaluation packet yet; canonical adoption remains blocked")

    memory = read_json(experiment / "STRUCTURED_MEMORY_V2_PROPOSAL.json", errors)
    if isinstance(memory, dict):
        required_memory_sections = {
            "schema_version",
            "verified_knowledge",
            "decisions",
            "failures",
            "experiments",
            "open_questions",
            "next_actions",
            "confidence_map",
            "provenance",
        }
        missing_memory = sorted(required_memory_sections.difference(memory))
        if missing_memory:
            errors.append("structured memory V2 missing: " + ", ".join(missing_memory))

    registry = read_json(ROOT / "experiments" / "registry.json", errors)
    if isinstance(registry, dict) and registry.get("registry_version") != "RA-PSI-REGISTRY-V1":
        errors.append("experiment registry has an unexpected version")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    validate(errors, warnings)
    result = {
        "ok": not errors,
        "root": str(ROOT),
        "errors": errors,
        "warnings": warnings,
        "canonical_adoption_allowed_by_validator": False,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
