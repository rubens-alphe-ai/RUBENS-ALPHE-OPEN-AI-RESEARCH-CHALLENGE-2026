#!/usr/bin/env python3
"""Run independent blind trials from a frozen experiment manifest.

The runner creates one fresh adapter request per trial, uses the paired seed
from the manifest, and saves the model answer unchanged.  It never scores an
answer and never updates canonical state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from model_adapter import AdapterConfig, AdapterError, build_adapter


DEFAULT_ENDPOINTS = {
    "ollama": "http://127.0.0.1:11434/api/chat",
    "openai-compatible": "https://api.deepseek.com/v1/chat/completions",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prompt_for(root: Path, trial: dict[str, object], prompt_path: Path) -> str:
    state_path = root / str(trial["state_path"])
    # Deliberately provide only the state and the fixed prompt.  Do not add the
    # condition label, prior answers, scores or expected result.
    return state_path.read_text(encoding="utf-8") + "\n\n" + prompt_path.read_text(encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    trials = manifest.get("trials", [])
    selected = [
        trial
        for trial in trials
        if args.condition == "all" or trial.get("condition") == args.condition
    ]
    prompt_path = root / "experiments" / str(manifest["experiment_id"]) / "TEST_PROMPT.md"

    config = AdapterConfig(
        provider=args.provider,
        model=args.model,
        endpoint=args.endpoint,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        timeout_seconds=args.timeout_seconds,
        think=args.think,
        api_key_env=args.api_key_env,
        api_key_file=args.api_key_file,
    )

    if args.dry_run:
        print(json.dumps({"selected_trials": selected, "dry_run": True}, indent=2, ensure_ascii=False))
        return 0

    adapter = build_adapter(config)
    for trial in selected:
        output_path = root / str(trial["output_path"])
        metadata_path = output_path.with_suffix(".metadata.json")
        if output_path.exists() and not args.overwrite:
            if args.resume:
                # A completed raw output is frozen evidence: resuming skips it,
                # it never regenerates it.
                print(json.dumps({"trial_id": trial["trial_id"], "skipped": "already generated"}))
                continue
            raise FileExistsError(f"Refusing to overwrite existing raw output: {output_path}")
        stale_error = output_path.with_suffix(".error.json")
        prompt = prompt_for(root, trial, prompt_path)
        try:
            content = adapter.generate(prompt, int(trial["seed"]))
        except AdapterError as exc:
            error_path = output_path.with_suffix(".error.json")
            error_path.write_text(
                json.dumps(
                    {
                        "trial_id": trial["trial_id"],
                        "pair_id": trial["pair_id"],
                        "condition": trial["condition"],
                        "provider": args.provider,
                        "model": args.model,
                        "error": str(exc),
                        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"ERROR {trial['trial_id']}: {exc}")
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        if stale_error.exists():
            # Keep the failed attempt as a record instead of deleting it.
            stale_error.rename(stale_error.with_name(stale_error.name.replace(".error.json", ".failed-attempt.json")))
        metadata = {
            "record_version": "RA-PSI-RAW-TRIAL-V1",
            "experiment_id": manifest["experiment_id"],
            "trial_id": trial["trial_id"],
            "pair_id": trial["pair_id"],
            "seed": trial["seed"],
            "condition": trial["condition"],
            "provider": args.provider,
            "model": args.model,
            "generation_settings": {
                "temperature": args.temperature,
                "max_output_tokens": args.max_output_tokens,
                "think": args.think,
            },
            "protocol_sha256": trial["protocol_sha256"],
            "prompt_sha256": trial["prompt_sha256"],
            "state_sha256": trial["state_sha256"],
            "output_sha256": file_sha256(output_path),
            "executed_at_utc": datetime.now(timezone.utc).isoformat(),
            "fresh_session_required": True,
            "scored": False,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"trial_id": trial["trial_id"], "output_sha256": metadata["output_sha256"]}))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "experiments" / "PROP-EXP-MEM-001" / "results" / "experiment-manifest.json",
    )
    parser.add_argument("--condition", choices=("all", "baseline", "structured"), default="all")
    parser.add_argument("--provider", default="ollama", choices=("ollama", "openai-compatible"))
    parser.add_argument(
        "--api-key-env",
        default="",
        help="name of the environment variable holding the API key (never the key itself)",
    )
    parser.add_argument(
        "--api-key-file",
        default="",
        help="path to a file holding the API key; keep it outside this tree",
    )
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument(
        "--endpoint",
        default="",
        help="chat endpoint; defaults per provider when omitted",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", type=int, default=2048)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument(
        "--think",
        dest="think",
        action="store_true",
        default=False,
        help="keep the reasoning channel enabled (off by default: reasoning models otherwise spend the whole budget before answering)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip trials whose raw output already exists and run only the missing ones",
    )
    args = parser.parse_args()
    if not args.endpoint:
        args.endpoint = DEFAULT_ENDPOINTS[args.provider]
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
