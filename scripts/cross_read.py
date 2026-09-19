#!/usr/bin/env python3
"""Read the same frozen handoffs again with another reader, and compare.

A measured difference should belong to what was written, not to who read it.
MEM-006 showed why this matters: its pre-registered reader failed, the ladder's
next rung happened to be the model that had written every handoff, and a model
reading its own writing is not an independent judge of it.

This reads an experiment's existing, frozen handoffs with a reader you name,
grades them against the same frozen key, and applies the same decision rule. It
writes into its own folder and never touches the experiment's recorded verdict:
a cross-read is a robustness check, not a replacement, unless the experiment's
own protocol says otherwise.

Example:
  python scripts/cross_read.py --experiment PROP-EXP-MEM-006 \\
      --model deepseek/deepseek-v4.1-flash --key openrouter \\
      --config ~/.ra-psi/run-config.json --label deepseek
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_quiz as hq  # noqa: E402
from evaluate_experiment import AdapterError, call, load_policy, sha256_text  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_trial(trial: dict, entry: dict, quiz: dict, rendered: list[dict], key: dict[str, str], out: Path) -> dict:
    stored = out / ("%s.json" % trial["trial_id"])
    if stored.is_file():
        return json.loads(stored.read_text(encoding="utf-8"))
    handoff = (ROOT / trial["output_path"]).read_text(encoding="utf-8")
    prompt = hq.reader_prompt(quiz, rendered, handoff)
    record = {"trial_id": trial["trial_id"], "pair_id": trial["pair_id"], "condition": trial["condition"],
              "reader_id": entry["evaluator_id"], "handoff_sha256": sha256_text(handoff), "read_at_utc": now()}
    try:
        content, served = call(entry, prompt, int(entry.get("max_tokens", 2000)))
    except AdapterError as exc:
        record["error"] = str(exc)[:300]
        return record
    answers, problems = hq.parse_answers(content, [item["id"] for item in rendered])
    if not answers:
        record["error"] = "reader returned no usable answer"
        return record
    record.update(served_model=served, answers=answers, problems=problems,
                  grade=hq.grade(answers, key, rendered))
    stored.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def decide_from(records: list[dict], rule: dict) -> dict:
    pairs: dict[str, dict] = {}
    for record in records:
        if "grade" in record:
            pairs.setdefault(record["pair_id"], {"pair_id": record["pair_id"]})[record["condition"]] = record["grade"]
    complete = sorted((pair for pair in pairs.values() if "baseline" in pair and "structured" in pair),
                      key=lambda pair: pair["pair_id"])
    return hq.decide(complete, rule)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--key", required=True, help="name of the key entry in the private config")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--label", required=True, help="folder name for this reading, e.g. deepseek")
    parser.add_argument("--endpoint", default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--max-tokens", type=int, default=2000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--extra-body", default='{"reasoning": {"effort": "low"}}')
    args = parser.parse_args()

    experiment = ROOT / "experiments" / args.experiment
    results = experiment / "results"
    policy = load_policy(experiment)
    quiz = json.loads((experiment / policy["quiz"]["file"]).read_text(encoding="utf-8"))
    rendered, key = hq.render_quiz(quiz, args.experiment + ":" + quiz["quiz_version"])
    stored_key = json.loads((results / "quiz" / "answer-key.json").read_text(encoding="utf-8"))["key"]
    if stored_key != key:
        raise SystemExit("the rendered key differs from the one used by the experiment; refusing to compare")

    private = json.loads(args.config.expanduser().read_text(encoding="utf-8"))
    location = private.get("keys", {}).get(args.key)
    if not location:
        raise SystemExit("no key location configured for %r" % args.key)
    entry = {"evaluator_id": "cross-" + args.label, "provider": args.key, "model": args.model,
             "endpoint": args.endpoint, "json_mode": False, "max_tokens": args.max_tokens,
             "extra_body": json.loads(args.extra_body),
             **{k: v for k, v in location.items() if k in ("api_key_file", "api_key_env")}}

    manifest = json.loads((results / "experiment-manifest.json").read_text(encoding="utf-8"))
    out = results / ("cross-read-" + args.label)
    out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        records = list(pool.map(lambda trial: read_trial(trial, entry, quiz, rendered, key, out), manifest["trials"]))

    failed = [record for record in records if "grade" not in record]
    decision = decide_from(records, policy["quiz"])
    decision.update(record_version="RA-PSI-CROSS-READ-V1", experiment_id=args.experiment, reader=args.model,
                    generator_model=policy["generation"]["model"], read_at_utc=now(),
                    status="exploratory unless the protocol names this reader",
                    trials_read=len(records) - len(failed), trials_failed=len(failed))
    (out / "decision.json").write_text(json.dumps(decision, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"reader": args.model, "read": decision["trials_read"], "failed": decision["trials_failed"],
                      "decision": decision["decision"], "summary": decision.get("summary")}, indent=2))


if __name__ == "__main__":
    main()
