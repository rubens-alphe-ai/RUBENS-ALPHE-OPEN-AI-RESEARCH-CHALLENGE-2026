#!/usr/bin/env python3
"""Create a reproducible paired-trial manifest without running a model.

The manifest freezes the protocol, prompt and state hashes before generation.
It contains no model answers and does not claim that any trial was executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


SEEDS = (101, 202, 303)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    root: Path,
    provider: str,
    model: str,
    experiment_id: str = "PROP-EXP-MEM-001",
    baseline_name: str = "BASELINE_STATE.json",
    structured_name: str = "STRUCTURED_MEMORY_V1.json",
    protocol_name: str = "RUN_INSTRUCTIONS.md",
    seeds: tuple[int, ...] = SEEDS,
) -> dict[str, object]:
    experiment = root / "experiments" / experiment_id
    results = experiment / "results"
    protocol = experiment / protocol_name
    prompt = experiment / "TEST_PROMPT.md"
    baseline = experiment / baseline_name
    structured = experiment / structured_name
    required = (protocol, prompt, baseline, structured)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing experiment inputs: " + ", ".join(missing))

    protocol_hash = file_sha256(protocol)
    prompt_hash = file_sha256(prompt)
    state_hashes = {
        "baseline": file_sha256(baseline),
        "structured": file_sha256(structured),
    }
    trials: list[dict[str, object]] = []
    for seed in seeds:
        pair_id = f"pair-{seed}"
        for condition, state_path in (("baseline", baseline), ("structured", structured)):
            trial_id = f"{condition}-{seed}"
            output_name = f"{condition}_trial_{seeds.index(seed) + 1:02d}.txt"
            trials.append(
                {
                    "trial_id": trial_id,
                    "pair_id": pair_id,
                    "seed": seed,
                    "condition": condition,
                    "state_path": str(state_path.relative_to(root)).replace("\\", "/"),
                    "output_path": str((results / output_name).relative_to(root)).replace("\\", "/"),
                    "protocol_sha256": protocol_hash,
                    "prompt_sha256": prompt_hash,
                    "state_sha256": state_hashes[condition],
                    "generation_provider": provider,
                    "generation_model": model,
                    "executed": False,
                }
            )

    return {
        "manifest_version": "RA-PSI-TRIAL-MANIFEST-V1",
        "experiment_id": experiment_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": protocol_hash,
        "prompt_sha256": prompt_hash,
        "generation": {
            "provider": provider,
            "model": model,
            "paired_seeds": list(seeds),
            "fresh_session_per_trial": True,
            "same_settings_across_conditions": True,
            "condition_label_in_prompt": False,
            # Local Ollama honours `seed`; hosted OpenAI-compatible providers
            # accept it without guaranteeing determinism.  Recorded so the
            # seeds are never over-claimed as a reproducibility guarantee.
            "seed_guarantees_determinism": provider == "ollama",
            "seed_role": (
                "deterministic sampling seed"
                if provider == "ollama"
                else "pairing label only; hosted sampling is best-effort"
            ),
        },
        "trials": trials,
        "status": "MANIFEST_ONLY_NO_TRIALS_EXECUTED",
        "next_step": "Run scripts/run_blind_trials.py, then collect independent scorecards.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--experiment", default="PROP-EXP-MEM-001")
    parser.add_argument("--baseline-state", default="BASELINE_STATE.json")
    parser.add_argument("--structured-state", default="STRUCTURED_MEMORY_V1.json")
    parser.add_argument("--protocol", default="RUN_INSTRUCTIONS.md")
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in SEEDS))
    args = parser.parse_args()
    seeds = tuple(int(value) for value in args.seeds.split(","))
    manifest = build_manifest(
        args.root,
        args.provider,
        args.model,
        experiment_id=args.experiment,
        baseline_name=args.baseline_state,
        structured_name=args.structured_state,
        protocol_name=args.protocol,
        seeds=seeds,
    )
    output = args.output or args.root / "experiments" / args.experiment / "results" / "experiment-manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(output), "trial_count": len(manifest["trials"]), "status": manifest["status"]}, indent=2))


if __name__ == "__main__":
    main()
