#!/usr/bin/env python3
"""Run a handoff-quiz experiment end to end: generate, read, grade, decide.

Stage 1 reuses run_experiment.py's generation (manifest, API trials, resume).
Stage 2 gives each handoff, alone, to a reader model with the frozen quiz, and
grades the letters against the key (see handoff_quiz.py). No judge model and no
blinding step are involved: the reader is never told a condition, and grading is
a comparison of letters that anyone can rerun from results/quiz/.

Example:
  python scripts/run_quiz_experiment.py --experiment PROP-EXP-MEM-004 --config ~/.ra-psi/run-config.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import handoff_quiz as hq  # noqa: E402
import run_experiment as rx  # noqa: E402
from evaluate_experiment import AdapterError, call, load_policy, pause_before_next, sha256_text  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reader_entry(policy: dict, private: dict) -> dict:
    reader = dict(policy["reader"])
    reader.update({k: v for k, v in rx.key_location(private, reader.pop("key")).items() if k in ("api_key_file", "api_key_env")})
    reader.setdefault("json_mode", False)
    return reader


def read_one(entry: dict, prompt: str, ids: list[str], limits: dict, pause: float, out: Path, retries: int = 1) -> dict:
    """Ask the reader, parse, retry once on an unusable answer; keep every attempt."""
    record = {"attempts": []}
    for attempt in range(retries + 1):
        time.sleep(pause_before_next(limits, prompt, pause) if limits else 0)
        try:
            content, served = call(entry, prompt, int(entry.get("max_tokens", 2000)), limits)
        except AdapterError as exc:
            record["attempts"].append({"error": str(exc)[:300]})
            continue
        answers, problems = hq.parse_answers(content, ids)
        raw_name = "%s.attempt%d.raw.txt" % (out.stem, attempt + 1)
        (out.parent / raw_name).write_text(content, encoding="utf-8")
        record["attempts"].append({"raw": raw_name, "response_sha256": sha256_text(content), "served_model": served,
                                   "problems": problems})
        if answers:
            # A partial answer is graded with its gaps counted as wrong; an
            # answer with no usable letters is not graded at all.
            record["answers"] = answers
        if not problems:
            break
    return record


def run(experiment_name: str, config_path: Path) -> dict:
    experiment = ROOT / "experiments" / experiment_name
    results = experiment / "results"
    policy = load_policy(experiment)
    private = json.loads(config_path.expanduser().read_text(encoding="utf-8"))
    report = {"record_version": "RA-PSI-RUN-REPORT-V1", "experiment_id": experiment_name, "design": "handoff_quiz",
              "started_at_utc": now(), "steps": []}

    def finish(status: str) -> dict:
        report.update(status=status, finished_at_utc=now())
        (results / "run-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return report

    spec = rx.generation_spec(policy)
    report["steps"].append(rx.ensure_manifest(experiment, spec))
    step = rx.run_trials(experiment, spec, private)
    report["steps"].append(step)
    if step["status"] != "complete":
        return finish("STOPPED_TRIALS_INCOMPLETE")

    quiz_cfg = policy["quiz"]
    quiz = json.loads((experiment / quiz_cfg["file"]).read_text(encoding="utf-8"))
    rendered, key = hq.render_quiz(quiz, experiment_name + ":" + quiz["quiz_version"])
    ids = [item["id"] for item in rendered]
    quiz_dir = results / "quiz"
    quiz_dir.mkdir(parents=True, exist_ok=True)
    (quiz_dir / "answer-key.json").write_text(json.dumps({"key": key, "rendered": rendered}, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")

    manifest = json.loads((results / "experiment-manifest.json").read_text(encoding="utf-8"))
    trials = list(manifest["trials"])
    random.Random(hq.seed_from(manifest["protocol_sha256"])).shuffle(trials)  # reading order hides pairing
    entry = reader_entry(policy, private)
    limits: dict = {}
    graded, failures = {}, []
    for trial in trials:
        out = quiz_dir / ("%s.json" % trial["trial_id"])
        if out.is_file():
            record = json.loads(out.read_text(encoding="utf-8"))
        else:
            handoff = (ROOT / trial["output_path"]).read_text(encoding="utf-8")
            prompt = hq.reader_prompt(quiz, rendered, handoff)
            record = read_one(entry, prompt, ids, limits, float(policy.get("default_batch_pause_seconds", 20)), out)
            if "answers" not in record:
                failures.append(trial["trial_id"])
                continue  # nothing stored: a later run asks again
            record.update(trial_id=trial["trial_id"], pair_id=trial["pair_id"], condition=trial["condition"],
                          prompt_sha256=sha256_text(prompt), read_at_utc=now(),
                          grade=hq.grade(record["answers"], key, rendered))
            out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        graded[trial["trial_id"]] = record
    report["steps"].append({"step": "reading", "status": "complete" if not failures else "incomplete",
                            "read": len(graded), "failed": failures})
    if failures:
        return finish("STOPPED_READING_INCOMPLETE")

    pairs: dict[str, dict] = {}
    for record in graded.values():
        pairs.setdefault(record["pair_id"], {"pair_id": record["pair_id"]})[record["condition"]] = record["grade"]
    complete = [pair for pair in pairs.values() if "baseline" in pair and "structured" in pair]
    decision = hq.decide(sorted(complete, key=lambda p: p["pair_id"]), quiz_cfg)
    decision.update(record_version="RA-PSI-QUIZ-DECISION-V1", experiment_id=experiment_name, decided_at_utc=now(),
                    rule={k: quiz_cfg[k] for k in ("keep_min_delta_pp", "invention_margin")},
                    reader_model=entry["model"], generator_model=spec["model"])
    (results / "decision.json").write_text(json.dumps(decision, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["steps"].append({"step": "decision", "status": decision["decision"], "reason_codes": decision["reason_codes"]})
    return finish("DECIDED")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.experiment, args.config)
    print(json.dumps({"status": report["status"], "steps": [s["step"] + ": " + str(s["status"]) for s in report["steps"]]}, indent=2))
    raise SystemExit(0 if report["status"] == "DECIDED" else 1)


if __name__ == "__main__":
    main()
