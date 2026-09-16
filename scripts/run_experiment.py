#!/usr/bin/env python3
"""Run a pre-registered experiment from frozen inputs to a verdict, unattended.

MEM-001 and MEM-002 each took days of relays: a manifest built by hand, trials
restarted after the local model ran out of memory, packets built, prompts
copied, evaluators replaced. Every step already had a script; nothing chained
them, so every transition waited for a person.

This script chains them. Each step is idempotent and checks the previous one:

1. manifest   — built from the experiment's evaluation_policy.json
                ("generation" block) unless one is already frozen;
2. trials     — generated through the API adapter; existing outputs are kept;
3. leak scan  — duplicates or condition labels stop the run before blinding;
4. packets    — shuffled blind packets and the private condition map;
5. evaluation — scorer ladder, fabrication checks, adjudication.

It can run on this machine or in GitHub Actions: keys are named in a private
configuration by file or by environment variable, never in the experiment.
Whatever happens, results/run-report.json says how far the run got and why it
stopped.

Example:
  python scripts/run_experiment.py --experiment PROP-EXP-MEM-003 --config ~/.ra-psi/run-config.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import create_experiment_manifest  # noqa: E402
import run_blind_trials  # noqa: E402
from evaluate_experiment import load_policy, run_evaluation  # noqa: E402

GENERATION_FIELDS = {"provider", "model", "endpoint", "key", "temperature", "max_output_tokens", "timeout_seconds",
                     "extra_body", "seeds", "baseline_state", "structured_state", "protocol"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generation_spec(policy: dict) -> dict:
    spec = policy.get("generation")
    if not isinstance(spec, dict):
        raise SystemExit("evaluation_policy.json has no generation block")
    unknown = sorted(set(spec) - GENERATION_FIELDS)
    missing = sorted({"provider", "model", "endpoint", "seeds", "baseline_state", "structured_state", "protocol"} - set(spec))
    if unknown or missing:
        raise SystemExit("generation block: unknown %s, missing %s" % (unknown, missing))
    return spec


def ensure_manifest(experiment: Path, spec: dict) -> dict:
    path = experiment / "results" / "experiment-manifest.json"
    if path.is_file():
        return {"step": "manifest", "status": "kept frozen manifest"}
    manifest = create_experiment_manifest.build_manifest(
        ROOT, spec["provider"], spec["model"], experiment_id=experiment.name,
        baseline_name=spec["baseline_state"], structured_name=spec["structured_state"],
        protocol_name=spec["protocol"], seeds=tuple(int(seed) for seed in spec["seeds"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"step": "manifest", "status": "created", "trials": len(manifest["trials"])}


def key_location(private: dict, name: str | None) -> dict:
    if not name:
        return {}
    location = private.get("keys", {}).get(name)
    if not location:
        raise SystemExit("no key location configured for %r" % name)
    return location


def run_trials(experiment: Path, spec: dict, private: dict) -> dict:
    location = key_location(private, spec.get("key"))
    args = argparse.Namespace(
        root=ROOT, manifest=experiment / "results" / "experiment-manifest.json", condition="all",
        provider=spec["provider"], model=spec["model"], endpoint=spec["endpoint"],
        temperature=float(spec.get("temperature", 0.8)), max_output_tokens=int(spec.get("max_output_tokens", 2048)),
        timeout_seconds=int(spec.get("timeout_seconds", 300)), think=None, dry_run=False, overwrite=False,
        retries=8, min_free_mb=0, memory_wait_seconds=0, resume=True,
        api_key_env=location.get("api_key_env", ""), api_key_file=location.get("api_key_file", ""),
        extra_body=spec.get("extra_body"))
    run_blind_trials.run(args)
    manifest = json.loads((experiment / "results" / "experiment-manifest.json").read_text(encoding="utf-8"))
    missing = [trial["trial_id"] for trial in manifest["trials"]
               if not (ROOT / trial["output_path"]).is_file() or (ROOT / trial["output_path"]).stat().st_size == 0]
    return {"step": "trials", "status": "complete" if not missing else "incomplete",
            "total": len(manifest["trials"]), "missing": missing}


def script(name: str, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / name), *arguments], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=ROOT)


def leak_scan(experiment: Path) -> dict:
    result = script("scan_packet_leaks.py", "--experiment", experiment.name)
    try:
        detail = json.loads(result.stdout)
    except json.JSONDecodeError:
        detail = {"stdout": result.stdout[-500:], "stderr": result.stderr[-500:]}
    # The per-trial rows name conditions; only the aggregate goes in the report.
    return {"step": "leak_scan", "status": "clear" if result.returncode == 0 else "blocked",
            "duplicates": detail.get("duplicate_outputs"), "strong_leak_count": len(detail.get("strong_leaks") or []),
            "missing_outputs": detail.get("missing_outputs")}


def build_packets(experiment: Path) -> dict:
    results = experiment / "results"
    packets = results / "blind_packets"
    if (packets / "packet-manifest.json").is_file() and (results / "condition-map.private.json").is_file():
        return {"step": "packets", "status": "kept existing packets"}
    result = script("build_blind_packets.py", "--manifest", str(results / "experiment-manifest.json"),
                    "--public-dir", str(packets), "--private-map", str(results / "condition-map.private.json"))
    if result.returncode != 0:
        return {"step": "packets", "status": "failed", "error": (result.stderr or result.stdout)[-500:]}
    return {"step": "packets", "status": "built"}


def run(experiment_name: str, config_path: Path) -> dict:
    experiment = ROOT / "experiments" / experiment_name
    policy = load_policy(experiment)
    private = json.loads(config_path.expanduser().read_text(encoding="utf-8"))
    report = {"record_version": "RA-PSI-RUN-REPORT-V1", "experiment_id": experiment_name,
              "started_at_utc": now(), "steps": []}

    def finish(status: str) -> dict:
        report["status"] = status
        report["finished_at_utc"] = now()
        target = experiment / "results" / "run-report.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return report

    spec = generation_spec(policy)
    report["steps"].append(ensure_manifest(experiment, spec))
    step = run_trials(experiment, spec, private)
    report["steps"].append(step)
    if step["status"] != "complete":
        return finish("STOPPED_TRIALS_INCOMPLETE")
    step = leak_scan(experiment)
    report["steps"].append(step)
    if step["status"] != "clear":
        return finish("STOPPED_LEAK_OR_DUPLICATE")
    step = build_packets(experiment)
    report["steps"].append(step)
    if step["status"] == "failed":
        return finish("STOPPED_PACKETS_FAILED")
    evaluation, code = run_evaluation(experiment_name, config_path, max_tokens=8000)
    report["steps"].append({"step": "evaluation", "status": evaluation.get("status", "ran"),
                            "scoring": [{k: v for k, v in item.items() if k != "detail"} for item in evaluation.get("scoring", [])],
                            "decision": evaluation.get("final_decision"),
                            "reason_codes": evaluation.get("final_reason_codes")})
    if code != 0:
        return finish("STOPPED_EVALUATION_REFUSED")
    return finish("DECIDED" if evaluation.get("final_decision") not in (None, "NOT_ADJUDICATED") else "NOT_ADJUDICATED")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--config", type=Path, required=True, help="private file naming where each key is")
    args = parser.parse_args()
    report = run(args.experiment, args.config)
    print(json.dumps({"status": report["status"], "steps": [s["step"] + ": " + str(s["status"]) for s in report["steps"]]},
                     indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["status"] in ("DECIDED",) else 1)


if __name__ == "__main__":
    main()
